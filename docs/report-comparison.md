# Compare benchmark suite reports

Use the read-only comparator after producing two bounded suite reports under the same environment and workload.

```bash
python -m commit_cannon.suite --count 10000 --runs 5 --warmups 1 --json baseline.json
# change the implementation or environment intentionally
python -m commit_cannon.suite --count 10000 --runs 5 --warmups 1 --json candidate.json

python -m commit_cannon.compare baseline.json candidate.json \
  --max-slowdown-percent 10 \
  --max-cv-percent 10
```

## Exit codes

- `0`: reports are comparable and the candidate stayed within the slowdown threshold.
- `1`: reports are comparable and the candidate exceeded the slowdown threshold.
- `2`: a report is invalid, unsafe, too noisy, or the environments/workloads differ.

The command prints a schema-versioned JSON result to standard output and never modifies either report.

## Comparability contract

The comparator requires equal values for:

- suite and benchmark schema versions;
- commit count, branch, measured runs, and warmups;
- repack setting;
- Git version and SHA-1 object format;
- operating system, release, machine architecture;
- Python version and CPU count.

Both reports must have `integrity: passed`, a sample count matching `runs`, positive finite timing/throughput values, and a coefficient of variation at or below the configured noise limit.

These checks intentionally favor false negatives over misleading performance claims. Run both suites on the same idle machine, with the same power mode, filesystem, Git/Python versions, and background workload.

## Threshold guidance

The default 10% slowdown limit is an operational policy, not a universal statistical truth. Pick a threshold before measuring, record why it is appropriate, and keep it stable for a series of comparisons. Increase the number of measured runs rather than weakening the noise limit when results are unstable.

The comparator is not a significance test and does not prove causality. It provides a bounded CI gate for controlled environments.
