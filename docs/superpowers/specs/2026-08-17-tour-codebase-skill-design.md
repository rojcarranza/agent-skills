# tour-codebase skill — design

Date: 2026-08-17

## Problem

Learning an unfamiliar repository currently takes two skills that do not
talk to each other. The community `acquire-codebase-knowledge` skill writes
seven documents into `docs/codebase/` and stops; the community `code-tour`
skill writes `.tour` files but only when someone has already decided what to
tour. Nothing decides which flows are worth walking through, and nothing
turns the discovery output into a replayable walkthrough.

The global `~/.claude/CLAUDE.md` claims `acquire-codebase-knowledge` ends by
writing a CodeTour. That instruction reaches Claude only — Copilot never
reads it — and the community skill itself knows nothing about tours, so the
behaviour is unenforced on both targets.

## Goal

A custom skill, `tour-codebase`, that takes a repository the user does not
know and leaves behind a chained series of CodeTour files they replay in the
IDE at their own pace, backed by the discovery documents that produced them.

Not a goal: teaching in chat. The chat output is a plan checkpoint and a
handoff summary. The tours are the deliverable.

## Shape

A conductor with its own tour-planning rules. Discovery is delegated to
`acquire-codebase-knowledge`; tour writing is delegated to `code-tour`. The
skill owns the two decisions those skills do not make — which tours to write,
and what a teaching step says — and falls back inline when either community
skill is absent (work VDI, proxy-blocked fetch).

Layout follows `code-review-pr`: a thin `SKILL.md` plus references loaded
per phase.

```
skills/tour-codebase/
  SKILL.md              # phases and run-wide rules, always loaded
  USAGE.md              # VS Code / JetBrains / Claude Code examples
  references/
    tour-plan.md        # tour progression, budgets, chaining, filenames
    flow-tracing.md     # find the real end-to-end path, per stack
    step-writing.md     # what a teaching step contains
```

The installer discovers custom skills by directory listing
(`install.py:682`, `install.py:797`), so no installer or test change is
required.

## Trigger contract

The skill claims the onboarding vocabulary; the community skill keeps the
documentation vocabulary. The description ends with pointers, the same way
`code-review-pr` points at `explain-logic`:

- Triggers: "onboard me to this repo", "tour this codebase", "teach me how
  this works", "help me understand this repo", "where do I start",
  "explain the architecture".
- Points elsewhere: documentation without tours →
  `acquire-codebase-knowledge`; a single PR, branch or file → `explain-logic`.

## Workflow

### Phase 0 — Scope

Resolve the repository root with `git rev-parse --show-toplevel`. A
non-git directory still works; the run says so, and tours carry no `ref`.

An argument narrows the run: a named area ("tour the auth flow"), a reduced
scope ("architecture only"), or `no docs`. A monorepo with several
workspaces gets one question — which workspace — never a tour of all of them.

### Phase 1 — Discovery

Delegate to `acquire-codebase-knowledge`, resolved from the first of
`~/.claude/skills/`, `~/.copilot/skills/`, `<repo>/.github/skills/`. Its
output contract stands: seven documents in `docs/codebase/`.

- `docs/codebase/` already present: ask once — reuse or refresh. Default
  reuse.
- Skill absent: run its `scripts/scan.py` if the directory exists, otherwise
  do inline discovery (README, manifests, entry points, directory layout)
  and state plainly that no documents were produced.

`docs/codebase/` is not covered by the global git ignore, unlike `.tours/`.
When the repository does not already ignore it, print the line and let the
user run it:

```
echo 'docs/codebase/' >> .git/info/exclude
```

Never edit the repository's `.gitignore`, and never run the command unasked.

### Phase 2 — Tour plan

Loads `references/tour-plan.md`. Default progression:

| File | Persona | Covers | Steps |
| --- | --- | --- | --- |
| `01-orientation.tour` | new-joiner | entry points, how to run it, where things live | 6–10 |
| `02-architecture.tour` | architect | layers, boundaries, dependency direction, config | 8–12 |
| `03-core-flow.tour` | new-joiner | one real end-to-end path in execution order | 10–15 |
| `04-conventions-and-tests.tour` | contributor | idioms, test layout, how to land a change | 6–10 |

Chaining: each tour sets `nextTour` to the following tour's title;
`01-orientation` sets `isPrimary: true`; `ref` is the current branch name so
replay resolves line numbers against a moving branch rather than a detached
commit.

The plan is presented in chat before anything is written: the tour titles,
one line each, and which flow tour 03 will trace. One confirmation, then
Phase 3. This is the only interactive stop in the run.

Collapse rule: a repository under roughly 15 source files with no cross-file
flow gets two tours (orientation plus flow, then conventions), with the
reason stated in one line.

### Phase 3 — Write the tours

Steps are built from evidence already gathered in Phases 1 and 2. No second
investigation pass — the same rule `explain-logic` carries.

Delegate to `code-tour`. When it is absent, write the JSON inline: an object
with `$schema`, `title`, `description`, `ref`, `isPrimary`, `nextTour` and
`steps` of `{file, line, description}` is enough for the CodeTour extension.

Files land in `.tours/`, numbered so replay order is visible in the file
list. Paths inside a `.tour` file always use forward slashes, including on
Windows.

Validation: `code-tour` ships `scripts/validate_tour.py`. Resolve it from
the installed skill directory — upstream's `SKILL.md` documents a
`~/.agents/skills/code-tour/scripts/` path this installer never creates.
Without the script: parse the JSON, and confirm every `file` exists and every
`line` falls inside that file.

### Phase 4 — Handoff

Short chat summary: tour files written, the flow tour 03 traced, documents
written or skipped, every `[ASK USER]` item discovery surfaced, and how to
open the tours. Offer `add-educational-comments` as a follow-up; never run it
unasked.

## References

`tour-plan.md` — the progression table, the collapse rule,
`nextTour`/`isPrimary`/`ref` wiring, filename convention, and what each tour
must not cover so steps are not duplicated across tours.

`flow-tracing.md` — entry-point signals per stack and how to walk one path:
Java/Spring (`@SpringBootApplication`, controller → service → repository,
Maven modules), Python (`pyproject` entry points, Click/argparse,
FastAPI/Flask route → handler), Go (`main`, mux routes, worker loops),
Node/TypeScript (`bin` and scripts, express/nest routes), Bash (installer
entry, call order), Bamboo (plan → stage → job → task), Docker/Helm/
Kubernetes (image entrypoint, values → template → workload). When several
flows qualify, take the one the README and the tests exercise most, unless
the user named one.

`step-writing.md` — step anatomy (what runs here, why it exists, what breaks
without it), quotes of at most five lines, one concept per step, idioms
defined rather than named, no improvement suggestions, and a closing step per
tour that points at the next one. Anti-patterns table.

## Edge cases

- Not a git repository — run continues, no `ref`, no `.git/info/exclude` hint.
- Empty or source-free repository — say so and stop; there is nothing to tour.
- Monorepo — one question, one workspace.
- Generated output (`dist/`, `build/`, `target/`, `node_modules/`,
  `__pycache__/`, `.next/`) is never toured.
- Community skills absent — fallbacks in Phases 1 and 3.
- Pre-existing `docs/codebase/` — reuse by default.
- Line drift after the tours are written — `ref` pins the branch; the handoff
  says a re-run refreshes them.

## Verification

- `cd agent-skills && python3 -m unittest test_install -v` passes unchanged;
  the skill list is dynamic, so a new directory needs no test edit.
- `python3 install.py --status` lists `tour-codebase`.
- `python3 install.py --target claude --dry-run` shows the new symlink.
- One real run against a live repository, with every produced `.tour` file
  passing `validate_tour.py`.

## Documentation to update

- `agent-skills/README.md` — layout list, and the paragraph naming the skills
  that end a run with a CodeTour.
- `agent-skills/README.md` usage list — link `skills/tour-codebase/USAGE.md`.
- `agent-skills/docs/community-skills.md` — note that
  `acquire-codebase-knowledge` is now called by `tour-codebase`, and that
  `tour-codebase` owns the onboarding triggers.
- `~/.claude/CLAUDE.md` (via `claude/CLAUDE.md` in this repo) — add
  `tour-codebase` to the walkthrough skills that leave a tour behind.
