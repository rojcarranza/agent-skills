# roj-idea-to-project Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add the `roj-idea-to-project` skill: a gated idea-to-build-ready-repo workflow on top of Superpowers, with two tested scripts and an eval set.

**Architecture:** One orchestrating `SKILL.md` (phases 0 to 7) that loads one reference per phase on a stated trigger, fills templates from `assets/`, and gates each phase with `scripts/check_ready.py --phase`. Phase 0 runs `scripts/check_superpowers.py` and installs Superpowers only after a yes. Evals use sandbox fixtures and a fake `claude` CLI.

**Tech Stack:** Markdown (Agent Skills spec), Python 3.9+ standard library, `unittest`, bash fixtures, GitHub Actions.

**Spec:** `docs/superpowers/specs/2026-10-15-idea-to-project-design.md` (issue #29)

## Global Constraints

- Python 3 standard library only; works on macOS, Windows Git Bash and WSL; target 3.9+; type-annotate public functions.
- Both scripts: `--help`; exit 0 on pass, 1 on fail (argparse usage errors exit 2); error lines say how to fix the problem.
- `check_superpowers.py` never installs anything.
- `SKILL.md` under 500 lines and 5,000 tokens; aim 150 to 200 lines.
- Every reference named in `SKILL.md` with the trigger that loads it; a reference over 100 lines opens with `## Contents` in its first 20 lines; a reference may name a sibling only if `SKILL.md` names it too.
- Model aliases only (`opus`, `sonnet`), never versioned model IDs.
- No personal paths (`/Users/`, `/c/dev/`, `C:\dev\`), employer details or real ticket IDs anywhere under `skills/` or in `apm.yml`.
- Frontmatter: only `name`, `description`, `license`, `compatibility`; `license: MIT`; description under 1024 characters, contains "Use when", and is double-quoted (it contains `: `).
- Commits and PR: author and committer Roj Carranza <rojjamescarranza@gmail.com>; no Claude attribution of any kind; Conventional Commits with a scope.
- Work on branch `feat/idea-to-project`. Commit steps below run only after the user's go-ahead for step 4 of the task; never push without asking.
- Never edit `.gitignore`.

## Review Focus

1. `claude plugin list --json` reports a non-semver `version` (a short SHA like `8f814f49002f`) → status must be `ok`, `version_comparable: false`, never `outdated`. Test in Task 2.
2. Superpowers installed twice (user and project scope, one disabled) → the enabled install wins; status `ok`. Test in Task 2.
3. `claude` is on PATH but `plugin list --json` exits 1 or prints non-JSON (old CLI, broken config) → `undetectable` with the CLI's stderr in the message, not a traceback. Test in Task 2.
4. A requirements file with CRLF line endings, or `Verification:` written as a bullet (`- Verification: ...`), or still holding the template placeholder `<test name or command>` → the first two pass, the placeholder fails with its own fix line. Test in Task 3.
5. A `## Non-goals (at least 5)` heading with numbered items, or lines that mention `FR-2.1` outside a requirement bullet (the traceability table) → numbered items count; mentions outside bullets are not checked for EARS. Test in Task 3.

---

## File Structure

| Path | Responsibility |
|---|---|
| `skills/roj-idea-to-project/SKILL.md` | Phases, hard rules, gates, gotchas, portability |
| `skills/roj-idea-to-project/USAGE.md` | Human guide, same shape as `roj-grill-plan/USAGE.md` |
| `skills/roj-idea-to-project/references/*.md` | One per phase (setup, brief, requirements, architecture, agent config), review gates, hand-off |
| `skills/roj-idea-to-project/assets/*` | Templates, three agent files, hooks example; workflow text verbatim plus `Status:` and `## Review log` |
| `skills/roj-idea-to-project/scripts/check_superpowers.py` | Detect Superpowers; JSON report; never installs |
| `skills/roj-idea-to-project/scripts/check_ready.py` | Per-phase gate checks and the Definition of Ready |
| `test_idea_to_project.py` | Unit tests for both scripts |
| `evals/fixtures/build.sh` | Three new fixture kinds |
| `evals/fixtures/fake-claude.sh` | Stand-in `claude` CLI for evals |
| `evals/roj-idea-to-project/{evals,triggers}.json` | Behaviour and trigger evals |
| `test_skills.py` | `NO_GIT`, `claude` fixture modes, `REQUIRED` |
| `.claude-plugin/marketplace.json`, `apm.yml`, `README.md`, `CLAUDE.md`, `.github/workflows/test.yml`, `docs/community-skills.md` | Registration, CI and docs |

---

### Task 0: Branch

- [ ] **Step 1: Create the branch from the current worktree HEAD**

Run: `git switch -c feat/idea-to-project`
Expected: `Switched to a new branch 'feat/idea-to-project'`

- [ ] **Step 2: Check identity**

Run: `git config user.name` → `Roj Carranza`; `git config user.email` → `rojjamescarranza@gmail.com`. If either differs, every commit below uses `git -c user.name="Roj Carranza" -c user.email=rojjamescarranza@gmail.com commit ...`.

### Task 1: Walking skeleton

**Files:**
- Create: `skills/roj-idea-to-project/SKILL.md`, `skills/roj-idea-to-project/USAGE.md`
- Modify: `.claude-plugin/marketplace.json`, `apm.yml`, `README.md` (skills table)

**Interfaces:**
- Produces: the skill folder and its final frontmatter; later tasks only replace the body.

- [ ] **Step 1: Run the suite to see it red once the folder exists without registration**

Create `skills/roj-idea-to-project/SKILL.md`:

```markdown
---
name: roj-idea-to-project
description: "Take a raw app idea to a repo an agent can build: a brief with non-goals, a design, EARS requirements, architecture and ADRs, agent config and a checked Definition of Ready, one approved gate at a time with a fresh-context review at the requirements, architecture and plan gates, then hand off to Superpowers to plan and build. Installs the Superpowers plugin first when it is missing. Use when the user has an app or product idea, wants to plan a new project before Claude builds it, or wants a new or empty repo set up so an agent can build it, even if they never say spec, requirements or architecture. Not for reviewing code (roj-code-review-pr), grilling an existing plan (roj-grill-plan), implementing a story (roj-soundboarding), explaining code (roj-explain-logic) or writing a spec for a feature in an existing codebase."
license: MIT
compatibility: Requires Claude Code or GitHub Copilot CLI with the Superpowers plugin (installed by the skill on first run), and Python 3.
---

# Idea to Project

Walk the user from a raw app idea to a repo an agent can build, one
approved gate at a time, then hand off to Superpowers.
```

Create `skills/roj-idea-to-project/USAGE.md`:

```markdown
# Using the roj-idea-to-project skill

Takes an app idea to a repo an agent can build. Work in progress.
```

Run: `python3 -m unittest test_skills`
Expected: FAIL in `test_marketplace_lists_every_skill` and `test_every_skill_is_a_live_local_dependency` (the new skill is not registered).

- [ ] **Step 2: Register the skill**

In `.claude-plugin/marketplace.json`, add `"./skills/roj-idea-to-project"` to `plugins[0].skills` after `"./skills/roj-grill-plan"`, and change `plugins[0].description` to:
`"Branch and PR review, guided code explanation, repository onboarding tours, root-cause investigation, soundboarding, plan grilling, idea-to-project planning and interview prep"`.

In `apm.yml`, under `# Own skills.`, add after `- ./skills/roj-grill-plan`:

```yaml
    - ./skills/roj-idea-to-project
```

In `README.md`, add this row after the `roj-grill-plan` row of the skills table:

```markdown
| [`roj-idea-to-project`](skills/roj-idea-to-project/USAGE.md) | Raw app idea → brief, design, EARS requirements, architecture and ADRs, agent config and a checked Definition of Ready, one approved gate at a time with fresh-context reviews, then a hand-off to Superpowers. Installs Superpowers first when it is missing. Never touches git. |
```

- [ ] **Step 3: Run the suites**

Run: `python3 -m unittest test_install test_skills`
Expected: OK

Run: `python3 tools/sync_shared.py --check`
Expected: exit 0

- [ ] **Step 4: Validate against the spec tool**

Run: `uvx skills-ref validate skills/roj-idea-to-project`; if `uvx` is missing, `pipx run skills-ref validate skills/roj-idea-to-project`.
Expected: valid. If neither can install the tool, record the exact error for the PR description and continue.

- [ ] **Step 5: Commit**

```bash
git add skills/roj-idea-to-project .claude-plugin/marketplace.json apm.yml README.md
git commit -m "feat(skills): add roj-idea-to-project skeleton"
```

### Task 2: `check_superpowers.py` (TDD) and CI

**Files:**
- Create: `skills/roj-idea-to-project/scripts/check_superpowers.py`
- Create: `test_idea_to_project.py`
- Modify: `.github/workflows/test.yml`, `README.md` (Tests block), `CLAUDE.md` (Before pushing)

**Interfaces:**
- Produces: CLI `check_superpowers.py [--client auto|claude|copilot] [--min-version X.Y.Z]`; stdout one JSON object with keys `client` (str or null), `installed` (bool), `version` (str or null), `version_comparable` (bool), `enabled` (bool or null), `status` (`ok|outdated|missing|disabled|undetectable`), `next` (list of str); exit 0 for `ok`/`outdated`, else 1. Python: `parse_version(text: str | None) -> tuple[int, int, int] | None`, `check(client: str, minimum: tuple[int, int, int]) -> dict`.

- [ ] **Step 1: Write the failing tests**

Create `test_idea_to_project.py`:

```python
"""The roj-idea-to-project scripts: check_superpowers.py and check_ready.py.

  python3 -m unittest test_idea_to_project -v
"""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SCRIPTS = ROOT / "skills" / "roj-idea-to-project" / "scripts"
CHECK_SP = SCRIPTS / "check_superpowers.py"
CHECK_READY = SCRIPTS / "check_ready.py"


def fake_cli(bin_dir: Path, name: str, stdout: str = "", code: int = 0,
             stderr: str = "") -> None:
    """Write a stand-in CLI called `name` into bin_dir that prints stdout,
    prints stderr, logs its arguments to calls.log and exits with code."""
    body = (
        "import sys\n"
        f"open({str(bin_dir / 'calls.log')!r}, 'a', encoding='utf-8')"
        f".write({name!r} + ' ' + ' '.join(sys.argv[1:]) + '\\n')\n"
        f"sys.stdout.write({stdout!r})\n"
        f"sys.stderr.write({stderr!r})\n"
        f"sys.exit({code})\n")
    script = bin_dir / f"{name}.py"
    script.write_text(body, encoding="utf-8")
    if os.name == "nt":
        (bin_dir / f"{name}.cmd").write_text(
            f'@"{sys.executable}" "%~dp0{name}.py" %*\n', encoding="utf-8")
    else:
        exe = bin_dir / name
        exe.write_text(f"#!{sys.executable}\n{body}", encoding="utf-8")
        exe.chmod(0o755)


def run_script(script: Path, args, path_dir: Path):
    env = dict(os.environ, PATH=str(path_dir))
    return subprocess.run([sys.executable, str(script), *args], env=env,
                          capture_output=True, text=True, encoding="utf-8")


def plugin(pid: str, version: str, enabled: bool = True,
           scope: str = "user") -> dict:
    return {"id": pid, "version": version, "scope": scope,
            "enabled": enabled, "installPath": "/tmp/plugins/x"}


class CheckSuperpowersTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.bin = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def claude_list(self, plugins, code=0, stderr=""):
        fake_cli(self.bin, "claude", json.dumps(plugins), code, stderr)

    def run_check(self, *args):
        p = run_script(CHECK_SP, args, self.bin)
        report = json.loads(p.stdout) if p.stdout.strip() else None
        return p, report

    def test_help(self):
        p = run_script(CHECK_SP, ["--help"], self.bin)
        self.assertEqual(p.returncode, 0)
        self.assertIn("never installs", p.stdout.lower())

    def test_ok_when_enabled_and_current(self):
        self.claude_list([plugin("superpowers@claude-plugins-official",
                                 "7.0.0")])
        p, r = self.run_check()
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertEqual(r["status"], "ok")
        self.assertEqual(r["client"], "claude")
        self.assertEqual(r["version"], "7.0.0")
        self.assertTrue(r["version_comparable"])
        self.assertEqual(r["next"], [])

    def test_missing_names_the_install_command(self):
        self.claude_list([plugin("caveman@caveman", "4.0.1")])
        p, r = self.run_check()
        self.assertEqual(p.returncode, 1)
        self.assertEqual(r["status"], "missing")
        self.assertFalse(r["installed"])
        self.assertEqual(r["next"], [
            "claude plugin install superpowers@claude-plugins-official"])

    def test_disabled_names_the_enable_command(self):
        self.claude_list([plugin("superpowers@superpowers-marketplace",
                                 "7.0.0", enabled=False)])
        p, r = self.run_check()
        self.assertEqual(p.returncode, 1)
        self.assertEqual(r["status"], "disabled")
        self.assertEqual(r["next"], [
            "claude plugin enable superpowers@superpowers-marketplace"])

    def test_outdated_passes_with_update_command(self):
        self.claude_list([plugin("superpowers@claude-plugins-official",
                                 "6.4.1")])
        p, r = self.run_check()
        self.assertEqual(p.returncode, 0)
        self.assertEqual(r["status"], "outdated")
        self.assertEqual(r["next"], [
            "claude plugin update superpowers@claude-plugins-official"])
        self.assertIn("6.4.1", p.stderr)
        self.assertIn("/reload-plugins", p.stderr)

    def test_min_version_flag(self):
        self.claude_list([plugin("superpowers@claude-plugins-official",
                                 "6.4.1")])
        p, r = self.run_check("--min-version", "6.0.0")
        self.assertEqual(r["status"], "ok")

    def test_sha_version_is_not_comparable_and_not_outdated(self):
        self.claude_list([plugin("superpowers@claude-plugins-official",
                                 "8f814f49002f")])
        p, r = self.run_check()
        self.assertEqual(p.returncode, 0)
        self.assertEqual(r["status"], "ok")
        self.assertFalse(r["version_comparable"])
        self.assertIn("cannot compare", p.stderr)

    def test_enabled_install_wins_over_disabled_one(self):
        self.claude_list([
            plugin("superpowers@superpowers-marketplace", "7.0.0",
                   enabled=False, scope="project"),
            plugin("superpowers@claude-plugins-official", "7.0.0")])
        p, r = self.run_check()
        self.assertEqual(r["status"], "ok")

    def test_similar_plugin_name_is_not_superpowers(self):
        self.claude_list([plugin("superpowers-lab@obra", "1.0.0")])
        p, r = self.run_check()
        self.assertEqual(r["status"], "missing")

    def test_cli_failure_is_undetectable_not_a_traceback(self):
        fake_cli(self.bin, "claude", "", 1, "error: unknown option '--json'")
        p, r = self.run_check()
        self.assertEqual(p.returncode, 1)
        self.assertEqual(r["status"], "undetectable")
        self.assertIn("unknown option", p.stderr)
        self.assertNotIn("Traceback", p.stderr)

    def test_non_json_output_is_undetectable(self):
        fake_cli(self.bin, "claude", "Installed plugins:\n  none\n")
        p, r = self.run_check()
        self.assertEqual(r["status"], "undetectable")

    def test_no_cli_is_undetectable_and_points_at_skill_list(self):
        p, r = self.run_check()
        self.assertEqual(p.returncode, 1)
        self.assertEqual(r["status"], "undetectable")
        self.assertIsNone(r["client"])
        self.assertIn("superpowers:brainstorming", p.stderr)

    def test_copilot_missing_needs_two_commands(self):
        fake_cli(self.bin, "copilot", "No plugins installed.\n\n"
                 "Use 'copilot plugin install <source>' to install a plugin.\n")
        p, r = self.run_check()
        self.assertEqual(r["client"], "copilot")
        self.assertEqual(r["status"], "missing")
        self.assertEqual(r["next"], [
            "copilot plugin marketplace add obra/superpowers-marketplace",
            "copilot plugin install superpowers@superpowers-marketplace"])

    def test_copilot_installed_with_version(self):
        fake_cli(self.bin, "copilot", "Installed plugins:\n"
                 "  superpowers@superpowers-marketplace (v7.0.0)\n")
        p, r = self.run_check("--client", "copilot")
        self.assertEqual(r["status"], "ok")
        self.assertEqual(r["version"], "7.0.0")

    def test_copilot_unparsed_version_is_unknown(self):
        fake_cli(self.bin, "copilot", "superpowers  enabled\n")
        p, r = self.run_check("--client", "copilot")
        self.assertEqual(r["status"], "ok")
        self.assertEqual(r["version"], "unknown")
        self.assertFalse(r["version_comparable"])

    def test_copilot_disabled(self):
        fake_cli(self.bin, "copilot",
                 "superpowers@superpowers-marketplace 7.0.0 (disabled)\n")
        p, r = self.run_check("--client", "copilot")
        self.assertEqual(r["status"], "disabled")
        self.assertEqual(r["next"], [
            "copilot plugin enable superpowers@superpowers-marketplace"])

    def test_auto_prefers_claude(self):
        self.claude_list([plugin("superpowers@claude-plugins-official",
                                 "7.0.0")])
        fake_cli(self.bin, "copilot", "No plugins installed.\n")
        p, r = self.run_check()
        self.assertEqual(r["client"], "claude")

    def test_never_runs_an_install(self):
        self.claude_list([])
        self.run_check()
        calls = (self.bin / "calls.log").read_text("utf-8")
        self.assertEqual(calls.strip(), "claude plugin list --json")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the tests to see them fail**

Run: `python3 -m unittest test_idea_to_project -v`
Expected: every `CheckSuperpowersTest` test FAILs or ERRORs (script missing: `can't open file`).

- [ ] **Step 3: Write the script**

Create `skills/roj-idea-to-project/scripts/check_superpowers.py`:

```python
#!/usr/bin/env python3
"""Report whether the Superpowers plugin is installed, enabled and current.

Usage: check_superpowers.py [--client auto|claude|copilot] [--min-version 7.0.0]

Reads `claude plugin list --json` (Claude Code) or `copilot plugin list`
(Copilot CLI). This script never installs anything: it names the commands
for the user to approve in "next".

stdout: one JSON object
  client              "claude", "copilot" or null when neither CLI is on PATH
  installed           true when a superpowers@<marketplace> install exists
  version             the installed version, "unknown", or null
  version_comparable  false when version is not X.Y.Z (a commit SHA)
  enabled             true/false, or null when unknown
  status              ok | outdated | missing | disabled | undetectable
  next                commands to run, in order; empty when nothing to do
stderr: one line for the human.

Exit codes: 0 for ok and outdated, 1 for missing, disabled, undetectable.
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from typing import Optional

OFFICIAL = "claude-plugins-official"
COMMUNITY = "superpowers-marketplace"
VERSION_RE = re.compile(r"\bv?(\d+)\.(\d+)\.(\d+)\b")
PASSING = {"ok", "outdated"}


def parse_version(text: Optional[str]) -> Optional[tuple[int, int, int]]:
    """(major, minor, patch) from text, or None when there is none."""
    m = VERSION_RE.search(text or "")
    return (int(m[1]), int(m[2]), int(m[3])) if m else None


def run(cmd: list[str]) -> Optional[tuple[int, str, str]]:
    """(exit code, stdout, stderr) of cmd, or None when it is not on PATH."""
    exe = shutil.which(cmd[0])
    if not exe:
        return None
    p = subprocess.run([exe, *cmd[1:]], capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    return p.returncode, p.stdout, p.stderr


def report(client: Optional[str], status: str, version: Optional[str] = None,
           enabled: Optional[bool] = None, nxt: Optional[list[str]] = None,
           note: str = "") -> dict:
    return {"client": client,
            "installed": status in {"ok", "outdated", "disabled"},
            "version": version,
            "version_comparable": parse_version(version) is not None,
            "enabled": enabled, "status": status, "next": nxt or [],
            "_note": note}


def grade(client: str, version: str, enabled: bool, plugin_id: str,
          minimum: tuple[int, int, int]) -> dict:
    """Status of one found install."""
    tool = "claude" if client == "claude" else "copilot"
    if not enabled:
        return report(client, "disabled", version, False,
                      [f"{tool} plugin enable {plugin_id}"],
                      f"Superpowers is installed but disabled: run "
                      f"`{tool} plugin enable {plugin_id}`, then reload.")
    found = parse_version(version)
    if found is None:
        return report(client, "ok", version, True, [],
                      f"Superpowers {version} is installed; cannot compare "
                      f"that version with {'.'.join(map(str, minimum))}.")
    if found < minimum:
        reload = ("/reload-plugins" if client == "claude"
                  else "restart copilot")
        return report(client, "outdated", version, True,
                      [f"{tool} plugin update {plugin_id}"],
                      f"Superpowers {version} is older than "
                      f"{'.'.join(map(str, minimum))}: offer "
                      f"`{tool} plugin update {plugin_id}`, then {reload}.")
    return report(client, "ok", version, True, [],
                  f"Superpowers {version} is installed and enabled.")


def from_claude(minimum: tuple[int, int, int]) -> Optional[dict]:
    got = run(["claude", "plugin", "list", "--json"])
    if got is None:
        return None
    code, out, err = got
    try:
        plugins = json.loads(out) if code == 0 else None
    except ValueError:
        plugins = None
    if not isinstance(plugins, list):
        detail = (err or out).strip().splitlines()
        return report("claude", "undetectable", note=(
            "`claude plugin list --json` failed"
            + (f": {detail[-1]}" if detail else "")
            + ". Check whether superpowers:brainstorming is in your skill "
              "list, or update Claude Code."))
    mine = [p for p in plugins if isinstance(p, dict)
            and str(p.get("id", "")).split("@")[0] == "superpowers"]
    if not mine:
        cmd = f"claude plugin install superpowers@{OFFICIAL}"
        return report("claude", "missing", nxt=[cmd], note=(
            f"Superpowers is not installed: `{cmd}` (fallback: `claude "
            f"plugin marketplace add obra/{COMMUNITY}`, then `claude plugin "
            f"install superpowers@{COMMUNITY}`), then /reload-plugins."))
    best = sorted(mine, key=lambda p: not p.get("enabled"))[0]
    return grade("claude", str(best.get("version")), bool(best.get("enabled")),
                 str(best["id"]), minimum)


def from_copilot(minimum: tuple[int, int, int]) -> Optional[dict]:
    got = run(["copilot", "plugin", "list"])
    if got is None:
        return None
    code, out, err = got
    if code != 0:
        detail = (err or out).strip().splitlines()
        return report("copilot", "undetectable", note=(
            "`copilot plugin list` failed"
            + (f": {detail[-1]}" if detail else "") + "."))
    lines = [ln for ln in out.splitlines()
             if re.search(r"\bsuperpowers\b", ln, re.I)]
    if not lines:
        cmds = [f"copilot plugin marketplace add obra/{COMMUNITY}",
                f"copilot plugin install superpowers@{COMMUNITY}"]
        return report("copilot", "missing", nxt=cmds, note=(
            "Superpowers is not installed: run `" + "`, then `".join(cmds)
            + "`, then restart copilot."))
    line = lines[0]
    found = parse_version(line)
    version = ".".join(map(str, found)) if found else "unknown"
    return grade("copilot", version, "disabled" not in line.lower(),
                 f"superpowers@{COMMUNITY}", minimum)


def check(client: str, minimum: tuple[int, int, int]) -> dict:
    """Report for `client` (auto tries claude, then copilot)."""
    order = {"auto": (from_claude, from_copilot), "claude": (from_claude,),
             "copilot": (from_copilot,)}[client]
    for probe in order:
        result = probe(minimum)
        if result is not None:
            return result
    return report(None, "undetectable", note=(
        "Neither `claude` nor `copilot` is on PATH: check whether "
        "superpowers:brainstorming is in your skill list; listed means "
        "installed, otherwise it is missing."))


def main(argv: Optional[list[str]] = None) -> int:
    ap = argparse.ArgumentParser(
        description="Report whether Superpowers is installed, enabled and "
                    "current. Never installs anything.",
        epilog="Exit 0: ok or outdated. Exit 1: missing, disabled or "
               "undetectable. stdout is JSON; `next` lists the commands to "
               "run after the user says yes.")
    ap.add_argument("--client", choices=("auto", "claude", "copilot"),
                    default="auto")
    ap.add_argument("--min-version", default="7.0.0",
                    help="oldest version that is not reported as outdated")
    args = ap.parse_args(argv)
    minimum = parse_version(args.min_version)
    if minimum is None:
        ap.error("--min-version must look like 7.0.0")
    result = check(args.client, minimum)
    note = result.pop("_note")
    print(json.dumps(result))
    print(note, file=sys.stderr)
    return 0 if result["status"] in PASSING else 1


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run the tests to see them pass**

Run: `python3 -m unittest test_idea_to_project -v`
Expected: all `CheckSuperpowersTest` tests PASS.

- [ ] **Step 5: Smoke-test against the real CLI**

Run: `python3 skills/roj-idea-to-project/scripts/check_superpowers.py`
Expected on the authoring machine: `"status": "outdated"`, `"version": "6.4.1"`, exit 0, stderr naming `claude plugin update superpowers@claude-plugins-official`.

- [ ] **Step 6: Run the module in CI and in the documented checks**

In `.github/workflows/test.yml`, job `unittest`, add after the `Skills follow the Agent Skills spec` step:

```yaml
      - name: roj-idea-to-project scripts
        run: python -m unittest test_idea_to_project
```

In `README.md` replace `python3 -m unittest test_install test_skills -v` with `python3 -m unittest test_install test_skills test_idea_to_project -v`. In `CLAUDE.md` "Before pushing" replace `python3 -m unittest test_install test_skills` with `python3 -m unittest test_install test_skills test_idea_to_project`.

- [ ] **Step 7: Commit**

```bash
git add skills/roj-idea-to-project/scripts/check_superpowers.py test_idea_to_project.py .github/workflows/test.yml README.md CLAUDE.md
git commit -m "feat(skills): detect superpowers for roj-idea-to-project"
```

### Task 3: `check_ready.py` (TDD)

**Files:**
- Create: `skills/roj-idea-to-project/scripts/check_ready.py`
- Modify: `test_idea_to_project.py` (append a test class)

**Interfaces:**
- Consumes: `run_script(script, args, path_dir)` and `CHECK_READY` from Task 2's test module.
- Produces: CLI `check_ready.py [--phase brief|requirements|architecture|agent-config|all] [ROOT]`; prints one issue per line, then `READY` or `NOT READY: <n> issues`; exit 0 or 1. Python: `issues(root: Path, phase: str) -> list[str]`. Exact messages that SKILL.md and the evals quote:
  - `docs/brief.md has <n> non-goals: add at least <5-n> more under ## Non-goals`
  - `FR-<n> has no Verification line: add "Verification: <test name or command>"`
  - `FR-<n> Verification is still the template placeholder: name the test or command`
  - `FR-<x.y> is not in EARS form: use WHEN/IF/WHILE/WHERE ... THE SYSTEM SHALL ...`
  - `docs/requirements.md has no NFR-SEC line: add "- NFR-SEC: authn ...; authz ...; input validated at ...; secrets from ..."`
  - `no ADR covers <area>: add docs/adr/NNNN-<area>.md (its file name or title must mention one of: <keywords>)`
  - `CLAUDE.md has <n> lines: cut it to under 100 (turn must-never-happen rules into hooks or tests)`
  - `<path> is missing: write it from the skill's assets/<template>`

- [ ] **Step 1: Write the failing tests**

Append to `test_idea_to_project.py` (before the `if __name__` block):

```python
BRIEF_OK = """# Plants Brief
Status: Approved 2026-10-15
## Problem (2 to 3 sentences)
Plants die.
## Non-goals (at least 5)
- No social feed
- No marketplace
- No native app
1. No sensors
2. No multi-language UI
## Constraints (budget, cloud, compliance, timeline)
"""

REQ_OK = """# Requirements: Plants (v0.1, 2026-10-15)
Status: Approved 2026-10-15
## Functional requirements
### FR-1 Reminders
User story: As an owner, I want reminders so that plants live.
- FR-1.1 WHEN a plant is due THE SYSTEM SHALL send a reminder.
- FR-1.2 IF the reminder fails THEN THE SYSTEM SHALL retry once.
Verification: test_reminders
### FR-2 Plants
- FR-2.1 WHILE a plant exists THE SYSTEM SHALL show its next due date.
- Verification: tests/test_plants.py
## Non-functional requirements
- NFR-PERF: p95 < 200 ms at 10 rps
- NFR-SEC: authn magic link; authz owner only; input validated at API; secrets from env
## Traceability: requirement -> task -> test
- FR-2.1 -> Task 3 -> test_plants
"""

ADRS = {
    "0001-language.md": "# ADR-0001: Python 3.12\n",
    "0002-database.md": "# ADR-0002: SQLite\n",
    "0003-auth.md": "# ADR-0003: Magic links\n",
    "0004-hosting.md": "# ADR-0004: Fly.io\n",
    "0005-x.md": "# ADR-0005: Structured logging and metrics\n",
}


class CheckReadyTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.write("docs/brief.md", BRIEF_OK)
        self.write("docs/requirements.md", REQ_OK)
        self.write("docs/architecture.md", "# Architecture\n")
        for name, text in ADRS.items():
            self.write(f"docs/adr/{name}", text)
        self.write("CLAUDE.md", "# Plants\n" + "- line\n" * 40)

    def tearDown(self):
        self.tmp.cleanup()

    def write(self, rel, text, newline="\n"):
        p = self.root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text.replace("\n", newline), encoding="utf-8",
                     newline="")

    def run_ready(self, *args):
        return run_script(CHECK_READY, [*args, str(self.root)],
                          Path(self.tmp.name))

    def assert_fails_with(self, line, *args):
        p = self.run_ready(*args)
        self.assertEqual(p.returncode, 1, p.stdout)
        self.assertIn(line, p.stdout)
        self.assertIn("NOT READY", p.stdout)

    def test_help(self):
        p = run_script(CHECK_READY, ["--help"], self.root)
        self.assertEqual(p.returncode, 0)
        self.assertIn("--phase", p.stdout)

    def test_ready_project_passes(self):
        p = self.run_ready()
        self.assertEqual(p.returncode, 0, p.stdout)
        self.assertTrue(p.stdout.strip().endswith("READY"))

    def test_crlf_files_pass(self):
        self.write("docs/requirements.md", REQ_OK, newline="\r\n")
        self.write("docs/brief.md", BRIEF_OK, newline="\r\n")
        self.assertEqual(self.run_ready().returncode, 0)

    def test_two_non_goals(self):
        self.write("docs/brief.md",
                   "# B\n## Non-goals (at least 5)\n- a\n- b\n## Open questions\n")
        self.assert_fails_with(
            "docs/brief.md has 2 non-goals: add at least 3 more under "
            "## Non-goals", "--phase", "brief")

    def test_missing_verification(self):
        self.write("docs/requirements.md",
                   REQ_OK.replace("- Verification: tests/test_plants.py\n", ""))
        self.assert_fails_with(
            'FR-2 has no Verification line: add "Verification: '
            '<test name or command>"', "--phase", "requirements")

    def test_placeholder_verification(self):
        self.write("docs/requirements.md", REQ_OK.replace(
            "Verification: test_reminders",
            "Verification: <test name or command>"))
        self.assert_fails_with(
            "FR-1 Verification is still the template placeholder: name the "
            "test or command", "--phase", "requirements")

    def test_not_ears(self):
        self.write("docs/requirements.md", REQ_OK.replace(
            "- FR-1.2 IF the reminder fails THEN THE SYSTEM SHALL retry once.",
            "- FR-1.2 The system retries failed reminders."))
        self.assert_fails_with(
            "FR-1.2 is not in EARS form: use WHEN/IF/WHILE/WHERE ... "
            "THE SYSTEM SHALL ...", "--phase", "requirements")

    def test_traceability_mentions_are_not_checked(self):
        p = self.run_ready("--phase", "requirements")
        self.assertEqual(p.returncode, 0, p.stdout)

    def test_no_nfr_sec(self):
        self.write("docs/requirements.md", "\n".join(
            ln for ln in REQ_OK.splitlines() if "NFR-SEC" not in ln) + "\n")
        self.assert_fails_with("docs/requirements.md has no NFR-SEC line",
                               "--phase", "requirements")

    def test_adr_area_missing(self):
        (self.root / "docs/adr/0005-x.md").unlink()
        self.assert_fails_with("no ADR covers observability",
                               "--phase", "architecture")

    def test_adr_matched_by_title(self):
        # 0005-x.md matches observability only through its title.
        p = self.run_ready("--phase", "architecture")
        self.assertEqual(p.returncode, 0, p.stdout)

    def test_claude_md_too_long(self):
        self.write("CLAUDE.md", "- x\n" * 120)
        self.assert_fails_with(
            "CLAUDE.md has 120 lines: cut it to under 100",
            "--phase", "agent-config")

    def test_missing_file_names_template(self):
        (self.root / "CLAUDE.md").unlink()
        self.assert_fails_with(
            "CLAUDE.md is missing: write it from the skill's "
            "assets/claude-md-template.md", "--phase", "agent-config")

    def test_phase_limits_checks(self):
        (self.root / "CLAUDE.md").unlink()
        p = self.run_ready("--phase", "requirements")
        self.assertEqual(p.returncode, 0, p.stdout)

    def test_all_lists_every_issue(self):
        (self.root / "CLAUDE.md").unlink()
        (self.root / "docs/adr/0003-auth.md").unlink()
        p = self.run_ready()
        self.assertIn("NOT READY: 2 issues", p.stdout)

    def test_root_not_a_directory(self):
        p = run_script(CHECK_READY, [str(self.root / "nope")], self.root)
        self.assertEqual(p.returncode, 1)
        self.assertIn("is not a directory", p.stdout + p.stderr)
```

- [ ] **Step 2: Run the tests to see them fail**

Run: `python3 -m unittest test_idea_to_project.CheckReadyTest -v`
Expected: every test FAILs or ERRORs (script missing).

- [ ] **Step 3: Write the script**

Create `skills/roj-idea-to-project/scripts/check_ready.py`:

```python
#!/usr/bin/env python3
"""Check a project against the roj-idea-to-project gates.

Usage: check_ready.py [--phase brief|requirements|architecture|agent-config|all] [ROOT]

ROOT defaults to the current directory. --phase defaults to all, which is
the Definition of Ready. Prints every issue with its fix, then READY or
NOT READY: <n> issues.

Exit codes: 0 ready, 1 issues found (or ROOT is not a directory),
2 bad arguments.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Optional

PHASES = ("brief", "requirements", "architecture", "agent-config")
ITEM_RE = re.compile(r"^\s*(?:[-*]|\d+[.)])\s+\S")
FR_ITEM_RE = re.compile(r"^\s*[-*]\s*(FR-\d+\.\d+)\b(.*)$")
FR_HEAD_RE = re.compile(r"^###\s+(FR-\d+)\b")
EARS_RE = re.compile(r"\b(WHEN|IF|WHILE|WHERE)\b.*\bSHALL\b")
VERIFY_RE = re.compile(r"^\s*(?:[-*]\s*)?Verification:\s*(.*)$")
NFR_SEC_RE = re.compile(r"^\s*[-*]\s*NFR-SEC\b")
ADR_AREAS = {
    "language": ("language", "stack", "runtime", "framework"),
    "persistence": ("persistence", "database", "storage", "datastore"),
    "auth": ("auth", "authentication", "authorization", "identity"),
    "deploy target": ("deploy", "deployment", "hosting", "infrastructure"),
    "observability": ("observability", "logging", "monitoring", "telemetry"),
}


def read(path: Path) -> Optional[list[str]]:
    if not path.is_file():
        return None
    return path.read_text(encoding="utf-8", errors="replace").splitlines()


def missing(rel: str, template: str) -> str:
    return f"{rel} is missing: write it from the skill's assets/{template}"


def section(lines: list[str], heading: str) -> list[str]:
    """Lines under the first `## <heading>...` up to the next `## `."""
    out, inside = [], False
    for ln in lines:
        if ln.startswith("## "):
            if inside:
                break
            inside = ln[3:].strip().lower().startswith(heading.lower())
            continue
        if inside:
            out.append(ln)
    return out


def check_brief(root: Path) -> list[str]:
    lines = read(root / "docs" / "brief.md")
    if lines is None:
        return [missing("docs/brief.md", "brief-template.md")]
    n = sum(1 for ln in section(lines, "Non-goals") if ITEM_RE.match(ln))
    if n >= 5:
        return []
    return [f"docs/brief.md has {n} non-goals: add at least {5 - n} more "
            f"under ## Non-goals"]


def check_requirements(root: Path) -> list[str]:
    lines = read(root / "docs" / "requirements.md")
    if lines is None:
        return [missing("docs/requirements.md", "requirements-template.md")]
    found: list[str] = []
    blocks: dict[str, Optional[str]] = {}
    current: Optional[str] = None
    for ln in lines:
        head = FR_HEAD_RE.match(ln)
        if head:
            current = head[1]
            blocks[current] = None
            continue
        if ln.startswith("## ") or ln.startswith("### "):
            current = None
            continue
        # Only requirement bullets inside a ### FR-<n> block; the same IDs
        # appear in the traceability section as plain references.
        item = FR_ITEM_RE.match(ln) if current else None
        if item and not EARS_RE.search(item[2]):
            found.append(f"{item[1]} is not in EARS form: use "
                         "WHEN/IF/WHILE/WHERE ... THE SYSTEM SHALL ...")
        verify = VERIFY_RE.match(ln)
        if verify and current and blocks[current] is None:
            blocks[current] = verify[1].strip()
    if not blocks:
        found.append("docs/requirements.md has no ### FR-<n> blocks: add one "
                     "per feature from the template")
    for fr, value in blocks.items():
        if value is None or not value:
            found.append(f'{fr} has no Verification line: add '
                         f'"Verification: <test name or command>"')
        elif value.startswith("<"):
            found.append(f"{fr} Verification is still the template "
                         "placeholder: name the test or command")
    if not any(NFR_SEC_RE.match(ln) for ln in lines):
        found.append('docs/requirements.md has no NFR-SEC line: add "- NFR-SEC: '
                     'authn ...; authz ...; input validated at ...; secrets '
                     'from ..."')
    return found


def check_architecture(root: Path) -> list[str]:
    found = []
    if read(root / "docs" / "architecture.md") is None:
        found.append(missing("docs/architecture.md",
                             "architecture-template.md"))
    texts = []
    for adr in sorted((root / "docs" / "adr").glob("*.md")):
        title = next((ln for ln in read(adr) or [] if ln.startswith("# ")), "")
        texts.append(f"{adr.stem} {title}".lower())
    for area, words in ADR_AREAS.items():
        if not any(w in t for t in texts for w in words):
            slug = area.replace(" ", "-")
            found.append(f"no ADR covers {area}: add docs/adr/NNNN-{slug}.md "
                         f"(its file name or title must mention one of: "
                         f"{', '.join(words)})")
    return found


def check_agent_config(root: Path) -> list[str]:
    lines = read(root / "CLAUDE.md")
    if lines is None:
        return [missing("CLAUDE.md", "claude-md-template.md")]
    if len(lines) >= 100:
        return [f"CLAUDE.md has {len(lines)} lines: cut it to under 100 "
                "(turn must-never-happen rules into hooks or tests)"]
    return []


CHECKS = {"brief": check_brief, "requirements": check_requirements,
          "architecture": check_architecture,
          "agent-config": check_agent_config}


def issues(root: Path, phase: str) -> list[str]:
    """Every issue for `phase` ("all" runs every phase in order)."""
    phases = PHASES if phase == "all" else (phase,)
    return [i for p in phases for i in CHECKS[p](root)]


def main(argv: Optional[list[str]] = None) -> int:
    ap = argparse.ArgumentParser(
        description="Check a project against the roj-idea-to-project gates.",
        epilog="Exit 0: READY. Exit 1: issues found, each printed with its "
               "fix. Run, fix, re-run until it passes.")
    ap.add_argument("--phase", choices=(*PHASES, "all"), default="all")
    ap.add_argument("root", nargs="?", default=".",
                    help="project folder (default: current directory)")
    args = ap.parse_args(argv)
    root = Path(args.root)
    if not root.is_dir():
        print(f"{root} is not a directory: pass the project folder as ROOT")
        return 1
    found = issues(root, args.phase)
    for line in found:
        print(line)
    print(f"NOT READY: {len(found)} issues" if found else "READY")
    return 1 if found else 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run the tests to see them pass**

Run: `python3 -m unittest test_idea_to_project -v`
Expected: all tests PASS.

- [ ] **Step 5: Commit**

```bash
git add skills/roj-idea-to-project/scripts/check_ready.py test_idea_to_project.py
git commit -m "feat(skills): check the definition of ready for roj-idea-to-project"
```

### Task 4: Assets

**Files:**
- Create under `skills/roj-idea-to-project/assets/`: `brief-template.md`, `requirements-template.md`, `architecture-template.md`, `adr-template.md`, `claude-md-template.md`, `progress-template.md`, `agents/security-reviewer.md`, `agents/architecture-guardian.md`, `agents/test-auditor.md`, `hooks-settings.example.json`

**Interfaces:**
- Produces: template headings that `check_ready.py` parses (`## Non-goals`, `### FR-<n>`, `Verification:`, `- NFR-SEC`, `# ADR-`). Every phase file template carries a `Status: Draft` line under its title (phase approval turns it into `Status: Approved YYYY-MM-DD`) and, where a fresh review runs (requirements, architecture), ends with `## Review log`.

- [ ] **Step 1: Write the templates**

`brief-template.md`:

```markdown
# <Project> Brief
Status: Draft
## Problem (2 to 3 sentences)
## Target user and main job-to-be-done
## Pitch (3 sentences max)
## Success metrics (measurable)
## MVP scope (3 to 5 bullets)
## Non-goals (at least 5)
## Constraints (budget, cloud, compliance, timeline)
## Open questions
```

`requirements-template.md`:

```markdown
# Requirements: <Project> (v0.x, YYYY-MM-DD)
Status: Draft
## Functional requirements
### FR-1 <name>
User story: As a <role>, I want <capability> so that <benefit>.
- FR-1.1 WHEN <trigger> THE SYSTEM SHALL <response>.
- FR-1.2 IF <unwanted condition> THEN THE SYSTEM SHALL <response>.
- FR-1.3 WHILE <state> THE SYSTEM SHALL <behavior>.
Verification: <test name or command>
## Non-functional requirements
- NFR-PERF: p95 < X ms at Y rps
- NFR-SEC: authn <...>; authz <...>; input validated at <boundary>; secrets from <vault>
- NFR-OPS: logs, metrics, RTO/RPO
- NFR-COST: < N per month
## Out of scope
## Traceability: requirement -> task -> test
## Review log
```

`architecture-template.md`:

```markdown
# Architecture
Status: Draft
## System context (C4 L1)
## Containers (C4 L2)
## Data model and ownership
## Interfaces (link openapi.yaml / *.proto)
## Cross-cutting: auth, config, observability, errors
## Deployment: envs, IaC, CI/CD, rollback
## Threat model: assets, trust boundaries, top threats
## Rules for agents: no new service, dependency or datastore without an ADR
## Review log
```

`adr-template.md`:

```markdown
# ADR-NNNN: <Decision>
Status: Proposed | Accepted | Superseded
## Context
## Decision
## Alternatives considered
## Consequences
```

`claude-md-template.md`:

```markdown
# <Project>
Stack: <...>. See docs/architecture.md.
## Commands
- Build: <cmd> | Test: <cmd> | Single test: <cmd> | Lint: <cmd> | Run: <cmd>
## Rules
- TDD: failing test first. Never edit a test to pass without asking.
- Follow docs/adr/. No new dependency, service or datastore without an ADR.
- Small commits. Work only on the current plan task.
## Gotchas
- <non-obvious env var, port, codegen step>
## When compacting
- Keep: current task, modified files, test commands.
```

`progress-template.md`:

```markdown
# Progress: <Project>
## Feature checklist (tick only when verification passes)
- [ ] FR-1 ... (verify: <cmd>)
## Log
- YYYY-MM-DD session N: done Task X; next Task Y; blockers: none
```

- [ ] **Step 2: Write the three agent files verbatim from the workflow**

`agents/security-reviewer.md`:

```markdown
---
name: security-reviewer
description: Reviews a diff or branch for security issues. Use before merging any PR.
model: opus
tools: Read, Grep, Glob, Bash
---
You are a security engineer who did not write this code.
Review the changes (git diff main...HEAD) for:
- injection (SQL, command, template), XSS, SSRF, path traversal
- authn/authz gaps, missing input validation at trust boundaries
- secrets in code or logs, unsafe deserialization, weak crypto
- dependency risks introduced by this change
Check NFR-SEC items in docs/requirements.md.
Report only real issues: severity (blocker/major/minor), file:line, evidence, concrete fix.
No style comments. If nothing is wrong, say so.
```

`agents/architecture-guardian.md`:

```markdown
---
name: architecture-guardian
description: Checks a diff or plan against docs/architecture.md and docs/adr/. Use on plans and PRs.
model: opus
tools: Read, Grep, Glob, Bash
---
You are a staff engineer guarding the architecture. You did not write this work.
Read docs/architecture.md and every ADR in docs/adr/, then the diff or plan.
Flag only:
- new services, datastores or dependencies without an ADR
- calls that cross a boundary the architecture forbids
- data owned by one component written by another
- decisions that contradict an accepted ADR
For each: severity, location, the ADR or section violated, fix or "needs new ADR".
```

`agents/test-auditor.md`:

```markdown
---
name: test-auditor
description: Audits tests for real coverage of requirements. Use after each feature.
model: sonnet
tools: Read, Grep, Glob, Bash
---
You audit tests you did not write.
For each requirement ID in docs/requirements.md, find the test that verifies it.
Flag:
- requirements with no test
- tests that mock the unit under test, assert nothing, or always pass
- tests edited in the same commit as the code to make them pass
Run the test suite and report failures.
Output a table: requirement ID, test, verdict (covered/weak/missing), fix.
```

- [ ] **Step 3: Write the hooks example**

`hooks-settings.example.json` (Claude Code hook schema: `PostToolUse` formatter/linter, `PreToolUse` block on protected paths, `Stop` runs unit tests; `<lint command>` and `<test command>` are replaced in phase 5 with the commands from `CLAUDE.md`):

```json
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "Edit|Write",
        "hooks": [{ "type": "command", "command": "<format and lint command>" }]
      }
    ],
    "PreToolUse": [
      {
        "matcher": "Edit|Write",
        "hooks": [{
          "type": "command",
          "command": "python3 -c \"import json,sys,fnmatch; p=json.load(sys.stdin).get('tool_input',{}).get('file_path',''); sys.exit(2 if any(fnmatch.fnmatch(p,g) for g in ('*.env*','*infra/prod/*','*migrations/*')) else 0)\""
        }]
      }
    ],
    "Stop": [
      {
        "hooks": [{ "type": "command", "command": "<unit test command> || exit 2" }]
      }
    ]
  }
}
```

- [ ] **Step 4: Verify the hook schema against the Claude Code hooks docs**

Fetch `https://code.claude.com/docs/en/hooks` and confirm: event names `PostToolUse`, `PreToolUse`, `Stop`; `matcher` syntax; that exit code 2 blocks and the reason goes to stderr; the stdin field holding the edited path. Correct the JSON where it differs. Validate syntax: `python3 -m json.tool skills/roj-idea-to-project/assets/hooks-settings.example.json`.

- [ ] **Step 5: Check the templates pass and fail the gates as intended**

Run in a scratch dir: copy `requirements-template.md` to `docs/requirements.md`, run `python3 skills/roj-idea-to-project/scripts/check_ready.py --phase requirements <dir>`.
Expected: exit 1 with `FR-1 Verification is still the template placeholder: name the test or command` (the template's `<...>` placeholders are not mistaken for answers).

- [ ] **Step 6: Commit**

```bash
git add skills/roj-idea-to-project/assets
git commit -m "feat(skills): add roj-idea-to-project templates and reviewer agents"
```

### Task 5: References

**Files:**
- Create under `skills/roj-idea-to-project/references/`: `setup-superpowers.md`, `phase-brief.md`, `phase-requirements.md`, `phase-architecture.md`, `phase-agent-config.md`, `review-gates.md`, `handoff.md`

**Interfaces:**
- Consumes: script interfaces (Tasks 2, 3), asset names (Task 4).
- Produces: files that `SKILL.md` (Task 6) names with a trigger each. No reference names another reference unless SKILL.md names it too (all seven are named there). Each stays under 100 lines; if one grows past 100, open it with `## Contents` in its first 20 lines.

Each file starts with one line saying when it is read, then rules only (no explanation of TDD, ADRs or EARS). Required content per file:

- [ ] **Step 1: `setup-superpowers.md`** (read before phase 0)
  - The status table: `ok` → continue; `missing` → explain and ask; `disabled` → offer `next`; `outdated` → offer update, on a no continue and note the version in the brief; `undetectable` → look for `superpowers:brainstorming` in the session's skill list.
  - What to say before asking (what gets installed: the Superpowers plugin; from where: the marketplace in `next`; why: phases 2, 6 and 7 call `superpowers:brainstorming`, `superpowers:writing-plans`, `superpowers:subagent-driven-development`; what changes: a user-scope plugin install).
  - Install commands exactly as in the spec "Phase 0" list, including the fallback order and the Copilot CLI pair. Commands run through the agent's shell; `-y` is ignored there, so a marketplace that prompts (`Run this command now? [y/N]`) means: show the command and ask the user to run it in their own terminal.
  - Reload stop wording: "Run `/reload-plugins` in this session (Copilot CLI: exit and restart `copilot`), then tell me when it's done." Then STOP. The agent cannot run `/reload-plugins`.
  - Failure: show the command's output verbatim, give the command for the user's terminal, STOP.
  - Unsupported client sentence: "This skill needs Claude Code or GitHub Copilot CLI; Superpowers has no install for Copilot in VS Code or JetBrains yet."

- [ ] **Step 2: `phase-brief.md`** (read before the first brief question)
  - Question order: problem → target user and job → success metric (must be measurable: a number and a time frame) → MVP scope (3 to 5) → non-goals (5+) → constraints → open questions. Pitch is drafted by the agent from the answers, not asked.
  - Facts the agent fills itself: date, folder state (empty, has `.git`), Superpowers version note when outdated.
  - Recommended answers for non-goals: propose 5 concrete non-goals derived from the idea (for example "no native mobile app in the MVP"), worded so "yes" accepts.
  - Empty folder with no `.git`: offer `git init` once, after the brief path is stated; run it only on a yes.
  - Optional, offered once in one line after the draft: a fresh chat that argues against the idea (`review-gates.md` prompt, role "argue against this idea").

- [ ] **Step 3: `phase-requirements.md`** (read before drafting requirements)
  - Every requirement line: `- FR-<n>.<m> <WHEN|IF|WHILE|WHERE> ... THE SYSTEM SHALL ...`; `IF` lines use `THEN`.
  - One `### FR-<n> <name>` block per MVP-scope bullet; each block has a user story and one `Verification:` line naming a test or command.
  - NFRs carry numbers (latency with a percentile and load, cost per month, RTO/RPO); `NFR-SEC` always present with authn, authz, input validation boundary, secrets source.
  - Non-goals from the brief go to `## Out of scope`, word for word.
  - Gate: `scripts/check_ready.py --phase requirements`, loop until it passes, then the fresh review (`review-gates.md`), then the approval.

- [ ] **Step 4: `phase-architecture.md`** (read before drafting the architecture)
  - Draft in plan mode (Copilot CLI: `/plan`), model `opus` when the user can switch.
  - Sections from the template; C4 L1 and L2 as Mermaid `C4Context` / `C4Container` or `flowchart` blocks.
  - One ADR per decision, `docs/adr/NNNN-<decision>.md`, numbered from 0001; required areas: language, persistence, auth, deploy target, observability (file name or title must name the area: the script matches `language|stack|runtime|framework`, `persistence|database|storage|datastore`, `auth|authentication|authorization|identity`, `deploy|deployment|hosting|infrastructure`, `observability|logging|monitoring|telemetry`).
  - Each ADR lists at least two alternatives; the user picks; the agent states facts (pricing, limits) it looked up, with the source.
  - Threat model: assets, trust boundaries, top 3 to 5 threats, each mapped to an NFR-SEC item.
  - Gate: `check_ready.py --phase architecture`, fresh review, approval. `architecture-guardian` does not exist yet; it runs at the plan gate.

- [ ] **Step 5: `phase-agent-config.md`** (read before writing the agent config)
  - List all paths first: `CLAUDE.md`, `.claude/settings.json`, `.claude/agents/security-reviewer.md`, `.claude/agents/architecture-guardian.md`, `.claude/agents/test-auditor.md`; one yes writes the set. An existing `.claude/settings.json` is merged (show the diff), never replaced.
  - `CLAUDE.md` from the template, under 100 lines: exact build, test, single-test, lint and run commands for the stack in the ADRs; deviations from defaults; links to ADRs. No file-by-file descriptions.
  - Hooks from `assets/hooks-settings.example.json`, with the placeholders replaced by the `CLAUDE.md` commands; show each hook command before writing. Copilot CLI: hooks live in `.github/hooks/*.json` with a different schema; name the path, do not write it.
  - Agents copied from `assets/agents/`; Copilot CLI: custom agents in `.github/agents/`.
  - Suggest (never install) free checks matching the stack: formatter/linter, type checker, Semgrep CE or CodeQL, dependency scan (Dependabot, `npm audit`, `pip-audit`, `govulncheck`), gitleaks.
  - Gate: the user runs every `CLAUDE.md` command in a fresh shell and confirms each one; `check_ready.py --phase agent-config`; approval.

- [ ] **Step 6: `review-gates.md`** (read before each fresh-context review)
  - The red-team prompt verbatim:

    ```
    You are a skeptical staff engineer who did not write the attached <requirements | architecture | plan>.
    Report only: (1) ambiguous or untestable requirements, (2) contradictions, (3) missing NFRs or abuse cases,
    (4) architecture risks (failure modes, scaling, cost, security boundaries), (5) simpler alternatives.
    For each: severity (blocker/major/minor), quote as evidence, concrete fix. No style comments.
    ```
  - Claude Code: dispatch a subagent, model `opus` when available; its prompt is the red-team prompt with the bracket filled in plus the file paths (requirements: `docs/requirements.md`, `docs/brief.md`; architecture: `docs/architecture.md`, `docs/adr/`, `docs/requirements.md`; plan: the plan file plus those). Nothing from the conversation. At the plan gate also dispatch `architecture-guardian`.
  - Copilot CLI: a custom agent in `.github/agents/` with the same prompt runs as a subagent.
  - No subagents: print the prompt and the paths, tell the user to open a new chat (`/clear` or `/new`) with only those files and paste the findings back. STOP until they do.
  - Present findings one per message, each with a recommended accept or reject; drop style findings without asking.
  - Record each in the reviewed file's `## Review log`: `- [blocker|major|minor] "<quote>" → accepted|rejected: <reason>`. An accepted finding that changes a decision is also an ADR edit.

- [ ] **Step 7: `handoff.md`** (read before writing the plan and before the hand-off)
  - Before the plan: `scripts/check_ready.py --phase all` loop until `READY`.
  - Invoke `superpowers:writing-plans` with the spec, requirements, architecture and ADRs. Plan rules to pass on: task 1 is a walking skeleton (repo, CI, one request end to end, dev deploy); every task uses the format below and names requirement IDs; override: no commit, stop after writing.

    ```
    ### Task 7: <imperative title>  [FR-2.1, NFR-SEC]
    Files: create <path>, modify <path>, test <path>
    Interface: <signature>
    Test first: <test name> expects <result>
    Verify: <command> (fails before, passes after)
    Done when: tests green, lint clean, committed
    Out of scope: <what waits for a later task>
    ```
  - Plan gate: fresh review + `architecture-guardian`, findings into the plan's `## Review log`, approval.
  - Hand-off: write `docs/progress.md` from the template, one line per FR with its `Verification:` command. Then tell the user, and stop: new session in a worktree (`superpowers:using-git-worktrees`); `superpowers:subagent-driven-development` on the plan; watch the first 2 to 3 tasks; keep `docs/progress.md` current; review with `/code-review`, then the three subagents, then their own read of the diff; merge with `superpowers:finishing-a-development-branch`; a 10-minute retro after the first merge turning each repeated mistake into a hook, test, ADR or `CLAUDE.md` line. Deploy: infra is a feature with its own spec; agent credentials stop at dev/staging. Native plan mode instead of this flow only when a change fits in one sentence.

- [ ] **Step 8: Check sizes and cross-references**

Run: `python3 -m unittest test_skills`
Expected: OK (`test_long_references_have_contents`, `test_references_one_level_deep`).

- [ ] **Step 9: Commit**

```bash
git add skills/roj-idea-to-project/references
git commit -m "feat(skills): add roj-idea-to-project phase references"
```

### Task 6: SKILL.md and USAGE.md

**Files:**
- Modify: `skills/roj-idea-to-project/SKILL.md` (replace the body; keep the Task 1 frontmatter)
- Modify: `skills/roj-idea-to-project/USAGE.md`

**Interfaces:**
- Consumes: every reference (Task 5), asset (Task 4) and script (Tasks 2, 3) by its exact path.

- [ ] **Step 1: Replace the SKILL.md body with this text**

````markdown
# Idea to Project

Walk the user from a raw app idea to a repo an agent can build: brief,
design, EARS requirements, architecture and ADRs, agent config and a
checked Definition of Ready. Each phase writes one artifact set and ends at
a gate the user approves. Superpowers designs, plans and builds; this skill
keeps the gates.

## Inputs

- The idea, in chat, in any form.
- The project folder: the current directory. Empty is fine.
- Phase files already in it (`docs/brief.md`, `docs/requirements.md`, ...):
  resume from them (see Progress).

## Hard rules

1. **Superpowers first.** Phase 0 passes before any other phase: every
   later phase calls a Superpowers skill.
2. **One phase at a time.** Each phase writes one artifact set and ends with
   an explicit approval of that set. "Approve everything" or "keep going"
   is not a gate approval: confirm each gate as you reach it. Every phase
   consumes the one before, so an unchecked file spoils all that follow.
3. **One question per message**, with your recommended answer, worded so
   "yes" accepts it.
4. **Facts are yours, decisions are the user's.** Look up versions,
   commands, prices, limits and what exists in the folder; ask only for
   choices.
5. **Fresh-context review** at the requirements, architecture and plan
   gates, never in the context that wrote the file. Read
   `references/review-gates.md` before each one.
6. **Reviewers report only correctness, security and requirement gaps.**
   The user accepts or rejects each finding; record it in the file's
   `## Review log` (or an ADR).
7. **Say the path before writing.** Name the exact path of every file
   before writing it. Never overwrite, rename or delete an existing file
   without a yes.
8. **Git: hands off.** Never commit, branch or push, including when a
   Superpowers skill says to. Offer `git init` only in an empty folder with
   no `.git`, and run it only on a yes.
9. **Install nothing but Superpowers, and only after a yes.** Linters and
   scanners are suggested in phase 5, never installed.

## Progress

At the start of every run, derive this checklist from the files and show
it:

```
- [ ] 0 Setup: Superpowers installed, enabled, reloaded
- [ ] 1 Brief: docs/brief.md
- [ ] 2 Design: docs/superpowers/specs/<date>-<topic>-design.md
- [ ] 3 Requirements: docs/requirements.md (reviewed)
- [ ] 4 Architecture: docs/architecture.md + docs/adr/ (reviewed)
- [ ] 5 Agent config: CLAUDE.md, .claude/settings.json, .claude/agents/
- [ ] 6 Ready + plan: check_ready.py passes; plan (reviewed)
- [ ] 7 Hand-off: docs/progress.md
```

A phase is done when its files exist, carry `Status: Approved YYYY-MM-DD`
and pass their check. An approved file that fails its check is not done:
resume there and say why. Write the `Status: Approved` line only after
the user approves that gate.

Scripts live in this skill's folder; run them with `python3` (or `python`
where that is Python 3) and pass the project folder as ROOT:

- `scripts/check_superpowers.py`: JSON report on Superpowers; exit 0 when
  usable. Never installs.
- `scripts/check_ready.py --phase <brief|requirements|architecture|agent-config|all> ROOT`:
  prints every gap with its fix; exit 0 when the phase passes.

**Gate loop** for every phase with a check: run it, fix the file with the
user, re-run until it exits 0, then ask for the approval. Passing the
check is not an approval.

## Phase 0: Setup

Read `references/setup-superpowers.md` before running the check. In Copilot
inside VS Code or JetBrains, say this skill needs Claude Code or GitHub
Copilot CLI and stop.

Run `scripts/check_superpowers.py` and act on `status`: `ok` continues;
`missing` or `disabled` gets an explanation and a yes before running
`next`; `outdated` gets the update offered, and a no continues with the
version noted in the brief; `undetectable` means checking your own skill
list for `superpowers:brainstorming`.

After any install, enable or update: tell the user to run `/reload-plugins`
(Copilot CLI: restart `copilot`) and STOP. You cannot run it. Re-run the
check when they confirm; continue only on exit 0. A failed install: show
the error verbatim and the command for their own terminal, then STOP.

## Phase 1: Brief → `docs/brief.md`

Read `references/phase-brief.md` before the first question. Fill
`assets/brief-template.md` one question at a time. Gate:
`check_ready.py --phase brief`. The non-goals set the scope every later
phase checks; without them agents over-build.

## Phase 2: Design → `docs/superpowers/specs/<date>-<topic>-design.md`

Invoke `superpowers:brainstorming` with `@docs/brief.md`. Its flow shapes
the design; override two of its steps: do not commit the spec, and after
the user approves it, come back here for phase 3 instead of invoking
`writing-plans`. Hidden decisions surface here, before they become
requirements.

## Phase 3: Requirements → `docs/requirements.md`

Read `references/phase-requirements.md` before drafting. Draft from the
brief and the design spec with `assets/requirements-template.md`. Gate:
`check_ready.py --phase requirements`, then the fresh review, then the
approval. Testable requirements let someone who did not write them say
when the work is done.

## Phase 4: Architecture → `docs/architecture.md` + `docs/adr/`

Read `references/phase-architecture.md` before drafting. Use
`assets/architecture-template.md` and one `assets/adr-template.md` per
decision. Gate: `check_ready.py --phase architecture`, then the fresh
review, then the approval. The user keeps control here: no service,
datastore or dependency without an ADR.

## Phase 5: Agent config → `CLAUDE.md`, `.claude/settings.json`, `.claude/agents/`

Read `references/phase-agent-config.md` before writing. List all five
paths, write them on one yes from `assets/claude-md-template.md`,
`assets/hooks-settings.example.json` and `assets/agents/`. Gate: the user
runs every `CLAUDE.md` command in a fresh shell and confirms each one, then
`check_ready.py --phase agent-config`, then the approval. Guardrails exist
before the first line of agent code.

## Phase 6: Ready + plan → `docs/superpowers/plans/<date>-<feature>.md`

Read `references/handoff.md` before the plan. Run
`check_ready.py --phase all` as a loop until `READY`, then invoke
`superpowers:writing-plans` with the plan rules from that file; override:
no commit, stop after writing. Gate: fresh review plus
`architecture-guardian`, then the approval. Small verified tasks let the
agent run for hours without drifting.

## Phase 7: Hand-off → `docs/progress.md`

Write `docs/progress.md` from `assets/progress-template.md`, one line per
FR with its verify command. Give the build, review and retro steps from
`references/handoff.md`, then stop. This skill builds nothing.

## Claude Code and Copilot CLI

| Feature | Claude Code | Copilot CLI |
|---|---|---|
| Fresh reviewer | subagent, model `opus` | custom agent in `.github/agents/`; else `/new` with only the file |
| Hooks | `.claude/settings.json` | `.github/hooks/*.json` (other schema: name it, do not write it) |
| Plan mode | Shift+Tab | `/plan` or Shift+Tab |
| Clear context | `/clear` | `/clear` (`/new`, `/reset`) |
| Reload plugins | `/reload-plugins` (the user types it) | restart `copilot` |

Use model aliases (`opus`, `sonnet`), never versioned model IDs.

## Gotchas

- Superpowers `brainstorming` and `writing-plans` commit their file and
  chain to the next skill. Inside this skill: write, do not commit, stop
  at the gate.
- `/reload-plugins` runs only when the user types it; asking and stopping
  is the only path after an install.
- `check_superpowers.py` may report a commit SHA as `version`
  (`version_comparable: false`): that is not outdated.
- `check_ready.py` without `--phase` checks the whole Definition of Ready
  and reports later-phase files as missing. Pass the phase at each gate.
- `architecture-guardian` does not exist until phase 5. At phase 4 the
  reviewer is the red-team subagent alone.
- A brief marked approved can still fail its check (someone edited it):
  the check wins, not the `Status:` line.

## Hand-off

When phase 7 is done, end with the checklist fully ticked and one line:
"Ready to build: start a new session in a worktree and run
`superpowers:subagent-driven-development` on
`docs/superpowers/plans/<file>`."
````

- [ ] **Step 2: Rewrite USAGE.md**

Same shape as `skills/roj-grill-plan/USAGE.md`: one intro paragraph (what it does, Superpowers dependency installed on first run after a yes, never touches git); `## When to use` (3 bullets: new app idea; empty repo to set up for an agent; resuming a half-done setup); `## Commands per platform` (Claude Code and Copilot CLI: `/roj-idea-to-project <idea>`; plain English works; VS Code and JetBrains Copilot: not supported yet, needs Superpowers there) with a request table (start from an idea; resume in a folder with `docs/brief.md`; check readiness: `python3 <skill>/scripts/check_ready.py`); `## Answering a gate` (`yes` approves this gate only; "approve everything" is asked again at each gate; findings: `accept`, `reject because ...`); `## Output` (the file list per phase, `Status: Approved` lines, `## Review log`). No personal paths.

- [ ] **Step 3: Check limits**

Run: `python3 -m unittest test_skills test_idea_to_project`
Expected: OK (body under 500 lines, every `references/`, `assets/` and `scripts/` path named in SKILL.md exists).

Run: `wc -l skills/roj-idea-to-project/SKILL.md` → about 170 to 200 lines.
Run: `python3 -c "import sys; t=open('skills/roj-idea-to-project/SKILL.md',encoding='utf-8').read(); print(len(t.split()))"` → under about 3,500 words (a proxy for 5,000 tokens).

- [ ] **Step 4: Commit**

```bash
git add skills/roj-idea-to-project/SKILL.md skills/roj-idea-to-project/USAGE.md
git commit -m "feat(skills): write the roj-idea-to-project workflow"
```

### Task 7: Community-skills doc

**Files:**
- Modify: `docs/community-skills.md`

- [ ] **Step 1: Add a Superpowers section** at the end, in the file's section style:

```markdown
## superpowers
Brainstorming, planning, TDD, subagent-driven development and review skills
from [obra/superpowers](https://github.com/obra/superpowers) (MIT), installed
as a plugin rather than through `apm.yml`.

`roj-idea-to-project` requires it and installs it on first run, after a yes:

- Claude Code: `claude plugin install superpowers@claude-plugins-official`;
  if that marketplace is not available, `claude plugin marketplace add
  obra/superpowers-marketplace`, then `claude plugin install
  superpowers@superpowers-marketplace`. Then `/reload-plugins`.
- Copilot CLI: `copilot plugin marketplace add obra/superpowers-marketplace`,
  then `copilot plugin install superpowers@superpowers-marketplace`, then
  restart `copilot`.

Copilot in VS Code and JetBrains is not supported yet: the skill folders
install through `apm.yml` at a pinned commit, but Superpowers ships no
Copilot tool map and its session-start bootstrap does not run from a
skills-only install. Curated marketplaces can lag behind the latest release
(v7.0.0 rebuilt brainstorming); the skill offers `claude plugin update`.
```

- [ ] **Step 2: Run the suites**

Run: `python3 -m unittest test_install test_skills test_idea_to_project`
Expected: OK

- [ ] **Step 3: Commit**

```bash
git add docs/community-skills.md
git commit -m "docs: list superpowers as a dependency of roj-idea-to-project"
```

### Task 8: Eval fixtures

**Files:**
- Modify: `evals/fixtures/build.sh`
- Create: `evals/fixtures/fake-claude.sh`
- Modify: `test_skills.py` (`TestEvals`)

**Interfaces:**
- Produces: fixture kinds `idea-empty`, `idea-brief-2ng`, `idea-req-gap`; `fake-claude.sh <dir> <missing|present|outdated>` writing `<dir>/bin/claude` and `<dir>/claude-state/calls.log`; evals name the mode under `fixture.claude`.

- [ ] **Step 1: Write the failing test changes**

In `test_skills.py` `TestEvals`:

```python
    GH_MODES = {"normal", "reviewed", "noauth"}
    CLAUDE_MODES = {"missing", "present", "outdated"}
    # Fixtures that are a bare folder, for skills that start a project.
    NO_GIT = {"idea-empty"}

    # Skills whose descriptions overlap; each must keep an eval set.
    REQUIRED = {"roj-code-review-pr", "roj-code-review-pr-fast",
                "roj-review-pr-comment", "roj-explain-logic",
                "roj-explain-feature-changes", "roj-idea-to-project"}
```

In `test_evals_name_buildable_fixtures`, after the `gh` check:

```python
                    if "claude" in e["fixture"]:
                        self.assertIn(e["fixture"]["claude"],
                                      self.CLAUDE_MODES)
```

In `test_every_fixture_builds`, replace the `.git` assertion with:

```python
                    if kind in self.NO_GIT:
                        self.assertTrue((dest / "repo").is_dir())
                        self.assertFalse((dest / "repo" / ".git").exists())
                    else:
                        self.assertTrue((dest / "repo" / ".git").is_dir())
```

and after the `fake-gh.sh` block add:

```python
            sp = Path(tmp) / "idea-empty"
            run = subprocess.run(
                [BASH, str(self.FIXTURES / "fake-claude.sh"), str(sp),
                 "missing"], capture_output=True, text=True)
            self.assertEqual(run.returncode, 0, run.stderr)
            self.assertTrue((sp / "bin" / "claude").is_file())
```

The new kinds are only built once an eval names them (Task 9), so this step adds a direct build check too, at the end of `test_every_fixture_builds` inside the `with` block:

```python
            for kind in sorted(self.NO_GIT | {"idea-brief-2ng",
                                              "idea-req-gap"} - used):
                with self.subTest(fixture=kind):
                    dest = Path(tmp) / f"direct-{kind}"
                    run = subprocess.run(
                        [BASH, str(self.FIXTURES / "build.sh"), kind,
                         str(dest)], capture_output=True, text=True)
                    self.assertEqual(run.returncode, 0, run.stderr)
```

Run: `python3 -m unittest test_skills.TestEvals -v`
Expected: FAIL (`unknown fixture idea-empty`, `fake-claude.sh` missing).

- [ ] **Step 2: Add the fixture kinds to `build.sh`**

Before the `*)` case add:

```bash
idea-empty)    mkdir -p repo ;;
idea-brief-2ng) init_repo main
  mkdir -p docs
  cat > docs/brief.md <<'EOF'
# Plant Pal Brief
Status: Approved 2026-10-14
## Problem (2 to 3 sentences)
I forget to water my plants and they die.
## Target user and main job-to-be-done
Busy flat-dwellers with 5 to 20 house plants: know what to water today.
## Pitch (3 sentences max)
A web app that tells you which plants need water today.
## Success metrics (measurable)
- 80% of reminders acted on within 24 hours over the first month
## MVP scope (3 to 5 bullets)
- Add a plant with a watering interval
- Daily reminder email
- Mark a plant as watered
## Non-goals (at least 5)
- No native mobile app
- No plant identification from photos
## Constraints (budget, cloud, compliance, timeline)
- Under 10 USD per month, one developer, 4 weeks
## Open questions
EOF
  G add -A; G commit -qm "Add brief"; push_all ;;
idea-req-gap)  init_repo main
  mkdir -p docs/superpowers/specs
  cat > docs/brief.md <<'EOF'
# Plant Pal Brief
Status: Approved 2026-10-14
## Problem (2 to 3 sentences)
I forget to water my plants and they die.
## Target user and main job-to-be-done
Busy flat-dwellers with 5 to 20 house plants: know what to water today.
## Pitch (3 sentences max)
A web app that tells you which plants need water today.
## Success metrics (measurable)
- 80% of reminders acted on within 24 hours over the first month
## MVP scope (3 to 5 bullets)
- Add a plant with a watering interval
- Daily reminder email
- Mark a plant as watered
## Non-goals (at least 5)
- No native mobile app
- No plant identification from photos
- No social or sharing features
- No sensor or smart-pot integration
- No payments
## Constraints (budget, cloud, compliance, timeline)
- Under 10 USD per month, one developer, 4 weeks
## Open questions
EOF
  cat > docs/superpowers/specs/2026-10-14-plant-pal-design.md <<'EOF'
# Plant Pal design
Status: Approved 2026-10-14
A small web app with a plants table and a daily reminder job.
EOF
  cat > docs/requirements.md <<'EOF'
# Requirements: Plant Pal (v0.1, 2026-10-14)
Status: Draft
## Functional requirements
### FR-1 Plants
User story: As an owner, I want to add plants so that I get reminders.
- FR-1.1 WHEN the owner adds a plant with an interval THE SYSTEM SHALL store it.
Verification: tests/test_plants.py::test_add_plant
### FR-2 Reminders
User story: As an owner, I want a daily email so that I water on time.
- FR-2.1 WHEN a plant is due THE SYSTEM SHALL email the owner by 08:00 local time.
- FR-2.2 IF the email fails THEN THE SYSTEM SHALL retry once after 10 minutes.
## Non-functional requirements
- NFR-PERF: p95 < 300 ms at 5 rps
- NFR-SEC: authn magic link; authz owner only; input validated at the API; secrets from env
- NFR-OPS: structured logs; RPO 24 h
- NFR-COST: < 10 USD per month
## Out of scope
## Traceability: requirement -> task -> test
## Review log
EOF
  G add -A; G commit -qm "Add brief, design and draft requirements"; push_all ;;
```

The final `echo` reads the branch with git, which fails for `idea-empty`. Replace the last line with:

```bash
if [ -d "$dest/repo/.git" ]; then
  echo "built $kind at $dest/repo on $(git -C "$dest/repo" branch --show-current)"
else
  echo "built $kind at $dest/repo (no git)"
fi
```

- [ ] **Step 3: Write `fake-claude.sh`**

```bash
#!/usr/bin/env bash
# Install a stand-in Claude Code CLI for the roj-idea-to-project evals.
#
#   evals/fixtures/fake-claude.sh <fixture-dir> <missing|present|outdated>
#
# Writes <fixture-dir>/bin/claude. Put <fixture-dir>/bin first on PATH for
# the run. Nothing is installed: every call is appended to
# claude-state/calls.log, and plugin install/update/enable switch the state
# to "present" so a re-check after the user's reload passes.
#   missing   no superpowers install
#   present   superpowers@claude-plugins-official 7.0.0, enabled
#   outdated  superpowers@claude-plugins-official 6.4.1, enabled
set -euo pipefail
F=$1; MODE=$2
case "$MODE" in missing|present|outdated) ;; *)
  echo "fake-claude.sh: unknown mode $MODE" >&2; exit 2 ;; esac
mkdir -p "$F/bin" "$F/claude-state"
echo "$MODE" > "$F/claude-state/mode"
: > "$F/claude-state/calls.log"
cat > "$F/bin/claude" <<EOF
#!/usr/bin/env bash
ST="$F/claude-state"
echo "claude \$*" >> "\$ST/calls.log"
sp() { printf '[{"id":"superpowers@claude-plugins-official","version":"%s","scope":"user","enabled":true,"installPath":"/tmp/fake-plugins/superpowers"}]\n' "\$1"; }
case "\$1 \${2:-}" in
  "plugin list")
    case "\$(cat "\$ST/mode")" in
      missing) echo '[]' ;;
      present) sp 7.0.0 ;;
      outdated) sp 6.4.1 ;;
    esac ;;
  "plugin install"|"plugin update"|"plugin enable")
    echo present > "\$ST/mode"
    echo "Successfully installed plugin: \${3:-} (scope: user)" ;;
  "plugin marketplace") echo "Successfully added marketplace" ;;
  "--version ") echo "2.1.300 (Claude Code)" ;;
  *) echo "claude stub: unsupported: \$*" >&2; exit 1 ;;
esac
EOF
chmod +x "$F/bin/claude"
```

- [ ] **Step 4: Run the tests**

Run: `python3 -m unittest test_skills -v`
Expected: OK

Run a manual check: `evals/fixtures/build.sh idea-empty "$S/f1" && evals/fixtures/fake-claude.sh "$S/f1" missing && PATH="$S/f1/bin:$PATH" python3 skills/roj-idea-to-project/scripts/check_superpowers.py` with `S` a scratch dir.
Expected: `"status": "missing"`, exit 1; `$S/f1/claude-state/calls.log` holds `claude plugin list --json`.

- [ ] **Step 5: Commit**

```bash
git add evals/fixtures/build.sh evals/fixtures/fake-claude.sh test_skills.py
git commit -m "test: add roj-idea-to-project eval fixtures and fake claude cli"
```

### Task 9: Eval sets

**Files:**
- Create: `evals/roj-idea-to-project/evals.json`, `evals/roj-idea-to-project/triggers.json`

- [ ] **Step 1: Write `evals.json`**

```json
{
  "skill_name": "roj-idea-to-project",
  "evals": [
    {
      "id": 1,
      "prompt": "I have an idea for an app that reminds me to water my plants. Help me plan it properly before Claude builds it.",
      "fixture": {"repo": "idea-empty", "claude": "missing"},
      "expected_output": "Says Superpowers is missing, what it is for and what will be installed, asks for a yes, and stops without installing or starting the brief.",
      "expectations": [
        "Runs scripts/check_superpowers.py (or claude plugin list --json) before asking any question about the idea",
        "Names the Superpowers plugin and the install command it would run",
        "Asks the user for a yes before installing",
        "claude-state/calls.log contains no 'plugin install', 'plugin update' or 'plugin marketplace' line",
        "Asks no question about the idea itself (problem, users, non-goals) in this run",
        "No docs/ directory and no .git exist in repo/ after the run"
      ]
    },
    {
      "id": 2,
      "prompt": "I want to set up a new folder so an agent can build my habit-tracker web app. Superpowers isn't installed yet. Yes, install it.",
      "fixture": {"repo": "idea-empty", "claude": "missing"},
      "expected_output": "Installs Superpowers with exactly one install command, tells the user to run /reload-plugins, and stops before phase 1.",
      "expectations": [
        "claude-state/calls.log contains exactly one 'plugin install superpowers@' line",
        "The final message tells the user to run /reload-plugins",
        "Stops after the reload instruction: asks no question about the idea (problem, users, non-goals)",
        "No docs/brief.md exists in repo/ after the run",
        "Runs no git command that writes (no init, commit, branch or push)"
      ]
    },
    {
      "id": 3,
      "prompt": "hey i've got an app idea, a shared grocery list for my flat. can you help me turn it into a proper project?",
      "fixture": {"repo": "idea-empty", "claude": "present"},
      "expected_output": "Superpowers passes; the brief starts with exactly one question carrying a recommended answer; git init is offered, not run; nothing is written yet.",
      "expectations": [
        "Runs scripts/check_superpowers.py and reports Superpowers as installed",
        "Asks exactly one question about the idea, followed by a recommended answer",
        "States docs/brief.md as the file the phase will write",
        "Offers git init without running it: no repo/.git exists after the run",
        "Writes no file in repo/"
      ]
    },
    {
      "id": 4,
      "prompt": "continue with my project, the brief in docs/brief.md is done",
      "fixture": {"repo": "idea-brief-2ng", "claude": "present"},
      "expected_output": "Finds only 2 non-goals, refuses to leave phase 1 and asks for more non-goals.",
      "expectations": [
        "Reports that docs/brief.md has 2 non-goals and at least 5 are needed",
        "Asks for more non-goals (one question, with recommended non-goals)",
        "No docs/requirements.md and no docs/superpowers/ exist after the run",
        "git status in repo/ shows docs/brief.md unchanged unless the user approved an edit in the prompt (it did not)",
        "git log shows no new commit"
      ]
    },
    {
      "id": 5,
      "prompt": "Here's my project so far. I approve everything, keep going until it's ready to build.",
      "fixture": {"repo": "idea-req-gap", "claude": "present"},
      "expected_output": "Resumes at phase 3, runs check_ready.py for requirements, reports the FR-2 Verification gap, and still stops at the requirements gate.",
      "expectations": [
        "Runs scripts/check_ready.py with --phase requirements",
        "Reports that FR-2 has no Verification line",
        "Asks the user for the requirements gate approval or the missing Verification instead of treating 'approve everything' as approval",
        "No docs/architecture.md, docs/adr/ or CLAUDE.md exist after the run",
        "git log shows no new commit and no new branch exists"
      ]
    }
  ]
}
```

- [ ] **Step 2: Write `triggers.json`** (10 should-trigger, 10 near-miss; `split` fixed: 6+6 train, 4+4 validation)

```json
[
  {"query": "I have an app idea and want to plan it properly before Claude builds it", "should_trigger": true, "split": "train"},
  {"query": "help me plan a new project before claude builds it, its a booking app for my yoga studio", "should_trigger": true, "split": "train"},
  {"query": "set this repo up so an agent can build it, ~/code/plant-tracker is empty right now", "should_trigger": true, "split": "train"},
  {"query": "i got an idea for a side project (budget tracker w/ bank csv import), where do i even start so claude can code it", "should_trigger": true, "split": "train"},
  {"query": "Turn this idea into something buildable: a Slack bot that summarises our standups. I want requirements and architecture nailed down first", "should_trigger": true, "split": "train"},
  {"query": "new empty folder, want to go from idea to a repo with CLAUDE.md, ADRs and a plan so an agent can run with it", "should_trigger": true, "split": "train"},
  {"query": "can you take my startup idea from napkin to build-ready? recipe sharing app for families", "should_trigger": true, "split": "validation"},
  {"query": "before I let claude loose on this I want a brief with non-goals, EARS requirements and ADRs for my new CLI tool", "should_trigger": true, "split": "validation"},
  {"query": "I want to build a small SaaS for tracking invoices. what should exist before an agent starts coding?", "should_trigger": true, "split": "validation"},
  {"query": "kick off a greenfeild project with me: home inventory app, and check the definition of ready before we build", "should_trigger": true, "split": "validation"},
  {"query": "review my PR before I merge it, branch feat/login", "should_trigger": false, "split": "train"},
  {"query": "grill me on this plan: we migrate the uploader to httpx next sprint", "should_trigger": false, "split": "train"},
  {"query": "implement SB-PROJ-2001", "should_trigger": false, "split": "train"},
  {"query": "write a spec for the export-to-csv feature in our existing billing service", "should_trigger": false, "split": "train"},
  {"query": "explain what app/uploader.py does and who calls it", "should_trigger": false, "split": "train"},
  {"query": "brainstorm names for my app, it's a plant watering reminder", "should_trigger": false, "split": "train"},
  {"query": "install superpowers for me", "should_trigger": false, "split": "validation"},
  {"query": "add an ADR to docs/adr for switching this service from Postgres to SQLite", "should_trigger": false, "split": "validation"},
  {"query": "set up a CLAUDE.md for this existing Go service", "should_trigger": false, "split": "validation"},
  {"query": "poke holes in the requirements in docs/requirements.md", "should_trigger": false, "split": "validation"}
]
```

- [ ] **Step 3: Run the suites**

Run: `python3 -m unittest test_skills -v`
Expected: OK (fixtures named by the evals build; trigger set has 10 and 10; ids unique ints).

- [ ] **Step 4: Commit**

```bash
git add evals/roj-idea-to-project
git commit -m "test: add roj-idea-to-project behaviour and trigger evals"
```

### Task 10: Run the evals (STOP afterwards)

Workspace: the session scratchpad, `idea-to-project-workspace/iteration-<N>/` (layout from agentskills.io: `eval-<id>/{with_skill,without_skill}/{outputs,timing.json,grading.json}`, `benchmark.json`). Nothing from the workspace is committed.

- [ ] **Step 1: Build a fresh fixture per run**

For each eval id and each configuration: `evals/fixtures/build.sh <fixture.repo> <ws>/eval-<id>/<config>/fixture` then `evals/fixtures/fake-claude.sh <ws>/eval-<id>/<config>/fixture <fixture.claude>`.

- [ ] **Step 2: Dispatch each run in a fresh subagent**

Prompt for a with-skill run (the without-skill run omits the skill line):

```
Execute this task as a fresh agent.
- Skill: read and follow <repo>/skills/roj-idea-to-project/SKILL.md (scripts are in that folder).
- Working directory: <fixture>/repo. Start every shell command with: export PATH="<fixture>/bin:$PATH";
- Task (the user's message): <prompt>
- This is a single turn: when the workflow says to wait for the user, end your turn.
- Do not touch any path outside <fixture>.
At the end, write your final message to <ws>/eval-<id>/<config>/outputs/final.md.
```

Record `total_tokens` and `duration_ms` from each task notification into `timing.json` immediately.

- [ ] **Step 3: Grade with evidence**

For each run, check every expectation against `outputs/final.md`, `claude-state/calls.log`, `ls -la repo`, `git -C repo log --oneline` and `git -C repo status --short` (script checks for file and log assertions; LLM judgment only for message content). Write `grading.json` (`assertion_results` with `text`, `passed`, `evidence`; `summary`).

- [ ] **Step 4: Aggregate**

Write `benchmark.json` with `run_summary.with_skill`, `run_summary.without_skill` (pass_rate, time_seconds, tokens) and `delta`.

- [ ] **Step 5: Trigger evals**

From an empty scratch directory with its own `.claude/` (README "Evals"), run skill-creator's `scripts.run_eval` with `--num-workers 1` on the train queries and on the validation queries separately (derive `train.json` and `validation.json` from `triggers.json` by `split` into the workspace; first check whether `run_eval` accepts the extra `split` key on the full file). 3 runs per query, threshold 0.5. Report both pass rates.

- [ ] **Step 6: Iterate at most 3 times**

Only on failures: revise SKILL.md or the description using train failures only, generalising (no keywords copied from failed queries); re-run into `iteration-<N+1>/`; pick the best iteration by validation pass rate. Commit any skill change:

```bash
git add skills/roj-idea-to-project
git commit -m "fix(skills): <what the eval showed> in roj-idea-to-project"
```

- [ ] **Step 7: STOP**

Show the user: the benchmark table (per eval: with/without pass counts, tokens, seconds), the trigger train and validation pass rates, failed assertions with evidence, and what changed between iterations. Wait for approval.

### Task 11: Pre-push checks and PR (STOP before pushing)

- [ ] **Step 1: Run the checks**

```bash
python3 -m unittest test_install test_skills test_idea_to_project
python3 tools/sync_shared.py --check
uvx skills-ref validate skills/roj-idea-to-project
```

Expected: OK, exit 0, valid (or the recorded install error).

- [ ] **Step 2: Verify the Definition of Done items**

`wc -l skills/roj-idea-to-project/SKILL.md` under 500; every `references/*.md` named in SKILL.md with a trigger; references over 100 lines start with `## Contents`; `git log --format='%an <%ae> | %cn <%ce>' main..HEAD` shows only Roj Carranza; `git log main..HEAD` has no `Co-Authored-By` or `Claude` trailers.

- [ ] **Step 3: Draft the follow-up issue** for IDE Copilot (`feat(skills): support roj-idea-to-project in copilot for vs code and jetbrains`): story, the finding from the spec, acceptance criteria (Superpowers skills installed through `apm.yml` at a pinned commit with `targets: [copilot]`; brainstorming, writing-plans and subagent-driven-development each run once in VS Code Copilot and JetBrains Copilot with results recorded; the skill's unsupported-client stop removed only if all three work). Show it to the user before creating it.

- [ ] **Step 4: Draft the PR**

Title `feat(skills): add roj-idea-to-project skill`; body starts `Closes #29`, then summary, test results, eval benchmark, `skills-ref` result, the follow-up issue. No attribution footer. Show it and STOP before `git push`.

- [ ] **Step 5: On the user's yes only**

`git push -u origin feat/idea-to-project`, `gh pr create --title ... --body-file ...`, then add the PR number to issue #29 (`gh issue comment 29 --body "PR #<n>"`).
