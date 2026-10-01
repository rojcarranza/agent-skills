# Kubernetes

Loaded when the diff touches YAML carrying both `apiVersion:` and `kind:`.
When the same file is a Helm template, load `platform-helm.md` too and review
the rendered shape, not just the source.

## Workload correctness

- `image` with a mutable tag (`latest`, `main`, an unpinned branch tag) in a
  deployed environment — the running version is then unreproducible.
  → **Major**.
- `imagePullPolicy: Always` with a mutable tag, or `IfNotPresent` with one —
  state which behavior the change produces.
- A `selector` or `matchLabels` changed on an existing Deployment: the field
  is immutable, so `kubectl apply` fails and the release breaks. → **Blocker**.
- Labels changed on the pod template without the selector, or the reverse, so
  the Service now matches nothing.
- `replicas` changed alongside an HPA that also owns the field.
- A rename of a resource that other manifests reference by name (Service,
  ConfigMap, Secret, ServiceAccount) — check every reference in the repo.

## Reliability

- No `resources.requests` and `resources.limits`. Missing requests break
  scheduling and eviction ordering; a missing memory limit lets one pod take
  the node. → **Major** in a production path.
- Probes missing, or `livenessProbe` configured so a slow start restarts the
  pod forever — a `startupProbe` is the fix.
- `readinessProbe` hitting an endpoint that reports healthy before
  dependencies are ready, so traffic arrives too early.
- `terminationGracePeriodSeconds` shorter than the shutdown path the app
  needs.
- No `PodDisruptionBudget` for a workload the rolling node drain will take
  down entirely.
- `strategy` changed to `Recreate`, which introduces downtime — always report
  it as a runtime impact.
- `maxUnavailable`/`maxSurge` values that allow zero available replicas.

## Configuration and secrets

- A `Secret` with literal `stringData` values committed. → **Blocker**.
- `envFrom` a ConfigMap or Secret that no manifest in the repo creates, and
  that the deploy does not create first — the pod stays in
  `CreateContainerConfigError`.
- A ConfigMap changed with no mechanism to roll the pods (no checksum
  annotation), so the change silently does not take effect until the next
  unrelated deploy.
- A volume mount path that shadows an existing directory in the image.
- `subPath` mounts, which do not receive ConfigMap updates.

## Security

- `securityContext` widened: `privileged: true`, `runAsUser: 0`,
  `allowPrivilegeEscalation: true`, added capabilities, `hostNetwork`,
  `hostPID`, or a `hostPath` volume. → at least **Major**, with the reason
  the change needs it.
- RBAC widened: new verbs, `*` on resources or apiGroups, a ClusterRole where
  a namespaced Role would do, or a binding to a broad subject like
  `system:authenticated`. → **Major**.
- A ServiceAccount with `automountServiceAccountToken` left on where the
  workload does not call the API.
- A Service changed to `type: LoadBalancer` or `NodePort`, exposing it beyond
  the cluster. → always report as a runtime impact.
- NetworkPolicy removed or loosened.

## Placement and scope

- `namespace` added, changed, or omitted where the apply relies on the
  caller's current context.
- `nodeSelector`, tolerations, or affinity changed such that no node matches
  and pods stay `Pending`.
- A `StatefulSet` volumeClaimTemplate changed — immutable, requires
  recreation, and risks the data.
- `PersistentVolumeClaim` `storageClassName` or size changed; size can only
  grow, and only where the class allows expansion.

## Not a finding here

- Field ordering, indentation, or `---` placement.
- Annotation and label naming preferences beyond the recommended keys.
- The absence of resources or probes on a Job that runs once and exits.
- Formatting a linter or `kubeconform` already validates.
