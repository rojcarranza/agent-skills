#!/usr/bin/env python3
"""The 1,000-line limit per code file: a standard-library copy of `baseline size`.

The gate also runs on computers without the baseline program, so this copy
keeps its meaning of a code file, its list format and its output lines. A
code file over the limit fails unless `.baseline-long-files` lists it; a
listed file may shrink but never grow.

  python3 tools/baseline_size.py [project]   # project defaults to this repository

Exit codes: 0 pass, 1 a new or grown file over the limit, 2 a usage error.
Python >= 3.8, standard library only.
"""
import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LIMIT = 1000
LIST_FILE = ".baseline-long-files"
CODE_EXTENSIONS = {
    ".swift", ".go", ".py", ".ts", ".tsx", ".js", ".jsx", ".mjs", ".sh", ".bash", ".nix",
    ".rs", ".kt", ".java", ".c", ".h", ".cc", ".cpp", ".m", ".rb",
}
# Dependency, build and bundle output never counts as project-written code.
SKIPPED_PARTS = {"node_modules", "vendor", "dist", "build", "Pods", ".build", "DerivedData", "third_party"}
SKIPPED_SUFFIXES = (".min.js", ".bundle.js", ".pb.go", ".generated.swift")


class UsageError(Exception):
    pass


def code_files(root):
    """Tracked files plus untracked files that are not ignored, that are code."""
    out = subprocess.run(
        ["git", "-C", str(root), "ls-files", "-z", "--cached", "--others", "--exclude-standard"],
        capture_output=True, text=True)
    if out.returncode != 0:
        raise UsageError("git ls-files failed: %s" % out.stderr.strip())
    names = sorted(set(n for n in out.stdout.split("\0") if n))
    return [n for n in names if (root / n).is_file() and is_code(n)]


def is_code(rel):
    if any(p in SKIPPED_PARTS for p in Path(rel).parts) or rel.endswith(SKIPPED_SUFFIXES):
        return False
    return Path(rel).suffix in CODE_EXTENSIONS


def line_count(path):
    with open(path, "rb") as handle:
        return sum(1 for _ in handle)


def read_list(root):
    path = root / LIST_FILE
    text = path.read_text(errors="replace") if path.is_file() else ""
    listed = {}
    for line in text.splitlines():
        if line.strip() and not line.startswith("#"):
            rel, _, count = line.rpartition("\t")
            if rel and count.strip().isdigit():
                listed[rel] = int(count)
    return listed


def measure(root):
    """Return (over, problems, notes): files over the limit, failures and shrink notes."""
    listed = read_list(root)
    over = {}
    for rel in code_files(root):
        count = line_count(root / rel)
        if count > LIMIT:
            over[rel] = count
    problems, notes = [], []
    for rel, count in sorted(over.items()):
        if rel not in listed:
            problems.append("%s has %d lines and is not on the list" % (rel, count))
        elif count > listed[rel]:
            problems.append("%s grew from %d to %d lines" % (rel, listed[rel], count))
        elif count < listed[rel]:
            notes.append("%s shrank from %d to %d lines; update the list" % (rel, listed[rel], count))
    for rel in sorted(listed):
        if rel not in over:
            notes.append("%s is under the limit or gone; remove it from the list" % rel)
    return over, problems, notes


def project_root(path):
    root = Path(path).resolve()
    if not root.is_dir():
        raise UsageError("not a folder: %s" % path)
    top = subprocess.run(["git", "-C", str(root), "rev-parse", "--show-toplevel"],
                         capture_output=True, text=True)
    # Paths in the list are relative to the top; measured from below it, none would match.
    if top.returncode != 0 or Path(top.stdout.strip()).resolve() != root:
        raise UsageError("not the top of a git working copy: %s" % root)
    return root


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("project", nargs="?", default=str(ROOT))
    args = parser.parse_args(argv)
    try:
        over, problems, notes = measure(project_root(args.project))
    except UsageError as error:
        print("error: %s" % error)
        return 2
    for line in problems:
        print("fail: " + line)
    for line in notes:
        print("note: " + line)
    print("size: %d files over %d lines, %d problems" % (len(over), LIMIT, len(problems)))
    if problems:
        print("next: split the file; listed files may shrink but never grow")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
