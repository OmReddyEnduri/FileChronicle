"""Unit tests for line diffing and unified diff computation."""

import unittest
from filechronicle.differ import compute_unified_diff, decode_content


class TestDiffer(unittest.TestCase):
    def test_decode_content(self):
        text = decode_content(b"Hello World")
        self.assertEqual(text, "Hello World")

        bin_result = decode_content(b"Hello\x00World")
        self.assertIsNone(bin_result)

    def test_identical_diff(self):
        content = b"Line 1\nLine 2\nLine 3\n"
        res = compute_unified_diff("test.txt", content, content)
        self.assertEqual(res.change_type, "unchanged")
        self.assertEqual(res.lines_added, 0)
        self.assertEqual(res.lines_deleted, 0)
        self.assertEqual(res.diff_text, "")

    def test_added_file_diff(self):
        new_content = b"Alpha\nBeta\nGamma\n"
        res = compute_unified_diff("new.txt", None, new_content)
        self.assertEqual(res.change_type, "added")
        self.assertEqual(res.lines_added, 3)
        self.assertEqual(res.lines_deleted, 0)
        self.assertIn("+Alpha", res.diff_text)
        self.assertIn("+Gamma", res.diff_text)

    def test_deleted_file_diff(self):
        old_content = b"Alpha\nBeta\n"
        res = compute_unified_diff("del.txt", old_content, None)
        self.assertEqual(res.change_type, "deleted")
        self.assertEqual(res.lines_added, 0)
        self.assertEqual(res.lines_deleted, 2)
        self.assertIn("-Alpha", res.diff_text)

    def test_modified_file_diff(self):
        old_content = b"Line A\nLine B\nLine C\n"
        new_content = b"Line A\nLine B modified\nLine C\nLine D\n"

        res = compute_unified_diff("mod.txt", old_content, new_content)
        self.assertEqual(res.change_type, "modified")
        self.assertEqual(res.lines_added, 2)
        self.assertEqual(res.lines_deleted, 1)
        self.assertIn("-Line B", res.diff_text)
        self.assertIn("+Line B modified", res.diff_text)
        self.assertIn("+Line D", res.diff_text)

    def test_binary_diff(self):
        old_bin = b"\x00\x01\x02"
        new_bin = b"\x00\x01\x03"

        res = compute_unified_diff("app.bin", old_bin, new_bin)
        self.assertTrue(res.is_binary)
        self.assertIn("Binary files", res.diff_text)


if __name__ == "__main__":
    unittest.main()
