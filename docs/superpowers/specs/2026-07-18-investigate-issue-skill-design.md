# Investigate-Issue Skill — Design

Date: 2026-07-18
Status: Approved

## Problem

Recurring workflow at work: a bug or build failure arrives as a problem +
context `.md` file (pasted Bamboo build logs, error output, description).
The user investigates the checked-out repo manually, validates the cause,
and writes up fix steps. No existing skill covers this end to end:

- `explain-logic` is comprehension-only, explicitly no fixes.
- `superpowers:systematic-debugging` is method-only, Claude-only
  (plugin), and produces no report artifact.
- awesome-copilot has OS/cloud triage skills but nothing for
  "problem .md in, validated root cause + fix steps .md out", and nothing
  Bamboo-aware.

Goal: one cross-platform skill (Copilot on work VDI, Claude Code at home)
that takes a problem `.md`, investigates the repo, validates the root
cause, and writes an investigation report with steps to solve — applying
the fix only when it is a repo code change and the user says yes.

## Scope

General-purpose issue investigator. Domains, in priority order of the
user's real workload:

- Bamboo pipeline / build plan failures (plan specs, stages, scripts)
- Bamboo agent / environment issues
- Python, Bash, Java, Go code and build logic
- Dockerfiles / images
- Kubernetes manifests (and Helm charts when present)

Bamboo is one domain among several, not the frame.

## Decisions made

- **Evidence**: problem `.md` + local repo only. No live Bamboo REST/CLI
  access — build logs and errors arrive pasted in the `.md`.
- **Validation**: reproduce locally when possible (run the failing
  script/test/build step); fall back to static evidence when repro is
  impossible (agent-side/env issues). Root cause is marked **Confirmed**
  (reproduced) or **Probable** (evidence-only) — never silently guessed.
- **Output**: `<problem-name>-investigation.md` written next to the input
  `.md`. Zero config, works on any repo/VDI.
- **Fix mode**: report first, then offer. Repo code/script fixes are
  offered for application (apply + rerun repro to verify). Non-code fixes
  (Bamboo admin UI, agent host, capabilities, env) become numbered manual
  instructions in the report — never auto-applied.
- **Chaining**: the skill chains to proven third-party skills when
  installed, with inline fallback when absent — no hard dependency, so
  both platforms degrade gracefully.
- **Agent host OS**: not assumed. Detected from repo evidence (Dockerfile
  base images, capability files, shebangs/paths). When root cause is
  host-level, the report names the distro and gives manual host
  instructions (and mentions the matching awesome-copilot `*-linux-triage`
  skill as an optional install).

## Third-party skill research (2026-07-18)

Chained (proven, portable):

| Skill | Source | Role |
|---|---|---|
| `debugging-and-error-recovery` | [addyosmani/agent-skills](https://github.com/addyosmani/agent-skills) | Root-cause discipline (Stop → Preserve → Diagnose → Fix → Guard → Resume). Fully platform-agnostic. New install.py upstream, both targets. |
| `systematic-debugging` | [obra/superpowers](https://github.com/obra/superpowers) | Same role on Claude side, already installed via plugin. Either satisfies the discipline step. |
| `context-map` | awesome-copilot (installed) | Map files relevant to the error before hypothesizing. |
| `explain-logic` | local (installed) | Trace unclear logic/flow during investigation. |

Rejected: awesome-copilot `diagnose` (audits AI workflows, not code),
anthropics/skills official repo (no debugging skill), AWS/Azure
investigation skills (cloud-specific), preinstalling a `*-linux-triage`
distro skill (agent distro unknown; detect instead).

## Layout

```
agent-skills/skills/investigate-issue/
├── SKILL.md                      # triggers + phased workflow
└── references/
    ├── bamboo-failures.md        # Bamboo pipeline + agent failure catalog
    ├── domain-checks.md          # Docker, k8s, per-language validation commands
    └── report-template.md        # investigation .md template
```

`install.py` discovers `skills/` automatically — the new skill needs no
installer change. One installer addition for the chained upstream:

- `ADDY_REPO_URL = "https://github.com/addyosmani/agent-skills.git"`,
  `ADDY_SKILLS = ["debugging-and-error-recovery"]` — cached, sparse-cloned,
  and installed exactly like the existing caveman upstream
  (`update_repo_cache` helper, own cache dir under
  `~/.agent-skills-cache/`, ZIP fallback URL).

## Trigger (SKILL.md description)

Fires on: "investigate this issue", "validate this bug", "why did this
pipeline/build fail", user drops a problem/context `.md` containing an
error or build log. Covers Bamboo pipelines and agents, build plans,
Java, Python, Bash, Go, Dockerfiles, Kubernetes.

Must not steal `explain-logic` triggers: pure comprehension requests
("explain", "walk me through") stay with `explain-logic`.

## Workflow

Six phases, in order. Skipping a phase must be justified in the report.

### 1. Intake

Read the problem `.md`. Extract: exact error lines (verbatim), failing
build stage/job, agent name, plan key — whatever is present. Classify the
issue: `repo-code (java|python|go)` | `script (bash)` |
`dockerfile/image` | `k8s-manifest` | `bamboo-plan/pipeline` |
`bamboo-agent/env`. Multiple classes allowed. If the `.md` lacks the
actual error text, ask for it once before proceeding.

### 2. Context

Locate the relevant code:

- If `context-map` is installed, use it to map files relevant to the
  error; otherwise search the repo directly (error strings, task names,
  script paths from the log).
- If the failing logic is unclear, chain to `explain-logic` for a trace;
  otherwise read the surrounding code inline.

### 3. Hypothesize

Ranked hypothesis list, each with evidence for and against, grounded in
phase-2 findings plus the matching reference catalog
(`bamboo-failures.md` for Bamboo classes, `domain-checks.md` otherwise).
Discipline rule: no fix proposed before a root cause survives phase 4.
If `debugging-and-error-recovery` (or `superpowers:systematic-debugging`)
is installed, invoke it here and let it govern phases 3–4; the inline
rules below are the fallback.

### 4. Validate

Top hypothesis first, one variable at a time:

- **Repro when possible**: run the failing thing locally with commands
  from `domain-checks.md` — e.g. `bash -n` / `shellcheck` / run the
  script, `pytest`, `mvn -q compile` or the failing Maven/Gradle goal,
  `go build` / `go vet`, `docker build`, `kubectl apply --dry-run=client`,
  `helm template`. A hypothesis that reproduces the pasted error =
  **Confirmed**.
- **Static otherwise** (agent-side, env, Bamboo config): check the
  catalog's evidence list (capability mismatch, missing tool/env var on
  agent, working-dir assumptions, checkout/artifact config, exit-code
  swallowing, JDK mismatch, …). Consistent evidence with no surviving
  competitor = **Probable**.

Rejected hypotheses are kept (one line each) for the report.

### 5. Report

Write `<problem-name>-investigation.md` next to the input file, from
`report-template.md`:

1. **Summary** — 3 lines max: what broke, root cause, fix in one phrase.
2. **Environment** — plan/stage/agent/language facts from the `.md`.
3. **Evidence** — quoted error lines + `file:line` findings.
4. **Hypotheses considered** — rejected ones, one line each, with the
   disqualifying evidence.
5. **Root cause** — Confirmed or Probable, with the proof.
6. **Solution** — one of:
   - *Code fix*: concrete change (diff or exact edit instructions).
   - *Manual fix*: numbered steps — where to go (Bamboo admin screen,
     agent host), exact commands/settings to change.
7. **Verification** — how to confirm it is fixed after applying
   (command to run, or which build to rerun and what to expect).

### 6. Solve

- Code/script fix in repo → ask the user; on yes, apply, rerun the
  phase-4 repro, and record the result in the report's Verification
  section.
- Manual fix → report only; no apply offer.

## Cross-platform rules

Same as the rest of the collection:

- No Claude-only tool names in SKILL.md — plain instructions ("search the
  repo for", "run this command").
- All chaining phrased as "if skill X is available, use it; otherwise do
  Y inline".
- Reports in English; error strings, commands, code verbatim.
- References loaded only when their class matches (keep token cost down).

## Out of scope

- Live Bamboo REST/CLI integration (future skill if ever needed).
- Auto-applying non-code fixes.
- Preinstalled Linux distro triage skills.
- CI systems other than Bamboo (GitHub Actions etc. — the generic
  domains still work, but no catalog for them).

## Verification

- Claude side: `python3 agent-skills/install.py --target claude`,
  confirm `~/.claude/skills/investigate-issue` symlink; run against a
  sample problem `.md` with a known bug in a scratch repo; report file
  appears next to input with Confirmed root cause.
- Copilot side (work VDI, still unverified for the whole collection):
  `python3 install.py --target copilot --dry-run` first, then real run;
  confirm `debugging-and-error-recovery` fetch from addyosmani upstream
  works behind the proxy, ZIP fallback documented.
