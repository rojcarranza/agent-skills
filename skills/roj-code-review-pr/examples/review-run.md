# Worked review

One complete run, end to end, on a realistic branch. Consult this only when
the output format needs grounding — it is not loaded by default.

The branch: `feature/LISA-4471-atomic-upgrade` in the Go deploy CLI. It adds
a `--wait-timeout` flag, switches the Helm upgrade call to atomic, and bumps
the chart used by the staging environment.

## Phase trace (what the skill did)

```
$ git symbolic-ref refs/remotes/origin/HEAD
refs/remotes/origin/main
$ git rev-list --count origin/main..HEAD
4
$ git merge-base origin/main HEAD
9f31c0a4c0b1e6b0d4a7c2f8e5b3a1d9c7e5f3a1
$ git diff --name-status origin/main...HEAD
M       cmd/deploy.go
M       internal/helm/client.go
M       charts/service/Chart.yaml
M       charts/service/values-staging.yaml
M       internal/helm/client_test.go
$ git diff --stat origin/main...HEAD
 5 files changed, 118 insertions(+), 21 deletions(-)
$ git rev-parse @{u}
fatal: no upstream configured for branch 'feature/LISA-4471-atomic-upgrade'
```

Lenses selected from the changed paths: `lang-go.md` (3 files),
`platform-helm.md` (2 files). No Kubernetes manifests changed, so
`platform-k8s.md` was not loaded. Mode: **pre-PR**, the branch has no
upstream.

Repository conventions read: `CLAUDE.md`, `.golangci.yml` (has `errcheck`
and `govet` enabled — so unchecked errors are not reported here, the linter
owns them).

Tooling offered and approved: `go vet ./...`, `helm template charts/service
-f charts/service/values-staging.yaml`. The `helm template` run is what
produced the Blocker below.

## The report

```
## Review — feature/LISA-4471-atomic-upgrade vs origin/main

deploy-cli · base `origin/main` @ `9f31c0a` · 4 commits ·
5 files · +118/-21 · lenses: lang-go, platform-helm · mode: pre-PR
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
`--wait-timeout` defaults to `0`, which Helm treats as "no timeout" rather
than "fail immediately", so an unhealthy release now blocks the Bamboo job
until the job's own timeout kills it — and because `Atomic` is set, the
rollback never runs.
Fails when: a bad image tag is deployed; before this branch the task failed
in seconds, now the agent is held for the job's full 60 minutes and the
release is left in `pending-upgrade`.
Fix: default to a bounded value (`5 * time.Minute`) and reject `0`.

#### 🟡 Minor

**`internal/helm/client.go:88`** · Probable
`ErrWaitTimeout` is returned with `fmt.Errorf("%v", err)`, so the underlying
Helm error cannot be matched with `errors.Is` by the caller added in this
same diff.
Assumption named: `cmd/deploy.go:120` is the only consumer today.
Fix: wrap with `%w`.

### Tests

`client_test.go` covers the timeout-to-exit-code mapping, including the
failure path — good. Not covered: the `Atomic` rollback path, and the
`--wait-timeout=0` case, which is the Major above. A table case with a zero
timeout would have caught it.

### Runtime / deploy impact

Every upgrade now blocks until the release is ready and rolls back on
failure, so deploy tasks that previously returned in seconds will run for as
long as the rollout takes. Bamboo task timeouts should be checked against the
new `--wait-timeout` default. Chart 0.4.0 renames nothing, so existing
releases upgrade in place.

### Needs your input

- Does the staging Bamboo deploy task pass `--wait-timeout` explicitly? The
  spec is not in this repository, so the effective default there is unknown.

### Good

- Mapping the timeout to its own exit code is the right call — Bamboo can
  distinguish it from a genuine failure.
- The test covers the failure path, not just the happy one.

Report: `feature-LISA-4471-atomic-upgrade-review.md`
Tour: `.tours/review-feature-LISA-4471-atomic-upgrade.tour`
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
