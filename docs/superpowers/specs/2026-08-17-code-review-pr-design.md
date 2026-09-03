# Code Review PR Skills — Design

Date: 2026-08-17
Status: approved (brainstorming session)

## Goal

Two custom agent skills that review the changes on the current Git feature
branch — before or after a PR is opened — across the four stacks in use
(Java/Maven, Python, Bash, Go) and their platforms (Bamboo, Docker,
Kubernetes, Helm). One workflow and one rule set serve every stack; the
relevant technology rules are selected from the diff, not hard-coded.

Every run also produces a plain-language summary of what the branch does,
so the review teaches the change as well as auditing it.

## Scope

Two skills under `agent-skills/skills/`:

1. `code-review-pr` — full review. Chat output, a Markdown report file, and
   a CodeTour file.
2. `code-review-pr-fast` — quick sanity check. Chat only, no files, no
   commands beyond `git`.

Out of scope: any PR-host integration. The skills never call the Bitbucket
or GitHub API, never post comments, and never read PR metadata. Everything
comes from local Git. Also out of scope: automatic fix application without
approval, and running builds or test suites unprompted.

## Constraints

- Installed by `agent-skills/install.py` to both Claude Code and GitHub
  Copilot (VS Code and JetBrains), so the layout must match the existing
  four skills: `SKILL.md`, `references/`, `examples/`, `USAGE.md`.
- No network access assumed. No PR host credentials assumed.
- Java projects use **Maven**. Gradle is not in use and is not detected.
- Bamboo is the CI/CD system; there is no live Bamboo access, so pipeline
  review is static reading of specs in the repo.
- Commits use Roj's Git identity only (repo-wide rule).

## Architecture

### Layout

```
skills/code-review-pr/
├── SKILL.md                      workflow only
├── references/
│   ├── review-method.md          ALWAYS loaded
│   ├── cross-cutting.md          ALWAYS loaded
│   ├── lang-java.md              ┐
│   ├── lang-python.md            │ loaded when the DIFF touches them
│   ├── lang-bash.md              │
│   ├── lang-go.md                ┘
│   ├── platform-bamboo.md        ┐
│   ├── platform-k8s.md           │ loaded when the DIFF touches them
│   ├── platform-helm.md          │
│   └── platform-docker.md        ┘
├── examples/
│   └── review-run.md             one full worked review (lazy-loaded)
└── USAGE.md

skills/code-review-pr-fast/
├── SKILL.md                      condensed workflow + fallback tables
└── USAGE.md
```

### Why three tiers rather than one file per technology

The originally proposed flat `rules/` directory placed `java.md` and
`bamboo.md` as peers. They are not peers: one is a language lens, the other
a platform lens, and a branch in a Java repository that only touches a
Bamboo spec needs the second and not the first. Splitting the two axes lets
detection load exactly what the diff justifies.

The flat layout also had no home for review *method* — severity, confidence,
false-positive suppression, cross-file reasoning. Left in `SKILL.md` it
inflates the one file that must stay reliable; copied into each technology
file it drifts. It gets its own always-loaded reference.

Finally, the defect classes that matter most in infrastructure automation —
hardcoded secrets, non-idempotent operations, missing timeouts, swallowed
exit codes, unguarded destructive commands — span Bash and Python and Go
alike. They live in one always-loaded `cross-cutting.md` rather than being
duplicated four times.

### Two skills, one rule set

| | `code-review-pr` | `code-review-pr-fast` |
|---|---|---|
| Output | chat + `<branch-slug>-review.md` + `.tours/review-<branch-slug>.tour` | chat only |
| Lenses | up to 3, from the diff | at most 1, or none |
| Tooling | proposes linters, waits for approval | `git` only |
| Scope | full, including the system pass | diff-local only |
| Use when | before or after opening a PR | quick check mid-work |

`code-review-pr-fast` resolves `review-method.md` from the sibling installed
skill directory (`~/.claude/skills/code-review-pr/references/`, or the
`~/.copilot/skills/` equivalent) — the same cross-skill path resolution
`explain-logic` already uses for code-tour's `validate_tour.py`. If that file
is not found, it falls back to condensed severity and confidence tables
inlined in its own `SKILL.md`. One source of truth in the normal case, no
hard dependency in the degraded case.

## File responsibilities

**`SKILL.md`** — workflow only: resolve base, collect the diff, detect
lenses, load references, run the review passes, emit the report. It owns no
domain knowledge and no severity definitions, and stays under roughly 150
lines.

**`references/review-method.md`** (always loaded) — the severity table, the
confidence table, the do-not-report list, the verification pass, the output
skeleton, and calibration examples: two findings worth reporting and three
rejected candidates with the reason each was rejected. Calibration lives
here because it must be present on every run; it is the main defence against
nitpicking.

**`references/cross-cutting.md`** (always loaded) — language-independent
defect classes: secrets and credentials in code or config, non-idempotent
operations, missing timeout/retry/backoff, swallowed errors and ignored exit
codes, destructive commands without a guard, unsafe defaults, logging that
leaks sensitive values, concurrency on shared state.

**`references/lang-*.md`** — one per language, listing what a reviewer must
check, not what the language is. Each ends with a "not a finding here" list
that names the common false positives for that language (for example, in
Bash: word splitting inside `[[ ]]` is safe and must not be flagged).

**`references/platform-*.md`** — Bamboo, Kubernetes, Helm, Docker. Same
shape, including the same closing "not a finding here" list.

**`examples/review-run.md`** — one full worked review of a realistic branch,
showing the exact output format end to end. Lazy-loaded; `SKILL.md` points
to it only when the output format needs grounding.

**`USAGE.md`** — user-facing documentation matching the other four skills.

## Technology detection

Detection is keyed on the changed files in the diff, never on what the
repository merely contains.

Stage 1 — paths from `git diff --name-only <base>...HEAD`:

| Signal | Lens |
|---|---|
| `*.java`, `pom.xml`, `**/pom.xml`, `.mvn/**`, `mvnw*` | lang-java |
| `*.py`, `pyproject.toml`, `requirements*.txt`, `setup.py`, `tox.ini` | lang-python |
| `*.sh`, `*.bash`, extensionless file with a shell shebang | lang-bash |
| `*.go`, `go.mod`, `go.sum` | lang-go |
| `bamboo-specs/**`, `bamboo.y*ml`, `*Spec.java` under a specs directory | platform-bamboo |
| YAML containing both `apiVersion:` and `kind:` | platform-k8s |
| `Chart.yaml`, `values*.y*ml`, `templates/**` under a chart directory | platform-helm |
| `Dockerfile*`, `*.dockerfile`, `docker-compose*.y*ml` | platform-docker |

Stage 2 — content sniffing, for ambiguous YAML only: Kubernetes manifest
versus Helm template versus Bamboo spec versus unrelated configuration.

Stage 3 — cap at three lenses, ranked by lines changed. When more lenses
match, the report names the ones that were skipped. Bamboo specs written in
Java legitimately match two lenses; the cap resolves the ranking.

Repository-level markers (the presence of `pom.xml`, say) are used only to
disambiguate, never to load a lens that no changed file justifies. In a
multi-module Maven repository, a changed child `pom.xml` pulls the parent
`pom.xml` into context for dependency management and version properties,
even though the parent is not in the diff.

## Git mechanics

### Base branch resolution

First hit wins; the resolved base is always printed in the report header.

1. An explicit argument (`/code-review-pr release/2.4`).
2. `git symbolic-ref refs/remotes/origin/HEAD` — the remote default branch.
3. The first that exists of `origin/main`, `origin/master`, `origin/develop`,
   then local `main`, `master`, `develop`.
4. Nothing found — ask once. Never guess.

Sanity gate: `git rev-list --count <base>..HEAD`. More than 40 commits, or a
diff over roughly 2000 lines, means the base is probably wrong — branched
from another feature branch, or a stale `origin`. The skill says so and asks
before spending a review on it. The report notes that the base ref may be
stale unless the user approves a fetch.

### Diff collection

Always three-dot: `git diff <base>...HEAD`. Two-dot would pull in everything
merged into the base since the branch point, which is the single largest
source of reviewing unrelated code.

1. `git log --oneline <base>..HEAD` — intent, from commit messages.
2. `git diff --name-status <base>...HEAD` — added, modified, deleted,
   renamed. Renames must not be reviewed as new code.
3. `git diff --stat` — size, which drives review depth.
4. Per-file diff with wide context (`-U15`).
5. Read the whole changed file for anything non-trivial. A diff alone
   misrepresents what the surrounding code already handles, and reading the
   file is where most false positives die.

Listed but not reviewed: `vendor/`, `target/`, `dist/`, `node_modules/`,
generated files (`*.pb.go`, `*_generated.go`), lockfiles, binaries.

Uncommitted work is excluded by default. When `git status --porcelain` is
dirty, the report states explicitly how many uncommitted files were left
out; silence there means reviewing the wrong thing.

### Staying in scope

- A finding may anchor only to a line inside a diff hunk. Surrounding code
  is read for context and produces a finding only when the change breaks it.
- Pre-existing defects the branch did not touch appear in a separate
  "Pre-existing, not introduced here" note, at most three of them, never in
  the findings list and never in the verdict.
- Pure renames, formatting-only hunks and generated files are skipped by
  name, one line each.

### Repository-local conventions

Loaded before reviewing, and they override the skill's generic rules:
`CLAUDE.md` / `AGENTS.md` / `.github/copilot-instructions.md`, then
`CONTRIBUTING.md`, then `.editorconfig`, then linter configuration
(`checkstyle.xml`, `spotbugs-*.xml`, `ruff.toml`, `setup.cfg`, `.flake8`,
`.golangci.yml`, `.shellcheckrc`, `.pre-commit-config.yaml`).

The governing rule: if a repository's own configuration already enforces
something, the review does not comment on it. The linter will, and
duplicating it is exactly the nitpicking this design aims to remove. Where a
repository convention conflicts with a rule file, the convention wins and
the report names the convention it deferred to.

### Pre-PR versus post-PR

Detected from Git alone: an upstream exists (`git rev-parse @{u}` succeeds)
and `git log @{u}..HEAD` is empty, so the branch is pushed — treat as
post-PR. Otherwise pre-PR. The mode is printed and can be overridden by
argument.

| | Pre-PR | Post-PR |
|---|---|---|
| Fix suggestions | may offer to apply, after asking | suggests only |
| History | may suggest squashing or message fixes | never; history is public |
| Extra section | drafts a PR description from the change summary | findings shaped as pasteable review comments, anchored `file:line`, split into requested changes versus nits |

### Tooling

The skill proposes a table of commands — the command, what it would catch,
its rough cost — and waits for approval. Nothing runs unapproved.
`helm template` and `kubeconform` are proposed for chart changes because
rendering catches what reading cannot. `code-review-pr-fast` never proposes
commands.

## Review method

### Severity — impact if shipped

| Level | Meaning | Action |
|---|---|---|
| Blocker | breaks at runtime or deploy, loses data, exposes a secret, or breaks a consumer contract | must fix before merge |
| Major | a real defect on a plausible input or failure path; bounded wrong behavior, or missing error handling on an operation that fails in production | fix before merge |
| Minor | correctness-neutral but costly later: a misleading name, duplicated logic, a missing test for new branch logic | author's call |
| Nit | style or preference, and only when no linter covers it | never blocks; at most three per review |

Severity measures impact, never certainty.

### Confidence — orthogonal, always tagged

- **Confirmed** — proven from code read in this repository, with quoted
  lines or command output.
- **Probable** — strong inference resting on exactly one unverified
  assumption, which must be named in the finding.
- **Speculative** — depends on facts not in the repository (cluster state,
  Bamboo variables, runtime environment).

Gates: nothing below Probable enters the findings list. Speculative items
carry no severity and become questions in "Needs your input". A Blocker must
be Confirmed, or it is downgraded.

### False positives and nitpicking

Never reported: anything a configured linter or formatter enforces; renames
and moves with unchanged content; "you could use a library"; idiom swaps;
performance claims without a measurement; inputs the type system prevents;
verbosity in test helpers; anything that cannot be tied to a changed line.

Two gates run before anything is printed:

1. **Verification pass** — re-read every candidate finding against the whole
   file rather than the diff, and drop any the surrounding code already
   handles. The archetypal false positive is a "missing nil check" that the
   caller performs.
2. **Failure-scenario rule** — every Major and Blocker must state concrete
   inputs or state leading to a concrete wrong output. If that sentence
   cannot be written, the finding is downgraded or dropped.

Findings are capped at roughly twelve; overflow is reported as a count
rather than padded out. A clean branch is reported as clean. Findings are
never invented to make the review look productive.

### Cross-file and system reasoning

A mandatory second pass after the per-file pass:

- For every changed public symbol, find all callers and verify each call
  site still holds. Callers outside the diff are where the real bugs are.
- Configuration-to-code coupling: a new environment variable or flag read in
  code — is it set in the Bamboo spec, the Helm values, the Dockerfile? A
  new Helm value — is it templated and defaulted? A renamed Kubernetes
  resource — do selectors and labels still match?
- Data crossing boundaries: files, exit codes, API payloads, artifacts
  passed between Bamboo jobs.
- Idempotency and partial failure: what happens on a re-run, and after a
  crash halfway through.
- Rolling-deploy compatibility: is the change safe while old and new run
  concurrently?

### Tests

Not coverage percentage. The checks are: does each new decision branch have
a test; do the tests assert behavior rather than implementation; are failure
paths tested — the case that matters most in automation code; can each test
actually fail. Existing assertions weakened or deleted in the diff to make a
failure go away are reported as Major. A bugfix without a regression test is
Major. New branch logic without a test is Minor.

### CI/CD and deployment changes

Reviewed as production code, not configuration.

- **Bamboo** — stage, job and task changes; variable scoping (global versus
  plan versus build); plaintext secrets; artifact passing between jobs;
  assumptions about agent capabilities; trigger changes; retry behavior.
- **Docker** — base image pinning, running as root, secrets in build args or
  layer history, `COPY` scope, cache invalidation.
- **Kubernetes** — resource requests and limits, probes, mutable image tags,
  rollout strategy, RBAC widening, ConfigMap and Secret references that must
  already exist.
- **Helm** — defaulted versus required values, rendering under default
  values, chart version bumps, renamed values as a breaking change, the
  rollback story.
- Closing question for all of them: what changes about what runs, when, and
  with which credentials — and can it be rolled back?

## Output format

1. **Header** — repository, branch, base and merge-base SHA, commit count,
   file count, lines added and removed, lenses loaded, mode, excluded paths.
2. **What this branch does** — the change summary. Intent in three to six
   sentences, one line per changed file, then the new behavior walked in
   execution order. Written before the findings, and every finding must be
   consistent with it.
3. **Verdict** — one line: approve, approve with nits, changes requested, or
   blocked, with counts by severity.
4. **Findings** — grouped by severity. Each carries `path:line`, severity,
   confidence, a one-sentence statement of the defect, the failure scenario,
   and a minimal suggested fix. No fix is applied without asking.
5. **Tests**.
6. **Runtime and deploy impact** — present when CI/CD or infrastructure
   changed.
7. **Needs your input** — the speculative questions.
8. **Good** — one to three real strengths, briefly.
9. `code-review-pr` only: the report file path and the tour file path.

### Report file

`<branch-slug>-review.md` at the repository root, following the convention
`investigate-issue` uses for its investigation reports. `<branch-slug>` is
the branch name with `/` replaced by `-`, so `feature/LISA-123` yields
`feature-LISA-123-review.md`. The same slug is used for the tour filename.

### CodeTour

`.tours/review-<branch-slug>.tour` in the repository under review, persona
`pr-reviewer`, chained to the `code-tour` skill with an inline fallback.
Steps are built from evidence already gathered — one step per `file:line`
already cited — ordered by the walkthrough in section 2 and then by
severity. There is no second investigation pass. The tour is skipped only
for a single-file branch with fewer than about three steps, and the skip is
stated in one line with its reason. `.tours/` is covered by the global Git
ignore, so tours stay local.

## Relationship to existing skills

- `explain-logic` explains code for comprehension and explicitly refuses to
  review. These skills review, and carry only as much explanation as section
  2 of the report needs. The boundary stays: "explain this branch" routes to
  `explain-logic`, "review this branch" routes here.
- `investigate-issue` starts from a failure and finds its root cause. These
  skills start from a diff and look for defects that have not happened yet.
- The bundled `/code-review` command and `cavecrew-reviewer` remain
  available; these skills differ by being stack-aware, Bamboo-aware, and by
  producing the change summary, report file and tour.

## Success criteria

- Running `code-review-pr` on a Java/Maven branch loads `lang-java.md` and
  no Go, Helm or Kubernetes rules.
- Running it on a branch that only edits Helm templates in the Go repository
  loads `platform-helm.md` and not `lang-go.md`.
- The base branch and merge-base SHA appear in every report, making a review
  reproducible.
- Reviews of a clean branch report no findings rather than manufacturing
  Nits.
- No finding duplicates something the repository's own linter configuration
  already enforces.
- Every Major or Blocker finding carries a concrete failure scenario.
- `code-review-pr-fast` completes with `git` calls only and writes no files.
