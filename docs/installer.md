# install.py reference

Skills and `install.py` are separate. [Cali](https://github.com/rojcarranza/cali)
installs the skills; `install.py` installs the extras around them and never
runs `cali`.

## Skills: install cali first

Cali reads this repo's skill list from GitHub, so no clone is needed:

```bash
go install github.com/rojcarranza/cali/cmd/cali@latest   # or `make install` in a cali clone
cali setup github:rojcarranza/agent-skills               # once
cali load roj-one-slide                                  # from any folder
cali status -g                                           # installed, newer versions
cali update -g --apply                                   # take newer versions
```

`cali setup` adds this repo to the `sources:` list in your own `cali.yaml`.
`cali load` finds the skill there, records it with `load: on-demand` and a
pin in your own `cali.yaml` and `cali.lock`, and copies it in. On WSL it fills
both the Linux home and your Windows home. Cali's own documentation has the
details.

## What install.py does

`install.py` installs my Claude Code and GitHub Copilot extras: the personal
instructions, the Superpowers start-up note, a JetBrains instruction block,
the GitHub MCP server and `graphify`, a CLI Cali does not install. It
touches no skills folder except the one `graphify` writes for itself. It
runs with no `cali` on the machine. Python >= 3.8, standard library only. For
a single skill in any agent, `npx skills add` is enough, see the
[README](../README.md#install).

## Flags and modes

```bash
python3 install.py                   # both agents
python3 install.py --target claude   # or copilot
python3 install.py --dry-run         # what would happen, nothing written
python3 install.py --status          # what is installed where, leftovers
python3 install.py --update          # skills with newer versions (reports only)
python3 install.py --upgrade         # newer graphify, then refresh its skill
python3 install.py --skills-only     # skip graphify (e.g. PyPI blocked)
python3 install.py --windows-home /mnt/c/Users/me   # WSL: name the Windows home
```

| Flag | Meaning |
| --- | --- |
| `--target` | `claude`, `copilot` or `both` (default `both`) |
| `--dry-run` | print the planned actions, read from the same item states as a real run; write and run nothing |
| `--status` | show what this script wrote, graphify and leftovers, read from the same item states as a real run; for skills it points to `cali status -g` |
| `--update` | prints `cali update -g`; changes nothing |
| `--upgrade` | upgrade external CLIs (`graphify`) before refreshing their skill files |
| `--skills-only` | skip `graphify` (e.g. PyPI blocked) |
| `--windows-home PATH` | WSL only: the Windows home that gets the JetBrains instructions (default: `%USERPROFILE%`, read through `cmd.exe`) |

Run order: deploy the personal instructions, register the GitHub MCP server,
write the JetBrains block into the Windows home (WSL only), then install
`graphify`. `--target` limits the instructions, the MCP server and graphify
to that agent.

### Item states and exit codes

The real run, `--dry-run` and `--status` read the disk the same way: one
inspect step names a state for each thing `install.py` manages (an
instruction file, the JetBrains block, an MCP entry, the old Claude rule, a
graphify skill per agent), and one table (`ACTIONS` in `install.py`) says what
each state means. A dry run therefore prints what the real run would report,
and `--status` warns about exactly what a run would change or leave.

| State | The run | `--status` |
| --- | --- | --- |
| `current` | nothing; an external prints "up to date" | clean |
| `missing`, `older`, `half` (an interrupted graphify install) | writes or reinstalls it | warns: re-run |
| `dotfiles-link`, `leftover` (the old `~/.claude/rules/personal.md`) | replaces the link, moves the rule to a backup | warns: re-run |
| `edited`, `foreign-link`, `unreadable` | keeps it and warns, row says `kept` | warns |
| `unavailable` (its CLI could not be installed) | skips it | warns |
| `failed` | the CLI install failed; row says `failed` | not reached |

The exit code is the worst state: `0` nothing needs you, `1` something was
kept or left for you to look at (an edited file, a link, a missing CLI; for
`--status`, anything a run would still change), `3` an install failed. A
failed install prints no "Verify" line for that skill.

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

## The skills list

[`cali.yaml`](../cali.yaml) is the list Cali reads after `cali setup`. Each
skill is a name with a git source. This repo keeps no `cali.lock`: the pins
are yours, in the `cali.yaml` and `cali.lock` that Cali writes for you.

```yaml
# Own skill: this repo, `.//` is the repo Cali reads it from
roj-explain-logic:
  source: .//skills/roj-explain-logic

# Community skill pinned to a commit, for one agent only
caveman:
  source: https://github.com/juliusbrussee/caveman//skills/caveman
  ref: 2e08b9177c07bb7249a8a2d1a6758e5db281d002
  targets: [copilot]
```

- **Pin to a commit.** Every community ref is a full commit SHA, so a new
  upstream version is a reviewed diff.
- **One agent only.** `targets: [copilot]` (or `[claude]`) limits an entry.
  Copilot is the work agent, so every entry is Copilot only, our skills
  and every community skill, cherry-picks included, except `roj-one-slide`,
  which also targets Claude.
- **Optional entries** are commented out in `cali.yaml`. Uncomment one to
  offer it to `cali load`.
- **Bumping a pin.** Put the new SHA in `cali.yaml` here; a user's
  `cali update -g --apply` moves their pin.
- **Local edits** to an installed skill are kept: `cali update` merges
  upstream changes into it.

Where things land:

| What | Claude Code | Copilot |
| --- | --- | --- |
| Skills (`cali load`, not `install.py`) | `~/.claude/skills/<name>/` | `~/.copilot/skills/<name>/` |
| Instructions | none (`~/.claude/CLAUDE.md` is yours) | `~/.copilot/instructions/personal.instructions.md` |
| MCP servers | `~/.claude.json` (`mcpServers`) | `~/.copilot/mcp-config.json` (`mcpServers`) |

The instruction files are `instructions/personal.instructions.md` and
`instructions/superpowers.instructions.md` (the Superpowers start-up
note and tool map), both deployed to `~/.copilot/instructions/` as is. VS Code
reads that folder; JetBrains does not, it reads one global file
(`~/.config/github-copilot/intellij/global-copilot-instructions.md`, or
`%LOCALAPPDATA%\github-copilot\intellij\global-copilot-instructions.md` on
Windows, per Microsoft's Java blog of July 9, 2025; the WSL run also writes
the Windows one). `install.py` writes the note and the personal instructions
there between `<!-- BEGIN agent-skills ... -->` and `<!-- END agent-skills -->`;
text outside the markers is kept, and edits inside are replaced on the next run.
Claude gets none: it reads the global `~/.claude/CLAUDE.md`.
An earlier `~/.claude/rules/personal.md` is moved to
`~/.agent-skills-backups/<UTC time>/claude/` when its body is a version this repo shipped; an edited copy
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

Earlier versions of `install.py` ran `cali sync` and cleaned up the skill
folders older installers (the pre-Cali copies, APM, the `roj-` rename and the
retired prompts) had left. This version touches none of them; `cali doctor`
lists skill folders Cali did not install, and you can delete them by hand.

Earlier versions also linked `~/.config/cali/cali.yaml` (or under
`$CALI_CONFIG_DIR` / `$XDG_CONFIG_HOME`) to this clone's `cali.yaml`, so Cali
wrote your loads into the clone. If you ran one, remove the link and run
`cali setup github:rojcarranza/agent-skills` again:

```bash
rm ~/.config/cali/cali.yaml    # only if it is a link into the agent-skills clone
```

A WSL run once wrote `.installed-from-wsl` into
`<Windows home>/.copilot/skills`; nothing reads it now and you can delete it.
`install.py` never uninstalls `apm` or deletes `~/.apm`.

## Platforms

Supported: macOS, Linux, Windows Git Bash, WSL Ubuntu. Python >= 3.8,
standard library only. Cali is a separate Go binary (`go install`, see the
README); it needs `git` on PATH. On Ubuntu 24.04 (WSL) a plain
`pip install --user` is refused for the system Python, so install `pipx`
(`sudo apt install pipx`) or `uv` there for `graphify`.

**graphify not found on WSL Ubuntu.** With neither `uv` nor `pipx`, the
installer skips `pip --user` (the system Python has an `EXTERNALLY-MANAGED`
marker) and prints the fix:

```bash
sudo apt install pipx
pipx ensurepath
```

Open a new shell and run `python3 install.py` again. If `graphify` is
installed but not found by name, `python3 install.py --status` prints the
`export PATH` line for `~/.local/bin`. A managed Python without `apt`, such as
Homebrew's, gets the generic `uv tool install` / `pipx install` advice instead.

| | macOS / Linux | Windows Git Bash | WSL Ubuntu |
| --- | --- | --- | --- |
| Run as | `python3 install.py` | `python install.py` (Windows Python) | `python3 install.py` |
| Home | `$HOME` | `%USERPROFILE%` | Linux `$HOME` |
| Serves | Claude Code, Copilot CLI/VS Code/JetBrains | the same, Windows side | Claude Code and Copilot CLI inside WSL (Linux home) and, through the Windows leg below, Windows-side JetBrains (instructions only) |

### WSL: two homes

Windows-side VS Code and JetBrains do not read the Linux home: they read
`%USERPROFILE%`. A WSL run of `install.py` writes the JetBrains instruction
block there:

- The home is `%USERPROFILE%`, asked of Windows through `cmd.exe` interop and
  converted with `wslpath -u`, or the path given to `--windows-home`.
- If it cannot be resolved (interop off, `wslpath` missing, the path not a
  directory) the run still writes the Linux home, then prints a warning
  saying why and how to fix it: pass `--windows-home /mnt/c/Users/<you>`, or
  run `install.py` from Git Bash.
- `--status` prints the Windows home it found.

Skills reach the Windows home through Cali: `cali setup` finds it once and
`cali load` then fills both homes. Not written into Windows by `install.py`:
Claude Code, `graphify` (its CLI has to be on the Windows PATH too), the
personal instructions and the GitHub MCP server. Run `install.py` from Git
Bash for those.

Which Copilot surface reads which folder (checked against the GitHub and VS
Code docs): personal skills are read from `~/.copilot/skills`,
`~/.claude/skills` and `~/.agents/skills` by Copilot CLI and agent mode in
VS Code; JetBrains lists skills as a preview feature. The docs do not say
how VS Code with Remote - WSL or JetBrains opening a WSL project resolve `~`.
The two homes cover every case: Copilot CLI in WSL reads the Linux home,
Windows IDEs the Windows one (the Linux home is also the one the Remote - WSL
extension host should see; this is untested here).

Every file the installer writes is UTF-8 with `\n` line endings. The
`installer-smoke` gate in `.no-mistakes.yaml` runs `install.py` against a
scratch home with no `cali` on the machine and checks it writes the extras
and no skills.

## External skills (installed by their own CLI)

Some skills ship with a tool rather than as a folder we can copy. Those are
listed in `EXTERNALS` in `install.py`: the installer puts the CLI on the
machine, then hands the per-target install to that CLI, so the skill is always
the upstream version and nothing is vendored here. It tries `uv tool install`,
then `pipx install`, then `python -m pip install --user` - the last one exists
wherever the installer runs, since it runs under that interpreter, but is
skipped on an externally managed Python (see [Platforms](#platforms)). A CLI it
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
`references/graph-first.md` (owned by `roj-review-code`, copied by
`tools/sync_shared.py`):

| Skill | Graph step |
| --- | --- |
| `roj-onboard-repo` | `GRAPH_REPORT.md` as the starting map; `graphify path` for the core flow |
| `roj-explain-logic` | `graphify explain` / `path` for callers and callees |
| `roj-explain-my-branch` | `graphify affected` / `explain` while tracing |
| `roj-review-code`, `roj-review-pr-comment` | `graphify affected` in the system pass (callers of changed symbols) |
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
`roj-review-code` in quick mode stays diff-local and never uses it. No skill
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
then `pip install --user --upgrade` - whichever owns it; the others fail fast,
and pip is skipped on an externally managed Python), then the same run
re-copies the skill files the new version ships. It reports
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
4. `python install.py --target both` — the instructions, the MCP server,
   then `graphify`.
5. Install `cali`, then load skills (see the top of this page). On a VDI
   whose WSL cannot find the Windows home, `cali setup` says so and names
   `CALI_WINDOWS_HOME`.
6. `python install.py --status` — verify new installs.
7. Cali fetches every skill from GitHub, so run `cali load` from a network
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
steps 1–3 and 4.

Cali installs skills as copies on every platform, so Windows needs no symlink
rights. A copy is a snapshot of the tree Cali pinned when you loaded it:
`cali update -g --apply` moves it.

Paths on Windows resolve under `%USERPROFILE%`: `~/.claude/skills` for
Claude, `~/.copilot/skills` for Copilot skills, `~/.copilot/instructions` for
Copilot instructions.
Old `.prompt.md` copies in `%APPDATA%\Code\User\prompts` are what VS Code's
"Migrate Prompt Files" dialog lists; this version no longer deletes them.
**Do not use that dialog's Convert button**: four of the old prompts share a
name with a real skill, and the converted stubs would shadow it. Delete the
files by hand.

`roj-soundboarding` writes SB documents to the root of the repository it runs
in. To use one shared folder instead, set `SOUNDBOARD_DIR` and
`PROJECTS_ROOT` once (`setx SOUNDBOARD_DIR C:\path\to\soundboard`, same
for `PROJECTS_ROOT`).

Team distribution per repo is Cali's too: run `cali add` without `-g` in the
team repo, and commit `cali.yaml`, `cali.lock` and `.github/skills/` (see
the README, "In a team repository"). A team repo on Bitbucket Data Center is
a source by its clone address, such as
`https://bitbucket.example.com/scm/PROJ/team-skills.git//skills/<name>`.

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
3. `cali setup github:rojcarranza/agent-skills`, then `cali load <skill>`
   (needs a network that reaches GitHub), and `python install.py --target
   copilot` for the instructions; `--skills-only` only skips `graphify`, for
   a blocked PyPI.
4. Reopen the IDE. In agent-mode chat type `/skill:roj-` — all ten custom
   skills should list.
5. Optional, per repo: `cali add` without `-g` in the team repo puts skills
   in its `.github/skills/` for every teammate (README, "In a team
   repository").

Nothing shows up: confirm chat is in agent mode, that the plugin is current,
that `cali status -g` lists the skills and `install.py --status` prints no
leftover warnings, and that they are under `~/.copilot/skills`.

## History

Before APM (2026-10), `install.py` copied community skills and linked our
skills. APM then installed them until Cali replaced it (2026-10-17), and
`install.py` ran `cali sync` until it stopped installing skills altogether.
Those installs left skill folders (bare pre-`roj-` names, generated prompt
skills, APM copies in `~/.agents/skills`, retired skills); this version does
not remove them. `cali doctor` lists the ones Cali did not install.
