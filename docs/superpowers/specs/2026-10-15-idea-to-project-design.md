# roj-idea-to-project skill — design

Date: 2026-10-15
Issue: #29

## Problem

The workflow in "From Idea to Agent-Built Project (Claude-Only Workflow)"
(2026-10-15) takes an app idea to a repo an agent can build on its own:
a brief, a design, EARS requirements, architecture and ADRs, agent config
and a Definition of Ready, each reviewed in a fresh context before the next
phase starts. Nothing in this repo runs it, so every gate depends on
remembering it by hand. The gates are easy to skip: an agent advances on
"approve everything", reviews its own work, or starts building before the
non-goals are written down.

## Goal

One skill, `roj-idea-to-project`, that runs the workflow one gate at a time
on top of Superpowers, checks the Definition of Ready with a script, and
hands off to Superpowers for planning and building. Superpowers is a hard
dependency: the skill installs it (after a yes) before phase 1.

Not goals:

- Building, reviewing or deploying the project. The skill stops at the
  hand-off.
- Installing anything other than Superpowers. Linters and scanners are
  suggested in phase 5, never installed.
- Committing, branching or pushing in the user's project.
- Copilot inside VS Code or JetBrains (see Decisions).
- Changing Superpowers.

## Decisions

| Question | Choice |
|---|---|
| Shape | One orchestrating skill, detail in per-phase references. One skill per phase would split the trigger and the gate state; a thin DoR-only skill would drop the brief, EARS and ADR discipline Superpowers underweights |
| Engine | Superpowers, required, no fallback path |
| Copilot in VS Code / JetBrains | Unsupported in this PR; the skill says it needs Claude Code or Copilot CLI and stops. Follow-up issue for the `apm.yml` route (finding below) |
| "One file per phase" | Each phase writes one **artifact set**, every path listed before writing, one approval per set. Only phase 4 (architecture + ADRs) and phase 5 (agent config) have more than one file |
| Superpowers older than v7.0.0 | Offer the update and the reload stop; on a no, continue with a one-line warning recorded in the brief. Only a missing or disabled Superpowers blocks |
| Phase state | In the files: each approved file gets `Status: Approved YYYY-MM-DD`. The progress checklist is derived from the files on start, so a fresh session resumes at the first unapproved phase |
| Review findings | Recorded in a `## Review log` section of the reviewed file; an accepted finding that changes a decision becomes an ADR edit |
| Eval 1 | Split into 1a (asks for a yes) and 1b (yes given: installs, says `/reload-plugins`, stops): 5 behaviour evals instead of 4 |
| Gate checks | `check_ready.py --phase` runs only the checks of the phase at hand; `--phase all` is the Definition of Ready |

### Finding: Superpowers for Copilot in VS Code / JetBrains through `apm.yml`

- **Installable: yes.** Superpowers' skill folders are self-contained
  (`skills/brainstorming/` ships its own `scripts/` and prompts). An entry
  `obra/superpowers/skills/<name>#bb92a77741419a4ab5f06e711a283343f1ada0c3`
  (tag v7.0.0) with `targets: [copilot]` lands in `~/.agents/skills/`, as
  `caveman` does today.
- **Working: not shown.** `skills/using-superpowers/references/` maps tools
  for Claude Code, Codex, Gemini, Pi, Antigravity, Hermes and Muse, not
  Copilot. The plugin's `hooks/session-start` bootstrap, which loads
  `using-superpowers` every session, does not run from a skills-only
  install. `brainstorming` degrades without a subagent tool;
  `subagent-driven-development` needs one.
- **Result:** phase 0 would pass while the hand-off cannot run, so the
  route waits for a follow-up that runs the skills in IDE Copilot first.

## Facts this design relies on

Checked on 2026-10-15.

- `claude plugin list --json` (Claude Code 2.1.300) prints an array, one
  object per install, always with `id`, `version`, `scope`, `enabled`,
  `installPath`. `id` is `name@marketplace`. `version` is not always
  semver: a git-sourced plugin reports a short SHA (`8f814f49002f`).
- `claude plugin install|update|enable` exit 0 on success, 1 on failure.
  `plugin update` takes effect in the next session or after
  `/reload-plugins`.
- `/reload-plugins` runs only when the user types it into the session; a
  relayed or agent-issued command is refused. The agent cannot reload.
- Superpowers v7.0.0 is the latest release (2026-10-10, commit `bb92a77`).
  `claude-plugins-official` served 6.4.1 on the authoring machine.
- Superpowers install commands (README): Claude Code
  `/plugin install superpowers@claude-plugins-official`, or
  `/plugin marketplace add obra/superpowers-marketplace` then
  `/plugin install superpowers@superpowers-marketplace`; Copilot CLI
  `copilot plugin marketplace add obra/superpowers-marketplace` then
  `copilot plugin install superpowers@superpowers-marketplace`. The shell
  forms are `claude plugin install …` and `claude plugin marketplace add …`.
- `copilot plugin list` (Copilot CLI 1.0.81) has no `--json`; it prints
  text, `No plugins installed.` when empty.
- Copilot CLI: custom agents in `.github/agents/` or `~/.copilot/agents/`
  run as subagents with their own context; hooks live in
  `.github/hooks/*.json`; plan mode is `/plan` or Shift+Tab; `/clear`
  (aliases `/new`, `/reset`) starts a new conversation.
- Superpowers `brainstorming` ends by committing the spec and invoking
  `writing-plans`. Inside this skill both are overridden (Gotchas).

## Components

### Layout

```
skills/roj-idea-to-project/
  SKILL.md
  USAGE.md
  references/
    setup-superpowers.md      # phase 0
    phase-brief.md            # phase 1
    phase-requirements.md     # phase 3
    phase-architecture.md     # phase 4
    phase-agent-config.md     # phase 5
    review-gates.md           # fresh-context review, red-team prompt
    handoff.md                # phase 6 plan rules, phase 7 hand-off
  assets/
    brief-template.md
    requirements-template.md
    architecture-template.md
    adr-template.md
    claude-md-template.md
    progress-template.md
    agents/security-reviewer.md
    agents/architecture-guardian.md
    agents/test-auditor.md
    hooks-settings.example.json
  scripts/
    check_superpowers.py
    check_ready.py
```

Phase 2 (design) has no reference of its own: it is three lines in
SKILL.md that invoke `superpowers:brainstorming` with the overrides.
Templates, the three agent files and the red-team prompt are copied from
the workflow verbatim; assets add only the `Status:` line and the
`## Review log` heading.

### SKILL.md

About 150 to 200 lines, under 500 lines and 5,000 tokens. Sections:
purpose (3 lines), Inputs, Hard rules, Progress checklist, one section per
phase, Gotchas, Hand-off.

Each phase section names its reference with its trigger ("Read
`references/phase-requirements.md` before drafting requirements"), the
file(s) it writes, the gate check, and the reason for the gate in one
line. Format and rules only: no explanation of TDD, ADRs or EARS.

Hard rules (from the issue, worded for the agent):

1. Phase 0 passes before any other phase.
2. One phase at a time; each writes one artifact set and ends with an
   explicit approval. "Approve everything" still gets a per-gate
   confirmation.
3. One question per message, each with a recommended answer.
4. Facts are the agent's, decisions are the user's.
5. Fresh-context review at the requirements, architecture and plan gates;
   never in the context that wrote the file.
6. Reviewers report only correctness, security and requirement gaps; the
   user accepts or rejects each finding; the decision is recorded.
7. State the exact path before writing; never overwrite, rename or delete
   without confirmation.
8. Git: never commit, branch or push. Offer `git init` only in an empty
   folder, after a yes.
9. Install nothing without a yes, and only Superpowers.

Progress checklist (copied into the reply and ticked as phases pass):

```
- [ ] 0 Setup: Superpowers installed, enabled, reloaded
- [ ] 1 Brief: docs/brief.md
- [ ] 2 Design: docs/superpowers/specs/<date>-<topic>-design.md
- [ ] 3 Requirements: docs/requirements.md (reviewed)
- [ ] 4 Architecture: docs/architecture.md + docs/adr/ (reviewed)
- [ ] 5 Agent config: CLAUDE.md, .claude/settings.json, .claude/agents/
- [ ] 6 Ready + plan: check_ready.py passes; plan (reviewed)
- [ ] 7 Hand-off: docs/progress.md
```

Gotchas (all observed or confirmed while designing):

- Superpowers `brainstorming` commits the spec and chains to
  `writing-plans`. In phase 2: write the spec, do not commit, stop after
  approval and return to phase 3. Same in phase 6 for `writing-plans`:
  no commit, stop after the plan review.
- `/reload-plugins` cannot be run by the agent; asking the user and
  stopping is the only path.
- A `version` that is a SHA cannot be compared to v7.0.0; say so, do not
  call it outdated.
- `check_ready.py` without `--phase` checks the whole DoR and will report
  later-phase files as missing; pass the phase at each gate.
- `architecture-guardian` does not exist until phase 5; at phase 4 the
  reviewer is the red-team subagent only.

Portability (one line each in SKILL.md):

| Feature | Claude Code | Copilot CLI |
|---|---|---|
| Fresh-context reviewer | subagent, model `opus` | custom agent in `.github/agents/` (runs as subagent); else print the prompt and `/new` with only the file |
| Hooks | `.claude/settings.json` | `.github/hooks/*.json` (different schema; phase 5 writes the Claude file and names the Copilot path) |
| Plan mode | plan mode (Shift+Tab) | `/plan` or Shift+Tab |
| Clear context | `/clear` | `/clear` (`/new`, `/reset`) |
| Reload after install | `/reload-plugins` | restart `copilot` |

Model aliases only (`opus`, `sonnet`).

### Phase flow

| # | Phase | Writes | Gate check | Fresh review |
|---|---|---|---|---|
| 0 | Setup | nothing | `check_superpowers.py` exit 0 | — |
| 1 | Brief | `docs/brief.md` | `check_ready.py --phase brief` | optional one-line offer: "argue against this idea" |
| 2 | Design | `docs/superpowers/specs/<date>-<topic>-design.md` via `superpowers:brainstorming` | user approves the spec | brainstorming's builder check |
| 3 | Requirements | `docs/requirements.md` | `check_ready.py --phase requirements` | red-team subagent |
| 4 | Architecture | `docs/architecture.md` + `docs/adr/NNNN-<decision>.md` | `check_ready.py --phase architecture` | red-team subagent |
| 5 | Agent config | `CLAUDE.md`, `.claude/settings.json`, `.claude/agents/{security-reviewer,architecture-guardian,test-auditor}.md` | `check_ready.py --phase agent-config`; user runs every `CLAUDE.md` command in a clean shell and confirms | — |
| 6 | Ready + plan | `docs/superpowers/plans/<date>-<feature>.md` via `superpowers:writing-plans` | `check_ready.py` (all) loop passes before the plan is written; task 1 is a walking skeleton; tasks use the workflow's task format | red-team subagent + `architecture-guardian` |
| 7 | Hand-off | `docs/progress.md` | — | — |

Phase 0, in order:

1. Unsupported client (Copilot in VS Code or JetBrains): say the skill
   needs Claude Code or Copilot CLI, stop.
2. Run `scripts/check_superpowers.py`.
3. `missing`: say what will be installed and why, ask for a yes, then run
   `claude plugin install superpowers@claude-plugins-official`; if that
   marketplace is not available, `claude plugin marketplace add
   obra/superpowers-marketplace` then `claude plugin install
   superpowers@superpowers-marketplace`. Copilot CLI:
   `copilot plugin marketplace add obra/superpowers-marketplace` then
   `copilot plugin install superpowers@superpowers-marketplace`.
4. `disabled`: offer the `next` command (`claude plugin enable …`), same
   yes.
5. After any install, enable or update: tell the user to run
   `/reload-plugins` (Copilot CLI: restart), STOP. Re-run the check after
   the user confirms; continue only on exit 0.
6. `outdated` (below v7.0.0): offer `claude plugin update
   superpowers@<marketplace>` and the same reload stop; on a no, continue
   and note the version in the brief.
7. Install fails: show the exact error and the command for the user's own
   terminal, STOP.
8. `undetectable`: check whether `superpowers:brainstorming` is in the
   session's skill list; listed passes, not listed is `missing`.

Phase 1 also offers `git init` when the folder is empty and has no `.git`,
after a yes.

Phase 7 writes `docs/progress.md` from the template (one checklist line
per FR with its verify command) and tells the user: new session in a
worktree, `superpowers:subagent-driven-development` on the plan, review
with `/code-review` then the three subagents then their own read of the
diff, finish with `superpowers:finishing-a-development-branch`, a 10-minute
retro after the first merge. Deploy: infra is its own spec. Native plan
mode instead of the full flow only when the change fits in one sentence.

### Fresh-context review (`references/review-gates.md`)

- Claude Code: dispatch a subagent (model `opus` when available) whose
  prompt holds only the file paths and the red-team prompt with
  `<requirements | architecture | plan>` filled in. No chat history, no
  summary of the conversation.
- Where subagents are unavailable: print the red-team prompt and tell the
  user to open a new chat with only that file, then paste the findings
  back.
- Present findings one at a time, each with a recommended accept or
  reject. Record each in `## Review log`:
  `- [blocker|major|minor] <quote> → accepted|rejected: <reason>`.
- Style findings are dropped without asking.

### `scripts/check_superpowers.py`

Python 3 standard library, `--help`, never installs.

- `--client claude|copilot|auto` (default `auto`: `claude` on PATH first,
  then `copilot`).
- Claude: `claude plugin list --json`; the entry whose `id` starts with
  `superpowers@`. Marketplace taken from the `id`.
- Copilot CLI: `copilot plugin list` text; a line containing
  `superpowers`, version by regex; line found but version not parsed →
  `version: unknown`.
- Neither CLI on PATH → `undetectable`.
- stdout: one JSON object `{client, installed, version,
  version_comparable, enabled, status, next}`; `status` is one of
  `ok|outdated|missing|disabled|undetectable`; `next` is the list of exact
  commands to run, in order (empty when there is nothing to do; Copilot CLI
  needs two for an install). stderr: one human line.
- Exit 0 for `ok` and `outdated`, 1 otherwise.
- `--min-version` (default `7.0.0`) for the outdated comparison.

### `scripts/check_ready.py`

Python 3 standard library, `--help`. `check_ready.py [--phase
brief|requirements|architecture|agent-config|all] [ROOT]`, default `all`
and the current directory.

- brief: `docs/brief.md` exists; 5 or more list items under
  `## Non-goals`.
- requirements: `docs/requirements.md` exists; every line with an
  `FR-x.y` ID matches `WHEN|IF|WHILE|WHERE … SHALL`; every `### FR-n`
  block has a `Verification:` line; a line starting `- NFR-SEC` exists.
- architecture: `docs/architecture.md` exists; ADRs in `docs/adr/*.md`
  cover language, persistence, auth, deploy target and observability,
  matched by filename or `# ADR-` title keyword with a short synonym list
  per area (persistence: database, storage, datastore; auth:
  authentication, authorization, identity; deploy: deployment, hosting,
  infrastructure; observability: logging, monitoring, telemetry;
  language: stack, runtime, framework).
- agent-config: `CLAUDE.md` exists and has fewer than 100 lines.
- `all`: every check above.
- Prints every failure with its fix, for example
  `FR-2.3 has no Verification line: add "Verification: <test name or command>"`
  or `docs/brief.md has 2 non-goals: add at least 3 more under ## Non-goals`.
  Ends with `READY` or `NOT READY: <n> issues`. Exit 0 or 1.
- Plain text, because the agent's next step is to fix and re-run and the
  lines are its instructions.

SKILL.md runs it as a loop at every gate and before the hand-off: run, fix,
re-run until it passes.

## Packaging and docs

- `.claude-plugin/marketplace.json`, `apm.yml` (local path), README skills
  table.
- `docs/community-skills.md`: a Superpowers section as a dependency of
  this skill, with the Claude Code and Copilot CLI commands and the IDE
  Copilot note. Superpowers is not added to `apm.yml`.
- `docs/stories/skills-inventory.md` lists no `roj-` skills; unchanged.
- `.github/workflows/test.yml`: a step running
  `python -m unittest test_idea_to_project`. README "Tests" and CLAUDE.md
  "Before pushing" name the new module.

Description (quoted, because it contains `: `):

> Take a raw app idea to a repo an agent can build: a brief with
> non-goals, a design, EARS requirements, architecture and ADRs, agent
> config and a checked Definition of Ready, one approved gate at a time
> with a fresh-context review at the requirements, architecture and plan
> gates, then hand off to Superpowers to plan and build. Installs the
> Superpowers plugin first when it is missing. Use when the user has an
> app or product idea, wants to plan a new project before Claude builds
> it, or wants a new or empty repo set up so an agent can build it, even
> if they never say spec, requirements or architecture. Not for reviewing
> code (roj-code-review-pr), grilling an existing plan (roj-grill-plan),
> implementing a story (roj-soundboarding), explaining code
> (roj-explain-logic) or writing a spec for a feature in an existing
> codebase.

`compatibility`: requires Claude Code or GitHub Copilot CLI with the
Superpowers plugin (installed by the skill on first run), and Python 3.
`license: MIT`.

## Testing

### Unit tests: `test_idea_to_project.py`

`unittest`, temp-dir fixtures, run in CI on ubuntu, macos and windows.

- `check_superpowers.py`: canned `claude plugin list --json` arrays for
  ok, outdated (6.4.1), SHA version, disabled, missing; canned
  `copilot plugin list` text; no CLI on PATH; exit codes and `next`.
  Scripts run as subprocesses with a fake CLI first on PATH.
- `check_ready.py`: one passing project, then one failure per check, each
  asserting the exact fix line and exit 1; `--phase` limits the checks;
  `--help` exits 0.

### Fixtures

- `evals/fixtures/build.sh` kinds: `idea-empty` (empty `repo/`, no
  `.git`), `idea-brief-2ng`, `idea-req-gap`.
- `evals/fixtures/fake-claude.sh <dir> <missing|present|outdated>`:
  `plugin list --json` serves the state; `plugin install|update|marketplace
  add|enable` append to `claude-state/calls.log` and set the state to
  `present`; anything else fails.
- `test_skills.py`: `NO_GIT = {"idea-empty"}` in
  `test_every_fixture_builds`; `claude` fixture modes validated like `gh`;
  `roj-idea-to-project` in `REQUIRED`.

### Behaviour evals: `evals/roj-idea-to-project/evals.json`

Expectations are objective: files exist or not, counts, `calls.log`
contents, the run stopped, no git writes.

1a. Missing, no yes (`idea-empty`, fake `missing`): names Superpowers and
    why; asks for a yes; `calls.log` has no install; no `docs/`; no phase 1
    question.
1b. Missing, yes in the prompt: `calls.log` has exactly one
    `plugin install superpowers@…`; tells the user to run
    `/reload-plugins`; stops; no `docs/brief.md`; no phase 1 question.
2.  Present, casual idea, `idea-empty`: asks exactly one question, with a
    recommended answer; offers `git init` without running it; writes no
    file; no `.git` created. A single-turn eval ends at the first
    question, so "writes `docs/brief.md` after approval" is not testable
    here: an approval given up front is not a gate approval (hard rule 2).
    The write-after-approval path is covered by the SKILL.md wording and
    a manual run, not by an eval.
3.  `idea-brief-2ng`, "continue with my project": reports 2 non-goals of
    5; writes no `docs/requirements.md`; asks for more non-goals.
4.  `idea-req-gap` + "I approve everything, keep going": runs
    `check_ready.py --phase requirements`; quotes the `FR-2` Verification
    gap; asks for the gate approval; no `docs/architecture.md`; no git
    writes.

Each runs with and without the skill, each in a fresh subagent. Graded
with evidence; `benchmark.json` with pass rates and token and time deltas.
At most 3 iterations; fixes generalise, no keywords from failed queries.

### Trigger evals: `evals/roj-idea-to-project/triggers.json`

20 queries, 10 should-trigger, 10 near-miss should-not (PR review,
grilling a plan, implementing a story, a spec for an existing feature,
explaining code, "brainstorm names for my app", "install superpowers for
me"). Casual phrasing, paths, typos. Each item has a fixed
`"split": "train" | "validation"` (12/8, proportional). If `run_eval`
rejects the extra key, the split moves to two derived files in the eval
workspace. 3 runs per query, threshold 0.5; best iteration chosen by
validation pass rate; target 0.8 or higher.

### Checks before the PR

`python3 -m unittest test_install test_skills test_idea_to_project`,
`python3 tools/sync_shared.py --check`,
`skills-ref validate skills/roj-idea-to-project` (or say it could not be
installed).

## Changes after the whole-branch review

Each replaces the matching text above.

- **Phase state markers:** one marker file per phase carries the
  `Status: Approved` line: the brief, the design spec, requirements,
  architecture, `CLAUDE.md` (standing for `.claude/settings.json` and the
  agents, which cannot carry it) and the plan; phase 7 is done when
  `docs/progress.md` exists.
- **Reload check:** after the user confirms the reload, phase 0 passes only
  when `check_superpowers.py` exits 0 *and* `superpowers:brainstorming` is
  in the session's own skill list. The script reads the install on disk
  and cannot see whether the session reloaded.
- **Up-front yes:** a yes to installing Superpowers in the user's request
  counts for the install (the only up-front yes the skill honours). The
  fallback marketplace (`obra/superpowers-marketplace`) gets its own yes.
- **`git init`:** a one-line note in the first brief message ("say
  `git init` whenever you want one"), not a question, so the first message
  still asks one question. Eval 3 expects the mention, not an offer.
- **ADR coverage:** ADRs carry an `Area:` line; `check_ready.py` reads it
  first and falls back to whole-word keywords in the file name or title.
- **Phase 5 gate and the `Stop` hook:** phase 5 verifies only the
  `CLAUDE.md` commands that can run before code exists and marks the rest
  "verified by plan task 1". The `Stop` hook is not written in phase 5;
  plan task 1 adds it once tests exist, because a failing test command
  with exit 2 would keep the planning session from ending its turn.
- **`check_superpowers.py`:** runs the CLI with stdin closed and a 30 s
  timeout (`--timeout`); a timeout is `undetectable`.
