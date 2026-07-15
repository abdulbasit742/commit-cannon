# AGENTS.md

## Scope

These instructions apply to the entire `abdulbasit742/commit-cannon` repository.

Project: a dependency-free, bounded **local Git fast-import benchmark**.

## Trust boundary

- `commit_cannon/stream.py` validates counts/refs and emits the protocol stream.
- `commit_cannon/benchmark.py` owns disposable repository creation, Git execution, verification, and cleanup.
- `commit_cannon/cli.py` owns exclusive reports and staged atomic publication of kept repositories.
- `commit_cannon/verify.py` validates schema-v2 reports and re-verifies kept repositories without writing to them.
- `commit_cannon/suite.py` owns disposable-only warmups/repeats, cumulative workload validation, statistics, and exclusive suite reports.
- `generate.py` is a compatibility stream frontend; it must retain the same cap and benchmark-only ref policy.
- `run.sh` must only delegate to the Python single-run CLI.

## Verified commands

```bash
python3 -m compileall -q commit_cannon generate.py scripts tests
PYTHONWARNINGS=error::ResourceWarning python3 -m unittest discover -s tests -p 'test_*.py' -v
bash -n run.sh
python3 scripts/repository_check.py
./run.sh --count 25 --json benchmark-report.json
python3 -m commit_cannon.suite --count 5 --runs 3 --warmups 1 --json suite-report.json
```

## Working rules

1. Keep runtime dependencies at zero unless a concrete benchmark requirement justifies one.
2. Never add `git push`, remote creation, force-updates, hosted-service targets, or automatic publication.
3. Never make the 100,000 per-run cap or 300,000 suite cumulative cap configurable through CLI flags, environment variables, config files, or hidden overrides.
4. Keep generated refs inside `benchmark` or `benchmark/...`.
5. Never run against the source repository, a non-empty directory, or an operator's existing repository.
6. Official `--keep` output must be built in a private sibling stage, fully verified, and published only through atomic no-replace semantics.
7. Never accept an existing keep destination, including an empty directory, and never traverse symlinked output parents.
8. A failed benchmark or publish must leave no final destination, no staging residue, and no report that claims a publication succeeded.
9. Keep post-publication verification read-only. It may run Git inspection commands, but must not repack, repair, checkout, rewrite refs, delete files, or normalize the report.
10. Keep statistical suites disposable-only. Do not add keep, remote, push, arbitrary setup, cache-clearing, or privileged system commands.
11. Suite reports must preserve individual samples, parameters, Git/runtime context, median, dispersion, and deterministic tip checks.
12. Report parsing and writing must fail closed on unknown/unsafe state, existing paths, unsupported schema versions, and symbolic-link paths.
13. Use argument arrays for subprocesses; do not enable shell execution.
14. Verify exact commit count, single expected ref, tip OID, SHA-1 object format, zero remotes, repository size, and `git fsck` before reporting verification success.
15. Keep CI counts small and local. Do not run resource-intensive benchmarks in CI.
16. Update tests, scanner, README, and audit documentation when the safety contract changes.

## Completion checklist

- all 36+ regression tests pass with `ResourceWarning` treated as an error
- Python and shell syntax checks pass
- repository safety scanner passes
- smoke report shows `integrity: passed` and `remote_count: 0`
- statistical suite smoke report contains bounded warmups/runs, identical deterministic tips, and individual samples
- kept-output smoke test leaves no staging directory and refuses an existing empty destination
- report verifier accepts an unchanged kept repository and rejects tampered count, tip, size, ref shape, remote state, or schema
- no generated repository or report is committed
- no hosted or destructive Git path is introduced
