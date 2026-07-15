# Changed-area security and abuse audit

## Removed risks

- default generation of one million commits and instructions toward 100 million
- automatic `git push --force`, configurable remote targets, and mutation of the source repository
- aggressive repack as an unavoidable step
- unsupported record-holder and throughput claims
- no validation, tests, integrity check, timeout, or result artifact
- inheritance of caller-controlled `GIT_DIR`, `GIT_WORK_TREE`, alternate object stores, global Git config, and related routing variables
- JSON reports silently replacing existing files

## Current controls

- 1,000-commit default and immutable 100,000-commit hard cap
- benchmark-only ref namespace
- disposable empty repository by default
- kept output must be empty, non-symlink, and outside the source tree
- minimal child-process environment with system/global Git config disabled
- explicit SHA-1 initialization for comparable deterministic tip fingerprints
- no remote is created; remote count is verified as zero
- `fast-import --done` plus a terminating `done` directive
- exact `rev-list --count`, `git fsck`, object-format, tip-OID, and commit-object verification
- bounded 5–600 second operation timeout
- no shell interpolation or `shell=True`
- optional, non-aggressive local repack
- reports use exclusive creation, refuse existing paths, and cannot be written inside a kept repository
- source scanner locks the cap, environment allowlist, SHA-1 fingerprint, and report-creation contracts
- CI uses only small local histories

## Residual risks

- 100,000 commits can still consume meaningful CPU, memory, and disk on a small machine.
- Timing results depend on hardware, filesystem, Git version, caching, and concurrent workloads.
- Keeping the generated repository transfers cleanup responsibility to the operator.
- `generate.py` can be piped into another local Git repository; operators must use a disposable repository.
- The per-operation timeout does not independently interrupt Python while it is streaming bytes to a stalled local Git process.
- Parent directories of operator-selected output paths may themselves involve filesystem mounts or symlinks outside this program's control.
- This repository has no license file.

## Explicit non-goals

The project must not add hosted-service pushes, force updates, remote creation, configurable hard-cap bypasses, automated record attempts, or instructions designed to burden third-party infrastructure.
