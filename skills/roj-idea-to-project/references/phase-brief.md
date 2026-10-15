# Phase 1: Brief

Read before the first brief question. Output: `docs/brief.md` from
`assets/brief-template.md`.

## Before the first question

- State the path: `docs/brief.md`.
- Folder empty and no `.git`: offer `git init` once, as its own question
  (recommended: yes). Run it only on a yes. Never commit.
- Fill facts yourself: today's date, the Superpowers version note from
  phase 0 when it was outdated.

## Question order

One per message, each with a recommended answer worded so "yes" accepts:

1. Problem: 2 to 3 sentences. Recommend a wording built from the idea.
2. Target user and the main job they hire the app for.
3. Success metric: a number and a time frame ("80% of reminders acted on
   within 24 hours in the first month"). Reject metrics without both.
4. MVP scope: 3 to 5 bullets. Recommend the smallest set that delivers the
   job.
5. Non-goals: at least 5. Recommend 5 concrete ones derived from the idea
   and from what the MVP scope leaves out ("no native mobile app in the
   MVP", "no payments"). The user can accept, swap or add.
6. Constraints: budget, cloud, compliance, timeline.
7. Open questions: what the user cannot decide yet.

Draft the pitch (3 sentences) yourself from the answers; do not ask it.

## Draft and gate

1. Show the full draft.
2. Offer once, in one line: "Want a fresh chat to argue against this idea
   first?" On a yes, follow `references/review-gates.md` with the role
   "argue against this idea" and the brief as the only file.
3. Run `scripts/check_ready.py --phase brief <ROOT>`; fix with the user
   until it exits 0.
4. Ask for the gate approval. On a yes, write `Status: Approved
   YYYY-MM-DD` under the title.

Fewer than 5 non-goals is never approved, whatever the user says: name the
count, propose more, ask again.
