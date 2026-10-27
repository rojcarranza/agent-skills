# roj-onboard-repo - usage

Turns a repository you have never worked on into a written onboarding guide in
`.onboarding/`: Mermaid diagrams of the architecture and one core flow, a code
walkthrough with `path:line` anchors, a reading order, how to run and test it,
and a page on reviewing a colleague's PR in that repo.

The guide is the output, in two forms of the same content: Markdown files you
can open in the IDE preview and review in Git-style diffs, and one
self-contained `index.html` with navigation, cards, tables and rendered
diagrams. Chat carries a short handoff - the explanation itself lives in the
files.

## When to use

- Joining a project, inheriting a service, or about to review PRs in a
  repository you did not write.
- Coming back to something you have not touched in months.
- Handing a repository to someone else and wanting the explanation to outlive
  the conversation.

Not for a single PR, branch, file or function - that is `roj-explain-logic`. Not
for finding defects - that is `roj-code-review-pr`.

## Invoking

Plain English works everywhere - the skill triggers from its description:

    onboard me to this repo
    tour this codebase
    teach me how this project works
    where do I start in this repo
    draw the architecture and explain the code
    onboard me, the deploy flow            # names the flow to walk through
    onboard me, architecture only          # README map and one flow
    onboard me and leave CodeTour files    # also writes one tour (VS Code only)

Explicit invocation differs per agent:

| Agent | Command |
| --- | --- |
| Copilot, VS Code | `/roj-onboard-repo` |
| Copilot, JetBrains | `/skill:roj-onboard-repo` |

Both are personal scope once installed, so they reach every project with no
per-repository seeding.

## What it does

1. Resolves the repository root and **reads your README or manifest by
   absolute path first**. If the read fails it stops, writes nothing and
   tells you which path failed and the tool's message - no guessed output.
2. Asks which workspace only when the repository is a monorepo.
3. Maps the repository into an evidence ledger of files actually read, with
   Git history for hotspots and a graphify graph when one exists.
4. Picks the one flow worth walking - the one you named, else the one the
   README exercises, else the most tested, else the deepest - and says which
   rule chose it. There is no plan checkpoint.
5. Writes the Markdown guide, then builds `index.html` from it with no second
   investigation.
6. Checks every `path:line` exists, every diagram follows the Mermaid rules,
   and the HTML holds the same diagrams, anchors and headings as the Markdown,
   before reporting.

## Output

`<repo>/.onboarding/`:

| File | Answers |
| --- | --- |
| `index.html` | the whole guide on one page: sidebar over README, flows, modules and PR review, cards, tables, light and dark themes, rendered diagrams, every `path:line` as a visible code reference |
| `README.md` | what is this, how is it built, where do I start. System map diagram, core flow diagram, run/test table, reading order, walkthrough, glossary, open questions |
| `flows/NN-<slug>.md` | what happens, step by step, when this runs. One to three flows |
| `reviewing-prs.md` | a colleague's PR touches X: what do I read and check. Area map, hotspots, silent seams, questions, how to run a test |
| `modules.md` | what each module owns and what depends on it |

The Markdown is the checked source; `index.html` is generated from it and a
check fails if the two diverge. Every file carries the commit it was built from and cites `path:line` for each
claim; what the code does not settle is marked `[?]`.

`.onboarding/` is personal. The run checks whether Git ignores it and, when it
does not, prints

    echo '.onboarding/' >> .git/info/exclude

for you to run. The skill never edits a repository's `.gitignore`.

## Opening the guide

Start with `index.html`, not chat:

- **Lavish** - when `lavish-axi` is on your `PATH`, the run prints
  `lavish-axi <path>/.onboarding/index.html`; run it to read the page and
  annotate any claim you doubt.
- **A browser** - otherwise open the file directly. The page needs network
  only for the Mermaid script, pinned to one version on `cdn.jsdelivr.net`. If
  that is blocked or offline, the guide still reads in full and each diagram
  shows its Mermaid source with a one-line notice.

The Markdown opens in the IDE preview:

- **VS Code** - the built-in Markdown preview renders Mermaid since 1.121. If
  you installed `bierner.markdown-mermaid` and the diagrams are blank, remove
  it.
- **JetBrains** - open the file and use the Markdown preview. If a diagram
  shows as text, tick *Mermaid* under Settings, Plugins, Installed. Android
  Studio has no Mermaid preview.
- **GitHub or GitLab** - renders Mermaid natively.
- **Anywhere else** - paste a block into <https://mermaid.live>.

If you want the page in a browser from the IDE: right-click `index.html`,
Open in Browser.

Bitbucket Data Center renders no Mermaid, so diagrams stay local and PR
comments stay plain text.

## Reviewing a colleague's PR afterwards

1. Read `.onboarding/reviewing-prs.md`: it maps changed paths to areas and
   flows, lists the hotspots and the silent seams to watch.
2. Understand the PR with that map: `/skill:roj-explain-logic PR <n>` in
   JetBrains, `/roj-explain-logic PR <n>` in VS Code.
3. Then `roj-code-review-pr PR <n> improve`, and `roj-review-pr-comment PR <n>
   improve` for Bitbucket comments. `improve` adds non-blocking suggestions
   after the defects; leave it off for defects only.

## CodeTour

No tours by default. Ask for them ("and leave CodeTour files") or say yes to
the closing offer, and the run writes one tour of the core flow into `.tours/`
from the guide's own anchors. CodeTour needs the VS Code extension; JetBrains
reads the guide instead. `.tours/` is in the global Git ignore.

## If a read fails

The run stops after its first read when your README and manifest cannot be
opened by absolute path. It prints the path, the tool's message and three
checks: chat is in agent mode, the IDE project root is the repository root,
the agent may read the workspace. Fix the cause and run again.

A file in the skill's own `references/` that cannot be opened does not stop
the run: it continues from `SKILL.md` and the handoff lists `Reference
unavailable: <name>`.

## Customising

The detail lives in `references/` as prose checklists - edit them directly:

- `templates.md` - the file skeletons, budgets and the anchor check script.
- `walkthrough-writing.md` - what a walkthrough step says, quoting limits,
  anti-patterns.
- `flow-tracing.md` - how the core flow is picked, and entry-point signals per
  stack (Java/Spring, Python, Go, Node/TypeScript, Bash, Bamboo,
  Docker/Kubernetes/Helm).
- `html-page.md` - the `index.html` contract, page skeleton and the check
  script that compares it with the Markdown. Shared with `roj-explain-logic`
  (its PR brief page): edit it here, then run `python3 tools/sync_shared.py`.
- `mermaid.md` - the diagram subset, syntax, pitfalls, the optional parse
  check, viewing. Shared: edit it here, then run
  `python3 tools/sync_shared.py`.
- `tours.md` - the optional CodeTour.

## Re-running

The guide is a snapshot: line numbers drift as the branch moves. Re-run to
refresh. An existing `.onboarding/` is never silently overwritten - the run
asks once.

## Install

Copilot only. Install it with the rest of this repo: see
[Install](../../README.md#install) in the README, and
[docs/installer.md](../../docs/installer.md) for flags, `--status` and the
work VDI.

The community skills `acquire-codebase-knowledge` and `code-tour` are not
required. An existing `docs/codebase/` is read as a lead; `code-tour` is used
by name only for the optional tour.
