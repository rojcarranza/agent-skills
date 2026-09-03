---
name: soundboarding
description: Soundboarding (SB) workflow — turn a user story (LISA-<id>.md) into an SB document with codebase-investigated core tasks, or implement an existing SB document task by task with review stops. Use when the user says "soundboarding", "create an SB", "SB document", "implement SB-...", or asks to turn a user story into a refined, investigated task list before implementation.
---

# Soundboarding

Turn a user story into a soundboarding (SB) document grounded in real code
investigation, present it to the team for refinement, then implement it task
by task. Three flows: **create**, **implement**, and **create + implement**
chained. Pick the flow from what the user asked for.

## Configuration

- SOUNDBOARD_DIR: `/c/dev/projects/wr/soundboard` (Windows: `C:\dev\projects\wr\soundboard`)
- PROJECTS_ROOT: `/c/dev/projects` (Windows: `C:\dev\projects`)
- TEMPLATE: the `SB-template.md` file in this skill's own folder; if it is
  missing, fall back to `SOUNDBOARD_DIR/SB-template.md`.

These paths are defaults, not requirements — the user can override
SOUNDBOARD_DIR or PROJECTS_ROOT by stating different paths in their message.

## Hard rules (all flows)

1. **Truthfulness:** State as fact only file paths and values you actually
   read from local checkouts during this run. Everything unverified goes into
   the Questions section. Never present an assumption as a finding.
2. **Template fidelity:** Read TEMPLATE fresh at the start of every create
   run and produce every section it defines. If no template can be found:
   STOP and ask. Never invent the structure.
3. **Git: hands off.** Never create a branch, never commit, never push — in
   any repository. All edits stay in the working tree; the user reviews,
   commits, and branches manually. Read-only git commands (`git status`,
   `git diff`) are allowed.
4. **Ask, don't guess:** when something is ambiguous, ask the user one
   question and wait for the answer.

## Flow 1: Create an SB document

Input: a user story markdown file (example: `LISA-110278.md`). Resolve it as
given relative to the current workspace first, then inside SOUNDBOARD_DIR.
If it cannot be found or read: STOP and ask. Never proceed with an invented
story.

1. **Read inputs.** Read the story file and TEMPLATE. Extract the goal, the
   acceptance criteria, and every repository, system, tool, and version
   mentioned or implied.
2. **Identify impacted repositories.** The repository open in the current
   workspace is assumed impacted unless the story clearly says otherwise.
   For every other repository named or implied, look for a local checkout
   under PROJECTS_ROOT, searching one and two directory levels deep. If a
   repository has no local checkout, add it to Questions ("Repo X is not
   cloned locally — investigate before implementation") and do not guess its
   contents.
3. **Investigate the code.** For each locally available impacted repository,
   find the concrete things that must change: exact files and paths, current
   values (versions, config properties, image tags, dependencies) and the
   required new values, and things already compliant — list those too, so
   the team knows they were checked. Record current values exactly as they
   appear in the files.
4. **Compose the SB document.** Follow TEMPLATE structure exactly:
   - **Title / Goal:** from the story.
   - **Acceptance Criteria:** copy the story's criteria verbatim as `- [ ]`
     checkboxes. Add newly discovered criteria as extra checkboxes suffixed
     with `*(proposed)*`.
   - **Core tasks:** concrete `- [ ]` checkboxes. Each code task starts with
     the repository it touches in backticks. Where investigation found exact
     changes, include before/after tables with columns: #, File/Property,
     Before, After, Reason. Non-code tasks (emails, requests to other teams)
     are plain checkboxes without a repo tag.
   - **Questions:** unknowns from the investigation, missing repos, story
     ambiguities — plus every standing question already in the template.
   - **Notes:** risks, environment caveats, and one line listing the
     impacted repositories.
   - **Testing:** proposed test cases with Test Case ID (TC-1, TC-2, ...),
     Situation, and Expected result filled in; leave Log and Build result
     link cells empty — they are completed during implementation.
5. **Write the output file.** Name it `SB-` + the story file's basename
   (`LISA-110278.md` → `SB-LISA-110278.md`) and write it into SOUNDBOARD_DIR
   by absolute path, regardless of the current workspace. If file-editing
   tools refuse to write outside the workspace, write from the terminal. If
   the output file already exists: show a short summary of what would change
   and ask before overwriting.
6. **Report.** End with a short summary: repositories investigated, findings
   verified vs assumed, and the open questions for team refinement.
7. **Tour.** Write the tour of the code the core tasks will touch (see Tour
   output) — it makes the investigation reviewable in the editor.

See `examples/LISA-110278.md` (story) and `examples/sb-LISA-110278.md`
(resulting SB) for the expected shape.

## Flow 2: Implement an SB document

Input: an SB document name or file (examples: `SB-LISA-110278`,
`SB-LISA-110278.md`, or an attached/opened file). A bare name resolves
inside SOUNDBOARD_DIR; `.md` is optional and matching is case-insensitive.
Multiple matches: list them and ask which. No match: STOP and ask.

1. **Read the SB document.** Parse the Core tasks checkboxes. Tasks already
   ticked `- [x]` are done — skip them (resumable mid-sprint).
2. **Determine target repositories.** The repository open in the current
   workspace is the primary target. A task starting with another repository
   name in backticks targets that repository's checkout under PROJECTS_ROOT
   (search one and two levels deep).
3. **Preflight.** Verify every repository needed by the remaining tasks
   exists locally; if one is missing, report which and STOP before touching
   anything. Run `git status --porcelain` in each target repository and warn
   about dirty working trees (informational only — continue after warning).
4. **Per-task loop.** For each unticked core task, in order:
   1. Announce the task.
   2. Non-code task (no repo tag — typically inform, email, request
      permissions, present to team): do not execute, do not tick; say it is
      manual and go to the review stop.
   3. Code task: make the edits in the target repository.
   4. Show what changed: files touched and a brief summary of each change.
   5. STOP and ask: approve, request changes, or skip?
      - Approve → tick a code task's checkbox to `- [x]` in the SB file
        (manual tasks stay unticked); continue.
      - Request changes → revise, show the result, stop again.
      - Skip → leave unticked, note the skip, continue.
5. **Testing phase.** For each Testing table row, run whatever is locally
   runnable (unit tests, linters, builds) and write a one-line result into
   the Log column — only results of commands actually run. For tests
   needing unreachable environments: set Log to `manual — pending`. Leave
   Build result link cells for the user. If the SB file is outside the
   workspace and editing tools refuse, update it from the terminal.
6. **Wrap-up.** Update the SB file (checkboxes, Testing table, add learnings
   to Notes). Report a per-repository list of changed files for manual
   review and commit, plus the manual tasks still open.
7. **Tour.** Refresh the tour (see Tour output) so it walks the code as
   implemented, not as planned.

## Flow 3: Create + implement in one run

For stories where team refinement between soundboarding and implementation
is skipped.

1. Run Flow 1 on the user's story input.
2. When the SB file is written, present a short summary and ask exactly one
   confirmation question: "SB created — proceed with implementation?" Wait.
   If declined, stop; the SB file stays as created.
3. On confirmation, run Flow 2 on the SB file just created — including every
   per-task review stop and the no-git rule.

## Tour output

Both flows end with a replayable CodeTour of the affected code, so the SB is
reviewable in the editor and not only as prose.

- **Path**: `.tours/sb-<LISA-id>.tour` in the primary target repository
  (`SB-LISA-110278.md` → `.tours/sb-LISA-110278.tour`). Tasks spanning
  repositories: one tour per repository, same name.
- **Persona**: `contributor`.
- **Steps**: Flow 1 — the `file:line` findings behind the core tasks, in the
  order the tasks are listed. Flow 2 — the same tour refreshed to the code as
  implemented, one step per changed location. Never investigate a second time
  to build the tour.
- **How**: chain to the `code-tour` skill. Missing? Write the tour inline —
  a JSON object with `$schema`, `title`, `description` and `steps` of
  `{file, line, description}` is enough for CodeTour to open it.
- **Validate**: `code-tour` ships `scripts/validate_tour.py`. Resolve it from
  the code-tour skill directory that is actually installed
  (`~/.claude/skills/code-tour/`, or `~/.copilot/skills/code-tour/`) — its
  SKILL.md documents a `~/.agents/...` path that does not exist here.

Skip the tour only when ALL hold: one file, no cross-file flow, under ~3
steps. Then say so in one line with the reason. The user asking for a tour
overrides a skip; "no tour" overrides the default. An SB with only non-code
tasks has nothing to walk: skip it and say so.

`.tours/` is in the global git ignore, so tours stay local — never add them
to the repo's `.gitignore` or commit them. This does not weaken the no-git
rule: writing a tour file is not a git operation.
