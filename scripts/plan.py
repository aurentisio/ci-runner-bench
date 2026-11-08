"""Emit a fixed-size matrix that leaves headroom under the per-provider budget."""

import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PROVIDERS = {
    "github": "ubuntu-24.04",
    "blacksmith": "blacksmith-4vcpu-ubuntu-2404",
    "boat": "boat",
}
spec = json.loads((ROOT / "workloads.json").read_text())
selected_provider = os.environ["SELECT_PROVIDER"]
selected_workload = os.environ["SELECT_WORKLOAD"]
if selected_provider not in ["all", *PROVIDERS]:
    raise ValueError("Unknown provider")
if selected_workload not in ["all", *spec["workloads"]]:
    raise ValueError("Unknown workload")
providers = list(PROVIDERS) if selected_provider == "all" else [selected_provider]
workloads = (
    list(spec["workloads"]) if selected_workload == "all" else [selected_workload]
)
seed = []
measure = []
for workload in workloads:
    for provider in providers:
        seed.append(
            {
                "provider": provider,
                "runner": PROVIDERS[provider],
                "workload": workload,
                "profile": "cold",
                "sample": 0,
            }
        )
# Alternate profiles and rotate providers to reduce a fixed scheduling-order bias.
for sample in [1, 2, 3]:
    for workload in workloads:
        for profile in ["cold", "warm"] if sample % 2 else ["warm", "cold"]:
            order = (
                providers[sample % len(providers) :]
                + providers[: sample % len(providers)]
            )
            for provider in order:
                measure.append(
                    {
                        "provider": provider,
                        "runner": PROVIDERS[provider],
                        "workload": workload,
                        "profile": profile,
                        "sample": sample,
                    }
                )
pilot = json.loads((ROOT / "results/pilot.json").read_text())[
    "spent_job_seconds_per_provider"
]
for provider in providers:
    scheduled_minutes = 5 * sum(r["provider"] == provider for r in seed + measure)
    # Include the plan job and leave time for uploads/cleanup and selective retries.
    if scheduled_minutes + pilot[provider] / 60 + 2 > 190:
        raise RuntimeError(f"Planned timeout budget is too large for {provider}")
print("seed=" + json.dumps({"include": seed}, separators=(",", ":")))
print("measure=" + json.dumps({"include": measure}, separators=(",", ":")))
