---
mode: agent
description: 'Review the current feature branch diff — change summary, severity/confidence-tagged findings, a -review.md report and a CodeTour'
---

Use the **code-review-pr** skill for this task. Follow its full workflow.

Base to review against (in priority order):
1. If I name a base branch in my message, diff against that
2. Otherwise resolve it: `origin/HEAD`, then `origin/main`, `origin/master`,
   `origin/develop`, then the local equivalents

Requirements:
- Git only — never call a GitHub or Bitbucket API, never read PR metadata,
  never post comments
- Three-dot diff: `git diff <base>...HEAD`
- Detect the stacks from the changed files, not from what the repository
  contains
- Defer to this repository's own conventions (CLAUDE.md, CONTRIBUTING.md,
  linter configs); do not report anything a configured linter already enforces
- Offer the verification commands as a table and wait for my approval — run
  nothing unapproved
- Every finding carries a severity and a confidence; a Blocker must be
  Confirmed; every Major or Blocker states a concrete failure scenario
- Write `<branch-slug>-review.md` at the repository root and the CodeTour
