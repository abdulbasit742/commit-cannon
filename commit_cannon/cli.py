"""Command-line entry point for the bounded local benchmark."""

from __future__ import annotations

import argparse
import ctypes
import errno
import os
import sys
import tempfile
from dataclasses import replace
from pathlib import Path

from .benchmark import BenchmarkError, run_benchmark
from .stream import DEFAULT_BRANCH, DEFAULT_COUNT, MAX_COMMITS

_AT_FDCWD = -100
_RENAME_NOREPLACE = 1
_RENAME_EXCL = 0x00000004


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="commit-cannon",
        description="Benchmark git fast-import inside an isolated local repository.",
    )
    parser.add_argument("--count", type=int, default=DEFAULT_COUNT, help=f"commit count (1-{MAX_COMMITS:,})")
    parser.add_argument("--branch", default=DEFAULT_BRANCH, help="local benchmark branch name")
    parser.add_argument(
        "--keep",
        type=Path,
        help="atomically publish the verified repository at a new path outside this source tree",
    )
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


def _reject_symlink_components(path: Path) -> None:
    for component in (path, *path.parents):
        if component.exists() and component.is_symlink():
            raise BenchmarkError("kept repository path must not traverse symbolic links")


def _validate_publish_destination(path: Path, source_root: Path) -> Path:
    unresolved = path.expanduser().absolute()
    _reject_symlink_components(unresolved.parent)
    unresolved.parent.mkdir(parents=True, exist_ok=True)
    _reject_symlink_components(unresolved.parent)

    destination = unresolved.resolve(strict=False)
    source_root = source_root.resolve()
    if destination == source_root or destination in source_root.parents or source_root in destination.parents:
        raise BenchmarkError("kept repository must be outside the source repository tree")
    if destination.exists() or destination.is_symlink():
        raise BenchmarkError("kept repository path must not already exist")
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


def _rename_noreplace(source: Path, destination: Path) -> None:
    """Atomically publish a directory without replacing an existing path."""

    if os.name == "nt":
        try:
            os.rename(source, destination)
        except FileExistsError as error:
            raise BenchmarkError("kept repository path appeared during publication; refusing to replace it") from error
        except OSError as error:
            raise BenchmarkError(f"unable to publish verified repository atomically: {error}") from error
        return

    libc = ctypes.CDLL(None, use_errno=True)
    source_bytes = os.fsencode(source)
    destination_bytes = os.fsencode(destination)

    if sys.platform.startswith("linux") and hasattr(libc, "renameat2"):
        renameat2 = libc.renameat2
        renameat2.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint]
        renameat2.restype = ctypes.c_int
        result = renameat2(_AT_FDCWD, source_bytes, _AT_FDCWD, destination_bytes, _RENAME_NOREPLACE)
    elif sys.platform == "darwin" and hasattr(libc, "renamex_np"):
        renamex_np = libc.renamex_np
        renamex_np.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_uint]
        renamex_np.restype = ctypes.c_int
        result = renamex_np(source_bytes, destination_bytes, _RENAME_EXCL)
    else:
        raise BenchmarkError("this platform lacks an atomic no-replace directory publish primitive")

    if result == 0:
        return
    error_number = ctypes.get_errno()
    if error_number in {errno.EEXIST, errno.ENOTEMPTY}:
        raise BenchmarkError("kept repository path appeared during publication; refusing to replace it")
    raise BenchmarkError(f"unable to publish verified repository atomically: {os.strerror(error_number)}")


def _run_with_atomic_keep(args: argparse.Namespace, report_path: Path | None, source_root: Path):
    destination = _validate_publish_destination(args.keep, source_root)
    report_created = False
    with tempfile.TemporaryDirectory(prefix=".commit-cannon-stage-", dir=destination.parent) as temporary:
        stage_repository = Path(temporary) / "repository"
        staged_result = run_benchmark(
            count=args.count,
            branch=args.branch,
            keep_repository=stage_repository,
            repack=args.repack,
            timeout_seconds=args.timeout,
            source_root=source_root,
        )
        result = replace(staged_result, kept_repository=str(destination))
        report = result.to_json() + "\n"
        if report_path:
            _write_report_exclusive(report_path, report)
            report_created = True
        try:
            _rename_noreplace(stage_repository, destination)
        except Exception:
            if report_created and report_path is not None:
                report_path.unlink(missing_ok=True)
            raise
        return result, report


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        source_root = Path.cwd().resolve()
        report_path = _validate_report_path(args.json_path, args.keep) if args.json_path else None
        if args.keep is not None:
            _result, report = _run_with_atomic_keep(args, report_path, source_root)
        else:
            result = run_benchmark(
                count=args.count,
                branch=args.branch,
                keep_repository=None,
                repack=args.repack,
                timeout_seconds=args.timeout,
                source_root=source_root,
            )
            report = result.to_json() + "\n"
            if report_path:
                _write_report_exclusive(report_path, report)
        sys.stdout.write(report)
        return 0
    except (TypeError, ValueError, BenchmarkError) as error:
        sys.stderr.write(f"ERROR: {error}\n")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
