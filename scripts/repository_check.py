#!/usr/bin/env python3
"""Fail when active code regains hosted-push or unbounded history behavior."""

from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ACTIVE_FILES = [
    ROOT / "generate.py",
    ROOT / "run.sh",
    *sorted((ROOT / "commit_cannon").glob("*.py")),
]
findings: list[str] = []

for path in ACTIVE_FILES:
    text = path.read_text(encoding="utf-8")
    relative = path.relative_to(ROOT)
    prohibited = {
        "git-push": r"\bgit\s+push\b",
        "force-update": r"(?:--force|-f\b)",
        "remote-add": r"\bgit\s+remote\s+add\b",
        "hosted-record-target": r"100[,_]?000[,_]?000|100M",
        "shell-execution": r"shell\s*=\s*True",
    }
    for rule, pattern in prohibited.items():
        if re.search(pattern, text, flags=re.IGNORECASE):
            findings.append(f"{relative}: prohibited {rule} pattern")

for path in sorted((ROOT / "commit_cannon").glob("*.py")) + [ROOT / "generate.py"]:
    try:
        ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except SyntaxError as error:
        findings.append(f"{path.relative_to(ROOT)}: syntax error: {error}")

stream_text = (ROOT / "commit_cannon" / "stream.py").read_text(encoding="utf-8")
match = re.search(r"^MAX_COMMITS\s*=\s*([0-9_]+)\s*$", stream_text, flags=re.MULTILINE)
if not match:
    findings.append("commit_cannon/stream.py: MAX_COMMITS hard cap is missing")
elif int(match.group(1).replace("_", "")) > 100_000:
    findings.append("commit_cannon/stream.py: MAX_COMMITS exceeds 100,000")

runner = (ROOT / "run.sh").read_text(encoding="utf-8")
if "python3 -m commit_cannon.cli" not in runner:
    findings.append("run.sh: must delegate to the reviewed Python CLI")

if findings:
    print(f"Repository safety check failed with {len(findings)} finding(s):", file=sys.stderr)
    for finding in findings:
        print(f"- {finding}", file=sys.stderr)
    raise SystemExit(1)

print(f"Repository safety check passed for {len(ACTIVE_FILES)} active files.")
