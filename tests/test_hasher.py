"""Unit tests for SHA-256 hashing and binary detection."""

import os
import tempfile
import unittest
from pathlib import Path

from filechronicle.hasher import (
    hash_bytes,
    hash_file,
    is_binary_content,
    is_binary_file,
)


class TestHasher(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.dir_path = Path(self.temp_dir.name)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_hash_bytes(self):
        # Empty string SHA-256
        empty_hash = hash_bytes(b"")
        self.assertEqual(
            empty_hash,
            "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        )

        hello_hash = hash_bytes(b"hello world\n")
        self.assertEqual(
            hello_hash,
            "a948904f2f0f479b8f8197694b30184b0d2ed1c1cd2a1ec0fb85d299a192a447",
        )

    def test_is_binary_content(self):
        self.assertFalse(is_binary_content(b""))
        self.assertFalse(is_binary_content(b"Hello world\nThis is regular text!"))
        self.assertTrue(is_binary_content(b"Hello\x00World"))
        # High concentration of non-printable control characters
        control_bytes = bytes([1, 2, 3, 4, 5] * 20)
        self.assertTrue(is_binary_content(control_bytes))

    def test_hash_file_text(self):
        sample_file = self.dir_path / "sample.txt"
        sample_file.write_text("Chronicle tracking test\nLine two\n", encoding="utf-8")

        sha256, size, is_bin = hash_file(sample_file)
        self.assertFalse(is_bin)
        self.assertGreater(size, 0)
        self.assertEqual(len(sha256), 64)

    def test_hash_file_binary(self):
        bin_file = self.dir_path / "binary.dat"
        bin_file.write_bytes(b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x01")

        sha256, size, is_bin = hash_file(bin_file)
        self.assertTrue(is_bin)
        self.assertTrue(is_binary_file(bin_file))
        self.assertEqual(size, 18)


if __name__ == "__main__":
    unittest.main()
