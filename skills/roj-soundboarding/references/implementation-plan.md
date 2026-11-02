# Implementation plan

The `## Implementation plan` section records how the story will be built:
the user's approach, the order of the core tasks, and the runtime path the
change touches. The create flow writes it; the implement flow follows it.
It sits between Acceptance Criteria and Core tasks and holds three
subsections, always all three.

## Contents

- Approach
- Task flow
- Change flow
- A template without the section
- How the implement flow uses it

## Approach

The user's idea about the workflow or the architecture, in a few bullets.

- Take it from the user's message or the story file, in the user's words:
  "keep the retry inside the HTTP client", "rebuild the image first, then
  the chart". Do not reword it into something else; add only what the
  investigation found it touches (`path:line`).
- No idea in the message or the story: draft the approach from the
  investigation and mark it. The first line of the subsection is exactly

  ```text
  > **Draft:** written by the agent from its investigation. Confirm or edit it before implementation.
  ```

  The marker stays until the user confirms or edits the approach; the
  implement flow removes it then. Never mark the user's own words as a draft.

## Task flow

A Mermaid `flowchart TD` of the core tasks, whenever there are two or more
(top-down keeps the labels readable in a narrow preview). With fewer, write
`- Not drawn: one core task.`

- One node per Core tasks checkbox. Node `Tn` is the n-th top-level
  checkbox, and its label starts with `Tn` and a few words of that task:
  `T3["T3 ACC URL and new image tag, rows 5-6"]`.
- Group the nodes in a `subgraph` per repository, named after the backtick
  tag, and one `subgraph manual["Manual"]` for the non-code tasks.
- A solid edge `T2 --> T3` means T3 needs T2 done first. Draw it only for a
  reason the investigation or the story gives (an image tag the chart needs,
  an API a test calls), and label it when the reason is not obvious:
  `T2 -->|"new image tag"| T3`. Tasks with no edge between them are
  independent.
- An open question that blocks a task is a node `Qn` (the n-th Questions
  item) with a dotted edge into that task: `Q1["Q1 Java version"] -.->|"blocks rows 2-4"| T2`.
- At most 15 nodes and 25 edges, as `references/mermaid.md` says; split by
  repository when a story needs more.

The task flow is the one exception to the "Draw from evidence" rule of
`references/mermaid.md`: its nodes are this SB's tasks and questions, not
code. Every other rule there applies: the safe subset, quoted labels, no
`end` as an ID, no styling.

## Change flow

A Mermaid flow diff (`references/mermaid.md`, "Flow diff") of the runtime
path or pipeline the story changes: a call, request, message, deployment or
CI step that runs differently afterwards. Draw only the steps the core tasks
add, change or remove, in run order.

- Each message starts with `+`, `~` or `-` and ends with `planned` for a step
  the core tasks will make, or `read` for what the code does today.
- A removed step is a `Note over` inside a red `rect` block.
- A step that builds, deploys or runs a new version or image is a changed
  step: `~ start the image with agent 12.1.6 on JDK 21, planned`.
- No step runs differently (a doc, a test, a value nothing reads at run
  time): write `- Not drawn: no runtime path or pipeline changes.`

## A template without the section

A team template that has no `## Implementation plan` keeps its shape (hard
rule 2): put `### Task flow` at the end of Core tasks, and `### Approach` and
`### Change flow` at the start of Notes, with the same content.

## How the implement flow uses it

The checkboxes stay the only progress mark: never mark progress inside a
diagram. An SB with no plan and no task flow runs in Core tasks order.

- **Order.** Task-flow order: a task comes after every task with a solid
  edge into it; otherwise Core tasks order.
- **Prerequisites.** Before a task, every task with a solid edge into it
  must be ticked, and every question with a dotted edge into it answered: a
  Questions item is answered once it is ticked `- [x]` or carries an answer
  after `→`, as roj-grill-plan writes them.
- **Departure.** The work departs from the plan when it would contradict the
  Approach, need an order or a prerequisite the task flow does not show, or
  change a runtime path differently from the change flow. A requested change
  at a review stop departs the same way.
- **Updating the plan.** Once the user agrees to a departure, write it into
  the section before the edit: the Approach bullet, the task flow's nodes and
  edges, or the change flow's steps, so the plan still says what is built.
  Edit the before/after table too when the departure changes an After value.
