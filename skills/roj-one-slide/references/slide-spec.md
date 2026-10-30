# Slide spec

## Contents

- Fields
- Body: before_after
- Body: sections
- Choosing the body
- Copy rules
- Limits the script enforces

The spec is one JSON object that `scripts/build_slide.py` turns into the
slide. Two complete examples: `assets/example-before-after.json` and
`assets/example-sections.json`.

## Fields

| Field | Required | Meaning |
|---|---|---|
| `key` | no | Story key, shown first in the title (`PROJ-1001`). |
| `link` | no | URL the key links to (the ticket). |
| `title` | yes | Story summary, without the key. |
| `presenter` | no | Name after "Presented by:" at the bottom, on the footer line or, when the template's footer has its own text, just above it. |
| `date` | no | `YYYY-MM-DD`; today when left out. Shown in the footer. |
| `layout` | no | Template layout name; default is the layout of the template's first slide with both a title and a content placeholder, else of its first slide. |
| `body` | yes | `kind` plus that kind's fields, below. |
| `body.goal` | yes | One sentence after the bold "Goal:". |

## Body: before_after

Two columns split by a divider: how it worked, how it works now.

```json
"body": {
  "kind": "before_after",
  "goal": "...",
  "before": {"stages": [...], "note": ["Removed", "..."]},
  "after":  {"stages": [...], "note": ["...", {"text": "...", "bold": true}]}
}
```

- `stages` run top to bottom with arrows between them. A stage is one box
  `{"caption": "...", "items": [...]}` or a list of boxes side by side.
  Stage N sits at the same height on both sides.
- An item is a coloured chip: a string, or
  `{"text": "...", "mono": true, "state": "removed"}`. `mono` sets it in a
  code font (variable or file names), `state: removed` strikes it through.
  Colours come from the template's theme, and the same text gets the same
  colour on both sides.
- A box with no caption and one item is drawn as a bare chip: use it for
  an end result ("PAYMENT GATEWAY").
- Arrows: one box to several fans out, several to several of the same
  count pair up.
- `note`: up to four short lines beside the first stage. On the before
  side it is a dashed box whose first line is bold red (what went away);
  on the after side it is italic, and `"bold": true` stresses a line.
  The first stage moves left or narrows to make room for it.

## Body: sections

The template's own content placeholder with the Goal and headed points,
optionally with a process flow and a picture underneath.

```json
"body": {
  "kind": "sections",
  "goal": "...",
  "sections": [
    {"heading": "Challenges", "points": ["...", "..."]},
    {"heading": "Next", "points": "one line of text"}
  ],
  "flow": [{"title": "Step", "points": ["...", "..."]}],
  "image": "path/to/screenshot.png"
}
```

- `points` as a list gives a heading line and "-" bullets; as a string it
  gives one line "Heading: text".
- `flow`: 2-5 steps left to right, each a filled title bar over a box of
  bullets, with arrows between.
- `image`: a path the user gave (a build result, a dashboard); placed right
  of the flow, or across the bottom without one. Keeps its proportions.

## Choosing the body

- **before_after** when the story changed how something flows or is
  wired: a pipeline, a deployment, a config that moved, a component that
  replaced another. The SB's before/after tables are the raw material;
  group their rows into the stages a listener would recognise (job or
  service names as captions, variables or artefacts as items).
- **sections** for everything else: a new capability, a fix, an upgrade
  with hurdles. Typical headings: "Challenges", "What changed",
  "Result", "Next". Add `flow` when the work had 2-5 clear steps; add
  `image` only when the user supplied one.

## Copy rules

The slide is on screen for a minute while the presenter talks. It carries
one message; the presenter fills in the rest.

- Title: the story summary as the team knows it, at most about 80
  characters after the key.
- Goal: the why, one sentence, about 15 words, no "In order to".
- Points: at most 3 per section, one line each, no full stops. Start with
  the noun or the verb that matters.
- Before/after: at most 4 stages a side and 3 items a box. Show only the
  part of the flow that changed plus one stage of context above and
  below.
- "Next" lists unticked core tasks and follow-ups from Notes, never
  finished work.
- Never put credentials, internal hostnames or customer names on the slide
  unless the user asks.

## Limits the script enforces

The script refuses (exit 1) and lists each problem when: the spec is not
valid JSON or a field has the wrong shape; the layout has no title
placeholder, its title overlaps the body region or, with no body
placeholder, sits below the top third of the slide; a sections slide has a
layout with no content placeholder; the title wraps past
two lines at the template's title size; the goal wraps past one line in a
before_after slide; a chip, caption or flow title does not fit its box even
at the smallest font size; a stage has too many boxes side by side; the
stages do not fit above the footer; a note has too many lines; the sections
or the flow run past the footer. Fix the spec, never the limits.
