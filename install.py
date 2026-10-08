#!/usr/bin/env python3
"""Install agent skills for GitHub Copilot and/or Claude Code.

Usage:
  python3 install.py --target claude
  python3 install.py --target copilot
  python3 install.py --target both --dry-run
  python3 install.py                # interactive: pick target + items
  python3 install.py --target claude --skills-only   # skip community fetch
  python3 install.py --repo .       # seed .github/skills
  python3 install.py --target both --upgrade   # newer graphify, then refresh
  python3 install.py --target claude --skill roj-code-review-pr  # cherry-pick
  python3 install.py --list         # what can be installed
  python3 install.py --add-inventory https://skills.sh/<owner>/<repo>/<skill>
  python3 install.py --check-inventory-updates
  python3 install.py --update       # latest pins + refresh what is installed

Python >= 3.8, standard library only.
Copilot gets copies; Claude gets per-skill symlinks (edit the repo, changes
are live). On filesystems without symlink support the installer falls back
to copying.

Two scopes. Personal scope (--target) writes to ~/.copilot/skills and
~/.claude/skills. Repo scope (--repo) writes copies into <repo>/.github/skills
for the whole team.

Any single skill also installs without this script, in any agent the
`skills` CLI supports: npx skills add r0jjames/agent-skills -s <name>. Every
skill directory is self-contained (tools/sync_shared.py keeps shared files
copied in), so nothing here is needed at runtime.

Earlier versions generated skills and Claude slash commands from prompts/.
That directory is gone; every install run removes what those versions
generated (see retire_prompts).

Skills come from three kinds of source: this repo (skills/), a community git
repo (SOURCES plus skills-inventory.json, sparse-cloned into
~/.agent-skills-cache; inventory repos at a pinned commit), and an external CLI
that installs its own skill (EXTERNALS — the installer bootstraps the CLI and
delegates). Externals need a package index, so --skills-only skips them, and
nothing about them auto-updates: --upgrade upgrades the CLI, and the same run
then re-copies the skill files the new version ships.
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
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent
SKILLS_SRC = REPO_ROOT / "skills"

BOTH = ("copilot", "claude")
# Also safe to vendor into a repo's .github/ for the whole team.
ANY = BOTH + ("repo",)

REPO_SKILLS_SUBDIR = Path(".github") / "skills"
REPO_PROMPTS_SUBDIR = Path(".github") / "prompts"

# Community sources, built from skills-inventory.json below. Per skill:
# targets it may install to, whether it is pre-selected (default) or an
# explicit cherry-pick, and an optional note shown when a target is skipped.
SOURCES = []

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


# Skills inventory: community skills picked from skills.sh, kept as data in
# skills-inventory.json rather than code. Each entry pins a commit, so an
# install is reproducible and a version bump is a reviewable diff. Entries
# from one GitHub repo become one source (one sparse clone) and must pin the
# same ref.
INVENTORY_PATH = REPO_ROOT / "skills-inventory.json"
INVENTORY_REQUIRED = ("source", "skill", "ref", "targets", "default")
INVENTORY_KEYS = set(INVENTORY_REQUIRED) | {"subdir", "folder", "note"}
_PART_RE = re.compile(r"[A-Za-z0-9_.-]+")
_SKILL_RE = re.compile(r"[a-z0-9][a-z0-9-]*")
_SHA_RE = re.compile(r"[0-9a-f]{40}")


class InventoryError(ValueError):
    """skills-inventory.json is malformed or clashes with a known name."""


def _safe_path(value, parts):
    """`value` is `parts` '/'-separated names (None = any number), none of
    them '.' or '..' — inventory values become URLs and cache paths."""
    split = str(value).split("/")
    return ((parts is None or len(split) == parts)
            and all(_PART_RE.fullmatch(s) and s not in (".", "..")
                    for s in split))


def load_inventory(path=None):
    """Validated entries of the inventory file; [] when there is none."""
    path = INVENTORY_PATH if path is None else Path(path)
    if not path.is_file():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except ValueError as e:
        raise InventoryError(f"{path.name}: not valid JSON ({e})")
    entries = data.get("skills") if isinstance(data, dict) else None
    if not isinstance(entries, list):
        raise InventoryError(f'{path.name}: expected {{"skills": [...]}}')
    seen = set()
    for i, entry in enumerate(entries, 1):
        where = f"{path.name} entry {i}"
        if not isinstance(entry, dict):
            raise InventoryError(f"{where}: expected an object")
        missing = [k for k in INVENTORY_REQUIRED if k not in entry]
        if missing:
            raise InventoryError(f"{where}: missing {', '.join(missing)}")
        unknown = sorted(set(entry) - INVENTORY_KEYS)
        if unknown:
            raise InventoryError(f"{where}: unknown key {', '.join(unknown)}")
        if not _safe_path(entry["source"], 2):
            raise InventoryError(f"{where}: source must be owner/repo")
        if "subdir" in entry and not _safe_path(entry["subdir"], None):
            raise InventoryError(f"{where}: subdir must be a relative path "
                                 f"inside the repo")
        if "folder" in entry and not _safe_path(entry["folder"], 1):
            raise InventoryError(f"{where}: folder must be one folder name")
        if not _SKILL_RE.fullmatch(str(entry["skill"])):
            raise InventoryError(f"{where}: skill must be lowercase-hyphen")
        if not _SHA_RE.fullmatch(str(entry["ref"])):
            raise InventoryError(f"{where}: ref must be a full 40-character "
                                 f"commit SHA")
        targets = entry["targets"]
        if (not isinstance(targets, list) or not targets
                or any(t not in ANY for t in targets)):
            raise InventoryError(f"{where}: targets must be a non-empty list "
                                 f"of {', '.join(ANY)}")
        if not isinstance(entry["default"], bool):
            raise InventoryError(f"{where}: default must be true or false")
        if entry["skill"] in seen:
            raise InventoryError(f"{where}: {entry['skill']} is listed twice")
        seen.add(entry["skill"])
    return entries


def inventory_sources(entries):
    """Inventory entries -> SOURCES-shaped dicts, one per GitHub repo."""
    by_repo = {}
    for entry in entries:
        repo = entry["source"]
        subdir = entry.get("subdir", "skills")
        source = by_repo.get(repo)
        if source is None:
            source = by_repo[repo] = {
                "label": repo,
                "url": f"https://github.com/{repo}.git",
                "ref": entry["ref"],
                "cache": repo.replace("/", "--"),
                "subdir": subdir,
                "fallback": (f"https://github.com/{repo}/tree/"
                             f"{entry['ref']}/{subdir}"),
                "inventory": True,
                "skills": {},
            }
        elif source["ref"] != entry["ref"] or source["subdir"] != subdir:
            raise InventoryError(f"{entry['skill']}: every {repo} entry must "
                                 f"pin the same ref and subdir")
        meta = {"targets": tuple(t for t in ANY if t in entry["targets"]),
                "default": entry["default"]}
        # skills.sh lists a skill by its frontmatter name; the folder it
        # lives in upstream may differ. Installs always use the name.
        if "folder" in entry:
            meta["folder"] = entry["folder"]
        if "note" in entry:
            meta["note"] = entry["note"]
        source["skills"][entry["skill"]] = meta
    return list(by_repo.values())


def check_inventory_names(sources, taken):
    """An inventory skill must not shadow a custom skill or an external:
    two sources for one directory name would overwrite each other."""
    for source in sources:
        for name in source["skills"]:
            if name in taken:
                raise InventoryError(
                    f"{name}: already a custom skill or external — "
                    f"remove it from {INVENTORY_PATH.name}")


def _inventory_sources():
    sources = inventory_sources(load_inventory())
    taken = ({p.name for p in SKILLS_SRC.iterdir() if p.is_dir()}
             | {e["name"] for e in EXTERNALS})
    check_inventory_names(sources, taken)
    return sources


try:
    SOURCES.extend(_inventory_sources())
except InventoryError as e:
    if __name__ != "__main__":
        raise
    sys.exit(f"install.py: {e}")


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


def registry():
    """{skill_name: (source, meta)} across all sources."""
    return {name: (source, meta)
            for source in SOURCES
            for name, meta in source["skills"].items()}


def source_by_label(label):
    return next(s for s in SOURCES if s["label"] == label)


def source_skills_subdir(source):
    """Directory inside a source's cache that holds its skill folders."""
    return source.get("subdir", "skills")


def all_community_names():
    return set(registry())


def default_community_names():
    return {n for n, (_, meta) in registry().items() if meta["default"]}




def required_by(skills, requires=None):
    """{name: [dependents]} for everything `skills` need, following custom
    skills that declare requirements of their own."""
    requires = REQUIRES if requires is None else requires
    out = {}
    queue = sorted(skills)
    seen = set(queue)
    while queue:
        skill = queue.pop(0)
        for dep in requires.get(skill, ()):
            out.setdefault(dep, []).append(skill)
            if dep not in seen:
                seen.add(dep)
                queue.append(dep)
    return out


def add_requirements(custom_names, sel_community, sel_externals,
                     requires=None):
    """Grow the three selections by what the selected custom skills need.
    Returns new (custom_names, sel_community, sel_externals) sets and logs
    each addition, so an item unticked in the picker coming back is
    explained."""
    custom_names = set(custom_names)
    sel_community = set(sel_community)
    sel_externals = set(sel_externals)
    pools = ((all_community_names(), sel_community),
             (all_external_names(), sel_externals),
             (custom_skill_names(), custom_names))
    for name, dependents in sorted(required_by(custom_names,
                                               requires).items()):
        for known, selected in pools:
            if name in known:
                if name not in selected:
                    selected.add(name)
                    log(f"{name} (required by {', '.join(dependents)})")
                break
    return custom_names, sel_community, sel_externals


def _present(dest_root, name):
    path = Path(dest_root) / name
    return path.is_symlink() or path.exists()


def missing_requirements(dest_root, requires=None):
    """[(skill, requirement)] for skills installed in dest_root whose
    requirements are not installed there."""
    requires = REQUIRES if requires is None else requires
    missing = []
    for skill in sorted(requires):
        if not _present(dest_root, skill):
            continue
        for dep in sorted(required_by([skill], requires)):
            if not _present(dest_root, dep):
                missing.append((skill, dep))
    return missing


def uninstall_dependents(names, dest_root, requires=None):
    """[(requirement, dependent)] for skills about to be removed from
    dest_root that a skill staying there still requires."""
    requires = REQUIRES if requires is None else requires
    removing = set(names)
    hits = []
    for skill in sorted(requires):
        if skill in removing or not _present(dest_root, skill):
            continue
        for dep in sorted(required_by([skill], requires)):
            if dep in removing and _present(dest_root, dep):
                hits.append((dep, skill))
    return hits


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


_SYMLINK_SUPPORT = {}


def symlinks_supported(directory):
    """Cached probe: can we create a symlink inside `directory`? Windows
    needs Developer Mode or admin, so this is False on most work machines.
    Probing up front avoids the backup-then-fail-then-copy cycle, which
    otherwise left a stale <skill>.bak dir behind on every run."""
    directory = Path(directory)
    key = str(directory)
    if key not in _SYMLINK_SUPPORT:
        directory.mkdir(parents=True, exist_ok=True)
        probe = directory / ".symlink-probe"
        try:
            if probe.is_symlink() or probe.exists():
                probe.unlink()
            probe.symlink_to(directory, target_is_directory=True)
            probe.unlink()
            _SYMLINK_SUPPORT[key] = True
        except OSError:
            warn(f"symlinks unsupported in {directory} — installing copies "
                 "(re-run install.py after editing a skill to refresh)")
            _SYMLINK_SUPPORT[key] = False
    return _SYMLINK_SUPPORT[key]


def install_symlink(src, dest, dry_run):
    """Symlink dest -> src. Returns 'linked'|'already linked' or a copy
    status suffixed with ' (copy fallback)' when symlinks are unsupported."""
    src, dest = Path(src), Path(dest)
    if not dry_run and not symlinks_supported(dest.parent):
        return install_copy(src, dest, dry_run) + " (copy fallback)"
    if dest.is_symlink():
        if dest.resolve() == src.resolve():
            return "already linked"
        if not dry_run:
            dest.unlink()  # wrong or broken link: replace
    elif dest.exists():
        backup = dest.parent / (dest.name + ".bak")
        if not dry_run:
            if backup.is_symlink() or backup.is_file():
                backup.unlink()
            elif backup.is_dir():
                shutil.rmtree(backup)
            dest.rename(backup)
            log(f"backed up existing {dest.name} to {backup.name}")
    if dry_run:
        return "linked"
    dest.parent.mkdir(parents=True, exist_ok=True)
    try:
        dest.symlink_to(src, target_is_directory=True)
        return "linked"
    except OSError:
        warn(f"symlink unsupported for {dest} — copying instead "
             "(re-run install.py after edits to refresh)")
        return install_copy(src, dest, dry_run=False) + " (copy fallback)"


def resolve_repo(path):
    """Validate a --repo value. Exits when it is not a directory; warns but
    proceeds when it has no .git (a worktree's .git is a file, not a dir)."""
    repo = Path(path).expanduser().resolve()
    if not repo.is_dir():
        sys.exit(f"--repo {path}: not a directory")
    if repo == REPO_ROOT or repo == REPO_ROOT.parent:
        warn(f"{repo} is the dotfiles repo itself — seeding it anyway")
    elif not (repo / ".git").exists():
        warn(f"{repo} has no .git — seeding .github/ there anyway")
    return repo


def target_root(target, repo=None):
    if target == "repo":
        return Path(repo) / REPO_SKILLS_SUBDIR
    return Path.home() / (".copilot" if target == "copilot"
                          else ".claude") / "skills"


def pick_targets(arg_target, repo=None):
    """Resolve --target value (or interactive menu) to a list of targets.
    --repo appends the 'repo' pseudo-target and suppresses the menu."""
    targets = []
    if arg_target:
        targets = (["copilot", "claude"] if arg_target == "both"
                   else [arg_target])
    elif not repo:
        print("Install skills for:")
        print("  1) GitHub Copilot   (~/.copilot/skills)")
        print("  2) Claude Code      (~/.claude/skills, symlinked)")
        print("  3) Both")
        choice = input("Choice [1-3]: ").strip()
        targets = {"1": ["copilot"], "2": ["claude"],
                   "3": ["copilot", "claude"]}.get(choice)
        if not targets:
            sys.exit("Invalid choice — run again or pass --target.")
    if repo:
        targets = targets + ["repo"]
    return targets


def status_targets(arg_target, repo):
    """Target list for --status. Never prompts."""
    if arg_target:
        base = ["copilot", "claude"] if arg_target == "both" else [arg_target]
    else:
        base = [] if repo else ["copilot", "claude"]
    return base + (["repo"] if repo else [])


def build_items(custom_skills):
    """Ordered installable items as (kind, name): custom skills, community
    skills, then CLI-installed externals."""
    items = [("skill", n) for n in custom_skills]
    items += [("community", n) for n in sorted(all_community_names())]
    items += [("external", n) for n in sorted(all_external_names())]
    return items


def item_tag(kind, name, targets, plugin_map):
    """Picker annotation: [installed] [update] [conflict], or ''."""
    tags = []
    reg = registry()
    for target in targets:
        dest = target_root(target) / name
        if not (dest.is_symlink() or dest.exists()):
            continue
        tags.append("[installed]")
        src = None
        if kind == "skill":
            src = SKILLS_SRC / name
        elif name in reg:
            source = reg[name][0]
            cand = (source_cache_dir(source)
                    / source_skills_subdir(source) / name)
            if cand.is_dir():
                src = cand
        if (src and src.is_dir() and not dest.is_symlink()
                and dest.is_dir() and not dirs_equal(src, dest)):
            tags.append("[update]")
        break
    if "claude" in targets and name in plugin_map:
        tags.append("[conflict]")
    return " ".join(tags)


def pick_items(items, preselected=None, tags=None):
    """Interactive toggle menu over (kind, name) items. preselected:
    optional bool list (default all True). tags: optional
    {(kind, name): str} shown after the item."""
    selected = (list(preselected) if preselected is not None
                else [True] * len(items))
    tags = tags or {}
    while True:
        print("\nSelect items to install:")
        for i, ((kind, name), on) in enumerate(zip(items, selected), 1):
            tag = tags.get((kind, name), "")
            suffix = f"  {tag}" if tag else ""
            print(f"  [{'x' if on else ' '}] {i:2}) {kind:9} {name}{suffix}")
        raw = input("Toggle number, 'a' = all, enter = confirm: ").strip().lower()
        if raw == "":
            chosen = [item for item, on in zip(items, selected) if on]
            if not chosen:
                sys.exit("Nothing selected — exiting without changes.")
            return chosen
        if raw == "a":
            value = not all(selected)
            selected = [value] * len(items)
        elif raw.isdigit() and 1 <= int(raw) <= len(items):
            idx = int(raw) - 1
            selected[idx] = not selected[idx]
        else:
            print("Invalid input.")


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
    generated skill dir left by install_symlink's backup. Only regular files
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


CACHE_ROOT = Path.home() / ".agent-skills-cache"
# Cache dirs from before skills-inventory.json, when each source had a
# hand-picked name. Every non-dry install run removes them once.
LEGACY_CACHES = ("awesome-copilot", "caveman", "addy-agent-skills",
                 "warp-common-skills", "anthropics-skills")


def source_cache_dir(source):
    return CACHE_ROOT / source["cache"]


def remove_legacy_caches(dry_run):
    for name in LEGACY_CACHES:
        cache = CACHE_ROOT / name
        if (cache / ".git").is_dir():
            if dry_run:
                log(f"dry-run: would remove old cache {cache}")
            else:
                shutil.rmtree(cache, ignore_errors=True)
                log(f"Removed old cache {cache} (now pinned per repo)")


def skill_folder(source, name):
    """Upstream folder of a source's skill (inventory entries may differ
    from the installed name)."""
    return source["skills"][name].get("folder", name)


def update_source_cache(source, dry_run, names=None):
    names = sorted(names) if names else sorted(source["skills"])
    subdir = source_skills_subdir(source)
    return update_repo_cache(
        source_cache_dir(source), source["url"], source["ref"],
        [f"{subdir}/{skill_folder(source, n)}" for n in names], dry_run,
        source["label"], source["fallback"], skills_subdir=subdir)


def run_git(args):
    subprocess.run(["git", *args], check=True)


def git_head(cache):
    """Commit a cache is checked out at, or None when it cannot be read."""
    try:
        out = subprocess.run(["git", "-C", str(cache), "rev-parse", "HEAD"],
                             check=True, capture_output=True, text=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None
    return out.stdout.strip()


def fetch_pinned(cache, url, ref, sparse, label):
    """Check out exactly `ref` in a sparse cache, whatever the branch says."""
    if (cache / ".git").is_dir():
        log(f"Updating {label} cache (pinned {ref[:7]})...")
    else:
        log(f"Cloning {label} (sparse, pinned {ref[:7]})...")
        cache.parent.mkdir(parents=True, exist_ok=True)
        run_git(["clone", "--depth", "1", "--filter=blob:none", "--sparse",
                 "--no-checkout", url, str(cache)])
    run_git(["-C", str(cache), "sparse-checkout", "set", *sparse])
    run_git(["-C", str(cache), "fetch", "--depth", "1", "origin", ref])
    run_git(["-C", str(cache), "reset", "--hard", "FETCH_HEAD"])


def update_repo_cache(cache, url, ref, sparse, dry_run, label,
                      fallback_url, skills_subdir="skills"):
    """Sparse-clone/refresh a skills repo at the pinned commit `ref`.
    Returns the cache path, or None when no usable cache exists.
    skills_subdir: where the skill folders live inside the repo."""
    skills_dir = cache / skills_subdir
    if dry_run:
        log(f"dry-run: would fetch {url} at {ref[:7]} into {cache}")
        return cache if skills_dir.is_dir() else None
    try:
        fetch_pinned(cache, url, ref, sparse, label)
        ok(f"{label} cache ready")
        return cache
    except (subprocess.CalledProcessError, FileNotFoundError):
        warn(f"Could not clone/update {label} (offline? proxy?).")
        if not skills_dir.is_dir():
            warn(f"Fallback: download the skill folders as ZIP from "
                 f"{fallback_url}")
            warn(f"and unzip into {skills_dir}, then re-run this script.")
            return None
        if git_head(cache) != ref:
            warn(f"Existing {label} cache is not at the pinned "
                 f"{ref[:7]} — skipped rather than install another version.")
            return None
        warn("Using existing local cache instead.")
        return cache


def remote_head(url):
    """Tip commit of a remote's default branch, or None when unreachable."""
    try:
        out = subprocess.run(["git", "ls-remote", url, "HEAD"], check=True,
                             capture_output=True, text=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None
    fields = out.stdout.split()
    return fields[0] if fields else None


def check_inventory_updates(sources=None):
    """Report inventory sources whose upstream moved past the pinned ref.
    Never installs; returns how many are behind."""
    sources = [s for s in (SOURCES if sources is None else sources)
               if s.get("inventory")]
    if not sources:
        log(f"No skills in {INVENTORY_PATH.name}")
        return 0
    behind = 0
    for source in sources:
        label, ref = source["label"], source["ref"]
        names = ", ".join(sorted(source["skills"]))
        head = remote_head(source["url"])
        if head is None:
            warn(f"{label} ({names}): upstream unreachable (offline? proxy?)")
        elif head == ref:
            ok(f"{label} ({names}): up to date at {ref[:7]}")
        else:
            behind += 1
            warn(f"{label} ({names}): pinned {ref[:7]}, upstream {head[:7]}")
            warn(f"  review https://github.com/{label}/compare/{ref[:12]}..."
                 f"{head[:12]}, then bump ref in {INVENTORY_PATH.name}")
    return behind


_SKILLS_SH_RE = re.compile(r"https?://(?:www\.)?skills\.sh/"
                           r"([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+)/"
                           r"([a-z0-9][a-z0-9-]*)/?")
_CLI_SPEC_RE = re.compile(r"([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+)@"
                          r"([a-z0-9][a-z0-9-]*)")
def parse_skill_spec(spec):
    """skills.sh URL or owner/repo@skill -> ("owner/repo", "skill")."""
    spec = spec.strip()
    for pattern in (_SKILLS_SH_RE, _CLI_SPEC_RE):
        m = pattern.fullmatch(spec)
        if m and _safe_path(f"{m[1]}/{m[2]}", 2):
            return f"{m[1]}/{m[2]}", m[3]
    raise InventoryError(f"{spec}: expected https://skills.sh/owner/repo/"
                         f"skill or owner/repo@skill")


def frontmatter_name(text):
    """`name` from a SKILL.md frontmatter block, or None."""
    parts = text.split("---", 2)
    if len(parts) < 3:
        return None
    for line in parts[1].splitlines():
        key, _, value = line.partition(":")
        if key.strip() == "name":
            return value.strip().strip("'\"")
    return None


def with_remote_tree(repo, ref, fn):
    """fn(paths, read) against repo at ref, without a checkout: paths are
    its SKILL.md files, shallowest first; read(path) returns a file's text
    (blobs are fetched on demand)."""
    def git(*args):
        return subprocess.run(["git", "-C", tmp, *args], check=True,
                              capture_output=True, text=True).stdout

    with tempfile.TemporaryDirectory() as tmp:
        try:
            git("init", "-q")
            git("remote", "add", "origin", f"https://github.com/{repo}.git")
            git("fetch", "-q", "--depth", "1", "--filter=blob:none",
                "origin", ref)
            paths = sorted((p for p in git("ls-tree", "-r", "--name-only",
                                           "FETCH_HEAD").splitlines()
                            if p.endswith("/SKILL.md")),
                           key=lambda p: (p.count("/"), p))
            return fn(paths, lambda p: git("show", f"FETCH_HEAD:{p}"))
        except (subprocess.CalledProcessError, FileNotFoundError):
            raise InventoryError(f"{repo}: could not fetch {ref[:7]} "
                                 f"(offline? proxy?)")


def locate_skill(repo, ref, skill):
    """(subdir, folder) of the skill skills.sh calls `skill` in repo at
    ref. A folder named after the skill wins; otherwise the SKILL.md whose
    frontmatter name matches, since skills.sh lists skills by that name."""
    def pick(paths, read):
        return (next((p for p in paths if Path(p).parent.name == skill), None)
                or next((p for p in paths
                         if frontmatter_name(read(p)) == skill), None))

    found = with_remote_tree(repo, ref, pick)
    if found is None:
        raise InventoryError(f"{skill}: no SKILL.md named {skill} in {repo} "
                             f"at {ref[:7]}")
    folder = Path(found).parent
    if str(folder.parent) == ".":
        raise InventoryError(f"{skill}: lives at the root of {repo} — "
                             f"top-level skill folders are not supported")
    return folder.parent.as_posix(), folder.name


def add_inventory(spec, path=None, dry_run=False):
    """Append a skills.sh skill to the inventory, pinned to the upstream
    tip (or to the ref its repo is already pinned at). Returns the entry."""
    path = INVENTORY_PATH if path is None else Path(path)
    repo, skill = parse_skill_spec(spec)
    entries = load_inventory(path)
    if any(e["skill"] == skill for e in entries):
        raise InventoryError(f"{skill} is already in {path.name}")
    if skill in custom_skill_names() | all_external_names():
        raise InventoryError(f"{skill}: already a custom skill or external "
                             f"— install it with --skill")
    same_repo = [e for e in entries if e["source"] == repo]
    if same_repo:
        ref = same_repo[0]["ref"]
        log(f"{repo} is already pinned at {ref[:7]} — reusing that ref")
    else:
        ref = remote_head(f"https://github.com/{repo}.git")
        if not ref:
            raise InventoryError(f"{repo}: upstream unreachable (offline? "
                                 f"proxy? typo?)")
    subdir, folder = locate_skill(repo, ref, skill)
    if same_repo and same_repo[0].get("subdir", "skills") != subdir:
        raise InventoryError(f"{skill}: lives in {subdir}/, but {repo} is "
                             f"pinned with another subdir — one subdir per "
                             f"repo")
    # Not default: every installed description loads into every session.
    entry = {"source": repo, "skill": skill, "ref": ref,
             "targets": ["claude", "copilot"], "default": False}
    if subdir != "skills":
        entry["subdir"] = subdir
    if folder != skill:
        entry["folder"] = folder
    if dry_run:
        log(f"dry-run: would add {json.dumps(entry)} to {path.name}")
        return entry
    path.write_text(json.dumps({"skills": entries + [entry]}, indent=2)
                    + "\n", encoding="utf-8")
    ok(f"Added {skill} ({repo} @ {ref[:7]}) to {path.name}")
    log(f"Next: review https://github.com/{repo}/blob/{ref}/{subdir}/"
        f"{folder}/SKILL.md, add a '## {skill}' section to "
        f"docs/community-skills.md, then commit")
    return entry


def bump_inventory(path=None, dry_run=False):
    """Move every inventory repo's pin to its upstream tip. A repo whose
    new commit lost one of our skills keeps its pin. Writes the file unless
    dry_run; returns (entries, [(repo, old, new), ...])."""
    path = INVENTORY_PATH if path is None else Path(path)
    entries = load_inventory(path)
    bumped = []
    for source in inventory_sources(entries):
        repo, old = source["label"], source["ref"]
        new = remote_head(source["url"])
        if new is None:
            warn(f"{repo}: upstream unreachable — kept at {old[:7]}")
            continue
        if new == old:
            ok(f"{repo}: up to date at {old[:7]}")
            continue
        subdir = source_skills_subdir(source)
        try:
            present = with_remote_tree(repo, new,
                                       lambda paths, read: set(paths))
        except InventoryError as e:
            warn(f"{e} — kept at {old[:7]}")
            continue
        gone = sorted(n for n in source["skills"]
                      if f"{subdir}/{skill_folder(source, n)}/SKILL.md"
                      not in present)
        if gone:
            warn(f"{repo}: {', '.join(gone)} no longer at {subdir}/ in "
                 f"{new[:7]} — kept at {old[:7]}; check upstream")
            continue
        for entry in entries:
            if entry["source"] == repo:
                entry["ref"] = new
        bumped.append((repo, old, new))
        log(f"{repo}: {old[:7]} -> {new[:7]}  https://github.com/{repo}/"
            f"compare/{old[:12]}...{new[:12]}")
    if bumped and not dry_run:
        path.write_text(json.dumps({"skills": entries}, indent=2) + "\n",
                        encoding="utf-8")
        ok(f"{path.name}: {len(bumped)} repo(s) bumped — review "
           f"`git diff {path.name}` and commit, so other machines get the "
           f"same versions")
    return entries, bumped


def check_checkout_current(root=None):
    """Warn when this agent-skills checkout is behind its upstream branch.
    Reads only; never pulls. Returns 'current', 'ahead', 'behind' or None
    when it cannot tell (no upstream, offline)."""
    root = str(REPO_ROOT if root is None else root)

    def git(*args):
        return subprocess.run(["git", "-C", root, *args], check=True,
                              capture_output=True, text=True).stdout.strip()

    try:
        upstream = git("rev-parse", "--abbrev-ref", "--symbolic-full-name",
                       "@{u}")
    except (subprocess.CalledProcessError, FileNotFoundError):
        log("agent-skills checkout tracks no branch (pinned?) — not "
            "checking for newer custom skills")
        return None
    remote, _, branch = upstream.partition("/")
    try:
        tip = git("ls-remote", remote, f"refs/heads/{branch}").split()[0]
        head = git("rev-parse", "HEAD")
    except (subprocess.CalledProcessError, FileNotFoundError, IndexError):
        warn(f"could not reach {upstream} — not checking for newer custom "
             f"skills")
        return None
    if tip == head:
        ok(f"agent-skills checkout is current with {upstream}")
        return "current"
    try:
        git("merge-base", "--is-ancestor", tip, "HEAD")
        return "ahead"
    except subprocess.CalledProcessError:
        warn(f"agent-skills checkout is behind {upstream}: run "
             f"`git -C {root} pull` for the latest custom skills, then "
             f"--update again")
        return "behind"


def installed_names(dest_root):
    """Directory names in a target root (what --update refreshes)."""
    if not dest_root.is_dir():
        return set()
    return {p.name for p in dest_root.iterdir()
            if p.is_dir() or p.is_symlink()}


def install_community_for_target(target, dest_root, sel_community, dry_run):
    """Install selected community skills for one target, honoring each
    skill's target policy. Sources carry their fetched cache under
    '_cache' (None = fetch failed or skipped)."""
    results = []
    for source in SOURCES:
        cache = source.get("_cache")
        for name, meta in source["skills"].items():
            if name not in sel_community:
                continue
            if target not in meta["targets"]:
                # The per-skill note explains a personal-scope exclusion; for
                # repo scope it would be misleading.
                note = (meta.get("note") if target in BOTH else None)
                results.append((target, name,
                                f"skipped ({note or 'not for ' + target})"))
                continue
            if not cache:
                continue
            src = (cache / source_skills_subdir(source)
                   / skill_folder(source, name))
            if not src.is_dir():
                results.append((target, name, "missing in cache — skipped"))
                continue
            results.append((target, name,
                            install_copy(src, dest_root / name, dry_run)))
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
    with tempfile.TemporaryDirectory() as scratch:
        cwd = repo if (target == "repo" and ext.get("repo_cwd")) else scratch
        if not run_cli(argv, cwd):
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


def uninstall_externals(names, target, dry_run):
    """Hand personal-scope removal back to the external's own CLI. Repo scope
    is a plain directory, so uninstall_skills handles it instead."""
    results = []
    if target == "repo":
        return results
    for ext in EXTERNALS:
        name = ext["name"]
        argv_tail = ext["uninstall"].get(target)
        if name not in names or not argv_tail or target not in ext["targets"]:
            continue
        dest = target_root(target) / name
        exe = find_cli(ext["cli"])
        if not exe:
            if not dest.exists():
                results.append((target, name, "not installed"))
            else:
                if not dry_run:
                    shutil.rmtree(dest)
                results.append((target, name, "removed (no CLI — dir only)"))
            continue
        if dry_run:
            results.append((target, name, "dry-run: would run "
                            f"{' '.join([ext['cli'], *argv_tail])}"))
            continue
        with tempfile.TemporaryDirectory() as scratch:
            done = run_cli([exe, *argv_tail], scratch)
        results.append((target, name, "removed (by CLI)" if done else "failed"))
    return results


def enabled_plugins(settings_path=None):
    settings_path = settings_path or (Path.home() / ".claude"
                                      / "settings.json")
    try:
        data = json.loads(Path(settings_path).read_text())
    except (OSError, ValueError):
        return {}
    plugins = data.get("enabledPlugins") or {}
    return {k: True for k, v in plugins.items() if v}


def plugin_skills(cache_root=None, settings_path=None):
    """{skill_name: plugin_id} across enabled Claude plugins (any cached
    version). Empty dict when config or cache is absent."""
    cache_root = Path(cache_root or Path.home() / ".claude" / "plugins"
                      / "cache")
    out = {}
    for plugin_id in enabled_plugins(settings_path):
        name, _, marketplace = plugin_id.partition("@")
        plugin_dir = cache_root / marketplace / name
        if not plugin_dir.is_dir():
            continue
        for version in plugin_dir.iterdir():
            skills_dir = version / "skills"
            if not skills_dir.is_dir():
                continue
            for entry in skills_dir.iterdir():
                if entry.is_dir():
                    out[entry.name] = plugin_id
    return out


def gather_status(target, dest_root, custom_names, plugin_map):
    """Classify installed skills in dest_root. Returns (rows, warnings);
    row = (name, kind, mechanism)."""
    reg = registry()
    ext_map = externals()
    rows, warnings = [], []
    if not dest_root.is_dir():
        return rows, warnings
    for entry in sorted(dest_root.iterdir()):
        if not (entry.is_dir() or entry.is_symlink()):
            continue
        name = entry.name
        if name.endswith(".bak"):
            warnings.append(f"{target}: {name} is a leftover backup — agents"
                            f" load it as a skill; delete it")
        if name not in custom_names and is_generated(entry):
            kind = "retired prompt (stale)"
            warnings.append(f"{target}: {name} was generated from a retired "
                            f"prompt — re-run install.py to remove it")
        elif name in custom_names:
            kind = "custom"
        elif name in reg:
            kind = f"community ({reg[name][0]['label']})"
        elif name in ext_map:
            version = external_version(entry, ext_map[name])
            kind = f"external ({ext_map[name]['package']}" + (
                f" {version})" if version else ")")
            cli = ext_map[name]["cli"]
            if not find_cli(cli):
                warnings.append(f"{target}: {name} skill is installed but its "
                                f"{cli} CLI is missing — the skill cannot run")
            else:
                hint = cli_path_hint(ext_map[name])
                if hint:
                    warnings.append(f"{target}: {hint}")
        else:
            kind = "unknown"
        mech = "symlink" if entry.is_symlink() else "copy"
        rows.append((name, kind, mech))
        if entry.is_symlink() and not entry.exists():
            warnings.append(f"{target}: {name} is a broken symlink")
        if name in reg and target not in reg[name][1]["targets"]:
            note = reg[name][1].get("note", "wrong target")
            warnings.append(f"{target}: {name} not meant for this target"
                            f" — {note}")
        if target == "claude" and name in plugin_map:
            warnings.append(f"claude: {name} also provided by enabled"
                            f" plugin {plugin_map[name]} — remove the"
                            f" skills-dir copy")
    for skill, dep in missing_requirements(dest_root):
        warnings.append(f"{target}: {skill} requires {dep}, which is not "
                        f"installed here — re-run install.py")
    return rows, warnings


def show_status(targets, repo=None):
    custom_names = custom_skill_names()
    plugin_map = plugin_skills()
    all_warnings = []
    for target in targets:
        dest_root = target_root(target, repo)
        print(f"\n{target}: {dest_root}")
        rows, warnings = gather_status(target, dest_root, custom_names,
                                       plugin_map)
        if not rows:
            print("  (nothing installed)")
        for name, kind, mech in rows:
            print(f"  {name:35} {kind:32} {mech}")
        leftovers = [n for _, n, _ in retire_prompts(
            target, dest_root, dry_run=True, repo=repo)
            if n.startswith(("prompt:", "command:"))]
        if leftovers:
            warnings.append(f"{target}: {len(leftovers)} file(s) left by the "
                            f"retired prompts ({', '.join(leftovers)}) — "
                            f"re-run install.py to remove them")
        all_warnings.extend(warnings)
    print()
    if all_warnings:
        for w in all_warnings:
            warn(w)
    else:
        ok("no conflicts detected")


def skill_description(skill_dir):
    """First sentence of a SKILL.md description, for --list."""
    try:
        text = (Path(skill_dir) / "SKILL.md").read_text(encoding="utf-8")
    except OSError:
        return ""
    parts = text.split("---", 2)
    if len(parts) < 3:
        return ""
    for line in parts[1].splitlines():
        key, _, value = line.partition(":")
        if key.strip() == "description":
            value = value.strip().strip("'\"")
            return value.split(". ")[0].rstrip(".") + "."
    return ""


def show_list():
    """Everything an install can select, grouped by kind."""
    print("Custom skills (this repo):")
    for name in sorted(custom_skill_names()):
        print(f"  {name:34} {skill_description(SKILLS_SRC / name)}")
    print("\nCommunity skills (* = installed by default):")
    for name, (source, meta) in sorted(registry().items()):
        mark = "*" if meta["default"] else " "
        targets = ",".join(t for t in ANY if t in meta["targets"])
        print(f"  {mark} {name:33} {source['label']} [{targets}]")
    print("\nExternals (installed by their own CLI):")
    for ext in EXTERNALS:
        mark = "*" if ext["default"] else " "
        print(f"  {mark} {ext['name']:33} {ext['doc']}")
    print("\nRequirements (installed alongside):")
    for skill, deps in sorted(REQUIRES.items()):
        print(f"  {skill:34} -> {', '.join(deps)}")
    print("\nAny agent, without this script: "
          "npx skills add r0jjames/agent-skills -s <name>")


def resolve_skill_args(raw):
    """--skill value -> (custom names, community names, external names).
    Exits on a name no source knows, listing what exists."""
    names = [n.strip() for n in raw.split(",") if n.strip()]
    custom, community, ext = (custom_skill_names(), all_community_names(),
                              all_external_names())
    unknown = [n for n in names if n not in custom | community | ext]
    if unknown:
        sys.exit(f"--skill: unknown {', '.join(unknown)} — run "
                 f"'install.py --list' to see what can be installed")
    return ({n for n in names if n in custom},
            {n for n in names if n in community},
            {n for n in names if n in ext})


def uninstall_skills(names, target, dest_root, known_names, force, dry_run):
    results = []
    for name in names:
        path = dest_root / name
        if not (path.is_symlink() or path.exists()):
            results.append((target, name, "not installed"))
            continue
        if name not in known_names and not force:
            results.append((target, name, "unknown — use --force"))
            continue
        if path.is_symlink():
            if not dry_run:
                path.unlink()
            results.append((target, name, "removed (symlink)"))
        else:
            if not dry_run:
                shutil.rmtree(path)
            results.append((target, name, "removed"))
    return results


def print_summary(results, targets, dry_run):
    print()
    title = "Planned actions (dry run)" if dry_run else "Install summary"
    log(title + ":")
    for target, name, status in results:
        print(f"  {target:8} {name:35} {status}")
    print()
    if "copilot" in targets:
        log("Verify Copilot:  /skills list  in Copilot CLI, or ask VS Code "
            "agent mode 'What skills do you have available?'")
    if "claude" in targets:
        log("Verify Claude:   ask 'what skills are available?' in a new "
            "claude session")
    ext_map = externals()
    touched = {name for _, name, status in results
               if name in ext_map and not status.startswith("skipped")}
    for name in sorted(touched):
        ext = ext_map[name]
        log(f"Verify {name}:  run '{ext['cli']} --version', then "
            f"'/{name} .' in the agent — {ext['doc']}")
        # Last thing printed, so a PATH problem cannot scroll out of view.
        hint = cli_path_hint(ext)
        if hint and not dry_run:
            warn(hint)
    if "repo" in targets:
        log("Verify JetBrains: reopen the project, Copilot Chat -> Agent "
            "mode, type '/skill:' — the repo's skills list there")
        log("These files are tracked by git — PR them for the team, or keep "
            "them local with: echo .github/ >> .git/info/exclude")


def main():
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--target", choices=["copilot", "claude", "both"],
                    help="where to install (omit for interactive menu)")
    ap.add_argument("--skills-only", action="store_true",
                    help="skip community skills and CLI-installed externals "
                         "(offline/proxy)")
    ap.add_argument("--upgrade", action="store_true",
                    help="upgrade external CLIs (graphify) to the latest "
                         "release before refreshing their skill files")
    ap.add_argument("--dry-run", action="store_true",
                    help="print planned actions without writing anything")
    ap.add_argument("--status", action="store_true",
                    help="show installed skills per target and conflicts")
    ap.add_argument("--uninstall", metavar="NAME[,NAME...]",
                    help="remove skills from the target")
    ap.add_argument("--force", action="store_true",
                    help="allow --uninstall of names the installer does "
                         "not know")
    ap.add_argument("--skill", "-s", metavar="NAME[,NAME...]",
                    help="install only these skills (custom, community or "
                         "external) plus what they require — no picker")
    ap.add_argument("--list", action="store_true",
                    help="list every installable skill and exit")
    ap.add_argument("--repo", metavar="PATH",
                    help="also seed <PATH>/.github/skills (repo scope, "
                         "shareable with the team)")
    ap.add_argument("--add-inventory", metavar="URL|OWNER/REPO@SKILL",
                    help="add a skills.sh skill to skills-inventory.json, "
                         "pinned to its current upstream commit")
    ap.add_argument("--update", action="store_true",
                    help="bump every skills-inventory.json pin to upstream, "
                         "then refresh only the skills already installed "
                         "(and upgrade their external CLIs)")
    ap.add_argument("--check-inventory-updates", action="store_true",
                    help="list inventory skills whose upstream moved past "
                         "the pinned commit (installs nothing)")
    args = ap.parse_args()
    repo = resolve_repo(args.repo) if args.repo else None

    if args.add_inventory:
        try:
            add_inventory(args.add_inventory, dry_run=args.dry_run)
        except InventoryError as e:
            sys.exit(f"--add-inventory: {e}")
        return

    if args.check_inventory_updates:
        check_inventory_updates()
        return

    if args.list:
        show_list()
        return

    if args.status:
        show_status(status_targets(args.target, repo), repo)
        return

    if args.uninstall:
        targets = pick_targets(args.target, repo)
        names = [n.strip() for n in args.uninstall.split(",") if n.strip()]
        known = (custom_skill_names() | all_community_names()
                 | all_external_names())
        for n in [n for n in names if n.startswith("prompt:")]:
            warn(f"{n}: prompts were retired — every install run removes "
                 f"what they generated")
        names = [n for n in names if not n.startswith("prompt:")]
        results = []
        for target in targets:
            for dep, skill in uninstall_dependents(
                    names, target_root(target, repo)):
                warn(f"{target}: removing {dep}, but {skill} still requires "
                     f"it — {skill} will run on its fallback")
            # Externals are removed by their own CLI in personal scope; in
            # repo scope they are ordinary copied directories.
            ext_names = [n for n in names if n in all_external_names()]
            results.extend(uninstall_externals(ext_names, target,
                                               args.dry_run))
            skills = [n for n in names
                      if target == "repo" or n not in ext_names]
            results.extend(uninstall_skills(
                skills, target, target_root(target, repo), known,
                args.force, args.dry_run))
        print_summary(results, targets, args.dry_run)
        return

    interactive = (args.target is None and repo is None and not args.skill
                   and not args.update)
    if args.update:
        # Refresh what is there; never prompts, never installs anything new.
        targets = status_targets(args.target, repo)
        args.upgrade = not args.skills_only
        check_checkout_current()
        if args.skills_only:
            log("--skills-only: inventory pins left as they are")
        else:
            try:
                entries, _ = bump_inventory(dry_run=args.dry_run)
                SOURCES[:] = inventory_sources(entries)
            except InventoryError as e:
                sys.exit(f"--update: {e}")
        present = {t: installed_names(target_root(t, repo)) for t in targets}
    else:
        targets = pick_targets(args.target, repo)
        present = None
    custom = sorted(p for p in SKILLS_SRC.iterdir() if p.is_dir())
    if not custom:
        sys.exit(f"No skills found in {SKILLS_SRC}")

    if interactive:
        items = build_items([p.name for p in custom])
        reg = registry()
        ext_map = externals()
        plugin_map = plugin_skills()
        preselected = [reg[n][1]["default"] if k == "community"
                       else ext_map[n]["default"] if k == "external"
                       else True
                       for k, n in items]
        tags = {(k, n): item_tag(k, n, targets, plugin_map)
                for k, n in items}
        tags = {kn: t for kn, t in tags.items() if t}
        chosen = pick_items(items, preselected=preselected, tags=tags)
        sel_skills = {n for k, n in chosen if k == "skill"}
        sel_community = {n for k, n in chosen if k == "community"}
        sel_externals = {n for k, n in chosen if k == "external"}
        custom = [p for p in custom if p.name in sel_skills]
    elif args.skill:
        sel_skills, sel_community, sel_externals = resolve_skill_args(
            args.skill)
        custom = [p for p in custom if p.name in sel_skills]
    elif args.update:
        everything = set().union(*present.values())
        sel_community = all_community_names() & everything
        sel_externals = all_external_names() & everything
        custom = [p for p in custom if p.name in everything]
    else:
        sel_community = default_community_names()
        sel_externals = default_external_names()

    if not args.update:
        names, sel_community, sel_externals = add_requirements(
            {p.name for p in custom}, sel_community, sel_externals)
        custom = sorted(p for p in SKILLS_SRC.iterdir()
                        if p.is_dir() and p.name in names)

    if args.skills_only:
        # Externals fetch from a package index, same network the community
        # sources need — --skills-only means neither is reachable.
        log("--skills-only: skipping community skills and externals")
        sel_externals = set()
        for source in SOURCES:
            source["_cache"] = None
    else:
        remove_legacy_caches(args.dry_run)
        for source in SOURCES:
            wanted = sel_community & set(source["skills"])
            source["_cache"] = (update_source_cache(source, args.dry_run,
                                                    names=wanted)
                                if wanted else None)
    if args.upgrade and args.skills_only:
        warn("--upgrade has nothing to do with --skills-only: externals are "
             "skipped entirely")
    results = []
    for ext in EXTERNALS:
        ext.pop("_upgrade", None)
        if ext["name"] not in sel_externals:
            ext["_exe"] = None
            continue
        ext["_exe"] = bootstrap_cli(ext, args.dry_run)
        # A missing CLI was just installed at its latest version; upgrading
        # only makes sense for one that was already there.
        if args.upgrade and (ext["_exe"] or args.dry_run):
            ext["_upgrade"] = upgrade_cli(ext, ext["_exe"], args.dry_run)
            results.append(("external", ext["name"], ext["_upgrade"]))

    for target in targets:
        dest_root = target_root(target, repo)
        log(f"Target {target}: {dest_root}")
        if not args.dry_run:
            dest_root.mkdir(parents=True, exist_ok=True)
        results.extend(remove_legacy(target, dest_root, args.dry_run))
        # --update: only what this target already has.
        only = present[target] if present is not None else None
        for skill in custom:
            if only is not None and skill.name not in only:
                continue
            if target == "claude":
                status = install_symlink(skill, dest_root / skill.name,
                                         args.dry_run)
            else:
                status = install_copy(skill, dest_root / skill.name,
                                      args.dry_run)
            results.append((target, skill.name, status))
        results.extend(install_community_for_target(
            target, dest_root,
            sel_community if only is None else sel_community & only,
            args.dry_run))
        results.extend(install_externals_for_target(
            target, sel_externals if only is None else sel_externals & only,
            repo, args.dry_run))
        results.extend(retire_prompts(target, dest_root, args.dry_run,
                                      repo=repo))

    print_summary(results, targets, args.dry_run)

    if not args.dry_run:
        # Last, so a missing dependency cannot scroll out of view.
        hint = (" — re-run without --skills-only when online"
                if args.skills_only
                else " — re-run install.py with network access to fetch it")
        for target in targets:
            for skill, dep in missing_requirements(target_root(target, repo)):
                warn(f"{target}: {skill} requires {dep}, which is not "
                     f"installed{hint}")


if __name__ == "__main__":
    main()
