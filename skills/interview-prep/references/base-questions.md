# Baseline Technical Questions — DevOps

Fixed set. Every candidate gets all of these regardless of CV. Embed them in
full in the generated interview doc (section "Baseline technical questions");
order may be tuned per candidate, content may not.

### B1. Linux — disk usage triage [Easy]

**Ask:** A server's disk is filling up. How do you find what's eating it?

**Expected:** Two layers: filesystem-level (`df -h` for mounts) and
directory-level (`du -sh *` / `du -h --max-depth=1`, `ncdu` for interactive
triage). Above bar mentions inodes (`df -i`) — you can be out of inodes with
disk space left. At bar: `df` and `du`. Below bar: only GUI tools.

**Probe:** Ever had an inode-exhaustion outage?

**Red flags:** Only knows GUI tools; no mount vs directory distinction.

**Comment:**

### B2. Linux — permissions [Easy]

**Ask:** Explain file permissions and the octal notation. What does `chmod 4755` mean?

**Expected:** Every file has owner, group, others, each with read/write/execute.
Octal: r=4, w=2, x=1, so 755 = `rwxr-xr-x`, 644 = `rw-r--r--`. Above bar
explains octal fluently, knows `chmod`/`chown`/`chgrp`, mentions setuid
(4xxx), setgid (2xxx), sticky bit (1xxx, common on `/tmp`), and says "don't
`chmod 777`". At bar: knows octal, can change permissions. Below bar: only
`chmod +x`.

**Probe:** What does 4755 mean? (setuid + rwxr-xr-x, e.g. `/usr/bin/passwd`.)

**Red flags:** Can't explain octal; only knows `chmod +x`.

**Comment:**

### B3. Git — trunk-based development [Medium]

**Ask:** Explain trunk-based development vs GitFlow.

**Expected:** Everyone integrates to a single shared branch (`main`/`trunk`)
at least daily. Branches are short-lived (hours). Unfinished work hides
behind feature flags. Requires fast, reliable CI and high test coverage —
the trade-off is less merge hell, more discipline. Above bar contrasts with
GitFlow (long-lived develop/release branches, merge pain), mentions release
strategy (release from main, tag commits) and feature flags, notes CI must
be fast and trustworthy or the model collapses. At bar: short-lived branches,
daily merge to main. Below bar: confuses with "commit directly to main with
no PR review".

**Probe:** How do you ship a feature that takes 3 weeks to build?

**Red flags:** Thinks trunk-based means no code review at all.

**Comment:**

### B4. Docker Compose — purpose and limits [Easy-Medium]

**Ask:** What is Docker Compose for? Would you run it in production?

**Expected:** Declarative file (`docker-compose.yml`) that brings up a
multi-service stack on one machine. Designed for local dev and small CI, not
production. Above bar defines services, networks, volumes; uses `depends_on`
and healthchecks; mounts source for hot-reload in dev; separate compose
files for dev vs CI; knows that for prod you reach for Kubernetes or Nomad,
not Compose. At bar: brings up app + database + cache. Below bar: thinks
Compose is a prod orchestrator.

**Probe:** How is `depends_on` different from waiting until the dependency is healthy?

**Red flags:** Thinks Compose is a production orchestrator.

**Comment:**

### B5. Kubernetes — core concepts [Medium]

**Ask:** What does Kubernetes do? Walk me through control plane, workload
objects (Deployment/StatefulSet/DaemonSet), and Services.

**Expected:** Orchestrates containers across a cluster of nodes. The control
plane holds desired state; controllers continuously reconcile actual state
to desired state. Containers run inside Pods, managed by higher-level
objects: Deployment (stateless), StatefulSet (stateful, stable identity),
DaemonSet (one per node, e.g. log shippers). Services give stable network
endpoints; Ingress routes external traffic. Above bar explains the control
loop, knows HPA scales pods on metrics, Cluster Autoscaler adds/removes
nodes, VPA resizes pods, mentions self-healing, rolling updates, readiness
vs liveness probes. At bar: orchestrator, runs containers, can scale. Below
bar: "it's Docker but bigger".

**Probe:** Difference between a readiness and a liveness probe? (Liveness
restarts the pod if it fails. Readiness pulls it out of the Service until
it passes again.)

**Red flags:** "It's Docker but bigger" with no further detail.

**Comment:**

### B6. CI/CD — multi-environment pipeline [Medium]

**Ask:** How would you design a pipeline that promotes a change from dev to
test to prod?

**Expected:** Above bar: build once, promote the same artefact — container
image (or jar) is identical from dev to prod, configuration changes per env
via env vars/ConfigMaps/per-env files, auto-promote on tests pass, manual
gate before prod, build stage and deploy stage are separate. Bonus:
artefact signing, SBOM. At bar: separate jobs per env, but they all rebuild.
Below bar: rebuilds per env from source — dev and prod artefacts are not
identical, so testing can't be trusted.

**Probe:** If it rebuilds per environment, ask what breaks when the build
isn't reproducible.

**Red flags:** Rebuilds separately per environment with no artefact
promotion concept.

**Comment:**

### B7. CI/CD — GitOps [Medium]

**Ask:** What is GitOps?

**Expected:** Git is the source of truth for the desired state of infra and
apps. A controller in the cluster (Argo CD, Flux) watches Git and reconciles
the cluster to match. Changes happen by PR, not by `kubectl apply` from a
laptop. Above bar notes audit trail for free, easy rollback (`git revert`),
drift detection, no direct cluster access needed for deploys, and knows the
controller pulls while the pipeline doesn't push. At bar: "we use Argo CD".
Below bar: "we use Git in our CI".

**Probe:** What's the difference between push-based CD and pull-based GitOps?

**Red flags:** Equates "using Git in CI" with GitOps.

**Comment:**

### B8. Infrastructure as Code [Medium]

**Ask:** Why use Infrastructure as Code? What problems does it solve?

**Expected:** Infrastructure described in version-controlled code so it's
reproducible, reviewable, auditable, rollbackable. Two flavours, often
combined: provisioning (Terraform, Pulumi, CloudFormation) creates cloud
resources; configuration management (Ansible, Chef, Puppet) configures OS,
installs packages. Above bar notes idempotency (apply twice -> same state),
drift detection (real state vs declared state), state file (Terraform),
modules, plan-then-apply workflow. At bar: "we use Terraform to create VMs".
Below bar: "we run bash scripts".

**Probe:** How do you handle secrets in Terraform state?

**Red flags:** No concept of idempotency or state; equates IaC with ad hoc
bash scripts.

**Comment:**

### B9. The incident scenario — answer framework [Hard]

**Ask:** Production goes down right after a deploy. Walk me through your
first 30 minutes.

**Expected:** The model answer is a mental checklist, not a script, and
order matters:
1. Confirm and scope — dashboards, error rate, latency, which services. Is
   it all of prod, one region, one service? A bad answer starts with logs;
   logs come later.
2. Communicate immediately — incident channel, page on-call peer, update
   status page if relevant. Set expectations: "investigating, will update
   in 10 minutes."
3. Stabilize before you understand — rollback to last good release, drain a
   bad node, scale up, flip a feature flag off. Recovery beats root cause.
4. Verify recovery — health checks green, smoke tests pass, error rate
   dropped. Don't declare resolved on a hunch.
5. Diagnose — now look at logs, traces, recent merges, config diff, infra
   changes. The most likely culprit is the most recent change.
6. Decide: fix-forward or stay reverted. Under pressure, stay reverted; ship
   the fix through the normal pipeline.
7. Post-incident — timeline, root cause, action items. At least one action
   that closes the gap that let this happen: new alert, new test, runbook,
   automation, guardrail.

**Probe:** Strong signals: mentions communication early, rolls back fast,
talks about a post-mortem and a follow-up action. Weak signals: starts by
debugging code, no rollback plan, blames "the team", no follow-up action.

**Red flags:** Starts with logs/debugging instead of scoping and
communicating; no rollback plan; blames the team; no follow-up action.

**Comment:**

### B10. OOP & Testing — overloading, TDD, mocking [Easy]

**Ask:** What's the difference between overloading and overriding? What's
the point of TDD? What's mocking for, and when does it go wrong?

**Expected:** Overloading is same class, different parameters, resolved at
compile time. Overriding is subclass, same signature, resolved at runtime,
uses `@Override`, and a subclass can't reduce visibility. TDD is Red (write
a failing test), Green (smallest code to pass), Refactor (clean up with the
test as a safety net) — the point is design pressure: writing the test
first forces you to design the API from the caller's view, not "more
tests". Mocking replaces a real collaborator with a controlled fake to
isolate the unit — used for slow, non-deterministic, or external things
(DB, network, file system, time, random).

**Probe:** What's the over-mocking smell? (You're testing the mocks, not
the behaviour — if your test is just "verify the mock was called", it's
brittle and worthless.)

**Red flags:** Confuses overloading and overriding; thinks TDD means
writing more tests rather than design pressure; can't identify the
over-mocking smell.

**Comment:**

### B11. Python — production-grade scripting [Medium]

**Ask:** You're writing a Python tool the team will run in the pipeline every
day. What separates a production-grade script from a quick hack?

**Expected:** Dependency isolation (venv/virtualenv, pinned requirements),
argument parsing (`argparse`) instead of hard-coded values, logging instead
of prints, explicit error handling and non-zero exit codes, tests. Above bar
mentions generators/iterators for large data (lazy, low memory), type hints,
packaging (`pyproject.toml`), and knows list comprehension vs generator
expression trade-off. At bar: venv + error handling. Below bar: "I'd just
write the script".

**Probe:** What does the GIL mean for a script doing lots of network calls
vs one doing heavy computation? (I/O-bound: threads fine, GIL released on
I/O. CPU-bound: need multiprocessing.)

**Red flags:** No concept of dependency isolation; global-state spaghetti
presented as normal.

**Comment:**

### B12. Java — JVM basics for tooling [Medium]

**Ask:** Java is our primary pipeline-scripting language. Walk me through
the basics: JDK vs JRE vs JVM, how dependencies are managed, and what you
watch for when a Java process runs in CI.

**Expected:** JVM executes bytecode; JRE = JVM + runtime libs; JDK = JRE +
compiler/tools. Dependencies via Maven or Gradle (declarative, transitive
resolution, local repo cache). In CI: heap sizing (`-Xmx`), GC pauses,
`OutOfMemoryError` vs container memory limits (JVM must be told about
cgroup limits on older versions). Above bar: knows classpath mechanics,
fat/uber jars, and that container-aware JVM flags matter. At bar: JDK
compiles, Maven builds. Below bar: can't separate JVM from Java syntax.

**Probe:** CI job dies with `OutOfMemoryError` only inside Docker — where
do you look first? (Container memory limit vs `-Xmx`; JVM default heap
sizing off host RAM.)

**Red flags:** Never touched build tooling; thinks Java knowledge ends at
the language.

**Comment:**

### B13. Go — why DevOps tooling loves it [Easy-Medium, Optional]

**Ask:** Why did Go become the default language for infrastructure tools —
Docker, Kubernetes, Terraform are all written in it?

**Expected:** Compiles to a single static binary (no runtime to install,
trivial container images), fast compile, cross-compilation built in,
goroutines/channels make concurrent network services simple, standard
library covers HTTP/JSON well. Above bar: explains goroutines vs OS threads
(multiplexed, cheap, scheduler in runtime) and channels for communication.
At bar: static binaries + concurrency. Below bar / honest zero: fine —
optional skill; calibrate honesty.

**Probe:** What's the difference between a goroutine and a thread?

**Red flags:** Claims Go experience but can't explain what a goroutine is.

**Comment:**

### B14. Kubernetes — Helm charts [Medium]

**Ask:** What does Helm add on top of raw Kubernetes manifests?

**Expected:** Package manager for K8s: a chart bundles templated manifests,
`values.yaml` parameterizes per environment, releases are versioned installs
into a cluster, `helm upgrade` / `helm rollback` manage lifecycle. Above
bar: template functions/helpers, chart dependencies, hooks, `helm diff`,
knows values-layering per env replaces manifest copy-paste, and where Helm
ends (no drift reconciliation — that's GitOps controllers). At bar:
"templating + install tool". Below bar: never used, thinks it's part of
kubectl.

**Probe:** `helm rollback` vs `kubectl rollout undo` — what's the
difference? (Helm reverts the whole release — all objects, values included;
rollout undo reverts one workload's pod template.)

**Red flags:** Helm on CV but can't describe values.yaml.

**Comment:**

### B15. Ansible — configuration management [Medium]

**Ask:** How does Ansible work, and where does it sit next to Terraform?

**Expected:** Agentless config management over SSH: inventory defines hosts,
playbooks (YAML) apply roles/tasks using modules. Idempotent by design —
modules describe desired state, running twice converges to the same result.
Terraform provisions infrastructure (creates the VM); Ansible configures it
(packages, users, files) — often combined. Above bar: roles for reuse,
handlers, vault for secrets, knows `shell`/`command` tasks break idempotency
unless guarded (`creates:`, `changed_when`). At bar: playbooks + inventory.
Below bar: "it runs scripts on servers".

**Probe:** How do you keep a playbook idempotent when you must run a raw
shell command?

**Red flags:** No idempotency concept; can't distinguish provisioning from
configuration.

**Comment:**

### B16. Bamboo — CI server and agents [Medium]

**Ask:** Our CI runs on Bamboo. Explain the moving parts of a CI server like
Bamboo or Jenkins: plans, stages, and how agents pick up work.

**Expected:** Build plan = pipeline definition; stages run sequentially,
jobs within a stage run in parallel; each job needs an agent. Agents are
local (on the server) or remote (separate machines); each declares
capabilities (JDK version, Docker, OS), and jobs declare requirements — the
server matches them. Above bar: elastic agents (spun on demand), agent
capacity as the usual bottleneck, artifacts passed between stages, and maps
all of it fluently from Jenkins experience (executor ≈ agent, Jenkinsfile ≈
plan). At bar: pipeline + agents run jobs. Below bar: only ever clicked
"run" in a UI.

**Probe:** A job sits queued forever while agents look idle — what's your
first check? (Capability/requirement mismatch.)

**Red flags:** No mental model of where builds physically execute.

**Comment:**

### B17. Splunk — centralized logging [Easy-Medium]

**Ask:** What is Splunk for, and how does log data get from a server into a
searchable dashboard?

**Expected:** Centralized log aggregation and search: forwarders on hosts
ship logs, indexers parse and store them, search heads run queries (SPL),
dashboards and alerts sit on top. Above bar: universal vs heavy forwarder,
index-time vs search-time field extraction, retention/index sizing, alerts
driving on-call, and can sketch an equivalent open stack (ELK, Loki) —
concepts transfer. At bar: "search engine for logs, agents ship them".
Below bar: "it's a dashboard".

**Probe:** You need error rate per service over the last hour — roughly what
does that search look like? (index/sourcetype filter, `stats count by`,
time window.)

**Red flags:** Claims Splunk but has never written a search.

**Comment:**

### B18. DCOS / Zookeeper / Mesos / Ambari [Medium, Optional]

**Ask:** Ever touched the Mesos-era stack — DC/OS, Zookeeper, Ambari? What
does Zookeeper actually provide to systems that depend on it?

**Expected:** Zookeeper: distributed coordination — consistent small
key-value store (znodes) used for config, service discovery, locks, leader
election; ephemeral znodes make failure detection work; needs an odd-sized
ensemble for quorum. Mesos: two-level scheduling — offers resources to
frameworks (Marathon for services), K8s largely won this space; DC/OS is
the commercial Mesos distribution. Ambari: provisioning/management UI for
Hadoop clusters. Above bar: quorum math (majority must be up), what
breaks on quorum loss (writes stop, dependents like Kafka/Mesos masters
degrade). Honest zero is acceptable — optional; calibrate honesty and
transfer reasoning from K8s (etcd plays Zookeeper's role).

**Probe:** 5-node Zookeeper ensemble — how many can you lose? (2; quorum
needs 3.)

**Red flags:** Bluffs familiarity; can't say what coordination even means.

**Comment:**

### B19. HDFS — architecture [Easy-Medium]

**Ask:** Sketch HDFS for me: what runs where, and what happens when a node
dies?

**Expected:** Distributed filesystem for large sequential reads: NameNode
holds metadata (namespace, block locations) in memory; DataNodes store
fixed-size blocks (128MB default); each block replicated (factor 3,
rack-aware). Write-once, append-only model. DataNode death: heartbeats stop,
NameNode re-replicates its blocks from surviving copies — self-healing. Above
bar: NameNode as SPOF and its HA setup (standby + journal nodes), why small
files hurt (metadata pressure), block size rationale (seek vs throughput).
At bar: NameNode metadata / DataNode blocks / replication. Below bar: "it's
Hadoop's disk".

**Probe:** Why huge blocks (128MB) instead of 4KB like a local filesystem?

**Red flags:** No replication concept; confuses HDFS with a database.

**Comment:**

### B20. Cloud — Azure or AWS core services [Medium]

**Ask:** Take your stronger cloud. Map the core building blocks: compute,
storage, networking, identity, managed Kubernetes — and name the equivalent
on the other cloud.

**Expected:** AWS: EC2, S3 (object) / EBS (block), VPC + subnets + security
groups, IAM (roles, policies), EKS. Azure: VMs, Blob Storage / managed
disks, VNet + NSGs, Entra ID (AAD) + RBAC, AKS. Above bar: IAM roles over
long-lived access keys (temporary credentials, no secret to leak),
public/private subnet design, managed-service trade-off (control vs
operational load) and cost awareness. At bar: names compute/storage/network
on one cloud. Below bar: "we had cloud" with no nameable service.

**Probe:** Why is an IAM role attached to a VM better than an access key in
a config file?

**Red flags:** Cloud listed on CV but can't name five services.

**Comment:**

### B21. Databases — Postgres, MongoDB, neo4j [Medium]

**Ask:** Same data, three databases: Postgres, MongoDB, neo4j. When is each
the right choice, and what does adding an index actually do?

**Expected:** Postgres: relational, ACID transactions, joins, schema —
default choice for structured data. MongoDB: document store, flexible
schema, natural fit for nested/varying JSON-shaped data. neo4j: graph —
when relationships ARE the data (dependencies, networks, recommendations)
and traversals would be join explosions in SQL. Index: extra structure
(B-tree typically) making reads O(log n) instead of scans, paid for with
slower writes and storage. Above bar: replication basics (Postgres
primary/replica streaming, Mongo replica sets), connection pooling, knows
"schemaless" still means schema-in-code. At bar: relational vs document vs
graph distinction. Below bar: can't differentiate them.

**Probe:** A query is slow; you add an index and writes get slower — why?

**Red flags:** No idea what an index is; picks the database by fashion.

**Comment:**

### B22. CS basics — data structures and Big O [Easy]

**Ask:** Stack vs queue — and where does each show up in real systems? Then:
HashMap get, ArrayList get, LinkedList get — complexities?

**Expected:** Stack = LIFO: undo, recursion/call stack, DFS, expression
evaluation. Queue = FIFO: task queues, message brokers, BFS, request
buffering. Big O = how runtime/memory grows with input, ignoring constants.
HashMap get/put: O(1) average, O(n) worst (all collisions; a tree since
Java 8 -> O(log n) worst). ArrayList: get O(1), add O(1) amortized, remove
from middle O(n). LinkedList: get O(n), add to head/tail O(1). At bar:
LIFO/FIFO + HashMap O(1). Below bar: can't rank O(1) vs O(n).

**Probe:** When does a HashMap degrade, and what did Java 8 change about
it?

**Red flags:** No use case for either structure; guesses complexities.

**Comment:**

### B23. Linux — VM creation on vSphere [Medium]

**Ask:** You need ten identical Linux VMs on VMware vSphere for a new test
environment. Walk me through how you'd do it.

**Expected:** Build one golden VM (or use an existing template): install OS,
VMware Tools, harden/configure; convert to template, then clone ten times
with per-VM customization (hostname, IP via customization spec or
cloud-init). Above bar: templates vs full clones vs linked clones,
right-sizing CPU/RAM, resource pools, and automating it (PowerCLI,
Terraform vSphere provider, Packer for image builds) rather than clicking
ten times. Post-clone disk growth: extend in vSphere, then `lsblk`, grow
partition, `resize2fs`/`xfs_growfs`. Type 1 vs type 2 hypervisor if asked.
At bar: template + clone by hand. Below bar: installs the OS ten times from
ISO.

**Probe:** You grew the virtual disk in vSphere but the guest still shows
the old size — what's missing? (Partition + filesystem growth inside the
guest.)

**Red flags:** No template concept; manual ISO installs presented as the
method.

**Comment:**

### BC1. Java coding task — CoffeeMachine [Pen & paper]

**Ask:** Review this Java program. What's wrong with it, and how would you
fix it?

```java
abstract class Drink {
    private void brew() {
        System.out.println("You got some generic drink");
    }
}

class Espresso extends Drink {
    @Override
    private void brew() {
        System.out.println("Here is your espresso");
    }
}

class Cappuccino extends Drink {
}

public class CoffeeMachine {
    public CoffeeMachine coffeeMachine = new CoffeeMachine();

    public CoffeeMachine() {}

    private void makeCoffee(Drink drink) {
        drink.brew();
    }

    public static void main(String[] args) {
        CoffeeMachine coffeeMachine = new CoffeeMachine();
        coffeeMachine.makeCoffee(new Espresso());
        coffeeMachine.makeCoffee(new Cappuccino());
    }
}
```

**Expected:** Four bugs, ranked by what a strong candidate will notice in order:
1. `private` methods cannot be overridden. In Java, private methods are not
   polymorphic — they're statically bound. So `@Override` on
   `Espresso.brew()` is a compile error: "method does not override or
   implement a method from a supertype". The strong candidate spots this
   immediately.
2. The recursive field initializer. `public CoffeeMachine coffeeMachine =
   new CoffeeMachine();` creates a new `CoffeeMachine` every time the
   constructor runs. The new one runs its initializers, which creates
   another. Result: `StackOverflowError` at runtime. This is the trap —
   sharp candidates spot it on a second read.
3. `makeCoffee` is `private` in `CoffeeMachine`. That's fine inside the
   class (it's called from `main`), but if asked to extend `CoffeeMachine`,
   they should note this restricts use.
4. `Cappuccino` has no `brew()` override. Even after fixing the access
   modifiers, `new Cappuccino().brew()` would print the parent message
   ("You got some generic drink"). A candidate noticing this shows they're
   reading the intent, not just chasing errors.

The fix:

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

**Scoring guide:** Spots 1 and 2 -> hire-level. Spots 1 only -> on the line,
probe further. Spots neither -> below bar for a Java-primary role.

**Probe:** If they only spot the private-override compile error, ask what
else could go wrong once that's fixed and the code actually runs — steer
them toward the recursive field initializer and the `StackOverflowError`.

**Red flags:** Doesn't notice the private-method-can't-override compile
error even when prompted.

**Comment:**

### BC2. Python coding task — whoami generator [Pen & paper]

**Ask:** What does this function do? Walk me through how it works.

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

x = whoami(24)
#xs = [i for i in x]
#print(xs)
```

**Expected:** It's a prime sieve — a generator variant of the Sieve of
Eratosthenes. For `n = 24` it yields `2, 3, 5, 7, 11, 13, 17, 19, 23`. How
it works (the elegant bit): `D` maps the next composite to wipe -> list of
primes that produced it. When `q` is not in `D`, it's prime: yield it, then
record that its square (`q*q`) is the first composite this prime will mark.
When `q` is in `D`, it's composite: for each prime that marked it, schedule
the next composite (`p + q`) for that prime, then drop the current entry.
What you're listening for: they notice `yield` -> it's a generator, lazy —
nothing happens until iterated (the commented-out `[i for i in x]` would
drive it). They identify it's about primes within a minute of reading.
Bonus: explains the dictionary trick (lazy sieve, only stores upcoming
composites instead of a full boolean array).

**Scoring guide:** Bar = spots the `yield`/generator laziness and identifies
primes within a minute. Below bar: stares at it, can't figure out what
`yield` does — for a role where Python is "nice-to-have" that's tolerable,
but note it.

**Probe:** Once they've identified it as prime-finding, push for depth —
what does the dictionary actually store, and why does memory stay small?
(It only tracks upcoming composites keyed by the prime that will strike
them, not a full boolean sieve array.)

**Red flags:** Can't identify what `yield` does at all, even after a hint.

**Comment:**
