# Report template

Loaded at phase 6. The report serves the developer first and the reviewer
second. Leave out any section that would be empty; never write "N/A".

## Skeleton

    # <branch> — change explanation

    Comparing `<branch> → <base>` (merge base `<sha>`), <n> commits.
    Uncommitted, not covered: <files, or "none">.
    Listed only (generated, vendored, formatting): <files, or "none">.
    Skipped phases: <only when there was no terminal>.

    # Feature Change Overview
    2–5 sentences: what the branch does, the main mechanism, the visible
    behavior change.

    # Why This Change Exists
    One bullet per reason, each labelled Confirmed, Likely or Unknown, with
    its evidence.

    # Changes by File
    ## `path/to/file` (added | modified | deleted | renamed)
    ### What changed
    ### Why
    ### Important functions/classes
    ### Before → After

    # New Functions / Classes
    ## `name()`
    The symbol card from references/tracing.md as an indented block.

    # End-to-End Flow
    From the entry point to the final effect, in run order, one hop per
    line, each with `path:line`.

    # Key Things to Understand
    3–7 numbered points the developer must be able to say out loud in review.

    # PR Explanation

    # PR Comments

    # Important Observations

Large branch: replace "Changes by File" with "Changes by Area", one `##` per
responsibility, listing its files under it. Put a five-line executive
summary before the overview.

A file with only a trivial change gets one line under its heading, not the
four subsections.

## Evidence rules

- Every behavior claim carries a `path:start-end` (or `path:line`)
  reference to the current file. Old code is referenced with "at the merge
  base".
- Every intent claim carries Confirmed, Likely or Unknown.
- No impact claim without evidence. Write "removes the repeated lookup
  previously performed by the caller", not "improves performance". If the
  impact depends on runtime conditions, say that.
- When code you could not read decides the behavior (a library, a service
  outside the repository), say so instead of guessing.

## Style

Write like a senior engineer explaining the change to another engineer:
factual, concise, tied to the code.

- Prefer: "Added", "Moved", "Changed", "Removed", "The function now",
  "Previously", "The caller now", "This separates", "This allows".
- Do not write, unless the code proves it: "elegantly", "robustly",
  "seamlessly", "enhances", "significantly improves", "comprehensive".
- Do not restate the diff line by line, explain language syntax, or teach
  the technology in general.

## PR Explanation — fallback rules

Used when `write-pr-description` is not installed.

- Open with 1–3 sentences: what changed and why.
- Then "Behavior changes" as bullets, each with a `path:start-end`
  reference. Include removed behavior.
- Then the flow on one line: `a()` → `b()` → `c()`.
- Then "Tests": what the tests cover, in one or two lines.
- No file inventory, no history of how the branch evolved, no padding.
- Short: a paragraph for a mechanical change, a few hundred words for a
  behavior change.

## PR Comments

One comment per meaningful change. Group related hunks into one comment;
never comment on trivial lines.

    ### `path:start-end` — <short title>
    What was added or changed, in one sentence.
    What happened before.
    The resulting flow or behavior, and why it matters to the reader.

## Important Observations

At most about five. Only items that change how the feature should be
understood:

- an unexpected behavior change,
- suspicious control flow,
- missing handling on a new path,
- dependency or configuration implications,
- tests that do not match the implementation.

Each item names the lines and the concrete consequence. For a full review,
tell the user to run a dedicated code-review skill.