---
name: roj-code-review-pr-fast
description: Quick chat-only review of the current Git feature branch diff, uncommitted changes included — no report file, no CodeTour, no commands beyond git. Use when the user says "quick review", "fast review", "sanity check my changes", "review this before I commit", or wants a short pass mid-work. For the full review with a written report, a change summary and a tour, use roj-code-review-pr instead.
license: MIT
allowed-tools: Read Grep Glob Bash(git diff *) Bash(git log *) Bash(git status *) Bash(git rev-parse *) Bash(git symbolic-ref *) Bash(git merge-base *) Bash(git show *)
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

1. **Base** — `git symbolic-ref refs/remotes/origin/HEAD`, else the first
   that exists of `origin/main`, `origin/master`, `origin/develop`, then
   local `main`, `master`, `develop`. Nothing resolves: ask once.
2. **Diff** — `git diff --stat <base>...HEAD`, then
   `git diff -U10 <base>...HEAD`. Three-dot always; two-dot pulls in
   unrelated merged work.
3. **Uncommitted** — `git status --porcelain`. When it lists changes, also
   run `git diff -U10 HEAD` (staged and unstaged edits) and read each
   untracked file it lists (`??`) as new code. This is the "before I
   commit" case, so it is reviewed, not skipped. Add
   `git diff --stat HEAD` and the untracked files to the header's file and
   line counts. On the base branch itself, the uncommitted diff is the
   whole review.
4. **Read** the whole file for any hunk whose surrounding context matters.
5. **Review** the changed hunks. Diff-local only — no caller search, no
   system pass, so the method's `graph-first.md` step does not apply. Say
   so at the end, so the user knows what was not checked.
6. **Verify** each candidate before printing it. Re-read its lines and check
   the claim itself, not only its consequence. A claim about what a library
   call returns or raises (on empty input, on error) is an assumption unless
   you are certain of it: make it the finding's named Probable assumption,
   or drop the finding. A wrong finding costs more trust than a missed one.
7. **Report** in chat.

Skip entirely: generated and vendored paths, renames with unchanged content.

## Output

Six lines of header and findings, nothing else:

```
<branch> vs <base> (+ uncommitted, when reviewed) · <n> files · +<a>/-<b> · lens: <one or none>
Verdict: <approve | approve with nits | changes requested | blocked>

🔴 `path:line` · Confirmed — <defect>. Fails when: <scenario>. Fix: <change>.
🟠 `path:line` · Probable — <defect>. Fails when: <scenario>. Fix: <change>.

Diff-local pass only — callers, config coupling and tests were not checked.
Run roj-code-review-pr for the full review.
```

Only 🔴 Blocker and 🟠 Major findings are printed; Minor and Nit are out of
scope for a fast pass. A missing test for a defect belongs in that defect's
Fix, not in a finding of its own. Order findings by severity, cap at five
and name the overflow count. Clean diff: say "Nothing to flag" and stop.
Never invent findings.

The lens in the header is the lens file's name without `.md`
(`lang-python`), or `none`.

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
