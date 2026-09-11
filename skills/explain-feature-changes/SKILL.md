---
name: explain-feature-changes
description: Explain the changes on the user's own Git feature branch compared with its base branch (develop or main) so they understand them and can explain them confidently in PR review. Covers what changed, why, how the new code works, before and after behavior, callers and code flow, and writes copy/paste-ready PR text plus per-change PR comments. Use when the user says "explain my changes compared to develop", "help me understand what I changed in this branch", "explain the new functions and code flow in my branch", "generate something I can paste into my PR", "help me explain these changes to my reviewer", or types /explain-feature-changes with an optional base branch. Not a code review. Not for a single file, a single function, or a branch the user did not write.
---

# Explain Feature Changes

Help the developer understand the changes on their own feature branch and
explain them to a reviewer. Do not summarize the diff. Trace the changed code
until its behavior is clear, then explain it.

This is not a code review. Report an issue only when it changes how the
feature should be understood (Important Observations in
`references/output-template.md`).

## Rules for the whole run

- Read-only. Run `git` commands and read files. The only other command is
  the tour validator in phase 8. Never commit, push, reset, rebase,
  checkout, switch, stash, fetch or edit source code unless the user asks.
- Write only two files: the report (phase 6) and the tour (phase 8).
- One plain `git` command per call. No `$(...)`, no pipes, no `grep`,
  `sed` or `awk`: the terminal may be PowerShell or cmd. Search code with
  `git grep -n`.
- In an IDE terminal (VS Code, IntelliJ, PyCharm, GoLand), put `--no-pager`
  right after `git` for `log`, `diff` and `show` — for example
  `git --no-pager diff --stat <base>...HEAD` — so no pager stops the run.
- Never invent intent, requirements or behavior. Label every intent claim
  confirmed, likely or unknown (phase 5).
- Reference code as `path/from/repo/root:start-end`. Quote code, commands
  and error text verbatim.

No terminal (agent mode off, or a Copilot setup without command access): say
so and ask for exactly two pastes — the output of `git diff <base>...HEAD`
and of `git log <base>..HEAD`. Ask for nothing else up front.
Explain from those two outputs, and name the skipped phases in the report
header.

## Companion skills

| Skill | Used in | If missing |
|---|---|---|
| `context-map` | phase 2, large branches | group the files yourself |
| `write-pr-description` | phase 6, PR Explanation | fallback rules in `references/output-template.md` |
| `code-tour` | phase 8 | write the tour inline |

A missing companion is not an error. Name it once in chat with its skills.sh
source (`github/awesome-copilot/context-map`,
`warpdotdev/common-skills/write-pr-description`,
`github/awesome-copilot/code-tour`) and continue with the fallback.

## Phase 1 — Resolve the base branch

First hit wins:

1. The user's argument (`/explain-feature-changes release/2.4`).
2. `develop`: use `origin/develop` if
   `git rev-parse --verify --quiet origin/develop` prints a SHA, else local
   `develop` if `git rev-parse --verify --quiet develop` does.
3. `main`: the same check for `origin/main`, then local `main`.
4. Nothing resolves: ask which branch to compare against. Never guess.

Run `git branch --show-current`. If it prints the base branch itself — for a
remote base such as `origin/develop`, also its local name `develop` — or
nothing (detached HEAD), ask which branch to explain.

Run `git merge-base <base> HEAD` and keep the printed SHA as `<merge-base>`
for later commands. State the comparison before anything else:

> Comparing `feature/x → develop` (merge base `a1b2c3d`)

The base ref may be stale. Say so if it matters; do not fetch.

## Phase 2 — Collect the diff

Run, in order:

1. `git status --porcelain` — uncommitted files are not explained. List
   them in the report header, so the reader knows what the PR text leaves
   out. Leave out this skill's own output: `<branch-slug>-changes.md` and
   anything under `.tours/`.
2. `git log <base>..HEAD` — commit subjects and bodies are intent evidence.
3. `git diff --name-status <base>...HEAD` — added, modified, deleted,
   renamed. A rename is not new code.
4. `git diff --stat <base>...HEAD` — size decides depth.
5. `git diff -U15 <base>...HEAD -- <file>` for each meaningful file. For a
   rename, pass both paths — `git diff -U15 <base>...HEAD -- <old> <new>` —
   so only the edits inside the moved file show, not the whole file as new.
6. Read the whole current file for anything non-trivial. A hunk alone hides
   what the surrounding code already does.

Always three-dot for `git diff`. Two-dot pulls in everything merged into the
base since the branch point.

List without explaining, one line each: vendored code, generated files,
lockfiles, binaries, and changes that only touch formatting, whitespace or
import order.

Large branch — more than about 15 meaningful files or 1000 changed lines: run
`context-map` over the changed files first, write the executive summary
before the details, and group files by responsibility (for example decision
logic, event processing, messaging, configuration, tests), never
alphabetically.

## Phase 3 — Build the change inventory

Load `references/tracing.md` from this skill's directory.

For each changed file record its status, what the file is for, what changed,
and one category: behavior, API/interface, configuration, dependency, test,
or trivial. For each function, method, class or configuration key record
whether it is new, modified or removed.

Rank by behavioral impact. Trivial changes get one line in the report and no
tracing.

## Phase 4 — Trace

For every new or behavior-changing symbol, follow `references/tracing.md`:
callers, callees, inputs, outputs, what the caller does with the result, the
code that did this job before, the tests that exercise it, and the
configuration that changes it. Then run its architecture checklist, limited
to what the diff touches.

Stop when you can state the behavior before and after in one or two
sentences each, with line references.

## Phase 5 — Establish intent

Evidence, strongest first: commit messages, ticket IDs in the branch name or
commits, test names and assertions, docs or comments changed in the diff,
naming. Label every intent claim:

- **Confirmed** — stated in a commit message, ticket reference, doc or test.
- **Likely** — "The likely purpose is …", followed by the evidence.
- **Unknown** — "The exact reason is not explicit in the code."

Never present a likely or unknown reason as confirmed.

## Phase 6 — Write

Load `references/output-template.md` and follow its skeleton, evidence rules
and style rules. Leave out any section that would be empty. Consult
`examples/example-run.md` if the depth or tone needs grounding; never copy
its facts.

PR Explanation: if `write-pr-description` is installed, follow it for this
section, with these overrides:

- The verified facts from phases 2–5 are its input. Skip its fact-gathering
  step entirely: no `gh`, and no commands other than this skill's.
- For its validation part, say what the tests cover and leave a visible
  `<how you validated>` placeholder for the developer. Never claim a test
  run you did not see.
- A PR template in the repository wins, if one exists
  (`.github/pull_request_template.md`, `.github/PULL_REQUEST_TEMPLATE/`,
  `docs/pull_request_template.md`).
- Keep the `path:start-end` references this skill requires.

Otherwise use the fallback rules in `references/output-template.md`.

Write the report to `<branch-slug>-changes.md` at the repository root, where
`<branch-slug>` is the current branch name with `/` replaced by `-`. Replace
an earlier report of the same name.

## Phase 7 — Self-check

Confirm each item and fix the report where one fails:

- The comparison names the right base and merge base.
- Every behavior claim has a `path:start-end` reference that matches the
  current file. Re-open each cited file and confirm the cited lines hold
  the code the claim is about — a docstring, comment or blank line next to
  it does not count.
- Every new or changed symbol lists its callers, or says it has none.
- Before and after are both stated for each behavior change.
- Every intent claim carries confirmed, likely or unknown.
- Tests are tied to the behavior they cover.
- No generic review findings, style advice or refactoring suggestions.
- The PR Explanation and PR Comments paste cleanly: no chat wording, no
  mention of this conversation.

## Phase 8 — Tour

Write `.tours/changes-<branch-slug>.tour` in the repository, persona
`pr-reviewer`, through the `code-tour` skill. If `code-tour` is missing,
write the JSON inline: `$schema`, `title`, `description`, and `steps` of
`{file, line, description}` is enough for the CodeTour extension to open it.

Steps follow the End-to-End Flow order and reuse only `file:line` references
already cited in the report. Never investigate again to build the tour.

Validate with `scripts/validate_tour.py` from the installed `code-tour`
skill directory: `~/.claude/skills/code-tour/`,
`~/.copilot/skills/code-tour/`, or `<repo>/.github/skills/code-tour/`. Its
own SKILL.md names an `~/.agents/...` path that usually does not exist.
Resolve the home directory to an absolute path first — `~` does not expand
in cmd — and run the script with `python`, or `python3` if `python` is not
found. Skip validation if the script or an interpreter is not found.

Skip the tour only when the branch changes one file and the tour would have
fewer than about three steps; say so in one line with the reason. The user
saying "no tour" skips it; "make a tour" overrides a skip. Never add
`.tours/` to `.gitignore` and never commit the tour.

## Finish — report in chat

After phase 8, print only:

- the comparison line,
- the Feature Change Overview,
- Key Things to Understand,
- the report path, and the tour path or the one-line reason there is no tour,
- one line naming any companion skill that was missing or a validator that
  could not run.

Uncommitted and listed-only files belong in the report header, not in chat.
Then say the report and `.tours/` are untracked and offer to add both to
`.git/info/exclude` so they are never committed. Never edit `.gitignore`.
