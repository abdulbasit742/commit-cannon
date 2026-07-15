# Reference review

Reviewed on 2026-07-15 before replacing the hosted record-attempt workflow and again while hardening benchmark isolation, cancellation, kept-output publication, post-publication verification, and repeated measurement.

## Isolation and repository-safety review

### 1. git/git

Adopted:

- treat `fast-import` as a backend fed by a validated frontend
- initialize an empty repository before import and terminate with `done`
- avoid force replacement and verify the imported ref
- isolate test configuration from operator Git configuration
- fix the object format and record a verified tip object ID
- treat stream delivery and backend completion as one process lifecycle
- publish a completed directory with operating-system no-replace rename semantics
- re-run native repository integrity checks (`fsck`, ref resolution, commit type, object format) when validating a published artifact

Not adopted: marks files, incremental imports, multiple branches, filesystem-access options, or hosted pushes.

### 2. newren/git-filter-repo

Adopted:

- fail closed around history-changing operations
- operate only on a fresh/disposable repository
- reject ambiguous, existing, symlinked, or source-tree destinations
- treat inherited Git routing/configuration as part of the trust boundary
- terminate incomplete history operations rather than leaving a half-controlled child process
- stage work away from the operator-visible final path and expose it only after verification
- reject unexpected repository shape rather than guessing which refs or paths are authoritative

Not adopted: history filtering, callbacks, remote removal, or package dependencies.

## Statistical measurement review

### 1. sharkdp/hyperfine

Adopted:

- warmup runs before measured samples
- statistical analysis across multiple runs
- machine-readable JSON with individual measurements
- explicit parameters and environment metadata
- visible dispersion instead of a single universal throughput claim

Not adopted: arbitrary shell commands, automatic run calibration, cache-clearing commands, setup hooks, or external dependencies.

### 2. ionelmc/pytest-benchmark

Adopted:

- separate measured rounds from correctness/integrity checks
- retain individual samples for later comparison
- make exact run counts operator-visible and bounded
- keep the benchmarked operation responsible for producing a valid result, not merely a fast result

Not adopted: pytest integration, adaptive iteration calibration, histogram plugins, or test-function wrappers.

### 3. criterion-rs/criterion.rs

Adopted:

- treat repeated benchmarking as statistics-driven measurement
- report central tendency and variation together
- preserve raw observations rather than publishing only a headline number

Not adopted: regression models, significance tests, HTML reports, plotting, or a Rust/runtime migration.

## Resulting decision

The useful product is a local protocol benchmark, not a hosted commit-count stunt. The current design combines a fixed per-run cap, disposable staged repositories, sanitized Git environment, deterministic SHA-1 history fingerprint, stream-wide timeout, bounded stderr diagnostics, process-group cleanup, integrity checks, zero remotes, atomic no-replace publication for kept output, no push path, exclusive machine-readable reports, a read-only post-publication verifier, and a separate disposable-only suite runner with bounded warmups/repeats and a 300,000-commit cumulative ceiling.
