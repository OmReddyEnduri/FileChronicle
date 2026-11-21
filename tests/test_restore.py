"""Unit tests for file restoration and safety protections."""

import tempfile
import unittest
from pathlib import Path

from filechronicle.engine import ChronicleEngine


class TestRestore(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.workspace = Path(self.temp_dir.name) / "workspace"
        self.workspace.mkdir()
        self.db_path = Path(self.temp_dir.name) / "test_restore.db"
        self.engine = ChronicleEngine(db_path=self.db_path)
        self.proj, _ = self.engine.init_project(str(self.workspace))

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_restore_previous_version(self):
        file_path = self.workspace / "doc.txt"
        file_path.write_text("Version 1 content\n", encoding="utf-8")

        snap1, _ = self.engine.create_snapshot(self.proj, message="Initial version")

        # Overwrite with Version 2
        file_path.write_text("Version 2 completely altered content\n", encoding="utf-8")
        snap2, _ = self.engine.create_snapshot(self.proj, message="Version 2")

        # Restore Version 1
        restored = self.engine.restore_file(
            rel_path="doc.txt",
            snapshot_id=snap1.id,
            target_path=str(self.workspace),
            force=False,
            backup=True,
        )

        self.assertEqual(restored.read_text(encoding="utf-8"), "Version 1 content\n")
        # Check that backup file was made
        bak_file = file_path.with_suffix(".txt.bak")
        self.assertTrue(bak_file.exists())
        self.assertEqual(bak_file.read_text(encoding="utf-8"), "Version 2 completely altered content\n")

    def test_restore_to_custom_destination(self):
        file_path = self.workspace / "source.txt"
        file_path.write_text("Original text here", encoding="utf-8")

        snap1, _ = self.engine.create_snapshot(self.proj, message="Baseline")

        dest = self.workspace / "restored_copy" / "target.txt"
        restored = self.engine.restore_file(
            rel_path="source.txt",
            snapshot_id=snap1.id,
            target_path=str(self.workspace),
            output_path=str(dest),
        )

        self.assertTrue(dest.exists())
        self.assertEqual(dest.read_text(encoding="utf-8"), "Original text here")

    def test_restore_nonexistent_or_deleted_file_raises(self):
        with self.assertRaises(ValueError):
            self.engine.restore_file("ghost.txt", snapshot_id=999, target_path=str(self.workspace))


if __name__ == "__main__":
    unittest.main()
