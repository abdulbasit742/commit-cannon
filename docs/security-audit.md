# Changed-area security and abuse audit

## Removed risks

- default generation of one million commits and instructions toward 100 million
- automatic `git push --force`, configurable remote targets, and mutation of the source repository
- aggressive repack as an unavoidable step
- unsupported record-holder and throughput claims
- no validation, tests, integrity check, timeout, or result artifact
- inheritance of caller-controlled Git routing/configuration variables
- JSON reports silently replacing existing files
- timeout coverage beginning only after stream production completed
- undrained child stderr and partial kept-repository publication
- no supported post-publication verification
- reliance on one timing sample as stable performance
- ad-hoc report comparison that could mix different machines, workloads, runtimes, or noisy samples

## Current controls

- 1,000-commit default and immutable 100,000-commit per-run hard cap
- 2–9 measured samples, 0–3 warmups, and a 300,000-commit suite ceiling
- benchmark-only refs and disposable repositories by default
- sanitized child Git environment, fixed SHA-1 format, deterministic tip verification, zero remotes, `git fsck`, exact commit count, and bounded timeout/process cleanup
- no shell interpolation, hosted push path, remote creation, or force update
- exclusive report creation and atomic no-replace publication for kept repositories
- read-only post-publication verification of report schema, refs, tip, object format, size, integrity, and remote count
- suite reports retain individual samples, robust central tendency, dispersion, and environment metadata
- report comparison accepts only regular non-symlink JSON files up to 1 MB
- baseline and candidate must match workload, Git version, object format, OS/release/architecture, Python version, CPU count, measured runs, warmups, and repack setting
- both reports must have passed integrity and have sample counts matching measured runs
- configurable slowdown and coefficient-of-variation thresholds are bounded to 0–100%
- comparator exit codes are stable: 0 pass, 1 regression, 2 invalid/incomparable/noisy
- comparator writes nothing, invokes no subprocess, and performs no network or repository operation
- source scanner locks generation, publication, verification, suite, and comparator contracts
- CI uses only small local histories

## Residual risks

- 100,000 commits and a 300,000-commit suite can still consume meaningful local resources.
- Timing depends on hardware, filesystem, caching, thermal state, power policy, and background work.
- A coefficient-of-variation limit and median slowdown threshold are operational heuristics, not a significance test or proof of causality.
- Requiring exact environment metadata prevents misleading comparisons but can also reject legitimately useful cross-version investigations; those should be analyzed manually rather than forced through the CI gate.
- The comparator trusts correctly formed report contents. Reports are not cryptographically signed, so authenticity still requires a trusted artifact channel.
- Keeping generated repositories transfers cleanup responsibility to the operator.
- Exact `.git` size verification rejects benign repacks because they alter the represented artifact.
- This repository has no license file.

## Explicit non-goals

The project must not add hosted-service pushes, force updates, remote creation, hard-cap bypasses, automated record attempts, arbitrary benchmark setup commands, privileged cache-clearing operations, or instructions designed to burden third-party infrastructure.
