# Bitbucket Data Center REST - reading and commenting

What `scripts/bitbucket_pr.py` does, so the agent and the user can check it.
Data Center only. The script is the only code that touches the network; it
builds every JSON body with `json.dumps` and reads the token from the
environment.

## Contents

- Configuration
- Commands
- Findings file
- What is sent
- Duplicates and re-reviews
- Errors and exit codes
- What this does not verify

## Configuration

| Variable | Holds | Notes |
|---|---|---|
| `BITBUCKET_URL` | server root, `https://bitbucket.example.com`, plus the context path if the server has one | `https` only (plain `http` only for `localhost`); no credentials in it |
| `BITBUCKET_TOKEN` | an HTTP access token | sent as `Authorization: Bearer <token>`; never printed, never an argument |

Create the token in Bitbucket under the profile menu, *Manage account*, *HTTP
access tokens*. It needs the access you use to comment in the web UI; a
read-only token can list comments and cannot post. Set both variables in the
shell that starts the agent, so the agent process inherits them:

| Shell | Command |
|---|---|
| bash, zsh, Git Bash | `export BITBUCKET_URL=https://bitbucket.example.com` and `export BITBUCKET_TOKEN=...` |
| PowerShell | `$env:BITBUCKET_URL = "https://bitbucket.example.com"` and `$env:BITBUCKET_TOKEN = "..."` |
| cmd | `set BITBUCKET_URL=https://bitbucket.example.com` and `set BITBUCKET_TOKEN=...` |

For every session, set them as user environment variables instead (Windows:
*Edit environment variables for your account*), then restart the editor or
terminal. A pasted PR URL on a different host than `BITBUCKET_URL` is never
sent the token.

## Commands

Run with `python3` (macOS, Linux, Git Bash), else `python` or `py -3`. Every
command prints one JSON document on stdout; errors go to stderr as
`error: ...`.

| Command | Network | Prints |
|---|---|---|
| `token-status` | none | `{"token": true, "baseUrl": "..."}` - whether the variables are set, never the token |
| `info --project K --repo S --pr N` | GET the PR | `title`, `description` (cut at 4000 characters), `state`, `source`, `target`, `headSha`, `targetSha` |
| `comments --project K --repo S --pr N [--head SHA]` | GET the PR activities, all pages | `comments`: `id`, `path`, `line`, `text` of every comment; with `--head`, `reviewed`: whether a comment carries ``Reviewed commit `<head12>` `` |
| `post ... --findings FILE\|- [--dry-run]` | GET the activities, POST comments | `status`, `posted`, `skipped`, `failed`, `summaryId`, `error` |

`--project` is the project key from the URL (`projects/<KEY>`), or `~<NAME>`
for a personal repository (`users/<name>`). `--dry-run` validates the file and
prints the requests it would send, with no token and no network.

## Findings file

```json
{
  "head": "<full head commit sha>",
  "summary": "<markdown for the PR-level comment, without the Reviewed line>",
  "comments": [
    {"path": "app/uploader.py", "line": 22, "lineType": "ADDED",
     "text": "<markdown>"}
  ]
}
```

`line` is the line number in the new file; `lineType` is `ADDED` or
`CONTEXT`. At most 15 comments; more is an input error. Pipe the JSON
to `--findings -`; no file is written. The text may hold quotes,
backslashes, backticks and newlines, and the script, not the shell, turns it
into requests.

## What is sent

- Inline comment: `POST /rest/api/1.0/projects/{key}/repos/{slug}/pull-requests/{id}/comments`
  with
  `{"text": "...", "anchor": {"path": "...", "line": 22, "lineType": "ADDED", "fileType": "TO"}}`.
  `fileType: "TO"` is the new side of the diff.
- Summary: the same endpoint with `{"text": "..."}` and no anchor, a
  PR-level comment. Its text ends with the line ``Reviewed commit `<head12>` ``,
  and lists any finding Bitbucket refused to anchor.
- Read: `GET .../pull-requests/{id}` for `info`, and
  `GET .../pull-requests/{id}/activities?start=&limit=` for `comments`,
  following `nextPageStart` until `isLastPage`. Comments are the activities
  whose `action` is `COMMENTED`; the anchor is read from the activity's
  `commentAnchor`, else the comment's `anchor`. Replies are not listed.

Nothing else is called: no approve, needs-work, merge, decline or edit
endpoint.

## Duplicates and re-reviews

- The `Reviewed commit` line makes a head idempotent: `comments --head` and
  `post` both stop when it is already on the PR.
- A new head is reviewed again. Before posting, the agent drops each finding
  that restates a comment already on the same file (lines move between
  heads, so the line number is not the key), and `post` additionally skips a
  comment whose path and text are identical to an existing one.
- When every finding is skipped, the summary is still posted (it says nothing
  is new), so the head gets its `Reviewed commit` line; a rerun after a
  partial post posts the missing summary.

## Errors and exit codes

| Exit | Meaning | Do |
|---|---|---|
| 0 | done, or nothing to post | read `status` |
| 2 | bad input or configuration (`BITBUCKET_URL` missing, `http` URL, malformed findings) | fix the input; the draft stands |
| 3 | `BITBUCKET_TOKEN` not set | stay with the pasteable draft |
| 4 | HTTP 401 or 403: token rejected or without permission | stop; do not retry with other credentials |
| 5 | server or network error, or a failure after some comments were posted | report `posted`; never repost those |

An HTTP 400, 404 or 409 on one inline comment (a line that is not in the PR
diff, or an anchor the server does not accept) does not stop the run: the
finding is listed under `failed` and appears in the summary comment.

## What this does not verify

The endpoints and the minimal anchor (`path`, `line`, `lineType`, `fileType`)
follow Atlassian's Bitbucket Data Center REST reference and community
examples; this repository tests the script against a stand-in server
(`evals/fixtures/fake_bitbucket.py`), not a live Data Center. Server versions
differ in how they treat an anchor on a PR whose source branch moved. If your
server answers 400 to every anchor, the script reports it, every finding
lands in the summary comment, and the draft is still pasteable.
