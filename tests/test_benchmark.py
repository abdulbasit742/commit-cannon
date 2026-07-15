from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from commit_cannon.benchmark import BenchmarkError, run_benchmark
from commit_cannon.cli import main


class BenchmarkTests(unittest.TestCase):
    def test_local_benchmark_imports_exact_count(self) -> None:
        result = run_benchmark(count=7, timeout_seconds=30)
        self.assertEqual(result.count, 7)
        self.assertEqual(result.integrity, "passed")
        self.assertEqual(result.remote_count, 0)
        self.assertIsNone(result.kept_repository)
        self.assertGreater(result.repository_size_bytes, 0)

    def test_kept_repository_has_no_remote(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            destination = Path(temporary) / "kept"
            result = run_benchmark(
                count=5,
                branch="benchmark/test",
                keep_repository=destination,
                timeout_seconds=30,
                source_root=Path.cwd(),
            )
            self.assertEqual(result.kept_repository, str(destination.resolve()))
            count = subprocess.check_output(
                ["git", "rev-list", "--count", "refs/heads/benchmark/test"],
                cwd=destination,
                text=True,
            ).strip()
            remotes = subprocess.check_output(["git", "remote"], cwd=destination, text=True).strip()
            self.assertEqual(count, "5")
            self.assertEqual(remotes, "")

    def test_non_empty_keep_directory_is_refused(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            destination = Path(temporary) / "kept"
            destination.mkdir()
            (destination / "important.txt").write_text("do not overwrite", encoding="utf-8")
            with self.assertRaises(BenchmarkError):
                run_benchmark(count=2, keep_repository=destination, source_root=Path.cwd())
            self.assertEqual((destination / "important.txt").read_text(encoding="utf-8"), "do not overwrite")

    def test_source_tree_destination_is_refused(self) -> None:
        source_root = Path.cwd().resolve()
        with self.assertRaises(BenchmarkError):
            run_benchmark(count=2, keep_repository=source_root / "nested-output", source_root=source_root)

    def test_repack_is_explicit_and_reported(self) -> None:
        result = run_benchmark(count=3, repack=True, timeout_seconds=30)
        self.assertTrue(result.repacked)

    def test_cli_writes_machine_readable_report(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            report = Path(temporary) / "report.json"
            exit_code = main(["--count", "4", "--json", str(report)])
            self.assertEqual(exit_code, 0)
            payload = json.loads(report.read_text(encoding="utf-8"))
            self.assertEqual(payload["count"], 4)
            self.assertEqual(payload["remote_count"], 0)
            self.assertEqual(payload["integrity"], "passed")

    def test_cli_rejects_over_cap_without_running_git(self) -> None:
        exit_code = main(["--count", "100001"])
        self.assertEqual(exit_code, 2)


if __name__ == "__main__":
    unittest.main()
