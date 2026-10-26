#!/usr/bin/env python3
"""Read and comment on one Bitbucket Data Center pull request over REST.

The only network code of roj-review-pr-comment. Python >= 3.8, standard
library only, so it runs the same from bash, PowerShell and cmd. All JSON is
built with json.dumps; nothing is escaped by hand.

  python bitbucket_pr.py token-status
  python bitbucket_pr.py info     --project KEY --repo SLUG --pr ID
  python bitbucket_pr.py comments --project KEY --repo SLUG --pr ID [--head SHA]
  python bitbucket_pr.py post     --project KEY --repo SLUG --pr ID
                                  --findings FILE|-  [--dry-run]

Environment (never passed as arguments, never printed):
  BITBUCKET_URL    server root, e.g. https://bitbucket.example.com (plus the
                   context path, if the server has one)
  BITBUCKET_TOKEN  HTTP access token, sent as "Authorization: Bearer ..."

The findings file for `post`:
  {"head": "<full head sha>",
   "summary": "<markdown for the PR-level comment>",
   "comments": [{"path": "app/x.py", "line": 12, "lineType": "ADDED",
                 "text": "<markdown>"}]}
`line` is the line number in the new file; `lineType` is ADDED or CONTEXT.

Exit codes: 0 ok, 2 bad input or configuration, 3 no token, 4 token
rejected, 5 server or network error.
"""
import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request

MAX_INLINE = 15
MAX_DESCRIPTION = 4000
PAGE = 100
MAX_PAGES = 200
LINE_TYPES = ("ADDED", "CONTEXT")
TIMEOUT = 30

EXIT_INPUT, EXIT_NO_TOKEN, EXIT_REJECTED, EXIT_SERVER = 2, 3, 4, 5


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


OPENER = urllib.request.build_opener(NoRedirect)


class Fail(Exception):
    def __init__(self, message, code):
        super().__init__(message)
        self.code = code


class ApiError(Exception):
    def __init__(self, status, message):
        super().__init__(f"HTTP {status}: {message}")
        self.status = status


def marker(head):
    """The visible line that tells a later run this head was reviewed."""
    return f"Reviewed commit `{head[:12]}`"


def base_url(env):
    url = (env.get("BITBUCKET_URL") or "").strip().rstrip("/")
    if not url:
        raise Fail("BITBUCKET_URL is not set (server root, e.g. "
                   "https://bitbucket.example.com)", EXIT_INPUT)
    parts = urllib.parse.urlsplit(url)
    if parts.scheme not in ("http", "https") or not parts.hostname:
        raise Fail("BITBUCKET_URL must be an http(s) URL", EXIT_INPUT)
    if parts.username or parts.password or parts.query or parts.fragment:
        raise Fail("BITBUCKET_URL must not carry credentials, a query or a "
                   "fragment", EXIT_INPUT)
    if parts.scheme == "http" and parts.hostname not in (
            "localhost", "127.0.0.1", "::1"):
        raise Fail("BITBUCKET_URL must be https: the token would travel in "
                   "clear text", EXIT_INPUT)
    return url


def token(env):
    value = (env.get("BITBUCKET_TOKEN") or "").strip()
    if not value:
        raise Fail("BITBUCKET_TOKEN is not set", EXIT_NO_TOKEN)
    if re.search(r"\s", value):
        raise Fail("BITBUCKET_TOKEN holds whitespace; it is not a token",
                   EXIT_INPUT)
    return value


def pr_path(project, repo, pr):
    quote = lambda s: urllib.parse.quote(str(s), safe="~")
    return (f"/rest/api/1.0/projects/{quote(project)}/repos/{quote(repo)}"
            f"/pull-requests/{quote(pr)}")


class Client:
    def __init__(self, env, project, repo, pr):
        self.root = base_url(env)
        self.token = token(env)
        self.pr_path = pr_path(project, repo, pr)

    def call(self, method, path, body=None, query=None):
        url = self.root + path
        if query:
            url += "?" + urllib.parse.urlencode(query)
        data = json.dumps(body).encode("utf-8") if body is not None else None
        req = urllib.request.Request(url, data=data, method=method, headers={
            "Authorization": f"Bearer {self.token}",
            "Accept": "application/json",
            **({"Content-Type": "application/json"} if data else {})})
        try:
            with OPENER.open(req, timeout=TIMEOUT) as resp:
                raw = resp.read()
        except urllib.error.HTTPError as err:
            if 300 <= err.code < 400:
                raise Fail(f"{self.root} answered HTTP {err.code}, a "
                           "redirect; the token is not sent elsewhere",
                           EXIT_SERVER) from None
            raise ApiError(err.code, error_message(err)) from None
        except (urllib.error.URLError, OSError) as err:
            raise Fail(f"cannot reach {self.root}: "
                       f"{getattr(err, 'reason', err)}", EXIT_SERVER) from None
        try:
            page = json.loads(raw) if raw else {}
        except ValueError:
            page = None
        if not isinstance(page, dict):
            raise Fail(f"{self.root} did not answer with a JSON object",
                       EXIT_SERVER)
        return page

    def pages(self, path, query=None):
        start = 0
        for _ in range(MAX_PAGES):
            page = self.call("GET", path,
                             query={**(query or {}), "start": start,
                                    "limit": PAGE})
            yield from page.get("values", [])
            if page.get("isLastPage", True):
                return
            start = page.get("nextPageStart", start + PAGE)


def error_message(err):
    try:
        errors = json.loads(err.read()).get("errors") or []
        return "; ".join(e.get("message", "") for e in errors) or err.reason
    except (ValueError, AttributeError):
        return str(err.reason)


def guard(call):
    """Turn an auth failure into its own exit code, other API errors into the
    server error code."""
    try:
        return call()
    except ApiError as err:
        code = EXIT_REJECTED if err.status in (401, 403) else EXIT_SERVER
        raise Fail(str(err), code) from None


def fetch_comments(client):
    """Every PR comment with an anchor or a PR-level one, replies left out."""
    out = []
    for act in client.pages(client.pr_path + "/activities"):
        if act.get("action") != "COMMENTED" or not act.get("comment"):
            continue
        comment = act["comment"]
        anchor = act.get("commentAnchor") or comment.get("anchor") or {}
        out.append({"id": comment.get("id"), "path": anchor.get("path"),
                    "line": anchor.get("line"),
                    "text": comment.get("text", "")})
    return out


def cmd_token_status(args, env, out):
    json.dump({"token": bool((env.get("BITBUCKET_TOKEN") or "").strip()),
               "baseUrl": (env.get("BITBUCKET_URL") or "").strip() or None},
              out)
    out.write("\n")


def cmd_info(args, env, out):
    client = Client(env, args.project, args.repo, args.pr)
    pr = guard(lambda: client.call("GET", client.pr_path))
    description = pr.get("description") or ""
    json.dump({
        "id": pr.get("id"), "title": pr.get("title"), "state": pr.get("state"),
        "description": description[:MAX_DESCRIPTION],
        "descriptionTruncated": len(description) > MAX_DESCRIPTION,
        "source": (pr.get("fromRef") or {}).get("displayId"),
        "target": (pr.get("toRef") or {}).get("displayId"),
        "headSha": (pr.get("fromRef") or {}).get("latestCommit"),
        "targetSha": (pr.get("toRef") or {}).get("latestCommit")}, out)
    out.write("\n")


def cmd_comments(args, env, out):
    client = Client(env, args.project, args.repo, args.pr)
    comments = guard(lambda: fetch_comments(client))
    result = {"comments": comments}
    if args.head:
        result["reviewed"] = any(marker(args.head) in c["text"]
                                 for c in comments)
    json.dump(result, out)
    out.write("\n")


def load_findings(source, stdin):
    try:
        if source == "-":
            raw = stdin.read()
        else:
            with open(source, encoding="utf-8") as fh:
                raw = fh.read()
        data = json.loads(raw)
    except (OSError, ValueError) as err:
        raise Fail(f"cannot read findings: {err}", EXIT_INPUT) from None
    if not isinstance(data, dict):
        raise Fail("findings must be a JSON object", EXIT_INPUT)
    head = data.get("head")
    if not isinstance(head, str) or not re.fullmatch(r"[0-9a-f]{12,64}", head):
        raise Fail("findings.head must be the head commit sha", EXIT_INPUT)
    if not isinstance(data.get("summary"), str) or not data["summary"].strip():
        raise Fail("findings.summary must be a non-empty string", EXIT_INPUT)
    comments = data.get("comments", [])
    if not isinstance(comments, list) or len(comments) > MAX_INLINE:
        raise Fail(f"findings.comments must be a list of at most "
                   f"{MAX_INLINE}", EXIT_INPUT)
    for i, c in enumerate(comments, 1):
        ok = (isinstance(c, dict)
              and isinstance(c.get("path"), str) and c["path"]
              and isinstance(c.get("line"), int)
              and not isinstance(c["line"], bool) and c["line"] >= 1
              and c.get("lineType") in LINE_TYPES
              and isinstance(c.get("text"), str) and c["text"].strip())
        if not ok:
            raise Fail(f"comment {i} needs path, line (>= 1), lineType "
                       f"({'|'.join(LINE_TYPES)}) and text", EXIT_INPUT)
    return data


def inline_body(c):
    return {"text": c["text"],
            "anchor": {"path": c["path"], "line": c["line"],
                       "lineType": c["lineType"], "fileType": "TO"}}


def summary_body(findings, unanchored):
    parts = [findings["summary"].strip()]
    if unanchored:
        parts.append("Findings Bitbucket could not anchor to a line:\n"
                     + "\n".join(f"- `{c['path']}:{c['line']}` - "
                                 f"{c['text'].strip().splitlines()[0]}"
                                 for c in unanchored))
    parts.append(marker(findings["head"]))
    return {"text": "\n\n".join(parts)}


def cmd_post(args, env, out, stdin):
    findings = load_findings(args.findings, stdin)
    comments = findings.get("comments", [])
    if args.dry_run:
        path = pr_path(args.project, args.repo, args.pr) + "/comments"
        json.dump({"dryRun": True, "requests": [
            {"method": "POST", "path": path, "body": body}
            for body in [inline_body(c) for c in comments]
            + [summary_body(findings, [])]]}, out, indent=2)
        out.write("\n")
        return
    client = Client(env, args.project, args.repo, args.pr)
    existing = guard(lambda: fetch_comments(client))
    if any(marker(findings["head"]) in c["text"] for c in existing):
        json.dump({"status": "already-reviewed", "posted": [],
                   "skipped": [], "failed": []}, out)
        out.write("\n")
        return
    seen = {(c["path"], c["text"].strip()) for c in existing if c["path"]}
    posted, skipped, failed, fatal = [], [], [], None
    for c in comments:
        if (c["path"], c["text"].strip()) in seen:
            skipped.append({"path": c["path"], "line": c["line"]})
            continue
        try:
            reply = client.call("POST", client.pr_path + "/comments",
                                inline_body(c))
            posted.append({"path": c["path"], "line": c["line"],
                           "id": reply.get("id")})
        except ApiError as err:
            if err.status in (400, 404, 409):
                failed.append({"path": c["path"], "line": c["line"],
                               "message": str(err), "text": c["text"]})
            else:
                fatal = err
                break
    status = "failed" if fatal and not posted else "partial" if fatal else "ok"
    summary_id = None
    all_skipped = comments and not posted and not failed and not fatal
    if not fatal and not all_skipped:
        try:
            body = summary_body(findings, [
                {"path": f["path"], "line": f["line"], "text": f["text"]}
                for f in failed])
            summary_id = client.call("POST", client.pr_path + "/comments",
                                     body).get("id")
        except ApiError as err:
            fatal, status = err, "partial" if posted else "failed"
    json.dump({"status": status, "posted": posted, "skipped": skipped,
               "failed": [{k: f[k] for k in ("path", "line", "message")}
                          for f in failed],
               "summaryId": summary_id,
               "error": str(fatal) if fatal else None}, out)
    out.write("\n")
    if fatal:
        raise Fail(str(fatal), EXIT_REJECTED if fatal.status in (401, 403)
                   else EXIT_SERVER)


def parser():
    ap = argparse.ArgumentParser(
        description="Read and comment on a Bitbucket Data Center PR.")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("token-status",
                   help="say whether BITBUCKET_TOKEN and BITBUCKET_URL are set")
    for name in ("info", "comments", "post"):
        p = sub.add_parser(name)
        p.add_argument("--project", required=True,
                       help="project key; ~USER for a personal repository")
        p.add_argument("--repo", required=True, help="repository slug")
        p.add_argument("--pr", required=True, help="pull request id")
        if name == "comments":
            p.add_argument("--head", help="full head sha: also report "
                           "whether it already carries a review")
        if name == "post":
            p.add_argument("--findings", required=True,
                           help="findings JSON file, or - for stdin")
            p.add_argument("--dry-run", action="store_true",
                           help="validate and print the requests; no token "
                           "and no network")
    return ap


def main(argv=None, env=None, out=None, stdin=None):
    env = os.environ if env is None else env
    out = out or sys.stdout
    stdin = stdin or sys.stdin
    args = parser().parse_args(argv)
    if args.cmd != "token-status" and not re.fullmatch(r"\d+", args.pr):
        print("error: --pr must be the numeric pull request id",
              file=sys.stderr)
        return EXIT_INPUT
    try:
        if args.cmd == "token-status":
            cmd_token_status(args, env, out)
        elif args.cmd == "info":
            cmd_info(args, env, out)
        elif args.cmd == "comments":
            cmd_comments(args, env, out)
        else:
            cmd_post(args, env, out, stdin)
    except Fail as err:
        print(f"error: {err}", file=sys.stderr)
        return err.code
    return 0


if __name__ == "__main__":
    sys.exit(main())
