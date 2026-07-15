"""Command-line entry point for the bounded local benchmark."""

from __future__ import annotations

import argparse
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
    parser.add_argument("--json", type=Path, dest="json_path", help="also write the result report to this path")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        result = run_benchmark(
            count=args.count,
            branch=args.branch,
            keep_repository=args.keep,
            repack=args.repack,
            timeout_seconds=args.timeout,
        )
        report = result.to_json() + "\n"
        sys.stdout.write(report)
        if args.json_path:
            args.json_path.parent.mkdir(parents=True, exist_ok=True)
            args.json_path.write_text(report, encoding="utf-8")
        return 0
    except (TypeError, ValueError, BenchmarkError) as error:
        sys.stderr.write(f"ERROR: {error}\n")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
