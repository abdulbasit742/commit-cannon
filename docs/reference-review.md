# Reference review

Reviewed on 2026-07-15 before replacing the hosted record-attempt workflow and again while hardening benchmark isolation, cancellation, kept-output publication, post-publication verification, repeated measurement, and report comparison.

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
- re-run native repository integrity checks when validating a published artifact

Not adopted: marks files, incremental imports, multiple branches, filesystem-access options, or hosted pushes.

### 2. newren/git-filter-repo

Adopted:

- fail closed around history-changing operations
- operate only on a fresh/disposable repository
- reject ambiguous, existing, symlinked, or source-tree destinations
- treat inherited Git routing/configuration as part of the trust boundary
- terminate incomplete history operations rather than leaving a half-controlled child process
- stage work away from the operator-visible final path and expose it only after verification

Not adopted: history filtering, callbacks, remote removal, or package dependencies.

## Statistical measurement and comparison review

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

- explicit baseline/candidate comparison
- operator-selected regression thresholds
- stable nonzero exit behavior for CI gates
- retain individual samples and reject correctness failures before comparing speed

Not adopted: pytest integration, adaptive iteration calibration, histogram plugins, or test-function wrappers.

### 3. airspeed-velocity/asv

Adopted:

- environment identity is part of benchmark comparability
- performance history must not silently mix machines, runtimes, or workloads
- regression reporting is separate from benchmark execution

Not adopted: environment creation, Git revision matrix execution, databases, web dashboards, plotting, or plugin infrastructure.

## Resulting decision

The useful product is a local protocol benchmark, not a hosted commit-count stunt. The current design combines a fixed per-run cap, disposable staged repositories, sanitized Git environment, deterministic SHA-1 history fingerprint, stream-wide timeout, bounded diagnostics, process-group cleanup, integrity checks, zero remotes, atomic no-replace publication, exclusive machine-readable reports, a read-only post-publication verifier, a bounded repeated suite runner, and a read-only comparator.

The comparator refuses changed workload/environment metadata, invalid integrity, symbolic-link reports, oversized inputs, and noisy suites. It returns machine-readable output with stable exit codes and applies only an explicit preselected slowdown threshold; it does not claim statistical significance or causality.
