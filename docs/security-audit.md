# Changed-area security and abuse audit

## Removed risks

- default generation of one million commits and instructions toward 100 million
- automatic `git push --force`, configurable remote targets, and mutation of the source repository
- aggressive repack as an unavoidable step
- unsupported record-holder and throughput claims
- no validation, tests, integrity check, timeout, or result artifact
- inheritance of caller-controlled `GIT_DIR`, `GIT_WORK_TREE`, alternate object stores, global Git config, and related routing variables
- JSON reports silently replacing existing files
- a timeout that started only after Python finished writing the complete fast-import stream
- undrained child stderr that could block a long-running import
- direct writes into the final `--keep` directory, which could expose partial Git state after failure or interruption
- acceptance of an existing empty keep directory, which made no-replace publication impossible
- no supported way to re-check a kept repository after publication or transfer
- reliance on one timing sample as if it represented stable performance

## Current controls

- 1,000-commit default and immutable 100,000-commit per-run hard cap
- repeated suites allow 2–9 measured samples and 0–3 warmups
- repeated suites enforce a 300,000-commit cumulative ceiling across measured and discarded runs
- the suite command is disposable-only and exposes no keep, remote, or push option
- benchmark-only ref namespace
- disposable empty repository by default
- a kept destination must be new, outside the source tree, and must not traverse symlinked parents
- kept repositories are built and verified in a private sibling staging directory
- Linux `renameat2(RENAME_NOREPLACE)`, macOS `renamex_np(RENAME_EXCL)`, or Windows no-replace rename atomically publishes the final directory
- unsupported platforms fail closed for `--keep`
- destination races never replace an existing path
- benchmark or publication failure removes staging output and leaves no final destination
- a report created before final publication is rolled back if publication fails
- minimal child-process environment with system/global Git config disabled
- explicit SHA-1 initialization for comparable deterministic tip fingerprints
- no remote is created; remote count is verified as zero
- `fast-import --done` plus a terminating `done` directive
- exact `rev-list --count`, `git fsck`, object-format, tip-OID, and commit-object verification
- bounded 5–600 second operation timeout covering stream production and Git import
- isolated fast-import process group termination on timeout
- concurrent stderr draining with a bounded 64 KiB diagnostic buffer
- no shell interpolation or `shell=True`
- optional, non-aggressive local repack
- reports use exclusive creation, refuse existing paths, and cannot be written inside a kept repository
- suite reports also use exclusive creation and include every measured sample
- a suite fails if Git version or deterministic tip changes between measured runs
- read-only post-publication verification rejects unknown report fields, oversized reports, report symlinks, repository symlink traversal, unexpected refs, changed count/tip/size, non-SHA-1 objects, and added remotes
- the verifier re-runs `git fsck` and uses the same sanitized Git environment as the benchmark
- source scanner locks the cap, environment allowlist, SHA-1 fingerprint, timeout, exclusive-report, atomic-publish, read-only verifier, and statistical-suite contracts
- CI uses only small local histories and verifies a real suite, staged keep publication, and report re-verification

## Residual risks

- 100,000 commits can still consume meaningful CPU, memory, and disk on a small machine before the configured timeout.
- A permitted 300,000-commit suite can consume more aggregate resources than one benchmark; the operator remains responsible for choosing a suitable count and quiet environment.
- Timing results depend on hardware, filesystem, Git version, caching, thermal state, and concurrent workloads. Repeated samples expose variability but do not remove it.
- Coefficient of variation is descriptive, not a statistical significance test or performance-regression verdict.
- Keeping the generated repository transfers cleanup responsibility to the operator.
- `generate.py` can be piped into another local Git repository; operators must use a disposable repository and manage that pipeline's lifetime themselves.
- Parent directories may be on unusual filesystems or mounts; the platform primitive can reject publication rather than weakening no-replace semantics.
- Filesystem or power failure after the atomic rename may still require normal filesystem recovery; this tool does not call system-wide sync operations.
- The schema-v2 report is not cryptographically signed. Anyone able to alter both a repository and its report can create a new matching pair; the verifier detects inconsistency, not authorship.
- Exact `.git` size comparison intentionally rejects benign post-publication repacks or maintenance because those change the artifact represented by the report.
- This repository has no license file.

## Explicit non-goals

The project must not add hosted-service pushes, force updates, remote creation, configurable hard-cap bypasses, automated record attempts, arbitrary benchmark setup commands, privileged cache-clearing operations, or instructions designed to burden third-party infrastructure.
