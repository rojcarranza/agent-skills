# Review method

Always loaded. Owns severity, confidence, suppression rules, the system
pass, the output skeleton, and calibration.

## Severity — impact if shipped

| Level | Meaning | Action |
|---|---|---|
| 🔴 Blocker | breaks at runtime or deploy, loses data, exposes a secret, or breaks a consumer contract | must fix before merge |
| 🟠 Major | a real defect on a plausible input or failure path; bounded wrong behavior, or missing error handling on an operation that fails in production | fix before merge |
| 🟡 Minor | correctness-neutral but costly later: a misleading name, duplicated logic, a missing test for new branch logic | author's call |
| 🔵 Nit | style or preference, and only when no linter covers it | never blocks; **max 3 per review** |

Severity measures impact, never certainty. "I am not sure" is confidence, and
it is a separate axis.

## Confidence — tagged on every finding

| Level | Meaning |
|---|---|
| **Confirmed** | proven from code read in this repository; quote the lines, or the command output |
| **Probable** | strong inference resting on exactly one unverified assumption — name the assumption in the finding |
| **Speculative** | depends on facts not in the repository (cluster state, Bamboo variables, runtime environment) |

Gates:

- Nothing below Probable enters the findings list.
- Speculative items carry no severity. They become questions in
  *Needs your input*.
- A Blocker must be Confirmed. Otherwise downgrade it.

## Never report

- Anything a configured linter or formatter already enforces.
- Renames and moves whose content did not change.
- "You could use a library / a framework / a different pattern."
- Idiom swaps with no behavioral difference.
- Performance claims without a measurement.
- Inputs the type system or the language prevents.
- Verbosity or duplication inside test helpers.
- Anything that cannot be tied to a line inside a diff hunk.
- Pre-existing defects the branch did not touch (they go in their own note,
  max 3, outside the verdict).

## Two gates before printing

**Verification pass.** Re-read every candidate finding against the whole
file, not the diff. Drop the ones the surrounding code already handles. The
archetypal false positive is a "missing nil check" that the caller performs.

**Failure-scenario rule.** Every Major and Blocker states concrete inputs or
state leading to a concrete wrong outcome: "when `values.yaml` omits
`image.tag`, the template renders `image:` and the pod fails ImagePullBackOff".
If that sentence cannot be written, downgrade or drop the finding.

Cap the list at roughly twelve findings. Overflow is reported as a count, not
padded out with Nits.

## System pass — mandatory, after the per-file pass

- **Callers.** For every changed public symbol, find all call sites and check
  each still holds. Call sites outside the diff are where the real bugs are.
- **Configuration to code.** A new environment variable or flag read in code
  — is it set in the Bamboo spec, the Helm values, the Dockerfile? A new Helm
  value — is it templated and defaulted? A renamed Kubernetes resource — do
  selectors and labels still match?
- **Boundaries.** Data crossing process lines: files, exit codes, API
  payloads, artifacts passed between Bamboo jobs.
- **Idempotency and partial failure.** What happens on a re-run, and after a
  crash halfway through.
- **Rolling deploys.** Is the change safe while the old and new versions run
  concurrently?

## Tests

Not coverage percentage. Ask:

- Does each new decision branch have a test?
- Do the tests assert behavior, or implementation detail?
- Are failure paths tested — the case that matters most in automation code?
- Can each test actually fail?
- Were existing assertions weakened or deleted in this diff to make a failure
  go away? → **Major**.
- Bugfix with no regression test → **Major**.
- New branch logic with no test → **Minor**.

## Output skeleton

```
## Review — <branch> vs <base>

<repo> · base `<base>` @ `<merge-base sha>` · <n> commits ·
<n> files · +<a>/-<b> · lenses: <loaded> (skipped: <if any>) ·
mode: pre-PR | post-PR
Excluded: <generated/vendored paths, uncommitted files>

### What this branch does
<3-6 sentences of intent>
- `path/to/file` — <one line>
<new behavior walked in execution order>

### Verdict
Changes requested — 1 Blocker, 2 Major, 1 Minor, 0 Nits

### Findings
#### 🔴 Blocker
**`path/to/file.go:42`** · Confirmed
<one sentence: the defect>
Fails when: <concrete inputs/state → concrete wrong outcome>
Fix: <minimal change>

#### 🟠 Major
...

### Tests
<what is covered, what new branch logic is not, missing failure-path tests>

### Runtime / deploy impact
<only when CI/CD or infrastructure changed>

### Needs your input
- <speculative question>

### Pre-existing, not introduced here
- <max 3, no severity>

### Good
- <1-3 real strengths, one line each>
```

The change summary is written **before** the findings, and every finding must
be consistent with it. Apply no fix without asking.

## Calibration

**Report this** — `deploy.sh:31`, Blocker, Confirmed:

```bash
kubectl delete namespace "$NS"
```

`$NS` is set from `${1:-}` with `set -u` absent, so an invocation with no
argument deletes the namespace named by the empty string, which `kubectl`
resolves to the current context's namespace. Concrete failure, one line, no
speculation needed.

**Report this** — `Chart.yaml:3`, Major, Probable:

The chart version was not bumped while `templates/deployment.yaml` changed.
Assumption named: the release pipeline uses chart version to decide whether
to upgrade. Evidence for it is in `bamboo-specs/deploy.yaml:58`.

**Do not report** — "`retryCount` should be a constant, not a literal 3."
Preference, no behavioral difference, not covered by a failure scenario.

**Do not report** — "This function is missing a nil check on `cfg`." The
only caller, `main.go:88`, constructs `cfg` two lines earlier and cannot pass
nil. The verification pass kills this one.

**Do not report** — "Consider using `pathlib` instead of `os.path`." Idiom
swap. The repository's `ruff.toml` does not enforce it, and neither does the
reviewer.
