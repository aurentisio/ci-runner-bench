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
