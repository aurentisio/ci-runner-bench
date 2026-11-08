"""Summarize the fixed benchmark matrix without mixing seeds into measurements."""

import argparse
import csv
import json
import math
import re
import statistics
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PROVIDERS = ["github", "blacksmith", "boat"]


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


def analyze(run_id):
    destination = ROOT / "results" / str(run_id)
    evidence = json.loads((destination / "evidence.json").read_text())
    workloads = list(json.loads((ROOT / "workloads.json").read_text())["workloads"])
    reports = evidence["reports"]
    boat_usage = json.loads((destination / "boat-usage.json").read_text())
    boat_by_job = {int(job["id"]): job for job in boat_usage}
    if len(boat_by_job) != 35 or any(job["state"] != "success" for job in boat_usage):
        raise RuntimeError("Boat billing evidence must include all 35 successful jobs")
    expected = {
        (provider, workload, profile, sample)
        for provider in PROVIDERS
        for workload in workloads
        for profile, samples in [("cold", [0, 1, 2, 3]), ("warm", [1, 2, 3])]
        for sample in samples
    }
    actual = [(r["provider"], r["workload"], r["cache"], r["sample"]) for r in reports]
    if len(actual) != len(expected) or set(actual) != expected:
        raise RuntimeError(
            "Evidence must contain exactly the complete 105-job workload matrix"
        )
    if evidence["run"]["conclusion"] != "success" or not all(
        r["passed"] for r in reports
    ):
        raise RuntimeError(
            "Resolve or explicitly analyze failures before publishing a success report"
        )
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
            r" / (github|blacksmith|boat) / ([\w-]+) / (cold|warm) / (\d+)$",
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
            for provider in PROVIDERS:
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
    spent = {
        provider: pilot[provider]
        + sum(r["job_seconds"] for r in rows if r["provider"] == provider)
        for provider in PROVIDERS
    }
    spent["github"] += sum(
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
        for provider in PROVIDERS:
            aggregate[profile][provider] = {
                "sum_workload_job_medians_seconds": sum(
                    median(provider, w, profile) for w in workloads
                ),
                "geomean_job_speedup_vs_github": statistics.geometric_mean(
                    median("github", w, profile) / median(provider, w, profile)
                    for w in workloads
                ),
                "geomean_compute_speedup_vs_github": statistics.geometric_mean(
                    median("github", w, profile, "compute_seconds")
                    / median(provider, w, profile, "compute_seconds")
                    for w in workloads
                ),
            }
    hardware = {}
    for provider in PROVIDERS:
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
        }
        for m in [1000, 5000, 10000, 50000]
    ]
    equal_work = []
    for count in [1000, 5000, 10000, 50000]:
        # One suite is five separate fresh-runner jobs, one per workload, warm dependencies.
        for provider in PROVIDERS:
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
                }
            )
    runtime = []
    for artifact in evidence["pyperformance"]:
        match = re.search(
            r"bench-(github|blacksmith|boat)-python-pyperformance-(cold|warm)-(\d+)/",
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
        "run": evidence["run"],
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
    parser.add_argument("run_id", type=int)
    analyze(parser.parse_args().run_id)
