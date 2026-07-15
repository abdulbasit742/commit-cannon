from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from commit_cannon.benchmark import BenchmarkError, BenchmarkResult
from commit_cannon.suite import main, run_suite, validate_suite_workload


def result(elapsed: float, *, tip: str = "a" * 40, git_version: str = "git version 2.45.0") -> BenchmarkResult:
    return BenchmarkResult(
        schema_version=2,
        count=100,
        branch="benchmark",
        started_at="2026-01-01T00:00:00+00:00",
        finished_at="2026-01-01T00:00:01+00:00",
        elapsed_seconds=elapsed,
        commits_per_second=100 / elapsed,
        repository_size_bytes=1024,
        git_version=git_version,
        object_format="sha1",
        tip_oid=tip,
        integrity="passed",
        remote_count=0,
        repacked=False,
        kept_repository=None,
    )


class SuiteTests(unittest.TestCase):
    def test_summary_uses_warmups_and_robust_statistics(self) -> None:
        values = iter([result(9.0), result(1.0), result(2.0), result(6.0)])
        calls: list[dict[str, object]] = []

        def runner(**kwargs: object) -> BenchmarkResult:
            calls.append(kwargs)
            return next(values)

        suite = run_suite(count=100, runs=3, warmups=1, runner=runner)
        self.assertEqual(len(calls), 4)
        self.assertTrue(all(call["keep_repository"] is None for call in calls))
        self.assertEqual(suite.total_generated_commits, 400)
        self.assertEqual(suite.median_elapsed_seconds, 2.0)
        self.assertEqual(suite.mean_elapsed_seconds, 3.0)
        self.assertEqual(suite.min_elapsed_seconds, 1.0)
        self.assertEqual(suite.max_elapsed_seconds, 6.0)
        self.assertEqual(len(suite.samples), 3)
        self.assertEqual(suite.integrity, "passed")

    def test_cumulative_commit_cap_fails_closed(self) -> None:
        with self.assertRaisesRegex(ValueError, "300,000"):
            validate_suite_workload(100_000, 3, 1)

    def test_runs_and_warmups_are_bounded(self) -> None:
        with self.assertRaises(ValueError):
            validate_suite_workload(1, 1, 0)
        with self.assertRaises(ValueError):
            validate_suite_workload(1, 10, 0)
        with self.assertRaises(ValueError):
            validate_suite_workload(1, 2, 4)

    def test_deterministic_tip_mismatch_is_rejected(self) -> None:
        values = iter([result(1.0, tip="a" * 40), result(1.1, tip="b" * 40)])
        with self.assertRaisesRegex(BenchmarkError, "tip changed"):
            run_suite(count=100, runs=2, warmups=0, runner=lambda **_kwargs: next(values))

    def test_git_version_change_is_rejected(self) -> None:
        values = iter([result(1.0), result(1.1, git_version="git version 2.46.0")])
        with self.assertRaisesRegex(BenchmarkError, "Git version changed"):
            run_suite(count=100, runs=2, warmups=0, runner=lambda **_kwargs: next(values))

    def test_cli_report_is_exclusive(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            report = Path(temporary) / "suite.json"
            self.assertEqual(
                main(["--count", "3", "--runs", "2", "--warmups", "0", "--json", str(report)]),
                0,
            )
            payload = json.loads(report.read_text(encoding="utf-8"))
            self.assertEqual(payload["schema_version"], 1)
            self.assertEqual(payload["runs"], 2)
            original = report.read_text(encoding="utf-8")
            self.assertEqual(
                main(["--count", "3", "--runs", "2", "--warmups", "0", "--json", str(report)]),
                2,
            )
            self.assertEqual(report.read_text(encoding="utf-8"), original)


if __name__ == "__main__":
    unittest.main()
