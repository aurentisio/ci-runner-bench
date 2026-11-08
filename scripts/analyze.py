"""Summarize the fixed benchmark matrix without mixing seeds into measurements."""

import argparse
import ast
import csv
import json
import math
import re
import statistics
import subprocess
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PROVIDERS = ["github", "blacksmith", "boat", "namespace"]


def namespace_monthly(minutes):
    """4 CPU / 16 GB is eight Linux unit-minutes per billed machine minute."""
    options = [
        {"plan": "Developer", "usd": minutes * 0.012},
        {"plan": "Team", "usd": 100 + max(0, minutes * 8 - 100000) * 0.0015},
        {"plan": "Business", "usd": 250 + max(0, minutes * 8 - 250000) * 0.0015},
    ]
    return min(options, key=lambda row: row["usd"])


def harness_contract(commit):
    source = subprocess.check_output(
        ["git", "show", f"{commit}:scripts/bench.py"], cwd=ROOT, text=True
    )
    tree = ast.parse(source)
    imports = sorted(
        ast.dump(node, include_attributes=False)
        for node in tree.body
        if isinstance(node, (ast.Import, ast.ImportFrom))
    )
    # Documentation and import ordering do not affect measured commands.
    tree.body = [
        node
        for node in tree.body
        if not isinstance(node, (ast.Import, ast.ImportFrom))
        and not (
            isinstance(node, ast.Expr)
            and isinstance(node.value, ast.Constant)
            and isinstance(node.value.value, str)
        )
    ]
    workflow = subprocess.check_output(
        ["git", "show", f"{commit}:.github/workflows/workload.yml"], cwd=ROOT, text=True
    )
    return tuple(imports), ast.dump(tree, include_attributes=False), workflow


def seconds(start, end):
    return (datetime.fromisoformat(end) - datetime.fromisoformat(start)).total_seconds()


def step_seconds(job, name):
    return sum(
        seconds(step["started_at"], step["completed_at"])
        for step in job["steps"]
        if step["name"] == name and step["conclusion"] == "success"
    )


def stats(values):
    return {"median": statistics.median(values), "min": min(values), "max": max(values)}


def analyze(run_ids):
    destination = (
        ROOT / "results" / (str(run_ids[0]) if len(run_ids) == 1 else "comparison")
    )
    destination.mkdir(parents=True, exist_ok=True)
    inputs = [
        json.loads((ROOT / "results" / str(run_id) / "evidence.json").read_text())
        for run_id in run_ids
    ]
    if len({harness_contract(item["run"]["head_sha"]) for item in inputs}) != 1:
        raise RuntimeError("Measured harness behavior differs across runs")
    evidence = {
        "runs": [item["run"] for item in inputs],
        "jobs": [job for item in inputs for job in item["jobs"]],
        "reports": [
            {**report, "run_id": item["run"]["id"]}
            for item in inputs
            for report in item["reports"]
        ],
        "pyperformance": [
            artifact for item in inputs for artifact in item["pyperformance"]
        ],
    }
    workloads = list(json.loads((ROOT / "workloads.json").read_text())["workloads"])
    reports = evidence["reports"]
    providers = [
        provider
        for provider in PROVIDERS
        if any(report["provider"] == provider for report in reports)
    ]
    boat_usage = [
        job
        for run_id, item in zip(run_ids, inputs, strict=True)
        if any(report["provider"] == "boat" for report in item["reports"])
        for job in json.loads(
            (ROOT / "results" / str(run_id) / "boat-usage.json").read_text()
        )
    ]
    boat_by_job = {int(job["id"]): job for job in boat_usage}
    if "boat" in providers and (
        len(boat_by_job) != 35 or any(job["state"] != "success" for job in boat_usage)
    ):
        raise RuntimeError("Boat billing evidence must include all 35 successful jobs")
    expected = {
        (provider, workload, profile, sample)
        for provider in providers
        for workload in workloads
        for profile, samples in [("cold", [0, 1, 2, 3]), ("warm", [1, 2, 3])]
        for sample in samples
    }
    actual = [(r["provider"], r["workload"], r["cache"], r["sample"]) for r in reports]
    if len(actual) != len(expected) or set(actual) != expected:
        raise RuntimeError(
            "Evidence must contain exactly 35 workload jobs per selected provider"
        )
    if any(run["conclusion"] != "success" for run in evidence["runs"]) or not all(
        r["passed"] for r in reports
    ):
        raise RuntimeError(
            "Resolve or explicitly analyze failures before publishing a success report"
        )
    for workload in workloads:
        if (
            len(
                {
                    json.dumps(report["identity"], sort_keys=True)
                    for report in reports
                    if report["workload"] == workload
                }
            )
            != 1
        ):
            raise RuntimeError("Source/configuration identity differs across providers")
    if len({r["environment"]["python"] for r in reports}) != 1:
        raise RuntimeError("Python versions differ across samples")
    if (
        len({json.dumps(r["environment"]["tools"], sort_keys=True) for r in reports})
        != 1
    ):
        raise RuntimeError("Tool versions differ across samples")
    if any(len(r["environment"]["affinity"]) != 4 for r in reports):
        raise RuntimeError("Unexpected CPU allocation")
    jobs = {}
    for job in evidence["jobs"]:
        match = re.search(
            r" / (github|blacksmith|boat|namespace) / ([\w-]+) / (cold|warm) / (\d+)$",
            job["name"],
        )
        if match:
            provider, workload, profile, sample = match.groups()
            jobs[(provider, workload, profile, int(sample))] = job
    rows = []
    stages = []
    for report in reports:
        key = (
            report["provider"],
            report["workload"],
            report["cache"],
            report["sample"],
        )
        job = jobs[key]
        if job["conclusion"] != "success":
            raise RuntimeError("A workload job did not pass")
        if report["seed"] != (report["sample"] == 0):
            raise RuntimeError("Seed identity mismatch")
        if report["cache"] == "warm" and report["cache_bytes_before"] <= 0:
            raise RuntimeError("A warm sample did not restore dependency bytes")
        row = {
            "provider": key[0],
            "workload": key[1],
            "cache": key[2],
            "sample": key[3],
            "seed": report["seed"],
            "job_id": job["id"],
            "run_id": report["run_id"],
            "job_url": job["html_url"],
            "job_seconds": seconds(job["started_at"], job["completed_at"]),
            "queue_seconds": seconds(job["created_at"], job["started_at"]),
            "workload_seconds": report["seconds"],
            "setup_seconds": step_seconds(job, "Setup pinned tools"),
            "restore_seconds": step_seconds(job, "Restore native dependency cache"),
            "seed_save_seconds": step_seconds(job, "Save native dependency cache seed"),
            "cache_bytes_before": report["cache_bytes_before"],
            "cache_bytes_after": report["cache_bytes_after"],
        }
        row["source_seconds"] = sum(
            s["seconds"] for s in report["stages"] if s["name"] == "source"
        )
        row["dependency_seconds"] = sum(
            s["seconds"] for s in report["stages"] if "dependencies" in s["name"]
        )
        row["compute_seconds"] = sum(
            s["seconds"]
            for s in report["stages"]
            if s["name"] != "source" and "dependencies" not in s["name"]
        )
        if row["provider"] == "boat":
            row["boat_reported_cost_usd"] = boat_by_job[job["id"]]["costDollars"]
        rows.append(row)
        for stage in report["stages"]:
            stages.append(
                {
                    "provider": key[0],
                    "workload": key[1],
                    "cache": key[2],
                    "sample": key[3],
                    "seed": report["seed"],
                    "stage": stage["name"],
                    "seconds": stage["seconds"],
                    **stage.get("resources", {}),
                }
            )
    measured = [r for r in rows if not r["seed"]]
    groups = []
    metrics = [
        "job_seconds",
        "queue_seconds",
        "workload_seconds",
        "setup_seconds",
        "restore_seconds",
        "source_seconds",
        "dependency_seconds",
        "compute_seconds",
    ]
    for workload in workloads:
        for profile in ["cold", "warm"]:
            for provider in providers:
                selected = [
                    r
                    for r in measured
                    if (r["provider"], r["workload"], r["cache"])
                    == (provider, workload, profile)
                ]
                groups.append(
                    {
                        "provider": provider,
                        "workload": workload,
                        "cache": profile,
                        "samples": len(selected),
                        **{
                            metric: stats([r[metric] for r in selected])
                            for metric in metrics
                        },
                    }
                )
    pilot = json.loads((ROOT / "results/pilot.json").read_text())[
        "spent_job_seconds_per_provider"
    ]
    pilot["namespace"] = json.loads(
        (ROOT / "results/namespace-readiness/run.json").read_text()
    )["execution_seconds"]
    spent = {
        provider: pilot[provider]
        + sum(r["job_seconds"] for r in rows if r["provider"] == provider)
        for provider in providers
    }
    spent["github"] = spent.get("github", 0) + sum(
        seconds(j["started_at"], j["completed_at"])
        for j in evidence["jobs"]
        if j["name"] == "plan"
    )
    if max(spent.values()) > 200 * 60:
        raise RuntimeError("Provider execution budget exceeded")

    def median(provider, workload, profile, metric="job_seconds"):
        return next(
            g[metric]["median"]
            for g in groups
            if (g["provider"], g["workload"], g["cache"])
            == (provider, workload, profile)
        )

    aggregate = {}
    for profile in ["cold", "warm"]:
        aggregate[profile] = {}
        for provider in providers:
            aggregate[profile][provider] = {
                "sum_workload_job_medians_seconds": sum(
                    median(provider, w, profile) for w in workloads
                ),
                "geomean_job_speedup_vs_github": statistics.geometric_mean(
                    median("github", w, profile) / median(provider, w, profile)
                    for w in workloads
                )
                if "github" in providers
                else None,
                "geomean_compute_speedup_vs_github": statistics.geometric_mean(
                    median("github", w, profile, "compute_seconds")
                    / median(provider, w, profile, "compute_seconds")
                    for w in workloads
                )
                if "github" in providers
                else None,
            }
    hardware = {}
    for provider in providers:
        selected = [r for r in reports if r["provider"] == provider]
        hardware[provider] = {
            "cpu_models": sorted(
                {
                    line.split(":", 1)[1].strip()
                    for r in selected
                    for line in r["environment"]["proc"]["/proc/cpuinfo"].splitlines()
                    if line.startswith("model name")
                }
            ),
            "memory_kib": sorted(
                {
                    int(
                        re.search(
                            r"MemTotal:\s+(\d+)",
                            r["environment"]["proc"]["/proc/meminfo"],
                        ).group(1)
                    )
                    for r in selected
                }
            ),
            "cpus": 4,
        }
    costs = [
        {
            "runner_minutes": m,
            "github_public_usd": 0,
            "github_paid_4cpu_list_usd": m * 0.012,
            "blacksmith_4cpu_before_free_credit_usd": m * 0.008,
            "boat_4cpu_one_seat_base_usd": max(20, m * 0.0006),
            "namespace_4cpu16gb_payg_usd": m * 0.012,
            "namespace_lowest_list_plan": namespace_monthly(m),
        }
        for m in [1000, 5000, 10000, 50000]
    ]
    equal_work = []
    for count in [1000, 5000, 10000, 50000]:
        # One suite is five separate fresh-runner jobs, one per workload, warm dependencies.
        for provider in providers:
            durations = [median(provider, w, "warm") for w in workloads]
            minutes = count * sum(durations) / 60
            rounded = count * sum(math.ceil(s / 60) for s in durations)
            equal_work.append(
                {
                    "provider": provider,
                    "five_job_suites": count,
                    "job_execution_minutes": minutes,
                    "github_paid_list_rounded_usd": rounded * 0.012
                    if provider == "github"
                    else None,
                    "blacksmith_unrounded_gross_usd": minutes * 0.008
                    if provider == "blacksmith"
                    else None,
                    "blacksmith_rounded_gross_usd": rounded * 0.008
                    if provider == "blacksmith"
                    else None,
                    "boat_measured_vm_base_usd": max(
                        20,
                        count
                        * sum(
                            statistics.median(
                                r["boat_reported_cost_usd"]
                                for r in measured
                                if r["provider"] == "boat"
                                and r["workload"] == w
                                and r["cache"] == "warm"
                            )
                            for w in workloads
                        ),
                    )
                    if provider == "boat"
                    else None,
                    "boat_starts": count * 5 if provider == "boat" else None,
                    "namespace_payg_seconds_only_usd": minutes * 0.012
                    if provider == "namespace"
                    else None,
                    "namespace_ceil_minute_payg_usd": rounded * 0.012
                    if provider == "namespace"
                    else None,
                    "namespace_ceil_minute_lowest_plan": namespace_monthly(rounded)
                    if provider == "namespace"
                    else None,
                }
            )
    runtime = []
    for artifact in evidence["pyperformance"]:
        match = re.search(
            r"bench-(github|blacksmith|boat|namespace)-python-pyperformance-(cold|warm)-(\d+)/",
            artifact["artifact"],
        )
        if not match:
            raise RuntimeError("Unexpected pyperformance artifact name")
        provider, profile, sample = match.groups()
        for benchmark in artifact["data"]["benchmarks"]:
            values = [v for run in benchmark["runs"] for v in run.get("values", [])]
            runtime.append(
                {
                    "provider": provider,
                    "cache": profile,
                    "sample": int(sample),
                    "benchmark": benchmark.get("metadata", {}).get(
                        "name", artifact["data"].get("metadata", {}).get("name")
                    ),
                    "seconds_per_operation": stats(values),
                    "values": len(values),
                }
            )
    summary = {
        "run": evidence["runs"][0],
        "runs": evidence["runs"],
        "providers": providers,
        "harness_behavior_verified_equal": True,
        "hardware": hardware,
        "groups": groups,
        "aggregate": aggregate,
        "spent_seconds_including_pilot": spent,
        "monthly_minute_costs": costs,
        "equal_work_costs": equal_work,
        "runtime": runtime,
        "boat_reported_total_vm_cost_usd": sum(
            job["costDollars"] for job in boat_usage
        ),
    }
    (destination / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    for filename, data in [("samples.csv", rows), ("stages.csv", stages)]:
        with (destination / filename).open("w") as stream:
            fields = list(dict.fromkeys(k for r in data for k in r))
            writer = csv.DictWriter(stream, fieldnames=fields)
            writer.writeheader()
            writer.writerows(data)
    print(
        json.dumps(
            {
                "groups": len(groups),
                "samples": len(measured),
                "aggregate": aggregate,
                "spent_minutes": {k: v / 60 for k, v in spent.items()},
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run_ids", type=int, nargs="+")
    analyze(parser.parse_args().run_ids)
