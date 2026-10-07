# Soundboarding Migration + Interactive Installer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Migrate the soundboarding Copilot skill from `~/Dev/sb-skill` into `agent-skills/` (prompts + cross-platform SKILL.md + bundled template/examples), add per-skill USAGE.md docs, and add per-item interactive selection to `install.py`.

**Architecture:** Prompts stay self-contained near-verbatim copies (work VDI deploys them alone); a parallel `skills/soundboarding/SKILL.md` carries the same workflow for Claude Code/IntelliJ with the template bundled beside it. `install.py` gains a plain-input item picker used only on the no-flags interactive path; the flag path is byte-for-byte behavior-compatible.

**Tech Stack:** Markdown prompt/skill files; Python >= 3.8 stdlib only; `unittest`.

**Spec:** `docs/superpowers/specs/2026-07-17-soundboarding-migration-design.md`

## Global Constraints

- Python >= 3.8, standard library only (no curses, no third-party deps).
- `~/Dev/sb-skill` is read-only source — never modify it.
- Prompt hard rules preserved verbatim (truthfulness, template fidelity, no git actions, per-task review stops).
- Work-path defaults stay: `SOUNDBOARD_DIR=/c/dev/projects/wr/soundboard`, `PROJECTS_ROOT=/c/dev/projects`.
- With any `--target` flag, `install.py` behavior is unchanged (installs everything, non-interactive) — `setup.sh` depends on this.
- All shell commands below run from `/Users/roj/Dev/.dotfiles` unless stated.

---

### Task 1: Migrate the three prompt files

**Files:**
- Create: `agent-skills/prompts/create-sb.prompt.md`
- Create: `agent-skills/prompts/implement-sb.prompt.md`
- Create: `agent-skills/prompts/create-implement-sb.prompt.md`

**Interfaces:**
- Consumes: `/Users/roj/Dev/sb-skill/prompts/*.prompt.md` (read-only source).
- Produces: three prompt files that Task 4's installer picks up by the existing `*.prompt.md` glob; Task 3's USAGE.md references them by these exact names.

- [ ] **Step 1: Copy the three files verbatim**

```bash
cp /Users/roj/Dev/sb-skill/prompts/create-sb.prompt.md \
   /Users/roj/Dev/sb-skill/prompts/implement-sb.prompt.md \
   /Users/roj/Dev/sb-skill/prompts/create-implement-sb.prompt.md \
   agent-skills/prompts/
```

- [ ] **Step 2: Add the override note to each Configuration section**

In each of the three copied files, insert this line as a new paragraph at the end of the `## Configuration` section (in `create-sb` and `implement-sb` that is directly after the line starting `On Windows these Git Bash paths map to`; in `create-implement-sb` it is directly after the `- SOUNDBOARD_DIR:` bullet):

```markdown
These paths are defaults, not requirements — override SOUNDBOARD_DIR or PROJECTS_ROOT by stating different paths in your message.
```

(`create-implement-sb.prompt.md` has no PROJECTS_ROOT; use this variant there:)

```markdown
This path is a default, not a requirement — override SOUNDBOARD_DIR by stating a different path in your message.
```

- [ ] **Step 3: Verify — diff shows only the override lines**

Run: `for f in create-sb implement-sb create-implement-sb; do diff /Users/roj/Dev/sb-skill/prompts/$f.prompt.md agent-skills/prompts/$f.prompt.md; done`
Expected: each diff shows exactly one added line (the override note), nothing else.

- [ ] **Step 4: Commit**

```bash
git add agent-skills/prompts/create-sb.prompt.md agent-skills/prompts/implement-sb.prompt.md agent-skills/prompts/create-implement-sb.prompt.md
git commit -m "feat(agent-skills): migrate soundboarding prompt files from sb-skill"
```

---

### Task 2: Create skills/soundboarding/ (SKILL.md + template + example pair)

**Files:**
- Create: `agent-skills/skills/soundboarding/SKILL.md`
- Create: `agent-skills/skills/soundboarding/SB-template.md` (copy)
- Create: `agent-skills/skills/soundboarding/examples/LISA-110278.md` (copy)
- Create: `agent-skills/skills/soundboarding/examples/sb-LISA-110278.md` (copy)

**Interfaces:**
- Consumes: `/Users/roj/Dev/sb-skill/examples/` files (read-only source).
- Produces: skill folder named `soundboarding` that Task 4's installer picks up by the existing `skills/*` dir scan; Task 3 adds `USAGE.md` into this same folder.

- [ ] **Step 1: Copy template and example pair**

```bash
mkdir -p agent-skills/skills/soundboarding/examples
cp /Users/roj/Dev/sb-skill/examples/SB-template.md agent-skills/skills/soundboarding/
cp /Users/roj/Dev/sb-skill/examples/LISA-110278.md agent-skills/skills/soundboarding/examples/
cp "/Users/roj/Dev/sb-skill/examples/sb-LISA-110278.md" agent-skills/skills/soundboarding/examples/
```

- [ ] **Step 2: Write SKILL.md**

Create `agent-skills/skills/soundboarding/SKILL.md` with exactly this content:

````markdown
---
name: soundboarding
description: Soundboarding (SB) workflow — turn a user story (LISA-<id>.md) into an SB document with codebase-investigated core tasks, or implement an existing SB document task by task with review stops. Use when the user says "soundboarding", "create an SB", "SB document", "implement SB-...", or asks to turn a user story into a refined, investigated task list before implementation.
---

# Soundboarding

Turn a user story into a soundboarding (SB) document grounded in real code
investigation, present it to the team for refinement, then implement it task
by task. Three flows: **create**, **implement**, and **create + implement**
chained. Pick the flow from what the user asked for.

## Configuration

- SOUNDBOARD_DIR: `/c/dev/projects/wr/soundboard` (Windows: `C:\dev\projects\wr\soundboard`)
- PROJECTS_ROOT: `/c/dev/projects` (Windows: `C:\dev\projects`)
- TEMPLATE: the `SB-template.md` file in this skill's own folder; if it is
  missing, fall back to `SOUNDBOARD_DIR/SB-template.md`.

These paths are defaults, not requirements — the user can override
SOUNDBOARD_DIR or PROJECTS_ROOT by stating different paths in their message.

## Hard rules (all flows)

1. **Truthfulness:** State as fact only file paths and values you actually
   read from local checkouts during this run. Everything unverified goes into
   the Questions section. Never present an assumption as a finding.
2. **Template fidelity:** Read TEMPLATE fresh at the start of every create
   run and produce every section it defines. If no template can be found:
   STOP and ask. Never invent the structure.
3. **Git: hands off.** Never create a branch, never commit, never push — in
   any repository. All edits stay in the working tree; the user reviews,
   commits, and branches manually. Read-only git commands (`git status`,
   `git diff`) are allowed.
4. **Ask, don't guess:** when something is ambiguous, ask the user one
   question and wait for the answer.

## Flow 1: Create an SB document

Input: a user story markdown file (example: `LISA-110278.md`). Resolve it as
given relative to the current workspace first, then inside SOUNDBOARD_DIR.
If it cannot be found or read: STOP and ask. Never proceed with an invented
story.

1. **Read inputs.** Read the story file and TEMPLATE. Extract the goal, the
   acceptance criteria, and every repository, system, tool, and version
   mentioned or implied.
2. **Identify impacted repositories.** The repository open in the current
   workspace is assumed impacted unless the story clearly says otherwise.
   For every other repository named or implied, look for a local checkout
   under PROJECTS_ROOT, searching one and two directory levels deep. If a
   repository has no local checkout, add it to Questions ("Repo X is not
   cloned locally — investigate before implementation") and do not guess its
   contents.
3. **Investigate the code.** For each locally available impacted repository,
   find the concrete things that must change: exact files and paths, current
   values (versions, config properties, image tags, dependencies) and the
   required new values, and things already compliant — list those too, so
   the team knows they were checked. Record current values exactly as they
   appear in the files.
4. **Compose the SB document.** Follow TEMPLATE structure exactly:
   - **Title / Goal:** from the story.
   - **Acceptance Criteria:** copy the story's criteria verbatim as `- [ ]`
     checkboxes. Add newly discovered criteria as extra checkboxes suffixed
     with `*(proposed)*`.
   - **Core tasks:** concrete `- [ ]` checkboxes. Each code task starts with
     the repository it touches in backticks. Where investigation found exact
     changes, include before/after tables with columns: #, File/Property,
     Before, After, Reason. Non-code tasks (emails, requests to other teams)
     are plain checkboxes without a repo tag.
   - **Questions:** unknowns from the investigation, missing repos, story
     ambiguities — plus every standing question already in the template.
   - **Notes:** risks, environment caveats, and one line listing the
     impacted repositories.
   - **Testing:** proposed test cases with Test Case ID (TC-1, TC-2, ...),
     Situation, and Expected result filled in; leave Log and Build result
     link cells empty — they are completed during implementation.
5. **Write the output file.** Name it `SB-` + the story file's basename
   (`LISA-110278.md` → `SB-LISA-110278.md`) and write it into SOUNDBOARD_DIR
   by absolute path, regardless of the current workspace. If file-editing
   tools refuse to write outside the workspace, write from the terminal. If
   the output file already exists: show a short summary of what would change
   and ask before overwriting.
6. **Report.** End with a short summary: repositories investigated, findings
   verified vs assumed, and the open questions for team refinement.

See `examples/LISA-110278.md` (story) and `examples/sb-LISA-110278.md`
(resulting SB) for the expected shape.

## Flow 2: Implement an SB document

Input: an SB document name or file (examples: `SB-LISA-110278`,
`SB-LISA-110278.md`, or an attached/opened file). A bare name resolves
inside SOUNDBOARD_DIR; `.md` is optional and matching is case-insensitive.
Multiple matches: list them and ask which. No match: STOP and ask.

1. **Read the SB document.** Parse the Core tasks checkboxes. Tasks already
   ticked `- [x]` are done — skip them (resumable mid-sprint).
2. **Determine target repositories.** The repository open in the current
   workspace is the primary target. A task starting with another repository
   name in backticks targets that repository's checkout under PROJECTS_ROOT
   (search one and two levels deep).
3. **Preflight.** Verify every repository needed by the remaining tasks
   exists locally; if one is missing, report which and STOP before touching
   anything. Run `git status --porcelain` in each target repository and warn
   about dirty working trees (informational only — continue after warning).
4. **Per-task loop.** For each unticked core task, in order:
   1. Announce the task.
   2. Non-code task (no repo tag — typically inform, email, request
      permissions, present to team): do not execute, do not tick; say it is
      manual and go to the review stop.
   3. Code task: make the edits in the target repository.
   4. Show what changed: files touched and a brief summary of each change.
   5. STOP and ask: approve, request changes, or skip?
      - Approve → tick a code task's checkbox to `- [x]` in the SB file
        (manual tasks stay unticked); continue.
      - Request changes → revise, show the result, stop again.
      - Skip → leave unticked, note the skip, continue.
5. **Testing phase.** For each Testing table row, run whatever is locally
   runnable (unit tests, linters, builds) and write a one-line result into
   the Log column — only results of commands actually run. For tests
   needing unreachable environments: set Log to `manual — pending`. Leave
   Build result link cells for the user. If the SB file is outside the
   workspace and editing tools refuse, update it from the terminal.
6. **Wrap-up.** Update the SB file (checkboxes, Testing table, add learnings
   to Notes). Report a per-repository list of changed files for manual
   review and commit, plus the manual tasks still open.

## Flow 3: Create + implement in one run

For stories where team refinement between soundboarding and implementation
is skipped.

1. Run Flow 1 on the user's story input.
2. When the SB file is written, present a short summary and ask exactly one
   confirmation question: "SB created — proceed with implementation?" Wait.
   If declined, stop; the SB file stays as created.
3. On confirmation, run Flow 2 on the SB file just created — including every
   per-task review stop and the no-git rule.
````

- [ ] **Step 3: Verify**

Run: `ls agent-skills/skills/soundboarding agent-skills/skills/soundboarding/examples && head -4 agent-skills/skills/soundboarding/SKILL.md`
Expected: `SKILL.md SB-template.md examples`, the two example files, and frontmatter starting `---` / `name: soundboarding`.

- [ ] **Step 4: Commit**

```bash
git add agent-skills/skills/soundboarding
git commit -m "feat(agent-skills): add cross-platform soundboarding skill with template and examples"
```

---

### Task 3: Usage docs (USAGE.md × 2, community-skills.md, README update)

**Files:**
- Create: `agent-skills/skills/soundboarding/USAGE.md`
- Create: `agent-skills/skills/explain-logic/USAGE.md`
- Create: `agent-skills/docs/community-skills.md`
- Modify: `agent-skills/README.md`

**Interfaces:**
- Consumes: prompt names from Task 1, skill folder from Task 2, existing README usage table content (moves into `skills/explain-logic/USAGE.md`).
- Produces: doc paths the README links to; nothing downstream consumes these programmatically.

- [ ] **Step 1: Write skills/soundboarding/USAGE.md**

````markdown
# Using the soundboarding skill

Turns a user story (`LISA-<id>.md`) into a soundboarding (SB) document with
codebase-investigated core tasks, then implements the SB task by task with a
review stop after every task. Never touches git — you review and commit
manually.

## When to use

- A user story needs refinement into concrete, investigated tasks before
  the team commits to it → **create**.
- A refined SB document is ready to execute → **implement**.
- Solo story, no team refinement needed → **create + implement** chained.

## Commands per platform

| Flow | VS Code Copilot (slash) | IntelliJ Copilot / any chat | Claude Code |
|---|---|---|---|
| Create SB | `/create-sb LISA-110278.md` | `Use the soundboarding skill: create an SB from LISA-110278.md` | `create an SB document from LISA-110278.md` |
| Implement SB | `/implement-sb SB-LISA-110278` | `Use the soundboarding skill: implement SB-LISA-110278` | `implement SB-LISA-110278` |
| Both chained | `/create-implement-sb LISA-110278.md` | `Use the soundboarding skill: create and implement LISA-110278.md` | `create and implement an SB from LISA-110278.md` |

Paths default to the work layout (`/c/dev/projects/wr/soundboard`,
`/c/dev/projects`). Override by saying so, e.g.
`create an SB from story.md — soundboard dir is ~/Dev/soundboard`.

## Worked example

Story input: [`examples/LISA-110278.md`](examples/LISA-110278.md) — upgrade
Bamboo API to v12.1.6 and verify agents/plans still work.

1. `/create-sb LISA-110278.md` — the skill reads the story, finds the
   impacted repos under the projects root, records exact current versions
   from the POMs and config files it can read, and writes
   `SB-LISA-110278.md` following `SB-template.md`. Unverifiable claims land
   in Questions, not in Core tasks. Output shape:
   [`examples/sb-LISA-110278.md`](examples/sb-LISA-110278.md).
2. Team refines the SB (acceptance criteria, task list, testing table).
3. From the repo where the work happens: `/implement-sb SB-LISA-110278` —
   executes core tasks one at a time, stops after each for
   approve/revise/skip, ticks checkboxes in the SB file, fills the Testing
   table Log column with real command results.
4. You review the working tree and commit manually.
````

- [ ] **Step 2: Write skills/explain-logic/USAGE.md**

Move the existing README usage table (README lines under "## Usage (VS Code / IntelliJ Copilot chat, agent mode)") into this file:

````markdown
# Using the explain-logic skill

Guided, step-by-step code comprehension: PR/branch diffs, files, functions —
explained as Concept → Code flow → Why → Gotchas, with the matching language
lens (Java / Python / Go / shell / Bamboo API).

## Commands per platform

VS Code gets the `/explain-code` and `/explain-and-review` slash commands
(from `prompts/`). IntelliJ has no prompt files — use the plain-English
prompts; the skill triggers on the phrasing. If a skill doesn't trigger,
name it once ("Use the explain-logic skill to ...") — after one explicit
use it picks up reliably. Claude Code triggers on the same phrasing.

| Goal | VS Code | IntelliJ / Claude Code |
|---|---|---|
| Understand a feature branch | `/explain-code the changes in this branch vs main` | `Use the explain-logic skill: walk me through the changes in this branch vs main` |
| Understand a PR | `/explain-code PR #142` | `Use the explain-logic skill: explain PR #142` |
| Understand a file | `/explain-code src/foo/bar.py` | `Use the explain-logic skill: explain the logic in src/foo/bar.py` |
| Understand a selection | select code → `/explain-code` | select code → `Explain the logic in this selection step by step` |
| Understand + flag risks | `/explain-and-review PR #142` | `Explain and review PR #142 — walkthrough first, then flag anything risky` |
| New repo, big picture first | `/explain-code — onboard me to this repo first, then explain branch feature/x` | `Onboard me to this repo first, then explain branch feature/x` |
| Save as replayable tour | add `then create a code tour` to any prompt | same phrasing (needs CodeTour extension in VS Code) |
| Terse output (save tokens) | add `use caveman mode` to any prompt | `Caveman mode: explain the changes in this branch vs main` |

## Worked example

`/explain-and-review PR #142` pulls the real diff, reads surrounding code,
callers, and tests, explains the change step by step, then a clearly
separated review phase rates findings 🔴 likely bug / 🟡 risky / 🟢 style.
````

- [ ] **Step 3: Write docs/community-skills.md**

````markdown
# Community skills

Fetched by `install.py` into `~/.agent-skills-cache/` and installed
alongside the custom skills. Sources: `github/awesome-copilot` and
`juliusbrussee/caveman`.

## code-tour
Creates CodeTour `.tour` walkthroughs through a repo, PR, or bug.
- `Create a code tour of the auth flow for a new joiner`
- `Make an RCA tour for the bug fixed in PR #97`

## acquire-codebase-knowledge
Maps and documents an existing codebase for onboarding.
- `Map this codebase and create onboarding docs`

## context-map
Lists every file relevant to a task before changes are made.
- `Build a context map for adding rate limiting to the API`

## architecture-blueprint-generator
Generates an architecture blueprint (stack detection, patterns, diagrams).
- `Generate an architecture blueprint for this repo`

## add-educational-comments
Adds explanatory comments to a file for learning purposes.
- `Add educational comments to src/scheduler.py`

## caveman
Terse-output mode — cuts output tokens while keeping technical substance.
- `Caveman mode: explain this build failure`
- Combine with other skills: `use caveman mode` appended to any prompt.
````

- [ ] **Step 4: Update agent-skills/README.md**

- In `## Layout`, add after the explain-logic bullet:

```markdown
- `skills/soundboarding/` — story → SB document → task-by-task
  implementation workflow (bundled `SB-template.md` + examples).
```

- Update the prompts bullet to:

```markdown
- `prompts/` — Copilot/VS Code `.prompt.md` slash commands
  (`/explain-code`, `/explain-and-review`, `/create-sb`, `/implement-sb`,
  `/create-implement-sb`). Not used by Claude.
```

- Replace the whole `## Usage (VS Code / IntelliJ Copilot chat, agent mode)` section (heading, intro paragraphs, table, and the "What the explain flow does" paragraph) with:

```markdown
## Usage

Per-skill guides with copy-paste examples for VS Code, IntelliJ, and
Claude Code:

- [explain-logic](skills/explain-logic/USAGE.md)
- [soundboarding](skills/soundboarding/USAGE.md)
- [community skills](docs/community-skills.md) (code-tour, caveman, ...)
```

- In `## Install`, replace the line `python3 install.py                    # interactive menu` with:

```markdown
python3 install.py                    # interactive: pick target + items
```

and add after the flags line:

```markdown
Interactive runs (no flags) show an item picker: toggle individual skills,
prompt files, and community skills by number, `a` for all, enter to
confirm. Flag runs install everything, unchanged.
```

- [ ] **Step 5: Verify links**

Run: `grep -n "USAGE.md\|community-skills.md" agent-skills/README.md && ls agent-skills/skills/explain-logic/USAGE.md agent-skills/skills/soundboarding/USAGE.md agent-skills/docs/community-skills.md`
Expected: three README links; three files exist.

- [ ] **Step 6: Commit**

```bash
git add agent-skills/skills/soundboarding/USAGE.md agent-skills/skills/explain-logic/USAGE.md agent-skills/docs/community-skills.md agent-skills/README.md
git commit -m "docs(agent-skills): per-skill USAGE guides and community skills index"
```

---

### Task 4: Interactive item picker in install.py

**Files:**
- Modify: `agent-skills/install.py`
- Test: `agent-skills/test_install.py`

**Interfaces:**
- Consumes: existing `install.py` module structure (`COMMUNITY_SKILLS`, `CAVEMAN_SKILLS`, `SKILLS_SRC`, `PROMPTS_SRC`, `install_prompts`, `main`).
- Produces:
  - `build_items(custom_skills, prompt_files) -> list[tuple[str, str]]` — ordered `(kind, name)` items, kinds `"skill"|"prompt"|"community"`; skill/community names are folder names, prompt names are file names (e.g. `create-sb.prompt.md`).
  - `pick_items(items) -> list[tuple[str, str]]` — interactive toggle loop; all pre-selected; number toggles, `a` toggles all on/off, empty input confirms; zero selected → `sys.exit` with message; invalid input re-prompts.
  - `install_prompts(dry_run, names=None)` — `names=None` keeps today's install-all behavior; otherwise only files whose `p.name` is in `names`.

- [ ] **Step 1: Write failing tests for build_items and pick_items**

Append to `agent-skills/test_install.py` (before the `if __name__` block):

```python
class TestBuildItems(unittest.TestCase):
    def test_orders_skills_prompts_community(self):
        items = install.build_items(
            custom_skills=["explain-logic", "soundboarding"],
            prompt_files=["create-sb.prompt.md", "explain-code.prompt.md"])
        kinds = [k for k, _ in items]
        self.assertEqual(kinds[:2], ["skill", "skill"])
        self.assertEqual(kinds[2:4], ["prompt", "prompt"])
        self.assertTrue(all(k == "community" for k in kinds[4:]))
        names = [n for _, n in items]
        for s in install.COMMUNITY_SKILLS + install.CAVEMAN_SKILLS:
            self.assertIn(s, names)


class TestPickItems(unittest.TestCase):
    ITEMS = [("skill", "explain-logic"), ("skill", "soundboarding"),
             ("prompt", "create-sb.prompt.md"), ("community", "caveman")]

    def pick(self, inputs):
        it = iter(inputs)
        with mock.patch("builtins.input", side_effect=lambda *_: next(it)):
            return install.pick_items(list(self.ITEMS))

    def test_enter_confirms_all_preselected(self):
        self.assertEqual(self.pick([""]), self.ITEMS)

    def test_number_toggles_off(self):
        result = self.pick(["2", ""])
        self.assertNotIn(("skill", "soundboarding"), result)
        self.assertEqual(len(result), 3)

    def test_toggle_twice_back_on(self):
        self.assertEqual(self.pick(["2", "2", ""]), self.ITEMS)

    def test_a_toggles_all_then_one_on(self):
        result = self.pick(["a", "3", ""])
        self.assertEqual(result, [("prompt", "create-sb.prompt.md")])

    def test_zero_selected_exits(self):
        with self.assertRaises(SystemExit):
            self.pick(["a", ""])

    def test_invalid_input_reprompts(self):
        self.assertEqual(self.pick(["zzz", "99", ""]), self.ITEMS)


class TestInstallPromptsFilter(TempDirTest):
    def test_names_filter_limits_install(self):
        prompts_src = self.tmp / "prompts"
        prompts_src.mkdir()
        (prompts_src / "a.prompt.md").write_text("a")
        (prompts_src / "b.prompt.md").write_text("b")
        user_dir = self.tmp / "Code" / "User"
        user_dir.mkdir(parents=True)
        with mock.patch("install.PROMPTS_SRC", prompts_src), \
             mock.patch("install.vscode_prompts_dir",
                        return_value=user_dir / "prompts"):
            results = install.install_prompts(dry_run=False,
                                              names={"b.prompt.md"})
        self.assertEqual([r[1] for r in results], ["prompt:b.prompt"])
        self.assertFalse((user_dir / "prompts" / "a.prompt.md").exists())
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd agent-skills && python3 -m unittest test_install -v 2>&1 | tail -5`
Expected: FAIL/ERROR — `AttributeError: module 'install' has no attribute 'build_items'` (and `pick_items`, and `TypeError` for the `names` kwarg).

- [ ] **Step 3: Implement build_items, pick_items, install_prompts filter**

In `agent-skills/install.py`, add after `pick_targets`:

```python
def build_items(custom_skills, prompt_files):
    """Ordered installable items as (kind, name): custom skills, prompt
    files, then community skills."""
    items = [("skill", n) for n in custom_skills]
    items += [("prompt", n) for n in prompt_files]
    items += [("community", n) for n in COMMUNITY_SKILLS + CAVEMAN_SKILLS]
    return items


def pick_items(items):
    """Interactive toggle menu over (kind, name) items. All pre-selected.
    Number toggles one, 'a' toggles all, empty input confirms. Exits when
    nothing is selected."""
    selected = [True] * len(items)
    while True:
        print("\nSelect items to install:")
        for i, ((kind, name), on) in enumerate(zip(items, selected), 1):
            print(f"  [{'x' if on else ' '}] {i:2}) {kind:9} {name}")
        raw = input("Toggle number, 'a' = all, enter = confirm: ").strip().lower()
        if raw == "":
            chosen = [item for item, on in zip(items, selected) if on]
            if not chosen:
                sys.exit("Nothing selected — exiting without changes.")
            return chosen
        if raw == "a":
            value = not all(selected)
            selected = [value] * len(items)
        elif raw.isdigit() and 1 <= int(raw) <= len(items):
            idx = int(raw) - 1
            selected[idx] = not selected[idx]
        else:
            print("Invalid input.")
```

Change `install_prompts` signature and loop:

```python
def install_prompts(dry_run, names=None):
    """Copy prompts/*.prompt.md into the VS Code user prompts dir.
    names: optional set of file names to install; None = all."""
```

and inside the loop, first line:

```python
    for p in sorted(PROMPTS_SRC.glob("*.prompt.md")):
        if names is not None and p.name not in names:
            continue
```

- [ ] **Step 4: Wire selection into main()**

In `main()`, replace the block from `targets = pick_targets(args.target)` through the `community_src`/`caveman_src` setup with:

```python
    interactive = args.target is None
    targets = pick_targets(args.target)
    custom = sorted(p for p in SKILLS_SRC.iterdir() if p.is_dir())
    if not custom:
        sys.exit(f"No skills found in {SKILLS_SRC}")
    prompt_files = sorted(p.name for p in PROMPTS_SRC.glob("*.prompt.md"))

    if interactive:
        chosen = pick_items(build_items([p.name for p in custom],
                                        prompt_files))
        sel_skills = {n for k, n in chosen if k == "skill"}
        sel_prompts = {n for k, n in chosen if k == "prompt"}
        sel_community = {n for k, n in chosen if k == "community"}
        custom = [p for p in custom if p.name in sel_skills]
    else:
        sel_prompts = None
        sel_community = set(COMMUNITY_SKILLS + CAVEMAN_SKILLS)

    community_src = None
    caveman_src = None
    if args.skills_only:
        log("--skills-only: skipping community and caveman skills")
    elif not sel_community:
        log("no community skills selected — skipping fetch")
    else:
        if sel_community & set(COMMUNITY_SKILLS):
            cache = update_community_cache(args.dry_run)
            if cache:
                community_src = cache / "skills"
        if sel_community & set(CAVEMAN_SKILLS):
            cave = update_caveman_cache(args.dry_run)
            if cave:
                caveman_src = cave / "skills"
```

In the per-target loop, filter community names and pass the prompt selection:

```python
        for src_root, names in ((community_src, COMMUNITY_SKILLS),
                                (caveman_src, CAVEMAN_SKILLS)):
            if not src_root:
                continue
            for name in names:
                if name not in sel_community:
                    continue
```

and:

```python
        if target == "copilot":
            results.extend(install_prompts(args.dry_run, names=sel_prompts))
```

Also update the module docstring usage line `python3 install.py                # interactive target menu` to `python3 install.py                # interactive: pick target + items`.

- [ ] **Step 5: Run full test suite**

Run: `cd agent-skills && python3 -m unittest test_install -v 2>&1 | tail -3`
Expected: `OK`, all tests pass (existing + new).

- [ ] **Step 6: Manual dry-run check (flag path unchanged)**

Run: `cd agent-skills && python3 install.py --target claude --dry-run --skills-only`
Expected: no picker prompt; summary lists `explain-logic` and `soundboarding`, both `linked`.

- [ ] **Step 7: Commit**

```bash
git add agent-skills/install.py agent-skills/test_install.py
git commit -m "feat(agent-skills): interactive per-item selection in install.py"
```

---

### Task 5: End-to-end verification

**Files:**
- None created; verification only.

**Interfaces:**
- Consumes: everything above.
- Produces: evidence for completion claim.

- [ ] **Step 1: Full test suite**

Run: `cd agent-skills && python3 -m unittest test_install -v 2>&1 | tail -3`
Expected: `OK`.

- [ ] **Step 2: Interactive picker smoke test**

Run: `cd agent-skills && printf '2\na\n1\n\n' | python3 install.py --dry-run 2>&1 | tail -20`
(Inputs: target=claude, toggle all off, toggle item 1 on, confirm.)
Expected: picker renders with `[x]`/`[ ]` marks; summary shows only `explain-logic` planned.

- [ ] **Step 3: Real install to Claude**

Run: `cd agent-skills && python3 install.py --target claude --skills-only`
Expected: `soundboarding` `linked` (new), `explain-logic` `already linked`; `ls -la ~/.claude/skills | grep soundboarding` shows the symlink.

- [ ] **Step 4: Working tree clean**

Run: `git status --porcelain`
Expected: empty.
