---
name: roj-idea-to-project
description: "Take a raw app idea to a repo an agent can build: a brief with non-goals, a design, EARS requirements, architecture and ADRs, agent config and a checked Definition of Ready, one approved gate at a time with a fresh-context review at the requirements, architecture and plan gates, then hand off to Superpowers to plan and build. Installs the Superpowers plugin first when it is missing. Use when the user has an app or product idea, wants to plan a new project before Claude builds it, or wants a new or empty repo set up so an agent can build it, even if they never say spec, requirements or architecture. Not for reviewing code (roj-code-review-pr), grilling an existing plan (roj-grill-plan), implementing a story (roj-soundboarding), explaining code (roj-explain-logic) or writing a spec for a feature in an existing codebase."
license: MIT
compatibility: Requires Claude Code or GitHub Copilot CLI with the Superpowers plugin (installed by the skill on first run), and Python 3.
---

# Idea to Project

Walk the user from a raw app idea to a repo an agent can build: brief,
design, EARS requirements, architecture and ADRs, agent config and a
checked Definition of Ready. Each phase writes one artifact set and ends at
a gate the user approves. Superpowers designs, plans and builds; this skill
keeps the gates.

## Inputs

- The idea, in chat, in any form.
- The project folder: the current directory. Empty is fine.
- Phase files already in it (`docs/brief.md`, `docs/requirements.md`, ...):
  resume from them (see Progress).

## Hard rules

1. **Superpowers first.** Phase 0 passes before any other phase: every
   later phase calls a Superpowers skill.
2. **One phase at a time.** Each phase writes one artifact set and ends with
   an explicit approval of that set. "Approve everything" or "keep going"
   is not a gate approval: confirm each gate as you reach it. Every phase
   consumes the one before, so an unchecked file spoils all that follow.
3. **One question per message**, with your recommended answer, worded so
   "yes" accepts it.
4. **Facts are yours, decisions are the user's.** Look up versions,
   commands, prices, limits and what exists in the folder; ask only for
   choices.
5. **Fresh-context review** at the requirements, architecture and plan
   gates, never in the context that wrote the file. Read
   `references/review-gates.md` before each one.
6. **Reviewers report only correctness, security and requirement gaps.**
   The user accepts or rejects each finding; record it in the file's
   `## Review log` (or an ADR).
7. **Say the path before writing.** Name the exact path of every file
   before writing it. Never overwrite, rename or delete an existing file
   without a yes.
8. **Git: hands off.** Never commit, branch or push, including when a
   Superpowers skill says to. Offer `git init` only in an empty folder with
   no `.git`, and run it only on a yes.
9. **Install nothing but Superpowers, and only after a yes.** Linters and
   scanners are suggested in phase 5, never installed.

## Progress

At the start of every run, derive this checklist from the files and show
it:

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

A phase is done when its files exist, carry `Status: Approved YYYY-MM-DD`
and pass their check. An approved file that fails its check is not done:
resume there and say why. Write the `Status: Approved` line only after
the user approves that gate.

Scripts live in this skill's folder; run them with `python3` (or `python`
where that is Python 3) and pass the project folder as ROOT:

- `scripts/check_superpowers.py`: JSON report on Superpowers; exit 0 when
  usable. Never installs.
- `scripts/check_ready.py --phase <brief|requirements|architecture|agent-config|all> ROOT`:
  prints every gap with its fix; exit 0 when the phase passes.

**Gate loop** for every phase with a check: run it, fix the file with the
user, re-run until it exits 0, then ask for the approval. Passing the
check is not an approval.

## Phase 0: Setup

Read `references/setup-superpowers.md` before running the check. In Copilot
inside VS Code or JetBrains, say this skill needs Claude Code or GitHub
Copilot CLI and stop.

Run `scripts/check_superpowers.py` and act on `status`: `ok` continues;
`missing` or `disabled` gets an explanation and a yes before running
`next`; `outdated` gets the update offered, and a no continues with the
version noted in the brief; `undetectable` means checking your own skill
list for `superpowers:brainstorming`.

After any install, enable or update: tell the user to run `/reload-plugins`
(Copilot CLI: restart `copilot`) and STOP. You cannot run it. Re-run the
check when they confirm; continue only on exit 0. A failed install: show
the error verbatim and the command for their own terminal, then STOP.

## Phase 1: Brief → `docs/brief.md`

Read `references/phase-brief.md` before the first question. Fill
`assets/brief-template.md` one question at a time. Gate:
`check_ready.py --phase brief`. The non-goals set the scope every later
phase checks; without them agents over-build.

## Phase 2: Design → `docs/superpowers/specs/<date>-<topic>-design.md`

Invoke `superpowers:brainstorming` with `@docs/brief.md`. Its flow shapes
the design; override two of its steps: do not commit the spec, and after
the user approves it, come back here for phase 3 instead of invoking
`writing-plans`. Hidden decisions surface here, before they become
requirements.

## Phase 3: Requirements → `docs/requirements.md`

Read `references/phase-requirements.md` before drafting. Draft from the
brief and the design spec with `assets/requirements-template.md`. Gate:
`check_ready.py --phase requirements`, then the fresh review, then the
approval. Testable requirements let someone who did not write them say
when the work is done.

## Phase 4: Architecture → `docs/architecture.md` + `docs/adr/`

Read `references/phase-architecture.md` before drafting. Use
`assets/architecture-template.md` and one `assets/adr-template.md` per
decision. Gate: `check_ready.py --phase architecture`, then the fresh
review, then the approval. The user keeps control here: no service,
datastore or dependency without an ADR.

## Phase 5: Agent config → `CLAUDE.md`, `.claude/settings.json`, `.claude/agents/`

Read `references/phase-agent-config.md` before writing. List all five
paths, write them on one yes from `assets/claude-md-template.md`,
`assets/hooks-settings.example.json` and `assets/agents/`. Gate: the user
runs every `CLAUDE.md` command in a fresh shell and confirms each one, then
`check_ready.py --phase agent-config`, then the approval. Guardrails exist
before the first line of agent code.

## Phase 6: Ready + plan → `docs/superpowers/plans/<date>-<feature>.md`

Read `references/handoff.md` before the plan. Run
`check_ready.py --phase all` as a loop until `READY`, then invoke
`superpowers:writing-plans` with the plan rules from that file; override:
no commit, stop after writing. Gate: fresh review plus
`architecture-guardian`, then the approval. Small verified tasks let the
agent run for hours without drifting.

## Phase 7: Hand-off → `docs/progress.md`

Write `docs/progress.md` from `assets/progress-template.md`, one line per
FR with its verify command. Give the build, review and retro steps from
`references/handoff.md`, then stop. This skill builds nothing.

## Claude Code and Copilot CLI

| Feature | Claude Code | Copilot CLI |
|---|---|---|
| Fresh reviewer | subagent, model `opus` | custom agent in `.github/agents/`; else `/new` with only the file |
| Hooks | `.claude/settings.json` | `.github/hooks/*.json` (other schema: name it, do not write it) |
| Plan mode | Shift+Tab | `/plan` or Shift+Tab |
| Clear context | `/clear` | `/clear` (`/new`, `/reset`) |
| Reload plugins | `/reload-plugins` (the user types it) | restart `copilot` |

Use model aliases (`opus`, `sonnet`), never versioned model IDs.

## Gotchas

- Superpowers `brainstorming` and `writing-plans` commit their file and
  chain to the next skill. Inside this skill: write, do not commit, stop
  at the gate.
- `/reload-plugins` runs only when the user types it; asking and stopping
  is the only path after an install.
- `check_superpowers.py` may report a commit SHA as `version`
  (`version_comparable: false`): that is not outdated.
- `check_ready.py` without `--phase` checks the whole Definition of Ready
  and reports later-phase files as missing. Pass the phase at each gate.
- `architecture-guardian` does not exist until phase 5. At phase 4 the
  reviewer is the red-team subagent alone.
- A brief marked approved can still fail its check (someone edited it):
  the check wins, not the `Status:` line.

## Hand-off

When phase 7 is done, end with the checklist fully ticked and one line:
"Ready to build: start a new session in a worktree and run
`superpowers:subagent-driven-development` on
`docs/superpowers/plans/<file>`."
