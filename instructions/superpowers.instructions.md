---
applyTo: "**"
description: Superpowers start-up note and tool map for Copilot Chat - loads using-superpowers in every chat.
---

# Superpowers

The Superpowers skills (version 7.0.0) are installed. At the start of every
chat, before your first answer or question, read the skill `using-superpowers`
(`~/.copilot/skills/using-superpowers/SKILL.md`) and follow it. It tells you to
check for a matching skill before acting.

Tool map. The skills name Claude Code's tools; use these in Copilot Chat:

- A reference such as `superpowers:writing-plans` means the skill
  `writing-plans`. Run a skill with the `/skill-name` command or by reading
  its `SKILL.md`, then follow it exactly.
- `Skill` tool: read the named skill's `SKILL.md` in
  `~/.copilot/skills/<name>/` (or the workspace's `.github/skills`) and follow
  it.
- `TodoWrite`: use Copilot's todo list. Without one, keep a checklist in your
  answer and tick it as you go.
- `Task` with a subagent: use a subagent or `runSubagent` when the chat offers
  it. Without one, do the work in this chat, step by step, and say so.
- `Read`, `Write`, `Edit`, `Bash`: use the matching file and terminal tools.
- Instructions in this note and in the user's other instructions win over a
  skill; a skill wins over default behaviour.
