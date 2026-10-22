# no-mistakes workflow

Gates run locally, because GitHub Actions is off on these repos. A pull
request is checked by [no-mistakes](https://github.com/kunchenguid/no-mistakes)
before it is ever pushed: you push to the `no-mistakes` remote, the daemon runs
the pipeline in a worktree, and only a passing branch is pushed to `origin`
and opened as a PR. A direct `git push origin` skips the gate entirely.

The built-in Test step is targeted (`commands.test` is "local targeted
validation ... not a CI-parity repository-wide regression command"), so each
repo declares its full suite as a `gates:` entry that runs after `test`, and
sets `no_ci: true` so an empty check list counts as passing. `gates`,
`no_ci` and `allow_repo_commands` are read only from the trusted default
branch, so the PR that adds them is not checked by its own gates.

## GitHub operations

Agents use [`gh-axi`](https://github.com/kunchenguid/gh-axi) for issues, PRs,
reviews and checks. Raw `gh` is a fallback only where gh-axi has no command,
and the agent says so when it uses it. Until the dotfiles pin lands, run it as
`npx -y gh-axi@0.1.43`.

## Onboard a repo

Steps marked **Claude Code** do nothing in other agents.

1. Run `no-mistakes init` in the repo. It needs an `origin` remote and adds the
   `no-mistakes` remote.
2. Add `.no-mistakes.yaml` and merge it to `main` first:

   ```yaml
   no_ci: true
   allow_repo_commands: false   # the default; leave it
   commands:
     lint: <your lint command>
   gates:
     - name: full-suite
       after: test
       command: "<your full check, e.g. the repo's validation command>"
   ```

3. **Claude Code:** deny direct pushes in `.claude/settings.json`:

   ```json
   { "permissions": { "deny": ["Bash(git push origin:*)"] } }
   ```

4. Add this line to `AGENTS.md`: "Push through `git push no-mistakes`, never
   `origin`." Other agents only have this line to go on.
5. Add this line to `AGENTS.md` or `CLAUDE.md`: "Use `gh-axi` for GitHub, not
   raw `gh`." Works in any agent, not only Claude Code.
6. Remove the repo's GitHub Actions workflow only after the pilot criteria
   pass.

## Update the pinned tools

The tools are pinned in the dotfiles repo; see its
[Upstream tools](https://github.com/rojcarranza/dotfiles#upstream-tools)
table for how to bump each one, `gh-axi` included. Monthly, as a PR you review:

1. Edit the tag in the dotfiles `flake.nix`, run `nix flake update no-mistakes`
   (or `treehouse`, `gh-axi`), then `./rebuild.sh`.
2. `no-mistakes daemon restart` - the running daemon keeps the old binary.
3. `no-mistakes doctor`.
4. Make one gated push on the pilot repo (ai-account-switcher).

Rollback: revert `flake.lock`, `./rebuild.sh`, then
`no-mistakes daemon restart`.
