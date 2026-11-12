---
name: roj-one-slide
description: "Builds one PowerPoint slide that presents an implemented story at a sprint demo or review, on the team's own deck template: story key and title, the Goal, how it was implemented, the result and what is next, with one optional visual (steps, a screenshot or a changed path). Input is an SB document from roj-soundboarding, a story file, pasted story text, or the chat and branch of what was just built. Use when the user says \"one slide\", \"demo slide\", \"sprint review slide\", \"make a slide for PROJ-123\", \"make a slide for what we just did\" or \"present this story\"."
argument-hint: "[SB document | story file | story key]"
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
   "Next" or stays off. No invented numbers, results or names. Result
   states only what a Testing row or build shows was run.
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

1. **Read the input.** An SB document: the Goal, the Approach and the
   Task flow or Change flow, the Core tasks (ticked ones are done), the
   Testing log and Notes. The per-file Before/After tables are background
   for wording only. A story file or pasted text: the summary, the goal
   and the acceptance criteria. No file, and the user says "what we just
   did": the chat and `git log` and `git diff` of the current branch,
   read-only. The key comes from the file name (`SB-PROJ-1001.md` →
   `PROJ-1001`), the branch or the text. The title link is a ticket URL
   found in the input, else `$TICKET_BASE_URL` followed by the key, else
   none.
2. **Write the message first**, before any layout: Goal (the SB Goal),
   How (2-4 points from the Approach, then the ticked core tasks), Result
   (only Testing rows that were actually run, plus the build result link
   when there is one) and Next (only open work). Leave Result off when
   nothing was run; never write a result that was not observed.
3. **Pick the one visual** as `references/slide-spec.md` describes under
   "Choosing the visual": a screenshot the user gave goes to the right of
   the text; steps when the work had 2-5 clear steps; a path change only
   when the Change flow shows a step removed or replaced in a running
   path, drawn only from that flow. None fits: text only. Never show a
   before and after of values (versions, flags, option names): put them
   in How as code-font words.
4. **Write the spec** to `<KEY>-slide.json` following
   `references/slide-spec.md`, and the copy rules there. Start from
   `assets/example-story-steps.json` or
   `assets/example-story-path-change.json`.
5. **Build.** Run the bundled script by its absolute path inside this
   skill's folder, trying `python`, then `python3`:
   `python <skill>/scripts/build_slide.py --template <TEMPLATE> --spec <KEY>-slide.json --out <KEY>-slide.pptx --preview <KEY>-slide.png`
   - Exit 1 lists every problem (text too long, too many items). Shorten
     or merge in the spec and run again; after three rounds show the
     problems to the user.
   - Exit 2: python-pptx is missing. Ask once to run
     `python -m pip install --user python-pptx`; run it only on a yes.
   - Exit 3: TEMPLATE cannot be read; say so and ask for another path.
6. **Look at the preview.** When the script printed `preview:`, open the
   PNG and check it as the audience will see it: no text cut off or
   overlapping, nothing running into the footer, chip colours readable,
   no large part of the slide left empty. Fix through the spec and
   rebuild. When it printed `preview skipped`, say the slide was not
   checked visually (LibreOffice renders it) and ask the user to open it.
7. **Report** in a few lines: the slide's path, what it shows (title,
   the visual, the one message of the slide), what was left out, and that
   editing `<KEY>-slide.json` and re-running step 5 rebuilds it.
