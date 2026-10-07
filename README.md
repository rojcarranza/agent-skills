# agent-skills

Agent skills for code review, code comprehension, repository onboarding,
root-cause investigation and DevOps team workflows. Each skill is one
self-contained [Agent Skills](https://agentskills.io/specification) folder,
so the same `SKILL.md` serves Claude Code, GitHub Copilot (VS Code and
JetBrains) and any other agent the [`skills`](https://skills.sh) CLI
supports.

## Install

**Any agent, with Node.js** — pick skills and agents interactively, or name
them:

```bash
npx skills add r0jjames/agent-skills                     # interactive
npx skills add r0jjames/agent-skills --list              # what is in here
npx skills add r0jjames/agent-skills -s roj-code-review-pr -a claude-code github-copilot -g
npx skills update                                        # pull new versions
```

**Claude Code plugin** — all skills as one plugin, updated through
`/plugin`:

```text
/plugin marketplace add r0jjames/agent-skills
/plugin install roj-skills@roj-agent-skills
```

Plugin skills are namespaced (`/roj-skills:roj-code-review-pr`). Use either
the plugin or a skills-dir install, not both — `install.py --status` flags
duplicates.

**Full setup from a clone** — custom skills plus the community skills and
CLI-installed tools they chain to, with the Windows copy fallback and team
repo seeding. Python >= 3.8, no dependencies:

```bash
python3 install.py --target claude    # symlinks into ~/.claude/skills
python3 install.py --target copilot   # copies into ~/.copilot/skills
python3 install.py --target both
python3 install.py                    # interactive picker
python3 install.py --list             # everything installable
python3 install.py --target claude --skill roj-code-review-pr   # just one
python3 install.py --status           # what is installed where + conflicts
python3 install.py --repo .           # seed .github/skills for the team
```

Every flag, the community skill list, externals (`graphify`), the Windows
VDI and JetBrains setup are in [docs/installer.md](docs/installer.md).

## Skills

| Skill | What it does |
| --- | --- |
| [`roj-code-review-pr`](skills/roj-code-review-pr/USAGE.md) | Reviews the current feature branch before or after a PR: change summary, severity/confidence-tagged findings and a `-review.md` report. Loads language/platform rules (Java, Python, Bash, Go, Bamboo, Docker, k8s, Helm) only for stacks the diff touches. Git-only. |
| [`roj-code-review-pr-fast`](skills/roj-code-review-pr-fast/USAGE.md) | Chat-only quick pass over the same diff, `git` calls only, nothing written. |
| [`roj-review-pr-comment`](skills/roj-review-pr-comment/USAGE.md) | Reviews an open GitHub PR with the same method and posts one `COMMENT` review with inline comments via `gh`. The only skill that writes to the PR host. |
| [`roj-explain-logic`](skills/roj-explain-logic/USAGE.md) | Guided walkthrough of a PR, branch, file or function: big picture → execution flow → why → gotchas, with language lenses. Optional explain-and-review mode. |
| [`roj-explain-feature-changes`](skills/roj-explain-feature-changes/USAGE.md) | Explains your own branch against `develop`/`main` with traced before/after behaviour, then writes PR-ready text and per-change comments. |
| [`roj-tour-codebase`](skills/roj-tour-codebase/USAGE.md) | Onboarding into an unfamiliar repo: a discovery pass, then a chained four-tour CodeTour series in `.tours/`. |
| [`roj-investigate-issue`](skills/roj-investigate-issue/USAGE.md) | Problem `.md` in, validated root cause and fix steps out (Bamboo, Java, Python, Bash, Go, Docker, k8s). |
| [`roj-soundboarding`](skills/roj-soundboarding/USAGE.md) | User story → code-investigated SB document → task-by-task implementation with review stops. Never touches git. |
| [`roj-interview-prep`](skills/roj-interview-prep/USAGE.md) | DevOps technical-interview document generated from a candidate's CV. |

Diagrams are always Mermaid: `roj-tour-codebase` puts a layer and a
core-flow diagram in `docs/codebase/ARCHITECTURE.md`, and the explain skills
draw flows and before/after structure the same way. GitHub renders them; VS
Code needs `bierner.markdown-mermaid`, JetBrains its Markdown Mermaid option.

Walkthrough skills **offer** a CodeTour at the end of a run and write one
into `.tours/` only on a yes, chaining to the community `code-tour` skill.
`roj-tour-codebase` is the exception: its tours are the output.

Community skills these chain to (`code-tour`, `acquire-codebase-knowledge`,
`write-pr-description`, ...) are described in
[docs/community-skills.md](docs/community-skills.md). Every skill degrades
to an inline fallback when a community skill is missing.

## Repository layout

```text
skills/<name>/
  SKILL.md        frontmatter (name, description, license) + instructions, < 500 lines
  USAGE.md        human guide: commands per agent, worked example
  references/     detail the agent loads on demand
  assets/         templates the skill fills in
  examples/       sample inputs and outputs
.claude-plugin/   marketplace.json — the Claude Code plugin view of skills/
tools/            sync_shared.py — copies shared files into every skill using them
install.py        full installer (see docs/installer.md)
test_install.py   installer tests
test_skills.py    spec + publishing checks for every skill
```

## Writing or changing a skill

- Follow the [Agent Skills spec](https://agentskills.io/specification): the
  `name` matches the folder, lowercase with hyphens and a `roj-` prefix; the
  `description` says what the skill does **and** when to use it, under
  1024 characters. Quote a value containing ` #` or `: `.
- Keep `SKILL.md` lean — every installed skill's description loads into
  every session, and the body loads in full on activation. Push detail into
  `references/` and point at it with a path relative to the skill root.
- A skill reads only its own folder. When two skills need the same file,
  the owner keeps it and `tools/sync_shared.py` copies it in — edit the
  owner's copy, then run `python3 tools/sync_shared.py`.
- No personal paths, ticket IDs or employer details — use placeholders
  (`PROJ-123`, `$SOUNDBOARD_DIR`). Put employer-specific strings in a
  git-ignored `.private-patterns` file (one regex per line) and the tests
  check for them locally.
- Add a new skill to `.claude-plugin/marketplace.json`; a test fails until
  you do.

## Tests

```bash
python3 -m unittest test_install test_skills -v
python3 tools/sync_shared.py --check
npx skills add . --list               # what skills.sh will discover
```

CI runs all three on every push and pull request.

## License

[MIT](LICENSE)
