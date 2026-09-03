# investigate-issue — usage

Takes a problem + context `.md` (pasted Bamboo build log, stack trace,
error output), investigates the checked-out repo, validates the root
cause, and writes `<problem>-investigation.md` next to the input with
evidence and steps to solve. Repo code fixes are offered for
application; Bamboo admin / agent host fixes come as numbered manual
instructions.

## When to use

- Bamboo pipeline / build plan failure to investigate.
- Bamboo agent behaving differently from local.
- Bug in Python / Bash / Java / Go code, Dockerfile, or k8s manifest,
  with an error or log to start from.

Not for pure code comprehension — that is `explain-logic`.

## Input format

Any `.md` containing the problem. More is better; minimum is the actual
error text. Useful content:

    # LISA-123 build fails on agent

    Plan: PROJ-PLAN, stage Build, job Compile, agent linux-agent-07
    Started failing after <commit/change if known>.

    ```
    <paste the failing part of the build log — exact error lines>
    ```

    Context: <anything you know — works locally, only this agent, ...>

## Install

From the repo root:

    python3 agent-skills/install.py --target claude    # mac / Claude Code
    python3 agent-skills/install.py --target copilot   # work / GitHub Copilot

The installer also fetches the chained helper skills:
`debugging-and-error-recovery` (addyosmani/agent-skills) and
`context-map` (awesome-copilot). The skill works without them — they
sharpen the method when present.

## Run — GitHub Copilot (work VDI, VS Code agent mode)

Open the repo the build runs against, then:

    investigate this issue: docs/issues/LISA-123.md

or paste the problem text directly and say "investigate this issue and
write the report next to docs/issues/LISA-123.md".

## Run — Claude Code

    cd <repo>
    claude
    > investigate docs/issues/LISA-123.md

## Output

`LISA-123-investigation.md` next to the input: Summary, Environment,
Evidence, Hypotheses considered, Root cause (Confirmed = reproduced
locally / Probable = evidence-only), Solution (diff or numbered manual
steps), Verification (what to run/rerun to confirm).

If the fix is a repo change, the skill asks before applying; on yes it
applies and reruns the repro, recording the result.
