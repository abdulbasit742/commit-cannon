# AGENTS.md

## Scope

These instructions apply to the entire `abdulbasit742/commit-cannon` repository.

Project: a dependency-free, bounded **local Git fast-import benchmark**.

## Trust boundary

- `commit_cannon/stream.py` validates counts/refs and emits the protocol stream.
- `commit_cannon/benchmark.py` owns disposable repository creation, Git execution, verification, and cleanup.
- `commit_cannon/cli.py` owns exclusive reports and staged atomic publication of kept repositories.
- `generate.py` is a compatibility stream frontend; it must retain the same cap and benchmark-only ref policy.
- `run.sh` must only delegate to the Python CLI.

## Verified commands

```bash
python3 -m compileall -q commit_cannon generate.py scripts tests
PYTHONWARNINGS=error::ResourceWarning python3 -m unittest discover -s tests -p 'test_*.py' -v
bash -n run.sh
python3 scripts/repository_check.py
./run.sh --count 25 --json benchmark-report.json
```

## Working rules

1. Keep runtime dependencies at zero unless a concrete benchmark requirement justifies one.
2. Never add `git push`, remote creation, force-updates, hosted-service targets, or automatic publication.
3. Never make the hard cap configurable through CLI flags, environment variables, config files, or hidden constants.
4. Keep generated refs inside `benchmark` or `benchmark/...`.
5. Never run against the source repository, a non-empty directory, or an operator's existing repository.
6. Official `--keep` output must be built in a private sibling stage, fully verified, and published only through atomic no-replace semantics.
7. Never accept an existing keep destination, including an empty directory, and never traverse symlinked output parents.
8. A failed benchmark or publish must leave no final destination, no staging residue, and no report that claims a publication succeeded.
9. Use argument arrays for subprocesses; do not enable shell execution.
10. Verify exact commit count, zero remotes, and repository integrity before reporting success.
11. Keep CI counts small and local. Do not run resource-intensive benchmarks in CI.
12. Update tests, scanner, README, and audit documentation when the safety contract changes.

## Completion checklist

- all 20+ regression tests pass with `ResourceWarning` treated as an error
- Python and shell syntax checks pass
- repository safety scanner passes
- smoke report shows `integrity: passed` and `remote_count: 0`
- kept-output smoke test leaves no staging directory and refuses an existing empty destination
- no generated repository or report is committed
- no hosted or destructive Git path is introduced
