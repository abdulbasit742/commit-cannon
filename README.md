# commit-cannon local benchmark

A bounded, reproducible benchmark for Git's `fast-import` backend.

This repository **does not push commits, add remotes, force-update branches, or target hosted Git services**. Every benchmark runs inside a new disposable local repository, verifies the generated history, records machine-readable results, and removes the temporary repository unless you explicitly keep it.

## Safety contract

- default: **1,000** commits
- hard, non-configurable cap: **100,000** commits
- generated refs are restricted to `benchmark` or `benchmark/...`
- the source repository and its parent/child directories cannot be used as output
- an existing non-empty output directory is never overwritten
- child Git processes receive an allowlisted environment; caller `GIT_DIR`, work-tree, alternate-object, credential, and global-config settings are not inherited
- repositories are explicitly initialized with SHA-1 for comparable deterministic fingerprints
- JSON reports are created exclusively and never replace existing files or live inside a kept benchmark repository
- no `git push`, remote creation, `--force`, shell execution, or hosted-service target exists in active code
- `git fsck`, exact commit-count verification, object-format validation, tip-object validation, and zero-remote verification run before success

The old 100-million-commit GitHub record attempt and automatic force-push workflow have been removed. Do not use this project to create abusive repository histories or impose load on a third-party service.

## Requirements

- Python 3.11 or newer
- Git available on `PATH`

There are no runtime Python dependencies.

## Run a disposable benchmark

```bash
./run.sh --count 1000
```

The command prints a JSON report and deletes the generated repository after verification.

Useful options:

```bash
# Save a new report; existing files are never replaced
./run.sh --count 10000 --json benchmark-report.json

# Keep an isolated local repository for inspection
./run.sh --count 5000 --keep /tmp/commit-cannon-output

# Include a normal local repack in the measurement
./run.sh --count 5000 --repack

# Use a nested benchmark-only ref
./run.sh --count 2500 --branch benchmark/python-3.12
```

`--keep` must point to a new or empty non-symlink directory outside this source tree. The generated repository has no remotes. A `--json` path must be new and outside any kept repository.

## Report fields

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
- kept repository path, when requested

Timing still depends on hardware, filesystem, Git version, caching, and concurrent workloads. Compare reports only in a controlled environment.

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

The frontend emits a terminating `done` directive, enforces the same hard cap, and only permits benchmark refs. It does not invoke Git or access the network itself.

## Verification

```bash
python3 -m compileall -q commit_cannon generate.py scripts tests
PYTHONWARNINGS=error::ResourceWarning \
  python3 -m unittest discover -s tests -p 'test_*.py' -v
bash -n run.sh
python3 scripts/repository_check.py
./run.sh --count 25 --json benchmark-report.json
```

The current suite contains 16 regression tests, including hostile Git-environment and report-clobber cases.

## Design references

See [docs/reference-review.md](docs/reference-review.md) for the reviewed Git, git-filter-repo, and hyperfine patterns. See [docs/security-audit.md](docs/security-audit.md) for the changed-area risk assessment.

## License

No license file is currently present. Do not assume permission to redistribute this code outside the rights granted by applicable law.
