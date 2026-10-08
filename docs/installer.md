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

Community skills are fetched into `~/.agent-skills-cache/` and installed/updated
in place (missing = install, present = update, unchanged = up to date):

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

### How our skills use the graph

Installing graphify saves nothing by itself: a skill has to ask the graph
before reading files. Seven skills do, through the shared
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

It applies only when `graphify-out/graph.json` exists, the CLI runs and the
graph is not older than the last commit; a stale graph gets one
`graphify update .` (no LLM) or is skipped. The graph only says where to
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
