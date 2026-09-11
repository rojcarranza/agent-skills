# Tracing changed code

Loaded at phase 3. Goal: know what each changed symbol does in the running
system, not only what its body says.

## Symbol card

Fill one card for each new or behavior-changing function, method, class,
component or configuration key.

| Field | What to write |
|---|---|
| File / lines | `path:start-end` of the current definition |
| Purpose | what it decides, computes or does — not its name restated |
| Inputs | parameters, plus state it reads (config, env vars, fields, DB) |
| Outputs | return value, plus side effects (writes, calls, messages, logs, exceptions) |
| Important conditions | the branches that change the outcome |
| Called by | each call site as `path:line` — the line where the caller invokes it, not the caller's range — or "no callers in the repository" |
| Calls | the downstream calls that matter |
| Return value use | what each caller does with the result |
| Before | the code that did this job at `<merge-base>`, or "new behavior" |
| Tests | the tests that exercise it, as `path:line` |

## Finding callers and callees

- Callers: `git grep -n "<name>("`, and for methods also
  `git grep -n "\.<name>("`. Search the bare name too, for references passed
  as values: callbacks, handlers, registries, config strings.
- Callees: read the body and open each call that affects the outcome.
- Stop rule: one caller level up and one callee level down. Go further only
  while the return value or side effect keeps flowing into code that changes
  behavior.
- No caller found: say so. It may be an entry point (route, CLI command,
  scheduled job, message consumer) or test-only code; find what registers
  it.

## Before and after

- Old version of a file: `git show <merge-base>:<path>`.
- Logic moved from elsewhere: `git log -S "<distinctive text>" --oneline <base>..HEAD`,
  then `git show <commit> -- <path>`. Also read the deleted lines in the
  caller's diff.
- Deleted code deserves the same attention as added code. Say which
  behavior disappeared.

## Trace paths by language

- **Java:** class → method → interface → implementation → caller. Wiring is
  often invisible: `git grep -n` for `@Component`, `@Service`, `@Bean`,
  `@Autowired`, `implements <Interface>`, and for configuration keys the
  `@Value` or `@ConfigurationProperties` that reads them. A changed
  `pom.xml` dependency is a behavior change when code uses it.
- **Python:** module → function → caller. Search
  `from <module> import <name>` and `<module>.<name>`. Unwrap decorators
  before describing a function. Click or argparse wiring shows the CLI
  entry point.
- **Go:** package → function → interface → implementation. Interfaces are
  satisfied implicitly, so search the method signature:
  `git grep -n "func (.*) <Method>("`. For goroutines and channels, state
  who sends, who receives, and who closes.
- **JavaScript / TypeScript:** export → import sites
  (`git grep -n "from '.*<module>'"`) → usage.
- **Bash:** script → function → external command. Find who runs the
  script: CI specs, other scripts, Dockerfiles, cron. State what happens
  when a command fails under the script's `set` options.
- **YAML / JSON / properties configuration:** key → code that reads the key
  → runtime behavior. Search the key's last segment as well as its full
  path. A key that nothing reads is dead configuration; say so.
- **SQL and migrations:** migration → tables and columns → the queries,
  entities or repositories that use them.
- **Pipelines (Bamboo specs, Dockerfiles, Helm, Kubernetes):** what changes
  about when or how things build, deploy or run.

## Architecture and technology checklist

Mention an item only when the diff touches it. Say how this change uses or
affects it; never explain the technology in general.

- Component responsibilities: did a job move between classes, modules or
  services?
- APIs and interfaces: signatures, request and response shapes, status
  codes, public methods, and who consumes them.
- Dependency injection and wiring.
- Messaging (Kafka topics, queues, events): producers, consumers, message
  shape, keys, ordering.
- Databases: schema, queries, transactions.
- Configuration: new keys, changed defaults, behavior when a key is absent.
- External integrations: calls to other systems, timeouts, retries.
- Concurrency and asynchronous processing.
- Error handling: new exceptions, swallowed errors, changed error flow.
- Processing pipelines and CI/CD: what runs, when, and in what order.

## Tests

For each new or changed test: the behavior it pins, the new scenarios, and
the implementation lines it exercises. Say whether each new behavior path
has a test. Mention a gap only when it matters for understanding the
feature, for example a new branch that no test reaches.
