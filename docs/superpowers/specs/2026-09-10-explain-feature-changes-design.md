# explain-feature-changes Skill — Design

Date: 2026-09-10
Status: approved (brainstorming session)
Source idea: `second-brain/2-Projects/Custom Agent Skills/AI Agent Skill - Feature Change Explainer.md`

## Goal

A custom agent skill that helps a developer understand the changes on their
own feature branch compared with its base branch, and explain those changes
confidently to a reviewer. It is not a code-review skill.

The skill turns the diff into:

1. a developer-facing explanation — what changed, why, how the new code works,
   before and after behavior, and how it fits the existing flow; and
2. copy/paste-ready PR text — a PR explanation plus one comment per meaningful
   change.

Core rule: do not summarize `git diff`. The diff is the starting point; the
skill traces callers, callees, tests and configuration until the behavior is
understood, and it separates confirmed facts from likely intent and unknowns.

## Scope

In scope:

- One skill, `explain-feature-changes`, under `agent-skills/skills/`.
- One prompt file, `prompts/explain-feature-changes.prompt.md`, so Copilot in
  VS Code gets the bare `/explain-feature-changes` command.
- An installer change so `write-pr-description` from
  `warpdotdev/common-skills` installs as a default community skill.
- A `REQUIRES` map in the installer so the skills this skill calls are
  installed with it in every install mode. See
  [Skill dependencies](#skill-dependencies).
- Documentation: `USAGE.md`, `README.md`, `docs/community-skills.md`.

Out of scope:

- Any PR-host integration. No Bitbucket or GitHub API calls, no posting
  comments, no reading PR metadata. Everything comes from local Git.
- Code review. Obvious issues that affect understanding go in a short
  "Important Observations" section; anything more is left to a dedicated
  review skill.
- Explaining single files, single functions, or branches the user did not
  write.
- Changes to the user's other custom skills.

## Constraints

- **No runtime dependency on the user's custom skills** (`explain-logic`,
  `code-review-pr`, `code-review-pr-fast`, `investigate-issue`, and so on).
  They may be renamed, removed or rewritten. The skill never names them.
  Reuse comes only from skills published on skills.sh.
- **Agent Skills standard.** Frontmatter holds only `name` and `description`.
  No Claude-only or Copilot-only tools in the core behavior.
- **Both IDE families.** VS Code and JetBrains (IntelliJ, PyCharm, GoLand),
  with Copilot and Claude in each. See [IDE support](#ide-support).
- **Read-only.** Only `git` commands and file reads. Never commit, push,
  reset, rebase, checkout, stash, or edit source unless the user asks. The
  only files written are the report and the tour.
- **Shell-neutral commands.** On the Windows VDI the JetBrains terminal may be
  PowerShell or cmd. The skill uses plain `git` commands only: no `$(...)`, no
  pipes, no `grep` or `sed`.
- Installed by `agent-skills/install.py` like the other custom skills; the
  installer discovers every directory under `skills/`, so the skill itself
  needs no installer change.
- Commits use Roj's Git identity only.

## Reuse decisions

Candidates were found through the skills.sh search API
(`https://skills.sh/api/search?q=...`) for "explain diff", "explain changes",
"pr description", "git diff", "code review", "code-tour" and "context map",
and their `SKILL.md` files were read before deciding.

| Skill | Relevance | Decision | Reason |
|---|---|---|---|
| `github/awesome-copilot/code-tour` | High | Compose | Writes the `.tours/` file in phase 8. Already a default community skill. |
| `github/awesome-copilot/context-map` | Medium | Compose | Maps related files first on large branches. Already a default community skill. |
| `warpdotdev/common-skills/write-pr-description` (MIT, 2.4K installs) | High | Compose | Shapes the PR Explanation: collect facts first, repository PR template wins, cut ruthlessly, no padding words. Its `gh` fact-gathering step is skipped; this skill supplies the verified facts. |
| `warpdotdev/common-skills/pr-walkthrough` (24K installs) | Low | Not used | Produces a Warp-branded D3 HTML page, needs `gh`, publishes to Cloudflare. |
| `chris-graffagnino/explain-diff` (MIT) | High overlap | Pattern only | Stated-vs-inferred intent and analysis lenses informed `tracing.md`. Installing it would add a second explainer competing for the same triggers. |
| `sjunepark/agent-scripts/change-explainer` | Low | Not used | Written for a cold reader; here the reader is the author. |
| `mryll/skills/explain-pr`, `aymericderbois/skills/explain-your-changes` | Low | Not used | Shallow; few installs. |
| `amplitude/mcp-marketplace/diff-intake`, `ruvnet/ruflo/diff-analyze` | Low | Not used | Different purpose. |
| `mattpocock/skills/code-review`, `coderabbitai/skills/code-review` and similar | Low | Not used | Code review is a different purpose. |

The same table ships in `USAGE.md`.

## Layout

```
agent-skills/
├── skills/explain-feature-changes/
│   ├── SKILL.md                 workflow only: phases 1-8
│   ├── references/
│   │   ├── tracing.md           symbol inventory, tracing, language trace
│   │   │                        paths, architecture checklist, tests
│   │   └── output-template.md   report skeleton, evidence and style rules,
│   │                            PR comment format, fallback PR rules
│   ├── examples/example-run.md  worked run on the should_trigger_integration()
│   │                            scenario from the source idea
│   └── USAGE.md                 examples per IDE, reuse table, JetBrains
│                                checklist
├── prompts/explain-feature-changes.prompt.md
├── install.py                   new warp-common-skills source, `subdir` key,
│                                REQUIRES map
├── test_install.py              subdir, dependency and portability tests
├── README.md                    layout entry, dependencies, JetBrains
│                                checklist count, root-install note
└── docs/community-skills.md     write-pr-description entry
```

`references/` files load only when a phase needs them: `tracing.md` at
phase 3, `output-template.md` at phase 6.

## Triggers

The frontmatter `description` targets the author explaining their own branch
against a base. Example phrases:

- "Explain my changes compared to develop."
- "Help me understand what I changed in this feature branch."
- "Explain the new functions and code flow in my branch."
- "Generate something I can paste into my PR explaining these changes."
- "Help me explain these changes to my code reviewer."

It states that the skill is not a code review and does not cover single
files, single functions, or other people's branches.

Known overlap: while `explain-logic` keeps generic triggers such as "walk me
through this branch", vague requests may select either skill. The explicit
command always selects this one. `explain-logic` is left unchanged because the
user plans to rework it.

## Invocation

- `/explain-feature-changes` — base branch resolved automatically.
- `/explain-feature-changes develop`, `/explain-feature-changes main` — the
  argument is the base branch.
- Automatic selection from the description, in any supported agent.

## IDE support

| | VS Code | JetBrains (IntelliJ / PyCharm / GoLand) |
|---|---|---|
| Copilot | `/explain-feature-changes` (prompt file, user profile) | `/skill:explain-feature-changes` (skill in `~/.copilot/skills/`, every project) |
| Copilot, repo seeded with `--repo .` | same | `/explain-feature-changes` (from `.github/prompts/`) |
| Claude | `/explain-feature-changes` (skill) | `/explain-feature-changes` (skill) |

Because the prompt shares its name with a real skill, the installer skips
generating a prompt-derived skill for it — the existing behavior for
`code-review-pr` and `tour-codebase`.

Rules that keep JetBrains working:

1. The prompt file uses no `${selection}` or `${input:...}` variables. Those
   are VS Code prompt variables and are not guaranteed to expand in JetBrains.
   The base branch is read from the message text.
2. Commands are plain `git`. Callers are found with `git grep -n <symbol>`.
   The merge base is obtained with `git merge-base <base> HEAD` and the
   printed SHA is reused in later commands, instead of `$(...)` substitution.
3. Copilot needs agent mode to run terminal commands. Without a terminal, the
   skill asks the user to paste `git diff <base>...HEAD`, explains that, and
   says which phases it skipped.
4. File references are plain `path/from/repo/root:start-end` text, which
   reads the same in VS Code chat, JetBrains chat and the Markdown report.
   No `#L` link anchors.
5. The `.tour` file opens in VS Code through the CodeTour extension. A
   JetBrains CodeTour viewer is not confirmed; during implementation, check
   the JetBrains Marketplace and record the result in `USAGE.md`. In
   JetBrains the report file is the primary navigation aid.
6. `write-pr-description` installs with `targets: ANY`, so JetBrains Copilot
   receives it through `~/.copilot/skills/`.

## Workflow (SKILL.md)

### Phase 1 — Resolve the base branch

1. The user's argument, if given.
2. `develop` — `origin/develop` if it exists, otherwise local `develop`.
3. `main` — `origin/main` if it exists, otherwise local `main`.
4. Otherwise ask the user. Never guess.

If the current branch is the resolved base, ask. Record
`git merge-base <base> HEAD` and print the comparison:

> Comparing: `feature/x → develop` (merge base `a1b2c3d`)

No commit-count or diff-size sanity gate (user decision).

### Phase 2 — Collect the diff

1. `git status --porcelain` — uncommitted files are listed in the report
   header and not explained. The explanation covers committed work only, so
   the PR text matches what reviewers will see.
2. `git log <base>..HEAD` — commit subjects and bodies as intent evidence.
3. `git diff --name-status <base>...HEAD` — added, modified, deleted, renamed.
4. `git diff --stat <base>...HEAD` — size drives depth.
5. `git diff -U15 <base>...HEAD -- <file>` per file.
6. Read the whole changed file for anything non-trivial.

Always three-dot for diffs. Vendor directories, generated files, lockfiles
and formatting-only changes get one line each.

Large branch (roughly more than 15 files or 1000 changed lines): chain
`context-map` if installed, write an executive summary first, and group files
by responsibility rather than alphabetically.

### Phase 3 — Build the change inventory

Load `references/tracing.md`. Per file: status, purpose of the file, what
changed, and category — behavior, API/interface, configuration, dependency,
test, or trivial. Per symbol: new, modified, or removed.

### Phase 4 — Trace

For each important symbol: callers (`git grep -n`), callees, inputs, outputs,
what happens with the return value, the previous code
(`git show <merge-base>:<path>`, `git log -S` for moved logic), tests that
exercise it, and configuration that affects it. Then run the architecture and
technology checklist, limited to what the change touches.

### Phase 5 — Establish intent

Evidence: commit messages, ticket IDs in the branch name or commits, test
names, documentation, naming. Every intent claim is labeled:

- **Confirmed** — directly observable in the repository.
- **Likely** — "The likely purpose is ..." with the evidence named.
- **Unknown** — "The exact reason is not explicit in the code."

### Phase 6 — Write

Load `references/output-template.md`. Sections, in order, omitting any that
would be empty:

1. Feature Change Overview (2–5 sentences)
2. Why This Change Exists (confirmed / likely / unknown)
3. Changes by File (what changed, why, important symbols, before → after)
4. New Functions / Classes (symbol cards)
5. End-to-End Flow
6. Key Things to Understand (3–7 points)
7. PR Explanation
8. PR Comments (one per meaningful, grouped change)
9. Important Observations

PR Explanation: pass the verified facts to `write-pr-description`, skip its
`gh` step, and honor a repository PR template if one exists. If the skill is
absent, apply the fallback rules in `output-template.md`.

Output:

- File: `<branch-slug>-changes.md` at the repository root, where
  `<branch-slug>` is the branch name with `/` replaced by `-`.
- Chat, after phase 8: the comparison line, the overview, Key Things to
  Understand, the report and tour paths; the offer covers the report and
  `.tours/`.
- The report is untracked. The skill says so and offers to add it to
  `.git/info/exclude`. It never edits `.gitignore`.

### Phase 7 — Self-check

Condensed from the source idea's §27: correct base, diff inspected,
surrounding code read, callers and downstream calls traced, before and after
explained, facts separated from assumptions, line references present, tests
inspected, no generic review findings, PR text pasteable.

### Phase 8 — Tour

Write `.tours/changes-<branch-slug>.tour`, persona `pr-reviewer`, through the
`code-tour` skill; if it is absent, write a minimal tour inline (`$schema`,
`title`, `description`, `steps` of `{file, line, description}`). Steps follow
the End-to-End Flow order and reuse only `file:line` references already
cited — no second investigation. Validate with `code-tour`'s
`scripts/validate_tour.py`, resolved from whichever installed skill directory
exists; skip validation if it cannot be found. Skip the tour only when the
branch is one file with fewer than about three steps, and say so in one line.

## references/tracing.md

- **Symbol card fields:** file, line range, purpose, inputs, outputs,
  important conditions, dependencies, side effects, callers, downstream calls,
  effect on the existing flow.
- **Trace paths by language:**
  - Java: class → method → interface → implementation → caller; Spring wiring
    via `git grep` for `@Component`, `@Bean`, `implements X`.
  - Python: module → function → caller; decorators, `from x import y`.
  - Go: package → function → interface → implementation; interfaces are
    implicit, so search for the method signature.
  - JavaScript/TypeScript: export → import sites.
  - Bash: script → function → external process; also who invokes the script
    (CI specs, other scripts).
  - YAML/configuration: key → code that reads the key → runtime behavior.
  - SQL: migration → queries and entities.
- **Before and after:** `git show <merge-base>:<path>` for the old version;
  `git log -S <text>` to find logic that moved.
- **Stop rule:** one caller level up and one callee level down; go further
  only while the return value keeps flowing.
- **Architecture and technology checklist:** component responsibilities,
  APIs and interfaces, dependency injection, Kafka and messaging, databases,
  configuration, external integrations, concurrency and async processing,
  error handling, CI/CD and Bamboo. Explain how this change uses or affects a
  technology; no generic tutorials.
- **Tests:** the behavior each test pins, new scenarios, whether the new path
  is exercised. Gaps only when they matter for understanding the feature.

## references/output-template.md

- **Report header:** comparison, merge base, commit count, uncommitted files
  left out, skipped files.
- **Section skeleton:** as listed in phase 6, following the source idea's §25.
- **Evidence rules:** `path:start-end` references for important claims; the
  confirmed / likely / unknown labels; no impact claim without evidence
  ("removes the repeated lookup previously performed by the caller", not
  "improves performance").
- **Style:** senior engineer to engineer. Preferred openings: "Added",
  "Moved", "Changed", "The function now", "Previously", "The caller now",
  "This separates", "This allows". Banned without evidence: "elegantly",
  "robustly", "enhances", "significantly improves".
- **PR comment format:** `### path:start-end — <title>`, then what was added
  or changed, what happened before, and the resulting flow. Related hunks are
  grouped; trivial lines get no comment.
- **Fallback PR Explanation rules:** concise, factual, references files,
  functions and line ranges, explains the reason, flow and before/after, no
  file inventory, copy/paste ready.
- **Important Observations:** at most about five, only items that change how
  the feature should be understood (unexpected behavior change, suspicious
  control flow, missing handling, dependency implications, tests that do not
  match the implementation). For a full review, point to a dedicated
  code-review skill without naming one.

## Installer change

New entry in `SOURCES`:

```python
{
    "label": "warp-common-skills",
    "url": "https://github.com/warpdotdev/common-skills.git",
    "branch": "main",
    "cache": "warp-common-skills",
    "subdir": ".agents/skills",
    "fallback": "https://github.com/warpdotdev/common-skills/tree/main/.agents/skills",
    "skills": {
        "write-pr-description": {"targets": ANY, "default": True},
    },
},
```

Every place that builds `cache / "skills"` resolves the directory through one
helper that returns `cache / source.get("subdir", "skills")` — fetch or
sparse-checkout, install, status and fallback handling. Sources without
`subdir` behave exactly as before.

## Skill dependencies

The skills this skill calls must be installed wherever it is installed.
Today that holds only for flag runs (`--target both`, and the root
`./install.py install agent-skills`, which runs the same flag run), because
`code-tour`, `context-map` and `write-pr-description` are all in the default
community set. It does not hold for interactive picks that untick a
dependency, for `--skills-only`, or after `--uninstall` of a dependency.

### Declaration

A `REQUIRES` map in `install.py`, next to `SOURCES`:

```python
REQUIRES = {
    "explain-feature-changes": ["code-tour", "context-map",
                                "write-pr-description"],
}
```

Keys are custom skill names. Values may be community skills, externals, or
other custom skills, so later skills can declare their own chains.

`README.md` currently says the root `./install.py install agent-skills` runs
"no community fetch". That is stale — `lib/tools/agent_skills.py`
deliberately runs a flag install without `--skills-only`. The README line is
corrected as part of this work, since dependency coverage depends on it.

### Behavior

- **Install (flag, interactive, `--repo`):** every selected custom skill's
  requirements are added to the same run and the same target. In the
  interactive picker a required item that was unticked is added back, and the
  run logs `write-pr-description (required by explain-feature-changes)`.
- **`--skills-only`:** nothing is fetched. A requirement already present in
  the target is fine. A missing one produces a summary warning —
  `explain-feature-changes: missing write-pr-description — re-run without
  --skills-only when online`. The skill still runs on its fallback.
- **`--status`:** lists missing requirements per target.
- **`--uninstall`:** removing a skill that an installed skill requires prints
  a warning naming the dependent. It does not block the uninstall.
- **Runtime:** if a required skill is absent anyway, the skill names it and
  its skills.sh source, uses its fallback, and continues.

### Invariants (enforced by tests)

- Every `REQUIRES` key is a directory under `skills/` — a renamed or removed
  custom skill fails the test instead of silently dropping its dependencies.
- Every value is a known custom, community or external name.
- Every requirement supports every target its dependent installs to.

## Testing

1. **Installer unit tests (`test_install.py`):** a source with `subdir`
   resolves its skills from that directory; a source without it still uses
   `skills/`; `write-pr-description` is in the default community set;
   `--status` reports it. Dependencies: the `REQUIRES` invariants above;
   flag and interactive runs add requirements; `--skills-only` warns about
   missing ones; `--status` lists them; `--uninstall` of a requirement warns.
   Run with `cd agent-skills && python3 -m unittest test_install -v`.
2. **Portability test:** scan the command text in `SKILL.md`,
   `references/tracing.md` and the prompt file — fenced code blocks and
   inline code spans that begin with `git`. Assert none contains `$(`, a
   backtick substitution, or a `|` pipe, and that no command invokes a bare
   `grep` or `sed` (`git grep` is allowed). Markdown table pipes outside code
   are not checked.
3. **Skill behavior**, following `superpowers:writing-skills`:
   - Build a scratch repository in the session scratchpad with a `develop`
     branch and a feature branch that adds `should_trigger_integration()`,
     moves a condition out of `process_event()`, adds a test and reads a new
     configuration key.
   - Run once without the skill (baseline) and once with it; score both
     against the phase 7 checklist — base named, callers traced, before/after
     correct, intent labels present, line ranges accurate, PR text pasteable.
   - Also run with a dirty working tree, and in a repository without
     `develop` or `main`, to exercise the header note and the ask path.
4. **Installer smoke test:** `python3 install.py --target both --dry-run`,
   then `python3 install.py --status`.
5. **JetBrains (manual):** a checklist in `USAGE.md` — agent mode enabled,
   `/skill:explain-feature-changes develop` lists and runs, `git` runs in the
   IDE terminal, the report opens. Record the CodeTour-viewer finding.
