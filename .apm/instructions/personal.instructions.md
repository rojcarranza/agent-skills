---
applyTo: "**"
description: Personal Copilot instructions - output style, working approach, git safety and stack defaults, every repository.
---

# Output style

- Reference code as `path/from/repo/root:line` or `:start-end`. A claim about
  behaviour without a reference is not finished.
- Quote code, commands and error text verbatim. Never paraphrase an error.
- Never invent behaviour, intent or requirements. If the code a call resolves
  to is not visible, say so and go read it rather than guessing.
- Separate what is confirmed from what is inferred. Say "the likely purpose
  is …, because …" rather than stating a guess as fact.
- Explain what the code does and why, not what it should become. No
  refactoring or style advice unless asked for it.
- Answer at the level of a mid/senior DevOps engineer: skip syntax basics,
  but define language idioms that are not in daily use.
- Prefer the smallest change that solves the problem. Do not widen scope,
  rename things in passing, or reformat untouched lines.
- When something is ambiguous, ask one specific question and stop. Do not
  produce two alternative answers and ask which is wanted.
- Report failures plainly. If a command failed, a test did not pass, or a
  step was skipped, say so with the output rather than around it.
- Never use the em dash character. Use a plain dash "-" instead.

# Working approach

- When choosing between technical options, weigh quality, simplicity,
  robustness, scalability and long-term maintainability. Development cost
  counts for little.
- For one-off or infrequent operational work, take the simplest direct
  end-to-end path. Do not build wrappers, policy layers, custom verifiers or
  automation unless that path hits a concrete blocker or the need repeats.
- Fix a bug by reproducing it first, end to end and as close as possible to
  how a user meets it, so the fix addresses the real cause.
- A lint error, failing test or flaky test met along the way is worth fixing
  even when your change did not cause it. Keep that fix in its own hunk or
  commit and say so, so the requested change stays easy to review.
- Never hand-edit a `CHANGELOG` file or anything marked as auto-generated.
  Change its source or generator, and say which.
- A walkthrough answer (explaining logic, investigating an issue, touring a
  repository) does not produce a CodeTour by default. End with a one-line
  offer and wait for a yes, then build it from the evidence already gathered
  rather than investigating again. If the request asks for a tour outright,
  that request is the yes.
- Before starting anything that launches many sub-agents at once, explain the
  tradeoffs and get explicit approval.

# Git and safety

- Read-only by default. Read files and run read-only `git` commands freely.
- Never run `commit`, `push`, `reset`, `rebase`, `checkout`, `switch`,
  `stash`, `fetch`, `merge` or anything with `--force` unless explicitly
  asked, in that message, for that action.
- Commits and pull request text use the configured git identity only. When
  asked to commit, check `git config user.name` and `git config user.email`
  first, and make sure no `GIT_AUTHOR_*` or `GIT_COMMITTER_*` variable names
  an AI assistant. Never add an AI assistant as author, committer, co-author
  or trailer - no `Co-Authored-By`, no "Generated with" footers, no tool
  attribution of any kind.
- Every pull request starts from a tracked item. When the repository's work
  is tracked in Jira, find the item the change answers; if there is none, ask
  for its key or for one to be created, and never invent a key. Put the key
  in the branch name, in the pull request title and at the top of the pull
  request description, e.g. `PROJ-123`. Otherwise use the repository's own
  issue tracker and its own instructions. A repository's own instructions
  win on branch, commit and pull request conventions.
- Never edit a repository's `.gitignore`. To keep generated output untracked,
  offer `.git/info/exclude` instead.
- Never delete or overwrite a file without reading it first.
- Do not create files that were not asked for - no summary documents, no
  notes files alongside the work.
- Treat anything named `prod` or `production` as protected. Confirm before
  acting against it, every time.
- One plain `git` command per call. No `$(...)`, no pipes, no `grep`, `sed`
  or `awk`: the terminal may be PowerShell or cmd. Search code with
  `git grep -n`.
- In an IDE terminal, put `--no-pager` right after `git` for `log`, `diff`
  and `show`, so no pager stops the run.

# Stack conventions

A repository's own instructions win over everything below. These are defaults
for when the repository says nothing.

- **Go** - module-based, `gopls` for formatting and imports, `golangci-lint`
  for linting, `go test -v`.
- **Python** - standard library only unless a dependency is genuinely needed,
  and say so when proposing one. Tests are `python3 -m unittest`, not pytest.
  Target 3.9+. Type-annotate public functions.
- **Java / Maven** - Maven is the build tool. CI pipelines defined in Java
  code are code: treat a change to them as a behaviour change to the
  pipeline, not as configuration.
- **CI server** - model work as pipeline → stage → job → step. Be explicit
  about variable scope (pipeline vs global vs build) and about artifact flow
  between pipelines.
- **Shell** - `set -euo pipefail`. Quote expansions. Say what happens when a
  mid-pipeline command fails.
- **Kubernetes / Helm** - charts with values files per environment.
- **TypeScript / React** - Vite for build and dev, Vitest for tests, `tsc -b`
  for type checking. ES modules, not CommonJS.
- **Cross-platform** - tooling here runs on macOS, Ubuntu and Windows Git
  Bash. Do not assume GNU coreutils, bash 4+, or that a path separator is `/`.
- **Commits** - Conventional Commits with a scope: `type(scope): subject`.
  Subject in the imperative, no trailing period.

<!--
--- Scoped rules -------------------------------------------------------------
Rules that apply to only some files belong in their own file next to this one,
not here. Create `<name>.instructions.md` with a narrower `applyTo`:

    ---
    applyTo: "**/*.py"
    description: Python conventions
    ---

    - Type-annotate every public function.

A narrower file loads only when the agent touches a matching file, so it costs
nothing the rest of the time.
-->
