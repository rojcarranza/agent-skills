# Using the roj-explain-logic skill

Guided, step-by-step code comprehension: PR/branch diffs, files, functions —
explained as Concept → Code flow → Why → Gotchas, with the matching language
lens (Java / Python / Go / shell / Bamboo API).

## Commands per platform

Copilot gets the `/roj-explain-code` and `/roj-explain-and-review` workflows
as generated skills in every project — `/roj-explain-code` in VS Code,
`/skill:roj-explain-code` in JetBrains (the skill itself is
`roj-explain-logic`). Claude Code has them as `/roj-explain-code` and
`/roj-explain-and-review` in both IDEs. Plain-English prompts work
everywhere; if the skill doesn't trigger, name it once ("Use the
roj-explain-logic skill to ...") — after one explicit use it picks up
reliably.

| Goal | Slash command | Plain chat / Claude Code |
|---|---|---|
| Understand a feature branch | `/roj-explain-code the changes in this branch vs main` | `Use the roj-explain-logic skill: walk me through the changes in this branch vs main` |
| Understand a PR | `/roj-explain-code PR #142` | `Use the roj-explain-logic skill: explain PR #142` |
| Understand a file | `/roj-explain-code src/foo/bar.py` | `Use the roj-explain-logic skill: explain the logic in src/foo/bar.py` |
| Understand a selection | select code → `/roj-explain-code` | select code → `Explain the logic in this selection step by step` |
| Understand + flag risks | `/roj-explain-and-review PR #142` | `Explain and review PR #142 — walkthrough first, then flag anything risky` |
| New repo, big picture first | `/roj-explain-code — onboard me to this repo first, then explain branch feature/x` | `Onboard me to this repo first, then explain branch feature/x` |
| Save as replayable tour | add `then create a code tour` to any prompt | same phrasing (needs CodeTour extension in VS Code) |
| Terse output (save tokens) | add `use caveman mode` to any prompt | `Caveman mode: explain the changes in this branch vs main` |

## Worked example

`/roj-explain-and-review PR #142` pulls the real diff, reads surrounding code,
callers, and tests, explains the change step by step, then a clearly
separated review phase rates findings 🔴 likely bug / 🟡 risky / 🟢 style.
