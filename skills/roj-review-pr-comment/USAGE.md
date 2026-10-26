# Using the roj-review-pr-comment skill

Reviews a Bitbucket Data Center pull request with the `roj-code-review-pr`
method and turns the result into Bitbucket comments. By default you get a
**draft**: each finding as `path:line` plus the comment text, ready to paste
into the PR. It posts to the PR only when you say post or comment, or answer
yes to its offer, and only when a Bitbucket access token is configured. It
never approves, marks needs work, merges, pushes or edits the PR, and it
never reads your token back or asks for it in chat.

## Requirements

- `git`, with `origin` pointing at the PR's repository.
- For posting only: Python 3 and network access to the Bitbucket server, an
  HTTP access token in `BITBUCKET_TOKEN` and the server root in
  `BITBUCKET_URL`. Without them the output is the pasteable draft, which
  needs nothing but `git`.

### Setting up posting

Create the token in Bitbucket: profile menu, *Manage account*, *HTTP access
tokens*. Put it in the environment of the shell that starts your editor or
terminal, so the agent inherits it:

| Shell | Commands |
|---|---|
| bash, zsh, Git Bash | `export BITBUCKET_URL=https://bitbucket.example.com` then `export BITBUCKET_TOKEN=...` |
| PowerShell | `$env:BITBUCKET_URL = "https://bitbucket.example.com"` then `$env:BITBUCKET_TOKEN = "..."` |
| cmd | `set BITBUCKET_URL=https://bitbucket.example.com` then `set BITBUCKET_TOKEN=...` |

Set them as user environment variables to keep them across sessions. The
token is only ever sent to `BITBUCKET_URL`, over https; a PR link on another
host is reviewed from git alone. `references/bitbucket-rest.md` lists exactly
which calls the script makes.

## Commands per platform

| Agent | Request |
|---|---|
| VS Code Copilot | `/roj-review-pr-comment 142` or `/roj-review-pr-comment https://bitbucket.example.com/projects/KEY/repos/slug/pull-requests/142/overview` |
| JetBrains Copilot | `/skill:roj-review-pr-comment 142` |
| Plain English | `Review PR 142, it merges into develop` (draft) or `Review PR 142 and post the comments` |

A bare PR id takes the project and repository from the `origin` remote. The
PR's target branch comes from the URL, the REST lookup, or a question; it is
never guessed from `origin/HEAD`.

## What happens

1. Loads the review method and the Bitbucket rules from this skill's own
   `references/`.
2. Resolves the PR. With a token it also reads the title, description and
   latest commit (the description becomes the intent source) and the
   comments already on the PR.
3. Fetches `refs/pull-requests/<id>/from` and the target branch, nothing
   checked out, and reads the diff and whole files from the fetched commit
   with `git diff` and `git show <sha>:<path>`, so a local checkout on another
   branch does not matter. If the fetched commit is older than the PR's
   latest, it stops and tells you to open the PR's Commits tab and retry.
4. Reviews the diff with the method's severity and confidence gates, and
   drops findings that restate a comment already on the PR.
5. Prints the draft: a summary comment and up to 15 inline comments, each in
   its own block. Findings without a commentable line, and any past 15, go in
   the summary.
6. On an explicit request, or a yes: posts the inline comments and then one
   PR-level summary comment ending in ``Reviewed commit `<sha>` ``. That line
   stops a second run from reviewing the same commit; a newer commit is
   reviewed again and skips what was already said.

A clean PR is reported as "No findings." - the skill never invents findings.

Works the same from bash and PowerShell: git commands are single lines, and
the findings JSON is piped to the one script that talks to Bitbucket, which
builds the requests itself, so there is no shell quoting to get wrong. cmd
has no heredoc or here-string, so there the skill stays with the draft.

## Install

Copilot only. Install it with the rest of this repo: see
[Install](../../README.md#install) in the README, and
[docs/installer.md](../../docs/installer.md) for flags, `--status` and the
work VDI.
