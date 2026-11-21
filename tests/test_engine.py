"""Unit tests for ChronicleEngine (snapshotting, differential tracking, status, diffs)."""

import tempfile
import unittest
from pathlib import Path

from filechronicle.engine import ChronicleEngine


class TestEngine(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.workspace = Path(self.temp_dir.name) / "workspace"
        self.workspace.mkdir()
        self.db_path = Path(self.temp_dir.name) / "test_engine.db"
        self.engine = ChronicleEngine(db_path=self.db_path)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_init_and_ignore_handling(self):
        proj, is_new = self.engine.init_project(str(self.workspace), name="WorkspaceTest")
        self.assertTrue(is_new)
        self.assertEqual(proj.name, "WorkspaceTest")

        # Verify .chronicleignore created
        self.assertTrue((self.workspace / ".chronicleignore").exists())

        # Calling init again returns existing
        proj2, is_new2 = self.engine.init_project(str(self.workspace))
        self.assertFalse(is_new2)
        self.assertEqual(proj.id, proj2.id)

    def test_snapshot_lifecycle(self):
        proj, _ = self.engine.init_project(str(self.workspace))

        # Create two files
        file1 = self.workspace / "file1.txt"
        file1.write_text("Line 1 in file 1\nLine 2 in file 1\n", encoding="utf-8")

        file2 = self.workspace / "file2.txt"
        file2.write_text("Hello from file 2\n", encoding="utf-8")

        # Snapshot 1
        snap1, sum1 = self.engine.create_snapshot(proj, message="Initial files")
        self.assertEqual(sum1["files_added"], 2)
        self.assertEqual(sum1["files_modified"], 0)
        self.assertEqual(sum1["files_deleted"], 0)
        self.assertEqual(sum1["total_files"], 2)

        # Status check - should be clean
        statuses = [s for s in self.engine.status(proj) if s.status != "clean"]
        self.assertEqual(len(statuses), 0)

        # Modify file 1
        file1.write_text("Line 1 in file 1\nLine 2 MODIFIED\nLine 3 added\n", encoding="utf-8")

        # Status check - file1 should be modified
        mod_status = [s for s in self.engine.status(proj) if s.status != "clean"]
        self.assertEqual(len(mod_status), 1)
        self.assertEqual(mod_status[0].rel_path, "file1.txt")
        self.assertEqual(mod_status[0].status, "modified")

        # Snapshot 2
        snap2, sum2 = self.engine.create_snapshot(proj, message="Update file 1")
        self.assertEqual(sum2["files_added"], 0)
        self.assertEqual(sum2["files_modified"], 1)
        self.assertEqual(sum2["files_deleted"], 0)
        self.assertEqual(sum2["total_files"], 2)

        # Diff between snap1 and snap2
        diffs = self.engine.diff_snapshots(snap1.id, snap2.id, target_path=str(self.workspace))
        self.assertEqual(len(diffs), 1)
        self.assertEqual(diffs[0].rel_path, "file1.txt")
        self.assertIn("-Line 2 in file 1", diffs[0].diff_text)
        self.assertIn("+Line 2 MODIFIED", diffs[0].diff_text)
        self.assertIn("+Line 3 added", diffs[0].diff_text)

        # Delete file 2
        file2.unlink()

        # Status check - file2 should be deleted
        del_status = [s for s in self.engine.status(proj) if s.status != "clean"]
        self.assertEqual(len(del_status), 1)
        self.assertEqual(del_status[0].rel_path, "file2.txt")
        self.assertEqual(del_status[0].status, "deleted")

        # Snapshot 3
        snap3, sum3 = self.engine.create_snapshot(proj, message="Deleted file 2")
        self.assertEqual(sum3["files_deleted"], 1)
        self.assertEqual(sum3["total_files"], 1)

        # History of file 1
        hist1 = self.engine.file_history("file1.txt", target_path=str(self.workspace))
        self.assertEqual(len(hist1), 3)  # added in snap1, modified in snap2, unchanged in snap3
        self.assertEqual(hist1[0][1].change_type, "added")
        self.assertEqual(hist1[1][1].change_type, "modified")
        self.assertEqual(hist1[2][1].change_type, "unchanged")


if __name__ == "__main__":
    unittest.main()
