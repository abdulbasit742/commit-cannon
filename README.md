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
- child Git processes receive an allowlisted environment; caller `GIT_DIR`, work-tree, alternate-object, credential, and global-config settings are not inherited
- repositories are explicitly initialized with SHA-1 for comparable deterministic fingerprints
- the operation timeout covers both Python stream production and Git import; a timed-out isolated process group is terminated
- Git stderr is drained concurrently and retained only in a bounded 64 KiB diagnostic buffer
- JSON reports are created exclusively and never replace existing files or live inside a kept benchmark repository
- if final kept-repository publication fails, a newly written report is rolled back
- no `git push`, remote creation, `--force`, shell execution, or hosted-service target exists in active code
- `git fsck`, exact commit-count verification, object-format validation, tip-object validation, and zero-remote verification run before success
- a kept repository can be re-verified later from its schema-v2 report through a read-only verifier

The old 100-million-commit GitHub record attempt and automatic force-push workflow have been removed. Do not use this project to create abusive repository histories or impose load on a third-party service.

## Requirements

- Python 3.11 or newer
- Git available on `PATH`
- Linux, macOS, or Windows for atomic kept-repository publication

There are no runtime Python dependencies. On Linux the CLI uses `renameat2(RENAME_NOREPLACE)`; on macOS it uses `renamex_np(RENAME_EXCL)`; Windows rename already refuses an existing destination. Other platforms fail closed for `--keep` instead of falling back to a clobber-prone publish.

## Run a disposable benchmark

```bash
./run.sh --count 1000
```

The command prints a JSON report and deletes the generated repository after verification.

Useful options:

```bash
# Save a new report; existing files are never replaced
./run.sh --count 10000 --json benchmark-report.json

# Publish a verified isolated repository at a path that does not yet exist
./run.sh --count 5000 --keep /tmp/commit-cannon-output

# Include a normal local repack in the measurement
./run.sh --count 5000 --repack

# Use a nested benchmark-only ref
./run.sh --count 2500 --branch benchmark/python-3.12

# Bound each Git operation, including stream delivery
./run.sh --count 2500 --timeout 60
```

`--keep` must point to a **non-existent** path outside this source tree and must not traverse symlinked parents. The CLI creates a private staging repository beside the final path, completes all integrity checks, and only then publishes it without replacing any path that appears concurrently. The generated repository has no remotes. A `--json` path must be new and outside any kept repository. `--timeout` accepts 5–600 seconds.

## Run a repeated statistical suite

A single timing can be noisy. Run bounded disposable warmups and repeated samples with:

```bash
python -m commit_cannon.suite \
  --count 5000 \
  --warmups 1 \
  --runs 5 \
  --json suite-report.json
```

The suite accepts 2–9 measured runs and 0–3 warmups. The product of commits per run and total runs must not exceed 300,000. It has no keep, remote, or push option. The schema-v1 report includes every sample, median/mean/min/max elapsed time, population standard deviation, coefficient of variation, median throughput, deterministic tip IDs, and basic machine/runtime metadata.

Prefer the median and treat a high coefficient of variation as an unstable environment. Compare reports only when parameters, Git version, and relevant machine/filesystem conditions are equivalent. See [docs/statistical-suites.md](docs/statistical-suites.md).

## Single-run report fields

The schema-v2 JSON report includes:

- requested and verified commit count
- benchmark branch
- start/finish timestamps
- elapsed seconds and commits per second
- `.git` directory size
- Git version
- object format, fixed to `sha1`
- verified tip object ID for run comparison
- integrity result
- remote count, which must remain zero
- whether repacking was included
- final kept repository path, when requested

Timing still depends on hardware, filesystem, Git version, caching, and concurrent workloads. Compare reports only in a controlled environment.

## Re-verify a kept repository

A report is useful only if the published repository still matches it. Re-run the read-only checks later with:

```bash
python -m commit_cannon.verify benchmark-report.json \
  --repository /tmp/commit-cannon-output
```

When `--repository` is omitted, the verifier uses the report's `kept_repository` value. It fails closed on unknown or missing report fields, symbolic-link paths, an unexpected ref, changed commit count, changed tip object ID, non-SHA-1 objects, added remotes, failed `git fsck`, or a changed `.git` size. It does not write to the report or repository.

The verifier confirms consistency and accidental/post-publication changes; it is not a cryptographic signature and does not prove who produced the report.

## Stream frontend

`generate.py` remains available for testing Git's import protocol directly:

```bash
mkdir /tmp/fast-import-test
cd /tmp/fast-import-test
git init --quiet --object-format=sha1
python /path/to/commit-cannon/generate.py 100 --branch benchmark/manual \
  | git fast-import --done --quiet
git rev-list --count refs/heads/benchmark/manual
```

The frontend emits a terminating `done` directive, enforces the same hard cap, and only permits benchmark refs. It does not invoke Git or access the network itself. The standalone pipeline is operator-managed; use the CLI when you need the enforced timeout, integrity checks, and atomic kept-output publication.

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

The current suite contains 36 regression tests, including hostile Git-environment, report-clobber, stalled-stream timeout, publish-race, symlink-parent, cleanup, report-rollback, report-schema, tampered-tip/count, added-remote, post-publication size-change, suite workload-cap, deterministic-tip, Git-version, warmup, statistics, and exclusive-suite-report cases.

## Design references

See [docs/reference-review.md](docs/reference-review.md) for the reviewed Git, git-filter-repo, Hyperfine, pytest-benchmark, and Criterion patterns. See [docs/security-audit.md](docs/security-audit.md) for the changed-area risk assessment.

## License

No license file is currently present. Do not assume permission to redistribute this code outside the rights granted by applicable law.
