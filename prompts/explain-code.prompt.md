---
mode: agent
description: 'Explain the logic of a PR, feature branch, file, or selection with a step-by-step walkthrough (Concept → Code flow → Why → Gotchas)'
---

Use the **explain-logic** skill for this task. Follow its full workflow.

Target to explain (in priority order):
1. If I selected code in the editor, explain that selection: ${selection}
2. If I mention a PR number or branch name in my message, pull the real diff first
3. Otherwise, ask me one question: "Which branch, PR, or file?"

Requirements:
- Comprehension only — no refactoring or improvement suggestions unless I ask
- Structure: big picture → execution flow in run order → why it works this way → gotchas
- Apply the language lens (Java / Python / Go / shell / Bamboo API) matching the code
- End by offering to save the walkthrough as a CodeTour if the code-tour skill is available
