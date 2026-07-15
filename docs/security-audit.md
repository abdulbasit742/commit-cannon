# Changed-area security and abuse audit

## Removed risks

- default generation of one million commits
- instructions to continue toward 100 million commits
- automatic `git push --force`
- configurable remote target
- direct mutation of the cloned source repository
- aggressive repack as an unavoidable step
- unsupported record-holder and throughput claims
- no validation, tests, integrity check, timeout, or result artifact

## Current controls

- 1,000-commit default and immutable 100,000-commit hard cap
- benchmark-only ref namespace
- disposable empty repository by default
- kept output must be empty and outside the source tree
- no remote is created; remote count is verified as zero
- `fast-import --done` plus a terminating `done` directive
- exact `rev-list --count` verification
- `git fsck --no-dangling` integrity check
- bounded 5–600 second operation timeout
- no shell interpolation or `shell=True`
- optional, non-aggressive local repack
- source scanner rejects push, force-update, remote-add, shell execution, and record-target patterns
- CI uses only small local histories

## Residual risks

- 100,000 commits can still consume meaningful CPU, memory, and disk on a small machine.
- Timing results are affected by hardware, filesystem, Git version, caching, and concurrent workloads; they are not universal performance claims.
- Keeping the generated repository transfers cleanup responsibility to the operator.
- `generate.py` can be piped into another local Git repository. Ref namespace restrictions and the absence of `--force` reduce risk, but operators should still use a disposable repository.
- This repository has no license file.

## Explicit non-goals

The project must not add hosted-service pushes, force updates, remote creation, configurable hard-cap bypasses, automated record attempts, or instructions designed to burden third-party infrastructure.
