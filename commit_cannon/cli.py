"""Command-line entry point for the bounded local benchmark."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from .benchmark import BenchmarkError, run_benchmark
from .stream import DEFAULT_BRANCH, DEFAULT_COUNT, MAX_COMMITS


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="commit-cannon",
        description="Benchmark git fast-import inside an isolated local repository.",
    )
    parser.add_argument("--count", type=int, default=DEFAULT_COUNT, help=f"commit count (1-{MAX_COMMITS:,})")
    parser.add_argument("--branch", default=DEFAULT_BRANCH, help="local benchmark branch name")
    parser.add_argument("--keep", type=Path, help="keep the generated repository at an empty path outside this source tree")
    parser.add_argument("--repack", action="store_true", help="include a bounded local git repack after import")
    parser.add_argument("--timeout", type=int, default=120, help="per-operation timeout in seconds (5-600)")
    parser.add_argument("--json", type=Path, dest="json_path", help="write a new result report without replacing an existing file")
    return parser


def _validate_report_path(path: Path, keep_repository: Path | None) -> Path:
    destination = path.expanduser().resolve()
    if destination.exists() or destination.is_symlink():
        raise BenchmarkError("report path already exists; refusing to replace it")
    if keep_repository is not None:
        keep = keep_repository.expanduser().resolve()
        if destination == keep or keep in destination.parents:
            raise BenchmarkError("report path must remain outside the kept benchmark repository")
    return destination


def _write_report_exclusive(path: Path, report: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        descriptor = os.open(path, flags, 0o600)
    except FileExistsError as error:
        raise BenchmarkError("report path already exists; refusing to replace it") from error
    except OSError as error:
        raise BenchmarkError(f"unable to create report safely: {error}") from error
    with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(report)


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        report_path = _validate_report_path(args.json_path, args.keep) if args.json_path else None
        result = run_benchmark(
            count=args.count,
            branch=args.branch,
            keep_repository=args.keep,
            repack=args.repack,
            timeout_seconds=args.timeout,
        )
        report = result.to_json() + "\n"
        sys.stdout.write(report)
        if report_path:
            _write_report_exclusive(report_path, report)
        return 0
    except (TypeError, ValueError, BenchmarkError) as error:
        sys.stderr.write(f"ERROR: {error}\n")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
