# Base resolution

One rule for every skill that diffs a branch against its base, so the same
branch is reviewed and explained against the same base. Git only; never fetch
unasked.

## Order - first hit wins

1. **The base the user names**: an argument (`against release/2.4`), or the
   target branch of the pull request - read from the PR page or URL the
   user gave, or from their words. Use `origin/<name>` when
   `git rev-parse --verify --quiet origin/<name>` prints a SHA, else the local
   `<name>` by the same check. Neither resolves: ask.
2. **A pull request whose target is unknown**: ask once ("Which branch does
   this PR merge into?"). A PR's base is its target branch; never take it from
   `origin/HEAD`, which is the repository default and often is not the
   target.
3. **A branch with no stated base**: take the nearest of these candidates.
   Build the list in this order and drop duplicates and any that do not
   resolve (`git rev-parse --verify --quiet`):
   - the branch `git symbolic-ref refs/remotes/origin/HEAD` names,
   - `origin/develop`, `origin/main`, `origin/master`,
   - local `develop`, `main`, `master` (only when no `origin/` form exists).

   For each, run `git rev-list --count <candidate>..<head>`, where `<head>` is
   the ref under review (`HEAD` for the current checkout). The smallest count
   is the branch point's branch, so a feature branch cut from `develop` is
   compared with `develop` even when `origin/HEAD` is `main`. A tie goes to
   the earlier candidate in the list.
4. **Nothing resolves**: ask once. Never guess.

State the result in one line, with how it was found: `base origin/develop
(nearest of origin/main, origin/develop)`, `base release/2.4 (argument)` or
`base origin/develop (PR target, from the user)`.

## Checks after resolving

- **Current branch is the base.** `git branch --show-current` prints the base
  itself (for `origin/develop`, also its local name `develop`) or nothing
  (detached HEAD): no commits are ahead. The calling skill decides what that
  means - a review treats the working tree as the change, an explanation asks
  which branch to explain.
- **Sanity gate.** `git rev-list --count <base>..<head>`. Over 40 commits, or a
  diff over roughly 2000 lines, usually means the wrong base (cut from another
  feature branch, or a stale `origin`). Say so and ask before continuing.
- **Merge base.** `git merge-base <base> <head>`; print its short SHA so the
  run is reproducible. The base ref may be stale: say so when it matters
  instead of fetching.
- **Three-dot diffs only.** `git diff <base>...<head>`. Two-dot also drags in
  everything merged into the base since the branch point, which is the main
  source of reviewing unrelated code.
