#!/usr/bin/env python3
"""Check a project against the roj-idea-to-project gates.

Usage: check_ready.py [--phase brief|requirements|architecture|agent-config|all] [ROOT]

ROOT defaults to the current directory. --phase defaults to all, which is
the Definition of Ready. Prints every issue with its fix, then READY or
NOT READY: <n> issues.

Exit codes: 0 ready, 1 issues found (or ROOT is not a directory),
2 bad arguments.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Optional

PHASES = ("brief", "requirements", "architecture", "agent-config")
ITEM_RE = re.compile(r"^\s*(?:[-*]|\d+[.)])\s+\S")
FR_ITEM_RE = re.compile(r"^\s*[-*]\s*(FR-\d+\.\d+)\b(.*)$")
FR_HEAD_RE = re.compile(r"^###\s+(FR-\d+)\b")
EARS_RE = re.compile(r"\b(WHEN|IF|WHILE|WHERE)\b.*\bSHALL\b")
FAILURE_RE = re.compile(r"\bIF\b.*\bTHEN\b.*\bSHALL\b")
VERIFY_RE = re.compile(r"^\s*(?:[-*]\s*)?Verification:\s*(.*)$")
NFR_SEC_RE = re.compile(r"^\s*[-*]\s*NFR-SEC\b")
AREA_RE = re.compile(r"^\s*Area:\s*(.+)$", re.I)
ADR_AREAS = {
    "language": ("language", "stack", "runtime", "framework"),
    "persistence": ("persistence", "database", "storage", "datastore"),
    "auth": ("auth", "authentication", "authorization", "identity"),
    "deploy target": ("deploy", "deployment", "hosting", "infrastructure"),
    "observability": ("observability", "logging", "monitoring", "telemetry"),
}
# Short forms accepted on an ADR's Area: line.
AREA_ALIASES = {"deploy": "deploy target"}


def read(path: Path) -> Optional[list[str]]:
    if not path.is_file():
        return None
    return path.read_text(encoding="utf-8", errors="replace").splitlines()


def missing(rel: str, template: str) -> str:
    return f"{rel} is missing: write it from the skill's assets/{template}"


def section(lines: list[str], heading: str) -> list[str]:
    """Lines under the first `## <heading>...` up to the next `## `."""
    out, inside = [], False
    for ln in lines:
        if ln.startswith("## "):
            if inside:
                break
            inside = ln[3:].strip().lower().startswith(heading.lower())
            continue
        if inside:
            out.append(ln)
    return out


def check_brief(root: Path) -> list[str]:
    lines = read(root / "docs" / "brief.md")
    if lines is None:
        return [missing("docs/brief.md", "brief-template.md")]
    n = sum(1 for ln in section(lines, "Non-goals") if ITEM_RE.match(ln))
    if n >= 5:
        return []
    return [f"docs/brief.md has {n} non-goals: add at least {5 - n} more "
            f"under ## Non-goals"]


def check_requirements(root: Path) -> list[str]:
    lines = read(root / "docs" / "requirements.md")
    if lines is None:
        return [missing("docs/requirements.md", "requirements-template.md")]
    found: list[str] = []
    blocks: dict[str, Optional[str]] = {}
    failure_path: set[str] = set()
    current: Optional[str] = None
    for ln in lines:
        head = FR_HEAD_RE.match(ln)
        if head:
            current = head[1]
            blocks[current] = None
            continue
        if ln.startswith("## ") or ln.startswith("### "):
            current = None
            continue
        # Only requirement bullets inside a ### FR-<n> block; the same IDs
        # appear in the traceability section as plain references.
        item = FR_ITEM_RE.match(ln) if current else None
        if item and not EARS_RE.search(item[2]):
            found.append(f"{item[1]} is not in EARS form: use "
                         "WHEN/IF/WHILE/WHERE ... THE SYSTEM SHALL ...")
        if item and FAILURE_RE.search(item[2]):
            failure_path.add(current)
        verify = VERIFY_RE.match(ln)
        if verify and current and blocks[current] is None:
            blocks[current] = verify[1].strip()
    if not blocks:
        found.append("docs/requirements.md has no ### FR-<n> blocks: add one "
                     "per feature from the template")
    for fr, value in blocks.items():
        if fr not in failure_path:
            found.append(f'{fr} has no IF ... THEN failure-path bullet: add '
                         f'"- {fr}.<m> IF <unwanted condition> THEN THE SYSTEM '
                         f'SHALL <response>."')
        if not value:
            found.append(f'{fr} has no Verification line: add '
                         f'"Verification: <test name or command>"')
        elif value.startswith("<"):
            found.append(f"{fr} Verification is still the template "
                         "placeholder: name the test or command")
    if not any(NFR_SEC_RE.match(ln) for ln in lines):
        found.append('docs/requirements.md has no NFR-SEC line: add "- NFR-SEC: '
                     'authn ...; authz ...; input validated at ...; secrets '
                     'from ..."')
    return found


def check_architecture(root: Path) -> list[str]:
    found = []
    if read(root / "docs" / "architecture.md") is None:
        found.append(missing("docs/architecture.md",
                             "architecture-template.md"))
    texts, declared = [], set()
    for adr in sorted((root / "docs" / "adr").glob("*.md")):
        lines = read(adr) or []
        title = next((ln for ln in lines if ln.startswith("# ")), "")
        texts.append(f"{adr.stem} {title}".lower().replace("-", " "))
        for ln in lines:
            area = AREA_RE.match(ln)
            if area:
                for a in area[1].split(","):
                    a = a.strip().lower()
                    declared.add(AREA_ALIASES.get(a, a))
    for area, words in ADR_AREAS.items():
        if area in declared or any(re.search(rf"\b{w}\b", t)
                                   for t in texts for w in words):
            continue
        slug = area.replace(" ", "-")
        found.append(f"no ADR covers {area}: add docs/adr/NNNN-{slug}.md, or "
                     f'add "Area: {area}" to the ADR that decides it (a file '
                     f"name or title mentioning one of {', '.join(words)} "
                     f"also counts)")
    return found


def check_agent_config(root: Path) -> list[str]:
    lines = read(root / "CLAUDE.md")
    if lines is None:
        return [missing("CLAUDE.md", "claude-md-template.md")]
    if len(lines) >= 100:
        return [f"CLAUDE.md has {len(lines)} lines: cut it to under 100 "
                "(turn must-never-happen rules into hooks or tests)"]
    return []


CHECKS = {"brief": check_brief, "requirements": check_requirements,
          "architecture": check_architecture,
          "agent-config": check_agent_config}


def issues(root: Path, phase: str) -> list[str]:
    """Every issue for `phase` ("all" runs every phase in order)."""
    phases = PHASES if phase == "all" else (phase,)
    return [i for p in phases for i in CHECKS[p](root)]


def main(argv: Optional[list[str]] = None) -> int:
    ap = argparse.ArgumentParser(
        description="Check a project against the roj-idea-to-project gates.",
        epilog="Exit 0: READY. Exit 1: issues found, each printed with its "
               "fix. Run, fix, re-run until it passes.")
    ap.add_argument("--phase", choices=(*PHASES, "all"), default="all")
    ap.add_argument("root", nargs="?", default=".",
                    help="project folder (default: current directory)")
    args = ap.parse_args(argv)
    root = Path(args.root)
    if not root.is_dir():
        print(f"{root} is not a directory: pass the project folder as ROOT")
        return 1
    found = issues(root, args.phase)
    for line in found:
        print(line)
    print(f"NOT READY: {len(found)} issues" if found else "READY")
    return 1 if found else 0


if __name__ == "__main__":
    sys.exit(main())
