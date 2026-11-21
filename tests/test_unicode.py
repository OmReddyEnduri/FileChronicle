"""Unit tests for unicode handling, emojis, and nested directory trees."""

import tempfile
import unittest
from pathlib import Path

from filechronicle.engine import ChronicleEngine


class TestUnicodeAndDeepTrees(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.workspace = Path(self.temp_dir.name) / "unicode_ws"
        self.workspace.mkdir()
        self.db_path = Path(self.temp_dir.name) / "test_unicode.db"
        self.engine = ChronicleEngine(db_path=self.db_path)
        self.proj, _ = self.engine.init_project(str(self.workspace))

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_unicode_and_deep_nesting(self):
        nested_dir = self.workspace / "src" / "deep" / "components"
        nested_dir.mkdir(parents=True)

        unicode_file = nested_dir / "international_🚀.md"
        unicode_bytes = "# FileChronicle 🚀\nMulti-lingual: 日本語, Español, Français, हिन्दी.\n".encode("utf-8")
        unicode_file.write_bytes(unicode_bytes)

        snap1, sum1 = self.engine.create_snapshot(self.proj, message="Add unicode file")
        self.assertEqual(sum1["files_added"], 1)

        # Verify content retrieval
        cat_content = self.engine.get_file_content("src/deep/components/international_🚀.md", snap1.id, str(self.workspace))
        self.assertEqual(cat_content, unicode_bytes)

        # Update unicode file
        new_bytes = unicode_bytes + "Added line with ✨ sparkle.\n".encode("utf-8")
        unicode_file.write_bytes(new_bytes)
        snap2, sum2 = self.engine.create_snapshot(self.proj, message="Update unicode file")
        self.assertEqual(sum2["files_modified"], 1)

        # Diff
        diffs = self.engine.diff_snapshots(snap1.id, snap2.id, str(self.workspace))
        self.assertEqual(len(diffs), 1)
        self.assertIn("✨ sparkle", diffs[0].diff_text)


if __name__ == "__main__":
    unittest.main()
