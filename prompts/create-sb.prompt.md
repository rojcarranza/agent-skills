---
agent: agent
description: Generate a soundboarding (SB) document from a user story, with codebase-investigated core tasks
---

# /create-sb — Create a Soundboarding Document

You create a soundboarding (SB) document from a user story file. The SB document is presented to the team to refine acceptance criteria, define concrete core tasks grounded in real code investigation, and define how to test — before implementation starts.

## Configuration

- SOUNDBOARD_DIR: `/c/dev/projects/wr/soundboard`
- PROJECTS_ROOT: `/c/dev/projects`
- TEMPLATE: `SOUNDBOARD_DIR/SB-template.md`

On Windows these Git Bash paths map to `C:\dev\projects\wr\soundboard` and `C:\dev\projects`.

These paths are defaults, not requirements — override SOUNDBOARD_DIR or PROJECTS_ROOT by stating different paths in your message.

## Input

The user's message names or attaches a user story markdown file (example: `LISA-110278.md`). Resolve the file in this order:

1. As given, relative to the current workspace.
2. Inside SOUNDBOARD_DIR.

If the story file cannot be found or read: STOP and ask the user for the correct path. Never proceed with an invented story.

## Hard rules

1. **Truthfulness:** State as fact only file paths and values you actually read from local checkouts during this run. Everything unverified goes into the Questions section. Never present an assumption as a finding.
2. **Template fidelity:** Read TEMPLATE fresh at the start of every run and produce every section it defines. If the template is missing or unreadable: STOP and ask. Never invent the structure.
3. **No git actions:** Do not create branches, commits, or pushes anywhere.
4. **Ask, don't guess:** When something is ambiguous, ask the user one question and wait for the answer.

## Steps

### 1. Read inputs

- Read the user story file and TEMPLATE.
- Extract from the story: the goal, the acceptance criteria, and every repository, system, tool, and version mentioned or implied.

### 2. Identify impacted repositories

- The repository open in the current workspace is assumed impacted unless the story clearly says otherwise.
- For every other repository the story names or implies, look for a local checkout under PROJECTS_ROOT, searching one and two directory levels deep (example: `/c/dev/projects/wr/<repo>`).
- If a repository has no local checkout, add it to the Questions section ("Repo X is not cloned locally — investigate before implementation") and do not guess its contents.

### 3. Investigate the code

For each locally available impacted repository, find the concrete things that must change to reach the story's goal:

- exact files and their paths
- current values (versions, config properties, image tags, dependencies) and the required new values
- things that are already compliant — list them too, so the team knows they were checked

Record current values exactly as they appear in the files.

### 4. Compose the SB document

Follow the TEMPLATE structure exactly, filling each section:

- **Title / Goal:** from the story.
- **Acceptance Criteria:** copy the story's criteria verbatim as `- [ ]` checkboxes. Add newly discovered criteria (version constraints, config requirements, deployment steps) as extra checkboxes, each suffixed with `*(proposed)*` so the team can see which are new.
- **Core tasks:** concrete `- [ ]` checkboxes. Each code task starts with the repository it touches in backticks — example: ``- [ ] `sara-bambooagent-helm`: update `values.yaml` imagetag for all 4 pools``. Where the investigation found exact changes, include before/after tables with columns: #, File/Property, Before, After, Reason. Non-code tasks (emails, requests to other teams) are plain checkboxes without a repo tag.
- **Questions:** unknowns from the investigation, missing repos, ambiguities in the story — plus every standing question already present in the template.
- **Notes:** risks, environment caveats, and one line listing the impacted repositories — example: `Impacted repositories: sara-bamboo-agent-deployment, sara-bambooagent-helm`.
- **Testing:** fill the table with proposed test cases: Test Case ID (TC-1, TC-2, ...), Situation, and Expected result filled in; leave the Log and Build result link cells empty — they are completed during implementation.

### 5. Write the output file

- Output name: `SB-` + the story file's basename. `LISA-110278.md` becomes `SB-LISA-110278.md`; `LISA-108692 - Batch 1.md` becomes `SB-LISA-108692 - Batch 1.md`.
- Write the file into SOUNDBOARD_DIR by absolute path, regardless of the current workspace.
- If your file-editing tools refuse to write outside the current workspace, write the file from the terminal instead (for example with a shell heredoc or redirect).
- If the output file already exists: show a short summary of what would change and ask before overwriting.

### 6. Report

End with a short summary: which repositories were investigated and which findings were verified, what was assumed, and the open questions to raise during team refinement.
