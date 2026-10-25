# roj-code-review-pr-fast — usage

A short chat-only pass over the current branch diff. No report file, no
CodeTour, no command other than `git`.

## When to use

- Mid-work sanity check before committing or pushing.
- A small diff where the full review would cost more than it returns.

Use `roj-code-review-pr` instead when the change is going into a PR, when you
want the change explained as well as reviewed, or when Bamboo specs,
Dockerfiles, Kubernetes manifests or Helm charts are involved.

## Invoking

    quick review
    fast review of my changes
    sanity check this branch

| Agent | Command |
| --- | --- |
| Claude Code (terminal, VS Code, JetBrains) | `/roj-code-review-pr-fast`, or plain English |
| Copilot, VS Code | `/roj-code-review-pr-fast` |
| Copilot, JetBrains | `/skill:roj-code-review-pr-fast` |

## What it does

Resolves the base the same way `roj-code-review-pr` does, takes
`git diff <base>...HEAD`, reads the whole file where context matters, and
reviews the changed hunks only. No caller search, no configuration-to-code
coupling check, no test analysis — the output says so explicitly at the end,
so nothing is silently skipped.

Findings use the same severity and confidence scales as the full skill, with
the same gates: nothing below Probable is reported, a Blocker must be
Confirmed, and every Major or Blocker states a concrete failure scenario.
Capped at five findings.

## Relationship to roj-code-review-pr

The severity, confidence and suppression rules live in
`roj-code-review-pr/references/` and are copied into this skill's own
`references/` by `tools/sync_shared.py`, so this skill runs on its own —
installed alone, in any agent, at any scope. Edit the rules in
`roj-code-review-pr`, then run the sync; CI fails on a stale copy. The
condensed tables in `SKILL.md` are a last-resort fallback.

## Install

Any agent, with Node.js:

    npx skills add rojcarranza/agent-skills -s roj-code-review-pr-fast

Or from a clone of this repo (adds the skills it depends on, plus the
Windows copy fallback):

    python3 install.py --target claude    # mac / Claude Code
    python3 install.py --target copilot   # work / GitHub Copilot
