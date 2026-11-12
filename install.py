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
JetBrains block, the GitHub MCP server (MCP_SERVERS) and graphify
(EXTERNALS), whose own CLI installs its skill.

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


def install_jetbrains_instructions(dry_run, path=None, label="copilot"):
    """Write jetbrains_block() into JetBrains' global file between the
    markers. A file without them gets the block appended; text outside the
    markers is never touched. A link is left alone with a warning."""
    dest = path or jetbrains_instruction_path()
    block = jetbrains_block()
    if dest.is_symlink():
        warn(f"{dest} is a link - left in place; JetBrains gets no "
             "start-up note from install.py")
        return []
    current = (dest.read_text(encoding="utf-8", errors="replace")
               if dest.is_file() else None)
    if current is None:
        new, status = block, "installed"
    else:
        current = current.replace("\r\n", "\n")
        begin = current.find(JETBRAINS_BEGIN)
        end = current.find(JETBRAINS_END, begin + 1) if begin >= 0 else -1
        if begin >= 0 and end >= 0:
            end += len(JETBRAINS_END)
            if current[end:end + 1] == "\n":
                end += 1
            new = current[:begin] + block + current[end:]
            status = "updated"
        else:
            sep = "" if not current.strip() else (
                "\n" if current.endswith("\n") else "\n\n")
            new = current + sep + ("\n" if sep else "") + block
            status = "added block"
        if new == current:
            return []
    if not dry_run:
        _write_text(dest, new)
    return [(label, dest.name, status)]


def install_instructions(target, dry_run):
    """Deploy INSTRUCTIONS_SRC and STARTUP_NOTE_SRC for target (Copilot
    only), and the JetBrains block. Each file is replaced when missing, a
    version this repo shipped, or the dotfiles repo's link; an edited copy or
    a link to anything else is kept with a warning. Nothing is returned for
    a file that is already current."""
    if instruction_path(target) is None:
        return []
    results = _deploy_instruction(target, dry_run, INSTRUCTIONS_SRC,
                                  instruction_path(target))
    results += _deploy_instruction(target, dry_run, STARTUP_NOTE_SRC,
                                   startup_note_path(target))
    results += install_jetbrains_instructions(dry_run)
    return results


def _deploy_instruction(target, dry_run, src, dest):
    new = src.read_text(encoding="utf-8")
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
        if current not in shipped_instructions(src):
            warn(f"{dest} differs from {src} — left in place; "
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


def show_status(targets, windows_home=None):
    """What this script wrote: instructions, MCP servers and externals."""
    print(f"  {SKILLS_HINT}\n  Installed skills: cali status -g\n")
    warnings = []
    for target in targets:
        root = target_root(target)
        for _, name, status in install_instructions(target, dry_run=True):
            if status == "replaced dotfiles link":
                warnings.append(f"{target}: {name} left by an older install "
                                "— re-run install.py to remove")
            else:
                warnings.append(f"{target}: {name} is not deployed or out of "
                                "date — re-run install.py")
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
        print(f"  windows home: {windows_home}  (JetBrains instructions)")
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
        show_status(targets, win_home)
        if win_problem:
            warn(WINDOWS_HOME_HELP.format(why=win_problem))
        return

    results = []
    for target in targets:
        if target == "claude":
            results.extend(retire_claude_rules(args.dry_run))
        results.extend(install_instructions(target, args.dry_run))
    if github_token():
        for target in targets:
            results.extend(register_mcp_servers(target, args.dry_run))
    else:
        log("No GitHub token ($token or 'gh auth login') - skipping MCP "
            "servers; instructions install as usual")
    if win_home is not None:
        # Windows-side JetBrains reads the Windows home's global file.
        results.extend(install_jetbrains_instructions(
            args.dry_run, jetbrains_instruction_path(home=win_home),
            label="windows"))

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
    log(SKILLS_HINT)
    if is_wsl():
        log(WSL_HINT)
        if win_problem:
            warn(WINDOWS_HOME_HELP.format(why=win_problem))


if __name__ == "__main__":
    main()
