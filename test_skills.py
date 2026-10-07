"""Every skill in skills/ against the Agent Skills spec (agentskills.io) and
this repo's publishing rules. An agent silently skips a SKILL.md whose
frontmatter breaks the spec, so these fail loudly instead.

  python3 -m unittest test_skills -v
"""
import json
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SKILLS = ROOT / "skills"
sys.path.insert(0, str(ROOT / "tools"))

import sync_shared  # noqa: E402

SPEC_KEYS = {"name", "description", "license", "compatibility", "metadata",
             "allowed-tools"}
NAME_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
# Paths a SKILL.md tells the agent to open, relative to the skill root.
LOCAL_REF_RE = re.compile(r"(?<![\w/.~-])((?:references|assets|scripts|examples)"
                          r"/[\w./-]+\.\w+)")
# Files of a community skill a custom skill chains to ("validate with its
# scripts/validate_tour.py"); optional, and the skills skip them when absent.
COMMUNITY_REFS = {"scripts/validate_tour.py",   # code-tour
                  "scripts/scan.py"}            # acquire-codebase-knowledge
# Strings that would publish a personal machine layout. Keep generic
# placeholders (PROJ-123, example.com) instead. Employer-specific names must
# not appear even here: list them one regex per line in .private-patterns
# (git-ignored), and local runs check those too.
PRIVATE_PATTERNS = [r"/c/dev/", r"C:\\dev\\", r"/Users/", r"second-brain"]
_local = ROOT / ".private-patterns"
if _local.is_file():
    PRIVATE_PATTERNS += [line.strip() for line in
                         _local.read_text(encoding="utf-8").splitlines()
                         if line.strip() and not line.startswith("#")]
PRIVATE_RE = re.compile("|".join(PRIVATE_PATTERNS), re.I)
# First word of a Mermaid block; anything else fails to render.
MERMAID_TYPES = {"flowchart", "graph", "sequenceDiagram", "classDiagram",
                 "stateDiagram", "stateDiagram-v2", "erDiagram", "journey",
                 "gantt", "pie", "mindmap", "timeline", "gitGraph",
                 "quadrantChart", "C4Context", "C4Container", "C4Component"}
MERMAID_RE = re.compile(r"^```mermaid\n(.*?)^```$", re.M | re.S)


def skill_dirs():
    return sorted(p for p in SKILLS.iterdir() if p.is_dir())


def frontmatter(text):
    """(dict of top-level keys -> raw value, body). Nested `metadata:`
    entries are collected as a dict. Enough YAML for single-line values,
    which is all the spec's fields need."""
    if not text.startswith("---\n"):
        return None, text
    head, sep, body = text[4:].partition("\n---\n")
    if not sep:
        return None, text
    fm, current = {}, None
    for line in head.splitlines():
        if not line.strip():
            continue
        if line.startswith((" ", "\t")) and current == "metadata":
            key, _, value = line.strip().partition(":")
            fm["metadata"][key.strip()] = value.strip().strip("'\"")
            continue
        key, _, value = line.partition(":")
        current = key.strip()
        value = value.strip()
        if value.startswith('"'):
            value = json.loads(value)
        fm[current] = {} if current == "metadata" and not value else value
    return fm, body


class SkillTest(unittest.TestCase):
    def each(self):
        for d in skill_dirs():
            text = (d / "SKILL.md").read_text(encoding="utf-8")
            fm, body = frontmatter(text)
            with self.subTest(skill=d.name):
                yield d, fm, body


class TestSpec(SkillTest):
    def test_skill_md_exists_with_frontmatter(self):
        for d in skill_dirs():
            with self.subTest(skill=d.name):
                self.assertTrue((d / "SKILL.md").is_file())
                fm, _ = frontmatter((d / "SKILL.md").read_text("utf-8"))
                self.assertIsNotNone(fm, "missing --- frontmatter ---")

    def test_only_spec_keys(self):
        for _, fm, _ in self.each():
            self.assertLessEqual(set(fm), SPEC_KEYS)

    def test_name(self):
        for d, fm, _ in self.each():
            name = fm.get("name", "")
            self.assertEqual(name, d.name, "name must match the directory")
            self.assertLessEqual(len(name), 64)
            self.assertRegex(name, NAME_RE)
            self.assertTrue(name.startswith("roj-"),
                            "custom skills carry the roj- prefix")

    def test_description(self):
        for _, fm, _ in self.each():
            desc = fm.get("description", "")
            self.assertTrue(desc)
            self.assertLessEqual(len(desc), 1024)
            self.assertRegex(desc, r"\bUse (when|this)\b",
                             "say when to use the skill")

    def test_plain_values_parse_as_written(self):
        """Unquoted YAML ends a value at ' #' (comment) and fails on ': '.
        `npx skills` cut a description at "PR #123" this way — quote it."""
        for d, _, _ in self.each():
            head = (d / "SKILL.md").read_text("utf-8")[4:].split("\n---\n")[0]
            for line in head.splitlines():
                key, _, value = line.partition(":")
                value = value.strip()
                if line.startswith(" ") or not value or value[0] in "\"'":
                    continue
                with self.subTest(key=key):
                    self.assertNotIn(" #", value)
                    self.assertNotIn(": ", value)

    def test_optional_fields(self):
        for _, fm, _ in self.each():
            self.assertEqual(fm.get("license"), "MIT")
            if "compatibility" in fm:
                self.assertLessEqual(len(fm["compatibility"]), 500)
            if "metadata" in fm:
                self.assertIsInstance(fm["metadata"], dict)

    def test_body_stays_small(self):
        """Spec: the whole SKILL.md loads on activation — under 500 lines,
        detail goes to references/."""
        for _, _, body in self.each():
            self.assertLess(len(body.splitlines()), 500)


class TestSelfContained(SkillTest):
    def test_referenced_files_exist(self):
        for d, _, body in self.each():
            for rel in sorted(set(LOCAL_REF_RE.findall(body))):
                if "<" in rel or "*" in rel or rel in COMMUNITY_REFS:
                    continue
                with self.subTest(path=rel):
                    self.assertTrue((d / rel).exists(),
                                    f"{d.name}/{rel} is referenced but missing")

    def test_no_reads_from_another_installed_skill(self):
        """A skill installed alone (npx skills add -s <name>) has no sibling
        to read from — copy shared files in with tools/sync_shared.py."""
        pattern = re.compile(r"skills/roj-[\w-]+/(references|assets|scripts)/")
        for d, _, body in self.each():
            self.assertIsNone(pattern.search(body))

    def test_shared_copies_in_sync(self):
        stale = [str(p.relative_to(ROOT)) for p in sync_shared.stale()]
        self.assertEqual(stale, [], "run: python3 tools/sync_shared.py")

    def test_every_skill_has_usage_guide(self):
        for d in skill_dirs():
            with self.subTest(skill=d.name):
                self.assertTrue((d / "USAGE.md").is_file())


class TestPublishable(unittest.TestCase):
    def test_no_private_paths_or_employer_details(self):
        for f in sorted(SKILLS.rglob("*.md")):
            text = f.read_text(encoding="utf-8")
            for n, line in enumerate(text.splitlines(), 1):
                with self.subTest(file=str(f.relative_to(ROOT)), line=n):
                    self.assertIsNone(PRIVATE_RE.search(line), line)

    def test_mermaid_blocks_name_a_diagram_type(self):
        """Skills draw diagrams in Mermaid (references/mermaid.md); an
        example that does not render teaches the agent broken syntax."""
        for f in sorted(SKILLS.rglob("*.md")):
            text = f.read_text(encoding="utf-8")
            self.assertEqual(len(re.findall(r"(?m)^```mermaid", text)),
                             len(MERMAID_RE.findall(text)),
                             f"unclosed mermaid block in {f.name}")
            for block in MERMAID_RE.findall(text):
                first = block.strip().split(None, 1)[0] if block.strip() else ""
                with self.subTest(file=str(f.relative_to(ROOT)), first=first):
                    self.assertIn(first, MERMAID_TYPES)
                    self.assertNotRegex(block, r"(?m)^\s*end\s*(-->|---)",
                                        "`end` cannot be a node ID")

    def test_license_file(self):
        self.assertIn("MIT License",
                      (ROOT / "LICENSE").read_text(encoding="utf-8"))

    def test_marketplace_lists_every_skill(self):
        data = json.loads((ROOT / ".claude-plugin" / "marketplace.json")
                          .read_text(encoding="utf-8"))
        listed = sorted(s for plugin in data["plugins"]
                        for s in plugin["skills"])
        self.assertEqual(listed,
                         [f"./skills/{d.name}" for d in skill_dirs()])


if __name__ == "__main__":
    unittest.main()
