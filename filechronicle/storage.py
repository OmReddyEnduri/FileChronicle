"""Content-addressable compressed blob storage."""

import zlib
from typing import Optional, Tuple
from .hasher import hash_bytes, is_binary_content


def compress_content(data: bytes) -> bytes:
    """Compress bytes using zlib at level 6."""
    return zlib.compress(data, level=6)


def decompress_content(compressed_data: bytes) -> bytes:
    """Decompress zlib-compressed bytes."""
    return zlib.decompress(compressed_data)


def prepare_blob(data: bytes) -> Tuple[str, int, bool, bytes]:
    """
    Prepare a blob for database storage.
    Returns:
        (sha256, uncompressed_size, is_binary, compressed_data)
    """
    sha = hash_bytes(data)
    size = len(data)
    is_bin = is_binary_content(data)
    compressed = compress_content(data)
    return sha, size, is_bin, compressed
