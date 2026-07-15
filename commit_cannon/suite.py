"""Run bounded repeated benchmarks and report robust summary statistics."""

from __future__ import annotations

import argparse
import json
import os
import platform
import statistics
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from .benchmark import BenchmarkError, BenchmarkResult, run_benchmark
from .stream import DEFAULT_BRANCH, DEFAULT_COUNT, MAX_COMMITS, validate_branch, validate_count

MAX_RUNS = 9
MAX_WARMUPS = 3
MAX_SUITE_COMMITS = 300_000
SUITE_SCHEMA_VERSION = 1


@dataclass(frozen=True)
class SuiteSample:
    elapsed_seconds: float
    commits_per_second: float
    repository_size_bytes: int
    tip_oid: str


@dataclass(frozen=True)
class SuiteResult:
    schema_version: int
    benchmark_schema_version: int
    count: int
    branch: str
    runs: int
    warmups: int
    total_generated_commits: int
    repacked: bool
    timeout_seconds: int
    started_at: str
    finished_at: str
    git_version: str
    object_format: str
    platform_system: str
    platform_release: str
    platform_machine: str
    python_version: str
    cpu_count: int | None
    median_elapsed_seconds: float
    mean_elapsed_seconds: float
    min_elapsed_seconds: float
    max_elapsed_seconds: float
    standard_deviation_seconds: float
    coefficient_of_variation_percent: float
    median_commits_per_second: float
    integrity: str
    samples: tuple[SuiteSample, ...]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2, sort_keys=True)


def validate_runs(value: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError("runs must be an integer")
    if not 2 <= value <= MAX_RUNS:
        raise ValueError(f"runs must be between 2 and {MAX_RUNS}")
    return value


def validate_warmups(value: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError("warmups must be an integer")
    if not 0 <= value <= MAX_WARMUPS:
        raise ValueError(f"warmups must be between 0 and {MAX_WARMUPS}")
    return value


def validate_suite_workload(count: int, runs: int, warmups: int) -> int:
    count = validate_count(count)
    runs = validate_runs(runs)
    warmups = validate_warmups(warmups)
    total = count * (runs + warmups)
    if total > MAX_SUITE_COMMITS:
        raise ValueError(
            f"suite workload must not exceed {MAX_SUITE_COMMITS:,} generated commits; requested {total:,}"
        )
    return total


def _round(value: float, digits: int = 6) -> float:
    return round(value, digits)


def run_suite(
    *,
    count: int = DEFAULT_COUNT,
    branch: str = DEFAULT_BRANCH,
    runs: int = 5,
    warmups: int = 1,
    repack: bool = False,
    timeout_seconds: int = 120,
    source_root: Path | None = None,
    runner: Callable[..., BenchmarkResult] = run_benchmark,
) -> SuiteResult:
    """Run warmups plus repeated disposable benchmarks under one cumulative cap."""

    branch = validate_branch(branch)
    total = validate_suite_workload(count, runs, warmups)
    if isinstance(timeout_seconds, bool) or not isinstance(timeout_seconds, int) or not 5 <= timeout_seconds <= 600:
        raise ValueError("timeout_seconds must be between 5 and 600")

    source_root = (source_root or Path.cwd()).resolve()
    started_at = datetime.now(timezone.utc)
    common = {
        "count": count,
        "branch": branch,
        "keep_repository": None,
        "repack": repack,
        "timeout_seconds": timeout_seconds,
        "source_root": source_root,
    }

    for _ in range(warmups):
        warmup = runner(**common)
        if warmup.integrity != "passed" or warmup.remote_count != 0:
            raise BenchmarkError("warmup benchmark failed the integrity contract")

    measured = [runner(**common) for _ in range(runs)]
    if any(result.integrity != "passed" or result.remote_count != 0 for result in measured):
        raise BenchmarkError("measured benchmark failed the integrity contract")
    if any(result.schema_version != 2 for result in measured):
        raise BenchmarkError("suite only accepts benchmark schema version 2")

    tip_oids = {result.tip_oid for result in measured}
    if len(tip_oids) != 1:
        raise BenchmarkError("deterministic benchmark tip changed between measured runs")
    git_versions = {result.git_version for result in measured}
    if len(git_versions) != 1:
        raise BenchmarkError("Git version changed between measured runs")
    object_formats = {result.object_format for result in measured}
    if object_formats != {"sha1"}:
        raise BenchmarkError("measured runs must use the SHA-1 object format")

    elapsed = [result.elapsed_seconds for result in measured]
    throughputs = [result.commits_per_second for result in measured]
    mean_elapsed = statistics.fmean(elapsed)
    standard_deviation = statistics.pstdev(elapsed)
    coefficient = (standard_deviation / mean_elapsed * 100.0) if mean_elapsed else 0.0

    samples = tuple(
        SuiteSample(
            elapsed_seconds=result.elapsed_seconds,
            commits_per_second=result.commits_per_second,
            repository_size_bytes=result.repository_size_bytes,
            tip_oid=result.tip_oid,
        )
        for result in measured
    )

    return SuiteResult(
        schema_version=SUITE_SCHEMA_VERSION,
        benchmark_schema_version=2,
        count=count,
        branch=branch,
        runs=runs,
        warmups=warmups,
        total_generated_commits=total,
        repacked=repack,
        timeout_seconds=timeout_seconds,
        started_at=started_at.isoformat(),
        finished_at=datetime.now(timezone.utc).isoformat(),
        git_version=measured[0].git_version,
        object_format="sha1",
        platform_system=platform.system(),
        platform_release=platform.release(),
        platform_machine=platform.machine(),
        python_version=platform.python_version(),
        cpu_count=os.cpu_count(),
        median_elapsed_seconds=_round(statistics.median(elapsed)),
        mean_elapsed_seconds=_round(mean_elapsed),
        min_elapsed_seconds=_round(min(elapsed)),
        max_elapsed_seconds=_round(max(elapsed)),
        standard_deviation_seconds=_round(standard_deviation),
        coefficient_of_variation_percent=_round(coefficient, 3),
        median_commits_per_second=_round(statistics.median(throughputs), 3),
        integrity="passed",
        samples=samples,
    )


def _write_report_exclusive(path: Path, report: str) -> None:
    destination = path.expanduser().resolve()
    if destination.exists() or destination.is_symlink():
        raise BenchmarkError("suite report path already exists; refusing to replace it")
    destination.parent.mkdir(parents=True, exist_ok=True)
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        descriptor = os.open(destination, flags, 0o600)
    except FileExistsError as error:
        raise BenchmarkError("suite report path already exists; refusing to replace it") from error
    except OSError as error:
        raise BenchmarkError(f"unable to create suite report safely: {error}") from error
    with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(report)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="commit-cannon-suite",
        description="Run bounded repeated disposable commit-cannon benchmarks.",
    )
    parser.add_argument("--count", type=int, default=DEFAULT_COUNT, help=f"commits per sample (1-{MAX_COMMITS:,})")
    parser.add_argument("--branch", default=DEFAULT_BRANCH, help="local benchmark branch name")
    parser.add_argument("--runs", type=int, default=5, help=f"measured samples (2-{MAX_RUNS})")
    parser.add_argument("--warmups", type=int, default=1, help=f"discarded warmups (0-{MAX_WARMUPS})")
    parser.add_argument("--repack", action="store_true", help="include a bounded local repack in every sample")
    parser.add_argument("--timeout", type=int, default=120, help="per-operation timeout in seconds (5-600)")
    parser.add_argument("--json", type=Path, dest="json_path", help="write a new aggregate report without replacing a file")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        result = run_suite(
            count=args.count,
            branch=args.branch,
            runs=args.runs,
            warmups=args.warmups,
            repack=args.repack,
            timeout_seconds=args.timeout,
            source_root=Path.cwd(),
        )
        report = result.to_json() + "\n"
        if args.json_path:
            _write_report_exclusive(args.json_path, report)
        sys.stdout.write(report)
        return 0
    except (TypeError, ValueError, BenchmarkError) as error:
        sys.stderr.write(f"ERROR: {error}\n")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
