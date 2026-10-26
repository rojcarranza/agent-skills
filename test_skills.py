"""Every skill in skills/ against the Agent Skills spec (agentskills.io) and
this repo's publishing rules. An agent silently skips a SKILL.md whose
frontmatter breaks the spec, so these fail loudly instead.

  python3 -m unittest test_skills -v
"""
import json
import math
import os
import re
import shutil
import subprocess
import tempfile
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SKILLS = ROOT / "skills"
sys.path.insert(0, str(ROOT / "tools"))

import sync_shared  # noqa: E402
import install  # noqa: E402

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
# The tour paragraph every walkthrough skill carries (see
# test_tour_offer_paragraph_matches).
TOUR_PARAGRAPH = """
On a yes, chain to `code-tour`; if it is not installed write the JSON inline
(`$schema`, `title`, `description`, `steps` of `{file, line, description}`).
Validate with its `scripts/validate_tour.py` from whichever installed dir
exists — resolve `~` to an absolute path (cmd does not expand it) and try
`python`, then `python3`; skip validation rather than failing the run.
`.tours/` is in the global git ignore: never commit a tour or edit
`.gitignore`.
"""
# First word of a Mermaid block; anything else fails to render.
MERMAID_TYPES = {"flowchart", "graph", "sequenceDiagram", "classDiagram",
                 "stateDiagram", "stateDiagram-v2", "erDiagram", "journey",
                 "gantt", "pie", "mindmap", "timeline", "gitGraph",
                 "quadrantChart", "C4Context", "C4Container", "C4Component"}
MERMAID_RE = re.compile(r"^```mermaid\n(.*?)^```$", re.M | re.S)
# Quoted labels, |edge labels| and %% comments may say "end"; node IDs may not.
MERMAID_TEXT_RE = re.compile(r'"[^"]*"|\|[^|]*\||%%.*')
END_ID_RE = re.compile(r"(?<![\w-])end(?![\w-])")


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

    def test_long_references_have_contents(self):
        """Anthropic's authoring guide: a reference file over 100 lines opens
        with a table of contents, so a partial read still shows its scope."""
        for d in skill_dirs():
            for f in sorted((d / "references").glob("*.md")):
                lines = f.read_text(encoding="utf-8").splitlines()
                if len(lines) <= 100:
                    continue
                with self.subTest(file=str(f.relative_to(ROOT))):
                    self.assertIn("## Contents", lines[:20])

    def test_references_one_level_deep(self):
        """A reference file may name a sibling only when SKILL.md names it
        too (exactly or by a `prefix-*.md` pattern), so every file the agent
        reads is reached straight from SKILL.md."""
        for d, _, body in self.each():
            refs = d / "references"
            if not refs.is_dir():
                continue
            names = {f.name for f in refs.glob("*.md")}
            globs = re.findall(r"`([\w-]+)-\*\.md`", body)
            for f in sorted(refs.glob("*.md")):
                text = f.read_text(encoding="utf-8")
                for other in sorted(names - {f.name}):
                    if other not in text:
                        continue
                    covered = other in body or any(
                        other.startswith(g + "-") for g in globs)
                    with self.subTest(file=f.name, names=other):
                        self.assertTrue(covered, f"{d.name}/SKILL.md never "
                                        f"names {other}, which {f.name} does")

    def test_tour_offer_paragraph_matches(self):
        """Walkthrough skills repeat one tour paragraph so each still works
        when installed alone. Copies must not drift: edit them together."""
        for d, _, body in self.each():
            if "On a yes, chain to `code-tour`" not in body:
                continue
            flat = " ".join(body.split())
            self.assertIn(" ".join(TOUR_PARAGRAPH.split()), flat)

    def test_every_skill_has_usage_guide(self):
        for d in skill_dirs():
            with self.subTest(skill=d.name):
                self.assertTrue((d / "USAGE.md").is_file())


class TestGraphFirst(unittest.TestCase):
    """Skills that read code ask a graphify graph first when the repo has
    one (references/graph-first.md)."""

    USES_GRAPH = ("roj-onboard-repo", "roj-explain-logic",
                  "roj-explain-feature-changes", "roj-code-review-pr",
                  "roj-review-pr-comment", "roj-investigate-issue",
                  "roj-soundboarding", "roj-grill-plan")
    COMMANDS = ("graphify query", "graphify explain", "graphify path",
                "graphify affected", "graphify update")

    def test_code_reading_skills_point_at_it(self):
        for name in self.USES_GRAPH:
            with self.subTest(name):
                skill = SKILLS / name
                self.assertIn("graph-first.md",
                              (skill / "SKILL.md").read_text("utf-8"))
                self.assertTrue(
                    (skill / "references" / "graph-first.md").is_file())

    def test_reference_covers_the_commands_and_the_guards(self):
        text = (SKILLS / "roj-code-review-pr" / "references"
                / "graph-first.md").read_text("utf-8")
        for needle in self.COMMANDS + ("graphify-out/graph.json",
                                       "--budget", "INFERRED"):
            with self.subTest(needle):
                self.assertIn(needle, text)

    def test_graph_is_read_only(self):
        text = (SKILLS / "roj-code-review-pr" / "references"
                / "graph-first.md").read_text("utf-8")
        self.assertIn("Built from commit:", text)
        self.assertIn("Never run `graphify update`", text)

    def test_command_rules_allow_the_graph_queries(self):
        # Skills whose rules list allowed commands must also allow the
        # read-only queries, or the graph step cannot run there.
        for name in ("roj-onboard-repo", "roj-explain-feature-changes",
                     "roj-code-review-pr", "roj-review-pr-comment"):
            with self.subTest(name):
                text = (SKILLS / name / "SKILL.md").read_text("utf-8")
                self.assertIn("read-only `graphify` queries", text)
                tools = re.search(r"^allowed-tools: (.*)$", text, re.M)
                if tools:
                    for cmd in ("query", "explain", "path", "affected"):
                        self.assertIn(f"Bash(graphify {cmd} *)",
                                      tools.group(1))

    def test_graph_check_runs_every_time_and_reports(self):
        # The check for graph.json must not hide behind "when it applies":
        # each skill states it as a rule and closes its output with one of
        # the three Graph: status lines.
        for name in self.USES_GRAPH:
            with self.subTest(name):
                text = (SKILLS / name / "SKILL.md").read_text("utf-8")
                flat = " ".join(text.split())
                start = flat.index("Graph check, first and every run")
                rule = flat[start:start + 700]
                # The statuses must sit in the closing instruction of the
                # rule itself, not in unrelated prose elsewhere.
                self.assertIn("Close", rule)
                closing = rule[rule.index("Close"):]
                for status in ("`Graph: used`", "`Graph: stale, skipped`",
                               "`Graph: none found, searched directly`"):
                    self.assertIn(status, closing)

    def test_graph_reference_has_only_three_statuses(self):
        text = (SKILLS / "roj-code-review-pr" / "references"
                / "graph-first.md").read_text("utf-8")
        flat = " ".join(text.split())
        statuses = set(re.findall(r"`Graph: [^`]*`", flat))
        self.assertEqual(statuses, {
            "`Graph: used`", "`Graph: stale, skipped`",
            "`Graph: none found, searched directly`"})


class TestOnboardRepoGuide(unittest.TestCase):
    """roj-onboard-repo writes a Markdown guide under .onboarding/ and must
    run when the host cannot expand `~` or open the skill's own folder: a
    JetBrains run once failed every read and still wrote tours."""

    ONBOARD = SKILLS / "roj-onboard-repo"
    # Home-directory shortcuts, the skill-root variable and a search of the
    # agents' skill folders: each needs a path the host may not resolve.
    LOOKUP_RE = re.compile(
        r"~[/\\]|\$SKILL_ROOT|\$\{SKILL_ROOT\}|\$HOME|%USERPROFILE%"
        r"|\.(?:claude|copilot|agents)/skills|skill folder|skill directory"
        r"|installed dir", re.I)

    def texts(self):
        yield self.ONBOARD / "SKILL.md"
        yield from sorted((self.ONBOARD / "references").glob("*.md"))

    def test_no_home_or_skill_folder_lookups(self):
        for f in self.texts():
            for n, line in enumerate(f.read_text("utf-8").splitlines(), 1):
                with self.subTest(file=f.name, line=n):
                    self.assertIsNone(self.LOOKUP_RE.search(line), line)

    def test_skill_md_is_complete_without_references(self):
        flat = " ".join((self.ONBOARD / "SKILL.md").read_text("utf-8").split())
        for needle in (".onboarding/", "Read gate", "stop and write nothing",
                       "Reference unavailable", "check-ignore",
                       "`flowchart TD`", "`sequenceDiagram`",
                       "reviewing-prs.md", "Every claim cites"):
            with self.subTest(needle=needle):
                self.assertIn(needle, flat)

    def test_tours_are_on_request_only(self):
        flat = " ".join((self.ONBOARD / "SKILL.md").read_text("utf-8").split())
        self.assertIn("CodeTour, on request only", flat)
        self.assertIn("No default tours", flat)
        for old in ("01-orientation.tour", "plan checkpoint, then"):
            self.assertNotIn(old, flat)
        for gone in ("tour-plan.md", "step-writing.md"):
            self.assertFalse((self.ONBOARD / "references" / gone).exists())

    def script(self, reference, name):
        """The fenced python block that follows `name` in a reference."""
        text = (self.ONBOARD / "references" / reference).read_text("utf-8")
        tail = text[text.index(f"`{name}`:"):]
        return re.search(r"```python\n(.*?)\n```", tail, re.S).group(1)

    def run_script(self, code, *args):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "check.py"
            path.write_text(code, encoding="utf-8")
            return subprocess.run([sys.executable, str(path), *map(str, args)],
                                  capture_output=True, text=True)

    GUIDE_DIAGRAM = "flowchart TD\n  a[\"x - a.py\"] --> b[\"y\"]"

    def build_guide(self, tmp, html_diagram=None):
        """A one-file guide plus an index.html built from it."""
        d = Path(tmp) / ".onboarding"
        d.mkdir()
        (Path(tmp) / "a.py").write_text("one\ntwo\nthree\n", "utf-8")
        (d / "README.md").write_text(
            "# R\n\n## 2. System map\n\n```mermaid\n" + self.GUIDE_DIAGRAM
            + "\n```\n\nSee `a.py:2-3`.\n", "utf-8")
        src = (html_diagram or self.GUIDE_DIAGRAM).replace(
            "&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        (d / "index.html").write_text(
            '<html><body><div id="mermaid-banner"></div><h3>2. System map</h3>'
            '<figure class="diagram"><p class="diagram-note">n</p>'
            f'<pre class="diagram-src">{src}</pre></figure>'
            '<code class="ref">a.py:2-3</code>'
            '<script src="https://cdn.jsdelivr.net/npm/mermaid@11.12.0/dist/'
            'mermaid.min.js"></script></body></html>', "utf-8")
        return d

    def test_html_check_script_catches_divergence(self):
        code = self.script("html-page.md", "check-html.py")
        with tempfile.TemporaryDirectory() as tmp:
            d = self.build_guide(tmp)
            ok = self.run_script(code, d)
            self.assertEqual(ok.returncode, 0, ok.stdout + ok.stderr)
        with tempfile.TemporaryDirectory() as tmp:
            d = self.build_guide(tmp, self.GUIDE_DIAGRAM + "\n  b --> c")
            bad = self.run_script(code, d)
            self.assertEqual(bad.returncode, 1)
            self.assertIn("diagrams differ", bad.stdout)

    def test_anchor_check_script_catches_bad_anchors(self):
        code = self.script("templates.md", "check-anchors.py")
        with tempfile.TemporaryDirectory() as tmp:
            d = self.build_guide(tmp)
            self.assertEqual(self.run_script(
                code, tmp, d / "README.md").returncode, 0)
            (d / "README.md").write_text("`a.py:9` `missing.py:1`", "utf-8")
            bad = self.run_script(code, tmp, d / "README.md")
            self.assertEqual(bad.returncode, 1)
            self.assertIn("a.py:9", bad.stdout)

    def test_index_html_contract(self):
        flat = " ".join((self.ONBOARD / "SKILL.md").read_text("utf-8").split())
        for needle in ("index.html", "references/html-page.md",
                       "lavish-axi", "cdn.jsdelivr.net/npm/mermaid@",
                       "never `latest`", "HTML matches Markdown"):
            with self.subTest(needle=needle):
                self.assertIn(needle, flat)
        page = (self.ONBOARD / "references" / "html-page.md").read_text("utf-8")
        urls = set(re.findall(r"https://cdn\.jsdelivr\.net/[^\s\"'),`]+", page))
        self.assertEqual(len(urls), 1, urls)
        self.assertRegex(next(iter(urls)), r"/npm/mermaid@\d+\.\d+\.\d+/")
        for needle in ('integrity="sha384-', 'class="diagram-src"',
                       'id="mermaid-banner"', 'prefers-color-scheme: dark',
                       'data-theme="dark"', 'code class="ref"',
                       "lavish-axi <ROOT>/.onboarding/index.html"):
            with self.subTest(needle=needle):
                self.assertIn(needle, page)

    def test_templates_ship_the_anchor_check(self):
        text = (self.ONBOARD / "references" / "templates.md").read_text("utf-8")
        self.assertIn("check-anchors.py", text)
        self.assertIn("sys.exit(1 if bad else 0)", text)


class TestReviewModes(unittest.TestCase):
    """roj-code-review-pr absorbed the fast review as its quick mode, and the
    skills that read a branch diff ship the shared base resolution."""

    def test_fast_skill_is_gone(self):
        self.assertFalse((SKILLS / "roj-code-review-pr-fast").exists())
        self.assertFalse((ROOT / "evals" / "roj-code-review-pr-fast").exists())

    def test_diff_reading_skills_ship_base_resolution(self):
        for name in ("roj-code-review-pr", "roj-explain-logic",
                     "roj-explain-feature-changes"):
            with self.subTest(name):
                self.assertTrue((SKILLS / name / "references" /
                                 "base-resolution.md").is_file())


class TestSoundboarding(unittest.TestCase):
    """The example SB is what the model copies: it must hold the template's
    sections and no others, and its tables must carry the evidence columns."""

    SB = SKILLS / "roj-soundboarding"

    @staticmethod
    def headings(text):
        return re.findall(r"(?m)^## (.+)$", text)

    def test_example_has_only_the_template_sections(self):
        template = (self.SB / "assets" / "SB-template.md").read_text("utf-8")
        example = (self.SB / "examples" / "SB-PROJ-1001.md").read_text("utf-8")
        self.assertEqual(self.headings(example), self.headings(template))

    def test_bundled_template_has_no_standing_question(self):
        template = (self.SB / "assets" / "SB-template.md").read_text("utf-8")
        section = re.search(r"(?ms)^## Questions\n(.*?)(?=^## |\Z)",
                            template)
        self.assertIsNotNone(section)
        bullets = [l[1:].strip() for l in section.group(1).splitlines()
                   if l.startswith("-")]
        self.assertEqual([b for b in bullets if b], [])

    def test_before_after_tables_carry_location_and_source(self):
        header = ("| # | File/Property | Location | Before | After | Reason "
                  "| Source |")
        example = (self.SB / "examples" / "SB-PROJ-1001.md").read_text("utf-8")
        self.assertIn(header, example)
        rows = [l for l in example.splitlines()
                if re.match(r"\| \d+ \|", l)]
        self.assertTrue(rows)
        for row in rows:
            with self.subTest(row=row[:40]):
                self.assertRegex(row, r"`[^`]+:\d+(?:[-,]\d+)*`")


def git_bash():
    """bash for the eval fixtures. On Windows, Git Bash next to git: a bare
    `bash` there can resolve to System32's WSL launcher."""
    if os.name != "nt":
        return shutil.which("bash")
    git = shutil.which("git")
    if not git:
        return None
    for candidate in (Path(git).parent.parent / "bin" / "bash.exe",
                      Path(git).parent / "bash.exe"):
        if candidate.is_file():
            return str(candidate)
    return None


BASH = git_bash()


class TestEvals(unittest.TestCase):
    """evals/<skill>/ holds skill-creator eval sets, outside skills/ so no
    install carries them. triggers.json feeds scripts/run_eval.py;
    evals.json follows skill-creator's schema, plus a "fixture" naming the
    sandbox repo (evals/fixtures/build.sh) and, for the PR-comment skill,
    the fake Bitbucket mode (evals/fixtures/fake_bitbucket.py)."""

    FIXTURES = ROOT / "evals" / "fixtures"
    BITBUCKET_MODES = {"normal", "reviewed", "prior"}
    CLAUDE_MODES = {"missing", "present", "outdated"}
    # Fixtures that are a bare folder, for skills that start a project.
    NO_GIT = {"idea-empty"}

    # Every shipped skill must keep an eval set: a skill without evals
    # fails test_required_eval_sets_exist.
    REQUIRED = {d.name for d in skill_dirs()}

    def eval_dirs(self):
        return sorted(p for p in (ROOT / "evals").iterdir()
                      if p.is_dir() and p != self.FIXTURES)

    def fixture_kinds(self):
        """The case labels of build.sh, one per fixture it can build."""
        text = (self.FIXTURES / "build.sh").read_text("utf-8")
        return set(re.findall(r"^([a-z][\w-]*)\)", text, re.M))

    def test_evals_name_buildable_fixtures(self):
        kinds = self.fixture_kinds()
        for d in self.eval_dirs():
            data = json.loads((d / "evals.json").read_text("utf-8"))
            for e in data["evals"]:
                with self.subTest(evals=d.name, id=e["id"]):
                    self.assertIn(e["fixture"]["repo"], kinds)
                    if "bitbucket" in e["fixture"]:
                        self.assertIn(e["fixture"]["bitbucket"],
                                      self.BITBUCKET_MODES)
                    if "claude" in e["fixture"]:
                        self.assertIn(e["fixture"]["claude"],
                                      self.CLAUDE_MODES)

    @unittest.skipUnless(BASH and shutil.which("git"), "needs bash and git")
    def test_every_fixture_builds(self):
        used = set()
        for d in self.eval_dirs():
            data = json.loads((d / "evals.json").read_text("utf-8"))
            used |= {e["fixture"]["repo"] for e in data["evals"]}
        with tempfile.TemporaryDirectory() as tmp:
            for kind in sorted(used):
                with self.subTest(fixture=kind):
                    dest = Path(tmp) / kind
                    run = subprocess.run(
                        [BASH, str(self.FIXTURES / "build.sh"), kind,
                         str(dest)], capture_output=True, text=True)
                    self.assertEqual(run.returncode, 0, run.stderr)
                    if kind in self.NO_GIT:
                        self.assertTrue((dest / "repo").is_dir())
                        self.assertFalse((dest / "repo" / ".git").exists())
                    else:
                        self.assertTrue((dest / "repo" / ".git").is_dir())
            sp = Path(tmp) / "idea-empty"
            run = subprocess.run(
                [BASH, str(self.FIXTURES / "fake-claude.sh"), str(sp),
                 "missing"], capture_output=True, text=True)
            self.assertEqual(run.returncode, 0, run.stderr)
            self.assertTrue((sp / "bin" / "claude").is_file())
            for kind in sorted(self.NO_GIT | {"idea-brief-2ng",
                                              "idea-req-gap"} - used):
                with self.subTest(fixture=kind):
                    dest = Path(tmp) / f"direct-{kind}"
                    run = subprocess.run(
                        [BASH, str(self.FIXTURES / "build.sh"), kind,
                         str(dest)], capture_output=True, text=True)
                    self.assertEqual(run.returncode, 0, run.stderr)

    def test_required_eval_sets_exist(self):
        present = {d.name for d in self.eval_dirs()}
        self.assertLessEqual(self.REQUIRED, present)
        for d in self.eval_dirs():
            with self.subTest(evals=d.name):
                self.assertTrue((d / "triggers.json").is_file())
                self.assertTrue((d / "evals.json").is_file())

    def test_eval_dirs_name_real_skills(self):
        names = {d.name for d in skill_dirs()}
        for d in self.eval_dirs():
            with self.subTest(evals=d.name):
                self.assertIn(d.name, names)

    def test_triggers_cover_both_sides(self):
        for d in self.eval_dirs():
            with self.subTest(evals=d.name):
                items = json.loads((d / "triggers.json").read_text("utf-8"))
                for item in items:
                    self.assertIsInstance(item["query"], str)
                    self.assertIsInstance(item["should_trigger"], bool)
                hits = sum(i["should_trigger"] for i in items)
                self.assertGreaterEqual(hits, 5, "too few should-trigger")
                self.assertGreaterEqual(len(items) - hits, 5,
                                        "too few should-not-trigger")
                queries = [i["query"] for i in items]
                self.assertEqual(len(queries), len(set(queries)))

    def test_behaviour_evals(self):
        for d in self.eval_dirs():
            with self.subTest(evals=d.name):
                data = json.loads((d / "evals.json").read_text("utf-8"))
                self.assertEqual(data["skill_name"], d.name)
                self.assertGreaterEqual(len(data["evals"]), 3)
                ids = [e["id"] for e in data["evals"]]
                self.assertEqual(len(ids), len(set(ids)))
                for e in data["evals"]:
                    with self.subTest(id=e.get("id")):
                        self.assertIsInstance(e["id"], int)
                        self.assertTrue(e["prompt"])
                        self.assertTrue(e["expected_output"])
                        self.assertIsInstance(e["expectations"], list)
                        self.assertTrue(e["expectations"])
                        for x in e["expectations"]:
                            self.assertIsInstance(x, str)


STOPWORDS = frozenset("""a an and any are as at be by do does for from has have
how i if in into what who why whom is it its my no not of on one or our so that the their them
then this to use used user users using want when which with you your""".split())

# Trigger phrases a user really types, per skill. Each must route to the
# owner and not to a sibling: the owner's description must score strictly
# highest. Add a row when a description changes or two skills start to blur.
ROUTES = {
    "roj-code-review-pr": [
        "review my pull request before I merge",
        "do a code review of this branch and find defects",
        "quick review of my uncommitted changes",
    ],
    "roj-review-pr-comment": [
        "review PR 123 and comment on it",
        "post a review on this PR",
        "review this Bitbucket pull request URL and leave inline comments",
    ],
    "roj-explain-logic": [
        "explain this function line by line",
        "walk me through how this code flow works",
        "what does this method do and who calls it",
    ],
    "roj-explain-feature-changes": [
        "explain my changes compared to develop",
        "help me explain this branch to my reviewer",
        "generate text I can paste into my PR describing what I changed",
    ],
    "roj-investigate-issue": [
        "investigate this issue and find the root cause",
        "why did this Bamboo pipeline build fail",
        "validate this bug from the stack trace in the problem file",
    ],
    "roj-soundboarding": [
        "create an SB document for this Jira ticket",
        "soundboard this user story before I implement it",
        "implement the story from the SB document",
    ],
    "roj-grill-plan": [
        "grill me on this story",
        "stress-test this plan and poke holes in it",
        "resolve the open questions in the SB",
    ],
    "roj-onboard-repo": [
        "onboard me to this repo",
        "tour this codebase",
        "where do I start in this project I just joined",
        "draw the architecture and explain the code before I review PRs",
    ],
    "roj-interview-prep": [
        "prepare an interview for this candidate from their CV",
        "new candidate interview prep",
        "final assessment of the interviewed candidate",
    ],
    "roj-idea-to-project": [
        "I have an app idea and want to plan it before building",
        "set up a new empty repo so an agent can build my product idea",
        "write requirements and architecture for a new app",
    ],
}


def _stem(word):
    for suffix in ("ing", "ed", "es", "s"):
        if word.endswith(suffix) and len(word) - len(suffix) >= 4:
            return word[:-len(suffix)]
    return word


def _tokens(text):
    return {_stem(w) for w in re.findall(r"[a-z0-9]+", text.lower())
            if w not in STOPWORDS and len(w) > 1}


NEGATIVE_RE = re.compile(r"^(?:Not for|Do NOT|Never|For [^.]*\buse\b)", re.I)


def route_units(description):
    """What a description offers an agent to match on: its quoted trigger
    phrases and its sentences, minus the ones that point away to a sibling
    ("Not for ...", "Do NOT use ..."), which would credit the sibling's
    vocabulary to this skill."""
    quoted, sentences = [], []
    for sentence in re.split(r"(?<=[.!?])\s+", description):
        if not NEGATIVE_RE.match(sentence):
            quoted += re.findall(r'"([^"]+)"', sentence)
            sentences.append(re.sub(r'"[^"]*"', " ", sentence))
    # A sentence left as "Uses the method." once a skill name is cut is a
    # stub, not a trigger; a quoted phrase is always one.
    sentences = [re.sub(r"roj-[a-z-]+", " ", s) for s in sentences]
    return quoted + [s for s in sentences if len(_tokens(s)) >= 3]


def route_scores(phrase, descriptions):
    """Cosine of IDF-weighted words between a phrase and the best unit of
    each description. A word every description shares says nothing; a word
    only one has decides. Deterministic, no model call."""
    units = {n: [_tokens(u) for u in route_units(d)]
             for n, d in descriptions.items()}
    owners = {n: set().union(*us) for n, us in units.items()}
    idf = {w: math.log(len(owners) / sum(w in o for o in owners.values()))
           for w in set().union(*owners.values())}
    want = _tokens(phrase)
    norm = math.sqrt(sum(idf.get(w, 0.0) ** 2 for w in want)) or 1.0

    def cosine(unit):
        size = math.sqrt(sum(idf[w] ** 2 for w in unit)) or 1.0
        return sum(idf[w] ** 2 for w in want & unit) / (norm * size)
    return {n: max(cosine(u) for u in us) for n, us in units.items()}


class TestRouting(unittest.TestCase):
    """Descriptions are all an agent sees when it picks a skill, so two
    that blur send a request to the wrong one."""

    @classmethod
    def setUpClass(cls):
        cls.descriptions = {}
        for d in skill_dirs():
            fm, _ = frontmatter((d / "SKILL.md").read_text("utf-8"))
            cls.descriptions[d.name] = fm["description"]

    def test_every_skill_has_routes(self):
        self.assertEqual(set(ROUTES), set(self.descriptions))
        for name, phrases in ROUTES.items():
            with self.subTest(skill=name):
                self.assertGreaterEqual(len(phrases), 3)

    def test_phrases_route_to_their_skill_and_not_a_sibling(self):
        for owner, phrases in ROUTES.items():
            for phrase in phrases:
                with self.subTest(skill=owner, phrase=phrase):
                    scores = route_scores(phrase, self.descriptions)
                    rivals = {n: round(s, 2) for n, s in scores.items()
                              if n != owner and s >= scores[owner]}
                    self.assertFalse(
                        rivals, f"scores {round(scores[owner], 2)} for "
                        f"{owner}, but {rivals} score as high")


class TestPublishable(unittest.TestCase):
    def test_no_private_paths_or_employer_details(self):
        for f in sorted([*SKILLS.rglob("*.md"),
                         *(ROOT / ".apm").rglob("*.md"),
                         ROOT / "cali.yaml"]):
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
                    if first not in ("flowchart", "graph"):
                        continue
                    for line in block.splitlines():
                        code = MERMAID_TEXT_RE.sub("", line).strip()
                        if code != "end":   # a bare `end` closes a subgraph
                            self.assertIsNone(END_ID_RE.search(code),
                                              f"`end` as a node ID: {line}")

    def test_license_file(self):
        self.assertIn("MIT License",
                      (ROOT / "LICENSE").read_text(encoding="utf-8"))

    def test_marketplace_lists_the_skills_claude_gets(self):
        """Only skills cali.yaml targets at Claude are in the plugin."""
        data = json.loads((ROOT / ".claude-plugin" / "marketplace.json")
                          .read_text(encoding="utf-8"))
        listed = sorted(s for plugin in data["plugins"]
                        for s in plugin["skills"])
        claude = {d["name"] for d in install.manifest_deps()
                  if d["active"] and (d["targets"] is None
                                      or "claude" in d["targets"])}
        self.assertEqual(listed,
                         [f"./skills/{d.name}" for d in skill_dirs()
                          if d.name in claude])


SHA_RE = re.compile(r"[0-9a-f]{40}")


class TestManifest(unittest.TestCase):
    """cali.yaml is the one list of skills install.py installs."""

    def setUp(self):
        self.deps = install.manifest_deps()

    def test_every_skill_is_live_from_this_repo(self):
        live = {d["name"]: d["source"] for d in self.deps if d["active"]}
        for d in skill_dirs():
            with self.subTest(skill=d.name):
                self.assertEqual(live.get(d.name),
                                 ".//skills/"
                                 + d.name)

    def test_every_requirement_is_live(self):
        live = install.manifest_skill_names()
        for skill, deps in install.REQUIRES.items():
            for dep in deps:
                with self.subTest(skill=skill, dep=dep):
                    self.assertIn(dep, live)

    def test_community_refs_are_full_shas(self):
        for d in self.deps:
            if d["source"].startswith(".//"):
                continue
            with self.subTest(dep=d["name"]):
                self.assertRegex(d["ref"] or "", SHA_RE)

    def test_names_are_unique(self):
        names = [d["name"] for d in self.deps]
        self.assertEqual(len(names), len(set(names)))

    def test_github_mcp_is_registered_for_both_agents(self):
        self.assertEqual(set(install.MCP_SERVERS["github-mcp-server"]),
                         {"claude", "copilot"})

    def test_instructions_apply_everywhere(self):
        text = (ROOT / ".apm" / "instructions"
                / "personal.instructions.md").read_text(encoding="utf-8")
        self.assertTrue(text.startswith("---\n"))
        self.assertIn('applyTo: "**"', text.split("---", 2)[1])


class TestNoStaleAccount(unittest.TestCase):
    """The GitHub account was renamed; old links rely on a redirect."""

    def test_no_reference_to_old_account(self):
        stale = "r0j" + "james"
        files = subprocess.run(
            ["git", "ls-files", "-z"], cwd=ROOT, capture_output=True,
            check=True).stdout.decode("utf-8").split("\0")
        hits = []
        for name in filter(None, files):
            try:
                text = (ROOT / name).read_text(encoding="utf-8")
            except (UnicodeDecodeError, FileNotFoundError):
                continue
            if stale in text.lower():
                hits.append(name)
        self.assertEqual(hits, [], "replace the old account name with rojcarranza")



def load_module(path):
    import importlib.util
    spec = importlib.util.spec_from_file_location(path.stem, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class TestReviewPrCommentSkill(unittest.TestCase):
    """roj-review-pr-comment drafts first and talks to Bitbucket Data Center
    only; the pieces that make that true are checked here."""

    SKILL = SKILLS / "roj-review-pr-comment"

    def text(self, name):
        return (self.SKILL / name).read_text("utf-8")

    def tools(self):
        fm, _ = frontmatter(self.text("SKILL.md"))
        return fm["allowed-tools"]

    def test_allowed_tools_read_the_pr_head_with_git_and_no_write_or_http(self):
        tools = re.findall(r"[^\s(]+(?:\([^)]*\))?", self.tools())
        for cmd in ("Bash(git fetch origin *)", "Bash(git show *)",
                    "Bash(git diff *)"):
            self.assertIn(cmd, tools)
        for tool in tools:
            self.assertNotIn(tool, ("Write", "Edit"))
            self.assertFalse(tool.startswith(("Bash(gh", "Bash(curl")), tool)


class TestBitbucketPrScript(unittest.TestCase):
    """scripts/bitbucket_pr.py against the stand-in server the evals use."""

    HEAD = "c" * 40
    TOKEN = "test-token"

    @classmethod
    def setUpClass(cls):
        cls.script = load_module(SKILLS / "roj-review-pr-comment" / "scripts"
                                 / "bitbucket_pr.py")
        cls.fake = load_module(ROOT / "evals" / "fixtures"
                               / "fake_bitbucket.py")

    def serve(self, mode="normal", reject=()):
        server, state = self.fake.serve(self.HEAD, mode, reject)
        self.addCleanup(server.shutdown)
        self.addCleanup(server.server_close)
        env = {"BITBUCKET_URL": f"http://127.0.0.1:{server.server_port}",
               "BITBUCKET_TOKEN": self.TOKEN}
        return env, state

    def run_cmd(self, argv, env, stdin=""):
        import contextlib
        import io
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stderr(err):
            code = self.script.main(argv, env=env, out=out,
                                    stdin=io.StringIO(stdin))
        self.assertNotIn(self.TOKEN, out.getvalue() + err.getvalue())
        text = out.getvalue()
        return code, (json.loads(text) if text.strip() else None), err.getvalue()

    PR = ["--project", "APP", "--repo", "uploader", "--pr", "7"]

    def findings(self, path, **extra):
        data = {"head": self.HEAD, "summary": "Retry uploads.\n\n1 finding.",
                "comments": [{"path": "app/uploader.py", "line": 22,
                              "lineType": "ADDED", "text":
                              'Says "x" with a \\ and a `tick`\nand \u00e9 \U0001F7E0'}]}
        data.update(extra)
        Path(path).write_text(json.dumps(data), encoding="utf-8")
        return str(path)

    def test_token_status_never_prints_the_token(self):
        env, _ = self.serve()
        code, data, _ = self.run_cmd(["token-status"], env)
        self.assertEqual((code, data["token"]), (0, True))
        code, data, _ = self.run_cmd(["token-status"], {})
        self.assertEqual((code, data), (0, {"token": False, "baseUrl": None}))

    def test_info_reads_target_and_head(self):
        env, _ = self.serve()
        code, data, _ = self.run_cmd(["info", *self.PR], env)
        self.assertEqual(code, 0)
        self.assertEqual((data["target"], data["headSha"]),
                         ("develop", self.HEAD))
        self.assertIn("nightly restart", data["description"])

    def test_comments_follow_pages_and_report_reviewed(self):
        env, state = self.serve("prior")
        code, data, _ = self.run_cmd(
            ["comments", *self.PR, "--head", self.HEAD], env)
        self.assertEqual(code, 0)
        self.assertGreater(len(state.activities), self.fake.PAGE_CAP)
        self.assertFalse(data["reviewed"])
        anchored = [c for c in data["comments"] if c["path"]]
        self.assertEqual([(c["path"], c["line"]) for c in anchored],
                         [("app/uploader.py", 20)])
        self.assertEqual(len(data["comments"]), 3)   # the OPENED one is out
        env, _ = self.serve("reviewed")
        _, data, _ = self.run_cmd(["comments", *self.PR, "--head", self.HEAD],
                                  env)
        self.assertTrue(data["reviewed"])

    def test_post_builds_anchors_and_a_marked_summary(self):
        env, state = self.serve()
        with tempfile.TemporaryDirectory() as tmp:
            f = self.findings(Path(tmp) / "f.json")
            code, data, _ = self.run_cmd(
                ["post", *self.PR, "--findings", f], env)
        self.assertEqual((code, data["status"]), (0, "ok"))
        inline, summary = state.posted
        self.assertEqual(inline["anchor"], {
            "path": "app/uploader.py", "line": 22, "lineType": "ADDED",
            "fileType": "TO"})
        self.assertEqual(inline["text"], 'Says "x" with a \\ and a `tick`\n'
                         'and \u00e9 \U0001F7E0')
        self.assertNotIn("anchor", summary)
        self.assertTrue(summary["text"].endswith(
            f"Reviewed commit `{self.HEAD[:12]}`"))
        self.assertEqual([c for c in state.calls if c.startswith("POST")],
                         [f"POST {self.fake.BASE}/comments"] * 2)

    def test_post_reads_stdin(self):
        env, state = self.serve()
        with tempfile.TemporaryDirectory() as tmp:
            f = self.findings(Path(tmp) / "f.json")
            raw = Path(f).read_text("utf-8")
        code, data, _ = self.run_cmd(["post", *self.PR, "--findings", "-"],
                                     env, stdin=raw)
        self.assertEqual((code, len(state.posted)), (0, 2))

    def test_post_skips_a_head_that_is_already_reviewed(self):
        env, state = self.serve("reviewed")
        with tempfile.TemporaryDirectory() as tmp:
            f = self.findings(Path(tmp) / "f.json")
            code, data, _ = self.run_cmd(["post", *self.PR, "--findings", f],
                                         env)
        self.assertEqual((code, data["status"]), (0, "already-reviewed"))
        self.assertEqual(state.posted, [])

    def test_an_identical_comment_is_skipped_but_the_head_still_gets_its_summary(self):
        env, state = self.serve("prior")
        text = state.activities[-1]["comment"]["text"]
        with tempfile.TemporaryDirectory() as tmp:
            f = Path(tmp) / "f.json"
            Path(f).write_text(json.dumps({
                "head": self.HEAD, "summary": "s", "comments": [
                    {"path": "app/uploader.py", "line": 25,
                     "lineType": "ADDED", "text": text}]}), encoding="utf-8")
            code, data, _ = self.run_cmd(["post", *self.PR, "--findings",
                                          str(f)], env)
        self.assertEqual(code, 0)
        self.assertEqual((len(data["skipped"]), data["posted"]), (1, []))
        (summary,) = state.posted
        self.assertNotIn("anchor", summary)
        self.assertIn("Nothing new", summary["text"])
        self.assertTrue(summary["text"].endswith(
            f"Reviewed commit `{self.HEAD[:12]}`"))

    def test_a_rerun_after_a_failed_summary_completes_the_review(self):
        env, state = self.serve()
        state.fail_summary = True
        with tempfile.TemporaryDirectory() as tmp:
            f = self.findings(Path(tmp) / "f.json")
            post = ["post", *self.PR, "--findings", f]
            code, data, _ = self.run_cmd(post, env)
            self.assertEqual((code, data["status"]), (5, "partial"))
            self.assertEqual(len(state.posted), 1)
            state.fail_summary = False
            code, data, _ = self.run_cmd(post, env)
            self.assertEqual((code, data["status"]), (0, "ok"))
            self.assertEqual(len(data["skipped"]), 1)
            self.assertEqual(len(state.posted), 2)
            self.assertTrue(state.posted[1]["text"].endswith(
                f"Reviewed commit `{self.HEAD[:12]}`"))
            code, data, _ = self.run_cmd(post, env)
            self.assertEqual(data["status"], "already-reviewed")
            self.assertEqual(len(state.posted), 2)

    def test_a_rejected_line_moves_into_the_summary(self):
        env, state = self.serve(reject=("app/uploader.py:22",))
        with tempfile.TemporaryDirectory() as tmp:
            f = self.findings(Path(tmp) / "f.json")
            code, data, _ = self.run_cmd(["post", *self.PR, "--findings", f],
                                         env)
        self.assertEqual((code, data["status"]), (0, "ok"))
        self.assertEqual(data["failed"][0]["line"], 22)
        (summary,) = state.posted
        self.assertIn("`app/uploader.py:22`", summary["text"])

    def test_dry_run_needs_no_token_or_network(self):
        with tempfile.TemporaryDirectory() as tmp:
            f = self.findings(Path(tmp) / "f.json")
            code, data, _ = self.run_cmd(
                ["post", *self.PR, "--findings", f, "--dry-run"], {})
        self.assertEqual(code, 0)
        self.assertEqual(len(data["requests"]), 2)
        self.assertTrue(data["requests"][0]["path"].endswith("/comments"))

    def stub(self, handler_fn):
        from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
        import threading
        seen = []

        class H(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def do_GET(self):
                seen.append(self.headers.get("Authorization"))
                handler_fn(self)

        server = ThreadingHTTPServer(("127.0.0.1", 0), H)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        return server, seen

    def test_a_redirect_is_refused_and_never_gets_the_token(self):
        target, target_seen = self.stub(
            lambda h: (h.send_response(200), h.end_headers()))

        def redirect(h):
            h.send_response(302)
            h.send_header("Location",
                          f"http://127.0.0.1:{target.server_port}/sso")
            h.end_headers()
        origin, _ = self.stub(redirect)
        env = {"BITBUCKET_URL": f"http://127.0.0.1:{origin.server_port}",
               "BITBUCKET_TOKEN": self.TOKEN}
        code, _, err = self.run_cmd(["info", *self.PR], env)
        self.assertEqual(code, 5, err)
        self.assertEqual(target_seen, [])

    def test_a_non_json_answer_is_a_server_error(self):
        def html(h):
            body = b"<html>SSO</html>"
            h.send_response(200)
            h.send_header("Content-Length", str(len(body)))
            h.end_headers()
            h.wfile.write(body)

        def array(h):
            body = b"[]"
            h.send_response(200)
            h.send_header("Content-Length", str(len(body)))
            h.end_headers()
            h.wfile.write(body)
        for fn in (html, array):
            server, _ = self.stub(fn)
            env = {"BITBUCKET_URL": f"http://127.0.0.1:{server.server_port}",
                   "BITBUCKET_TOKEN": self.TOKEN}
            for argv in (["info", *self.PR], ["comments", *self.PR]):
                code, _, err = self.run_cmd(argv, env)
                self.assertEqual(code, 5, err)

    def test_a_transport_failure_mid_post_still_reports_what_was_posted(self):
        for second, status, expected in (
                (b"<html>SSO</html>", 200, "JSON object"),
                (None, 200, "cannot reach"),
                (None, 502, "HTTP 502")):
            with self.subTest(second=second, status=status):
                self.mid_post_failure(second, status, expected)

    def mid_post_failure(self, second, status, expected):
        from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
        import threading
        posts = []

        class H(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def reply(self, body, cut=False, status=200):
                self.send_response(status)
                self.send_header("Content-Length",
                                 str(len(body) + (50 if cut else 0)))
                self.end_headers()
                self.wfile.write(body)
                if cut:
                    self.wfile.flush()
                    self.close_connection = True

            def do_GET(self):
                self.reply(b'{"values": [], "isLastPage": true}')

            def do_POST(self):
                self.rfile.read(int(self.headers["Content-Length"]))
                posts.append(1)
                if len(posts) == 1:
                    self.reply(b'{"id": 50}')
                else:
                    self.reply(second or b'{"id":', cut=second is None,
                               status=status)

        server = ThreadingHTTPServer(("127.0.0.1", 0), H)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        env = {"BITBUCKET_URL": f"http://127.0.0.1:{server.server_port}",
               "BITBUCKET_TOKEN": self.TOKEN}
        with tempfile.TemporaryDirectory() as tmp:
            f = self.findings(Path(tmp) / "f.json")
            data = json.loads(Path(f).read_text(encoding="utf-8"))
            data["comments"].append(dict(data["comments"][0], line=30,
                                         text="second finding"))
            Path(f).write_text(json.dumps(data), encoding="utf-8")
            code, out, err = self.run_cmd(["post", *self.PR, "--findings", f],
                                          env)
        self.assertEqual(code, 5, err)
        self.assertEqual(out["status"], "partial")
        self.assertEqual([p["line"] for p in out["posted"]], [22])
        self.assertIn(expected, out["error"])
        self.assertEqual(len(posts), 2)

    def test_failures_have_their_own_exit_codes(self):
        env, state = self.serve()
        with tempfile.TemporaryDirectory() as tmp:
            f = self.findings(Path(tmp) / "f.json")
            post = ["post", *self.PR, "--findings", f]
            self.assertEqual(self.run_cmd(post, {**env, "BITBUCKET_TOKEN": ""})[0], 3)
            self.assertEqual(self.run_cmd(post, {**env, "BITBUCKET_TOKEN": "bad"})[0], 4)
            self.assertEqual(self.run_cmd(post, {"BITBUCKET_TOKEN": "t"})[0], 2)
            self.assertEqual(self.run_cmd(
                post, {"BITBUCKET_TOKEN": "t",
                       "BITBUCKET_URL": "http://bitbucket.example.com"})[0], 2)
            self.assertEqual(self.run_cmd(
                post, {**env, "BITBUCKET_URL": "http://127.0.0.1:1"})[0], 5)
            self.assertEqual(self.run_cmd(
                ["info", "--project", "APP", "--repo", "nope", "--pr", "7"],
                env)[0], 5)
            self.assertEqual(self.run_cmd(
                ["info", "--project", "APP", "--repo", "x", "--pr", "7/x"],
                env)[0], 2)
        self.assertEqual(state.posted, [])

    def test_bad_findings_are_input_errors(self):
        env, state = self.serve()
        with tempfile.TemporaryDirectory() as tmp:
            for name, mutate in {
                    "line type": lambda d: d["comments"][0].update(
                        lineType="REMOVED"),
                    "line": lambda d: d["comments"][0].update(line=0),
                    "text": lambda d: d["comments"][0].update(text=" "),
                    "head": lambda d: d.update(head="main"),
                    "summary": lambda d: d.update(summary=""),
                    "too many": lambda d: d.update(
                        comments=d["comments"] * 16)}.items():
                with self.subTest(name):
                    f = Path(tmp) / "f.json"
                    self.findings(f)
                    data = json.loads(f.read_text("utf-8"))
                    mutate(data)
                    f.write_text(json.dumps(data), encoding="utf-8")
                    code, _, err = self.run_cmd(
                        ["post", *self.PR, "--findings", str(f)], env)
                    self.assertEqual(code, 2, err)
        self.assertEqual(state.posted, [])


if __name__ == "__main__":
    unittest.main()
