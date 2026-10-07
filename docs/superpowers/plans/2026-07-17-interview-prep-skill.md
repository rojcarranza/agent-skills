# Interview-Prep Skill Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Cross-platform agent skill (`interview-prep`) that generates a complete DevOps interview document from a candidate CV, embedding a fixed baseline question set plus CV-tailored questions.

**Architecture:** Pure-markdown skill under `agent-skills/skills/interview-prep/` following the soundboarding pattern: `SKILL.md` (workflow) + `USAGE.md` (per-platform install/run) + `references/` (baseline questions, calibration, interview frame, output template). No installer changes — `install.py` picks up any skill under `skills/`.

**Tech Stack:** Markdown only. Source material: the Obsidian vault at `/Users/roj/Dev/second-brain/6-Work/technical-interviews/` (cheatsheet, Interview guide, existing prompt, past candidate docs).

## Global Constraints

- Spec: `docs/superpowers/specs/2026-07-17-interview-prep-skill-design.md` — follow it exactly.
- Repo: `/Users/roj/Dev/.dotfiles`. All new files live under `agent-skills/skills/interview-prep/`.
- Vault (read-only source, except Task 5's pointer edit): `/Users/roj/Dev/second-brain/6-Work/technical-interviews/`. Vault is NOT a git repo workflow — never run git there.
- Expected answers/calibration must stay faithful to `2026-06-08-interviewer-cheatsheet.md` — copy its bar definitions, don't invent new ones.
- Skill must never commit/branch/push when it runs (write the same "Git: hands off" rule soundboarding uses).
- Question layout everywhere: heading blocks (`### Qn. <competency> — <topic> [Difficulty]` with `**Ask:** / **Expected:** / **Red flags:** / **Comment:**`), never tables.
- Final doc section is `## Result` with `**Pass: Yes / No**` + `**Comment:**`.
- Commit after every task with the trailer:
  `Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>` and
  `Claude-Session: https://claude.ai/code/session_01F2uCxuNKWPBrBuVDdaiY2Z`

---

### Task 1: Baseline questions + calibration references

**Files:**
- Create: `agent-skills/skills/interview-prep/references/base-questions.md`
- Create: `agent-skills/skills/interview-prep/references/calibration.md`
- Source: `/Users/roj/Dev/second-brain/6-Work/technical-interviews/2026-06-08-interviewer-cheatsheet.md` (read fully first)
- Source: `/Users/roj/Dev/second-brain/6-Work/technical-interviews/Coding Assessment.md` (verbatim code blocks)

**Interfaces:**
- Produces: `references/base-questions.md` with question IDs `B1`-`B10`, `BC1` (Java), `BC2` (Python) — SKILL.md (Task 3) and candidate-template.md (Task 2) refer to these IDs.
- Produces: `references/calibration.md` — the bundled fallback for the vault cheatsheet.

- [ ] **Step 1: Write `base-questions.md`**

Header then 12 entries. Exact skeleton per entry (content filled from the cheatsheet sections named below):

```markdown
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
```

The 12 entries and their cheatsheet source sections:

| ID | Difficulty | Cheatsheet source section | Ask (short) |
|---|---|---|---|
| B1 | Easy | `## Linux > ### Disk usage` | disk filling up — find what's eating it |
| B2 | Easy | `## Linux > ### Permissions` | explain permissions + octal; probe 4755 |
| B3 | Medium | `## Git, trunk-based development` | trunk-based vs GitFlow; probe 3-week feature |
| B4 | Easy-Med | `## Docker Compose` | what Compose is for; prod? probe depends_on vs healthy |
| B5 | Medium | `## Kubernetes` | what K8s does: control plane, Deployment/StatefulSet/DaemonSet, Services; probe readiness vs liveness |
| B6 | Medium | `## CI/CD > ### Multi-environment pipeline` | pipeline dev→test→prod; bar = build once, promote artefact |
| B7 | Medium | `## CI/CD > ### GitOps` | what is GitOps; probe push vs pull CD |
| B8 | Medium | `## Infrastructure as Code` | why IaC: idempotency, state, drift; probe secrets in TF state |
| B9 | Hard | `## The incident scenario, the answer framework` | prod down right after deploy — first 30 min; full 7-step framework as Expected |
| B10 | Easy | `## OOP > ### Overloading vs overriding` + `## Testing > ### TDD` + `### Mocking` | overloading vs overriding; TDD purpose; probe over-mocking smell |
| BC1 | — | `## The Java coding task, what to expect` | CoffeeMachine task — code verbatim from `Coding Assessment.md`, 4 expected findings + scoring guide (spots 1+2 = hire-level) |
| BC2 | — | `## The Python coding task, what to expect` | whoami generator — code verbatim, bar = spots yield/generator + identifies primes within a minute |

For every entry, `**Expected:**` compresses the cheatsheet's Concept +
above/at/below bar into 3-6 lines; `**Probe:**` and `**Red flags:**` come
from the same section. BC1/BC2 keep their full code blocks and scoring
guides.

- [ ] **Step 2: Write `calibration.md`**

Bundled fallback for the vault cheatsheet (used in standalone mode). Start with:

```markdown
# Interviewer Calibration — DevOps (bundled copy)

Fallback for when the vault cheatsheet
(`2026-06-08-interviewer-cheatsheet.md`) is not available. If the vault
version exists, use it instead — it is authoritative.
```

Then copy the cheatsheet body (everything from `## Linux` through
`## Final calibration` inclusive) with only formatting normalization — no
content edits. Include the four final-calibration questions.

- [ ] **Step 3: Verify structure**

Run: `grep -c '^### B' agent-skills/skills/interview-prep/references/base-questions.md`
Expected: `12`

Run: `grep -c '^\*\*Comment:\*\*' agent-skills/skills/interview-prep/references/base-questions.md`
Expected: `12`

Run: `grep -c '^## ' agent-skills/skills/interview-prep/references/calibration.md`
Expected: `>= 9` (Linux, Git, Compose, K8s, CI/CD, IaC, CS basics, OOP, Clean code, Testing, Java task, Python task, incident, final calibration — at least 9 top-level sections survive the copy)

- [ ] **Step 4: Commit**

```bash
git add agent-skills/skills/interview-prep/references/
git commit -m "feat(agent-skills): interview-prep baseline questions and calibration references"
```

---

### Task 2: Interview frame + candidate template references

**Files:**
- Create: `agent-skills/skills/interview-prep/references/interview-frame.md`
- Create: `agent-skills/skills/interview-prep/references/candidate-template.md`
- Source: `/Users/roj/Dev/second-brain/6-Work/technical-interviews/Interview guide.md`
- Source (structure examples): `Candidates/DevOps Interview - Dragos Neagu.md`

**Interfaces:**
- Consumes: question IDs `B1`-`B10`, `BC1`, `BC2` from Task 1.
- Produces: `candidate-template.md` — the exact skeleton SKILL.md (Task 3) instructs the agent to fill.

- [ ] **Step 1: Write `interview-frame.md`**

Three parts, copied/adapted from `Interview guide.md`:

```markdown
# Interview Frame — agenda, intro, calibration

## 60-minute agenda

| Section | Time | Purpose |
|---|---|---|
| A. Introduction | 5 min | Welcome, set tone, logistics check |
| B. Candidate background / CV discussion | 15-20 min | Self-intro, career story, CV flags |
| C. Technical assessment | 20-25 min | Baseline + CV-specific questions, coding task |
| D. Scenarios + behavioural | 8-10 min | Production scenarios, STAR |
| E. Candidate questions | 10-15 min | Their questions; profile engagement |
| F. Wrap-up | 2 min | Next steps, close on time |

## Introduction script (personalize per candidate)

> **Hi <Name>, great to meet you!** Thanks for taking the time to join us
> today. I hope the connection is clear on your end.
>
> **Quick bit about me: I'm Roj, a Software Engineer working in a DevOps
> capacity on one of our client engagements here at Luxoft Netherlands.**
> <one personalized connection line from the CV — shared employer, tech,
> location, or notable project>
>
> The role we're looking to fill is a DevOps engineer on our team. The focus
> is CI/CD pipelines, Linux, containers, and Kubernetes, with Java being the
> primary language for pipeline scripting. We'll cover all of that today.
>
> **Here's the plan for the next 50-60 minutes. We'll start with you — walk
> me through your background. Then we'll move into technical discussion,**
> covering DevOps topics and a short coding task. After that I'll leave at
> least 15 minutes for your questions about the role, the team, and how we
> work day to day. Sound good?
>
> Then let's start. Tell me about yourself.

Logistics to verify: audio clear, camera on (or explained), on time.
Opening notes to deliver: you'll be typing notes (quiet stretches normal);
flag any sound issues.

## Final calibration (answer before writing the Result)

1. Could I sit next to this person daily and enjoy it?
2. Will they raise the team's bar, or lean on it?
3. When they don't know, do they say so?
4. When they disagree, can they hold their ground respectfully?

A clear "yes" on all four is a hire. A clear "no" on any is at least a
serious conversation with HR + PM before moving forward.
```

- [ ] **Step 2: Write `candidate-template.md`**

The full output skeleton. `{{placeholders}}` mark what the agent fills at
generation time; everything else is literal:

```markdown
---
title: DevOps Interview Script - {{candidate_name}}
created: {{today}}
type: zettel
tags: [zettel, status/seedling, interview, devops]
source:
---

# DevOps Interview Script
### Candidate: {{candidate_name}}

---

## Part 1 — Candidate Summary

**Overview:** {{2-5 sentence profile: current role, employer, location, seniority read}}

**Years of relevant experience:** {{estimate with reasoning}}

### Per-technology experience matrix

| Required tech | CV evidence | Est. years | Verdict |
|---|---|---|---|
| {{one row per role competency: Confident / Validate / Absent}} |

**Technical strengths:** {{list}}

**Potential concerns or CV flags:** {{date overlaps, unnamed employers, tool-less claims — each with a planned non-accusatory question}}

**Suggested interview focus areas:** {{list}}

## Part 2 — Interview Plan

{{agenda table from interview-frame, times tuned to this candidate}}

## Part 3 — Introduction

{{intro script from interview-frame, personalized connection line filled}}

## Part 4 — CV Deep Dive

{{per significant project/claim, heading blocks:}}

### D{{n}}. {{project / claim}}

**Ask:** {{question}}

**Expected:** {{what a good answer looks like; the claim being validated}}

**Red flags:** {{...}}

**Comment:**

## Part 5 — Baseline Technical Questions

{{ALL of B1-B10 from base-questions.md, embedded in full — Ask / Expected /
Probe / Red flags / Comment blocks. Order tunable; content fixed. Add a
one-line skip note where the CV clearly shows depth (still ask, faster).}}

## Part 6 — CV-Specific Technical Questions

{{5-8 questions: deep where CV claims depth, one grouped gap-check question
covering all absent role competencies. Same heading-block layout, numbered
T1, T2, ...}}

## Part 7 — Scenarios

{{2-3 production scenarios matched to their stack, S1..Sn: **Situation:** /
**Ask:** / **Expected:** (use the incident framework as model) /
**Red flags:** / **Comment:**}}

## Part 8 — Behavioural (STAR)

{{3-5 questions personalized to the CV — ownership, mentoring, incidents,
conflict, pressure. **Ask:** / **Listen for:** / **Comment:**}}

## Part 9 — Coding Tasks

{{BC1 Java + BC2 Python from base-questions.md, verbatim: code, expected
findings, scoring guide, Comment field each}}

## Result

{{the four final-calibration questions as a checklist}}

**Pass: Yes / No**

**Comment:**

### Final Assessment (fill after interview)

Paste answers/comments above, then re-run the skill with "final assessment
for {{candidate_name}}": strengths, weaknesses, confidence level, overall
score /100, hiring recommendation, risks if hired.
```

- [ ] **Step 3: Verify structure**

Run: `grep -c '^## Part' agent-skills/skills/interview-prep/references/candidate-template.md`
Expected: `9`

Run: `grep -c 'Pass: Yes / No' agent-skills/skills/interview-prep/references/candidate-template.md`
Expected: `1`

- [ ] **Step 4: Commit**

```bash
git add agent-skills/skills/interview-prep/references/
git commit -m "feat(agent-skills): interview-prep frame and candidate template references"
```

---

### Task 3: SKILL.md

**Files:**
- Create: `agent-skills/skills/interview-prep/SKILL.md`
- Pattern reference: `agent-skills/skills/soundboarding/SKILL.md` (frontmatter style, hard-rules style)

**Interfaces:**
- Consumes: all four reference files by relative path (`references/…`).
- Produces: the runnable skill — trigger description, vault detection, generation flow, final-assessment flow.

- [ ] **Step 1: Write `SKILL.md`**

```markdown
---
name: interview-prep
description: Generate a complete DevOps technical-interview document for a candidate from their CV — candidate summary, tech matrix, personalized intro, CV deep-dive, fixed baseline question set, CV-specific questions, scenarios, behavioural, coding tasks, and a pass/no-pass result section. Use when the user says "interview prep", "prepare interview for <name>", "new candidate", drops a CV to prepare against, or asks for a "final assessment" of an interviewed candidate.
---

# Interview Prep

Produce one interview document per candidate. Two flows: **generate**
(CV in, interview doc out) and **final assessment** (filled doc in,
verdict out). Pick the flow from what the user asked.

## Vault detection

Check the working directory, then one level up, for these names:

- `2026-06-08-interviewer-cheatsheet.md` — calibration source
- `Interview guide.md` — agenda + intro source
- `CVs/` — CV source directory
- `Candidates/` — output directory

**Vault mode** (all four found): read CVs from `CVs/`, write output to
`Candidates/DevOps Interview - <Candidate Name>.md`. The vault cheatsheet
and guide are authoritative — use them instead of the bundled
`references/calibration.md` and `references/interview-frame.md`.

**Standalone mode** (anything missing): ask the user for the CV file path
and the output directory, and use the bundled references for everything.
Never fail because the vault is absent.

## Hard rules

1. **Git: hands off.** Never branch, commit, or push — in any repository.
   The user reviews and commits manually. Read-only git commands allowed.
2. **Evidence-driven:** every CV-specific question must trace to a CV claim
   or a role-competency gap. No generic filler questions.
3. **Baseline is fixed:** embed ALL of B1-B10 + BC1 + BC2 from
   `references/base-questions.md` in full. Reorder freely; never rewrite,
   drop, or dilute their content or expected answers.
4. **Non-accusatory flags:** CV oddities (overlapping dates, unnamed
   employers, tool-less claims like "built CI/CD" with no tool named) get a
   direct but neutral question in the deep dive — flag, don't accuse.
5. **Honest gaps aren't penalties:** the calibration test for an absent
   skill is whether the candidate says "I don't know" cleanly and shows a
   transfer plan.
6. **Ask, don't guess:** multiple CVs and no candidate named → ask which.
   CV unreadable → ask for pasted text.

## Role competency list (edit here when the role changes)

Assess every candidate against all of these, even those missing from the CV:
Python, Java, Bash/Shell, Go (optional), Docker, Kubernetes + Helm, Ansible,
Terraform, Bamboo + agents, Splunk, Zookeeper + Mesos + Ambari, HDFS,
Linux + VM creation (VMware vSphere), Cloud (Azure or AWS), Databases
(Postgres, neo4j, MongoDB).

## Flow 1: Generate

1. Detect mode (above). Locate the CV; `.docx` → extract text (`textutil
   -convert txt` on macOS, `pandoc`, or python-docx one-liner; all fail →
   ask for paste).
2. Read calibration + frame (vault versions in vault mode, bundled
   otherwise) and `references/base-questions.md`.
3. Fill `references/candidate-template.md` top to bottom:
   - Part 1 matrix: one row per role competency, verdict
     Confident / Validate / Absent, with CV evidence quoted.
   - Part 4: one deep-dive block per significant project/claim + one block
     per CV flag.
   - Part 5: baseline set, embedded in full (rule 3).
   - Part 6: 5-8 CV-specific questions — deep where the CV claims depth;
     ONE grouped gap-check question covering all Absent competencies (never
     six separate zero-questions).
   - Part 7: 2-3 scenarios matched to their stack; incident framework from
     calibration is the model answer.
   - Part 8: 3-5 STAR questions tied to actual CV events.
   - Part 9: both coding tasks verbatim.
4. Every question block ends with an empty `**Comment:**` line.
5. Write the file; report the path. Do not commit.

## Flow 2: Final assessment

Input: a generated doc whose Comment fields / pasted answers are filled.
Fill the `### Final Assessment` section: strengths, weaknesses, confidence
level, overall score /100, hiring recommendation (tie it to the four
final-calibration questions and the Pass verdict), risks if hired. Change
nothing else in the doc.
```

- [ ] **Step 2: Verify frontmatter parses and references resolve**

Run: `head -5 agent-skills/skills/interview-prep/SKILL.md`
Expected: `---`, `name: interview-prep`, `description: …`

Run: `for f in base-questions calibration interview-frame candidate-template; do test -f agent-skills/skills/interview-prep/references/$f.md && echo "$f ok"; done`
Expected: four `ok` lines

- [ ] **Step 3: Commit**

```bash
git add agent-skills/skills/interview-prep/SKILL.md
git commit -m "feat(agent-skills): interview-prep skill workflow"
```

---

### Task 4: USAGE.md + install verification

**Files:**
- Create: `agent-skills/skills/interview-prep/USAGE.md`
- Pattern reference: `agent-skills/skills/soundboarding/USAGE.md` (read first, match its structure)
- Test: `agent-skills/test_install.py` (existing suite, must stay green)

**Interfaces:**
- Consumes: skill directory completed in Tasks 1-3.

- [ ] **Step 1: Write `USAGE.md`**

Match soundboarding USAGE structure. Content to cover (adapt headings to the
existing pattern):

```markdown
# interview-prep — usage

## Install

From the repo root:

    python3 agent-skills/install.py --target claude    # mac / Claude Code
    python3 agent-skills/install.py --target copilot   # work / GitHub Copilot
    python3 agent-skills/install.py --target both

Claude gets a symlink (edit the repo, changes are live); Copilot gets a copy
(re-run install after edits).

## Run — Claude Code (mac, inside the vault)

    cd ~/Dev/second-brain/6-Work/technical-interviews
    claude
    > prepare interview for <candidate name>

Vault mode auto-detected: CV read from `CVs/`, doc written to
`Candidates/DevOps Interview - <Candidate Name>.md`.

## Run — Copilot (work)

Open any folder, invoke the skill (`/skills list` to confirm it's
installed), then: "prepare interview for <name>, CV at <path>, output to
<dir>". Standalone mode uses the bundled calibration and frame.

## After the interview

Fill the Comment fields and the Pass verdict in the doc, then:
"final assessment for <candidate name>".

## Editing the baseline

Baseline questions live in `references/base-questions.md` in the dotfiles
repo. Edit there, commit, re-run install for Copilot (Claude symlink picks
it up automatically).
```

- [ ] **Step 2: Run the installer test suite**

Run: `cd /Users/roj/Dev/.dotfiles/agent-skills && python3 test_install.py`
Expected: all tests pass (same count as before this change; suite discovers skills dynamically)

- [ ] **Step 3: Verify installer sees the new skill**

Run: `cd /Users/roj/Dev/.dotfiles/agent-skills && python3 install.py --target claude` (choose/confirm `interview-prep` if the interactive selector prompts)
Expected: output lists `interview-prep` installed; then
`test -L ~/.claude/skills/interview-prep && echo symlink-ok` → `symlink-ok`

- [ ] **Step 4: Commit**

```bash
git add agent-skills/skills/interview-prep/USAGE.md
git commit -m "docs(agent-skills): interview-prep usage guide"
```

---

### Task 5: Vault pointer + end-to-end dry run

**Files:**
- Modify: `/Users/roj/Dev/second-brain/6-Work/technical-interviews/Technical Interview - Prompt.md` (vault file — NOT in this git repo, do not commit it anywhere)
- Uses: `/Users/roj/Dev/second-brain/6-Work/technical-interviews/CVs/Dragos Neagu LUXOFT.docx`

**Interfaces:**
- Consumes: installed skill from Task 4.

- [ ] **Step 1: Replace the vault prompt with a pointer**

Overwrite `Technical Interview - Prompt.md` body (keep its frontmatter) with:

```markdown
# Superseded — use the interview-prep skill

This prompt has been replaced by the `interview-prep` agent skill
(dotfiles → `agent-skills/skills/interview-prep/`).

Run from this directory:

    claude
    > prepare interview for <candidate name>

CV goes in `CVs/`, output appears in `Candidates/`. After the interview,
fill the Comment fields and Pass verdict, then ask:
"final assessment for <candidate name>".

The old full prompt is preserved in git history of the previous workflow and
superseded by `SKILL.md` in the skill folder.
```

- [ ] **Step 2: Dry run in vault mode**

From `/Users/roj/Dev/second-brain/6-Work/technical-interviews`, execute the
skill's Flow 1 against the Dragos Neagu CV, writing to
`Candidates/DevOps Interview - Dragos Neagu (skill dry-run).md` (suffixed
name — a real doc for this candidate already exists; don't overwrite it).

Verify in the output:
- All of Parts 1-9 + `## Result` present.
- Part 5 contains 10 `### B` blocks; Part 9 contains both code blocks.
- Every question block has `**Comment:**`.
- Matrix has one row per role competency (15 rows).

- [ ] **Step 3: Compare against the real Dragos doc**

Read `Candidates/DevOps Interview - Dragos Neagu.md` side by side. Tone and
calibration should match (same concerns: three concurrent roles, unnamed
CI/CD tool, no Java). Divergence in structure is fine (new template);
divergence in calibration is a bug — fix SKILL.md/references and re-run.

- [ ] **Step 4: Clean up and finish**

Delete the dry-run file. Report results to the user; leave vault changes
uncommitted (vault is theirs to manage).

---

## Self-review notes

- Spec coverage: structure→T1-T4, vault detection→T3, baseline set→T1,
  template→T2, competency list→T3, workflow+final-assessment→T3,
  install→T4, vault pointer+testing→T5. Standalone-mode dry run from the
  spec's testing section is covered by USAGE instructions + skill rule
  (never fail outside vault); acceptable to verify at work install time
  since no Copilot host exists on this machine.
- No placeholders: every file's content or exact source mapping is inline.
- ID consistency: B1-B10/BC1/BC2 used identically in Tasks 1, 2, 3, 5.
