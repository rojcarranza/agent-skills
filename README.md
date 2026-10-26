# agent-skills

Agent skills for code review, code comprehension, repository onboarding,
root-cause investigation and DevOps team workflows. Each skill is one
self-contained [Agent Skills](https://agentskills.io/specification) folder,
so the same `SKILL.md` serves Claude Code, GitHub Copilot (VS Code and
JetBrains) and any other agent the [`skills`](https://skills.sh) CLI
supports.

## Install

**Everything, with Cali (recommended)** — my skills, the community skills
they chain to, personal instructions and the GitHub MCP server, for
Copilot (`roj-idea-to-project` also for Claude Code). The skills are listed in one manifest
([`cali.yaml`](cali.yaml), pinned in [`cali.lock`](cali.lock)) and
installed by [Cali](https://github.com/rojcarranza/cali).

1. Install `cali` from a clone of its repo (`make install`, or
   `sh scripts/install.sh` on Git Bash). `install.py` cannot install it for
   you: it stops and prints those commands when `cali` is missing.
2. Clone this repo and run the installer:

   ```bash
   git clone https://github.com/rojcarranza/agent-skills && cd agent-skills
   python3 install.py --target both        # or claude / copilot
   python3 install.py --status             # what is installed where
   python3 install.py --update             # which skills have newer versions
   ```

   On Windows use Git Bash and `python`; on WSL run it inside WSL, and
   again from Git Bash for Windows-side VS Code and JetBrains.
   `install.py` runs `cali sync -g --manifest <clone>/cali.yaml`, writes the
   personal instructions and the GitHub MCP server entry, and installs
   `graphify` (a CLI Cali does not install).

   The GitHub MCP server is added only when a GitHub login exists:
   `$token`, else `gh auth token` when the GitHub CLI is logged in. With
   neither (a work machine on Bitbucket, say) it installs skills and
   instructions only and skips MCP servers — no prompt, nothing to
   remember. The first run also removes the entries older versions of
   `install.py` and APM left for skills Cali installs again, and warns
   about the rest.

To add or drop a skill, edit `cali.yaml` and re-run `install.py`.
`install.py --update` lists skills with newer upstream versions; bump the
SHA in `cali.yaml`, then `cali update -g --manifest cali.yaml --apply`.

**Only some skills, with Node.js** — `npx skills add rojcarranza/agent-skills`
(interactive), or `-s <skill> -a github-copilot -g`. Only
`roj-idea-to-project` also supports Claude Code (`-a claude-code github-copilot`).

**Claude Code plugin** — `/plugin marketplace add rojcarranza/agent-skills`,
then `/plugin install roj-skills@roj-agent-skills`. The plugin carries only
`roj-idea-to-project`, the one skill that supports Claude; the rest are for
Copilot. Plugin skills are namespaced (`/roj-skills:roj-idea-to-project`).

Use one route per machine: a plugin plus a skills-dir install lists each skill twice.

**In a team repository** — add an `apm.yml` to that repo listing the skills
it needs, e.g. `rojcarranza/agent-skills/skills/roj-code-review-pr#<commit>` (pin a commit), and
run `apm install`. Commit `apm.yml` and `apm.lock.yaml`; teammates run
`apm install` after cloning.

Every flag, the manifest, externals (`graphify`), the Windows VDI and
JetBrains setup are in [docs/installer.md](docs/installer.md).

Putting a repo behind local `no-mistakes` gates, and updating the pinned
tools, is in [docs/workflow.md](docs/workflow.md).

## Skills

| Skill | What it does |
| --- | --- |
| [`roj-code-review-pr`](skills/roj-code-review-pr/USAGE.md) | Reviews a branch, a teammate's branch or a Bitbucket Data Center PR, without a checkout: `auto` picks a quick chat-only pass or a full review (change summary, severity/confidence-tagged findings, a `-review.md` report) from the size and risk of the diff. Optional intent source (PR text, Jira story, SB acceptance criteria). Loads language/platform rules (Java, Python, Bash, Go, Bamboo, Docker, k8s, Helm) only for stacks the diff touches. Git-only. |
| [`roj-review-pr-comment`](skills/roj-review-pr-comment/USAGE.md) | Reviews a Bitbucket Data Center PR with the same method, fetched by ref with no checkout, and drafts the findings as pasteable `path:line` comments. Posts them through the Bitbucket REST API only when asked and a `BITBUCKET_TOKEN` is set. The only skill that writes to the PR host. |
| [`roj-explain-logic`](skills/roj-explain-logic/USAGE.md) | Guided walkthrough of a PR, branch, file or function: big picture → execution flow → why → gotchas, with language lenses. Optional explain-and-review mode. |
| [`roj-explain-feature-changes`](skills/roj-explain-feature-changes/USAGE.md) | Explains your own branch against `develop`/`main` with traced before/after behaviour, then writes PR-ready text and per-change comments. |
| [`roj-tour-codebase`](skills/roj-tour-codebase/USAGE.md) | Onboarding into an unfamiliar repo: a Markdown guide in `.onboarding/` with Mermaid diagrams of the architecture and a core flow, a code walkthrough anchored to `path:line`, a reading order, and a page on reviewing a colleague's PR. Stops on a failed read instead of guessing. CodeTour only on request. |
| [`roj-investigate-issue`](skills/roj-investigate-issue/USAGE.md) | Problem `.md` in, validated root cause and fix steps out (Bamboo, Java, Python, Bash, Go, Docker, k8s). |
| [`roj-soundboarding`](skills/roj-soundboarding/USAGE.md) | User story (file, pasted Jira text or Jira key) → code-investigated SB document → task-by-task implementation with review stops. Never touches git. |
| [`roj-grill-plan`](skills/roj-grill-plan/USAGE.md) | Grills a story, SB document or plan in rounds of questions with recommended answers, looks facts up itself, then writes the decisions back into the file. |
| [`roj-idea-to-project`](skills/roj-idea-to-project/USAGE.md) | Raw app idea → brief, design, EARS requirements, architecture and ADRs, agent config and a checked Definition of Ready, one approved gate at a time with fresh-context reviews, then a hand-off to Superpowers. Installs Superpowers first when it is missing. Never touches git. |
| [`roj-interview-prep`](skills/roj-interview-prep/USAGE.md) | DevOps technical-interview document generated from a candidate's CV. |

Diagrams are always Mermaid: `roj-tour-codebase` puts a system map and a
core-flow diagram in `.onboarding/README.md`, and the explain skills draw
flows and before/after structure the same way. GitHub renders them; VS Code
1.121 and later renders them in the built-in Markdown preview, JetBrains in
the Markdown preview with its Mermaid plugin ticked.

Skills that read code ask a [graphify](docs/installer.md#how-our-skills-use-the-graph)
graph first when the repo has one (`graphify-out/`), and read only the files
it points at — fewer tokens on large repos. Build one per repo with
`graphify update .` (code only, no LLM).

Walkthrough skills **offer** a CodeTour at the end of a run and write one
into `.tours/` only on a yes, chaining to the community `code-tour` skill.
`roj-tour-codebase` follows the same rule: its output is the `.onboarding/`
guide, and a tour is written only when asked.

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
cali.yaml         every skill and community skill install.py installs (Cali manifest)
cali.lock         the tree each of them is pinned to (and commit, for community skills)
.apm/instructions/  personal instructions install.py deploys to Copilot
tools/            sync_shared.py — copies shared files into every skill using them
install.py        runs cali sync, deploys instructions and MCP servers, installs graphify (docs/installer.md)
test_install.py   installer tests
test_skills.py    spec, publishing, evals and description-routing checks
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
- A new skill is one PR: the `skills/<name>/` folder, its
  `.claude-plugin/marketplace.json` entry, its `cali.yaml` entry
  (`source: .//skills/<name>`) and its `cali.lock` entry. Commit the skill,
  then run `cali sync -g --manifest cali.yaml` to write the lock entry and
  commit that too; a test fails until all four are in.
- A change to an existing skill moves its tree: commit it, then run
  `cali update -g --manifest cali.yaml --apply` and commit the `cali.lock`
  change in the same PR. A test fails until you do.

## Tests

```bash
python3 -m unittest test_install test_skills test_idea_to_project -v
python3 tools/sync_shared.py --check
npx skills add . --list               # what skills.sh will discover
```

The no-mistakes gate runs all three on every push (GitHub Actions is off, see
[docs/workflow.md](docs/workflow.md)).

### Evals

`evals/<skill>/` holds [skill-creator](https://github.com/anthropics/claude-plugins-official/tree/main/plugins/skill-creator)
eval sets, kept outside `skills/` so no install ships them. Every skill
needs both files, and `test_skills.py` also fails when two descriptions
route one trigger phrase ambiguously:

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
python3 evals/fixtures/fake_bitbucket.py /tmp/run-1 <fixture.bitbucket> &   # PR-comment evals only
```

The fake Bitbucket serves PR 7 of `APP/uploader` from that repository on
127.0.0.1 and prints `BITBUCKET_URL=http://127.0.0.1:<port>`; export that and
`BITBUCKET_TOKEN=test-token` for the run. It records every request line and
the comments it accepts under `/tmp/run-1/bb-state/` instead of reaching a
real server; stop it afterwards and grade from those files.

`test_skills.py` checks that every fixture builds and the files' shape,
not the scores.

## License

[MIT](LICENSE)
