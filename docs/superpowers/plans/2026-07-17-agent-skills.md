# Agent Skills Collection + Cross-Platform Installer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** One versioned home in the dotfiles repo for custom agent skills (refined `explain-logic`, new `caveman-mode`) with a stdlib-Python installer targeting GitHub Copilot and/or Claude Code.

**Architecture:** `agent-skills/` directory holding single-source `SKILL.md` skills (one format serves both platforms), Copilot-only `.prompt.md` files, and `install.py` which copies skills for Copilot, symlinks them for Claude (dotfiles convention), and sparse-clones five community skills from `github/awesome-copilot`. A thin `setup.sh` registers the Claude side into the existing `install.sh` tool pattern.

**Tech Stack:** Python ≥ 3.8 stdlib only (`argparse`, `pathlib`, `shutil`, `filecmp`, `subprocess`), `unittest` for tests, bash for the dotfiles `setup.sh` shim.

**Spec:** `docs/superpowers/specs/2026-07-17-agent-skills-design.md`

## Global Constraints

- Python ≥ 3.8, standard library only — no pip installs anywhere.
- `explain-logic`'s `description:` frontmatter is copied **verbatim** from the draft (trigger accuracy depends on it).
- Community skills fetched: `code-tour`, `acquire-codebase-knowledge`, `context-map`, `architecture-blueprint-generator`, `add-educational-comments` from `https://github.com/github/awesome-copilot.git` branch `main`, cached in `~/.agent-skills-cache/awesome-copilot`.
- Copilot destination: `~/.copilot/skills/` (copies) + VS Code user prompts dir. Claude destination: `~/.claude/skills/` (per-skill symlinks for custom skills, copies for community skills).
- Installer must be idempotent — second run reports "up to date" everywhere.
- Bash `setup.sh` scripts source `lib/common.sh` and use its `info`/`ok`/`skip`/`warn` helpers (see `claude/setup.sh` for the pattern).
- Test command: `cd agent-skills && python3 -m unittest test_install -v`.

---

### Task 1: Scaffold + caveman-mode skill

**Files:**
- Create: `agent-skills/skills/caveman-mode/SKILL.md`

**Interfaces:**
- Produces: `agent-skills/skills/` directory layout that Tasks 2–5 populate and `install.py` iterates (`SKILLS_SRC = REPO_ROOT / "skills"`).

- [ ] **Step 1: Write the skill file**

Write `agent-skills/skills/caveman-mode/SKILL.md` with exactly this content:

```markdown
---
name: caveman-mode
description: Ultra-terse output mode that cuts response tokens while keeping full technical accuracy. Use when the user says "caveman mode", "be terse", "be brief", "save tokens", "less tokens", "shorter answers", or asks for compressed output. Stays active for the rest of the session until the user says "normal mode" or "stop caveman".
---

# Caveman Mode

Respond terse like smart caveman. All technical substance stays. Only fluff dies.

## Persistence

Active on every response once triggered — no drifting back to verbose after a few
turns. Turns off only when the user says "stop caveman" or "normal mode".

## Rules

- Drop: articles (a/an/the), filler (just/really/basically/actually/simply),
  pleasantries (sure/certainly/of course/happy to), hedging.
- Sentence fragments OK. Short synonyms: "big" not "extensive"; "fix" not
  "implement a solution for".
- No tool-call narration. No decorative tables or emoji.
- Never invent abbreviations (cfg/impl/req/fn) — tokenizers split them the same
  as the full word: zero tokens saved, reader still has to decode. Standard
  well-known acronyms OK (DB/API/HTTP).
- Keep verbatim, always: technical terms, code, API names, CLI commands, file
  paths, and exact error strings.
- Don't dump long raw logs — quote the shortest decisive line.
- Pattern: `[thing] [action] [reason]. [next step].`

Not: "Sure! I'd be happy to help. The issue you're experiencing is likely caused by..."
Yes: "Bug in auth middleware. Token expiry check uses `<` not `<=`. Fix:"

## Auto-clarity — write normal when

- Security warnings.
- Confirmations for irreversible or destructive actions.
- Multi-step sequences where compression risks misreading the order.

Resume terse output after the clear part is done.

## Boundaries

Code, commit messages, PR descriptions, and documentation are always written
in normal full prose.
```

- [ ] **Step 2: Verify frontmatter structure**

Run: `head -4 agent-skills/skills/caveman-mode/SKILL.md`
Expected: `---`, `name: caveman-mode`, `description: Ultra-terse ...`, `---` — frontmatter opens and closes, `name` matches the directory name.

- [ ] **Step 3: Commit**

```bash
git add agent-skills/skills/caveman-mode/SKILL.md
git commit -m "feat(agent-skills): add portable caveman-mode skill"
```

---

### Task 2: explain-logic skill (compressed) + Copilot prompt files

**Files:**
- Create: `agent-skills/skills/explain-logic/SKILL.md`
- Create: `agent-skills/prompts/explain-code.prompt.md`
- Create: `agent-skills/prompts/explain-and-review.prompt.md`

**Interfaces:**
- Consumes: `agent-skills/skills/` layout from Task 1.
- Produces: `agent-skills/prompts/*.prompt.md` that `install_prompts()` (Task 4) globs.

- [ ] **Step 1: Write the compressed skill**

Write `agent-skills/skills/explain-logic/SKILL.md`. The `description:` value below is copied verbatim from the draft — do not edit it:

````markdown
---
name: explain-logic
description: Explain the logic of code the user is reading — a pull request, a feature branch diff, a file, or a function — as a guided, step-by-step walkthrough. Use this skill whenever the user says things like "explain this PR", "walk me through this branch", "what does this code do", "help me understand this logic", "explain the changes", "why does this work", "trace this flow", or pastes/points at code they are trying to understand. Trigger even if they don't say "explain" — any request to understand, read, review-for-comprehension, or onboard onto code counts. Covers Java, Python, Go, shell scripts, and Atlassian Bamboo API/specs code.
---

# Explain Logic

Goal: comprehension, not review. Explain what IS, why it exists, how it flows.
No improvement suggestions unless asked.

## Step 1 — Scope

Priority order:

1. **PR / feature branch**: pull the real diff first — never explain from memory.
   - Branch: `git diff main...HEAD` (base unclear: check `git merge-base`).
     Changed files: `git diff --stat main...HEAD`.
   - GitHub PR: GitHub MCP tools (`get_pull_request`, `get_pull_request_diff`)
     if available, else `gh pr diff <number>`.
2. **File/function**: read the whole file, not just the snippet.
3. **Ambiguous**: ask ONE question ("Which branch/PR, or which file?"), then proceed.

## Step 2 — Context before explaining

A diff alone lies. Always:

- Read the full function/class around each changed hunk.
- Trace callers and callees (grep/IDE search on names).
- Check tests touching the changed code — tests document intent.
- Read the PR description and commit messages.
- Note config/CI in the diff (Bamboo specs, pipelines, Dockerfiles, Helm) —
  these change runtime behavior, not just code.

## Step 3 — Structure: Concept → Code → Why

Never jump straight to line-by-line.

1. **Big picture** — 2-4 sentences: problem solved, overall approach.
   One-line role per changed file.
2. **Flow** — walk the execution path in run order, not file-by-file.
   Each step: inputs → transformation → outputs. Text/mermaid diagram when
   3+ moving parts. Quote the actual lines, then explain in plain language.
   Name patterns used (retry loop, factory, decorator, context manager,
   goroutine + channel, trap/cleanup) with a one-line definition.
3. **Why** — this approach vs the obvious alternative; what breaks without
   each key piece; edge cases handled and visibly NOT handled; side effects
   (files written, API calls, env vars read, exit codes, state mutated).
4. **Gotchas** — non-obvious, surprising, or easy-to-misread parts.
   2-3 self-check questions the user can answer to confirm understanding.

## Step 4 — Depth

- Diff < 100 lines: full line-level walkthrough.
- Large diff: flow first, then offer "which part should I zoom into line-by-line?"
- User is a mid/senior DevOps engineer: skip syntax basics, DO define
  language idioms they may not use daily.

## Language lenses

- **Java**: DI/annotations doing invisible work (`@Autowired`, `@Bean`),
  generics bounds, checked vs unchecked exceptions, stream chains (unroll
  into steps), builder patterns.
- **Python**: decorators (show the unwrapped equivalent), context managers,
  nested comprehensions (unroll), Click/argparse CLI wiring, exception
  breadth (bare `except` vs specific), type hints as documentation.
- **Go**: goroutines/channels (who sends, who receives, when it closes),
  `defer` order, error wrapping (`fmt.Errorf` + `%w`), interfaces satisfied
  implicitly (find the concrete type), zero values.
- **Shell**: `set -euo pipefail` implications, quoting/word-splitting risks,
  exit-code logic (`&&`, `||`, `$?`), traps, subshell vs current shell,
  here-docs. Always state what happens when a mid-pipeline command fails.
- **Bamboo API/specs**: map code to plan → stage → job → task, identify the
  REST endpoints called, variable scoping (plan vs global vs build),
  trigger/artifact flow between plans.

## Companion skills — use if installed

| Skill | When |
|---|---|
| context-map | fuzzy scope: map all relevant files before explaining |
| acquire-codebase-knowledge | new repo or repo-wide question: build the codebase map first |
| code-tour | after any walkthrough, offer a replayable `.tours/*.tour` |
| architecture-blueprint-generator | change touches system structure: refresh the architecture doc |
| add-educational-comments | offer AFTER the walkthrough; never add comments without asking |
| caveman-mode | user asks terse/brief/save tokens: apply it to the output |

Chain: context-map → acquire-codebase-knowledge → this skill → code-tour (optional).

## Explain-and-review mode

Only when the user explicitly asks to also review ("explain and review",
"flag anything risky"). Run a SECOND phase after the full explanation, with
clearly separated headers — never mix review into the explanation:

- **Logic risks**: boundary conditions, inverted conditions, off-by-one,
  unhandled states.
- **Error handling**: swallowed exceptions, bare excepts, shell commands
  failing silently.
- **Edge cases**: empty/null input, concurrency, retries, timeouts.
- **Side effects**: partial writes, non-idempotent operations, CI/CD
  runtime impact.

Rate findings: 🔴 likely bug / 🟡 risky, verify / 🟢 style-level. Tie every
finding to specific lines with the reason it is risky. Solid code: say so
plainly — never invent findings.

## Rules

- Never invent behavior — if you can't see the code a call resolves to,
  say so and go read it.
- Prefer "this line does X because Y" over "this improves Z".
- No refactoring advice unless explicitly requested.
- Diff touches CI/CD or infra: always end with "runtime impact" — what
  changes about how/when things execute.
````

- [ ] **Step 2: Write the two prompt files (verbatim from the draft)**

Write `agent-skills/prompts/explain-code.prompt.md`:

```markdown
---
mode: agent
description: 'Explain the logic of a PR, feature branch, file, or selection with a step-by-step walkthrough (Concept → Code flow → Why → Gotchas)'
---

Use the **explain-logic** skill for this task. Follow its full workflow.

Target to explain (in priority order):
1. If I selected code in the editor, explain that selection: ${selection}
2. If I mention a PR number or branch name in my message, pull the real diff first
3. Otherwise, ask me one question: "Which branch, PR, or file?"

Requirements:
- Comprehension only — no refactoring or improvement suggestions unless I ask
- Structure: big picture → execution flow in run order → why it works this way → gotchas
- Apply the language lens (Java / Python / Go / shell / Bamboo API) matching the code
- End by offering to save the walkthrough as a CodeTour if the code-tour skill is available
```

Write `agent-skills/prompts/explain-and-review.prompt.md`:

```markdown
---
mode: agent
description: 'Explain the logic of a PR, feature branch, file, or selection step by step, THEN review it for risky logic, bugs, and edge cases'
---

Use the **explain-logic** skill in explain-and-review mode. Two phases, in this order:

## Phase 1 — Explain (comprehension first)
Follow the explain-logic skill workflow fully:
big picture → execution flow in run order → why it works this way → gotchas.
Apply the matching language lens (Java / Python / Go / shell / Bamboo API).

Target (in priority order):
1. If I selected code in the editor, explain that selection: ${selection}
2. If I mention a PR number or branch name, pull the real diff first
3. Otherwise, ask me one question: "Which branch, PR, or file?"

## Phase 2 — Review (only after I understand it)
Now switch hats and review the SAME code:
- **Logic risks**: off-by-one, wrong boundary conditions, inverted conditions, unhandled states
- **Error handling**: swallowed exceptions, bare excepts, missing error propagation, shell commands that fail silently
- **Edge cases**: empty input, nulls/zero values, concurrent execution, retries, timeouts
- **Side-effect risks**: partial writes, non-idempotent operations, CI/CD runtime impact
- Rate each finding: 🔴 likely bug / 🟡 risky, verify / 🟢 style-level

Rules:
- Keep the two phases clearly separated with headers — never mix review comments into the explanation
- Every finding must reference the specific line(s) and say WHY it is risky, not just what to change
- If the code is solid, say so — do not invent findings to fill space
```

- [ ] **Step 3: Verify description is verbatim**

Run: `diff <(sed -n '3p' agent-skills/skills/explain-logic/SKILL.md) <(sed -n '3p' /Users/roj/Downloads/copilot-explain-code-skill/SKILL.md)`
Expected: no output (line 3 — the description — is identical). If the Downloads folder is gone, skip this check; the description text is embedded in Step 1 above.

- [ ] **Step 4: Commit**

```bash
git add agent-skills/skills/explain-logic agent-skills/prompts
git commit -m "feat(agent-skills): add compressed explain-logic skill and Copilot prompts"
```

---

### Task 3: install.py primitives — dirs_equal, install_copy, install_symlink

**Files:**
- Create: `agent-skills/install.py`
- Test: `agent-skills/test_install.py`

**Interfaces:**
- Produces (used by Tasks 4–5):
  - `dirs_equal(a: Path, b: Path) -> bool`
  - `install_copy(src: Path, dest: Path, dry_run: bool) -> str` — returns `"installed" | "updated" | "up to date"`
  - `install_symlink(src: Path, dest: Path, dry_run: bool) -> str` — returns `"linked" | "already linked"` or `"<copy status> (copy fallback)"`
  - Module-level constants: `REPO_ROOT`, `SKILLS_SRC`, `PROMPTS_SRC`, `COMMUNITY_SKILLS`, `AWESOME_REPO_URL`, `AWESOME_BRANCH`, `ZIP_FALLBACK_URL`
  - Logging helpers: `log(msg)`, `ok(msg)`, `warn(msg)`

- [ ] **Step 1: Write the failing tests**

Write `agent-skills/test_install.py`:

```python
import shutil
import tempfile
import unittest
from pathlib import Path

import install


class TempDirTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)

    def make_skill(self, root, name="skill-a", content="hello"):
        d = self.tmp / root / name
        d.mkdir(parents=True)
        (d / "SKILL.md").write_text(content)
        return d


class TestDirsEqual(TempDirTest):
    def test_identical_trees_equal(self):
        a = self.make_skill("a")
        b = self.make_skill("b")
        self.assertTrue(install.dirs_equal(a, b))

    def test_different_file_content_not_equal(self):
        a = self.make_skill("a", content="one")
        b = self.make_skill("b", content="two")
        self.assertFalse(install.dirs_equal(a, b))

    def test_extra_file_not_equal(self):
        a = self.make_skill("a")
        b = self.make_skill("b")
        (b / "extra.md").write_text("x")
        self.assertFalse(install.dirs_equal(a, b))

    def test_nested_difference_detected(self):
        a = self.make_skill("a")
        b = self.make_skill("b")
        (a / "sub").mkdir()
        (a / "sub" / "f.txt").write_text("1")
        (b / "sub").mkdir()
        (b / "sub" / "f.txt").write_text("2")
        self.assertFalse(install.dirs_equal(a, b))


class TestInstallCopy(TempDirTest):
    def test_new_install(self):
        src = self.make_skill("src")
        dest = self.tmp / "dest" / "skill-a"
        status = install.install_copy(src, dest, dry_run=False)
        self.assertEqual(status, "installed")
        self.assertEqual((dest / "SKILL.md").read_text(), "hello")

    def test_up_to_date(self):
        src = self.make_skill("src")
        dest = self.tmp / "dest" / "skill-a"
        install.install_copy(src, dest, dry_run=False)
        self.assertEqual(install.install_copy(src, dest, dry_run=False), "up to date")

    def test_updated(self):
        src = self.make_skill("src")
        dest = self.tmp / "dest" / "skill-a"
        install.install_copy(src, dest, dry_run=False)
        (src / "SKILL.md").write_text("changed")
        self.assertEqual(install.install_copy(src, dest, dry_run=False), "updated")
        self.assertEqual((dest / "SKILL.md").read_text(), "changed")

    def test_dry_run_writes_nothing(self):
        src = self.make_skill("src")
        dest = self.tmp / "dest" / "skill-a"
        status = install.install_copy(src, dest, dry_run=True)
        self.assertEqual(status, "installed")
        self.assertFalse(dest.exists())

    def test_replaces_symlink_with_copy(self):
        src = self.make_skill("src")
        other = self.make_skill("other", name="skill-b")
        dest = self.tmp / "dest" / "skill-a"
        dest.parent.mkdir(parents=True)
        dest.symlink_to(other)
        status = install.install_copy(src, dest, dry_run=False)
        self.assertEqual(status, "updated")
        self.assertFalse(dest.is_symlink())
        self.assertEqual((dest / "SKILL.md").read_text(), "hello")


class TestInstallSymlink(TempDirTest):
    def test_creates_link(self):
        src = self.make_skill("src")
        dest = self.tmp / "dest" / "skill-a"
        status = install.install_symlink(src, dest, dry_run=False)
        self.assertEqual(status, "linked")
        self.assertTrue(dest.is_symlink())
        self.assertEqual(dest.resolve(), src.resolve())

    def test_already_linked(self):
        src = self.make_skill("src")
        dest = self.tmp / "dest" / "skill-a"
        install.install_symlink(src, dest, dry_run=False)
        self.assertEqual(install.install_symlink(src, dest, dry_run=False),
                         "already linked")

    def test_wrong_link_replaced(self):
        src = self.make_skill("src")
        other = self.make_skill("other", name="skill-b")
        dest = self.tmp / "dest" / "skill-a"
        dest.parent.mkdir(parents=True)
        dest.symlink_to(other)
        status = install.install_symlink(src, dest, dry_run=False)
        self.assertEqual(status, "linked")
        self.assertEqual(dest.resolve(), src.resolve())

    def test_broken_link_replaced(self):
        src = self.make_skill("src")
        dest = self.tmp / "dest" / "skill-a"
        dest.parent.mkdir(parents=True)
        dest.symlink_to(self.tmp / "gone")
        status = install.install_symlink(src, dest, dry_run=False)
        self.assertEqual(status, "linked")
        self.assertEqual(dest.resolve(), src.resolve())

    def test_real_dir_backed_up(self):
        src = self.make_skill("src")
        dest = self.make_skill("dest", content="old local copy")
        status = install.install_symlink(src, dest, dry_run=False)
        self.assertEqual(status, "linked")
        self.assertTrue(dest.is_symlink())
        backup = dest.parent / (dest.name + ".bak")
        self.assertEqual((backup / "SKILL.md").read_text(), "old local copy")

    def test_dry_run_writes_nothing(self):
        src = self.make_skill("src")
        dest = self.tmp / "dest" / "skill-a"
        status = install.install_symlink(src, dest, dry_run=True)
        self.assertEqual(status, "linked")
        self.assertFalse(dest.exists())


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd agent-skills && python3 -m unittest test_install -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'install'`

- [ ] **Step 3: Write install.py with the primitives**

Write `agent-skills/install.py`:

```python
#!/usr/bin/env python3
"""Install agent skills globally for GitHub Copilot and/or Claude Code.

Usage:
  python3 install.py --target claude
  python3 install.py --target copilot
  python3 install.py --target both --dry-run
  python3 install.py                # interactive target menu
  python3 install.py --target claude --skills-only   # skip community fetch

Python >= 3.8, standard library only.
Copilot gets copies; Claude gets per-skill symlinks (edit the repo, changes
are live). On filesystems without symlink support the installer falls back
to copying.
"""
import argparse
import filecmp
import os
import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent
SKILLS_SRC = REPO_ROOT / "skills"
PROMPTS_SRC = REPO_ROOT / "prompts"

AWESOME_REPO_URL = "https://github.com/github/awesome-copilot.git"
AWESOME_BRANCH = "main"
ZIP_FALLBACK_URL = "https://github.com/github/awesome-copilot/tree/main/skills"

COMMUNITY_SKILLS = [
    "code-tour",
    "acquire-codebase-knowledge",
    "context-map",
    "architecture-blueprint-generator",
    "add-educational-comments",
]


def log(msg):
    print(f"[skills] {msg}")


def ok(msg):
    print(f"[  ok  ] {msg}")


def warn(msg):
    print(f"[ warn ] {msg}", file=sys.stderr)


def dirs_equal(a, b):
    """Recursive content comparison of two directories (like diff -rq)."""
    cmp = filecmp.dircmp(a, b)
    if cmp.left_only or cmp.right_only or cmp.funny_files:
        return False
    _, mismatch, errors = filecmp.cmpfiles(a, b, cmp.common_files, shallow=False)
    if mismatch or errors:
        return False
    return all(dirs_equal(Path(a) / d, Path(b) / d) for d in cmp.common_dirs)


def install_copy(src, dest, dry_run):
    """Copy skill dir src -> dest. Returns 'installed'|'updated'|'up to date'."""
    src, dest = Path(src), Path(dest)
    if dest.is_symlink() or dest.is_file():
        if not dry_run:
            dest.unlink()
            shutil.copytree(src, dest)
        return "updated"
    if not dest.exists():
        if not dry_run:
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copytree(src, dest)
        return "installed"
    if dirs_equal(src, dest):
        return "up to date"
    if not dry_run:
        shutil.rmtree(dest)
        shutil.copytree(src, dest)
    return "updated"


def install_symlink(src, dest, dry_run):
    """Symlink dest -> src. Returns 'linked'|'already linked' or a copy
    status suffixed with ' (copy fallback)' when symlinks are unsupported."""
    src, dest = Path(src), Path(dest)
    if dest.is_symlink():
        if dest.resolve() == src.resolve():
            return "already linked"
        if not dry_run:
            dest.unlink()  # wrong or broken link: replace
    elif dest.exists():
        backup = dest.parent / (dest.name + ".bak")
        if not dry_run:
            if backup.is_symlink() or backup.is_file():
                backup.unlink()
            elif backup.is_dir():
                shutil.rmtree(backup)
            dest.rename(backup)
        log(f"backed up existing {dest.name} to {backup.name}")
    if dry_run:
        return "linked"
    dest.parent.mkdir(parents=True, exist_ok=True)
    try:
        dest.symlink_to(src, target_is_directory=True)
        return "linked"
    except OSError:
        warn(f"symlink unsupported for {dest} — copying instead "
             "(re-run install.py after edits to refresh)")
        return install_copy(src, dest, dry_run=False) + " (copy fallback)"
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd agent-skills && python3 -m unittest test_install -v`
Expected: all tests PASS (15 tests, OK).

- [ ] **Step 5: Commit**

```bash
git add agent-skills/install.py agent-skills/test_install.py
git commit -m "feat(agent-skills): install.py copy/symlink primitives with tests"
```

---

### Task 4: install.py environment — target selection, VS Code prompts dir, prompt install

**Files:**
- Modify: `agent-skills/install.py` (append functions)
- Test: `agent-skills/test_install.py` (append test classes)

**Interfaces:**
- Consumes: `install_copy`, `log`, `ok`, `warn`, `PROMPTS_SRC` from Task 3.
- Produces (used by Task 5):
  - `pick_targets(arg_target) -> list` — `["copilot"]`, `["claude"]`, or `["copilot", "claude"]`
  - `vscode_prompts_dir() -> Path | None`
  - `install_prompts(dry_run: bool) -> list` — list of `("copilot", "prompt:<stem>", status)` tuples

- [ ] **Step 1: Write the failing tests**

Append to `agent-skills/test_install.py` (above the `if __name__` block):

```python
from unittest import mock


class TestPickTargets(unittest.TestCase):
    def test_explicit_targets(self):
        self.assertEqual(install.pick_targets("copilot"), ["copilot"])
        self.assertEqual(install.pick_targets("claude"), ["claude"])
        self.assertEqual(install.pick_targets("both"), ["copilot", "claude"])

    def test_interactive_menu(self):
        with mock.patch("builtins.input", return_value="2"):
            self.assertEqual(install.pick_targets(None), ["claude"])

    def test_interactive_invalid_exits(self):
        with mock.patch("builtins.input", return_value="9"):
            with self.assertRaises(SystemExit):
                install.pick_targets(None)


class TestVscodePromptsDir(TempDirTest):
    def test_appdata_windows_layout(self):
        user = self.tmp / "AppData" / "Code" / "User"
        user.mkdir(parents=True)
        with mock.patch.dict(os.environ, {"APPDATA": str(self.tmp / "AppData")}):
            self.assertEqual(install.vscode_prompts_dir(), user / "prompts")

    def test_none_when_no_vscode(self):
        with mock.patch.dict(os.environ, {}, clear=True), \
             mock.patch("install.Path.home", return_value=self.tmp):
            self.assertIsNone(install.vscode_prompts_dir())


class TestInstallPrompts(TempDirTest):
    def test_installs_and_reports(self):
        prompts_src = self.tmp / "prompts"
        prompts_src.mkdir()
        (prompts_src / "explain-code.prompt.md").write_text("prompt body")
        user_dir = self.tmp / "Code" / "User"
        user_dir.mkdir(parents=True)
        with mock.patch("install.PROMPTS_SRC", prompts_src), \
             mock.patch("install.vscode_prompts_dir",
                        return_value=user_dir / "prompts"):
            results = install.install_prompts(dry_run=False)
        self.assertEqual(results, [("copilot", "prompt:explain-code.prompt", "installed")])
        self.assertEqual((user_dir / "prompts" / "explain-code.prompt.md").read_text(),
                         "prompt body")

    def test_up_to_date_second_run(self):
        prompts_src = self.tmp / "prompts"
        prompts_src.mkdir()
        (prompts_src / "explain-code.prompt.md").write_text("prompt body")
        user_dir = self.tmp / "Code" / "User"
        user_dir.mkdir(parents=True)
        with mock.patch("install.PROMPTS_SRC", prompts_src), \
             mock.patch("install.vscode_prompts_dir",
                        return_value=user_dir / "prompts"):
            install.install_prompts(dry_run=False)
            results = install.install_prompts(dry_run=False)
        self.assertEqual(results[0][2], "up to date")

    def test_no_vscode_dir_warns_and_returns_empty(self):
        with mock.patch("install.vscode_prompts_dir", return_value=None):
            self.assertEqual(install.install_prompts(dry_run=False), [])
```

Also add `import os` to the top of `test_install.py` if not present.

- [ ] **Step 2: Run tests to verify the new ones fail**

Run: `cd agent-skills && python3 -m unittest test_install -v`
Expected: Task 3 tests PASS; new tests FAIL with `AttributeError: module 'install' has no attribute 'pick_targets'` (and similar).

- [ ] **Step 3: Implement the functions**

Append to `agent-skills/install.py`:

```python
def pick_targets(arg_target):
    """Resolve --target value (or interactive menu) to a list of targets."""
    if arg_target:
        return ["copilot", "claude"] if arg_target == "both" else [arg_target]
    print("Install skills for:")
    print("  1) GitHub Copilot   (~/.copilot/skills + VS Code prompts)")
    print("  2) Claude Code      (~/.claude/skills, symlinked)")
    print("  3) Both")
    choice = input("Choice [1-3]: ").strip()
    targets = {"1": ["copilot"], "2": ["claude"],
               "3": ["copilot", "claude"]}.get(choice)
    if not targets:
        sys.exit("Invalid choice — run again or pass --target.")
    return targets


def vscode_prompts_dir():
    """Locate the VS Code user prompts dir, or None if VS Code is absent."""
    candidates = []
    appdata = os.environ.get("APPDATA")
    if appdata:
        candidates.append(Path(appdata) / "Code" / "User")          # Windows
    candidates.append(Path.home() / "Library" / "Application Support"
                      / "Code" / "User")                            # macOS
    candidates.append(Path.home() / ".config" / "Code" / "User")    # Linux
    for c in candidates:
        if c.is_dir():
            return c / "prompts"
    return None


def install_prompts(dry_run):
    """Copy prompts/*.prompt.md into the VS Code user prompts dir."""
    results = []
    user_dir = vscode_prompts_dir()
    if user_dir is None:
        warn("VS Code user dir not found — prompt files not installed.")
        warn("Per-repo alternative: copy prompts/*.prompt.md into .github/prompts/")
        return results
    if not dry_run:
        user_dir.mkdir(parents=True, exist_ok=True)
    for p in sorted(PROMPTS_SRC.glob("*.prompt.md")):
        dest = user_dir / p.name
        if dest.exists() and filecmp.cmp(p, dest, shallow=False):
            status = "up to date"
        else:
            status = "updated" if dest.exists() else "installed"
            if not dry_run:
                shutil.copy2(p, dest)
        results.append(("copilot", f"prompt:{p.stem}", status))
    return results
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd agent-skills && python3 -m unittest test_install -v`
Expected: all tests PASS (23 tests, OK).

- [ ] **Step 5: Commit**

```bash
git add agent-skills/install.py agent-skills/test_install.py
git commit -m "feat(agent-skills): target selection, VS Code prompt install"
```

---

### Task 5: install.py — community skill cache, main orchestration, summary

**Files:**
- Modify: `agent-skills/install.py` (append functions + entry point)
- Test: `agent-skills/test_install.py` (append test class)

**Interfaces:**
- Consumes: everything from Tasks 3–4.
- Produces: runnable CLI — `python3 install.py --target ... [--skills-only] [--dry-run]`; `update_community_cache(dry_run) -> Path | None`; `print_summary(results, targets, dry_run)`.

- [ ] **Step 1: Write the failing tests**

Append to `agent-skills/test_install.py`:

```python
class TestCommunityCache(TempDirTest):
    def test_clone_failure_warns_and_returns_none(self):
        cache = self.tmp / "cache" / "awesome-copilot"
        boom = subprocess.CalledProcessError(128, ["git", "clone"])
        with mock.patch("install.cache_dir", return_value=cache), \
             mock.patch("install.run_git", side_effect=boom):
            self.assertIsNone(install.update_community_cache(dry_run=False))

    def test_clone_failure_uses_existing_cache(self):
        cache = self.tmp / "cache" / "awesome-copilot"
        (cache / ".git").mkdir(parents=True)
        (cache / "skills" / "code-tour").mkdir(parents=True)
        boom = subprocess.CalledProcessError(128, ["git", "fetch"])
        with mock.patch("install.cache_dir", return_value=cache), \
             mock.patch("install.run_git", side_effect=boom):
            self.assertEqual(install.update_community_cache(dry_run=False), cache)

    def test_fresh_clone_invokes_git(self):
        cache = self.tmp / "cache" / "awesome-copilot"
        calls = []
        with mock.patch("install.cache_dir", return_value=cache), \
             mock.patch("install.run_git", side_effect=lambda a: calls.append(a)):
            result = install.update_community_cache(dry_run=False)
        self.assertEqual(result, cache)
        self.assertEqual(calls[0][0], "clone")
        self.assertIn("sparse-checkout", calls[1])
```

Also add `import subprocess` to the top of `test_install.py`.

- [ ] **Step 2: Run tests to verify the new ones fail**

Run: `cd agent-skills && python3 -m unittest test_install -v`
Expected: new tests FAIL with `AttributeError: module 'install' has no attribute 'cache_dir'` (and similar); earlier tests PASS.

- [ ] **Step 3: Implement cache, summary, and main**

Append to `agent-skills/install.py`:

```python
def cache_dir():
    return Path.home() / ".agent-skills-cache" / "awesome-copilot"


def run_git(args):
    subprocess.run(["git", *args], check=True)


def update_community_cache(dry_run):
    """Sparse-clone/refresh github/awesome-copilot. Returns cache path or
    None when no usable cache exists."""
    cache = cache_dir()
    sparse = [f"skills/{s}" for s in COMMUNITY_SKILLS]
    if dry_run:
        log(f"dry-run: would clone/update {AWESOME_REPO_URL} into {cache}")
        return cache if (cache / "skills").is_dir() else None
    try:
        if (cache / ".git").is_dir():
            log("Updating awesome-copilot cache...")
            run_git(["-C", str(cache), "sparse-checkout", "set", *sparse])
            run_git(["-C", str(cache), "fetch", "--depth", "1",
                     "origin", AWESOME_BRANCH])
            run_git(["-C", str(cache), "reset", "--hard",
                     f"origin/{AWESOME_BRANCH}"])
        else:
            log("Cloning awesome-copilot (sparse, only needed skills)...")
            cache.parent.mkdir(parents=True, exist_ok=True)
            run_git(["clone", "--depth", "1", "--filter=blob:none", "--sparse",
                     "-b", AWESOME_BRANCH, AWESOME_REPO_URL, str(cache)])
            run_git(["-C", str(cache), "sparse-checkout", "set", *sparse])
        ok("awesome-copilot cache ready")
        return cache
    except (subprocess.CalledProcessError, FileNotFoundError):
        warn("Could not clone/update awesome-copilot (offline? proxy?).")
        if (cache / "skills").is_dir():
            warn("Using existing local cache instead.")
            return cache
        warn(f"Fallback: download the skill folders as ZIP from {ZIP_FALLBACK_URL}")
        warn(f"and unzip into {cache / 'skills'}, then re-run this script.")
        return None


def print_summary(results, targets, dry_run):
    print()
    title = "Planned actions (dry run)" if dry_run else "Install summary"
    log(title + ":")
    for target, name, status in results:
        print(f"  {target:8} {name:35} {status}")
    print()
    if "copilot" in targets:
        log("Verify Copilot:  /skills list  in Copilot CLI, or ask VS Code "
            "agent mode 'What skills do you have available?'")
    if "claude" in targets:
        log("Verify Claude:   ask 'what skills are available?' in a new "
            "claude session")


def main():
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--target", choices=["copilot", "claude", "both"],
                    help="where to install (omit for interactive menu)")
    ap.add_argument("--skills-only", action="store_true",
                    help="skip fetching community skills (offline/proxy)")
    ap.add_argument("--dry-run", action="store_true",
                    help="print planned actions without writing anything")
    args = ap.parse_args()

    targets = pick_targets(args.target)
    custom = sorted(p for p in SKILLS_SRC.iterdir() if p.is_dir())
    if not custom:
        sys.exit(f"No skills found in {SKILLS_SRC}")

    community_src = None
    if args.skills_only:
        log("--skills-only: skipping community skills")
    else:
        cache = update_community_cache(args.dry_run)
        if cache:
            community_src = cache / "skills"

    results = []
    for target in targets:
        dest_root = Path.home() / (".copilot" if target == "copilot"
                                   else ".claude") / "skills"
        log(f"Target {target}: {dest_root}")
        if not args.dry_run:
            dest_root.mkdir(parents=True, exist_ok=True)
        for skill in custom:
            if target == "claude":
                status = install_symlink(skill, dest_root / skill.name,
                                         args.dry_run)
            else:
                status = install_copy(skill, dest_root / skill.name,
                                      args.dry_run)
            results.append((target, skill.name, status))
        if community_src:
            for name in COMMUNITY_SKILLS:
                src = community_src / name
                if not src.is_dir():
                    results.append((target, name, "missing in cache — skipped"))
                    continue
                results.append((target, name,
                                install_copy(src, dest_root / name,
                                             args.dry_run)))
        if target == "copilot":
            results.extend(install_prompts(args.dry_run))

    print_summary(results, targets, args.dry_run)


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd agent-skills && python3 -m unittest test_install -v`
Expected: all tests PASS (26 tests, OK).

- [ ] **Step 5: Smoke-test the CLI dry run**

Run: `cd agent-skills && python3 install.py --target both --dry-run --skills-only`
Expected: planned-actions table listing `caveman-mode` and `explain-logic` for both targets plus `prompt:` rows for copilot (or the VS Code warn), verify hints at the end, nothing written to `~/.copilot` or `~/.claude`.

- [ ] **Step 6: Commit**

```bash
git add agent-skills/install.py agent-skills/test_install.py
git commit -m "feat(agent-skills): community skill fetch and CLI orchestration"
```

---

### Task 6: dotfiles integration — setup.sh, install.sh registration, README

**Files:**
- Create: `agent-skills/setup.sh`
- Create: `agent-skills/README.md`
- Modify: `install.sh:13` (`ALL_TOOLS` array)

**Interfaces:**
- Consumes: `install.py --target claude --skills-only` CLI from Task 5; `lib/common.sh` helpers.
- Produces: `./install.sh agent-skills` working end-to-end.

- [ ] **Step 1: Write setup.sh**

Write `agent-skills/setup.sh`:

```bash
#!/usr/bin/env bash
# Agent skills: symlink custom skills into ~/.claude/skills via install.py.
# Community skills are skipped here (network); fetch them with:
#   python3 agent-skills/install.py --target claude
# Copilot install runs on the work machine:
#   python3 install.py --target copilot
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/../lib/common.sh"

if ! command -v python3 &>/dev/null; then
  warn "python3 not found — skipping agent skills."
  exit 0
fi

python3 "$SCRIPT_DIR/install.py" --target claude --skills-only
ok "Agent skills setup complete."
```

- [ ] **Step 2: Register the tool in install.sh**

In `install.sh`, change line 13 from:

```bash
ALL_TOOLS=(zsh starship nvim wezterm vscode claude terminal-macos iterm2 citrix-vdi)
```

to:

```bash
ALL_TOOLS=(zsh starship nvim wezterm vscode claude agent-skills terminal-macos iterm2 citrix-vdi)
```

(`agent-skills` after `claude` — it depends on nothing, but grouping the AI tooling together reads better. It is not macOS-only, so `MAC_ONLY` is untouched.)

- [ ] **Step 3: Write README.md**

Write `agent-skills/README.md`:

```markdown
# agent-skills

Custom agent skills usable by both GitHub Copilot and Claude Code, plus an
installer. One `SKILL.md` format serves both platforms.

## Layout

- `skills/explain-logic/` — guided code-comprehension walkthroughs
  (PR/branch diffs, files, functions) with language lenses.
- `skills/caveman-mode/` — portable terse-output mode (token saver).
- `prompts/` — Copilot/VS Code `.prompt.md` slash commands
  (`/explain-code`, `/explain-and-review`). Not used by Claude.
- `install.py` — cross-platform installer (Python >= 3.8, stdlib only).

## Install

```bash
python3 install.py --target claude    # home: symlinks into ~/.claude/skills
python3 install.py --target copilot   # work: copies into ~/.copilot/skills
python3 install.py --target both
python3 install.py                    # interactive menu
```

Flags: `--dry-run` (print planned actions), `--skills-only` (skip the
community-skill fetch — offline or behind a proxy).

Also fetched (Copilot community catalog, sparse-cloned into
`~/.agent-skills-cache/`): code-tour, acquire-codebase-knowledge,
context-map, architecture-blueprint-generator, add-educational-comments.

`./install.sh agent-skills` from the repo root runs the Claude install
(custom skills only) as part of normal dotfiles setup.

## Work VDI (Windows, Git Bash)

1. Copy this folder over (or clone the repo).
2. `python3 install.py --target copilot --dry-run` — sanity-check paths.
3. `python3 install.py --target copilot`
4. If the proxy blocks the clone, follow the printed ZIP fallback, or use
   `--skills-only`.

Team distribution per repo: copy `skills/*` into the repo's
`.github/skills/` and `prompts/*` into `.github/prompts/`, then PR.

## Tests

```bash
cd agent-skills && python3 -m unittest test_install -v
```
```

- [ ] **Step 4: Run the integrated tool**

Run: `bash install.sh agent-skills`
Expected: `===== agent-skills =====`, per-skill status lines (`linked` for `caveman-mode` and `explain-logic`), summary table, `✅ Agent skills setup complete.` Then verify: `ls -l ~/.claude/skills/` shows `caveman-mode` and `explain-logic` symlinks pointing into the repo.

- [ ] **Step 5: Commit**

```bash
git add agent-skills/setup.sh agent-skills/README.md install.sh
git commit -m "feat(agent-skills): dotfiles setup.sh integration and README"
```

---

### Task 7: End-to-end verification

**Files:**
- No new files — verification only.

- [ ] **Step 1: Full Claude install (with community skills)**

Run: `cd agent-skills && python3 install.py --target claude`
Expected: awesome-copilot cache cloned/updated; summary shows `caveman-mode`/`explain-logic` as `already linked` and the five community skills as `installed` (copies) under `~/.claude/skills/`.

- [ ] **Step 2: Idempotency check**

Run: `cd agent-skills && python3 install.py --target claude` (again)
Expected: every row reports `already linked` or `up to date`. Nothing reinstalls.

- [ ] **Step 3: Symlink liveness check**

Run: `grep -l "caveman" ~/.claude/skills/caveman-mode/SKILL.md && readlink ~/.claude/skills/explain-logic`
Expected: SKILL.md readable through the link; readlink prints the repo path `.../agent-skills/skills/explain-logic`.

- [ ] **Step 4: Copilot dry run (Mac stand-in for VDI sanity)**

Run: `cd agent-skills && python3 install.py --target copilot --dry-run`
Expected: planned copies into `~/.copilot/skills`, prompt rows (VS Code exists on this Mac) — and nothing actually written: `ls ~/.copilot/skills 2>&1` unchanged from before.

- [ ] **Step 5: Full test suite one last time**

Run: `cd agent-skills && python3 -m unittest test_install -v`
Expected: all 26 tests PASS.

- [ ] **Step 6: Skill triggering check (manual, user)**

In a fresh `claude` session ask: "what skills are available?" — expect `explain-logic` and `caveman-mode` listed. Real Copilot verification happens on the work VDI with `--dry-run` then a real run.
