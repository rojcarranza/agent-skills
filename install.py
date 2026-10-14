#!/usr/bin/env python3
"""Install Roj's AI setup for Claude Code and GitHub Copilot through APM.

Usage:
  python3 install.py                     # both agents
  python3 install.py --target claude     # or copilot
  python3 install.py --dry-run           # what would happen
  python3 install.py --status            # what is installed, leftovers
  python3 install.py --update            # pins with newer releases
  python3 install.py --upgrade           # newer graphify, then refresh
  python3 install.py --skills-only       # skip graphify (offline/proxy)

Python >= 3.8, standard library only. On Windows run it from Git Bash as
`python install.py`; on WSL run it inside WSL (and again from Git Bash for
Windows-side IDEs).

apm.yml lists every skill, instruction and MCP server. This script writes
~/.apm/apm.yml pointing at this clone and runs `apm install -g`; APM does
the rest. What APM cannot do stays here: removing what pre-APM versions of
this script installed, and graphify (EXTERNALS), whose own CLI installs its
skill.

Any single skill also installs without this script, in any agent the
`skills` CLI supports: npx skills add rojcarranza/agent-skills -s <name>.
"""
import argparse
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
# Also safe to vendor into a repo's .github/ for the whole team.
ANY = BOTH + ("repo",)

REPO_SKILLS_SUBDIR = Path(".github") / "skills"
REPO_PROMPTS_SUBDIR = Path(".github") / "prompts"


# External skills: shipped and installed by their own CLI, never vendored
# here. We bootstrap the CLI, then delegate each target's install to it, so an
# external is always the upstream version — nothing to keep in sync.
EXTERNALS = [
    {
        "name": "graphify",
        "package": "graphifyy",
        "cli": "graphify",
        "targets": ANY,
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
        # `vscode install` also writes <cwd>/.github/copilot-instructions.md.
        # Personal scope runs in a scratch cwd to keep that out of whatever
        # directory the installer was launched from; repo scope runs in the
        # repo, where the file belongs.
        "repo_cwd": True,
        # Written into the repo by `vscode install` alongside the skill;
        # repo scope is only current while it is there.
        "repo_files": (".github/copilot-instructions.md",),
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


# apm.yml: the manifest APM installs from (https://microsoft.github.io/apm/).
# Read here only for names — status, legacy cleanup and tests — with a line
# parser for the shapes this repo's apm.yml uses, so no YAML dependency.
MANIFEST_PATH = REPO_ROOT / "apm.yml"
_DEP_ITEM_RE = re.compile(r"^\s*(#\s*)?-\s+(.*)$")
_OBJECT_KEY_RE = re.compile(r"^[\w-]+:\s")


def _strip_comment(value):
    return re.sub(r"\s+#.*$", "", value).strip()


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


def _scalar(raw):
    return _unquote(_strip_comment(raw))


def _normalise_dep(dep):
    """Fill path/ref/targets/name for the shorthand and the object form."""
    spec = dep.get("spec")
    if spec is not None:
        path, _, ref = spec.partition("#")
        dep["path"], dep["ref"] = path, ref or None
    else:
        dep["path"] = dep.get("path") or dep.get("git") or dep.get("name", "")
        dep["ref"] = dep.get("ref")
    targets = dep.get("targets")
    dep["targets"] = (tuple(t.strip() for t in targets.strip("[]").split(",")
                            if t.strip())
                      if isinstance(targets, str) else None)
    name = dep["path"].rstrip("/").rsplit("/", 1)[-1]
    dep["name"] = name[:-len(".git")] if name.endswith(".git") else name
    return dep


def parse_manifest(text):
    """apm.yml text -> {'apm': [dep, ...], 'mcp': [dep, ...]}. A commented
    list item (`# - x`) is a dependency with active False — how apm.yml marks
    optional skills."""
    out = {"apm": [], "mcp": []}
    section, current = None, None
    for raw in text.splitlines():
        line = raw.rstrip()
        stripped = line.strip()
        if not stripped:
            continue
        indent = len(line) - len(line.lstrip())
        if indent <= 2 and not stripped.startswith(("-", "#")):
            key = stripped.split(":", 1)[0]
            section = key if indent == 2 and key in out else None
            current = None
            continue
        if section is None:
            continue
        item = _DEP_ITEM_RE.match(line)
        if item:
            body = _strip_comment(item.group(2))
            current = {"active": not item.group(1)}
            if _OBJECT_KEY_RE.match(body):
                key, _, value = body.partition(":")
                current[key.strip()] = _unquote(value.strip())
            else:
                current["spec"] = _unquote(body)
            out[section].append(current)
        elif not stripped.startswith("#") and current is not None:
            key, _, value = stripped.partition(":")
            current[key.strip()] = _scalar(value)
    return {name: [_normalise_dep(d) for d in deps]
            for name, deps in out.items()}


def manifest_deps(path=None, section="apm"):
    text = Path(path or MANIFEST_PATH).read_text(encoding="utf-8")
    return parse_manifest(text)[section]


def manifest_skill_names(active_only=True):
    """Skill folder names apm.yml installs (or lists, with active_only off)."""
    return {d["name"] for d in manifest_deps()
            if d["active"] or not active_only}


# User scope. `apm install -g` reads ~/.apm/apm.yml and resolves relative
# paths against ~/.apm, so the manifest there is generated, not linked: one
# dependency, this clone's absolute path, whose own apm.yml lists the rest.
# A plain file on every OS — no symlink support needed on Windows.
USER_MANIFEST_MARKER = ("# Generated by agent-skills install.py. Edit apm.yml "
                        "in the clone, not this file.")
APM_INSTALL_HINT = """\
apm (Agent Package Manager) is not installed. Install it, open a new shell,
then re-run install.py:
  macOS / Linux:     brew install apm
                     curl -sSL https://aka.ms/apm-unix | sh
  Windows:           winget install --id Microsoft.APM --exact --source winget
  Python 3.10+:      python3 -m pip install apm-cli
https://microsoft.github.io/apm/getting-started/installation/"""
WSL_HINT = ("WSL: this installed into the Linux home, for Claude Code and "
            "Copilot CLI inside WSL. VS Code and JetBrains on Windows read "
            "%USERPROFILE% — run install.py from Git Bash too.")


def apm_home():
    return Path.home() / ".apm"


def render_user_manifest(repo_root=None):
    root = Path(repo_root or REPO_ROOT).resolve().as_posix()
    return (f"{USER_MANIFEST_MARKER}\n"
            "name: user\n"
            "version: 1.0.0\n"
            "dependencies:\n"
            "  apm:\n"
            f"    - {json.dumps(root)}\n")


def write_user_manifest(text, force=False, dry_run=False):
    """Write ~/.apm/apm.yml. Exits rather than replace one this script did
    not write, unless force."""
    dest = apm_home() / "apm.yml"
    status = "written"
    if dest.is_file():
        current = dest.read_text(encoding="utf-8")
        if current == text:
            return "up to date"
        if not current.startswith(USER_MANIFEST_MARKER) and not force:
            sys.exit(f"{dest} exists and was not written by install.py. Move "
                     f"it aside, or re-run with --force to replace it.")
        status = "updated"
    if not dry_run:
        dest.parent.mkdir(parents=True, exist_ok=True)
        if dest.is_symlink():
            dest.unlink()
        with open(dest, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(text)
    return status


def apm_install_argv(exe, targets):
    value = ",".join(t for t in ("claude", "copilot") if t in targets)
    # --update makes a dependency removed from apm.yml disappear; pins are
    # full SHAs, so it cannot move them.
    return [exe, "install", "-g", "--update", "--target", value]


def run_apm(argv):
    """Run apm with its output passed through; returns its exit code."""
    try:
        return subprocess.run(argv).returncode
    except OSError as exc:
        warn(f"{' '.join(argv)} failed: {exc}")
        return 127


def is_wsl():
    if sys.platform != "linux":
        return False
    try:
        return "microsoft" in Path("/proc/version").read_text(
            encoding="utf-8").lower()
    except OSError:
        return False


# Before APM, this script copied or linked every skill itself. Those entries
# would collide with APM's: it rejects a symlinked skill destination, and on
# Copilot it deploys to ~/.agents/skills, so an old ~/.copilot/skills copy
# would load as a duplicate.
INSTRUCTIONS_SRC = REPO_ROOT / ".apm" / "instructions" / "personal.instructions.md"


def legacy_skill_names():
    """Every skill an earlier install.py put in a skills dir itself: ours,
    and every community skill apm.yml lists (all were in the old inventory).
    Externals are left to their own CLI."""
    return custom_skill_names() | {d["name"] for d in manifest_deps()
                                   if not d["path"].startswith("./")}


def _links_into_clone(entry):
    try:
        target = Path(os.readlink(entry))
    except OSError:
        return False
    if not target.is_absolute():
        target = entry.parent / target
    return SKILLS_SRC.resolve() in target.resolve().parents


def remove_installer_skills(target, dest_root, apm_owns, dry_run):
    """Remove what pre-APM installs left in dest_root. apm_owns: APM has
    installed at user scope here (~/.apm/apm.lock.yaml exists), so a Claude
    copy is APM's, not ours."""
    results = []
    if not dest_root.is_dir():
        return results
    names = legacy_skill_names()
    for entry in sorted(dest_root.iterdir()):
        if entry.name not in names:
            continue
        if entry.is_symlink():
            if _links_into_clone(entry) or not entry.exists():
                _remove(entry, dry_run)
                results.append((target, entry.name, "removed (pre-APM link)"))
            else:
                warn(f"{entry} is a link outside this clone — APM cannot "
                     f"install {entry.name} over it; remove it if it is stale")
        elif (entry.is_dir() and (target == "copilot" or not apm_owns)
              and is_ours(entry, entry.name)):
            _remove(entry, dry_run)
            results.append((target, entry.name, "removed (pre-APM copy)"))
    return results


def copilot_instruction_path():
    return (Path.home() / ".copilot" / "instructions"
            / INSTRUCTIONS_SRC.name)


def remove_instruction_copy(dry_run):
    """The dotfiles repo linked (or, on Windows, copied) the same file APM
    now deploys. Remove a link or an identical copy; keep an edited one."""
    dest = copilot_instruction_path()
    if dest.is_symlink():
        _remove(dest, dry_run)
        return [("copilot", dest.name,
                 "removed (dotfiles link — APM deploys it now)")]
    if not dest.is_file():
        return []
    if dest.read_bytes() == INSTRUCTIONS_SRC.read_bytes():
        _remove(dest, dry_run)
        return [("copilot", dest.name,
                 "removed (dotfiles copy — APM deploys it now)")]
    warn(f"{dest} differs from {INSTRUCTIONS_SRC} — left in place; merge "
         f"your edits into the repo copy, delete it, and re-run")
    return []


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


def dirs_equal(a, b):
    """Recursive content comparison of two directories (like diff -rq)."""
    cmp = filecmp.dircmp(a, b)
    if cmp.left_only or cmp.right_only or cmp.funny_files:
        return False
    _, mismatch, errors = filecmp.cmpfiles(a, b, cmp.common_files, shallow=False)
    if mismatch or errors:
        return False
    return all(dirs_equal(Path(a) / d, Path(b) / d) for d in cmp.common_dirs)


def install_copy(src, dest, dry_run):
    """Copy skill dir src -> dest. Returns 'installed'|'updated'|'up to date'."""
    src, dest = Path(src), Path(dest)
    if dest.is_symlink() or dest.is_file():
        if not dry_run:
            dest.unlink()
            shutil.copytree(src, dest)
        return "updated"
    if not dest.exists():
        if not dry_run:
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copytree(src, dest)
        return "installed"
    if dirs_equal(src, dest):
        return "up to date"
    if not dry_run:
        shutil.rmtree(dest)
        shutil.copytree(src, dest)
    return "updated"


def target_root(target, repo=None):
    if target == "repo":
        return Path(repo) / REPO_SKILLS_SUBDIR
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


def prompts_dir_for(target, repo=None):
    """Where earlier installs put *.prompt.md for a target, or None."""
    if target == "repo":
        return Path(repo) / REPO_PROMPTS_SUBDIR
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
    for line in skill_md.read_text(encoding="utf-8").splitlines()[:5]:
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


def retire_prompts(target, dest_root, dry_run, repo=None):
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
    pdir = prompts_dir_for(target, repo)
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
         f"the skills folder), then re-run "
         f"install.py --target copilot")
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


def install_external_for_target(target, ext, exe, repo, dry_run):
    """Delegate one external's install for one target.

    Personal scope runs the CLI in a scratch directory so the repo-scoped
    files some installers write next to the cwd land nowhere. Repo scope runs
    it in the repo (where those files belong), then copies the personal skill
    into <repo>/.github/skills for JetBrains Copilot."""
    name = ext["name"]
    if target not in ext["targets"]:
        return [(target, name, f"skipped (not for {target})")]
    # Repo scope reuses the copilot install: same skill, seeded per project.
    argv_key = "copilot" if target == "repo" else target
    argv = [exe or ext["cli"], *ext["install"][argv_key]]
    shown = " ".join([ext["cli"], *ext["install"][argv_key]])
    if dry_run:
        planned = [(target, name, f"dry-run: would run {shown}")]
        if target == "repo":
            planned.append((target, name, "dry-run: would copy into "
                            f"{target_root('repo', repo) / name}"))
        return planned
    if not exe:
        return [(target, name, "skipped (CLI unavailable)")]
    if (external_current(ext, exe, target_root(target, repo) / name)
            and (target != "repo" or all(
                (Path(repo) / f).is_file()
                for f in ext.get("repo_files", ())))):
        return [(target, name, "up to date")]
    # The CLI writes the personal skill; repo scope copies it afterwards.
    cli_dest = target_root(argv_key) / name
    with tempfile.TemporaryDirectory() as scratch:
        cwd = repo if (target == "repo" and ext.get("repo_cwd")) else scratch
        if not run_cli_install(argv, cwd, cli_dest):
            return [(target, name, "failed")]
    if target != "repo":
        return [(target, name, "installed (by CLI)")]
    src = target_root("copilot") / name
    if not src.is_dir():
        return [(target, name, f"failed — {src} missing after install")]
    return [(target, name,
             install_copy(src, target_root("repo", repo) / name, dry_run))]


def install_externals_for_target(target, sel_externals, repo, dry_run):
    """Install selected externals for one target. Each carries its resolved
    CLI path under '_exe' (None = missing and not installable)."""
    results = []
    for ext in EXTERNALS:
        if ext["name"] not in sel_externals:
            continue
        results.extend(install_external_for_target(
            target, ext, ext.get("_exe"), repo, dry_run))
    return results


def show_status(targets):
    exe = find_cli("apm")
    if exe:
        run_apm([exe, "deps", "list", "-g"])
    else:
        warn("apm is not installed — nothing APM manages can be listed")
    warnings = []
    apm_owns = (apm_home() / "apm.lock.yaml").exists()
    for target in targets:
        root = target_root(target)
        left = remove_installer_skills(target, root, apm_owns, dry_run=True)
        if left:
            warnings.append(f"{target}: {', '.join(n for _, n, _ in left)} "
                            f"left by a pre-APM install in {root} — re-run "
                            f"install.py to remove")
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
    ap.add_argument("--force", action="store_true",
                    help="replace a ~/.apm/apm.yml install.py did not write")
    ap.add_argument("--status", action="store_true",
                    help="show what APM installed, graphify, and leftovers")
    ap.add_argument("--update", action="store_true",
                    help="list apm.yml pins with newer upstream releases "
                         "(apm outdated -g); bump them in apm.yml, re-run")
    ap.add_argument("--upgrade", action="store_true",
                    help="upgrade external CLIs (graphify) before refreshing "
                         "their skill files")
    ap.add_argument("--skills-only", action="store_true",
                    help="skip externals (graphify) — offline/proxy")
    args = ap.parse_args()
    targets = (["copilot", "claude"] if args.target == "both"
               else [args.target])

    if args.status:
        show_status(targets)
        return

    exe = find_cli("apm")
    if args.update:
        if not exe:
            sys.exit(APM_INSTALL_HINT)
        if args.dry_run:
            log("dry-run: would run apm outdated -g")
            return
        sys.exit(run_apm([exe, "outdated", "-g"]))
    if not exe and not args.dry_run:
        sys.exit(APM_INSTALL_HINT)

    manifest = render_user_manifest()
    # Refuse a foreign ~/.apm/apm.yml before anything is removed.
    write_user_manifest(manifest, args.force, dry_run=True)
    results = []
    apm_owns = (apm_home() / "apm.lock.yaml").exists()
    for target in targets:
        results.extend(remove_installer_skills(
            target, target_root(target), apm_owns, args.dry_run))
        results.extend(remove_legacy(target, target_root(target),
                                     args.dry_run))
        results.extend(retire_prompts(target, target_root(target),
                                      args.dry_run))
    if "copilot" in targets:
        results.extend(remove_instruction_copy(args.dry_run))
    results.append(("apm", "~/.apm/apm.yml", write_user_manifest(
        manifest, args.force, args.dry_run)))
    argv = apm_install_argv(exe or "apm", targets)
    if args.dry_run:
        if not exe:
            warn("apm is not installed — a real run stops here")
        results.append(("apm", "install",
                        "dry-run: would run " + " ".join(["apm", *argv[1:]])))
    else:
        code = run_apm(argv)
        if code:
            print_summary(results, targets, args.dry_run)
            sys.exit(code)
        results.append(("apm", "install", "done"))

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
            target, sel_externals, None, args.dry_run))

    print_summary(results, targets, args.dry_run)
    if is_wsl():
        log(WSL_HINT)


if __name__ == "__main__":
    main()
