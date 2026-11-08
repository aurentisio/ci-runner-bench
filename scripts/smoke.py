"""Check provider plumbing; these timings are not benchmark results."""

import hashlib
import json
import os
from pathlib import Path
import platform
import random
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parent.parent
OUTPUT = ROOT / ".smoke"
PAYLOAD = random.Random(42).randbytes(1024 * 1024)


def run(command, *, timeout=120):
    started = time.monotonic()
    result = subprocess.run(
        command, cwd=ROOT, check=True, text=True, capture_output=True, timeout=timeout
    )
    print(result.stdout, end="", flush=True)
    if result.stderr:
        print(result.stderr, end="", file=sys.stderr, flush=True)
    return {"command": command, "seconds": time.monotonic() - started, "stdout": result.stdout}


def main():
    if sys.argv[1:] == ["--verify-cache"]:
        actual = (OUTPUT / "cache" / "probe.bin").read_bytes()
        if actual != PAYLOAD:
            raise RuntimeError("Restored cache bytes differ from the seeded payload")
        (OUTPUT / "cache-result.json").write_text(
            json.dumps({"bytes": len(actual), "sha256": hashlib.sha256(actual).hexdigest(), "verified": True}, indent=2)
        )
        print("Cache roundtrip verified (1 MiB)")
        return
    if sys.argv[1:]:
        raise SystemExit("Usage: python scripts/smoke.py [--verify-cache]")
    OUTPUT.mkdir(exist_ok=True)
    evidence = {
        "provider": os.environ.get("BENCH_PROVIDER", "local"),
        "commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "platform": platform.platform(),
        "cpu_count": os.cpu_count(),
        "cpu_affinity_count": len(os.sched_getaffinity(0)) if hasattr(os, "sched_getaffinity") else None,
        "python": platform.python_version(),
        "resources": {},
        "stages": [],
        "passed": False,
    }
    for name in ["/etc/os-release", "/proc/meminfo", "/sys/fs/cgroup/cpu.max", "/sys/fs/cgroup/memory.max"]:
        path = Path(name)
        if path.is_file():
            evidence["resources"][name] = path.read_text()
    try:
        for command in [["mise", "--version"], ["node", "--version"], ["rustc", "--version"], ["cargo", "--version"], ["uv", "--version"]]:
            evidence["stages"].append(run(command))
        evidence["stages"].append(run(["npm", "ci", "--no-audit", "--no-fund"]))
        (OUTPUT / "probe.ts").write_text('const answer: number = 6 * 7; if (answer !== 42) throw new Error("TypeScript probe failed");\n')
        evidence["stages"].append(run(["node", "node_modules/typescript/bin/tsc", ".smoke/probe.ts", "--outDir", ".smoke/js", "--strict", "--skipLibCheck", "--target", "ES2022"]))
        evidence["stages"].append(run(["node", ".smoke/js/probe.js"]))
        (OUTPUT / "probe.rs").write_text('fn main() { assert_eq!((1..=1000).sum::<u64>(), 500500); println!("Rust probe passed"); }\n')
        evidence["stages"].append(run(["rustc", "--edition=2024", "-O", ".smoke/probe.rs", "-o", ".smoke/rust-probe"]))
        evidence["stages"].append(run([str(OUTPUT / "rust-probe")]))
        evidence["stages"].append(run(["uv", "sync", "--frozen"]))
        evidence["stages"].append(run(["uv", "run", "--frozen", "python", "-c", 'import json, pyperformance; assert json.loads(json.dumps({"answer": 42}))["answer"] == 42; print("Python probe passed")']))
        deadline = time.monotonic() + 30
        while True:
            try:
                evidence["stages"].append(run(["docker", "info", "--format", "{{.ServerVersion}}"], timeout=10))
                break
            except subprocess.CalledProcessError:
                if time.monotonic() >= deadline:
                    raise
                time.sleep(1)
        evidence["stages"].append(run(["docker", "run", "--rm", "--network", "none", "alpine:3.22.2", "sh", "-c", "test 42 -eq 42"]))
        (OUTPUT / "cache").mkdir(exist_ok=True)
        (OUTPUT / "cache" / "probe.bin").write_bytes(PAYLOAD)
        evidence["passed"] = True
    except (OSError, subprocess.SubprocessError) as error:
        evidence["error"] = str(error)
        if isinstance(error, subprocess.CalledProcessError):
            evidence["stdout"] = error.stdout
            evidence["stderr"] = error.stderr
        raise
    finally:
        (OUTPUT / "environment.json").write_text(json.dumps(evidence, indent=2))


if __name__ == "__main__":
    main()
