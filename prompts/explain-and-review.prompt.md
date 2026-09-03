---
mode: agent
description: 'Explain the logic of a PR, feature branch, file, or selection step by step, THEN review it for risky logic, bugs, and edge cases'
---

Use the **explain-logic** skill in explain-and-review mode. Two phases, in this order:

## Phase 1 — Explain (comprehension first)
Follow the explain-logic skill workflow fully:
big picture → execution flow in run order → why it works this way → gotchas.
Apply the matching language lens (Java / Python / Go / shell / Bamboo API).

Target (in priority order):
1. If I selected code in the editor, explain that selection: ${selection}
2. If I mention a PR number or branch name, pull the real diff first
3. Otherwise, ask me one question: "Which branch, PR, or file?"

## Phase 2 — Review (only after I understand it)
Now switch hats and review the SAME code:
- **Logic risks**: off-by-one, wrong boundary conditions, inverted conditions, unhandled states
- **Error handling**: swallowed exceptions, bare excepts, missing error propagation, shell commands that fail silently
- **Edge cases**: empty input, nulls/zero values, concurrent execution, retries, timeouts
- **Side-effect risks**: partial writes, non-idempotent operations, CI/CD runtime impact
- Rate each finding: 🔴 likely bug / 🟡 risky, verify / 🟢 style-level

Rules:
- Keep the two phases clearly separated with headers — never mix review comments into the explanation
- Every finding must reference the specific line(s) and say WHY it is risky, not just what to change
- If the code is solid, say so — do not invent findings to fill space
