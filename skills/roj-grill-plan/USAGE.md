# Using the roj-grill-plan skill

Stress-tests a user story, an SB document or a plan before anyone
implements it. The agent asks in rounds: every question it can ask now,
numbered, each with a recommended answer that "yes" accepts. It looks facts
up in the repo itself and only asks you for decisions. At the end it writes
the agreed answers back into the file, after you confirm. Never touches git.

The round format comes from `grilling` in
[mattpocock/skills](https://github.com/mattpocock/skills) (MIT). This skill
adds the story and SB input, the write-back, and works without `grilling`
installed.

## When to use

- An SB document has a long Questions section → resolve it before
  `/roj-soundboarding implement`.
- A story's acceptance criteria are vague → pin them down before
  soundboarding.
- You have a plan in your head or in chat → find the decisions you skipped.

## Commands per platform

Claude Code and VS Code Copilot: `/roj-grill-plan <request>`. JetBrains
Copilot: `/skill:roj-grill-plan <request>`. Plain English works everywhere.

| Goal | Request |
|---|---|
| Resolve an SB's open questions | `/roj-grill-plan SB-PROJ-1001` |
| Sharpen a story | `/roj-grill-plan PROJ-1001.md` |
| Stress-test a plan in chat | `/roj-grill-plan` followed by the plan |
| Straight after soundboarding | answer yes to "Grill the open questions now?" |

## Answering a round

- `yes to all`: accept every recommendation in the round.
- `Q2 no, use 5 retries`: override one answer.
- `skip Q3`: keep it open; it is written back as open.
- `stop`: end the session and go to the summary.

## Output

- **SB document**: the Questions section becomes a checklist. Resolved items
  are ticked with `→ <answer>`; open ones are tagged `(open: ...)` or
  `(needs: <role>)`. Changes to other sections are proposed and applied only
  on a separate yes.
- **Story**: a `## Decisions` section at the end.
- **Plan in chat**: a decision log in chat, no file.

Items only someone else can answer can go into a questionnaire through
`to-questionnaire` (a cherry-pick in `install.py`). See
[examples/grill-round.md](examples/grill-round.md) for a full session.
