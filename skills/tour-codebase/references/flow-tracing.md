# Flow tracing

Loaded at phase 2, to pick and walk the one path tour 03 traces.

## Picking the flow

In order. First rule that fires wins.

1. The reader named it ("tour the auth flow"). Trace that, even if a bigger
   one exists.
2. The path the README's own example exercises. A repository's quickstart is
   the flow its authors consider central.
3. The path with the most test coverage. Count test files referencing each
   entry point; the winner is the flow the team maintains hardest.
4. The path from the process entry point that reaches the most layers.

State the rule that fired in the phase 2 plan, with the entry point as
`file:line`. A reader who disagrees corrects it at the one checkpoint.

Reject a flow when it never leaves one file — that is a function, not a
flow. Fall back to the next candidate.

## Walking it

Execution order, always. The reader follows control, not the file tree.

For each step: what arrives here, what this code does to it, what leaves.
Stop stepping when the path exits the process (response returned, file
written, exit code set, message published).

Cross a boundary explicitly. When control moves from one layer to the next,
say which boundary was crossed and what guarantees hold on the far side.

Do not step into: logging, metrics, generic error wrappers, dependency
injection plumbing that the architecture tour already showed, and helpers
whose name fully describes them. Name them in the passing step instead.

## Entry-point signals per stack

### Java / Spring / Maven

Entry: `public static void main`, `@SpringBootApplication`, or a
`spring-boot-maven-plugin` module in `pom.xml`. Multi-module: the module
producing the executable jar.

Path: `@RestController` / `@Controller` method → `@Service` → repository or
client → response mapper. Route to method comes from
`@RequestMapping`/`@GetMapping` values.

Watch for: `@Transactional` boundaries, `@Async` handoffs, filters and
interceptors that run before the controller, and any `@Bean` that replaces a
default. Those are control transfers with no call site in the code.

### Python

Entry: `[project.scripts]` or `console_scripts` in `pyproject.toml` /
`setup.py`, `if __name__ == "__main__"`, an ASGI/WSGI `app` object, or a
Celery task module.

Path: Click/argparse command function → service function → client or ORM
call. FastAPI/Flask: decorator on the route function is the registration;
the function body is the step.

Watch for: decorators that wrap behaviour (retry, cache, auth), context
managers holding transactions or connections, and generators — the code after
a `yield` runs later than it reads.

### Go

Entry: `package main`'s `func main`. Servers: `http.ListenAndServe`,
`mux.HandleFunc`, gRPC `RegisterXServer`.

Path: handler func → service struct method → repository or client.
Interfaces are satisfied implicitly, so step at the concrete type the
constructor wires in, not at the interface.

Watch for: goroutine launches (who sends, who receives, when the channel
closes), `defer` order, `context` cancellation, and error wrapping with `%w`.

### Node / TypeScript

Entry: `bin` or `scripts` in `package.json`, `main`/`exports`, an Express
`app.listen`, a Nest module.

Path: route registration → controller → service → data layer. Middleware
runs before the handler and is invisible at the call site — step at the
registration.

Watch for: `tsconfig.json` path aliases (`@/foo` is not a directory),
barrel-file re-exports hiding the real module, and `await` chains that
serialise what looks concurrent.

### Bash / installers / dotfiles

Entry: the script's first executed line after its function definitions, or
the CLI subcommand dispatcher.

Path: dispatcher → per-target function → the commands that touch the system.

Watch for: `set -euo pipefail` (or its absence — then a mid-pipeline failure
is silent), traps, subshells that lose variable assignments, and symlink
versus copy branches that make the same script behave differently per host.

### Bamboo / CI

Entry: the plan specification class or the YAML pipeline definition.

Path: plan → stage → job → task, in declared order. Artifacts and triggers
are the edges between plans; name them when the path leaves one plan.

Watch for: variable scope (plan versus global versus build), agent
capability requirements that decide where a job lands, and tasks that shell
out — the real work is in the script, not in the task definition.

### Docker / Kubernetes / Helm

Entry: `ENTRYPOINT` or `CMD` in the Dockerfile; for a chart, `values.yaml`.

Path: values → template → rendered workload → the container's entrypoint →
the application's own entry point. Cross into the application flow only when
the tour is about the deployment; otherwise stop at the entrypoint and say
which application flow it starts.

Watch for: init containers, `command` overrides in the manifest that ignore
the image's `ENTRYPOINT`, config maps and secrets mounted as files, and
probes that restart the workload.

## Mixed stacks

A repository whose flow crosses stacks (a shell installer that calls Python,
a chart that deploys a Java service) is traced as one flow with the boundary
called out. Do not split it into two tours — the boundary is the most
valuable step in the tour.
