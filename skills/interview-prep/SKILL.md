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
3. **Baseline is fixed:** embed ALL `B*` and `BC*` entries from
   `references/base-questions.md` in full (currently B1-B23 + BC1/BC2).
   Reorder freely; never rewrite, drop, or dilute their content or expected
   answers. Entries marked `Optional` stay in the doc — the skip note may
   say "ask only if time allows".
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
     per CV flag (CV oddities only — overlapping dates, unnamed employers,
     tool-less/vague claims). Absent competencies are handled only by Part
     6's grouped gap-check, never here.
   - Part 5: baseline set, embedded in full (rule 3). Where the CV clearly
     shows depth on a baseline topic, add a one-line skip note (ask faster,
     don't dwell) — the question itself always stays.
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
