---
agent: agent
description: Execute the core tasks of a soundboarding (SB) document task by task, with a review stop after each
---

# /implement-sb — Implement a Soundboarding Document

You execute the Core tasks of an existing SB document, one task at a time, stopping for user review after every task.

## Configuration

- SOUNDBOARD_DIR: `/c/dev/projects/wr/soundboard`
- PROJECTS_ROOT: `/c/dev/projects`

On Windows these Git Bash paths map to `C:\dev\projects\wr\soundboard` and `C:\dev\projects`.

These paths are defaults, not requirements — override SOUNDBOARD_DIR or PROJECTS_ROOT by stating different paths in your message.

## Input

The user names or attaches an SB document (examples: `SB-LISA-110278`, `SB-LISA-110278.md`, or an attached file). Resolve it like this:

- Attached file: use it directly.
- A name: resolve it inside SOUNDBOARD_DIR. The `.md` extension is optional and matching is case-insensitive.
- Multiple matches (example: `SB-LISA-108692 - Batch 1.md` and `SB-LISA-108692 - Batch 2.md`): list them and ask which one.
- No match: STOP and ask.

## Hard rules

1. **Git: hands off.** Never create a branch, never commit, never push — in any repository. All edits stay in the working tree. The user reviews, commits, and branches manually. You may run read-only git commands (`git status`, `git diff`).
2. **One task, then stop.** After each core task, stop and wait for explicit user approval before continuing to the next.
3. **Ask, don't guess:** if a task is ambiguous, ask the user one question and wait for the answer.
4. **Truthful testing:** write into the Testing table only the results of commands you actually ran.

## Steps

### 1. Read the SB document

Parse the Core tasks checkboxes. Tasks already ticked `- [x]` are done — skip them. This makes the skill resumable mid-sprint.

### 2. Determine target repositories

- The repository open in the current workspace is the primary target.
- A task that starts with another repository name in backticks targets that repository's local checkout under PROJECTS_ROOT (search one and two directory levels deep).

### 3. Preflight

- Verify every repository needed by the remaining tasks exists locally. If one is missing: report which, and STOP before touching anything.
- Run `git status --porcelain` in each target repository. If a working tree is dirty, warn the user which files are already modified. This is informational only — continue after warning.

### 4. Per-task loop

For each unticked core task, in order:

1. Announce the task.
2. If it is a non-code task — it does not start with a repository name in backticks (typically inform, email, request permissions, present to team): do not execute it and do not tick it. Say it is manual and go to the review stop.
3. If it is a code task: make the edits in the target repository.
4. Show what changed: the files touched and a brief summary of each change.
5. STOP and ask: approve, request changes, or skip?
   - Approve → for a code task, tick the task's checkbox to `- [x]` in the SB file; for a manual task, leave it unticked (per step 2). Either way, continue to the next task.
   - Request changes → revise, show the result, stop again.
   - Skip → leave the checkbox unticked, note the skip, continue.

### 5. Testing phase

After the core tasks are done:

- For each row of the Testing table, run whatever is locally runnable (unit tests, linters, builds) and write a one-line result summary into the Log column.
- For tests that need environments you cannot reach (deployments, agent connectivity, other teams): set the Log cell to `manual — pending`. Leave the Build result link cells for the user.
- If the SB file is outside the current workspace and your editing tools refuse to modify it, update it from the terminal instead.

### 6. Wrap-up

- Update the SB file: checkboxes, the Testing table, and add anything important learned during implementation to Notes.
- Report a per-repository list of changed files so the user can review and commit manually, plus the list of manual tasks still open.
