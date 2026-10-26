# Worked review

One complete run, end to end, on a realistic branch. Consult this only when
the output format needs grounding — it is not loaded by default.

The branch: `feature/PROJ-4471-atomic-upgrade` in the Go deploy CLI. It adds
a `--wait-timeout` flag and passes it from the staging Bamboo spec, switches
the Helm upgrade call to atomic, and bumps the chart used by the staging
environment.

## Phase trace (what the skill did)

```
$ git symbolic-ref refs/remotes/origin/HEAD
refs/remotes/origin/main
$ git rev-parse --verify --quiet origin/develop
3c8d2e17b5a94f60c1e7d2b8a6f4e9c0d1b3a5f7
$ git rev-parse --verify --quiet origin/master
$ git rev-list --count origin/main..HEAD
4
$ git rev-list --count origin/develop..HEAD
11
$ git merge-base origin/main HEAD
9f31c0a4c0b1e6b0d4a7c2f8e5b3a1d9c7e5f3a1
$ git diff --name-status origin/main...HEAD
M       cmd/deploy.go
M       internal/helm/client.go
M       charts/service/Chart.yaml
M       charts/service/values-staging.yaml
M       internal/helm/client_test.go
M       bamboo-specs/deploy.yaml
$ git diff --stat origin/main...HEAD
 6 files changed, 119 insertions(+), 21 deletions(-)
$ git rev-parse @{u}
fatal: no upstream configured for branch 'feature/PROJ-4471-atomic-upgrade'
```

Base: `origin/main` (nearest of origin/main, origin/develop): 4 commits
ahead of it against 11 for `origin/develop`, and `origin/master` does not
resolve.

Lenses selected from the changed paths: `lang-go.md` (3 files),
`platform-helm.md` (2 files). No Kubernetes manifests changed, so
`platform-k8s.md` was not loaded. Mode: **full** (auto: a Bamboo spec and a
Helm chart changed, so a deploy path), stage **pre-PR**.

Repository conventions read: `CLAUDE.md`, `.golangci.yml` (has `errcheck`
and `govet` enabled — so unchecked errors are not reported here, the linter
owns them).

Opt-in asked once, up front: the user answered `checks`. The declared checks
run were `go vet ./...` and `helm template charts/service -f
charts/service/values-staging.yaml`, then the narrowest test for the flag,
`go test ./cmd -run TestWaitTimeout`. The `helm template` run is what
produced the Blocker below. The test passed, but its table only parses `5m`,
so it could not disprove the Major. A repro confirmed it: a scratch
`main.go` outside the repository that calls `time.ParseDuration("300")`,
the parser the flag uses, run with `go run /tmp/review-repro/main.go`,
exited 1 with `time: missing unit in duration "300"`, and was deleted
after.

## The report

```
## Review — feature/PROJ-4471-atomic-upgrade vs origin/main

deploy-cli · base `origin/main` @ `9f31c0a` · 4 commits ·
6 files · +119/-21 · lenses: lang-go, platform-helm ·
mode: full · stage: pre-PR
Uncommitted: none
Intent: none
Excluded: none

### What this branch does

Adds a `--wait-timeout` flag to `deploy`, and makes the Helm upgrade wait for
the release to become ready instead of returning as soon as the API accepts
it. When the wait fails, the upgrade now rolls back automatically rather than
leaving the release in `pending-upgrade`. The staging chart is bumped to
0.4.0 to pick up the matching probe changes.

- `cmd/deploy.go` — registers `--wait-timeout`, defaults it, passes it down.
- `internal/helm/client.go` — sets `Atomic`, `Wait` and `Timeout` on the
  upgrade action; maps a timeout error to a distinct exit code.
- `charts/service/Chart.yaml` — version 0.3.2 → 0.4.0.
- `charts/service/values-staging.yaml` — adds `probes.startupSeconds`.
- `internal/helm/client_test.go` — covers the timeout mapping.
- `bamboo-specs/deploy.yaml` — the staging deploy task passes
  `--wait-timeout 300`.

Flow: `deploy` parses flags → `helm.Client.Upgrade` builds the action with
`Atomic: true`, `Wait: true`, `Timeout: <flag>` → on a wait failure Helm
rolls back and returns an error → `Upgrade` wraps it as `ErrWaitTimeout` →
`cmd/deploy.go` exits 4 so the Bamboo task can distinguish a timeout from a
genuine failure.

### Verdict

Changes requested — 1 Blocker, 1 Major, 1 Minor, 0 Nits

### Findings

#### 🔴 Blocker

**`charts/service/values-staging.yaml:14`** · Confirmed
`probes.startupSeconds` is read by the template as
`.Values.probes.startupSeconds` but the production values file still has no
`probes` key, and `values.yaml` provides no default.
Fails when: deploying to production, `helm template` renders
`initialDelaySeconds:` with an empty value and the apply is rejected with
`error validating data: expected type int, got null`. Verified by running
`helm template charts/service` with the default values.
Fix: add `probes: {startupSeconds: 30}` to `charts/service/values.yaml`, or
guard the template with `default 30`.

#### 🟠 Major

**`cmd/deploy.go:57`** · Confirmed
The flag is parsed with `time.ParseDuration`, which needs a unit, but
`bamboo-specs/deploy.yaml:34`, added in this same diff, passes
`--wait-timeout 300`. A bare `300` is rejected, so the staging deploy task
can no longer run.
Fails when: the staging plan runs; `deploy` exits with `invalid argument
"300" for "--wait-timeout" flag: time: missing unit in duration "300"` before
any Helm call, and every deploy from this branch fails in Bamboo. Verified by
`go run /tmp/review-repro/main.go`, a scratch file calling
`time.ParseDuration("300")`: exit 1, `time: missing unit in duration "300"`.
Fix: pass `--wait-timeout 5m` in the spec, or accept bare seconds in the
flag parser.

#### 🟡 Minor

**`internal/helm/client.go:88`** · Probable
`ErrWaitTimeout` is returned with `fmt.Errorf("%v", err)`, so the underlying
Helm error cannot be matched with `errors.Is` by the caller added in this
same diff.
Assumption named: `cmd/deploy.go:120` is the only consumer today.
Fix: wrap with `%w`.

### Tests

`client_test.go` covers the timeout-to-exit-code mapping, including the
failure path — good. Not covered: the `Atomic` rollback path, and flag
parsing of the value the Bamboo spec actually passes (`300`), which is the
Major above. A table case with that input would have caught it.

Commands run: `go vet ./...` (exit 0), `helm template charts/service -f
charts/service/values-staging.yaml` (exit 0), `helm template charts/service`
(exit 1), `go test ./cmd -run TestWaitTimeout` (exit 0), scratch
`go run /tmp/review-repro/main.go` (exit 1).

### Runtime / deploy impact

Every upgrade now blocks until the release is ready and rolls back on
failure, so deploy tasks that previously returned in seconds will run for as
long as the rollout takes. Bamboo task timeouts should be checked against the
new `--wait-timeout` value. Chart 0.4.0 renames nothing, so existing
releases upgrade in place.

### Needs your input

- Does the production Bamboo plan pass `--wait-timeout` in the same form as
  staging? Only the staging spec is in this repository, so its value there is
  unknown.

### Good

- Mapping the timeout to its own exit code is the right call — Bamboo can
  distinguish it from a genuine failure.
- The test covers the failure path, not just the happy one.

Report: `feature-PROJ-4471-atomic-upgrade-review.md`
Tour: `.tours/review-feature-PROJ-4471-atomic-upgrade.tour`
```

## What was deliberately not reported

- `cmd/deploy.go:44` uses `:=` where the file elsewhere uses `var` — style,
  and `golangci-lint` does not enforce it.
- An unchecked `defer f.Close()` in `client.go` — `errcheck` is enabled in
  `.golangci.yml`, so the linter owns it.
- "The `Upgrade` method is getting long" — no failure scenario, so it is not
  a finding.
- A missing nil check on `cfg` in `client.go:61` — the only caller constructs
  it three lines earlier. Killed by the verification pass.
