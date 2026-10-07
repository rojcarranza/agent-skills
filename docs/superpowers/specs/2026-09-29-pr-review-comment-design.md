# review-pr-comment skill + PR-create hook — design

Date: 2026-09-29

## Problem

Personal projects get no automatic review when a PR is opened. The options
today each need something that is not always there: Copilot PR review needs
Copilot quota on the account, and a Claude CI workflow needs an API key or
OAuth token stored as a repository secret.

The existing `code-review-pr` and `code-review-pr-fast` skills already hold
a good review method, but they run only when asked and are deliberately
git-only — they never touch the PR host. So their findings never reach the
PR.

## Goal

When Claude Code opens a PR (`gh pr create`) in a repository owned by the
user, a review is posted to that PR automatically, as one GitHub `COMMENT`
review with inline comments — using the Claude subscription of the session
that opened it. No token in the repo, no CI.

Copilot review stays available as an opt-in extra, off by default.

Not goals:

- PRs opened from the GitHub web UI or a plain terminal. Only PRs created
  through Claude Code trigger the review. The skill can still be run by hand
  on any PR.
- Approving, requesting changes, pushing fixes, or writing report files.
- Changing `code-review-pr`. Its "git-only, no PR host API" contract stays
  intact — that contract is what keeps it safe on work repositories.

## Decisions

| Question | Choice |
|---|---|
| Where PRs are created | From Claude Code (`gh pr create` via the Bash tool) |
| Trigger mechanism | `PostToolUse` hook injecting `additionalContext` that tells Claude to run the skill |
| Output on GitHub | One review, `event: COMMENT`, inline comments + short summary body |
| Which repos | Owner-based allowlist; default is the user's login `r0jjames` |
| Confirmation before posting | None — auto-post. The user's request is standing authorization, scoped to allowlisted owners |
| Copilot | Opt-in switch, default off; requested by the hook alongside Claude's review |

Rejected approaches:

- **Hook spawns a headless `claude -p` review.** Detached and context-free,
  but cold-starts, bills a second session, and fails silently.
- **Add a `--post` mode to `code-review-pr`.** One skill fewer, but breaks
  its git-only contract.

Known limit of the chosen approach: a hook cannot force a skill to run. It
injects an instruction Claude follows. Reliable in practice, not a hard
guarantee. The review also runs in the same session, so it spends that
session's context — which is also why it is good: the session that opened
the PR knows why the branch exists.

## Components

### 1. `agent-skills/skills/review-pr-comment/SKILL.md`

- **Input:** PR URL or number. No argument → the current branch's PR
  (`gh pr view`).
- **Method:** loads `references/review-method.md`, `cross-cutting.md`, and
  the matching technology lenses from the installed `code-review-pr` skill,
  resolved with the same four-location lookup `code-review-pr-fast` uses
  (`<repo>/.github/skills/`, `~/.copilot/skills/`, `~/.claude/skills/`,
  `~/.agents/skills/`). Depends on `code-review-pr`; does not copy it. If the
  method is not found anywhere, say so in one line and stop — no review
  without the method.
- **Posts:** exactly one review per run via
  `gh api repos/{owner}/{repo}/pulls/{n}/reviews --input <payload.json>`.
- Invocable by hand (`/review-pr-comment 42`) as well as from the hook.
- `skillOverrides`: `user-invocable-only`, like the other custom skills —
  no per-turn listing cost.
- `REQUIRES` in `agent-skills/install.py`: `code-review-pr`.
- Documented as a new entry in `agent-skills/README.md` Layout, with its
  dependency on `code-review-pr` listed under Skill dependencies.

### 2. `claude/pr_review_hook.py`

Python 3, stdlib only — it parses the hook's JSON payload and must run on
Windows/Git Bash where `jq` is not guaranteed.

Registered in `claude/settings.json`:

```json
"hooks": {
  "PostToolUse": [
    {
      "matcher": "Bash",
      "hooks": [
        { "type": "command", "command": "python3 \"$HOME/.claude/pr_review_hook.py\"" }
      ]
    }
  ]
}
```

Logic, as pure functions so it is unit-testable:

1. `parse_payload(stdin)` → `tool_input.command` and the tool's output.
   Anything malformed → no-op.
2. Proceed only if the command contains `gh pr create` **and** the output
   contains `https://github.com/<owner>/<repo>/pull/<n>`. Both are required,
   so `echo "gh pr create"` does not trigger.
3. `owner_allowed(owner, PR_REVIEW_OWNERS)` — case-insensitive match against
   the comma-separated list.
4. If `PR_REVIEW_COPILOT=1`: `gh api -X POST
   repos/{owner}/{repo}/pulls/{n}/requested_reviewers -f
   'reviewers[]=copilot-pull-request-reviewer[bot]'`. (`gh` 2.64.0 on this
   machine does not document `@copilot` for `--add-reviewer`, so the REST
   endpoint is used.)
5. `build_output(...)` → hook JSON with
   `hookSpecificOutput: {hookEventName: "PostToolUse", additionalContext}`: "A PR was just opened at <url>
   in an allowlisted repository. Review it now: read
   ~/.claude/skills/review-pr-comment/SKILL.md and follow it for this PR."
   The hook names the file rather than the skill because custom skills are
   `user-invocable-only` in `skillOverrides` (kept out of the per-turn
   listing); reading the file works regardless.
   Plus one line on the Copilot request's outcome when it was attempted.

Always exits 0. Never blocks the tool call.

On Windows/Git Bash `python3` may not be on `PATH` (only `python` or `py`).
The live verification covers macOS/Linux; Windows is checked when the
installer next runs there, and the command is adjusted then if needed.

Added to `_FILES` in `lib/tools/claude.py` so it lands in `~/.claude/`
(symlink on macOS/Linux, copy on Windows) next to `statusline-command.sh`.

### 3. Configuration

Environment variables in `claude/settings.json` `env`:

| Variable | Default | Meaning |
|---|---|---|
| `PR_REVIEW_OWNERS` | `r0jjames` | Comma-separated GitHub owners/orgs whose repos get auto-review |
| `PR_REVIEW_COPILOT` | `0` | `1` also requests a Copilot review |

A repository's own `.claude/settings.json` can set either variable to
override the global value (add an org, turn Copilot on for one repo, or set
`PR_REVIEW_OWNERS` to empty to opt out). No extra config file.

### 4. Docs

- `agent-skills/README.md`: Layout entry for `review-pr-comment`, and its
  dependency on `code-review-pr`.
- `claude/README.md`: the hook, its two variables, and how to opt a repo
  in or out.

## Review flow

1. **Hook** (after `gh pr create` succeeds): extract URL → check owner →
   optionally request Copilot → emit `additionalContext`.
2. **Gather:** `gh pr view <url> --json
   number,baseRefName,headRefOid,isDraft,title,body`. Diff with
   `git diff -U15 origin/<base>...HEAD` from the local checkout. If local
   `HEAD` ≠ `headRefOid`, use `gh pr diff <n>` instead.
3. **Dedupe:** list the PR's reviews
   (`gh api repos/{owner}/{repo}/pulls/{n}/reviews`). If any body contains
   `<!-- review-pr-comment:<headRefOid> -->`, stop and say the commit is
   already reviewed.
4. **Review** per the `code-review-pr` method: every finding anchors to a
   line in a diff hunk, has a severity and confidence, and is dropped if it
   cannot be tied to a concrete failure. Draft PRs are reviewed too.
5. **Post** one payload:
   - `commit_id`: `headRefOid`; `event`: `COMMENT`.
   - `body`: 2–4 lines on what the PR does, finding counts by severity, any
     finding that could not anchor inline, and the hidden marker
     `<!-- review-pr-comment:<headRefOid> -->` as the last line.
   - `comments[]`: `{path, line, side: "RIGHT", body}` — severity tag,
     problem, concrete fix. When the fix is a direct replacement of the
     anchored lines, the body includes a ```` ```suggestion ```` block.
   - At most 15 inline comments, highest severity first. The rest go in the
     body as a list.
   - No findings → still post a short "No findings" review, so a run is
     visible.
   - No Claude attribution footer (global CLAUDE.md). Posts as the user via
     `gh` auth.
6. **Report in chat:** review URL and counts.

## Error handling

| Failure | Behaviour |
|---|---|
| Hook: bad JSON, no URL, owner not allowed, `gh pr create` failed | Silent no-op, exit 0 |
| Copilot request fails (no Copilot on account/plan) | Context line says it was not requested; Claude's review proceeds |
| GitHub `422` on the review (a line not in the diff) | Retry once with every finding moved into the body |
| `gh` not authenticated / no network | Print findings in chat, state that nothing was posted |
| `code-review-pr` method not installed | Say so in one line and stop |
| Same head SHA already reviewed | Skip, say so |

## Testing

**`tests/test_pr_review_hook.py`** (stdlib `unittest`, `gh` mocked):

- Create command + allowed owner → `additionalContext` naming the skill and
  URL.
- Disallowed owner, non-create command, output without URL, malformed or
  empty stdin → no output, exit 0.
- Multiple comma-separated owners; case-insensitive match.
- `echo "gh pr create"` with no URL in output → no trigger.
- `PR_REVIEW_COPILOT=1` → calls `requested_reviewers` with
  `copilot-pull-request-reviewer[bot]`; a failing call still returns the
  review context plus the not-requested line.

**`tests/test_claude.py`** additions:

- `pr_review_hook.py` is in `_FILES`.
- The hook command in `settings.json` uses `$HOME/.claude/` (not a
  machine-specific path).
- `PR_REVIEW_OWNERS` and `PR_REVIEW_COPILOT` defaults are present in `env`.

**Skill, live verification** (skills are prose; checked by running them):

- Frontmatter valid; the `code-review-pr` references resolve from the
  installed location.
- End-to-end on a throwaway repo owned by `r0jjames`: branch with a planted
  bug → Claude opens the PR → hook fires → one `COMMENT` review lands with
  inline comments on the correct lines and the marker → a manual re-run on
  the same SHA is skipped.
- Once with `PR_REVIEW_COPILOT=1`, to confirm the Copilot reviewer request
  works on this account. If it does not, the Copilot switch is removed from
  the implementation rather than shipped broken.
- Negative: a repo not in the allowlist gets no review.

**Done means:** `python3 -m unittest discover tests` and
`python3 agent-skills/test_install.py` pass, and the live test PR's URL is
reported as evidence.
