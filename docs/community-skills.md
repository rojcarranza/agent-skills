# Community skills

Every skill here is listed in [`cali.yaml`](../cali.yaml) — live ones install by
default, commented ones are optional: uncomment and re-run `install.py`.
Every live one installs for Copilot only (`targets: [copilot]`).
Sources: `github/awesome-copilot`, `juliusbrussee/caveman`,
`addyosmani/agent-skills`, `warpdotdev/common-skills`, `anthropics/skills`,
`vercel-labs/skills`, `pbakaus/impeccable` and `mattpocock/skills`. Each skill in `cali.yaml` gets a section here.

## code-tour
Creates CodeTour `.tour` walkthroughs through a repo, PR, or bug.
- `Create a code tour of the auth flow for a new joiner`
- `Make an RCA tour for the bug fixed in PR #97`

`roj-explain-logic`, `roj-investigate-issue`, `roj-soundboarding` and `roj-code-review-pr`
chain to this skill at the end of a run and fall back to writing a minimal
`.tour` inline when it is absent. `roj-tour-codebase` invokes it by name, once,
only when the reader asks for a tour of the core flow.

Upstream gotcha: its `SKILL.md` documents the bundled scripts at
`~/.agents/skills/code-tour/scripts/`, a path Cali does not create —
it lands in `~/.copilot/skills/code-tour/`. Resolve
`validate_tour.py` from the installed skill directory instead. The community
copy is deliberately not patched; a re-fetch would overwrite the change.

## acquire-codebase-knowledge
Maps and documents an existing codebase, writing seven documents into
`docs/codebase/`.
- `Map this codebase and create onboarding docs`

`roj-tour-codebase` no longer calls it: it owns the onboarding vocabulary
("onboard me", "tour this repo", "teach me how this works") and writes its own
guide in `.onboarding/`. An existing `docs/codebase/` is read as a lead and
cross-checked against the code. Reach for this skill directly when the seven
reference documents are wanted.

## context-map
Lists every file relevant to a task before changes are made.
- `Build a context map for adding rate limiting to the API`

## caveman
Terse-output mode — cuts output tokens while keeping technical substance.
- `Caveman mode: explain this build failure`
- Combine with other skills: `use caveman mode` appended to any prompt.

## debugging-and-error-recovery
Systematic debugging discipline: reproduce, isolate, fix, verify. From
`addyosmani/agent-skills`, Copilot only — on Claude the superpowers plugin's
`systematic-debugging` fills the same role.
- `Debug why the payment webhook test fails intermittently`

`roj-investigate-issue` hands phases 3–4 to it (or to `systematic-debugging`)
when present and keeps an inline hypothesis list otherwise.

## observability-and-instrumentation
Adds logging, metrics and tracing to code that lacks them. Cherry-pick from
`addyosmani/agent-skills`.
- `Add structured logging and metrics to the job runner`

## ci-cd-and-automation
Designs and fixes CI/CD pipelines. Cherry-pick from `addyosmani/agent-skills`.
- `Set up a GitHub Actions pipeline with test and release stages`

## security-and-hardening
Security review and hardening steps for code and config. Cherry-pick from
`addyosmani/agent-skills`.
- `Harden this Dockerfile and check the service for injection risks`

## deprecation-and-migration
Plans deprecations and migrations with compatibility windows. Cherry-pick
from `addyosmani/agent-skills`.
- `Plan the migration off the v1 config format`

## pdf
Reads, fills, merges and creates PDF files. Cherry-pick from
`anthropics/skills`, Copilot only (Claude has its own).
- `Merge these three PDFs and add page numbers`

## docx
Creates and edits Word documents. Cherry-pick from `anthropics/skills`.
- `Turn this interview guide into a Word document`

`roj-interview-prep` reads `.docx` CVs with its own text-extraction fallback
and never requires it.

## pptx
Creates and edits PowerPoint decks. Cherry-pick from `anthropics/skills`.
- `Make a five-slide deck from this design doc`

## xlsx
Creates and edits spreadsheets. Cherry-pick from `anthropics/skills`.
- `Build a spreadsheet comparing these three vendors`

## write-pr-description
Writes a PR body that gives the reviewer what the diff cannot: motivation,
behavior changes, decisions and blast radius. Repository PR templates win.
From `warpdotdev/common-skills` (MIT), fetched from its `.agents/skills/`
folder.
- `Write the PR description for this branch`

`roj-explain-feature-changes` requires it and hands it verified facts for the
PR Explanation section, skipping its `gh` steps. Without it,
`roj-explain-feature-changes` uses its own fallback rules.

## find-skills
Searches the open skills ecosystem (`npx skills find <query>`) when a task
might already have a skill. From `vercel-labs/skills` (MIT), via
`cali.yaml`.
- `Is there a skill for Terraform plan reviews?`
- `Find a skill for writing changelogs`

`roj-investigate-issue` (a stack outside its classes) and `roj-soundboarding`
(a story leaning on an uncovered stack) point at it and fall back to
suggesting `npx skills find <stack>` when it is absent. Neither installs
anything during a run.

Upstream gotcha: its last step offers `npx skills add <owner/repo@skill> -g -y`,
a one-off global install nothing here records. Treat that as a trial; to
keep a skill, add it to `cali.yaml` pinned to a commit, re-run `install.py` and
commit the entry with its `cali.lock` change. The community copy is deliberately not patched.

## impeccable
Designs, critiques and polishes frontend UI: layout, typography, color,
motion, UX copy, accessibility and design systems. From `pbakaus/impeccable`
(Apache-2.0), fetched from its `plugin/skills/` folder at tag `skill-v4.7.0`.
- `Critique the settings page and fix the visual hierarchy`
- `Polish this landing page`

Upstream gotcha: `scripts/impeccable` runs a native engine. Impeccable's own
installer copies it into `scripts/bin/<os>-<arch>/`, but the skill in git has
no binary. Installed through Cali, the launcher downloads the engine on first
use to `~/.impeccable/bin/<version>/`, which is outside the skill folder. The
skill folder stays byte-identical to the commit and under Cali's 10 MiB
per-file cap. Do not copy a binary into `scripts/bin/`: Cali can no longer
read the folder, and every `status`, `update` and `sync` fails on it.

Its long builds spawn shipped agents (`impeccable-finish-reviewer`,
`impeccable-documenter`, `impeccable-asset-producer`,
`impeccable-manual-edit-applier`). Those agents are not part of the skill
folder, and Cali does not install them. Without them the skill falls back to
its `reference/degraded/` in-thread passes. Agents left in `~/.claude/agents/`
by impeccable's own installer are not updated with the pinned skill.

## grilling
Interviews you about a plan, decision or idea in rounds: every question that
can be answered now, numbered, each with a recommended answer that "yes"
accepts. Looks facts up itself and leaves the decisions to you. From
`mattpocock/skills` (MIT), fetched from its `skills/productivity/` folder.
Cherry-pick: optional, uncomment it in `cali.yaml`.
- `Grill me on this migration plan`
- `Stress-test my idea for splitting the build agents`

`roj-grill-plan` uses the same round format for user stories and SB
documents and writes the answers back into the file; it works without this
skill installed.

## grill-me
Slash-only wrapper (`/grill-me`) that calls `grilling`. Claude only: its body
tells the agent to call the Skill tool, which Copilot does not have. Install
it together with `grilling`. Optional, from `mattpocock/skills`: uncomment it
in `cali.yaml`, its `targets: [claude]` line included.
- `/grill-me` followed by the plan

## to-questionnaire
Turns a decision you cannot answer alone into a Markdown questionnaire for
one person to fill in, written to `to-questionnaire-<slug>.md`. Optional, from
`mattpocock/skills`: uncomment it in `cali.yaml`.
- `Turn the open questions on the cache design into a questionnaire for the platform team`

`roj-grill-plan` offers it at the end of a run for questions only someone
else can answer, and lists them in chat when it is absent.

## superpowers
Brainstorming, planning, TDD, subagent-driven development and review skills
from [obra/superpowers](https://github.com/obra/superpowers) (MIT), installed
as a plugin rather than through `cali.yaml`.

`roj-idea-to-project` requires it and installs it on first run, after a yes:

- Claude Code: `claude plugin install superpowers@claude-plugins-official`;
  if that marketplace is not available, `claude plugin marketplace add
  obra/superpowers-marketplace`, then `claude plugin install
  superpowers@superpowers-marketplace`. Then `/reload-plugins`.
- Copilot CLI: `copilot plugin marketplace add obra/superpowers-marketplace`,
  then `copilot plugin install superpowers@superpowers-marketplace`, then
  restart `copilot`.

Copilot in VS Code and JetBrains is not supported yet: the skill folders
install through `cali.yaml` at a pinned commit, but Superpowers ships no
Copilot tool map and its session-start bootstrap does not run from a
skills-only install. Curated marketplaces can lag behind the latest release
(v7.0.0 rebuilt brainstorming); the skill offers `claude plugin update`.
