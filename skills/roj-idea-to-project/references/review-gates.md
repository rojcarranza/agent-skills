# Fresh-context review

Read before each fresh-context review: the requirements, architecture and
plan gates (and the optional "argue against this idea" brief review).

A reviewer is only useful if it did not write the work. Pass files, never
the conversation.

## Red-team prompt

Fill the bracket with `requirements`, `architecture` or `plan`:

```
You are a skeptical staff engineer who did not write the attached <requirements | architecture | plan>.
Report only: (1) ambiguous or untestable requirements, (2) contradictions, (3) missing NFRs or abuse cases,
(4) architecture risks (failure modes, scaling, cost, security boundaries), (5) simpler alternatives.
For each: severity (blocker/major/minor), quote as evidence, concrete fix. No style comments.
```

For the brief review, replace the first line with "You are a skeptical
investor who did not write the attached brief. Argue against this idea."

## Files per gate

| Gate | Paths given to the reviewer |
|---|---|
| Requirements | `docs/requirements.md`, `docs/brief.md` |
| Architecture | `docs/architecture.md`, `docs/adr/`, `docs/requirements.md` |
| Plan | the plan file, `docs/requirements.md`, `docs/architecture.md`, `docs/adr/` |

## How to dispatch

- **Claude Code:** dispatch a subagent with model `opus` when available.
  Its prompt is the red-team prompt plus the paths, and nothing else: no
  summary of the conversation, no hint of what you expect. At the plan gate
  also dispatch the project's `architecture-guardian` agent on the plan.
- **Copilot CLI:** a custom agent in `.github/agents/` with the same
  prompt runs as a subagent with its own context.
- **No subagents:** print the prompt and the paths. Tell the user to open a
  new chat (`/clear`, Copilot CLI `/new`) with only those files, then paste
  the findings back. STOP until they do.

Never review in the context that wrote the file.

## Handling findings

- Drop style comments without asking.
- Present the rest one per message: severity, the quote, the fix, and your
  recommendation (accept or reject, with the reason in one line).
- The user decides. Record every decision in the reviewed file's
  `## Review log`:

  ```
  - [major] "<quote>" → accepted: <what changed>
  - [minor] "<quote>" → rejected: <the user's reason>
  ```

- An accepted finding that changes a decision also edits the ADR (new
  `Context` line, or a superseding ADR).
- Re-run the phase's `check_ready.py --phase` after applying accepted
  fixes.
