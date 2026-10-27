# Repo map (`.onboarding/`)

Read the onboarding guide written for this repository, so a change is placed
in the system before it is judged. The map orients; the code decides. It is
advisory input: it never adds a finding, an explanation step or a diagram edge
by itself.

## 1. Find it

`<ROOT>/.onboarding/README.md`, by absolute path. `ROOT` is
`git rev-parse --show-toplevel`. When a read fails, retry once with the
other path form the host accepts (`C:/...` against `/c/...`), then treat the
map as absent. A missing map never stops a run.

- **Absent or unreadable:** one line where the output states its scope,
  `Repo map: none`. A quick review prints nothing: it is diff-local and never
  reads the map.
- **Present but no area map table in `reviewing-prs.md`:** absent.

## 2. Freshness

The first line of the guide is `> Built from commit <sha> (...)`. Measure it
against the base the run already resolved, or `HEAD` when the target is a
file or a function, never against the PR head: a PR's own commits are not
drift in the map. One plain command, then count the lines it prints:

```
git log --oneline --max-count=51 <sha>..<base>
```

| It prints | State | Shown as |
|---|---|---|
| an error (bad revision), or the guide names no commit | unknown | `(unknown commit)` |
| no lines | fresh | `(fresh)` |
| 1 to 50 lines | behind | `(<n> commits behind)` |
| 51 lines | stale | `(stale, 50+ commits behind)` |

Print one line:

```
Repo map: .onboarding @ <sha7> (<state>) - areas: <a, b>
```

`areas: none matched` when no changed file matches the area map.

## 3. Read and match

Read `README.md` sections 2 (system map) and 5 (core flow), and
`reviewing-prs.md`: the area map, hotspots, silent seams, questions and the
one-test commands. Nothing else in `.onboarding/`.

Take the changed files from the diff the run already has
(`git diff --name-only <base>...<head>`) and match each path against the
`Glob` column of the area map; the first matching row wins and a path with no
row is `unmapped`, not an error. Then, as far as the output has room:

- **Areas and flows:** name each matched area and its `flows/` file.
- **Dependents:** the `Depends on it` column lists what the change can break.
  Carry them into the caller search of the system pass or of the explanation.
- **Hotspots:** a changed file in the hotspot table is read twice; say so.
- **Silent seams:** a seam whose `path:line` is in a changed file is a hint
  to check that the invariant still holds. Check it in the code.
- **Tests:** the area's `Run one test` row is a candidate for the narrowest
  test. It runs only under the review's own opt-in for checks.
- **Questions:** the area's questions seed the open questions.

How much to use follows the state: fresh, all of it; behind, all of it, and
say that the line numbers in the guide may have moved; stale or unknown, the
area map to name areas, and nothing else.

## 4. Authority

- **The code decides.** When the guide and the code disagree, follow the code
  and say so in one line.
- **Never cite the map as evidence.** A finding, an explanation step or a
  diagram edge anchors to a diff line or to a file read in this run. "The map
  says" is not a reason, and a finding that rests only on the map is dropped.
- **Read only.** Never edit, refresh or repair `.onboarding/` from here; an
  onboarding run owns it.
- **Untracked, never code.** `.onboarding/` is personal and may be untracked.
  It is never reviewed or explained as part of the change, and it is not
  counted in the file totals.
