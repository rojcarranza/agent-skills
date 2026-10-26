# roj-code-review-pr - usage

Reviews a Git change for defects: your own branch (uncommitted work
included), a teammate's branch, or a Bitbucket Data Center pull request,
without checking anything out. One skill, two depths, picked for you:

- **quick** - chat only, Blocker and Major findings only, diff-local, `git`
  commands only, at most five findings.
- **full** - change summary, severity-and-confidence-tagged findings, the
  system pass (callers, config-to-code coupling, idempotency, rolling
  deploys), a Markdown report and an optional CodeTour.
- **auto** (the default) - quick unless the change is large or risky.

It never calls a Bitbucket or GitHub API, never posts comments, and never
asks for or pins a model: it runs on whatever the agent already selected
(Copilot Auto, the Claude default) and launches no subagents unless you ask.

## When to use

- Before pushing a branch or opening a PR. Staged, unstaged and untracked
  files are reviewed with the commits; on the base branch the working tree
  alone is the review.
- A teammate's branch or a Bitbucket Data Center PR, fetched by ref without a
  checkout.
- A quick sanity check mid-work.

Not for pure comprehension - that is `roj-explain-logic`. Not for diagnosing a
build that already failed - that is `roj-investigate-issue`. To draft or post
review comments on a Bitbucket PR, use `roj-review-pr-comment`.

## Invoking

Plain English works everywhere - the skill triggers from its description:

    review my branch                          # auto picks the depth
    quick review                              # force quick
    full review of my branch                  # force full
    review my branch against release/2.4      # explicit base branch
    review origin/feature/PROJ-123-retry      # a branch, no checkout
    review PR 214, it merges into develop     # Bitbucket Data Center PR
    review my branch, the story says: <text>  # with an intent source

Explicit invocation differs per agent:

| Agent | Command |
| --- | --- |
| Copilot, VS Code | `/roj-code-review-pr` |
| Copilot, JetBrains | `/skill:roj-code-review-pr` |

Both are personal scope once installed, so they reach every project
with no per-repository seeding.

## Targets

| You give | It reviews |
|---|---|
| nothing | the current branch and all local changes |
| `against <base>` | the same, with that base |
| `<branch>` or `origin/<branch>` | that branch, read with `git diff <base>...<ref>` and `git show <ref>:<path>`; local changes are not part of it |
| a PR id or URL | the PR head, fetched with `git fetch origin refs/pull-requests/<id>/from`, nothing checked out |

The base of a PR is its target branch: take it from the URL or tell it, or it
asks. It never guesses `origin/HEAD` for a PR. Without a stated base, it picks
the nearest of `origin/HEAD`'s branch, `develop`, `main` and `master` - the one
with the fewest commits between it and the branch - and prints the choice with
the merge-base SHA. The Data Center specifics, and what Atlassian documents
about them, are in `references/forge-bitbucket-dc.md`.

## Depth: how auto chooses

Auto picks **full** when any of these holds, measured on the change without
generated, vendored and lockfile paths:

- more than 10 files, or more than 400 changed lines (added plus deleted);
- a deploy or CI file: Bamboo spec, Kubernetes manifest, Helm chart,
  Dockerfile or compose file, `Jenkinsfile`, `bitbucket-pipelines.yml`,
  `.github/workflows`;
- auth, secrets, credentials, permissions or crypto code or config;
- a schema or data migration (`migrations/`, `*.sql`);
- a contract file (`*.proto`, `openapi*`, `swagger*`).

Otherwise it is **quick**; a borderline change is quick, and the quick output
offers `full`. It prints the choice and why in one line. Saying `quick` or
`full` always wins.

## Intent source (optional)

Paste the PR description or Jira story text, or point at an SB / story file
with acceptance criteria. The review then also reports **acceptance criterion
not met** and **out-of-scope change** findings, and a short *Intent check*
lists each criterion as met, not met or not verifiable here. Without one,
commit messages are the only intent evidence and no intent findings are made.

## Repo map (optional)

When the repository has an `.onboarding/` guide (`roj-onboard-repo` writes
it), a full review reads its system map and `reviewing-prs.md` and prints one
line in the report header and in chat, such as
`Repo map: .onboarding @ a1b2c3d (fresh) - areas: uploads`. The guide only
points the review at the areas, dependents, hotspots and silent seams the
diff touches; every finding still anchors to a diff line, and the code wins
when the two disagree. A guide 50 or more commits behind the base, or one that
names a commit this clone does not have, is used only to name areas. Quick
mode never reads it, and an untracked `.onboarding/` or `.pr-review/` folder
is never reviewed as code.

## Running checks (full mode)

One question, up front: run the repo's own checks to confirm findings?
`no` (the default) runs nothing beyond `git`; `checks` runs the declared
linters and the narrowest tests for the changed code; `checks+probe` also
runs a mutation probe on up to two new decision branches (change one
condition in a scratch copy, run the narrowest test, restore the file - a
mutation that stays green is a missing-test finding). There is no later
approval stop. Checks need the code checked out, so they are skipped for a
branch or PR target.

## Output

Quick: chat only, in the six-line shape described in `SKILL.md`.

Full: chat gets the verdict, one line per finding and the report path. Files:

- `<branch-slug>-review.md` (`pr-<id>-review.md` for a PR) at the repository
  root, where `<branch-slug>` is the branch name with `/` replaced by `-`.
  The skill offers once to add that name to `.git/info/exclude` so
  `git add -A` skips it; it never edits `.gitignore`. Ask for "chat only"
  and nothing is written.
- `.tours/review-<branch-slug>.tour`, persona `pr-reviewer`, only if you
  accept the offer. `.tours/` is in the global Git ignore, so tours stay local.

Report sections: header, **what this branch does**, verdict, findings by
severity, intent check, tests, runtime and deploy impact, questions that need
your input, pre-existing issues, and what was done well.

Every finding carries a severity (Blocker / Major / Minor / Nit - impact if
shipped) and a confidence (Confirmed / Probable / Speculative). A Blocker
must be Confirmed. Every Major or Blocker states a concrete failure scenario,
or it is dropped. A claim about what a tool or library does is Confirmed only
when its source was read or its behaviour observed in this run.

## Pre-PR versus post-PR

A PR target, or a request that says the PR is already open, is post-PR.
Everything else is pre-PR: without a PR host there is no way to tell whether a
PR exists, so a pushed branch is not assumed to have one.

- **Pre-PR** - drafts a PR description from the change summary, and may offer
  to apply fixes after asking.
- **Post-PR** - shapes findings as pasteable review comments split into
  requested changes versus nits, and never suggests rewriting history.

## Customising

The rules live in `references/`. Edit them directly - they are prose
checklists, not code.

- `review-method.md` - severity, confidence, intent findings, suppression
  rules, output skeleton, calibration examples.
- `cross-cutting.md` - secrets, idempotency, error handling, timeouts,
  destructive operations.
- `lang-java.md`, `lang-python.md`, `lang-bash.md`, `lang-go.md`.
- `platform-bamboo.md`, `platform-k8s.md`, `platform-helm.md`,
  `platform-docker.md`.
- `full-review.md` - the full-mode procedure, checks and report rules.
- `base-resolution.md`, `forge-bitbucket-dc.md`.

`review-method.md`, `cross-cutting.md`, the lens files, `base-resolution.md`
and `forge-bitbucket-dc.md` are copied into the skills that use them by
`tools/sync_shared.py`: edit them here, then run the sync.

Each lens ends with a "not a finding here" list. That list is what keeps the
review from turning into nitpicking - extend it whenever the skill flags
something you do not care about.

## Install

Copilot only. Install it with the rest of this repo: see
[Install](../../README.md#install) in the README, and
[docs/installer.md](../../docs/installer.md) for flags, `--status` and the
work VDI.

If the skill does not appear in JetBrains: confirm chat is in agent mode,
that the Copilot plugin is current, and that `install.py --status` lists
`roj-code-review-pr` under `~/.copilot/skills`. Type `/skill:` to list
everything - the picker filters on the namespaced name, so `/code-rev`
matches nothing there.

The quick pass used to be a separate skill; it is now this skill's quick
mode. Remove a leftover copy of the old one from `~/.copilot/skills` or
`~/.claude/skills`.
