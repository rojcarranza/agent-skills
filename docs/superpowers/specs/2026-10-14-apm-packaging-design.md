# APM packaging — design

Date: 2026-10-14
Status: approved; revision 2 (CLI reference findings, platforms)

## Goal

As Roj, using both Claude Code and GitHub Copilot, I want every piece of AI
content I install — my skills, the community skills they chain to, my
personal instructions and my MCP servers — declared in one
[APM](https://microsoft.github.io/apm/) manifest in this repo, so that one
command sets up either agent on any machine and a version bump is one
reviewed diff.

`agent-skills` becomes the "whole AI setup" repo. APM owns the content;
`install.py` shrinks to the things APM cannot do.

## What we know about APM (from its docs, 2026-10-14)

- `apm.yml` declares `dependencies.apm` (git packages, subpaths, refs,
  per-dependency `targets`) and `dependencies.mcp` (registry names or
  self-defined servers). `apm.lock.yaml` pins resolved commits and
  content hashes; for `-g` it lives in `~/.apm/`.
- A subpath dependency (`owner/repo/path/to/skill#ref`) installs one skill
  folder from a repo with no `apm.yml` — the same form as
  `anthropics/skills/skills/frontend-design`.
- `apm install -g` reads `~/.apm/apm.yml` and deploys to user scope.
  MCP at user scope is documented for Claude Code and Copilot CLI; skills
  and instructions are documented in principle only.
- Claude user scope: skills in `~/.claude/skills/<name>/`, instructions as
  rules. Copilot user scope: skills in `~/.agents/skills/<name>/` (not
  `~/.copilot/skills/`), instructions in `~/.copilot/instructions/`.
- "Symlinked skill destinations remain rejected" — a skill folder that is
  already a symlink (what `install.py` creates today) can block an install.
- With `-g` the source root is `$HOME`: relative paths in
  `~/.apm/apm.yml` resolve against `~/.apm`, not against this repo, so a
  symlinked or copied manifest cannot use `./skills/...`.
- Local path dependencies accept `./path`, `/abs/path` and `~/path`.
- `apm update` rewrites the manifest it reads; `apm outdated -g` only
  reports. `apm prune` has no `-g`.
- Hooks and agents at user scope are not documented.
- Install: `brew install apm`, `curl -sSL https://aka.ms/apm-unix | sh`,
  `python3 -m pip install apm-cli` (Python 3.10+), or on Windows
  `winget install --id Microsoft.APM --exact --source winget`.

Every "documented in principle" point is verified in Step 0 before code.

## Step 0 — throwaway check (no PR)

In a scratch `HOME`, with `apm` installed, run `apm install -g` on a cut-down
manifest: one local skill (`./skills/roj-explain-logic`), one community
subpath skill (`code-tour`), one copilot-only skill (`caveman`), the
instructions file, and the GitHub MCP server. Record, for both targets:

1. where each item lands;
2. whether a pre-existing symlinked `~/.claude/skills/<name>` blocks it;
3. whether `targets: [copilot]` keeps `caveman` out of Claude;
4. whether a local path dependency is copied or linked, and whether an edit
   in `skills/` shows up without re-running install;
5. **package wiring (W2, the default):** a `~/.apm/apm.yml` whose only
   dependency is the absolute path of this repo installs the repo's own
   `apm.yml` dependencies transitively — `./skills/...` resolved against
   the repo, community subpaths, MCP — and deploys the repo's
   `.apm/instructions/`;
6. commenting a dependency out of the repo `apm.yml` and re-running
   `apm install -g` removes what it deployed;
7. the registry names of the GitHub and Playwright MCP servers.

If W2 fails item 5, use **render wiring (W1)**: `install.py` writes
`~/.apm/apm.yml` as a copy of the repo manifest with every `./` path
rewritten to an absolute path into the repo, and the instructions file
listed as a local file dependency. Everything else in this spec holds for
either wiring.

Outcomes:

- All pass → build Step 1 as written.
- A single item fails → amend this spec for that item before planning.
- User-scope skills fail outright → stop; fall back to approach B (APM for
  MCP and instructions only, `install.py` keeps skills) with a new spec.

Findings go into the PR description of Step 1. Nothing from Step 0 is kept.

## Step 1 — agent-skills change

### Manifest

New `apm.yml` at the repo root — the repo's package manifest. No lockfile
is committed: the user-scope `apm.lock.yaml` lives in `~/.apm/` and holds
machine-specific local paths; reproducibility comes from the full-SHA
refs in `apm.yml`, as it does today in `skills-inventory.json`.

```yaml
name: roj-ai-setup
version: 1.0.0
description: Roj's skills, community skills, instructions and MCP servers for Claude Code and Copilot
targets: [claude, copilot]
includes: auto
dependencies:
  apm:
    # Own skills. Local paths, so skills/ stays where npx skills and the
    # Claude plugin marketplace expect it.
    - ./skills/roj-code-review-pr
    - ./skills/roj-code-review-pr-fast
    - ./skills/roj-explain-feature-changes
    - ./skills/roj-explain-logic
    - ./skills/roj-interview-prep
    - ./skills/roj-investigate-issue
    - ./skills/roj-review-pr-comment
    - ./skills/roj-soundboarding
    - ./skills/roj-tour-codebase
    # Community defaults, same commits skills-inventory.json pins today.
    - github/awesome-copilot/skills/code-tour#7cce7cfb4b61196c36d7e8eb8475ae84b356b126
    - github/awesome-copilot/skills/acquire-codebase-knowledge#7cce7cfb4b61196c36d7e8eb8475ae84b356b126
    - github/awesome-copilot/skills/context-map#7cce7cfb4b61196c36d7e8eb8475ae84b356b126
    - warpdotdev/common-skills/.agents/skills/write-pr-description#2a03b403b4f8d42cb54b8953697737193b2e8306
    - vercel-labs/skills/skills/find-skills#87a266971d9460a3d2606075b8e91edc83325472
    # Copilot only: Claude gets these from plugins.
    - git: https://github.com/juliusbrussee/caveman.git     # Claude: caveman plugin
      path: skills/caveman
      ref: 2e08b9177c07bb7249a8a2d1a6758e5db281d002
      targets: [copilot]
    - git: https://github.com/addyosmani/agent-skills.git   # Claude: superpowers:systematic-debugging
      path: skills/debugging-and-error-recovery
      ref: 1401c8b8030e023baeebb31781a6653fe8e93026
      targets: [copilot]
    # Optional — uncomment and re-run install.py:
    # - github/awesome-copilot/skills/architecture-blueprint-generator#7cce7cf...
    # - github/awesome-copilot/skills/add-educational-comments#7cce7cf...
    # - github/awesome-copilot/skills/{arch,centos,debian,fedora}-linux-triage#7cce7cf...
    # - addyosmani/agent-skills/skills/{observability-and-instrumentation,ci-cd-and-automation,security-and-hardening,deprecation-and-migration}#1401c8b...
    # - anthropics/skills/skills/{pdf,docx,pptx,xlsx}#683bc88...
  mcp:
    - io.github.github/github-mcp-server
    # Optional — only for projects with a UI to drive:
    # - microsoft/playwright-mcp   # registry name confirmed in Step 0
```

The commented optional lines are written out one per skill with full SHAs in
the real file; the brace shorthand above is only for this spec. Subpaths
(`skills/` vs repo root) are confirmed per source in Step 0 and the plan.

Rules:

- Only today's `default: true` inventory entries are live dependencies; the
  rest are commented. The interactive picker goes away.
- A copilot-only entry uses the object form with `targets: [copilot]` and a
  comment saying where Claude gets the equivalent. This replaces the
  inventory's `targets` and `note` fields.
- `context-map` stays a default for parity with today; it is already turned
  off for Claude in `~/.claude/settings.json` `skillOverrides`.
- MCP: GitHub server live, Playwright commented. `MCP_DOCKER` stays outside
  APM — it only connects while Rancher Desktop runs.

### Instructions

`.apm/instructions/personal.instructions.md` moves here from
`dotfiles/copilot/personal.instructions.md`, unchanged (`applyTo: "**"`). APM
deploys it to `~/.copilot/instructions/` and to Claude's rules. It must keep
passing the "no personal paths, ticket IDs or employer details" rule, so
`test_skills.py` scans `.apm/` too.

### Installer

`install.py` keeps its name and its main entry
`python3 install.py --target claude|copilot|both`. The run becomes:

1. **Preflight** — `apm` on `PATH`, else print the install commands above and
   exit 1. Never installs APM itself.
2. **Legacy cleanup** — remove entries the old installer made in
   `~/.claude/skills` and `~/.copilot/skills` (symlinks into this repo, or
   copies it recorded), reusing `is_ours` / `remove_legacy`. Anything not
   ours is left alone and reported. This runs before APM so a symlinked
   destination cannot block it and Copilot does not end up with each skill
   in both `~/.copilot/skills` and `~/.agents/skills`. A symlinked
   `~/.copilot/instructions/personal.instructions.md` (made by dotfiles
   today) is removed with a message so APM can write its copy; Step 2 stops
   dotfiles from recreating it.
3. **Write the user manifest** — `~/.apm/apm.yml` is generated, never
   linked: a marker comment line, `name`, `version`, and one dependency,
   this repo's absolute path in forward-slash form (`C:/Users/...` on
   Windows). The same file on every OS, so no symlink question. An
   existing `~/.apm/apm.yml` without the marker is refused unless
   `--force`; with the marker it is rewritten when it differs.
4. **`apm install -g --target <claude|copilot|claude,copilot>`**, output
   passed through; a non-zero exit is the installer's exit. On WSL a
   closing hint says Windows-side VS Code and JetBrains read
   `%USERPROFILE%`, so run `install.py` from Git Bash too for them.
5. **Externals** — graphify bootstrap and its per-target delegation,
   unchanged.

Flags:

| Flag | After |
| --- | --- |
| `--target` | kept |
| `--dry-run` | kept: prints cleanup, link and the `apm` argv; runs nothing |
| `--force` | new: replace a foreign `~/.apm/apm.yml` |
| `--status` | `apm deps list -g` plus graphify state plus leftover legacy entries |
| `--update` | `apm outdated -g`: reports newer upstream tags; bump the SHA in `apm.yml`, then re-run (a reviewed diff, as today) |
| `--upgrade` | kept (graphify) |
| `--skills-only` | kept: skips graphify (offline / proxy) |
| `--add-inventory`, `--check-inventory-updates`, `--skill`, `--list`, `--repo`, `--uninstall`, interactive picker | removed — edit `apm.yml` and re-run instead |

Deleted: `skills-inventory.json`, `SOURCES`, the inventory loader and its
validation, the sparse-clone source cache, `--repo` seeding, and their tests.
`REQUIRES` stays as data for a test only (see Testing).

Unchanged: `skills/`, `.claude-plugin/marketplace.json`, `tools/sync_shared.py`,
so `npx skills add` and `/plugin install` keep working for anyone who does
not use APM.

### README and docs

The README `## Install` section is rewritten so the APM route comes first.
Target text:

````markdown
## Install

**Everything, with APM (recommended)** — my skills, the community skills
they chain to, personal instructions and MCP servers, for Claude Code and
Copilot, from one manifest ([`apm.yml`](apm.yml)).

1. Install [APM](https://microsoft.github.io/apm/getting-started/installation/):

   ```bash
   brew install apm                        # macOS / Linux
   python3 -m pip install apm-cli          # anywhere with Python 3.10+
   winget install --id Microsoft.APM --exact --source winget   # Windows
   ```

2. Clone and install:

   ```bash
   git clone https://github.com/rojcarranza/agent-skills && cd agent-skills
   python3 install.py --target both        # or claude / copilot
   python3 install.py --status             # what is installed where
   python3 install.py --update             # which pins have newer releases
   ```

   On Windows use Git Bash and `python`; on WSL run it inside WSL, and
   again from Git Bash for Windows-side VS Code and JetBrains.
   `install.py` writes `~/.apm/apm.yml` pointing at this clone, runs `apm install -g`,
   and installs `graphify` (a CLI APM cannot package).

To add or drop a skill or MCP server, edit `apm.yml` and re-run
`install.py`. `install.py --update` lists pins with newer upstream
releases; bump the SHA in `apm.yml` and re-run.

**Only some skills, with Node.js** — `npx skills add rojcarranza/agent-skills`
(interactive), or `-s <skill> -a claude-code github-copilot -g`.

**Claude Code plugin** — `/plugin marketplace add rojcarranza/agent-skills`,
then `/plugin install roj-skills@roj-agent-skills`.

Use one route per machine — `install.py --status` flags duplicates.

**In a team repository** — add an `apm.yml` to that repo listing the skills
it needs, e.g. `rojcarranza/agent-skills/skills/roj-code-review-pr#<commit>` (pin a commit), and
run `apm install`. Commit `apm.yml` and `apm.lock.yaml`; teammates run
`apm install` after cloning.
````

Other docs:

- `README.md` repository layout: replace the `skills-inventory.json` line
  with `apm.yml` and `.apm/instructions/`.
- `docs/installer.md`: rewrite "Flags and modes", replace "Skills inventory"
  and "Updating everything" with an "APM manifest" section (adding,
  pinning, optional entries, `apm update`), keep the externals, Windows VDI
  and JetBrains sections, adjusted for the APM step and Copilot's
  `~/.agents/skills` path.
- `docs/community-skills.md`: point "how to install" at `apm.yml`; the
  per-skill descriptions stay.

### Platforms

Supported: macOS, Linux, Windows Git Bash, WSL Ubuntu. Python >= 3.8,
standard library only (APM's own pip install needs 3.10; brew, winget and
the curl installer do not).

| | macOS / Linux | Windows Git Bash | WSL Ubuntu |
| --- | --- | --- | --- |
| Run as | `python3 install.py` | `python install.py` (Windows Python) | `python3 install.py` |
| Home | `$HOME` | `%USERPROFILE%` | Linux `$HOME` |
| `apm` lookup | `PATH`, `~/.local/bin` | `PATH` plus `.exe`/`.cmd` suffixes and the pip user Scripts dir (existing `find_cli`) | as Linux |
| Repo path in manifest | `/Users/...`, `/home/...` | `C:/Users/...` | `/home/...` or `/mnt/c/...` |
| Serves | Claude Code, Copilot CLI/VS Code/JetBrains | the same, Windows side | Claude Code and Copilot CLI inside WSL; Windows-side IDEs need a Git Bash run too |

Legacy cleanup on Windows handles copies, never assumes symlinks. Every
file the installer writes is UTF-8 with `\n` line endings.
CI runs the unit tests on `ubuntu-latest`, `macos-latest` and
`windows-latest` (Git Bash shell), and an `apm install -g --dry-run`
smoke job against a temporary `HOME` on all three. WSL is covered by the
Linux runs plus a manual check.

### Testing

`test_install.py` — `subprocess` calls to `apm` are mocked; no test needs
APM installed:

- preflight prints install commands and exits 1 when `apm` is missing;
- manifest link: symlink vs copy, idempotent re-run, foreign file refused,
  `--force` replaces it;
- exact `apm install -g --target …` argv for each `--target`;
- `--dry-run` runs no subprocess and writes nothing;
- legacy cleanup removes only our entries and reports others;
- `--status` and `--update` call the expected `apm` argv;
- graphify tests keep passing unchanged.

`test_skills.py` (stdlib only — `apm.yml` read with a small line parser,
no PyYAML):

- every `skills/<name>` is a live `./skills/<name>` dependency in `apm.yml`
  and in `marketplace.json`;
- every `REQUIRES` value is a live (uncommented) dependency in `apm.yml`;
- every community ref is a full 40-char SHA;
- `.apm/` passes the personal-paths / `.private-patterns` scan.

Manual, before merge, on the Mac (and on WSL Ubuntu and Git Bash when at
those machines): `python3 install.py --target both`, then
`--status`; in Claude Code and in Copilot (VS Code) confirm the skills list,
the instruction and the GitHub MCP server.

### Tracking

Issue `feat(install): manage skills, instructions and mcp through apm`,
branch `feat/apm-install`, PR starting with `Closes #<issue>`.

## Step 2 — dotfiles change (after Step 1 merges)

Own issue and PR in the dotfiles repo:

- remove `copilot/personal.instructions.md` and the `install copilot` step;
  `copilot/README.md` points at `agent-skills` (`.apm/instructions/`);
- `claude/` unchanged (settings, PR-review hook, statusline, CLAUDE.md);
- reword the `~/.claude/CLAUDE.md` graphify bullet only if the install
  command it names changes.

## Out of scope

- Hooks through APM — the PR-review hook stays in dotfiles until APM
  documents user-scope hooks.
- Claude plugins and marketplaces — stay in `~/.claude/settings.json`.
- Publishing to an APM marketplace or tagging releases for consumers beyond
  the README example.
- A Windows VDI test run — README note only.
- Moving `claude/settings.json`, statusline or global `CLAUDE.md` into APM.
