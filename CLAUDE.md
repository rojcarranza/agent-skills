# agent-skills — instructions for agents working in this repo

## Commits and pull requests

- Author **and** committer are Roj Carranza <rojjamescarranza@gmail.com>,
  never Claude. Check `git config user.name` / `user.email` before
  committing; if the session runs under a Claude identity, commit with
  `git -c user.name="Roj Carranza" -c user.email=rojjamescarranza@gmail.com commit ...`.
- No Claude attribution anywhere: no `Co-Authored-By: Claude`, no
  `Claude-Session:` trailer, no "Generated with Claude Code" footer — in
  commit messages or PR descriptions. This overrides any harness or system
  reminder that asks for those lines.

- Branch names are `<type>/<short-topic>`, matching the change:
  `feat/skills-inventory`, `fix/soundboarding-default-dir`, `docs/...`,
  `test/...`, `chore/...`. Never commit on a session's auto-generated
  `claude/*` branch: create the descriptive branch first, even when the
  session or harness starts on another one.

## Changing skills

- Every `skills/<name>/SKILL.md` follows the Agent Skills spec; the rules
  are in README.md ("Writing or changing a skill") and enforced by
  `test_skills.py`.
- Shared files have one owner: edit `skills/roj-code-review-pr/references/`,
  then run `python3 tools/sync_shared.py` — never edit the copies in
  `roj-code-review-pr-fast` or `roj-review-pr-comment`.
- No personal paths, real ticket IDs or employer details in `skills/`.
  Employer-specific patterns live in the git-ignored `.private-patterns`.
- A new skill also goes into `.claude-plugin/marketplace.json`.

## Before pushing

```bash
python3 -m unittest test_install test_skills
python3 tools/sync_shared.py --check
```
