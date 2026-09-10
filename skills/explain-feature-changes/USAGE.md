# explain-feature-changes — usage

Explains the changes on your own feature branch compared with its base, so
you understand them and can explain them in PR review. It traces callers,
callees, tests and configuration instead of summarizing the diff, labels
intent as confirmed, likely or unknown, and writes PR-ready text.

Not a code review. For a review, use a dedicated code-review skill.

## When to use

- Before opening a PR, to understand and describe what the branch does.
- Before a review meeting, to be able to explain every change.
- To get a PR description and per-change PR comments you can paste.

Not for a single file or function, and not for someone else's branch.

## Invoking

Plain English works in every agent — the skill triggers from its
description:

    explain my changes compared to develop
    help me understand what I changed in this branch
    explain the new functions and code flow in my branch
    generate something I can paste into my PR
    help me explain these changes to my reviewer

Explicit invocation:

| Agent | VS Code | IntelliJ / PyCharm / GoLand |
| --- | --- | --- |
| Claude Code | `/explain-feature-changes [base]` | `/explain-feature-changes [base]` |
| Copilot | `/explain-feature-changes [base]` (prompt file) | `/skill:explain-feature-changes [base]` |
| Copilot, repo seeded with `install.py --repo .` | same | `/explain-feature-changes [base]` |

Examples: `/explain-feature-changes`, `/explain-feature-changes develop`,
`/skill:explain-feature-changes main`.

Base branch without an argument: `develop` (`origin/develop`, then local),
then `main` (`origin/main`, then local). If neither exists, the skill asks.

## What it does

1. Resolves the base and prints `feature/x → develop (merge base <sha>)`.
2. Collects the committed diff with `git diff <base>...HEAD`. Uncommitted
   files are listed in the report header, not explained.
3. Builds a change inventory and ranks changes by behavioral impact.
4. Traces each new or changed symbol: callers (`git grep -n`), callees,
   inputs, outputs, the code it replaced (`git show <merge-base>:<path>`),
   tests and configuration.
5. Labels intent as confirmed, likely or unknown, from commit messages,
   ticket IDs, tests and naming.
6. Writes the report and a CodeTour.

It runs `git` commands and reads files; the only other command is the
CodeTour validator script at the end. It never commits, pushes, checks out
or edits code. Every `git` command is plain `git`, so it behaves the same
in bash, PowerShell and cmd.

## Output

- Chat: the comparison line, the overview, Key Things to Understand, and
  the report path.
- `<branch-slug>-changes.md` at the repository root (branch name with `/`
  replaced by `-`). Untracked; the skill offers to add it to
  `.git/info/exclude`.
- `.tours/changes-<branch-slug>.tour`, persona `pr-reviewer`.

Report sections: Feature Change Overview, Why This Change Exists, Changes by
File, New Functions / Classes, End-to-End Flow, Key Things to Understand, PR
Explanation, PR Comments, Important Observations. Empty sections are left
out.

The tour opens in VS Code with the CodeTour extension. No maintained
JetBrains viewer was found (checked 2026-09-10); in IntelliJ, PyCharm and
GoLand use the report's `path:line` references to navigate.

## Dependencies

`install.py` installs these with the skill, to the same targets, in every
install mode. The skill still runs without them, on its own fallback.

| Skill | Source (skills.sh) | Used for |
| --- | --- | --- |
| `code-tour` | `github/awesome-copilot` | writing the tour |
| `context-map` | `github/awesome-copilot` | mapping related files on large branches |
| `write-pr-description` | `warpdotdev/common-skills` | shaping the PR Explanation |

`python3 install.py --status` lists any requirement that is missing.
`--skills-only` cannot fetch them; the run ends with a warning naming what
is missing.

## JetBrains checklist

1. Copilot plugin up to date and signed in.
2. **Settings → Languages & Frameworks → GitHub Copilot → Chat → Agent** —
   agent mode on. Without it Copilot cannot run `git`, and the skill asks
   you to paste the diff instead.
3. `python install.py --target copilot` (both skills and dependencies land
   in `~/.copilot/skills`, which JetBrains reads).
4. Reopen the IDE, open a feature branch, type
   `/skill:explain-feature-changes develop` in agent-mode chat.
5. Approve the `git` commands it proposes in the IDE terminal. The report
   appears at the repository root.

## Skills considered

Found through the skills.sh search API. Only skills published there were
considered for reuse.

| Skill | Relevance | Decision | Reason |
| --- | --- | --- | --- |
| `github/awesome-copilot/code-tour` | High | Compose | Writes the tour |
| `github/awesome-copilot/context-map` | Medium | Compose | Maps related files on large branches |
| `warpdotdev/common-skills/write-pr-description` | High | Compose | PR body rules: facts first, repo template wins, cut hard, no padding |
| `warpdotdev/common-skills/pr-walkthrough` | Low | Not used | Branded D3 HTML page, needs `gh`, publishes to Cloudflare |
| `chris-graffagnino/explain-diff` | High overlap | Pattern only | Stated-vs-inferred intent and analysis lenses informed the tracing rules; installing it would add a competing explainer |
| `sjunepark/agent-scripts/change-explainer` | Low | Not used | Written for a cold reader, not the author |
| `mryll/skills/explain-pr`, `aymericderbois/skills/explain-your-changes` | Low | Not used | Shallow, few installs |
| `amplitude/mcp-marketplace/diff-intake`, `ruvnet/ruflo/diff-analyze` | Low | Not used | Different purpose |
| `mattpocock/skills/code-review`, `coderabbitai/skills/code-review` | Low | Not used | Code review is a different purpose |
