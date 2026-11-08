# Measurement method

The experiment compares three configured Linux x64 runner products, rather than
claiming identical physical hardware: public GitHub `ubuntu-24.04`, Blacksmith
`blacksmith-4vcpu-ubuntu-2404`, and Boat `boat` (default size). Each exposes four
CPUs. Guest CPU models, kernels, OS patch versions, memory and exact tool versions
are preserved with every workload result. Boat has approximately 8 GB RAM; the
other two have approximately 16 GB.

## Work and repetition

Five pinned workloads cover compiler type checking and bundling, two Rust clean
builds, a Python test suite, and Python CPU runtime. Full upstream commit IDs and
descriptions live in `workloads.json`; package lockfiles and `mise.toml` pin tools
and dependencies. The commands and four-job Rust compilation limit are identical
across providers. All workloads must pass their correctness checks.

Each provider first runs five cold seeds on separate fresh runners. After **all**
seeds pass, it runs three cold and three warm fresh-runner samples per workload.
Seeds populate caches and are excluded from speed statistics, but included in
execution and cost budgets. The matrix rotates provider order and alternates
cold/warm order between repetitions; no provider gets a fixed first position.
At most six matrix jobs run concurrently across providers. Matrix scheduling
therefore affects total workflow elapsed time; it is not a throughput ranking.

The suite has 105 workload jobs (15 seeds + 90 measured jobs), plus one small
GitHub planning job. A five-minute job timeout limits scheduled execution to
175 timeout-minutes per provider, leaving room below the 200-minute ceiling for
the earlier smoke jobs, uploads, planning and selective retries. Actual job
execution is accounted for using Actions timestamps, including failed smoke
attempts. Queue time is separate from execution; provider billing may include VM
startup and teardown outside Actions timestamps.

## Cache fairness

Both profiles execute the same commands. Cold clears the harness-owned package
cache and skips archive restoration; it does not flush provider infrastructure,
registry/CDN caches, host caches or preinstalled tools. Warm restores a
provider-specific, workload-specific seed keyed to this workflow run and the
source/toolchain/lockfiles. A successful matching admission marker and package
manager integrity checks are required. Missing warm caches fail the job.

Only npm, Cargo, uv and pip package caches are saved under
`.bench/cache/<workload>`. No source trees, target directories, emitted bundles,
virtual environments, or results are retained. Cargo check output is removed
before the release build, even within one job. Every profile recreates build
directories and virtual environments. This measures dependency caching with
clean builds, rather than incremental build caching.

Each provider uses its supported archive-cache backend: `actions/cache` on
GitHub and Boat, and Blacksmith's automatically enabled transparent cache on
Blacksmith. The same cache action SHA and payload policy are used for all.
Blacksmith activation and representative exact-key restores are verified in logs.
Cache archives contain platform-specific dependencies and differ slightly in
bytes; sharing absolute-path archives between providers would be invalid.

Boat snapshots, Blacksmith sticky disks, Docker layer caching, custom images,
and compiled Rust target caches are separate optimizations and are outside this
matched experiment. Docker functionality was checked in the pilot; a Docker
image-build performance workload is not included in this suite.

## What each timing means

- **Job execution:** Actions `started_at` to `completed_at`, including runner
  setup, pinned tool installation, source checkout/fetch, cache restoration,
  actual workload, artifact upload and runner cleanup. It excludes queue wait.
- **Workload:** Python monotonic time inside the harness, including upstream
  source fetching/copying, dependency installation, computation and correctness.
- **Compute:** Sum of build, type-check, test, bundle, render and runtime stages;
  excludes source fetch and dependency-install stages. The Python runtime stage
  also includes pyperformance process/virtual-environment management.
- **Setup and cache:** Actions step timestamps, with one-second resolution.
- **Queue:** Job creation to start. The API does not expose time a matrix entry
  spends waiting to be materialized by GitHub's six-job concurrency gate. This
  metric cannot represent total user-visible workflow wait or pure VM boot time.
- **Resources:** GNU time records peak RSS, user/system CPU time and wall time
  for each process tree; peak RSS is not total VM memory. Full environment data
  is available in `evidence.json`.

Each group reports three samples, a median, and the observed minimum/maximum.
Three samples do not justify p95/p99 claims or a universal provider ranking.
Aggregate speedup uses the geometric mean of per-workload ratios with equal
workload weight. Sum-of-medians comparisons represent a serial five-job suite,
not the actual parallel workflow critical path.

The runtime subset uses pyperformance's `--fast` mode with `json_dumps` and
`regex_v8`. Raw calibrated values and worker metadata are preserved. These short
runs provide directional evidence, not publication-quality stable microbenchmark
estimates. Cache state should not meaningfully change CPU throughput; differences
between cold and warm runtime values may reflect run variance.

## Reproduction

```sh
gh workflow run benchmark.yml --repo aurentisio/ci-runner-bench --ref main \
  -f provider=all -f workload=all
# Wait for completion, then substitute its run ID:
python scripts/collect.py RUN_ID
python scripts/analyze.py RUN_ID
```

These are manually dispatched workflows: push and pull requests do not start a
benchmark. A fresh dispatch creates fresh cache keys and seeds. Another full run
uses a new budget; the planning check is a per-dispatch bound, not an account-wide
billing or lifetime cumulative spending limit. Do not launch another full suite
as a retry when rerunning just failed jobs is sufficient.

`evidence.json` preserves raw reports, pyperformance values and Actions job/step
metadata. `samples.csv` includes seeds and all measured samples; `stages.csv`
contains stage timings/resources. `summary.json` is regenerated by the analyzer,
which rejects missing/duplicate samples, failed checks, tool-version differences,
unexpected CPU allocation and execution-budget overruns.
