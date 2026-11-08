# CI runner benchmark — 8 November 2026

[Completed workflow](https://github.com/aurentisio/ci-runner-bench/actions/runs/42508215226) · measured commit `81e48cd0f04e0f7b8efc577a094f760feb25f5d8` · 105/105 workload jobs passed on the first attempt, plus the planning job. The workflow ran for about 15 minutes with six matrix jobs allowed at once.

**Blacksmith finished these short CI jobs fastest overall.** A serial warm-cache five-job suite, calculated by summing workload medians, took **154 seconds on Blacksmith, 218 seconds on GitHub, and 225 seconds on Boat**. Blacksmith used 29% less execution time than GitHub; Boat used 3% more. This is an equal-workload summary, not the parallel workflow critical path.

Boat often executed computation quickly, but tool setup and cache transfer erased that advantage at job level. Public GitHub runner compute is free. Boat has a very low VM rate but a paid plan minimum and start limits; Blacksmith is the strongest speed result here. These findings apply to the tested Linux tiers and workloads, not macOS, larger runners, Docker builds, or every private repository.

## Complete-job speed

Seconds, **median (minimum–maximum)** over three fresh runners per cell. Includes setup, cache transfer, source fetch, dependencies, build/tests and upload/cleanup. Lower is better. Seeds are excluded.

| Workload | Cache | GitHub | Blacksmith | Boat |
| --- | --- | ---: | ---: | ---: |
| typescript-compiler | cold | **57** (55–61) | **39** (32–42) | **58** (56–61) |
| typescript-compiler | warm | **63** (56–73) | **46** (41–49) | **65** (62–67) |
| rust-regex | cold | **38** (36–40) | **27** (23–28) | **32** (30–33) |
| rust-regex | warm | **29** (27–36) | **25** (20–27) | **39** (38–74) |
| rust-ripgrep | cold | **64** (58–71) | **36** (35–44) | **47** (43–50) |
| rust-ripgrep | warm | **67** (51–69) | **34** (34–34) | **52** (48–54) |
| python-jinja | cold | **20** (19–23) | **19** (16–20) | **25** (24–56) |
| python-jinja | warm | **21** (21–21) | **20** (17–21) | **28** (27–81) |
| python-pyperformance | cold | **42** (38–42) | **35** (29–35) | **40** (39–67) |
| python-pyperformance | warm | **38** (35–40) | **29** (28–29) | **41** (41–46) |

| Serial sum of five job medians | GitHub | Blacksmith | Boat |
| --- | ---: | ---: | ---: |
| cold | 221 s | 156 s | 202 s |
| warm | 218 s | 154 s | 225 s |

Across equally weighted workload ratios, the geometric-mean complete-job speedups versus GitHub were 1.36× Blacksmith / 1.06× Boat cold, and 1.34× Blacksmith / 0.92× Boat warm. These differ from the serial sum because every workload receives equal weight regardless of duration.

## What the caches actually changed

All 45 warm samples restored a matching seed and passed. Representative exact-key cache hits, archive sizes and Blacksmith transparent-cache activation are preserved in [cache-audit.json](results/42508215226/cache-audit.json). The same package-cache policy and commands were used on every provider; no compiled outputs or virtual environments were retained.

| Provider | Workload | Cold dependency install | Warm dependency install | Warm restore |
| --- | --- | ---: | ---: | ---: |
| GitHub | typescript-compiler | 3.79 s | 3.81 s | 1 s |
| GitHub | rust-regex | 5.90 s | 0.07 s | 1 s |
| GitHub | rust-ripgrep | 5.49 s | 0.12 s | 2 s |
| GitHub | python-jinja | 0.52 s | 0.47 s | 1 s |
| GitHub | python-pyperformance | 0.37 s | 0.12 s | 2 s |
| Blacksmith | typescript-compiler | 2.08 s | 1.84 s | 1 s |
| Blacksmith | rust-regex | 2.92 s | 0.06 s | 1 s |
| Blacksmith | rust-ripgrep | 2.37 s | 0.06 s | 0 s |
| Blacksmith | python-jinja | 0.37 s | 0.31 s | 0 s |
| Blacksmith | python-pyperformance | 0.21 s | 0.06 s | 1 s |
| Boat | typescript-compiler | 2.63 s | 1.59 s | 13 s |
| Boat | rust-regex | 2.32 s | 0.06 s | 11 s |
| Boat | rust-ripgrep | 1.72 s | 0.06 s | 7 s |
| Boat | python-jinja | 0.36 s | 0.26 s | 3 s |
| Boat | python-pyperformance | 0.41 s | 0.06 s | 5 s |

The clearest cache benefit was Cargo: warm fetching fell to approximately 0.06–0.12 seconds. On Boat, however, Rust regex restored in a median 11 seconds, compared with only 2.32 seconds for cold fetching. TypeScript's roughly 52 MB archive took a median 13 seconds to restore on Boat, versus about 1 second on GitHub/Blacksmith. Fast npm/uv cold installation leaves little room to recover transfer overhead.

A warm sample taking longer overall does **not** establish that cached dependencies slowed its compilation. Different fresh hosts were assigned to repetitions, and source-fetch/network/runtime variance remains visible in the ranges. GitHub exposed six CPU model strings across the run; Boat exposed two. Compare cache transfer plus dependency time to diagnose caching, rather than attributing every cold/warm job difference to the cache.

For these workloads, retain Blacksmith's native cache for Cargo and measure whether small Python/npm caches justify even its low restore overhead. On Boat, skip archive caching where transfer exceeds fresh installation; test snapshots or a persistent native cache separately before adopting them. Incremental Rust target caching could have a much larger benefit, but was intentionally excluded from the matched clean-build comparison. For longer CI jobs, setup overhead becomes a smaller proportion of the total.

## Computation and Python runtime

Compute-stage geometric-mean speedups against GitHub were 1.54× Blacksmith / 1.62× Boat cold, and 1.67× Blacksmith / 1.87× Boat warm. This excludes source fetch and dependency installation. It includes the pyperformance harness's process/environment overhead, so the raw runtime measurements below provide a separate view.

| pyperformance operation | GitHub | Blacksmith | Boat |
| --- | ---: | ---: | ---: |
| json_dumps | 7.23 ms | 4.05 ms | 3.85 ms |
| regex_v8 | 18.34 ms | 9.78 ms | 9.15 ms |

Runtime cells are medians of six measured job medians (cold and warm together), using pyperformance's short `--fast` mode. They are directional estimates; no p95, statistical-significance or publication-quality stability claims are made. Full worker/calibration values remain in the raw evidence.

## Hardware and budget

| Provider | Exposed CPUs | Guest memory | Total execution including both pilot attempts |
| --- | ---: | ---: | ---: |
| GitHub | 4 | 15.61 GiB | 26.85 min / 200 min |
| Blacksmith | 4 | 15.42 GiB | 18.70 min / 200 min |
| Boat | 4 | 7.76 GiB | 28.60 min / 200 min |

GitHub hosts included AMD EPYC and Intel Xeon models. Blacksmith reported Intel Xeon or AMD EPYC; Boat reported Ryzen 9 9950X or Ryzen 7 9700X. These are provider product comparisons with different memory, kernels and host allocation, not an identical-CPU laboratory experiment. Every job used the same pinned Node/Python/Rust/uv versions and four-CPU affinity. Hardware/model details are preserved for every sample.

Boat's API reports **$0.02** of VM usage for the 35 full-run jobs (1.91 cents), before applying plan credit. The API's usage value is not an additional monthly invoice; its billing boundary differs from Actions execution timestamps. No benchmark retries were needed. The earlier pilot's two artifact-upload failures count in the budget.

## Monthly runner-minute costs

USD list-rate scenarios checked 8 November 2026. Each row means the same number of **billable provider minutes**, not the same amount of completed work. Paid GitHub is a 4-core larger-runner rate projection; that product was **not** benchmarked. The measured public standard 4-CPU GitHub tier is free. Private standard Linux is normally 2 CPUs, so its price/performance cannot be substituted into this 4-CPU comparison.

| Billable min/month | GitHub public measured tier | GitHub paid 4-core gross | Blacksmith 4-vCPU gross | Boat default base, one seat |
| ---: | ---: | ---: | ---: | ---: |
| 1,000 | $0 | $12.00 | $8.00 | $20.00 |
| 5,000 | $0 | $60.00 | $40.00 | $20.00 |
| 10,000 | $0 | $120.00 | $80.00 | $20.00 |
| 50,000 | $0 | $600.00 | $400.00 | $30.00 |

GitHub paid uses $0.012/min and rounds each job up to a whole minute; Team/Enterprise membership is separate. Eligible larger-runner usage can draw from the account's included compute value. Team currently includes $18/month, shared with other eligible compute; subtract only what remains available. Public standard runners remain independently free. [Runner rates](https://docs.github.com/en/billing/reference/actions-runner-pricing), [allowances/storage](https://docs.github.com/en/billing/concepts/product-billing/github-actions).

Blacksmith's 4-vCPU Linux x64 selector lists $0.008/min. It advertises 3,000 free monthly minutes; the table deliberately shows **gross before that credit**, because the accessible first-party pricing page does not establish the normalization at 4 vCPUs or billing rounding. Its full documentation was inaccessible during this experiment. Do not subtract 3,000 raw 4-vCPU minutes without checking the account's allowance. [Blacksmith pricing](https://www.blacksmith.sh/pricing).

Boat default is $0.036/hour ($0.0006/min), metered per second. A $20 one-seat plan returns its price as expiring VM credit: base = max($20, VM usage). Extra seats raise the minimum. Snapshots beyond the included count, extra starts and optional services are separate. [Boat pricing](https://docs.boat.dev/pricing).

### Boat's start limits materially change short-job costs

The $20 plan includes 12/60/200 starts per minute/hour/day. Daily starts 201–300 cost $0.03 each, 301–400 $0.05, and 401–1,200 $0.07; the highest applicable minute/hour/day bracket applies. CI can instead wait for capacity. Extra starts are not enabled by this experiment. [Start limits](https://docs.boat.dev/limits#extra-starts).

The following **planning scenarios** assume evenly spaced jobs over 30 days, no other account usage, and choosing the cheapest advertised plan plus required extra starts. They do not change your subscription and do not predict bursty workloads. Each duration includes the VM's entire billed lifetime.

| VM minutes/month | If each job lasts 5 min | If each job lasts 1 min |
| ---: | ---: | ---: |
| 1,000 | $20.00 (plan $20) | $20.00 (plan $20) |
| 5,000 | $20.00 (plan $20) | $20.00 (plan $20) |
| 10,000 | $20.00 (plan $20) | $100.00 (plan $100) |
| 50,000 | $100.00 (plan $100) | $500.00 (plan $500) |

At 50,000 one-minute jobs the $20 plan cannot finish all starts within a 30-day month at its maximum daily start ceiling. Spreading bursts, grouping tiny tasks into one job, queueing, or selecting a different plan changes the economics. The low VM rate alone is insufficient for estimating short-job CI costs.

## Same completed work per month

One suite = all five workloads as **five separate warm-cache jobs**. Extrapolations use observed job medians; Boat uses median API-reported per-job VM cost, which includes its billing overhead. GitHub paid assumes the observed public timings carry over to an unmeasured paid 4-core runner. Blacksmith shows unrounded–whole-minute-rounded **gross** estimates because rounding was not verified. Boat chooses the cheapest plan under evenly spaced starts over 30 days; bursts or other usage can cost more. Public GitHub compute remains $0 for every row.

| Five-job suites/month | GitHub public | GitHub paid 4-core gross, hypothetical | Blacksmith gross range | Boat even-start planning scenario |
| ---: | ---: | ---: | ---: | ---: |
| 1,000 | $0 | $84.00 | $20.53–$40.00 | $20.00 (plan $20) |
| 5,000 | $0 | $420.00 | $102.67–$200.00 | $100.00 (plan $100) |
| 10,000 | $0 | $840.00 | $205.33–$400.00 | $500.00 (plan $500) |
| 50,000 | $0 | $4,200.00 | $1,026.67–$2,000.00 | $12,300.00 (plan $2000) |

These are runner-compute planning figures before tax, negotiated discounts and account credits. GitHub Team/Enterprise fees, archive/artifact storage and optional add-ons are excluded from these tables. No sticky disk or retained-build add-on was selected in the measured workloads. GitHub's repository cache allowance is 10 GB; the saved cache set here is small. Blacksmith's account-specific archive-cache allowance/charges were not verified, so the table is not a complete invoice quote. Setup and cold cache-seeding cost are additional when starting a new project; the benchmark's actual seeds are included in the execution-budget evidence.

## Evidence and reproduction

- [Raw workload, runtime and Actions evidence](results/42508215226/evidence.json)
- [Per-sample CSV](results/42508215226/samples.csv) and [per-stage CSV](results/42508215226/stages.csv)
- [Machine-readable summary](results/42508215226/summary.json), [Boat usage](results/42508215226/boat-usage.json) and [cache audit](results/42508215226/cache-audit.json)
- [Interactive overview](reports/overview.html)
- [Methodology and reproduction commands](METHODOLOGY.md)

All workflows remain manual. No GCP infrastructure, Depot runs, macOS releases or production operations form part of this experiment.
