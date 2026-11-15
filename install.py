#!/usr/bin/env python3
"""Install Roj's AI setup for Claude Code and GitHub Copilot.

Usage:
  python3 install.py                     # both agents
  python3 install.py --target claude     # or copilot
  python3 install.py --dry-run           # what would happen
  python3 install.py --status            # what is installed, leftovers
  python3 install.py --update            # skills with newer upstream versions
  python3 install.py --upgrade           # newer graphify, then refresh
  python3 install.py --skills-only       # skip graphify (e.g. PyPI blocked)

Python >= 3.8, standard library only. On Windows run it from Git Bash as
`python install.py`. On WSL run it inside WSL: it also writes the JetBrains
instructions into the Windows home (--windows-home PATH names it).

This script installs no skills and never runs cali. Skills are installed by
cali (https://github.com/rojcarranza/cali), which reads this repo's cali.yaml
from GitHub: `cali setup github:rojcarranza/agent-skills` once, then
`cali load <skill>`. Here: personal instructions, the start-up note, the
JetBrains block, removal of the retired GitHub MCP entry (RETIRED_MCP_SERVERS)
and graphify (EXTERNALS), whose own CLI installs its skill.

Any single skill also installs without this script, in any agent the
`skills` CLI supports: npx skills add rojcarranza/agent-skills -s <name>.
"""
import argparse
import contextlib
import json
import os
import re
import shutil
import subprocess
import sys
import sysconfig
import tempfile
import time
from pathlib import Path
from typing import NamedTuple

REPO_ROOT = Path(__file__).resolve().parent
SKILLS_SRC = REPO_ROOT / "skills"

BOTH = ("copilot", "claude")


# External skills: shipped and installed by their own CLI, never vendored
# here. We bootstrap the CLI, then delegate each target's install to it, so an
# external is always the upstream version — nothing to keep in sync.
EXTERNALS = [
    {
        "name": "graphify",
        "package": "graphifyy",
        "cli": "graphify",
        "targets": BOTH,
        "default": True,
        "doc": "knowledge graph over code/docs/PDFs — /graphify",
        # Per target: argv for the CLI. Claude's own install auto-picks the
        # PowerShell skill variant on Windows, so no --platform is needed.
        #
        # Copilot gets `vscode install`, not `copilot install`: both write the
        # same ~/.copilot/skills/graphify/SKILL.md, and only the vscode body
        # drives extraction by hand. The copilot body calls a parallel Agent
        # tool that neither VS Code Copilot Chat nor JetBrains Copilot has.
        # That personal scope is what serves both IDEs.
        "install": {"claude": ["install"], "copilot": ["vscode", "install"]},
        "uninstall": {"claude": ["claude", "uninstall"],
                      "copilot": ["vscode", "uninstall"]},
        # `vscode install` also writes <cwd>/.github/copilot-instructions.md,
        # so the CLI runs in a scratch cwd (install_external_for_target).
        "version_file": ".graphify_version",
    },
]

# Skills a custom skill calls at runtime. Installing the key installs every
# value alongside it, to the same targets, in every install mode. Values may
# be community skills, externals or other custom skills; chains are followed.
REQUIRES = {
    # context-map and write-pr-description were dropped: the first is off by
    # choice in ~/.claude/settings.json skillOverrides, the second was never
    # installed. The skill falls back inline for both, so declaring them only
    # pulled their descriptions into every session for nothing.
    "roj-explain-my-branch": ("code-tour",),
    # Custom skills never require each other: shared files are copied into
    # each skill by tools/sync_shared.py, so every skill also installs alone
    # through `npx skills add`.
}


# cali.yaml: the list cali reads. Read here only for names and
# targets — tests — with a line parser for the
# shapes this repo's cali.yaml uses, so no YAML dependency. A commented skill
# (`  # name:` with its `  #   key: value` lines) is an optional one.
# shortcut: inline `[a, b]` target lists only; parse YAML properly if
# cali.yaml ever needs block lists or anchors.
MANIFEST_PATH = REPO_ROOT / "cali.yaml"
_SKILL_LINE_RE = re.compile(r"^  (#\s*)?([\w-]+):\s*(.*)$")
_FIELD_LINE_RE = re.compile(r"^  (#)?\s+([\w-]+):\s*(.*)$")


def _strip_comment(value):
    return re.sub(r"(^|\s+)#.*$", "", value).strip()


def _unquote(value):
    """A YAML scalar in double quotes (JSON escapes) or single quotes."""
    if len(value) >= 2 and value[0] == value[-1] == '"':
        try:
            return json.loads(value)
        except ValueError:
            return value[1:-1]
    if len(value) >= 2 and value[0] == value[-1] == "'":
        return value[1:-1]
    return value


def parse_manifest(text: str) -> list:
    """cali.yaml text -> [{'name', 'source', 'ref', 'targets', 'load', 'active'}].
    ref is the `ref:` field, else the @ref of the source; targets is a tuple,
    or None for the manifest's default targets."""
    skills, current, in_skills = [], None, False
    for raw in text.splitlines():
        line = raw.rstrip()
        if not line.strip():
            continue
        if not line.startswith((" ", "#")):
            in_skills = line.split(":", 1)[0] == "skills"
            current = None
            continue
        if not in_skills:
            continue
        entry = _SKILL_LINE_RE.match(line)
        if entry and not _strip_comment(entry.group(3)):
            current = {"name": entry.group(2), "active": not entry.group(1),
                       "source": "", "ref": None, "targets": None,
                       "load": "always"}
            skills.append(current)
            continue
        field = _FIELD_LINE_RE.match(line)
        if (field and current is not None
                and bool(field.group(1)) != current["active"]):
            key, value = field.group(2), _unquote(_strip_comment(field.group(3)))
            if key == "targets":
                current["targets"] = tuple(
                    t.strip() for t in value.strip("[]").split(",") if t.strip())
            elif key in ("source", "ref", "load"):
                current[key] = value
    for dep in skills:
        if dep["ref"] is None and "@" in dep["source"].rsplit("//", 1)[-1]:
            dep["ref"] = dep["source"].rsplit("@", 1)[1]
    return skills


def manifest_deps(path=None):
    text = Path(path or MANIFEST_PATH).read_text(encoding="utf-8")
    return parse_manifest(text)


def manifest_skill_names(active_only=True):
    """Skill folder names cali.yaml installs (or lists, with active_only off)."""
    return {d["name"] for d in manifest_deps()
            if d["active"] or not active_only}


def is_wsl():
    if sys.platform != "linux":
        return False
    try:
        return "microsoft" in Path("/proc/version").read_text(
            encoding="utf-8").lower()
    except OSError:
        return False


_WINDOWS_PATH_RE = re.compile(r"^[A-Za-z]:[\\/]")


def windows_userprofile():
    """%USERPROFILE% as Windows spells it (C:\\Users\\name) read through
    cmd.exe interop, or None when interop is off or cmd.exe is missing."""
    for exe in (shutil.which("cmd.exe"), "/mnt/c/Windows/System32/cmd.exe"):
        if not exe or not os.path.isfile(exe):
            continue
        try:
            # chcp 65001 makes cmd print UTF-8, so a non-ASCII user name
            # survives; cwd on /mnt/c spares cmd its UNC-path complaint.
            run = subprocess.run(
                [exe, "/c", "chcp 65001 >nul & echo %USERPROFILE%"],
                stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, timeout=30,
                cwd="/mnt/c" if os.path.isdir("/mnt/c") else None)
        except (OSError, subprocess.SubprocessError):
            continue
        lines = [ln.strip() for ln in
                 run.stdout.decode("utf-8", "replace").splitlines()
                 if ln.strip()]
        if run.returncode == 0 and lines and "%USERPROFILE%" not in lines[-1]:
            return lines[-1]
    return None


def wsl_path(windows_path):
    """C:\\Users\\name -> /mnt/c/Users/name through wslpath, or None."""
    exe = shutil.which("wslpath")
    if not exe:
        return None
    try:
        run = subprocess.run([exe, "-u", windows_path], stdout=subprocess.PIPE,
                             stderr=subprocess.DEVNULL, text=True, timeout=30)
    except (OSError, subprocess.SubprocessError):
        return None
    out = run.stdout.strip()
    return Path(out) if run.returncode == 0 and out else None


def resolve_windows_home(override=None):
    """(Path, None) for the Windows home a WSL run also delivers Copilot
    skills to, else (None, why). override is --windows-home: a /mnt/... path
    or a C:\\... one. Without it the home is %USERPROFILE%, asked of Windows."""
    raw = override or windows_userprofile()
    if not raw:
        return None, ("cmd.exe interop is not available, so %USERPROFILE% "
                      "cannot be read")
    if _WINDOWS_PATH_RE.match(raw):
        home = wsl_path(raw)
        if home is None:
            return None, f"wslpath could not convert {raw}"
    else:
        home = Path(raw)
    if not home.is_dir():
        return None, f"{home} is not a directory"
    if home.resolve() == Path.home().resolve():
        return None, f"{home} is the Linux home, not a Windows one"
    return home, None


INSTRUCTIONS_SRC = REPO_ROOT / "instructions" / "personal.instructions.md"
# Where earlier commits kept the file (APM's folder), so their versions still
# count as ours to update.
INSTRUCTIONS_OLD_RELS = (".apm/instructions/personal.instructions.md",)
# The Superpowers start-up note and tool map. Copilot Chat has no plugin hook,
# so this file is the whole integration: without it the skills stay inert.
STARTUP_NOTE_SRC = REPO_ROOT / "instructions" / "superpowers.instructions.md"
# JetBrains reads one global instruction file and not ~/.copilot/instructions.
# install.py owns only the part between these markers; text outside is kept.
JETBRAINS_BEGIN = "<!-- BEGIN agent-skills: written by install.py, edits inside are replaced -->"
JETBRAINS_END = "<!-- END agent-skills -->"


def instruction_path(target):
    """Where the personal instructions go, or None for a target that gets
    none. Claude reads the global ~/.claude/CLAUDE.md instead."""
    if target == "claude":
        return None
    return Path.home() / ".copilot" / "instructions" / INSTRUCTIONS_SRC.name


def claude_rules_path():
    """Where earlier versions deployed the instructions for Claude."""
    return Path.home() / ".claude" / "rules" / "personal.md"


def _instruction_body(text):
    """text without its front matter: the part every rendering shared."""
    if text.startswith("---\n"):
        end = text.find("\n---\n", 4)
        if end >= 0:
            return text[end + 5:]
    return text


def inspect_claude_rules():
    """The personal.md rule earlier versions deployed for Claude. A copy
    whose body this repo shipped is a leftover to move to backup_dir()
    (Claude got it with `applyTo:` turned into `paths:`); an edited copy or a
    link is kept with a warning; no file is nothing to do."""
    path = claude_rules_path()
    if path.is_symlink():
        return Item("claude", path.name, "foreign-link", note=(
            f"{path} is a link - left in place; Claude now gets no "
            "personal instructions from install.py"))
    if not path.is_file():
        return Item("claude", path.name, "current")
    current = path.read_text(encoding="utf-8", errors="replace")
    if _instruction_body(current) not in {
            _instruction_body(t) for t in shipped_instructions()}:
        return Item("claude", path.name, "edited", note=(
            f"{path} differs from every version install.py shipped - left "
            "in place; Claude now gets no personal instructions from "
            "install.py"))

    def apply(dry_run):
        dest = _move_aside(path, "claude", dry_run)
        return f"moved to {dest} (Claude gets none)"
    return Item("claude", path.name, "leftover", apply)


def retire_claude_rules(dry_run):
    return run_items([inspect_claude_rules()], dry_run)


def shipped_instructions(src=None):
    """Every version of INSTRUCTIONS_SRC this clone has shipped: the file
    on disk plus each committed one (none when git or history is missing).
    A deployed file equal to one of them is ours to update."""
    src = src or INSTRUCTIONS_SRC
    texts = {src.read_text(encoding="utf-8")}
    rels = (src.relative_to(REPO_ROOT).as_posix(),
            *(INSTRUCTIONS_OLD_RELS if src == INSTRUCTIONS_SRC else ()))
    try:
        for rel in rels:
            log = subprocess.run(["git", "log", "--format=%H", "--", rel],
                                 cwd=str(REPO_ROOT), capture_output=True,
                                 text=True, timeout=60)
            for sha in log.stdout.split() if log.returncode == 0 else ():
                show = subprocess.run(["git", "show", f"{sha}:{rel}"],
                                      cwd=str(REPO_ROOT), capture_output=True,
                                      timeout=60)
                if show.returncode == 0:
                    texts.add(show.stdout.decode("utf-8", "replace")
                              .replace("\r\n", "\n"))
    except (OSError, subprocess.SubprocessError):
        pass
    return texts


def _links_into_dotfiles(link):
    """True for a link to <dotfiles>/copilot/<name>, the layout the dotfiles
    installer linked from: a copilot/ folder next to an install.py."""
    try:
        target = link.resolve()
    except (OSError, RuntimeError):
        return False
    return (target.name == link.name and target.parent.name == "copilot"
            and (target.parent.parent / "install.py").is_file())


def _write_text(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)


def startup_note_path(target):
    """Where the Superpowers start-up note goes (Copilot only), beside the
    personal instructions that VS Code reads."""
    if target == "claude":
        return None
    return Path.home() / ".copilot" / "instructions" / STARTUP_NOTE_SRC.name


def jetbrains_instruction_path(home=None, windows=None):
    """JetBrains' global Copilot instruction file (Microsoft for Java, July
    2025): %LOCALAPPDATA%\\github-copilot\\intellij\\ on Windows,
    ~/.config/github-copilot/intellij/ elsewhere. home: a Windows home, for
    the WSL leg."""
    name = "global-copilot-instructions.md"
    windows = IS_WINDOWS if windows is None else windows
    if home is not None:
        return home / "AppData" / "Local" / "github-copilot" / "intellij" / name
    if windows:
        base = os.environ.get("LOCALAPPDATA")
        base = Path(base) if base else Path.home() / "AppData" / "Local"
        return base / "github-copilot" / "intellij" / name
    return Path.home() / ".config" / "github-copilot" / "intellij" / name


def jetbrains_block():
    """The text install.py owns in JetBrains' file: the start-up note, then
    the personal instructions, without their front matter."""
    parts = [_instruction_body(p.read_text(encoding="utf-8")).strip()
             for p in (STARTUP_NOTE_SRC, INSTRUCTIONS_SRC)]
    return "\n".join([JETBRAINS_BEGIN, "\n\n".join(parts), JETBRAINS_END]) + "\n"


def inspect_jetbrains_instructions(path=None, label="copilot"):
    """The JetBrains global file: install.py owns only the block between the
    markers. A file without them gets the block appended; text outside the
    markers is never touched. A link is left alone."""
    dest = path or jetbrains_instruction_path()
    block = jetbrains_block()
    if dest.is_symlink():
        return Item(label, dest.name, "foreign-link", note=(
            f"{dest} is a link - left in place; JetBrains gets no "
            "start-up note from install.py"))
    current = (dest.read_text(encoding="utf-8", errors="replace")
               if dest.is_file() else None)
    if current is None:
        new, state, text = block, "missing", None
    else:
        current = current.replace("\r\n", "\n")
        begin = current.find(JETBRAINS_BEGIN)
        end = current.find(JETBRAINS_END, begin + 1) if begin >= 0 else -1
        if begin >= 0 and end >= 0:
            end += len(JETBRAINS_END)
            if current[end:end + 1] == "\n":
                end += 1
            new = current[:begin] + block + current[end:]
            text = None
        else:
            sep = "" if not current.strip() else (
                "\n" if current.endswith("\n") else "\n\n")
            new = current + sep + ("\n" if sep else "") + block
            text = "added block"
        state = "current" if new == current else "older"

    def apply(dry_run):
        if not dry_run:
            _write_text(dest, new)
        return text
    return Item(label, dest.name, state, apply)


def install_jetbrains_instructions(dry_run, path=None, label="copilot"):
    return run_items([inspect_jetbrains_instructions(path, label)], dry_run)


def inspect_instructions(target):
    """Items for the personal instructions, the start-up note and the
    JetBrains block (Copilot only; Claude reads ~/.claude/CLAUDE.md)."""
    if instruction_path(target) is None:
        return []
    return [inspect_instruction(target, INSTRUCTIONS_SRC,
                                instruction_path(target)),
            inspect_instruction(target, STARTUP_NOTE_SRC,
                                startup_note_path(target)),
            inspect_jetbrains_instructions()]


def install_instructions(target, dry_run):
    """Deploy the instruction files for target, as inspect_instructions
    names their states: each is replaced when missing, a version this repo
    shipped, or the dotfiles repo's link; an edited copy or a link to
    anything else is kept with a warning."""
    return run_items(inspect_instructions(target), dry_run)


def inspect_instruction(target, src, dest):
    new = src.read_text(encoding="utf-8")
    note = None
    if dest.is_symlink():
        if _links_into_dotfiles(dest):
            state = "dotfiles-link"
        else:
            state = "foreign-link"
            note = (f"{dest} links somewhere other than the dotfiles repo — "
                    f"left in place; remove it so install.py can deploy "
                    f"{dest.name}")
    elif dest.is_file():
        current = dest.read_text(encoding="utf-8", errors="replace")
        if current == new:
            state = "current"
        elif current in shipped_instructions(src):
            state = "older"
        else:
            state = "edited"
            note = (f"{dest} differs from {src} — left in place; "
                    "merge your edits into the repo copy, delete it, and "
                    "re-run")
    else:
        state = "missing"

    def apply(dry_run):
        if not dry_run:
            if dest.is_symlink():
                dest.unlink()
            _write_text(dest, new)
    return Item(target, dest.name, state, apply, note)


# MCP servers install.py once registered and now removes, per target, from
# Claude Code ~/.claude.json and Copilot CLI ~/.copilot/mcp-config.json, both
# under "mcpServers". gh-axi replaces the GitHub server, so install.py no
# longer adds it. An entry is removed only while it still equals what this
# script wrote; a hand-tuned one stays. Other servers (Neon, Obsidian) are
# never touched.
GITHUB_MCP_URL = "https://api.githubcopilot.com/mcp/"
RETIRED_MCP_SERVERS = {
    "github-mcp-server": {
        "claude": {"type": "http", "url": GITHUB_MCP_URL},
        "copilot": {"type": "http", "url": GITHUB_MCP_URL, "tools": ["*"]},
    },
}


def mcp_config_path(target):
    if target == "claude":
        return Path.home() / ".claude.json"
    return Path.home() / ".copilot" / "mcp-config.json"


def inspect_mcp_servers(target):
    """One item per RETIRED_MCP_SERVERS entry still present for target. A
    missing file or entry has nothing to do; a file that is not a JSON
    object is never rewritten."""
    path = mcp_config_path(target)
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return [Item(target, "mcp", "unreadable", note=(
            f"{path} is not valid JSON ({exc}) — left alone; remove the "
            "retired MCP servers by hand"))]
    servers = data.get("mcpServers", {}) if isinstance(data, dict) else None
    if not isinstance(servers, dict):
        return [Item(target, "mcp", "unreadable", note=(
            f"{path} has no mcpServers object — left alone; remove the "
            "retired MCP servers by hand"))]
    items = []
    for name, configs in RETIRED_MCP_SERVERS.items():
        if name not in servers or target not in configs:
            continue
        if servers[name] != configs[target]:
            items.append(Item(target, f"mcp:{name}", "edited", note=(
                f"{path}: {name} differs from what install.py wrote — kept; "
                "remove it by hand if you no longer want it")))
            continue

        def apply(dry_run, name=name):
            if not dry_run:
                _remove_mcp_server(path, name)
        items.append(Item(target, f"mcp:{name}", "stale", apply))
    return items


def _remove_mcp_server(path, name):
    data = json.loads(path.read_text(encoding="utf-8"))
    data["mcpServers"].pop(name, None)
    # Same directory, then rename: a crash never leaves a half-written file.
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=path.name + ".")
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as fh:
            json.dump(data, fh, indent=2)
            fh.write("\n")
        shutil.copymode(str(path), tmp)
        os.replace(tmp, str(path))
    except OSError:
        with contextlib.suppress(OSError):
            os.unlink(tmp)
        raise


def retire_mcp_servers(target, dry_run):
    """Remove each RETIRED_MCP_SERVERS entry install.py wrote to target's
    config, keeping every other key."""
    return run_items(inspect_mcp_servers(target), dry_run)


def externals():
    """{external_name: ext}."""
    return {ext["name"]: ext for ext in EXTERNALS}


def all_external_names():
    return set(externals())


def default_external_names():
    return {e["name"] for e in EXTERNALS if e["default"]}


def log(msg):
    print(f"[skills] {msg}")


def ok(msg):
    print(f"[  ok  ] {msg}")


def warn(msg):
    print(f"[ warn ] {msg}", file=sys.stderr)


# ---- item states -------------------------------------------------------
# Every file or setting install.py manages is an Item. One inspect step per
# kind reads the disk and names the Item's state; ACTIONS says what each state
# means. The real run, --dry-run and --status all read the same states and the
# same table, so they cannot disagree about the disk, and no code compares
# status text.
OK, ATTENTION, FAILED = 0, 1, 3     # the exit code is the worst level


class Action(NamedTuple):
    do: str          # "write": the run changes the item; "keep": it is left
    #                  alone; "none": nothing to do
    done: str        # the row text after the run (items may override it)
    run_level: int   # level once the run has applied this state
    status_level: int  # level of the state as --status finds it
    status_msg: str  # --status line; None: the item's own note


ACTIONS = {
    # nothing to do
    "current": Action("none", None, OK, OK, None),
    "not-for-target": Action("none", "skipped", OK, OK, None),
    # the run writes it
    "missing": Action("write", "installed", OK, ATTENTION,
                      "{name} is not deployed or out of date — re-run "
                      "install.py"),
    "stale": Action("write", "removed", OK, ATTENTION,
                    "{name} is retired — re-run install.py to remove"),
    "older": Action("write", "updated", OK, ATTENTION,
                    "{name} is not deployed or out of date — re-run "
                    "install.py"),
    "half": Action("write", "installed", OK, ATTENTION,
                   "{name} is half installed — re-run install.py"),
    "dotfiles-link": Action("write", "replaced dotfiles link", OK, ATTENTION,
                            "{name} left by an older install — re-run "
                            "install.py to remove"),
    "leftover": Action("write", "moved aside", OK, ATTENTION,
                       "{name} left by an older install — re-run install.py "
                       "to move it aside"),
    # the run leaves it, and the user has to look
    "edited": Action("keep", "kept (edited by you)", ATTENTION, ATTENTION,
                     None),
    "foreign-link": Action("keep", "kept (a link)", ATTENTION, ATTENTION,
                           None),
    "unreadable": Action("keep", "kept (unreadable)", ATTENTION, ATTENTION,
                         None),
    "unavailable": Action("keep", "skipped (CLI unavailable)", ATTENTION,
                          ATTENTION, None),
    # the run tried and it did not work
    "failed": Action("none", "failed", FAILED, FAILED, None),
}


class Row(tuple):
    """One line of the summary: (target, name, status text) that also
    remembers the state it ended in, which decides the exit code."""

    def __new__(cls, target, name, status, state="current"):
        row = super().__new__(cls, (target, name, status))
        row.state = state
        return row

    @property
    def level(self):
        return ACTIONS[self.state].run_level


class Item:
    """One thing install.py manages. apply(dry_run) changes it and returns
    None, a status text, or (state, text) when it ended in another state;
    it must write nothing on a dry run."""

    def __init__(self, target, name, state, apply=None, note=None,
                 done=None, current=None):
        self.target, self.name, self.state = target, name, state
        self.apply, self.note = apply, note
        self.done, self.current = done, current


def run_items(items, dry_run):
    """Act on each item as its state says; return the summary rows."""
    rows = []
    for item in items:
        action = ACTIONS[item.state]
        state, text = item.state, None
        if action.do == "write":
            out = item.apply(dry_run)
            if isinstance(out, tuple):
                state, text = out
            else:
                text = out
            text = text or item.done or action.done
        elif action.do == "keep":
            if item.note:
                warn(item.note)
            text = action.done
        elif item.state == "current":
            text = item.current
        else:
            text = item.done or action.done
        if text:
            rows.append(Row(item.target, item.name, text, state))
    return rows


def worst_level(rows):
    """The exit code: 0 clean, 1 something kept or left for you, 3 failed."""
    return max((r.level for r in rows), default=OK)


def status_warnings(items):
    """(level, line) for every item --status cannot call clean."""
    out = []
    for item in items:
        action = ACTIONS[item.state]
        if action.status_level == OK:
            continue
        msg = (action.status_msg.format(name=item.name)
               if action.status_msg else item.note)
        out.append((action.status_level, f"{item.target}: {msg}"))
    return out


def target_root(target):
    return Path.home() / (".copilot" if target == "copilot"
                          else ".claude") / "skills"


def custom_skill_names():
    """Names of the skills in skills/ — also the directory names they take
    in every target root."""
    if not SKILLS_SRC.is_dir():
        return set()
    return {p.name for p in SKILLS_SRC.iterdir() if p.is_dir()}


# Taken once, so every copy one run moves lands in the same folder.
_RUN_STAMP = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())


def backup_dir(home=None):
    """Where install.py keeps what it moved aside, one folder per run, in
    the Linux home or, for the WSL Windows leg, in `home`."""
    return (home or Path.home()) / ".agent-skills-backups" / _RUN_STAMP


def _move_aside(path, target, dry_run, home=None):
    """Move path to backup_dir()/<target>/<name> (a free name) and return
    where it went, or would go on a dry run."""
    dest = backup_dir(home) / target / path.name
    n = 1
    while dest.exists():
        n += 1
        dest = dest.with_name(f"{path.name}-{n}")
    if not dry_run:
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(path), str(dest))
    return dest


def user_script_dirs():
    """Directories a user-scope install drops executables into. uv and pipx
    use ~/.local/bin; `pip install --user` uses the interpreter's user scheme
    (on Windows that is %APPDATA%\\Python\\PythonXY\\Scripts). Any of them may
    be missing from this process's PATH even when a new shell would find it."""
    dirs = [Path.home() / ".local" / "bin"]
    try:
        scheme = (sysconfig.get_preferred_scheme("user")
                  if hasattr(sysconfig, "get_preferred_scheme")
                  else ("nt_user" if os.name == "nt" else "posix_user"))
        dirs.append(Path(sysconfig.get_path("scripts", scheme)))
    except (KeyError, ValueError, AttributeError):
        pass
    return tuple(dict.fromkeys(dirs))


def pip_install_cmd():
    """`pip install` for this interpreter. --user is invalid inside a venv,
    where site-packages is already writable and private."""
    cmd = [sys.executable, "-m", "pip", "install"]
    if sys.prefix == getattr(sys, "base_prefix", sys.prefix):
        cmd.append("--user")
    return cmd


USER_BIN_DIRS = user_script_dirs()
CLI_SUFFIXES = ("", ".exe", ".cmd", ".bat") if os.name == "nt" else ("",)


def pip_externally_managed():
    """True when `pip install --user` would be refused (PEP 668): Debian,
    Ubuntu 24.04, Homebrew and Arch ship an EXTERNALLY-MANAGED marker next to
    the stdlib. A venv is never managed, so pip stays usable there."""
    if sys.prefix != getattr(sys, "base_prefix", sys.prefix):
        return False
    try:
        return (Path(sysconfig.get_path("stdlib")) / "EXTERNALLY-MANAGED").is_file()
    except (KeyError, ValueError, OSError):
        return False


# Best first. pip is the last resort - it is always there (we are running
# under it) but installs into the user site rather than an isolated venv, and
# the loops skip it when pip_externally_managed().
BOOTSTRAP_CMDS = (["uv", "tool", "install"], ["pipx", "install"],
                  pip_install_cmd())
UPGRADE_CMDS = (["uv", "tool", "upgrade"], ["pipx", "upgrade"],
                pip_install_cmd() + ["--upgrade"])


def find_cli(name):
    """Absolute path to a CLI, or None."""
    found = shutil.which(name)
    if found:
        return found
    for d in USER_BIN_DIRS:
        for suffix in CLI_SUFFIXES:
            candidate = d / (name + suffix)
            if candidate.is_file():
                return str(candidate)
    return None


def cli_path_hint(ext):
    """Actionable line when an external's CLI exists but the shell cannot find
    it by name, else None. The skill invokes it bare, so an off-PATH install
    is installed-but-inert — the one failure that otherwise looks like
    success."""
    found = find_cli(ext["cli"])
    if not found or shutil.which(ext["cli"]):
        return None
    directory = Path(found).parent
    # Git Bash needs the Windows scripts dir translated before it can be
    # prepended to a POSIX PATH.
    where = (f'$(cygpath -u "{directory}")' if os.name == "nt"
             else str(directory))
    return (f"{ext['cli']} is installed at {found}, but {directory} is not on "
            f"PATH — the skill calls '{ext['cli']}' by name. Add it with: "
            f"""echo 'export PATH="$PATH:{where}"' >> ~/.bashrc""")


def cli_version(exe):
    """`<cli> --version` reduced to the bare version, or None."""
    if not exe:
        return None
    try:
        out = subprocess.run([exe, "--version"], capture_output=True,
                             text=True, timeout=60)
    except (OSError, subprocess.SubprocessError):
        return None
    first = (out.stdout or out.stderr or "").strip().splitlines()
    return first[0].split()[-1] if first and first[0].split() else None


def upgrade_cli(ext, exe, dry_run):
    """Upgrade an already-installed external in place. Returns a status
    string for the summary.

    Which manager installed the package is not recorded anywhere, so the
    managers are tried in install order: the ones that do not own this
    package fail immediately and cost nothing."""
    if dry_run:
        return f"dry-run: would upgrade {ext['package']}"
    before = cli_version(exe)
    for cmd in UPGRADE_CMDS:
        via = "pip" if cmd[0] == sys.executable else cmd[0]
        if via != "pip" and not shutil.which(cmd[0]):
            continue
        if via == "pip" and pip_externally_managed():
            continue
        log(f"Upgrading {ext['package']} with {via}...")
        try:
            subprocess.run([*cmd, ext["package"]], check=True)
        except (subprocess.CalledProcessError, OSError):
            continue
        after = cli_version(find_cli(ext["cli"]) or exe)
        if before and after and before != after:
            return f"upgraded ({before} -> {after})"
        return f"already latest ({after or before or 'version unknown'})"
    warn(f"No uv/pipx/pip could upgrade {ext['package']}")
    return "upgrade unavailable"


def bootstrap_cli(ext, dry_run):
    """Ensure an external's CLI is present. Returns its path, or None when it
    is missing and could not be installed — callers skip the external then
    rather than failing the whole run."""
    found = find_cli(ext["cli"])
    if found or dry_run:
        return found
    for cmd in BOOTSTRAP_CMDS:
        via = "pip" if cmd[0] == sys.executable else cmd[0]
        if via != "pip" and not shutil.which(cmd[0]):
            continue
        if via == "pip" and pip_externally_managed():
            continue
        log(f"Installing {ext['package']} with {via}...")
        try:
            subprocess.run([*cmd, ext["package"]], check=True)
        except (subprocess.CalledProcessError, OSError):
            warn(f"{via} could not install {ext['package']}")
            continue
        found = find_cli(ext["cli"])
        if found:
            ok(f"{ext['cli']} ready ({found})")
            return found
        warn(f"{via} reported success but {ext['cli']} is not on PATH")
    if (pip_externally_managed() and shutil.which("apt")
            and not shutil.which("pipx")):
        warn(f"No {ext['cli']} CLI, and pip is refused for this system "
             f"Python (PEP 668) - skipping. Run 'sudo apt install pipx' "
             f"and 'pipx ensurepath', open a new shell, then re-run "
             f"'python3 install.py'.")
        return None
    pip_hint = ("" if pip_externally_managed() else
                f", or 'python -m pip install --user {ext['package']}'")
    warn(f"No {ext['cli']} CLI and no uv/pipx/pip could install it - skipping. "
         f"Install it yourself with 'uv tool install {ext['package']}' "
         f"(or 'pipx install {ext['package']}'{pip_hint}) and re-run.")
    return None


def run_cli(argv, cwd):
    try:
        subprocess.run(argv, cwd=str(cwd), check=True)
        return True
    except (subprocess.CalledProcessError, OSError) as exc:
        warn(f"{' '.join(str(a) for a in argv)} failed: {exc}")
        return False


def external_version(dest, ext):
    """Version the external's CLI stamped into an installed skill dir."""
    try:
        return (dest / ext["version_file"]).read_text(
            encoding="utf-8").strip() or None
    except (OSError, KeyError):
        return None


IS_WINDOWS = os.name == "nt"
# A CLI's own installer can lose a rename race on Windows: VS Code/JetBrains
# watching ~/.copilot/skills, or antivirus scanning freshly written files,
# holds a handle and the rename fails with "Access is denied" (WinError 5).
# Retry once after a pause; a second failure is reported with a hint.
WINDOWS_RETRY_DELAY = 3


def run_cli_install(argv, cwd, skill_dir):
    """run_cli, plus one retry on Windows after clearing a staging dir the
    failed attempt may have left behind."""
    if run_cli(argv, cwd):
        return True
    if not IS_WINDOWS:
        return False
    log(f"retrying in {WINDOWS_RETRY_DELAY}s (Windows file lock?)")
    shutil.rmtree(skill_dir / "references.tmp", ignore_errors=True)
    time.sleep(WINDOWS_RETRY_DELAY)
    if run_cli(argv, cwd):
        return True
    warn(f"{skill_dir} is locked: close VS Code and JetBrains (they watch "
         "the skills folder), then re-run "
         "install.py --target copilot")
    return False


_SKILL_REF_RE = re.compile(r"references/[\w./-]+\.md")


def external_state(ext, exe, dest):
    """State of an installed external skill dir: missing (no dir), current
    (a complete skill stamped with the CLI's own version, so re-running its
    installer would change nothing), half (an interrupted install: a leftover
    references.tmp, no SKILL.md, or a references/ file SKILL.md names but
    that is missing) or older (complete, but not stamped with the CLI's
    version, or the version is unknown)."""
    if not dest.exists():
        return "missing"
    skill_md = dest / "SKILL.md"
    body = None
    if skill_md.is_file():
        try:
            body = skill_md.read_text(encoding="utf-8")
        except OSError:
            pass
    if (body is None or (dest / "references.tmp").exists()
            or not all((dest / ref).is_file()
                       for ref in set(_SKILL_REF_RE.findall(body)))):
        return "half"
    version = cli_version(exe)
    if version is None or external_version(dest, ext) != version:
        return "older"
    return "current"


def external_current(ext, exe, dest):
    return external_state(ext, exe, dest) == "current"


def inspect_external(target, ext, exe, mode="run"):
    """Item for one external on one target. mode: "run" (exe is the CLI, or
    None when it could not be installed), "dry-run" (exe None means the run
    would install the CLI first) or "status" (exe is whatever is on disk)."""
    name = ext["name"]
    if target not in ext["targets"]:
        return Item(target, name, "not-for-target",
                    done=f"skipped (not for {target})")
    dest = target_root(target) / name
    note = None
    if exe is None and mode != "dry-run":
        state = "unavailable"
        if mode == "status":
            note = (f"{name} skill is installed but its {ext['cli']} CLI "
                    "is missing")
    else:
        state = external_state(ext, exe, dest)
    shown = " ".join([ext["cli"], *ext["install"][target]])

    def apply(dry_run):
        if dry_run:
            return f"dry-run: would run {shown}"
        # The CLI runs in a scratch directory, so the repo-scoped files some
        # installers write next to the cwd land nowhere.
        with tempfile.TemporaryDirectory() as scratch:
            if not run_cli_install([exe, *ext["install"][target]], scratch,
                                   dest):
                return ("failed", "failed")
    return Item(target, name, state, apply, note, done="installed (by CLI)",
                current="up to date")


def install_external_for_target(target, ext, exe, dry_run):
    """Delegate one external's install for one target, as its state says."""
    return run_items([inspect_external(
        target, ext, exe, "dry-run" if dry_run else "run")], dry_run)


def inspect_externals_for_target(target, sel_externals, mode="run"):
    """Items for the selected externals. Each carries its resolved CLI path
    under '_exe' (None = missing and not installable)."""
    return [inspect_external(target, ext, ext.get("_exe"), mode)
            for ext in EXTERNALS if ext["name"] in sel_externals]


def install_externals_for_target(target, sel_externals, dry_run):
    return run_items(inspect_externals_for_target(
        target, sel_externals, "dry-run" if dry_run else "run"), dry_run)


WSL_HINT = ("WSL: VS Code and JetBrains on Windows read %USERPROFILE%; this "
            "run wrote the JetBrains instructions there. Run install.py "
            "from Git Bash for the other extras on the Windows side. Skills "
            "come from cali, not this script: `cali setup` once, then "
            "`cali load <skill>` fills both homes.")
WINDOWS_HOME_HELP = """\
WSL: could not find the Windows home ({why}).
Windows-side JetBrains reads its instructions there, so they were NOT
written. Either
  - re-run with the Windows home named:
      python3 install.py --windows-home /mnt/c/Users/<your Windows user>
  - or run install.py from Git Bash on Windows."""
SKILLS_HINT = ("Skills are installed by cali, not this script: "
               "`cali setup github:rojcarranza/agent-skills` once, then "
               "`cali load <skill>`. See the README.")


def collect_extras(targets, win_home=None):
    """Items for the instruction files, MCP servers and the Windows
    JetBrains block, in the order a run handles them."""
    items = []
    for target in targets:
        if target == "claude":
            items.append(inspect_claude_rules())
        items.extend(inspect_instructions(target))
    for target in targets:
        items.extend(inspect_mcp_servers(target))
    if win_home is not None:
        # Windows-side JetBrains reads the Windows home's global file.
        items.append(inspect_jetbrains_instructions(
            jetbrains_instruction_path(home=win_home), "windows"))
    return items


def show_status(targets, windows_home=None):
    """What this script wrote: instructions, MCP servers and externals, each
    read the way a run reads it. Returns the exit code, the worst level."""
    print(f"  {SKILLS_HINT}\n  Installed skills: cali status -g\n")
    items = collect_extras(targets, windows_home)
    extra = []
    for target in targets:
        root = target_root(target)
        for ext in EXTERNALS:
            dest = root / ext["name"]
            if not dest.is_dir():
                continue
            version = external_version(dest, ext)
            print(f"  {target:8} {ext['name']:30} external "
                  f"({ext['package']}{' ' + version if version else ''})")
            items.append(inspect_external(target, ext, find_cli(ext["cli"]),
                                          "status"))
            if find_cli(ext["cli"]) and cli_path_hint(ext):
                extra.append(f"{target}: {cli_path_hint(ext)}")
    if windows_home is not None:
        print(f"  windows home: {windows_home}  (JetBrains instructions)")
    print()
    found = status_warnings(items)
    for _, line in found:
        warn(line)
    for line in extra:
        warn(line)
    level = max([lv for lv, _ in found], default=OK)
    if not found and not extra:
        ok("no conflicts detected")
    return max(level, ATTENTION if extra else OK)


def print_summary(results, targets, dry_run):
    print()
    log(("Planned actions (dry run)" if dry_run else "Install summary") + ":")
    for target, name, status in results:
        print(f"  {target:8} {name:35} {status}")
    print()
    if "copilot" in targets:
        log("Verify Copilot:  /skills list  in Copilot CLI, or ask VS Code "
            "agent mode 'What skills do you have available?'")
    if "claude" in targets:
        log("Verify Claude:   ask 'what skills are available?' in a new "
            "claude session")
    done = {"current", "missing", "older", "half"}
    for name in sorted({r[1] for r in results
                        if r[1] in externals()
                        and getattr(r, "state", "current") in done}):
        ext = externals()[name]
        log(f"Verify {name}:  run '{ext['cli']} --version', then "
            f"'/{name} .' in the agent — {ext['doc']}")
        hint = cli_path_hint(ext)
        if hint and not dry_run:
            warn(hint)


def main():
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--target", choices=["copilot", "claude", "both"],
                    default="both", help="where to install (default: both)")
    ap.add_argument("--dry-run", action="store_true",
                    help="print planned actions without writing or running "
                         "anything")
    ap.add_argument("--status", action="store_true",
                    help="show what this script wrote and leftovers; skills "
                         "are `cali status -g`")
    ap.add_argument("--update", action="store_true",
                    help="skills are updated by cali: prints `cali update -g`")
    ap.add_argument("--upgrade", action="store_true",
                    help="upgrade external CLIs (graphify) before refreshing "
                         "their skill files")
    ap.add_argument("--skills-only", action="store_true",
                    help="skip graphify (e.g. PyPI blocked)")
    ap.add_argument("--windows-home", metavar="PATH",
                    help="WSL: the Windows home that gets the JetBrains "
                         "instructions (default: %%USERPROFILE%%, read "
                         "through cmd.exe)")
    args = ap.parse_args()
    targets = (["copilot", "claude"] if args.target == "both"
               else [args.target])

    if args.update:
        print("Skills are updated by cali: run `cali update -g` to see newer "
              "versions, `cali update -g --apply` to take them.")
        return

    # WSL: Windows-side JetBrains reads the Windows home's instruction file.
    win_home, win_problem = None, None
    if is_wsl() and "copilot" in targets:
        win_home, win_problem = resolve_windows_home(args.windows_home)

    if args.status:
        code = show_status(targets, win_home)
        if win_problem:
            warn(WINDOWS_HOME_HELP.format(why=win_problem))
            code = max(code, ATTENTION)
        if code:
            sys.exit(code)
        return

    results = []
    results.extend(run_items(collect_extras(targets, win_home), args.dry_run))

    sel_externals = set() if args.skills_only else default_external_names()
    if args.skills_only:
        log("--skills-only: skipping externals")
    for ext in EXTERNALS:
        ext.pop("_upgrade", None)
        if ext["name"] not in sel_externals:
            ext["_exe"] = None
            continue
        ext["_exe"] = bootstrap_cli(ext, args.dry_run)
        if args.upgrade and (ext["_exe"] or args.dry_run):
            ext["_upgrade"] = upgrade_cli(ext, ext["_exe"], args.dry_run)
            results.append(Row("external", ext["name"], ext["_upgrade"],
                               "unavailable"
                               if ext["_upgrade"] == "upgrade unavailable"
                               else "current"))
    mode = "dry-run" if args.dry_run else "run"
    items = [i for target in targets
             for i in inspect_externals_for_target(target, sel_externals,
                                                   mode)]
    results.extend(run_items(items, args.dry_run))

    print_summary(results, targets, args.dry_run)
    log(SKILLS_HINT)
    if is_wsl():
        log(WSL_HINT)
        if win_problem:
            warn(WINDOWS_HOME_HELP.format(why=win_problem))
    code = worst_level(results)
    if code:
        sys.exit(code)


if __name__ == "__main__":
    main()
