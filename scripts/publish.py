"""Generate the benchmark's Markdown report and interactive HTML overview."""

import argparse
import json
import statistics
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LABELS = {
    "github": "GitHub",
    "blacksmith": "Blacksmith",
    "boat": "Boat",
    "namespace": "Namespace",
}


def boat_monthly(compute_dollars, starts):
    """Illustrative evenly spaced starts over 30 days; not burst/invoice prediction."""
    options = []
    for plan, included in [(20, 200), (100, 840), (500, 1680), (2000, 2400)]:
        daily = starts / 30
        if daily > 6 * included:
            continue
        extra = max(0, daily - included)
        fees = 30 * (
            min(extra, included * 0.5) * 0.03
            + min(max(0, extra - included * 0.5), included * 0.5) * 0.05
            + max(0, extra - included) * 0.07
        )
        options.append(
            {
                "plan_usd": plan,
                "starts_usd": fees,
                "total_usd": max(plan, compute_dollars) + fees,
            }
        )
    return min(options, key=lambda x: x["total_usd"]) if options else None


def publish(dataset):
    path = ROOT / "results" / dataset
    summary = json.loads((path / "summary.json").read_text())
    providers = summary["providers"]
    workloads = list(dict.fromkeys(g["workload"] for g in summary["groups"]))
    runs = summary["runs"]

    def group(provider, workload, profile):
        return next(
            g
            for g in summary["groups"]
            if (g["provider"], g["workload"], g["cache"])
            == (provider, workload, profile)
        )

    def total(provider, profile):
        return summary["aggregate"][profile][provider][
            "sum_workload_job_medians_seconds"
        ]

    def money(value):
        return f"${value:,.2f}"

    def table(headers, rows):
        return [
            "| " + " | ".join(headers) + " |",
            "| " + " | ".join("---" for _ in headers) + " |",
            *["| " + " | ".join(map(str, row)) + " |" for row in rows],
        ]

    ranking = sorted(providers, key=lambda provider: total(provider, "warm"))
    winner = ranking[0]
    cold_winner = min(providers, key=lambda provider: total(provider, "cold"))
    less = (1 - total(winner, "warm") / total("github", "warm")) * 100
    lines = [
        "# CI runner benchmark — four-provider ranking",
        "",
        f"**{LABELS[winner]} narrowly leads the observed warm-cache total; {LABELS[cold_winner]} leads cold-cache totals.** The warm leader totals **{total(winner, 'warm'):.0f} seconds**, using the sum of five workload medians: **{less:.0f}% less job execution time than GitHub**. This is a serial five-job summary, not the actual parallel workflow duration.",
        "",
        "Namespace and Blacksmith are close: warm totals are 149 versus 154 seconds, while cold totals are 161 versus 156 seconds. A roughly 3% gap with three samples in separate runs is not evidence of a statistically established winner. Namespace leads Python and the Rust regex workload; Blacksmith leads TypeScript; warm ripgrep medians tie.",
        "",
        f"All **{35 * len(providers)} workload jobs** passed: {5 * len(providers)} cache seeds and {30 * len(providers)} measured jobs. Each workload/provider/cache group has three fresh-runner samples. Seeds count toward execution budgets but not speed rankings.",
        "",
        "## Run provenance and comparison limits",
        "",
        "The original GitHub/Blacksmith/Boat run and the later Namespace run were executed separately on 8 November 2026. They are not a simultaneous race. The Namespace-only matrix could schedule six jobs on that provider at once; the original matrix shared six slots among three providers. Scheduling/host load and network conditions may differ. No workflow-elapsed throughput ranking is inferred.",
        "",
    ]
    for run in runs:
        lines += [
            f"- [Run {run['id']}]({run['html_url']}): {run['created_at']} → {run['updated_at']}; commit `{run['head_sha']}`."
        ]
    lines += [
        "",
        "The analyzer verified equal workload-harness syntax (ignoring only module documentation and import ordering), identical reusable workload workflow, source/configuration identities, tool versions and four-CPU affinity across all inputs. Full commits differ because orchestration, documentation and provider support changed. The original [three-provider report](reports/initial-three-providers.md) and raw evidence remain available.",
        "",
        "This ranking uses **dependency-only archive caching and clean builds**. Namespace uses the same pinned `actions/cache` action and cache-content policy; its native persistent cache volumes, custom images and checkout caching are **not enabled**. Blacksmith automatically enables its transparent archive-cache backend. This establishes a matched baseline, not the maximum optimized performance of each provider.",
        "",
        "## Complete-job speed",
        "",
        "Seconds: **median (minimum–maximum)**, n=3. Includes setup, pinned tool installation, archive restore, source fetch, dependencies, builds/tests, upload and cleanup; excludes queueing. Lower is better.",
        "",
    ]
    rows = []
    for workload in workloads:
        for profile in ["cold", "warm"]:
            values = [group(p, workload, profile)["job_seconds"] for p in providers]
            rows.append(
                [
                    workload,
                    profile,
                    *[
                        f"**{v['median']:.0f}** ({v['min']:.0f}–{v['max']:.0f})"
                        for v in values
                    ],
                ]
            )
    lines += table(["Workload", "Cache", *[LABELS[p] for p in providers]], rows)
    lines += ["", "### Serial suite totals", ""]
    lines += table(
        ["Cache", *[LABELS[p] for p in providers]],
        [
            [profile, *[f"{total(p, profile):.0f} s" for p in providers]]
            for profile in ["cold", "warm"]
        ],
    )
    lines += [
        "",
        "The warm suite order is "
        + " → ".join(f"{LABELS[p]} ({total(p, 'warm'):.0f} s)" for p in ranking)
        + ". Rankings describe these products and short workloads, not all CI or identical physical hardware.",
        "",
        "### Geometric-mean speedups versus GitHub",
        "",
        "Every workload has equal weight in this table. Ratios above 1× mean faster. These differ from serial totals, which give long jobs more weight.",
        "",
    ]
    lines += table(
        [
            "Provider",
            "Cold complete job",
            "Warm complete job",
            "Cold compute",
            "Warm compute",
        ],
        [
            [
                LABELS[p],
                *[
                    f"{summary['aggregate'][profile][p][metric]:.2f}×"
                    for metric in [
                        "geomean_job_speedup_vs_github",
                        "geomean_compute_speedup_vs_github",
                    ]
                    for profile in ["cold", "warm"]
                ],
            ]
            for p in providers
        ],
    )
    lines += [
        "",
        "## Cache effectiveness",
        "",
        f"All **{15 * len(providers)} warm jobs** restored a successful matching seed and passed package-manager integrity checks. The cache contains only npm/Cargo/uv/pip package data; source, compiled outputs, target directories and virtual environments are recreated. Cold does not flush registry/CDN, host or provider infrastructure caches.",
        "",
        "Dependency installation and archive restore are separate below. Restore step timings have one-second resolution, so 0 s means below the timestamp resolution.",
        "",
    ]
    lines += table(
        ["Provider", "Workload", "Cold install", "Warm install", "Warm restore"],
        [
            [
                LABELS[p],
                w,
                f"{group(p, w, 'cold')['dependency_seconds']['median']:.2f} s",
                f"{group(p, w, 'warm')['dependency_seconds']['median']:.2f} s",
                f"{group(p, w, 'warm')['restore_seconds']['median']:.0f} s",
            ]
            for p in providers
            for w in workloads
        ],
    )
    lines += [
        "",
        "In the original run, Boat's TypeScript archive (~52 MB) took a median 13 seconds to restore, while cold dependency installation took 2.63 seconds. Cargo's warm dependency fetch was much faster, but Boat's transfer often outweighed the saving. Small npm/uv caches also have little room to recover transfer overhead. A warmer job taking longer overall does not prove its cached dependencies slowed compilation: source-fetch, hardware and runtime variance remain visible in the ranges.",
        "",
        "Namespace's archive restores took a median 1 second for each workload. Cargo fetching fell to about 0.06 seconds warm, so the dependency saving exceeded the restore cost. TypeScript's combined dependency work was 4.49 seconds cold versus 3.44 seconds warm plus 1 second of restoration: little net gain. The one-second archive restore also exceeds the small Python dependency-install savings. These are archive-cache observations, not measurements of Namespace's persistent cache volumes.",
        "",
        "Prefer a cache when the dependency work it saves exceeds restoration cost. Native persistent cache volumes or snapshots could change that result, but require a separately labelled test. Incremental Rust target caching was excluded here to preserve clean builds. Namespace's native-volume advantage is therefore not established by this experiment.",
        "",
        "## Python runtime",
        "",
        "Milliseconds per operation: median of six measured job medians (cold and warm combined). pyperformance uses `--fast` for JSON/regex; these are directional estimates with worker/calibration evidence preserved, not stable publication-quality claims.",
        "",
    ]
    lines += table(
        ["Operation", *[LABELS[p] for p in providers]],
        [
            [
                benchmark,
                *[
                    f"{statistics.median(r['seconds_per_operation']['median'] for r in summary['runtime'] if r['provider'] == p and r['benchmark'] == benchmark and r['sample'] > 0) * 1000:.2f} ms"
                    for p in providers
                ],
            ]
            for benchmark in ["json_dumps", "regex_v8"]
        ],
    )
    lines += [
        "",
        "## Hardware and execution budget",
        "",
        "Each product exposed four CPUs. Boat has ~8 GB RAM; the others ~16 GB. CPU models, kernels and provider images vary. Three samples do not establish tail latency or statistical significance.",
        "",
    ]
    lines += table(
        [
            "Provider",
            "Guest RAM",
            "Observed CPU model strings",
            "Execution incl. pilots/seeds",
        ],
        [
            [
                LABELS[p],
                f"{min(summary['hardware'][p]['memory_kib']) / 1024**2:.2f} GiB",
                "; ".join(summary["hardware"][p]["cpu_models"]),
                f"{summary['spent_seconds_including_pilot'][p] / 60:.2f} / 200 min",
            ]
            for p in providers
        ],
    )
    lines += [
        "",
        "GitHub's budget includes planning jobs from both runs and both original pilot attempts; Namespace includes its readiness run. No benchmark retries were needed. Boat reported "
        + f"{summary['boat_reported_total_vm_cost_usd'] * 100:.2f} cents of VM usage for its 35 full-run jobs, covered by its existing plan credit. Provider VM billing boundaries differ from Actions execution timestamps; no account invoice was inferred.",
        "",
        "## Monthly cost at fixed billable minutes",
        "",
        "USD list-rate scenarios, checked 8 November 2026. These rows fix **billable machine minutes**, not completed work. GitHub public standard compute is free. Paid GitHub is a hypothetical 4-core larger-runner rate projection: that product was not measured. Private standard Linux is normally 2 CPUs and cannot inherit these 4-CPU performance results.",
        "",
    ]
    lines += table(
        [
            "Billable min/month",
            "GitHub public",
            "GitHub paid 4-core gross",
            "Blacksmith gross",
            "Boat one-seat base",
            "Namespace 4×16 PAYG",
            "Namespace lowest listed plan",
        ],
        [
            [
                f"{r['runner_minutes']:,}",
                "$0",
                money(r["github_paid_4cpu_list_usd"]),
                money(r["blacksmith_4cpu_before_free_credit_usd"]),
                money(r["boat_4cpu_one_seat_base_usd"]),
                money(r["namespace_4cpu16gb_payg_usd"]),
                money(r["namespace_lowest_list_plan"]["usd"])
                + " ("
                + r["namespace_lowest_list_plan"]["plan"]
                + ")",
            ]
            for r in summary["monthly_minute_costs"]
        ],
    )
    lines += [
        "",
        "GitHub paid is $0.012/min with whole-minute job rounding. Team/Enterprise membership is separate; Team's shared $18 included compute value can reduce eligible larger-runner charges if still available. Public standard compute remains independently free. [Rates](https://docs.github.com/en/billing/reference/actions-runner-pricing), [allowances/storage](https://docs.github.com/en/billing/concepts/product-billing/github-actions).",
        "",
        "Blacksmith 4-vCPU Linux x64 is $0.008/min. Gross values exclude its advertised 3,000 free monthly minutes because first-party allowance normalization at 4 CPUs and rounding could not be verified. The documentation was inaccessible; do not subtract 3,000 raw 4-vCPU minutes without checking the account. [Pricing](https://www.blacksmith.sh/pricing).",
        "",
        "Boat default is $0.036/hour, billed per second. Its $20 one-seat plan returns the price as expiring VM credit: base=max($20,usage). Seats, extra starts, extra snapshots and optional services can add cost. [Pricing](https://docs.boat.dev/pricing).",
        "",
        "Namespace's tested 4-CPU/16-GB shape consumes **8 Linux unit-minutes per machine minute**, because memory also counts. PAYG is $0.012/min. Team is $100 including 100,000 units; Business $250 including 250,000; additional units cost $0.0015. Cheapest-plan projections assume those allowances are unshared. Billing has a one-minute minimum and a 15-second rounding grace; published examples are 30s→1min, 70s→1min, 150s→3min. Trial credits are excluded. [Namespace pricing](https://namespace.so/pricing).",
        "",
        "### Boat job-start sensitivity",
        "",
        "A $20 plan includes 12/60/200 starts per minute/hour/day; higher start brackets cost $0.03/$0.05/$0.07 and have hard ceilings. CI can wait instead. Scenarios below assume evenly spaced starts over 30 days and choose the cheapest listed plan plus required extra starts. No subscriptions or extra-start settings were changed. [Limits](https://docs.boat.dev/limits#extra-starts).",
        "",
    ]
    scenarios = []
    for minutes in [1000, 5000, 10000, 50000]:
        five = boat_monthly(minutes * 0.0006, minutes / 5)
        one = boat_monthly(minutes * 0.0006, minutes)
        scenarios.append(
            {"minutes": minutes, "five_minute_jobs": five, "one_minute_jobs": one}
        )
    lines += table(
        ["VM min/month", "5-min jobs", "1-min jobs"],
        [
            [
                f"{r['minutes']:,}",
                money(r["five_minute_jobs"]["total_usd"])
                + f" (plan ${r['five_minute_jobs']['plan_usd']})",
                money(r["one_minute_jobs"]["total_usd"])
                + f" (plan ${r['one_minute_jobs']['plan_usd']})",
            ]
            for r in scenarios
        ],
    )
    lines += [
        "",
        "At 50,000 one-minute starts the $20 plan cannot finish within a 30-day month at its daily maximum. Bursts, grouping tasks, queueing and other account usage change the result. Each scenario's job duration includes the entire billed VM lifetime.",
        "",
        "## Monthly cost for the same completed work",
        "",
        "One suite is five separate warm-cache jobs, one per workload. Uses measured job medians; Boat uses median API-reported job costs. Paid GitHub assumes public-runner timings carry over to an unmeasured paid runner. Blacksmith shows unrounded–whole-minute-rounded gross estimates. Namespace uses conservative whole-minute job rounding and shows PAYG / lowest listed plan; it omits the 15-second grace and any VM time outside Actions, so it is a planning estimate. Boat assumes evenly spaced starts over 30 days and cheapest listed plan. Public GitHub remains $0.",
        "",
    ]
    rows = []
    for count in [1000, 5000, 10000, 50000]:
        selected = {
            r["provider"]: r
            for r in summary["equal_work_costs"]
            if r["five_job_suites"] == count
        }
        boat = boat_monthly(selected["boat"]["boat_measured_vm_base_usd"], count * 5)
        ns = selected["namespace"]
        rows.append(
            [
                f"{count:,}",
                "$0",
                money(selected["github"]["github_paid_list_rounded_usd"]),
                money(selected["blacksmith"]["blacksmith_unrounded_gross_usd"])
                + "–"
                + money(selected["blacksmith"]["blacksmith_rounded_gross_usd"]),
                money(boat["total_usd"]) + f" (plan ${boat['plan_usd']})"
                if boat
                else "Beyond ceiling",
                money(ns["namespace_ceil_minute_payg_usd"])
                + " / "
                + money(ns["namespace_ceil_minute_lowest_plan"]["usd"])
                + " ("
                + ns["namespace_ceil_minute_lowest_plan"]["plan"]
                + ")",
            ]
        )
    lines += table(
        [
            "Five-job suites/month",
            "GitHub public",
            "GitHub paid gross",
            "Blacksmith gross range",
            "Boat start scenario",
            "Namespace PAYG / best plan",
        ],
        rows,
    )
    lines += [
        "",
        "Compute estimates exclude tax, negotiated discounts, account credits, GitHub membership, artifact/archive storage and optional add-ons. GitHub includes 10 GB repository cache; Blacksmith's account-specific archive pricing was not verified. Namespace persistent cache volumes were not enabled, so their storage/snapshot fees are not added. Starting new projects also incurs setup and cache-seeding work. These figures are not invoice quotes.",
        "",
        "## Evidence and reproduction",
        "",
    ]
    lines += [
        f"- [Run {run['id']} raw evidence](results/{run['id']}/evidence.json)"
        for run in runs
    ]
    lines += [
        f"- [Combined summary](results/{dataset}/summary.json), [samples](results/{dataset}/samples.csv), [stage timings/resources](results/{dataset}/stages.csv)",
        "- [Original cache audit](results/42508215226/cache-audit.json), [Namespace cache audit](results/42512395289/cache-audit.json), [Boat usage](results/42508215226/boat-usage.json)",
        "- [Interactive overview](reports/overview.html) and [methodology](METHODOLOGY.md)",
        "",
        "All workflows are manual. GCP, Depot, macOS, Docker image-build performance and production operations remain outside this experiment.",
        "",
    ]
    (ROOT / "REPORT.md").write_text("\n".join(lines))
    (path / "boat-cost-scenarios.json").write_text(
        json.dumps(scenarios, indent=2) + "\n"
    )
    html = (
        (ROOT / "reports/template.html")
        .read_text()
        .replace("__SUMMARY__", json.dumps(summary).replace("</", "<\\/"))
    )
    (ROOT / "reports/overview.html").write_text(html)
    print("Published four-provider REPORT.md and reports/overview.html")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("dataset", choices=["comparison"])
    publish(parser.parse_args().dataset)
