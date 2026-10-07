# review-pr-comment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** When Claude Code opens a PR in a repo owned by an allowlisted GitHub owner, a `COMMENT` review with inline comments is posted to it automatically.

**Architecture:** A stdlib-Python `PostToolUse` hook (`claude/pr_review_hook.py`) watches Bash calls for `gh pr create`, checks the new PR's owner against `PR_REVIEW_OWNERS`, optionally requests Copilot, and injects `additionalContext` telling Claude to read and follow `~/.claude/skills/review-pr-comment/SKILL.md`. The skill reuses `code-review-pr`'s method files and posts one review through `gh api`.

**Tech Stack:** Python 3.8+ stdlib, `unittest`, `gh` CLI, Claude Code hooks/settings, SKILL.md.

**Spec:** `docs/superpowers/specs/2026-09-29-pr-review-comment-design.md`

## Global Constraints

- Hook: Python 3, stdlib only; always exits 0; never blocks the tool call.
- Config via `claude/settings.json` `env`: `PR_REVIEW_OWNERS` default `r0jjames`, `PR_REVIEW_COPILOT` default `0`.
- Hook command path uses `$HOME/.claude/`, never a machine-specific path.
- Review: exactly one review per run, `event: COMMENT`, max 15 inline comments, hidden marker `<!-- review-pr-comment:<headRefOid> -->` as the body's last line.
- No Claude attribution in reviews or commits (no `Co-Authored-By`, no `Claude-Session`, no "Generated with Claude").
- `code-review-pr` is not modified.
- New skill is `user-invocable-only` in `skillOverrides`.
- Tests run from repo root: `python3 -m unittest discover tests` and `python3 agent-skills/test_install.py`.

## Review Focus

- `gh pr create` fails (no URL in output) → hook prints nothing. Pinned in Task 1 (`test_failed_create_is_silent`).
- `tool_response` arrives as a plain string instead of a dict → URL still found. Pinned in Task 1 (`test_string_tool_response`).
- `PR_REVIEW_OWNERS` unset or empty (a repo opting out) → no trigger. Pinned in Task 1 (`test_empty_owners_disables`).
- `gh` missing from PATH during the Copilot request → no exception, review context still emitted. Pinned in Task 1 (`test_copilot_gh_missing`).
- A command that chains `gh pr create` with other commands whose output holds an unrelated PR URL (e.g. `gh pr list`) — accepted limitation: the first URL is used. Chained create-then-list is rare; documented in the hook's docstring, not tested.

---

### Task 1: The hook script

**Files:**
- Create: `claude/pr_review_hook.py`
- Test: `tests/test_pr_review_hook.py`

**Interfaces:**
- Produces: `claude/pr_review_hook.py` with
  `parse_payload(raw: str) -> tuple[str, str]`,
  `find_pr(command: str, output: str) -> Optional[tuple[str, str, int]]`,
  `owner_allowed(owner: str, owners_env: str) -> bool`,
  `request_copilot(owner: str, repo: str, number: int) -> bool`,
  `build_output(url: str, copilot: Optional[bool]) -> dict`,
  `main(stdin, out, env) -> int`. Constant `SKILL_PATH = "~/.claude/skills/review-pr-comment/SKILL.md"`.

- [ ] **Step 1: Write the failing tests**

`tests/test_pr_review_hook.py`:

```python
# tests/test_pr_review_hook.py
from __future__ import annotations

import importlib.util
import io
import json
import subprocess
import unittest
from pathlib import Path
from unittest import mock

_PATH = Path(__file__).resolve().parents[1] / "claude" / "pr_review_hook.py"
_spec = importlib.util.spec_from_file_location("pr_review_hook", _PATH)
hook = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(hook)

URL = "https://github.com/r0jjames/demo/pull/7"


def payload(command="gh pr create --fill", stdout=URL + "\n", response=None):
    if response is None:
        response = {"stdout": stdout, "stderr": "", "interrupted": False}
    return json.dumps({"hook_event_name": "PostToolUse", "tool_name": "Bash",
                       "tool_input": {"command": command},
                       "tool_response": response})


def run(raw, owners="r0jjames", copilot="0"):
    out = io.StringIO()
    code = hook.main(io.StringIO(raw), out,
                     {"PR_REVIEW_OWNERS": owners, "PR_REVIEW_COPILOT": copilot})
    return code, out.getvalue()


class TriggerTest(unittest.TestCase):
    def test_create_with_allowed_owner_emits_context(self):
        code, out = run(payload())
        self.assertEqual(code, 0)
        data = json.loads(out)["hookSpecificOutput"]
        self.assertEqual(data["hookEventName"], "PostToolUse")
        self.assertIn(URL, data["additionalContext"])
        self.assertIn(hook.SKILL_PATH, data["additionalContext"])

    def test_disallowed_owner_is_silent(self):
        self.assertEqual(run(payload(), owners="someone-else"), (0, ""))

    def test_other_command_is_silent(self):
        self.assertEqual(run(payload(command="gh pr view 7")), (0, ""))

    def test_failed_create_is_silent(self):
        self.assertEqual(
            run(payload(stdout="", response={"stdout": "",
                                             "stderr": "no commits"})),
            (0, ""))

    def test_echo_without_url_does_not_trigger(self):
        self.assertEqual(
            run(payload(command='echo "gh pr create"', stdout="gh pr create\n")),
            (0, ""))

    def test_malformed_stdin_is_silent(self):
        for raw in ("", "not json", "[]", '{"tool_input": "x"}'):
            self.assertEqual(run(raw), (0, ""), raw)

    def test_string_tool_response(self):
        code, out = run(payload(response=URL))
        self.assertIn(URL, out)

    def test_multiple_owners_case_insensitive(self):
        code, out = run(payload(), owners="some-org, R0JJames")
        self.assertIn(URL, out)

    def test_empty_owners_disables(self):
        self.assertEqual(run(payload(), owners=""), (0, ""))


class CopilotTest(unittest.TestCase):
    def test_off_by_default_never_calls_gh(self):
        with mock.patch.object(hook.subprocess, "run") as sp:
            run(payload())
        sp.assert_not_called()

    def test_on_requests_copilot_reviewer(self):
        with mock.patch.object(hook.subprocess, "run",
                               return_value=mock.Mock(returncode=0)) as sp:
            code, out = run(payload(), copilot="1")
        args = sp.call_args[0][0]
        self.assertEqual(args[:4], ["gh", "api", "-X", "POST"])
        self.assertIn("repos/r0jjames/demo/pulls/7/requested_reviewers", args)
        self.assertIn("reviewers[]=copilot-pull-request-reviewer[bot]", args)
        self.assertIn("Copilot review was also requested", out)

    def test_failed_request_still_emits_review_context(self):
        with mock.patch.object(hook.subprocess, "run",
                               return_value=mock.Mock(returncode=1)):
            code, out = run(payload(), copilot="1")
        self.assertIn(hook.SKILL_PATH, out)
        self.assertIn("Copilot review failed", out)

    def test_copilot_gh_missing(self):
        with mock.patch.object(hook.subprocess, "run",
                               side_effect=FileNotFoundError("gh")):
            code, out = run(payload(), copilot="1")
        self.assertEqual(code, 0)
        self.assertIn("Copilot review failed", out)

    def test_copilot_timeout(self):
        with mock.patch.object(hook.subprocess, "run",
                               side_effect=subprocess.TimeoutExpired("gh", 30)):
            code, out = run(payload(), copilot="1")
        self.assertIn("Copilot review failed", out)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m unittest tests.test_pr_review_hook -v`
Expected: ERROR — `FileNotFoundError` for `claude/pr_review_hook.py`.

- [ ] **Step 3: Write the hook**

`claude/pr_review_hook.py`:

```python
#!/usr/bin/env python3
"""Claude Code PostToolUse hook: auto-review PRs Claude opens.

After a Bash call that ran `gh pr create` and printed a new PR URL, if the
repo owner is in PR_REVIEW_OWNERS, tell Claude to review the PR by reading
the review-pr-comment skill file. With PR_REVIEW_COPILOT=1, also request a
Copilot review.

The first github.com PR URL in the output is used, so a command that chains
`gh pr create` with another command printing PR URLs may pick the wrong one.

Always exits 0 with no output unless it is triggering a review — a hook
must never block or break the tool call it follows.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from typing import Optional, Tuple

SKILL_PATH = "~/.claude/skills/review-pr-comment/SKILL.md"
COPILOT_BOT = "copilot-pull-request-reviewer[bot]"
PR_URL = re.compile(r"https://github\.com/([\w.-]+)/([\w.-]+)/pull/(\d+)")


def parse_payload(raw: str) -> Tuple[str, str]:
    """(command, output) from the hook payload; ("", "") if malformed."""
    try:
        data = json.loads(raw)
    except ValueError:
        return "", ""
    if not isinstance(data, dict):
        return "", ""
    tool_input = data.get("tool_input")
    command = tool_input.get("command", "") if isinstance(tool_input, dict) else ""
    response = data.get("tool_response")
    if isinstance(response, dict):
        output = "\n".join(str(response.get(k) or "") for k in ("stdout", "stderr"))
    else:
        output = str(response or "")
    return str(command), output


def find_pr(command: str, output: str) -> Optional[Tuple[str, str, int]]:
    """(owner, repo, number) when the command created a PR, else None."""
    if "gh pr create" not in command:
        return None
    match = PR_URL.search(output)
    if match is None:
        return None
    return match.group(1), match.group(2), int(match.group(3))


def owner_allowed(owner: str, owners_env: str) -> bool:
    allowed = {o.strip().lower() for o in owners_env.split(",") if o.strip()}
    return owner.lower() in allowed


def request_copilot(owner: str, repo: str, number: int) -> bool:
    """gh 2.64 does not document @copilot for --add-reviewer; use REST."""
    try:
        result = subprocess.run(
            ["gh", "api", "-X", "POST",
             f"repos/{owner}/{repo}/pulls/{number}/requested_reviewers",
             "-f", f"reviewers[]={COPILOT_BOT}"],
            capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.SubprocessError):
        return False
    return result.returncode == 0


def build_output(url: str, copilot: Optional[bool]) -> dict:
    context = (f"A PR was just opened at {url} in an allowlisted repository. "
               f"Review it now: read {SKILL_PATH} and follow it for this PR.")
    if copilot is True:
        context += " A Copilot review was also requested."
    elif copilot is False:
        context += (" Requesting a Copilot review failed; continue with the "
                    "Claude review and mention it in the final report.")
    return {"hookSpecificOutput": {"hookEventName": "PostToolUse",
                                   "additionalContext": context}}


def main(stdin=sys.stdin, out=sys.stdout, env=os.environ) -> int:
    pr = find_pr(*parse_payload(stdin.read()))
    if pr is None:
        return 0
    owner, repo, number = pr
    if not owner_allowed(owner, env.get("PR_REVIEW_OWNERS", "")):
        return 0
    copilot = (request_copilot(owner, repo, number)
               if env.get("PR_REVIEW_COPILOT") == "1" else None)
    url = f"https://github.com/{owner}/{repo}/pull/{number}"
    out.write(json.dumps(build_output(url, copilot)) + "\n")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:  # never break the tool call this hook follows
        sys.exit(0)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m unittest tests.test_pr_review_hook -v`
Expected: 14 tests, OK.

- [ ] **Step 5: Smoke-test as a real process**

Run:
```bash
echo '{"tool_input":{"command":"gh pr create"},"tool_response":{"stdout":"https://github.com/r0jjames/x/pull/1"}}' \
  | PR_REVIEW_OWNERS=r0jjames python3 claude/pr_review_hook.py; echo "exit=$?"
echo 'garbage' | python3 claude/pr_review_hook.py; echo "exit=$?"
```
Expected: first prints the JSON with `additionalContext` then `exit=0`; second prints only `exit=0`.

- [ ] **Step 6: Commit**

```bash
git add claude/pr_review_hook.py tests/test_pr_review_hook.py
git commit -m "feat(claude): add PR-create hook that triggers an auto-review"
```

---

### Task 2: Install and settings wiring

**Files:**
- Modify: `lib/tools/claude.py:18` (`_FILES`)
- Modify: `claude/settings.json` (add `env`, `hooks`, one `skillOverrides` entry)
- Modify: `tests/test_claude.py` (`ClaudeSettingsTest`)
- Modify: `claude/README.md` ("What the installer does" + new "PR auto-review" section)

**Interfaces:**
- Consumes: `claude/pr_review_hook.py` from Task 1.
- Produces: `~/.claude/pr_review_hook.py` after install; settings keys `env.PR_REVIEW_OWNERS`, `env.PR_REVIEW_COPILOT`, `hooks.PostToolUse`.

- [ ] **Step 1: Write the failing tests**

Append to `ClaudeSettingsTest` in `tests/test_claude.py` (before `if __name__`):

```python
    def test_pr_review_hook_is_installed(self):
        self.assertIn("pr_review_hook.py", claude._FILES)

    def test_pr_review_hook_command_is_not_machine_specific(self):
        entries = self.settings()["hooks"]["PostToolUse"]
        commands = [h["command"] for e in entries if e["matcher"] == "Bash"
                    for h in e["hooks"]]
        hook = [c for c in commands if "pr_review_hook.py" in c]
        self.assertEqual(len(hook), 1, commands)
        self.assertIn("$HOME/.claude/pr_review_hook.py", hook[0])
        self.assertNotIn("/Users/", hook[0])
        self.assertNotIn("/home/", hook[0])

    def test_pr_review_defaults(self):
        env = self.settings()["env"]
        self.assertEqual(env["PR_REVIEW_OWNERS"], "r0jjames")
        self.assertEqual(env["PR_REVIEW_COPILOT"], "0")

    def test_review_skill_stays_out_of_the_listing(self):
        overrides = self.settings()["skillOverrides"]
        self.assertEqual(overrides["review-pr-comment"], "user-invocable-only")
```

- [ ] **Step 2: Run to verify they fail**

Run: `python3 -m unittest tests.test_claude -v`
Expected: 4 failures/errors (`KeyError: 'hooks'`, `'env'`, `'review-pr-comment'`, and the `_FILES` assertion).

- [ ] **Step 3: Implement**

`lib/tools/claude.py` line 18:

```python
_FILES = ("settings.json", "statusline-command.sh", "CLAUDE.md",
          "pr_review_hook.py")
```

Also update the module docstring's first line to `"""Claude Code: CLI install + global settings + statusline + PR-review hook.`.

`claude/settings.json`: add `"review-pr-comment": "user-invocable-only",` after the `"code-review-pr-fast"` line in `skillOverrides`, and add these two top-level keys directly after the `statusLine` block:

```json
  "env": {
    "PR_REVIEW_OWNERS": "r0jjames",
    "PR_REVIEW_COPILOT": "0"
  },
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "Bash",
        "hooks": [
          {
            "type": "command",
            "command": "python3 \"$HOME/.claude/pr_review_hook.py\""
          }
        ]
      }
    ]
  },
```

`claude/README.md`: in "What the installer does", insert after item 3 and renumber the CLI step to 5:

```markdown
4. Links `claude/pr_review_hook.py` → `~/.claude/pr_review_hook.py` (the
   PR auto-review hook, below).
```

Change "the three config files are **copied**" to "the config files are **copied**" in the Windows section, and add this section before "## Not managed by this repo":

````markdown
## PR auto-review

`settings.json` registers `pr_review_hook.py` as a `PostToolUse` hook on
Bash. When Claude runs `gh pr create` and the new PR's owner is in
`PR_REVIEW_OWNERS`, the hook tells Claude to follow
`~/.claude/skills/review-pr-comment/SKILL.md` (from `agent-skills`), which
posts one `COMMENT` review with inline comments to the PR. It posts
without asking — the allowlist is the authorization.

| Variable | Default | Meaning |
|---|---|---|
| `PR_REVIEW_OWNERS` | `r0jjames` | Comma-separated owners/orgs whose repos get auto-review; empty disables |
| `PR_REVIEW_COPILOT` | `0` | `1` also requests a Copilot review |

Override per repository in its `.claude/settings.json`:

```json
{ "env": { "PR_REVIEW_COPILOT": "1" } }
```

`{ "env": { "PR_REVIEW_OWNERS": "" } }` opts a repo out. PRs opened from the
web UI or a plain terminal are not reviewed; run `/review-pr-comment <n>` by
hand for those. On Windows/Git Bash the hook needs `python3` on `PATH`.
````

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -c "import json;json.load(open('claude/settings.json'))" && python3 -m unittest tests.test_claude -v`
Expected: JSON parses; all tests OK (the install tests pick up the new `_FILES` entry automatically via `setUp`).

- [ ] **Step 5: Commit**

```bash
git add lib/tools/claude.py claude/settings.json claude/README.md tests/test_claude.py
git commit -m "feat(claude): register the PR auto-review hook and its settings"
```

---

### Task 3: The review-pr-comment skill

**Files:**
- Create: `agent-skills/skills/review-pr-comment/SKILL.md`
- Modify: `agent-skills/install.py:184-190` (`REQUIRES`)
- Modify: `agent-skills/README.md` (Layout list + Skill dependencies table)

**Interfaces:**
- Consumes: `SKILL_PATH` from Task 1 (`~/.claude/skills/review-pr-comment/SKILL.md`) — the skill directory name must be exactly `review-pr-comment`. Method files from `code-review-pr/references/`: `review-method.md`, `cross-cutting.md`, `lang-{bash,go,java,python}.md`, `platform-{bamboo,docker,helm,k8s}.md`.
- Produces: the installed skill at `~/.claude/skills/review-pr-comment/`.

- [ ] **Step 1: Write the failing test for the dependency**

Check how `test_install.py` tests `REQUIRES` (around line 1645) and add, in the same class and style:

```python
    def test_review_pr_comment_requires_code_review_pr(self):
        self.assertIn("code-review-pr",
                      install.REQUIRES["review-pr-comment"])
```

(Use whatever name the file imports the installer module as — check the top of `agent-skills/test_install.py`.)

Run: `python3 agent-skills/test_install.py 2>&1 | tail -5`
Expected: one ERROR, `KeyError: 'review-pr-comment'`.

- [ ] **Step 2: Add the dependency**

In `agent-skills/install.py` `REQUIRES`:

```python
REQUIRES = {
    # context-map and write-pr-description were dropped: ...(keep comment)
    "explain-feature-changes": ("code-tour",),
    "review-pr-comment": ("code-review-pr",),
}
```

Run: `python3 agent-skills/test_install.py 2>&1 | tail -3`
Expected: OK.

- [ ] **Step 3: Write the skill**

`agent-skills/skills/review-pr-comment/SKILL.md`:

````markdown
---
name: review-pr-comment
description: Review an open GitHub pull request and post the findings to it as one COMMENT review with inline comments. Runs automatically after Claude opens a PR in an allowlisted repository (the pr_review_hook tells Claude to follow this file), or by hand with a PR URL or number. Uses the code-review-pr method. For a local branch without a PR, use code-review-pr instead.
---

# Review PR — post comments

Review a GitHub PR's diff with the `code-review-pr` method and post the
result to the PR: one review, `event: COMMENT`, inline comments on the
changed lines, a short summary body. Posts without asking — reaching this
skill through the hook means the repo owner is allowlisted, and a manual
run is an explicit request.

Rules for the whole run:

- Commands allowed: `git`, `gh pr view`, `gh pr diff`, `gh api` on this
  PR's reviews. Nothing else.
- Never approve, request changes, push, or edit the PR.
- Every finding anchors to a line inside a diff hunk, carries a severity and
  a confidence, and dies if it cannot be tied to concrete failure.
- A clean PR is reported as clean. Never invent findings.
- No Claude attribution anywhere in the review.

## 1. Load the method

Read `references/review-method.md` and `references/cross-cutting.md` from
the installed `code-review-pr` skill. First location that exists wins:

1. `<repo>/.github/skills/code-review-pr/references/`
2. `~/.copilot/skills/code-review-pr/references/`
3. `~/.claude/skills/code-review-pr/references/`
4. `~/.agents/skills/code-review-pr/references/`

None found: say "code-review-pr is not installed — run
`agent-skills/install.py`" and stop. No review without the method.

Load technology lenses (`lang-*.md`, `platform-*.md`) from the same
directory only for stacks the diff touches, as the method's lens-selection
phase says.

## 2. Resolve the PR

Argument is a URL or number; none → the current branch's PR.

```bash
gh pr view <arg> --json number,url,baseRefName,headRefOid,isDraft,title,body,headRepositoryOwner,headRepository
```

Take `owner`/`repo` from the URL. No PR found: say so and stop. Draft PRs
are reviewed like any other.

## 3. Skip if this commit is already reviewed

```bash
gh api repos/<owner>/<repo>/pulls/<n>/reviews --paginate --jq '.[].body'
```

If any body contains `<!-- review-pr-comment:<headRefOid> -->`, say
"<headRefOid short> already reviewed: <url>" and stop.

## 4. Collect the diff

If `git rev-parse HEAD` equals `headRefOid`:

```bash
git fetch origin <baseRefName> --quiet
git diff -U15 origin/<baseRefName>...HEAD
```

Otherwise use `gh pr diff <n>`. Read whole changed files where the method
says to. The PR title and body are the stated intent.

## 5. Review

Follow the loaded method: severity (🔴 Blocker, 🟠 Major, 🟡 Minor,
🔵 Nit), confidence (Confirmed, Probable; Speculative never becomes a
finding), and its gates and never-report list.

For each finding record `path`, `line` (line number in the **new** file,
inside a hunk's `+`/context range), severity, confidence, the defect, the
failure scenario, and the fix.

## 6. Build and post the review

Order findings by severity. The first 15 become inline comments; any beyond
15, and any whose line is not in a hunk, go in the body.

Inline comment body:

```
🟠 **Major** · Probable — <defect>.

Fails when: <scenario>.

Fix: <change>.
```

When the fix replaces exactly the anchored line, append a suggestion block
with the replacement line:

````
```suggestion
<replacement line>
```
````

Review body:

```
**Automated review** — <2–4 lines: what this PR does>

<n> findings: <x> 🔴 · <y> 🟠 · <z> 🟡 · <w> 🔵

<findings that could not go inline, one per line as `path:line` — summary>

<!-- review-pr-comment:<headRefOid> -->
```

No findings: body is the summary line, "No findings.", and the marker.

Write the payload to a temp file **outside the repo** (`mktemp`), then post
and delete it:

```json
{
  "commit_id": "<headRefOid>",
  "event": "COMMENT",
  "body": "<review body>",
  "comments": [
    {"path": "<path>", "line": <line>, "side": "RIGHT", "body": "<comment body>"}
  ]
}
```

```bash
gh api repos/<owner>/<repo>/pulls/<n>/reviews --method POST --input "$payload"
rm -f "$payload"
```

## 7. Failures

- **HTTP 422** (a line not in the diff): move every inline comment into the
  body as `path:line` entries, set `comments` to `[]`, post once more. Do
  not retry again.
- **`gh` not authenticated / network error**: print the findings in chat in
  the inline-comment format and say nothing was posted.

## 8. Report

One or two lines in chat: the review URL (`html_url` from the response),
finding counts, and — if the hook said so — that the Copilot request
failed.
````

- [ ] **Step 4: Validate frontmatter and install locally**

Run:
```bash
head -4 agent-skills/skills/review-pr-comment/SKILL.md
python3 agent-skills/install.py --help | head -20
```
Then install the skill for Claude using the flag the help shows for a single skill (e.g. `python3 agent-skills/install.py --claude review-pr-comment` — check the help output; do not guess). Expected: `~/.claude/skills/review-pr-comment/SKILL.md` exists and `~/.claude/skills/code-review-pr/references/review-method.md` exists.

Run: `ls -l ~/.claude/skills/review-pr-comment/SKILL.md ~/.claude/skills/code-review-pr/references/review-method.md`
Expected: both listed.

- [ ] **Step 5: Update agent-skills/README.md**

In Layout, after the `code-review-pr-fast` bullet:

```markdown
- `skills/review-pr-comment/` — reviews an open GitHub PR with the
  `code-review-pr` method and posts one `COMMENT` review with inline
  comments via `gh`. Triggered automatically by the `claude` tool's
  `pr_review_hook.py` when Claude opens a PR in an allowlisted repo (see
  [claude/README.md](../claude/README.md#pr-auto-review)); also runnable by
  hand. The only custom skill that writes to the PR host.
```

In the Skill dependencies table add the row:

```markdown
| `review-pr-comment` | `code-review-pr` |
```

- [ ] **Step 6: Run the full suite**

Run: `python3 -m unittest discover tests 2>&1 | tail -3 && python3 agent-skills/test_install.py 2>&1 | tail -3`
Expected: both `OK`.

- [ ] **Step 7: Commit**

```bash
git add agent-skills/skills/review-pr-comment agent-skills/install.py agent-skills/test_install.py agent-skills/README.md
git commit -m "feat(agent-skills): add review-pr-comment, posting reviews to PRs"
```

---

### Task 4: Live end-to-end verification

No code unless a check fails. Needs a new Claude Code session so the new hook and settings load. **Creating a GitHub repo and PRs is outward-facing — confirm with the user before Step 1.**

**Files:**
- Modify (only if Step 5 fails): `claude/pr_review_hook.py`, `claude/settings.json`, `claude/README.md`, `tests/test_pr_review_hook.py`, `tests/test_claude.py` to remove the Copilot switch.

- [ ] **Step 1: Make a throwaway repo with a planted bug**

```bash
cd "$(mktemp -d)" && git init -q -b main && printf 'def total(xs):\n    return sum(xs)\n' > calc.py
git add . && git commit -qm init
gh repo create r0jjames/pr-review-sandbox --private --source . --push
git switch -c planted-bug
printf 'def total(xs):\n    t = 0\n    for i in range(1, len(xs)):\n        t += xs[i]\n    return t\n' > calc.py
git commit -qam "refactor: loop in total" && git push -qu origin planted-bug
```

- [ ] **Step 2: Open the PR through Claude Code**

In a fresh `claude` session in that directory, ask: "open a PR for this branch". Expected: after `gh pr create`, Claude reads the skill file and posts a review without being asked.

- [ ] **Step 3: Check the review**

```bash
gh api repos/r0jjames/pr-review-sandbox/pulls/1/reviews --jq '.[] | {state, body}'
gh api repos/r0jjames/pr-review-sandbox/pulls/1/comments --jq '.[] | {path, line, body}'
```
Expected: exactly one review, `state: "COMMENTED"`, body ends with `<!-- review-pr-comment:<sha> -->`; an inline comment on `calc.py` line 3 flagging the skipped first element; no Claude attribution.

- [ ] **Step 4: Check dedupe**

In the same session run `/review-pr-comment 1`. Expected: "already reviewed", and the reviews list still has one entry.

- [ ] **Step 5: Check Copilot**

In the sandbox add `.claude/settings.json` with `{"env":{"PR_REVIEW_COPILOT":"1"}}`, push a second branch, open PR 2 through Claude. Then:
```bash
gh api repos/r0jjames/pr-review-sandbox/pulls/2/requested_reviewers
```
Expected: Copilot is listed (or has already reviewed). **If the request fails on this account, remove the Copilot switch** (the `request_copilot` function and its tests, the `PR_REVIEW_COPILOT` env key and its test, the README row), run the suite, and commit `fix(claude): drop the Copilot switch — not available on this account`.

- [ ] **Step 6: Negative check**

In the sandbox set `.claude/settings.json` to `{"env":{"PR_REVIEW_OWNERS":""}}`, open PR 3 through Claude. Expected: no review posted.

- [ ] **Step 7: Clean up and report**

Report the PR 1 review URL as evidence. Ask the user before deleting the sandbox repo (`gh repo delete r0jjames/pr-review-sandbox` needs the `delete_repo` scope).
