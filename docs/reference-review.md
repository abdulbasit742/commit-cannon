# Reference review

Reviewed on 2026-07-15 before replacing the hosted record-attempt workflow and again while hardening benchmark isolation, cancellation, kept-output publication, and post-publication verification.

## 1. git/git

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

## 2. newren/git-filter-repo

Adopted:

- fail closed around history-changing operations
- operate only on a fresh/disposable repository
- reject ambiguous, existing, symlinked, or source-tree destinations
- treat inherited Git routing/configuration as part of the trust boundary
- terminate incomplete history operations rather than leaving a half-controlled child process
- stage work away from the operator-visible final path and expose it only after verification
- reject unexpected repository shape rather than guessing which refs or paths are authoritative

Not adopted: history filtering, callbacks, remote removal, or package dependencies.

## 3. sharkdp/hyperfine

Adopted:

- machine-readable versioned JSON results
- visible benchmark parameters and reproducibility metadata
- timing reports without universal performance claims
- output files that are explicit artifacts rather than hidden state
- bounded benchmark execution and controlled diagnostic output
- report the final published path rather than an internal staging path
- keep report consumption explicit and schema-aware

Not adopted: arbitrary shell commands, statistical multi-run orchestration, cache-clearing commands, or external runtime dependencies.

## Resulting decision

The useful product is a local protocol benchmark, not a hosted commit-count stunt. The current design combines a fixed cap, disposable staged repository, sanitized Git environment, deterministic SHA-1 history fingerprint, stream-wide timeout, bounded stderr diagnostics, process-group cleanup, integrity checks, zero remotes, atomic no-replace publication for kept output, no push path, exclusive machine-readable reports, and a read-only verifier that can later prove a kept repository still matches its schema-v2 report.
