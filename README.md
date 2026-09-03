# agent-skills

Custom agent skills usable by GitHub Copilot (VS Code and JetBrains IDEs) and
Claude Code, plus an installer. One `SKILL.md` format serves every platform.

## Layout

- `skills/explain-logic/` — guided code-comprehension walkthroughs
  (PR/branch diffs, files, functions) with language lenses.
- `skills/soundboarding/` — story → SB document → task-by-task
  implementation workflow (bundled `SB-template.md` + examples).
- `skills/interview-prep/` — DevOps interview doc generator from a CV
  (vault-aware, bundled calibration references).
- `skills/investigate-issue/` — problem `.md` in, validated root cause +
  fix-steps `-investigation.md` out (Bamboo plans/agents, Java, Python,
  Bash, Go, Docker, k8s).
- `skills/code-review-pr/` — feature-branch review before or after a PR:
  change summary, severity/confidence-tagged findings, `-review.md` report
  and a tour. Rules split into always-loaded method + cross-cutting, and
  language/platform lenses (Java/Maven, Python, Bash, Go, Bamboo, k8s, Helm,
  Docker) loaded from the diff. Git-only — no PR host API.
- `skills/code-review-pr-fast/` — chat-only short pass over the same diff,
  `git` calls only, no files written. Reads its method from
  `code-review-pr` when installed.
- `skills/tour-codebase/` — onboarding into a repository you do not know:
  delegates discovery to `acquire-codebase-knowledge`, then writes a chained
  four-tour CodeTour series (orientation, architecture, core flow,
  conventions) into `.tours/`. Tour planning, flow tracing and step writing
  are its own references; the community skills do the scanning and the
  `.tour` writing.
- `prompts/` — `.prompt.md` slash commands (`/explain-code`,
  `/explain-and-review`, `/create-sb`, `/implement-sb`,
  `/create-implement-sb`, `/code-review-pr`, `/code-review-pr-fast`,
  `/tour-codebase`). Prompt files are Copilot's format and are
  **repo-scoped**: Copilot reads them from `<repo>/.github/prompts/`. VS Code
  additionally reads a user-profile copy, which is why the slash commands
  appear there without seeding a repo. The installer covers the two agents
  that read neither — JetBrains Copilot gets a generated skill per prompt,
  Claude gets a generated `~/.claude/commands/<stem>.md`. See
  [Where each prompt lands](#where-each-prompt-lands).
- `install.py` — installer for macOS, Linux and Windows/Git Bash
  (Python >= 3.8, stdlib only). Also bootstraps the CLI-installed externals
  (see [External skills](#external-skills-installed-by-their-own-cli)) —
  today that is `graphify`.

`explain-logic`, `soundboarding`, `investigate-issue` and `code-review-pr`
each end a run by
writing a CodeTour file into `.tours/` in the repo they worked on (chaining to
the community `code-tour` skill), skipping only trivial single-file cases.
`tour-codebase` is the one whose tours *are* the output — a chained series
rather than a single file. The
[`git`](../git/README.md) tool keeps `.tours/` out of every repository, and
`vsls-contrib.codetour` in [`vscode/extensions.txt`](../vscode/extensions.txt)
opens the files.

## Install

```bash
python3 install.py --target claude    # home: symlinks into ~/.claude/skills
python3 install.py --target copilot   # work: copies into ~/.copilot/skills
python3 install.py --target both
python3 install.py                    # interactive: pick target + items
python3 install.py --status                      # what is installed where + conflicts
python3 install.py --uninstall caveman --target copilot
python3 install.py --uninstall prompt:create-sb --target copilot
```

Repo scope — seeds `<repo>/.github/skills` and `<repo>/.github/prompts`, the
only scope JetBrains Copilot reads prompt files from:

```bash
python3 install.py --repo .                 # seed the repo you are standing in
python3 install.py --repo . --skills-only   # our skills + prompts, no third-party
python3 install.py --repo . --status        # what a project already carries
python3 install.py --repo . --uninstall prompt:create-sb
python3 install.py --target copilot --repo .   # personal + repo in one run
```

`--repo` writes copies only (never symlinks) and seeds `.github/` only —
`.claude/skills` and `.agents/skills` workspace scopes are left alone.

Flags: `--dry-run` (print planned actions), `--skills-only` (skip the
community-skill fetch — offline or behind a proxy), `--upgrade` (upgrade
external CLIs before refreshing their skills), `--force` (bypass unknown-name
checks on uninstall).

Interactive runs (no flags) show an item picker: toggle individual skills,
prompt files, and community skills by number, `a` for all, enter to
confirm. Flag runs install custom skills, prompts, and the default community set; cherry-picks are interactive-only. Interactive picker tags items
as `[installed]`, `[update]`, or `[conflict]`.

Community skills are fetched into `~/.agent-skills-cache/` and installed/updated
in place (missing = install, present = update, unchanged = up to date):

**Default (both targets, unless noted):**
- From `github/awesome-copilot`: code-tour, acquire-codebase-knowledge,
  context-map, architecture-blueprint-generator, add-educational-comments.
- From `juliusbrussee/caveman`: caveman terse-output skill (Copilot only; Claude
  uses the caveman plugin). explain-logic points at it for terse mode.
- From `addyosmani/agent-skills`: debugging-and-error-recovery (Copilot only;
  Claude uses superpowers:systematic-debugging). investigate-issue chains it
  when present.

**Cherry-picks (interactive mode only, default unchecked):**
- From `addyosmani/agent-skills`: observability-and-instrumentation,
  ci-cd-and-automation, security-and-hardening, deprecation-and-migration.
- From `anthropics/skills`: pdf, docx, pptx, xlsx.

`./install.py install agent-skills` from the repo root runs the custom-skill
install (no community fetch) as part of normal dotfiles setup — Claude only on
macOS/Linux, **both** Claude and Copilot on Windows (Git Bash).

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
   interactive picker (recommended: it also offers the community skills and
   the VS Code prompt files).
5. `python install.py --status` — verify new installs.
6. If the proxy blocks the clone, follow the printed ZIP fallback, or use
   `--skills-only`.

Step 4 also installs `graphifyy` from PyPI so the `graphify` skill has its
CLI — with `uv` or `pipx` if either is on the box, otherwise plain
`pip install --user`. If the proxy blocks PyPI,
the run prints the manual command and carries on without it — and
`--skills-only` skips it outright. A `graphify` skill without its CLI is
inert, and `--status` says so.

From the repo root, `python install.py install agent-skills` does steps 1–4
for the custom skills only.

**Symlinks on Windows** need Developer Mode or an admin shell. Without them the
installer detects this up front, prints `symlinks unsupported in <dir> —
installing copies`, and installs copies to both targets instead. Copies are
snapshots: **re-run the installer after editing a skill** to refresh them.
`--status` flags any leftover `<skill>.bak` directory from an older run — delete
those, the agents load them as extra skills.

Paths on Windows resolve under `%USERPROFILE%`: `~/.claude/skills`,
`~/.copilot/skills`, and `%APPDATA%\Code\User\prompts`. Repo scope resolves
to `<repo>\.github\skills` and `<repo>\.github\prompts`.

Team distribution per repo: `python install.py --repo <path>`, then PR the
`.github/` additions. Two things to check before committing them — the three
SB prompts hardcode `SOUNDBOARD_DIR: /c/dev/projects/wr/soundboard`, which is
a personal machine path, and a team repo may already own a prompt file of the
same name (`--dry-run` shows `updated` when a seed would overwrite one). To
keep a seed local instead, `echo .github/ >> .git/info/exclude` — per-repo and
invisible to teammates. Do not add these paths to the global
[`git/ignore`](../git/ignore): `.github/prompts/` is GitHub's own mechanism
for team sharing, and a global rule would suppress intentional additions
everywhere.

## Where each prompt lands

No agent reads every format, so one `prompts/*.prompt.md` is installed three
ways. All three are personal scope — they reach every project with no
per-repository seeding.

| Destination | Serves | Spelling |
| --- | --- | --- |
| VS Code user prompts dir | Copilot in VS Code | `/create-sb` |
| `~/.copilot/skills/<stem>/SKILL.md` (generated) | Copilot in JetBrains | `/skill:create-sb` |
| `~/.claude/commands/<stem>.md` (generated) | Claude in VS Code and JetBrains | `/create-sb` |
| `<repo>/.github/prompts/` (`--repo` only) | Copilot in JetBrains, that repo, shareable | `/create-sb` |

Both generated forms carry the prompt body verbatim and end with a
`Generated from prompts/<file>` marker — derived, never edited by hand.
Re-running the installer refreshes them. The Claude form drops the
Copilot-only `mode: agent` key and appends `My request: $ARGUMENTS`, so text
typed after the command reaches the prompt.

**A prompt named after a skill generates neither.** `code-review-pr`,
`code-review-pr-fast` and `tour-codebase` exist in both `skills/` and
`prompts/`; the skill already owns `~/.copilot/skills/<name>/` and answers to
`/<name>` in Claude, so generating over it would replace the real `SKILL.md`
with the prompt stub. Those three install as prompt files only, and
`--status` reports the generator as `skipped (real skill of same name)`.
The result is one spelling per agent:

| | VS Code | JetBrains |
| --- | --- | --- |
| Copilot | `/code-review-pr` (prompt file) | `/skill:code-review-pr` (skill) |
| Claude | `/code-review-pr` (skill) | `/code-review-pr` (skill) |

Remove a generated command with `--uninstall prompt:<stem> --target claude`.

## JetBrains (IntelliJ / PyCharm / GoLand)

Copilot reads the two customization kinds from different scopes:

| Kind | Personal scope | Repo scope | JetBrains |
| --- | --- | --- | --- |
| Skills (`SKILL.md`) | `~/.copilot/skills` | `.github/skills/` | both work |
| Prompt files (`.prompt.md`) | VS Code profile only | `.github/prompts/` | repo scope only |

Prompt files have no personal scope outside VS Code — JetBrains drives its
chat through the Copilot CLI harness, which reads no global prompts
directory. A bare `/create-sb` therefore only exists in a repo that has been
seeded, which is per-project by construction.

To get the same commands in **every** project, `--target copilot` also
generates one skill per prompt file into `~/.copilot/skills/<stem>/SKILL.md`,
carrying the prompt body verbatim plus a description that triggers on the
command name. Skills are personal scope, so those reach every project with no
seeding — except for the three prompts that share a name with a real skill,
which need no generated copy. JetBrains namespaces them, so you type:

| | VS Code | JetBrains, any project |
| --- | --- | --- |
| Soundboarding | `/create-sb LISA-110278.md` | `/skill:create-sb LISA-110278.md` |
| Explain | `/explain-code PR #142` | `/skill:explain-code PR #142` |

The generated skills are derived, never edited by hand — each ends with a
`Generated from prompts/<file>` marker, and re-running the installer
refreshes them after a prompt changes. `--status` lists them as
`custom (from prompt)`; `--uninstall <stem>` removes one.

Note that the filter text differs: typing `/create-s` matches nothing,
because the skill picker filters on the namespaced name. Type `/skill:` to
list everything, and remember that skills still trigger from their
`description` in plain English.

Setup checklist:

1. GitHub Copilot plugin installed from the JetBrains Marketplace, up to
   date, signed in.
2. **Settings → Languages & Frameworks → GitHub Copilot → Chat → Agent** —
   enable agent mode. Restart the IDE if the toggle has just appeared.
3. `python install.py --target copilot --skills-only`.
4. Reopen the IDE. In agent-mode chat type `/skill:` — the seven custom
   skills and the five generated from prompts should all list.
5. Optional, per repo: `python install.py --repo .` also seeds
   `.github/prompts/`, which restores the bare `/create-sb` spelling in that
   project and shares both with teammates.

Nothing shows up: confirm chat is in agent mode, that the plugin is current,
and that `install.py --status` lists the skills under `~/.copilot/skills`.
For the repo-scoped spelling, check the files are at
`<project root>/.github/prompts/` — the folder open in the IDE, not a
submodule — and that their frontmatter says `mode: agent`.

One caveat: `${selection}` in `explain-code.prompt.md` and
`explain-and-review.prompt.md` is a VS Code prompt variable and is not
guaranteed to expand in JetBrains. Both prompts already fall back to asking
which branch, PR, or file you mean.

## Usage

Per-skill guides with copy-paste examples for VS Code, JetBrains IDEs, and
Claude Code:

- [explain-logic](skills/explain-logic/USAGE.md)
- [soundboarding](skills/soundboarding/USAGE.md)
- [interview-prep](skills/interview-prep/USAGE.md)
- [investigate-issue](skills/investigate-issue/USAGE.md)
- [code-review-pr](skills/code-review-pr/USAGE.md)
- [code-review-pr-fast](skills/code-review-pr-fast/USAGE.md)
- [tour-codebase](skills/tour-codebase/USAGE.md)
- [community skills](docs/community-skills.md) (code-tour, caveman, ...)

## Tests

```bash
cd agent-skills && python3 -m unittest test_install -v
```
