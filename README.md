# commit-cannon local benchmark

A bounded, reproducible benchmark for Git's `fast-import` backend.

This repository **does not push commits, add remotes, force-update branches, or target hosted Git services**. Every benchmark runs inside a new disposable local repository, verifies the generated history, records machine-readable results, and removes the temporary repository unless you explicitly keep it.

## Safety contract

- default: **1,000** commits
- hard, non-configurable per-run cap: **100,000** commits
- statistical suites are capped at **300,000 cumulative generated commits**
- generated refs are restricted to `benchmark` or `benchmark/...`
- the source repository and its parent/child directories cannot be used as output
- a kept destination must be a new path; existing files and even empty directories are never replaced
- kept output is built and verified in a hidden sibling staging directory, then published with an atomic no-replace directory rename
- symlinked output parents are rejected and failed runs leave no final destination or staging residue
- child Git processes receive an allowlisted environment; caller Git routing/configuration is not inherited
- repositories are explicitly initialized with SHA-1 for comparable deterministic fingerprints
- the operation timeout covers both Python stream production and Git import
- Git stderr is drained concurrently and retained only in a bounded diagnostic buffer
- JSON reports are created exclusively and never replace existing files
- no `git push`, remote creation, `--force`, shell execution, or hosted-service target exists in active code
- integrity, count, object format, tip object, and zero remotes are verified before success
- kept repositories can be re-verified later from schema-v2 reports
- repeated-suite comparison is read-only and rejects mismatched or noisy environments

The old 100-million-commit GitHub record attempt and automatic force-push workflow have been removed. Do not use this project to create abusive repository histories or impose load on a third-party service.

## Requirements

- Python 3.11 or newer
- Git available on `PATH`
- Linux, macOS, or Windows for atomic kept-repository publication

There are no runtime Python dependencies.

## Run a disposable benchmark

```bash
./run.sh --count 1000
```

Useful options:

```bash
./run.sh --count 10000 --json benchmark-report.json
./run.sh --count 5000 --keep /tmp/commit-cannon-output
./run.sh --count 5000 --repack
./run.sh --count 2500 --branch benchmark/python-3.12
./run.sh --count 2500 --timeout 60
```

`--keep` must point to a non-existent path outside this source tree and must not traverse symlinked parents. A `--json` path must be new and outside any kept repository. `--timeout` accepts 5–600 seconds.

## Run a repeated statistical suite

```bash
python -m commit_cannon.suite \
  --count 5000 \
  --warmups 1 \
  --runs 5 \
  --json baseline.json
```

The suite accepts 2–9 measured runs and 0–3 warmups. The product of commits per run and total runs must not exceed 300,000. It has no keep, remote, or push option. The schema-v1 report includes every sample, robust summary statistics, deterministic tip IDs, and machine/runtime metadata.

## Compare suite reports

Produce a candidate under the same controlled environment, then run:

```bash
python -m commit_cannon.compare baseline.json candidate.json \
  --max-slowdown-percent 10 \
  --max-cv-percent 10
```

The comparator refuses invalid, symlinked, oversized, noisy, or workload/environment-mismatched reports and never modifies either input.

- exit `0`: comparable and within threshold
- exit `1`: comparable regression
- exit `2`: invalid, noisy, or incomparable

The threshold is an operational CI policy, not a statistical-significance claim. See [docs/report-comparison.md](docs/report-comparison.md).

## Single-run report fields

The schema-v2 JSON report includes count, branch, timestamps, elapsed time, throughput, `.git` size, Git version, SHA-1 object format, tip OID, integrity, remote count, repack state, and kept path.

Timing depends on hardware, filesystem, Git version, caching, thermal state, and concurrent workloads.

## Re-verify a kept repository

```bash
python -m commit_cannon.verify benchmark-report.json \
  --repository /tmp/commit-cannon-output
```

The verifier fails closed on unknown or missing fields, symbolic-link paths, unexpected refs, changed count/tip/size, non-SHA-1 objects, added remotes, or failed `git fsck`. It does not write to the report or repository.

## Stream frontend

```bash
mkdir /tmp/fast-import-test
cd /tmp/fast-import-test
git init --quiet --object-format=sha1
python /path/to/commit-cannon/generate.py 100 --branch benchmark/manual \
  | git fast-import --done --quiet
git rev-list --count refs/heads/benchmark/manual
```

The frontend enforces the same hard cap and benchmark-only refs. It does not invoke Git or access the network itself.

## Verification

```bash
python3 -m compileall -q commit_cannon generate.py scripts tests
PYTHONWARNINGS=error::ResourceWarning \
  python3 -m unittest discover -s tests -p 'test_*.py' -v
bash -n run.sh
python3 scripts/repository_check.py
./run.sh --count 25 --json benchmark-report.json
python3 -m commit_cannon.suite --count 5 --runs 3 --warmups 1 --json suite-report.json
```

The suite now contains 46 regression tests covering generation, isolation, timeout cleanup, exclusive reports, atomic publication, post-publication verification, repeated statistics, and fail-closed report comparison.

## Design references

See [docs/reference-review.md](docs/reference-review.md), [docs/report-comparison.md](docs/report-comparison.md), and [docs/security-audit.md](docs/security-audit.md).

## License

No license file is currently present. Do not assume permission to redistribute this code outside the rights granted by applicable law.
