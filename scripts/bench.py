"""Small workload harness. Cloud orchestration is deliberately manual in this phase."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parent.parent
SPEC = json.loads((ROOT / "workloads.json").read_text())
BENCH = ROOT / ".bench"


def command(args, *, cwd=ROOT, env=None):
    print("+ " + " ".join(map(str, args)), flush=True)
    subprocess.run(list(map(str, args)), cwd=cwd, env=env, check=True, timeout=300)


def prepare(name):
    source = SPEC["sources"][name]
    destination = BENCH / "sources" / name
    if destination.exists():
        commit = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=destination, text=True
        ).strip()
        if commit != source["commit"]:
            raise RuntimeError(f"Unexpected source revision in {destination}")
        return destination
    destination.mkdir(parents=True)
    try:
        command(["git", "init", "-q"], cwd=destination)
        command(
            ["git", "remote", "add", "origin", source["repository"]], cwd=destination
        )
        if source["paths"]:
            command(["git", "sparse-checkout", "init", "--cone"], cwd=destination)
            command(
                ["git", "sparse-checkout", "set", *source["paths"]], cwd=destination
            )
        command(
            [
                "git",
                "fetch",
                "--depth=1",
                "--filter=blob:none",
                "origin",
                source["commit"],
            ],
            cwd=destination,
        )
        command(["git", "checkout", "--detach", "FETCH_HEAD"], cwd=destination)
    except (OSError, subprocess.SubprocessError):
        shutil.rmtree(destination)
        raise
    return destination


def run_workload(name, cache_mode):
    definition = SPEC["workloads"][name]
    cache = BENCH / "cache" / name
    work = BENCH / "work" / name
    results = BENCH / "results"
    results.mkdir(parents=True, exist_ok=True)
    identity = {
        "workload": name,
        "spec": definition,
        "source": SPEC["sources"].get(definition.get("source")),
        "configuration": {
            p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest()
            for p in ["mise.toml", "package-lock.json", "uv.lock"]
        },
    }
    marker = cache / "admission.json"
    if cache_mode == "cold":
        if cache.exists():
            shutil.rmtree(cache)
    elif not marker.exists() or json.loads(marker.read_text()) != identity:
        raise RuntimeError(
            "Warm mode requires a successful cold seed with the same workload and source"
        )
    cache.mkdir(parents=True, exist_ok=True)
    if work.exists():
        shutil.rmtree(work)
    work.mkdir(parents=True)
    env = {
        **os.environ,
        "CI": "true",
        "CARGO_BUILD_JOBS": "4",
        "CARGO_TARGET_DIR": str(work / "target"),
        "CARGO_HOME": str(cache / "cargo"),
        "UV_CACHE_DIR": str(cache / "uv"),
        "PIP_CACHE_DIR": str(cache / "pip"),
        "npm_config_cache": str(cache / "npm"),
    }
    report = {
        "workload": name,
        "cache": cache_mode,
        "identity": identity,
        "stages": [],
        "passed": False,
    }

    def stage(label, args, cwd=ROOT):
        started = time.monotonic()
        try:
            command(args, cwd=cwd, env=env)
        finally:
            report["stages"].append(
                {
                    "name": label,
                    "command": list(map(str, args)),
                    "seconds": time.monotonic() - started,
                }
            )

    started = time.monotonic()
    try:
        if "source" in definition:
            source_started = time.monotonic()
            source = prepare(definition["source"]) / definition["path"]
            shutil.copytree(
                source,
                work / "source",
                ignore=shutil.ignore_patterns(".git", ".venv", "target"),
            )
            report["stages"].append(
                {"name": "source", "seconds": time.monotonic() - source_started}
            )
        source = work / "source"
        kind = definition["kind"]
        if kind == "typescript":
            stage("dependencies", ["npm", "ci", "--no-audit", "--no-fund"])
            stage(
                "upstream-dependencies",
                ["npm", "ci", "--no-audit", "--no-fund"],
                source,
            )
            stage(
                "generate",
                ["npm", "exec", "--no", "--", "hereby", "generate-diagnostics"],
                source,
            )
            tsc = [
                "node",
                ROOT / "node_modules/typescript/bin/tsc",
                "-p",
                source / "src/compiler",
                "--ignoreDeprecations",
                "6.0",
            ]
            stage("typecheck", [*tsc, "--noEmit", "--extendedDiagnostics"])
            stage("emit", [*tsc, "--outDir", work / "dist"])
            bundle = work / "compiler.cjs"
            stage(
                "bundle",
                [
                    ROOT / "node_modules/.bin/esbuild",
                    source / "src/compiler/_namespaces/ts.ts",
                    "--bundle",
                    "--minify",
                    "--platform=node",
                    "--format=cjs",
                    f"--outfile={bundle}",
                ],
            )
            stage(
                "verify-parser",
                [
                    "node",
                    "-e",
                    "const ts=require(process.argv[1]); const f=ts.createSourceFile('probe.ts','const answer: number = 42;',ts.ScriptTarget.Latest); if(f.parseDiagnostics.length) throw new Error('Parser verification failed');",
                    bundle,
                ],
            )
        elif kind.startswith("rust-"):
            stage("dependencies", ["cargo", "fetch", "--locked"], source)
            stage("check", ["cargo", "check", "--locked"], source)
            shutil.rmtree(work / "target")
            stage("release", ["cargo", "build", "--release", "--locked"], source)
            if kind == "rust-application":
                stage(
                    "tests",
                    ["cargo", "test", "--release", "--locked", "--workspace", "--lib"],
                    source,
                )
                corpus = work / "corpus.txt"
                corpus.write_text(
                    "".join(
                        f"record-{i:06d} level={'error' if i % 100 == 0 else 'info'}\n"
                        for i in range(200_000)
                    )
                )
                stage(
                    "search",
                    [work / "target/release/rg", "--count", "level=error", corpus],
                )
                actual = subprocess.check_output(
                    [work / "target/release/rg", "--count", "level=error", corpus],
                    text=True,
                ).strip()
                if actual != "2000":
                    raise RuntimeError("ripgrep output verification failed")
        elif kind == "python-tests":
            stage(
                "dependencies",
                [
                    "uv",
                    "sync",
                    "--frozen",
                    "--python",
                    sys.executable,
                    "--no-default-groups",
                    "--group",
                    "tests",
                ],
                source,
            )
            python = source / ".venv/bin/python"
            stage("tests", [python, "-m", "pytest", "-q", "tests"], source)
            stage(
                "render",
                [
                    python,
                    "-c",
                    "from jinja2 import Environment; t=Environment().from_string('{% for x in xs %}{{ x * x }} {% endfor %}'); expected=t.render(xs=range(1000)); assert all(t.render(xs=range(1000)) == expected for _ in range(1000))",
                ],
                source,
            )
        else:
            if (ROOT / ".venv").exists():
                shutil.rmtree(ROOT / ".venv")
            stage(
                "dependencies", ["uv", "sync", "--frozen", "--python", sys.executable]
            )
            stage(
                "cpu",
                [
                    "uv",
                    "run",
                    "--frozen",
                    "pyperformance",
                    "run",
                    "--fast",
                    "--benchmarks",
                    "json_dumps,regex_v8",
                    "--output",
                    work / "pyperformance.json",
                ],
            )
        report["passed"] = True
        marker.write_text(json.dumps(identity, indent=2))
    finally:
        report["seconds"] = time.monotonic() - started
        (results / f"{name}-{cache_mode}.json").write_text(json.dumps(report, indent=2))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("list")
    prepare_parser = commands.add_parser("prepare")
    prepare_parser.add_argument("source", choices=SPEC["sources"])
    run_parser = commands.add_parser("run")
    run_parser.add_argument("workload", choices=SPEC["workloads"])
    run_parser.add_argument("--cache", choices=["cold", "warm"], required=True)
    args = parser.parse_args()
    if args.command == "list":
        for name, definition in SPEC["workloads"].items():
            print(f"{name}: {definition['description']}")
    elif args.command == "prepare":
        print(prepare(args.source))
    else:
        run_workload(args.workload, args.cache)


if __name__ == "__main__":
    main()
