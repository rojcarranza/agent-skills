# Soundboarding Skill Migration + Interactive Installer — Design

Date: 2026-07-17
Status: approved

## Goal

Migrate the soundboarding (SB) Copilot skill from `~/Dev/sb-skill` into
`agent-skills/`, make it usable by both Copilot and Claude Code, add
per-skill usage docs, and make `install.py` interactively selectable
per item.

## Background

`~/Dev/sb-skill` holds three GitHub Copilot prompt files that automate
the soundboarding workflow at work: turn a user story (`LISA-<id>.md`)
into an SB document with codebase-investigated core tasks
(`/create-sb`), execute the SB task by task with review stops
(`/implement-sb`), or both chained (`/create-implement-sb`). Prompts
hardcode work VDI paths (`SOUNDBOARD_DIR=/c/dev/projects/wr/soundboard`,
`PROJECTS_ROOT=/c/dev/projects`) and require `SB-template.md` at
runtime. `agent-skills/` already has the target pattern:
`skills/<name>/SKILL.md` (cross-platform) + `prompts/*.prompt.md`
(Copilot/VS Code), installed by `install.py`.

## Decisions (user-confirmed)

1. **Format:** prompts + SKILL.md (approach A, self-contained pair).
   Prompts stay standalone because work VDI copies them alone into the
   VS Code prompts dir; SKILL.md carries the same workflow for Claude
   Code / IntelliJ. Duplication accepted.
2. **Paths:** keep work paths as documented defaults; add one line per
   prompt saying the user can override `SOUNDBOARD_DIR` /
   `PROJECTS_ROOT` in their message.
3. **Assets:** ship `SB-template.md` plus one example pair
   (`LISA-110278.md` story → `sb-LISA-110278.md` SB) inside
   `skills/soundboarding/`.
4. **Old repo:** `~/Dev/sb-skill` untouched.
5. **Interactive install:** item picker covers custom skills, prompt
   files, and community skills.
6. **Usage docs:** `USAGE.md` per custom skill + `docs/community-skills.md`
   for community ones; README links all.

## Layout

```
agent-skills/
  prompts/
    create-sb.prompt.md            # near-verbatim + override note
    implement-sb.prompt.md         # near-verbatim + override note
    create-implement-sb.prompt.md  # near-verbatim + override note
    explain-code.prompt.md         # existing
    explain-and-review.prompt.md   # existing
  skills/
    explain-logic/
      SKILL.md                     # existing
      USAGE.md                     # new
    soundboarding/
      SKILL.md                     # new, cross-platform workflow
      USAGE.md                     # new
      SB-template.md               # copied from sb-skill examples
      examples/
        LISA-110278.md             # story input
        sb-LISA-110278.md          # generated SB output
  docs/
    community-skills.md            # new: purpose + example prompts per
                                   # community skill
  install.py                       # interactive item picker added
  test_install.py                  # selection tests added
  README.md                        # updated layout + links to usage docs
```

## Component: migrated prompts

Copied near-verbatim from `sb-skill/prompts/`. Only change: the
Configuration section of each gains one line —

> Override SOUNDBOARD_DIR or PROJECTS_ROOT by stating new paths in your
> message; these are defaults, not requirements.

All hard rules preserved verbatim: truthfulness (unverified claims go
to Questions), template fidelity (read template fresh, stop if
missing), no git operations, per-task review stops, Testing table
updates.

## Component: skills/soundboarding/SKILL.md

Frontmatter `name: soundboarding`, description triggering on:
"soundboarding", "SB document", "create an SB", "implement SB-…",
story-file-to-SB phrasing. Body mirrors the three flows (create,
implement, create+implement) with the same hard rules, adapted:

- TEMPLATE resolves to the bundled `SB-template.md` next to SKILL.md
  first; falls back to `SOUNDBOARD_DIR/SB-template.md`.
- `SOUNDBOARD_DIR` / `PROJECTS_ROOT` documented as overridable
  defaults (same values as the prompts).
- Platform-neutral wording (no VS Code-specific references).

## Component: usage docs

`skills/<name>/USAGE.md` (explain-logic, soundboarding): what the
skill does, when to use it, copy-paste examples for VS Code slash
commands, IntelliJ Copilot phrasing, and Claude Code phrasing.
Soundboarding's includes a worked story→SB→implement walkthrough
referencing the bundled example files.

`docs/community-skills.md`: one short section per community-fetched
skill (code-tour, acquire-codebase-knowledge, context-map,
architecture-blueprint-generator, add-educational-comments, caveman):
purpose + 1–2 example prompts.

README: usage details move to links into these docs; layout section
updated with soundboarding entries.

USAGE.md files ride along with skill folder install (symlink/copy);
no installer awareness needed.

## Component: interactive installer

`install.py`, stdlib only, plain input loops (works in Git Bash):

- **No CLI flags:** target menu (existing) → new item picker. Numbered
  list of every installable item: each custom skill, each prompt file,
  each community skill. Toggle by number, `a` = all, empty enter =
  confirm. All items pre-selected by default.
- **Any flags given** (`--target`, `--skills-only`, `--dry-run` with
  `--target`): current non-interactive install-everything behavior,
  unchanged — `setup.sh` and scripted VDI installs keep working.
- `--dry-run` respects interactive selection when no target flag given.
- Selection filters which skills are symlinked/copied, which prompts
  are installed, and which community skills are fetched.

## Error handling

- Prompt/skill runtime errors unchanged from source (STOP-and-ask
  rules inside the prompt text).
- Picker: invalid input re-prompts; empty selection = confirm current
  state; zero items selected = warn and exit without changes.
- Community fetch failures: existing warn-and-continue behavior kept,
  applied only to selected items.

## Testing

- `test_install.py`: new tests for selection parsing (toggle, `a`,
  confirm, invalid input, zero-selection exit) and for filtering logic
  (selected subset installs only those items). Existing tests must
  keep passing (flag path unchanged).
- Manual: `python3 install.py --dry-run --target claude` (unchanged
  output plus soundboarding), interactive run exercising the picker.

## Out of scope

- Changes to `~/Dev/sb-skill`.
- Any git automation inside the SB workflow.
- curses/TUI for the picker.
