# install.py reference

`install.py` is the full installer: personal scope for Claude Code and
GitHub Copilot, repo scope for a team, community skills, CLI-installed
externals and the Windows copy fallback. Python >= 3.8, standard library
only. For a single skill in any agent, `npx skills add` is enough — see the
[README](../README.md#install).

## Flags and modes

```bash
python3 install.py --target claude    # home: symlinks into ~/.claude/skills
python3 install.py --target copilot   # work: copies into ~/.copilot/skills
python3 install.py --target both
python3 install.py                    # interactive: pick target + items
python3 install.py --status                      # what is installed where + conflicts
python3 install.py --uninstall caveman --target copilot
python3 install.py --list                        # everything installable
python3 install.py --target claude --skill roj-code-review-pr,pdf   # cherry-pick
python3 install.py --add-inventory https://skills.sh/vercel-labs/skills/find-skills
python3 install.py --check-inventory-updates     # pinned skills behind upstream
python3 install.py --update --target both        # latest of everything installed
```

Repo scope — seeds `<repo>/.github/skills`, shareable with the team:

```bash
python3 install.py --repo .                 # seed the repo you are standing in
python3 install.py --repo . --skills-only   # our skills, no third-party
python3 install.py --repo . --status        # what a project already carries
python3 install.py --repo . --uninstall roj-soundboarding
python3 install.py --target copilot --repo .   # personal + repo in one run
```

`--repo` writes copies only (never symlinks) and seeds `.github/` only —
`.claude/skills` and `.agents/skills` workspace scopes are left alone.

Flags: `--dry-run` (print planned actions), `--skills-only` (skip the
community-skill fetch — offline or behind a proxy), `--upgrade` (upgrade
external CLIs before refreshing their skills), `--force` (bypass unknown-name
checks on uninstall).

Interactive runs (no flags) show an item picker: toggle individual skills,
community skills and externals by number, `a` for all, enter to confirm.
The picker tags items as `[installed]`, `[update]`, or `[conflict]`. Flag
runs install every custom skill plus the default community set;
`--skill a,b` installs only the named skills (custom, community or
external) plus their requirements, with no picker.

Community skills are the entries of `skills-inventory.json` (see
[Skills inventory](#skills-inventory-skillssh)). Each repo is fetched at its
pinned commit into `~/.agent-skills-cache/<owner>--<repo>` and installed or
updated in place (missing = install, present = update, unchanged = up to
date):

**Default (both targets, unless noted):**
- From `github/awesome-copilot`: code-tour, acquire-codebase-knowledge,
  context-map. `architecture-blueprint-generator` and
  `add-educational-comments` are cherry-picks, not defaults — every installed
  skill's description loads into every session, and neither has a dependent.
- From `juliusbrussee/caveman`: caveman terse-output skill (Copilot only; Claude
  uses the caveman plugin). roj-explain-logic points at it for terse mode.
- From `addyosmani/agent-skills`: debugging-and-error-recovery (Copilot only;
  Claude uses superpowers:systematic-debugging). roj-investigate-issue chains it
  when present.
- From `warpdotdev/common-skills`: write-pr-description (fetched from its
  `.agents/skills/` folder). roj-explain-feature-changes uses it for the PR
  Explanation.

**Cherry-picks (interactive mode only, default unchecked):**
- From `addyosmani/agent-skills`: observability-and-instrumentation,
  ci-cd-and-automation, security-and-hardening, deprecation-and-migration.
- From `anthropics/skills`: pdf, docx, pptx, xlsx.
- From `github/awesome-copilot`: arch-, centos-, debian- and
  fedora-linux-triage. roj-investigate-issue names the matching one when a
  root cause sits on the build agent's host.

In [dotfiles](https://github.com/r0jjames/.dotfiles),
`./install.py install agent-skills` clones this repo next to the dotfiles
checkout (override with `AGENT_SKILLS_DIR`), checks out the pinned ref and
runs a flag install — custom skills, default community skills and externals —
as part of normal machine setup: Claude only on macOS/Linux, **both** Claude and Copilot on
Windows (Git Bash).

### Skill dependencies

`REQUIRES` in `install.py` lists the skills a custom skill calls. Installing
the skill installs its requirements to the same targets in every mode — flag,
interactive and `--repo`. An item unticked in the picker comes back with a
`(required by …)` log line.

| Skill | Requires |
| --- | --- |
| `roj-explain-feature-changes` | `code-tour` |

`--skills-only` cannot fetch requirements; the run ends with a warning for
each one missing. `--status` lists missing requirements per target.
`--uninstall` of a requirement that an installed skill still needs warns,
then removes it. A test fails if a `REQUIRES` key stops matching a
directory under `skills/`, so a rename cannot silently drop dependencies.

Custom skills never require each other. Files two skills share — the
review method `roj-code-review-pr-fast` and `roj-review-pr-comment` read —
are copied into each skill by `tools/sync_shared.py`, so every skill also
installs alone through `npx skills add`.

## Skills inventory (skills.sh)

`skills-inventory.json` lists community skills picked from
[skills.sh](https://skills.sh) as data instead of code. The installer merges
it into the community sources at start-up, so inventory skills behave like
any other community skill: `--list`, the picker, `--skill`, `--status`,
`--repo` and `--skills-only` all apply.

```json
{
  "skills": [
    {
      "source": "vercel-labs/skills",
      "skill": "find-skills",
      "ref": "87a266971d9460a3d2606075b8e91edc83325472",
      "targets": ["claude", "copilot"],
      "default": true
    }
  ]
}
```

| Key | Meaning |
| --- | --- |
| `source` | GitHub `owner/repo` |
| `skill` | name skills.sh lists (the `name` in its `SKILL.md`); also the installed folder name |
| `ref` | full commit SHA — the installer fetches exactly this commit |
| `targets` | any of `claude`, `copilot`, `repo` |
| `default` | `true` = installed by flag runs and pre-ticked in the picker |
| `subdir` | optional, folder holding the skill folders (default `skills`) |
| `folder` | optional, upstream folder name when it differs from `skill` |
| `note` | optional, shown when a target is skipped |

**Adding a skill.** Copy the skills.sh URL (or the `owner/repo@skill` form
`npx skills add` takes) and run `--add-inventory`. It reads the repo's tree at
the upstream tip, finds the `SKILL.md` whose folder or `name` matches —
skills.sh lists `vercel-react-best-practices`, which lives in
`skills/react-best-practices/` — and appends an entry pinned to that commit
with `default: false`, since every installed description loads into every
session. A second skill from an already-pinned repo reuses that repo's `ref`:
one repo is one sparse clone at one commit. Then review the printed
`SKILL.md` link, add a section to
[community-skills.md](community-skills.md), and commit.

**Updating.** `--check-inventory-updates` compares each pinned `ref` with the
upstream tip and prints a compare link for the ones behind; it installs
nothing. `--update` does the rest in one run (see
[Updating everything](#updating-everything)). Either way the new pins are a
diff of this file, so a new upstream version goes through review like any
other change. The tool `find-skills` itself installs with
`npx skills add -g`, outside this file — use that for a trial, the inventory
for keeps.

**Offline.** A failed fetch reuses the local cache only when it is still at
the pinned commit; a cache at another commit is skipped rather than installed.

Names may not clash: an inventory skill that matches a custom skill or an
external stops the installer with an error.

**Dependencies stay covered.** A test scans every custom skill for the
outside skills it names (chain tables, "the `x` skill", `<distro>-x`
templates) and fails unless each is installable: in the inventory, an
external, another custom skill, or a Claude plugin it lists
(`systematic-debugging` from superpowers). A new chain therefore lands with
its inventory entry.

## Updating everything

```bash
python3 install.py --update --target both    # omit --target: both personal targets
python3 install.py --update --repo .         # a team repo's .github/skills
python3 install.py --update --dry-run        # what would move, nothing written
```

One run, three steps:

1. **This checkout.** Warns when the agent-skills checkout is behind its
   upstream branch (`git pull`, then `--update` again). It never pulls: a
   dotfiles-pinned checkout stays where it is.
2. **Pins.** Moves every repo in `skills-inventory.json` to its upstream
   tip and rewrites the file, with a compare link per repo. A repo whose new
   commit no longer has one of our skills keeps its pin and says so. Review
   `git diff skills-inventory.json` and commit, so every machine gets the
   same versions.
3. **Installed skills.** Refreshes only what each target already has:
   custom skills (Claude's symlinks are already live; Copilot and repo
   copies are re-copied), inventory skills at the new pins, and externals
   with `--upgrade`. Nothing new is installed — use `--skill` or the picker
   for that.

`--update --skills-only` skips the network: pins stay, custom copies are
refreshed. Skills installed with `npx skills add` are not tracked here;
`npx skills update` refreshes those.

## External skills (installed by their own CLI)

Some skills ship with a tool rather than as a folder we can copy. Those are
listed in `EXTERNALS` in `install.py`: the installer puts the CLI on the
machine, then hands the per-target install to that CLI, so the skill is always
the upstream version and nothing is vendored here. It tries `uv tool install`,
then `pipx install`, then `python -m pip install --user` — the last one always
exists, since the installer is itself running under that interpreter. A CLI it
cannot install is a skip with instructions, never a failed run. `--skills-only`
skips externals along with community skills — both need the network.

After a `pip --user` install the executable lands in the interpreter's user
scripts dir (`%APPDATA%\Python\PythonXY\Scripts` on Windows), which the
installer finds even when the shell cannot. That case — installed but not
callable by name — is the one failure that looks like success, since the skill
invokes the CLI bare, so the run ends with the exact `export PATH` line to fix
it (`cygpath`-wrapped on Windows) and `--status` repeats it. The slash command
itself (`/graphify .`) is typed **in the agent's chat**, never in a shell.

**[`graphify`](https://github.com/Graphify-Labs/graphify)** (`graphifyy` on
PyPI) — maps a project (code, docs, PDFs, images, video) into a knowledge
graph you query instead of grepping, and writes `graphify-out/` with
`graph.html`, `GRAPH_REPORT.md` and `graph.json`. Code is parsed locally with
tree-sitter; the semantic pass over docs uses whichever agent invoked it. Run
it as `/graphify .`.

| Target | What the installer runs | Where it lands |
| --- | --- | --- |
| claude | `graphify install` | `~/.claude/skills/graphify/` (auto-picks the PowerShell variant on Windows) |
| copilot | `graphify vscode install` | `~/.copilot/skills/graphify/` — personal scope, so **VS Code and JetBrains Copilot both see it** |
| repo (`--repo P`) | the same, run inside `P` | `P/.github/skills/graphify/` + `P/.github/copilot-instructions.md` |

Copilot deliberately gets the `vscode` skill body, not the `copilot` one.
Both write the same `~/.copilot/skills/graphify/SKILL.md`, but the `copilot`
body dispatches extraction through a parallel Agent tool that neither VS Code
Copilot Chat nor JetBrains Copilot has; the `vscode` body drives the same
extraction by hand. Copilot CLI reads the same file and only loses the
parallelism.

`graphify vscode install` also writes `.github/copilot-instructions.md` next
to its working directory, so personal-scope runs happen in a scratch dir and
only `--repo` writes that file, into the repo where it belongs.

`graphify install` appends an always-on `## graphify` section to
`~/.claude/CLAUDE.md` — a symlink to `claude/CLAUDE.md` in this repo — unless
the word `graphify` already appears there. The bullet in `claude/CLAUDE.md`
is that guard: it keeps graphify skill-only (no per-session token cost) and
keeps the CLI out of a repo-managed file.

### Updating an external

Nothing about an external updates itself. Three layers move independently:

```bash
python3 install.py --target both --upgrade   # CLI + skill files, in that order
python3 install.py --repo . --upgrade        # and any per-project copies
```

`--upgrade` upgrades the package (trying `uv tool upgrade`, `pipx upgrade`,
then `pip install --user --upgrade` — whichever owns it; the others fail fast),
then the same run re-copies the skill files the new version ships. It reports
`upgraded (0.9.50 -> 0.9.51)` or `already latest (…)` in the summary. Without
`--upgrade` a re-run only refreshes the skill files: the bootstrap installs a
CLI only when it is missing, never over one that already works.

The third layer is the graph itself (`graphify-out/`), which the agent
rebuilds — a full `/graphify .` or an incremental `graphify update <path>`
after code changes. A stale graph is worse than none, since the skill tells
the agent to trust it over reading files.

`--status` prints the version stamped into each skill dir. If it disagrees
with `graphify --version`, the skill files are behind — re-run with
`--upgrade`.

Uninstall goes back through the CLI: `python3 install.py --uninstall graphify
--target both`. Repo scope is a plain copy, removed as a directory.

## Work VDI (Windows, Git Bash)

Run everything with `python` (Git Bash has no `python3` unless you alias it).

1. Copy this folder over (or clone the repo).
2. `python install.py --target both --dry-run` — sanity-check paths.
3. `python install.py --status` — check what's currently installed.
4. `python install.py --target both` — or `python install.py` for the
   interactive picker (recommended: it also offers the community skills).
5. `python install.py --status` — verify new installs.
6. If the proxy blocks the clone, follow the printed ZIP fallback, or use
   `--skills-only`.

Step 4 also installs `graphifyy` from PyPI so the `graphify` skill has its
CLI — with `uv` or `pipx` if either is on the box, otherwise plain
`pip install --user`. If the proxy blocks PyPI,
the run prints the manual command and carries on without it — and
`--skills-only` skips it outright. A `graphify` skill without its CLI is
inert, and `--status` says so.

From the dotfiles repo root, `python install.py install agent-skills` does steps 1–4
for the custom skills only.

**Symlinks on Windows** need Developer Mode or an admin shell. Without them the
installer detects this up front, prints `symlinks unsupported in <dir> —
installing copies`, and installs copies to both targets instead. Copies are
snapshots: **re-run the installer after editing a skill** to refresh them.
`--status` flags any leftover `<skill>.bak` directory from an older run — delete
those, the agents load them as extra skills.

Paths on Windows resolve under `%USERPROFILE%`: `~/.claude/skills`,
and `~/.copilot/skills`. Repo scope resolves to `<repo>\.github\skills`.
`%APPDATA%\Code\User\prompts` is only touched to delete the `.prompt.md`
copies older installs left there — they are what VS Code's "Migrate Prompt
Files" dialog lists. **Do not use that dialog's Convert button**: four of the
old prompts share a name with a real skill, and the converted stubs would
shadow it. Re-run the installer instead.

`roj-soundboarding` writes SB documents to the root of the repository it runs
in. To use one shared folder instead, set `SOUNDBOARD_DIR` and
`PROJECTS_ROOT` once (`setx SOUNDBOARD_DIR C:\path\to\soundboard`, same
for `PROJECTS_ROOT`).

Team distribution per repo: `python install.py --repo <path>`, then PR the
`.github/` additions. Check first that the team repo does not already own a
skill of the same name (`--dry-run` shows `updated` when a seed would
overwrite one). To
keep a seed local instead, `echo .github/ >> .git/info/exclude` — per-repo and
invisible to teammates. Do not add these paths to the global
[`git/ignore`](https://github.com/r0jjames/.dotfiles/blob/main/git/ignore): `.github/skills/` is GitHub's own mechanism
for team sharing, and a global rule would suppress intentional additions
everywhere.

## JetBrains (IntelliJ / PyCharm / GoLand)

Copilot reads skills from `~/.copilot/skills` (personal, every project) and
`<repo>/.github/skills/` (repo scope). JetBrains namespaces skills, so they
are typed as `/skill:<name>`:

| | VS Code | JetBrains, any project |
| --- | --- | --- |
| Soundboarding | `/roj-soundboarding create an SB from PROJ-1001.md` | `/skill:roj-soundboarding create an SB from PROJ-1001.md` |
| Explain | `/roj-explain-logic PR #142` | `/skill:roj-explain-logic PR #142` |

The skill picker filters on the namespaced name: type `/skill:roj-` to list
every custom workflow. Skills still trigger from their `description` in plain
English.

Setup checklist:

1. GitHub Copilot plugin installed from the JetBrains Marketplace, up to
   date, signed in.
2. **Settings → Languages & Frameworks → GitHub Copilot → Chat → Agent** —
   enable agent mode. Restart the IDE if the toggle has just appeared.
3. `python install.py --target copilot` (behind the proxy, add
   `--skills-only`; skills with requirements then warn and run on their
   fallbacks).
4. Reopen the IDE. In agent-mode chat type `/skill:roj-` — all nine custom
   skills should list.
5. Optional, per repo: `python install.py --repo .` seeds `.github/skills/`
   to share them with teammates.

Nothing shows up: confirm chat is in agent mode, that the plugin is current,
and that `install.py --status` lists the skills under `~/.copilot/skills`
with no leftover-prompt warnings.

## History: the roj- rename and retired prompts

Every custom skill and prompt carries a `roj-` prefix, so they sort together
and never collide with a community or plugin skill. Installs made before the
rename used bare names (`create-sb`, `explain-logic`, ...). Every install run
removes those leftovers — Copilot copies whose `SKILL.md` declares the old
name, Claude symlinks, generated Claude commands, and old `.prompt.md`
files — and logs each as `removed (renamed to roj-...)`. A skill of the same
bare name that the installer did not write is left alone.

`prompts/` used to hold nine `.prompt.md` workflows that the installer turned
into generated Copilot skills and Claude slash commands (`/roj-create-sb`,
`/roj-explain-code`, ...). Copilot stopped reading prompt files and each
workflow duplicated a skill, so they were retired: ask the skill instead
(`/roj-soundboarding create an SB from ...`, `/roj-explain-logic ...`).
Every install run removes what the prompts generated — skill dirs and
commands carrying the `Generated from prompts/` marker, and `.prompt.md`
copies under our names — logged as `removed (prompts retired — use the
skill)`. `--status` warns about any that remain.
