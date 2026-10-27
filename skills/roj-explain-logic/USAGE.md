# Using the roj-explain-logic skill

Guided, step-by-step code comprehension: PR/branch diffs, files, functions —
explained as Concept → Code flow → Why → Gotchas, with the matching language
lens (Java / Python / Go / shell / Bamboo API). Flows with three or more
moving parts come with a Mermaid diagram (`references/mermaid.md`). A PR or
a branch is written down instead: a brief with a diagram of what the change
touches and a page to open in a browser or the IDE preview (below).

## Commands per platform

VS Code Copilot: `/roj-explain-logic <request>`. JetBrains
Copilot: `/skill:roj-explain-logic <request>`. Plain English triggers it
everywhere; if it does not, name it once ("Use the roj-explain-logic skill
to ...").

| Goal | Request |
|---|---|
| Understand a feature branch | `/roj-explain-logic the changes in this branch vs main` |
| Understand a PR | `/roj-explain-logic PR #142` (a Bitbucket Data Center PR id or URL is fetched without a checkout) |
| Brief before reviewing | `/roj-explain-logic brief me on PR 42 before I review it` writes `.pr-review/pr-42/brief.md` and `brief.html` |
| Understand a file | `/roj-explain-logic src/foo/bar.py` |
| Understand a selection | select code → `Explain the logic in this selection step by step` |
| Understand + flag risks | `/roj-explain-logic explain and review PR #142` |
| New repo, big picture first | use `roj-onboard-repo` first, then `/roj-explain-logic branch feature/x` |
| Save as replayable tour | add `then create a code tour` (needs the CodeTour extension in VS Code) |
| Terse output (save tokens) | add `use caveman mode` |

## The PR brief

For a PR or a branch the walkthrough is a file, not a chat answer:
`.pr-review/pr-<n>/brief.md` (branches: `.pr-review/branch-<slug>/`) and
`brief.html`, the same content as one self-contained page. The brief has seven
sections in a fixed order: what the PR does (and a claims check when the PR
text and the diff disagree), where it sits, a flow diff, the files, the
walkthrough, a reading order, and questions for the author with what was not
checked. The flow diff is a Mermaid sequence diagram of only the changed
steps: green is new, amber changed, red removed, and every step also carries a
`+` `~` `-` tag so it reads without colour. A PR that only changes docs, tests,
comments or formatting gets `No flow change` and no diagram.

Open `brief.html` in a browser (or in Lavish when `lavish-axi` is installed);
open `brief.md` in the IDE preview (JetBrains needs the *Mermaid* plugin
ticked). Chat gets a summary of at most 12 lines and the next command:
`roj-code-review-pr`. The brief holds no defects and no advice, and
`.pr-review/` stays out of Git (the skill prints the `.git/info/exclude` line
and never runs it). A Bitbucket Data Center PR has no title or description
without REST, so the brief uses the commit messages unless you paste the PR
text.

## Worked example

`/roj-explain-logic explain and review PR #142` pulls the real diff, reads
surrounding code, callers, and tests, explains the change step by step, then
a clearly separated review phase applies the shared review method of
`roj-code-review-pr`: findings carry a severity (Blocker / Major / Minor /
Nit) and a confidence (Confirmed / Probable), and a Major or Blocker states
the concrete input that fails.

## Repo map (optional)

When the repository has an `.onboarding/` guide (`roj-onboard-repo` writes
it), the big picture names the areas, flows and dependents the change
touches, and says how fresh the guide is: `Repo map: .onboarding @ a1b2c3d
(fresh) - areas: uploads`. The guide only orients the walkthrough; every step
still cites the code, and the code wins when the two disagree.
