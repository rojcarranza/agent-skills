---
name: roj-explain-logic
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
| acquire-codebase-knowledge | new repo or repo-wide question: build the codebase map first |
| code-tour | only after the user accepts the offer (see Tour output below) |
| caveman | user asks terse/brief/save tokens: apply it to the output |

Chain: acquire-codebase-knowledge → this skill → code-tour (last hop only on
a yes). `context-map`, `architecture-blueprint-generator` and
`add-educational-comments` are cherry-picks that are normally not installed —
if one is present, use it for scope mapping, architecture refresh and
post-walkthrough commenting respectively.

## Tour output (ask first)

**Off by default.** After the walkthrough, offer in one line — "Want a
replayable CodeTour of this?" — and build it only on a yes. "Make a tour" up
front skips the offer; "no tour" suppresses it. Skip the offer too when the
walkthrough covered one file with no cross-file flow in under ~3 steps.

- **Path**: `.tours/explain-<branch-or-file>.tour` in the repo being
  explained.

- **Persona**: `pr-reviewer` for a PR/branch, `new-joiner` for a
  file/function.

- **Steps**: the Flow section from step 3, in execution order. Reuse
  `file:line` already cited; never re-investigate.

On a yes, chain to `code-tour`; if it is not installed write the JSON inline
(`$schema`, `title`, `description`, `steps` of `{file, line, description}`).
Validate with its `scripts/validate_tour.py` from whichever installed dir
exists — resolve `~` to an absolute path (cmd does not expand it) and try
`python`, then `python3`; skip validation rather than failing the run.
`.tours/` is in the global git ignore: never commit a tour or edit
`.gitignore`.

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
