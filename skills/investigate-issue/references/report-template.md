# Report template

File name: `<problem-name>-investigation.md`, same directory as the
input `.md` (input `LISA-123.md` → `LISA-123-investigation.md`).
Sections in this order; drop a section only if truly empty and say so.

```markdown
# Investigation — <problem name / ticket id>

## Summary

<max 3 lines: what broke, root cause, fix in one phrase>

## Environment

- Plan / stage / job: <from problem .md, or "not stated">
- Agent: <name/type, or "not stated">
- Language / runtime: <e.g. Java 17 / Maven 3.9, from log or repo pins>
- Issue class: <repo-code | script | dockerfile/image | k8s-manifest |
  bamboo-plan | bamboo-agent>

## Evidence

<quoted error lines, verbatim, shortest decisive ones>

<repo findings as `path/to/file:line` — one line each, what it shows>

## Hypotheses considered

<rejected ones only, one line each:>
- <hypothesis> — rejected: <disqualifying evidence>

## Root cause — <Confirmed | Probable>

<the cause, and the proof: for Confirmed, the local repro command and
its output matching the pasted error; for Probable, the evidence chain
and why no competing hypothesis survives>

## Solution

<ONE of the two forms:>

<Code fix — the concrete change:>
```diff
<diff, or exact edit instructions with file:line>
```

<Manual fix — numbered steps, exact locations:>
1. <Bamboo admin screen path / agent host + command / capability name /
   env var — what to change and to what value>
2. ...

## Verification

<how to confirm after applying: exact local command and expected
output, or which plan/build to rerun and what to expect in its log>
```

Rules:

- Error strings, commands, code verbatim — never paraphrased.
- No fix text anywhere above the Solution section.
- If the fix was applied during the run (user approved a code fix),
  append the rerun result to Verification — including a failing rerun.
