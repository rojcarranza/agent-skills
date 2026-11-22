# Recommendations pass (`improve`)

Loaded on every run unless the request says `no suggestions`. It adds
non-blocking recommendations on three areas - Logic, Comments and Design - and
keeps them apart from the defects: the author fixes what is wrong first, then
sees what would make the next change easier. Defects keep every slot, every
severity and the whole verdict; a recommendation takes none of them.

The areas and their baselines are adapted from public skills, in our own
words (USAGE.md, *Credits*): Google's engineering practices (design first,
comments explain why, one structural problem outranks ten nits), Addy Osmani's
agent-skills (structural remedies, propose the move), Matt Pocock's skills
(Fowler's smells as "possible X"), Anthropic's pr-review-toolkit (check each
comment against the code) and Conventional Comments (the non-blocking label).

## Contents

- Mode
- When it runs
- Major and Minor
- Three areas
- Evidence rules
- Caps and placement
- Bitbucket comments
- Calibration

## Mode

`improve` is **on for every target**: a branch, the current checkout and a PR.
`no suggestions` turns it off for the run; `improve` ("suggest improvements",
"feedback on the code", "polish", "simplify", "readability") is still accepted
and changes nothing. Off means this file is not loaded, nothing here applies
and the output has no recommendation anywhere.

## When it runs

After the verification pass and the failure-scenario rule, never before: the
defect list is final first. Recommendations anchor to lines inside diff hunks.
Pre-existing code is not a target; it stays in the pre-existing note (at most
3). A recommendation whose fix has to touch a file outside the diff is a
follow-up and goes to the summary only.

## Major and Minor

| Level | Means |
|---|---|
| Major | leaving it makes a named later change harder or riskier: a rule that lives in two places, a comment that will mislead the next edit, a type that allows an invalid state |
| Minor | polish: clearer, shorter or more consistent, but the next change is no harder without it |

The *Cost of leaving it* sentence must name the later change for a Major. A
Major recommendation is never a defect: with a failure scenario it is a
defect and keeps its severity. Major prints first, then Minor.

## Three areas

Nothing else is admitted. Each row needs the evidence named.

| Area | Admits | Evidence required |
|---|---|---|
| Logic | nested or repeated conditionals; a condition bolted onto an unrelated flow; duplicated branches; dead code the diff adds. Each comes with the simpler equivalent | the lines, with the `path:line` of each repeat (at least 2 for a branch, 3 for a block), or the unused symbol |
| Comments | a comment that contradicts the code; a comment that says what, not why; a magic value, workaround or ordering rule with no why; a TODO the diff adds with no owner or ticket; a missing doc where the sibling functions have one | the comment's claim beside the lines that contradict it, or the two sibling `path:line`s. Never "add a docstring" alone: write the sentence that belongs there |
| Design | a possible smell from the named list below, with the move that fixes it | the smell's evidence (counts, the repeated `path:line`s) and the move |

Comments rules: read each comment's claim against the code before judging it;
a comment that restates the line is a Minor; one that will mislead the next
edit is a Major. Prefer deleting a what-comment or renaming the thing over
adding more text.

**Design list.** Label each as `possible <smell>` and propose the move. A rule
in the repository's `CLAUDE.md`, `AGENTS.md`, `CONTRIBUTING.md` or lint config
overrides this list, and so does a sibling pattern the repository already uses
twice.

Smells: duplicated code; long function; large class or module; long parameter
list; feature envy (a function using another module's data more than its
own); data clumps (the same values always passed together); primitive
obsession (a string or number standing for a concept); shotgun surgery (one
change needs edits in many places); divergent change (one module edited for
unrelated reasons); speculative generality (an unused flag, layer or hook);
message chains; a type that allows an invalid state.

Moves: extract a function; inline a needless layer; move the function to the
data it uses; introduce a parameter object; replace a primitive with a small
type; replace nested conditionals with guard clauses; make the invalid state
unrepresentable (a closed set of values, a required field); put the rule in
one place and call it from the others.

A design decision the diff cannot explain is a question for *Needs your
input*, not a recommendation. One structural problem outranks ten nits: lead
with it.

A missing test for a new branch stays in *Tests*, and a defect stays a
defect. A recommendation that would change behaviour is not one: reclassify
it as a defect candidate and run the defect gates on it, or drop it.

**Sort once, never both.** An item that fits an area and has no failure
scenario (duplicated logic, a copy of an existing helper, a misleading
comment, a magic value) is a recommendation, not a Minor or a Nit. An item
with a failure scenario stays a defect. A copy of an existing helper is a
Design recommendation (move: call the helper) and names its `path:line`.

## Evidence rules

All seven are required. A candidate that fails one is dropped, not softened.

1. It anchors to a line inside a diff hunk.
2. It carries the concrete shape: the replacement in at most 6 lines, or the
   existing helper or rule it should match, with `path:line`.
3. One sentence, *Cost of leaving it*: what gets harder. It stands where
   "Fails when" stands for a defect.
4. One sentence, *Same behaviour because*, written after re-reading the whole
   file. If it cannot be written, it is not a recommendation.
5. A confidence tag, Confirmed or Probable, under the method's library-claim
   rule. Speculative is dropped.
6. It is not on the never-report list: nothing a configured linter enforces,
   no idiom swap with no behavioural difference, no performance claim without
   a measurement, no "use a library or a different pattern" that names no
   smell, rule or concrete move, no rename of unchanged content.
7. It does not contradict the intent source.

## Caps and placement

- **Quick:** at most 3 recommendations, Major first, after the findings under
  `Recommendations (non-blocking, not in the verdict):`, never counted toward
  the five-finding cap.
- **Full:** a `### Recommendations (non-blocking)` section after *Tests* and
  before *Needs your input*: at most 5 Major and 5 Minor. Nits keep their cap
  of 3.
- **The verdict ignores recommendations.** `Changes requested - 1 Blocker, 2
  Major, 0 Minor, 0 Nit (+ 2 Major, 3 Minor recommendations)`. A defect
  Major and a Major recommendation are counted apart.
- **A Blocker comes first** on a branch or the current checkout. With a
  Blocker among the defects, chat shows no recommendation at all: not as a
  list, not as a one-line example. Chat carries only the counts on the verdict
  and one line, `<n> recommendations in the report file - fix the Blocker
  first`; the report file holds them in full. Quick mode writes no file, so it
  prints `<n> recommendations held back - fix the Blocker first` and nothing
  else. A PR target has no such hold: its recommendations are comments to
  paste, they follow the defects and say non-blocking.
- The report header carries `improve: on` and `suggestions: <n>` (the count of
  recommendations).
- Praise stays where it is (*Good*, 1 to 3 items, strengths first); no praise
  is added here.
- Nothing worth recommending: print `Recommendations: none worth making`.
  Never fill the section.

Each recommendation in a report reads:

```
**`path/to/file.py:42`** · Major · Design · Confirmed
possible duplicated code: <what>.
Cost of leaving it: <sentence naming the later change>.
Instead: <the move, as an existing helper `path:line` or a code block of at most 6 lines>.
Same behaviour because: <sentence>.
```

Quick prints one line each: `💡 path:line · Major · Design · Confirmed - <what>.
Cost of leaving it: ... Instead: ... Same behaviour because: ...` under
`Recommendations (non-blocking, not in the verdict):`.

## Bitbucket comments

Used by `roj-review-pr-comment`, and by the `### Comments to paste` section of
a PR review. The text of a comment, the layout and the slot rules are in
`pr-comments.md`, the one format both use. Recommendations are posted only by
`roj-review-pr-comment`, and only when the request or the yes says `improve`; they are never Bitbucket tasks
or "blocker" comments.

- Defect comments keep their shape (`🟠 **Major** · Probable - ...`).
- A recommendation comment is plain text, in the sense of Conventional
  Comments, and starts `💡 **Suggestion (non-blocking)** · <Major|Minor> · <Area>`.
- Inline slots are the script's 15. Defects take slots first. Recommendations
  get at most 5 of what remains, Major first. The rest go to the summary under
  *Further suggestions*. A recommendation never displaces a defect.
- The draft shows two headings, `Inline comments - defects (n)` and `Inline
  comments - suggestions (n)`. The summary counts them apart.

## Calibration

**Report this** - `jobs/export.py:30`, Major, Design, Confirmed. Possible
duplicated code: lines 30-34, 52-56 and 71-75 are the same five lines (open
the output file with `encoding="utf-8", newline=""`, write the header row).
Cost of leaving it: the next export copies the block again and can drop the
`newline` argument. Instead: one helper `def _open_out(path): ...` with those
five lines, called at the three sites. Same behaviour because each site passes
the same arguments in the same order and no site uses the handle before the
header.

**Report this** - `app/retry.py:12`, Major, Comments, Confirmed. The comment
says `# retries 3 times` and the loop is `range(5)`: the next edit will trust
the comment. Instead: `# up to 5 attempts: the upload API rate-limits at 5
per minute` if that is the reason, else delete the comment. Same behaviour
because only a comment changes.

**Do not report** - "Consider a dataclass here." No smell, no shape, no cost,
and the file's other records are dicts. It fails rules 2 and 3.

**Do not report** - "Add a docstring." No sentence to put in it and no
sibling that has one. It fails rule 2.

**Do not report** - "Make `3` a named constant." A preference with no cost
and no second site. It fails rule 3, and it is an idiom swap under rule 6.
