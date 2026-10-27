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
`python install.py`. On WSL run it inside WSL: it also copies the Copilot
skills to the Windows home that Windows-side VS Code and JetBrains read
(--windows-home PATH names it, --no-windows-home skips it).

cali.yaml lists every skill; this script runs
`cali sync -g --manifest <clone>/cali.yaml` (https://github.com/rojcarranza/cali)
to install them. The rest is done here: personal instructions, the GitHub
MCP server (MCP_SERVERS), removing what older versions of this script and
APM installed, and graphify (EXTERNALS), whose own CLI installs its skill.

Any single skill also installs without this script, in any agent the
`skills` CLI supports: npx skills add rojcarranza/agent-skills -s <name>.
"""
import argparse
import contextlib
import filecmp
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
    "roj-explain-feature-changes": ("code-tour",),
    # Custom skills never require each other: shared files are copied into
    # each skill by tools/sync_shared.py, so every skill also installs alone
    # through `npx skills add`.
}


# cali.yaml: the manifest Cali installs from. Read here only for names and
# targets — status, legacy cleanup and tests — with a line parser for the
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
    """cali.yaml text -> [{'name', 'source', 'ref', 'targets', 'active'}].
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
                       "source": "", "ref": None, "targets": None}
            skills.append(current)
            continue
        field = _FIELD_LINE_RE.match(line)
        if (field and current is not None
                and bool(field.group(1)) != current["active"]):
            key, value = field.group(2), _unquote(_strip_comment(field.group(3)))
            if key == "targets":
                current["targets"] = tuple(
                    t.strip() for t in value.strip("[]").split(",") if t.strip())
            elif key in ("source", "ref"):
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


# Cali is a Go binary with no PyPI package, so install.py cannot bootstrap
# it the way it does graphify; a missing cali stops the run with this.
CALI_INSTALL_HINT = """\
cali is not installed (or not on PATH). Install it from a clone of
https://github.com/rojcarranza/cali, open a new shell, then re-run install.py:
  macOS / Linux / WSL:  make install
  Windows Git Bash:     sh scripts/install.sh"""
WSL_HINT = ("WSL: Claude Code and Copilot CLI inside WSL read the Linux "
            "home. VS Code and JetBrains on Windows read %USERPROFILE%, which "
            "gets the Copilot skills only, not graphify, the personal "
            "instructions or the GitHub MCP server - run install.py from "
            "Git Bash for those.")
WINDOWS_HOME_HELP = """\
WSL: could not find the Windows home ({why}).
Windows-side VS Code and JetBrains read the Copilot skills there, so they
will NOT see the skills just installed in the Linux home. Either
  - re-run with the Windows home named:
      python3 install.py --windows-home /mnt/c/Users/<your Windows user>
  - or run install.py from Git Bash on Windows.
--no-windows-home skips this step."""
# Cali states (`cali status --json`) for a folder Cali did not put there:
# no pristine copy of the locked version, or a skill not locked yet.
NOT_CALIS = {"base-lost", "unlocked"}


def apm_home():
    """APM's user dir. Only read: its lockfile says what APM deployed."""
    return Path.home() / ".apm"


def cali_argv(exe: str, *args: str) -> list:
    """A cali command against this clone's cali.yaml, in the global scope:
    skills land in ~/.claude/skills and ~/.copilot/skills, and cali.lock is
    read and written next to cali.yaml."""
    return [exe, *args, "-g", "--manifest", str(MANIFEST_PATH)]


def run_cali(argv: list) -> int:
    """Run cali with its output passed through; returns its exit code."""
    try:
        return subprocess.run(argv).returncode
    except OSError as exc:
        warn(f"{' '.join(argv)} failed: {exc}")
        return 127


def cali_status_rows(exe: str):
    """{(skill, target): (state, ...)} from `cali status --offline --json`,
    or None when cali cannot say — callers then remove no copies."""
    try:
        # stderr passes through, so a failing cali shows its own error.
        run = subprocess.run(cali_argv(exe, "status", "--offline", "--json"),
                             stdout=subprocess.PIPE, text=True, timeout=120)
        rows = json.loads(run.stdout)["rows"] if run.returncode == 0 else None
        if rows is not None:
            return {(r["skill"], r["target"]): tuple(r["states"])
                    for r in rows}
    except (OSError, subprocess.SubprocessError, ValueError, KeyError,
            TypeError):
        pass
    warn("cali status --offline --json gave no usable result — no skill "
         "copies are removed this run")
    return None


def github_token():
    """$token, else the logged-in GitHub CLI's, else None (a machine with no
    GitHub login, e.g. one whose repos live on Bitbucket). The GitHub MCP
    server is registered only when there is one, as under APM; the token
    itself is never written to any config."""
    if os.environ.get("token"):
        return os.environ["token"]
    gh = shutil.which("gh")
    if not gh:
        return None
    try:
        run = subprocess.run([gh, "auth", "token"], capture_output=True,
                             text=True, timeout=30)
    except (OSError, subprocess.SubprocessError):
        return None
    token = (run.stdout or "").strip()
    return token if run.returncode == 0 and token else None


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


# Before APM, this script copied or linked every skill itself; APM then
# copied them again. Cali never replaces a folder it did not install (sync
# reports it as kept), and it deploys Copilot skills to ~/.copilot/skills,
# so APM's ~/.agents/skills copies would load twice.
INSTRUCTIONS_SRC = REPO_ROOT / ".apm" / "instructions" / "personal.instructions.md"


def legacy_skill_names():
    """Every skill an earlier install put in a skills dir: ours, and every
    skill cali.yaml lists, live or optional (all were in the old inventory
    or apm.yml). Externals are left to their own CLI."""
    return custom_skill_names() | manifest_skill_names(active_only=False)


# Skills earlier versions of cali.yaml installed, since pruned. Their
# folders stay behind: cali sync never deletes one.
RETIRED_SKILLS = (
    "add-educational-comments", "arch-linux-triage",
    "architecture-blueprint-generator", "centos-linux-triage",
    "debian-linux-triage", "fedora-linux-triage", "roj-code-review-pr-fast",
    "roj-tour-codebase",
)
# Copilot-only skills no cali.yaml ever installed for Claude: a Claude copy
# came from somewhere else.
NEVER_CLAUDE_SKILLS = ("caveman", "debugging-and-error-recovery")


def stale_skill_names(target):
    """Skills an earlier install may have put in target's skills dir that
    Cali no longer installs there: live cali.yaml skills limited to other
    targets, and RETIRED_SKILLS. Optional (commented) skills are not stale,
    nor are NEVER_CLAUDE_SKILLS for Claude."""
    never = set(NEVER_CLAUDE_SKILLS) if target == "claude" else set()
    return ((custom_skill_names() | manifest_skill_names()
             | set(RETIRED_SKILLS)) - managed_skill_names(target) - never)


def managed_skill_names(target):
    """Skills Cali installs for target: every active cali.yaml skill not
    limited to other targets. Only these are safe to remove — cali sync
    puts them straight back."""
    return {d["name"] for d in manifest_deps()
            if d["active"] and (d["targets"] is None or target in d["targets"])}


def read_lockfile():
    """~/.apm/apm.lock.yaml text, or None on a machine APM never ran on."""
    try:
        return (apm_home() / "apm.lock.yaml").read_text(
            encoding="utf-8", errors="replace")
    except OSError:
        return None


def apm_deployed_skill(name, lock_text):
    """True if the APM lockfile records deploying .agents/skills/<name>.
    The name must end there: code-tour is not code-tour-x."""
    if lock_text is None:
        return False
    pattern = r"\.agents/skills/" + re.escape(name) + r"(?![\w.-])"
    return re.search(pattern, lock_text.replace("\\", "/")) is not None


def _links_into_a_checkout(entry):
    """True for a link to <root>/skills/<name> in any checkout of this repo
    (this clone, the main checkout of a worktree, or another clone): a root
    with install.py and .claude-plugin/marketplace.json."""
    # resolve(), not os.readlink(): on Windows readlink returns a \\?\-prefixed
    # path that never compares equal to SKILLS_SRC.
    try:
        target = entry.resolve()
    except (OSError, RuntimeError):
        return False
    if SKILLS_SRC.resolve() in target.parents:
        return True
    root = target.parent.parent
    return (target.parent.name == "skills" and target.name == entry.name
            and target.is_dir() and (root / "install.py").is_file()
            and (root / ".claude-plugin" / "marketplace.json").is_file())


def remove_installer_skills(target, dest_root, dry_run, cali_rows=None,
                            home=None):
    """Remove what older installs left in dest_root, for skills Cali now
    installs for target. cali_rows is cali_status_rows(): a copy is moved to
    backup_dir() only when Cali says it did not install it (NOT_CALIS), so a
    Cali-installed folder, local edits included, is never touched. Without
    cali_rows no copy is moved. For a stale_skill_names() entry, which Cali
    will not reinstall for target, only a link an older installer made is
    moved to backup_dir(); a real folder is kept, and its path is printed
    with a warning to delete it if stale (Cali keeps no record of the hosts
    a skill was dropped from). The exception is a RETIRED_SKILLS folder whose
    SKILL.md declares its own name: only our installs ever put it there, so
    it is moved to backup_dir() too. Any other leftover Cali will not
    reinstall is kept, with a warning when its SKILL.md declares that name.
    home is the home dest_root belongs to, when it is not the current one."""
    results = []
    if not dest_root.is_dir():
        return results
    stale = stale_skill_names(target)
    names = legacy_skill_names() | stale
    managed = managed_skill_names(target)
    for entry in sorted(dest_root.iterdir()):
        if entry.name not in names:
            continue
        if entry.is_symlink():
            ours = _links_into_a_checkout(entry) or not entry.exists()
        else:
            ours = entry.is_dir() and is_ours(entry, entry.name)
        if entry.name not in managed:
            retired = (entry.name in RETIRED_SKILLS and ours
                       and not entry.is_symlink())
            if entry.name in stale and ours and (entry.is_symlink() or retired):
                dest = _move_aside(entry, target, dry_run, home)
                results.append((target, entry.name,
                                f"moved to {dest} (not installed for {target})"
                                if not retired else
                                f"moved to {dest} (retired skill)"))
            elif entry.name in stale:
                warn(f"{entry} is left over: Cali no longer installs "
                     f"{entry.name} for {target} — kept; delete it if it "
                     "is stale")
            elif ours:
                warn(f"{entry} was installed by an old installer; Cali does "
                     f"not manage {entry.name} for {target} — uncomment it in "
                     "cali.yaml to keep it updated, or delete it")
            continue
        if entry.is_symlink():
            if ours:
                _remove(entry, dry_run)
                results.append((target, entry.name, "removed (pre-APM link)"))
            else:
                warn(f"{entry} is a link outside this clone — Cali cannot "
                     f"install {entry.name} over it; remove it if it is stale")
        elif ours and cali_rows is not None and NOT_CALIS & set(
                cali_rows.get((entry.name, target), ())):
            # base-lost also covers a Cali folder whose data dir was wiped, so
            # the copy may hold local edits: move it aside, never delete it.
            dest = _move_aside(entry, target, dry_run, home)
            results.append((target, entry.name,
                            f"moved to {dest} (not installed by Cali)"))
    return results


def apm_skills_root():
    """Where APM deployed Copilot skills."""
    return Path.home() / ".agents" / "skills"


def remove_apm_skills(dry_run, lock_text):
    """Remove the ~/.agents/skills copies APM deployed for skills Cali now
    installs for Copilot (in ~/.copilot/skills). Only folders the APM
    lockfile lists — ~/.agents/skills is shared with other tools."""
    results = []
    root = apm_skills_root()
    for name in sorted(managed_skill_names("copilot")):
        entry = root / name
        if (entry.is_dir() and not entry.is_symlink()
                and apm_deployed_skill(name, lock_text)):
            _remove(entry, dry_run)
            results.append(("copilot", name,
                            "removed (APM copy in ~/.agents/skills)"))
    return results


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


def retire_claude_rules(dry_run):
    """Move the personal.md rule earlier versions deployed for Claude to
    backup_dir(), when its body is one this repo shipped (Claude got it with
    `applyTo:` turned into `paths:`). An edited copy or a link is kept with
    a warning."""
    path = claude_rules_path()
    if path.is_symlink():
        warn(f"{path} is a link - left in place; Claude now gets no "
             "personal instructions from install.py")
        return []
    if not path.is_file():
        return []
    current = path.read_text(encoding="utf-8", errors="replace")
    if _instruction_body(current) not in {
            _instruction_body(t) for t in shipped_instructions()}:
        warn(f"{path} differs from every version install.py shipped - left "
             "in place; Claude now gets no personal instructions from "
             "install.py")
        return []
    dest = _move_aside(path, "claude", dry_run)
    return [("claude", path.name, f"moved to {dest} (Claude gets none)")]


def shipped_instructions():
    """Every version of INSTRUCTIONS_SRC this clone has shipped: the file
    on disk plus each committed one (none when git or history is missing).
    A deployed file equal to one of them is ours to update."""
    texts = {INSTRUCTIONS_SRC.read_text(encoding="utf-8")}
    rel = INSTRUCTIONS_SRC.relative_to(REPO_ROOT).as_posix()
    try:
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


def install_instructions(target, dry_run):
    """Deploy INSTRUCTIONS_SRC for target (Copilot only). Replaces a missing file, a
    version this repo shipped, or the dotfiles repo's link; keeps an
    edited copy or a link to anything else, with a warning. Nothing is
    returned when the file is already current."""
    dest = instruction_path(target)
    if dest is None:
        return []
    new = INSTRUCTIONS_SRC.read_text(encoding="utf-8")
    if dest.is_symlink():
        if not _links_into_dotfiles(dest):
            warn(f"{dest} links somewhere other than the dotfiles repo — left "
                 f"in place; remove it so install.py can deploy {dest.name}")
            return []
        status = "replaced dotfiles link"
    elif dest.is_file():
        current = dest.read_text(encoding="utf-8", errors="replace")
        if current == new:
            return []
        if current not in shipped_instructions():
            warn(f"{dest} differs from {INSTRUCTIONS_SRC} — left in place; "
                 "merge your edits into the repo copy, delete it, and re-run")
            return []
        status = "updated"
    else:
        status = "installed"
    if not dry_run:
        if dest.is_symlink():
            dest.unlink()
        _write_text(dest, new)
    return [(target, dest.name, status)]


# MCP servers install.py registers, per target, in the shape each agent's
# user config takes: Claude Code ~/.claude.json and Copilot CLI
# ~/.copilot/mcp-config.json, both under "mcpServers". The GitHub server is
# remote and signs in with OAuth, so no token goes in the file. An entry of
# the same name is never replaced, so a hand-tuned one survives.
GITHUB_MCP_URL = "https://api.githubcopilot.com/mcp/"
MCP_SERVERS = {
    "github-mcp-server": {
        "claude": {"type": "http", "url": GITHUB_MCP_URL},
        "copilot": {"type": "http", "url": GITHUB_MCP_URL, "tools": ["*"]},
    },
    # Optional, for projects with a UI to drive: microsoft/playwright-mcp —
    # add its entry here from https://github.com/microsoft/playwright-mcp.
}


def mcp_config_path(target):
    if target == "claude":
        return Path.home() / ".claude.json"
    return Path.home() / ".copilot" / "mcp-config.json"


def register_mcp_servers(target, dry_run):
    """Add each MCP_SERVERS entry missing from target's config, keeping
    every other key. A file that is not a JSON object is never rewritten."""
    path = mcp_config_path(target)
    try:
        data = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    except (OSError, ValueError) as exc:
        warn(f"{path} is not valid JSON ({exc}) — left alone; add the MCP "
             "servers by hand")
        return []
    servers = data.get("mcpServers", {}) if isinstance(data, dict) else None
    if not isinstance(servers, dict):
        warn(f"{path} has no mcpServers object — left alone; add the MCP "
             "servers by hand")
        return []
    results = []
    for name, configs in MCP_SERVERS.items():
        if target not in configs:
            continue
        if name in servers:
            results.append((target, f"mcp:{name}", "already configured"))
            continue
        servers[name] = configs[target]
        results.append((target, f"mcp:{name}", "added"))
    if dry_run or not any(s == "added" for _, _, s in results):
        return results
    data["mcpServers"] = servers
    # Same directory, then rename: a crash never leaves a half-written file.
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=path.name + ".")
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as fh:
            json.dump(data, fh, indent=2)
            fh.write("\n")
        if path.exists():
            shutil.copymode(str(path), tmp)
        os.replace(tmp, str(path))
    except OSError:
        with contextlib.suppress(OSError):
            os.unlink(tmp)
        raise
    return results


# Custom skills and prompts were renamed with a "roj-" prefix. Installs made
# before the rename still carry the bare names; every install run removes
# those leftovers (see remove_legacy) so no agent lists a workflow twice.
LEGACY_PREFIX = "roj-"


# Stems of the prompts/*.prompt.md files earlier versions shipped. Installs
# made then left generated skills, Claude commands and .prompt.md copies
# under these names; retire_prompts removes them on every install run.
RETIRED_PROMPTS = (
    "roj-code-review-pr", "roj-code-review-pr-fast", "roj-create-implement-sb",
    "roj-create-sb", "roj-explain-and-review", "roj-explain-code",
    "roj-explain-feature-changes", "roj-implement-sb", "roj-tour-codebase",
)
GENERATED_MARKER = "Generated from prompts/"


def legacy_name(name):
    """'roj-create-sb' -> 'create-sb'; None for names never renamed."""
    if name.startswith(LEGACY_PREFIX):
        return name[len(LEGACY_PREFIX):]
    return None


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


def target_root(target):
    return Path.home() / (".copilot" if target == "copilot"
                          else ".claude") / "skills"


def vscode_prompts_dir():
    """Locate the VS Code user prompts dir, or None if VS Code is absent.
    Only read to remove .prompt.md copies earlier installs left there."""
    candidates = []
    appdata = os.environ.get("APPDATA")
    if appdata:
        candidates.append(Path(appdata) / "Code" / "User")          # Windows
    candidates.append(Path.home() / "Library" / "Application Support"
                      / "Code" / "User")                            # macOS
    candidates.append(Path.home() / ".config" / "Code" / "User")    # Linux
    for c in candidates:
        if c.is_dir():
            return c / "prompts"
    return None


def custom_skill_names():
    """Names of the skills in skills/ — also the directory names they take
    in every target root."""
    if not SKILLS_SRC.is_dir():
        return set()
    return {p.name for p in SKILLS_SRC.iterdir() if p.is_dir()}


def claude_commands_dir():
    """Claude's personal slash-command scope, where earlier installs wrote
    one generated command per prompt."""
    return Path.home() / ".claude" / "commands"


def prompts_dir_for(target):
    """Where earlier installs put *.prompt.md for a target, or None."""
    if target == "copilot":
        return vscode_prompts_dir()
    return None                      # claude never used prompt files


def legacy_names():
    """Pre-rename names of every custom skill. Leftovers of retired prompts,
    renamed or not, belong to retire_prompts."""
    return sorted(filter(None, (legacy_name(n)
                                for n in custom_skill_names())))


def is_ours(entry, old):
    """True if a skills-dir entry named `old` came from this installer: a
    symlink (Claude target, now dangling after the rename) or a copy whose
    SKILL.md declares that name."""
    if entry.is_symlink():
        return True
    skill_md = entry / "SKILL.md"
    if not skill_md.is_file():
        return False
    for line in skill_md.read_text(encoding="utf-8",
                                   errors="replace").splitlines()[:5]:
        if line.strip() == f"name: {old}":
            return True
    return False


def is_generated(path):
    """True for a file, or a skill dir's SKILL.md, that an earlier install
    generated from prompts/ — never a real skill or a hand-written file."""
    path = Path(path)
    if path.is_dir() and not path.is_symlink():
        path = path / "SKILL.md"
    try:
        return GENERATED_MARKER in path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return False


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


def _remove(path, dry_run):
    if dry_run:
        return
    if path.is_symlink() or path.is_file():
        path.unlink()
    else:
        shutil.rmtree(path)


def remove_legacy(target, dest_root, dry_run):
    """Delete skill dirs left under pre-rename names. Generated prompt
    leftovers are handled by retire_prompts."""
    results = []
    for old in legacy_names():
        new = LEGACY_PREFIX + old
        entry = dest_root / old
        if (entry.is_symlink() or entry.exists()) and is_ours(entry, old):
            _remove(entry, dry_run)
            results.append((target, old, f"removed (renamed to {new})"))
    return results


def retire_prompts(target, dest_root, dry_run):
    """Remove everything earlier installs generated from prompts/, under
    current and pre-rename names: generated skill dirs in dest_root, Claude
    slash commands, and .prompt.md copies, plus a <name>.bak copy of a
    generated skill dir left by an old backup. Only regular files
    and dirs carrying the generated marker (or, for .prompt.md, one of our
    names) are touched — never a symlink, which points at something the
    user owns."""
    results = []
    status = "removed (prompts retired — use the skill)"
    names = sorted(set(RETIRED_PROMPTS)
                   | {legacy_name(n) for n in RETIRED_PROMPTS})
    for name in names:
        for dirname in (name, f"{name}.bak"):
            entry = dest_root / dirname
            if (entry.is_dir() and not entry.is_symlink()
                    and is_generated(entry)):
                _remove(entry, dry_run)
                results.append((target, dirname, status))
        cmd = claude_commands_dir() / f"{name}.md"
        if (target == "claude" and cmd.is_file() and not cmd.is_symlink()
                and is_generated(cmd)):
            _remove(cmd, dry_run)
            results.append((target, f"command:{name}", status))
    pdir = prompts_dir_for(target)
    if pdir is not None and pdir.is_dir():
        for name in names:
            old = pdir / f"{name}.prompt.md"
            if old.is_file() and not old.is_symlink():
                _remove(old, dry_run)
                results.append((target, f"prompt:{name}", status))
        if not dry_run and not any(pdir.iterdir()):
            pdir.rmdir()
    return results


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
# Best first. pip is the last resort — it is always there (we are running
# under it) but installs into the user site rather than an isolated venv.
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
        log(f"Upgrading {ext['package']} with {via}...")
        try:
            subprocess.run([*cmd, ext["package"]], check=True)
        except (subprocess.CalledProcessError, OSError):
            continue
        after = cli_version(find_cli(ext["cli"]) or exe)
        if before and after and before != after:
            return f"upgraded ({before} -> {after})"
        return f"already latest ({after or before or 'version unknown'})"
    warn(f"No uv/pipx/pip available to upgrade {ext['package']}")
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
    warn(f"No {ext['cli']} CLI and no uv/pipx/pip to install it — skipping. "
         f"Install it yourself with 'uv tool install {ext['package']}' "
         f"(or 'pipx install {ext['package']}', or "
         f"'python -m pip install --user {ext['package']}') and re-run.")
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


def external_current(ext, exe, dest):
    """True when dest holds a complete skill stamped with the CLI's own
    version — re-running the CLI's installer would change nothing. An
    interrupted install (a leftover references.tmp, or a references/ file
    SKILL.md names but that is missing) is never current."""
    version = cli_version(exe)
    skill_md = dest / "SKILL.md"
    if (version is None or not skill_md.is_file()
            or external_version(dest, ext) != version
            or (dest / "references.tmp").exists()):
        return False
    try:
        body = skill_md.read_text(encoding="utf-8")
    except OSError:
        return False
    return all((dest / ref).is_file()
               for ref in set(_SKILL_REF_RE.findall(body)))


def install_external_for_target(target, ext, exe, dry_run):
    """Delegate one external's install for one target. The CLI runs in a
    scratch directory so the repo-scoped files some installers write next to
    the cwd land nowhere."""
    name = ext["name"]
    if target not in ext["targets"]:
        return [(target, name, f"skipped (not for {target})")]
    argv = [exe or ext["cli"], *ext["install"][target]]
    shown = " ".join([ext["cli"], *ext["install"][target]])
    if dry_run:
        return [(target, name, f"dry-run: would run {shown}")]
    if not exe:
        return [(target, name, "skipped (CLI unavailable)")]
    dest = target_root(target) / name
    if external_current(ext, exe, dest):
        return [(target, name, "up to date")]
    with tempfile.TemporaryDirectory() as scratch:
        if not run_cli_install(argv, scratch, dest):
            return [(target, name, "failed")]
    return [(target, name, "installed (by CLI)")]


def install_externals_for_target(target, sel_externals, dry_run):
    """Install selected externals for one target. Each carries its resolved
    CLI path under '_exe' (None = missing and not installable)."""
    results = []
    for ext in EXTERNALS:
        if ext["name"] not in sel_externals:
            continue
        results.extend(install_external_for_target(
            target, ext, ext.get("_exe"), dry_run))
    return results


def _tree_files(root):
    return {p.relative_to(root).as_posix(): p
            for p in root.rglob("*") if p.is_file()}


def _same_tree(a, b):
    """True when folders a and b hold the same files with the same bytes."""
    files_a, files_b = _tree_files(a), _tree_files(b)
    return (files_a.keys() == files_b.keys()
            and all(filecmp.cmp(str(files_a[k]), str(files_b[k]), shallow=False)
                    for k in files_a))


def _copy_skill(src, dest, win_home):
    """Put a copy of src at dest. The copy is built beside dest first, so an
    interrupted run never leaves half a skill; an existing dest is moved to
    the Windows home's backup folder and returned. Raises OSError."""
    tmp = dest.with_name(f".{dest.name}.tmp")
    shutil.rmtree(tmp, ignore_errors=True)
    shutil.copytree(str(src), str(tmp))
    backup = None
    try:
        if dest.exists():
            backup = _move_aside(dest, "copilot", False, win_home)
        os.replace(str(tmp), str(dest))
    except OSError:
        shutil.rmtree(tmp, ignore_errors=True)
        if backup is not None and not dest.exists():
            shutil.move(str(backup), str(dest))
        raise
    return backup


def sync_windows_home(win_home, dry_run):
    """The WSL Windows leg: make the Copilot skills Cali installed in the
    Linux home also exist in win_home/.copilot/skills, where Windows-side
    VS Code and JetBrains read them.

    Not `cali sync` with HOME pointed at win_home: Cali would also install the
    Claude target there, keep its pristine copies under /mnt/c, and treat
    every folder a Git Bash run put there as foreign. So the skills Cali
    manages for Copilot are copied (symlinks do not work across /mnt/c); a
    differing folder is moved to <win_home>/.agent-skills-backups first, and
    retired skills are cleaned up as in the Linux home. graphify is not
    copied: its CLI would have to be on the Windows PATH as well."""
    dest_root = win_home / ".copilot" / "skills"
    src_root = target_root("copilot")
    results = [("windows" if t == "copilot" else t, n, s)
               for t, n, s in remove_installer_skills(
                   "copilot", dest_root, dry_run, home=win_home)]
    for name in sorted(managed_skill_names("copilot")):
        src, dest = src_root / name, dest_root / name
        if dest.is_symlink():
            warn(f"{dest} is a link - left in place; remove it so install.py "
                 f"can copy {name} there")
            continue
        if not src.is_dir():
            if not dry_run:
                warn(f"{src} is missing - {name} not copied to {dest_root}")
                results.append(("windows", name, "skipped (no Linux copy)"))
            else:
                results.append(("windows", name, f"would be copied to {dest}"))
            continue
        if dest.is_dir() and _same_tree(src, dest):
            continue
        if dry_run:
            kept = (f", old copy to {_move_aside(dest, 'copilot', True, win_home)}"
                    if dest.exists() else "")
            results.append(("windows", name, f"would be copied to {dest}{kept}"))
            continue
        try:
            backup = _copy_skill(src, dest, win_home)
        except OSError as exc:
            warn(f"could not copy {name} to {dest}: {exc} - close VS Code and "
                 "JetBrains (they watch the skills folder) and re-run")
            results.append(("windows", name, "failed"))
            continue
        results.append(("windows", name, "copied" if backup is None
                        else f"updated (old copy moved to {backup})"))
    return results


def show_status(targets, windows_home=None):
    exe = find_cli("cali")
    if exe:
        run_cali(cali_argv(exe, "list"))
    else:
        warn("cali is not installed — nothing Cali manages can be listed")
    warnings = []
    cali_rows = cali_status_rows(exe) if exe else None
    lock_text = read_lockfile()
    for target in targets:
        root = target_root(target)
        left = remove_installer_skills(target, root, dry_run=True,
                                       cali_rows=cali_rows)
        if left:
            warnings.append(f"{target}: {', '.join(n for _, n, _ in left)} "
                            f"left by an older install in {root} — re-run "
                            f"install.py to remove")
        older = (remove_legacy(target, root, dry_run=True)
                 + retire_prompts(target, root, dry_run=True))
        if target == "copilot":
            older += remove_apm_skills(True, lock_text)
        else:
            older += retire_claude_rules(dry_run=True)
        for _, name, status in install_instructions(target, dry_run=True):
            if status == "replaced dotfiles link":
                older.append((target, name, status))
            else:
                warnings.append(f"{target}: {name} is not deployed or out of "
                                "date — re-run install.py")
        for _, name, _ in older:
            warnings.append(f"{target}: {name} left by an older install — "
                            "re-run install.py to remove")
        for ext in EXTERNALS:
            dest = root / ext["name"]
            if not dest.is_dir():
                continue
            version = external_version(dest, ext)
            print(f"  {target:8} {ext['name']:30} external "
                  f"({ext['package']}{' ' + version if version else ''})")
            if not find_cli(ext["cli"]):
                warnings.append(f"{target}: {ext['name']} skill is installed "
                                f"but its {ext['cli']} CLI is missing")
            elif cli_path_hint(ext):
                warnings.append(f"{target}: {cli_path_hint(ext)}")
    if windows_home is not None:
        print(f"  windows home: {windows_home}  (Copilot skills in "
              f"{windows_home / '.copilot' / 'skills'})")
        todo = sync_windows_home(windows_home, dry_run=True)
        copies = [n for _, n, s in todo if s.startswith("would be copied")]
        if copies:
            warnings.append(f"windows: {len(copies)} skill(s) missing or out "
                            f"of date ({', '.join(copies)}) - re-run "
                            "install.py to copy them")
        for _, name, status in todo:
            if not status.startswith("would be copied"):
                warnings.append(f"windows: {name} {status} - re-run "
                                "install.py")
    print()
    for w in warnings:
        warn(w)
    if not warnings:
        ok("no conflicts detected")


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
    for name in sorted({n for _, n, s in results
                        if n in externals() and not s.startswith("skipped")}):
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
                    help="show what Cali installed, graphify, and leftovers")
    ap.add_argument("--update", action="store_true",
                    help="list skills with newer upstream versions "
                         "(cali status); changes nothing")
    ap.add_argument("--upgrade", action="store_true",
                    help="upgrade external CLIs (graphify) before refreshing "
                         "their skill files")
    ap.add_argument("--skills-only", action="store_true",
                    help="skip graphify (e.g. PyPI blocked)")
    ap.add_argument("--windows-home", metavar="PATH",
                    help="WSL: the Windows home to copy the Copilot skills "
                         "to (default: %%USERPROFILE%%, read through "
                         "cmd.exe)")
    ap.add_argument("--no-windows-home", action="store_true",
                    help="WSL: install into the Linux home only")
    args = ap.parse_args()
    targets = (["copilot", "claude"] if args.target == "both"
               else [args.target])

    # WSL: Windows-side VS Code and JetBrains read the Windows home, so the
    # Copilot skills go there as well.
    win_home, win_problem = None, None
    if is_wsl() and "copilot" in targets and not args.no_windows_home:
        win_home, win_problem = resolve_windows_home(args.windows_home)

    if args.status:
        show_status(targets, win_home)
        if win_problem:
            warn(WINDOWS_HOME_HELP.format(why=win_problem))
        return

    exe = find_cli("cali")
    if not exe and args.dry_run:
        warn("cali is not installed — a real run would stop here:\n"
             + CALI_INSTALL_HINT)
    elif not exe:
        sys.exit(CALI_INSTALL_HINT)
    if args.update:
        if args.dry_run:
            log("dry-run: would run cali status -g --manifest "
                f"{MANIFEST_PATH}")
            return
        sys.exit(run_cali(cali_argv(exe, "status")))

    results = []
    cali_rows = cali_status_rows(exe) if exe else None
    lock_text = read_lockfile()
    for target in targets:
        results.extend(remove_installer_skills(
            target, target_root(target), args.dry_run, cali_rows=cali_rows))
        results.extend(remove_legacy(target, target_root(target),
                                     args.dry_run))
        results.extend(retire_prompts(target, target_root(target),
                                      args.dry_run))
        if target == "copilot":
            results.extend(remove_apm_skills(args.dry_run, lock_text))
        else:
            results.extend(retire_claude_rules(args.dry_run))
        results.extend(install_instructions(target, args.dry_run))
    if github_token():
        for target in targets:
            results.extend(register_mcp_servers(target, args.dry_run))
    else:
        log("No GitHub token ($token or 'gh auth login') — skipping MCP "
            "servers; skills and instructions install as usual")
    argv = cali_argv(exe or "cali", "sync")
    if args.dry_run:
        results.append(("cali", "sync", "dry-run: would run "
                        + " ".join(["cali", *argv[1:]])))
    else:
        code = run_cali(argv)
        if code:
            print_summary(results, targets, args.dry_run)
            warn("cali sync failed — skill folders removed or moved above come back "
                 "once a re-run of install.py succeeds")
            sys.exit(code)
        results.append(("cali", "sync", "done"))
    if win_home is not None:
        results.extend(sync_windows_home(win_home, args.dry_run))

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
            results.append(("external", ext["name"], ext["_upgrade"]))
    for target in targets:
        results.extend(install_externals_for_target(
            target, sel_externals, args.dry_run))

    print_summary(results, targets, args.dry_run)
    if is_wsl():
        log(WSL_HINT)
        if win_problem:
            warn(WINDOWS_HOME_HELP.format(why=win_problem))


if __name__ == "__main__":
    main()
