# User story: Skills inventory for skills.sh community skills

## Story

**As a** maintainer of `agent-skills`
**I want** one inventory file where I list the skills.sh skills I use (for example
`vercel-labs/skills@find-skills`), and `install.py` installs them with my own skills
**so that** I stop installing third-party skills by hand on each machine, and every
machine (home Claude, work Copilot, team repos) gets the same reviewed set.

## Context (what exists today)

- `install.py` already installs community skills, but the list is **hardcoded** in the
  `SOURCES` Python constant (awesome-copilot, caveman, addy, warp, anthropics).
- Adding a skill found on skills.sh means editing Python, adding a repo URL, branch,
  cache dir, fallback URL and targets by hand.
- `docs/community-skills.md` documents them, also by hand.
- `find-skills` (from `vercel-labs/skills`) teaches the agent to run
  `npx skills find <query>` and `npx skills add <owner/repo@skill>`. It does discovery,
  not inventory: whatever it installs lives outside this repo and is not reproducible.

## Acceptance criteria

**AC1: Inventory file is the source of truth**
- Given a `skills-inventory.json` (or `.toml`) at the repo root
- When I add an entry `{ "source": "vercel-labs/skills", "skill": "find-skills", "targets": ["claude", "copilot"], "default": true, "ref": "<commit-sha>" }`
- Then `install.py --list` shows `find-skills` under community skills
- And `SOURCES` in `install.py` is built from this file (no skill names hardcoded in Python)

**AC2: Add from a skills.sh URL**
- Given a URL like `https://www.skills.sh/vercel-labs/skills/find-skills`
- When I run `python3 install.py --add-inventory <url>`
- Then the entry is appended with `owner`, `repo`, `skill` parsed from the URL and the current upstream commit pinned as `ref`
- And it also accepts the CLI form `vercel-labs/skills@find-skills`

**AC3: Install, update, status work as today**
- Flag runs install all `default: true` inventory entries; others stay cherry-picks in the picker
- `--status` reports each inventory skill as installed, update, or conflict
- `--skills-only` still skips them (offline/proxy case)
- `--repo .` seeds only entries whose targets include `repo`

**AC4: Pinned and reviewed, not "latest from the internet"**
- Every entry has a `ref` (commit SHA); install fetches that ref only
- `python3 install.py --check-inventory-updates` lists entries whose upstream moved, without installing
- Bumping a `ref` is a normal commit, so the change is reviewable in a PR

**AC5: Tests and docs**
- `test_install.py` covers: parsing the file, URL parsing, unknown/duplicate entries, missing `ref` fails
- `docs/community-skills.md` gets a section per inventory entry (test fails if one is missing, like the marketplace check)
- README "Install" section mentions the inventory in one line

**AC6: find-skills is the first entry**
- `find-skills` is in the inventory, `default: true`, targets claude and copilot
- Its `npx skills add ... -g -y` step is documented as discovery only: to keep a skill, add it to the inventory (AC2)

**AC7: Existing skills point at find-skills when they hit a gap (Option A)**
- Given `roj-investigate-issue` or `roj-soundboarding` is working on a stack it has no loaded rules for (for example Terraform, Rust)
- When the skill notices the gap
- Then it suggests one line: `npx skills find <stack>`, and to keep a result, add it to the inventory (AC2)
- And it never installs anything itself; it only suggests
- And when `find-skills` is not installed, the skill still works (inline fallback, same as other community chains)
- And `docs/community-skills.md` lists both skills under "chains to" for `find-skills`

**AC8: One command gets everything installed to latest**
- When I run `python3 install.py --update`
- Then it warns if this agent-skills checkout is behind its upstream branch (never pulls)
- And moves every inventory pin to the upstream tip, rewriting the file with a compare link per repo (a repo whose new commit lost one of our skills keeps its pin)
- And refreshes only the skills each target already has, upgrading externals; nothing new is installed

**AC9: Custom skills' dependencies stay in the inventory**
- A test scans every custom skill for the outside skills it names and fails unless each is installable (inventory, external, custom, or a listed Claude plugin)

## Decision log

| Option | Decision |
| --- | --- |
| A. Gap hint in `roj-investigate-issue` and `roj-soundboarding` | **Chosen**, see AC7 |
| B. New `roj-curate-skills` skill that writes into the inventory | Not now; revisit if "find, then add to inventory" repeats often |
| C. No integration | Rejected |
| Migration of hardcoded `SOURCES` | Done: every community skill is an inventory entry |
| `--update` and pins | Bumps and records pins in the file (reviewable diff), not "latest on this machine only" |
| `--update` and this checkout | Warn only; never pulls, so a dotfiles-pinned checkout stays put |

## Out of scope

- Mirroring or vendoring third-party skill files into `skills/`
- Auto-installing whatever `npx skills find` returns
- Scraping skills.sh rankings (the site is a UI over GitHub repos; we fetch from GitHub)
- Claude plugins (superpowers, caveman on Claude): not skills.sh skills, so not in the inventory

## Risks and trade-offs

- **Context cost:** every installed skill's description loads into every session. Keep `default: false` unless a custom skill depends on it.
- **Supply chain:** third-party SKILL.md files are instructions the agent follows. Pinning `ref` plus PR review of bumps is the guard.
- **JSON vs keep Python:** moving `SOURCES` to a data file touches tested code paths. Lower-risk path: keep `SOURCES` for existing entries and merge inventory entries into it at load time, then migrate later.

## Tasks

1. Define inventory schema and add `skills-inventory.json` with `find-skills`
2. Load inventory into `SOURCES` in `install.py` (group entries by `owner/repo` so one sparse clone serves several skills)
3. Add `--add-inventory <url|owner/repo@skill>` and `--check-inventory-updates`
4. Tests in `test_install.py`; doc-coverage test for `docs/community-skills.md`
5. Docs: `docs/installer.md`, `docs/community-skills.md`, README one-liner
6. AC7: add the gap hint to `roj-investigate-issue` and `roj-soundboarding` SKILL.md files, with inline fallback
7. Move the hardcoded `SOURCES` entries into `skills-inventory.json` (completes AC1)
8. AC8: `--update`
9. AC9: dependency test; add the `<distro>-linux-triage` skills it found missing

**Estimate:** 3 to 5 points for tasks 1 to 6; 3 points for tasks 7 to 9.
