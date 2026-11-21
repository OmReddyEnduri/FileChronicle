"""Unit tests for SQLite database layer and blob deduplication."""

import tempfile
import unittest
from pathlib import Path

from filechronicle.db import ChronicleDB
from filechronicle.storage import prepare_blob


class TestDatabase(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test_chronicle.db"
        self.db = ChronicleDB(self.db_path)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_project_creation_and_lookup(self):
        proj1 = self.db.get_or_create_project("D:/my_project", name="My Project")
        self.assertIsNotNone(proj1.id)
        self.assertEqual(proj1.name, "My Project")

        # Second lookup returns existing
        proj2 = self.db.get_or_create_project("D:/my_project")
        self.assertEqual(proj1.id, proj2.id)

        # Lookup by child path
        found = self.db.find_project_for_path("D:/my_project/src/main.py")
        self.assertIsNotNone(found)
        self.assertEqual(found.id, proj1.id)

    def test_blob_storage_and_deduplication(self):
        data = b"Universal file intelligence content"
        sha, size, is_bin, compressed = prepare_blob(data)

        # First insert succeeds
        inserted = self.db.store_blob(sha, size, is_bin, compressed)
        self.assertTrue(inserted)
        self.assertTrue(self.db.has_blob(sha))

        # Duplicate insert ignored
        inserted_again = self.db.store_blob(sha, size, is_bin, compressed)
        self.assertFalse(inserted_again)

        # Retrieve and verify content
        record = self.db.get_blob(sha)
        self.assertIsNotNone(record)
        self.assertEqual(record.content, data)
        self.assertEqual(record.size, len(data))

    def test_snapshot_and_revision_lifecycle(self):
        proj = self.db.get_or_create_project(self.temp_dir.name, name="TestProj")

        # Create snapshot
        snap = self.db.create_snapshot(
            project_id=proj.id,
            snapshot_tag="snap-test-001",
            message="Initial setup",
            total_files=2,
            total_bytes=100,
            files_added=2,
            files_modified=0,
            files_deleted=0,
        )
        self.assertIsNotNone(snap.id)

        # Store a blob for the revision
        data = b"print('hello')"
        sha, size, is_bin, compressed = prepare_blob(data)
        self.db.store_blob(sha, size, is_bin, compressed)

        # Record revision
        revisions = [
            {
                "snapshot_id": snap.id,
                "project_id": proj.id,
                "rel_path": "hello.py",
                "sha256": sha,
                "file_size": size,
                "mtime": 1000.0,
                "change_type": "added",
                "lines_added": 1,
                "lines_deleted": 0,
                "diff_unified": "+print('hello')",
            }
        ]
        self.db.record_file_revisions(revisions)

        # Query snapshot revisions
        active_revs = self.db.get_snapshot_revisions(snap.id)
        self.assertIn("hello.py", active_revs)
        self.assertEqual(active_revs["hello.py"].sha256, sha)

        # Query file history
        history = self.db.get_file_history(proj.id, "hello.py")
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0][0].id, snap.id)
        self.assertEqual(history[0][1].change_type, "added")


if __name__ == "__main__":
    unittest.main()
