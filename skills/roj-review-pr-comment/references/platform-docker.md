# Docker

Loaded when the diff touches `Dockerfile*`, `*.dockerfile`, or
`docker-compose*.y*ml`.

## Base image

- A base image tag that is mutable (`latest`, `17`, `alpine`) where the build
  must be reproducible. Pin the version, and pin by digest where the registry
  allows it.
- A base image changed across distributions (Debian to Alpine, or the
  reverse): musl versus glibc breaks native dependencies, and the shell,
  package manager, and default user all change. → always report as runtime
  impact.
- A base image whose OS packages the build then installs from a repository
  that may not be reachable from the Bamboo agent's network.
- A multi-stage build losing its final stage's minimal base, so build
  toolchains ship to production.

## Secrets and build context

- `ARG` or `ENV` carrying a token, password, or private key — it stays in the
  image layer history regardless of a later `RUN rm`. → **Blocker**.
- A credential file `COPY`d in and deleted in a later layer: still present in
  the earlier layer. Use a build secret mount or a multi-stage copy.
- `COPY . .` with no `.dockerignore`, pulling `.git`, local `.env` files, and
  build output into the image.
- A `.dockerignore` entry removed in this diff — check what now enters the
  context.

## Layers and caching

- A `COPY` of the whole source placed before dependency installation,
  invalidating the dependency cache on every source change.
- Package manager cache not cleaned in the same `RUN` (`apt-get clean`,
  `rm -rf /var/lib/apt/lists/*`, `--no-cache` for apk), so the cleanup layer
  does not shrink the image.
- `apt-get install` without `--no-install-recommends` where size matters.
- `apt-get update` in a separate `RUN` from `install` — the update layer
  caches and the install then uses a stale index.

## Runtime configuration

- No `USER` directive, so the container runs as root. → **Major** in a
  deployed image.
- `ENTRYPOINT`/`CMD` in shell form where signal handling matters: the process
  runs under `/bin/sh -c` and does not receive `SIGTERM`, so the pod is
  killed after the grace period rather than shutting down. → **Major** for a
  long-running service.
- `WORKDIR` changed, invalidating relative paths elsewhere in the file or in
  the Kubernetes manifest's `command`/`args`.
- An `EXPOSE`d port that no longer matches the Service or the probe.
- Environment defaults added that shadow values the deployment sets.
- Healthcheck removed, or one whose interval and retries exceed the
  orchestrator's patience.

## Consistency with the rest of the diff

- A runtime dependency added to the application (a new Python package, a new
  CLI the script calls) with no corresponding install in the Dockerfile.
  → **Major**: it works locally and fails in the container.
- A tool version in the image diverging from the one pinned in `pom.xml`,
  `go.mod`, or the Bamboo agent capability.
- A file path referenced by a Kubernetes `volumeMount` or a Helm value that
  the image does not create.

## Compose files

- A published port bound to `0.0.0.0` where localhost was intended.
- A named volume replaced by a bind mount to a developer-specific path.
- A service dependency expressed with `depends_on` only, which waits for
  start and not for readiness.

## Not a finding here

- Instruction ordering that does not affect caching or correctness.
- `ADD` versus `COPY` where the source is a plain local path and the file is
  consistent.
- Label and comment conventions.
- Image size on a build-only stage.
