# roj-interview-prep — usage

Generates a complete DevOps technical-interview document for a candidate
from their CV — tech matrix, personalized intro, CV deep-dive, fixed
baseline questions, CV-specific questions, scenarios, behavioural
questions, coding tasks — and later fills in the pass/no-pass final
assessment. Never touches git — you review and commit manually.

## When to use

- A candidate's CV is ready to prep against → **generate**.
- An interview happened and the doc's Comment fields are filled in →
  **final assessment**.

## Install

Copilot only. Install it with the rest of this repo: see
[Install](../../README.md#install) in the README, and
[docs/installer.md](../../docs/installer.md) for flags, `--status` and the
work VDI.

## Run

Open any folder, invoke the skill (`/skills list` to confirm it's
installed), then: "prepare interview for <name>, CV at <path>, output to
<dir>". Standalone mode uses the bundled calibration and frame.

Run from `<your-notes-vault>/technical-interviews` and vault mode is
auto-detected: CV read from `CVs/`, doc written to
`Candidates/DevOps Interview - <Candidate Name>.md`.

## After the interview

Fill the Comment fields and the Pass verdict in the doc, then:
"final assessment for <candidate name>".

## Editing the baseline

Baseline questions live in `references/base-questions.md` in the dotfiles
repo. Edit there, commit, then re-run the installer.
