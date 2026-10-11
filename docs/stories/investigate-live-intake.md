# User story: Investigate a failed build from its live logs, then hand off the fix

Tracked in r0jjames/agent-skills#13 (moved from r0jjames/bam-cli#68).

## Story

**As a** developer who uses Copilot with Bamboo and Bitbucket Data Center at work, and Claude or Copilot with GitHub at home
**I want** to say "why did build PROJ-PLAN-44 fail? fix it" and have `roj-investigate-issue` fetch the failed logs itself, find and validate the root cause, and leave a verified fix ready for me to raise
**so that** I stop copying build logs into a `.md` file by hand, and the same skill works at work and at home.

## Context (what exists today)

- `roj-investigate-issue` already does the hard part: classify, gather context, rank causes, validate (**Confirmed**/**Probable**), write `<problem>-investigation.md`, and apply a repo fix after approval.
- Its intake is a **pasted problem `.md` only**. The SKILL.md says "There is no live Bamboo access".
- It stops after the fix, with no text ready for a PR.
- `bam` (r0jjames/bam-cli) reads Bamboo over REST: `bam build logs --failed` works today, and `bam build investigate --json` is planned in r0jjames/bam-cli#59.
- Work setup: **Copilot only**, **Bitbucket Data Center**, **Bamboo**. Bitbucket Data Center has no Pipelines, so Bamboo is the only work CI source.
- Home setup: Claude Code and Copilot, GitHub, GitHub Actions and a personal Bamboo.

## Acceptance criteria

**AC1: Live intake from Bamboo**
- Given `bam` is installed and the user names a build (`PROJ-PLAN-44`), a plan or target, or says "my last build"
- When the skill starts
- Then it runs `bam build investigate <build> --json` (r0jjames/bam-cli#59)
- And when that command does not exist yet, it falls back to `bam build show <build>` plus `bam build logs <build> --failed --tail 200`
- And when `bam` is missing, it says so in one line and asks for a pasted log (today's flow)

**AC2: Live intake from GitHub Actions**
- Given a GitHub remote and `gh` is installed and authenticated
- When the user names a run (URL or ID) or says "the last failed run"
- Then it reads the run with `gh run view <id>` and `gh run view <id> --log-failed`

**AC3: Source detection**
- An explicit argument wins: a build key, a run URL, or a `.md` path
- Otherwise detect from the repo: `.bam.yaml` or `bamboo-specs/` → Bamboo; `.github/workflows/` with a `github.com` remote → GitHub Actions
- When both or neither match, ask one question

**AC4: Intake becomes a problem `.md` in `.investigations/`, the rest is unchanged**
- Fetched evidence is written to `.investigations/<build-key>.md` at the repo root, in the same shape the skill reads today (plan/stage/job/agent, build URL, commit, the decisive error lines, failed tests)
- Phases 2 to 5 run unchanged on it, so the report lands at `.investigations/<build-key>-investigation.md`
- The skill checks `git check-ignore .investigations/`; when the folder is not ignored it says so in one line and suggests adding it to the global git ignore. It never edits `.gitignore` (same rule as `.tours/`)
- A pasted `.md` stays the default and works exactly as today, with its report next to it

**AC5: Read-only against CI**
- Only read commands run against CI: `bam build show|logs|investigate|tree`, `gh run view|list`
- Never `bam run`, `bam build rerun|cancel`, `gh run rerun|cancel`, or anything that triggers a build or deploy, even when asked mid-run; suggest the command instead

**AC6: Secrets stay masked**
- Values that look like tokens, passwords or keys are masked in the problem `.md`, the report and the PR description
- Only the decisive error lines are quoted, never the whole log

**AC7: Fix handoff**
- The report always gets a **PR description** section: cause, fix, link to the failed build, verification output. This is the handoff on every host
- **Bitbucket Data Center or any non-GitHub remote (work):** the skill stops after the verified fix. No branch, commit, push or PR link; the user raises the PR
- **GitHub remote (home):** given a repo code fix was applied and the phase-4 rerun passed, the skill offers "Create a branch and PR link?". On yes it creates `fix/<build-key-lowercase>`, commits only the fix files, asks again before `git push`, then prints `https://github.com/<owner>/<repo>/compare/<branch>?expand=1`
- It never runs `gh pr create` or calls any PR host API, so `roj-review-pr-comment` stays the only skill that writes to a PR host
- It never commits anything under `.investigations/`

**AC8: Copilot first**
- Works in VS Code Copilot agent mode (the work setup) and in Claude Code
- When the agent cannot run commands, it says so and falls back to a pasted log (same rule as `roj-code-review-pr`)

**AC9: Tests, evals, docs**
- `python3 -m unittest test_install test_skills` and `python3 tools/sync_shared.py --check` pass
- New eval fixtures with placeholders only (`bamboo.example.com`, `PROJ-PLAN-44`): a `bam` JSON report, a `bam build logs --failed` output and a `gh run view --log-failed` output, each with an expected class and root cause
- `description` gains triggers: "build failed", "pipeline is red", "fix the build", "investigate PROJ-PLAN-44"
- `USAGE.md` documents the live sources, `.investigations/` and the handoff; the README table row is updated

## Decision log

| Option | Decision |
| --- | --- |
| A. Extend `roj-investigate-issue` with live intake and handoff | **Chosen.** One skill per trigger ("why did the build fail"), no second description loaded into every session |
| B. New `roj-fix-build` skill that chains to `roj-investigate-issue` | Rejected for now; two skills would compete for the same trigger |
| Bitbucket Pipelines source | Dropped: work is Bitbucket Data Center, which has no Pipelines |
| Where fetched evidence goes | `.investigations/` at the repo root, git-ignored by the user, never committed |
| PR handoff at work (Bitbucket Data Center) | None: the skill stops at the verified fix and the PR description in the report; the user raises the PR |
| PR handoff at home (GitHub) | Branch, commit and push after asking, then the compare link only. No `gh pr create` |
| PR host APIs | Never called; `roj-review-pr-comment` stays the only writer |
| AI summary inside `bam` (`--ai`) | Rejected in r0jjames/bam-cli#59: bam stays deterministic, the agent does the reasoning |
| Primary agent | Copilot (the only agent at work); Claude Code at home |

## Out of scope

- Bitbucket Pipelines, Jenkins, GitLab CI
- Creating PRs, or branches, commits and pushes on Bitbucket remotes
- Triggering, rerunning or cancelling builds; auto-merge
- Bitbucket Data Center or GitHub API calls of any kind
- Bamboo admin or agent-host fixes (still numbered manual steps in the report)

## Risks and trade-offs

- **Copilot terminal access at work:** if command approval is blocked, AC8's fallback keeps the skill usable, only slower.
- **`bam` on work machines:** needs a token for the work Bamboo. Without `bam`, AC1 falls back to pasted logs.
- **Context size:** large logs blow the context window. Use `--json` errors or `--tail`, never full logs.
- **Employer details:** fetched logs carry real hostnames and keys. They stay in `.investigations/`, which is never committed; fixtures use placeholders, and `.private-patterns` guards `skills/`.

## Tasks

1. SKILL.md: new intake step (AC1 to AC4), read-only rule (AC5), masking (AC6)
2. `references/sources.md`: bam, gh and pasted-log intake, with the fallbacks
3. SKILL.md phase 6: host-aware handoff (AC7); `assets/report-template.md` gets a PR description section
4. Copilot no-terminal fallback (AC8)
5. Eval fixtures and expected results (AC9)
6. `description`, USAGE.md, README row
7. Run `test_install`, `test_skills`, `sync_shared --check`

**Estimate:** 3 points for tasks 1, 2, 4 and 6; 2 points for tasks 3 and 5.

## Depends on

- r0jjames/bam-cli#59 for the best Bamboo intake. The fallback in AC1 works without it.
