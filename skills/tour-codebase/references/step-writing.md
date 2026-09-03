# Step writing

Loaded at phase 3. Decides what a step says.

A tour step is read next to the code it points at, by someone who has not
seen this repository before. The code is already on screen — the step exists
to say what the code cannot.

## Anatomy

Three sentences, in this order. Two is fine; five is too many.

1. **What runs here.** Plain language, present tense. "This resolves the base
   branch before any diff is collected."
2. **Why it exists here.** The constraint, the alternative rejected, the
   caller that depends on it. This is the sentence a reader cannot get from
   the code.
3. **What breaks without it.** Concrete: what would be wrong, not "it would
   fail". Skip it when the answer is obvious.

The first and last step of each tour carry no `file` — a `description` alone
makes a content step, which CodeTour renders as prose. The opening states
what the tour covers and what the reader knows at the end; the closing states
what was learned and names the next tour.

## Rules

- **Quote at most five lines**, and only when the step is about a specific
  expression. The reader sees the file; a quote that repeats the screen wastes
  the step.
- **One concept per step.** Two concepts means two steps, or one that is
  cut.
- **Define the idiom, do not name it.** "A context manager — the resource is
  released when the block exits, even on an exception" teaches. "Uses a
  context manager" does not.
- **Anchor at the line that acts**, not at the declaration above it. The
  route registration, the assignment, the call — not the blank line or the
  decorator, unless the decorator *is* the mechanism.
- **Name the invisible.** Dependency injection, annotation processing,
  middleware, code generation, implicit interface satisfaction: say what
  moves control and where it comes from.
- **Say what is not there.** A missing timeout, an unhandled branch, a
  deliberate no-op is worth a sentence — as a fact about the code, never as a
  criticism.
- **No review.** No severity, no suggestion, no "this could be improved".
  A reader who wants that runs `code-review-pr`.
- **Second person, no ceremony.** "You are now inside the retry loop", not
  "The reader will observe that".

## Anti-patterns

| Do not write | Write instead |
| --- | --- |
| "This function validates the input." | "Everything past this point assumes the path is absolute — this is where a relative path is rejected." |
| "Uses the factory pattern." | "The constructor never picks the implementation; this factory does, from the `target` argument." |
| "See the code below." | Nothing. The code is on screen. |
| A 30-line quote of the function being pointed at | One line of it, or none. |
| "Note that this is somewhat inefficient." | Omit. Comprehension tour, not a review. |
| "Handles errors." | "A failure here is swallowed on purpose — the caller retries the whole batch." |

## Anchoring checks

Before a step ships:

- The file exists, at the path written into the tour, with forward slashes.
- The line number falls inside the file and points at the line the text
  describes — not one line off after an edit.
- The text does not contradict the code it points at.
- No other tour in this run steps at the same `file:line`.

A step that fails a check is repaired from evidence already gathered, or
dropped. Never approximate a line number, and never re-investigate the
repository to save a step.
