---
agent: agent
description: Create a soundboarding document from a user story, then immediately implement its core tasks
---

# /create-implement-sb — Create and Implement in One Run

Combined flow for stories where team refinement between soundboarding and implementation is skipped. This prompt chains the two other soundboarding prompts; it defines no behavior of its own beyond the chaining and one confirmation gate.

## Configuration

- SOUNDBOARD_DIR: `/c/dev/projects/wr/soundboard`

This path is a default, not a requirement — override SOUNDBOARD_DIR by stating a different path in your message.

## Steps

1. Read `SOUNDBOARD_DIR/prompts/create-sb.prompt.md` and execute its instructions, treating the user's message as the user story input. If that file cannot be read: STOP and ask — do not improvise the create phase.
2. When the SB file has been written, present a short summary of it and ask exactly one confirmation question: "SB created — proceed with implementation?" Wait for the answer. If the user declines, stop here; the SB file stays as created.
3. On confirmation, read `SOUNDBOARD_DIR/prompts/implement-sb.prompt.md` and execute its instructions on the SB file you just created — including every per-task review stop and the no-git rule. If that file cannot be read: STOP and ask.
