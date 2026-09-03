---
name: code-review-pr
description: Review the changes on the current Git feature branch, before or after a PR is opened, and write a review report plus a CodeTour. Use when the user says "review my branch", "review this PR", "code review", "review before I push", "check my changes", or asks for defects/risks in a diff. Detects the stacks the diff touches (Java/Maven, Python, Bash, Go, Bamboo, Docker, Kubernetes, Helm) and loads only the matching rules. Git-only — never calls a PR host API. For pure comprehension ("explain this branch") use explain-logic; for a quick chat-only pass use code-review-pr-fast.
---

# Code Review PR

Review the diff between the current feature branch and its base. Report
defects that would matter if shipped, plus a plain-language summary of what
the branch does so the change is understood, not just audited.

Rules that hold for the whole run:

- Evidence is the local repository and `git`. There is no PR host access —
  never invent PR state, review comments, or CI results.
- No command other than `git` runs without explicit approval.
- Every finding anchors to a line inside a diff hunk, carries a severity and
  a confidence, and dies if it cannot be tied to concrete failure.
- Quote code, commands, and error strings verbatim.
- A clean branch is reported as clean. Never invent findings.

Always load `references/review-method.md` and `references/cross-cutting.md`
from this skill's own directory before reviewing. Load technology lenses only
as phase 3 selects them.

The skill needs a terminal to run `git`. If the agent cannot run commands
(some Copilot configurations), say so and ask the user to paste
`git diff <base>...HEAD` — then review that, and skip phases 5 and 8.

## Phase 1 — Resolve the base branch

First hit wins. Print the result in the report header.

1. An explicit argument from the user (`code-review-pr release/2.4`).
2. `git symbolic-ref refs/remotes/origin/HEAD`.
3. First that exists: `origin/main`, `origin/master`, `origin/develop`, then
   local `main`, `master`, `develop`.
4. Nothing resolves — ask once. Never guess.

Sanity gate: `git rev-list --count <base>..HEAD`. Over 40 commits, or a diff
over roughly 2000 lines, usually means the wrong base (branched off another
feature branch, or a stale `origin`). Say so and ask before reviewing.

Record `git merge-base <base> HEAD` — the report prints it so the review is
reproducible. The base ref may be stale; note that rather than fetching
unasked.

## Phase 2 — Collect the diff

Always three-dot. Two-dot drags in everything merged into the base since the
branch point, which is the main source of reviewing unrelated code.

1. `git log --oneline <base>..HEAD` — intent from commit messages.
2. `git diff --name-status <base>...HEAD` — added, modified, deleted,
   renamed. Renames are not new code.
3. `git diff --stat <base>...HEAD` — size drives depth.
4. `git diff -U15 <base>...HEAD -- <file>` per file.
5. Read the whole changed file for anything non-trivial. A diff alone
   misrepresents what the surrounding code already handles; reading the file
   is where most false positives die.

List but do not review: `vendor/`, `target/`, `dist/`, `node_modules/`,
generated files (`*.pb.go`, `*_generated.go`), lockfiles, binaries.

Uncommitted work is excluded. If `git status --porcelain` is dirty, state in
the report how many uncommitted files were left out.

Determine the mode: if `git rev-parse @{u}` succeeds and `git log @{u}..HEAD`
is empty, the branch is pushed — **post-PR**. Otherwise **pre-PR**.

## Phase 3 — Detect the stacks

Keyed on the changed files, never on what the repository merely contains.

| Signal in the diff | Lens |
|---|---|
| `*.java`, `pom.xml`, `.mvn/**`, `mvnw*` | `lang-java.md` |
| `*.py`, `pyproject.toml`, `requirements*.txt`, `setup.py`, `tox.ini` | `lang-python.md` |
| `*.sh`, `*.bash`, extensionless file with a shell shebang | `lang-bash.md` |
| `*.go`, `go.mod`, `go.sum` | `lang-go.md` |
| `bamboo-specs/**`, `bamboo.y*ml`, `*Spec.java` under specs | `platform-bamboo.md` |
| YAML with both `apiVersion:` and `kind:` | `platform-k8s.md` |
| `Chart.yaml`, `values*.y*ml`, `templates/**` in a chart dir | `platform-helm.md` |
| `Dockerfile*`, `*.dockerfile`, `docker-compose*.y*ml` | `platform-docker.md` |

Ambiguous YAML: sniff the content (Kubernetes manifest vs Helm template vs
Bamboo spec vs unrelated config) before assigning a lens.

Cap at three lenses, ranked by lines changed; name the skipped ones in the
report. Repository markers (`pom.xml` merely existing) disambiguate only —
never load a lens no changed file justifies. In a multi-module Maven repo, a
changed child `pom.xml` pulls the parent into context for dependency
management and version properties.

## Phase 4 — Load repository conventions

Read, in order, and treat as overriding this skill's generic rules:
`CLAUDE.md` / `AGENTS.md` / `.github/copilot-instructions.md`,
`CONTRIBUTING.md`, `.editorconfig`, then linter config (`checkstyle.xml`,
`spotbugs-*.xml`, `ruff.toml`, `setup.cfg`, `.flake8`, `.golangci.yml`,
`.shellcheckrc`, `.pre-commit-config.yaml`).

**If the repository's own configuration already enforces something, do not
comment on it.** The linter will. Where a convention conflicts with a rule
file, the convention wins and the report names it.

## Phase 5 — Offer tooling

Propose a table — command, what it would catch, rough cost — and wait. Never
run anything unapproved. Typical candidates when the diff touches them:
`shellcheck`, `go vet`, `golangci-lint run`, `ruff check`, `mvn -q
-DskipTests verify`, `helm lint`, `helm template`, `kubeconform`.
Skip the offer entirely when the diff touches no code they cover.

## Phase 6 — Review

1. **Per-file pass** — each changed hunk against `cross-cutting.md` and the
   selected lenses.
2. **System pass** (mandatory) — see `review-method.md`: callers of changed
   symbols, configuration-to-code coupling, data crossing boundaries,
   idempotency and partial failure, rolling-deploy compatibility.
3. **Verification pass** — re-read each candidate finding against the whole
   file and drop the ones the surrounding code already handles.

Scope discipline: a finding may anchor only to a line inside a diff hunk.
Pre-existing defects go in a separate note, at most three, never in the
verdict. Renames, formatting-only hunks and generated files get one line
each.

## Phase 7 — Report

Follow the output skeleton in `references/review-method.md`. Consult
`examples/review-run.md` if the format needs grounding.

Write the report to `<branch-slug>-review.md` at the repository root, where
`<branch-slug>` is the branch name with `/` replaced by `-`.

Pre-PR mode adds a drafted PR description built from the change summary, and
may offer to apply fixes — after asking. Post-PR mode shapes findings as
pasteable review comments split into requested changes versus nits, and never
suggests rewriting history.

## Phase 8 — Tour

End with `.tours/review-<branch-slug>.tour` in the repository under review,
persona `pr-reviewer`. Chain to the `code-tour` skill; if it is missing,
write the tour inline — a JSON object with `$schema`, `title`, `description`
and `steps` of `{file, line, description}` is enough.

Steps come from evidence already gathered — one step per `file:line` already
cited, ordered by the change summary and then by severity. Never
re-investigate the repository to build the tour.

Validate with `code-tour`'s `scripts/validate_tour.py`, resolved from
whichever installed skill directory exists — `~/.copilot/skills/code-tour/`,
`~/.claude/skills/code-tour/`, or `<repo>/.github/skills/code-tour/`. Its own
SKILL.md documents a `~/.agents/...` path that usually does not exist. Skip
validation rather than failing the run if the script cannot be found.

Skip the tour only when the branch is one file with fewer than about three
steps; then say so in one line with the reason. `.tours/` is in the global
Git ignore — never add it to the repository's `.gitignore` or commit it.

## Companion skills — use if installed

| Skill | When |
|---|---|
| `code-tour` | always, for phase 8 |
| `explain-logic` | the changed logic is hard to follow: trace it, then review |
| `context-map` | the diff touches many files and the relationships are unclear |
| `investigate-issue` | a finding turns out to be an already-failing build |
| `caveman` | user asks for terse output |
