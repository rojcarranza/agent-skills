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

    USES_GRAPH = ("roj-tour-codebase", "roj-explain-logic",
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
        for name in ("roj-tour-codebase", "roj-explain-feature-changes",
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
    the fake gh mode (evals/fixtures/fake-gh.sh)."""

    FIXTURES = ROOT / "evals" / "fixtures"
    GH_MODES = {"normal", "reviewed", "noauth"}
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
                    if "gh" in e["fixture"]:
                        self.assertIn(e["fixture"]["gh"], self.GH_MODES)
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
            gh = Path(tmp) / "pyrepo"
            run = subprocess.run(
                [BASH, str(self.FIXTURES / "fake-gh.sh"), str(gh),
                 "normal"], capture_output=True, text=True)
            self.assertEqual(run.returncode, 0, run.stderr)
            self.assertTrue((gh / "bin" / "gh").is_file())
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
        "review this GitHub pull request URL and leave inline comments",
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
    "roj-tour-codebase": [
        "onboard me to this repo",
        "tour this codebase",
        "where do I start in this project I just joined",
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


if __name__ == "__main__":
    unittest.main()
