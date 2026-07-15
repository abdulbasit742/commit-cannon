# Statistical benchmark suites

A single timing can be dominated by cache state, filesystem activity, CPU scheduling, antivirus scans, thermal throttling, or unrelated processes. `commit-cannon.suite` runs a small, bounded set of disposable benchmarks and reports the individual measurements plus summary statistics.

## Run a suite

```bash
python -m commit_cannon.suite \
  --count 5000 \
  --warmups 1 \
  --runs 5 \
  --json suite-report.json
```

Defaults:

- 1,000 commits per sample
- 1 discarded warmup
- 5 measured runs
- no repack
- 120-second timeout for each Git operation

Hard limits:

- 2–9 measured runs
- 0–3 warmups
- at most 300,000 generated commits across warmups and measured runs
- the existing 100,000-commit per-run cap remains unchanged

Every run is disposable. The suite command has no keep, remote, or push option.

## Report interpretation

The schema-v1 suite report contains:

- every measured elapsed time, throughput, repository size, and deterministic tip object ID
- median, mean, minimum, maximum, population standard deviation, and coefficient of variation
- median commits per second
- Git version, Python version, operating system, release, machine architecture, and logical CPU count
- the benchmark parameters and cumulative generated-commit count

Prefer the median when comparing noisy runs. A high coefficient of variation means the environment was unstable; repeat the suite under quieter and more consistent conditions instead of presenting a precise performance claim.

Only compare reports when commit count, branch, repack setting, Git version, object format, and broadly relevant machine/filesystem conditions are equivalent. The suite rejects changed Git versions or deterministic tip IDs within one invocation.

## Non-goals

The suite does not clear caches, change system priorities, control CPU frequency, pin processes to cores, infer statistical significance, or execute arbitrary setup commands. Those features would expand privileges and environmental side effects beyond this repository's local Git benchmark boundary.
