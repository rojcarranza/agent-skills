#!/usr/bin/env python3
"""A stand-in Bitbucket Data Center for the roj-review-pr-comment evals.

  python evals/fixtures/fake_bitbucket.py <fixture-dir> <normal|reviewed|prior>

Serves PR 7 of project APP, repository uploader, on 127.0.0.1 from the repo
that build.sh made as `pyrepo-bb-pr` (the head is refs/pull-requests/7/from
in <fixture-dir>/origin.git). The first line it prints is
`BITBUCKET_URL=http://127.0.0.1:<port>`; export that and
BITBUCKET_TOKEN=test-token for the run, and stop the server afterwards.
Nothing leaves the machine. Every request line is appended to
<fixture-dir>/bb-state/calls.log (never a header, so never the token) and the
comments it accepts are kept in bb-state/posted.json for grading.

  normal    a PR with one unrelated human comment
  reviewed  an earlier run already reviewed this head: its summary comment
            carries the "Reviewed commit" line for the head
  prior     an earlier run reviewed an older head and commented on
            app/uploader.py; this head is new

Also importable: serve(head, mode) -> (server, state), for the unit tests.
Python >= 3.8, standard library only.
"""
import json
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

TOKEN = "test-token"
PROJECT, REPO, PR = "APP", "uploader", "7"
BASE = f"/rest/api/1.0/projects/{PROJECT}/repos/{REPO}/pull-requests/{PR}"
PAGE_CAP = 2          # small pages, so clients must follow nextPageStart
LINE_TYPES = {"ADDED", "CONTEXT", "REMOVED"}
FILE_TYPES = {"FROM", "TO"}


class State:
    def __init__(self, head, mode, reject=()):
        self.head, self.mode = head, mode
        self.fail_summary = False
        self.reject = set(reject)       # "path:line" the server refuses
        self.calls, self.posted, self.next_id = [], [], 100
        self.activities = [
            {"action": "OPENED"},
            {"action": "COMMENTED",
             "comment": {"id": 1, "text": "Is this the ticket for the nightly "
                         "restart?", "comments": []}}]
        if mode == "reviewed":
            self.activities.append(self.summary(head, "Earlier run."))
        elif mode == "prior":
            self.activities.append(self.summary("a" * 40, "Earlier run."))
            self.activities.append({
                "action": "COMMENTED",
                "commentAnchor": {"path": "app/uploader.py", "line": 20,
                                  "lineType": "ADDED", "fileType": "TO"},
                "comment": {"id": 3, "comments": [], "text":
                            "\U0001F7E0 **Major** · Probable - upload() "
                            "returns None after the last failed attempt.\n\n"
                            "Fails when: every attempt raises.\n\nFix: "
                            "re-raise the last error."}})

    @staticmethod
    def summary(head, body):
        return {"action": "COMMENTED", "comment": {
            "id": 2, "comments": [],
            "text": f"{body}\n\nReviewed commit `{head[:12]}`"}}


def handler(state):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def reply(self, status, body):
            data = json.dumps(body).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def error(self, status, message):
            self.reply(status, {"errors": [{"message": message}]})

        def route(self, method):
            url = urlsplit(self.path)
            state.calls.append(f"{method} {url.path}")
            if self.headers.get("Authorization") != f"Bearer {TOKEN}":
                return self.error(401, "Authentication failed")
            if method == "GET" and url.path == BASE:
                return self.reply(200, {
                    "id": int(PR), "state": "OPEN",
                    "title": "Retry uploads on transient failures",
                    "description": "Uploads fail during the ingest API "
                                   "nightly restart; retry with backoff.",
                    "fromRef": {"displayId": "feature/retry-uploads",
                                "latestCommit": state.head},
                    "toRef": {"displayId": "develop",
                              "latestCommit": "b" * 40}})
            if method == "GET" and url.path == BASE + "/activities":
                q = parse_qs(url.query)
                start = int(q.get("start", ["0"])[0])
                limit = min(int(q.get("limit", ["25"])[0]), PAGE_CAP)
                values = state.activities[start:start + limit]
                last = start + limit >= len(state.activities)
                return self.reply(200, {
                    "values": values, "isLastPage": last,
                    **({} if last else {"nextPageStart": start + limit})})
            if method == "POST" and url.path == BASE + "/comments":
                return self.post()
            self.error(404, f"No such resource: {url.path}")

        def post(self):
            try:
                size = int(self.headers.get("Content-Length", "0"))
                body = json.loads(self.rfile.read(size))
            except ValueError:
                return self.error(400, "Request body is not valid JSON")
            text, anchor = body.get("text"), body.get("anchor")
            if not isinstance(text, str) or not text.strip():
                return self.error(400, "Comment text is required")
            if anchor is None and state.fail_summary:
                return self.error(500, "Internal error")
            if anchor is not None:
                ok = (isinstance(anchor, dict)
                      and isinstance(anchor.get("path"), str)
                      and isinstance(anchor.get("line"), int)
                      and anchor.get("lineType") in LINE_TYPES
                      and anchor.get("fileType") in FILE_TYPES)
                if not ok:
                    return self.error(400, "The comment anchor is invalid")
                if f"{anchor['path']}:{anchor['line']}" in state.reject:
                    return self.error(409, "The specified line is not part "
                                      "of the diff")
            state.next_id += 1
            state.posted.append(body)
            comment = {"id": state.next_id, "text": text, "comments": []}
            state.activities.append(
                {"action": "COMMENTED", "comment": comment,
                 **({"commentAnchor": anchor} if anchor else {})})
            self.reply(201, comment)

        def do_GET(self):
            self.route("GET")

        def do_POST(self):
            self.route("POST")

    return Handler


def serve(head, mode, reject=()):
    state = State(head, mode, reject)
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler(state))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server, state


def main(argv):
    if len(argv) != 3 or argv[2] not in ("normal", "reviewed", "prior"):
        print(__doc__, file=sys.stderr)
        return 2
    dest, mode = Path(argv[1]), argv[2]
    head = subprocess.run(
        ["git", "-C", str(dest / "origin.git"), "rev-parse",
         "refs/pull-requests/7/from"], capture_output=True, text=True,
        check=True).stdout.strip()
    state_dir = dest / "bb-state"
    state_dir.mkdir(exist_ok=True)
    server, state = serve(head, mode)
    print(f"BITBUCKET_URL=http://127.0.0.1:{server.server_port}", flush=True)
    seen = 0
    try:
        while True:
            threading.Event().wait(0.2)
            if len(state.calls) != seen:
                seen = len(state.calls)
                (state_dir / "calls.log").write_text(
                    "\n".join(state.calls) + "\n", encoding="utf-8")
                (state_dir / "posted.json").write_text(
                    json.dumps(state.posted, indent=2), encoding="utf-8")
    except KeyboardInterrupt:
        return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
