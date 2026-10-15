# Using the roj-idea-to-project skill

Takes a raw app idea to a repo an agent can build on its own: a brief with
non-goals, a design, EARS requirements, architecture and ADRs, agent config
(`CLAUDE.md`, hooks, reviewer agents) and a checked Definition of Ready.
Each phase writes one set of files and stops for your approval; the
requirements, architecture and plan are reviewed by a fresh Claude context
that never saw the conversation. Superpowers does the design, planning and
building: the skill installs it on first run, after you say yes. Never
touches git, apart from offering `git init` in an empty folder.

The workflow is the Claude-only "idea to agent-built project" pipeline:
Superpowers as the engine, plus EARS acceptance criteria, ADRs you own, a
lean `CLAUDE.md` and deterministic hooks.

## When to use

- You have an app idea and want it planned before an agent writes code.
- You have an empty folder and want it set up so an agent can build in it.
- You stopped half-way: run it again in the same folder and it resumes at
  the first phase that is not approved.

## Commands per platform

Claude Code and GitHub Copilot CLI: `/roj-idea-to-project <your idea>`.
Plain English works too. Copilot in VS Code and JetBrains is not supported
yet: Superpowers has no install there.

| Goal | Request |
|---|---|
| Start from an idea | `/roj-idea-to-project a shared grocery list for my flat` |
| Resume in a folder that has `docs/brief.md` | `/roj-idea-to-project continue` |
| Check the Definition of Ready yourself | `python3 <skill dir>/scripts/check_ready.py` |
| Check one gate | `python3 <skill dir>/scripts/check_ready.py --phase requirements` |
| Check Superpowers | `python3 <skill dir>/scripts/check_superpowers.py` |

## Phases

| # | Phase | Files |
|---|---|---|
| 0 | Superpowers installed, enabled, reloaded | none |
| 1 | Brief | `docs/brief.md` |
| 2 | Design (Superpowers brainstorming) | `docs/superpowers/specs/<date>-<topic>-design.md` |
| 3 | Requirements, reviewed | `docs/requirements.md` |
| 4 | Architecture, reviewed | `docs/architecture.md`, `docs/adr/` |
| 5 | Agent config | `CLAUDE.md`, `.claude/settings.json`, `.claude/agents/` |
| 6 | Definition of Ready, then the plan, reviewed | `docs/superpowers/plans/<date>-<feature>.md` |
| 7 | Hand-off | `docs/progress.md` |

## Answering a gate

- `yes`: approves this gate only. "Approve everything" is asked again at
  each gate, by design.
- One question per message, each with a recommended answer: `yes` accepts
  it; or give your own answer.
- Review findings come one at a time: `accept` or `reject, because ...`.
  Your decision is written into the file's `## Review log`.
- After an install the skill asks you to run `/reload-plugins` (Copilot CLI:
  restart `copilot`) and waits: it cannot reload plugins itself.

## Output

Approved files carry `Status: Approved YYYY-MM-DD`. Reviewed files end with
a `## Review log`. At the end, start a new session in a worktree and run
`superpowers:subagent-driven-development` on the plan.
