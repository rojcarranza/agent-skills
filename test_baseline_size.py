"""Tests for tools/baseline_size.py, the 1,000-line limit per code file
(issue #139): a code file over 1,000 lines fails the gate unless
.baseline-long-files lists it, and a listed file may shrink but never grow.

  python3 -m unittest test_baseline_size -v
"""
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent / "tools" / "baseline_size.py"
LIST_HEADER = (
    "# Code files over the size limit when this list was written: path, tab, lines.\n"
    "# A listed file may shrink but not grow. Remove a line when its file is under the limit.\n"
)


def python_source(lines):
    return "".join("setting_%d = %d\n" % (n, n) for n in range(lines))


@unittest.skipUnless(shutil.which("git"), "needs git")
class TestSizeCheck(unittest.TestCase):
    """Runs the check as the gate does, on a fresh git working copy."""

    def setUp(self):
        self.project = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.project, ignore_errors=True)
        subprocess.run(["git", "init", "-q", str(self.project)], check=True)

    def write(self, rel, text):
        path = self.project / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, "utf-8")

    def check(self):
        run = subprocess.run([sys.executable, str(SCRIPT), str(self.project)],
                             capture_output=True, text=True)
        return run.returncode, run.stdout.splitlines()

    def test_new_code_file_over_the_limit_fails(self):
        self.write("tools/report.py", python_source(1001))
        self.assertEqual(self.check(), (1, [
            "fail: tools/report.py has 1001 lines and is not on the list",
            "size: 1 files over 1000 lines, 1 problems",
            "next: split the file; listed files may shrink but never grow",
        ]))

    def test_code_file_at_the_limit_passes(self):
        self.write("tools/report.py", python_source(1000))
        self.assertEqual(self.check(), (0, ["size: 0 files over 1000 lines, 0 problems"]))

    def test_listed_file_at_its_count_passes(self):
        self.write(".baseline-long-files", LIST_HEADER + "install.py\t1200\n")
        self.write("install.py", python_source(1200))
        self.assertEqual(self.check(), (0, ["size: 1 files over 1000 lines, 0 problems"]))

    def test_listed_file_that_grows_fails(self):
        self.write(".baseline-long-files", LIST_HEADER + "install.py\t1200\n")
        self.write("install.py", python_source(1201))
        self.assertEqual(self.check(), (1, [
            "fail: install.py grew from 1200 to 1201 lines",
            "size: 1 files over 1000 lines, 1 problems",
            "next: split the file; listed files may shrink but never grow",
        ]))

    def test_listed_file_that_shrinks_passes_with_a_note(self):
        self.write(".baseline-long-files", LIST_HEADER + "install.py\t1200\n")
        self.write("install.py", python_source(1199))
        self.assertEqual(self.check(), (0, [
            "note: install.py shrank from 1200 to 1199 lines; update the list",
            "size: 1 files over 1000 lines, 0 problems",
        ]))

    def test_listed_file_under_the_limit_asks_to_leave_the_list(self):
        self.write(".baseline-long-files", LIST_HEADER + "install.py\t1200\n")
        self.write("install.py", python_source(900))
        self.assertEqual(self.check(), (0, [
            "note: install.py is under the limit or gone; remove it from the list",
            "size: 0 files over 1000 lines, 0 problems",
        ]))

    def test_only_project_written_code_counts(self):
        """Documents, dependencies, build output, bundles and ignored files
        are not code this project wrote."""
        long_source = python_source(1001)
        for rel in ("docs/guide.md", "node_modules/left-pad/index.js", "dist/app.js",
                    "web/app.min.js", "generated/schema.py"):
            self.write(rel, long_source)
        self.write(".gitignore", "generated/\n")
        self.assertEqual(self.check(), (0, ["size: 0 files over 1000 lines, 0 problems"]))


if __name__ == "__main__":
    unittest.main()
