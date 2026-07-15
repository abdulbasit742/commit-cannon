"""Read-only comparison for bounded commit-cannon suite reports."""

from __future__ import annotations

import argparse
import json
import math
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

MAX_REPORT_BYTES = 1_000_000
DEFAULT_MAX_SLOWDOWN_PERCENT = 10.0
DEFAULT_MAX_CV_PERCENT = 10.0
COMPARABLE_FIELDS = (
    "schema_version",
    "benchmark_schema_version",
    "count",
    "branch",
    "runs",
    "warmups",
    "repacked",
    "git_version",
    "object_format",
    "platform_system",
    "platform_release",
    "platform_machine",
    "python_version",
    "cpu_count",
)


class ComparisonError(ValueError):
    """Raised when a report cannot be trusted or compared."""


@dataclass(frozen=True)
class ComparisonResult:
    schema_version: int
    status: str
    baseline_path: str
    candidate_path: str
    max_slowdown_percent: float
    max_cv_percent: float
    baseline_median_elapsed_seconds: float
    candidate_median_elapsed_seconds: float
    elapsed_slowdown_percent: float
    baseline_median_commits_per_second: float
    candidate_median_commits_per_second: float
    throughput_change_percent: float
    baseline_coefficient_of_variation_percent: float
    candidate_coefficient_of_variation_percent: float
    comparable_fields: tuple[str, ...]
    reason: str

    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=2, sort_keys=True)


def _finite_number(value: Any, field: str, *, positive: bool = False) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ComparisonError(f"{field} must be numeric")
    number = float(value)
    if not math.isfinite(number) or (positive and number <= 0):
        qualifier = "positive and finite" if positive else "finite"
        raise ComparisonError(f"{field} must be {qualifier}")
    return number


def _read_report(path: Path) -> dict[str, Any]:
    report_path = path.expanduser().resolve(strict=False)
    if path.is_symlink():
        raise ComparisonError(f"report path must not be a symbolic link: {path}")
    if not report_path.is_file():
        raise ComparisonError(f"report is not a regular file: {path}")
    size = report_path.stat().st_size
    if size <= 0 or size > MAX_REPORT_BYTES:
        raise ComparisonError(f"report size must be between 1 and {MAX_REPORT_BYTES} bytes: {path}")
    try:
        payload = json.loads(report_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ComparisonError(f"unable to read valid JSON report {path}: {error}") from error
    if not isinstance(payload, dict):
        raise ComparisonError(f"report root must be an object: {path}")
    return payload


def _validate_report(payload: dict[str, Any], label: str) -> dict[str, Any]:
    required = {
        *COMPARABLE_FIELDS,
        "integrity",
        "median_elapsed_seconds",
        "median_commits_per_second",
        "coefficient_of_variation_percent",
        "samples",
    }
    missing = sorted(required - payload.keys())
    if missing:
        raise ComparisonError(f"{label} report is missing fields: {', '.join(missing)}")
    if payload["schema_version"] != 1 or payload["benchmark_schema_version"] != 2:
        raise ComparisonError(f"{label} report schema is unsupported")
    if payload["integrity"] != "passed" or payload["object_format"] != "sha1":
        raise ComparisonError(f"{label} report did not pass the integrity contract")
    if isinstance(payload["runs"], bool) or not isinstance(payload["runs"], int) or not 2 <= payload["runs"] <= 9:
        raise ComparisonError(f"{label} runs value is invalid")
    if isinstance(payload["warmups"], bool) or not isinstance(payload["warmups"], int) or not 0 <= payload["warmups"] <= 3:
        raise ComparisonError(f"{label} warmups value is invalid")
    if not isinstance(payload["samples"], list) or len(payload["samples"]) != payload["runs"]:
        raise ComparisonError(f"{label} sample count does not match runs")
    _finite_number(payload["median_elapsed_seconds"], f"{label}.median_elapsed_seconds", positive=True)
    _finite_number(payload["median_commits_per_second"], f"{label}.median_commits_per_second", positive=True)
    cv = _finite_number(payload["coefficient_of_variation_percent"], f"{label}.coefficient_of_variation_percent")
    if cv < 0 or cv > 1000:
        raise ComparisonError(f"{label} coefficient of variation is invalid")
    for index, sample in enumerate(payload["samples"]):
        if not isinstance(sample, dict):
            raise ComparisonError(f"{label} sample {index} must be an object")
        _finite_number(sample.get("elapsed_seconds"), f"{label}.samples[{index}].elapsed_seconds", positive=True)
        _finite_number(sample.get("commits_per_second"), f"{label}.samples[{index}].commits_per_second", positive=True)
    return payload


def _validate_threshold(value: float, label: str, maximum: float) -> float:
    value = _finite_number(value, label)
    if not 0 <= value <= maximum:
        raise ComparisonError(f"{label} must be between 0 and {maximum}")
    return value


def compare_reports(
    baseline: dict[str, Any],
    candidate: dict[str, Any],
    *,
    baseline_path: str = "baseline",
    candidate_path: str = "candidate",
    max_slowdown_percent: float = DEFAULT_MAX_SLOWDOWN_PERCENT,
    max_cv_percent: float = DEFAULT_MAX_CV_PERCENT,
) -> ComparisonResult:
    baseline = _validate_report(baseline, "baseline")
    candidate = _validate_report(candidate, "candidate")
    max_slowdown_percent = _validate_threshold(max_slowdown_percent, "max_slowdown_percent", 100.0)
    max_cv_percent = _validate_threshold(max_cv_percent, "max_cv_percent", 100.0)

    mismatches = [field for field in COMPARABLE_FIELDS if baseline[field] != candidate[field]]
    if mismatches:
        raise ComparisonError(f"reports are not comparable; changed fields: {', '.join(mismatches)}")

    baseline_cv = float(baseline["coefficient_of_variation_percent"])
    candidate_cv = float(candidate["coefficient_of_variation_percent"])
    if baseline_cv > max_cv_percent or candidate_cv > max_cv_percent:
        raise ComparisonError(
            "reports are too noisy to compare; "
            f"coefficient of variation is {baseline_cv:.3f}% / {candidate_cv:.3f}% "
            f"with a {max_cv_percent:.3f}% limit"
        )

    baseline_elapsed = float(baseline["median_elapsed_seconds"])
    candidate_elapsed = float(candidate["median_elapsed_seconds"])
    baseline_throughput = float(baseline["median_commits_per_second"])
    candidate_throughput = float(candidate["median_commits_per_second"])
    slowdown = (candidate_elapsed / baseline_elapsed - 1.0) * 100.0
    throughput_change = (candidate_throughput / baseline_throughput - 1.0) * 100.0
    regressed = slowdown > max_slowdown_percent

    return ComparisonResult(
        schema_version=1,
        status="regressed" if regressed else "passed",
        baseline_path=baseline_path,
        candidate_path=candidate_path,
        max_slowdown_percent=round(max_slowdown_percent, 3),
        max_cv_percent=round(max_cv_percent, 3),
        baseline_median_elapsed_seconds=baseline_elapsed,
        candidate_median_elapsed_seconds=candidate_elapsed,
        elapsed_slowdown_percent=round(slowdown, 3),
        baseline_median_commits_per_second=baseline_throughput,
        candidate_median_commits_per_second=candidate_throughput,
        throughput_change_percent=round(throughput_change, 3),
        baseline_coefficient_of_variation_percent=baseline_cv,
        candidate_coefficient_of_variation_percent=candidate_cv,
        comparable_fields=COMPARABLE_FIELDS,
        reason=(
            f"median elapsed time exceeded the {max_slowdown_percent:.3f}% limit"
            if regressed
            else f"median elapsed time stayed within the {max_slowdown_percent:.3f}% limit"
        ),
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="commit-cannon-compare",
        description="Compare two trusted commit-cannon suite reports without modifying either file.",
    )
    parser.add_argument("baseline", type=Path)
    parser.add_argument("candidate", type=Path)
    parser.add_argument("--max-slowdown-percent", type=float, default=DEFAULT_MAX_SLOWDOWN_PERCENT)
    parser.add_argument("--max-cv-percent", type=float, default=DEFAULT_MAX_CV_PERCENT)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        baseline = _read_report(args.baseline)
        candidate = _read_report(args.candidate)
        result = compare_reports(
            baseline,
            candidate,
            baseline_path=str(args.baseline),
            candidate_path=str(args.candidate),
            max_slowdown_percent=args.max_slowdown_percent,
            max_cv_percent=args.max_cv_percent,
        )
        sys.stdout.write(result.to_json() + "\n")
        return 1 if result.status == "regressed" else 0
    except ComparisonError as error:
        sys.stderr.write(f"ERROR: {error}\n")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
