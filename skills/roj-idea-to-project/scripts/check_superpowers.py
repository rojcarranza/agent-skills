#!/usr/bin/env python3
"""Report whether the Superpowers plugin is installed, enabled and current.

Usage: check_superpowers.py [--client auto|claude|copilot] [--min-version 7.0.0]

Reads `claude plugin list --json` (Claude Code) or `copilot plugin list`
(Copilot CLI). This script never installs anything: it names the commands
for the user to approve in "next".

stdout: one JSON object
  client              "claude", "copilot" or null when neither CLI is on PATH
  installed           true when a superpowers@<marketplace> install exists
  version             the installed version, "unknown", or null
  version_comparable  false when version is not X.Y.Z (a commit SHA)
  enabled             true/false, or null when unknown
  status              ok | outdated | missing | disabled | undetectable
  next                commands to run, in order; empty when nothing to do
stderr: one line for the human.

Exit codes: 0 for ok and outdated, 1 for missing, disabled, undetectable.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import signal
import shutil
import subprocess
import sys
from typing import Optional

OFFICIAL = "claude-plugins-official"
COMMUNITY = "superpowers-marketplace"
VERSION_RE = re.compile(r"\bv?(\d+)\.(\d+)\.(\d+)\b")
PASSING = {"ok", "outdated"}
TIMEOUT = 30  # seconds; a CLI waiting on a login prompt must not hang phase 0
# Copilot list lines: the plugin name is "superpowers" itself, not a plugin
# from the superpowers-marketplace or a superpowers-* sibling.
COPILOT_NAME_RE = re.compile(r"(?<![\w@-])superpowers(?![\w-])", re.I)
# claude plugin list ids that are not marketplace installs: no CLI command
# can update or enable them.
NOT_MARKETPLACE = {"inline", "skills-dir", "synced"}


def parse_version(text: Optional[str]) -> Optional[tuple[int, int, int]]:
    """(major, minor, patch) from text, or None when there is none."""
    m = VERSION_RE.search(text or "")
    return (int(m[1]), int(m[2]), int(m[3])) if m else None


def kill_tree(p: subprocess.Popen) -> None:
    """Kill p and everything it started: a CLI shim (npm's claude.cmd, a
    node wrapper) leaves a grandchild holding the output pipes."""
    if os.name == "nt":
        subprocess.run(["taskkill", "/T", "/F", "/PID", str(p.pid)],
                       capture_output=True)
    else:
        try:
            os.killpg(p.pid, signal.SIGKILL)
        except OSError:
            p.kill()


def run(cmd: list[str], timeout: int) -> Optional[tuple[int, str, str]]:
    """(exit code, stdout, stderr) of cmd, or None when it is not on PATH."""
    exe = shutil.which(cmd[0])
    if not exe:
        return None
    try:
        p = subprocess.Popen(
            [exe, *cmd[1:]], stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, text=True, encoding="utf-8",
            errors="replace", start_new_session=os.name != "nt")
    except OSError as e:
        return 126, "", f"could not run {exe}: {e}"
    try:
        out, err = p.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        kill_tree(p)
        p.communicate()
        return 124, "", f"timed out after {timeout}s (is it waiting on a prompt?)"
    return p.returncode, out, err


def report(client: Optional[str], status: str, version: Optional[str] = None,
           enabled: Optional[bool] = None, nxt: Optional[list[str]] = None,
           note: str = "") -> dict:
    return {"client": client,
            "installed": status in {"ok", "outdated", "disabled"},
            "version": version,
            "version_comparable": parse_version(version) is not None,
            "enabled": enabled, "status": status, "next": nxt or [],
            "_note": note}


def grade(client: str, version: str, enabled: bool, plugin_id: str,
          minimum: tuple[int, int, int]) -> dict:
    """Status of one found install."""
    tool = "claude" if client == "claude" else "copilot"
    managed = plugin_id.split("@", 1)[-1] not in NOT_MARKETPLACE
    if not enabled:
        how = (f"run `{tool} plugin enable {plugin_id}`" if managed else
               f"turn it on where {plugin_id} is loaded from")
        return report(client, "disabled", version, False,
                      [f"{tool} plugin enable {plugin_id}"] if managed else [],
                      f"Superpowers is installed but disabled: {how}, then "
                      f"reload.")
    found = parse_version(version)
    if found is None:
        return report(client, "ok", version, True, [],
                      f"Superpowers {version} is installed; cannot compare "
                      f"that version with {'.'.join(map(str, minimum))}.")
    if found < minimum:
        reload = ("/reload-plugins" if client == "claude"
                  else "restart copilot")
        how = (f"offer `{tool} plugin update {plugin_id}`, then {reload}"
               if managed else f"update it where {plugin_id} is loaded from")
        return report(client, "outdated", version, True,
                      [f"{tool} plugin update {plugin_id}"] if managed else [],
                      f"Superpowers {version} is older than "
                      f"{'.'.join(map(str, minimum))}: {how}.")
    return report(client, "ok", version, True, [],
                  f"Superpowers {version} is installed and enabled.")


def from_claude(minimum: tuple[int, int, int],
                timeout: int) -> Optional[dict]:
    got = run(["claude", "plugin", "list", "--json"], timeout)
    if got is None:
        return None
    code, out, err = got
    try:
        plugins = json.loads(out) if code == 0 else None
    except ValueError:
        plugins = None
    if not isinstance(plugins, list):
        detail = (err or out).strip().splitlines()
        return report("claude", "undetectable", note=(
            "`claude plugin list --json` failed"
            + (f": {detail[-1]}" if detail else "")
            + ". Check whether superpowers:brainstorming is in your skill "
              "list, or update Claude Code."))
    mine = [p for p in plugins if isinstance(p, dict)
            and str(p.get("id", "")).split("@")[0] == "superpowers"]
    if not mine:
        cmd = f"claude plugin install superpowers@{OFFICIAL}"
        return report("claude", "missing", nxt=[cmd], note=(
            f"Superpowers is not installed: `{cmd}` (fallback: `claude "
            f"plugin marketplace add obra/{COMMUNITY}`, then `claude plugin "
            f"install superpowers@{COMMUNITY}`), then /reload-plugins."))
    best = sorted(mine, key=lambda p: not p.get("enabled"))[0]
    return grade("claude", str(best.get("version") or "unknown"),
                 bool(best.get("enabled")),
                 str(best["id"]), minimum)


def from_copilot(minimum: tuple[int, int, int],
                 timeout: int) -> Optional[dict]:
    got = run(["copilot", "plugin", "list"], timeout)
    if got is None:
        return None
    code, out, err = got
    if code != 0:
        detail = (err or out).strip().splitlines()
        return report("copilot", "undetectable", note=(
            "`copilot plugin list` failed"
            + (f": {detail[-1]}" if detail else "") + "."))
    lines = [ln for ln in out.splitlines() if COPILOT_NAME_RE.search(ln)]
    if not lines:
        cmds = [f"copilot plugin marketplace add obra/{COMMUNITY}",
                f"copilot plugin install superpowers@{COMMUNITY}"]
        return report("copilot", "missing", nxt=cmds, note=(
            "Superpowers is not installed: run `" + "`, then `".join(cmds)
            + "`, then restart copilot."))
    line = lines[0]
    found = parse_version(line)
    version = ".".join(map(str, found)) if found else "unknown"
    return grade("copilot", version, "disabled" not in line.lower(),
                 f"superpowers@{COMMUNITY}", minimum)


def check(client: str, minimum: tuple[int, int, int],
          timeout: int = TIMEOUT) -> dict:
    """Report for `client` (auto tries claude, then copilot)."""
    order = {"auto": (from_claude, from_copilot), "claude": (from_claude,),
             "copilot": (from_copilot,)}[client]
    for probe in order:
        result = probe(minimum, timeout)
        if result is not None:
            return result
    return report(None, "undetectable", note=(
        "Neither `claude` nor `copilot` is on PATH: check whether "
        "superpowers:brainstorming is in your skill list; listed means "
        "installed, otherwise it is missing."))


def main(argv: Optional[list[str]] = None) -> int:
    ap = argparse.ArgumentParser(
        description="Report whether Superpowers is installed, enabled and "
                    "current. Never installs anything.",
        epilog="Exit 0: ok or outdated. Exit 1: missing, disabled or "
               "undetectable. stdout is JSON; `next` lists the commands to "
               "run after the user says yes.")
    ap.add_argument("--client", choices=("auto", "claude", "copilot"),
                    default="auto")
    ap.add_argument("--min-version", default="7.0.0",
                    help="oldest version that is not reported as outdated")
    ap.add_argument("--timeout", type=int, default=TIMEOUT,
                    help="seconds to wait for the CLI (default: %(default)s)")
    args = ap.parse_args(argv)
    minimum = parse_version(args.min_version)
    if minimum is None:
        ap.error("--min-version must look like 7.0.0")
    result = check(args.client, minimum, args.timeout)
    note = result.pop("_note")
    print(json.dumps(result))
    print(note, file=sys.stderr)
    return 0 if result["status"] in PASSING else 1


if __name__ == "__main__":
    sys.exit(main())
