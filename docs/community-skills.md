# Community skills

Every skill here is listed in [`apm.yml`](../apm.yml) — live ones install by
default, commented ones are optional: uncomment and re-run `install.py`.
Sources: `github/awesome-copilot`, `juliusbrussee/caveman`,
`addyosmani/agent-skills`, `warpdotdev/common-skills`, `anthropics/skills`,
`vercel-labs/skills` and `mattpocock/skills`. Each skill in `apm.yml` gets a section here.

## code-tour
Creates CodeTour `.tour` walkthroughs through a repo, PR, or bug.
- `Create a code tour of the auth flow for a new joiner`
- `Make an RCA tour for the bug fixed in PR #97`

`roj-explain-logic`, `roj-investigate-issue`, `roj-soundboarding` and `roj-code-review-pr`
chain to this skill at the end of a run and fall back to writing a minimal
`.tour` inline when it is absent. `roj-tour-codebase` drives it four times in one
run, for a chained series.

Upstream gotcha: its `SKILL.md` documents the bundled scripts at
`~/.agents/skills/code-tour/scripts/`, a path APM does not create for Claude —
skills land in `~/.claude/skills/` (Copilot: `~/.agents/skills/`). Resolve
`validate_tour.py` from the installed skill directory instead. The community
copy is deliberately not patched; a re-fetch would overwrite the change.

## acquire-codebase-knowledge
Maps and documents an existing codebase, writing seven documents into
`docs/codebase/`.
- `Map this codebase and create onboarding docs`

`roj-tour-codebase` calls it as its discovery phase and owns the onboarding
vocabulary ("onboard me", "tour this repo", "teach me how this works"). Reach
for this skill directly only when documents are wanted without tours.

## context-map
Lists every file relevant to a task before changes are made.
- `Build a context map for adding rate limiting to the API`

## architecture-blueprint-generator
Generates an architecture blueprint (stack detection, patterns, diagrams).
- `Generate an architecture blueprint for this repo`

## add-educational-comments
Adds explanatory comments to a file for learning purposes.
- `Add educational comments to src/scheduler.py`

## arch-linux-triage
## centos-linux-triage
## debian-linux-triage
## fedora-linux-triage
Host diagnosis for one Linux distribution: services, packages, logs,
networking. Cherry-picks from `github/awesome-copilot` — install the one
matching your build agents.
- `Triage why the docker service keeps restarting on this Debian agent`

`roj-investigate-issue` names the matching one in its Solution when a root
cause sits on the agent host; it never requires them.

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
`anthropics/skills`.
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
`apm.yml`.
- `Is there a skill for Terraform plan reviews?`
- `Find a skill for writing changelogs`

`roj-investigate-issue` (a stack outside its classes) and `roj-soundboarding`
(a story leaning on an uncovered stack) point at it and fall back to
suggesting `npx skills find <stack>` when it is absent. Neither installs
anything during a run.

Upstream gotcha: its last step offers `npx skills add <owner/repo@skill> -g -y`,
a one-off global install nothing here records. Treat that as a trial; to
keep a skill, add it to `apm.yml` pinned to a commit, re-run `install.py` and
commit the entry. The community copy is deliberately not patched.

## grilling
Interviews you about a plan, decision or idea in rounds: every question that
can be answered now, numbered, each with a recommended answer that "yes"
accepts. Looks facts up itself and leaves the decisions to you. From
`mattpocock/skills` (MIT), fetched from its `skills/productivity/` folder.
Cherry-pick: optional, uncomment it in `apm.yml`.
- `Grill me on this migration plan`
- `Stress-test my idea for splitting the build agents`

`roj-grill-plan` uses the same round format for user stories and SB
documents and writes the answers back into the file; it works without this
skill installed.

## grill-me
Slash-only wrapper (`/grill-me`) that calls `grilling`. Claude only: its body
tells the agent to call the Skill tool, which Copilot does not have. Install
it together with `grilling`. Optional, from `mattpocock/skills`: uncomment it
in `apm.yml` and add `targets: [claude]` (object form).
- `/grill-me` followed by the plan

## to-questionnaire
Turns a decision you cannot answer alone into a Markdown questionnaire for
one person to fill in, written to `to-questionnaire-<slug>.md`. Optional, from
`mattpocock/skills`: uncomment it in `apm.yml`.
- `Turn the open questions on the cache design into a questionnaire for the platform team`

`roj-grill-plan` offers it at the end of a run for questions only someone
else can answer, and lists them in chat when it is absent.
