---
mode: agent
description: 'Quick chat-only pass over the current branch diff — at most five findings, no report file, no tour'
---

Use the **code-review-pr-fast** skill for this task. Follow its full workflow.

Base: whichever branch I name, otherwise resolve it the way `code-review-pr`
does.

Requirements:
- Chat output only — write no file, run no command other than `git`
- Review the changed hunks only; read the whole file where context matters
- Nothing below Probable confidence; a Blocker must be Confirmed; cap at five
  findings
- End by stating what was skipped (callers, config-to-code coupling, tests)
- If this is going into a PR, or the diff touches Bamboo specs, Dockerfiles,
  Kubernetes manifests or Helm charts, say so and offer `code-review-pr`
  instead
