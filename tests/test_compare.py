from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from commit_cannon.compare import ComparisonError, compare_reports, main


def report(**overrides):
    payload = {
        "schema_version": 1,
        "benchmark_schema_version": 2,
        "count": 1000,
        "branch": "benchmark",
        "runs": 3,
        "warmups": 1,
        "repacked": False,
        "git_version": "git version 2.45.0",
        "object_format": "sha1",
        "platform_system": "Linux",
        "platform_release": "6.8",
        "platform_machine": "x86_64",
        "python_version": "3.12.4",
        "cpu_count": 8,
        "integrity": "passed",
        "median_elapsed_seconds": 1.0,
        "median_commits_per_second": 1000.0,
        "coefficient_of_variation_percent": 2.0,
        "samples": [
            {"elapsed_seconds": 0.99, "commits_per_second": 1010.1},
            {"elapsed_seconds": 1.0, "commits_per_second": 1000.0},
            {"elapsed_seconds": 1.01, "commits_per_second": 990.1},
        ],
    }
    payload.update(overrides)
    return payload


class CompareReportsTests(unittest.TestCase):
    def test_passes_within_threshold(self):
        result = compare_reports(report(), report(median_elapsed_seconds=1.05, median_commits_per_second=952.38))
        self.assertEqual(result.status, "passed")
        self.assertAlmostEqual(result.elapsed_slowdown_percent, 5.0)

    def test_marks_regression_over_threshold(self):
        result = compare_reports(report(), report(median_elapsed_seconds=1.2, median_commits_per_second=833.33))
        self.assertEqual(result.status, "regressed")
        self.assertGreater(result.elapsed_slowdown_percent, 10)

    def test_rejects_changed_environment(self):
        with self.assertRaisesRegex(ComparisonError, "platform_machine"):
            compare_reports(report(), report(platform_machine="arm64"))

    def test_rejects_changed_workload(self):
        with self.assertRaisesRegex(ComparisonError, "count"):
            compare_reports(report(), report(count=2000))

    def test_rejects_noisy_reports(self):
        with self.assertRaisesRegex(ComparisonError, "too noisy"):
            compare_reports(report(), report(coefficient_of_variation_percent=15.0))

    def test_rejects_failed_integrity(self):
        with self.assertRaisesRegex(ComparisonError, "integrity"):
            compare_reports(report(integrity="failed"), report())

    def test_rejects_sample_count_mismatch(self):
        with self.assertRaisesRegex(ComparisonError, "sample count"):
            compare_reports(report(samples=[]), report())

    def test_rejects_invalid_thresholds(self):
        with self.assertRaisesRegex(ComparisonError, "max_slowdown_percent"):
            compare_reports(report(), report(), max_slowdown_percent=101)

    def test_cli_exit_codes_are_stable(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            baseline = root / "baseline.json"
            candidate = root / "candidate.json"
            baseline.write_text(json.dumps(report()), encoding="utf-8")
            candidate.write_text(json.dumps(report(median_elapsed_seconds=1.2)), encoding="utf-8")
            self.assertEqual(main([str(baseline), str(candidate)]), 1)
            self.assertEqual(main([str(baseline), str(candidate), "--max-slowdown-percent", "25"]), 0)

    def test_cli_rejects_symlinked_input(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            baseline = root / "baseline.json"
            candidate = root / "candidate.json"
            link = root / "baseline-link.json"
            baseline.write_text(json.dumps(report()), encoding="utf-8")
            candidate.write_text(json.dumps(report()), encoding="utf-8")
            try:
                link.symlink_to(baseline)
            except (OSError, NotImplementedError):
                self.skipTest("symbolic links unavailable")
            self.assertEqual(main([str(link), str(candidate)]), 2)


if __name__ == "__main__":
    unittest.main()
