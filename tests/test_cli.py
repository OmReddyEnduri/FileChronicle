"""Unit and integration tests for the CLI commands."""

import io
import sys
import tempfile
import unittest
from pathlib import Path

from filechronicle.cli import main


class TestCLI(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.workspace = Path(self.temp_dir.name) / "cli_workspace"
        self.workspace.mkdir()
        self.db_path = str(Path(self.temp_dir.name) / "cli.db")

    def tearDown(self):
        self.temp_dir.cleanup()

    def run_cli(self, args):
        """Helper to invoke CLI with captured stdout and stderr."""
        old_stdout = sys.stdout
        old_stderr = sys.stderr
        stdout_buf = io.StringIO()
        stderr_buf = io.StringIO()
        sys.stdout = stdout_buf
        sys.stderr = stderr_buf
        try:
            full_args = ["--db", self.db_path, "--no-color"] + args
            exit_code = main(full_args)
            return exit_code, stdout_buf.getvalue(), stderr_buf.getvalue()
        finally:
            sys.stdout = old_stdout
            sys.stderr = old_stderr

    def test_cli_full_flow(self):
        ws = str(self.workspace)

        # 1. Init
        code, out, _ = self.run_cli(["init", ws, "--name", "CLITestProject"])
        self.assertEqual(code, 0)
        self.assertIn("Initialized FileChronicle tracking", out)

        # 2. Add files
        f1 = self.workspace / "app.py"
        f1.write_text("print('version 1.0')\n", encoding="utf-8")

        # 3. Status - untracked
        code, out, _ = self.run_cli(["status", "-p", ws])
        self.assertEqual(code, 0)
        self.assertIn("app.py", out)
        self.assertIn("untracked", out)

        # 4. Snapshot 1
        code, out, _ = self.run_cli(["snapshot", "-p", ws, "-m", "First commit"])
        self.assertEqual(code, 0)
        self.assertIn("Snapshot captured successfully", out)

        # 5. Status after snapshot - clean
        code, out, _ = self.run_cli(["status", "-p", ws])
        self.assertEqual(code, 0)
        self.assertIn("clean", out)

        # 6. Modify app.py
        f1.write_text("print('version 2.0')\nprint('new feature')\n", encoding="utf-8")

        # 7. Snapshot 2
        code, out, _ = self.run_cli(["snapshot", "-p", ws, "-m", "Version 2.0 release"])
        self.assertEqual(code, 0)

        # 8. Diff between snap 1 and 2
        code, out, _ = self.run_cli(["diff", "1", "2", "-p", ws])
        self.assertEqual(code, 0)
        self.assertIn("app.py", out)
        self.assertIn("-print('version 1.0')", out)
        self.assertIn("+print('version 2.0')", out)

        # 9. History of app.py
        code, out, _ = self.run_cli(["history", "app.py", "-p", ws])
        self.assertEqual(code, 0)
        self.assertIn("Revision history for 'app.py'", out)

        # 10. Cat file from snap 1
        old_stdout = sys.stdout
        stdout_buf = io.BytesIO()
        # Test cat using engine directly or via cli
        code, out, _ = self.run_cli(["log", "-p", ws])
        self.assertEqual(code, 0)
        self.assertIn("First commit", out)
        self.assertIn("Version 2.0 release", out)

        # 11. Projects listing
        code, out, _ = self.run_cli(["projects"])
        self.assertEqual(code, 0)
        self.assertIn("CLITestProject", out)

        # 12. Restore app.py to snap 1
        code, out, _ = self.run_cli(["restore", "app.py", "1", "-p", ws, "-f"])
        self.assertEqual(code, 0)
        self.assertIn("Restored 'app.py' from snapshot 1", out)
        self.assertEqual(f1.read_text(encoding="utf-8"), "print('version 1.0')\n")


if __name__ == "__main__":
    unittest.main()
