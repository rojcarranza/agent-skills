---
name: roj-one-slide
description: Build one PowerPoint slide that presents an implemented story at a sprint demo or review, on the team's own deck template - story key and title, a one-sentence goal, then a before/after flow diagram or headed points with an optional process flow and screenshot. Input is an SB document from roj-soundboarding, a story file or pasted story text. Use when the user says "one slide", "demo slide", "sprint review slide", "make a slide for PROJ-123" or "present this story", or asks for a PowerPoint summary of a story they finished.
license: MIT
metadata:
  cali-tools: python3|python
---

# One slide

Turn a finished story into the single slide the user presents at the demo.
The slide is built on the team's own template deck, so the logo, fonts,
colours and footer are the deck's, and a bundled script draws the content
with the template's theme colours.

## Configuration

- TEMPLATE: the team's `.pptx`. Resolve in this order: a path in the user's
  message, then `$SLIDE_TEMPLATE` (PowerShell: `$env:SLIDE_TEMPLATE`), then
  `slide-template.pptx` in SOUNDBOARD_DIR (`$SOUNDBOARD_DIR`, else the root
  of the current repository). None found: ask for the path once, mention
  `SLIDE_TEMPLATE`, and wait. Never fall back to a generic theme. A deck the
  team already presents from is the best template: the script uses the
  layout of its first slide and drops its slides from the copy. Not needed
  when the user asks only for the spec: then stop after step 3.
- PRESENTER: a name in the message, then `$SLIDE_PRESENTER`, then the first
  word of `git config user.name`. Empty: leave the line off.
- OUTPUT: `<KEY>-slide.pptx` in the folder of the input file (the current
  directory for pasted text), with the spec beside it as `<KEY>-slide.json`
  and the preview as `<KEY>-slide.png`. An existing slide: ask before
  overwriting.

State the resolved TEMPLATE and OUTPUT in one line at the start of the run.

## Hard rules

1. **One slide.** Never a second slide, a title slide or an end slide.
2. **Truthfulness.** Every word on the slide comes from the input or the
   user. An unticked core task is not presented as done: it goes under
   "Next" or stays off. No invented numbers, results or names.
3. **Read-only template, hands-off git.** Never write to TEMPLATE. Never
   commit, branch or push; read-only git commands are allowed.
4. **Change the spec, not the file.** Every fix is an edit to the JSON spec
   and a re-run of the script. Never patch the `.pptx` XML by hand.
5. **Editable in PowerPoint.** The slide is the template's placeholders plus
   native shapes, text and glued arrows, never a picture of a slide or a
   diagram. The preview PNG is for checking only and never goes on the
   slide; the only picture allowed is a screenshot the user supplied.
6. **Ask, don't guess.** One question when the input is ambiguous.

## Flow

1. **Read the input.** An SB document: the Goal, the Core tasks (ticked
   ones are done), the before/after tables, the Testing log and Notes. A
   story file or pasted text: the summary, the goal and the acceptance
   criteria. The key comes from the file name (`SB-PROJ-1001.md` →
   `PROJ-1001`) or the text. The title link is a ticket URL found in the
   input, else `$TICKET_BASE_URL` followed by the key, else none.
2. **Choose the body** as `references/slide-spec.md` describes under
   "Choosing the body": `before_after` when the story changed a flow,
   pipeline, configuration or structure that boxes can show; `sections`
   otherwise, with a `flow` of 2-5 steps when the work had clear steps and
   an `image` only when the user gave one.
3. **Write the spec** to `<KEY>-slide.json` following
   `references/slide-spec.md`, and the copy rules there. Start from
   `assets/example-before-after.json` or `assets/example-sections.json`.
4. **Build.** Run the bundled script by its absolute path inside this
   skill's folder, trying `python`, then `python3`:
   `python <skill>/scripts/build_slide.py --template <TEMPLATE> --spec <KEY>-slide.json --out <KEY>-slide.pptx --preview <KEY>-slide.png`
   - Exit 1 lists every problem (text too long, too many items). Shorten
     or merge in the spec and run again; after three rounds show the
     problems to the user.
   - Exit 2: python-pptx is missing. Ask once to run
     `python -m pip install --user python-pptx`; run it only on a yes.
   - Exit 3: TEMPLATE cannot be read; say so and ask for another path.
5. **Look at the preview.** When the script printed `preview:`, open the
   PNG and check it as the audience will see it: no text cut off or
   overlapping, nothing running into the footer, chip colours readable,
   no box left mostly empty. Fix through the spec and rebuild. When it
   printed `preview skipped`, say the slide was not checked visually
   (LibreOffice renders it) and ask the user to open it.
6. **Report** in a few lines: the slide's path, what it shows (title,
   body kind, the one message of the slide), what was left out, and that
   editing `<KEY>-slide.json` and re-running step 4 rebuilds it.
