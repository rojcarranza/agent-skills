---
name: roj-onboard-repo
description: Onboard a developer onto an unfamiliar repository with a written guide they open in the IDE or a browser - Mermaid diagrams of the architecture and one core flow, a code walkthrough anchored to path:line, a reading order, how to run and test it, and a page on reviewing a colleague's PR in this repo. Use when the user says "onboard me to this repo", "tour this codebase", "teach me how this works", "help me understand this repo", "where do I start", "walk me through the architecture", "draw the architecture and explain the code", or joins a project they have never worked on. Writes .onboarding/ as Markdown plus a single-page index.html, and stops on a failed read instead of guessing; CodeTour files only on request. For a single PR, branch, file or function use roj-explain-logic; for defects use roj-code-review-pr.
license: MIT
---

# Onboard Me To This Repo

Turn a repository the reader does not know into one guide they can read in
their IDE: what it is, how it is built (diagram), what happens when it runs
(diagram plus a step-by-step walkthrough of the real code), where to start
reading, and what to look at when a colleague's PR touches it.

The guide is the deliverable: Markdown files in `<ROOT>/.onboarding/` as the
checked source, and `.onboarding/index.html`, the same content as one
self-contained page with navigation, cards and rendered diagrams. Chat carries
a short handoff, not the walkthrough. CodeTour files are an extra, written only
when the reader asks.

## Rules for the whole run

This file is complete without any reference file. References add depth; none
is a dependency.

1. **Absolute paths only.** `ROOT` is `git rev-parse --show-toplevel`; with no
   Git repository it is the working directory, and the handoff says so. Every
   read and write is `<ROOT>/...`. Never a home-directory shortcut, never a
   path relative to this skill, never a search for the skill's folder. On
   Windows Git Bash, if a read fails on `/c/...`, retry once with
   `cygpath -m "$ROOT"` (`C:/...`), then once with the IDE's project-relative
   path.
2. **Read gate before any write.** First read `README*` or the main manifest
   by absolute path. If all three path forms fail, **stop and write nothing**.
   Print the failing path, the tool's message verbatim, and three checks:
   chat is in agent mode, the IDE project root is the repository root, the
   agent may read the workspace. No guides, no tours, no guesses.
3. **References are depth, not dependencies.** If a file in `references/`
   cannot be opened, continue from this file and add `Reference unavailable:
   <name>` to the handoff. Never search the disk for it.
4. **No delegation by path.** Do not locate or call another skill through its
   folder. `acquire-codebase-knowledge` and `code-tour` may be invoked **by
   name** when the host lists them, and `code-tour` only for the optional
   tour. An existing `docs/codebase/` or an overview doc such as
   `CODEBASE-OVERVIEW*.md` is a lead: read it, cross-check it against the
   code, cite it.
5. **Evidence.** Every claim cites a `path:line` that exists. What the code
   does not settle is marked `[?]` and collected in section 9. Never describe
   framework behaviour from memory when the code that implements it is
   readable. Comprehension, not review: no defects, no improvement advice;
   that is `roj-code-review-pr`.
6. **Writes only under `<ROOT>/.onboarding/`**, and `<ROOT>/.tours/` on
   request. Commands beyond file reads are `git`, the
   read-only `graphify` queries in `references/graph-first.md`, and `node`
   for the Mermaid parse check only with approval. Nothing else runs without
   approval.

Graph check, first and every run: look for `graphify-out/graph.json` as
soon as phase 0 has resolved the repository root, before any discovery. Present: load `references/graph-first.md`. Absent:
discover directly. Close the final chat message with a Graph line only when it
informs: `Graph: used` or `Graph: stale, skipped` when a graph exists, `Graph:
none found, searched directly` only when a large repository (hundreds of
source files) has none; otherwise print no Graph line.

## Phase 0 - Scope

Resolve `ROOT`, run the read gate (rule 2), then read the argument:

| Argument | Effect |
| --- | --- |
| a named flow - "the deploy flow" | phase 2 traces that flow |
| `architecture only` | README map and one flow; no `modules.md` |
| a workspace name | monorepo: scope to it |
| names tours - "leave CodeTour files" | write the tour after the guide (phase 5) |
| none | the full guide |

Stop in these cases:

- **Monorepo.** Several workspaces (`workspaces` in `package.json`,
  `packages/`, `apps/`, a multi-module `pom.xml`, a Go workspace) and no
  workspace named: ask which one, once, and write nothing before the answer.
  This is the only question the run asks before writing.
- **Nothing to tour.** No source files outside generated output. Say so.
- **Existing `.onboarding/`.** Ask once: refresh (overwrite our own files) or
  keep and stop.

`.onboarding/` is personal and stays out of Git. Check
`git check-ignore -q .onboarding/`; when it is not ignored, print this line
for the reader to run, and never run it or edit `.gitignore`:

```
echo '.onboarding/' >> .git/info/exclude
```

## Phase 1 - Recon into an evidence ledger

Keep a ledger of every file actually read; the guide's footer reports it.
Read, in this order, stopping when the map and one flow are evidenced:

1. `git ls-files`: top two levels, source-file counts per directory, ignoring
   generated output (`dist/`, `build/`, `target/`, `out/`, `node_modules/`,
   `__pycache__/`, `.next/`, vendored trees).
2. `README*`, manifests (`package.json`, `pyproject.toml`, `pom.xml`,
   `go.mod`, chart or script entry points), CI files, test layout.
3. Entry points per stack: `references/flow-tracing.md`.
4. Hotspots, for the PR page:
   `git log --since=1.year --name-only --format= | grep -v '^$' | sort | uniq -c | sort -rn | head -20`
5. With `graphify-out/`, `GRAPH_REPORT.md` first as the starting map.

README architecture is intent, not fact: cross-check every claim against the
tree before repeating it. Say what was not read. Load `references/mermaid.md`
before drawing.

## Phase 2 - Pick the flow (no checkpoint)

Rule order, first that fires wins: the flow the reader named, the README's own
example, the most-tested path, the deepest path. Infrastructure repos (Bash,
Helm, Bamboo, Docker) trace the install, deploy or pipeline path. Reject a
flow that never leaves one file. State the flow and the rule that chose it
in the guide and in the handoff; the reader redirects afterwards. Detail:
`references/flow-tracing.md`. Do not stop to ask.

## Phase 3 - Write the guide

Every file opens with the header line:

```
> Built from commit `<sha>` (<date>, branch `<branch>`). Every claim cites `path:line`.
```

(no Git: say `Built without Git history.`). In this order, so a partial run is
still useful. Skeletons and budgets: `references/templates.md`.

| File | Answers | Diagrams |
| --- | --- | --- |
| `README.md` | what is this, how is it built, where do I start | system map `flowchart TD`, core flow `sequenceDiagram` |
| `flows/01-<slug>.md` (1-3 total) | what happens, step by step, when X runs | one `sequenceDiagram`; `stateDiagram-v2` if real states exist |
| `reviewing-prs.md` | a colleague's PR touches X: what do I read and check | none required |
| `modules.md` | what does each module own and what depends on it | one `flowchart` per module group; `classDiagram` or `erDiagram` only for real types or tables |

`README.md` sections, in this order: 1. What this is. 2. System map. 3. Run
it, test it. 4. Reading order. 5. Core flow. 6. Data and state (one line when
the code has none). 7. Conventions and tests. 8. Glossary. 9. Open questions.
Footer: the evidence ledger (files read, count, commit).

- **System map:** the diagram plus five to eight bullets, each with a path.
- **Run it, test it:** a table of task, command and source. Commands are
  quoted from manifests, scripts and CI and are **not executed**.
- **Reading order:** at most ten entries, `path:line`, why now, what the
  reader can say afterwards.
- **Core flow:** the diagram, then a numbered walkthrough. Each step has a
  `path:line`, says what runs, why it is there and what breaks without it,
  and quotes at most five lines. Rules: `references/walkthrough-writing.md`.
- `architecture only` writes the README and one flow, no `modules.md`. A
  repository under about 15 source files with no cross-file flow gets the
  README and `reviewing-prs.md` only; say why in one line.

`reviewing-prs.md` is built from the same ledger, with no second
investigation: an **area map** (`glob | area | flow | depends on it | tests`),
the **hotspots** with commit counts, **silent seams** (invariants the code
does not enforce, found while tracing, such as behaviour that depends on
registration order), **questions to ask by area** and **how to run one test**
per area. Grounded in this repo's code, never generic.

Diagrams: the five types in `references/mermaid.md`, nothing else. At most 15
nodes and 25 edges each, at most eight diagrams per run, every label quoted.

**Then `index.html`**, built from the Markdown you just wrote, never from a
second look at the code (`references/html-page.md` has the skeleton, the
mapping and the check script). Inline CSS and JavaScript in one file, a sidebar
over README, flows, modules and reviewing PRs, cards, tables, readable light
and dark themes. Every `path:line` is a visible `<code class="ref">`. Diagrams
render from one pinned `cdn.jsdelivr.net/npm/mermaid@<x.y.z>` script (never
`latest`); each diagram's Mermaid source also sits in the page as a code block,
which stays visible with a one-line notice when the script fails to load or a
diagram fails to render. The page holds exactly the Markdown's diagrams,
anchors and headings, no more and no fewer.

## Phase 4 - Verify (mandatory, cheap)

Nothing unanchored ships. A failing item is repaired from the ledger or
dropped.

1. **Anchors.** Every `path:line` exists and is in range. Run the check script
   in `references/templates.md`; without it, confirm each cited file with
   `git ls-files` and its length with `wc -l`.
2. **Diagrams.** The checklist in `references/mermaid.md`: type from the
   subset, quoted labels, no reserved IDs, within the limits. The Node parse
   check is optional and needs approval.
3. **Truth.** Every diagram node is a real thing in the ledger and every edge
   is a call, import or message you read. Every flow step cites the line that
   does it.
4. **HTML matches Markdown.** `index.html` holds the same diagrams, `path:line`
   anchors and headings as the Markdown, loads Mermaid only from the pinned
   CDN URL, and keeps the source-and-notice fallback. Run the check script in
   `references/html-page.md`; without it, compare the diagram count and the
   anchors by hand.
5. No defect talk, no improvement advice, no tour files unless asked.

## Phase 5 - Handoff (15 lines or fewer)

In chat, no diagram (chat panels are not known to render Mermaid):

1. The path of `<ROOT>/.onboarding/index.html` and how to open it: in Lavish
   when `command -v lavish-axi` finds it, as `lavish-axi <path>` (print it,
   never run it); otherwise in a browser. The Markdown opens in the IDE
   preview: VS Code built in; JetBrains with the *Mermaid* plugin ticked under
   Settings, Plugins. Details: `references/mermaid.md`,
   `references/html-page.md`.
2. The flow chosen, in one sentence, and the rule that chose it.
3. The ignore line when `.onboarding/` is not ignored (printed, not run).
4. Open questions, as numbered `[?]` items.
5. Files read, and any `Reference unavailable: <name>`.
6. The next step for reviewing a colleague's PR: read
   `.onboarding/reviewing-prs.md`, then `/skill:roj-explain-logic PR <n>`
   (JetBrains) or `/roj-explain-logic PR <n>` (VS Code) to understand it with
   this map, then `roj-code-review-pr`, then `roj-review-pr-comment` for
   Bitbucket comments.
7. The Graph line, per the graph check above.
8. One offer, unless the reader already named tours: "Want a CodeTour of the
   core flow (VS Code only)?"

## CodeTour, on request only

No default tours. On a yes, or when the request named tours: one tour of 6-12
steps built from the anchors in `flows/01-*.md`, with no second investigation,
written to `<ROOT>/.tours/` and validated for real anchors. Invoke `code-tour`
by name if the host lists it; otherwise write the JSON inline. Rules:
`references/tours.md`.

## Gotchas

**Line numbers drift.** The header names the commit. Say a re-run refreshes
the guide; do not promise anchors survive a rebase.

**Framework magic needs its wiring shown.** Dependency injection, decorators,
route registration and code generation move control in ways no single file
shows. Anchor at the registration site, not at the annotation.

**Generated output is never walked through.** A step in compiled code teaches
the compiler, not the codebase.

**Evidence over memory.** A claim you cannot anchor is either dropped or
marked `[?]`, never approximated.
