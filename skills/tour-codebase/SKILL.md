---
name: tour-codebase
description: Learn an unfamiliar repository by touring it. Use when the user says "onboard me to this repo", "tour this codebase", "teach me how this works", "help me understand this repo", "where do I start", "walk me through the architecture", or joins a project they have never worked on. Runs a discovery pass first, then leaves a chained series of CodeTour files in .tours/ that replay in the IDE at the reader's own pace. For documentation without tours use acquire-codebase-knowledge; for a single PR, branch, file or function use explain-logic.
---

# Tour Codebase

Turn a repository the reader does not know into a replayable course: four
chained CodeTour files, backed by the discovery documents that produced them.

The tours are the deliverable. Chat carries one plan checkpoint and a closing
handoff — not the walkthrough itself.

Rules that hold for the whole run:

- Every tour step anchors to a real `file:line` that exists at write time.
  A step that cannot be anchored is dropped, not approximated.
- Evidence comes from the repository. Never describe a framework's behaviour
  from memory when the code that implements it is readable.
- Comprehension, not review. No defects, no improvement suggestions, no
  refactoring advice unless the reader asks — that is `code-review-pr`.
- Steps are built from evidence gathered in phases 1 and 2. There is no
  second investigation pass while writing tours.
- Nothing outside `.tours/` and `docs/codebase/` is written, and no command
  beyond `git` and the delegated skills' own scripts runs without approval.

Load `references/tour-plan.md` at phase 2, `references/flow-tracing.md` when
phase 2 picks the core flow, and `references/step-writing.md` at phase 3.
None of them are needed before that.

## Phase 0 — Scope

Resolve the repository root: `git rev-parse --show-toplevel`. A directory
that is not a Git repository still works — say so once, and write tours with
no `ref` field.

Read the argument, if any:

| Argument | Effect |
| --- | --- |
| a named area — "tour the auth flow" | phase 2 traces that flow in tour 03 |
| "architecture only" | tours 02 and 03 only |
| "no docs" | phase 1 discovers in-session, writes nothing to `docs/codebase/` |
| none | full run |

Stop before phase 1 in two cases:

- **Monorepo.** Several workspaces (`workspaces` in `package.json`,
  `packages/`, `apps/`, a multi-module `pom.xml`, a Go workspace). Ask which
  one, once. Never tour all of them in one run.
- **Nothing to tour.** No source files outside generated output. Say so and
  stop.

## Phase 1 — Discovery

Delegate to `acquire-codebase-knowledge`. Resolve it from the first path that
exists:

1. `~/.claude/skills/acquire-codebase-knowledge/`
2. `~/.copilot/skills/acquire-codebase-knowledge/`
3. `<repo>/.github/skills/acquire-codebase-knowledge/`

Its output contract stands: `STACK.md`, `STRUCTURE.md`, `ARCHITECTURE.md`,
`CONVENTIONS.md`, `INTEGRATIONS.md`, `TESTING.md` and `CONCERNS.md` in
`docs/codebase/`.

- `docs/codebase/` already present — ask once, reuse or refresh. Reuse is the
  default; stale documents still beat a re-scan the reader did not ask for.
- Skill not installed — run its `scripts/scan.py` if the directory exists at
  all, otherwise discover inline: `README`, manifests, entry points,
  directory layout, test layout, CI configuration. State plainly that no
  documents were produced.
- `no docs` argument — discover inline regardless, write nothing.

`.tours/` is covered by the global Git ignore; `docs/codebase/` is not. When
documents were written and the repository does not already ignore them, print
this and let the reader decide:

```
echo 'docs/codebase/' >> .git/info/exclude
```

Never edit the repository's `.gitignore`, and never run that command unasked.

Carry into phase 2: the entry points, the layer boundaries, the conventions,
the test layout, and every `[ASK USER]` item discovery raised.

## Phase 2 — Plan the tours

Load `references/tour-plan.md`. Default progression:

| File | Persona | Covers | Steps |
| --- | --- | --- | --- |
| `01-orientation.tour` | new-joiner | entry points, how to run it, where things live | 6–10 |
| `02-architecture.tour` | architect | layers, boundaries, dependency direction, configuration | 8–12 |
| `03-core-flow.tour` | new-joiner | one real end-to-end path, in execution order | 10–15 |
| `04-conventions-and-tests.tour` | contributor | idioms, test layout, how to land a change | 6–10 |

Pick the flow for tour 03 with `references/flow-tracing.md`. When several
paths qualify, take the one the README and the tests exercise most — unless
the reader named one, which always wins.

Then print the plan and stop:

- the four titles, one line each on what the tour covers,
- the flow tour 03 will trace, named by its entry point (`file:line`),
- anything discovery could not answer that would change the plan.

One confirmation, then phase 3. This is the only interactive stop in the run.

## Phase 3 — Write the tours

Delegate to the `code-tour` skill, resolved the same way as phase 1. Write
`references/step-writing.md` rules into every step description.

Missing `code-tour`: write the JSON inline. An object with `$schema`,
`title`, `description`, `ref`, `isPrimary`, `nextTour` and `steps` of
`{file, line, description}` is all the CodeTour extension needs.

- Files land in `.tours/`, numbered so replay order is visible in the file
  list.
- Paths inside a `.tour` file always use forward slashes, on every host.
- `ref` is the current branch name, so replay resolves against a moving
  branch rather than a detached commit. No branch, no `ref`.

Validate after **all** tours are written, not one at a time — the validator
checks `nextTour` against the titles of the other `.tour` files, so an
early check reports a chain that is merely incomplete.

`code-tour` ships `scripts/validate_tour.py`. Resolve it from the installed
skill directory, since its own `SKILL.md` documents a
`~/.agents/skills/code-tour/scripts/` path this installer never creates. Run
it from the repository root — `file` values resolve relative to the working
directory:

```
python3 ~/.claude/skills/code-tour/scripts/validate_tour.py .tours/*.tour
```

Without the script: parse the JSON, confirm every `file` exists and every
`line` falls inside that file. A failing step is fixed or dropped, never
shipped. Warnings about opening and closing steps mean a content step is
missing — add it, do not ignore it.

## Phase 4 — Handoff

Short. In chat:

1. The tour files written, in replay order, with their step counts.
2. The flow tour 03 traced, one sentence.
3. Documents written, reused, or skipped.
4. Every `[ASK USER]` item from discovery, as numbered questions.
5. How to open them: VS Code, command palette, `CodeTour: Open Tour`.
   JetBrains has no CodeTour plugin — there the `.tour` files are read as
   JSON, and `docs/codebase/` is the better entry point.

Then offer, without doing any of it: zooming into a step with
`explain-logic`, annotating a file with `add-educational-comments`, or
re-running after the branch moves.

## Gotchas

**Generated output is never toured.** `dist/`, `build/`, `target/`, `out/`,
`node_modules/`, `__pycache__/`, `.next/`, vendored trees. A tour step
pointing at compiled code teaches the compiler, not the codebase.

**README architecture is intent, not fact.** Cross-check every claim against
the directory tree before a step repeats it.

**Line numbers drift.** Tours are a snapshot. `ref` pins the branch, and the
handoff says a re-run refreshes them — do not promise they survive a rebase.

**Framework magic needs its wiring shown.** Dependency injection, decorators,
route registration and code generation move control in ways no single file
shows. Anchor the step at the registration site, not at the annotation.

**Small repositories do not need four tours.** Under roughly 15 source files
with no cross-file flow, collapse to two — orientation plus flow, then
conventions — and say why in one line.
