# Using the roj-soundboarding skill

Turns a user story into a soundboarding (SB) document with
codebase-investigated core tasks, then implements the SB task by task with a
review stop after every task. The story is a `<TICKET-ID>.md` file, pasted
Jira ticket text, or a Jira key or URL. Never touches git - you review and
commit manually.

## When to use

- A user story needs refinement into concrete, investigated tasks before
  the team commits to it → **create**.
- A refined SB document is ready to execute → **implement**.
- Solo story, no team refinement needed → **create + implement** chained.

Plain wording routes here too: "plan this ticket", "break this ticket into
tasks", "break this story into tasks", "refine this story".

## Commands per platform

One skill, three flows — pick the flow in the request. VS Code Copilot:
`/roj-soundboarding <request>`. JetBrains Copilot:
`/skill:roj-soundboarding <request>`. Plain English works everywhere.

| Flow | Request |
|---|---|
| Create SB | `/roj-soundboarding create an SB from PROJ-1001.md` |
| Implement SB | `/roj-soundboarding implement SB-PROJ-1001` |
| Both chained | `/roj-soundboarding create and implement PROJ-1001.md` |
| From pasted Jira text | `/roj-soundboarding create an SB from this ticket:` + the pasted text |
| From a Jira key | `/roj-soundboarding create an SB from PROJ-1001` |

A Jira key or URL is read only when an Atlassian or Jira tool (an MCP server)
is connected to your Copilot session; the skill never calls the Jira API
itself and never writes to Jira. Without such a tool it asks you to paste the
ticket text. The SB file is named from the ticket key (`SB-PROJ-1001.md`).

By default the SB document is written to the root of the repository you run
the skill in, next to the code it describes, and sibling checkouts of that
repository are searched for the other repos a story touches. The skill says
where it will write at the start of each run.

To keep stories and SB documents in one shared folder instead, set the
directories once in your shell profile:

```bash
export SOUNDBOARD_DIR=~/work/soundboard   # stories + SB documents
export PROJECTS_ROOT=~/work/projects      # local checkouts of team repos
```

Windows (PowerShell): `setx SOUNDBOARD_DIR C:\work\soundboard`. A path in
the request wins over both, e.g.
`create an SB from story.md — soundboard dir is ~/Dev/soundboard`.

## Your own template

The skill uses `SOUNDBOARD_DIR/SB-template.md` when that file exists and its
bundled `assets/SB-template.md` otherwise, and says which at the start of the
run. Put team standing questions in your own copy, for example a sprint
review question, so every SB you create carries it:

```markdown
## Questions

- Do we add a slide to our sprint review presentation for this story?
```

Keep the section headings the bundled template defines; the skill produces
exactly the sections of the template in use.

## The implementation plan

The bundled template has an `## Implementation plan` section between
Acceptance Criteria and Core tasks. It tells the implement flow how you want
the story built:

- **Approach:** your idea about the workflow or the architecture. Put it in
  the request or the story file, e.g.
  `/roj-soundboarding create an SB from PROJ-1001.md; upgrade the agents before the plans`,
  and the section records your words. Without one, the skill drafts the
  approach from its investigation and marks it `Draft`; confirm or edit it
  before implementing.
- **Task flow:** a Mermaid diagram of the core tasks, grouped by repository,
  showing which task needs which and which open question blocks which task.
  Drawn when there are two or more core tasks.
- **Change flow:** a Mermaid diagram of the runtime path or pipeline the
  story changes, with the new, changed and removed steps. Drawn only when
  the story changes one.

The diagrams render in the SB file's preview in VS Code and JetBrains (tick
the Mermaid plugin there if it shows text), on GitHub and on
<https://mermaid.live>.

`implement` reads the section before the first task. It asks once when the
approach is still a draft, takes the tasks in task-flow order and stops
before a task whose prerequisite is unticked or whose blocking question is
still open. When an edit would depart from the plan, it stops and asks, then
writes the agreed change into the section, so the plan stays true. The
checkboxes stay the only progress mark.

A team template without the section keeps its shape: the task flow goes
under Core tasks, and the approach and change flow under Notes. An SB with no
plan is implemented in Core tasks order, as before.

## Implementing safely

`implement` warns when a target repository is on its default branch (the
skill never creates a branch; `git switch -c <type>/<TICKET-ID>` carries your
uncommitted edits along), runs a baseline test before the first task so
failures that predate the work are not blamed on it, runs the narrowest
relevant check after each task, and ends by offering `roj-code-review-pr` on
the working tree, passing the SB's acceptance criteria in the review request
as what to check the change against. Once every code task is ticked it also
offers a demo slide through `roj-one-slide`.
Which command it picks per stack (Go, Maven, Gradle, Python, shell, Docker,
Helm, Kubernetes manifests) is in
[`references/test-commands.md`](references/test-commands.md); it runs only
commands the repository provides and never deploys.

## Worked example

Story input: [`examples/PROJ-1001.md`](examples/PROJ-1001.md) — upgrade
the Bamboo API to v12.1.6 and verify agents and plans still work.

1. `/roj-soundboarding create an SB from PROJ-1001.md` — the skill reads the
   story, finds the impacted repos under PROJECTS_ROOT, records exact
   current versions from the POMs and config files it can read, and writes
   `SB-PROJ-1001.md` following `assets/SB-template.md`, with a draft
   approach, a task flow and a change flow in its Implementation plan.
   Unverifiable claims land in Questions, not in Core tasks. Output shape:
   [`examples/SB-PROJ-1001.md`](examples/SB-PROJ-1001.md). The repositories
   in the example are fictional; every row carries the `path:line` it was
   read from and a Source, and what could not be verified is a Question.
2. Team refines the SB (acceptance criteria, task list, testing table).
   To settle the Questions section first, answer yes to "Grill the open
   questions now?" at the end of step 1, or run
   `/roj-grill-plan SB-PROJ-1001` later (see
   [roj-grill-plan](../roj-grill-plan/USAGE.md)).
3. From the repo where the work happens:
   `/roj-soundboarding implement SB-PROJ-1001` — executes core tasks one at
   a time in task-flow order, stops at an unticked prerequisite or a
   departure from the plan, verifies each diff against the SB's
   before/after table, stops
   after each for approve/revise/skip, ticks checkboxes in the SB file, and
   fills the Testing table Log column with real command results.
4. You review the working tree and commit manually.
