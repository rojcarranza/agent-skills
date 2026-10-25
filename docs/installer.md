# install.py reference

`install.py` installs my Claude Code and GitHub Copilot setup: my skills and
the community skills they chain to, through
[Cali](https://github.com/rojcarranza/cali) from the repo's
[`cali.yaml`](../cali.yaml); the personal instructions; and the GitHub MCP
server. It also removes what older versions and APM installed and installs
`graphify`, a CLI Cali does not install. Python >= 3.8, standard library
only. For a single skill in any agent, `npx skills add` is enough —
see the [README](../README.md#install).

## Flags and modes

```bash
python3 install.py                   # both agents
python3 install.py --target claude   # or copilot
python3 install.py --dry-run         # what would happen, nothing written
python3 install.py --status          # what is installed where, leftovers
python3 install.py --update          # skills with newer versions (reports only)
python3 install.py --upgrade         # newer graphify, then refresh its skill
python3 install.py --skills-only     # skip graphify (e.g. PyPI blocked)
```

| Flag | Meaning |
| --- | --- |
| `--target` | `claude`, `copilot` or `both` (default `both`) |
| `--dry-run` | print the planned actions; write and run nothing |
| `--status` | run `cali list`, then show graphify and leftovers |
| `--update` | run `cali status`: lists skills with local edits or newer upstream versions; changes nothing |
| `--upgrade` | upgrade external CLIs (`graphify`) before refreshing their skill files |
| `--skills-only` | skip `graphify` (e.g. PyPI blocked) |

Run order: stop with install instructions if `cali` is missing (a dry run
only says so), remove what older installs left (see "Old installs"), deploy
the personal instructions, register the GitHub MCP server, run
`cali sync -g --manifest <clone>/cali.yaml`, then install `graphify`. Every
`cali` command `install.py` runs takes `-g --manifest <clone>/cali.yaml`:
skills land in `~/.claude/skills` and `~/.copilot/skills`, and `cali.lock`
is read and written next to `cali.yaml` in the clone.

`--target` limits the cleanup, instructions, MCP servers and `graphify`.
`cali sync` has no target option, so it always installs every target
`cali.yaml` names.

The GitHub MCP server is registered only when a GitHub login exists:
`$token`, else `gh auth token`; with neither, `install.py` skips MCP servers
and says so. A machine without a GitHub login, e.g. one whose repos live on
Bitbucket, therefore installs cleanly; an MCP server configured on an
earlier run is left in place. The token itself is never written: the server
is remote and signs in on first use.

In [dotfiles](https://github.com/rojcarranza/.dotfiles),
`./install.py install agent-skills` clones this repo next to the dotfiles
checkout (override with `AGENT_SKILLS_DIR`), checks out the pinned ref and
runs `install.py` as part of normal machine setup.

## The Cali manifest

[`cali.yaml`](../cali.yaml) is the one list of skills. `install.py` points
`cali` at it in the clone, so editing `cali.yaml` here and re-running
`install.py` is the whole workflow. Each skill is a name with a git source:

```yaml
# Own skill: this clone at its checked-out HEAD, pinned by cali.lock
roj-explain-logic:
  source: .//skills/roj-explain-logic

# Community skill pinned to a commit, for one agent only
caveman:
  source: https://github.com/juliusbrussee/caveman//skills/caveman
  ref: 2e08b9177c07bb7249a8a2d1a6758e5db281d002
  targets: [copilot]
```

- **Pin to a commit.** Every community ref is a full commit SHA, so a new
  upstream version is a reviewed diff. [`cali.lock`](../cali.lock) records
  the commit and tree of every community skill, and the tree of ours.
- **One agent only.** `targets: [copilot]` (or `[claude]`) limits an entry.
  Copilot is the work agent, so every entry is Copilot only except
  `roj-idea-to-project`, which installs for both. Every community skill,
  cherry-picks included, is Copilot only.
- **Optional entries** are commented out in `cali.yaml`. Uncomment one and
  re-run `install.py` to install it. Commenting a live entry out drops it
  from `cali.lock` on the next run, but `cali sync` never deletes a folder:
  remove it with `cali remove <name> -g`, or delete it.
- **Bumping a pin.** `install.py --update` lists skills with newer
  upstream versions. Put the new SHA in `cali.yaml`, then run
  `cali update -g --manifest cali.yaml --apply` (a re-run of `install.py`
  only reports `ref changed`), review the `cali.lock` diff and commit it.
- **Our own skills** come from the clone at its checked-out HEAD
  (`.//skills/<name>`), so a branch installs its own version before it is
  merged. A committed edit moves the skill's tree:
  `cali update -g --manifest cali.yaml --apply` moves `cali.lock` to it.
  Commit that lock change in the same PR; until then
  `cali sync --frozen` fails with "locked tree is behind the repo".
- **Local edits** to an installed skill are kept: `cali sync` never
  overwrites a folder, and `cali update` merges upstream changes into it.

Where things land:

| What | Claude Code | Copilot |
| --- | --- | --- |
| Skills (Cali) | `~/.claude/skills/<name>/` | `~/.copilot/skills/<name>/` |
| Instructions | none (`~/.claude/CLAUDE.md` is yours) | `~/.copilot/instructions/personal.instructions.md` |
| MCP servers | `~/.claude.json` (`mcpServers`) | `~/.copilot/mcp-config.json` (`mcpServers`) |

The instruction file is `.apm/instructions/personal.instructions.md`, deployed
to Copilot as is. Claude gets none: it reads the global `~/.claude/CLAUDE.md`.
An earlier `~/.claude/rules/personal.md` is moved to the backup folder (see
"Old installs") when its body is a version this repo shipped; an edited copy
or a link is kept with a warning. A deployed file is replaced when it is
missing, a version this repo shipped (any commit of that file), or the
dotfiles repo's link; one you edited, or a link to anything else, is kept
with a warning — move the edits into the repo copy and delete it.

MCP servers are listed in `MCP_SERVERS` in `install.py`, in the shape each
config takes ([Claude Code](https://code.claude.com/docs/en/mcp),
[Copilot CLI](https://docs.github.com/en/copilot/how-tos/copilot-cli/customize-copilot/add-mcp-servers)).
A server already present under that name is left as it is, and a config
file that is not valid JSON is never rewritten. Playwright is an optional
entry to add there.

Skills added with `npx skills add` are not tracked here; `npx skills update`
refreshes those.

## Old installs

Before Cali, `install.py` copied or linked every skill itself, and then APM
copied them. Every run removes what those left, but only for skills Cali
installs again for that agent: our own skills and the active (uncommented)
skills in `cali.yaml` for that target.

- Links into a checkout of this repo (this clone, or another clone or
  worktree of it), and dangling links, are removed.
- A copy whose `SKILL.md` declares that name is moved to
  `~/.agent-skills-backups/<UTC time>/<target>/<name>` only when
  `cali status` says Cali did not install it (`base-lost` or `unlocked`).
  It is never deleted: `base-lost` also covers a Cali folder whose data dir
  was wiped, which may hold local edits. A folder Cali installed is never
  touched. Without `cali` no copy is moved.
- APM's Copilot copies in `~/.agents/skills` are removed when
  `~/.apm/apm.lock.yaml` lists them; anything else there (other tools use
  that folder) is left alone.

- A skill Cali no longer installs for that agent is moved to the same
  backup folder, whether Cali or an older installer put it there: a
  Copilot-only skill in
  `~/.claude/skills` (every one but `roj-idea-to-project`), and the pruned
  community skills (`RETIRED_SKILLS` in `install.py`) in either agent. Only
  a link into a checkout of this repo, a dangling link, or a copy whose
  `SKILL.md` declares that name moves; a folder with any other name, such
  as `no-mistakes`, is never touched.
- `~/.claude/rules/personal.md`, which earlier versions deployed for
  Claude, is moved to `<backup>/claude/personal.md` when its body is a
  version this repo shipped. An edited copy or a link is kept with a
  warning.

`--dry-run` lists these moves without making them, and `--status` lists
whatever is still left. An optional skill still commented out in
`cali.yaml` is kept with a warning: uncomment it in `cali.yaml` to have
Cali manage it, or delete it. If `cali sync` then fails, the run says so: the removed entries
come back once a re-run succeeds. `install.py` never uninstalls `apm` or
deletes `~/.apm`.

## Platforms

Supported: macOS, Linux, Windows Git Bash, WSL Ubuntu. Python >= 3.8,
standard library only. `cali` is a Go binary with its own installer (see
its README); it needs `git` on PATH. On Ubuntu 24.04 (WSL) a plain
`pip install --user` is refused for the system Python, so install `pipx`
(`sudo apt install pipx`) or `uv` there for `graphify`.

| | macOS / Linux | Windows Git Bash | WSL Ubuntu |
| --- | --- | --- | --- |
| Run as | `python3 install.py` | `python install.py` (Windows Python) | `python3 install.py` |
| Home | `$HOME` | `%USERPROFILE%` | Linux `$HOME` |
| `cali` lookup | `PATH`, `~/.local/bin` | `PATH` plus `.exe`/`.cmd` suffixes and the pip user Scripts dir | as Linux |
| Serves | Claude Code, Copilot CLI/VS Code/JetBrains | the same, Windows side | Claude Code and Copilot CLI inside WSL; Windows-side IDEs need a Git Bash run too |

Legacy cleanup on Windows handles copies, never assumes symlinks. Every file
the installer writes is UTF-8 with `\n` line endings. CI runs the unit tests
on `ubuntu-latest`, `macos-latest` and `windows-latest` (Git Bash shell),
plus a real `install.py` smoke test against a scratch home, which builds
`cali` and runs only when the `CALI_REPO_TOKEN` secret can read the Cali
repository.

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
4. Install `cali` (its README: `sh scripts/install.sh` from Git Bash).
5. `python install.py --target both` — skills through `cali`, the
   instructions, the MCP server, then `graphify`.
6. `python install.py --status` — verify new installs.
7. Cali fetches every skill from GitHub, so run the install from a network
   that reaches GitHub. `--skills-only` only skips `graphify`; it helps when
   PyPI is the blocked part.

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

From the dotfiles repo root, `python install.py install agent-skills` does
steps 1–3 and 5.

Cali installs skills as copies on every platform, so Windows needs no symlink
rights. Copies are snapshots of the tree in `cali.lock`: an edit to one of
our skills reaches them after it is committed and
`cali update -g --manifest cali.yaml --apply` has moved the lock. A re-run
removes legacy `.bak` copies of retired prompts.

Paths on Windows resolve under `%USERPROFILE%`: `~/.claude/skills` for
Claude, `~/.copilot/skills` for Copilot skills, `~/.copilot/instructions` for
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

Team distribution per repo is still APM's: add an `apm.yml` to the team repo
listing the skills it needs, pinned to a commit, and run `apm install` there
(see the README, "In a team repository"). Commit `apm.yml` and
`apm.lock.yaml`.

## JetBrains (IntelliJ / PyCharm / GoLand)

Copilot reads skills from `~/.copilot/skills` (personal, every project, where
Cali puts them) and `<repo>/.github/skills/` (repo scope). JetBrains namespaces skills, so they
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
   (Cali needs it; `--skills-only` only skips `graphify`, for a blocked PyPI).
4. Reopen the IDE. In agent-mode chat type `/skill:roj-` — all ten custom
   skills should list.
5. Optional, per repo: an `apm.yml` in the team repo shares them with
   teammates (README, "In a team repository").

Nothing shows up: confirm chat is in agent mode, that the plugin is current,
that `install.py --status` lists the skills and prints no leftover
warnings, and that they are under `~/.copilot/skills`.

## History: the roj- rename and retired prompts

Before APM (2026-10), `install.py` copied community skills from
`skills-inventory.json` and linked our skills. APM then installed them from
`apm.yml` until Cali replaced it (2026-10-17). Every run removes what both
left for the skills Cali installs again and warns about the rest (see "Old
installs").

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
