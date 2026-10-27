# PR comments

The one format for a finding written as a pull request comment. Two places
use it and must agree: the `### Comments to paste` section that
`roj-code-review-pr` ends a PR review with (in `review.md` and in chat), and
the draft `roj-review-pr-comment` prints and posts. Nothing here posts
anything; `roj-review-pr-comment` posts, and only on request.

## Voice

The reader is the PR author, who has not seen the review. Write to them
("you", imperative fix), one comment per finding, and make it stand alone:

1. what is wrong, in one sentence that names the code;
2. when it fails: the concrete input or state and the wrong outcome;
3. the fix: the change, and when it replaces the anchored line or a few
   lines, the improved code in a plain fenced block (no Bitbucket suggestion
   block exists). A fix that needs several files says so in words.

No attribution, no praise, no "I think" for a Confirmed finding, no
severity words other than Blocker, Major, Minor, Nit.

## Anchor

Each comment is headed by `` `path:line` `` on the PR head: the line number
in the **new** file of an added (`+`) or context line inside a hunk. Before
writing it, read that line with `git show <head>:<path>` and check the quoted
code is on it; a line that drifted is the commonest error. A finding with no
commentable line (a deleted line, a criterion no hunk satisfies) has no
inline comment and goes in the summary.

## Comment shapes

A defect:

```text
🟠 **Major** · Probable - <defect>.

Fails when: <scenario>.

Fix: <change>.
```

Markers: 🔴 **Blocker**, 🟠 **Major**, 🟡 **Minor**, 🔵 **Nit**, then the
confidence (Confirmed or Probable). Every comment has a `Fix:` line.

A suggestion (non-blocking, never a Bitbucket task or a blocker comment):

```text
💡 **Suggestion (non-blocking)** · Reuse · Confirmed - <what>.

Cost of leaving it: <sentence>.

Instead: <existing helper path:line, or a plain fenced block of at most 6 lines>.
```

## Layout

Defects first, worst first. Defects take the inline slots first, up to 15;
the rest go in the summary. Suggestions follow: at most 5 inline, in the slots
the defects left, never more than 15 inline in all; the rest, with every
suggestion that has no line, go in the summary under `Further suggestions`.
A suggestion never displaces a defect.

````
### Comments to paste

Summary comment:
```text
<2-4 lines: what this PR does>

<n> findings: <x> 🔴 · <y> 🟠 · <z> 🟡 · <w> 🔵 · <s> suggestions

<findings with no line, one per line as `path:line` - summary>

Further suggestions:
<suggestions with no inline slot, one per line as `path:line` - summary>
```

Inline comments - defects (<n>):

`app/uploader.py:22`
```text
<defect comment>
```

Inline comments - suggestions (<n>):

`app/cli.py:9`
```text
<suggestion comment>
```
````

A class with nothing in it says `none`. No findings at all: the summary reads
"No findings." and the two inline headings say `none`. With suggestions off
(`no suggestions`) the suggestions heading, the `· <s> suggestions` count and
`Further suggestions` are left out and the one inline heading reads `Inline
comments (<n>)`. Each comment is its own fenced block so it pastes into
Bitbucket as written.
