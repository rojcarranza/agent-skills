# Bamboo

Loaded when the diff touches `bamboo-specs/**`, `bamboo.y*ml`, or `*Spec.java`
under a specs directory. There is no live Bamboo access: review the specs as
code, and never claim what a build did.

## Plan structure

- A new task added to the wrong job, so it runs on a different agent than the
  work it depends on.
- Stages are sequential and jobs inside a stage are parallel — a change that
  moves a task between them changes what runs concurrently. Check for two
  jobs now writing the same path on the same agent.
- A stage marked manual, or its manual gate removed, changing whether a
  deploy needs approval. → always report the change, at least **Major** when
  the gate was removed.
- A final task (cleanup, artifact publish) moved out of the final position,
  so it no longer runs when an earlier task fails.
- A job with no timeout, able to hold an agent indefinitely.

## Variables

- Scope: global versus plan versus deployment versus build-specific. A
  variable referenced at a scope where it is not defined resolves to the
  literal `${bamboo.name}` string rather than failing. → **Major**.
- A variable renamed in the spec but still referenced by an inline script, or
  the reverse.
- `${bamboo.<var>}` used inside a shell script task where shell expansion and
  Bamboo substitution interact — Bamboo substitutes first, so a value with
  spaces or quotes breaks the script.
- A secret referenced without the password/secret variable type, so it is
  printed in the build log. → **Blocker**.
- A default added for a variable that should fail loudly when unset.

## Artifacts and dependencies

- A downstream job consuming an artifact whose producing job is now in the
  same stage (artifacts only cross stage boundaries).
- An artifact pattern changed so it matches nothing — the build passes and
  the deploy gets an empty directory.
- Shared artifact flag changed, affecting whether other plans can consume it.
- A plan trigger or dependency added that creates a cycle, or that fires a
  deploy on every branch build.

## Repositories and triggers

- Branch creation/deletion behavior, or the plan branch expiry, changed such
  that feature branch builds stop running.
- A trigger changed from polling to remote (or the reverse) without the
  corresponding hook.
- A checkout task that changes the working directory or disables clean
  checkout — stale files then persist between builds on the same agent.

## Agents and capabilities

- A task requiring a tool (`helm`, `kubectl`, a JDK version, a Python
  interpreter) with no matching capability requirement on the job. It works
  on the agent that happens to have it, and fails on the next one. → **Major**.
- A JDK or build tool version changed in the spec without the matching
  `pom.xml` or `go.mod` change, or the reverse.
- Docker-based tasks added where agents may not run a Docker daemon.
- Assumptions about the agent's OS, shell, or `PATH` — see the portability
  section of `cross-cutting.md`.

## Scripts inside specs

Inline script tasks get the full `lang-bash.md` treatment. Two Bamboo-specific
additions:

- A script that does not set `set -euo pipefail` — Bamboo marks the task
  failed only on a non-zero exit code from the script as a whole.
- Output that a later task parses being mixed with Bamboo's own log lines.

## Deployment projects

- An environment's tasks changed without the equivalent change in the other
  environments, so staging and production diverge silently.
- A release naming scheme changed, breaking the link between build and
  deploy.
- A rollback path that no longer matches the deploy path.

## Not a finding here

- YAML key ordering, quoting style, or comment placement in the specs.
- Plan or stage naming preferences.
- Task descriptions.
- Anything about Bamboo server configuration that the specs do not control.
