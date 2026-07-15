from __future__ import annotations

import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

from commit_cannon.benchmark import run_benchmark
from commit_cannon.verify import (
    ReportVerificationError,
    load_report,
    main,
    validate_report,
    verify_repository,
)


class ReportVerificationTests(unittest.TestCase):
    def create_fixture(self, root: Path):
        repository = root / "kept"
        result = run_benchmark(
            count=5,
            branch="benchmark/verify",
            keep_repository=repository,
            timeout_seconds=30,
            source_root=Path.cwd(),
        )
        report_path = root / "report.json"
        report_path.write_text(result.to_json() + "\n", encoding="utf-8")
        return repository, report_path, json.loads(result.to_json())

    def test_verifies_matching_report_and_repository(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            repository, report_path, _payload = self.create_fixture(Path(temporary))
            report = load_report(report_path)
            verification = verify_repository(repository, report, timeout_seconds=30)
            self.assertTrue(verification["verified"])
            self.assertEqual(verification["count"], 5)
            self.assertEqual(verification["branch"], "benchmark/verify")
            self.assertEqual(main([str(report_path), "--repository", str(repository)]), 0)

    def test_rejects_unknown_report_fields(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            _repository, _report_path, payload = self.create_fixture(Path(temporary))
            payload["unreviewed"] = True
            with self.assertRaisesRegex(ReportVerificationError, "unknown fields"):
                validate_report(payload)

    def test_rejects_tampered_commit_count(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            repository, _report_path, payload = self.create_fixture(Path(temporary))
            payload["count"] = 4
            with self.assertRaisesRegex(ReportVerificationError, "expects 4 commits"):
                verify_repository(repository, validate_report(payload), timeout_seconds=30)

    def test_rejects_tampered_tip(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            repository, _report_path, payload = self.create_fixture(Path(temporary))
            payload["tip_oid"] = "0" * 40
            with self.assertRaisesRegex(ReportVerificationError, "tip does not match"):
                verify_repository(repository, validate_report(payload), timeout_seconds=30)

    def test_rejects_added_remote(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            repository, report_path, _payload = self.create_fixture(Path(temporary))
            subprocess.run(
                ["git", "remote", "add", "origin", str(repository)],
                cwd=repository,
                check=True,
                env={"PATH": os.environ.get("PATH", "")},
            )
            with self.assertRaisesRegex(ReportVerificationError, "remote-free"):
                verify_repository(repository, load_report(report_path), timeout_seconds=30)

    def test_rejects_repository_size_change(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            repository, report_path, _payload = self.create_fixture(Path(temporary))
            (repository / ".git" / "unexpected").write_bytes(b"changed")
            with self.assertRaisesRegex(ReportVerificationError, "repository size changed"):
                verify_repository(repository, load_report(report_path), timeout_seconds=30)

    @unittest.skipUnless(hasattr(os, "symlink"), "symbolic links are unavailable")
    def test_rejects_symlinked_report(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _repository, report_path, _payload = self.create_fixture(root)
            link = root / "report-link.json"
            try:
                link.symlink_to(report_path)
            except OSError as error:
                self.skipTest(f"unable to create symlink: {error}")
            with self.assertRaisesRegex(ReportVerificationError, "symbolic link"):
                load_report(link)


if __name__ == "__main__":
    unittest.main()
