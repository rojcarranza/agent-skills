# Agent Skills Collection + Cross-Platform Installer — Design

Date: 2026-07-17
Status: Approved

## Problem

A custom Copilot skill (`explain-logic`) exists as a loose draft in
`~/Downloads/copilot-explain-code-skill` with a bash-only, Copilot-only
installer. Goals:

1. Refine `explain-logic` — its purpose is helping the user understand code
   and logic, especially changes pushed to a feature branch.
2. Reduce token usage by porting caveman-style compression into a form
   Copilot can use (the caveman plugin is Claude-Code-only, hook-based).
3. Give all current and future custom skills one organized, versioned home.
4. Replace the bash installer with one cross-platform Python script that
   installs skills globally for GitHub Copilot, Claude Code, or both.

## Decisions made

- Only `explain-logic` exists today; structure must hold future skills.
- Caveman compression becomes a **standalone portable skill**
  (`caveman-mode`), referenced by `explain-logic` — not baked in.
- Everything lives **inside the dotfiles repo** at
  `~/Dev/.dotfiles/agent-skills/`.
- **Python-only installer** (`install.py`, stdlib, Python >= 3.8);
  `install-skills.sh` is deleted.
- Claude installs use **per-skill symlinks** (dotfiles convention: edit
  repo, live everywhere); Copilot installs use copies. Windows falls back
  to copy if symlink fails.

## Layout

```
~/Dev/.dotfiles/agent-skills/
├── install.py
├── skills/
│   ├── explain-logic/SKILL.md      # refined + compressed
│   └── caveman-mode/SKILL.md       # new, portable caveman port
├── prompts/                        # Copilot/VS Code only
│   ├── explain-code.prompt.md
│   └── explain-and-review.prompt.md
└── README.md
```

One SKILL.md format serves both platforms — Copilot and Claude read the
same `name`/`description` frontmatter.

## install.py

- `--target copilot|claude|both`; no flag → interactive numbered menu.
- `--skills-only`: skip community-skill fetch (offline/proxy case).
- `--dry-run`: print planned actions, write nothing (for VDI sanity check).
- **Copilot target**: copy `skills/*` → `~/.copilot/skills/`; copy
  `prompts/*.prompt.md` → VS Code user prompts dir. Detect prompts dir:
  Windows `%APPDATA%/Code/User/prompts`, macOS
  `~/Library/Application Support/Code/User/prompts`, Linux
  `~/.config/Code/User/prompts`.
- **Claude target**: symlink `~/.claude/skills/<name>` → repo skill dir,
  one link per skill (community skills coexist as copies). Skip prompt
  files — Claude triggers on skill descriptions.
- **Community skills** — `code-tour`, `acquire-codebase-knowledge`,
  `context-map`, `architecture-blueprint-generator`,
  `add-educational-comments` — sparse-cloned from
  `github/awesome-copilot` into `~/.agent-skills-cache/`, updated on
  re-run, copied to each chosen target.
- Idempotent; per-skill status report: installed (new) / updated /
  already up to date.
- Exit summary: what landed where + verify command per platform
  (Copilot: `/skills list`; Claude: ask "what skills are available?").

### Error handling

- Clone blocked (proxy): warn, continue installing custom skills, print
  ZIP-download fallback URL and target path.
- VS Code user dir missing: warn, print per-repo `.github/prompts/`
  alternative.
- Broken existing symlink at destination: replace.
- Real directory where a symlink is wanted: move to `<name>.bak`, then
  link.
- Symlink creation fails (Windows without developer mode): fall back to
  copy, note that re-running install.py refreshes copies.

## explain-logic refinements

- Compress body caveman-style from ~105 to ~60 lines. All substance
  preserved: scope detection (feature-branch diff via
  `git diff $(git merge-base ...)...HEAD`, PR via gh CLI or GitHub MCP,
  file/function), context gathering (surrounding code, callers/callees,
  tests, commit messages, CI/config files), the
  Concept → Code flow → Why → Gotchas structure, depth calibration,
  the five language lenses (Java / Python / Go / shell / Bamboo API),
  explain-and-review mode, and the rules section.
- `description:` frontmatter kept verbatim — trigger accuracy depends
  on it.
- New rule line: "User asks terse/brief/save tokens: apply caveman-mode
  skill if installed."
- Companion-skills section becomes a compact table — one line per skill,
  "use if installed", chaining order preserved:
  context-map → acquire-codebase-knowledge → explain-logic →
  code-tour (optional persist).
- Both `.prompt.md` files updated only if the skill's structure text
  changes; behavior identical.

## caveman-mode skill (new)

Portable port of the caveman plugin's "full" level as a plain SKILL.md —
no hooks, works in Copilot and Claude:

- Triggers: "terse", "brief", "save tokens", "caveman mode",
  "less tokens".
- Rules: drop articles/filler/pleasantries/hedging; sentence fragments
  OK; short synonyms; never invent abbreviations (tokenizer saves
  nothing); technical terms, code, API names, CLI commands, and exact
  error strings verbatim.
- Persistence: stays active for the session until "normal mode" /
  "stop caveman".
- Auto-clarity exceptions (write normal): security warnings,
  irreversible-action confirmations, multi-step sequences where
  compression risks misreading.
- Boundary: code, commit messages, PR descriptions, and docs are always
  written normal.

## Testing

- `install.py --target claude` run on this Mac: verify symlinks resolve,
  skills trigger in a fresh Claude Code session.
- `install.py --dry-run --target copilot` on the work VDI before a real
  run; Copilot behavior verified there by the user (Windows not testable
  from this machine).
- Re-run installer twice: second run must report "already up to date"
  for everything (idempotency check).

## Out of scope

- Per-repo `.github/skills/` team distribution (documented in README as
  a manual copy, not automated).
- Porting caveman "lite"/"ultra"/"wenyan" levels — full only.
- Any changes to community skills' content.
