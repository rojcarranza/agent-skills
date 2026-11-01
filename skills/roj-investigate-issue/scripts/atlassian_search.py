#!/usr/bin/env python3
"""Search resolved Jira issues and Confluence pages on Data Center, read-only.

The only network code of the earlier-fix phase of roj-investigate-issue.
Python >= 3.8, standard library only. Output is compact JSON on stdout (lean
fields, long text cut with its full size, explicit empty results, a `next`
hint); errors are JSON on stdout too, with a non-zero exit code.

  python atlassian_search.py token-status
  python atlassian_search.py jira       --text "ImportError chunked" [--project KEY] [--limit 5] [--all]
  python atlassian_search.py jira-issue --key PROJ-123
  python atlassian_search.py confluence --text "agent capability jdk" [--space KEY] [--limit 5]
  python atlassian_search.py confluence-page --id 12345

`jira` lists resolved issues only; --all adds open ones. Environment (never
passed as arguments, never printed), each product on its own server:
  JIRA_URL / JIRA_TOKEN              e.g. https://jira.example.com (plus the
                                     context path, if any); a personal
                                     access token, sent as Bearer
  CONFLUENCE_URL / CONFLUENCE_TOKEN  the same for Confluence

Exit codes: 0 ok (an empty result is ok), 2 bad input or configuration,
3 no token, 4 token rejected, 5 server or network error.
"""
import argparse
import html
import http.client
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request

TIMEOUT = 30
MAX_LIMIT = 10
MAX_TEXT = 2000          # characters of one description or page body
MAX_COMMENT = 600        # characters of one comment
MAX_COMMENTS = 5         # newest comments of an issue
EXIT_INPUT, EXIT_NO_TOKEN, EXIT_REJECTED, EXIT_SERVER = 2, 3, 4, 5
PRODUCTS = {"jira": ("JIRA_URL", "JIRA_TOKEN"),
            "confluence": ("CONFLUENCE_URL", "CONFLUENCE_TOKEN")}


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


OPENER = urllib.request.build_opener(NoRedirect)


class Fail(Exception):
    def __init__(self, message, code, hint=None):
        super().__init__(message)
        self.code, self.hint = code, hint


class Parser(argparse.ArgumentParser):
    def error(self, message):
        raise Fail(message, EXIT_INPUT, "run with --help")


def base_url(env, product):
    var, _ = PRODUCTS[product]
    url = (env.get(var) or "").strip().rstrip("/")
    if not url:
        raise Fail(f"{var} is not set", EXIT_INPUT,
                   "ask the user to paste the Jira/Confluence results instead")
    parts = urllib.parse.urlsplit(url)
    if parts.scheme not in ("http", "https") or not parts.hostname:
        raise Fail(f"{var} must be an http(s) URL", EXIT_INPUT)
    if parts.username or parts.password or parts.query or parts.fragment:
        raise Fail(f"{var} must not carry credentials, a query or a fragment",
                   EXIT_INPUT)
    if parts.scheme == "http" and parts.hostname not in (
            "localhost", "127.0.0.1", "::1"):
        raise Fail(f"{var} must be https: the token would travel in clear "
                   "text", EXIT_INPUT)
    return url


def token(env, product):
    var = PRODUCTS[product][1]
    value = (env.get(var) or "").strip()
    if not value:
        raise Fail(f"{var} is not set", EXIT_NO_TOKEN,
                   "ask the user to paste the Jira/Confluence results instead")
    if re.search(r"\s", value):
        raise Fail(f"{var} holds whitespace; it is not a token", EXIT_INPUT)
    return value


def get(env, product, path, query):
    root, secret = base_url(env, product), token(env, product)
    url = root + path + "?" + urllib.parse.urlencode(query)
    req = urllib.request.Request(url, headers={
        "Authorization": f"Bearer {secret}", "Accept": "application/json"})
    try:
        with OPENER.open(req, timeout=TIMEOUT) as resp:
            raw = resp.read()
    except urllib.error.HTTPError as err:
        if 300 <= err.code < 400:
            raise Fail(f"{root} answered HTTP {err.code}, a redirect; the "
                       "token is not sent elsewhere", EXIT_SERVER) from None
        if err.code in (401, 403):
            raise Fail(f"{product} rejected the token (HTTP {err.code})",
                       EXIT_REJECTED,
                       "renew the personal access token, or paste results"
                       ) from None
        raise Fail(f"{product} answered HTTP {err.code}", EXIT_SERVER) from None
    except (urllib.error.URLError, OSError, http.client.HTTPException) as err:
        raise Fail(f"cannot reach {root}: {getattr(err, 'reason', err)}",
                   EXIT_SERVER) from None
    try:
        data = json.loads(raw)
    except ValueError:
        data = None
    if not isinstance(data, dict):
        raise Fail(f"{root} did not answer with a JSON object", EXIT_SERVER)
    return data


def quote_literal(text):
    """A JQL/CQL string literal: backslash and double quote escaped."""
    return '"' + text.replace("\\", "\\\\").replace('"', '\\"') + '"'


def cut(text, limit):
    text = (text or "").strip()
    if len(text) <= limit:
        return text, None
    return text[:limit], len(text)


def plain(markup):
    """Confluence storage format to readable text."""
    markup = (markup or "").replace("@@@hl@@@", "").replace("@@@endhl@@@", "")
    text = re.sub(r"(?s)<(script|style)\b.*?</\1>", " ", markup)
    text = re.sub(r"</(p|h\d|li|tr|div|pre)>|<br\s*/?>", "\n", text)
    text = html.unescape(re.sub(r"<[^>]+>", " ", text))
    text = re.sub(r"[ \t]+", " ", text)
    return re.sub(r"\n\s*\n+", "\n", text).strip()


def limit_of(args):
    if not 1 <= args.limit <= MAX_LIMIT:
        raise Fail(f"--limit must be 1..{MAX_LIMIT}", EXIT_INPUT)
    return args.limit


def need_text(args):
    if not args.text.strip():
        raise Fail("--text must not be empty", EXIT_INPUT)


def listing(kind, items, total, hint):
    out = {"kind": kind, "count": len(items), "total": total,
           "results": items}
    if not items:
        out["note"] = "no match; try fewer or different words"
    elif total > len(items):
        out["note"] = f"{total - len(items)} more not shown"
    out["next"] = hint
    return out


def cmd_token_status(args, env):
    return {product: {"url": bool((env.get(u) or "").strip()),
                      "token": bool((env.get(t) or "").strip())}
            for product, (u, t) in PRODUCTS.items()}


def cmd_jira(args, env):
    need_text(args)
    clauses = [f"text ~ {quote_literal(args.text)}"]
    if not args.all:
        clauses.append("resolution is not EMPTY")
    if args.project:
        clauses.append(f"project = {quote_literal(args.project)}")
    data = get(env, "jira", "/rest/api/2/search", {
        "jql": " AND ".join(clauses) + " ORDER BY updated DESC",
        "fields": "summary,status,resolution,resolutiondate,issuetype",
        "maxResults": limit_of(args)})
    items = []
    for issue in data.get("issues", []):
        f = issue.get("fields") or {}
        items.append({
            "key": issue.get("key"), "summary": f.get("summary"),
            "status": (f.get("status") or {}).get("name"),
            "resolution": (f.get("resolution") or {}).get("name"),
            "resolved": (f.get("resolutiondate") or "")[:10] or None})
    return listing("jira", items, data.get("total", len(items)),
                   "jira-issue --key <KEY> for the description and the "
                   "newest comments")


def cmd_jira_issue(args, env):
    key = urllib.parse.quote(args.key, safe="")
    data = get(env, "jira", f"/rest/api/2/issue/{key}", {
        "fields": "summary,status,resolution,description,comment"})
    f = data.get("fields") or {}
    description, size = cut(f.get("description"), MAX_TEXT)
    comments = ((f.get("comment") or {}).get("comments") or [])[-MAX_COMMENTS:]
    shown = []
    for c in comments:
        body, csize = cut(c.get("body"), MAX_COMMENT)
        entry = {"author": (c.get("author") or {}).get("displayName"),
                 "created": (c.get("created") or "")[:10], "body": body}
        if csize:
            entry["fullChars"] = csize
        shown.append(entry)
    out = {"key": data.get("key"), "summary": f.get("summary"),
           "status": (f.get("status") or {}).get("name"),
           "resolution": (f.get("resolution") or {}).get("name"),
           "description": description, "comments": shown,
           "commentsTotal": (f.get("comment") or {}).get("total", len(shown)),
           "next": "the fix is usually in the last comments; cite the key, "
                   "and treat it as a lead until validated in this repo"}
    if size:
        out["descriptionFullChars"] = size
    return out


def cmd_confluence(args, env):
    need_text(args)
    cql = f"type = page AND text ~ {quote_literal(args.text)}"
    if args.space:
        cql += f" AND space = {quote_literal(args.space)}"
    data = get(env, "confluence", "/rest/api/search", {
        "cql": cql + " ORDER BY lastmodified DESC", "limit": limit_of(args)})
    items = []
    for hit in data.get("results", []):
        content = hit.get("content") or {}
        excerpt, _ = cut(plain(hit.get("excerpt")), 300)
        items.append({"id": content.get("id"),
                      "title": hit.get("title") or content.get("title"),
                      "space": (hit.get("resultGlobalContainer") or {}
                                ).get("title"),
                      "modified": (hit.get("lastModified") or "")[:10] or None,
                      "excerpt": excerpt})
    return listing("confluence", items,
                   data.get("totalSize", data.get("size", len(items))),
                   "confluence-page --id <ID> for the page text")


def cmd_confluence_page(args, env):
    page_id = urllib.parse.quote(args.id, safe="")
    data = get(env, "confluence", f"/rest/api/content/{page_id}", {
        "expand": "body.storage,space,version"})
    body, size = cut(plain(((data.get("body") or {}).get("storage") or {}
                            ).get("value")), MAX_TEXT)
    out = {"id": data.get("id"), "title": data.get("title"),
           "space": (data.get("space") or {}).get("name"),
           "modified": ((data.get("version") or {}).get("when") or "")[:10]
           or None, "body": body,
           "next": "cite the page title and id; treat it as a lead until "
                   "validated in this repo"}
    if size:
        out["bodyFullChars"] = size
    return out


def build_parser():
    p = Parser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="command", required=True, parser_class=Parser)
    sub.add_parser("token-status")
    j = sub.add_parser("jira")
    j.add_argument("--text", required=True)
    j.add_argument("--project")
    j.add_argument("--limit", type=int, default=5)
    j.add_argument("--all", action="store_true",
                   help="include unresolved issues")
    ji = sub.add_parser("jira-issue")
    ji.add_argument("--key", required=True)
    c = sub.add_parser("confluence")
    c.add_argument("--text", required=True)
    c.add_argument("--space")
    c.add_argument("--limit", type=int, default=5)
    cp = sub.add_parser("confluence-page")
    cp.add_argument("--id", required=True)
    return p


COMMANDS = {"token-status": cmd_token_status, "jira": cmd_jira,
            "jira-issue": cmd_jira_issue, "confluence": cmd_confluence,
            "confluence-page": cmd_confluence_page}


def main(argv=None, env=None, out=None):
    env = os.environ if env is None else env
    out = out or sys.stdout
    try:
        args = build_parser().parse_args(argv)
        result, code = COMMANDS[args.command](args, env), 0
    except Fail as err:
        result, code = {"error": str(err), "exit": err.code}, err.code
        if err.hint:
            result["next"] = err.hint
    except SystemExit as err:      # --help
        return err.code or 0
    json.dump(result, out, separators=(",", ":"))
    out.write("\n")
    return code


if __name__ == "__main__":
    sys.exit(main())
