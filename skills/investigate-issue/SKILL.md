---
name: investigate-issue
description: Investigate a reported bug or build failure, validate the root cause in the checked-out repo, and write a step-by-step solution report as a Markdown file. Use when the user says "investigate this issue", "validate this bug", "why did this pipeline/build fail", "find the root cause", or drops a problem/context .md file containing an error, stack trace, or build log. Covers Atlassian Bamboo pipelines, build plans and agents, plus Java, Python, Bash, Go, Dockerfiles, and Kubernetes manifests. Do NOT use for pure comprehension requests ("explain this code", "walk me through") — that is explain-logic's job.
---

# Investigate Issue

Take a problem + context `.md` file, investigate the repo, validate the
root cause, and write `<problem-name>-investigation.md` next to the input
file with evidence and steps to solve. Apply a fix only when it is a repo
code change and the user approves.

Rules that hold for the whole run:

- Evidence is the problem `.md` (pasted logs/errors) plus the local repo.
  There is no live Bamboo access — never invent build state.
- No fix is proposed before a root cause survives validation.
- Root cause is labeled **Confirmed** (reproduced locally) or
  **Probable** (evidence-only) — never presented as certain when it is not.
- Quote error strings, commands, and code verbatim.
- Skipping a phase must be justified in the report.

Helper skills are optional: every chain step below has an inline
fallback, so the workflow succeeds with no helpers installed.

## Phase 1 — Intake

Read the problem `.md` the user points at (or ask for it — one question).
Extract whatever is present:

- Exact error lines, verbatim (the shortest decisive lines).
- Failing plan key / stage / job / task, agent name, build number.
- Language/runtime facts (JDK version in log header, Python version, …).

Classify the issue — multiple classes allowed:

| Class | Typical signal |
|---|---|
| `repo-code` (java, python, go) | compile error, test failure, stack trace into repo code |
| `script` (bash) | script task fails, exit code, `command not found` |
| `dockerfile/image` | `docker build` fails, image task errors |
| `k8s-manifest` | apply/rollout errors, CrashLoopBackOff, probe failures |
| `bamboo-plan` | plan spec errors, task/stage config, artifacts, variables |
| `bamboo-agent` | works locally but not on agent, capability/env/tool missing |

If the `.md` has no actual error text (only a description), ask once for
the error/log, then proceed with what exists.

## Phase 2 — Context

Locate the code behind the failure:

- If a `context-map` skill is available, use it to map files relevant to
  the error. Otherwise search the repo directly for: quoted error
  strings, task/script names from the log, file paths in the stack trace.
- Read the full function/script/manifest around each suspect line, not
  just the line itself.
- If the failing logic is hard to follow, chain to the `explain-logic`
  skill for a trace; otherwise trace it inline (callers, callees, data
  flow into the failing point).
- Note repo facts the hypotheses will need: build tool and version
  pins, base images in Dockerfiles, agent OS hints (shebangs, image
  tags, capability files).

## Phase 3 — Hypothesize

If a systematic debugging skill is available
(`debugging-and-error-recovery`, or `systematic-debugging` on Claude),
invoke it now and let its discipline govern phases 3–4. Inline fallback:

- Write a ranked hypothesis list. Each entry: cause, evidence for,
  evidence against.
- Ground Bamboo-class hypotheses in `references/bamboo-failures.md`;
  ground docker/k8s/language classes in `references/domain-checks.md`.
  Load only the reference matching the phase-1 class.
- Rejected hypotheses are kept — the report lists them with the
  disqualifying evidence.

## Phase 4 — Validate

Test the top hypothesis first, one variable at a time.

**Reproduce when possible.** Run the failing thing locally with the
commands in `references/domain-checks.md` (e.g. run the script /
`shellcheck`, `pytest` the failing test, the failing Maven/Gradle goal,
`go build` / `go vet`, `docker build`, `kubectl apply --dry-run=client`).
A run that reproduces the pasted error = **Confirmed**.

**Static evidence otherwise.** Agent-side, environment, and Bamboo
configuration causes usually cannot be reproduced locally. Walk the
matching checklist in `references/bamboo-failures.md` (capabilities,
missing tools/env vars, working-dir assumptions, artifact/checkout
config, exit-code swallowing, JDK mismatch, …). Consistent evidence with
no surviving competing hypothesis = **Probable**.

If the top hypothesis dies, move to the next — do not stretch evidence
to save it.

## Phase 5 — Report

Write the report next to the input file: input `LISA-123.md` produces
`LISA-123-investigation.md` in the same directory. Follow
`references/report-template.md`. Sections, in order:

1. **Summary** — 3 lines max: what broke, root cause, fix in one phrase.
2. **Environment** — plan/stage/agent/language facts from intake.
3. **Evidence** — quoted error lines + `file:line` findings.
4. **Hypotheses considered** — rejected ones, one line each.
5. **Root cause** — Confirmed or Probable, with the proof.
6. **Solution** — one of:
   - *Code fix*: the concrete change — diff or exact edit instructions.
   - *Manual fix*: numbered steps with exact locations (Bamboo admin
     screen path, agent host command, capability name, env var) — for
     anything outside the repo.
7. **Verification** — how to confirm the fix after applying: command to
   run locally, or which build to rerun and what output to expect.

When the root cause is on the agent host, name the detected OS/distro in
the Solution and note that a matching awesome-copilot
`<distro>-linux-triage` skill exists for deeper host diagnosis.

## Phase 6 — Solve

- **Code/script fix in the repo**: ask the user whether to apply it. On
  yes — apply the change, rerun the phase-4 repro, and record the result
  in the report's Verification section (including a failed rerun; never
  claim success without the passing output).
- **Manual fix** (Bamboo admin, agent host, capabilities, env): the
  numbered instructions in the report are the deliverable. Never attempt
  to apply these.

## Phase 7 — Tour

Write a replayable CodeTour walking the failure path, so the next person
hitting this bug can step through the evidence instead of rereading prose.

- **Path**: `.tours/rca-<problem-name>.tour` — same stem as the report, so
  `LISA-123.md` gives `LISA-123-investigation.md` and `.tours/rca-LISA-123.tour`.
- **Persona**: `bug-fixer`.
- **Steps**: the report's Evidence section, in failure order — one step per
  `file:line` finding, ending at the fix location. Each description says what
  this line contributes to the failure. Never re-investigate to build the tour.
- **How**: chain to the `code-tour` skill. Missing? Write the tour inline —
  a JSON object with `$schema`, `title`, `description` and `steps` of
  `{file, line, description}` is enough for CodeTour to open it.
- **Validate**: `code-tour` ships `scripts/validate_tour.py`. Resolve it from
  the code-tour skill directory that is actually installed
  (`~/.claude/skills/code-tour/`, or `~/.copilot/skills/code-tour/`) — its
  SKILL.md documents a `~/.agents/...` path that does not exist here.

Skip the tour only when ALL hold: one file, no cross-file flow, under ~3
steps. Then say so in one line with the reason — "No tour — one-line fix in a
single script." The user asking for a tour overrides a skip; "no tour"
overrides the default. A root cause outside the repo (Bamboo config, agent
host) has no code path to walk: skip it and say so.

`.tours/` is in the global git ignore, so tours stay local — never add them
to the repo's `.gitignore` or commit them unless asked.
