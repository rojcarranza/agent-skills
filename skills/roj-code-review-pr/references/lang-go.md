# Go

Loaded when the diff touches `*.go`, `go.mod`, or `go.sum`. The Go project
here is a CLI that deploys Kubernetes packages, so weight error propagation,
context handling, and exit codes.

## Errors

- An error assigned to `_`, or returned without being checked at the call
  site.
- `err` shadowed inside an `if` or a closure so the outer one stays nil.
- Wrapping lost: `fmt.Errorf("...: %v", err)` where callers use
  `errors.Is`/`errors.As` — use `%w`.
- A sentinel error compared with `==` when the producer now wraps it.
- An error message that starts with a capital or ends with punctuation only
  matters if the repo's linter says so; an error message missing the value
  that failed always matters.
- `panic` in library code, or in a CLI path where a non-zero exit and a clear
  message is the correct behavior.
- `os.Exit` called where deferred cleanup still needs to run — deferred
  functions do not run.

## Context, timeouts, cancellation

- A network, exec, or Kubernetes API call without a `context.Context`, or
  with `context.Background()` where the caller's context should flow.
- `context.WithTimeout` whose `cancel` is not deferred.
- A long-running loop that never checks `ctx.Done()`.
- A `context.Context` stored in a struct field rather than passed as the
  first argument.

## Concurrency

- A goroutine started with no way to know it finished, and no error path.
- A loop variable captured by a goroutine (still worth checking when the
  module's Go version predates 1.22).
- A channel written to with no reader, or never closed, where a range waits
  on it.
- `sync.WaitGroup.Add` inside the goroutine instead of before it.
- Shared map or slice written from more than one goroutine without a mutex.
- A mutex copied by value (a struct containing `sync.Mutex` passed or
  returned by value).

## Slices, maps, defer

- A subslice retaining the backing array of a large slice.
- `append` to a slice shared with another owner, mutating it in place.
- Map iteration order assumed stable.
- `defer` inside a loop, accumulating until the function returns.
- `defer` on a value that is reassigned afterwards — arguments are evaluated
  at defer time, the body at return time.
- A `nil` map written to.
- Zero values treated as "unset" where zero is a legitimate value — the same
  trap as Python truthiness.

## Interfaces and types

- A nil concrete pointer stored in an interface: the interface is not nil,
  so `if err != nil` is true for a nil `*MyError`.
- An interface defined in the producer package rather than at the consumer,
  where the repository does the latter.
- A type assertion without the two-value form, so it panics.

## CLI behavior

- Exit codes: a failure path that exits 0, or every failure collapsing to 1
  where callers (Bamboo tasks) distinguish them.
- Output to stdout that a caller parses, mixed with progress messages that
  belong on stderr.
- A new flag with no default documented, or a flag whose default is
  destructive.
- A change to an existing flag name, shorthand, or default — that is a
  breaking change for every Bamboo plan invoking the CLI. → **Major** unless
  the diff also updates the callers.
- Missing confirmation, `--dry-run`, or `--yes` on a destructive deploy path.

## Kubernetes and Helm client code

- Errors from the API server treated uniformly — `IsNotFound`, `IsConflict`,
  and `IsAlreadyExists` usually need distinct handling and are what makes a
  deploy idempotent.
- Resources created without checking for existing ones, or updated with a
  full replace that drops fields other controllers own.
- No retry on conflict for read-modify-write on a resource.
- Waiting for rollout with no timeout, or by sleeping rather than watching.
- Namespace or context taken from the ambient kubeconfig rather than from an
  explicit flag.

## Modules

- `go.mod` Go version raised above what the Bamboo agent's toolchain
  provides.
- A dependency added at a pre-release or pseudo-version.
- `go.sum` not updated alongside `go.mod`, or the reverse.
- `replace` directives left pointing at a local path.

## Tests

- A new exported function or a new error branch with no test.
- `t.Parallel()` added to tests that share state.
- Table tests whose cases do not include the failure path.
- A test asserting on an error string rather than with `errors.Is`.

## Not a finding here

- Naming style, receiver names, or comment formatting — `gofmt` and
  `golangci-lint` own these.
- `var` versus `:=`; struct literal field ordering.
- Preferring a helper package over the standard library where the repository
  already does so.
- Missing doc comments on unexported identifiers.
