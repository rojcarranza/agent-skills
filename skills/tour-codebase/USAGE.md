# tour-codebase — usage

Turns a repository you have never worked on into a replayable course: four
chained CodeTour files in `.tours/`, backed by the discovery documents in
`docs/codebase/` that produced them.

The tours are the output. Chat carries one plan checkpoint and a closing
summary — the walkthrough itself lives in the IDE, replayed at your pace.

## When to use

- Joining a project, inheriting a service, or reviewing a repository you did
  not write.
- Coming back to something you have not touched in months.
- Handing a repository to someone else and wanting the walkthrough to outlive
  the conversation.

Not for a single PR, branch, file or function — that is `explain-logic`. Not
for documentation without tours — that is `acquire-codebase-knowledge`, which
this skill calls anyway. Not for finding defects — that is `code-review-pr`.

## Invoking

Plain English works everywhere — the skill triggers from its description:

    onboard me to this repo
    tour this codebase
    teach me how this project works
    where do I start in this repo
    tour this codebase, the auth flow      # names the flow tour 03 traces
    tour this codebase, architecture only  # tours 02 and 03 only
    tour this codebase, no docs            # nothing written to docs/codebase/

Explicit invocation differs per agent:

| Agent | Command |
| --- | --- |
| Claude Code (terminal, VS Code, JetBrains) | `/tour-codebase`, or plain English |
| Copilot, VS Code | `/tour-codebase` |
| Copilot, JetBrains | `/skill:tour-codebase` |

All three are personal scope once installed, so they reach every project with
no per-repository seeding.

## What it does

1. Resolves the repository root, and asks which workspace when the repository
   is a monorepo.
2. Delegates discovery to `acquire-codebase-knowledge`, which writes the seven
   documents in `docs/codebase/`. An existing `docs/codebase/` is reused
   unless you ask for a refresh; a missing skill falls back to its `scan.py`,
   then to inline discovery.
3. Picks the one flow worth tracing — the one you named, else the one the
   README exercises, else the one the tests cover hardest.
4. **Prints the plan and stops.** Four titles, one line each, and the entry
   point of the flow it will trace. This is the only interactive stop.
5. Writes the tours through `code-tour` (inline JSON when that skill is
   absent), then validates every step's `file:line` before reporting.

## Output

`.tours/`, in replay order:

| File | Persona | Answers |
| --- | --- | --- |
| `01-orientation.tour` | new-joiner | what is this, how do I run it, where does everything live |
| `02-architecture.tour` | architect | layers, boundaries, dependency direction, configuration |
| `03-core-flow.tour` | new-joiner | what actually happens when it runs |
| `04-conventions-and-tests.tour` | contributor | idioms, test layout, how to land a change |

Each tour links to the next through CodeTour's `nextTour` field, so replaying
`01` walks you through all four. `ref` is set to the current branch.

A small repository (under roughly 15 source files, no cross-file flow)
collapses to two tours, with the reason stated.

`.tours/` is in the global Git ignore, so tours stay local. `docs/codebase/`
is **not** — when documents are written, the run prints

    echo 'docs/codebase/' >> .git/info/exclude

for you to run if you would rather they stayed out of `git status`. The skill
never edits a repository's `.gitignore`.

## Opening the tours

- **VS Code** — install `vsls-contrib.codetour` (already in this repo's
  [`vscode/extensions.txt`](../../../vscode/extensions.txt)), then command
  palette, `CodeTour: Open Tour`. The CodeTour sidebar lists all four.
- **JetBrains** — no CodeTour plugin exists. Read the `.tour` files as JSON,
  or use `docs/codebase/` as the entry point and jump to the `file:line`
  values by hand.

## Customising

The rules live in `references/` as prose checklists — edit them directly:

- `tour-plan.md` — which tours exist, what each covers, step budgets,
  chaining, the collapse rule.
- `flow-tracing.md` — how the core flow is picked, and entry-point signals
  per stack (Java/Spring, Python, Go, Node/TypeScript, Bash, Bamboo,
  Docker/Kubernetes/Helm).
- `step-writing.md` — what a step says, quoting limits, anti-patterns.

Want a fifth tour, a different persona, or a different flow-picking rule?
`tour-plan.md` is where that change belongs.

## Re-running

Tours are a snapshot: line numbers drift as the branch moves. Re-run to
refresh. An existing `.tours/` is never silently overwritten — the run names
what is there and asks once.

## Install

From the repo root:

    python3 agent-skills/install.py --target claude    # mac / Claude Code
    python3 agent-skills/install.py --target copilot   # work / GitHub Copilot
    python3 agent-skills/install.py --target both

On the Windows VDI use `python` rather than `python3`. Copilot installs to
`~/.copilot/skills/` (under `%USERPROFILE%` on Windows), which is personal
scope: the skill reaches every project, in both VS Code and JetBrains
agent-mode chat, with no `.github/skills` seeding.

Copilot receives copies, not symlinks — re-run the installer after editing any
reference file. `--status` shows what is installed where.

This skill delegates to two community skills the installer already fetches by
default, `acquire-codebase-knowledge` and `code-tour`. It runs without them,
with the fallbacks described above, but installing them is what makes the
output good — do not use `--skills-only` on a machine where you plan to run
this skill, unless a proxy leaves you no choice.
