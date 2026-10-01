# Interviewer Calibration — DevOps (bundled copy)

Fallback for when the vault cheatsheet
(`2026-06-08-interviewer-cheatsheet.md`) is not available. If the vault
version exists, use it instead — it is authoritative.

## Linux

### Disk usage

- **Concept**: two layers. **Filesystem-level** (mounted volumes, how full) and **directory-level** (which folder is fat).
- **Above bar**: `df -h` for mounts, `du -sh *` or `du -h --max-depth=1` for hotspots, `ncdu` for interactive triage. Mentions inodes (`df -i`): you can be out of inodes with disk space left.
- **At bar**: `df` and `du`.
- **Below bar**: only knows GUI tools.
- **Probe:** ever had an inode-exhaustion outage?

### Permissions

- **Concept**: every file has owner, group, others, each with read/write/execute. Octal: r=4, w=2, x=1. So 755 = `rwxr-xr-x`. 644 = `rw-r--r--`.
- **Above bar**: explains octal fluently, knows `chmod`, `chown`, `chgrp`, mentions setuid (4xxx), setgid (2xxx), sticky bit (1xxx, common on `/tmp`). Says "don't `chmod 777`".
- **At bar**: knows octal, can change permissions.
- **Below bar**: only `chmod +x`.
- **Probe:** what does 4755 mean? (setuid + rwxr-xr-x, e.g. `/usr/bin/passwd`.)

### Extending storage

- **Concept**: kernel sees the new device -> partition it -> format -> mount -> persist.
- **Above bar**: `lsblk` to confirm, `fdisk`/`parted` for partition, `mkfs.ext4` or `xfs`, `mount`, add to `/etc/fstab` with UUID (not device path, which can change). Bonus: LVM (`pvcreate`, `vgextend`, `lvextend`, `resize2fs`) for online growth.
- **At bar**: format, mount, fstab.
- **Below bar**: skips fstab. Means it won't survive a reboot.
- **Probe:** why use UUID in fstab instead of `/dev/sdb1`?

### Host IPs

- **Concept**: kernel exposes interfaces via `iproute2`. `ifconfig` is from `net-tools`, deprecated.
- **Above bar**: `ip a` (or `ip addr`), `ip r` for routes, `hostname -I` for a quick list. Notes that `ifconfig` is legacy.
- **At bar**: knows one of `ip a` or `ifconfig`.
- **Below bar**: doesn't know `ip` at all.

---

## Git, trunk-based development

- **Concept**: everyone integrates to a single shared branch (`main`/`trunk`) at least daily. Branches are short-lived (hours). Unfinished work hides behind **feature flags**. Requires **fast, reliable CI** and high test coverage. The trade-off is: less merge hell, more discipline.
- **Above bar**: contrasts with GitFlow (long-lived develop/release branches, merge pain). Mentions release strategy (release from main, tag commits) and feature flags for incomplete work. Notes that CI must be fast and trustworthy or the model collapses.
- **At bar**: short-lived branches, daily merge to main.
- **Below bar**: confuses with "commit directly to main with no PR review".
- **Probe:** how do you ship a feature that takes 3 weeks to build?

---

## Docker Compose

- **Concept**: declarative file (`docker-compose.yml`) that brings up a multi-service stack on one machine. Designed for **local dev and small CI**, **not production**.
- **Above bar**: defines services, networks, volumes. Uses `depends_on` and healthchecks. Mounts source for hot-reload in dev. Separate compose files for dev vs CI. Knows that for prod you reach for Kubernetes or Nomad, not Compose.
- **At bar**: brings up app + database + cache.
- **Below bar**: thinks Compose is a prod orchestrator.
- **Probe:** how is `depends_on` different from waiting until the dependency is healthy?

---

## Kubernetes

- **Concept**: orchestrates containers across a cluster of nodes. The **control plane** holds desired state. **Controllers** continuously reconcile actual state to desired state. Containers run inside **Pods**. Pods are managed by higher-level objects: **Deployment** (stateless), **StatefulSet** (stateful, stable identity), **DaemonSet** (one per node, e.g. log shippers). **Services** give stable network endpoints. **Ingress** routes external traffic.
- **Above bar**: explains the control loop. Knows **HPA** scales pods on metrics, **Cluster Autoscaler** adds/removes nodes, **VPA** resizes pods. Mentions self-healing (a dead pod is recreated), rolling updates, readiness vs liveness probes.
- **At bar**: orchestrator, runs containers, can scale.
- **Below bar**: "it's Docker but bigger".
- **Probe:** difference between a readiness and a liveness probe? (Liveness restarts the pod if it fails. Readiness pulls it out of the Service until it passes again.)

### Other orchestrators

- **HashiCorp Nomad**: simpler, runs non-container workloads too.
- **AWS ECS**: AWS-native, easier than EKS for simple workloads.
- **Docker Swarm**: simple, mostly legacy now.
- **OpenShift**: Red Hat's K8s distribution with extras.

---

## CI/CD

### Types of tests

- **Unit**: a single class or function, no I/O, milliseconds, run on every commit.
- **Component**: a single service in isolation, mocked deps.
- **Contract**: producer and consumer agree on a schema (Pact). Catches breaking API changes.
- **Integration**: real database, real message broker, slower.
- **E2E**: full stack, browser or API client, brittle, run on merge or nightly.
- **Performance**: load and stress, scheduled.
- **Test pyramid**: lots of unit, fewer integration, very few e2e.

### Failed deployment

The right instinct order: **detect, communicate, recover, diagnose, prevent**.
- **Detect** via health checks, canary metrics, alerts.
- **Communicate** in the incident channel. Don't fix silently.
- **Recover** by rollback (previous Helm release, blue-green switch, revert deployment). Recovery beats root cause when users are bleeding.
- **Diagnose** after recovery with logs, traces, config diff, recent commits.
- **Prevent** with a post-mortem: monitoring gap, missing test, missing guardrail.

### Multi-environment pipeline

- **Above bar**: **build once, promote the same artefact**. Container image (or jar) is identical from dev to prod. Configuration changes per env via env vars, ConfigMaps, or per-env files. Auto-promote on tests pass, manual gate before prod. Build stage and deploy stage are separate. Bonus: artefact signing, SBOM.
- **At bar**: separate jobs per env, but they all rebuild.
- **Below bar**: rebuilds per env from source. Means dev and prod artefacts are not identical, you can't trust your testing.

### GitOps

- **Concept**: **Git is the source of truth for the desired state** of your infra and apps. A **controller** in the cluster (Argo CD, Flux) watches Git and reconciles the cluster to match. Changes happen by **PR**, not by `kubectl apply` from a laptop.
- **Above bar**: notes audit trail for free, easy rollback (`git revert`), drift detection, no direct cluster access needed for deploys. Knows the controller pulls, the pipeline doesn't push.
- **At bar**: "we use Argo CD".
- **Below bar**: "we use Git in our CI".
- **Probe:** what's the difference between push-based CD and pull-based GitOps?

---

## Infrastructure as Code

- **Concept**: infrastructure described in version-controlled code so it's **reproducible, reviewable, auditable, rollbackable**. Two flavours, often combined:
  - **Provisioning** (Terraform, Pulumi, CloudFormation): create cloud resources.
  - **Configuration management** (Ansible, Chef, Puppet): configure OS, install packages.
- **Above bar**: notes **idempotency** (apply twice -> same state), **drift detection** (real state vs declared state), **state file** (Terraform), modules, plan-then-apply workflow.
- **At bar**: "we use Terraform to create VMs".
- **Below bar**: "we run bash scripts".
- **Probe:** how do you handle secrets in Terraform state?

---

## CS basics

### Stack vs queue

- **Stack** = LIFO. Last in, first out. Use cases: undo, recursion / call stack, DFS, expression evaluation.
- **Queue** = FIFO. First in, first out. Use cases: task queues, message brokers, BFS, request buffering.

### Big O

- **Concept**: how runtime (or memory) grows as input size grows, ignoring constants.
- Common: O(1), O(log n), O(n), O(n log n), O(n^2), O(2^n).
- HashMap get/put: **O(1) average, O(n) worst** (all collisions, degenerates to a list, or a tree since Java 8 -> O(log n) worst).
- ArrayList get: O(1). add: O(1) amortized. remove from middle: O(n).
- LinkedList get: O(n). add to head/tail: O(1).

---

## OOP

### The four pillars

- **Abstraction**: expose what, hide how. Interface vs implementation.
- **Encapsulation**: bundle data with the operations on it, hide internals. Achieved with private fields + accessors.
- **Inheritance**: subclass reuses and extends a parent. Use sparingly. Prefer composition.
- **Polymorphism**: same call, different runtime behaviour based on type. Two kinds: **subtype** (override) and **ad-hoc** (overload).

### Overloading vs overriding

| | Overloading | Overriding |
|---|---|---|
| Where | Same class | Subclass |
| Signature | Different parameters | Same signature |
| Resolved | Compile time | Runtime |
| Annotation | none | `@Override` |
| Access modifier rule | n/a | subclass can't reduce visibility |

### Patterns worth knowing

- **Singleton**: one instance. Be careful, hides dependencies.
- **Factory**: create objects without exposing construction logic.
- **Builder**: complex objects with many optional fields.
- **Strategy**: swap algorithm at runtime.
- **Observer**: pub/sub, event-driven.
- **Decorator**: wrap to add behaviour without subclassing.

A good candidate names patterns they actually used and why. A weak one lists Gang of Four like flashcards.

---

## Clean code

### Signals of good code

Easy to **read**, easy to **change**, easy to **delete**. Small functions, clear names, single responsibility, low coupling, high cohesion. Tests exist and run fast.

### Comments

Nuance is the right answer.
- **Good**: comments explain **why** (business rule, weird workaround, non-obvious trade-off). Public API docs. License headers.
- **Smell**: comments explain **what** the code does. Usually the code should be clearer.
- **Bad**: comments that lie because the code changed and they didn't.

---

## Testing

### TDD

**Red, Green, Refactor.**
1. **Red**: write a test that fails.
2. **Green**: write the smallest code that makes it pass.
3. **Refactor**: clean up with the test as a safety net.

The point is **design pressure**: writing the test first forces you to design the API from the caller's view. The point is *not* "more tests".

### Mocking

Replace a real collaborator with a controlled fake to isolate the unit. Use for slow, non-deterministic, or external things: DB, network, file system, time, random.

**Over-mocking smell**: you're testing the mocks, not the behaviour. If your test is just "verify the mock was called", it's brittle and worthless.

### Java testing stack

- **JUnit 5** (Jupiter), the standard.
- **Mockito** for mocks.
- **AssertJ** or Hamcrest for readable assertions.
- **Testcontainers** for real dependencies (Postgres, Kafka) in tests.
- **WireMock** for HTTP doubles.
- **RestAssured** for HTTP assertions.

---

## The Java coding task, what to expect

Code is in the script. Four bugs, ranked by what a strong candidate will notice in order:

1. **`private` methods cannot be overridden.** In Java, private methods are not polymorphic. They're statically bound. So `@Override` on `Espresso.brew()` is a **compile error**: "method does not override or implement a method from a supertype". The strong candidate spots this immediately.

2. **The recursive field initializer.** `public CoffeeMachine coffeeMachine = new CoffeeMachine();` creates a new `CoffeeMachine` every time the constructor runs. The new one runs its initializers, which creates another. Result: **`StackOverflowError`** at runtime. This is the trap. Sharp candidates spot it on a second read.

3. **`makeCoffee` is `private`** in `CoffeeMachine`. That's fine inside the class (it's called from `main`), but if asked to extend `CoffeeMachine`, they should note this restricts use.

4. **`Cappuccino` has no `brew()` override.** Even after fixing the access modifiers, `new Cappuccino().brew()` would print the parent message ("You got some generic drink"). A candidate noticing this shows they're reading the *intent*, not just chasing errors.

### How to fix

```java
abstract class Drink {
    void brew() {                       // package-private, overridable
        System.out.println("You got some generic drink");
    }
}

class Espresso extends Drink {
    @Override
    void brew() { System.out.println("Here is your espresso"); }
}

class Cappuccino extends Drink {
    @Override
    void brew() { System.out.println("Here is your cappuccino"); }
}

public class CoffeeMachine {
    // removed the recursive field

    public CoffeeMachine() {}

    void makeCoffee(Drink drink) { drink.brew(); }

    public static void main(String[] args) {
        CoffeeMachine m = new CoffeeMachine();
        m.makeCoffee(new Espresso());
        m.makeCoffee(new Cappuccino());
    }
}
```

**Scoring guide:**
- Spots 1 and 2 -> hire-level.
- Spots 1 only -> on the line, probe further.
- Spots neither -> below bar for a Java-primary role.

---

## The Python coding task, what to expect

```python
def whoami(n):
    D = {}
    q = 2
    while q <= n:
        if q not in D:
            yield q
            D[q * q] = [q]
        else:
            for p in D[q]:
                D.setdefault(p + q, []).append(p)
            del D[q]
        q += 1
```

**What it is**: a **prime sieve**, a generator variant of the Sieve of Eratosthenes. For `n = 24` it yields `2, 3, 5, 7, 11, 13, 17, 19, 23`.

**How it works** (the elegant bit):
- `D` maps **the next composite to wipe** -> list of primes that produced it.
- When `q` is **not in `D`**, it's prime: yield it, then record that its square (`q*q`) is the first composite this prime will mark.
- When `q` is **in `D`**, it's composite: for each prime that marked it, schedule the next composite (`p + q`) for that prime, then drop the current entry.

**What you're listening for:**
- **They notice `yield`** -> it's a **generator**, lazy. Nothing happens until iterated. The commented-out `[i for i in x]` would drive it.
- **They identify it's about primes** within a minute of reading.
- **Bonus**: explains the dictionary trick (lazy sieve, only stores upcoming composites instead of a full boolean array).

**Below bar**: stares at it, can't figure out what `yield` does. For a role where Python is "nice-to-have", that's tolerable, but note it.

---

## The incident scenario, the answer framework

The model answer is a **mental checklist**, not a script. Order matters.

1. **Confirm and scope**. Look at dashboards, error rate, latency, which services. Is it all of prod, one region, one service? **A bad answer starts with logs**. Logs come later.
2. **Communicate immediately**. Incident channel, page on-call peer, update status page if relevant. Set expectations: "investigating, will update in 10 minutes."
3. **Stabilize before you understand**. Rollback to last good release, drain a bad node, scale up, flip a feature flag off. **Recovery beats root cause.**
4. **Verify recovery**. Health checks green, smoke tests pass, error rate dropped. Don't declare resolved on a hunch.
5. **Diagnose**. Now look at logs, traces, recent merges, config diff, infra changes. The most likely culprit is the most recent change.
6. **Decide: fix-forward or stay reverted.** Under pressure, stay reverted. Ship the fix through the normal pipeline.
7. **Post-incident**. Timeline, root cause, action items. **At least one action that closes the gap that let this happen**: new alert, new test, runbook, automation, guardrail.

**Strong signals**: mentions communication early, rolls back fast, talks about a post-mortem and a follow-up action.
**Weak signals**: starts by debugging code, no rollback plan, blames "the team", no follow-up action.

---

## Final calibration

Before you give a recommendation, ask yourself the four guide questions:

1. Could I sit next to this person daily and enjoy it?
2. Will they raise the team's bar, or lean on it?
3. When they don't know, do they say so?
4. When they disagree, can they hold their ground respectfully?

A clear "yes" on all four is a hire. A clear "no" on any is at least a serious conversation with HR + PM before moving forward.

---
