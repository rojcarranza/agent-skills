# PR brief

Loaded when the target is a pull request or a branch (SKILL.md Step 1,
priority 1). Comprehension only: the brief says what the change does and how
the run differs, never what is wrong with it or how to improve it. That is
`roj-code-review-pr`.

## Contents

- Where it goes
- Run order
- brief.md template
- Caps and rules
- Flow diff
- Evidence tiers and the claims check
- No flow change
- Check script
- brief.html
- Chat contract

## Where it goes

- A PR: `<ROOT>/.pr-review/pr-<n>/brief.md` and `brief.html`. A branch:
  `<ROOT>/.pr-review/branch-<slug>/`, the slug being the branch name in
  lower case with every run of other characters turned into `-`.
- `ROOT` is `git rev-parse --show-toplevel`. Absolute paths only, never a
  home-directory shortcut. On Windows Git Bash, if a read fails on `/c/...`,
  retry once with `cygpath -m "$ROOT"`, then once with the IDE's
  project-relative path.
- **Read gate before any write.** Read `README*` or the main manifest by
  absolute path first. If all three path forms fail, stop and write nothing:
  print the failing path, the tool's message verbatim and three checks (chat is
  in agent mode, the IDE project root is the repository root, the agent may
  read the workspace).
- Writes only under `<ROOT>/.pr-review/`. Commands beyond file reads: `git`,
  the read-only `graphify` queries, and `python3` (or `python`) running the
  two check scripts from a scratch file outside the repository.
- `.pr-review/` is personal and stays out of Git. Run
  `git check-ignore -q .pr-review/`; when it is not ignored, print this line
  for the reader and never run it or edit `.gitignore`:

```
echo '.pr-review/' >> .git/info/exclude
```

## Run order

One pass, no second investigation. The brief is built from the evidence of
Steps 1 and 2.

1. Resolve the target (Step 1). Keep the facts for the header: the head SHA
   (first 12), `<base>`, the merge base (first 7), today's date, the target
   branch. A Bitbucket Data Center PR is fetched by ref without a checkout
   and every file is read as `git show <head>:<path>`.
2. Read the context (Step 2) and keep a ledger of every file read.
3. Write `brief.md` from the template below.
4. Run the check script on it; repair what it reports in the Markdown.
5. Write `brief.html` from `brief.md` (below), then run the page check.
6. Print the chat summary.

## brief.md template

Section headings and their order are the contract.

````markdown
# PR brief: <title> (PR <n>)

> Built from head `<sha12>` vs `<base>` @ `<merge-base7>` (<date>, target `<branch>`). Every claim cites `path:line`.
> Intent: <pasted PR text | commit messages | none given>.

## 1. What this PR does

<At most 6 lines, from the diff.>

**Claims check.** <Only when the diff clearly differs from the stated intent.>

## 2. Where it sits

<The areas the change touches, from the paths of the changed files.>

## 3. Flow diff

```mermaid
sequenceDiagram
  ...
```

- <step> · `path:line` · <fact>

## 4. Files

| File | Role | Change |
| --- | --- | --- |

## 5. Walkthrough

## 6. Reading order

## 7. Questions for the author, and what was not checked

1. [?] <question> (`path:line`)

Not checked: <by role>.
````

## Caps and rules

- **Title.** The PR title when the user pasted it, else the subject of the
  first commit on the branch.
- **Section 1.** At most 6 lines, built from the diff, never from the PR text
  or the commit messages: what the change does, how big it is (files, lines
  added and removed) and what it is made of.
- **Intent source.** The header names where the intent came from: the PR text
  the user pasted, the commit messages, or `none given`. Never invent PR text.
  A Bitbucket Data Center PR has no title or description without REST: do not
  stop to ask, use the commit messages and say `commit messages (no PR text
  pasted)`; the chat summary offers to rerun with the pasted text.
- **Section 2.** Name each area the change touches (a directory or module),
  what it holds and what calls into it, from the callers and tests already
  traced.
- **Section 3.** The flow diff below, then the proof list: one item per
  diagram step, `<step> · path:line · fact`, where `<step>` is the message
  number of the diagram or the word `removed`. A payload diff (a `diff` block
  of at most 12 lines headed with its step) only when a request, event,
  model, schema or environment variable changed.
- **Section 4.** One row per changed file; `Change` is `new`, `changed`,
  `removed` or `renamed`. Over 25 files: group the rest by directory with
  counts, and say lockfiles and generated output were collapsed.
- **Section 5.** The steps of the flow in run order, using the Concept, Code,
  Why method of Step 3. Each step has a `path:line`, what runs, why it is
  there and what breaks without it; quotes of at most 5 lines. A diff over 100
  lines: the flow first, then the zoom offer of Step 4. A diff that touches
  CI, CD or infrastructure ends the section with its runtime impact.
- **Section 6.** At most 8 entries: `path:line`, why read it now.
- **Section 7.** Up to 5 `[?]` questions, each a thing the code cannot
  answer (an intent, a caller outside the repository, a version, a config
  value). Never a question that doubts the code (`is that intended?`,
  `should it raise?`): that is a review finding.
  Then `Not checked:`, by role only (`a live Data Center server`, `the
  deploy job`), never a host name or a credential.
- **No defect talk and no improvement advice anywhere**, not even softened.
  An outcome that looks wrong is stated as plain behaviour, in the flow where
  it happens (`returns None after three failed attempts`), with none of
  `bug`, `risk`, `should`, `missing`, `unsafe` or `is that intended`; judging
  it is `roj-code-review-pr`'s job. A mismatch between intent and diff is a
  fact for the claims check.
- Every `path:line` exists at the head, every diagram node is something
  read, every edge a call or message read. A line the diff removed has no
  place at the head: cite the head file and the line where the removal shows,
  and for a deleted file give the path in the files table with no `line`.
- A brief of a PR the reader has seen before is rewritten whole, not patched.

## Flow diff

The syntax is in `references/mermaid.md` (*Flow diff*): `rect` blocks, the
`+` `~` `-` tags, the tier word at the end of each label. In short:

- One `sequenceDiagram` of only the changed steps, in run order, with
  `autonumber`. At most 12 steps and 5 participants. One `rect` block per
  class that occurs: `rgba(0,180,0,0.12)` new, `rgba(255,190,0,0.15)`
  changed, `rgba(220,0,0,0.12)` removed.
- Tags carry the meaning when a host ignores colour: `+` new, `~` changed,
  `-` removed. A removed step is a `Note over` inside the red block, not a
  numbered message.
- More changed steps than fit: draw the 12 on the main path and name the rest
  in one line under the diagram (`Further changed steps not drawn: ...`).
- A change that moves modules or files without altering a runtime path: one
  `flowchart LR` with a `Before` and an `After` subgraph instead. Infra
  changes (Bamboo, Helm, Docker, scripts): a `flowchart LR` of the pipeline or
  render order, as `references/mermaid.md` says.
- No emoji in a label. Other diagram types are not used in a brief.

## Evidence tiers and the claims check

Every step and every proof item carries a tier, and a tier is never upgraded:

| Tier | Meaning |
| --- | --- |
| `read` | the code that does it was read, at `path:line` |
| `inferred` | follows from code read, but the call or the wiring is not visible (a framework, a registration, a config value) |
| `ran` | a command ran and its output was seen; this skill runs only `git` and the check scripts, so `ran` is rare |

The **claims check** compares the stated intent with the diff and prints a
line only when they clearly differ: `The commit message says "<quote>"; the
diff does <what> (`path:line`).` Both sides are cited. When they agree, or
when the difference is a matter of reading, print nothing.

## No flow change

A PR that only changes documentation, tests, comments or formatting has no
flow to draw. Section 3 is one line, `**No flow change.** <what changed>`,
with no diagram and no proof list; the files table stays; sections 5 and 6 are
short (what each file group says or checks, where to start). A PR that mixes
a doc change with a code change draws the flow of the code change only.

## Check script

Save to a scratch file outside the repository and run with `python3` (or
`python` on Windows). `--rev` is the head SHA of a PR that is not checked out;
without it files are read from the working tree.

```
python3 check-brief.py --rev <head> <ROOT> <ROOT>/.pr-review/pr-<n>/brief.md
```

It fails when an anchor does not resolve, a section is missing or out of
order, the header is missing, a diagram breaks a cap, an in-block step has no
tag or tier, or a no-flow-change brief carries a diagram. `check-brief.py`:

```python
import re, subprocess, sys
from pathlib import Path

args = sys.argv[1:]
rev = None
if args[:1] == ["--rev"]:
    rev, args = args[1], args[2:]
root, brief = Path(args[0]), Path(args[1])
text = brief.read_text(encoding="utf-8")
ANCHOR = re.compile(r"`([\w./@+-]+):(\d+)(?:-(\d+))?`(?:-`(\d+)`)?")
OPEN = ("rect", "alt", "opt", "loop", "par", "critical", "break")
bad = []

def length(path):
    if rev:
        run = subprocess.run(["git", "-C", str(root), "show", f"{rev}:{path}"], capture_output=True)
        return len(run.stdout.decode("utf-8", "replace").splitlines()) if run.returncode == 0 else 0
    f = root / path
    return len(f.read_text(encoding="utf-8", errors="replace").splitlines()) if f.is_file() else 0

ok = 0
for m in ANCHOR.finditer(text):
    path, start = m.group(1), int(m.group(2))
    end = int(m.group(3) or m.group(4) or start)
    if ("." not in path and "/" not in path) or re.fullmatch(r"[\d.]+", path):
        continue
    n = length(path)
    if start < 1 or end < start or end > n:
        bad.append(f"bad anchor {path}:{start}-{end} (file has {n} lines)")
    else:
        ok += 1

if re.findall(r"^## (\d)\. ", text, re.M) != list("1234567"):
    bad.append("sections 1 to 7 are missing or out of order")
if not re.search(r"^> Built from head `[0-9a-f]{12}` vs ", text, re.M):
    bad.append("header line missing")
blocks = re.findall(r"^```mermaid\n(.*?)^```$", text, re.M | re.S)
if "**No flow change.**" in text:
    if blocks:
        bad.append("a no-flow-change brief has a diagram")
elif len(blocks) != 1:
    bad.append(f"expected one diagram, found {len(blocks)}")
for block in blocks:
    lines = [ln.strip() for ln in block.splitlines() if ln.strip()]
    if re.search("[\U0001F000-\U0001FAFF☀-➿]", block):
        bad.append("emoji in a diagram")
    if lines[0].startswith("flowchart"):
        continue
    if lines[0] != "sequenceDiagram":
        bad.append(f"diagram type {lines[0]} is not allowed in a brief")
        continue
    stack, steps, rects = [], 0, 0
    people = sum(bool(re.match(r"(participant|actor) ", ln)) for ln in lines)
    for ln in lines[1:]:
        word = ln.split(" ")[0]
        if word in OPEN:
            stack.append(word)
            rects += word == "rect"
        elif word == "end" and stack:
            stack.pop()
        elif re.match(r"\S+\s*-{1,2}>>?\s*\S+\s*:", ln) or ln.startswith("Note "):
            steps += 1
            if "rect" in stack and not (re.search(r":\s*[+~-]\s", ln) and re.search(r",\s*(read|inferred|ran)$", ln)):
                bad.append(f"step needs a +, ~ or - tag and a tier word: {ln}")
    if people > 5:
        bad.append(f"{people} participants, the cap is 5")
    if steps > 12:
        bad.append(f"{steps} steps, the cap is 12")
    if not rects:
        bad.append("flow diff has no rect block")
print("\n".join(bad) or f"brief ok: {ok} anchors, {len(blocks)} diagram")
sys.exit(1 if bad else 0)
```

The Mermaid checklist of `references/mermaid.md` still applies; the Node
parse is optional and needs the reader's approval.

## brief.html

Built from `brief.md`, never from a second look at the code, with
`references/html-page.md`: the skeleton, the mapping and its check script.
For a brief: one `<section class="doc" id="brief">`, the title as `<h2>`, the
two header lines as `<p class="stamp">`, one card per `## N.` section with the
id `brief-<N>`, a sidebar entry per card, `PR <n>` as the sidebar heading.
Run the page check:

```
python3 check-html.py <ROOT>/.pr-review/pr-<n> brief.html
```

The page holds exactly the Markdown's diagrams, anchors and headings. The
`rect` colours are drawn by the pinned Mermaid; the `+` `~` `-` tags read
without them.

## Chat contract

At most 12 lines, no diagram (chat panels are not known to render Mermaid).
Count every printed line, blank lines and the ignore line included: one line
per item, no bold headings, no findings and no behaviour details (those are in
the brief), and drop the optional items first when the count runs over. Items
2 and 9 are never dropped, and 9 always prints both command forms:

1. What the PR does, in one or two sentences, and its size.
2. The absolute path of `brief.html` and how to open it: `lavish-axi <path>`
   printed (never run) only when `command -v lavish-axi` finds it, otherwise
   the browser (`open`, `xdg-open`, `start`, or the IDE's Open in Browser).
   The Markdown opens in the IDE preview: VS Code built in, JetBrains with the
   *Mermaid* plugin ticked under Settings, Plugins.
3. The intent source, and for a Data Center PR the offer to rerun with the
   pasted PR text.
4. The claims-check line, when there is one.
5. The ignore line when `.pr-review/` is not ignored (printed, not run).
6. The `[?]` questions, at most 3, numbered.
7. `Reference unavailable: <name>` for any reference that could not be opened,
   and the Graph line of SKILL.md.
8. The zoom offer for a large diff, and the one-line tour offer.
9. The next step: `/skill:roj-code-review-pr PR <n>` in JetBrains,
   `/roj-code-review-pr PR <n>` in VS Code, then
   `roj-review-pr-comment PR <n>` for Bitbucket comments. A PR review adds
   non-blocking suggestions after the defects; say `no suggestions` for
   defects only.
