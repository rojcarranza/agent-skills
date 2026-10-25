---
name: roj-soundboarding
description: Soundboarding (SB) workflow - turn a user story (a story .md, pasted Jira ticket text, or a Jira key or URL read through a connected Atlassian/Jira tool) into an SB document with codebase-investigated core tasks, or implement an existing SB document task by task with review stops. Use when the user says "soundboarding", "create an SB", "SB document", "implement SB-...", "plan this ticket", "break this story into tasks" or "refine this story", or asks to turn a story or ticket into a refined, investigated task list before implementation.
license: MIT
---

# Soundboarding

Turn a user story into a soundboarding (SB) document grounded in real code
investigation, present it to the team for refinement, then implement it task
by task. Three flows: **create**, **implement**, and **create + implement**
chained. Pick the flow from what the user asked for.

## Configuration

- SOUNDBOARD_DIR: where story files and SB documents live.
- PROJECTS_ROOT: the directory that holds local checkouts of the team's
  repositories.
- TEMPLATE: `SOUNDBOARD_DIR/SB-template.md` when it exists - a template
  you keep beside your stories overrides the bundled one, so each team or
  repository supplies its own standing questions. Otherwise
  `assets/SB-template.md` in this skill's own folder.

Resolve SOUNDBOARD_DIR and PROJECTS_ROOT in this order: a path stated in the
user's message, then the environment variable of the same name
(`echo "$SOUNDBOARD_DIR"`, `echo "$PROJECTS_ROOT"`; PowerShell:
`$env:SOUNDBOARD_DIR`). Still unset, never ask — use the defaults:

- SOUNDBOARD_DIR: the root of the repository the skill runs in
  (`git rev-parse --show-toplevel`; outside a git repository, the current
  working directory). Story files and SB documents then live next to the
  code they describe.
- PROJECTS_ROOT: the parent directory of that repository root.

State the resolved SOUNDBOARD_DIR and the TEMPLATE in use in one line at
the start of the run, so the user sees where the SB document will be
written and which template shapes it.

## Hard rules (all flows)

1. **Truthfulness:** State as fact only file paths and values you actually
   read from local checkouts during this run. Everything unverified goes into
   the Questions section. Never present an assumption as a finding.
2. **Template fidelity:** Read TEMPLATE fresh at the start of every create
   run and produce every section it defines, and no section it does not.
   If no template can be found: STOP and ask. Never invent the structure.
3. **Git: hands off.** Never create a branch, never commit, never push - in
   any repository. All edits stay in the working tree; the user reviews,
   commits, and branches manually. Read-only git commands (`git status`,
   `git diff`, `git branch --show-current`) are allowed. Jira is read-only
   too: never comment on, transition or edit a ticket.
4. **Ask, don't guess:** when something is ambiguous, ask the user one
   question and wait for the answer.
5. **Graph check, first and every run:** before investigating a repository,
   look for `graphify-out/graph.json` at its root. Present: follow
   `references/graph-first.md`. Absent: search directly. Close the final chat
   message with a Graph line only when it informs: `Graph: used` or
   `Graph: stale, skipped` when a graph exists, `Graph: none found, searched
   directly` only when a large repository (hundreds of source files) has none.
   Otherwise print no Graph line; this replaces the always-print closing rule
   in that file. The read-only `graphify` queries in that file are allowed
   alongside the read-only git commands.

## Flow 1: Create an SB document

Input: the user story, in any of these forms (pick by what the user gave):

- A story markdown file (example: `PROJ-1001.md`). Resolve it as given
  relative to the current workspace first, then inside SOUNDBOARD_DIR.
- Ticket text pasted into the message (a Jira issue copied from the browser,
  with or without its key).
- A Jira key (`PROJ-1001`) or issue URL with no file. Read it with an
  Atlassian or Jira tool when one is connected to this session (look at the
  tools you have for one that reads a single issue; use that tool's own
  arguments). Fetch only the issue: summary, description, acceptance
  criteria, labels and links. No such tool, or the call fails: ask the user to
  paste the ticket text, and wait. Never call the Jira REST API yourself, ask
  for a token, or write to Jira.

If the story cannot be found, read or fetched: STOP and ask. Never proceed
with an invented story. The story's key names the output file (step 5); pasted
text without a key: ask for a name for the file, once.

1. **Read inputs.** Read the story and TEMPLATE. Extract the goal, the
   acceptance criteria, and every repository, system, tool, and version
   mentioned or implied.
2. **Identify impacted repositories.** The repository open in the current
   workspace is assumed impacted unless the story clearly says otherwise.
   For every other repository named or implied, look for a local checkout
   under PROJECTS_ROOT, searching one and two directory levels deep. If a
   repository has no local checkout, add it to Questions ("Repo X is not
   cloned locally — investigate before implementation") and do not guess its
   contents.
3. **Investigate the code.** When a repository has a graph
   (`references/graph-first.md`), first run one `graphify query` per
   acceptance criterion to find the files, then read them — values still
   come from the files (rule 1).
   For each locally available impacted repository,
   find the concrete things that must change: exact files and paths, current
   values (versions, config properties, image tags, dependencies) and the
   required new values, and things already compliant — list those too, so
   the team knows they were checked. Record current values exactly as they
   appear in the files. When the story leans on a stack or tool no loaded
   skill covers (Terraform, Rust, …), add one Questions entry: "No skill
   loaded for <stack> — `npx skills find <stack>` may have one" (run the
   search through `find-skills` when it is available). Suggest only: never
   install a skill during the run.
4. **Compose the SB document.** Follow TEMPLATE structure exactly:
   - **Title / Goal:** from the story.
   - **Acceptance Criteria:** copy the story's criteria verbatim as `- [ ]`
     checkboxes. Add newly discovered criteria as extra checkboxes suffixed
     with `*(proposed)*`.
   - **Core tasks:** concrete `- [ ]` checkboxes. Each code task starts with
     the repository it touches in backticks. Where investigation found exact
     changes, include before/after tables with columns: #, File/Property,
     Location, Before, After, Reason, Source. Location is `path:line` of the
     Before value as read this run. Source says where the After value and the
     Reason come from: `story` (with the criterion), a documentation URL you opened
     this run for a vendor fact, or `Question <n>` for an assumption you could not verify.
     A vendor or product fact with no Source goes into Questions instead of
     the table or Notes. Non-code tasks (emails, requests to other teams) are
     plain checkboxes without a repo tag.
   - **Questions:** unknowns from the investigation, missing repos, story
     ambiguities — plus every standing question already in the template.
   - **Notes:** risks, environment caveats, and one line listing the
     impacted repositories.
   - **Testing:** proposed test cases with Test Case ID (TC-1, TC-2, ...),
     Situation, and Expected result filled in; leave Log and Build result
     link cells empty — they are completed during implementation.
5. **Write the output file.** Name it `SB-` + the story file's basename
   (`PROJ-1001.md` → `SB-PROJ-1001.md`; `PROJ-1002 - Batch 1.md` →
   `SB-PROJ-1002 - Batch 1.md`); for a pasted or fetched story, `SB-` + its
   key (`SB-PROJ-1001.md`). Write it into SOUNDBOARD_DIR
   by absolute path, regardless of the current workspace. If file-editing
   tools refuse to write outside the workspace, write from the terminal. If
   the output file already exists: show a short summary of what would change
   and ask before overwriting.
6. **Report.** End with a short summary: repositories investigated, findings
   verified vs assumed, and the open questions for team refinement.
   When Questions has open items, offer in one line: "Grill the open
   questions now?" On a yes, chain to the `roj-grill-plan` skill on the SB
   file; if it is not installed, list the open questions with a recommended
   answer each. Never start grilling unasked. Skip the offer in Flow 3,
   which asks exactly one question.
7. **Tour (ask first).** Offer a tour of the code the core tasks will touch
   (see Tour output) and build it only on a yes.

See `examples/PROJ-1001.md` (story) and `examples/SB-PROJ-1001.md`
(resulting SB) for the expected shape.

## Flow 2: Implement an SB document

Input: an SB document name or file (examples: `SB-PROJ-1001`,
`SB-PROJ-1001.md`, or an attached/opened file). A bare name resolves
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
   anything. In each target repository run `git status --porcelain` and
   `git branch --show-current`, and warn about:
   - a dirty working tree;
   - the default branch: the current branch equals the one
     `git symbolic-ref --short refs/remotes/origin/HEAD` names (without
     `origin/`), or, when that is unset, is `main`, `master` or `develop`.
     Say: "Edits will land on <branch>. This skill never creates a branch;
     run `git switch -c <type>/<TICKET-ID>` first, or later - uncommitted
     edits move with you."

   Both warnings are informational only - continue after warning.
   Then run the **baseline test** once per target repository, before the
   first task, when no core task is ticked yet and Notes has no baseline line
   (otherwise the tree already carries task edits; say it is skipped). Pick the
   command as `references/test-commands.md` describes. Record the result as
   one Notes line - `Baseline (<repo>): <command> - <passed | N failing: names>`
   - so failures that predate the work stay separate from the task's. A
   failing baseline is recorded, not fixed; continue.
4. **Per-task loop.** For each unticked core task, in order:
   1. Announce the task.
   2. Non-code task (no repo tag — typically inform, email, request
      permissions, present to team): do not execute, do not tick; say it is
      manual and go to the review stop.
   3. Code task: make the edits in the target repository.
   4. Verify before reporting: run `git diff` in the target repository and
      compare it with the task's before/after table. Every listed change
      must be present with the exact After value, and no file outside the
      task may have new changes (files preflight already reported as dirty
      are exempt unless the task edits them). Report any mismatch.
   5. Run the narrowest relevant check for the files the task changed (the
      test file or package covering them, or the linter for a config
      file), as `references/test-commands.md` describes. Compare a failure
      with the baseline: one the baseline already had is pre-existing; a new
      one follows the root-cause rule of the Testing phase. No narrower
      check exists: say so - never invent a command or a result.
   6. Show what changed: files touched, a brief summary of each change, and
      the check run with its one-line result.
   7. STOP and ask: approve, request changes, or skip?
      - Approve → tick a code task's checkbox to `- [x]` in the SB file
        (manual tasks stay unticked); continue.
      - Request changes → revise, show the result, stop again.
      - Skip → leave unticked, note the skip, continue.
5. **Testing phase.** For each Testing table row, run whatever is locally
   runnable (unit tests, linters, builds) and write a one-line result into
   the Log column — only results of commands actually run. A failing test,
   lint or build: find the root cause first (read the full error, form a
   hypothesis, confirm it), then propose the fix and stop for approval —
   never stack guess-fixes. For tests
   needing unreachable environments: set Log to `manual — pending`. Leave
   Build result link cells for the user. If the SB file is outside the
   workspace and editing tools refuse, update it from the terminal.
6. **Wrap-up.** Update the SB file (checkboxes, Testing table, add learnings
   to Notes). Report a per-repository list of changed files for manual
   review and commit, plus the manual tasks still open.
   When any code task was approved, offer in one line: "Review the working
   tree with roj-code-review-pr?" On a yes, chain to `roj-code-review-pr` on
   the uncommitted changes, with the SB's Acceptance Criteria as the intent
   it checks against; if the skill is not installed, say so and stop. Never
   start the review unasked.
7. **Tour (ask first).** Offer to refresh the tour (see Tour output) so it
   walks the code as implemented, not as planned. Build it only on a yes.

## Flow 3: Create + implement in one run

For stories where team refinement between soundboarding and implementation
is skipped.

1. Run Flow 1 on the user's story input.
2. When the SB file is written, present a short summary and ask exactly one
   confirmation question: "SB created — proceed with implementation?" Wait.
   If declined, stop; the SB file stays as created.
3. On confirmation, run Flow 2 on the SB file just created — including every
   per-task review stop and the no-git rule.

## Tour output (ask first)

**Off by default.** Offer in one line at the end of either flow — "Want a
CodeTour of the affected code?" — and build it only on a yes. "Make a tour"
up front skips the offer; "no tour" suppresses it. Skip the offer too when
the SB touches one file with no cross-file flow in under ~3 steps, or has
only non-code tasks.

- **Path**: `.tours/sb-<TICKET-ID>.tour` in the primary target repository
  (`SB-PROJ-1001.md` → `.tours/sb-PROJ-1001.tour`); one tour per
  repository when tasks span several, same name.

- **Persona**: `contributor`.

- **Steps**: Flow 1 — the `file:line` findings behind the core tasks, in
  task order. Flow 2 — the same tour refreshed to the code as implemented,
  one step per changed location. Never investigate a second time.

On a yes, chain to `code-tour`; if it is not installed write the JSON inline
(`$schema`, `title`, `description`, `steps` of `{file, line, description}`).
Validate with its `scripts/validate_tour.py` from whichever installed dir
exists — resolve `~` to an absolute path (cmd does not expand it) and try
`python`, then `python3`; skip validation rather than failing the run.
`.tours/` is in the global git ignore: never commit a tour or edit
`.gitignore`. Writing a tour file is not a git operation, so this does not
weaken the no-git rule.
