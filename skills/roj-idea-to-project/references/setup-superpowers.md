# Phase 0: Superpowers setup

Read before running `scripts/check_superpowers.py`.

## Act on `status`

| `status` | Do |
|---|---|
| `ok` | Continue to phase 1. A `version_comparable: false` version (a commit SHA) is `ok`, not outdated. |
| `missing` | Explain (below), ask for a yes, run `next` in order, then the reload stop. |
| `disabled` | Same as `missing`, with the enable command in `next`. |
| `outdated` | Offer `next` (the update) with the same explanation and reload stop. On a no, continue and add `Superpowers <version> (older than 7.0.0)` under `## Constraints` in the brief. |
| `undetectable` | Look for `superpowers:brainstorming` in your own skill list. Listed: treat as `ok`. Not listed: treat as `missing` and use the Claude Code commands below. |

## Before asking for the yes

Say, in four short lines:

- **What:** the Superpowers plugin (obra/superpowers, MIT).
- **From where:** the marketplace named in `next`.
- **Why:** phases 2, 6 and 7 call `superpowers:brainstorming`,
  `superpowers:writing-plans` and `superpowers:subagent-driven-development`;
  there is no path through this workflow without them.
- **What changes:** a user-scope plugin install on this machine; nothing in
  the project folder.

Then one question: "Install it now?" with the recommendation yes.

## Install commands, in order

Claude Code:

1. `claude plugin install superpowers@claude-plugins-official`
2. Only if 1 fails because that marketplace is not available:
   `claude plugin marketplace add obra/superpowers-marketplace`, then
   `claude plugin install superpowers@superpowers-marketplace`

GitHub Copilot CLI:

1. `copilot plugin marketplace add obra/superpowers-marketplace`
2. `copilot plugin install superpowers@superpowers-marketplace`

Update (outdated): `claude plugin update superpowers@<marketplace>`, with the
marketplace taken from the installed `id`.

A marketplace entry that prints `Run this command now? [y/N]` cannot be
accepted from your shell (`-y` is ignored inside an agent session). Show the
command and ask the user to run it in their own terminal, then STOP.

## Reload stop

After any install, enable or update, say exactly:

> Run `/reload-plugins` in this session (Copilot CLI: exit and restart
> `copilot`), then tell me when it's done.

Then STOP. You cannot run `/reload-plugins`: it only runs when the user
types it. When the user confirms, run `scripts/check_superpowers.py` again
and continue only on exit 0.

## Install fails

Show the command's output verbatim (never paraphrase it), give the exact
command for the user to run in their own terminal, and STOP. Never start
phase 1 without Superpowers.

## Unsupported client

In Copilot inside VS Code or JetBrains, say:

> This skill needs Claude Code or GitHub Copilot CLI. Superpowers has no
> install for Copilot in VS Code or JetBrains yet.

Then stop.
