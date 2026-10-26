# Bitbucket Data Center pull requests

Read a Bitbucket Data Center pull request with `git` alone: no REST call, no
token, no checkout. Data Center only - Bitbucket Cloud has different refs and
URLs; if the remote is Cloud, ask for the branch name and use it as a branch
target.

## Contents

- Recognise the target
- Fetch the PR head
- Read the PR
- When the ref is missing or stale
- Why `from` and not `merge`
- Sources

## Recognise the target

The user gives a PR id (`42`, `PR 42`) or a URL such as
`https://<host>/projects/<KEY>/repos/<slug>/pull-requests/<id>/overview`
(a personal repository has a user name in the place of `projects/<KEY>`).
Take the id and the repository slug from it.

1. `git remote get-url origin` - the slug in the URL must match the slug of
   `origin`. Different repository: stop and say so; the PR is not in this
   clone.
2. The PR's **target branch** is its base. Take it from the URL or page the
   user pasted, or ask ("Which branch does this PR merge into?"). Never use
   `origin/HEAD` for a PR (see base resolution).

## Fetch the PR head

Two separate calls, nothing checked out, no local branch created:

1. `git fetch origin <target>` - refreshes `origin/<target>`, so the diff does
   not carry commits the target has since gained.
2. `git fetch origin refs/pull-requests/<id>/from`, then
   `git rev-parse FETCH_HEAD`. Keep the printed SHA as `<head>`; a later
   fetch overwrites `FETCH_HEAD`.

The user asking for the PR review is the request to fetch these two refs;
nothing else is fetched.

## Read the PR

Everything is read from `<head>`, never from the working tree, which may be
on another revision:

- Diff: `git diff <base>...<head>` (three-dot, `<base>` = `origin/<target>`).
  Data Center 7 and later shows the PR as the source tip against its common
  ancestor with the target, which is what the three-dot diff computes.
- Commits: `git log <base>..<head>`.
- Whole files: `git show <head>:<path>`. A file the PR deleted is read from
  the base instead: `git show <base>:<path>`.
- Intent: the PR title and description are not available without REST. Ask the
  user to paste them, or to name a Jira story or SB file, as the intent
  source.

A PR is always **post-PR** for the report: findings are written as comments
the author can act on, not as a pre-push checklist.

Local checks (tests, linters) need the PR head in the working tree. Do not
check it out unasked; say that the checks were skipped because the PR is not
checked out.

## When the ref is missing or stale

- `fatal: couldn't find remote ref refs/pull-requests/<id>/from`: the ref is
  not available on this server or for this PR. Ask for the source branch name
  and review it as a branch target (`git fetch origin <branch>`, then
  `origin/<branch>`), or for the pasted diff.
- The ref can lag the PR. On 7.0 the `from` ref was not created or updated
  until someone opened the PR's diff or commits tab; Atlassian fixed that in
  7.12.0 (BSERV-12284), so on an older server it can point at an earlier
  source commit. When the user can give the latest commit id shown on the PR,
  compare it with `<head>`; a mismatch means ask the user to open the PR's
  Commits tab and retry, or use the branch name.
- Atlassian does not document these refs as a supported interface (no
  documentation page was found for them). Treat the fetch as best effort and
  state the SHA reviewed in the report header, so the review is reproducible.

## Why `from` and not `merge`

Do not review `refs/pull-requests/<id>/merge`. Bitbucket 7.x and later does
not maintain merge refs: Atlassian tracks leftover ones as outdated
(BSERV-13950), and the PR diff since 7.0 is the source tip against its common
ancestor with the target (a 2-way diff), not a preview of the merge result.
Conflicts are not part of the diff; the PR page says whether there are any.

## Sources

- Atlassian, "Comparison of a Pull Request Diff between Bitbucket Server and
  Data Center versions up to 6.x and from 7.x onwards":
  <https://support.atlassian.com/bitbucket-data-center/kb/comparison-of-a-pull-request-diff-between-bitbucket-server-and-data-center-versions-up-to-6x-and-from-7x-onwards/>
  - the 7.x PR diff is the source tip against its common ancestor with the
  target, and the switch from a 3-way to a 2-way diff is permanent.
- Atlassian Jira BSERV-12284, "Eagerly update refs/pull-requests/*/from when a
  pull request's source branch changes":
  <https://jira.atlassian.com/browse/BSERV-12284> - the
  `refs/pull-requests/<id>/from` ref exists, and was not created or updated
  eagerly before the fix in 7.12.0.
- Atlassian Jira BSERV-13950, "Cleanup the outdated
  refs/pull-requests/<PR_ID>/merge refs on packed-refs file on Bitbucket 7.x
  and 8.x": <https://jira.atlassian.com/browse/BSERV-13950> - `merge` refs are
  outdated leftovers on 7.x and 8.x.
