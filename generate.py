#!/usr/bin/env python3
"""Compatibility frontend that emits a bounded fast-import stream to stdout."""

from __future__ import annotations

import argparse
import sys

from commit_cannon.stream import DEFAULT_BRANCH, DEFAULT_COUNT, MAX_COMMITS, write_fast_import_stream


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Emit a bounded local git fast-import stream.")
    parser.add_argument("count", nargs="?", type=int, default=DEFAULT_COUNT, help=f"commit count (1-{MAX_COMMITS:,})")
    parser.add_argument("--branch", default=DEFAULT_BRANCH)
    args = parser.parse_args(argv)
    try:
        write_fast_import_stream(sys.stdout.buffer, count=args.count, branch=args.branch)
        return 0
    except (TypeError, ValueError) as error:
        sys.stderr.write(f"ERROR: {error}\n")
        return 2
    except BrokenPipeError:
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
