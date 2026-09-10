---
mode: agent
description: 'Explain my feature branch against its base — what changed, why, how it works, before/after, code flow — plus PR-ready text and a CodeTour'
---

Use the **explain-feature-changes** skill for this task. Follow its full workflow.

Base branch (in priority order):
1. If I name a base branch in my message, compare against that
2. Otherwise `develop` (`origin/develop`, then local), then `main`
   (`origin/main`, then local)
3. If neither exists, ask me — do not guess

Requirements:
- Read-only: only `git` commands and file reads; never commit, push, reset,
  rebase, checkout or edit code
- Plain `git` commands only — no `$(...)`, pipes, `grep` or `sed` (the
  terminal may be PowerShell or cmd)
- Three-dot diff: `git diff <base>...HEAD`; committed work only — list
  uncommitted files in the report header
- Trace callers, callees, tests and configuration — do not just summarize
  the diff
- Label intent as confirmed, likely or unknown; never invent it
- Not a code review — only observations that change how the feature should
  be understood
- Write `<branch-slug>-changes.md` at the repository root and the CodeTour
