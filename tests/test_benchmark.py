from __future__ import annotations

import json
import os
import subprocess
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from commit_cannon.benchmark import (
    BenchmarkError,
    _import_stream,
    _safe_environment,
    run_benchmark,
)
from commit_cannon.cli import main


class BenchmarkTests(unittest.TestCase):
    def test_local_benchmark_imports_exact_count_and_fingerprint(self) -> None:
        result = run_benchmark(count=7, timeout_seconds=30)
        self.assertEqual(result.count, 7)
        self.assertEqual(result.integrity, "passed")
        self.assertEqual(result.remote_count, 0)
        self.assertEqual(result.object_format, "sha1")
        self.assertRegex(result.tip_oid, r"^[0-9a-f]{40}$")
        self.assertEqual(result.schema_version, 2)

    def test_git_environment_drops_repository_routing_variables(self) -> None:
        environment = _safe_environment(
            {
                "PATH": os.environ.get("PATH", ""),
                "GIT_DIR": "/tmp/attacker.git",
                "GIT_WORK_TREE": "/tmp/attacker",
                "GIT_OBJECT_DIRECTORY": "/tmp/objects",
                "GIT_ALTERNATE_OBJECT_DIRECTORIES": "/tmp/alternate",
                "GIT_CONFIG_GLOBAL": "/tmp/attacker-config",
                "HOME": "/tmp/attacker-home",
            }
        )
        for key in (
            "GIT_DIR",
            "GIT_WORK_TREE",
            "GIT_OBJECT_DIRECTORY",
            "GIT_ALTERNATE_OBJECT_DIRECTORIES",
            "HOME",
        ):
            self.assertNotIn(key, environment)
        self.assertEqual(environment["GIT_CONFIG_GLOBAL"], os.devnull)

    def test_hostile_git_environment_cannot_redirect_benchmark(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            outside = Path(temporary) / "outside.git"
            subprocess.run(
                ["git", "init", "--bare", "--quiet", str(outside)],
                check=True,
                stdout=subprocess.DEVNULL,
            )
            before = sorted(path.relative_to(outside) for path in outside.rglob("*"))
            with patch.dict(
                os.environ,
                {"GIT_DIR": str(outside), "GIT_WORK_TREE": str(Path(temporary) / "work")},
                clear=False,
            ):
                result = run_benchmark(count=3, timeout_seconds=30)
            self.assertEqual(result.count, 3)
            self.assertEqual(sorted(path.relative_to(outside) for path in outside.rglob("*")), before)

    def test_stream_timeout_covers_python_writer_and_git_import(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            repository = Path(temporary)
            subprocess.run(
                ["git", "init", "--quiet", "--object-format=sha1"],
                cwd=repository,
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )

            def stalled_writer(*_args: object, **_kwargs: object) -> None:
                time.sleep(0.25)

            started = time.monotonic()
            with patch("commit_cannon.benchmark.write_fast_import_stream", side_effect=stalled_writer):
                with self.assertRaisesRegex(BenchmarkError, "while streaming or importing"):
                    _import_stream(
                        repository,
                        count=1,
                        branch="benchmark",
                        timeout_seconds=0.05,
                    )
            self.assertLess(time.monotonic() - started, 1.0)

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
            self.assertEqual(count, "5")
            self.assertEqual(subprocess.check_output(["git", "remote"], cwd=destination, text=True).strip(), "")

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
        self.assertTrue(run_benchmark(count=3, repack=True, timeout_seconds=30).repacked)

    def test_cli_writes_machine_readable_report_once(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            report = Path(temporary) / "report.json"
            self.assertEqual(main(["--count", "4", "--json", str(report)]), 0)
            payload = json.loads(report.read_text(encoding="utf-8"))
            self.assertEqual(payload["count"], 4)
            self.assertEqual(payload["object_format"], "sha1")
            original = report.read_text(encoding="utf-8")
            self.assertEqual(main(["--count", "2", "--json", str(report)]), 2)
            self.assertEqual(report.read_text(encoding="utf-8"), original)

    def test_report_cannot_be_written_inside_kept_repository(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            keep = Path(temporary) / "kept"
            report = keep / "report.json"
            self.assertEqual(main(["--count", "2", "--keep", str(keep), "--json", str(report)]), 2)
            self.assertFalse(keep.exists())

    def test_cli_rejects_over_cap_without_running_git(self) -> None:
        self.assertEqual(main(["--count", "100001"]), 2)


if __name__ == "__main__":
    unittest.main()
