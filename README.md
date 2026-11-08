# CI runner bench

Small, manually triggered CI experiments on GitHub-hosted, Blacksmith and Boat
runners. This repository contains no application or production credentials.

**The full benchmark is complete:** all 105 workload jobs passed, covering five
workloads, cold/warm package caches and three repetitions on every provider.
Read the [speed and monthly-cost report](REPORT.md), open the
[interactive overview](reports/overview.html), or inspect the
[raw evidence](results/42508215226/evidence.json).

## First run

The **Provider smoke** workflow runs one job per provider. It validates checkout,
pinned Node/Python/Rust toolchains, small language programs, Docker and a byte-for-byte
1 MiB cache save/restore. It uploads environment and check evidence as JSON.
Smoke timings are capability checks, not performance rankings.

The requested Linux tiers are GitHub Ubuntu 24.04, Blacksmith 4-vCPU Ubuntu 24.04
and default Boat. CPU, memory and cgroup limits are recorded; equal labels are not
proof of equal hardware. No workload is scheduled automatically on push or PR.

## Budget

The initial smoke run has three jobs with eight-minute timeouts (at most 24
scheduled execution minutes across all providers, plus platform teardown overhead).
Subsequent benchmarks have a ceiling of 200 aggregate runner-minutes per provider,
including setup, cache seeding, failures and retries. Provider billing credits and
VM lifetime are accounted for separately.

GCP and Depot are outside the initial scope. Do not add credentials, deployment
steps or release publishing to this benchmark.

## Workload catalog

Upstream code is fetched at full commit IDs in `workloads.json`. It stays in the
ignored `.bench/` directory; upstream licenses remain with their source trees.

| Workload | Upstream | Different CI behavior covered |
| --- | --- | --- |
| TypeScript compiler | [microsoft/TypeScript](https://github.com/microsoft/TypeScript), v6.0.3 | Locked npm installation, diagnostic generation, compiler type checking, JS emit, esbuild bundling and parser correctness |
| Rust regex | [rust-lang/rustc-perf](https://github.com/rust-lang/rustc-perf), regex-automata corpus | Dependency fetching, library checking and clean optimized compilation |
| Rust ripgrep | [BurntSushi/ripgrep](https://github.com/BurntSushi/ripgrep) | Workspace compilation, library tests and verified search over a deterministic corpus |
| Python Jinja | [pallets/jinja](https://github.com/pallets/jinja) | Locked environment creation, upstream pytest suite and template rendering |
| Python runtime | [python/pyperformance](https://github.com/python/pyperformance), 1.14.0 | Small JSON and regex runtime benchmarks using the suite's fast mode |

The compiler workload follows the maintained `strada-compiler` case in
[Microsoft's benchmarking repository](https://github.com/microsoft/typescript-benchmarking).
The older Compiler/Compiler-Unions fixtures produce diagnostics with modern
TypeScript; they are deliberately not used. We do not count failing compilations
as successful builds or silently ignore diagnostics.

```sh
mise trust
mise install
python scripts/bench.py list
python scripts/bench.py run typescript-compiler --cache cold
python scripts/bench.py run typescript-compiler --cache warm
```

Commands are identical across providers. `cold` clears only this harness's local
package caches; it does not claim to flush host page caches or registry CDNs.
`warm` requires a successful matching seed. Build directories and virtual
environments are recreated in both modes. Rust compilation is capped at four
jobs on every provider. Package-manager cache locations are explicit and all
reside under `.bench/cache/<workload>/`.

A native provider cache can save that directory between fresh runners using a
provider/workload/toolchain/lockfile-specific key. It must not include source
checkouts, build outputs, virtual environments, or results. The cache's admission
marker checks the pinned source and configuration, and the underlying package
manager still performs normal integrity checks. Warm jobs fail if a matching
cache is absent. Archive keys must never be shared across providers' filesystem
layouts.

Per-stage timing and pass/fail JSON is written to `.bench/results/`. Raw
pyperformance output stays in the workload's work directory. Local validation
is for correctness only and is not part of cloud rankings.

## Full benchmark

The manual **Benchmark** workflow runs five cache-seeding jobs per provider,
then three cold and three warm fresh-runner samples per workload/provider.
All seeds must pass before measurement starts. Six matrix jobs run at once;
each workload job has a five-minute timeout. No benchmark starts on push or PR.

```sh
gh workflow run benchmark.yml --repo aurentisio/ci-runner-bench --ref main \
  -f provider=all -f workload=all
# After completion, use its run ID:
python scripts/collect.py RUN_ID
python scripts/analyze.py RUN_ID
# Rebuild the reviewed report for this archived experiment:
python scripts/publish.py 42508215226
```

The scripts preserve and validate per-stage timing, resource use, environment,
cache admission and Actions metadata. Provider-native archive caches retain only
package dependencies. Incremental build outputs, VM snapshots and sticky disks
are separate experiments. The run-specific Boat usage and cache audit were
collected through its CLI and GitHub logs; `analyze.py` requires the Boat usage
file before producing billing projections. The narrative report and overview
contain findings specific to the first run and must be reviewed for any rerun.

See [METHODOLOGY.md](METHODOLOGY.md) for metric definitions, limitations and budget
accounting. [REPORT.md](REPORT.md) includes medians/ranges, cache effectiveness,
1k/5k/10k/50k monthly-minute projections and equal-workload cost scenarios.
Public GitHub and hypothetical paid 4-core GitHub prices are separate. Unknown
Blacksmith allowance normalization/rounding and Boat's job-start costs are explicit.

## Pilot status

[Successful smoke run](https://github.com/aurentisio/ci-runner-bench/actions/runs/42506897147):
GitHub, Blacksmith and Boat all passed toolchain, Docker, cache save/restore and
artifact checks. The probe's restored bytes matched on all three providers.
[Committed pilot evidence](results/pilot.json) records tool versions, actual
CPU/memory and execution time spent on the pilot attempts.

All three exposed four CPUs. Boat exposed about 8 GB RAM, while GitHub and
Blacksmith exposed about 16 GB; this remains a visible qualification for later
comparisons. The first attempt passed the functional probes but failed the
artifact step because hidden files were excluded; that workflow error was fixed.

Local correctness validation passed all five upstream workloads, including the
Jinja tests, ripgrep library tests and exact search-count verification. Warm
cache admission and clean rebuilds were also exercised on TypeScript and the
Rust regex corpus. Ripgrep is pinned to release 15.1.0 because newer development
commits require a newer Rust compiler than this suite's shared pinned toolchain.
The [full performance matrix](https://github.com/aurentisio/ci-runner-bench/actions/runs/42508215226)
subsequently passed all 106 jobs including planning. Including pilots and seeds,
execution totaled 26.85 minutes on GitHub, 18.70 on Blacksmith and 28.60 on Boat.

## Namespace readiness

Namespace is connected to `aurentisio` and can access this repository. Its
[readiness run](https://github.com/aurentisio/ci-runner-bench/actions/runs/42512002388)
passed checkout, the pinned toolchains, TypeScript/Rust/Python probes, Docker,
byte-verified 1 MiB archive-cache save/restore and artifact upload. The job used
`nscloud-ubuntu-24.04-amd64-4x16`, exposed four CPUs and about 16 GB RAM, and took
15 seconds of Actions execution. [Readiness evidence](results/namespace-readiness)
is preserved separately from the original three-provider benchmark.

This is a connectivity/capability check. Namespace has not yet run the full
workload matrix, and these smoke timings do not establish a speed ranking.
Namespace's native persistent cache volumes were not exercised by this check.
