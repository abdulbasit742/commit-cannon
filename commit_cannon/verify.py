"""Validate a benchmark report and re-verify a kept repository without mutation."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping

from .benchmark import BenchmarkError, _directory_size, _run_git
from .stream import validate_branch, validate_count

_MAX_REPORT_BYTES = 64 * 1024
_REPORT_KEYS = frozenset(
    {
        "schema_version",
        "count",
        "branch",
        "started_at",
        "finished_at",
        "elapsed_seconds",
        "commits_per_second",
        "repository_size_bytes",
        "git_version",
        "object_format",
        "tip_oid",
        "integrity",
        "remote_count",
        "repacked",
        "kept_repository",
    }
)


@dataclass(frozen=True)
class ReportRecord:
    schema_version: int
    count: int
    branch: str
    started_at: str
    finished_at: str
    elapsed_seconds: float
    commits_per_second: float
    repository_size_bytes: int
    git_version: str
    object_format: str
    tip_oid: str
    integrity: str
    remote_count: int
    repacked: bool
    kept_repository: str | None


class ReportVerificationError(BenchmarkError):
    """Raised when a report or kept repository fails read-only verification."""


def _number(value: object, field: str, *, integer: bool = False) -> int | float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ReportVerificationError(f"report field {field!r} must be numeric")
    if integer and not isinstance(value, int):
        raise ReportVerificationError(f"report field {field!r} must be an integer")
    if value < 0:
        raise ReportVerificationError(f"report field {field!r} must be non-negative")
    return value


def _timestamp(value: object, field: str) -> str:
    if not isinstance(value, str):
        raise ReportVerificationError(f"report field {field!r} must be an ISO timestamp")
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as error:
        raise ReportVerificationError(f"report field {field!r} is not a valid ISO timestamp") from error
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ReportVerificationError(f"report field {field!r} must include a timezone")
    return value


def validate_report(payload: Mapping[str, object]) -> ReportRecord:
    """Fail closed on unknown, missing, or unsafe report fields."""

    if not isinstance(payload, Mapping):
        raise ReportVerificationError("report root must be a JSON object")
    keys = frozenset(payload)
    missing = sorted(_REPORT_KEYS - keys)
    extra = sorted(keys - _REPORT_KEYS)
    if missing or extra:
        detail = []
        if missing:
            detail.append(f"missing fields: {', '.join(missing)}")
        if extra:
            detail.append(f"unknown fields: {', '.join(extra)}")
        raise ReportVerificationError("invalid report schema; " + "; ".join(detail))

    schema_version = payload["schema_version"]
    if schema_version != 2 or isinstance(schema_version, bool):
        raise ReportVerificationError("only report schema version 2 is supported")

    try:
        count = validate_count(payload["count"])
        branch = validate_branch(payload["branch"])
    except (TypeError, ValueError) as error:
        raise ReportVerificationError(str(error)) from error

    started_at = _timestamp(payload["started_at"], "started_at")
    finished_at = _timestamp(payload["finished_at"], "finished_at")
    if datetime.fromisoformat(finished_at) < datetime.fromisoformat(started_at):
        raise ReportVerificationError("finished_at cannot precede started_at")

    elapsed_seconds = float(_number(payload["elapsed_seconds"], "elapsed_seconds"))
    commits_per_second = float(_number(payload["commits_per_second"], "commits_per_second"))
    repository_size_bytes = int(_number(payload["repository_size_bytes"], "repository_size_bytes", integer=True))

    git_version = payload["git_version"]
    if not isinstance(git_version, str) or not git_version.startswith("git version ") or len(git_version) > 200:
        raise ReportVerificationError("git_version is invalid")
    if payload["object_format"] != "sha1":
        raise ReportVerificationError("object_format must be sha1")
    tip_oid = payload["tip_oid"]
    if not isinstance(tip_oid, str) or not re.fullmatch(r"[0-9a-f]{40}", tip_oid):
        raise ReportVerificationError("tip_oid must be a canonical SHA-1 object ID")
    if payload["integrity"] != "passed":
        raise ReportVerificationError("report integrity must be passed")
    if payload["remote_count"] != 0 or isinstance(payload["remote_count"], bool):
        raise ReportVerificationError("report remote_count must be zero")
    if not isinstance(payload["repacked"], bool):
        raise ReportVerificationError("repacked must be boolean")

    kept_repository = payload["kept_repository"]
    if kept_repository is not None and (not isinstance(kept_repository, str) or not kept_repository.strip()):
        raise ReportVerificationError("kept_repository must be a non-empty string or null")

    return ReportRecord(
        schema_version=2,
        count=count,
        branch=branch,
        started_at=started_at,
        finished_at=finished_at,
        elapsed_seconds=elapsed_seconds,
        commits_per_second=commits_per_second,
        repository_size_bytes=repository_size_bytes,
        git_version=git_version,
        object_format="sha1",
        tip_oid=tip_oid,
        integrity="passed",
        remote_count=0,
        repacked=payload["repacked"],
        kept_repository=kept_repository,
    )


def load_report(path: Path) -> ReportRecord:
    """Read a small regular JSON file without following a report symlink."""

    report_path = path.expanduser().absolute()
    if report_path.is_symlink():
        raise ReportVerificationError("report path must not be a symbolic link")
    try:
        stat = report_path.stat()
    except OSError as error:
        raise ReportVerificationError(f"unable to read report: {error}") from error
    if not report_path.is_file():
        raise ReportVerificationError("report path must be a regular file")
    if stat.st_size > _MAX_REPORT_BYTES:
        raise ReportVerificationError("report exceeds the 64 KiB size limit")
    try:
        payload = json.loads(report_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ReportVerificationError(f"unable to parse report JSON: {error}") from error
    return validate_report(payload)


def _reject_symlink_components(path: Path) -> None:
    for component in (path, *path.parents):
        if component.exists() and component.is_symlink():
            raise ReportVerificationError("repository path must not traverse symbolic links")


def verify_repository(repository: Path, report: ReportRecord, timeout_seconds: int = 60) -> dict[str, Any]:
    """Re-run integrity checks against a kept repository without modifying it."""

    if isinstance(timeout_seconds, bool) or not isinstance(timeout_seconds, int) or not 5 <= timeout_seconds <= 600:
        raise ReportVerificationError("timeout_seconds must be between 5 and 600")
    unresolved = repository.expanduser().absolute()
    _reject_symlink_components(unresolved)
    repo = unresolved.resolve()
    if not repo.is_dir() or not (repo / ".git").is_dir() or (repo / ".git").is_symlink():
        raise ReportVerificationError("repository must be a normal Git work tree with a real .git directory")

    if _run_git(["rev-parse", "--is-inside-work-tree"], repo, timeout_seconds) != "true":
        raise ReportVerificationError("path is not a Git work tree")
    top_level = Path(_run_git(["rev-parse", "--show-toplevel"], repo, timeout_seconds)).resolve()
    if top_level != repo:
        raise ReportVerificationError("repository path must be the Git top-level directory")
    if _run_git(["rev-parse", "--show-object-format"], repo, timeout_seconds) != "sha1":
        raise ReportVerificationError("repository object format does not match the report")

    refs = [line for line in _run_git(["for-each-ref", "--format=%(refname)"], repo, timeout_seconds).splitlines() if line]
    expected_ref = f"refs/heads/{report.branch}"
    if refs != [expected_ref]:
        raise ReportVerificationError("repository must contain exactly the reported benchmark ref")
    imported_count = int(_run_git(["rev-list", "--count", expected_ref], repo, timeout_seconds))
    if imported_count != report.count:
        raise ReportVerificationError(f"report expects {report.count} commits but repository contains {imported_count}")
    tip_oid = _run_git(["rev-parse", "--verify", expected_ref], repo, timeout_seconds)
    if tip_oid != report.tip_oid:
        raise ReportVerificationError("repository tip does not match the report")
    if _run_git(["cat-file", "-t", tip_oid], repo, timeout_seconds) != "commit":
        raise ReportVerificationError("reported tip is not a commit")
    if _run_git(["remote"], repo, timeout_seconds):
        raise ReportVerificationError("repository must remain remote-free")
    _run_git(["fsck", "--no-dangling", "--no-progress"], repo, timeout_seconds)

    current_size = _directory_size(repo / ".git")
    if current_size != report.repository_size_bytes:
        raise ReportVerificationError(
            f"repository size changed: report={report.repository_size_bytes}, current={current_size}"
        )

    return {
        "schema_version": 1,
        "verified": True,
        "repository": str(repo),
        "count": imported_count,
        "branch": report.branch,
        "tip_oid": tip_oid,
        "object_format": "sha1",
        "remote_count": 0,
        "repository_size_bytes": current_size,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="commit-cannon-verify",
        description="Read-only verification of a schema-v2 report and kept benchmark repository.",
    )
    parser.add_argument("report", type=Path, help="schema-v2 JSON benchmark report")
    parser.add_argument("--repository", type=Path, help="kept repository path; defaults to the report value")
    parser.add_argument("--timeout", type=int, default=60, help="per-Git-command timeout in seconds (5-600)")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        report = load_report(args.report)
        repository_value = args.repository or (Path(report.kept_repository) if report.kept_repository else None)
        if repository_value is None:
            raise ReportVerificationError("repository path is required because the report has no kept_repository")
        result = verify_repository(repository_value, report, args.timeout)
        result["report"] = str(args.report.expanduser().absolute())
        sys.stdout.write(json.dumps(result, indent=2, sort_keys=True) + "\n")
        return 0
    except (TypeError, ValueError, BenchmarkError, OSError) as error:
        sys.stderr.write(f"ERROR: {error}\n")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
