"""SQLite database schema and queries for FileChronicle."""

import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import List, Optional, Tuple, Dict, Any, Generator
from datetime import datetime

from .models import Project, Snapshot, FileRevision, BlobRecord
from .storage import decompress_content, compress_content
from .config import DEFAULT_IGNORE_PATTERNS


SCHEMA_SQL = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS projects (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    root_path TEXT UNIQUE NOT NULL,
    created_at TEXT NOT NULL,
    ignore_patterns TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS blobs (
    sha256 TEXT PRIMARY KEY,
    size INTEGER NOT NULL,
    is_binary INTEGER NOT NULL,
    compressed_content BLOB NOT NULL
);

CREATE TABLE IF NOT EXISTS snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL,
    snapshot_tag TEXT NOT NULL,
    message TEXT NOT NULL,
    created_at TEXT NOT NULL,
    total_files INTEGER NOT NULL DEFAULT 0,
    total_bytes INTEGER NOT NULL DEFAULT 0,
    files_added INTEGER NOT NULL DEFAULT 0,
    files_modified INTEGER NOT NULL DEFAULT 0,
    files_deleted INTEGER NOT NULL DEFAULT 0,
    FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS file_revisions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    snapshot_id INTEGER NOT NULL,
    project_id INTEGER NOT NULL,
    rel_path TEXT NOT NULL,
    sha256 TEXT NOT NULL,
    file_size INTEGER NOT NULL,
    mtime REAL NOT NULL,
    change_type TEXT NOT NULL,
    lines_added INTEGER NOT NULL DEFAULT 0,
    lines_deleted INTEGER NOT NULL DEFAULT 0,
    diff_unified TEXT,
    FOREIGN KEY(snapshot_id) REFERENCES snapshots(id) ON DELETE CASCADE,
    FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE,
    FOREIGN KEY(sha256) REFERENCES blobs(sha256)
);

CREATE INDEX IF NOT EXISTS idx_snapshots_project ON snapshots(project_id);
CREATE INDEX IF NOT EXISTS idx_snapshots_tag ON snapshots(snapshot_tag);
CREATE INDEX IF NOT EXISTS idx_revisions_snap ON file_revisions(snapshot_id);
CREATE INDEX IF NOT EXISTS idx_revisions_path ON file_revisions(project_id, rel_path);
CREATE INDEX IF NOT EXISTS idx_revisions_sha ON file_revisions(sha256);
"""


class ChronicleDB:
    """Manages SQLite operations for chronicle."""

    def __init__(self, db_path: Path):
        self.db_path = Path(db_path).resolve()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    @contextmanager
    def _get_connection(self) -> Generator[sqlite3.Connection, None, None]:
        conn = sqlite3.connect(str(self.db_path), timeout=30.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        try:
            with conn:
                yield conn
        finally:
            conn.close()

    def _init_db(self):
        with self._get_connection() as conn:
            conn.executescript(SCHEMA_SQL)

    # Project operations
    def get_or_create_project(self, root_path: str, name: Optional[str] = None, ignore_patterns: Optional[List[str]] = None) -> Project:
        normalized_path = str(Path(root_path).resolve())
        proj_name = name or Path(normalized_path).name or "root"
        default_patterns = json.dumps(ignore_patterns if ignore_patterns is not None else DEFAULT_IGNORE_PATTERNS)

        with self._get_connection() as conn:
            row = conn.execute(
                "SELECT id, name, root_path, created_at, ignore_patterns FROM projects WHERE root_path = ?",
                (normalized_path,),
            ).fetchone()

            if row:
                return Project(
                    id=row["id"],
                    name=row["name"],
                    root_path=row["root_path"],
                    created_at=row["created_at"],
                    ignore_patterns=json.loads(row["ignore_patterns"]),
                )

            now = datetime.now().isoformat()
            cursor = conn.execute(
                "INSERT INTO projects (name, root_path, created_at, ignore_patterns) VALUES (?, ?, ?, ?)",
                (proj_name, normalized_path, now, default_patterns),
            )
            project_id = cursor.lastrowid
            return Project(
                id=project_id,
                name=proj_name,
                root_path=normalized_path,
                created_at=now,
                ignore_patterns=json.loads(default_patterns),
            )

    def find_project_for_path(self, path: str) -> Optional[Project]:
        """Find the closest enclosing registered project for a given path."""
        target = Path(path).resolve()
        with self._get_connection() as conn:
            rows = conn.execute("SELECT id, name, root_path, created_at, ignore_patterns FROM projects").fetchall()

        matched_project = None
        longest_match = -1

        for row in rows:
            root = Path(row["root_path"])
            try:
                # Check if target is inside root or equals root
                target.relative_to(root)
                match_len = len(str(root))
                if match_len > longest_match:
                    longest_match = match_len
                    matched_project = Project(
                        id=row["id"],
                        name=row["name"],
                        root_path=row["root_path"],
                        created_at=row["created_at"],
                        ignore_patterns=json.loads(row["ignore_patterns"]),
                    )
            except ValueError:
                continue

        return matched_project

    def list_projects(self) -> List[Project]:
        with self._get_connection() as conn:
            rows = conn.execute("SELECT id, name, root_path, created_at, ignore_patterns FROM projects ORDER BY id").fetchall()
            return [
                Project(
                    id=r["id"],
                    name=r["name"],
                    root_path=r["root_path"],
                    created_at=r["created_at"],
                    ignore_patterns=json.loads(r["ignore_patterns"]),
                )
                for r in rows
            ]

    # Blob operations
    def store_blob(self, sha256: str, size: int, is_binary: bool, compressed_content: bytes) -> bool:
        """Stores blob if not already existing. Returns True if inserted, False if existed."""
        with self._get_connection() as conn:
            try:
                conn.execute(
                    "INSERT INTO blobs (sha256, size, is_binary, compressed_content) VALUES (?, ?, ?, ?)",
                    (sha256, size, 1 if is_binary else 0, compressed_content),
                )
                return True
            except sqlite3.IntegrityError:
                return False

    def get_blob(self, sha256: str) -> Optional[BlobRecord]:
        with self._get_connection() as conn:
            row = conn.execute(
                "SELECT sha256, size, is_binary, compressed_content FROM blobs WHERE sha256 = ?",
                (sha256,),
            ).fetchone()
            if not row:
                return None
            decompressed = decompress_content(row["compressed_content"])
            return BlobRecord(
                sha256=row["sha256"],
                size=row["size"],
                is_binary=bool(row["is_binary"]),
                content=decompressed,
            )

    def has_blob(self, sha256: str) -> bool:
        with self._get_connection() as conn:
            row = conn.execute("SELECT 1 FROM blobs WHERE sha256 = ?", (sha256,)).fetchone()
            return row is not None

    # Snapshot operations
    def create_snapshot(
        self,
        project_id: int,
        snapshot_tag: str,
        message: str,
        total_files: int,
        total_bytes: int,
        files_added: int,
        files_modified: int,
        files_deleted: int,
    ) -> Snapshot:
        now = datetime.now().isoformat()
        with self._get_connection() as conn:
            cursor = conn.execute(
                """
                INSERT INTO snapshots (
                    project_id, snapshot_tag, message, created_at,
                    total_files, total_bytes, files_added, files_modified, files_deleted
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    project_id,
                    snapshot_tag,
                    message,
                    now,
                    total_files,
                    total_bytes,
                    files_added,
                    files_modified,
                    files_deleted,
                ),
            )
            snap_id = cursor.lastrowid
            return Snapshot(
                id=snap_id,
                project_id=project_id,
                snapshot_tag=snapshot_tag,
                message=message,
                created_at=now,
                total_files=total_files,
                total_bytes=total_bytes,
                files_added=files_added,
                files_modified=files_modified,
                files_deleted=files_deleted,
            )

    def get_snapshot(self, project_id: int, identifier: Any) -> Optional[Snapshot]:
        """Fetch snapshot by ID integer or snapshot_tag."""
        with self._get_connection() as conn:
            if isinstance(identifier, int) or (isinstance(identifier, str) and identifier.isdigit()):
                row = conn.execute(
                    "SELECT * FROM snapshots WHERE project_id = ? AND id = ?",
                    (project_id, int(identifier)),
                ).fetchone()
            else:
                row = conn.execute(
                    "SELECT * FROM snapshots WHERE project_id = ? AND snapshot_tag = ?",
                    (project_id, str(identifier)),
                ).fetchone()

            if not row:
                return None
            return Snapshot(
                id=row["id"],
                project_id=row["project_id"],
                snapshot_tag=row["snapshot_tag"],
                message=row["message"],
                created_at=row["created_at"],
                total_files=row["total_files"],
                total_bytes=row["total_bytes"],
                files_added=row["files_added"],
                files_modified=row["files_modified"],
                files_deleted=row["files_deleted"],
            )

    def get_latest_snapshot(self, project_id: int) -> Optional[Snapshot]:
        with self._get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM snapshots WHERE project_id = ? ORDER BY id DESC LIMIT 1",
                (project_id,),
            ).fetchone()
            if not row:
                return None
            return Snapshot(
                id=row["id"],
                project_id=row["project_id"],
                snapshot_tag=row["snapshot_tag"],
                message=row["message"],
                created_at=row["created_at"],
                total_files=row["total_files"],
                total_bytes=row["total_bytes"],
                files_added=row["files_added"],
                files_modified=row["files_modified"],
                files_deleted=row["files_deleted"],
            )

    def list_snapshots(self, project_id: int, limit: int = 50) -> List[Snapshot]:
        with self._get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM snapshots WHERE project_id = ? ORDER BY id DESC LIMIT ?",
                (project_id, limit),
            ).fetchall()
            return [
                Snapshot(
                    id=row["id"],
                    project_id=row["project_id"],
                    snapshot_tag=row["snapshot_tag"],
                    message=row["message"],
                    created_at=row["created_at"],
                    total_files=row["total_files"],
                    total_bytes=row["total_bytes"],
                    files_added=row["files_added"],
                    files_modified=row["files_modified"],
                    files_deleted=row["files_deleted"],
                )
                for row in rows
            ]

    # File Revision operations
    def record_file_revisions(self, revisions: List[Dict[str, Any]]) -> None:
        if not revisions:
            return
        with self._get_connection() as conn:
            conn.executemany(
                """
                INSERT INTO file_revisions (
                    snapshot_id, project_id, rel_path, sha256,
                    file_size, mtime, change_type, lines_added, lines_deleted, diff_unified
                ) VALUES (
                    :snapshot_id, :project_id, :rel_path, :sha256,
                    :file_size, :mtime, :change_type, :lines_added, :lines_deleted, :diff_unified
                )
                """,
                revisions,
            )

    def get_snapshot_revisions(self, snapshot_id: int, active_only: bool = True) -> Dict[str, FileRevision]:
        """
        Get map of rel_path -> FileRevision for a snapshot.
        If active_only=True, excludes files with change_type='deleted'.
        """
        query = "SELECT * FROM file_revisions WHERE snapshot_id = ?"
        if active_only:
            query += " AND change_type != 'deleted'"

        with self._get_connection() as conn:
            rows = conn.execute(query, (snapshot_id,)).fetchall()
            return {
                r["rel_path"]: FileRevision(
                    id=r["id"],
                    snapshot_id=r["snapshot_id"],
                    project_id=r["project_id"],
                    rel_path=r["rel_path"],
                    sha256=r["sha256"],
                    file_size=r["file_size"],
                    mtime=r["mtime"],
                    change_type=r["change_type"],
                    lines_added=r["lines_added"],
                    lines_deleted=r["lines_deleted"],
                    diff_unified=r["diff_unified"],
                )
                for r in rows
            }

    def get_file_history(self, project_id: int, rel_path: str) -> List[Tuple[Snapshot, FileRevision]]:
        """Fetch all revisions of a file along with their snapshots in chronological order."""
        with self._get_connection() as conn:
            rows = conn.execute(
                """
                SELECT 
                    s.id as s_id, s.project_id as s_proj_id, s.snapshot_tag, s.message, s.created_at as s_created_at,
                    s.total_files, s.total_bytes, s.files_added, s.files_modified, s.files_deleted,
                    r.id as r_id, r.snapshot_id, r.project_id as r_proj_id, r.rel_path, r.sha256,
                    r.file_size, r.mtime, r.change_type, r.lines_added, r.lines_deleted, r.diff_unified
                FROM file_revisions r
                JOIN snapshots s ON r.snapshot_id = s.id
                WHERE r.project_id = ? AND r.rel_path = ?
                ORDER BY s.id ASC
                """,
                (project_id, rel_path),
            ).fetchall()

            results = []
            for r in rows:
                snap = Snapshot(
                    id=r["s_id"],
                    project_id=r["s_proj_id"],
                    snapshot_tag=r["snapshot_tag"],
                    message=r["message"],
                    created_at=r["s_created_at"],
                    total_files=r["total_files"],
                    total_bytes=r["total_bytes"],
                    files_added=r["files_added"],
                    files_modified=r["files_modified"],
                    files_deleted=r["files_deleted"],
                )
                rev = FileRevision(
                    id=r["r_id"],
                    snapshot_id=r["snapshot_id"],
                    project_id=r["r_proj_id"],
                    rel_path=r["rel_path"],
                    sha256=r["sha256"],
                    file_size=r["file_size"],
                    mtime=r["mtime"],
                    change_type=r["change_type"],
                    lines_added=r["lines_added"],
                    lines_deleted=r["lines_deleted"],
                    diff_unified=r["diff_unified"],
                )
                results.append((snap, rev))
            return results

    def get_file_revision_in_snapshot(self, snapshot_id: int, rel_path: str) -> Optional[FileRevision]:
        with self._get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM file_revisions WHERE snapshot_id = ? AND rel_path = ?",
                (snapshot_id, rel_path),
            ).fetchone()
            if not row:
                return None
            return FileRevision(
                id=row["id"],
                snapshot_id=row["snapshot_id"],
                project_id=row["project_id"],
                rel_path=row["rel_path"],
                sha256=row["sha256"],
                file_size=row["file_size"],
                mtime=row["mtime"],
                change_type=row["change_type"],
                lines_added=row["lines_added"],
                lines_deleted=row["lines_deleted"],
                diff_unified=row["diff_unified"],
            )
