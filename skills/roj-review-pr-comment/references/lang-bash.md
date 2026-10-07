# Bash and shell

Loaded when the diff touches `*.sh`, `*.bash`, or an extensionless file with
a shell shebang. These scripts run unattended on Bamboo agents, so an
unnoticed failure is worse than a wrong result.

## Failure handling — check first

- No `set -euo pipefail` (or an explicit, documented reason). A script that
  continues after a failed command in a deploy path is at least **Major**.
- `set -e` present but defeated: the failing command sits in a condition, in
  a `&&` chain, or in a function called from `if`.
- A pipeline whose real work is not the last stage, with no `pipefail` — the
  exit code reported is the last command's, so `curl … | tee log` reports
  success when `curl` failed.
- `|| true` used to silence a command whose failure matters.
- `$?` checked after an intervening command, so it reflects the wrong one.
- No `trap` for cleanup where the script creates temp files, holds a lock,
  or leaves a cluster resource behind on interrupt.

## Quoting and expansion

- Unquoted `$VAR` or `$(cmd)` anywhere a value can contain a space, a glob,
  or be empty — especially in `rm`, `kubectl`, `cp`, and `test`.
- `"$@"` written as `$@` or `$*` when forwarding arguments.
- Unquoted expansion in a destructive command where an unset variable
  expands to nothing: `rm -rf "$DIR"/` with `DIR` unset. → **Blocker** when
  `set -u` is absent.
- `${VAR:-default}` versus `${VAR-default}` confusion for empty-but-set.
- Word splitting when reading lines: `for line in $(cat f)` instead of
  `while IFS= read -r line`.
- Missing `-r` on `read`, so backslashes are eaten.

## Command usage

- A command that may not exist on the agent, with no `command -v` guard and
  no declared Bamboo capability.
- GNU-only flags (`sed -i` without a suffix, `date -d`, `readlink -f`,
  `grep -P`) where the agent may be BSD or Alpine.
- `cd` without checking it succeeded, followed by a destructive command.
- Absolute paths to tools, or reliance on the caller's `PATH` for a tool the
  script installs.
- `curl` without `-f` (so an HTTP 500 body is treated as success), without
  `--max-time`, or without retry on a flaky endpoint.
- `kubectl`/`helm` without an explicit `--context` or `--namespace` when the
  agent's current context is not controlled by the script.

## Structure and state

- A script that is not safe to re-run: see idempotency in
  `cross-cutting.md`.
- Temp files created with a predictable name instead of `mktemp`.
- A lock file created without a trap to remove it.
- Local variables not declared `local` inside a function, leaking into the
  caller.
- A function returning data by echoing while also echoing progress messages
  to stdout — the caller captures both. Progress belongs on stderr.
- Long argument parsing rewritten in this diff — confirm every previously
  supported flag still works.

## Secrets

- A secret passed as a command-line argument (visible in `ps` and in Bamboo
  logs) rather than through an environment variable or a file.
- `set -x` enabled around a command that carries a token — it lands in the
  build log. → **Blocker**.
- A credential written to a file without restricting permissions.

## Tests

- A change in behavior with no corresponding check, where the repository has
  a test harness (`bats`, a `tests/` directory, or a self-test flag).
- A script with no dry-run or `--help` path where its siblings have one.
- A destructive path with no confirmation and no `--yes` flag.

## Not a finding here

- Quoting inside `[[ ]]` — word splitting does not occur there.
- `echo` versus `printf` for plain literal strings.
- `$(…)` versus backticks where the file is already consistent.
- Indentation, `then` on the same line, or two-space versus four-space.
- Anything `.shellcheckrc` disables for the repository, and anything
  ShellCheck itself is run on in CI.
