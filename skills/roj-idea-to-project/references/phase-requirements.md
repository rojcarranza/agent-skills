# Phase 3: Requirements

Read before drafting requirements. Output: `docs/requirements.md` from
`assets/requirements-template.md`. Inputs: `docs/brief.md` and the approved
design spec.

## Format

- One `### FR-<n> <name>` block per MVP-scope bullet, numbered from 1.
- Each block: one user story line, then requirement bullets, then one
  `Verification:` line naming a test or a command.
- Every requirement bullet is `- FR-<n>.<m> <pattern> ... THE SYSTEM SHALL ...`:

  | Pattern | Use for |
  |---|---|
  | `WHEN <trigger>` | an event |
  | `IF <unwanted condition> THEN` | an error or abuse case |
  | `WHILE <state>` | behaviour during a state |
  | `WHERE <feature is present>` | an optional feature |

- Each FR has at least one `IF ... THEN` bullet: the failure path.
- `Verification:` names something that will exist: a test file and name,
  or a command with its expected result. Never the template placeholder.

## Non-functional requirements

Each carries a number:

- `NFR-PERF`: a percentile, a latency and a load (`p95 < 300 ms at 5 rps`).
- `NFR-SEC`: always present: authn, authz, the boundary where input is
  validated, where secrets come from.
- `NFR-OPS`: logs, metrics, RTO and RPO.
- `NFR-COST`: an amount per month.

## Other sections

- `## Out of scope`: the brief's non-goals, word for word.
- `## Traceability`: leave the heading; phase 6 fills it from the plan.
- `## Review log`: filled at the gate.

## Gate

1. Run `scripts/check_ready.py --phase requirements <ROOT>`; fix with the
   user until it exits 0.
2. Fresh-context review: follow `references/review-gates.md` with
   `<requirements>`.
3. Ask for the gate approval. On a yes, write `Status: Approved
   YYYY-MM-DD` under the title.
