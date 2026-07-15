from __future__ import annotations

import io
import unittest

from commit_cannon.stream import MAX_COMMITS, validate_branch, validate_count, write_fast_import_stream


class StreamTests(unittest.TestCase):
    def test_count_bounds(self) -> None:
        self.assertEqual(validate_count(1), 1)
        self.assertEqual(validate_count(MAX_COMMITS), MAX_COMMITS)
        for invalid in (0, -1, MAX_COMMITS + 1):
            with self.assertRaises(ValueError):
                validate_count(invalid)

    def test_bool_is_not_a_count(self) -> None:
        with self.assertRaises(TypeError):
            validate_count(True)

    def test_branch_validation(self) -> None:
        self.assertEqual(validate_branch("benchmark/local"), "benchmark/local")
        for invalid in ("", "HEAD", "-bad", "main", "bad..name", ".hidden", "x.lock", "bad name", "a@{b"):
            with self.subTest(invalid=invalid):
                with self.assertRaises(ValueError):
                    validate_branch(invalid)

    def test_stream_is_deterministic_and_complete(self) -> None:
        first = io.BytesIO()
        second = io.BytesIO()
        write_fast_import_stream(first, count=3, branch="benchmark")
        write_fast_import_stream(second, count=3, branch="benchmark")
        self.assertEqual(first.getvalue(), second.getvalue())
        text = first.getvalue().decode("utf-8")
        self.assertEqual(text.count("commit refs/heads/benchmark\n"), 3)
        self.assertIn("mark :3\n", text)
        self.assertIn("from :2\n", text)
        self.assertTrue(text.endswith("done\n"))

    def test_stream_flushes_in_chunks(self) -> None:
        class CountingBuffer(io.BytesIO):
            def __init__(self) -> None:
                super().__init__()
                self.writes = 0

            def write(self, data: bytes) -> int:
                self.writes += 1
                return super().write(data)

        output = CountingBuffer()
        write_fast_import_stream(output, count=5, flush_every=2)
        self.assertEqual(output.writes, 3)


if __name__ == "__main__":
    unittest.main()
