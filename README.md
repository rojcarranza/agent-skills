# agent-skills

Custom agent skills usable by GitHub Copilot (VS Code and JetBrains IDEs) and
Claude Code, plus an installer. One `SKILL.md` format serves every platform.

## Layout

- `skills/roj-explain-logic/` — guided code-comprehension walkthroughs
  (PR/branch diffs, files, functions) with language lenses.
- `skills/roj-soundboarding/` — story → SB document → task-by-task
  implementation workflow (bundled `SB-template.md` + examples).
- `skills/roj-interview-prep/` — DevOps interview doc generator from a CV
  (vault-aware, bundled calibration references).
- `skills/roj-investigate-issue/` — problem `.md` in, validated root cause +
  fix-steps `-investigation.md` out (Bamboo plans/agents, Java, Python,
  Bash, Go, Docker, k8s).
- `skills/roj-code-review-pr/` — feature-branch review before or after a PR:
  change summary, severity/confidence-tagged findings, `-review.md` report
  and a tour. Rules split into always-loaded method + cross-cutting, and
  language/platform lenses (Java/Maven, Python, Bash, Go, Bamboo, k8s, Helm,
  Docker) loaded from the diff. Git-only — no PR host API.
- `skills/roj-code-review-pr-fast/` — chat-only short pass over the same diff,
  `git` calls only, no files written. Reads its method from
  `roj-code-review-pr` when installed.
- `skills/roj-review-pr-comment/` — reviews an open GitHub PR with the
  `roj-code-review-pr` method and posts one `COMMENT` review with inline
  comments via `gh`. Triggered automatically by the `claude` tool's
  `pr_review_hook.py` when Claude opens a PR in an allowlisted repo (see
  [claude/README.md](../claude/README.md#pr-auto-review)); also runnable by
  hand. The only custom skill that writes to the PR host.
- `skills/roj-tour-codebase/` — onboarding into a repository you do not know:
  delegates discovery to `acquire-codebase-knowledge`, then writes a chained
  four-tour CodeTour series (orientation, architecture, core flow,
  conventions) into `.tours/`. Tour planning, flow tracing and step writing
  are its own references; the community skills do the scanning and the
  `.tour` writing.
- `skills/roj-explain-feature-changes/` — explains your own feature branch
  against `develop` or `main`: traced before/after behavior, intent labelled
  confirmed / likely / unknown, a `-changes.md` report with PR-ready text and
  per-change PR comments, and an optional tour. Requires `code-tour` (see
  [Skill dependencies](#skill-dependencies)); it falls back inline when
  `context-map` or `write-pr-description` are absent.
- `prompts/` — workflow sources (`roj-explain-code`, `roj-explain-and-review`,
  `roj-create-sb`, `roj-implement-sb`, `roj-create-implement-sb`,
  `roj-code-review-pr`, `roj-code-review-pr-fast`, `roj-tour-codebase`,
  `roj-explain-feature-changes`). Copilot no longer reads `.prompt.md` files
  in either IDE, so none are installed: Copilot gets a generated skill per
  prompt, Claude a generated `~/.claude/commands/<stem>.md`. See
  [Where each prompt lands](#where-each-prompt-lands).
- `install.py` — installer for macOS, Linux and Windows/Git Bash
  (Python >= 3.8, stdlib only). Also bootstraps the CLI-installed externals
  (see [External skills](#external-skills-installed-by-their-own-cli)) —
  today that is `graphify`.

`roj-explain-logic`, `roj-soundboarding`, `roj-investigate-issue`, `roj-code-review-pr` and
`roj-explain-feature-changes` **offer** a CodeTour at the end of a run and write
one into `.tours/` only on a yes (chaining to the community `code-tour`
skill). A tour is a second generation pass over material the run already
produced, so it is opt-in; asking for one up front skips the confirmation.
`roj-tour-codebase` is the one whose tours *are* the output — a chained series
rather than a single file, built without asking, since that is the request.
The
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
python3 install.py --uninstall prompt:roj-create-sb --target copilot
```

Repo scope — seeds `<repo>/.github/skills`, shareable with the team:

```bash
python3 install.py --repo .                 # seed the repo you are standing in
python3 install.py --repo . --skills-only   # our skills + prompts, no third-party
python3 install.py --repo . --status        # what a project already carries
python3 install.py --repo . --uninstall prompt:roj-create-sb
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

`./install.py install agent-skills` from the repo root runs a flag install —
custom skills, default community skills and externals — as part of normal
dotfiles setup: Claude only on macOS/Linux, **both** Claude and Copilot on
Windows (Git Bash).

### Skill dependencies

`REQUIRES` in `install.py` lists the skills a custom skill calls. Installing
the skill installs its requirements to the same targets in every mode — flag,
interactive and `--repo`. An item unticked in the picker comes back with a
`(required by …)` log line.

| Skill | Requires |
| --- | --- |
| `roj-explain-feature-changes` | `code-tour` |
| `roj-review-pr-comment` | `roj-code-review-pr` |

`--skills-only` cannot fetch requirements; the run ends with a warning for
each one missing. `--status` lists missing requirements per target.
`--uninstall` of a requirement that an installed skill still needs warns,
then removes it. A test fails if a `REQUIRES` key stops matching a
directory under `skills/`, so a rename cannot silently drop dependencies.

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

From the repo root, `python install.py install agent-skills` does steps 1–4
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
prompts share a name with a real skill, and the converted stubs would shadow
it. Re-run the installer instead.

Team distribution per repo: `python install.py --repo <path>`, then PR the
`.github/` additions. Two things to check before committing them — the three
SB prompts hardcode `SOUNDBOARD_DIR: /c/dev/projects/wr/soundboard`, which is
a personal machine path, and a team repo may already own a skill of the
same name (`--dry-run` shows `updated` when a seed would overwrite one). To
keep a seed local instead, `echo .github/ >> .git/info/exclude` — per-repo and
invisible to teammates. Do not add these paths to the global
[`git/ignore`](../git/ignore): `.github/skills/` is GitHub's own mechanism
for team sharing, and a global rule would suppress intentional additions
everywhere.

## Where each prompt lands

Copilot dropped prompt files (`.prompt.md`) in both VS Code and JetBrains, and
Claude never read them, so each `prompts/*.prompt.md` is a source the
installer turns into two generated files. Both are personal scope — they
reach every project with no per-repository seeding.

| Destination | Serves |
| --- | --- |
| `~/.copilot/skills/<stem>/SKILL.md` (generated) | Copilot in VS Code and JetBrains |
| `~/.claude/commands/<stem>.md` (generated) | Claude in VS Code and JetBrains |
| `<repo>/.github/skills/<stem>/SKILL.md` (`--repo` only) | Copilot, that repo, shareable |

Both carry the prompt body verbatim and end with a `Generated from
prompts/<file>` marker — derived, never edited by hand. Re-running the
installer refreshes them, and deletes any `.prompt.md` copy an older install
left in the VS Code user prompts dir or `<repo>/.github/prompts/`. The Claude
form drops the Copilot-only `agent: agent` key and appends
`My request: $ARGUMENTS`, so text typed after the command reaches the prompt.

**A prompt named after a skill generates neither.** `roj-code-review-pr`,
`roj-code-review-pr-fast`, `roj-tour-codebase` and
`roj-explain-feature-changes` exist in both `skills/` and `prompts/`; the
skill already owns the name, so generating over it would replace the real
`SKILL.md` with the prompt stub. `--status` reports the generator as
`skipped (real skill of same name)`.

Spelling per agent:

| | VS Code | JetBrains |
| --- | --- | --- |
| Copilot | `/roj-create-sb` | `/skill:roj-create-sb` |
| Claude | `/roj-create-sb` | `/roj-create-sb` |

Remove a generated skill with `--uninstall <stem> --target copilot`, a
generated command with `--uninstall prompt:<stem> --target claude`.

### The roj- rename

Every custom skill and prompt carries a `roj-` prefix, so they sort together
and never collide with a community or plugin skill. Installs made before the
rename used bare names (`create-sb`, `explain-logic`, ...). Every install run
removes those leftovers — Copilot copies whose `SKILL.md` declares the old
name, Claude symlinks, generated Claude commands, and old `.prompt.md`
files — and logs each as `removed (renamed to roj-...)`. A skill of the same
bare name that the installer did not write is left alone.

## JetBrains (IntelliJ / PyCharm / GoLand)

Copilot reads skills from `~/.copilot/skills` (personal, every project) and
`<repo>/.github/skills/` (repo scope). JetBrains namespaces skills, so they
are typed as `/skill:<name>`:

| | VS Code | JetBrains, any project |
| --- | --- | --- |
| Soundboarding | `/roj-create-sb LISA-110278.md` | `/skill:roj-create-sb LISA-110278.md` |
| Explain | `/roj-explain-code PR #142` | `/skill:roj-explain-code PR #142` |

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
4. Reopen the IDE. In agent-mode chat type `/skill:roj-` — the nine custom
   skills and the five generated from prompts should all list.
5. Optional, per repo: `python install.py --repo .` seeds `.github/skills/`
   to share them with teammates.

Nothing shows up: confirm chat is in agent mode, that the plugin is current,
and that `install.py --status` lists the skills under `~/.copilot/skills`
with no `.prompt.md` warnings.

One caveat: `${selection}` in `roj-explain-code.prompt.md` and
`roj-explain-and-review.prompt.md` was a prompt-file variable and does not
expand in a skill. Both already fall back to asking which branch, PR, or file
you mean.

## Usage

Per-skill guides with copy-paste examples for VS Code, JetBrains IDEs, and
Claude Code:

- [roj-explain-logic](skills/roj-explain-logic/USAGE.md)
- [roj-soundboarding](skills/roj-soundboarding/USAGE.md)
- [roj-interview-prep](skills/roj-interview-prep/USAGE.md)
- [roj-investigate-issue](skills/roj-investigate-issue/USAGE.md)
- [roj-code-review-pr](skills/roj-code-review-pr/USAGE.md)
- [roj-code-review-pr-fast](skills/roj-code-review-pr-fast/USAGE.md)
- [roj-tour-codebase](skills/roj-tour-codebase/USAGE.md)
- [roj-explain-feature-changes](skills/roj-explain-feature-changes/USAGE.md)
- [community skills](docs/community-skills.md) (code-tour, caveman, ...)

## Tests

```bash
cd agent-skills && python3 -m unittest test_install -v
```
