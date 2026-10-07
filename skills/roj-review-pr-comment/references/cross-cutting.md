# Cross-cutting defects

Always loaded. Language-independent classes that dominate infrastructure and
automation code. Check every changed hunk against these before reaching for a
language lens.

## Secrets and credentials

- Tokens, passwords, private keys, kubeconfigs, `.pem` files added to the
  repository, or embedded in a Dockerfile, Helm value, Bamboo spec, or test
  fixture. → **Blocker**, always.
- Secrets passed as command-line arguments (visible in `ps`, and in Bamboo
  build logs) rather than through environment or a file.
- Secrets echoed, logged, or included in an error message.
- A secret removed from a file in this diff but still present in Git history
  — note it: deleting the line does not rotate the credential.
- Credentials widened: a token that gained scope, a role that gained verbs.

## Idempotency and re-runs

Automation is re-run. For each changed operation, ask what happens the second
time and after a crash halfway through.

- `mkdir`, `create`, `add`, `insert` without an "already exists" path.
- Appends to a file that is not truncated first.
- Counters, sequence numbers, or timestamps written outside a transaction.
- A multi-step deploy with no rollback path when step 3 of 5 fails.
- Operations whose retry duplicates a side effect (a message sent twice, a
  release created twice).

## Error handling

- An error assigned and not checked; an exception caught and discarded.
- A bare `except:` / `catch (Exception)` / `|| true` swallowing everything,
  including the failure the caller needed to see.
- An exit code ignored, or lost through a pipe.
- An error logged and then execution continuing as if it succeeded.
- Error messages that omit the value that caused the failure — unactionable
  in a Bamboo log.

## Timeouts, retries, resource limits

- A network call, subprocess, or lock acquisition with no timeout. → at least
  **Major** when it runs in CI or in a deploy path, where it hangs the agent.
- Retries with no backoff, no cap, or retrying a non-idempotent operation.
- Retrying on errors that will never succeed (a 400, a parse failure).
- Unbounded reads into memory (a whole log file, a whole API page set).

## Destructive operations

- `rm -rf`, `kubectl delete`, `DROP`, `truncate`, force-push, registry
  deletion — check the guard on the path or selector, and what an empty or
  unset variable expands to.
- A destructive step that runs before the check that would have stopped it.
- Deletions keyed on a wildcard or a label that could match more than
  intended.

## Unsafe defaults

- A default that is permissive (`allow`, `*`, `latest`, `debug`, `insecure`,
  `verify=False`, `--force`) rather than restrictive.
- A default that points at production.
- A configuration value that silently falls back instead of failing loudly
  when it is required.

## Logging and observability

- Sensitive values in logs (see Secrets).
- A new failure path with no log line — invisible in a Bamboo build log.
- Logging inside a tight loop.
- Log levels inverted: an operator-actionable failure at `debug`, routine
  progress at `error`.

## Concurrency and shared state

- Shared mutable state touched from more than one thread, goroutine, or
  process without a lock.
- A file or lock written by parallel Bamboo jobs on the same agent.
- Check-then-act on anything another process can change in between.

## Portability

- A path, tool, or shell built-in assumed present on the Bamboo agent but not
  declared as a capability.
- Hardcoded `/tmp`, `/home/<user>`, or an absolute path to a tool.
- GNU-only flags where the agent may run BSD utilities, or the reverse.
- Line-ending or locale assumptions.

## Dependencies

- A new dependency added for something the standard library already does.
- A version range that can float into a breaking major.
- A dependency added to the runtime scope when it is only needed for tests.
- A transitive upgrade that changes behavior, with nothing in the diff
  acknowledging it.

## Not a finding here

- Naming, ordering, or formatting preferences.
- Defensive checks the caller provably makes.
- "This could theoretically race" with no shared state named.
- Missing timeouts on purely local, in-memory operations.
