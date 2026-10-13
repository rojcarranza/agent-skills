# Graph first

Reading files is the expensive part of a run. When the repository carries a
graphify knowledge graph, ask the graph where to look, then read only that.
Without one, skip this file and work as the skill describes.

## When it applies

1. `graphify-out/graph.json` and `graphify-out/GRAPH_REPORT.md` exist at the
   repository root.
2. Freshness, with `git` only: read the `Built from commit:` line near the
   top of `GRAPH_REPORT.md` and compare it with `git rev-parse HEAD`.
   - Same commit: the graph is current.
   - Different: `git diff --name-only <built> HEAD` lists the files changed
     since. Read those from disk, never from the graph. When the files the
     task is about are mostly in that list, or `<built>` is unknown to git,
     skip the graph.
   - Files in `git status --porcelain` are always read from disk.
3. The first graphify command fails (CLI missing): skip the graph for the
   whole run.

Only the read-only commands below run. Never run `graphify update`,
`graphify watch` or `/graphify`, and never create or change
`graphify-out/`: that writes into the user's repo. When the graph is stale,
or a large repository (hundreds of source files) has none, say once at the
end: "`graphify update .` refreshes the code graph in seconds, without an
LLM, so the next run reads less." (The full `/graphify .` also maps docs,
but spends tokens doing it.)

## Commands

| Need | Command |
|---|---|
| What is relevant to a question or an error | `graphify query "<question>" --budget 1500` |
| What a symbol is and what touches it | `graphify explain "<Symbol>"` |
| How A reaches B | `graphify path "<A>" "<B>"` |
| What depends on X (callers, blast radius) | `graphify affected "<X>" --depth 2` |
| Architecture overview | read `graphify-out/GRAPH_REPORT.md` once |

Never read `graph.json` itself — it is large; the commands summarize it.
Keep `--budget` at 1500 or below: ask a narrower question rather than raise
it.

## Rules

- The graph says where to look, not what is true. Read the lines before
  stating a fact, quoting code or anchoring a finding; the skill's evidence
  rules are unchanged. Edges tagged INFERRED or AMBIGUOUS are leads, never
  evidence.
- Code and graph disagree: the code wins. Say once that the graph looks
  stale.
- Skills that list their allowed commands allow these read-only graphify
  commands alongside `git`; nothing else is added.
- The check for `graphify-out/graph.json` runs every time, before the first
  file search. Close the output with exactly one of three lines:
  `Graph: used`, `Graph: stale, skipped` or
  `Graph: none found, searched directly`. A stale graph that still helped
  (changed files read from disk) is `Graph: used`; say so in the sentence
  before the line, not in the line. Mention "refreshed first" there too if the
  user updated the graph before the run.
