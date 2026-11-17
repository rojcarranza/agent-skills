# agent-skills — instructions for agents working in this repo

## Track every change with an issue

- Before implementing a change, create a GitHub issue (or user story) for
  it: a one-line user story ("As ..., I want ..., so that ..."), the
  background, checkable acceptance criteria and what is out of scope. If a
  matching open issue exists, use it instead of creating a duplicate.
- Title it `<type>(<scope>): <summary>` (Conventional Commits), with the same
  type as the branch and the PR: `feat(skills): ...`, `fix(install): ...`,
  `docs: ...`, `test: ...`, `chore: ...`. Lowercase, imperative, no trailing
  period. The commit subject and the PR title reuse the same line.
- Write the story for one user-visible outcome, small enough for one PR, and
  phrase each acceptance criterion so it can be checked yes or no.
- Create the issue first, then the branch, then the code. Do not start
  implementing until the issue exists.
- Mention the PR number in the issue.
- A change that grows beyond its acceptance criteria gets the issue updated
  first, then the code.

## Commits and pull requests

- Branch names are `<type>/<short-topic>`, matching the change:
  `feat/skills-inventory`, `fix/soundboarding-default-dir`, `docs/...`,
  `test/...`, `chore/...`. Never commit on a branch a session or harness
  named after itself (such as `<agent>/...`): create the descriptive branch
  first, even when the session or harness starts on another one.

## Changing skills

- Every `skills/<name>/SKILL.md` follows the Agent Skills spec; the rules
  are in README.md ("Writing or changing a skill") and enforced by
  `test_skills.py`.
- Shared files have one owner: edit the owner file listed in `tools/sync_shared.py`,
  then run `python3 tools/sync_shared.py` — never edit the copies in
  `roj-review-pr-comment`, `roj-explain-logic` or `roj-explain-my-branch`.
- No personal paths, real ticket IDs or employer details in `skills/`.
  Employer-specific patterns live in the git-ignored `.private-patterns`.
- A new skill is one PR: `skills/<name>/` and its `cali.yaml` entry
  (`source: .//skills/<name>`). This repo keeps no `cali.lock`: cali pins
  what a user loads in their own `cali.yaml` and `cali.lock`.

## Before pushing

```bash
python3 -m unittest test_install test_skills
python3 tools/sync_shared.py --check
```

Push through `git push no-mistakes <branch>`, never `origin`: the
`.no-mistakes.yaml` gates (the checks above, an installer smoke test and the skills
listing) run under Python 3.12 via `uv` on whichever computer does the work.
Run `/code-review` only on PRs that did not go through no-mistakes. The gates
cover only the computer they run on: before changing the installer, run the
commands above by hand on the other two of macOS, Ubuntu and Windows (Git Bash),
with Python 3.12 as CI did.
