#!/usr/bin/env bash
# Build the sandbox repository a behaviour eval runs in.
#
#   evals/fixtures/build.sh <kind> <dest>
#
# Creates <dest>/origin.git (a bare "remote") and <dest>/repo (a clone with
# origin/HEAD set), in the state the eval's prompt assumes. <dest> must be
# missing or empty. The kinds are the labels of the case statement below;
# evals.json names one per eval under "fixture".
set -euo pipefail
kind=$1; dest=$2
if [ -e "$dest" ] && [ -n "$(ls -A "$dest")" ]; then
  echo "build.sh: $dest is not empty" >&2; exit 2
fi
mkdir -p "$dest"; cd "$dest"
G() { git -c user.name=Dev -c user.email=dev@example.com "$@"; }
init_repo() { # $1 = default branch
  git init -q --bare origin.git; git -C origin.git symbolic-ref HEAD "refs/heads/$1"
  git init -q -b "$1" repo; cd repo; git remote add origin ../origin.git
}
push_all() { G push -q origin --all; git remote set-head origin -a >/dev/null; }

py_base() {
  mkdir -p app tests
  cat > app/uploader.py <<'EOF'
import requests


def upload(url, payload, session=None):
    """POST payload as JSON and return the parsed response."""
    s = session or requests.Session()
    resp = s.post(url, json=payload, timeout=10)
    resp.raise_for_status()
    return resp.json()
EOF
  cat > app/cli.py <<'EOF'
import sys
from app.uploader import upload


def main(argv):
    result = upload(argv[1], {"name": argv[2]})
    print(result["id"])


if __name__ == "__main__":
    main(sys.argv)
EOF
  cat > tests/test_uploader.py <<'EOF'
from unittest import mock
from app.uploader import upload


def test_upload_returns_json():
    s = mock.Mock()
    s.post.return_value.json.return_value = {"id": 1}
    assert upload("http://x", {}, session=s) == {"id": 1}
EOF
  printf 'requests==2.32.3\n' > requirements.txt
  G add -A; G commit -qm "Initial uploader"
}
py_retry_feature() { # retry loop that swallows the final failure -> returns None
  G checkout -qb feature/retry-uploads
  cat > app/uploader.py <<'EOF'
import time

import requests

RETRIES = 3


def upload(url, payload, session=None):
    """POST payload as JSON and return the parsed response.

    Retries transient failures with exponential backoff.
    """
    s = session or requests.Session()
    for attempt in range(RETRIES):
        try:
            resp = s.post(url, json=payload, timeout=10)
            resp.raise_for_status()
            return resp.json()
        except requests.RequestException:
            time.sleep(2 ** attempt)
EOF
  cat >> tests/test_uploader.py <<'EOF'


def test_upload_retries_then_succeeds():
    s = mock.Mock()
    ok = mock.Mock()
    ok.json.return_value = {"id": 2}
    import requests
    s.post.side_effect = [requests.ConnectionError(), ok]
    with mock.patch("app.uploader.time.sleep"):
        assert upload("http://x", {}, session=s) == {"id": 2}
EOF
  G add -A; G commit -qm "Retry uploads on transient failures

Uploads to the ingest API fail during its nightly restart. Retry up to
three times with exponential backoff."
}

case "$kind" in
pyrepo)        init_repo main; py_base; py_retry_feature; push_all ;;
pyrepo-dirty)  init_repo main; py_base; py_retry_feature; push_all
  cat >> app/cli.py <<'EOF'

API_TOKEN = "ghp_live_9f8a7b6c5d4e3f2a1b0c"
EOF
  cat > app/notify.py <<'EOF'
import subprocess


def notify(channel, message):
    subprocess.run(f"slack-cli send {channel} '{message}'", shell=True)
EOF
  ;;
pyrepo-clean)  init_repo main; py_base
  G checkout -qb feature/slugify
  cat > app/slug.py <<'EOF'
import re


def slugify(text: str) -> str:
    """Lower-case text and join runs of non-alphanumerics with '-'."""
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
EOF
  cat > tests/test_slug.py <<'EOF'
from app.slug import slugify


def test_slugify():
    assert slugify("Hello, World!") == "hello-world"
    assert slugify("  --  ") == ""
EOF
  G add -A; G commit -qm "Add slugify helper for upload names"; push_all ;;
helm)          init_repo main
  mkdir -p chart/templates
  printf 'apiVersion: v2\nname: ingest\nversion: 0.3.1\nappVersion: "1.4.0"\n' > chart/Chart.yaml
  printf 'replicaCount: 2\nimage:\n  repository: registry.example.com/ingest\n  tag: "1.4.0"\n' > chart/values.yaml
  cat > chart/templates/deployment.yaml <<'EOF'
apiVersion: apps/v1
kind: Deployment
metadata:
  name: {{ .Release.Name }}-ingest
spec:
  replicas: {{ .Values.replicaCount }}
  selector:
    matchLabels:
      app: {{ .Release.Name }}-ingest
  template:
    metadata:
      labels:
        app: {{ .Release.Name }}-ingest
    spec:
      containers:
        - name: ingest
          image: "{{ .Values.image.repository }}:{{ .Values.image.tag }}"
EOF
  G add -A; G commit -qm "Ingest chart"
  G checkout -qb feature/team-labels
  cat > chart/templates/deployment.yaml <<'EOF'
apiVersion: apps/v1
kind: Deployment
metadata:
  name: {{ .Release.Name }}-ingest
spec:
  replicas: {{ .Values.replicaCount }}
  selector:
    matchLabels:
      app: {{ .Release.Name }}-ingest
      team: data-platform
  template:
    metadata:
      labels:
        app: {{ .Release.Name }}-ingest
        team: data-platform
    spec:
      containers:
        - name: ingest
          image: "{{ .Values.image.repository }}:{{ .Values.image.tag }}"
          resources:
            limits:
              memory: 512Mi
EOF
  G add -A; G commit -qm "Label ingest pods with the owning team"; push_all ;;
mixed)         init_repo main
  mkdir -p svc tools
  printf 'def parse(line):\n    return line.split(",")\n' > tools/parse.py
  printf 'package main\n\nfunc main() {}\n' > svc/main.go
  printf 'FROM python:3.12-slim\nCOPY tools /tools\n' > Dockerfile
  G add -A; G commit -qm "Base"
  G checkout -qb feature/csv-service
  cat > tools/parse.py <<'EOF'
import csv


def parse(line):
    return next(csv.reader([line]))


def parse_file(path):
    with open(path) as fh:
        return [parse(l) for l in fh]
EOF
  cat > svc/main.go <<'EOF'
package main

import (
	"fmt"
	"net/http"
	"os"
)

func main() {
	http.HandleFunc("/healthz", func(w http.ResponseWriter, r *http.Request) {
		fmt.Fprintln(w, "ok")
	})
	port := os.Getenv("PORT")
	http.ListenAndServe(":"+port, nil)
}
EOF
  cat > Dockerfile <<'EOF'
FROM golang:1.22 AS build
WORKDIR /src
COPY svc .
RUN go build -o /svc main.go

FROM python:3.12-slim
COPY tools /tools
COPY --from=build /svc /usr/local/bin/svc
CMD ["svc"]
EOF
  G add -A; G commit -qm "Serve parsed CSV over HTTP"; push_all ;;
develop-go)    init_repo develop
  cat > worker.go <<'EOF'
package worker

// Run processes jobs sequentially.
func Run(jobs []string, handle func(string) error) []error {
	var errs []error
	for _, j := range jobs {
		if err := handle(j); err != nil {
			errs = append(errs, err)
		}
	}
	return errs
}
EOF
  printf 'module example.com/worker\n\ngo 1.22\n' > go.mod
  G add -A; G commit -qm "Sequential worker"
  G checkout -qb feature/parallel-worker
  cat > worker.go <<'EOF'
package worker

import "sync"

// Run processes jobs with n goroutines and returns every error.
func Run(jobs []string, n int, handle func(string) error) []error {
	in := make(chan string)
	out := make(chan error)
	var wg sync.WaitGroup
	for i := 0; i < n; i++ {
		wg.Add(1)
		go func() {
			defer wg.Done()
			for j := range in {
				if err := handle(j); err != nil {
					out <- err
				}
			}
		}()
	}
	go func() {
		for _, j := range jobs {
			in <- j
		}
		close(in)
	}()
	go func() {
		wg.Wait()
		close(out)
	}()
	var errs []error
	for err := range out {
		errs = append(errs, err)
	}
	return errs
}
EOF
  G add -A; G commit -qm "Process jobs in parallel

Nightly batches grew past the window; fan out over n workers."
  push_all ;;
deploy-sh)     init_repo main
  cat > deploy.sh <<'EOF'
#!/usr/bin/env bash
# Deploy the ingest chart to the namespace given as $1.
NS=${1:-}
helm template ingest ./chart --set image.tag="$(git rev-parse --short HEAD)" \
  | kubectl apply -n "$NS" -f - | tee deploy.log
kubectl rollout status deploy/ingest -n "$NS" --timeout=120s
echo "deployed to $NS"
EOF
  chmod +x deploy.sh; G add -A; G commit -qm "Deploy script"; push_all ;;
net-py)        init_repo main
  mkdir -p lib
  cat > lib/net.py <<'EOF'
import time
import urllib.request


def fetch(url, attempts=3, delay=1.0):
    """Return the body of url, retrying on any error."""
    for i in range(attempts):
        try:
            with urllib.request.urlopen(url, timeout=5) as r:
                return r.read()
        except Exception:
            if i == attempts:
                raise
            time.sleep(delay * (i + 1))
EOF
  G add -A; G commit -qm "Fetch helper"; push_all ;;
many-defects)  init_repo main; py_base
  G checkout -qb feature/batch-import
  cat > app/batch.py <<'EOF'
import os
import pickle
import subprocess

import requests

DB_PASSWORD = "Pr0d-s3cret!"


def load_jobs(path):
    with open(path, "rb") as fh:
        return pickle.load(fh)


def run_job(job):
    subprocess.run(f"import-tool --name {job['name']}", shell=True)


def fetch_manifest(url):
    return requests.get(url, verify=False).json()


def cleanup(tmpdir):
    os.system("rm -rf " + tmpdir + "/*")


def average(values):
    return sum(values) / len(values)


def first_error(results):
    for r in results:
        if r["status"] == "error":
            return r
    return results[0]
EOF
  G add -A; G commit -qm "Batch import of upload jobs"; push_all ;;
clean-py)      init_repo main
  mkdir -p lib
  cat > lib/iterutil.py <<'EOF'
from itertools import islice


def chunked(iterable, size):
    """Yield lists of at most `size` items from `iterable`, in order."""
    if size < 1:
        raise ValueError("size must be at least 1")
    it = iter(iterable)
    while True:
        chunk = list(islice(it, size))
        if not chunk:
            return
        yield chunk
EOF
  G add -A; G commit -qm "Add chunked() helper"; push_all ;;
develop-py)    init_repo develop; py_base; py_retry_feature; push_all ;;
develop-py-on-base) init_repo develop; py_base; py_retry_feature; push_all; G checkout -q develop ;;
grill-sb)      init_repo main; py_base
  cat > PROJ-2001.md <<'EOF'
# PROJ-2001: Retry failed uploads

As a CLI user, I want uploads to retry on transient errors, so that a
flaky network does not fail the whole run.

## Acceptance criteria

- Uploads survive short outages.
- The CLI still fails fast on bad input.
EOF
  cat > SB-PROJ-2001.md <<'EOF'
# Example Platform / PROJ-2001

> **Goal:** Retry uploads on transient errors.

## Acceptance Criteria

- [ ] Uploads survive short outages.
- [ ] The CLI still fails fast on bad input.
- [ ] Retries are logged. *(proposed)*

## Core tasks

- [ ] `uploader`: mount an HTTPAdapter with a Retry policy in `app/uploader.py`.
- [ ] `uploader`: add a test for the retry policy in `tests/test_uploader.py`.

## Questions

- Which requests version are we on, and does it support urllib3 Retry?
- How many retries, and with what backoff?
- Should retries cover POST, which is not idempotent?
- Does the API team need to know about the extra load from retries?
- Do we add a slide to our sprint review presentation for this story?

## Notes

- Impacted repositories: uploader

## Testing

| Test Case ID | Situation | Expected result | Log | Build result link |
|--------------|-----------|-----------------|-----|-------------------|
| TC-1 | Server returns 503 twice, then 200 | Upload succeeds | | |
EOF
  G add -A; G commit -qm "Add PROJ-2001 story and SB"; push_all ;;
idea-empty)    mkdir -p repo ;;
idea-brief-2ng) init_repo main
  mkdir -p docs
  cat > docs/brief.md <<'EOF'
# Plant Pal Brief
Status: Approved 2026-10-14
## Problem (2 to 3 sentences)
I forget to water my plants and they die.
## Target user and main job-to-be-done
Busy flat-dwellers with 5 to 20 house plants: know what to water today.
## Pitch (3 sentences max)
A web app that tells you which plants need water today.
## Success metrics (measurable)
- 80% of reminders acted on within 24 hours over the first month
## MVP scope (3 to 5 bullets)
- Add a plant with a watering interval
- Daily reminder email
- Mark a plant as watered
## Non-goals (at least 5)
- No native mobile app
- No plant identification from photos
## Constraints (budget, cloud, compliance, timeline)
- Under 10 USD per month, one developer, 4 weeks
## Open questions
EOF
  G add -A; G commit -qm "Add brief"; push_all ;;
idea-req-gap)  init_repo main
  mkdir -p docs/superpowers/specs
  cat > docs/brief.md <<'EOF'
# Plant Pal Brief
Status: Approved 2026-10-14
## Problem (2 to 3 sentences)
I forget to water my plants and they die.
## Target user and main job-to-be-done
Busy flat-dwellers with 5 to 20 house plants: know what to water today.
## Pitch (3 sentences max)
A web app that tells you which plants need water today.
## Success metrics (measurable)
- 80% of reminders acted on within 24 hours over the first month
## MVP scope (3 to 5 bullets)
- Add a plant with a watering interval
- Daily reminder email
- Mark a plant as watered
## Non-goals (at least 5)
- No native mobile app
- No plant identification from photos
- No social or sharing features
- No sensor or smart-pot integration
- No payments
## Constraints (budget, cloud, compliance, timeline)
- Under 10 USD per month, one developer, 4 weeks
## Open questions
EOF
  cat > docs/superpowers/specs/2026-10-14-plant-pal-design.md <<'EOF'
# Plant Pal design
Status: Approved 2026-10-14
A small web app with a plants table and a daily reminder job.
EOF
  cat > docs/requirements.md <<'EOF'
# Requirements: Plant Pal (v0.1, 2026-10-14)
Status: Draft
## Functional requirements
### FR-1 Plants
User story: As an owner, I want to add plants so that I get reminders.
- FR-1.1 WHEN the owner adds a plant with an interval THE SYSTEM SHALL store it.
Verification: tests/test_plants.py::test_add_plant
### FR-2 Reminders
User story: As an owner, I want a daily email so that I water on time.
- FR-2.1 WHEN a plant is due THE SYSTEM SHALL email the owner by 08:00 local time.
- FR-2.2 IF the email fails THEN THE SYSTEM SHALL retry once after 10 minutes.
## Non-functional requirements
- NFR-PERF: p95 < 300 ms at 5 rps
- NFR-SEC: authn magic link; authz owner only; input validated at the API; secrets from env
- NFR-OPS: structured logs; RPO 24 h
- NFR-COST: < 10 USD per month
## Out of scope
## Traceability: requirement -> task -> test
## Review log
EOF
  G add -A; G commit -qm "Add brief, design and draft requirements"; push_all ;;
*) echo "unknown fixture $kind" >&2; exit 2 ;;
esac
if [ -d "$dest/repo/.git" ]; then
  echo "built $kind at $dest/repo on $(git -C "$dest/repo" branch --show-current)"
else
  echo "built $kind at $dest/repo (no git)"
fi
