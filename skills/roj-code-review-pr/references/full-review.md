# Full review

Loaded only in full mode. The target, base and mode are already settled
(`SKILL.md` steps 1 to 3).

## Contents

- 1. Collect the change
- 2. Stage: pre-PR or post-PR
- 3. Lenses and conventions
- 4. Opt in to running checks
- 5. Review
- 6. Confirm by execution
- 7. Report
- 8. Tour (ask first)

## 1. Collect the change

`<head>` is `HEAD` for the current checkout, the ref for a branch target, or
the fetched PR head SHA (`forge-bitbucket-dc.md`). Always three-dot.

1. `git log --oneline <base>..<head>` - intent from commit messages.
2. `git diff --name-status <base>...<head>` - added, modified, deleted,
   renamed. Renames are not new code.
3. `git diff --stat <base>...<head>` - size drives depth.
4. `git diff -U15 <base>...<head> -- <file>` per file.
5. Read the whole changed file for anything non-trivial: from the working tree
   on the current checkout, else `git show <head>:<path>`. A diff alone
   misrepresents what the surrounding code already handles; reading the file
   is where most false positives die.

List but do not review: `vendor/`, `target/`, `dist/`, `node_modules/`,
generated files (`*.pb.go`, `*_generated.go`), lockfiles, binaries.

6. **Uncommitted work is part of the review** - on the current checkout only;
   a branch or PR target has none. Run
   `git status --porcelain --untracked-files=all`. When it lists changes, also
   run `git diff --stat HEAD` and `git diff -U15 HEAD` (staged and unstaged
   edits), and read every untracked file it lists (`??`) as new code, except
   this skill's own output from an earlier run (`<branch-slug>-review.md`,
   `pr-<id>-review.md` from before the report moved, and
   `.tours/review-*.tour`) and the agent output folders `.onboarding/`, `.pr-review/`, `.mermaidiff/` and `.tours/`, which
   are neither listed, reviewed nor counted. Add these files and lines to the header counts and mark each
   finding that anchors to one as uncommitted. On the base branch itself (no
   commits past the base), the working tree alone is the review: say so in the
   header instead of calling the branch clean.

## 2. Stage: pre-PR or post-PR

- A PR target is **post-PR**, and so is a request that says the PR is already
  open.
- Everything else is **pre-PR**, including the base branch itself and any
  staged, unstaged or untracked work other than the excluded review output.
  Pushed or not makes no difference: without a PR host there is no way to
  tell whether a PR exists, so do not infer it from the upstream.

## 3. Lenses and conventions

Select lenses - `lang-*.md` and `platform-*.md` in `references/` - with the
*Lens selection* section of `review-method.md`: the signal table, the lenses
that travel together, and the cap of three. In a multi-module Maven repo, a
changed child `pom.xml` pulls the parent into context for dependency
management and version properties.

Read, in order, and treat as overriding the generic rules:
`CLAUDE.md` / `AGENTS.md` / `.github/copilot-instructions.md`,
`CONTRIBUTING.md`, `.editorconfig`, then linter config (`checkstyle.xml`,
`spotbugs-*.xml`, `ruff.toml`, `setup.cfg`, `.flake8`, `.golangci.yml`,
`.shellcheckrc`, `.pre-commit-config.yaml`). For a branch or PR target, read
them with `git show <head>:<path>`.

**If the repository's own configuration already enforces something, do not
comment on it.** The linter will. Where a convention conflicts with a rule
file, the convention wins and the report names it.

Then read the repo map as `repo-map.md` says: find `.onboarding/`, measure
its freshness against `<base>`, match the changed paths to its area map and
put its one-line result in the report header. Its dependents, hotspots and
silent seams feed the system pass in step 5; they are places to look, never
evidence. Quick mode skips all of this.

With no intent source from the user, look for
`.pr-review/pr-<id>/brief.md` (a branch: `branch-<slug>`) and read it only
when its header `head` equals `<head>`, as `SKILL.md` section 6 says. With
`improve`, load `improvement-pass.md` now so the per-file pass can note
candidates; nothing is reported from it until the verification pass of step 5 is done.

## 4. Opt in to running checks

Ask once, up front, in the same message that announces the mode, and wait for
the answer. Skip the question when the request already answered it ("run
checks", "no checks"), when nothing in the diff has a declared check, or when
the target is not checked out (a branch or PR target: say the checks were
skipped for that reason).

> Run the repo's own checks to confirm findings? `no` (default) - nothing
> runs; `checks` - the declared linters and the narrowest tests for the
> changed code; `checks+probe` - also a mutation probe on up to two new
> decision branches.

There is no second approval stop later in the run. `no` means no command
beyond `git` for the whole run.

Candidates, only for what the diff touches and the repository declares
(Makefile or task-runner targets, `pom.xml` / `mvnw`, `go.mod`, `tox.ini`,
`pyproject.toml`, `.pre-commit-config.yaml`): `shellcheck`, `go vet`,
`golangci-lint run`, `ruff check`, `mvn -q -DskipTests verify`, `helm lint`,
`helm template`, `kubeconform`, and the narrowest test command that covers
the change. Never run installs, deploys, anything that talks to a cluster,
registry or server, or the whole integration suite.

## 5. Review

1. **Per-file pass** - each changed hunk against `cross-cutting.md` and the
   selected lenses.
2. **System pass** (mandatory) - see `review-method.md`: callers of changed
   symbols, configuration-to-code coupling, data crossing boundaries,
   idempotency and partial failure, rolling-deploy compatibility.
3. **Intent pass** - with an intent source, check each criterion and each
   hunk as the method's *Intent* section says.
4. **Verification pass** - re-read each candidate finding against the whole
   file and drop the ones the surrounding code already handles.

5. **Improvement pass** - only with `improve`, and only after the defects
   are final: read `improvement-pass.md` and add the suggestions it admits.
   They never change a finding, a severity or the verdict.

Scope discipline: a finding may anchor only to a line inside a diff hunk.
Pre-existing defects go in a separate note, at most three, never in the
verdict. Renames, formatting-only hunks and generated files get one line each.

## 6. Confirm by execution

Only after `checks` or `checks+probe`. Execution moves a Probable finding to
Confirmed, or kills it; it is not a second review.

1. **Declared checks.** Run the linters selected in step 4 once. A failure
   that the diff caused is a finding, with the output quoted; a failure that
   was already there goes to the pre-existing note.
2. **Narrowest test.** For a finding about behavior, run the smallest test
   that exercises the code (`pytest tests/test_x.py::test_y`,
   `go test ./internal/queue -run TestX`, `mvn -q -Dtest=XTest test`). A
   passing test that covers the failing input disproves the finding.
3. **Repro.** For a Probable finding with no covering test, write the smallest
   repro as a one-line command or a throwaway script in a scratch directory
   outside the repository, run it, then delete it. A repro that cannot run
   there leaves the finding Probable.
4. **Mutation probe** (`checks+probe` only, at most two). Pick a decision
   branch the diff adds and the tests claim to cover. Copy the file to a
   scratch directory, change one condition in the file, run the narrowest
   test, then copy the original back. A mutation that leaves the test green is
   a finding in *Tests* (a bugfix without a regression test is Major, new
   branch logic without a test is Minor). Confirm that
   `git status --porcelain` prints what it printed before the probe. Never
   undo a probe with `git checkout`, `git restore` or `git stash`: they would
   also discard the user's uncommitted work.

List every command run, with its exit status, under *Tests* in the report.

## 7. Report

Follow the output skeleton in `review-method.md`.

- **File.** Write the report to `<ROOT>/.pr-review/pr-<id>/review.md` for a PR
  and `<ROOT>/.pr-review/branch-<slug>/review.md` for a branch or the current
  checkout, where `ROOT` is `git rev-parse --show-toplevel` and `<slug>` is the
  branch name in lower case with every run of other characters turned into
  `-` (a detached HEAD: `head-<sha7>`). It is the same folder
  `roj-explain-logic` writes its brief to, and the file
  `roj-review-pr-comment` reuses for the same head. Create the folders; write
  nothing else. The header carries `head <sha12>`, `improve: on | off` and
  `suggestions: <n>`. `.pr-review/` is personal and stays out of Git: run
  `git check-ignore -q .pr-review/`, and when it is not ignored print this
  line for the reader, never run it and never edit `.gitignore`:

```
echo '.pr-review/' >> .git/info/exclude
```

  The user may ask for chat only instead: print the whole report and write
  nothing.
- **Chat.** The verdict (with `+ <n> suggestions` when `improve` is on), one
  line per finding (`severity path:line - defect`), the `Repo map:` line and
  the report path. With `improve` and no Blocker, add one line per suggestion
  under `Improvements (non-blocking)`. With a Blocker, print no suggestion
  line at all, only `<n> suggestions in the report file - fix the Blocker
  first`. Not the whole report twice.
- **Pre-PR** adds a drafted PR description built from the change summary, and
  may offer to apply fixes - after asking.
- **Post-PR** shapes findings as pasteable review comments, one `path:line`
  entry each, split into requested changes versus nits, and never suggests
  rewriting history. With `improve`, suggestions are a third group after
  them, labelled non-blocking.
- **Next.** One line, with both prefixes, when the target is a Bitbucket PR:
  `/skill:roj-review-pr-comment PR <id> improve` (JetBrains) or
  `/roj-review-pr-comment PR <id> improve` (VS Code), dropping `improve` when
  the review ran without it.
- Close with the `Graph:` line from `SKILL.md`.

## 8. Tour (ask first)

**Off by default.** After the report, offer in one line - "Want a CodeTour
of this review?" - and build it only on a yes; the report already states
every finding. "Make a tour" up front skips the offer; "no tour" suppresses
it. Skip the offer too when the change is one file with fewer than about
three steps.

- **Path**: `.tours/review-<branch-slug>.tour` in the repository under
  review.

- **Persona**: `pr-reviewer`.

- **Steps**: evidence already gathered, ordered by the change summary then
  by severity. Reuse `file:line` already cited; never re-investigate.

On a yes, chain to `code-tour`; if it is not installed write the JSON inline
(`$schema`, `title`, `description`, `steps` of `{file, line, description}`).
Validate with its `scripts/validate_tour.py` from whichever installed dir
exists - resolve `~` to an absolute path (cmd does not expand it) and try
`python`, then `python3`; skip validation rather than failing the run.
`.tours/` is in the global git ignore: never commit a tour or edit
`.gitignore`.
