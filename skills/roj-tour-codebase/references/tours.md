# CodeTour, on request

Loaded only when the reader asked for tours or said yes to the offer. The
guide in `.onboarding/` is the deliverable; a tour replays part of it in the
VS Code CodeTour extension. JetBrains has no CodeTour plugin, so never
suggest one there.

## Build

One tour of 6-12 steps for the core flow, built from the anchors already in
`flows/01-*.md`. No second investigation: a step with no anchor in the guide
is dropped.

- File: `<ROOT>/.tours/core-flow.tour`. Paths inside a tour always use forward
  slashes, on every host.
- Invoke `code-tour` by name when the host lists it as a skill. Otherwise write
  the JSON inline: an object with `$schema`, `title`, `description`, `ref` and
  `steps` of `{file, line, description}`.
- `ref` is the current branch name; no branch, no `ref`.
- The first and last step are content steps (a `description` and no `file`):
  the opening says what the tour covers, the closing says what was learned and
  points at `.onboarding/README.md`.
- A step's description follows `walkthrough-writing.md`: what runs, why it is
  here, what breaks without it.
- A `file:line` appears in at most one step.

## Validate

Parse the JSON, confirm every `file` exists under `ROOT` and every `line`
falls inside that file, with the anchor check or `wc -l`. When `code-tour`
ships a validator and the host exposes it by skill name, use that; never go
looking for its folder. A failing step is fixed or dropped, never shipped.

`.tours/` is in the global Git ignore: never commit a tour and never edit
`.gitignore`. An existing `.tours/core-flow.tour` is named and the reader is
asked once, overwrite or keep.
