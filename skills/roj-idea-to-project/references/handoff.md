# Phase 6 and 7: plan and hand-off

Read before writing the plan and before the hand-off.

## Definition of Ready

Run `scripts/check_ready.py --phase all <ROOT>` as a loop until it prints
`READY`. It checks: 5+ non-goals; every `FR-x.y` in EARS form; a
`Verification:` line per FR; `NFR-SEC`; ADRs for language, persistence,
auth, deploy target and observability; `CLAUDE.md` under 100 lines. The
user has also confirmed the `CLAUDE.md` commands in a fresh shell
(phase 5) and every fresh review has a decided `## Review log`.

## The plan

Suggest a new session first (`/clear`; Copilot CLI `/new`): the files carry
the context. Then invoke `superpowers:writing-plans` with the design spec,
`docs/requirements.md`, `docs/architecture.md` and `docs/adr/`, and these
rules:

- Task 1 is a walking skeleton: repo layout, CI, one request end to end,
  a dev deploy.
- Every task names the requirement IDs it serves and uses this format:

  ```
  ### Task 7: <imperative title>  [FR-2.1, NFR-SEC]
  Files: create <path>, modify <path>, test <path>
  Interface: <signature>
  Test first: <test name> expects <result>
  Verify: <command> (fails before, passes after)
  Done when: tests green, lint clean, committed
  Out of scope: <what waits for a later task>
  ```

- Fill `## Traceability` in `docs/requirements.md` from the plan:
  requirement → task → test.
- Overrides: do not commit the plan; stop after writing it and return to
  this gate instead of starting execution.

Gate: fresh-context review with `<plan>` plus `architecture-guardian` on the
plan file, findings into a `## Review log` at the end of the plan, then the
approval.

## Hand-off

1. Write `docs/progress.md` from `assets/progress-template.md`: one
   `- [ ] FR-<n> <name> (verify: <the FR's Verification>)` line per FR.
2. Tell the user, then stop:
   - Start a new session in a worktree (`superpowers:using-git-worktrees`)
     and run `superpowers:subagent-driven-development` on the plan. Watch
     the first 2 to 3 tasks, then let it run. Keep `docs/progress.md`
     current.
   - Review: `/code-review`, then the three reviewer agents, then read the
     diff yourself. Fix only correctness and requirement gaps. Merge with
     `superpowers:finishing-a-development-branch`.
   - Deploy is a feature with its own spec. Agent credentials stop at dev
     and staging.
   - After the first merge, a 10-minute retro: turn each repeated mistake
     into a hook, test, ADR or `CLAUDE.md` line; delete lines that changed
     nothing.
   - For a later change that fits in one sentence, native plan mode is
     enough; anything bigger goes back through this skill's phases.
