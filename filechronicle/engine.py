"""Core differential snapshot engine for FileChronicle."""

import fnmatch
import os
import shutil
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any

from .config import get_db_path, DEFAULT_IGNORE_PATTERNS
from .db import ChronicleDB
from .differ import compute_unified_diff
from .hasher import hash_file, hash_bytes, is_binary_file
from .models import Project, Snapshot, FileRevision, FileStatus, DiffResult
from .storage import prepare_blob


class ChronicleEngine:
    """Manages tracking, differential snapshots, diffs, history, and restoration."""

    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or get_db_path()
        self.db = ChronicleDB(self.db_path)

    def init_project(self, target_path: Optional[str] = None, name: Optional[str] = None) -> Tuple[Project, bool]:
        """
        Initialize directory tracking.
        Returns:
            (Project, is_newly_created)
        """
        resolved_path = Path(target_path or os.getcwd()).resolve()
        if not resolved_path.exists():
            resolved_path.mkdir(parents=True, exist_ok=True)

        existing = self.db.find_project_for_path(str(resolved_path))
        is_new = False
        if not existing or Path(existing.root_path).resolve() != resolved_path:
            is_new = True
            project = self.db.get_or_create_project(
                root_path=str(resolved_path),
                name=name or resolved_path.name,
                ignore_patterns=DEFAULT_IGNORE_PATTERNS,
            )
        else:
            project = existing

        # Ensure a default .chronicleignore exists if not present
        ignore_file = resolved_path / ".chronicleignore"
        if not ignore_file.exists():
            with open(ignore_file, "w", encoding="utf-8") as f:
                f.write("# FileChronicle ignore rules\n")
                f.write(".git/\n")
                f.write(".filechronicle/\n")
                f.write("__pycache__/\n")
                f.write("*.pyc\n")
                f.write("node_modules/\n")
                f.write(".venv/\n")
                f.write("*.bak\n")
                f.write("*.tmp\n")

        return project, is_new

    def get_project(self, target_path: Optional[str] = None) -> Project:
        """Resolve project for target path or cwd. Raises ValueError if not tracked."""
        resolved = str(Path(target_path or os.getcwd()).resolve())
        project = self.db.find_project_for_path(resolved)
        if not project:
            raise ValueError(
                f"Directory '{resolved}' is not tracked by FileChronicle. "
                f"Run 'chronicle init' first to begin tracking."
            )
        return project

    def load_ignore_patterns(self, project: Project) -> List[str]:
        """Aggregate ignore patterns from project settings and .chronicleignore."""
        patterns = list(project.ignore_patterns or DEFAULT_IGNORE_PATTERNS)
        root = Path(project.root_path)
        ignore_file = root / ".chronicleignore"
        if ignore_file.exists():
            try:
                with open(ignore_file, "r", encoding="utf-8", errors="ignore") as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith("#"):
                            patterns.append(line)
            except OSError:
                pass
        return patterns

    def is_ignored(self, rel_path: str, is_dir: bool, patterns: List[str]) -> bool:
        """Check if relative path or directory matches any ignore pattern."""
        # Normalize to forward slashes
        norm_path = rel_path.replace("\\", "/")
        basename = os.path.basename(norm_path)

        for pat in patterns:
            pat = pat.replace("\\", "/")
            # Directory specific pattern
            if pat.endswith("/"):
                dir_pat = pat.rstrip("/")
                if is_dir and (fnmatch.fnmatch(norm_path, dir_pat) or fnmatch.fnmatch(basename, dir_pat)):
                    return True
                if norm_path.startswith(dir_pat + "/") or f"/{dir_pat}/" in f"/{norm_path}/":
                    return True
            else:
                if fnmatch.fnmatch(norm_path, pat) or fnmatch.fnmatch(basename, pat):
                    return True
                # Match subdirectory components
                if fnmatch.fnmatch(norm_path, f"*/{pat}") or fnmatch.fnmatch(norm_path, f"{pat}/*"):
                    return True
        return False

    def scan_directory(self, project: Project) -> Dict[str, Dict[str, Any]]:
        """
        Scan all non-ignored files under project root.
        Returns:
            dict of rel_path -> {
                'abs_path': Path,
                'sha256': str,
                'file_size': int,
                'mtime': float,
                'is_binary': bool
            }
        """
        root = Path(project.root_path)
        patterns = self.load_ignore_patterns(project)
        scanned_files: Dict[str, Dict[str, Any]] = {}

        for dirpath, dirnames, filenames in os.walk(root):
            # Compute relative dirpath
            rel_dir = os.path.relpath(dirpath, root)
            if rel_dir == ".":
                rel_dir = ""

            # Filter dirnames in-place to prevent traversing ignored directories
            filtered_dirs = []
            for d in dirnames:
                dir_rel = os.path.join(rel_dir, d).replace("\\", "/")
                if not self.is_ignored(dir_rel, is_dir=True, patterns=patterns):
                    filtered_dirs.append(d)
            dirnames[:] = filtered_dirs

            for fname in filenames:
                file_rel = os.path.join(rel_dir, fname).replace("\\", "/")
                if self.is_ignored(file_rel, is_dir=False, patterns=patterns):
                    continue

                abs_file = Path(dirpath) / fname
                try:
                    stat = abs_file.stat()
                    sha256, file_size, is_bin = hash_file(abs_file)
                    scanned_files[file_rel] = {
                        "abs_path": abs_file,
                        "sha256": sha256,
                        "file_size": file_size,
                        "mtime": stat.st_mtime,
                        "is_binary": is_bin,
                    }
                except (OSError, PermissionError):
                    continue

        return scanned_files

    def status(self, project: Optional[Project] = None, target_path: Optional[str] = None) -> List[FileStatus]:
        """
        Compute status of working directory compared to the latest snapshot.
        """
        proj = project or self.get_project(target_path)
        latest_snap = self.db.get_latest_snapshot(proj.id)
        current_files = self.scan_directory(proj)

        prev_revisions = {}
        if latest_snap:
            prev_revisions = self.db.get_snapshot_revisions(latest_snap.id, active_only=True)

        results: List[FileStatus] = []
        all_paths = set(current_files.keys()).union(set(prev_revisions.keys()))

        for rel_path in sorted(all_paths):
            on_disk = current_files.get(rel_path)
            in_snap = prev_revisions.get(rel_path)

            if on_disk and not in_snap:
                results.append(
                    FileStatus(
                        rel_path=rel_path,
                        status="untracked",
                        file_size=on_disk["file_size"],
                        mtime=on_disk["mtime"],
                        sha256=on_disk["sha256"],
                        old_sha256=None,
                    )
                )
            elif in_snap and not on_disk:
                results.append(
                    FileStatus(
                        rel_path=rel_path,
                        status="deleted",
                        file_size=0,
                        mtime=0.0,
                        sha256=None,
                        old_sha256=in_snap.sha256,
                    )
                )
            elif on_disk and in_snap:
                if on_disk["sha256"] != in_snap.sha256:
                    results.append(
                        FileStatus(
                            rel_path=rel_path,
                            status="modified",
                            file_size=on_disk["file_size"],
                            mtime=on_disk["mtime"],
                            sha256=on_disk["sha256"],
                            old_sha256=in_snap.sha256,
                        )
                    )
                else:
                    results.append(
                        FileStatus(
                            rel_path=rel_path,
                            status="clean",
                            file_size=on_disk["file_size"],
                            mtime=on_disk["mtime"],
                            sha256=on_disk["sha256"],
                            old_sha256=in_snap.sha256,
                        )
                    )

        return results

    def create_snapshot(
        self,
        project: Optional[Project] = None,
        target_path: Optional[str] = None,
        message: str = "",
        tag: Optional[str] = None,
    ) -> Tuple[Snapshot, Dict[str, Any]]:
        """
        Capture a full differential snapshot of the project directory.
        Returns:
            (Snapshot, summary_dict)
        """
        proj = project or self.get_project(target_path)
        current_files = self.scan_directory(proj)
        latest_snap = self.db.get_latest_snapshot(proj.id)

        prev_revisions: Dict[str, FileRevision] = {}
        if latest_snap:
            prev_revisions = self.db.get_snapshot_revisions(latest_snap.id, active_only=True)

        # Generate tag if not provided
        now_dt = datetime.now()
        snap_tag = tag or f"snap-{now_dt.strftime('%Y%m%d-%H%M%S')}"
        snap_msg = message or f"Snapshot at {now_dt.strftime('%Y-%m-%d %H:%M:%S')}"

        files_added = 0
        files_modified = 0
        files_deleted = 0
        total_bytes = 0
        total_files = len(current_files)

        revisions_to_record: List[Dict[str, Any]] = []

        # Process all files currently on disk
        for rel_path, file_meta in current_files.items():
            total_bytes += file_meta["file_size"]
            abs_path = file_meta["abs_path"]
            curr_sha = file_meta["sha256"]
            curr_size = file_meta["file_size"]
            curr_mtime = file_meta["mtime"]
            curr_is_bin = file_meta["is_binary"]

            # Read file bytes for blob storage if not present
            with open(abs_path, "rb") as f:
                content_bytes = f.read()

            if not self.db.has_blob(curr_sha):
                sha, size, is_bin, compressed = prepare_blob(content_bytes)
                self.db.store_blob(sha, size, is_bin, compressed)

            prev_rev = prev_revisions.get(rel_path)

            if prev_rev is None:
                # Newly added file
                files_added += 1
                diff_res = compute_unified_diff(
                    rel_path=rel_path,
                    old_bytes=None,
                    new_bytes=content_bytes,
                    old_label="/dev/null",
                    new_label=f"snapshot:{snap_tag}",
                )
                revisions_to_record.append({
                    "project_id": proj.id,
                    "rel_path": rel_path,
                    "sha256": curr_sha,
                    "file_size": curr_size,
                    "mtime": curr_mtime,
                    "change_type": "added",
                    "lines_added": diff_res.lines_added,
                    "lines_deleted": diff_res.lines_deleted,
                    "diff_unified": diff_res.diff_text,
                })
            elif prev_rev.sha256 != curr_sha:
                # Modified file
                files_modified += 1
                old_blob = self.db.get_blob(prev_rev.sha256)
                old_bytes = old_blob.content if old_blob else None

                diff_res = compute_unified_diff(
                    rel_path=rel_path,
                    old_bytes=old_bytes,
                    new_bytes=content_bytes,
                    old_label=f"snapshot:{latest_snap.snapshot_tag}",
                    new_label=f"snapshot:{snap_tag}",
                )
                revisions_to_record.append({
                    "project_id": proj.id,
                    "rel_path": rel_path,
                    "sha256": curr_sha,
                    "file_size": curr_size,
                    "mtime": curr_mtime,
                    "change_type": "modified",
                    "lines_added": diff_res.lines_added,
                    "lines_deleted": diff_res.lines_deleted,
                    "diff_unified": diff_res.diff_text,
                })
            else:
                # Unchanged file
                revisions_to_record.append({
                    "project_id": proj.id,
                    "rel_path": rel_path,
                    "sha256": curr_sha,
                    "file_size": curr_size,
                    "mtime": curr_mtime,
                    "change_type": "unchanged",
                    "lines_added": 0,
                    "lines_deleted": 0,
                    "diff_unified": None,
                })

        # Process deleted files (in previous snapshot, but absent on disk)
        for rel_path, prev_rev in prev_revisions.items():
            if rel_path not in current_files:
                files_deleted += 1
                old_blob = self.db.get_blob(prev_rev.sha256)
                old_bytes = old_blob.content if old_blob else None

                diff_res = compute_unified_diff(
                    rel_path=rel_path,
                    old_bytes=old_bytes,
                    new_bytes=None,
                    old_label=f"snapshot:{latest_snap.snapshot_tag}",
                    new_label="/dev/null",
                )
                revisions_to_record.append({
                    "project_id": proj.id,
                    "rel_path": rel_path,
                    "sha256": prev_rev.sha256,
                    "file_size": 0,
                    "mtime": 0.0,
                    "change_type": "deleted",
                    "lines_added": diff_res.lines_added,
                    "lines_deleted": diff_res.lines_deleted,
                    "diff_unified": diff_res.diff_text,
                })

        # Insert snapshot
        snapshot = self.db.create_snapshot(
            project_id=proj.id,
            snapshot_tag=snap_tag,
            message=snap_msg,
            total_files=total_files,
            total_bytes=total_bytes,
            files_added=files_added,
            files_modified=files_modified,
            files_deleted=files_deleted,
        )

        # Set snapshot_id on revisions and batch insert
        for rev in revisions_to_record:
            rev["snapshot_id"] = snapshot.id

        self.db.record_file_revisions(revisions_to_record)

        summary = {
            "snapshot_id": snapshot.id,
            "snapshot_tag": snapshot.snapshot_tag,
            "total_files": total_files,
            "total_bytes": total_bytes,
            "files_added": files_added,
            "files_modified": files_modified,
            "files_deleted": files_deleted,
            "message": snap_msg,
        }
        return snapshot, summary

    def diff_snapshots(
        self,
        snap_id_1: Any,
        snap_id_2: Any,
        target_path: Optional[str] = None,
        file_filter: Optional[str] = None,
    ) -> List[DiffResult]:
        """
        Compute unified diffs of changed files between two snapshots.
        """
        project = self.get_project(target_path)
        snap1 = self.db.get_snapshot(project.id, snap_id_1)
        snap2 = self.db.get_snapshot(project.id, snap_id_2)

        if not snap1:
            raise ValueError(f"Snapshot '{snap_id_1}' not found in project '{project.name}'.")
        if not snap2:
            raise ValueError(f"Snapshot '{snap_id_2}' not found in project '{project.name}'.")

        revs1 = self.db.get_snapshot_revisions(snap1.id, active_only=True)
        revs2 = self.db.get_snapshot_revisions(snap2.id, active_only=True)

        all_paths = set(revs1.keys()).union(set(revs2.keys()))
        if file_filter:
            norm_filter = file_filter.replace("\\", "/")
            all_paths = {p for p in all_paths if p == norm_filter or fnmatch.fnmatch(p, norm_filter)}

        diff_results: List[DiffResult] = []

        for rel_path in sorted(all_paths):
            r1 = revs1.get(rel_path)
            r2 = revs2.get(rel_path)

            old_bytes = None
            new_bytes = None
            old_sha = None
            new_sha = None

            if r1:
                old_sha = r1.sha256
                old_blob = self.db.get_blob(r1.sha256)
                old_bytes = old_blob.content if old_blob else None

            if r2:
                new_sha = r2.sha256
                new_blob = self.db.get_blob(r2.sha256)
                new_bytes = new_blob.content if new_blob else None

            if old_sha == new_sha:
                continue

            diff_res = compute_unified_diff(
                rel_path=rel_path,
                old_bytes=old_bytes,
                new_bytes=new_bytes,
                old_label=f"snapshot:{snap1.snapshot_tag}",
                new_label=f"snapshot:{snap2.snapshot_tag}",
            )
            diff_res.old_sha256 = old_sha
            diff_res.new_sha256 = new_sha
            diff_results.append(diff_res)

        return diff_results

    def file_history(self, rel_path: str, target_path: Optional[str] = None) -> List[Tuple[Snapshot, FileRevision]]:
        """
        Get all revisions of a file across snapshots.
        """
        project = self.get_project(target_path)
        norm_path = rel_path.replace("\\", "/")
        # Strip leading ./ or /
        norm_path = norm_path.lstrip("./").lstrip("/")
        return self.db.get_file_history(project.id, norm_path)

    def restore_file(
        self,
        rel_path: str,
        snapshot_id: Any,
        target_path: Optional[str] = None,
        output_path: Optional[str] = None,
        force: bool = False,
        backup: bool = True,
    ) -> Path:
        """
        Restore a file's state from a specific snapshot.
        """
        project = self.get_project(target_path)
        snap = self.db.get_snapshot(project.id, snapshot_id)
        if not snap:
            raise ValueError(f"Snapshot '{snapshot_id}' not found.")

        norm_rel = rel_path.replace("\\", "/").lstrip("./").lstrip("/")
        revision = self.db.get_file_revision_in_snapshot(snap.id, norm_rel)

        if not revision:
            raise ValueError(f"File '{norm_rel}' does not exist in snapshot '{snap.snapshot_tag}' (ID: {snap.id}).")

        if revision.change_type == "deleted":
            raise ValueError(f"File '{norm_rel}' was marked as deleted in snapshot '{snap.snapshot_tag}'.")

        blob = self.db.get_blob(revision.sha256)
        if not blob or blob.content is None:
            raise ValueError(f"Corrupted storage: Blob data for SHA '{revision.sha256}' is missing.")

        # Determine target file location
        if output_path:
            dest_file = Path(output_path).resolve()
        else:
            dest_file = (Path(project.root_path) / norm_rel).resolve()

        # Safety checks if file exists
        if dest_file.exists() and not force:
            # Check if destination file has changes
            curr_sha, _, _ = hash_file(dest_file)
            if curr_sha != revision.sha256:
                if backup:
                    bak_path = dest_file.with_suffix(dest_file.suffix + ".bak")
                    shutil.copy2(dest_file, bak_path)

        dest_file.parent.mkdir(parents=True, exist_ok=True)
        with open(dest_file, "wb") as f:
            f.write(blob.content)

        return dest_file

    def get_file_content(self, rel_path: str, snapshot_id: Any, target_path: Optional[str] = None) -> bytes:
        """Fetch raw file bytes from a specific snapshot."""
        project = self.get_project(target_path)
        snap = self.db.get_snapshot(project.id, snapshot_id)
        if not snap:
            raise ValueError(f"Snapshot '{snapshot_id}' not found.")

        norm_rel = rel_path.replace("\\", "/").lstrip("./").lstrip("/")
        revision = self.db.get_file_revision_in_snapshot(snap.id, norm_rel)
        if not revision:
            raise ValueError(f"File '{norm_rel}' was not recorded in snapshot '{snap.snapshot_tag}'.")

        blob = self.db.get_blob(revision.sha256)
        if not blob or blob.content is None:
            raise ValueError(f"Blob not found for hash {revision.sha256}")

        return blob.content
