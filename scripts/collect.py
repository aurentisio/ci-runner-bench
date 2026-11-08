"""Download completed Actions evidence and preserve a compact, auditable dataset."""

import argparse
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REPO = "aurentisio/ci-runner-bench"


def gh(*args):
    return subprocess.check_output(["gh", *args], text=True)


def collect(run_id):
    run = json.loads(gh("api", f"repos/{REPO}/actions/runs/{run_id}"))
    if run["status"] != "completed":
        raise RuntimeError("Collect only completed runs so evidence is not partial")
    output = ROOT / "results" / str(run_id)
    output.mkdir(parents=True, exist_ok=True)
    download = ROOT / ".bench" / "downloads" / str(run_id)
    subprocess.run(
        ["gh", "run", "download", str(run_id), "--repo", REPO, "--dir", str(download)],
        check=True,
    )
    pages = json.loads(
        gh(
            "api",
            "--paginate",
            "--slurp",
            f"repos/{REPO}/actions/runs/{run_id}/jobs?per_page=100",
        )
    )
    jobs = []
    for page in pages:
        for job in page["jobs"]:
            jobs.append(
                {
                    key: job[key]
                    for key in [
                        "id",
                        "name",
                        "status",
                        "conclusion",
                        "created_at",
                        "started_at",
                        "completed_at",
                        "html_url",
                        "labels",
                        "runner_name",
                        "steps",
                    ]
                }
            )
    reports = []
    runtime = []
    for path in sorted(download.rglob("*.json")):
        data = json.loads(path.read_text())
        if "workload" in data and "stages" in data:
            data["artifact"] = path.relative_to(download).as_posix()
            reports.append(data)
        elif "benchmarks" in data:
            # Preserve pyperf's values, calibration and instability warnings.
            runtime.append(
                {"artifact": path.relative_to(download).as_posix(), "data": data}
            )
    evidence = {
        "run": {
            key: run[key]
            for key in [
                "id",
                "html_url",
                "head_sha",
                "status",
                "conclusion",
                "created_at",
                "updated_at",
                "run_attempt",
            ]
        },
        "jobs": jobs,
        "reports": reports,
        "pyperformance": runtime,
    }
    (output / "evidence.json").write_text(json.dumps(evidence, indent=2) + "\n")
    print(
        f"Collected {len(jobs)} jobs and {len(reports)} workload reports into {output}"
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run_id", type=int)
    collect(parser.parse_args().run_id)
