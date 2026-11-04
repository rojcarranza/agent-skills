"""Every skill in skills/ against the Agent Skills spec (agentskills.io) and
this repo's publishing rules. An agent silently skips a SKILL.md whose
frontmatter breaks the spec, so these fail loudly instead.

  python3 -m unittest test_skills -v
"""
import ast
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
             "allowed-tools", "argument-hint"}
# Every description loads into every session, so it stays short (the spec
# allows 1024).
DESCRIPTION_CAP = 700
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

    def test_description_is_short_and_third_person(self):
        """Best practice: a description loads in every session, so it stays
        under DESCRIPTION_CAP and speaks about the user, never to them."""
        for d, fm, _ in self.each():
            desc = fm["description"]
            self.assertLessEqual(len(desc), DESCRIPTION_CAP)
            # Quoted triggers and skill names (roj-explain-my-branch) are
            # not second-person prose.
            prose = re.sub(r'"[^"]*"', "", desc)
            prose = re.sub(r"\broj-[a-z-]+", "", prose)
            self.assertNotRegex(prose, r"(?i)\b(you|your|I|my)\b")

    def test_argument_hint(self):
        """Every skill takes input (a PR, a file, a story), so each hints at
        it in the slash-command menu."""
        for d, fm, _ in self.each():
            hint = fm.get("argument-hint", "")
            self.assertTrue(hint, "add argument-hint")
            self.assertLessEqual(len(hint), 80)

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


def declared(fm, key):
    """A metadata comma list, as cali doctor splits it."""
    raw = (fm.get("metadata") or {}).get(key, "")
    return [v.strip() for v in raw.split(",") if v.strip()]


def required_env_reads(script):
    """Variables a script reads from the environment with no default:
    os.getenv("X") or getenv("X"), os.environ["X"], and .get("X") on
    os.environ or on an `env` mapping passed in its place (bitbucket_pr.py's
    main(env=...)). Setting or deleting a variable is not a read."""
    def is_env(node):
        name = node.attr if isinstance(node, ast.Attribute) else getattr(
            node, "id", "")
        return name in ("environ", "env")

    found = set()
    for node in ast.walk(ast.parse(script.read_text(encoding="utf-8"))):
        if (isinstance(node, ast.Subscript) and is_env(node.value)
                and isinstance(node.ctx, ast.Load)):
            key = node.slice
        elif (isinstance(node, ast.Call)
              and (getattr(node.func, "id", "") == "getenv"
                   or (isinstance(node.func, ast.Attribute)
                       and (node.func.attr == "getenv" or (
                           node.func.attr == "get"
                           and is_env(node.func.value)))))
              and len(node.args) == 1 and not node.keywords):
            key = node.args[0]
        else:
            continue
        if isinstance(key, ast.Constant) and isinstance(key.value, str):
            found.add(key.value)
    return found


class TestDeclaredNeeds(SkillTest):
    """Issue #97: each skill declares what it needs in metadata.cali-env (the
    variables it reads that have no default) and metadata.cali-tools (the
    programs it runs). `cali doctor` warns on an unset variable or a program
    missing from PATH, so a wrong declaration warns about the wrong thing."""

    ENV_RE = re.compile(r"^[A-Z_][A-Z0-9_]*$")
    TOOL_RE = re.compile(r"^[\w.-]+(\|[\w.-]+)*$")

    @staticmethod
    def texts(d, body):
        """What the skill tells the agent and what its scripts run. The body,
        not the frontmatter, so a declaration never vouches for itself."""
        files = [*sorted((d / "references").glob("*.md")),
                 *sorted((d / "scripts").glob("*.py"))]
        return "\n".join([body] + [f.read_text(encoding="utf-8")
                                   for f in files])

    def test_scripts_read_only_declared_variables(self):
        for d, fm, _ in self.each():
            env = set(declared(fm, "cali-env"))
            for script in sorted((d / "scripts").glob("*.py")):
                for var in sorted(required_env_reads(script)):
                    with self.subTest(script=script.name, var=var):
                        self.assertIn(var, env, f"{script.name} reads {var}: "
                                      "add it to metadata.cali-env")

    def test_declared_variables_are_used(self):
        for d, fm, body in self.each():
            text = self.texts(d, body)
            for var in declared(fm, "cali-env"):
                with self.subTest(var=var):
                    self.assertRegex(var, self.ENV_RE)
                    self.assertRegex(text, rf"(?<!\w){var}(?!\w)",
                                     f"{d.name} never names {var}")

    def test_declared_tools_are_run(self):
        """An entry's program is run as a command: `git diff ...` in prose,
        or a code line starting with it. Doctor passes an entry when any of
        its alternatives is on PATH, so one of them being run is enough."""
        for d, fm, body in self.each():
            text = self.texts(d, body)
            for entry in declared(fm, "cali-tools"):
                with self.subTest(entry=entry):
                    self.assertRegex(entry, self.TOOL_RE)
                    self.assertTrue(any(
                        re.search(rf"(?m)(?:`|^\s*){re.escape(t)}[ `]", text)
                        for t in entry.split("|")),
                        f"{d.name} never runs {entry}")

    def test_python_is_declared_by_either_name(self):
        """Issue #97: Python is `python` on Windows and `python3` in WSL and
        Linux, so doctor must accept either: write python3|python."""
        for d, fm, _ in self.each():
            for entry in declared(fm, "cali-tools"):
                if {"python", "python3"} & set(entry.split("|")):
                    with self.subTest(entry=entry):
                        self.assertEqual(entry, "python3|python")


class TestGraphFirst(unittest.TestCase):
    """Skills that read code ask a graphify graph first when the repo has
    one (references/graph-first.md)."""

    USES_GRAPH = ("roj-onboard-repo", "roj-explain-logic",
                  "roj-explain-my-branch", "roj-review-code",
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
        text = (SKILLS / "roj-review-code" / "references"
                / "graph-first.md").read_text("utf-8")
        for needle in self.COMMANDS + ("graphify-out/graph.json",
                                       "--budget", "INFERRED"):
            with self.subTest(needle):
                self.assertIn(needle, text)

    def test_graph_is_read_only(self):
        text = (SKILLS / "roj-review-code" / "references"
                / "graph-first.md").read_text("utf-8")
        self.assertIn("Built from commit:", text)
        self.assertIn("Never run `graphify update`", text)

    def test_command_rules_allow_the_graph_queries(self):
        # Skills whose rules list allowed commands must also allow the
        # read-only queries, or the graph step cannot run there.
        for name in ("roj-onboard-repo", "roj-explain-my-branch",
                     "roj-review-code", "roj-review-pr-comment"):
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
        text = (SKILLS / "roj-review-code" / "references"
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

    def test_index_html_pins_one_mermaid_script(self):
        page = (self.ONBOARD / "references" / "html-page.md").read_text("utf-8")
        urls = set(re.findall(r"https://cdn\.jsdelivr\.net/[^\s\"'),`]+", page))
        self.assertEqual(len(urls), 1, urls)
        self.assertRegex(next(iter(urls)), r"/npm/mermaid@\d+\.\d+\.\d+/")
        # SKILL.md carries the same pinned tag, for a run that cannot open
        # references/html-page.md.
        tag = re.search(r'<script src="(https://cdn\.jsdelivr\.net[^"]*)"\s+'
                        r'integrity="([^"]*)"', page)
        skill = (self.ONBOARD / "SKILL.md").read_text("utf-8")
        self.assertIn(f'src="{tag.group(1)}" integrity="{tag.group(2)}"', skill)


class TestReviewModes(unittest.TestCase):
    """roj-review-code absorbed the fast review as its quick mode, and the
    skills that read a branch diff ship the shared base resolution."""

    def test_fast_skill_is_gone(self):
        self.assertFalse((SKILLS / "roj-code-review-pr-fast").exists())
        self.assertFalse((ROOT / "evals" / "roj-code-review-pr-fast").exists())

    def test_diff_reading_skills_ship_base_resolution(self):
        for name in ("roj-review-code", "roj-explain-logic",
                     "roj-explain-my-branch"):
            with self.subTest(name):
                self.assertTrue((SKILLS / name / "references" /
                                 "base-resolution.md").is_file())


class TestRepoMap(unittest.TestCase):
    """The PR skills read the .onboarding/ map roj-onboard-repo writes. The
    map orients and never counts as evidence, and an untracked guide is never
    reviewed as if it were the change."""

    OWNER = SKILLS / "roj-review-code" / "references" / "repo-map.md"
    CONSUMERS = ("roj-review-code", "roj-explain-logic",
                 "roj-review-pr-comment", "roj-explain-my-branch")
    OUTPUT_DIRS = (".onboarding/", ".pr-review/")

    def test_every_consumer_names_the_reference_and_ships_it(self):
        for name in self.CONSUMERS:
            with self.subTest(skill=name):
                skill = SKILLS / name
                self.assertIn("references/repo-map.md",
                              (skill / "SKILL.md").read_text("utf-8"))
                self.assertEqual((skill / "references" / "repo-map.md")
                                 .read_text("utf-8"),
                                 self.OWNER.read_text("utf-8"))

    def test_reference_states_the_freshness_states_and_the_authority_rule(self):
        flat = " ".join(self.OWNER.read_text("utf-8").split())
        for state in ("(fresh)", "(<n> commits behind)",
                      "(stale, 50+ commits behind)", "(unknown commit)"):
            self.assertIn(state, flat)
        self.assertIn("git log --oneline --max-count=51 <sha>..<base>", flat)
        self.assertIn("The code decides", flat)
        self.assertIn("Never cite the map as evidence", flat)
        self.assertIn("never reads the map", flat)       # quick mode

    def test_review_skill_keeps_agent_output_folders_out_of_the_change(self):
        for rel in ("SKILL.md", "references/full-review.md"):
            text = (SKILLS / "roj-review-code" / rel).read_text("utf-8")
            flat = " ".join(text.split())
            for folder in self.OUTPUT_DIRS:
                with self.subTest(file=rel, folder=folder):
                    self.assertIn(folder, flat)

    def test_reference_commands_stay_inside_each_skills_allowed_tools(self):
        """The two commands the reference runs must pass the review skills'
        allow-lists, so reading the map never triggers an approval stop."""
        for name in ("roj-review-code", "roj-review-pr-comment"):
            fm, _ = frontmatter((SKILLS / name / "SKILL.md").read_text("utf-8"))
            tools = fm["allowed-tools"]
            with self.subTest(skill=name):
                self.assertIn("Bash(git log *)", tools)
                self.assertIn("Bash(git diff *)", tools)
                self.assertIn("Bash(git rev-parse *)", tools)


class TestImprovementPass(unittest.TestCase):
    """`improve` is an opt-in axis of the two review skills: non-blocking
    suggestions kept apart from the defects, under hard evidence rules. The
    full review report lives in .pr-review/pr-<n>/review.md, where the comment
    skill finds it for the same head instead of reviewing twice."""

    REVIEW = SKILLS / "roj-review-code"
    COMMENT = SKILLS / "roj-review-pr-comment"
    OWNER = REVIEW / "references" / "improvement-pass.md"

    def flat(self, path):
        return " ".join(path.read_text("utf-8").split())

    def test_both_review_skills_name_the_pass_and_ship_the_same_copy(self):
        for skill in (self.REVIEW, self.COMMENT):
            with self.subTest(skill=skill.name):
                self.assertIn("references/improvement-pass.md",
                              (skill / "SKILL.md").read_text("utf-8"))
                self.assertEqual(
                    (skill / "references" / "improvement-pass.md")
                    .read_text("utf-8"), self.OWNER.read_text("utf-8"))

    def test_skills_that_never_suggest_do_not_ship_the_pass(self):
        for name in ("roj-explain-logic", "roj-explain-my-branch",
                     "roj-onboard-repo"):
            with self.subTest(skill=name):
                self.assertFalse((SKILLS / name / "references" /
                                  "improvement-pass.md").exists())

    def test_pass_states_the_lenses_the_seven_rules_and_the_caps(self):
        text = self.OWNER.read_text("utf-8")
        flat = " ".join(text.split())
        for lens in ("Reuse", "Simplify", "Clarity", "Convention"):
            self.assertRegex(text, re.compile(rf"^\| {lens} \|", re.M),
                             f"lens {lens}")
        rules = re.search(r"## Evidence rules\n(.*?)\n## ", text, re.S).group(1)
        self.assertEqual(re.findall(r"^(\d)\. ", rules, re.M),
                         list("1234567"))
        for phrase in ("Cost of leaving it", "Same behaviour because",
                       "at most 6 lines", "Confirmed or Probable",
                       "at most 3 suggestions", "never counted toward the",
                       "at most 5 inline suggestions plus 3 more",
                       "The verdict ignores suggestions",
                       "With a Blocker among the defects, chat shows no "
                       "suggestion at all", "the report file holds them in "
                       "full", "Sort once, never both",
                       "never Bitbucket tasks", "Default **off**"):
            self.assertIn(phrase, flat)

    def test_pass_runs_only_after_the_defects_are_final(self):
        flat = self.flat(self.OWNER)
        self.assertIn("After the verification pass and the failure-scenario "
                      "rule, never before", flat)
        self.assertIn("Pre-existing code is not a suggestion target", flat)

    def test_method_skeleton_keeps_suggestions_out_of_the_verdict(self):
        text = (self.REVIEW / "references" / "review-method.md"
                ).read_text("utf-8")
        skeleton = text[text.index("## Output skeleton"):]
        self.assertIn("### Improvements (non-blocking)", skeleton)
        self.assertIn("head `<sha12>`", skeleton)
        self.assertIn("improve: on | off \u00b7 suggestions: <n>", skeleton)
        flat = " ".join(skeleton.split())
        self.assertIn("The verdict counts defects only", flat)
        # Improvements sit after Tests and before Needs your input.
        self.assertLess(skeleton.index("### Tests"),
                        skeleton.index("### Improvements (non-blocking)"))
        self.assertLess(skeleton.index("### Improvements (non-blocking)"),
                        skeleton.index("### Needs your input"))

    def test_description_budget_and_the_improve_word(self):
        for skill in (self.REVIEW, self.COMMENT):
            fm, _ = frontmatter((skill / "SKILL.md").read_text("utf-8"))
            with self.subTest(skill=skill.name):
                self.assertLessEqual(len(fm["description"]), 1024)
                self.assertIn("improve", fm["description"])

    def test_report_moved_into_the_pr_folder(self):
        full = self.flat(self.REVIEW / "references" / "full-review.md")
        self.assertIn(".pr-review/pr-<id>/review.md", full)
        self.assertIn(".pr-review/branch-<slug>/review.md", full)
        self.assertIn("never run it and never edit `.gitignore`", full)
        self.assertNotIn("Write the report to `<branch-slug>-review.md`",
                         full)
        usage = self.flat(self.REVIEW / "USAGE.md")
        self.assertIn(".pr-review/pr-<id>/review.md", usage)

    def test_comment_skill_reuses_a_review_of_the_same_head(self):
        flat = self.flat(self.COMMENT / "SKILL.md")
        for phrase in ("Findings reused from review.md @ <head12>",
                       ".pr-review/pr-<id>/review.md",
                       "equal the first 12 of `<head>`",
                       "do not run a second review",
                       "Report no finding that is not in the file",
                       "Re-validate each candidate against the `-U3` diff"):
            self.assertIn(phrase, flat)

    def test_fixtures_for_the_improve_evals_exist(self):
        kinds = TestEvals().fixture_kinds()
        self.assertGreaterEqual(
            kinds, {"pyrepo-bb-pr-dup", "pyrepo-bb-pr-review",
                    "pyrepo-bb-pr-review-old", "pyrepo-dirty-dup"})


class TestPrReviewDefaults(unittest.TestCase):
    """A colleague's PR (a Bitbucket URL or id) gets a full review with
    suggestions and paste-ready comments by default, Ansible is a risk path,
    and the exact output shape sits at the top of SKILL.md, where a small
    model reads it before it reviews."""

    def test_skill_md_stays_short_enough_for_a_small_model(self):
        text = (SKILLS / "roj-review-code" / "SKILL.md").read_text("utf-8")
        self.assertLess(len(text.splitlines()), 300)

    def test_evals_cover_the_defaults_and_the_ansible_fixtures(self):
        data = json.loads((ROOT / "evals" / "roj-review-code"
                           / "evals.json").read_text("utf-8"))
        fixtures = {e["fixture"]["repo"] for e in data["evals"]}
        self.assertGreaterEqual(fixtures, {"ansible", "ansible-bb-pr"})
        prompts = " ".join(e["prompt"] for e in data["evals"])
        self.assertIn("no suggestions", prompts)


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

    @staticmethod
    def section(text, heading, level="##"):
        """The body under `heading` up to the next heading of that level."""
        match = re.search(rf"(?ms)^{level} {re.escape(heading)}\n(.*?)"
                          rf"(?=^{level} |\Z)", text)
        return match.group(1) if match else None

    def test_template_puts_the_plan_before_core_tasks(self):
        """Issue #94, the captain's answer in SCR-15: the Implementation plan
        sits between Acceptance Criteria and Core tasks and holds the
        approach, the task flow and the change flow."""
        template = (self.SB / "assets" / "SB-template.md").read_text("utf-8")
        heads = self.headings(template)
        at = heads.index("Implementation plan")
        self.assertEqual(heads[at - 1:at + 2],
                         ["Acceptance Criteria", "Implementation plan",
                          "Core tasks"])
        plan = self.section(template, "Implementation plan")
        self.assertEqual(re.findall(r"(?m)^### (.+)$", plan),
                         ["Approach", "Task flow", "Change flow"])

    def test_example_plan_draws_both_flows(self):
        """Issue #94: the example the model copies carries a task flow and a
        change flow, and the task flow's nodes are the SB's own tasks and
        questions: `Tn` is the n-th Core tasks checkbox, which is how the
        implement flow (references/implementation-plan.md) reads it."""
        example = (self.SB / "examples" / "SB-PROJ-1001.md").read_text("utf-8")
        plan = self.section(example, "Implementation plan")
        task_flow = MERMAID_RE.findall(self.section(plan, "Task flow", "###"))
        change = MERMAID_RE.findall(self.section(plan, "Change flow", "###"))
        self.assertEqual([b.split(None, 1)[0] for b in task_flow],
                         ["flowchart"])
        self.assertEqual([b.split(None, 1)[0] for b in change],
                         ["sequenceDiagram"])
        tasks = re.findall(r"(?m)^- \[[ x]\] ",
                           self.section(example, "Core tasks"))
        questions = re.findall(r"(?m)^- ", self.section(example, "Questions"))
        nodes = set(re.findall(r'\b([TQ])(\d+)\["\1\2 ', task_flow[0]))
        self.assertEqual(sorted(int(n) for k, n in nodes if k == "T"),
                         list(range(1, len(tasks) + 1)))
        self.assertLessEqual({int(n) for k, n in nodes if k == "Q"},
                             set(range(1, len(questions) + 1)))

    def test_example_draft_approach_carries_the_marker(self):
        """Issue #94, answer 4: an approach the agent drafted is marked, and
        the implement flow asks about it by that marker, so the example must
        carry the marker exactly as the reference defines it."""
        ref = (self.SB / "references" / "implementation-plan.md").read_text(
            "utf-8")
        marker = re.search(r"```text\n\s*(> \*\*Draft:\*\*.*)\n", ref).group(1)
        example = (self.SB / "examples" / "SB-PROJ-1001.md").read_text("utf-8")
        approach = self.section(self.section(example, "Implementation plan"),
                                "Approach", "###")
        self.assertEqual(approach.strip().splitlines()[0], marker)

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
                    self.assertTrue((dest / "repo" / ".git").is_dir())

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


class TestPrBrief(unittest.TestCase):
    """roj-explain-logic writes .pr-review/pr-<n>/brief.md and brief.html for
    a PR. The page check is html-page.md's, the brief check is pr-brief.md's;
    both are run here exactly as the skill ships them."""

    EXPLAIN = SKILLS / "roj-explain-logic"
    ONBOARD = TestOnboardRepoGuide.ONBOARD
    script = TestOnboardRepoGuide.script
    run_script = TestOnboardRepoGuide.run_script
    DIAGRAM = """sequenceDiagram
  autonumber
  actor U as user
  participant A as agent
  participant S as script
  U->>A: review PR 7
  rect rgba(0,180,0,0.12)
  A->>S: + info, read
  end
  rect rgba(255,190,0,0.15)
  S->>A: ~ fetch the head, inferred
  end
  rect rgba(220,0,0,0.12)
  Note over A,S: - removed: gh pr diff, read
  end"""
    BRIEF = (
        "# PR brief: x (PR 7)\n\n"
        "> Built from head `0123456789ab` vs `origin/develop` @ `abcdef0` "
        "(2026-10-26, target `develop`). Every claim cites `path:line`.\n"
        "> Intent: commit messages.\n\n"
        "## 1. What this PR does\n\nIt retries.\n\n"
        "## 2. Where it sits\n\nThe app.\n\n"
        "## 3. Flow diff\n\n```mermaid\n{diagram}\n```\n\n"
        "- 2 \u00b7 `a.py:2` \u00b7 info\n\n"
        "## 4. Files\n\n| File | Role | Change |\n| --- | --- | --- |\n"
        "| `a.py` | code | changed |\n\n"
        "## 5. Walkthrough\n\nSteps.\n\n## 6. Reading order\n\n1. `a.py:1`\n\n"
        "## 7. Questions for the author, and what was not checked\n\n"
        "1. [?] Why?\n\nNot checked: a live server.\n")

    def brief_script(self):
        text = (self.EXPLAIN / "references" / "pr-brief.md").read_text("utf-8")
        tail = text[text.index("`check-brief.py`:"):]
        return re.search(r"```python\n(.*?)\n```", tail, re.S).group(1)

    def page_script(self):
        text = (self.EXPLAIN / "references" / "html-page.md").read_text("utf-8")
        tail = text[text.index("`check-html.py`:"):]
        return re.search(r"```python\n(.*?)\n```", tail, re.S).group(1)

    def build(self, tmp, brief=None):
        """A repo folder holding a.py and .pr-review/pr-7/brief.md."""
        root = Path(tmp)
        (root / "a.py").write_text("one\ntwo\nthree\n", "utf-8")
        d = root / ".pr-review" / "pr-7"
        d.mkdir(parents=True)
        (d / "brief.md").write_text(
            brief or self.BRIEF.format(diagram=self.DIAGRAM), "utf-8")
        return root, d

    def check(self, root, d, *flags):
        return self.run_script(self.brief_script(), *flags, root, d / "brief.md")

    def test_brief_check_passes_a_good_brief(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, d = self.build(tmp)
            run = self.check(root, d)
            self.assertEqual(run.returncode, 0, run.stdout + run.stderr)

    @unittest.skipUnless(shutil.which("git"), "needs git")
    def test_brief_check_reads_the_head_not_the_working_tree(self):
        """A PR is not checked out: anchors resolve against `--rev`."""
        git = ["git", "-c", "user.name=Dev", "-c", "user.email=dev@example.com"]
        with tempfile.TemporaryDirectory() as tmp:
            root, d = self.build(tmp)
            subprocess.run([*git, "init", "-q", str(root)], check=True)
            subprocess.run([*git, "-C", str(root), "add", "a.py"], check=True)
            subprocess.run([*git, "-C", str(root), "commit", "-qm", "x"],
                           check=True)
            (root / "a.py").write_text("one\n", "utf-8")  # working tree moved on
            head = subprocess.run(
                ["git", "-C", str(root), "rev-parse", "HEAD"],
                capture_output=True, text=True, check=True).stdout.strip()
            self.assertEqual(self.check(root, d, "--rev", head).returncode, 0)
            bad = self.check(root, d)
            self.assertEqual(bad.returncode, 1)
            self.assertIn("a.py:2", bad.stdout)

    def test_brief_check_catches_each_rule(self):
        good = self.BRIEF.format(diagram=self.DIAGRAM)
        no_rect = good
        for line in ("  rect rgba(0,180,0,0.12)\n", "  rect rgba(255,190,0,0.15)\n",
                     "  rect rgba(220,0,0,0.12)\n", "  end\n"):
            no_rect = no_rect.replace(line, "")
        cases = {
            "bad anchor": (good.replace("`a.py:2`", "`a.py:9`"),
                           "bad anchor a.py:9"),
            "section missing": (good.replace("## 6. ", "## 8. "),
                                "sections 1 to 7"),
            "header missing": (good.replace("> Built from head", "> From"),
                               "header line missing"),
            "untagged step": (good.replace("+ info, read", "info"),
                              "needs a +, ~ or - tag"),
            "no tier word": (good.replace("+ info, read", "+ info"),
                             "needs a +, ~ or - tag"),
            "no rect": (no_rect, "no rect block"),
            "emoji": (good.replace("+ info, read", "+ \U0001F7E2 info, read"),
                      "emoji"),
            "no-flow-change with a diagram": (good.replace(
                "## 3. Flow diff\n\n", "## 3. Flow diff\n\n**No flow change.** x\n\n"),
                                              "no-flow-change brief has a diagram"),
        }
        for name, (brief, message) in cases.items():
            with self.subTest(case=name), tempfile.TemporaryDirectory() as tmp:
                root, d = self.build(tmp, brief)
                run = self.check(root, d)
                self.assertEqual(run.returncode, 1, run.stdout)
                self.assertIn(message, run.stdout)

    def test_brief_check_enforces_the_diagram_caps(self):
        many = "\n".join(f"  A->>S: + step {i}, read" for i in range(12))
        peers = "\n".join(f"  participant P{i} as p{i}" for i in range(4))
        for name, diagram, message in (
            ("13 steps", self.DIAGRAM.replace(
                "  rect rgba(0,180,0,0.12)\n", "  rect rgba(0,180,0,0.12)\n" + many + "\n"),
             "steps, the cap is 12"),
            ("6 participants", self.DIAGRAM.replace(
                "  U->>A", peers + "\n  U->>A"), "participants, the cap is 5"),
        ):
            with self.subTest(case=name), tempfile.TemporaryDirectory() as tmp:
                root, d = self.build(tmp, self.BRIEF.format(diagram=diagram))
                run = self.check(root, d)
                self.assertEqual(run.returncode, 1, run.stdout)
                self.assertIn(message, run.stdout)

    def test_no_flow_change_brief_passes_without_a_diagram(self):
        head, rest = self.BRIEF.split("## 3. Flow diff")
        tail = rest[rest.index("## 4. Files"):]
        brief = head + "## 3. Flow diff\n\n**No flow change.** Docs only.\n\n" + tail
        with tempfile.TemporaryDirectory() as tmp:
            root, d = self.build(tmp, brief)
            run = self.check(root, d)
            self.assertEqual(run.returncode, 0, run.stdout)

    def build_page(self, d, diagram):
        src = diagram.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        (d / "brief.html").write_text(
            '<html><body><div id="mermaid-banner"></div>'
            + "".join(f"<h3>{h}</h3>" for h in re.findall(
                r"^## (.+)$", (d / "brief.md").read_text("utf-8"), re.M))
            + '<figure class="diagram"><p class="diagram-note">n</p>'
            f'<pre class="diagram-src">{src}</pre></figure>'
            '<code class="ref">a.py:2</code><code class="ref">a.py:1</code>'
            '<script src="https://cdn.jsdelivr.net/npm/mermaid@11.12.0/dist/'
            'mermaid.min.js"></script></body></html>', "utf-8")

    def test_page_check_takes_a_page_name_and_ignores_other_markdown(self):
        code = self.page_script()
        with tempfile.TemporaryDirectory() as tmp:
            root, d = self.build(tmp)
            self.build_page(d, self.DIAGRAM)
            (d / "review.md").write_text(
                "## Extra\n\n```mermaid\nflowchart TD\n  a --> b\n```\n"
                "`other.py:3`\n", "utf-8")
            run = self.run_script(code, d, "brief.html")
            self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
        with tempfile.TemporaryDirectory() as tmp:
            root, d = self.build(tmp)
            self.build_page(d, self.DIAGRAM + "\n  A->>S: + more, read")
            bad = self.run_script(code, d, "brief.html")
            self.assertEqual(bad.returncode, 1)
            self.assertIn("diagrams differ", bad.stdout)

    def test_onboarding_copy_of_the_page_script_is_the_shared_one(self):
        self.assertEqual(
            self.page_script(), self.script("html-page.md", "check-html.py"))

    def test_skill_names_reference_files_that_exist(self):
        body = (self.EXPLAIN / "SKILL.md").read_text("utf-8")
        for name in set(re.findall(r"references/([\w.-]+\.md)", body)):
            with self.subTest(name=name):
                self.assertTrue((self.EXPLAIN / "references" / name).is_file())


STOPWORDS = frozenset("""a an and any are as at be by do does for from has have
how i if in into what who why whom is it its my no not of on one or our so that the their them
then this to use used user users using want when which with you your""".split())

# Trigger phrases a user really types, per skill. Each must route to the
# owner and not to a sibling: the owner's description must score strictly
# highest. Add a row when a description changes or two skills start to blur.
ROUTES = {
    "roj-review-code": [
        "review my pull request before I merge",
        "do a code review of this branch and find defects",
        "quick review of my uncommitted changes",
        "review PR 42 and suggest improvements",
    ],
    "roj-review-pr-comment": [
        "review PR 123 and comment on it",
        "post a review on this PR",
        "review this Bitbucket pull request URL and leave inline comments",
        "review PR 42 and comment, include improvement suggestions",
    ],
    "roj-explain-logic": [
        "explain this function line by line",
        "walk me through how this code flow works",
        "what does this method do and who calls it",
        "explain this pull request and draw how the change flows",
    ],
    "roj-explain-my-branch": [
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
    "roj-one-slide": [
        "make a demo slide for this story",
        "build one slide for the sprint review",
        "a one slide PowerPoint of the story I finished",
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


try:
    import pptx  # noqa: F401
    HAVE_PPTX = True
except ImportError:
    HAVE_PPTX = False


@unittest.skipUnless(HAVE_PPTX, "needs python-pptx")
class TestOneSlideScript(unittest.TestCase):
    """build_slide.py puts exactly one slide on the user's template, leaves
    the template alone and refuses a spec that would overflow the slide."""

    SCRIPT = SKILLS / "roj-one-slide" / "scripts" / "build_slide.py"
    SECTIONS = {
        "key": "PROJ-1", "link": "https://jira.example.com/browse/PROJ-1",
        "title": "Add retries", "presenter": "Alex", "date": "2026-10-30",
        "body": {"kind": "sections", "goal": "Survive flaky uploads",
                 "sections": [{"heading": "Next", "points": "tune backoff"}]}}
    BEFORE_AFTER = {
        "key": "PROJ-2", "title": "Move to 3.12", "date": "2026-10-30",
        "body": {"kind": "before_after", "goal": "Stay on a supported runtime",
                 "before": {"stages": [{"caption": "build", "items": ["3.10"]},
                                       [{"items": ["DEPLOY"]}]]},
                 "after": {"stages": [{"caption": "build", "items": ["3.12"]},
                                      [{"items": ["DEPLOY"]}]]}}}

    def setUp(self):
        from pptx import Presentation
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp)
        prs = Presentation()
        for _ in range(2):  # a deck in use, not an empty template
            prs.slides.add_slide(prs.slide_layouts[1]).shapes.title.text = "old"
        self.template = self.tmp / "team.pptx"
        prs.save(str(self.template))
        self.template_bytes = self.template.read_bytes()

    def team_deck(self, width=12192000, title_pt=28, body_pt=18):
        """A deck with a team's sizes, unlike python-pptx's default 44/32pt."""
        from pptx import Presentation
        prs = Presentation()
        prs.slide_width = width
        master = prs.slide_master
        margin = 838200 if width > 9144000 else 457200  # as Office's own decks
        for ph in master.placeholders:
            if ph.placeholder_format.idx in (0, 1):
                ph.left, ph.width = margin, width - 2 * margin
        self.set_text_sizes(master, title_pt, body_pt)
        return prs

    @staticmethod
    def set_text_sizes(master, title_pt, body_pt):
        from pptx.oxml.ns import qn
        styles = master._element.find(qn("p:txStyles"))
        for style, pt in (("p:titleStyle", title_pt), ("p:bodyStyle", body_pt)):
            styles.find(qn(style)).find(qn("a:lvl1pPr")).find(
                qn("a:defRPr")).set("sz", str(pt * 100))

    def save_deck(self, prs, name="deck.pptx"):
        path = self.tmp / name
        prs.save(str(path))
        return path

    def add_second_master(self, prs, layout_name):
        """Copy the deck's master, theme and "Title and Content" layout into
        a second master, as pasting slides from another deck does."""
        from lxml import etree
        from pptx.opc.constants import RELATIONSHIP_TYPE as RT
        from pptx.opc.package import Part
        from pptx.opc.packuri import PackURI
        from pptx.oxml.ns import qn
        from pptx.parts.slide import SlideLayoutPart, SlideMasterPart
        package = prs.part.package
        old_master = prs.slide_master.part
        old_layout = prs.slide_layouts[1].part
        old_theme = old_master.part_related_by(RT.THEME)
        theme = etree.fromstring(old_theme.blob)
        dk2 = theme.find(".//" + qn("a:dk2"))[0]
        dk2.getparent().replace(dk2, etree.Element(
            qn("a:srgbClr"), val="FFFF00"))
        new_theme = Part(PackURI("/ppt/theme/theme2.xml"),
                         old_theme.content_type, package, etree.tostring(theme))
        master = SlideMasterPart.load(
            PackURI("/ppt/slideMasters/slideMaster2.xml"),
            old_master.content_type, package, old_master.blob)
        layout = SlideLayoutPart.load(
            PackURI("/ppt/slideLayouts/slideLayout12.xml"),
            old_layout.content_type, package, old_layout.blob)
        layout._element.cSld.set("name", layout_name)
        layout.relate_to(master, RT.SLIDE_MASTER)
        master.relate_to(new_theme, RT.THEME)
        id_list = master._element.find(qn("p:sldLayoutIdLst"))
        for child in list(id_list):
            id_list.remove(child)
        etree.SubElement(id_list, qn("p:sldLayoutId"), {
            "id": "2147483800",
            qn("r:id"): master.relate_to(layout, RT.SLIDE_LAYOUT)})
        etree.SubElement(prs.part._element.find(qn("p:sldMasterIdLst")),
                         qn("p:sldMasterId"), {
            "id": "2147483801", qn("r:id"): prs.part.relate_to(
                master, RT.SLIDE_MASTER)})
        return prs.slide_masters[1]

    def build(self, spec, template=None):
        spec_path, out = self.tmp / "spec.json", self.tmp / "out.pptx"
        spec_path.write_text(
            spec if isinstance(spec, str) else json.dumps(spec), "utf-8")
        run = subprocess.run(
            [sys.executable, str(self.SCRIPT), "--template",
             str(template or self.template), "--spec", str(spec_path),
             "--out", str(out)], capture_output=True, text=True)
        return run, out

    def shapes(self, out):
        """Every shape on the one slide, groups opened up."""
        from pptx import Presentation
        prs = Presentation(str(out))
        self.assertEqual(len(prs.slides), 1)
        slide, found, todo = prs.slides[0], [], list(prs.slides[0].shapes)
        while todo:
            shape = todo.pop(0)
            found.append(shape)
            if shape.shape_type == 6:  # group
                todo += list(shape.shapes)
        return slide, found

    def texts(self, out):
        slide, shapes = self.shapes(out)
        return slide, [s.text_frame.text for s in shapes if s.has_text_frame]

    def test_sections_slide(self):
        run, out = self.build(self.SECTIONS)
        self.assertEqual(run.returncode, 0, run.stderr)
        slide, texts = self.texts(out)
        title = slide.shapes.title.text_frame.paragraphs[0].runs
        self.assertEqual(title[0].text, "PROJ-1")
        self.assertEqual(title[0].hyperlink.address, self.SECTIONS["link"])
        joined = "\n".join(texts)
        for want in ("Goal:", "Survive flaky uploads", "Next: tune backoff",
                     "Presented by:\u00a0Alex", "October 30, 2026"):
            self.assertIn(want, joined)
        self.assertNotIn("old", texts)
        self.assertEqual(self.template.read_bytes(), self.template_bytes)

    def test_before_after_slide(self):
        run, out = self.build(self.BEFORE_AFTER)
        self.assertEqual(run.returncode, 0, run.stderr)
        _, texts = self.texts(out)
        for want in ("Before", "After", "3.10", "3.12", "DEPLOY", "build"):
            self.assertIn(want, texts)

    def test_diagram_stays_editable(self):
        """Native shapes in one group per box and arrows glued to the boxes,
        so moving a box in PowerPoint drags its arrows; never a picture."""
        run, out = self.build(self.BEFORE_AFTER)
        self.assertEqual(run.returncode, 0, run.stderr)
        slide, shapes = self.shapes(out)
        self.assertFalse([s for s in shapes if s.shape_type == 13])
        self.assertTrue([s for s in slide.shapes if s.shape_type == 6])
        ids = {s.shape_id for s in shapes}
        arrows = [s for s in shapes if s.name.startswith("Arrow")]
        self.assertTrue(arrows)
        a = "{http://schemas.openxmlformats.org/drawingml/2006/main}"
        for arrow in arrows:
            for end in ("stCxn", "endCxn"):
                with self.subTest(arrow=arrow.name, end=end):
                    glue = arrow._element.find(f".//{a}{end}")
                    self.assertIsNotNone(glue)
                    self.assertIn(int(glue.get("id")), ids)

    def test_overflow_is_refused_and_nothing_is_written(self):
        spec = json.loads(json.dumps(self.BEFORE_AFTER))
        spec["body"]["goal"] = "word " * 60
        spec["body"]["after"]["stages"][0]["items"] = ["X" * 80]
        run, out = self.build(spec)
        self.assertEqual(run.returncode, 1)
        self.assertIn("goal is longer than one line", run.stderr)
        self.assertIn("too long for its box", run.stderr)
        self.assertFalse(out.exists())

    def test_bundled_examples_build(self):
        """The specs SKILL.md starts from, against references/slide-spec.md,
        on a wide deck and a 10-inch one: a note beside the first stage and
        glued arrows between flow steps. Rejects an example that drifts from
        the schema and a note with no room on a narrow deck."""
        assets = SKILLS / "roj-one-slide" / "assets"
        a = "{http://schemas.openxmlformats.org/drawingml/2006/main}"
        for width in (12192000, 9144000):
            deck = self.save_deck(self.team_deck(width))
            with self.subTest(width=width, example="before-after"):
                spec = json.loads(
                    (assets / "example-before-after.json").read_text("utf-8"))
                run, out = self.build(spec, deck)
                self.assertEqual(run.returncode, 0, run.stderr)
                _, shapes = self.shapes(out)
                notes = {s.name: s.text_frame.text for s in shapes
                         if s.name.startswith("Note")}
                self.assertIn("Removed", notes["Note Before"])
                self.assertIn("Checkout never waits", notes["Note After"])
            with self.subTest(width=width, example="sections"):
                spec = json.loads(
                    (assets / "example-sections.json").read_text("utf-8"))
                run, out = self.build(spec, deck)
                self.assertEqual(run.returncode, 0, run.stderr)
                _, shapes = self.shapes(out)
                boxes = {s.shape_id for s in shapes
                         if s.name.startswith("Step box")}
                arrows = [s for s in shapes if s.name.startswith("Arrow")]
                self.assertEqual(len(boxes), 3)
                self.assertEqual(len(arrows), 2)
                for arrow in arrows:
                    self.assertIn(int(arrow._element.find(
                        f".//{a}stCxn").get("id")), boxes)
                    self.assertIn(int(arrow._element.find(
                        f".//{a}endCxn").get("id")), boxes)

    def test_flow_box_holds_the_lines_its_points_wrap_to(self):
        """Five steps across 16:9 leave 1492790 EMU for text (box width less
        margins and bullet indent), and 'word word word word' at 12pt
        Helvetica is wider than that, so three points take six lines. Rejects
        a box sized as if they took three."""
        spec = json.loads(json.dumps(self.SECTIONS))
        spec["body"]["sections"] = []
        spec["body"]["flow"] = [
            {"title": f"S{i}", "points": ["word word word word"] * 3}
            for i in range(5)]
        run, out = self.build(spec, self.save_deck(self.team_deck()))
        self.assertEqual(run.returncode, 0, run.stderr)
        _, shapes = self.shapes(out)
        box = next(s for s in shapes if s.name.startswith("Step box"))
        text_room = box.height - box.text_frame.margin_top
        self.assertGreaterEqual(text_room / 12700, 6 * 12 * 1.2)

    def test_long_words_and_headings_count_their_wrapped_lines(self):
        for name, change, wanted in (
                ("title", lambda s: s.update(title="x" * 300),
                 "the title wraps"),
                ("point", lambda s: s["body"]["sections"].__setitem__(
                    0, {"heading": "Next", "points": ["x" * 2000]}),
                 "sections run"),
                ("heading", lambda s: s["body"]["sections"].__setitem__(
                    0, {"heading": "x" * 2000, "points": ["short"]}),
                 "sections run")):
            with self.subTest(name):
                spec = json.loads(json.dumps(self.SECTIONS))
                change(spec)
                run, out = self.build(spec, self.save_deck(self.team_deck()))
                self.assertEqual(run.returncode, 1, run.stderr)
                self.assertIn(wanted, run.stderr)
                self.assertFalse(out.exists())

    def test_invalid_specs_are_listed_not_tracebacks(self):
        bad_image = self.tmp / "shot.png"
        bad_image.write_text("not an image", "utf-8")

        def sections(**fields):
            spec = json.loads(json.dumps(self.SECTIONS))
            spec["body"].update(fields)
            return spec

        def stages(stage):
            spec = json.loads(json.dumps(self.BEFORE_AFTER))
            spec["body"]["before"]["stages"] = [stage]
            return spec

        no_goal = {"title": "T", "goal": "top level",
                   "body": {"kind": "sections"}}
        for name, spec, wanted in (
                ("not JSON", "{not json", "cannot read the spec"),
                ("not an object", "[]", "one JSON object"),
                ("no title", {"body": {}}, "title is required"),
                ("date not text", {**self.SECTIONS, "date": 20261030},
                 "date must be text"),
                ("no body", {"title": "T"}, "body is required"),
                ("goal outside body", no_goal, "body.goal is required"),
                ("unknown kind", sections(kind="chart"), "body.kind"),
                ("section without heading",
                 sections(sections=[{"points": ["a"]}]), "needs a heading"),
                ("section without points",
                 sections(sections=[{"heading": "a"}]), "points must be"),
                ("flow step without title",
                 sections(flow=[{"points": ["a"]}, {"title": "b"}]),
                 "needs a title"),
                ("image not found", sections(image="missing.png"), "not found"),
                ("image not a picture", sections(image=str(bad_image)),
                 "cannot be placed"),
                ("item without text", stages({"items": [{"mono": True}]}),
                 "an item is text"),
                ("empty stage", stages([]), "has no boxes"),
                ("stages missing", {**self.BEFORE_AFTER, "body": {
                    "kind": "before_after", "goal": "g"}}, "stages is required"),
                ("too many boxes", stages([{"items": ["a"]}] * 12),
                 "too many boxes"),
                ("note bold not a boolean", {**self.BEFORE_AFTER, "body": {
                    **self.BEFORE_AFTER["body"], "after": {
                        **self.BEFORE_AFTER["body"]["after"],
                        "note": [{"text": "a", "bold": "yes"}]}}},
                 "bold must be true or false"),
                ("control character in a caption",
                 stages({"caption": "a\x0bb", "items": ["c"]}),
                 "control character"),
                ("control character in an item",
                 stages({"items": ["a\x0bb"]}), "control character"),
                ("control character in a flow title",
                 sections(flow=[{"title": "a\x0bb"}, {"title": "c"}]),
                 "control character"),
                ("lone surrogate in the title",
                 {**self.SECTIONS, "title": "a\ud800b"},
                 "control character")):
            with self.subTest(name):
                run, out = self.build(spec)
                self.assertEqual(run.returncode, 1, run.stderr)
                self.assertNotIn("Traceback", run.stderr)
                self.assertIn(wanted, run.stderr)
                self.assertFalse(out.exists())

    def test_null_optional_fields_build_like_absent_ones(self):
        """Pasted ticket text can have no key; key is optional in slide-spec.md."""
        spec = {**self.SECTIONS, "key": None, "link": None, "presenter": None,
                "date": None, "layout": None}
        run, out = self.build(spec)
        self.assertEqual(run.returncode, 0, run.stderr)
        slide, _ = self.shapes(out)
        self.assertEqual(slide.shapes.title.text_frame.text, "Add retries")

    def test_custom_show_deck_leaves_one_slide_part(self):
        """A slide in a custom show has two references. Left in place, python-
        pptx keeps the old part and writes a second slide1.xml, a malformed
        zip per the OPC rule that part names are unique."""
        import zipfile
        from collections import Counter
        from lxml import etree
        from pptx import Presentation
        from pptx.opc.constants import RELATIONSHIP_TYPE as RT
        from pptx.oxml.ns import qn
        prs = self.team_deck()
        old = prs.slides.add_slide(prs.slide_layouts[1])
        old.shapes.title.text = "old slide"
        r_id = prs.part.relate_to(old.part, RT.SLIDE)
        p_ns = "http://schemas.openxmlformats.org/presentationml/2006/main"
        r_ns = ("http://schemas.openxmlformats.org/officeDocument/2006/"
                "relationships")
        prs.part._element.find(qn("p:notesSz")).addnext(etree.fromstring(
            f'<p:custShowLst xmlns:p="{p_ns}" xmlns:r="{r_ns}">'
            '<p:custShow name="Demo" id="0"><p:sldLst>'
            f'<p:sld r:id="{r_id}"/></p:sldLst></p:custShow></p:custShowLst>'))
        props = prs.part.part_related_by(RT.PRES_PROPS)
        root = etree.fromstring(props.blob)
        root.insert(0, etree.fromstring(
            f'<p:showPr xmlns:p="{p_ns}"><p:custShow id="0"/></p:showPr>'))
        props._blob = etree.tostring(root)

        run, out = self.build(self.SECTIONS, self.save_deck(prs))
        self.assertEqual(run.returncode, 0, run.stderr)
        with zipfile.ZipFile(out) as package:
            names = package.namelist()
            self.assertEqual(
                [n for n, count in Counter(names).items() if count > 1], [])
            self.assertEqual(
                [n for n in names if re.fullmatch(r"ppt/slides/[^/]+", n)],
                ["ppt/slides/slide1.xml"])
            self.assertNotIn(b"custShow", package.read("ppt/presProps.xml"))
        built = Presentation(str(out))
        self.assertIsNone(built.part._element.find(qn("p:custShowLst")))
        self.assertNotIn("old slide", self.texts(out)[1])

    def assert_only_the_new_slide(self, out):
        """OPC requires unique part names; the old text must be gone too."""
        import zipfile
        from collections import Counter
        with zipfile.ZipFile(out) as package:
            names = package.namelist()
            self.assertEqual(
                [n for n, count in Counter(names).items() if count > 1], [])
            self.assertEqual(
                [n for n in names if re.fullmatch(r"ppt/slides/[^/]+", n)],
                ["ppt/slides/slide1.xml"])
            for name in names:
                self.assertNotIn(b"old deck text", package.read(name), name)

    def old_slide(self, prs):
        slide = prs.slides.add_slide(prs.slide_layouts[1])
        slide.shapes.title.text = "old deck text"
        return slide

    def test_slide_collapsed_in_outline_view_is_dropped(self):
        """viewProps.xml points at the slide with its own relationship."""
        from lxml import etree
        from pptx.opc.constants import RELATIONSHIP_TYPE as RT
        from pptx.oxml.ns import qn
        prs = self.team_deck()
        old = self.old_slide(prs)
        view = prs.part.part_related_by(RT.VIEW_PROPS)
        r_id = view.relate_to(old.part, RT.SLIDE)
        root = etree.fromstring(view.blob)
        p_ns = "http://schemas.openxmlformats.org/presentationml/2006/main"
        r_ns = ("http://schemas.openxmlformats.org/officeDocument/2006/"
                "relationships")
        root.append(etree.fromstring(
            f'<p:outlineViewPr xmlns:p="{p_ns}" xmlns:r="{r_ns}"><p:sldLst>'
            f'<p:sld r:id="{r_id}" collapse="1"/></p:sldLst></p:outlineViewPr>'))
        view._blob = etree.tostring(root)
        run, out = self.build(self.SECTIONS, self.save_deck(prs))
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assert_only_the_new_slide(out)
        from pptx import Presentation
        kept = Presentation(str(out)).part.part_related_by(RT.VIEW_PROPS)
        self.assertIsNone(etree.fromstring(kept.blob).find(f".//{qn('p:sld')}"))

    def test_home_button_on_the_master_loses_its_link_to_a_dropped_slide(self):
        from lxml import etree
        from pptx import Presentation
        from pptx.opc.constants import RELATIONSHIP_TYPE as RT
        from pptx.oxml.ns import qn
        prs = self.team_deck()
        old = self.old_slide(prs)
        master = prs.slide_master
        r_id = master.part.relate_to(old.part, RT.SLIDE)
        name = master._element.find(f".//{qn('p:cNvPr')}")
        etree.SubElement(name, qn("a:hlinkClick"), {
            qn("r:id"): r_id, "action": "ppaction://hlinksldjump"})
        run, out = self.build(self.SECTIONS, self.save_deck(prs))
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assert_only_the_new_slide(out)
        built = Presentation(str(out)).slide_master._element
        self.assertIsNone(built.find(f".//{qn('a:hlinkClick')}"))

    def test_output_does_not_describe_the_template_deck(self):
        """A live deck is the recommended template, and the slide gets sent on:
        its preview and properties must not show the deck's other stories."""
        import zipfile
        prs = self.team_deck()
        self.old_slide(prs)
        props = prs.core_properties
        props.title = "old deck text"
        props.subject = props.keywords = props.comments = "old deck text"
        props.category = "old deck text"
        deck = self.save_deck(prs)
        with zipfile.ZipFile(deck) as package:
            for carried in ("docProps/thumbnail.jpeg", "docProps/app.xml"):
                self.assertIn(carried, package.namelist())
        run, out = self.build(self.SECTIONS, deck)
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assert_only_the_new_slide(out)
        with zipfile.ZipFile(out) as package:
            for gone in ("docProps/thumbnail.jpeg", "docProps/app.xml"):
                self.assertNotIn(gone, package.namelist())
        from pptx import Presentation
        self.assertEqual(Presentation(str(out)).core_properties.title,
                         "PROJ-1 Add retries")

    def office_section_header(self, prs):
        """Office's 16:9 geometry: a big mid-slide title with the text under."""
        layout = prs.slide_layouts[2]
        for ph in layout.placeholders:
            if ph.placeholder_format.idx == 0:
                ph.top, ph.height = 1709738, 2852737
            elif ph.placeholder_format.idx == 1:
                ph.top, ph.height = 4589463, 1500187
        return layout

    def test_default_layout_passes_over_a_section_header(self):
        prs = self.team_deck()
        section = self.office_section_header(prs)
        for layout in (prs.slide_layouts[0], section, prs.slide_layouts[1]):
            prs.slides.add_slide(layout)
        run, out = self.build(self.SECTIONS, self.save_deck(prs))
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertEqual(self.shapes(out)[0].slide_layout.name,
                         "Title and Content")

    def test_default_layout_falls_back_to_the_templates_story_layout(self):
        """A deck of section headers and two-column slides still has Title
        and Content among its layouts; the slide goes there."""
        for index in (2, 3):  # Section Header, Two Content
            with self.subTest(index=index):
                prs = self.team_deck()
                section = self.office_section_header(prs)
                layout = section if index == 2 else prs.slide_layouts[3]
                prs.slides.add_slide(layout)
                run, out = self.build(self.SECTIONS, self.save_deck(prs))
                self.assertEqual(run.returncode, 0, run.stderr)
                self.assertEqual(self.shapes(out)[0].slide_layout.name,
                                 "Title and Content")

    def test_default_layout_passes_over_a_two_content_slide(self):
        """Two Content's half-width body refuses both bundled examples."""
        prs = self.team_deck()
        for index in (3, 1):  # Two Content, then Title and Content
            prs.slides.add_slide(prs.slide_layouts[index])
        deck = self.save_deck(prs)
        for example in ("before-after", "sections"):
            with self.subTest(example):
                spec = json.loads((SKILLS / "roj-one-slide" / "assets"
                                   / f"example-{example}.json").read_text("utf-8"))
                run, out = self.build(spec, deck)
                self.assertEqual(run.returncode, 0, run.stderr)
                self.assertEqual(self.shapes(out)[0].slide_layout.name,
                                 "Title and Content")

    def test_refusal_on_an_ill_fitting_layout_points_to_a_better_one(self):
        """Rejects telling the agent only to cut content when the layout is
        what leaves no room: a low title, or a body split in two."""
        spec = json.loads((SKILLS / "roj-one-slide" / "assets"
                           / "example-before-after.json").read_text("utf-8"))
        for layout in ("Section Header", "Two Content"):
            with self.subTest(layout):
                prs = self.team_deck()
                self.office_section_header(prs)
                run, out = self.build({**spec, "layout": layout},
                                      self.save_deck(prs))
                self.assertEqual(run.returncode, 1, run.stderr)
                self.assertIn(f"layout {layout!r} leaves this slide little "
                              "room", run.stderr)
                hint = run.stderr.split("set layout to one of:")[1]
                self.assertIn("'Title and Content'", hint)
                self.assertNotIn("'Section Header'", hint)
                self.assertNotIn("'Two Content'", hint)
                self.assertFalse(out.exists())

    def test_linked_footer_text_keeps_a_valid_link(self):
        """Every r:id on a slide must name one of the slide's own
        relationships (OPC); a copied footer link must not dangle."""
        from pptx import Presentation
        prs = self.team_deck()
        footer = next(ph for ph in prs.slide_layouts[1].placeholders
                      if ph.placeholder_format.type == 15)
        footer.text_frame.text = "Team wiki"
        footer.text_frame.paragraphs[0].runs[0].hyperlink.address = (
            "https://example.com/wiki")
        run, out = self.build(self.SECTIONS, self.save_deck(prs))
        self.assertEqual(run.returncode, 0, run.stderr)
        slide = Presentation(str(out)).slides[0]
        r_ns = ("{http://schemas.openxmlformats.org/officeDocument/2006/"
                "relationships}")
        used = {v for e in slide._element.iter() for k, v in e.attrib.items()
                if k.startswith(r_ns)}
        self.assertTrue(used)
        self.assertLessEqual(used, set(slide.part.rels.keys()))
        placed = next(s for s in slide.placeholders
                      if s.placeholder_format.type == 15)
        self.assertEqual(placed.text_frame.paragraphs[0].runs[0].hyperlink
                         .address, "https://example.com/wiki")

    def test_body_grows_down_from_a_short_bottom_anchored_placeholder(self):
        """Office's Comparison body is 639762 EMU high and set to the bottom,
        so six lines of 18pt would rise over the title unless the box holds
        them. Rejects a box left at the layout's height."""
        spec = json.loads(json.dumps(self.SECTIONS))
        spec["layout"] = "Comparison"
        spec["body"]["sections"] = [
            {"heading": "Done", "points": ["one", "two", "three"]},
            {"heading": "Next", "points": "tune backoff"}]
        run, out = self.build(spec, self.save_deck(self.team_deck()))
        self.assertEqual(run.returncode, 0, run.stderr)
        slide, _ = self.shapes(out)
        body = next(s for s in slide.placeholders
                    if s.placeholder_format.idx == 1)
        self.assertEqual(body.top, 1535113)
        self.assertGreaterEqual(body.height / 12700, 6 * 18 * 1.2)

    def test_body_that_fits_keeps_the_layouts_position(self):
        """The look on the template stays: no position of its own unless the
        text needs a taller box."""
        run, out = self.build(self.SECTIONS, self.save_deck(self.team_deck()))
        self.assertEqual(run.returncode, 0, run.stderr)
        slide, _ = self.shapes(out)
        body = next(s for s in slide.placeholders
                    if s.placeholder_format.idx == 1)
        self.assertIsNone(body._element.spPr.find(
            "{http://schemas.openxmlformats.org/drawingml/2006/main}xfrm"))

    def test_missing_spec_file_is_listed(self):
        run = subprocess.run(
            [sys.executable, str(self.SCRIPT), "--template", str(self.template),
             "--spec", str(self.tmp / "none.json"),
             "--out", str(self.tmp / "out.pptx")],
            capture_output=True, text=True)
        self.assertEqual(run.returncode, 1, run.stderr)
        self.assertNotIn("Traceback", run.stderr)
        self.assertIn("cannot read the spec", run.stderr)

    def test_layout_is_the_first_slide_with_title_and_content(self):
        """A deck opening with a title slide tells stories on its next one."""
        prs = self.team_deck()
        for index in (0, 1):
            prs.slides.add_slide(prs.slide_layouts[index])
        run, out = self.build(self.BEFORE_AFTER, self.save_deck(prs))
        self.assertEqual(run.returncode, 0, run.stderr)
        slide, _ = self.shapes(out)
        self.assertEqual(slide.slide_layout.name, "Title and Content")

    def test_layout_whose_title_overlaps_the_body_is_refused(self):
        spec = {**self.BEFORE_AFTER, "layout": "Title Slide"}
        run, out = self.build(spec, self.save_deck(self.team_deck()))
        self.assertEqual(run.returncode, 1, run.stderr)
        self.assertIn("overlaps the body region", run.stderr)
        self.assertIn("'Title and Content'", run.stderr)
        for refused in ("'Title Slide'", "'Blank'"):
            self.assertNotIn(refused, run.stderr.split("set layout to")[1])
        self.assertFalse(out.exists())

    def test_title_only_layout_builds_a_diagram_below_its_title(self):
        """No body placeholder means no body to overlap; the diagram starts
        under the title. Sections still need a content placeholder, and the
        refusal names only layouts that have one."""
        spec = {**self.BEFORE_AFTER, "layout": "Title Only"}
        run, out = self.build(spec, self.save_deck(self.team_deck()))
        self.assertEqual(run.returncode, 0, run.stderr)
        slide, shapes = self.shapes(out)
        title_bottom = slide.shapes.title.top + slide.shapes.title.height
        goal = next(s for s in shapes if s.name == "Goal")
        self.assertGreaterEqual(goal.top, title_bottom)

        spec = {**self.SECTIONS, "layout": "Title Only"}
        run, _ = self.build(spec, self.save_deck(self.team_deck()))
        self.assertEqual(run.returncode, 1, run.stderr)
        self.assertIn("no content placeholder", run.stderr)
        self.assertNotIn("'Title Only'", run.stderr.split("set layout to")[1])

    def test_layout_without_a_title_is_refused(self):
        spec = {**self.BEFORE_AFTER, "layout": "Blank"}
        run, out = self.build(spec, self.save_deck(self.team_deck()))
        self.assertEqual(run.returncode, 1, run.stderr)
        self.assertNotIn("Traceback", run.stderr)
        self.assertIn("no title placeholder", run.stderr)
        self.assertFalse(out.exists())

    def test_unknown_layout_lists_every_master(self):
        prs = self.team_deck()
        self.add_second_master(prs, "Story")
        spec = {**self.BEFORE_AFTER, "layout": "Nope"}
        run, _ = self.build(spec, self.save_deck(prs))
        self.assertEqual(run.returncode, 1, run.stderr)
        self.assertIn("'Story'", run.stderr)

    def test_theme_and_text_size_come_from_the_layouts_own_master(self):
        """The second master has a yellow dk2, the first chip's fill, so the
        chip text must turn dark (below 2.5:1 with white). The first master's
        60pt body would refuse the text; the second's 18pt fits it."""
        from pptx.enum.dml import MSO_THEME_COLOR
        prs = self.team_deck(body_pt=60)
        second = self.add_second_master(prs, "Story")
        self.set_text_sizes(second, 28, 18)
        prs.slides.add_slide(second.slide_layouts[0])
        deck = self.save_deck(prs)
        run, out = self.build(self.SECTIONS, deck)
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertEqual(self.shapes(out)[0].slide_layout.name, "Story")
        run, out = self.build(self.BEFORE_AFTER, deck)
        self.assertEqual(run.returncode, 0, run.stderr)
        _, shapes = self.shapes(out)
        chip = next(s for s in shapes if s.name == "Item 3.10")
        self.assertEqual(chip.text_frame.paragraphs[0].runs[0].font.color
                         .theme_color, MSO_THEME_COLOR.DARK_1)

    def test_chip_text_follows_the_masters_colour_map(self):
        """On a dark-background master tx2 is lt2 (EEECE1 in this theme, about
        1.2:1 with white) and tx1 is white too, so both light chips need dk1
        text. On the ordinary map tx2 is dk2 (1F497D) and white stays."""
        from pptx.enum.dml import MSO_THEME_COLOR
        from pptx.oxml.ns import qn
        normal = self.team_deck()
        dark = self.team_deck()
        dark.slide_master._element.find(qn("p:clrMap")).attrib.update(
            {"bg1": "dk1", "tx1": "lt1", "bg2": "dk2", "tx2": "lt2"})

        def text_colours(prs):
            run, out = self.build(self.BEFORE_AFTER, self.save_deck(prs))
            self.assertEqual(run.returncode, 0, run.stderr)
            _, shapes = self.shapes(out)
            colours = {}
            for s in shapes:
                if s.name in ("Item 3.10", "Item DEPLOY"):
                    color = s.text_frame.paragraphs[0].runs[0].font.color
                    colours[s.name] = color.theme_color if color.type else None
            return colours

        self.assertEqual(text_colours(dark), {
            "Item 3.10": MSO_THEME_COLOR.DARK_1,
            "Item DEPLOY": MSO_THEME_COLOR.DARK_1})
        self.assertEqual(text_colours(normal), {
            "Item 3.10": None, "Item DEPLOY": MSO_THEME_COLOR.DARK_1})

    def test_flow_title_stays_readable_on_a_light_accent(self):
        """White on a yellow accent1 is about 1.1:1, under the 2.5:1 limit."""
        from lxml import etree
        from pptx.enum.dml import MSO_THEME_COLOR
        from pptx.opc.constants import RELATIONSHIP_TYPE as RT
        from pptx.oxml.ns import qn
        prs = self.team_deck()
        theme = prs.slide_master.part.part_related_by(RT.THEME)
        root = etree.fromstring(theme.blob)
        accent = root.find(".//" + qn("a:accent1"))[0]
        accent.getparent().replace(
            accent, etree.Element(qn("a:srgbClr"), val="FFFF00"))
        theme._blob = etree.tostring(root)
        spec = json.loads(json.dumps(self.SECTIONS))
        spec["body"]["flow"] = [{"title": "One"}, {"title": "Two"}]
        run, out = self.build(spec, self.save_deck(prs))
        self.assertEqual(run.returncode, 0, run.stderr)
        _, shapes = self.shapes(out)
        head = next(s for s in shapes if s.name == "Step title One")
        self.assertEqual(head.text_frame.paragraphs[0].runs[0].font.color
                         .theme_color, MSO_THEME_COLOR.DARK_1)

    def test_date_is_fixed_text_not_a_field(self):
        """A date field shows the day the deck is opened, not the spec's. The
        layout's date also shares shape id 2 with the title it would clash
        with on the slide."""
        prs = self.team_deck()
        layout = prs.slide_layouts[1]
        date = next(ph for ph in layout.placeholders
                    if ph.placeholder_format.type == 16)
        date._element.nvSpPr.cNvPr.id = 2
        run, out = self.build(self.SECTIONS, self.save_deck(prs))
        self.assertEqual(run.returncode, 0, run.stderr)
        _, shapes = self.shapes(out)
        placed = next(s for s in shapes if s.is_placeholder
                      and s.placeholder_format.type == 16)
        self.assertEqual(placed.text_frame.text, "October 30, 2026")
        a = "{http://schemas.openxmlformats.org/drawingml/2006/main}"
        self.assertIsNone(placed._element.find(f".//{a}fld"))
        ids = [s.shape_id for s in shapes]
        self.assertEqual(len(ids), len(set(ids)))

    def test_footer_keeps_the_templates_text_under_the_presenter(self):
        prs = self.team_deck()
        footer = next(ph for ph in prs.slide_layouts[1].placeholders
                      if ph.placeholder_format.type == 15)
        footer.text_frame.text = "Team confidential"
        run, out = self.build(self.SECTIONS, self.save_deck(prs))
        self.assertEqual(run.returncode, 0, run.stderr)
        _, shapes = self.shapes(out)
        placed = next(s for s in shapes if s.is_placeholder
                      and s.placeholder_format.type == 15)
        self.assertEqual(placed.text_frame.text, "Team confidential")
        presenter = next(s for s in shapes if s.name == "Presented by")
        self.assertLessEqual(presenter.top + presenter.height, footer.top)

    def test_empty_footer_stays_empty_with_the_presenter_on_its_line(self):
        run, out = self.build(self.SECTIONS)
        self.assertEqual(run.returncode, 0, run.stderr)
        _, shapes = self.shapes(out)
        placed = next(s for s in shapes if s.is_placeholder
                      and s.placeholder_format.type == 15)
        self.assertEqual(placed.text_frame.text.strip(), "")
        presenter = next(s for s in shapes if s.name == "Presented by")
        self.assertGreater(presenter.top, placed.top)

    def test_unreadable_template(self):
        bad = self.tmp / "bad.pptx"
        bad.write_text("not a deck", "utf-8")
        run, out = self.build(self.SECTIONS, bad)
        self.assertEqual(run.returncode, 3)
        self.assertFalse(out.exists())


class TestPublishable(unittest.TestCase):
    def test_no_private_paths_or_employer_details(self):
        # Scripts and JSON too: a slide spec or a fixture copied from work
        # carries names as easily as prose does.
        for f in sorted([*SKILLS.rglob("*.md"), *SKILLS.rglob("*.json"),
                         *SKILLS.rglob("*.py"), *SKILLS.rglob("*.sh"),
                         *(ROOT / "evals").rglob("*.json"),
                         *(ROOT / "instructions").rglob("*.md"),
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
        text = (ROOT / "instructions"
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


class TestAtlassianSearchScript(unittest.TestCase):
    """scripts/atlassian_search.py (issue #91): the earlier-fix phase of
    roj-investigate-issue reads Jira and Confluence over REST with personal
    access tokens, read-only, and degrades to a pasted fallback."""

    SKILL = SKILLS / "roj-investigate-issue"
    TOKEN = "pat-secret-value"

    @classmethod
    def setUpClass(cls):
        cls.script = load_module(cls.SKILL / "scripts" / "atlassian_search.py")

    def serve(self, jira_total=7):
        import threading
        from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
        from urllib.parse import parse_qs, urlsplit
        test = self
        seen = []

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def do_GET(self):
                url = urlsplit(self.path)
                q = parse_qs(url.query)
                seen.append((url.path, q, self.headers.get("Authorization")))
                if self.headers.get("Authorization") != f"Bearer {test.TOKEN}":
                    return self.reply(401, {})
                if url.path == "/rest/api/2/search":
                    issues = [] if "nomatch" in q["jql"][0] else [
                        {"key": "OPS-12", "fields": {
                            "summary": "Agent fails: no JDK 17",
                            "status": {"name": "Done"},
                            "resolution": {"name": "Fixed"},
                            "resolutiondate": "2025-03-04T10:00:00.000+0000"}}]
                    return self.reply(200, {"total": jira_total if issues else 0,
                                            "issues": issues})
                if url.path == "/rest/api/2/issue/OPS-12":
                    return self.reply(200, {"key": "OPS-12", "fields": {
                        "summary": "Agent fails: no JDK 17",
                        "status": {"name": "Done"},
                        "resolution": {"name": "Fixed"},
                        "description": "x" * 3000,
                        "comment": {"total": 1, "comments": [{
                            "author": {"displayName": "Dev"},
                            "created": "2025-03-04T09:00:00.000+0000",
                            "body": "Install JDK 17 on the agent."}]}}})
                if url.path == "/rest/api/search":
                    return self.reply(200, {"totalSize": 1, "results": [{
                        "title": "Agent capabilities",
                        "excerpt": "set the @@@hl@@@JDK@@@endhl@@@ &amp; path",
                        "lastModified": "2025-02-01T00:00:00.000Z",
                        "resultGlobalContainer": {"title": "Build"},
                        "content": {"id": "555"}}]})
                if url.path == "/rest/api/content/555":
                    return self.reply(200, {"id": "555", "title": "Agent capabilities",
                        "space": {"name": "Build"},
                        "version": {"when": "2025-02-01T00:00:00.000Z"},
                        "body": {"storage": {"value":
                            "<p>Add <b>JDK</b> capability.</p><script>x()</script>"}}})
                self.reply(404, {})

            def reply(self, status, body):
                data = json.dumps(body).encode()
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        self.addCleanup(server.shutdown)
        self.addCleanup(server.server_close)
        url = f"http://127.0.0.1:{server.server_port}"
        env = {"JIRA_URL": url, "JIRA_TOKEN": self.TOKEN,
               "CONFLUENCE_URL": url, "CONFLUENCE_TOKEN": self.TOKEN}
        return env, seen

    def run_cmd(self, argv, env):
        import io
        out = io.StringIO()
        code = self.script.main(argv, env=env, out=out)
        self.assertNotIn(self.TOKEN, out.getvalue())
        return code, json.loads(out.getvalue())

    def test_skill_declares_its_needs_for_cali_doctor(self):
        fm, _ = frontmatter((self.SKILL / "SKILL.md").read_text("utf-8"))
        self.assertEqual(
            [v.strip() for v in fm["metadata"]["cali-env"].split(",")],
            ["JIRA_URL", "JIRA_TOKEN", "CONFLUENCE_URL", "CONFLUENCE_TOKEN"])
        self.assertEqual(fm["metadata"]["cali-tools"], "python3|python")

    def test_jira_search_lists_resolved_issues_leanly(self):
        env, seen = self.serve()
        code, data = self.run_cmd(
            ["jira", "--text", 'JDK "17"', "--project", "OPS"], env)
        self.assertEqual(code, 0)
        self.assertEqual(data["results"][0], {
            "key": "OPS-12", "summary": "Agent fails: no JDK 17",
            "status": "Done", "resolution": "Fixed", "resolved": "2025-03-04"})
        self.assertEqual((data["count"], data["total"]), (1, 7))
        self.assertIn("6 more not shown", data["note"])
        self.assertIn("jira-issue", data["next"])
        jql = seen[0][1]["jql"][0]
        self.assertIn('text ~ "JDK \\"17\\""', jql)
        self.assertIn("resolution is not EMPTY", jql)
        self.assertIn('project = "OPS"', jql)

    def test_all_flag_drops_the_resolved_filter(self):
        env, seen = self.serve()
        self.run_cmd(["jira", "--text", "jdk", "--all"], env)
        self.assertNotIn("resolution", seen[0][1]["jql"][0])

    def test_empty_result_is_explicit_and_ok(self):
        env, _ = self.serve()
        code, data = self.run_cmd(["jira", "--text", "nomatch"], env)
        self.assertEqual((code, data["count"]), (0, 0))
        self.assertIn("no match", data["note"])

    def test_jira_issue_truncates_and_keeps_the_fix_comment(self):
        env, _ = self.serve()
        _, data = self.run_cmd(["jira-issue", "--key", "OPS-12"], env)
        self.assertEqual(len(data["description"]), self.script.MAX_TEXT)
        self.assertEqual(data["descriptionFullChars"], 3000)
        self.assertEqual(data["comments"][0]["body"],
                         "Install JDK 17 on the agent.")

    def test_confluence_search_and_page_read_as_text(self):
        env, _ = self.serve()
        _, hits = self.run_cmd(["confluence", "--text", "jdk",
                                "--space", "BUILD"], env)
        self.assertEqual(hits["results"][0]["id"], "555")
        self.assertNotIn("@@@", hits["results"][0]["excerpt"])
        _, page = self.run_cmd(["confluence-page", "--id", "555"], env)
        self.assertEqual(page["body"], "Add JDK capability.")

    def test_missing_or_rejected_token_has_its_own_exit_code(self):
        env, _ = self.serve()
        code, data = self.run_cmd(
            ["jira", "--text", "x"], {**env, "JIRA_TOKEN": ""})
        self.assertEqual((code, data["exit"]), (3, 3))
        self.assertIn("paste", data["next"])
        code, _ = self.run_cmd(["jira", "--text", "x"],
                               {**env, "JIRA_TOKEN": "wrong"})
        self.assertEqual(code, 4)
        code, _ = self.run_cmd(["jira", "--text", "x"], {})
        self.assertEqual(code, 2)
        self.assertEqual(self.run_cmd(["token-status"], {})[1],
                         {"jira": {"url": False, "token": False},
                          "confluence": {"url": False, "token": False}})

    def test_clear_text_remote_url_and_unknown_flags_fail_loud(self):
        code, _ = self.run_cmd(["jira", "--text", "x"], {
            "JIRA_URL": "http://jira.example.com", "JIRA_TOKEN": "t"})
        self.assertEqual(code, 2)
        env, _ = self.serve()
        self.assertEqual(self.run_cmd(["jira", "--text", "x", "--bogus"],
                                      env)[0], 2)
        self.assertEqual(self.run_cmd(["jira", "--text", "x", "--limit",
                                       "99"], env)[0], 2)

    def test_skill_runs_the_phase_and_keeps_it_read_only(self):
        body = (self.SKILL / "SKILL.md").read_text("utf-8")
        self.assertIn("references/earlier-fixes.md", body)
        ref = (self.SKILL / "references" / "earlier-fixes.md").read_text("utf-8")
        self.assertIn("Paste fallback", ref)
        self.assertNotIn("POST", (self.SKILL / "scripts"
                                  / "atlassian_search.py").read_text("utf-8"))


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
