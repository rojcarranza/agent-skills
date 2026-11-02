# Java (Maven)

Loaded when the diff touches `*.java`, `pom.xml`, `.mvn/**`, or `mvnw*`.
Gradle is not used in these projects.

## Correctness

- `equals` changed without `hashCode` (or the reverse); either used on a
  mutable field that is also a map key.
- `Optional` unwrapped with `get()` without `isPresent()`; `Optional` used as
  a field or a parameter.
- Autoboxing comparisons: `Integer == Integer` outside the cache range,
  a boxed value unboxed on a path where it can be null.
- Integer division where a fraction was intended; overflow on `int`
  arithmetic that should be `long`.
- `String` compared with `==`.
- Mutable state returned directly from a getter, or a collection field
  assigned from a caller-owned collection without copying.
- Streams: a stateful lambda in `map`/`filter`, a stream consumed twice,
  `parallelStream` on a small or IO-bound workload, `findFirst` on an
  unordered source.
- Switch or enum handling that gained a case elsewhere but not here.

## Resources and errors

- `Closeable` not in try-with-resources: `InputStream`, `Connection`,
  `HttpClient` responses, `Files.lines`, `Scanner`.
- `catch (Exception e)` swallowing, or logging then rethrowing the same
  exception (duplicate stack traces in the Bamboo log).
- `InterruptedException` caught without restoring the interrupt flag.
- Checked exception converted into `RuntimeException` with the cause dropped.
- `finally` that returns or throws and discards the original exception.

## Concurrency

- Shared mutable field without `volatile`, a lock, or an atomic type.
- `SimpleDateFormat`, `Calendar`, or a `Random` instance shared across
  threads.
- `ExecutorService` created and never shut down.
- Futures whose exceptions are never observed (`submit` without checking).
- Double-checked locking without `volatile`.

## Spring and DI (when present)

- Field injection added where the project uses constructor injection.
- A new `@Bean` or `@Component` that duplicates an existing bean type and
  will make injection ambiguous.
- `@Transactional` on a private or self-invoked method — the proxy is
  bypassed, so the annotation does nothing.
- `@Value` on a property with no default and no entry in any profile's
  configuration.
- Scope mismatch: a stateful bean left as the default singleton.

## Maven (`pom.xml`)

- Version added without going through `dependencyManagement` in a
  multi-module repository, or a child overriding a managed version silently.
- A version range or `LATEST`/`RELEASE` instead of a pinned version.
- Scope wrong: a test-only library added at `compile`, or a provided
  container library bundled.
- A new dependency that duplicates one already on the tree under a different
  coordinate (check for both `javax.*` and `jakarta.*`, or two JSON
  libraries).
- Plugin version unpinned, so the Bamboo agent can resolve a different one
  than the developer machine.
- `maven.compiler.release` / `source`/`target` changed — confirm the agent's
  JDK matches.
- A new module added to `<modules>` but not built in the Bamboo plan, or the
  reverse.
- Surefire or Failsafe configuration that skips tests, excludes a pattern, or
  sets `testFailureIgnore`.

## Logging

- `System.out.println` where the project uses a logger.
- String concatenation inside a log call instead of parameterized `{}`.
- An exception logged without passing the throwable, losing the stack trace.

## Tests

- A new branch in a `switch`, `if`, or exception path with no test.
- `assertTrue(true)`-shaped tests, or a test with no assertion.
- `@Disabled`/`@Ignore` added in this diff without a reason and a ticket.
- Mocks asserting on interactions that do not establish behavior.
- Test relying on execution order or on a shared static field.

## Not a finding here

- Checked versus unchecked exception preference where the codebase is
  consistent.
- `var` versus explicit types; import ordering; final on locals.
- Lombok usage in a repository that already uses Lombok.
- Builder versus constructor style.
- Anything Checkstyle or SpotBugs is configured to catch.
