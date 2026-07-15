from __future__ import annotations

import json
import tempfile
import unittest
from dataclasses import dataclass
from pathlib import Path
from unittest.mock import patch

from commit_cannon.benchmark import BenchmarkError
from commit_cannon.cli import main


@dataclass(frozen=True)
class FakeResult:
    kept_repository: str | None
    count: int = 3

    def to_json(self) -> str:
        return json.dumps({"count": self.count, "kept_repository": self.kept_repository}, sort_keys=True)


def fake_run_benchmark(*, keep_repository: Path | None, **_kwargs):
    assert keep_repository is not None
    keep_repository.mkdir()
    (keep_repository / "verified.txt").write_text("ok", encoding="utf-8")
    return FakeResult(kept_repository=str(keep_repository))


class AtomicKeepTests(unittest.TestCase):
    def test_cli_publishes_verified_stage_to_new_destination(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            destination = Path(temporary) / "kept"
            report = Path(temporary) / "report.json"
            with patch("commit_cannon.cli.run_benchmark", side_effect=fake_run_benchmark):
                self.assertEqual(main(["--keep", str(destination), "--json", str(report)]), 0)
            self.assertEqual((destination / "verified.txt").read_text(encoding="utf-8"), "ok")
            self.assertEqual(json.loads(report.read_text(encoding="utf-8"))["kept_repository"], str(destination.resolve()))
            self.assertEqual(list(Path(temporary).glob(".commit-cannon-stage-*")), [])

    def test_existing_even_empty_destination_is_refused(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            destination = Path(temporary) / "kept"
            destination.mkdir()
            with patch("commit_cannon.cli.run_benchmark") as runner:
                self.assertEqual(main(["--keep", str(destination)]), 2)
                runner.assert_not_called()
            self.assertEqual(list(destination.iterdir()), [])

    def test_benchmark_failure_leaves_no_destination(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            destination = Path(temporary) / "kept"
            with patch("commit_cannon.cli.run_benchmark", side_effect=BenchmarkError("failed")):
                self.assertEqual(main(["--keep", str(destination)]), 2)
            self.assertFalse(destination.exists())
            self.assertEqual(list(Path(temporary).glob(".commit-cannon-stage-*")), [])

    def test_publish_failure_rolls_back_report(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            destination = Path(temporary) / "kept"
            report = Path(temporary) / "report.json"
            with patch("commit_cannon.cli.run_benchmark", side_effect=fake_run_benchmark), patch(
                "commit_cannon.cli._rename_noreplace", side_effect=BenchmarkError("blocked")
            ):
                self.assertEqual(main(["--keep", str(destination), "--json", str(report)]), 2)
            self.assertFalse(destination.exists())
            self.assertFalse(report.exists())

    def test_destination_race_never_replaces_existing_directory(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            destination = Path(temporary) / "kept"

            def destination_race(source: Path, target: Path) -> None:
                target.mkdir()
                (target / "important.txt").write_text("preserve", encoding="utf-8")
                raise BenchmarkError("kept repository path appeared during publication; refusing to replace it")

            with patch("commit_cannon.cli.run_benchmark", side_effect=fake_run_benchmark), patch(
                "commit_cannon.cli._rename_noreplace", side_effect=destination_race
            ):
                self.assertEqual(main(["--keep", str(destination)]), 2)
            self.assertEqual((destination / "important.txt").read_text(encoding="utf-8"), "preserve")
            self.assertEqual(list(Path(temporary).glob(".commit-cannon-stage-*")), [])

    def test_symlinked_parent_is_refused_before_benchmark(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            real_parent = root / "real"
            real_parent.mkdir()
            linked_parent = root / "linked"
            try:
                linked_parent.symlink_to(real_parent, target_is_directory=True)
            except (OSError, NotImplementedError):
                self.skipTest("directory symlinks are unavailable")
            destination = linked_parent / "kept"
            with patch("commit_cannon.cli.run_benchmark") as runner:
                self.assertEqual(main(["--keep", str(destination)]), 2)
                runner.assert_not_called()
            self.assertFalse((real_parent / "kept").exists())


if __name__ == "__main__":
    unittest.main()
