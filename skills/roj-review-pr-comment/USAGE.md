# Using the roj-review-pr-comment skill

Reviews an open GitHub pull request with the `roj-code-review-pr` method and
posts the result to the PR: one review with `event: COMMENT`, inline comments
on changed lines, and a short summary body. It never approves, requests
changes, pushes or edits the PR. It is the only custom skill that writes to
the PR host.

## Requirements

- `git`, and the GitHub CLI `gh` authenticated for the PR's repository
  (`gh auth status`).
- Network access to GitHub.

## Commands per platform

| Agent | Request |
|---|---|
| VS Code Copilot | `/roj-review-pr-comment 142` or `/roj-review-pr-comment https://github.com/<owner>/<repo>/pull/142` |
| JetBrains Copilot | `/skill:roj-review-pr-comment 142` |
| Plain English | `Review PR #142 and post the findings as comments` |

No argument reviews the PR for the current branch.

## What happens

1. Loads the review method from this skill's own `references/` (a synced
   copy of `roj-code-review-pr`'s rules).
2. Resolves the PR with `gh pr view` and stops if this head commit already
   carries a review from this skill (a hidden
   `<!-- review-pr-comment:<sha> -->` marker in the body).
3. Reads the diff, reviews it with the method's severity and confidence
   gates, and posts one review. Up to 15 findings go inline; the rest, and
   any finding outside GitHub's diff hunks, go in the body.
4. Replies in chat with the review URL and finding counts.

A clean PR is posted as "No findings." — the skill never invents findings.

## Automatic runs

In the [dotfiles](https://github.com/rojcarranza/.dotfiles) setup a Claude Code
hook (`pr_review_hook.py`) asks Claude to run this skill right after it opens
a PR in an allowlisted repository. Without that hook the skill only runs
when asked.

## Install

Copilot only. Install it with the rest of this repo: see
[Install](../../README.md#install) in the README, and
[docs/installer.md](../../docs/installer.md) for flags, `--status` and the
work VDI.
