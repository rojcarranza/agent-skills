# Phase 5: Agent config

Read before writing the agent config. Output, as one set on one yes:

- `CLAUDE.md` from `assets/claude-md-template.md`
- `.claude/settings.json` from `assets/hooks-settings.example.json`
- `.claude/agents/security-reviewer.md`, `.claude/agents/architecture-guardian.md`,
  `.claude/agents/test-auditor.md` from `assets/agents/`

List all five paths first. A file that already exists is merged (show the
diff) on its own yes, never replaced.

## CLAUDE.md

- Under 100 lines. For each line: would removing it cause a mistake? If
  not, cut it.
- Exact build, test, single-test, lint and run commands for the stack in
  the ADRs. Look them up for that stack; do not guess flags.
- Deviations from the stack's defaults, and links to `docs/adr/`.
- No file-by-file descriptions, nothing an agent can read from the code.
- Must-never-happen rules become hooks or tests, not prose.

## Hooks

- Replace the placeholders in the example with the `CLAUDE.md` commands:
  `PostToolUse` runs the formatter and linter after `Edit|Write`;
  `PreToolUse` blocks edits to `.env*`, `infra/prod/**` and
  `migrations/**`.
- No `Stop` hook yet: with no code, the test command fails on every turn
  and exit 2 would stop the agent from ending its turn to ask for the
  plan approval. The plan's task 1 adds it once the tests exist (see
  `references/handoff.md`).
- Show every hook command before writing it.
- Copilot CLI: hooks live in `.github/hooks/*.json` with a different
  schema. Name that path for the user; do not write it.

## Reviewer agents

Copy the three files as they are. They use model aliases (`opus`,
`sonnet`). Copilot CLI: custom agents go in `.github/agents/`.

## Suggest, never install

Name the free checks that fit the stack, with one line each on where they
run: formatter and linter (hook), type checker (hook and CI), Semgrep CE or
CodeQL (CI), dependency scan (Dependabot, `npm audit`, `pip-audit`,
`govulncheck`), gitleaks (pre-commit and CI). Installing them is the
user's job or a plan task.

## Gate

1. Ask the user to run, in a fresh shell, every `CLAUDE.md` command that
   can work before any code exists (tool versions, the linter on an empty
   tree, `git status`), and report the result. Fix the ones that fail.
   Mark the rest in `CLAUDE.md`'s `## Gotchas` as "verified by plan task
   1": the walking skeleton is what makes them runnable.
2. Run `scripts/check_ready.py --phase agent-config <ROOT>` until it exits
   0.
3. Ask for the gate approval for the set.
