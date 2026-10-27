#!/usr/bin/env python3
"""Copy shared skill files from their owning skill into the skills that use
them, so every skill directory is self-contained.

The Agent Skills spec expects a skill to carry everything it reads: an agent
installing one skill (``npx skills add ... -s roj-review-pr-comment``, a
project-scope ``.claude/skills/``, any of the 70+ agents ``skills`` supports)
gets that directory and nothing else. Edit the owner's copy, then run:

  python3 tools/sync_shared.py          # rewrite the copies
  python3 tools/sync_shared.py --check  # exit 1 if any copy is stale (CI)

Python >= 3.8, standard library only.
"""
import argparse
import filecmp
import shutil
import sys
from pathlib import Path

SKILLS = Path(__file__).resolve().parent.parent / "skills"

# owner (relative to skills/) -> dirs that carry an identical copy. An owner
# dir shares every *.md in it; an owner file shares just that file; an owner
# with a `*` shares the files that glob matches (review lenses travel as
# `lang-*.md` and `platform-*.md`).
REVIEW = "roj-code-review-pr/references/"
SHARED = {
    REVIEW + "review-method.md": (
        "roj-review-pr-comment/references",
        "roj-explain-logic/references",
    ),
    REVIEW + "cross-cutting.md": (
        "roj-review-pr-comment/references",
        "roj-explain-logic/references",
    ),
    REVIEW + "lang-*.md": (
        "roj-review-pr-comment/references",
        "roj-explain-logic/references",
    ),
    REVIEW + "platform-*.md": (
        "roj-review-pr-comment/references",
        "roj-explain-logic/references",
    ),
    REVIEW + "base-resolution.md": (
        "roj-explain-logic/references",
        "roj-explain-feature-changes/references",
    ),
    REVIEW + "forge-bitbucket-dc.md": (
        "roj-review-pr-comment/references",
        "roj-explain-logic/references",
    ),
    REVIEW + "repo-map.md": (
        "roj-review-pr-comment/references",
        "roj-explain-logic/references",
        "roj-explain-feature-changes/references",
    ),
    REVIEW + "improvement-pass.md": (
        "roj-review-pr-comment/references",
    ),
    REVIEW + "graph-first.md": (
        "roj-review-pr-comment/references",
        "roj-onboard-repo/references",
        "roj-explain-logic/references",
        "roj-explain-feature-changes/references",
        "roj-investigate-issue/references",
        "roj-soundboarding/references",
        "roj-grill-plan/references",
    ),
    "roj-onboard-repo/references/mermaid.md": (
        "roj-explain-logic/references",
        "roj-explain-feature-changes/references",
    ),
    "roj-onboard-repo/references/html-page.md": (
        "roj-explain-logic/references",
    ),
}


def sources(owner):
    path = SKILLS / owner
    if "*" in path.name:
        return sorted(path.parent.glob(path.name))
    return [path] if path.is_file() else sorted(path.glob("*.md"))


def pairs():
    """(source file, copy path) for every shared file."""
    for owner, copies in SHARED.items():
        for src in sources(owner):
            for copy in copies:
                yield src, SKILLS / copy / src.name


def stale():
    """Copies that are missing, differ from the owner, or no longer exist
    in the owner (orphans)."""
    out = [dst for src, dst in pairs()
           if not dst.is_file() or not filecmp.cmp(src, dst, shallow=False)]
    for owner, copies in SHARED.items():
        path = SKILLS / owner
        if path.is_file():  # a single file leaves no orphans
            continue
        pattern = path.name if "*" in path.name else "*.md"
        names = {p.name for p in sources(owner)}
        for copy in copies:
            out += [p for p in sorted((SKILLS / copy).glob(pattern))
                    if p.name not in names]
    return out


def sync():
    for src, dst in pairs():
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, dst)
    for path in stale():           # only orphans remain after the copy
        path.unlink()


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--check", action="store_true",
                    help="report stale copies and exit 1 instead of writing")
    args = ap.parse_args()
    if args.check:
        bad = stale()
        for path in bad:
            print(f"stale: {path.relative_to(SKILLS.parent)}")
        if bad:
            print("run: python3 tools/sync_shared.py")
        sys.exit(1 if bad else 0)
    sync()
    print("shared files in sync")


if __name__ == "__main__":
    main()
