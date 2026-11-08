# CI runner bench

Small, manually triggered CI experiments on GitHub-hosted, Blacksmith and Boat
runners. This repository contains no application or production credentials.

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

## Measurement phase, after the smoke gate

The full cloud benchmark matrix is not enabled yet. Start with five workloads,
cold/warm dependency states and three fresh-runner samples each. Keep identical
commands and cache contents, while using each provider's supported cache backend.
Seeding, slow samples, failures and retries count toward the 200-minute budget.
Use remaining time for provider-native optimizations as a separately labelled
experiment; do not mix snapshots, retained build outputs or incremental builds
into the matched comparison.

Record queue/startup time separately from job execution, tooling, cache transfer,
source fetch, dependencies, build/test work and upload/teardown. Report medians,
ranges and failures; three samples do not establish tail-latency percentiles.
Keep hardware and memory differences visible. No speed ranking is inferred from
the smoke check.

The final cost model will show 1,000 / 5,000 / 10,000 / 50,000 runner-minutes per
month and equal numbers of completed workloads. Include weighted allowances,
subscriptions, cache storage and setup costs. Public/free and private/paid usage
must be separate; dollar totals must not assume every provider normalizes minutes
the same way. Cost data is not available from the smoke probe alone.

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
No full performance matrix has been launched.
