# code-review-pr — usage

Reviews the diff between the current feature branch and its base, before or
after a PR is opened. Produces a change summary, severity-and-confidence
tagged findings, a Markdown report at the repository root, and a CodeTour.

Git-only: it never calls a Bitbucket or GitHub API, never reads PR metadata,
and never posts comments.

## When to use

- Before pushing a feature branch, or before opening a PR.
- After opening a PR, to produce findings you can paste as review comments.
- Any branch touching Java/Maven, Python, Bash, Go, Bamboo specs, Dockerfiles,
  Kubernetes manifests or Helm charts.

Not for pure comprehension — that is `explain-logic`. Not for diagnosing a
build that already failed — that is `investigate-issue`. For a quick chat-only
pass mid-work, use `code-review-pr-fast`.

## Invoking

Plain English works everywhere — the skill triggers from its description:

    review my branch
    code review before I open the PR
    review this PR
    review my branch against release/2.4     # explicit base branch

Explicit invocation differs per agent:

| Agent | Command |
| --- | --- |
| Claude Code (terminal, VS Code, JetBrains) | `/code-review-pr`, or plain English |
| Copilot, VS Code | `/code-review-pr` |
| Copilot, JetBrains | `/skill:code-review-pr` |

All three are personal scope once installed, so they reach every project
with no per-repository seeding.

With no argument the base is resolved from `origin/HEAD`, then `origin/main`,
`origin/master`, `origin/develop`, then their local equivalents. The resolved
base and merge-base SHA are printed in the report, so a review is
reproducible.

## What it does

1. Resolves the base and warns when the diff looks too large to be the right
   one (over 40 commits, or roughly 2000 lines).
2. Collects the diff with `git diff <base>...HEAD` — three-dot, so work
   merged into the base since the branch point is never reviewed.
3. Detects the stacks from the **changed files**, not from what the
   repository contains, and loads at most three rule files.
4. Reads the repository's own conventions (`CLAUDE.md`, `CONTRIBUTING.md`,
   linter configs) and defers to them. Anything a configured linter enforces
   is not reported.
5. Offers a table of verification commands (`shellcheck`, `go vet`,
   `ruff check`, `helm template`, `kubeconform`, …) and waits for approval.
   Nothing runs unapproved.
6. Reviews per file, then across files (callers, config-to-code coupling,
   idempotency, rolling deploys), then verifies each finding against the
   whole file before printing it.

## Output

Chat, plus two files:

- `<branch-slug>-review.md` at the repository root, where `<branch-slug>` is
  the branch name with `/` replaced by `-`.
- `.tours/review-<branch-slug>.tour`, persona `pr-reviewer`, openable with
  the CodeTour extension. `.tours/` is in the global Git ignore, so tours
  stay local.

Report sections: header, **what this branch does**, verdict, findings by
severity, tests, runtime and deploy impact, questions that need your input,
pre-existing issues, and what was done well.

Every finding carries a severity (Blocker / Major / Minor / Nit — impact if
shipped) and a confidence (Confirmed / Probable / Speculative). A Blocker
must be Confirmed. Every Major or Blocker states a concrete failure scenario,
or it is dropped.

## Pre-PR versus post-PR

Detected from Git: a pushed branch with an upstream and nothing ahead is
treated as post-PR.

- **Pre-PR** — drafts a PR description from the change summary, and may offer
  to apply fixes after asking.
- **Post-PR** — shapes findings as pasteable review comments split into
  requested changes versus nits, and never suggests rewriting history.

## Customising

The rules live in `references/`. Edit them directly — they are prose
checklists, not code.

- `review-method.md` — severity, confidence, suppression rules, output
  skeleton, calibration examples.
- `cross-cutting.md` — secrets, idempotency, error handling, timeouts,
  destructive operations.
- `lang-java.md`, `lang-python.md`, `lang-bash.md`, `lang-go.md`.
- `platform-bamboo.md`, `platform-k8s.md`, `platform-helm.md`,
  `platform-docker.md`.

Each file ends with a "not a finding here" list. That list is what keeps the
review from turning into nitpicking — extend it whenever the skill flags
something you do not care about.

## Install

From the repo root:

    python3 agent-skills/install.py --target claude    # mac / Claude Code
    python3 agent-skills/install.py --target copilot   # work / GitHub Copilot
    python3 agent-skills/install.py --target both

On the Windows VDI use `python` rather than `python3`. Copilot installs to
`~/.copilot/skills/` (under `%USERPROFILE%` on Windows), which is personal
scope: the skill is then available in every project, in both VS Code and
JetBrains agent-mode chat. No `.github/skills` seeding is required.

Copilot receives copies, not symlinks — re-run the installer after editing
any rule file. `--status` shows what is installed where.

If the skill does not appear in JetBrains: confirm chat is in agent mode,
that the Copilot plugin is current, and that `install.py --status` lists
`code-review-pr` under `~/.copilot/skills`. Type `/skill:` to list
everything — the picker filters on the namespaced name, so `/code-rev`
matches nothing there.
