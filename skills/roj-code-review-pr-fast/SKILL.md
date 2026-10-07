---
name: roj-code-review-pr-fast
description: Quick chat-only review of the current Git feature branch diff — no report file, no CodeTour, no commands beyond git. Use when the user says "quick review", "fast review", "sanity check my changes", "review this before I commit", or wants a short pass mid-work. For the full review with a written report, a change summary and a tour, use roj-code-review-pr instead.
license: MIT
allowed-tools: Read Grep Glob Bash(git diff:*) Bash(git log:*) Bash(git status:*) Bash(git rev-parse:*) Bash(git symbolic-ref:*) Bash(git merge-base:*) Bash(git show:*)
---

# Code Review PR — fast

A short pass over the branch diff. Chat output only. Nothing is written to
disk and no tool other than `git` runs.

Use `roj-code-review-pr` instead when the change is going into a PR, when the
user wants to understand the change, or when infrastructure and CI/CD are
involved.

## Load the method

Read `references/review-method.md` from this skill's folder — a copy of
`roj-code-review-pr`'s method, so this skill runs on its own. If it cannot
be read, use the condensed tables at the bottom of this file and say in one
line that the full method was not found.

Load at most one technology lens (`lang-*.md`, `platform-*.md`) from the
same `references/` directory, and only when the diff is dominated by one
stack — pick it with the method's *Lens selection* table. A pair the method
says travels together (Helm + Kubernetes, Bamboo + Bash) counts as one. When
the diff spans several stacks, load none and rely on the method plus
`cross-cutting.md`.

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
Run roj-code-review-pr for the full review.
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
