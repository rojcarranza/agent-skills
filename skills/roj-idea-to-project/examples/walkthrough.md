# Walkthrough: from idea to build-ready repo

One example app, **Plant Pal** (a web app that emails you which house plants
need water today), taken through every phase in Claude Code. The skill's
messages are shortened; script output is shown exactly as the scripts print
it. Your answers can be as short as `yes`.

## Contents

- [Before you start](#before-you-start)
- [Phase 0: Superpowers](#phase-0-superpowers)
- [Phase 1: Brief](#phase-1-brief)
- [Phase 2: Design](#phase-2-design)
- [Phase 3: Requirements and the first fresh review](#phase-3-requirements-and-the-first-fresh-review)
- [Phase 4: Architecture and ADRs](#phase-4-architecture-and-adrs)
- [Phase 5: Agent config](#phase-5-agent-config)
- [Taking a break: resume after /clear](#taking-a-break-resume-after-clear)
- [Phase 6: Definition of Ready and the plan](#phase-6-definition-of-ready-and-the-plan)
- [Phase 7: Hand-off and building](#phase-7-hand-off-and-building)
- [Answers that work at any gate](#answers-that-work-at-any-gate)
- [When something goes wrong](#when-something-goes-wrong)

## Before you start

- Open Claude Code (or GitHub Copilot CLI) **in the project folder**. An
  empty folder is fine; the skill writes every file relative to it.
- Have Python 3 on PATH (`python3 --version`); the skill's two checks are
  Python scripts.
- Set aside 1 to 3 hours for phases 1 to 6. You can stop after any gate and
  resume later: the state lives in the files, not in the chat.
- Nothing is committed for you. Commit the files yourself whenever you like.

Start with your idea in plain words:

```
/roj-idea-to-project an app that emails me which of my plants need water today
```

Every run starts by showing where the project stands:

```
- [ ] 0 Setup: Superpowers installed, enabled, reloaded
- [ ] 1 Brief: docs/brief.md
- [ ] 2 Design: docs/superpowers/specs/<date>-<topic>-design.md
- [ ] 3 Requirements: docs/requirements.md (reviewed)
- [ ] 4 Architecture: docs/architecture.md + docs/adr/ (reviewed)
- [ ] 5 Agent config: CLAUDE.md, .claude/settings.json, .claude/agents/
- [ ] 6 Ready + plan: check_ready.py passes; plan (reviewed)
- [ ] 7 Hand-off: docs/progress.md
```

## Phase 0: Superpowers

The skill runs `scripts/check_superpowers.py --client claude`. On a machine
without Superpowers it prints:

```
{"client": "claude", "installed": false, "version": null, "version_comparable": false, "enabled": null, "status": "missing", "next": ["claude plugin install superpowers@claude-plugins-official"]}
```

The skill explains what it will install (the Superpowers plugin), from
where (`claude-plugins-official`), why (phases 2, 6 and 7 call its
brainstorming, planning and build skills) and what changes (a user-scope
plugin install, nothing in your project), then asks:

> Install it now? I recommend yes.

```
yes
```

It runs `claude plugin install superpowers@claude-plugins-official`, which
prints `Successfully installed plugin: superpowers@claude-plugins-official
(scope: user)`, and then stops:

> Run `/reload-plugins` in this session (Copilot CLI: exit and restart
> `copilot`), then tell me when it's done.

The agent cannot reload plugins itself. Type:

```
/reload-plugins
```

```
done
```

The check now prints `"status": "ok"` and the skill confirms
`superpowers:brainstorming` is in its own skill list. Phase 0 is ticked.

Variations:

- **Already installed:** phase 0 passes without a question.
- **Older than v7.0.0:** the skill offers
  `claude plugin update superpowers@claude-plugins-official`. Say `no` and
  it continues, noting the version in the brief.
- **You said yes up front** ("…and yes, install Superpowers"): it installs
  without asking again. This is the only up-front yes it accepts.
- **Install fails:** it shows the error exactly and the command to run in
  your own terminal, then waits.

## Phase 1: Brief

Output: `docs/brief.md`. The skill names the path, then asks **one question
per message**, each with its suggested answer. In an empty folder it also
mentions, once: "This folder is not a git repo; say `git init` whenever you
want one."

> **Problem.** Suggested: "I forget to water my house plants and they die.
> Calendar reminders don't fit plants with different intervals." Use this?

```
yes
```

> **Target user and job.** Suggested: "Busy flat-dwellers with 5 to 20
> plants: know what to water today." OK?

```
yes, but say 3 to 30 plants
```

The questions continue: a **success metric** (it must have a number and a
time frame, e.g. "80% of reminders acted on within 24 hours in the first
month"), **MVP scope** (3 to 5 bullets), **non-goals**, **constraints** and
**open questions**. The pitch is drafted for you.

**Non-goals** need at least 5. The skill proposes 5 from your idea:

> 1. No native mobile app  2. No plant identification from photos
> 3. No social or sharing features  4. No sensor or smart-pot integration
> 5. No payments. Accept these?

```
yes, and add "no push notifications in the MVP"
```

Before the gate the skill runs `scripts/check_ready.py --phase brief` and
offers, once, a fresh chat that argues against the idea (`no` is fine).
Then:

> Approve `docs/brief.md`?

```
yes
```

It adds `Status: Approved 2026-10-15` under the title. With fewer than 5
non-goals the check prints, for example,
`docs/brief.md has 2 non-goals: add at least 3 more under ## Non-goals`, and
the skill will not move on, whatever you answer.

## Phase 2: Design

The skill hands your brief to `superpowers:brainstorming`, which asks its
own questions one at a time (data model, how reminders are scheduled,
trade-offs) and writes
`docs/superpowers/specs/2026-10-15-plant-pal-design.md`. Inside this skill
it does not commit the spec, and after you approve it comes back to phase 3
instead of starting a plan.

```
yes, approve the design
```

## Phase 3: Requirements and the first fresh review

Output: `docs/requirements.md`. One `### FR-<n>` block per MVP bullet, every
requirement in EARS form, a failure path per FR and a `Verification:` line
naming the test:

```
### FR-2 Reminders
User story: As an owner, I want a daily email so that I water on time.
- FR-2.1 WHEN a plant is due THE SYSTEM SHALL email the owner by 08:00 local time.
- FR-2.2 IF the email fails THEN THE SYSTEM SHALL retry once after 10 minutes.
Verification: tests/test_reminders.py::test_due_plant_emailed
```

The gate check catches gaps and says how to fix each one. A draft with
FR-1 missing its failure path and FR-2 missing its test prints:

```
FR-1 has no IF ... THEN failure-path bullet: add "- FR-1.<m> IF <unwanted condition> THEN THE SYSTEM SHALL <response>."
FR-2 has no Verification line: add "Verification: <test name or command>"
NOT READY: 2 issues
```

The skill proposes each fix as a question; it re-runs the check until it
prints `READY`.

Then the **fresh-context review**. The skill starts a reviewer (a subagent
on `opus`) that gets only the file paths and a red-team prompt, never this
conversation. Findings come back one per message, with a recommendation:

> **[major]** "THE SYSTEM SHALL email the owner by 08:00 local time"
> doesn't say whose local time. Fix: store a time zone per owner.
> Recommendation: accept.

```
accept
```

> **[minor]** "retry once after 10 minutes": a queue would be simpler to
> reason about. Recommendation: reject (one retry is enough for an MVP).

```
reject, because one retry is enough for the MVP
```

Both decisions are written into the file's `## Review log`:

```
- [major] "email the owner by 08:00 local time" → accepted: time zone stored per owner (FR-1.3)
- [minor] "retry once after 10 minutes" → rejected: one retry is enough for the MVP
```

Then the gate. **"I approve everything" does not skip it:**

```
I approve everything, keep going
```

> Thanks, but I can't take that as approval for the gates ahead. Approve
> `docs/requirements.md` as it stands now?

```
yes
```

## Phase 4: Architecture and ADRs

Output: `docs/architecture.md` (C4 context and container diagrams, data
ownership, threat model) and one ADR per decision in `docs/adr/`. The
skill suggests switching to `opus` and plan mode for this phase.

The skill looks facts up (prices, free tiers, limits, with sources) and
asks you only for the choice, one ADR at a time:

> **Persistence.** Options: SQLite on a persistent volume (no extra cost,
> one instance) or managed Postgres (a monthly fee, scales out); the skill
> quotes the current price it looked up, with the source. Your budget is
> under 10 USD a month. Recommendation: SQLite. OK?

```
yes
```

Each ADR names the area it decides with an `Area:` line:

```
# ADR-0002: SQLite on a volume
Status: Accepted
Area: persistence
```

The check needs ADRs for language, persistence, auth, deploy target and
observability. With only the first two written it prints:

```
no ADR covers auth: add docs/adr/NNNN-auth.md, or add "Area: auth" to the ADR that decides it (a file name or title mentioning one of auth, authentication, authorization, identity also counts)
no ADR covers deploy target: add docs/adr/NNNN-deploy-target.md, or add "Area: deploy target" to the ADR that decides it (a file name or title mentioning one of deploy, deployment, hosting, infrastructure also counts)
no ADR covers observability: add docs/adr/NNNN-observability.md, or add "Area: observability" to the ADR that decides it (a file name or title mentioning one of observability, logging, monitoring, telemetry also counts)
NOT READY: 3 issues
```

The skill asks the three remaining decisions, re-runs the check, runs a
fresh review of the architecture (same accept and reject flow), then asks
for the gate approval.

## Phase 5: Agent config

The skill lists five paths and writes them on one `yes`:

- `CLAUDE.md`: under 100 lines, with the exact build, test, lint and run
  commands for the stack you chose
- `.claude/settings.json`: hooks that run the formatter and linter after
  each edit, and block edits to `.env*`, `infra/prod/` and `migrations/`
- `.claude/agents/security-reviewer.md`, `architecture-guardian.md`,
  `test-auditor.md`: reviewers for later

It shows every hook command before writing. It also **suggests** free
checks for your stack (a linter, Semgrep CE, `pip-audit`, gitleaks) but
installs none of them.

Then it asks you to run the commands that can work before any code exists
in a fresh terminal (for example `python3 --version`, `ruff --version`) and
report back:

```
all work
```

Commands that need code (the test run, the server) are marked "verified by
plan task 1" in `CLAUDE.md`: the first build task makes them runnable. The
hook that runs your tests when the agent stops is added in that task too,
so it cannot block the planning session.

## Taking a break: resume after /clear

The skill recommends a fresh session before the plan. Type `/clear` (or
close the session), then later, in the same folder:

```
/roj-idea-to-project continue
```

It rebuilds the checklist from the files and their `Status: Approved`
lines:

```
- [x] 0 Setup: Superpowers installed, enabled, reloaded (7.0.0)
- [x] 1 Brief: docs/brief.md
- [x] 2 Design: docs/superpowers/specs/2026-10-15-plant-pal-design.md
- [x] 3 Requirements: docs/requirements.md (reviewed)
- [x] 4 Architecture: docs/architecture.md + docs/adr/ (reviewed)
- [x] 5 Agent config: CLAUDE.md, .claude/settings.json, .claude/agents/
- [ ] 6 Ready + plan: check_ready.py passes; plan (reviewed)
- [ ] 7 Hand-off: docs/progress.md
```

If you edited an approved file and it no longer passes its check, the skill
resumes at that phase and tells you why.

## Phase 6: Definition of Ready and the plan

First `scripts/check_ready.py --phase all` runs until it prints `READY`.
Then `superpowers:writing-plans` writes
`docs/superpowers/plans/2026-10-15-plant-pal.md`. Task 1 is a walking
skeleton (repo layout, CI, one request end to end, a dev deploy); every task
names the requirement IDs it serves, its files, the test written first and
the command that proves it:

```
### Task 3: Send the daily reminder email  [FR-2.1, FR-2.2, NFR-SEC]
Files: create app/reminders.py, test tests/test_reminders.py
Test first: test_due_plant_emailed expects one email per owner with all due plants
Verify: pytest tests/test_reminders.py (fails before, passes after)
Done when: tests green, lint clean, committed
Out of scope: SMS or push
```

The plan gets a fresh review plus the `architecture-guardian` agent, the
same accept and reject flow, then the last approval.

## Phase 7: Hand-off and building

The skill writes `docs/progress.md`, one line per FR with its verify
command, and stops. It builds nothing. To build:

1. Start a **new** Claude Code session in the project folder (ideally in a
   git worktree) and ask it to run `superpowers:subagent-driven-development`
   on `docs/superpowers/plans/2026-10-15-plant-pal.md`.
2. Watch the first 2 or 3 tasks, then let it run. Keep `docs/progress.md`
   ticked as features pass.
3. Review: `/code-review`, then the three reviewer agents, then read the
   diff yourself.
4. After the first merge, spend 10 minutes on a retro: turn each repeated
   mistake into a hook, a test, an ADR or a `CLAUDE.md` line.

## Answers that work at any gate

| You type | Effect |
|---|---|
| `yes` | Accepts the suggested answer, or approves this gate only |
| `no, <your answer>` | Uses your answer instead |
| `accept` / `reject, because …` | Decides a review finding; recorded in `## Review log` |
| `I approve everything` | Thanked, then each gate is still asked |
| `git init` | Initialises git in an empty folder (never commits) |
| `continue` | Resumes at the first phase that is not approved |

## When something goes wrong

| Symptom | What to do |
|---|---|
| "This skill needs Claude Code or GitHub Copilot CLI" | You are in Copilot inside VS Code or JetBrains, which Superpowers does not support yet (#30). Switch to Claude Code or Copilot CLI. |
| Phase 0 asks for `/reload-plugins` again after you said done | The session did not reload. Type `/reload-plugins` (Copilot CLI: restart `copilot`), then say done. |
| The check times out | `claude` is waiting on a prompt (first run or login). Run `claude` once in your own terminal, then continue. |
| `NOT READY` you do not understand | Run `python3 <skill dir>/scripts/check_ready.py --phase <phase>` yourself: every line says what to add. |
| A reviewer finding is only about style | The skill drops those; only correctness, security and requirement gaps reach you. |
