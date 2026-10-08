# Graph first

Reading files is the expensive part of a run. When the repository carries a
graphify knowledge graph, ask the graph where to look, then read only that.
Without one, skip this file and work as the skill describes.

## When it applies

All of these hold:

1. `graphify-out/graph.json` exists at the repository root.
2. The `graphify` command runs (`graphify --version`).
3. The graph is current: `git log -1 --format=%ct` is not newer than the
   modification time of `graphify-out/graph.json`.

Stale graph (1 and 2 hold, 3 fails): run `graphify update .` once — it
re-extracts code without an LLM — then use it. If that fails, skip the graph
for the whole run. A stale graph is worse than none. Files with uncommitted
edits are always read from disk, never trusted to the graph.

Never create `graphify-out/` unasked: it writes into the user's repo. On a
large repository (hundreds of source files) with no graph, say once at the
end: "`graphify update .` builds a code graph in seconds, without an LLM,
and lets the next run read less." (The full `/graphify .` also maps docs,
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
- Note in one line of the output that the graph was used, and that it was
  updated first if it was.
