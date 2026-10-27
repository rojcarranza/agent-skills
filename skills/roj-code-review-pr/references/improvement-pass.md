# Improvement pass (`improve`)

Optional. Loaded only when the request asks for it. It adds non-blocking
suggestions to a review and keeps them apart from the defects: the author
fixes what is wrong first, then sees what could be cleaner. Defects keep every
slot, every severity and the whole verdict; a suggestion takes none of them.

## Contents

- Mode
- When it runs
- Four lenses
- Evidence rules
- Caps and placement
- Bitbucket comments
- Calibration

## Mode

`improve` is an axis word like `quick` and `full`. It also means "suggest
improvements", "feedback on the code", "polish", "simplify", "readability".
Default **off**: without it this file is not loaded, nothing in this file
applies and the output keeps its usual shape. A bare "review" never turns it
on.

## When it runs

After the verification pass and the failure-scenario rule, never before: the
defect list is final first. Suggestions anchor to lines inside diff hunks.
Pre-existing code is not a suggestion target; it stays in the existing
pre-existing note (at most 3). A suggestion whose fix has to touch a file
outside the diff is a follow-up and goes to the summary only.

## Four lenses

Nothing else is admitted.

| Lens | Admits | Evidence required |
|---|---|---|
| Reuse | the diff re-implements something that already exists | the existing symbol's `path:line`, found by graph or search in this run |
| Simplify | duplicated logic inside the diff, an unneeded flag or layer, dead code the diff adds | the repeated lines (at least 3 occurrences) or the unused symbol, with the `path:line` of each |
| Clarity | a name or comment the diff introduces that contradicts the code, a magic value, a function doing several jobs | the contradicting lines, or the length and responsibilities counted |
| Convention | the diff departs from a rule file or from at least two sibling call sites | the rule line (`CLAUDE.md`, `CONTRIBUTING.md`, lint config) or the two sibling `path:line`s |

A missing test for a new branch stays in *Tests*, and a defect stays a
defect. A suggestion that would change behaviour is not an improvement:
reclassify it as a defect candidate and run the defect gates on it, or drop
it.

**Sort once, never both.** With `improve`, an item that fits a lens and has no
failure scenario (duplicated logic, a copy of an existing helper, a misleading
name, a magic value) is a suggestion, not a Minor or a Nit. An item with a
failure scenario stays a defect. Without `improve` nothing changes: such items
stay Minor or Nit as the method says.

## Evidence rules

All seven are required. A candidate that fails one is dropped, not softened.

1. It anchors to a line inside a diff hunk.
2. It carries the concrete shape: the replacement in at most 6 lines, or the
   existing helper or rule it should match, with `path:line`.
3. One sentence, *Cost of leaving it*: what gets harder. It stands where
   "Fails when" stands for a defect.
4. One sentence, *Same behaviour because*, written after re-reading the whole
   file. If it cannot be written, it is not an improvement.
5. A confidence tag, Confirmed or Probable, under the method's library-claim
   rule. Speculative is dropped.
6. It is not on the never-report list: nothing a configured linter enforces,
   no idiom swap with no behavioural difference, no performance claim without
   a measurement, no "use a library or a different pattern", no rename of
   unchanged content.
7. It does not contradict the intent source.

## Caps and placement

- **Quick with `improve`:** at most 3 suggestions, printed after the findings
  under their own line, never counted toward the five-finding cap.
- **Full:** a `### Improvements (non-blocking)` section after *Tests* and
  before *Needs your input*: at most 5 inline suggestions plus 3 more for the
  summary only, 8 in all. Nits keep their cap of 3. The comment skill uses
  the full caps.
- **The verdict ignores suggestions.** `Changes requested - 1 Blocker, 2
  Major, 0 Minor, 0 Nits` stays as it is, with `+ 3 suggestions` appended.
- **A Blocker comes first.** With a Blocker among the defects, chat shows no
  suggestion at all: not as a list, not as a one-line example. Chat carries
  only `+ <n> suggestions` on the verdict and one line, `<n> suggestions in
  the report file - fix the Blocker first`; the report file holds them in
  full. Quick mode writes no file, so it prints `<n> suggestions held back -
  fix the Blocker first` and nothing else.
- The report header carries `improve: on` and `suggestions: <n>`.
- Praise stays where it is (*Good*, 1 to 3 items); no praise is added.
- Nothing worth suggesting: print `Improvements: none worth suggesting`. Never
  fill the section.

Each suggestion in a report reads:

```
**`path/to/file.py:42`** · Reuse · Confirmed
<what>.
Cost of leaving it: <sentence>.
Instead: <existing helper `path:line`, or a code block of at most 6 lines>.
Same behaviour because: <sentence>.
```

Quick prints one line each: `💡 path:line · <Lens> · <Confidence> - <what>.
Cost of leaving it: ... Instead: ... Same behaviour because: ...` under
`Suggestions (non-blocking, not in the verdict):`.

## Bitbucket comments

Used by `roj-review-pr-comment`. Suggestions are posted only when `improve`
was requested; they are never Bitbucket tasks or "blocker" comments.

- Defect comments keep their shape (`🟠 **Major** · Probable - ...`).
- A suggestion comment is plain text, in the sense of Conventional Comments:

```text
💡 **Suggestion (non-blocking)** · Reuse · Confirmed - <what>.

Cost of leaving it: <sentence>.

Instead: <existing helper path:line, or a plain fenced block of at most 6 lines>.
```

- Inline slots are the script's 15. Defects take slots first. Suggestions get
  at most 5 of what remains. The rest go to the summary under *Further
  suggestions*. A suggestion never displaces a defect.
- The draft shows two headings, `Inline comments - defects (n)` and `Inline
  comments - suggestions (n)`. The summary counts them apart.

## Calibration

**Report this** - `jobs/export.py:30`, Simplify, Confirmed. Lines 30-34,
52-56 and 71-75 are the same five lines (open the output file with
`encoding="utf-8", newline=""`, write the header row). Cost of leaving it:
the next export copies the block again and can drop the `newline` argument.
Instead: one helper `def _open_out(path): ...` with those five lines, called
at the three sites. Same behaviour because each site passes the same
arguments in the same order and no site uses the handle before the header.

**Do not report** - "Consider a dataclass here." No shape, no cost, and the
file's other records are dicts. It fails rules 2 and 3.

**Do not report** - "Make `3` a named constant." A preference with no cost
and no second site. It fails rule 3, and it is an idiom swap under rule 6.
