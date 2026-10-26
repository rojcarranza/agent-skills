---
name: roj-explain-logic
description: Explain the logic of code the user is reading — a pull request, a feature branch diff, a file, or a function — as a guided, step-by-step walkthrough. For a PR or branch it writes a brief, with a flow diagram and an HTML page, under .pr-review/. Use when the user says "explain this PR", "brief me on this PR", "explain this PR and draw the flow", "walk me through this branch", "explain this function", "what does this method do", "who calls this", "what does this code do", "help me understand this logic", "why does this work", "trace this flow", or pastes/points at code they are trying to understand, even without the word "explain". Also for "explain and review" or "explain this and flag anything risky", which adds a review pass after the walkthrough. Covers Java, Python, Go, shell scripts, and Atlassian Bamboo API/specs code. For the user's own branch explained for their PR use roj-explain-feature-changes; for onboarding to a whole repo use roj-onboard-repo; for finding defects use roj-code-review-pr.
license: MIT
---

# Explain Logic

Goal: comprehension, not review. Explain what IS, why it exists, how it flows.
No improvement suggestions unless asked.

## Step 1 — Scope

Priority order:

1. **PR / feature branch**: pull the real diff first — never explain from memory.
   - Branch: resolve `<base>` with `references/base-resolution.md` - the
     user's named branch, else the nearest candidate; nothing resolves, ask.
     Then `git diff --stat <base>...HEAD` and `git diff <base>...HEAD`.
   - Bitbucket Data Center PR (an id or URL): fetch its head without a
     checkout and read from it, as `references/forge-bitbucket-dc.md` says.
   - GitHub PR: the GitHub MCP server's pull-request tools if one is
     connected, else `gh pr diff <number>`.
   - A PR or branch is explained as a **brief**, written to
     `.pr-review/pr-<n>/brief.md` and `brief.html`, not as a long chat
     answer. Load `references/pr-brief.md` now: where the files go, the read
     gate, the template, the caps and the check scripts (it uses
     `references/mermaid.md` and `references/html-page.md`). If it cannot be
     opened, explain in chat as for a file and print `Reference unavailable:
     pr-brief.md`.
2. **File/function**: read the whole file, not just the snippet.
3. **Ambiguous**: ask ONE question ("Which branch/PR, or which file?"), then proceed.

## Step 2 — Context before explaining

A diff alone lies. Always:

- Read the full function/class around each changed hunk.
- Trace callers and callees. When `references/graph-first.md` applies, start
  with `graphify explain` / `graphify path` and read what they name;
  otherwise grep/IDE search on names.
- Check tests touching the changed code — tests document intent.
- Read the PR description and commit messages.
- Note config/CI in the diff (Bamboo specs, pipelines, Dockerfiles, Helm) —
  these change runtime behavior, not just code.

## Step 3 — Structure: Concept → Code → Why

Never jump straight to line-by-line. For a PR or branch these steps fill the
brief's sections 1, 2 and 5; chat carries only the summary in
`references/pr-brief.md`.

1. **Big picture** — 2-4 sentences: problem solved, overall approach.
   One-line role per changed file.
2. **Flow** — walk the execution path in run order, not file-by-file.
   Each step: inputs → transformation → outputs. In chat (file and function
   targets; a PR or branch keeps its diagram in the brief) a Mermaid diagram
   when 3+ moving parts — `sequenceDiagram` for a call path, `flowchart` for
   structure; never ASCII art. Load `references/mermaid.md` before drawing. Quote the actual lines, then explain in plain language.
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
- Pitch to the user's level: skip syntax basics they already use, DO define
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
a yes). `context-map` is an optional companion — if it is present, use it
for scope mapping.

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
"flag anything risky"). Run a SECOND phase after the full explanation, under
its own header - never mix review into the explanation.

The review is the shared review method, not a scale of its own: read
`references/review-method.md` and `references/cross-cutting.md`, and the
lenses (`lang-*.md`, `platform-*.md`) the method's *Lens selection* picks for
the code in scope. Apply its severity (Blocker, Major, Minor, Nit),
confidence (Confirmed, Probable; Speculative becomes a question), its
failure-scenario rule, its never-report list and its verification pass, and
print findings in its format (`path:line`, severity, confidence, "Fails when",
fix). For a PR the brief is written first; the review prints in chat after its
summary and is never written into the brief. The callers and tests you already traced for the explanation are the
system pass. Run no command beyond `git`. Solid code: say so plainly - never
invent findings.

## Rules

- Graph check, first and every run: look for `graphify-out/graph.json` at the
  repository root before tracing callers. Present: follow
  `references/graph-first.md`. Absent: search directly. Close the answer with
  a Graph line only when it informs: `Graph: used` or `Graph: stale, skipped`
  when a graph exists, `Graph: none found, searched directly` only when a
  large repository (hundreds of source files) has none; otherwise print no
  Graph line. The read-only `graphify` queries in
  that file are allowed alongside `git`.
- Never invent behavior — if you can't see the code a call resolves to,
  say so and go read it.
- Prefer "this line does X because Y" over "this improves Z".
- No refactoring advice unless explicitly requested.
- Diff touches CI/CD or infra: always end with "runtime impact" — what
  changes about how/when things execute.
- PR or branch target: write only under `<ROOT>/.pr-review/`; print the
  `.git/info/exclude` line when it is not ignored, never run it, never edit
  `.gitignore`.
