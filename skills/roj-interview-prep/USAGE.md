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

Any agent, with Node.js:

    npx skills add rojcarranza/agent-skills -s roj-interview-prep

Or from a clone of this repo (adds the skills it depends on, plus the
Windows copy fallback):

    python3 install.py --target claude    # mac / Claude Code
    python3 install.py --target copilot   # work / GitHub Copilot
    python3 install.py --target both

Claude gets a symlink (edit the repo, changes are live); Copilot gets a copy
(re-run install after edits).

## Run — Claude Code (mac, inside the vault)

    cd <your-notes-vault>/technical-interviews
    claude
    > prepare interview for <candidate name>

Vault mode auto-detected: CV read from `CVs/`, doc written to
`Candidates/DevOps Interview - <Candidate Name>.md`.

## Run — Copilot (work)

Open any folder, invoke the skill (`/skills list` to confirm it's
installed), then: "prepare interview for <name>, CV at <path>, output to
<dir>". Standalone mode uses the bundled calibration and frame.

## After the interview

Fill the Comment fields and the Pass verdict in the doc, then:
"final assessment for <candidate name>".

## Editing the baseline

Baseline questions live in `references/base-questions.md` in the dotfiles
repo. Edit there, commit, re-run install for Copilot (Claude symlink picks
it up automatically).
