# Slide spec

## Contents

- Fields
- Body: story
- Body: before_after
- Body: sections
- Choosing the visual
- Copy rules
- Limits the script enforces

The spec is one JSON object that `scripts/build_slide.py` turns into the
slide. Two complete examples: `assets/example-story-steps.json` and
`assets/example-story-path-change.json`. Write `story` bodies;
`before_after` and `sections` stay for specs written earlier.

## Fields

| Field | Required | Meaning |
|---|---|---|
| `key` | no | Story key, shown first in the title (`PROJ-1001`). |
| `link` | no | URL the key links to (the ticket). |
| `title` | yes | Story summary, without the key. |
| `presenter` | no | Name after "Presented by:" at the bottom. |
| `date` | no | `YYYY-MM-DD`; today when left out. Shown in the footer. |
| `layout` | no | Template layout name; default is the layout of the template's first slide. |
| `body` | yes | `kind` (`story`) plus that kind's fields, below. |
| `body.goal` | yes | One sentence after the bold "Goal:". |

## Body: story

The message first: Goal, How, Result and Next as text in the template's
content placeholder, then at most one visual.

```json
"body": {
  "kind": "story",
  "goal": "...",
  "how": ["...", "..."],
  "result": "...",
  "next": "...",
  "flow": [{"title": "Step", "points": ["..."]}]
}
```

- `how` (required): 2-4 points, from the SB's Approach, then the ticked
  core tasks. Property values (versions, flags, option names) appear here
  as code-font words, never as a drawing.
- `result` (optional): a string or a list; only Testing rows that were
  run, plus the build result link. Leave it out when nothing was run.
- `next` (optional): a string or a list; open work only.
- One visual at most; two together are refused:
  - `flow`: 2-5 steps left to right, as in the sections body; the boxes
    grow to fill the space under the text.
  - `image`: a screenshot the user gave, to the right of the text, with
    its proportions kept.
  - `path_change`: `{"before": {...}, "after": {...}}`, each side in the
    shape of `before_after` below (`stages`, `note`), drawn under the
    text. Two to three stages a side fit; the note is one or two lines.
  - none: text only.

## Body: before_after

Two columns split by a divider: how it worked, how it works now.

```json
"body": {
  "kind": "before_after",
  "goal": "...",
  "before": {"label": "Before", "stages": [...], "note": ["Removed", "..."]},
  "after":  {"label": "After",  "stages": [...], "note": ["...", {"text": "...", "bold": true}]}
}
```

- `stages` run top to bottom with arrows between them. A stage is one box
  `{"caption": "...", "items": [...]}` or a list of boxes side by side.
  Stage N sits at the same height on both sides.
- An item is a coloured chip: a string, or
  `{"text": "...", "mono": true, "state": "removed", "color": "accent4"}`.
  `mono` sets it in a code font (variable or file names), `state: removed`
  strikes it through, `color` overrides the automatic colour (`accent1` to
  `accent6`, `tx2`). The same text gets the same colour on both sides.
- A box with no caption and one item is drawn as a bare chip: use it for
  an end result ("PAYMENT GATEWAY").
- Arrows: one box to several fans out, several to several of the same
  count pair up.
- `note`: up to four short lines beside the first stage. On the before
  side it is a dashed box whose first line is bold red (what went away);
  on the after side it is italic, and `"bold": true` stresses a line.
  It needs the first stage to be a single box.

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

## Choosing the visual

Write the text first, then pick the visual from the content:

- **image** when the user supplied a screenshot (a build result, a
  dashboard, the feature running): it goes right of the text.
- **flow** when the work had 2-5 clear steps (the SB's Task flow).
- **path_change** only when the SB's Change flow removes or replaces a
  step in a path that runs (a job, a call, a hand-off), and drawn only
  from that flow. Never from the per-file Before/After tables: a version
  bump, a flag or a config value is a How point in code font, not a
  before and after.
- **none** when no visual fits: the slide is text only. Do not invent a
  diagram to fill space.

## Copy rules

The slide is on screen for a minute while the presenter talks. It carries
one message; the presenter fills in the rest.

- Title: the story summary as the team knows it, at most about 80
  characters after the key.
- Goal: the why, one sentence, about 15 words, no "In order to".
- Points: at most 3 per section (How up to 4), one line each, no full
  stops. Start with the noun or the verb that matters.
- Result: one line, what was run and observed, with the build link when
  there is one.
- Path change: 2-3 stages a side and 3 items a box. Show only the part
  of the flow that changed plus one stage of context.
- "Next" lists unticked core tasks and follow-ups from Notes, never
  finished work.
- Never put credentials, internal hostnames or customer names on the slide
  unless the user asks.

## Limits the script enforces

The script refuses (exit 1) and lists each problem when: the title is over
110 characters with the key; the goal wraps past one line in a
before_after slide; a chip, caption or flow title does not fit its box even
at the smallest font size; the stages do not fit above the footer; a story has fewer than 2 or more
than 4 How points or more than one visual; a note
has no room or too many lines; the sections or the flow run past the
footer. Fix the spec, never the limits.
