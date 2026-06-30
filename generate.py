#!/usr/bin/env python3
"""
commit-cannon: emit a git fast-import stream of N empty commits.

Why fast-import: it is the fastest native git path for bulk commits.
Instead of forking `git commit` per commit (~hundreds/sec) it streams
commit objects straight into a packfile. On a normal box this does
millions of commits per minute, well past the ~100K/min the current
100M record holder used.

Usage:
    python3 generate.py <count> | git fast-import --force
"""
import sys


def main():
    count = int(sys.argv[1]) if len(sys.argv) > 1 else 1_000_000
    name = "commit cannon"
    email = "cannon@example.com"
    ts = 1700000000  # fixed timestamp, keeps things deterministic + fast
    msg = b"x\n"
    out = sys.stdout.buffer

    buf = bytearray()
    flush_every = 50_000

    for i in range(1, count + 1):
        buf += b"commit refs/heads/master\n"
        buf += b"mark :%d\n" % i
        buf += b"committer %s <%s> %d +0000\n" % (name.encode(), email.encode(), ts)
        buf += b"data %d\n" % len(msg)
        buf += msg
        if i > 1:
            buf += b"from :%d\n" % (i - 1)
        buf += b"\n"

        if i % flush_every == 0:
            out.write(buf)
            buf = bytearray()

    if buf:
        out.write(buf)
    out.flush()


if __name__ == "__main__":
    main()
