# Community skills

Fetched by `install.py` into `~/.agent-skills-cache/` and installed
alongside the custom skills. Sources: `github/awesome-copilot` and
`juliusbrussee/caveman`.

## code-tour
Creates CodeTour `.tour` walkthroughs through a repo, PR, or bug.
- `Create a code tour of the auth flow for a new joiner`
- `Make an RCA tour for the bug fixed in PR #97`

`explain-logic`, `investigate-issue`, `soundboarding` and `code-review-pr`
chain to this skill at the end of a run and fall back to writing a minimal
`.tour` inline when it is absent. `tour-codebase` drives it four times in one
run, for a chained series.

Upstream gotcha: its `SKILL.md` documents the bundled scripts at
`~/.agents/skills/code-tour/scripts/`, a path this installer never creates —
skills land in `~/.claude/skills/` and `~/.copilot/skills/`. Resolve
`validate_tour.py` from the installed skill directory instead. The community
copy is deliberately not patched; a re-fetch would overwrite the change.

## acquire-codebase-knowledge
Maps and documents an existing codebase, writing seven documents into
`docs/codebase/`.
- `Map this codebase and create onboarding docs`

`tour-codebase` calls it as its discovery phase and owns the onboarding
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

## caveman
Terse-output mode — cuts output tokens while keeping technical substance.
- `Caveman mode: explain this build failure`
- Combine with other skills: `use caveman mode` appended to any prompt.
