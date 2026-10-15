# Phase 4: Architecture and ADRs

Read before drafting the architecture. Output: `docs/architecture.md` from
`assets/architecture-template.md`, and `docs/adr/NNNN-<decision>.md` from
`assets/adr-template.md`, numbered from 0001. List every path before
writing; one yes writes the set.

## How to draft

- Draft in plan mode (Copilot CLI: `/plan`). Suggest the user switch to
  `opus` for this phase when they can.
- Every section of the template is filled. C4 L1 and L2 are Mermaid blocks
  (`C4Context` / `C4Container`, or `flowchart`).
- Data model: every entity has one owning component.
- Threat model: assets, trust boundaries, the top 3 to 5 threats, each
  mapped to an `NFR-SEC` item in `docs/requirements.md`.
- `## Rules for agents`: no new service, dependency or datastore without
  an ADR.

## ADRs

One per decision. Each ADR carries an `Area:` line naming the required
area it decides (`Area: persistence`; several, comma-separated, are fine;
`other` for the rest). The gate script reads that line first; failing it,
it matches whole words in the file name or `# ADR-` title:

| Area | Name or title must mention one of |
|---|---|
| language | language, stack, runtime, framework |
| persistence | persistence, database, storage, datastore |
| auth | auth, authentication, authorization, identity |
| deploy target | deploy, deployment, hosting, infrastructure |
| observability | observability, logging, monitoring, telemetry |

For each ADR:

- At least two alternatives under `## Alternatives considered`.
- Facts (pricing, free-tier limits, licence, maintenance status) are yours:
  look them up and cite the source. The choice is the user's: one question
  per ADR, with your recommendation and its reason in one line.
- `Status: Accepted` only after the user picks.

## Gate

1. Run `scripts/check_ready.py --phase architecture <ROOT>`; fix with the
   user until it exits 0.
2. Fresh-context review: follow `references/review-gates.md` with
   `<architecture>`. `architecture-guardian` does not exist yet; it runs at
   the plan gate.
3. Ask for the gate approval. On a yes, write `Status: Approved
   YYYY-MM-DD` under the title of `docs/architecture.md`.
