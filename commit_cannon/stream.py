"""Generate a deterministic, bounded ``git fast-import`` stream."""

from __future__ import annotations

from typing import BinaryIO

DEFAULT_COUNT = 1_000
MAX_COMMITS = 100_000
DEFAULT_BRANCH = "benchmark"
DEFAULT_TIMESTAMP = 1_700_000_000

_FORBIDDEN_REF_CHARS = set(" ~^:?*[\\")


def validate_count(value: int) -> int:
    """Return a validated commit count.

    The hard cap is intentionally not configurable. This project is a local
    benchmark, not a hosted-service load generator.
    """

    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError("count must be an integer")
    if value < 1:
        raise ValueError("count must be at least 1")
    if value > MAX_COMMITS:
        raise ValueError(f"count must not exceed the hard cap of {MAX_COMMITS:,}")
    return value


def validate_branch(value: str) -> str:
    """Validate a conservative local branch name without invoking a shell."""

    if not isinstance(value, str):
        raise TypeError("branch must be a string")
    branch = value.strip()
    if not branch or len(branch) > 100:
        raise ValueError("branch must contain 1 to 100 characters")
    if branch == "HEAD" or branch.startswith("-"):
        raise ValueError("branch name is reserved or unsafe")
    if branch != "benchmark" and not branch.startswith("benchmark/"):
        raise ValueError("branch must stay inside the benchmark namespace")
    if branch.startswith("/") or branch.endswith("/") or branch.endswith("."):
        raise ValueError("branch cannot start/end with slash or end with dot")
    if ".." in branch or "//" in branch or "@{" in branch:
        raise ValueError("branch contains a forbidden sequence")
    if any(char in _FORBIDDEN_REF_CHARS or ord(char) < 32 or ord(char) == 127 for char in branch):
        raise ValueError("branch contains a forbidden character")
    for component in branch.split("/"):
        if not component or component.startswith(".") or component.endswith(".lock"):
            raise ValueError("branch contains an unsafe path component")
    return branch


def write_fast_import_stream(
    output: BinaryIO,
    *,
    count: int,
    branch: str = DEFAULT_BRANCH,
    start_timestamp: int = DEFAULT_TIMESTAMP,
    flush_every: int = 1_000,
) -> None:
    """Write a complete deterministic stream and terminate it with ``done``."""

    count = validate_count(count)
    branch = validate_branch(branch)
    if flush_every < 1 or flush_every > MAX_COMMITS:
        raise ValueError(f"flush_every must be between 1 and {MAX_COMMITS:,}")
    if not isinstance(start_timestamp, int) or start_timestamp < 0:
        raise ValueError("start_timestamp must be a non-negative integer")

    ref = f"refs/heads/{branch}".encode("utf-8")
    buffer = bytearray()

    for index in range(1, count + 1):
        message = f"benchmark commit {index}\n".encode("utf-8")
        buffer.extend(b"commit " + ref + b"\n")
        buffer.extend(f"mark :{index}\n".encode("ascii"))
        buffer.extend(
            f"committer commit-cannon <benchmark@example.invalid> {start_timestamp + index - 1} +0000\n".encode(
                "ascii"
            )
        )
        buffer.extend(f"data {len(message)}\n".encode("ascii"))
        buffer.extend(message)
        if index > 1:
            buffer.extend(f"from :{index - 1}\n".encode("ascii"))
        buffer.extend(b"\n")

        if index % flush_every == 0:
            output.write(buffer)
            buffer.clear()

    buffer.extend(b"done\n")
    output.write(buffer)
    output.flush()
