# install.py reference

`install.py` installs my Claude Code and GitHub Copilot setup through
[APM](https://microsoft.github.io/apm/): my skills, the community skills they
chain to, personal instructions and MCP servers, all listed in the repo's
[`apm.yml`](../apm.yml). It also removes what older versions installed and
installs `graphify`, a CLI APM cannot package. Python >= 3.8, standard
library only. For a single skill in any agent, `npx skills add` is enough —
see the [README](../README.md#install).

## Flags and modes

```bash
python3 install.py                   # both agents
python3 install.py --target claude   # or copilot
python3 install.py --dry-run         # what would happen, nothing written
python3 install.py --status          # what is installed where, leftovers
python3 install.py --update          # pins with newer releases (reports only)
python3 install.py --upgrade         # newer graphify, then refresh its skill
python3 install.py --skills-only     # skip graphify (e.g. PyPI blocked)
```

| Flag | Meaning |
| --- | --- |
| `--target` | `claude`, `copilot` or `both` (default `both`) |
| `--dry-run` | print the planned actions; write and run nothing |
| `--force` | replace a `~/.apm/apm.yml` that `install.py` did not write |
| `--status` | show what APM installed, graphify, and leftovers |
| `--update` | run `apm outdated -g`: lists `apm.yml` pins with newer upstream releases; changes nothing |
| `--upgrade` | upgrade external CLIs (`graphify`) before refreshing their skill files |
| `--skills-only` | skip `graphify` (e.g. PyPI blocked) |

Run order: remove what pre-APM versions installed, write `~/.apm/apm.yml`
(pointing at this clone), run `apm install -g --update --target <value>`,
then install `graphify`. A `~/.apm/apm.yml` that `install.py` did not write
stops the run unless `--force` is given. On the first run APM prompts for a
`token` value for the GitHub MCP server (a GitHub token); in a
non-interactive shell set `token=...` in the environment first.

In [dotfiles](https://github.com/rojcarranza/.dotfiles),
`./install.py install agent-skills` clones this repo next to the dotfiles
checkout (override with `AGENT_SKILLS_DIR`), checks out the pinned ref and
runs `install.py` as part of normal machine setup.

## The APM manifest

[`apm.yml`](../apm.yml) is the one list of what gets installed. `install.py`
writes `~/.apm/apm.yml` with absolute paths into this clone, so editing
`apm.yml` here and re-running `install.py` is the whole workflow. Entries
under `dependencies.apm` take two forms:

```yaml
# Short form: owner/repo/path#<full commit SHA>
- github/awesome-copilot/skills/code-tour#7cce7cfb4b61196c36d7e8eb8475ae84b356b126

# Object form, when the skill is for one agent only
- git: https://github.com/juliusbrussee/caveman.git
  path: skills/caveman
  ref: 2e08b9177c07bb7249a8a2d1a6758e5db281d002
  targets: [copilot]
```

- **Pin to a commit.** Every community ref is a full commit SHA, so a new
  upstream version is a reviewed diff.
- **One agent only.** `targets: [copilot]` (or `[claude]`) limits an entry;
  caveman and debugging-and-error-recovery are Copilot only because Claude
  gets the same from a plugin.
- **Optional entries** are commented out in `apm.yml`. Uncomment one and
  re-run `install.py` to install it. Comment a live entry out and re-run to
  remove it, since `install.py` passes `--update`.
- **Bumping a pin.** `install.py --update` lists pins with newer releases.
  Put the new SHA in `apm.yml`, review the diff, re-run `install.py`.
- **MCP servers** sit under `dependencies.mcp` (the GitHub server is live;
  Playwright is an optional entry).

Where things land (APM 0.33.0):

| What | Claude Code | Copilot |
| --- | --- | --- |
| Skills | `~/.claude/skills/<name>/` (copies) | `~/.agents/skills/<name>/` |
| Instructions | `~/.claude/rules/personal.md` | `~/.copilot/instructions/personal.instructions.md` |
| MCP servers | `~/.claude.json` (`mcpServers`) | `~/.copilot/mcp-config.json` |

APM records what it installed in `~/.apm/apm.lock.yaml`. Skills are copies,
so re-run `install.py` after editing a skill in this clone. Skills added with
`npx skills add` are not tracked here; `npx skills update` refreshes those.

The first run removes what older versions left, but only for skills APM
installs again for that agent: our own skills and the active (uncommented)
community skills in `apm.yml` for that target. It removes copies whose
`SKILL.md` declares that name and links into a checkout of this repo (this
clone, or another clone or worktree of it). A Claude copy that
`~/.apm/apm.lock.yaml` lists under `.claude/skills/` is APM's and stays.
Anything else the old installer left — an optional skill still commented
out in `apm.yml`, or a Copilot-only skill in `~/.claude/skills` — is kept
with a warning: uncomment it in `apm.yml` to have APM manage it, or delete
it. An `~/.copilot/instructions/personal.instructions.md` you edited (the
dotfiles one) is kept with a warning; move its content into
`.apm/instructions/` and delete it to let APM own the file. If `apm install`
then fails, the run says so: the removed entries come back once a re-run
succeeds.

## Platforms

Supported: macOS, Linux, Windows Git Bash, WSL Ubuntu. Python >= 3.8,
standard library only (APM's own pip install needs 3.10; brew, winget and the
curl installer do not).

| | macOS / Linux | Windows Git Bash | WSL Ubuntu |
| --- | --- | --- | --- |
| Run as | `python3 install.py` | `python install.py` (Windows Python) | `python3 install.py` |
| Home | `$HOME` | `%USERPROFILE%` | Linux `$HOME` |
| `apm` lookup | `PATH`, `~/.local/bin` | `PATH` plus `.exe`/`.cmd` suffixes and the pip user Scripts dir | as Linux |
| Repo path in manifest | `/Users/...`, `/home/...` | `C:/Users/...` | `/home/...` or `/mnt/c/...` |
| Serves | Claude Code, Copilot CLI/VS Code/JetBrains | the same, Windows side | Claude Code and Copilot CLI inside WSL; Windows-side IDEs need a Git Bash run too |

Legacy cleanup on Windows handles copies, never assumes symlinks. Every file
the installer writes is UTF-8 with `\n` line endings. CI runs the unit tests
on `ubuntu-latest`, `macos-latest` and `windows-latest` (Git Bash shell),
plus a real `apm install` smoke test against a scratch home.

## External skills (installed by their own CLI)

Some skills ship with a tool rather than as a folder we can copy. Those are
listed in `EXTERNALS` in `install.py`: the installer puts the CLI on the
machine, then hands the per-target install to that CLI, so the skill is always
the upstream version and nothing is vendored here. It tries `uv tool install`,
then `pipx install`, then `python -m pip install --user` — the last one always
exists, since the installer is itself running under that interpreter. A CLI it
cannot install is a skip with instructions, never a failed run. `--skills-only`
skips externals; it needs the network.

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

Copilot deliberately gets the `vscode` skill body, not the `copilot` one.
Both write the same `~/.copilot/skills/graphify/SKILL.md`, but the `copilot`
body dispatches extraction through a parallel Agent tool that neither VS Code
Copilot Chat nor JetBrains Copilot has; the `vscode` body drives the same
extraction by hand. Copilot CLI reads the same file and only loses the
parallelism.

`graphify vscode install` also writes `.github/copilot-instructions.md` next
to its working directory, so `install.py` runs it in a scratch dir and no
file lands in whatever directory you launched it from.

`graphify install` appends an always-on `## graphify` section to
`~/.claude/CLAUDE.md` — a symlink to `claude/CLAUDE.md` in this repo — unless
the word `graphify` already appears there. The bullet in `claude/CLAUDE.md`
is that guard: it keeps graphify skill-only (no per-session token cost) and
keeps the CLI out of a repo-managed file.

### How our skills use the graph

Installing graphify saves nothing by itself: a skill has to ask the graph
before reading files. Eight skills do, through the shared
`references/graph-first.md` (owned by `roj-code-review-pr`, copied by
`tools/sync_shared.py`):

| Skill | Graph step |
| --- | --- |
| `roj-tour-codebase` | `GRAPH_REPORT.md` as the discovery map; `graphify path` for the core flow |
| `roj-explain-logic` | `graphify explain` / `path` for callers and callees |
| `roj-explain-feature-changes` | `graphify affected` / `explain` while tracing |
| `roj-code-review-pr`, `roj-review-pr-comment` | `graphify affected` in the system pass (callers of changed symbols) |
| `roj-investigate-issue` | `graphify query "<error line>"` in phase 2 |
| `roj-soundboarding` | one `graphify query` per acceptance criterion |
| `roj-grill-plan` | `graphify query` for each fact a question needs |

It applies only when `graphify-out/` has a graph and the CLI runs.
Freshness is checked with `git`: the `Built from commit:` line in
`GRAPH_REPORT.md` against `HEAD`, and files changed since are read from
disk. Skills only run the read-only graphify queries (allowed alongside
`git` in their command rules and `allowed-tools`); they never update or
create the graph, and suggest `graphify update .` when it is stale. The graph only says where to
look: findings and quotes still come from reading the lines.
`roj-code-review-pr-fast` stays diff-local and never uses it. No skill
creates `graphify-out/` unasked. Per repo, `graphify update .` builds a
code-only graph in seconds without an LLM (this repo: about 1,500 nodes);
`/graphify .` also maps docs and spends tokens doing it. Re-run
`graphify update .`, or leave `graphify watch .` running, to keep it
current.

### Updating an external

Nothing about an external updates itself. Three layers move independently:

```bash
python3 install.py --target both --upgrade   # CLI + skill files, in that order
```

`--upgrade` upgrades the package (trying `uv tool upgrade`, `pipx upgrade`,
then `pip install --user --upgrade` — whichever owns it; the others fail fast),
then the same run re-copies the skill files the new version ships. It reports
`upgraded (0.9.50 -> 0.9.51)` or `already latest (…)` in the summary. Without
`--upgrade` a re-run only refreshes the skill files: the bootstrap installs a
CLI only when it is missing, never over one that already works.

A target whose skill is already stamped with the CLI's version (for
graphify, `.graphify_version` equal to `graphify --version`) reports
`up to date` and the CLI's installer is not run at all, so routine runs
never rewrite the folder. An interrupted install (a leftover
`references.tmp`, or a `references/` file named in `SKILL.md` but missing)
is never treated as up to date: the next run repairs it. On Windows a failed CLI install is retried once,
three seconds later, after clearing a leftover `references.tmp`.

The third layer is the graph itself (`graphify-out/`), which the agent
rebuilds — a full `/graphify .` or an incremental `graphify update <path>`
after code changes. A stale graph is worse than none, since the skill tells
the agent to trust it over reading files.

`--status` prints the version stamped into each skill dir. If it disagrees
with `graphify --version`, the skill files are behind — re-run with
`--upgrade`.

To remove it, use the CLI: `graphify claude uninstall` and
`graphify vscode uninstall`.

## Work VDI (Windows, Git Bash)

Run everything with `python` (Git Bash has no `python3` unless you alias it).

1. Copy this folder over (or clone the repo).
2. `python install.py --target both --dry-run` — sanity-check paths.
3. `python install.py --status` — check what's currently installed.
4. `python install.py --target both` — installs through APM (install APM
   first; see the [README](../README.md#install)), then `graphify`.
5. `python install.py --status` — verify new installs.
6. APM fetches the community skills from GitHub, so run the install from a
   network that reaches GitHub. `--skills-only` only skips `graphify`; it
   helps when PyPI is the blocked part.

Step 4 also installs `graphifyy` from PyPI so the `graphify` skill has its
CLI — with `uv` or `pipx` if either is on the box, otherwise plain
`pip install --user`. If the proxy blocks PyPI,
the run prints the manual command and carries on without it — and
`--skills-only` skips it outright. A `graphify` skill without its CLI is
inert, and `--status` says so.

`PermissionError: [WinError 5] Access is denied: '...\graphify\references.tmp'
-> '...\graphify\references'` comes from graphify's own installer: Windows
refuses to rename a folder while another process holds a file in it — VS
Code or JetBrains watching `~\.copilot\skills`, or antivirus scanning the
files graphify just wrote. The installer retries once; if it still fails,
close the IDEs, delete `~/.copilot/skills/graphify/references.tmp` and
`references`, and run `python install.py --target copilot`.
Every other skill in the run is unaffected.

From the dotfiles repo root, `python install.py install agent-skills` does steps 1–4.

APM installs skills as copies on every platform, so Windows needs no symlink
rights. Copies are snapshots: **re-run the installer after editing a skill** to
refresh them. A re-run removes legacy `.bak` copies of retired prompts.

Paths on Windows resolve under `%USERPROFILE%`: `~/.claude/skills` for
Claude, `~/.agents/skills` for Copilot skills, `~/.copilot/instructions` for
Copilot instructions.
`%APPDATA%\Code\User\prompts` is only touched to delete the `.prompt.md`
copies older installs left there — they are what VS Code's "Migrate Prompt
Files" dialog lists. **Do not use that dialog's Convert button**: four of the
old prompts share a name with a real skill, and the converted stubs would
shadow it. Re-run the installer instead.

`roj-soundboarding` writes SB documents to the root of the repository it runs
in. To use one shared folder instead, set `SOUNDBOARD_DIR` and
`PROJECTS_ROOT` once (`setx SOUNDBOARD_DIR C:\path\to\soundboard`, same
for `PROJECTS_ROOT`).

Team distribution per repo: add an `apm.yml` to the team repo listing the
skills it needs, pinned to a commit, and run `apm install` there (see the
README, "In a team repository"). Commit `apm.yml` and `apm.lock.yaml`.

## JetBrains (IntelliJ / PyCharm / GoLand)

Copilot reads skills from `~/.agents/skills` (personal, every project, where
APM puts them) and `<repo>/.github/skills/` (repo scope). JetBrains namespaces skills, so they
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
3. `python install.py --target copilot` from a network that reaches GitHub
   (APM needs it; `--skills-only` only skips `graphify`, for a blocked PyPI).
4. Reopen the IDE. In agent-mode chat type `/skill:roj-` — all ten custom
   skills should list.
5. Optional, per repo: an `apm.yml` in the team repo shares them with
   teammates (README, "In a team repository").

Nothing shows up: confirm chat is in agent mode, that the plugin is current,
that `install.py --status` lists the skills among APM's dependencies and
prints no leftover warnings, and that they are under `~/.agents/skills`.

## History: the roj- rename and retired prompts

Before APM (2026-10), `install.py` copied community skills from
`skills-inventory.json` and linked our skills; the first APM run removes
those entries for the skills APM installs again and warns about the rest
(see "The APM manifest").

Every custom skill and prompt carries a `roj-` prefix, so they sort together
and never collide with a community or plugin skill. Installs made before the
rename used bare names (`create-sb`, `explain-logic`, ...). Every install run
removes those leftovers — Copilot copies whose `SKILL.md` declares the old
name, Claude symlinks, generated Claude commands, and old `.prompt.md`
files — and logs each as `removed (renamed to roj-...)`. A skill of the same
bare name that the installer did not write is left alone. `--status` warns
about any that remain.

`prompts/` used to hold nine `.prompt.md` workflows that the installer turned
into generated Copilot skills and Claude slash commands (`/roj-create-sb`,
`/roj-explain-code`, ...). Copilot stopped reading prompt files and each
workflow duplicated a skill, so they were retired: ask the skill instead
(`/roj-soundboarding create an SB from ...`, `/roj-explain-logic ...`).
Every install run removes what the prompts generated — skill dirs and
commands carrying the `Generated from prompts/` marker, and `.prompt.md`
copies under our names — logged as `removed (prompts retired — use the
skill)`. `--status` warns about any that remain.
