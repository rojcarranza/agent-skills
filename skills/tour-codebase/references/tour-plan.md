# Tour plan

Loaded at phase 2. Decides what gets toured, in what order, and how the
tours chain.

## The progression

Four tours, each answering one question a new reader asks in this order.

### 01-orientation.tour — "what is this and how do I run it?"

Persona `new-joiner`. 6–10 steps.

Covers: the entry point that starts the thing, the command that builds it,
the command that runs the tests, the top-level directories and what each
owns, the configuration file a reader must know about on day one.

Does not cover: how the layers relate (tour 02), what happens inside a
request (tour 03), naming rules (tour 04).

Open at the repository's front door — `README` build command, `main`,
`install.py`, `package.json` scripts, the Dockerfile `ENTRYPOINT` — and close
by naming the flow tour 03 will trace.

### 02-architecture.tour — "how is it put together?"

Persona `architect`. 8–12 steps.

Covers: the layers that exist and the directory each lives in, the direction
dependencies point, the key abstractions (interfaces, base classes,
protocols) and one concrete implementation of each, where configuration
enters the process, where the process talks to the outside world.

Does not cover: line-level logic (tour 03), a full inventory of
implementations — one per abstraction is the budget.

Prefer the seam over the implementation. The interface, the registration
site, the factory, the dependency-injection wiring: those are where a reader
learns the shape.

### 03-core-flow.tour — "what actually happens when it runs?"

Persona `new-joiner`. 10–15 steps. Chosen with `flow-tracing.md`.

Covers: one path, end to end, in execution order — never file order. Entry
point, each transformation, each branch a reader must know about, the exit.

Does not cover: alternative paths, error handling that is not on the main
path, every helper the path touches. Mention a skipped branch in the step
that passes it; do not step into it.

This is the tour that teaches the codebase. Spend the step budget here.

### 04-conventions-and-tests.tour — "how do I add to it?"

Persona `contributor`. 6–10 steps.

Covers: naming and file layout shown at one real example each, the error
handling and logging idioms, how tests are organised and what a typical test
looks like, the command that runs them, the linter or formatter enforced,
and the one thing this repository does differently from its ecosystem's
default.

Does not cover: aspirational rules from `CONTRIBUTING.md` that the code does
not follow. When the two disagree, step at the code and say the document
disagrees.

## Opening and closing steps

Every tour opens and closes with a **content step** — a step with a
`description` and no `file`, so CodeTour shows prose rather than jumping into
a file.

- Opening: what this tour covers, what the reader knows at the end, roughly
  how long it is.
- Closing: what was just learned, and the title of the next tour.

Both count against the step budget. `code-tour`'s `validate_tour.py` warns
when a tour starts or ends on a file step, which is the same rule.

## Chaining

- Every tour sets `nextTour` to the **title** of the following tour (the
  CodeTour field takes a title, not a filename). The last tour omits it.
- `01-orientation` sets `isPrimary: true`. No other tour does.
- `ref` is the current branch name for every tour. No branch, no `ref`.
- Titles read as a course: `1. Orientation`, `2. Architecture`,
  `3. Core flow: <what it traces>`, `4. Conventions and tests`. The numeric
  prefix survives in the CodeTour sidebar, which sorts by title.
- `description` is one sentence: what the reader knows after replaying it.

Filenames are `.tours/01-orientation.tour`, `.tours/02-architecture.tour`,
`.tours/03-core-flow.tour`, `.tours/04-conventions-and-tests.tour`. A run
scoped to one area suffixes the flow tour: `03-core-flow-auth.tour`.

## Step budgets

The budgets in the table are limits, not quotas. A repository that runs out
of things worth saying at step 7 of tour 02 stops at step 7.

Over budget means the tour is trying to be two tours. Cut to the steps a
reader cannot understand the next tour without.

## No duplicate steps

A `file:line` appears in at most one tour. When two tours want the same line,
the earlier tour keeps the orientation-level mention and the later tour steps
one level deeper — a different line in the same file, not the same one twice.

## Collapse rule

Under roughly 15 source files, or no flow that crosses files:

- `01-orientation.tour` — orientation and the flow, 8–12 steps.
- `02-conventions-and-tests.tour` — 5–8 steps.

Say which rule fired, in one line, in the phase 2 plan.

## Re-runs

An existing `.tours/` with tours from a previous run: name them in the plan
and ask once — overwrite or write alongside with a suffix. Never silently
overwrite a tour someone may have hand-edited.
