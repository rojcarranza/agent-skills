# Example: grilling SB-PROJ-2001.md

Input Questions section before the session:

```markdown
## Questions

- Which requests version are we on, and does it support urllib3 Retry?
- How many retries, and with what backoff?
- Should retries cover POST, which is not idempotent?
- Does the API team need to know about the extra load from retries?
- Do we add a slide to our sprint review presentation for this story?
```

## Round 1

✅ requests is pinned to 2.32.3 (`requirements.txt:1`), which ships urllib3
Retry through `HTTPAdapter(max_retries=...)`. Settled, no question needed.

❓ **Q1** - **Retry budget**: How many attempts, and which backoff?
Options: (a) 3 retries, exponential backoff 0.5s; (b) 5 retries, fixed 1s;
(c) make both configurable.

➡️ (a) 3 retries with 0.5s exponential backoff: enough for transient 5xx
without hiding a real outage.

---

❓ **Q2** - **Retrying POST**: `upload()` sends a POST. Retry it only on
connection errors and 502/503/504, where the server did not process it?

➡️ Yes: retrying a POST after a 500 can create a duplicate upload.

---

❓ **Q3** - **Sprint review slide**: Skip the slide for this story?

➡️ Yes: no user-visible change.

User: "yes to all"

## Round 2

Q4 (the API team's load) depended on Q1. With 3 retries the peak load can
reach 4x on a bad minute, which only the API team can judge.

❓ **Q4** - **API team**: Mark "extra load from retries" as needs someone else
(API team owner) instead of deciding it here?

➡️ Yes.

User: "yes"

## Written back after "yes, write it"

```markdown
## Questions

- [x] Which requests version are we on, and does it support urllib3 Retry? → 2.32.3 (requirements.txt:1), Retry available via HTTPAdapter
- [x] How many retries, and with what backoff? → 3 retries, exponential backoff 0.5s
- [x] Should retries cover POST, which is not idempotent? → only connection errors and 502/503/504
- [ ] Does the API team need to know about the extra load from retries? (needs: API team owner)
- [x] Do we add a slide to our sprint review presentation for this story? → no, no user-visible change
```
