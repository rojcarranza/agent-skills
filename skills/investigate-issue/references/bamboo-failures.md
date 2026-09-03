# Bamboo failure catalog

Evidence checklists for `bamboo-plan` and `bamboo-agent` issue classes.
Each entry: symptom → what to check in the problem `.md` and the repo.
All checks are static — no live Bamboo access.

## Plan / pipeline side

### Script task fails

- **Exit code non-zero, unclear which command**: inline scripts run as
  one shell — without `set -e` a mid-script failure is swallowed and the
  *last* command's exit code decides the task result. Check the script
  (inline in plan spec, or file in repo) for missing
  `set -euo pipefail`; check whether the failing command's error appears
  mid-log while the task still ran further commands.
- **`command not found`**: tool missing on the agent (see agent side) or
  PATH differs — plan specs run non-login shells; `.bashrc`/`.profile`
  additions are absent. Check for tools referenced by bare name that the
  repo installs elsewhere.
- **Works locally, fails in plan**: working-directory assumption. Script
  tasks start in the job's build directory
  (`.../xml-data/build-dir/<PLAN>-<JOB>`), not the repo subdir. Check
  `cd` calls, relative paths, and the task's declared working
  subdirectory in the plan spec.

### Plan specs (Java or YAML)

- **Spec build fails**: compile error in Java specs — treat as
  `repo-code (java)` and reproduce with the specs project's Maven build.
- **Change didn't take effect**: specs publish on commit to the linked
  repo; check log for the specs execution result, and check the spec
  actually targets the plan key in question.
- **Variable empty/wrong**: Bamboo variables are `${bamboo.name}` in
  tasks and `bamboo_name` as env vars in scripts. Common causes: plan
  variable vs global variable shadowing; deployment-project variables
  not visible to build plans; variables containing `password`/`secret`
  are masked to `********` in logs (masking is not the bug). Check the
  spec's variable definitions against the names the script reads.

### Checkout / repository

- **File missing that exists in repo**: shallow clone or wrong
  branch/revision — check checkout task config in spec (force clean,
  shallow clones toggle) and whether the file arrived after the plan
  branch diverged.
- **Stale state between builds**: no clean checkout; leftover build
  artifacts from previous run in the build dir. Check for "Force clean
  build" absence + untracked files the script assumes absent.
- **Submodules empty**: submodule checkout not enabled on the linked
  repository config.

### Artifacts

- **Artifact empty / not found in later stage**: copy pattern is
  relative to the artifact's declared *location* dir, not repo root.
  Check location + copy pattern against where the build actually writes
  output. Shared flag must be on for cross-stage/job consumption;
  consuming job needs an artifact *dependency*, not just same plan.
- **Jobs can't see each other's files**: jobs (even same stage) run on
  potentially different agents with separate build dirs — files move
  between jobs ONLY via artifacts. Any hypothesis assuming shared disk
  between jobs is wrong.

### Stages / structure

- **Order-dependent failures**: stages run sequentially, jobs within a
  stage run in parallel. Race between parallel jobs (shared external
  resource, same deploy target) is a candidate whenever two jobs touch
  one thing.
- **Task skipped silently**: final tasks run even after failure;
  regular tasks stop at first failing task. Check task order and
  "final" flags in the spec.

## Agent side

### Capability / routing

- **Build queued forever or "no agent can build"**: job requirements vs
  agent capabilities mismatch. Check requirements in the spec
  (explicit `requirement` entries, plus implicit ones added by
  executable tasks like Maven/JDK selections) against what the intended
  agent offers.
- **Wrong agent picked it up**: missing distinguishing requirement;
  check whether the plan pins agent via requirement at all.

### Tools / environment

- **`command not found` / version mismatch on agent**: tool absent or
  older than local. Check repo for version pins (`pom.xml`
  maven-enforcer, `go.mod` go directive, `.python-version`,
  `Dockerfile` base tags) vs versions visible in the build log header.
- **JDK mismatch**: log usually prints the JDK; compare with
  `pom.xml`/`build.gradle` target. `Unsupported class file major
  version` / `invalid target release` = exactly this.
- **Env var set locally, absent on agent**: capabilities and
  `bamboo-capabilities.properties` define agent env; scripts reading
  `$HOME`-dependent config (`~/.m2/settings.xml`, `~/.netrc`,
  `~/.docker/config.json`) behave differently under the bamboo user.
- **Ephemeral/elastic agent missing tool**: agent image lacks the tool;
  fix belongs in the agent image definition, not the plan.

### Host state

- **Intermittent failures, one agent only**: agent-local state — disk
  full (`No space left on device`), leftover processes, corrupted local
  caches (`~/.m2`, `~/.gradle`, go module cache), docker daemon state.
  Evidence: same plan green on other agents; agent name in failing runs
  constant.
- **Permission denied on build dir files**: files created as root by a
  previous docker-based task now unremovable/unwritable by the bamboo
  user. Check for docker tasks writing into the build dir without
  `--user` mapping.
- **Clock/locale oddities**: token/cert validation errors ("not yet
  valid"), date-parsing test failures only on agent.

### Docker on agent

- **`Cannot connect to the Docker daemon`**: docker not running or
  bamboo user not in docker group on that agent.
- **Image pull fails on agent, works locally**: registry auth is
  per-user (`~/.docker/config.json` of the bamboo user) or proxy
  differs on the agent host.

## Deciding Probable

Agent/env causes rarely reproduce locally. Mark **Probable** only when:
the evidence list of one entry above matches, no competing hypothesis
survives, and the report's Verification section says exactly which
build/agent to rerun to confirm.
