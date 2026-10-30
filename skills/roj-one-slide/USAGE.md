# roj-one-slide - usage

Builds the one slide you present at a sprint demo or review for a story you
finished: the story key (linked to the ticket) and title, a one-sentence
Goal, then a before/after flow diagram or headed points with an optional
process flow and screenshot. The slide is built on your team's own deck, so
it matches the rest of the demo. Never touches git.

## When to use

- You implemented a story with `roj-soundboarding` and the demo is coming:
  hand it the SB document. Flow 2 of `roj-soundboarding` offers this at the
  end.
- You have a story file or the ticket text and want the slide anyway.

## Install

Copilot only. Install it with the rest of this repo: see
[Install](../../README.md#install) in the README.

It needs Python with `python-pptx` (`python -m pip install --user
python-pptx`; the skill asks before installing it). LibreOffice is
optional: with it the skill renders the slide to a PNG and checks it before
handing it over; without it, open the slide yourself.

## Set up once

1. Save a deck your team presents from as `slide-template.pptx`, or point
   at one. The layout of its first slide is used, and its slides are not
   copied. A `.potx` has to be saved as `.pptx` first.
2. Tell the skill where it is, in the request or once for all runs:

   ```bash
   export SLIDE_TEMPLATE="$HOME/templates/team-demo.pptx"
   export SLIDE_PRESENTER="Alex"                         # optional
   export TICKET_BASE_URL="https://jira.example.com/browse/"  # optional
   ```

   PowerShell: `$env:SLIDE_TEMPLATE = "C:\templates\team-demo.pptx"`.
   Without `SLIDE_TEMPLATE` the skill looks for `slide-template.pptx` in
   `$SOUNDBOARD_DIR` (or the repository root), then asks.

Keep the template out of public repositories: it carries your employer's
branding.

## Run

- `make a demo slide for SB-PROJ-1001`
- `one slide for PROJ-1001.md, presented by Alex, add build-result.png`
- `sprint review slide for this story:` + the pasted ticket text

Output, next to the input file: `PROJ-1001-slide.pptx`, the spec it was
built from (`PROJ-1001-slide.json`) and the preview (`PROJ-1001-slide.png`).

## Tweaking the slide

Edit `PROJ-1001-slide.json` (the format is in
[references/slide-spec.md](references/slide-spec.md)) and ask the skill to
rebuild, or run the script yourself:

```bash
python <skill-folder>/scripts/build_slide.py --template "$SLIDE_TEMPLATE" --spec PROJ-1001-slide.json --out PROJ-1001-slide.pptx --preview PROJ-1001-slide.png
```

The script refuses text that would overflow the slide and says what to
shorten. Small touches after that (moving a box, a colour) are fine to do in
PowerPoint; a rebuild overwrites them.
