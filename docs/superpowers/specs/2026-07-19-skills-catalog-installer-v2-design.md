# Skills Catalog + Installer v2 — Design

Date: 2026-07-19
Status: approved (brainstorming session)

## Goal

One catalog page documenting every agent-skill source and every custom
skill (with its chain), an accurate record of what is installed where,
and an installer that can show installed state, install selectively
(custom vs community, Claude vs Copilot), uninstall, and warn on
conflicts.

## Scope

Three deliverables:

1. Update `~/Dev/second-brain/1-Notes/Agent Skills Catalog.md`.
2. Fix the one live conflict (caveman duplicated on Claude).
3. Extend `agent-skills/install.py` (+ `test_install.py`, README).

Out of scope: external skill managers (skills-manage, aas), installing
new cherry-pick skills now, running anything on the work VDI.

## Current state (verified 2026-07-19, Mac)

- `~/.claude/skills/`: community copies — code-tour, context-map,
  acquire-codebase-knowledge, architecture-blueprint-generator,
  add-educational-comments, **caveman (duplicate, remove)**; custom
  symlinks — explain-logic, soundboarding, interview-prep,
  investigate-issue.
- `~/.copilot/skills/`: same set as copies, plus
  debugging-and-error-recovery (correct: Copilot-only).
- Claude plugins enabled: superpowers, caveman, skill-creator,
  code-simplifier, claude-md-management, claude-code-setup. Disabled:
  vercel, supabase, frontend-design.

## 1. Catalog note update

File: `/Users/roj/Dev/second-brain/1-Notes/Agent Skills Catalog.md`.

### My custom skills section

One entry per skill using the note's own template plus **Lives at:**
and **Chains:** lines.

| Skill | Chain |
|---|---|
| explain-logic | context-map → acquire-codebase-knowledge → explain-logic → code-tour (optional); caveman when terse output asked |
| investigate-issue | context-map → explain-logic (when failing logic unclear) → debugging-and-error-recovery (Copilot) / superpowers:systematic-debugging (Claude); helpers optional, inline fallback for every step |
| soundboarding | two flows: create-SB (story → SB doc) and implement-SB (SB doc → tasks with review stops); chained or standalone |
| interview-prep | standalone; bundled calibration references |

Invocation column for all four: auto-trigger on Claude, `/prompt`
commands on Copilot (`/explain-code`, `/create-sb`, `/implement-sb`,
`/create-implement-sb`, explain-and-review).

### Current install state section

New section: table per machine (Mac/Claude, Mac/Copilot, work VDI
Windows/Copilot) listing installed skills with kind
(custom/community/plugin) and install mechanism (symlink/copy/plugin).
Date-stamped; refreshed manually or from `install.py --status` output.
Work VDI row marked unverified (memory: Copilot VDI install
unverified).

### Other edits

- Quick reference table: add row for the `agent-skills` custom repo.
- Each existing entry gets an explicit verdict tag: **installed**,
  **cherry-pick via installer**, or **skip**.
- Note the caveman-on-Claude rule: plugin wins, installer never puts
  caveman into `~/.claude/skills/`.

## 2. Conflict fix

Delete `~/.claude/skills/caveman/` (copy). Claude keeps the caveman
plugin (auto-update, hooks, cavecrew agents). Copilot keeps its copy —
no plugin system there. No other removals: the five community skills
don't collide with superpowers process skills, and
debugging-and-error-recovery is already Copilot-only.

## 3. Installer v2

Single stdlib-only `install.py`, Python ≥ 3.8, flag-style CLI
(back-compat: `--target`, `--dry-run`, `--skills-only`, bare
interactive run all keep working; dotfiles root
`./install.py install agent-skills` unchanged).

### Source registry

Replace the three hardcoded source constants with one registry list;
each entry:

```python
{
  "label": "addyosmani/agent-skills",
  "url": "https://github.com/addyosmani/agent-skills.git",
  "branch": "main",
  "cache": "addy-agent-skills",
  "skills": ["debugging-and-error-recovery", ...],
  "targets": {"debugging-and-error-recovery": ["copilot"], ...},
  "default": True,   # pre-selected in picker / included in flag runs
}
```

Sources:

| Source | Skills | Targets | Default |
|---|---|---|---|
| github/awesome-copilot | code-tour, acquire-codebase-knowledge, context-map, architecture-blueprint-generator, add-educational-comments | both | yes |
| juliusbrussee/caveman | caveman | **copilot only** | yes |
| addyosmani/agent-skills | debugging-and-error-recovery | copilot only | yes |
| addyosmani/agent-skills | observability-and-instrumentation, ci-cd, security-and-hardening, deprecation-and-migration | both | **no** (cherry-pick) |
| anthropics/skills | document skills (pdf, docx, pptx, xlsx) | both | **no** (cherry-pick) |

mattpocock/skills: excluded — slash-command/plugin oriented; install
as a Claude plugin manually if ever wanted.

Exact addyosmani/anthropics skill folder names verified against the
upstream repos at implementation time; registry adjusted to what
exists.

### `--status`

Prints per target (claude, copilot):

- each installed skill: name, kind (custom / community / unknown),
  mechanism (symlink / copy), source repo when known;
- conflict warnings:
  - skill dir also provided by an enabled Claude plugin (read
    `~/.claude/plugins/config.json` for enabled plugins, scan plugin
    cache `skills/` dirs for name collisions);
  - broken symlinks;
  - skills in a target the registry marks as wrong-target (e.g.
    caveman under `~/.claude/skills`).

Read-only; works without network.

### `--uninstall NAME[,NAME...]`

Removes named skill dirs/symlinks from selected target(s)
(`--target` required or interactive prompt). Unknown names (not
custom, not in registry) refuse unless `--force`. `--dry-run`
honored. Prompt files uninstall via `prompt:<name>`.

### Interactive picker

- Groups: custom skills, prompts, community (per source).
- Tags per item: `[installed]`, `[update]` (content differs),
  `[conflict]` (status-check hit), cherry-picks default unchecked.
- Existing toggle UX unchanged (number toggles, `a` all, enter
  confirm).

### Tests

`test_install.py` extended: registry target filtering (caveman never
lands in claude dest), status classification (custom vs community vs
unknown, plugin collision detection with a faked plugin cache),
uninstall (known name removed, unknown refused, `--force`,
`--dry-run`), picker tagging. Existing tests keep passing.

### README

Update: new flags, cherry-pick sources, caveman-on-Claude rule, VDI
section gains `--status` step.

## Error handling

- Network failure on fetch: existing cache-fallback + ZIP hint per
  source (unchanged pattern).
- Missing plugin config/cache: status skips plugin-collision check
  with a warning, never crashes.
- Uninstall of symlink removes the link only, never the repo source.

## Success criteria

- `install.py --status` on Mac shows current state and zero conflicts
  after caveman copy removed.
- `install.py --target claude` never installs caveman to Claude.
- Cherry-pick sources installable by explicit selection only.
- Catalog note has filled custom-skills section, install-state table,
  verdict tags.
- All unit tests pass.
