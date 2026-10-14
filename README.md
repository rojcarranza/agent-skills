# agent-skills

Agent skills for code review, code comprehension, repository onboarding,
root-cause investigation and DevOps team workflows. Each skill is one
self-contained [Agent Skills](https://agentskills.io/specification) folder,
so the same `SKILL.md` serves Claude Code, GitHub Copilot (VS Code and
JetBrains) and any other agent the [`skills`](https://skills.sh) CLI
supports.

## Install

**Everything, with APM (recommended)** — my skills, the community skills
they chain to, personal instructions and MCP servers, for Claude Code and
Copilot, from one manifest ([`apm.yml`](apm.yml)).

1. Install [APM](https://microsoft.github.io/apm/getting-started/installation/):

   ```bash
   brew install apm                        # macOS / Linux
   python3 -m pip install apm-cli          # anywhere with Python 3.10+
   winget install --id Microsoft.APM --exact --source winget   # Windows
   ```

2. Clone and install:

   ```bash
   git clone https://github.com/rojcarranza/agent-skills && cd agent-skills
   python3 install.py --target both        # or claude / copilot
   python3 install.py --status             # what is installed where
   python3 install.py --update             # which pins have newer releases
   ```

   On Windows use Git Bash and `python`; on WSL run it inside WSL, and
   again from Git Bash for Windows-side VS Code and JetBrains.
   `install.py` writes `~/.apm/apm.yml` pointing at this clone, runs `apm install -g`,
   and installs `graphify` (a CLI APM cannot package).

   On the first run APM asks for a `token` value for the GitHub MCP server
   (a GitHub token). In a non-interactive shell set `token=...` in the
   environment first. The first run also removes the entries older versions
   of `install.py` left behind.

To add or drop a skill or MCP server, edit `apm.yml` and re-run
`install.py`. `install.py --update` lists pins with newer upstream
releases; bump the SHA in `apm.yml` and re-run.

**Only some skills, with Node.js** — `npx skills add rojcarranza/agent-skills`
(interactive), or `-s <skill> -a claude-code github-copilot -g`.

**Claude Code plugin** — `/plugin marketplace add rojcarranza/agent-skills`,
then `/plugin install roj-skills@roj-agent-skills`. Plugin skills are
namespaced (`/roj-skills:roj-code-review-pr`).

Use one route per machine — `install.py --status` flags duplicates.

**In a team repository** — add an `apm.yml` to that repo listing the skills
it needs, e.g. `rojcarranza/agent-skills/skills/roj-code-review-pr#<commit>` (pin a commit), and
run `apm install`. Commit `apm.yml` and `apm.lock.yaml`; teammates run
`apm install` after cloning.

Every flag, the manifest, externals (`graphify`), the Windows VDI and
JetBrains setup are in [docs/installer.md](docs/installer.md).

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

Skills that read code ask a [graphify](docs/installer.md#how-our-skills-use-the-graph)
graph first when the repo has one (`graphify-out/`), and read only the files
it points at — fewer tokens on large repos. Build one per repo with
`graphify update .` (code only, no LLM).

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
apm.yml           every skill, community skill and MCP server install.py installs (APM manifest)
.apm/instructions/  personal instructions APM deploys to Copilot and Claude
tools/            sync_shared.py — copies shared files into every skill using them
install.py        writes ~/.apm/apm.yml, runs apm install -g, installs graphify (docs/installer.md)
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
  Keep references one level deep — a reference file may name a sibling only
  when `SKILL.md` names it too — and open any reference over 100 lines with
  a `## Contents` list.
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

### Evals

`evals/<skill>/` holds [skill-creator](https://github.com/anthropics/claude-plugins-official/tree/main/plugins/skill-creator)
eval sets, kept outside `skills/` so no install ships them:

- `triggers.json` — realistic prompts marked `should_trigger`, mostly
  near-misses aimed at sibling skills, to test the `description`.
- `evals.json` — behaviour checks in skill-creator's schema.

Run a trigger set from an empty scratch directory with its own `.claude/`
— the runner writes temporary command files into the nearest one, which
is otherwise `~/.claude/`. It calls `claude -p` once per query, so it costs
tokens:

```bash
mkdir -p /tmp/skill-evals/.claude && cd /tmp/skill-evals
PYTHONPATH=<skill-creator dir> python3 -m scripts.run_eval \
  --eval-set <repo>/evals/<skill>/triggers.json \
  --skill-path <repo>/skills/<skill> --num-workers 1
```

Keep `--num-workers 1`: every worker drops a copy of the skill into the
same `.claude/commands/`, so parallel runs see several identical skills,
invoke another worker's copy and score a miss. A skill you already have
installed competes with its own copy, so its should-trigger scores read
low.

`run_eval` reads only `triggers.json`. Behaviour checks in `evals.json`
run through the skill-creator skill itself: ask Claude, with skill-creator
loaded, to run `evals/<skill>/evals.json` against `skills/<skill>`. It
runs each prompt with and without the skill, grades the outputs against
`expectations`, and opens its review viewer.

Each behaviour eval names the repository it runs in under `fixture`.
Build a fresh one per run, so no run sees another's output:

```bash
evals/fixtures/build.sh <fixture.repo> /tmp/run-1          # repo at /tmp/run-1/repo
evals/fixtures/fake-gh.sh /tmp/run-1 <fixture.gh>          # PR-comment evals only
```

The fake `gh` serves PR #123 from that repository and records every call
and review POST under `/tmp/run-1/gh-state/` instead of reaching GitHub;
put `/tmp/run-1/bin` first on the run's `PATH` and grade from those files.

`test_skills.py` checks that every fixture builds and the files' shape,
not the scores.

## License

[MIT](LICENSE)
