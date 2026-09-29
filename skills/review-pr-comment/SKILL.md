---
name: review-pr-comment
description: Review an open GitHub pull request and post the findings to it as one COMMENT review with inline comments. Runs automatically after Claude opens a PR in an allowlisted repository (the pr_review_hook tells Claude to follow this file), or by hand with a PR URL or number. Uses the code-review-pr method. For a local branch without a PR, use code-review-pr instead.
---

# Review PR — post comments

Review a GitHub PR's diff with the `code-review-pr` method and post the
result to the PR: one review, `event: COMMENT`, inline comments on the
changed lines, a short summary body. Posts without asking — reaching this
skill through the hook means the repo owner is allowlisted, and a manual
run is an explicit request.

Rules for the whole run:

- Commands allowed: `git`, `gh pr view`, `gh pr diff`, `gh api` on this
  PR's reviews. Nothing else.
- Never approve, request changes, push, or edit the PR.
- Every finding anchors to a line inside a diff hunk, carries a severity and
  a confidence, and dies if it cannot be tied to concrete failure.
- A clean PR is reported as clean. Never invent findings.
- No Claude attribution anywhere in the review.

## 1. Load the method

Read `references/review-method.md` and `references/cross-cutting.md` from
the installed `code-review-pr` skill. First location that exists wins:

1. `<repo>/.github/skills/code-review-pr/references/`
2. `~/.copilot/skills/code-review-pr/references/`
3. `~/.claude/skills/code-review-pr/references/`
4. `~/.agents/skills/code-review-pr/references/`

None found: say "code-review-pr is not installed — run
`agent-skills/install.py`" and stop. No review without the method.

Load technology lenses (`lang-*.md`, `platform-*.md`) from the same
directory only for stacks the diff touches, as the method's lens-selection
phase says.

## 2. Resolve the PR

Argument is a URL or number; none → the current branch's PR.

```bash
gh pr view <arg> --json number,url,baseRefName,headRefOid,isDraft,title,body,headRepositoryOwner,headRepository
```

Take `owner`/`repo` from the URL. No PR found: say so and stop. Draft PRs
are reviewed like any other.

## 3. Skip if this commit is already reviewed

```bash
gh api repos/<owner>/<repo>/pulls/<n>/reviews --paginate --jq '.[].body'
```

If any body contains `<!-- review-pr-comment:<headRefOid> -->`, say
"<headRefOid short> already reviewed: <url>" and stop.

## 4. Collect the diff

If `git rev-parse HEAD` equals `headRefOid`:

```bash
git fetch origin <baseRefName> --quiet
git diff -U15 origin/<baseRefName>...HEAD
```

Otherwise use `gh pr diff <n>`. Read whole changed files where the method
says to. The PR title and body are the stated intent.

The 15-line context is for reading only. GitHub accepts inline comments
only on lines inside **its own** diff, which has 3 lines of context. Get
the commentable ranges from `gh pr diff <n>`, whose hunks are GitHub's, and
use them in step 6.

## 5. Review

Follow the loaded method: severity (🔴 Blocker, 🟠 Major, 🟡 Minor,
🔵 Nit), confidence (Confirmed, Probable; Speculative never becomes a
finding), and its gates and never-report list.

For each finding record `path`, `line` (line number in the **new** file),
severity, confidence, the defect, the
failure scenario, and the fix.

## 6. Build and post the review

Order findings by severity. A finding is inline-eligible only when its
`line` falls inside a `+`/context range of a `gh pr diff` hunk (step 4).
The first 15 eligible findings become inline comments. Everything else,
the ineligible findings and any past 15, goes in the body.

Inline comment body:

```
🟠 **Major** · Probable — <defect>.

Fails when: <scenario>.

Fix: <change>.
```

When the fix replaces exactly the anchored line, append a suggestion block
with the replacement line:

````
```suggestion
<replacement line>
```
````

Review body:

```
**Automated review** — <2–4 lines: what this PR does>

<n> findings: <x> 🔴 · <y> 🟠 · <z> 🟡 · <w> 🔵

<findings that could not go inline, one per line as `path:line` — summary>

<!-- review-pr-comment:<headRefOid> -->
```

No findings: body is the summary line, "No findings.", and the marker.

Post it in **one** Bash call, with the JSON on stdin through a quoted
heredoc. No temp file, and no shell variable carried across calls, since
those do not survive between Bash calls:

```bash
gh api repos/<owner>/<repo>/pulls/<n>/reviews --method POST --input - <<'REVIEW_JSON'
{
  "commit_id": "<headRefOid>",
  "event": "COMMENT",
  "body": "<review body>",
  "comments": [
    {"path": "<path>", "line": <line>, "side": "RIGHT", "body": "<comment body>"}
  ]
}
REVIEW_JSON
```

The payload must be valid JSON: escape `"`, `\` and newlines (`\n`) inside
string values.

## 7. Failures

- **HTTP 422** (a line not in the diff): move every inline comment into the
  body as `path:line` entries, set `comments` to `[]`, post once more. Do
  not retry again. If that also fails, show GitHub's error message and the
  findings in chat.
- **`gh` not authenticated / network error**: print the findings in chat in
  the inline-comment format and say nothing was posted.

## 8. Report

One or two lines in chat: the review URL (`html_url` from the response),
finding counts, and — if the hook said so — that the Copilot request
failed.
