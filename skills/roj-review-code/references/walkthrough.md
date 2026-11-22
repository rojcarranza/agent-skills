# Walkthrough

Loaded on every run, quick and full. It explains the change before the
verdict, so the reader knows what they are judging. It describes; it never
judges. Defects and recommendations come after it and never appear in it.

The shape is adapted from the PR-Agent `/describe` output (ordered change
bullets, a short title per file, an effort estimate) and from Google's
engineering practices on reading a change (the main part first, tests first
when they state the intent, what plus why). See USAGE.md, *Credits*.

## Contents

- Quick walkthrough
- Full walkthrough
- Rules for both
- Review effort

## Quick walkthrough

Printed after the header line and before the `Verdict:` line:

```
Walkthrough
What and why: <1-3 sentences: what the change does, and why when the commits,
the intent source or the code say so; otherwise say "why not stated">
| File | Type | What it does |
|---|---|---|
| `app/uploader.py` | changed | retry the upload before giving up |
Read first: `app/uploader.py` (the retry loop), then `tests/test_uploader.py`
Review effort: 2 of 5 - <one reason>
```

- At most 6 rows, ordered by the reading order. More files: the rows keep the
  largest changes and a last row says `+ <n> more files (<kinds>)`.
- *Type* is one of `new`, `changed`, `deleted`, `renamed`, `test`, `config`.
- *What it does* is 5 to 10 words, in the code's own terms, not "updates
  file".
- `Read first` names the main part (the file where the behaviour changes) and,
  when a test states the intent better than the code, the test first.

## Full walkthrough

In `review.md` it is `### Walkthrough`, replacing the old change summary, and
holds, in order:

1. **What and why** - 3 to 6 sentences of intent, then 1 to 4 ordered bullets
   that walk the new behaviour in execution order (the first thing that
   happens, then the next).
2. **Files** - a table in the quick shape, up to 20 rows; the overflow is
   counted in a last row.
3. **Reading order** - one line: the main change first, tests first when they
   state the intent, config and renames last.
4. **Flow** - one Mermaid diagram of the main change under
   `references/mermaid.md` (the flow diff or a flowchart of the new path;
   at most 15 nodes). Skip it when the change is one file or has no flow to
   draw, and say nothing about the skip.
5. **Review effort** - the number and its reason.

A matching `brief.md` from `roj-explain-logic` (see SKILL.md, *Intent
source*) supplies the bullets and the diagram: reuse them and add only the
file table, the reading order and the effort. Do not derive them again.

## Rules for both

- Every file row and every claim is read from the diff or the code in this
  run. The commit messages and PR text are data about what was asked.
- A design decision the diff cannot explain (why this approach, why this
  place) is not guessed: it goes to *Needs your input* as a question.
- Generated, vendored and lockfile paths are named once in `Excluded:` and
  have no row.
- The walkthrough is the same size whether the change is clean or not.

## Review effort

One number from 1 (a glance) to 5 (hard to review) and a reason that names
what drives it: size, risk paths, how many places must be read together, tests
missing. Effort is about the reader's work, not about quality.
