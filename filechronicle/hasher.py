"""Fast SHA-256 hashing and binary detection."""

import hashlib
from pathlib import Path
from typing import Tuple, Union


CHUNK_SIZE = 64 * 1024  # 64 KB chunks
BINARY_DETECTION_BYTES = 8192  # Check first 8KB for null bytes
# ASCII control chars 0-31 excluding \t (9), \n (10), \r (13)
CONTROL_CHARS = set(range(0, 32)) - {9, 10, 13}


def is_binary_content(data: bytes) -> bool:
    """Check if byte buffer contains null bytes or unprintable control sequences."""
    if not data:
        return False
    sample = data[:BINARY_DETECTION_BYTES]
    if b"\x00" in sample:
        return True
    # Count non-text control characters
    non_text = sum(b in CONTROL_CHARS for b in sample)
    return (non_text / len(sample)) > 0.30 if sample else False


def is_binary_file(file_path: Union[str, Path]) -> bool:
    """Determine whether a file is binary by inspecting its leading bytes."""
    try:
        with open(file_path, "rb") as f:
            chunk = f.read(BINARY_DETECTION_BYTES)
            return is_binary_content(chunk)
    except (OSError, IOError):
        return False


def hash_bytes(data: bytes) -> str:
    """Compute SHA-256 hexadecimal digest for raw bytes."""
    return hashlib.sha256(data).hexdigest()


def hash_file(file_path: Union[str, Path]) -> Tuple[str, int, bool]:
    """
    Compute SHA-256 hash, file size in bytes, and binary status.
    Streams in 64KB chunks for memory efficiency.
    Returns:
        (sha256_hex, file_size, is_binary)
    """
    hasher = hashlib.sha256()
    total_size = 0
    first_chunk = True
    binary = False

    with open(file_path, "rb") as f:
        while True:
            chunk = f.read(CHUNK_SIZE)
            if not chunk:
                break
            if first_chunk:
                binary = is_binary_content(chunk)
                first_chunk = False
            hasher.update(chunk)
            total_size += len(chunk)

    return hasher.hexdigest(), total_size, binary
