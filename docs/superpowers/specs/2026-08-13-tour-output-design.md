# Tour output for walkthrough skills — design

Date: 2026-08-13

## Problem

Four skills produce a walkthrough of real code — `explain-logic`,
`investigate-issue`, `soundboarding` and the community
`acquire-codebase-knowledge` — but the walkthrough dies with the chat
session. The `code-tour` skill can write a replayable CodeTour `.tour`
file, yet only `explain-logic` mentions it, and only as an optional
offer. The VS Code CodeTour extension that opens those files is not in
`vscode/extensions.txt`, so a generated tour has nothing to open it.

## Goal

A walkthrough leaves a replayable artifact by default. Opening it in VS
Code requires no manual setup on either machine.

## Behavior

Each of the four skills ends its run by writing a CodeTour file into
`.tours/` in the repository being worked on.

**Skip rule.** The tour is written by default. It is skipped only when
all three hold: a single file is involved, there is no cross-file flow,
and the walkthrough is under about three steps. On a skip the skill says
so in one line, naming the reason — for example `No tour — single
function, the walkthrough covers it.` The user asking for a tour
overrides a skip; the user saying "no tour" overrides the default.

**Persona and file name** per skill:

| Skill | Persona | Tour path |
|---|---|---|
| `explain-logic` | `new-joiner`, or `pr-reviewer` for a PR/branch | `.tours/explain-<branch-or-file>.tour` |
| `investigate-issue` | `bug-fixer` | `.tours/rca-<problem-name>.tour` |
| `soundboarding` | `contributor` | `.tours/sb-<LISA-id>.tour` |
| `acquire-codebase-knowledge` | `new-joiner` | `.tours/onboarding.tour` |

The `investigate-issue` tour uses the same stem as its report, so
`LISA-123.md` yields `LISA-123-investigation.md` and
`.tours/rca-LISA-123.tour`.

**No second pass.** Tour steps are built from evidence the skill has
already gathered. `investigate-issue` mirrors its Evidence section —
`file:line` findings in failure order. `explain-logic` mirrors its Flow
section in execution order. A skill does not re-investigate the
repository to build the tour.

**Generation.** Each skill chains to the `code-tour` skill when it is
installed, passing the persona and the collected `file:line` evidence,
and lets it write and validate the file. When `code-tour` is missing,
the skill writes a minimal tour inline: a JSON object with `$schema`,
`title`, `description` and a `steps` array of `{file, line,
description}`. That is the shape CodeTour needs to open a tour; the full
schema is not duplicated into our skills.

`code-tour`'s own `SKILL.md` documents its helper scripts at
`~/.agents/skills/code-tour/scripts/`, a path that does not exist on
either machine — the skill installs into `~/.claude/skills/code-tour/`
(and `~/.copilot/skills/code-tour/` on the work Windows box). Our skills
therefore instruct resolving `validate_tour.py` from the `code-tour`
skill directory that is actually installed, rather than from the
hardcoded path. The community copy is not patched, because it is
overwritten on every re-fetch; `agent-skills/docs/community-skills.md`
records the discrepancy instead.

## Where the rule lives

The rule is stated in two kinds of place, for two different reasons.

`claude/CLAUDE.md` gets a short entry covering all four skills. User
instructions outrank skills, so this reaches
`acquire-codebase-knowledge` without forking a community skill or adding
overlay machinery to the installer.

The three repository-owned skills — `explain-logic`,
`investigate-issue`, `soundboarding` — each get a `## Tour output`
section carrying the same rule with their own persona and file name.
This is not redundant with `CLAUDE.md`: the work Windows box installs
these skills into `~/.copilot/skills`, and Copilot does not read
`CLAUDE.md`. Without the in-skill section the behavior would silently
disappear on that machine.

## Install changes

**CodeTour extension.** `vscode/extensions.txt` gains
`vsls-contrib.codetour` under a new `# ---- Docs / walkthroughs ----`
group, untagged so it installs on both machines.

**Ignoring `.tours/`.** Generated tours are private, so they are ignored
globally rather than per repository — the alternative would have the
agent editing a tracked `.gitignore` in every repository it touches.

A new `git` tool brings the global excludes file into the repository as
`git/ignore`. It carries the line already present in
`~/.config/git/ignore` (`**/.claude/settings.local.json`) plus `.tours/`.
The tool follows the existing pattern: symlink on macOS and Linux, copy
on Git Bash where symlinks need admin rights. It points
`core.excludesFile` at the installed file only when that setting is
unset, so an existing configuration is never overwritten silently.
Uninstall removes the link or copy and restores the dated backup, the
same as every other tool; the git config entry is left in place, since
removing it could disturb settings the tool did not create.

Supporting updates: registration in `lib/tools/__init__.py`, a
`git/README.md`, a row in the root `README.md` folder table, and
`tests/test_git.py` covering target resolution, install, probe and
uninstall in a temporary `HOME`.

## Out of scope

Committing tours, sharing them with a team, per-repository tour indexes,
and any change to how the four skills perform their primary work. The
tour is an additional output, not a replacement for the explanation or
the investigation report.
