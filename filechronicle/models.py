"""Data models and structures for FileChronicle."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List, Dict, Any


@dataclass
class Project:
    """Represents a tracked project or directory."""
    id: int
    name: str
    root_path: str
    created_at: str
    ignore_patterns: List[str] = field(default_factory=list)


@dataclass
class BlobRecord:
    """Represents a content-addressed data blob."""
    sha256: str
    size: int
    is_binary: bool
    content: Optional[bytes] = None


@dataclass
class Snapshot:
    """Represents a point-in-time snapshot of a project."""
    id: int
    project_id: int
    snapshot_tag: str
    message: str
    created_at: str
    total_files: int = 0
    total_bytes: int = 0
    files_added: int = 0
    files_modified: int = 0
    files_deleted: int = 0


@dataclass
class FileRevision:
    """Represents a file's state in a specific snapshot."""
    id: int
    snapshot_id: int
    project_id: int
    rel_path: str
    sha256: str
    file_size: int
    mtime: float
    change_type: str  # 'added', 'modified', 'unchanged', 'deleted'
    lines_added: int = 0
    lines_deleted: int = 0
    diff_unified: Optional[str] = None


@dataclass
class FileStatus:
    """Represents working directory status for a file relative to latest snapshot."""
    rel_path: str
    status: str  # 'untracked', 'modified', 'deleted', 'clean'
    file_size: int = 0
    mtime: float = 0.0
    sha256: Optional[str] = None
    old_sha256: Optional[str] = None
    lines_added: int = 0
    lines_deleted: int = 0


@dataclass
class DiffResult:
    """Unified diff output for a file between two points."""
    rel_path: str
    change_type: str
    old_sha256: Optional[str]
    new_sha256: Optional[str]
    lines_added: int
    lines_deleted: int
    diff_text: str
    is_binary: bool = False
