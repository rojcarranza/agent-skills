# Interview-Prep Skill — Design

**Date:** 2026-07-17
**Status:** Approved approach A — single cross-platform skill in `agent-skills/`

## Goal

One agent skill that, given a candidate CV, generates a complete interview
document: candidate summary, tailored questions, plus a fixed baseline
technical question set every candidate receives. Runs under Claude Code (mac,
inside the Obsidian vault) and GitHub Copilot (work). Output lands in the
vault's `Candidates/` directory; CVs are read from `CVs/`.

## Skill structure

```
agent-skills/skills/interview-prep/
├── SKILL.md                  # workflow, vault detection, generation rules
├── USAGE.md                  # install + run instructions per platform
└── references/
    ├── base-questions.md     # baseline question set (below) with expected answers
    ├── calibration.md        # distilled cheatsheet: above/at/below bar per topic
    ├── interview-frame.md    # intro script, 60-min agenda, final-calibration questions
    └── candidate-template.md # generated doc skeleton
```

No installer change: `agent-skills/install.py` already installs every skill
under `skills/` to both Copilot (`~/.copilot/skills`, copies) and Claude
(`~/.claude/skills`, symlinks).

## Vault detection (self-contained + vault-aware)

At run start, check the working directory (and one level up) for:

- `2026-06-08-interviewer-cheatsheet.md` → wins over bundled `calibration.md`
- `Interview guide.md` → wins over bundled `interview-frame.md`
- `CVs/` → CV source directory
- `Candidates/` → output directory

All present → vault mode: read CV from `CVs/` (if several, ask which),
write `Candidates/DevOps Interview - <Candidate Name>.md`.
Any missing → standalone mode: ask for CV path and output directory, use
bundled references. Never fail because the vault is absent.

CV files may be `.docx` — extract text with whatever the platform offers
(`textutil` on macOS, `pandoc`, or python-docx via a short script). If
extraction fails, ask the user to paste the CV text.

## Baseline question set (every candidate, fixed)

Distilled from the interviewer cheatsheet. 10 questions + 2 coding tasks.
Each entry in `base-questions.md` carries: difficulty, competency, the
question, expected answer (above/at/below bar), probe/follow-up.

| # | Difficulty | Competency | Question (short form) |
|---|---|---|---|
| B1 | Easy | Linux | Disk full on a server — how do you find what's eating it? (df/du/ncdu; probe: inodes) |
| B2 | Easy | Linux | Explain file permissions and octal notation. (probe: what does 4755 mean?) |
| B3 | Medium | Git | Explain trunk-based development vs GitFlow. (probe: how do you ship a 3-week feature?) |
| B4 | Easy-Med | Docker | What is Docker Compose for, and would you run it in production? (probe: depends_on vs healthy) |
| B5 | Medium | Kubernetes | Explain what Kubernetes does — control plane, Deployments, Services. (probe: readiness vs liveness) |
| B6 | Medium | CI/CD | Design a pipeline promoting through dev/test/prod. (bar: build once, promote same artefact) |
| B7 | Medium | GitOps | What is GitOps? (probe: push-based CD vs pull-based GitOps) |
| B8 | Medium | IaC | What makes infrastructure-as-code valuable? Idempotency, state, drift. (probe: secrets in Terraform state) |
| B9 | Hard | Incident | Prod is down right after a deployment — walk me through your first 30 minutes. (framework: confirm/communicate/stabilize/verify/diagnose/prevent) |
| B10 | Easy | OOP+Testing | Overloading vs overriding; what is TDD really for? (probe: over-mocking smell) |
| BC1 | — | Java coding | CoffeeMachine task (4 bugs; scoring: spots private-override + recursive field = hire-level) |
| BC2 | — | Python coding | whoami generator (prime sieve; bar: spots yield/generator, identifies primes) |

Expected answers and scoring lifted verbatim in spirit from the cheatsheet so
calibration stays consistent with past interviews.

## Generated document template

Filename: `DevOps Interview - <Candidate Name>.md`, Obsidian frontmatter
(title, created, type: zettel, interview/devops tags — matches existing docs).

Sections, in order:

1. **Candidate summary** — overview, years of experience, per-technology
   matrix (competency, CV evidence, est. years, verdict
   Confident/Validate/Absent), strengths, concerns/CV flags, focus areas.
2. **Interview plan** — 60-minute agenda table (from interview-frame).
3. **Introduction script** — personalized from the frame's intro.
4. **CV deep dive** — per significant project/claim, heading blocks.
5. **Baseline technical questions** — the fixed set above, embedded in full.
   Order may be tuned per candidate (skip-level notes allowed, content fixed).
6. **CV-specific technical questions** — 5-8 generated from the CV: go deep
   where the CV claims depth, gap-check where role requirements are absent
   (one grouped gap-check question, not six zeros).
7. **Scenario questions** — 2-3 production scenarios matched to their stack.
8. **Behavioural questions** — STAR, personalized (ownership, mentoring,
   incidents, conflict, pressure).
9. **Coding tasks** — both tasks with code, expected findings, scoring guide.
10. **Result** — final-calibration four questions, then:

```markdown
## Result

**Pass: Yes / No**

**Comment:**
```

Every question in sections 4-9 uses the heading-block layout:

```markdown
### Q3. Kubernetes — probes [Medium]

**Ask:** ...
**Expected:** ...
**Red flags:** ...
**Comment:**
```

`**Comment:**` is always present and empty — filled live during interview.

## Role competency list

Kept from the existing prompt (Python, Java, Bash, Go, Docker, K8s+Helm,
Ansible, Terraform, Bamboo, Splunk, Zookeeper/Mesos/Ambari, HDFS,
Linux+vSphere, Azure/AWS, Postgres/neo4j/MongoDB). Lives in SKILL.md as an
editable list; the tech matrix in section 1 assesses every candidate against
all of it.

## Skill workflow (SKILL.md flow)

1. Detect vault vs standalone (above).
2. Locate CV; if multiple, ask which candidate.
3. Extract CV text.
4. Read calibration + frame (vault versions if present, else bundled).
5. Generate the document per template. Evidence rule: every CV-specific
   question traces to a CV claim or role requirement. Flag CV oddities
   (date overlaps, unnamed employers, tool-less claims) with a
   non-accusatory question.
6. Write to output dir; report path.
7. Post-interview flow: user pastes answers / fills comments, invokes the
   skill again with "final assessment" → skill fills strengths, weaknesses,
   score, recommendation under Result.

Git rule: skill never commits; vault is not a git workflow.

## Existing vault files

- `Technical Interview - Prompt.md` — superseded by the skill; update it to a
  short pointer ("use the interview-prep skill") rather than deleting.
- Cheatsheet and Interview guide stay authoritative in the vault (vault mode
  reads them directly).

## Out of scope

- No automation of scheduling, HR mail, scoring math.
- No new install tooling.
- Role is DevOps-focused; other roles = edit competency list + baseline set
  later.

## Testing

- Dry run in vault: generate doc for an existing CV (Dragos Neagu docx) and
  compare tone/structure against past docs.
- Standalone dry run in a scratch dir with a copied CV: confirm bundled
  references used, output path asked.
- `python3 agent-skills/test_install.py` still green; `install.py --target both`
  lists the new skill.
