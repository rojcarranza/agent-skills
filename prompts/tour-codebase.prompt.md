---
mode: agent
description: 'Onboard into this repository as a chained four-tour CodeTour series in .tours/, backed by docs/codebase/'
---

Use the **tour-codebase** skill for this task. Follow its full workflow.

Scope (in priority order):
1. Honour what I name in my message — a flow ("the auth flow"), a subset
   ("architecture only"), or an opt-out ("no docs")
2. If this is a monorepo, ask which workspace before starting
3. Otherwise tour the repository I have open

Requirements:
- Delegate discovery to `acquire-codebase-knowledge`; reuse an existing
  `docs/codebase/` unless I ask for a refresh
- Print the four-tour plan and stop for my approval — that is the only
  interactive stop
- Write the tours through `code-tour`, chained with `nextTour`, `ref` set to
  the current branch
- Validate every step's `file:line` before reporting
- Never edit this repository's `.gitignore` — print the `.git/info/exclude`
  line for `docs/codebase/` instead
