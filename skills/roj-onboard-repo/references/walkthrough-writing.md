# Walkthrough writing

Loaded at phase 3. Decides what each step of the guide's code walkthrough says
(the numbered steps under "Core flow" in `README.md` and in `flows/*.md`).

A step is read next to the code it points at, by someone who has not seen this
repository before. The code is one click away; the step exists to say what the
code cannot.

## Anatomy

Three sentences, in this order. Two is fine; five is too many.

1. **What runs here.** Plain language, present tense. "This resolves the base
   branch before any diff is collected."
2. **Why it exists here.** The constraint, the alternative rejected, the
   caller that depends on it. This is the sentence a reader cannot get from
   the code.
3. **What breaks without it.** Concrete: what would be wrong, not "it would
   fail". Skip it when the answer is obvious.

Each step starts with a bold name and its anchor:
`1. **Route.** ` followed by `path:line` in backticks, then the sentences.

## Rules

- **Quote at most five lines**, and only when the step is about a specific
  expression. A quote that repeats what the reader sees by opening the file
  wastes the step.
- **One concept per step.** Two concepts means two steps, or one that is cut.
- **Define the idiom, do not name it.** "A context manager - the resource is
  released when the block exits, even on an exception" teaches. "Uses a
  context manager" does not.
- **Anchor at the line that acts**, not at the declaration above it. The
  route registration, the assignment, the call - not the blank line or the
  decorator, unless the decorator *is* the mechanism.
- **Name the invisible.** Dependency injection, annotation processing,
  middleware, code generation, implicit interface satisfaction: say what moves
  control and where it comes from.
- **Say what is not there.** A missing timeout, an unhandled branch, a
  deliberate no-op is worth a sentence - as a fact about the code, never as a
  criticism.
- **No review.** No severity, no suggestion, no "this could be improved". A
  reader who wants that runs `roj-code-review-pr`.
- **Second person, no ceremony.** "You are now inside the retry loop", not
  "The reader will observe that".
- **Execution order, always.** The reader follows control, not the file tree.
  Cross a boundary explicitly: say which layer control moved to and what holds
  on the far side.

## Anti-patterns

| Do not write | Write instead |
| --- | --- |
| "This function validates the input." | "Everything past this point assumes the path is absolute - this is where a relative path is rejected." |
| "Uses the factory pattern." | "The constructor never picks the implementation; this factory does, from the `target` argument." |
| "See the code below." | Nothing. Say what the code cannot. |
| A 30-line quote of the function being pointed at | One line of it, or none. |
| "Note that this is somewhat inefficient." | Omit. Comprehension, not a review. |
| "Handles errors." | "A failure here is swallowed on purpose - the caller retries the whole batch." |

## Anchoring checks

Before a step ships:

- The file exists, at the path written, relative to `ROOT`, with forward
  slashes.
- The line number falls inside the file and points at the line the text
  describes, not one line off after an edit.
- The text does not contradict the code it points at.
- A claim that came from a document is marked as the document's claim until
  the code confirms it.

A step that fails a check is repaired from evidence already gathered, or
dropped. Never approximate a line number, and never re-investigate the
repository to save a step.
