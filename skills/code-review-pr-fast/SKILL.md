---
name: code-review-pr-fast
description: Quick chat-only review of the current Git feature branch diff — no report file, no CodeTour, no commands beyond git. Use when the user says "quick review", "fast review", "sanity check my changes", "review this before I commit", or wants a short pass mid-work. For the full review with a written report, a change summary and a tour, use code-review-pr instead.
---

# Code Review PR — fast

A short pass over the branch diff. Chat output only. Nothing is written to
disk and no tool other than `git` runs.

Use `code-review-pr` instead when the change is going into a PR, when the
user wants to understand the change, or when infrastructure and CI/CD are
involved.

## Load the method

Read `references/review-method.md` from the installed `code-review-pr`
skill. Try these in order and stop at the first that exists — the right one
depends on the agent and the platform, so do not assume:

1. `<repo>/.github/skills/code-review-pr/references/review-method.md`
   (repo scope, seeded by `install.py --repo .`)
2. `~/.copilot/skills/code-review-pr/references/review-method.md`
   (GitHub Copilot personal scope, VS Code and JetBrains)
3. `~/.claude/skills/code-review-pr/references/review-method.md`
   (Claude Code personal scope)
4. `~/.agents/skills/code-review-pr/references/review-method.md`

On Windows and Git Bash, `~` resolves under `%USERPROFILE%`; the same four
paths apply. If none exist, use the condensed tables at the bottom of this
file and say in one line that the full method was not found.

Load at most one technology lens from the same `references/` directory, and
only when the diff is dominated by one stack. When the diff spans several,
load none and rely on the method plus `cross-cutting.md`.

## Run

1. **Base** — `git symbolic-ref refs/remotes/origin/HEAD`, else the first of
   `origin/main`, `origin/master`, `origin/develop`. Nothing resolves: ask
   once.
2. **Diff** — `git diff --stat <base>...HEAD`, then
   `git diff -U10 <base>...HEAD`. Three-dot always; two-dot pulls in
   unrelated merged work.
3. **Read** the whole file for any hunk whose surrounding context matters.
4. **Review** the changed hunks. Diff-local only — no caller search, no
   system pass. Say so at the end, so the user knows what was not checked.
5. **Report** in chat.

Skip entirely: uncommitted work, generated and vendored paths, renames with
unchanged content.

## Output

Six lines of header and findings, nothing else:

```
<branch> vs <base> · <n> files · +<a>/-<b> · lens: <one or none>
Verdict: <approve | approve with nits | changes requested | blocked>

🔴 `path:line` · Confirmed — <defect>. Fails when: <scenario>. Fix: <change>.
🟠 `path:line` · Probable — <defect>. Fails when: <scenario>. Fix: <change>.

Diff-local pass only — callers, config coupling and tests were not checked.
Run code-review-pr for the full review.
```

Clean diff: say "Nothing to flag" and stop. Never invent findings, never pad
with Nits, cap at five findings and name the overflow count.

## Condensed tables (fallback only)

Use these when `review-method.md` cannot be found.

**Severity** — 🔴 Blocker: breaks at runtime or deploy, loses data, exposes a
secret. 🟠 Major: real defect on a plausible failure path. 🟡 Minor:
correctness-neutral but costly later. 🔵 Nit: style, only when no linter
covers it, max 3.

**Confidence** — Confirmed: proven from code read here. Probable: one named
unverified assumption. Speculative: needs facts outside the repo — becomes a
question, never a finding.

**Gates** — nothing below Probable is reported; a Blocker must be Confirmed;
every Major or Blocker states concrete inputs leading to a concrete wrong
outcome, or it is dropped.

**Never report** — anything a configured linter enforces, renames, library
suggestions, idiom swaps, unmeasured performance claims, pre-existing
defects, anything not tied to a changed line.
