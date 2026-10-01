# Domain checks — repro commands and evidence lists

Validation commands per issue class. Prefer the *exact* failing thing
from the build log (same goal, same test, same flags) over a generic
command. Never run commands that mutate external systems (deploys,
pushes, `kubectl apply` without `--dry-run`).

## Bash / shell scripts

- Syntax: `bash -n script.sh`
- Static analysis: `shellcheck script.sh` (if installed)
- Run it: same invocation as the failing task, from a scratch dir that
  mimics the build dir layout (files the script expects may exist only
  after checkout/build steps — recreate minimally).
- Classic causes: missing `set -euo pipefail`; word-splitting on
  unquoted variables; `cd` without `|| exit`; assuming GNU coreutils
  flags on a BSD/alpine agent (or vice versa).

## Python

- Repro the failing test: `pytest path/to/test.py::test_name -x -q`
  (or the runner the log shows: `tox`, `poetry run pytest`, plain
  `unittest`).
- Import/syntax only: `python -m py_compile file.py`
- Env drift: compare traceback's python version with repo pin
  (`.python-version`, `pyproject.toml requires-python`); check whether
  the failing import is in the lock/requirements file at the version
  the log installed.

## Java (Maven / Gradle)

- Repro the failing goal from the log:
  `mvn -q <goal> -pl <module>` / `./gradlew <task>` — same module, same
  profile flags the plan passes.
- Compile only: `mvn -q compile` / `./gradlew compileJava`
- One test: `mvn -q -Dtest=ClassName#method test`
- Classic causes: JDK target vs runtime mismatch (`invalid target
  release`, `Unsupported class file major version`); SNAPSHOT
  dependency drift between local `~/.m2` and agent's; enforcer plugin
  rules failing only on agent versions.

## Go

- Build: `go build ./...` — Vet: `go vet ./...`
- One test: `go test -run TestName ./pkg/...`
- Classic causes: `go.mod` go directive newer than agent toolchain;
  private module fetch needs `GOPRIVATE`/netrc absent on agent; CGO
  needed but no compiler on agent (`CGO_ENABLED` mismatch).

## Dockerfile / image

- Repro: `docker build .` (add `--target <stage>` for the failing
  multi-stage step; `--progress=plain` for full step output).
- Classic causes: `COPY` path outside build context or hit by
  `.dockerignore`; base tag moved (`latest`, unpinned minor) — agent
  cache holds old image while local pulled new, or inverse
  (`docker build --pull` to test); RUN step needs network/proxy the
  agent lacks; case-sensitive paths (mac local vs linux agent).

## Kubernetes manifests / Helm

- Schema/dry-run: `kubectl apply --dry-run=client -f file.yaml`
  (server-side validation needs a cluster — mark Probable if none).
- Helm: `helm template <chart> -f values.yaml` then dry-run the output;
  `helm lint <chart>`.
- Reading pasted cluster errors:
  - `CrashLoopBackOff` — container exits; real cause is in container
    logs, not the manifest; check entrypoint/command overrides first.
  - `ImagePullBackOff` — image name/tag typo, missing pull secret,
    or registry auth.
  - `OOMKilled` — memory limit vs actual usage.
  - Probe failures — path/port of liveness/readiness vs what the app
    serves, and initial delay vs app startup time.
  - Pending pods — resource requests unschedulable, node selectors,
    taints.

## When repro is impossible

Cause lives on the agent/cluster/env you cannot touch. Switch to static
evidence (`bamboo-failures.md` for agent classes), mark the root cause
**Probable**, and make the report's Verification section name the exact
rerun that would confirm it.
