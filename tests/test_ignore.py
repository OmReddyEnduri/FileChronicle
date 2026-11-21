"""Unit tests for ignore pattern resolution and nested directory traversal."""

import tempfile
import unittest
from pathlib import Path

from filechronicle.engine import ChronicleEngine


class TestIgnorePatterns(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.workspace = Path(self.temp_dir.name) / "ignore_ws"
        self.workspace.mkdir()
        self.db_path = Path(self.temp_dir.name) / "test_ignore.db"
        self.engine = ChronicleEngine(db_path=self.db_path)
        self.proj, _ = self.engine.init_project(str(self.workspace))

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_custom_chronicleignore(self):
        # Add custom ignore pattern
        ignore_file = self.workspace / ".chronicleignore"
        with open(ignore_file, "a", encoding="utf-8") as f:
            f.write("*.log\n")
            f.write("build/\n")
            f.write("temp_secret.txt\n")

        # Create files
        (self.workspace / "normal.txt").write_text("Normal content")
        (self.workspace / "app.log").write_text("Should be ignored")
        (self.workspace / "temp_secret.txt").write_text("Secret")

        build_dir = self.workspace / "build"
        build_dir.mkdir()
        (build_dir / "output.bin").write_bytes(b"\x00\x01\x02")

        scanned = self.engine.scan_directory(self.proj)

        self.assertIn("normal.txt", scanned)
        self.assertNotIn("app.log", scanned)
        self.assertNotIn("temp_secret.txt", scanned)
        self.assertNotIn("build/output.bin", scanned)


if __name__ == "__main__":
    unittest.main()
