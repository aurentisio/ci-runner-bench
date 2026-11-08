# CI runner benchmark — four-provider ranking

**Namespace narrowly leads the observed warm-cache total; Blacksmith leads cold-cache totals.** The warm leader totals **149 seconds**, using the sum of five workload medians: **32% less job execution time than GitHub**. This is a serial five-job summary, not the actual parallel workflow duration.

Namespace and Blacksmith are close: warm totals are 149 versus 154 seconds, while cold totals are 161 versus 156 seconds. A roughly 3% gap with three samples in separate runs is not evidence of a statistically established winner. Namespace leads Python and the Rust regex workload; Blacksmith leads TypeScript; warm ripgrep medians tie.

All **140 workload jobs** passed: 20 cache seeds and 120 measured jobs. Each workload/provider/cache group has three fresh-runner samples. Seeds count toward execution budgets but not speed rankings.

## Run provenance and comparison limits

The original GitHub/Blacksmith/Boat run and the later Namespace run were executed separately on 8 November 2026. They are not a simultaneous race. The Namespace-only matrix could schedule six jobs on that provider at once; the original matrix shared six slots among three providers. Scheduling/host load and network conditions may differ. No workflow-elapsed throughput ranking is inferred.

- [Run 42508215226](https://github.com/aurentisio/ci-runner-bench/actions/runs/42508215226): 2026-11-08T18:05:31Z → 2026-11-08T18:20:27Z; commit `81e48cd0f04e0f7b8efc577a094f760feb25f5d8`.
- [Run 42512395289](https://github.com/aurentisio/ci-runner-bench/actions/runs/42512395289): 2026-11-08T18:55:24Z → 2026-11-08T19:00:13Z; commit `75170bba71bd7e7c2817d1b65de1aeeb59e34376`.

The analyzer verified equal workload-harness syntax (ignoring only module documentation and import ordering), identical reusable workload workflow, source/configuration identities, tool versions and four-CPU affinity across all inputs. Full commits differ because orchestration, documentation and provider support changed. The original [three-provider report](reports/initial-three-providers.md) and raw evidence remain available.

This ranking uses **dependency-only archive caching and clean builds**. Namespace uses the same pinned `actions/cache` action and cache-content policy; its native persistent cache volumes, custom images and checkout caching are **not enabled**. Blacksmith automatically enables its transparent archive-cache backend. This establishes a matched baseline, not the maximum optimized performance of each provider.

## Complete-job speed

Seconds: **median (minimum–maximum)**, n=3. Includes setup, pinned tool installation, archive restore, source fetch, dependencies, builds/tests, upload and cleanup; excludes queueing. Lower is better.

| Workload | Cache | GitHub | Blacksmith | Boat | Namespace |
| --- | --- | --- | --- | --- | --- |
| typescript-compiler | cold | **57** (55–61) | **39** (32–42) | **58** (56–61) | **54** (51–54) |
| typescript-compiler | warm | **63** (56–73) | **46** (41–49) | **65** (62–67) | **52** (49–53) |
| rust-regex | cold | **38** (36–40) | **27** (23–28) | **32** (30–33) | **24** (23–25) |
| rust-regex | warm | **29** (27–36) | **25** (20–27) | **39** (38–74) | **20** (20–20) |
| rust-ripgrep | cold | **64** (58–71) | **36** (35–44) | **47** (43–50) | **37** (37–38) |
| rust-ripgrep | warm | **67** (51–69) | **34** (34–34) | **52** (48–54) | **34** (34–35) |
| python-jinja | cold | **20** (19–23) | **19** (16–20) | **25** (24–56) | **16** (14–17) |
| python-jinja | warm | **21** (21–21) | **20** (17–21) | **28** (27–81) | **15** (15–17) |
| python-pyperformance | cold | **42** (38–42) | **35** (29–35) | **40** (39–67) | **30** (30–31) |
| python-pyperformance | warm | **38** (35–40) | **29** (28–29) | **41** (41–46) | **28** (28–29) |

### Serial suite totals

| Cache | GitHub | Blacksmith | Boat | Namespace |
| --- | --- | --- | --- | --- |
| cold | 221 s | 156 s | 202 s | 161 s |
| warm | 218 s | 154 s | 225 s | 149 s |

The warm suite order is Namespace (149 s) → Blacksmith (154 s) → GitHub (218 s) → Boat (225 s). Rankings describe these products and short workloads, not all CI or identical physical hardware.

### Geometric-mean speedups versus GitHub

Every workload has equal weight in this table. Ratios above 1× mean faster. These differ from serial totals, which give long jobs more weight.

| Provider | Cold complete job | Warm complete job | Cold compute | Warm compute |
| --- | --- | --- | --- | --- |
| GitHub | 1.00× | 1.00× | 1.00× | 1.00× |
| Blacksmith | 1.36× | 1.34× | 1.54× | 1.67× |
| Boat | 1.06× | 0.92× | 1.62× | 1.87× |
| Namespace | 1.38× | 1.46× | 1.49× | 1.70× |

## Cache effectiveness

All **60 warm jobs** restored a successful matching seed and passed package-manager integrity checks. The cache contains only npm/Cargo/uv/pip package data; source, compiled outputs, target directories and virtual environments are recreated. Cold does not flush registry/CDN, host or provider infrastructure caches.

Dependency installation and archive restore are separate below. Restore step timings have one-second resolution, so 0 s means below the timestamp resolution.

| Provider | Workload | Cold install | Warm install | Warm restore |
| --- | --- | --- | --- | --- |
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
| Namespace | typescript-compiler | 4.49 s | 3.44 s | 1 s |
| Namespace | rust-regex | 3.67 s | 0.06 s | 1 s |
| Namespace | rust-ripgrep | 3.07 s | 0.06 s | 1 s |
| Namespace | python-jinja | 0.36 s | 0.26 s | 1 s |
| Namespace | python-pyperformance | 0.41 s | 0.06 s | 1 s |

In the original run, Boat's TypeScript archive (~52 MB) took a median 13 seconds to restore, while cold dependency installation took 2.63 seconds. Cargo's warm dependency fetch was much faster, but Boat's transfer often outweighed the saving. Small npm/uv caches also have little room to recover transfer overhead. A warmer job taking longer overall does not prove its cached dependencies slowed compilation: source-fetch, hardware and runtime variance remain visible in the ranges.

Namespace's archive restores took a median 1 second for each workload. Cargo fetching fell to about 0.06 seconds warm, so the dependency saving exceeded the restore cost. TypeScript's combined dependency work was 4.49 seconds cold versus 3.44 seconds warm plus 1 second of restoration: little net gain. The one-second archive restore also exceeds the small Python dependency-install savings. These are archive-cache observations, not measurements of Namespace's persistent cache volumes.

Prefer a cache when the dependency work it saves exceeds restoration cost. Native persistent cache volumes or snapshots could change that result, but require a separately labelled test. Incremental Rust target caching was excluded here to preserve clean builds. Namespace's native-volume advantage is therefore not established by this experiment.

## Python runtime

Milliseconds per operation: median of six measured job medians (cold and warm combined). pyperformance uses `--fast` for JSON/regex; these are directional estimates with worker/calibration evidence preserved, not stable publication-quality claims.

| Operation | GitHub | Blacksmith | Boat | Namespace |
| --- | --- | --- | --- | --- |
| json_dumps | 7.23 ms | 4.05 ms | 3.85 ms | 4.06 ms |
| regex_v8 | 18.34 ms | 9.78 ms | 9.15 ms | 8.98 ms |

## Hardware and execution budget

Each product exposed four CPUs. Boat has ~8 GB RAM; the others ~16 GB. CPU models, kernels and provider images vary. Three samples do not establish tail latency or statistical significance.

| Provider | Guest RAM | Observed CPU model strings | Execution incl. pilots/seeds |
| --- | --- | --- | --- |
| GitHub | 15.61 GiB | AMD EPYC 7763 64-Core Processor; AMD EPYC 9V45 96-Core Processor; AMD EPYC 9V74 80-Core Processor; INTEL(R) XEON(R) PLATINUM 8573C; Intel(R) Xeon(R) 6973P-C; Intel(R) Xeon(R) Platinum 8370C CPU @ 2.80GHz | 26.97 / 200 min |
| Blacksmith | 15.42 GiB | AMD EPYC; Intel(R) Xeon(R) Processor | 18.70 / 200 min |
| Boat | 7.76 GiB | AMD Ryzen 7 9700X 8-Core Processor; AMD Ryzen 9 9950X 16-Core Processor | 28.60 / 200 min |
| Namespace | 15.68 GiB | AMD EPYC | 18.47 / 200 min |

GitHub's budget includes planning jobs from both runs and both original pilot attempts; Namespace includes its readiness run. No benchmark retries were needed. Boat reported 1.91 cents of VM usage for its 35 full-run jobs, covered by its existing plan credit. Provider VM billing boundaries differ from Actions execution timestamps; no account invoice was inferred.

## Monthly cost at fixed billable minutes

USD list-rate scenarios, checked 8 November 2026. These rows fix **billable machine minutes**, not completed work. GitHub public standard compute is free. Paid GitHub is a hypothetical 4-core larger-runner rate projection: that product was not measured. Private standard Linux is normally 2 CPUs and cannot inherit these 4-CPU performance results.

| Billable min/month | GitHub public | GitHub paid 4-core gross | Blacksmith gross | Boat one-seat base | Namespace 4×16 PAYG | Namespace lowest listed plan |
| --- | --- | --- | --- | --- | --- | --- |
| 1,000 | $0 | $12.00 | $8.00 | $20.00 | $12.00 | $12.00 (Developer) |
| 5,000 | $0 | $60.00 | $40.00 | $20.00 | $60.00 | $60.00 (Developer) |
| 10,000 | $0 | $120.00 | $80.00 | $20.00 | $120.00 | $100.00 (Team) |
| 50,000 | $0 | $600.00 | $400.00 | $30.00 | $600.00 | $475.00 (Business) |

GitHub paid is $0.012/min with whole-minute job rounding. Team/Enterprise membership is separate; Team's shared $18 included compute value can reduce eligible larger-runner charges if still available. Public standard compute remains independently free. [Rates](https://docs.github.com/en/billing/reference/actions-runner-pricing), [allowances/storage](https://docs.github.com/en/billing/concepts/product-billing/github-actions).

Blacksmith 4-vCPU Linux x64 is $0.008/min. Gross values exclude its advertised 3,000 free monthly minutes because first-party allowance normalization at 4 CPUs and rounding could not be verified. The documentation was inaccessible; do not subtract 3,000 raw 4-vCPU minutes without checking the account. [Pricing](https://www.blacksmith.sh/pricing).

Boat default is $0.036/hour, billed per second. Its $20 one-seat plan returns the price as expiring VM credit: base=max($20,usage). Seats, extra starts, extra snapshots and optional services can add cost. [Pricing](https://docs.boat.dev/pricing).

Namespace's tested 4-CPU/16-GB shape consumes **8 Linux unit-minutes per machine minute**, because memory also counts. PAYG is $0.012/min. Team is $100 including 100,000 units; Business $250 including 250,000; additional units cost $0.0015. Cheapest-plan projections assume those allowances are unshared. Billing has a one-minute minimum and a 15-second rounding grace; published examples are 30s→1min, 70s→1min, 150s→3min. Trial credits are excluded. [Namespace pricing](https://namespace.so/pricing).

### Boat job-start sensitivity

A $20 plan includes 12/60/200 starts per minute/hour/day; higher start brackets cost $0.03/$0.05/$0.07 and have hard ceilings. CI can wait instead. Scenarios below assume evenly spaced starts over 30 days and choose the cheapest listed plan plus required extra starts. No subscriptions or extra-start settings were changed. [Limits](https://docs.boat.dev/limits#extra-starts).

| VM min/month | 5-min jobs | 1-min jobs |
| --- | --- | --- |
| 1,000 | $20.00 (plan $20) | $20.00 (plan $20) |
| 5,000 | $20.00 (plan $20) | $20.00 (plan $20) |
| 10,000 | $20.00 (plan $20) | $100.00 (plan $100) |
| 50,000 | $100.00 (plan $100) | $500.00 (plan $500) |

At 50,000 one-minute starts the $20 plan cannot finish within a 30-day month at its daily maximum. Bursts, grouping tasks, queueing and other account usage change the result. Each scenario's job duration includes the entire billed VM lifetime.

## Monthly cost for the same completed work

One suite is five separate warm-cache jobs, one per workload. Uses measured job medians; Boat uses median API-reported job costs. Paid GitHub assumes public-runner timings carry over to an unmeasured paid runner. Blacksmith shows unrounded–whole-minute-rounded gross estimates. Namespace uses conservative whole-minute job rounding and shows PAYG / lowest listed plan; it omits the 15-second grace and any VM time outside Actions, so it is a planning estimate. Boat assumes evenly spaced starts over 30 days and cheapest listed plan. Public GitHub remains $0.

| Five-job suites/month | GitHub public | GitHub paid gross | Blacksmith gross range | Boat start scenario | Namespace PAYG / best plan |
| --- | --- | --- | --- | --- | --- |
| 1,000 | $0 | $84.00 | $20.53–$40.00 | $20.00 (plan $20) | $60.00 / $60.00 (Developer) |
| 5,000 | $0 | $420.00 | $102.67–$200.00 | $100.00 (plan $100) | $300.00 / $250.00 (Team) |
| 10,000 | $0 | $840.00 | $205.33–$400.00 | $500.00 (plan $500) | $600.00 / $475.00 (Business) |
| 50,000 | $0 | $4,200.00 | $1,026.67–$2,000.00 | $12,300.00 (plan $2000) | $3,000.00 / $2,875.00 (Business) |

Compute estimates exclude tax, negotiated discounts, account credits, GitHub membership, artifact/archive storage and optional add-ons. GitHub includes 10 GB repository cache; Blacksmith's account-specific archive pricing was not verified. Namespace persistent cache volumes were not enabled, so their storage/snapshot fees are not added. Starting new projects also incurs setup and cache-seeding work. These figures are not invoice quotes.

## Evidence and reproduction

- [Run 42508215226 raw evidence](results/42508215226/evidence.json)
- [Run 42512395289 raw evidence](results/42512395289/evidence.json)
- [Combined summary](results/comparison/summary.json), [samples](results/comparison/samples.csv), [stage timings/resources](results/comparison/stages.csv)
- [Original cache audit](results/42508215226/cache-audit.json), [Namespace cache audit](results/42512395289/cache-audit.json), [Boat usage](results/42508215226/boat-usage.json)
- [Interactive overview](reports/overview.html) and [methodology](METHODOLOGY.md)

All workflows are manual. GCP, Depot, macOS, Docker image-build performance and production operations remain outside this experiment.
