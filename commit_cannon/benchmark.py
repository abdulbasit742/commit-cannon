"""Run the commit-stream benchmark inside a disposable local repository."""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import tempfile
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from .stream import DEFAULT_BRANCH, validate_branch, validate_count, write_fast_import_stream


class BenchmarkError(RuntimeError):
    """Raised when a local benchmark cannot be completed safely."""


@dataclass(frozen=True)
class BenchmarkResult:
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

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2, sort_keys=True)


_ENV_ALLOWLIST = ("PATH", "PATHEXT", "SYSTEMROOT", "COMSPEC", "WINDIR", "TMP", "TEMP", "TMPDIR")


def _safe_environment(source: Mapping[str, str] | None = None) -> dict[str, str]:
    """Return a minimal deterministic environment for child Git processes.

    Git repository-routing variables, alternate object stores, global config,
    credential helpers, and hooks inherited from the caller must not escape the
    disposable benchmark boundary.
    """

    parent = os.environ if source is None else source
    env = {key: parent[key] for key in _ENV_ALLOWLIST if parent.get(key)}
    env.update(
        {
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_CONFIG_GLOBAL": os.devnull,
            "GIT_TERMINAL_PROMPT": "0",
            "GIT_AUTHOR_NAME": "commit-cannon",
            "GIT_AUTHOR_EMAIL": "benchmark@example.invalid",
            "GIT_COMMITTER_NAME": "commit-cannon",
            "GIT_COMMITTER_EMAIL": "benchmark@example.invalid",
            "LC_ALL": "C",
            "LANG": "C",
        }
    )
    return env


def _run_git(args: list[str], cwd: Path, timeout_seconds: int) -> str:
    try:
        completed = subprocess.run(
            ["git", *args],
            cwd=cwd,
            env=_safe_environment(),
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=timeout_seconds,
        )
    except FileNotFoundError as error:
        raise BenchmarkError("git is required but was not found") from error
    except subprocess.TimeoutExpired as error:
        raise BenchmarkError(f"git command timed out after {timeout_seconds} seconds") from error
    except subprocess.CalledProcessError as error:
        detail = (error.stderr or error.stdout or "git command failed").strip()
        raise BenchmarkError(detail) from error
    return completed.stdout.strip()


def _directory_size(path: Path) -> int:
    total = 0
    for entry in path.rglob("*"):
        if entry.is_file() and not entry.is_symlink():
            total += entry.stat().st_size
    return total


def _validate_keep_path(path: Path, source_root: Path) -> Path:
    destination = path.expanduser().resolve()
    source_root = source_root.resolve()
    if destination == source_root or destination in source_root.parents or source_root in destination.parents:
        raise BenchmarkError("kept repository must be outside the source repository tree")
    if destination.exists():
        if not destination.is_dir():
            raise BenchmarkError("kept repository path must be a directory")
        if destination.is_symlink() or any(destination.iterdir()):
            raise BenchmarkError("kept repository directory must be empty and not a symbolic link")
    else:
        destination.mkdir(parents=True)
    return destination


def _import_stream(repo: Path, *, count: int, branch: str, timeout_seconds: int) -> None:
    try:
        process = subprocess.Popen(
            ["git", "fast-import", "--done", "--quiet"],
            cwd=repo,
            env=_safe_environment(),
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
    except FileNotFoundError as error:
        raise BenchmarkError("git is required but was not found") from error

    assert process.stdin is not None
    try:
        write_fast_import_stream(process.stdin, count=count, branch=branch)
        process.stdin.close()
        process.wait(timeout=timeout_seconds)
    except (BrokenPipeError, subprocess.TimeoutExpired) as error:
        process.kill()
        process.wait()
        raise BenchmarkError("git fast-import failed or timed out") from error
    finally:
        if process.stdin and not process.stdin.closed:
            process.stdin.close()

    stdout = process.stdout.read() if process.stdout else b""
    stderr_bytes = process.stderr.read() if process.stderr else b""
    if process.stdout:
        process.stdout.close()
    if process.stderr:
        process.stderr.close()
    stderr = stderr_bytes.decode("utf-8", errors="replace")
    if process.returncode != 0:
        detail = stderr.strip() or stdout.decode("utf-8", errors="replace").strip()
        raise BenchmarkError(detail or "git fast-import failed")


def run_benchmark(
    *,
    count: int,
    branch: str = DEFAULT_BRANCH,
    keep_repository: Path | None = None,
    repack: bool = False,
    timeout_seconds: int = 120,
    source_root: Path | None = None,
) -> BenchmarkResult:
    """Run a bounded import benchmark without creating a remote or pushing."""

    count = validate_count(count)
    branch = validate_branch(branch)
    if isinstance(timeout_seconds, bool) or not isinstance(timeout_seconds, int) or not 5 <= timeout_seconds <= 600:
        raise ValueError("timeout_seconds must be between 5 and 600")

    source_root = (source_root or Path.cwd()).resolve()
    temporary: tempfile.TemporaryDirectory[str] | None = None
    created_keep_path = False

    if keep_repository is None:
        temporary = tempfile.TemporaryDirectory(prefix="commit-cannon-")
        repo = Path(temporary.name) / "repository"
        repo.mkdir()
        kept_path: str | None = None
    else:
        target = keep_repository.expanduser().resolve()
        created_keep_path = not target.exists()
        repo = _validate_keep_path(target, source_root)
        kept_path = str(repo)

    started_wall = datetime.now(timezone.utc)
    started = time.perf_counter()

    try:
        _run_git(["init", "--quiet", "--object-format=sha1"], repo, timeout_seconds)
        remotes_before = _run_git(["remote"], repo, timeout_seconds)
        if remotes_before:
            raise BenchmarkError("benchmark repository unexpectedly contains a remote")

        _import_stream(repo, count=count, branch=branch, timeout_seconds=timeout_seconds)

        ref = f"refs/heads/{branch}"
        imported_count = int(_run_git(["rev-list", "--count", ref], repo, timeout_seconds))
        if imported_count != count:
            raise BenchmarkError(f"expected {count} commits but imported {imported_count}")

        _run_git(["fsck", "--no-dangling", "--no-progress"], repo, timeout_seconds)
        object_format = _run_git(["rev-parse", "--show-object-format"], repo, timeout_seconds)
        if object_format != "sha1":
            raise BenchmarkError(f"expected sha1 object format but found {object_format}")
        tip_oid = _run_git(["rev-parse", "--verify", ref], repo, timeout_seconds)
        if not re.fullmatch(r"[0-9a-f]{40}", tip_oid):
            raise BenchmarkError("benchmark tip is not a canonical SHA-1 object ID")
        if _run_git(["cat-file", "-t", tip_oid], repo, timeout_seconds) != "commit":
            raise BenchmarkError("benchmark ref does not resolve to a commit")
        if repack:
            _run_git(["repack", "-adq"], repo, timeout_seconds)

        remotes = [line for line in _run_git(["remote"], repo, timeout_seconds).splitlines() if line]
        if remotes:
            raise BenchmarkError("benchmark repository must remain remote-free")

        elapsed = time.perf_counter() - started
        finished_wall = datetime.now(timezone.utc)
        git_version = _run_git(["--version"], repo, timeout_seconds)
        size = _directory_size(repo / ".git")

        return BenchmarkResult(
            schema_version=2,
            count=count,
            branch=branch,
            started_at=started_wall.isoformat(),
            finished_at=finished_wall.isoformat(),
            elapsed_seconds=round(elapsed, 6),
            commits_per_second=round(count / elapsed, 3) if elapsed else 0.0,
            repository_size_bytes=size,
            git_version=git_version,
            object_format=object_format,
            tip_oid=tip_oid,
            integrity="passed",
            remote_count=0,
            repacked=repack,
            kept_repository=kept_path,
        )
    except Exception:
        if keep_repository is not None and created_keep_path:
            shutil.rmtree(repo, ignore_errors=True)
        raise
    finally:
        if temporary is not None:
            temporary.cleanup()
