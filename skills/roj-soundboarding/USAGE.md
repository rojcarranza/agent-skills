# Using the roj-soundboarding skill

Turns a user story (`<TICKET-ID>.md`) into a soundboarding (SB) document with
codebase-investigated core tasks, then implements the SB task by task with a
review stop after every task. Never touches git — you review and commit
manually.

## When to use

- A user story needs refinement into concrete, investigated tasks before
  the team commits to it → **create**.
- A refined SB document is ready to execute → **implement**.
- Solo story, no team refinement needed → **create + implement** chained.

## Commands per platform

One skill, three flows — pick the flow in the request. Claude Code and VS Code
Copilot: `/roj-soundboarding <request>`. JetBrains Copilot:
`/skill:roj-soundboarding <request>`. Plain English works everywhere.

| Flow | Request |
|---|---|
| Create SB | `/roj-soundboarding create an SB from PROJ-1001.md` |
| Implement SB | `/roj-soundboarding implement SB-PROJ-1001` |
| Both chained | `/roj-soundboarding create and implement PROJ-1001.md` |

Set the two directories once in your shell profile so the skill never asks:

```bash
export SOUNDBOARD_DIR=~/work/soundboard   # stories + SB documents
export PROJECTS_ROOT=~/work/projects      # local checkouts of team repos
```

Windows (PowerShell): `setx SOUNDBOARD_DIR C:\work\soundboard`. A path in
the request wins over both, e.g.
`create an SB from story.md — soundboard dir is ~/Dev/soundboard`.

## Worked example

Story input: [`examples/PROJ-1001.md`](examples/PROJ-1001.md) — upgrade
the Bamboo API to v12.1.6 and verify agents and plans still work.

1. `/roj-soundboarding create an SB from PROJ-1001.md` — the skill reads the
   story, finds the impacted repos under PROJECTS_ROOT, records exact
   current versions from the POMs and config files it can read, and writes
   `SB-PROJ-1001.md` following `assets/SB-template.md`. Unverifiable claims
   land in Questions, not in Core tasks. Output shape:
   [`examples/SB-PROJ-1001.md`](examples/SB-PROJ-1001.md).
2. Team refines the SB (acceptance criteria, task list, testing table).
3. From the repo where the work happens:
   `/roj-soundboarding implement SB-PROJ-1001` — executes core tasks one at
   a time, verifies each diff against the SB's before/after table, stops
   after each for approve/revise/skip, ticks checkboxes in the SB file, and
   fills the Testing table Log column with real command results.
4. You review the working tree and commit manually.
