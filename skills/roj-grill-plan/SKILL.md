---
name: roj-grill-plan
description: Grill the user on a user story, an SB (soundboarding) document or a plan pasted in chat, in rounds of numbered questions that each carry a recommended answer, until no decision is left silently assumed. Looks facts up in the repo itself and only asks for decisions, then writes the agreed answers back into the file after confirmation. Use when the user says "grill me on this story", "grill SB-PROJ-123", "stress-test this plan", "poke holes in my plan", "resolve the open questions in the SB", or accepts the grilling offer at the end of a roj-soundboarding run. Not for finding defects in code (roj-code-review-pr) or explaining code (roj-explain-logic).
license: MIT
---

# Grill Plan

Interview the user about a story, an SB document or a plan until both sides
share one understanding of it. Map the open decisions as a **design tree**:
each decision branches into the decisions that hang off it. Work the tree in
**rounds**, then write the agreed answers back where the team will read them.

## Inputs

- **User story** `.md` (example: `PROJ-1001.md`).
- **SB document** (`SB-*.md`): it has the soundboarding headings Acceptance
  Criteria, Core tasks, Questions, Notes and Testing.
- **Plan in chat**: pasted text or the plan from the current conversation.

Resolve a file as given relative to the workspace first, then inside
`$SOUNDBOARD_DIR` when that variable is set. The `.md` suffix is optional and
matching is case-insensitive (`SB-PROJ-1001` finds `SB-PROJ-1001.md`).
Multiple matches: list them and ask which. Not found: STOP and ask. Never
grill an invented story.

## Hard rules

1. **Facts are yours, decisions are the user's.** When a question needs a
   fact (a version, a path, whether a config or caller exists), find it
   yourself by reading files and running read-only git (`git log`,
   `git show`, `git grep`) and the read-only `graphify` queries. Never ask
   the user for something you can look up. Put each decision to the user and
   wait.
2. **Truthfulness.** State as fact only what you read during this run, with
   `file:line`. A fact you cannot reach (repository not cloned, another
   team's system) is not guessed: it becomes a "needs someone else" item.
3. **No acting on the plan.** Do not implement anything. The only file this
   skill edits is the input file, and only after the confirmation in step 5.
4. **Git: hands off.** Never create a branch, commit or push.
5. **Graph check, first and every run:** before looking facts up in a
   repository, look for `graphify-out/graph.json` at its root. Present:
   follow `references/graph-first.md`. Absent: search directly. Close the
   final chat message with a Graph line only when it informs: `Graph: used` or
   `Graph: stale, skipped` when a graph exists, `Graph: none found, searched
   directly` only when a large repository (hundreds of source files) has none;
   otherwise print no Graph line.

## Flow

1. **Map the tree.** Read the input. List every open decision:
   - SB document: every Questions item, every Acceptance Criteria item
     marked *(proposed)*, and every core task whose before/after table has an
     empty or `?` cell.
   - Story or plan: the goal, scope edges, acceptance criteria that cannot
     be checked yes or no, risks, and dependencies on other teams.
   Drop decisions the input already answers.
2. **Settle the facts first.** For each item that is really a fact, look it
   up (rule 1) and report it as a finding, not a question:
   `✅ requests is pinned to 2.32.3 (requirements.txt:1)`.
3. **Ask a round.** The **frontier** is every decision whose prerequisites
   are settled. Ask the frontier, at most 7 questions per round (the rest wait
   for the next one), numbered across the whole session:

   ```
   ❓ **Q1** - **<question title>**: <question body, options if any>

   ➡️ <your recommended answer, with the reason in one line>

   ---
   ```

   Word each question so "yes" accepts your recommendation. A question that
   depends on another question still open in this round belongs to a later
   round. Then STOP and wait. The user can answer "yes to all", "Q2 no,
   <answer>", or "skip Q3" (it stays open).
4. **Recompute and repeat.** Each answer reshapes the tree: settled
   decisions unblock the ones that hang off them, and an answer can raise new
   questions. Keep a running decision log. Stop when the frontier is empty or
   the user says stop.
5. **Confirm.** Present the log under three bold labels, **Resolved**,
   **Still open** and **Needs someone else**, then ask one question:
   "Shared understanding reached. Write this back to `<file>`?" For a plan in
   chat there is no file: the log is the output, so end here.
6. **Write back** (on a yes only). Show a short summary of what will change
   first.
   - SB document: rewrite the Questions section only. Resolved items become
     `- [x] <question> → <answer>`; open ones stay `- [ ] <question>` with
     `(open: <reason>)` or `(needs: <role>)` appended. Add questions the
     session raised, in the same form. When an answer changes an Acceptance
     Criteria item, a core task or a Testing row, propose that edit and apply
     it only on a separate yes.
   - User story: add a `## Decisions` section at the end (update it when it
     already exists) in the same checkbox form. Leave the rest untouched.
7. **Hand off.** When items need someone else, offer in one line to turn
   them into a questionnaire with the `to-questionnaire` skill; when it is
   not installed, list them in chat grouped by who must answer. When the
   input was an SB document with nothing left open, name the next step:
   `/roj-soundboarding implement SB-<TICKET-ID>`.

See `examples/grill-round.md` for one round and the written-back Questions
section.
