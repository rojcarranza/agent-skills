# Example Platform / PROJ-1001

> **Goal:** Validate that all Bamboo agents and build plans are compatible and operational after the ACC
> environment upgrade to Bamboo 12.1.6, with every component on Java 21.

---

## ⚠️ Java Version Requirement

Bamboo 12.1.x requires **Java 21 as a minimum** (Java 17 support was dropped in Bamboo 12.0).

| Java Version | Compatible with Bamboo 12.1.x? |
|---|---|
| Java 8 | ❌ Will NOT connect to a 12.1.x server |
| Java 11 | ❌ Will NOT connect to a 12.1.x server |
| Java 17 | ❌ Support dropped in Bamboo 12.0 |
| Java 21 | ✅ Required minimum |
| Java 25 | ✅ Supported — installed as an additional build capability |

---

## Acceptance Criteria

- [ ] A PR is prepared in which our Maven dependency is updated to use the new Bamboo API version
  - [ ] POM is updated
- [ ] A test is performed against the ACC environment from our local development environment to see if we can deploy several plans
- [ ] The plan publisher is executed on ACC
  - [ ] It should be able to deploy all plans
  - [ ] It should succeed running all unit tests
- [ ] It is checked if we can still communicate with the various Bamboo REST APIs
  - [ ] We add a simple test plan which can call another plan and read out the results to at least test the Bamboo API functionality
  - [ ] Code is adapted if needed
- [ ] If any critical issue is found that is not easy to solve, the responsible team is informed
  - [ ] Inform the release manager that not everything can be tested (ACC is isolated from external systems)
  - [ ] The prepared PR is kept up to date until the new Bamboo version is released to production
- [ ] All remote agents are confirmed to be running Java 21. *(proposed)*
- [ ] `ci-agent-image` and `ci-agent-helm` changes are reviewed and merged. *(proposed)*
- [ ] A new agent image is built, tagged and published after the repository changes. *(proposed)*
- [ ] The Helm chart is deployed to ACC with the new image tag and the ACC server URL, and agent connectivity is confirmed. *(proposed)*

---

## Core tasks

- [ ] `plan-specs`: update the Bamboo API dependency in `pom.xml` to the 12.1.6 version.
- [ ] `ci-agent-image`: apply the agent changes in the table below.
- [ ] `ci-agent-helm`: set the ACC server URL and the new image tag (table below).
- [ ] Run the plan publisher on ACC and confirm all plans deploy.
- [ ] Validate Bamboo REST API communication — Basic Auth is disabled by default on new instances, so check every call that relies on it.
- [ ] `plan-specs`: add a test plan that calls another plan and reads back its result.
- [ ] Inform the release manager about the scenarios ACC isolation prevents us from testing.

### `ci-agent-image`

| # | File/Property | Before | After | Reason |
|---|---|---|---|---|
| 1 | `docker/Dockerfile` `BAMBOO_VERSION` | `9.6.9` | **`12.1.6`** | The agent JAR fetched at build time must match the server version; a 9.6.9 agent will not connect to a 12.1.x server. |
| 2 | `docker/wrapper.conf` `wrapper.java.version.min` | `8` | **`21`** | Stops the wrapper from starting on a JDK that cannot connect. |
| 3 | `docker/wrapper.conf` `wrapper.java.version.fallback` | `11` | **`21`** | The fallback must not drop to an incompatible JDK. |
| 4 | `docker/agent.sh` `JAVA_FALLBACK` | `/opt/java/jdk-8/bin/java` | **`/opt/java/jdk-21/bin/java`** | If `/usr/bin/java` is missing at runtime, the old fallback starts the agent on Java 8. |

> **Already compliant ✅ (checked, no change needed):**
> - Java 21 is the system default via `alternatives` and `JAVA_HOME`.
> - `--add-opens` JVM flags for Java 21 module access are already present in `wrapper.conf`.

### `ci-agent-helm`

| # | File/Property | Before | After | Reason |
|---|---|---|---|---|
| 5 | `values.yaml` `agent_server_url` | production URL | ACC server URL (in `values-acc.yaml`) | Agents under test must not register with the production server. |
| 6 | `values.yaml` `imagetag` (all 4 pools) | `2026-02-17_13-53` | new image tag | The current tag is the image built against Bamboo 9.6.9. |

---

## Questions

- Do we add a slide to our sprint review presentation for this story?
- What is the confirmed ACC server URL for `agent_server_url`? It is not in any checked-out repository.
- Is Basic Auth still enabled on the upgraded ACC instance for our REST integrations?
- Should we keep a dedicated `values-acc.yaml` so ACC and production Helm values never mix?
- Repo `plan-publisher` is not cloned locally — investigate before implementation.

## Notes

- Older JDKs (8, 11, 17) stay registered as executable capabilities for plans that need them; only the agent wrapper must run on Java 21.
- ACC may still be linked to production repositories. Confirm the linked repository in the build logs; re-saving the configuration fixes the link.
- ACC is isolated from some external systems, so not every scenario can be tested there.
- Impacted repositories: `plan-specs`, `ci-agent-image`, `ci-agent-helm`, `plan-publisher` (not cloned).

## Testing

| Test Case ID | Situation | Expected result | Log | Build result link |
|--------------|-----------|-----------------|-----|-------------------|
| TC-1 | Run the plan publisher against ACC | All plans deploy without errors | | |
| TC-2 | Run the `plan-specs` unit tests on the new API version | All tests pass | | |
| TC-3 | Run the new test plan that calls a second plan | The second plan's result is read back | | |
| TC-4 | Deploy the Helm chart to ACC with the new image | All 4 agent pools show **Online** | | |
| TC-5 | Inspect an agent build log | The agent reports Java 21 | | |
