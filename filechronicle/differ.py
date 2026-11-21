"""Line diff computation and unified diff generation."""

import difflib
from typing import Tuple, List, Optional
from .models import DiffResult
from .hasher import is_binary_content


def decode_content(raw_bytes: bytes) -> Optional[str]:
    """Attempt decoding content as UTF-8 with fallback to latin-1."""
    if is_binary_content(raw_bytes):
        return None
    try:
        return raw_bytes.decode("utf-8")
    except UnicodeDecodeError:
        try:
            return raw_bytes.decode("latin-1")
        except UnicodeDecodeError:
            return None


def compute_unified_diff(
    rel_path: str,
    old_bytes: Optional[bytes],
    new_bytes: Optional[bytes],
    old_label: str = "previous",
    new_label: str = "current",
) -> DiffResult:
    """
    Compute unified diff between two byte buffers.
    Handles text, added files, deleted files, and binary files.
    """
    # Case 1: Identical content
    if old_bytes == new_bytes:
        return DiffResult(
            rel_path=rel_path,
            change_type="unchanged",
            old_sha256=None,
            new_sha256=None,
            lines_added=0,
            lines_deleted=0,
            diff_text="",
            is_binary=False,
        )

    # Check for binary
    old_is_bin = is_binary_content(old_bytes) if old_bytes else False
    new_is_bin = is_binary_content(new_bytes) if new_bytes else False
    if old_is_bin or new_is_bin:
        change_type = "added" if old_bytes is None else ("deleted" if new_bytes is None else "modified")
        return DiffResult(
            rel_path=rel_path,
            change_type=change_type,
            old_sha256=None,
            new_sha256=None,
            lines_added=0,
            lines_deleted=0,
            diff_text=f"Binary files {rel_path} ({old_label} vs {new_label}) differ\n",
            is_binary=True,
        )

    # Decode text
    old_text = decode_content(old_bytes) if old_bytes is not None else ""
    new_text = decode_content(new_bytes) if new_bytes is not None else ""

    if old_text is None or new_text is None:
        change_type = "added" if old_bytes is None else ("deleted" if new_bytes is None else "modified")
        return DiffResult(
            rel_path=rel_path,
            change_type=change_type,
            old_sha256=None,
            new_sha256=None,
            lines_added=0,
            lines_deleted=0,
            diff_text=f"Binary or non-decodable files {rel_path} differ\n",
            is_binary=True,
        )

    old_lines = old_text.splitlines(keepends=True) if old_bytes is not None else []
    new_lines = new_text.splitlines(keepends=True) if new_bytes is not None else []

    if old_bytes is None:
        change_type = "added"
        fromfile = "/dev/null"
    else:
        fromfile = f"a/{rel_path}"

    if new_bytes is None:
        change_type = "deleted"
        tofile = "/dev/null"
    else:
        tofile = f"b/{rel_path}"

    if old_bytes is not None and new_bytes is not None:
        change_type = "modified"

    diff_generator = difflib.unified_diff(
        old_lines,
        new_lines,
        fromfile=f"{fromfile} ({old_label})",
        tofile=f"{tofile} ({new_label})",
    )
    diff_lines = list(diff_generator)
    diff_text = "".join(diff_lines)

    # Count added and deleted lines
    lines_added = 0
    lines_deleted = 0
    for line in diff_lines:
        if line.startswith("+") and not line.startswith("+++"):
            lines_added += 1
        elif line.startswith("-") and not line.startswith("---"):
            lines_deleted += 1

    return DiffResult(
        rel_path=rel_path,
        change_type=change_type,
        old_sha256=None,
        new_sha256=None,
        lines_added=lines_added,
        lines_deleted=lines_deleted,
        diff_text=diff_text,
        is_binary=False,
    )
