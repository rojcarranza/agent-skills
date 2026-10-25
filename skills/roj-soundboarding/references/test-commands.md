# Test commands

Flow 2 runs a baseline test before the first task and the narrowest relevant
check after each task. This file says which command to pick. The rule that
overrides everything below: run only a command the repository itself
provides, and report only what it printed.

## Picking the command

1. The repository's own entry point wins: a `Makefile` or `justfile` test
   target, a `scripts/test*` file, or the command in `README`/`CONTRIBUTING`.
   A Bamboo plan or Bitbucket pipeline file shows what CI runs; use its test
   command, but never trigger the plan or pipeline.
2. Otherwise match the build file:

| Found | Baseline | Narrowest |
|---|---|---|
| `go.mod` | `go test ./...` | `go test ./<package dir>` |
| `pom.xml` | `mvn -q test` | `mvn -q test -Dtest=<TestClass>` |
| `build.gradle`, `build.gradle.kts` | `./gradlew test` (`gradlew.bat` on cmd) | `./gradlew test --tests <TestClass>` |
| `pyproject.toml`, `pytest.ini`, `tox.ini` | `python -m pytest -q` | `python -m pytest -q <test file>` |
| Python tests with no pytest | `python -m unittest` | `python -m unittest <module>` |
| `*.sh` with `tests/*.bats` | `bats tests` | `bats tests/<file>.bats` |
| `*.sh` only | `shellcheck <file>` | same, on the changed scripts |
| `Dockerfile` | `hadolint Dockerfile` when installed | same |
| Helm chart (`Chart.yaml`) | `helm lint <chart dir>` | `helm template <chart dir>` to render |
| Kubernetes manifests | `kubectl apply --dry-run=client -f <file>` | same, on the changed files |

3. A tool in the table that is not installed is not a failure: say it is
   missing and run the next best check, or log `manual - pending`.
4. Nothing matches: say no test command was found. Do not guess one.

## Limits

- Never run anything that changes a shared system: no deploy, `kubectl apply`
  without `--dry-run`, `helm install` or `upgrade`, `docker push`, Terraform
  `apply`, or a Bamboo/Bitbucket call. A check that needs one is
  `manual - pending`.
- Do not install dependencies or upgrade tools to make a check run. A build
  tool's normal dependency download is fine.
- Shell syntax differs on Windows: use `gradlew.bat`, `python` instead of
  `python3`, and quote paths with spaces. Prefer the repository's own script
  over a command you typed.
- A change to a Dockerfile, a chart value or a pipeline file usually has no
  unit test. Run the lint or render check above, or say none applies.
