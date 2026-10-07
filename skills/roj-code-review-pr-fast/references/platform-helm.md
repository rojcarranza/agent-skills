# Helm

Loaded when the diff touches `Chart.yaml`, `values*.y*ml`, or files under a
chart's `templates/`. Review the chart as an interface: the values are its
API, and the rendered manifests are its output. Load `platform-k8s.md`
alongside when templates render workloads.

## Values as an interface

- A value renamed, moved, or removed. Every consumer — other values files,
  the Bamboo deploy task, the Go CLI, a parent chart — must change with it.
  Missed, the value silently falls back to the chart default. → **Major**.
- A value's type changed (string to list, scalar to map): overrides in
  environment values files then fail to merge.
- A new value referenced in a template with no entry in `values.yaml` and no
  default — it renders empty rather than failing. Use
  `required "message" .Values.x` when it is mandatory. → **Major**.
- A default made permissive (`replicaCount: 1` for a production chart,
  `debug: true`, an open ingress host).
- Nested maps overridden in an environment file: Helm merges maps but
  **replaces lists**, so appending to a list in an override does not work.

## Templates

- `{{ .Values.x }}` with no `default` and no guard where `x` may be absent —
  produces `image:` with an empty tag, or a manifest with a missing field.
- Quoting: a numeric-looking value (a version, a port, a tag such as `1.10`)
  rendered unquoted becomes a number or loses a trailing zero. Use `| quote`.
- Indentation helpers: `nindent` versus `indent` confusion, producing a valid
  YAML document with the block in the wrong place.
- `toYaml` output not piped through `nindent`.
- A `range` that shadows `.` and then references `.Values` inside without
  `$.Values`.
- `include` versus `template` where the output is piped — `template` cannot
  be piped.
- Name helpers changed (`fullname`, `name`), renaming every resource in the
  release and orphaning the old ones. → **Blocker** on an existing release.
- Resource names exceeding 63 characters after the release name is prefixed.
- A hook (`helm.sh/hook`) added or its weight changed — check ordering and
  whether `hook-delete-policy` leaves resources behind.
- A checksum annotation on the pod template missing when a ConfigMap or
  Secret template changed, so pods do not roll.

## Chart metadata

- `templates/` changed with no `version` bump in `Chart.yaml` — if the deploy
  pipeline keys on chart version, the upgrade is a no-op. → **Major** when
  the pipeline does.
- `appVersion` and the image tag diverging.
- A dependency added to `Chart.yaml` without `Chart.lock` updated, or with a
  floating version range.
- `condition` or `tags` on a dependency that no values file sets, so the
  subchart never renders.
- `apiVersion: v1` chart gaining v2-only fields.

## Release safety

- A change requiring `--force` or a delete-and-recreate — say so explicitly.
- An immutable field changed (see `platform-k8s.md`): the upgrade fails
  mid-release and leaves it `pending-upgrade`.
- No `--atomic` or `--wait` in the deploy invocation for a change that can
  half-apply.
- CRDs added under `crds/` — Helm never upgrades or deletes them.
- A resource moved between charts or renamed, leaving the old object behind
  with no owner.

## Verification worth offering

`helm template` with each environment's values file, and `helm lint`.
Rendering catches what reading templates cannot — empty values, broken
indentation, name length. Offer both, run only on approval.

## Not a finding here

- Whitespace chomping style (`{{-` versus `{{`) that does not change output.
- Helper naming conventions inside `_helpers.tpl`.
- Comment density in templates.
- Values file key ordering.
