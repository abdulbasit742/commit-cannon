# Reference review

Reviewed on 2026-07-15 before replacing the hosted record-attempt workflow.

## 1. git/git

Relevant source: `Documentation/git-fast-import.adoc`.

Adopted:

- treat `fast-import` as a backend fed by a validated frontend
- initialize an empty repository before import
- terminate the stream with `done` and invoke `fast-import --done`
- avoid `--force`, which Git documents as allowing modified branches to be replaced even when commits would be lost
- verify the imported ref after the stream is complete

Not adopted:

- unsafe stream features, marks files, incremental import, multiple branches, or filesystem-access options

## 2. newren/git-filter-repo

Relevant source: `README.md` and its safety rationale for history rewriting.

Adopted:

- fail closed around destructive history operations
- operate on a disposable/fresh repository rather than the working repository
- reject ambiguous or unsafe destinations
- keep the implementation as a small, inspectable Python frontend

Not adopted:

- history filtering, rewriting callbacks, remote removal logic, or filter-repo dependencies

## 3. sharkdp/hyperfine

Relevant source: `README.md`.

Adopted:

- machine-readable JSON results
- explicit preparation and optional measurement stages
- report elapsed time rather than making unsupported performance claims
- keep benchmark parameters visible and reproducible

Not adopted:

- arbitrary shell commands, statistical multi-run orchestration, cache-clearing commands, or external runtime dependencies

## Resulting decision

The useful product is a local protocol/performance benchmark, not a hosted commit-count stunt. The repository now provides a bounded import, exact verification, integrity checks, no remotes, no push path, and an auditable result report.
