# Using the roj-explain-logic skill

Guided, step-by-step code comprehension: PR/branch diffs, files, functions —
explained as Concept → Code flow → Why → Gotchas, with the matching language
lens (Java / Python / Go / shell / Bamboo API). Flows with three or more
moving parts come with a Mermaid diagram (`references/mermaid.md`).

## Commands per platform

Claude Code and VS Code Copilot: `/roj-explain-logic <request>`. JetBrains
Copilot: `/skill:roj-explain-logic <request>`. Plain English triggers it
everywhere; if it does not, name it once ("Use the roj-explain-logic skill
to ...").

| Goal | Request |
|---|---|
| Understand a feature branch | `/roj-explain-logic the changes in this branch vs main` |
| Understand a PR | `/roj-explain-logic PR #142` |
| Understand a file | `/roj-explain-logic src/foo/bar.py` |
| Understand a selection | select code → `Explain the logic in this selection step by step` |
| Understand + flag risks | `/roj-explain-logic explain and review PR #142` |
| New repo, big picture first | use `roj-tour-codebase` first, then `/roj-explain-logic branch feature/x` |
| Save as replayable tour | add `then create a code tour` (needs the CodeTour extension in VS Code) |
| Terse output (save tokens) | add `use caveman mode` |

## Worked example

`/roj-explain-logic explain and review PR #142` pulls the real diff, reads
surrounding code, callers, and tests, explains the change step by step, then
a clearly separated review phase rates findings 🔴 likely bug / 🟡 risky /
🟢 style.
