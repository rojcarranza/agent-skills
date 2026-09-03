#!/usr/bin/env python3
"""Install agent skills for GitHub Copilot and/or Claude Code.

Usage:
  python3 install.py --target claude
  python3 install.py --target copilot
  python3 install.py --target both --dry-run
  python3 install.py                # interactive: pick target + items
  python3 install.py --target claude --skills-only   # skip community fetch
  python3 install.py --repo .       # seed .github/skills + .github/prompts
  python3 install.py --target both --upgrade   # newer graphify, then refresh

Python >= 3.8, standard library only.
Copilot gets copies; Claude gets per-skill symlinks (edit the repo, changes
are live). On filesystems without symlink support the installer falls back
to copying.

Two scopes. Personal scope (--target) writes to ~/.copilot/skills and
~/.claude/skills and, for Copilot, the VS Code user prompts dir. Repo scope
(--repo) writes copies into <repo>/.github/{skills,prompts} — the only scope
JetBrains Copilot reads prompt files from, so it is what gives IntelliJ,
PyCharm and GoLand the /create-sb-style slash commands.

The prompts in prompts/ reach every agent in every IDE, in three forms: the
.prompt.md itself (Copilot in VS Code, and repo scope), a generated skill in
~/.copilot/skills (Copilot in JetBrains, as /skill:<name>), and a generated
slash command in ~/.claude/commands (Claude in both IDEs, as /<name>).
A prompt named after a real skill in skills/ generates neither — the skill
already answers to that name in both places.

Skills come from three kinds of source: this repo (skills/), a community git
repo (SOURCES, sparse-cloned into ~/.agent-skills-cache), and an external CLI
that installs its own skill (EXTERNALS — the installer bootstraps the CLI and
delegates). Externals need a package index, so --skills-only skips them, and
nothing about them auto-updates: --upgrade upgrades the CLI, and the same run
then re-copies the skill files the new version ships.
"""
import argparse
import filecmp
import json
import os
import shutil
import subprocess
import sys
import sysconfig
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent
SKILLS_SRC = REPO_ROOT / "skills"
PROMPTS_SRC = REPO_ROOT / "prompts"

AWESOME_REPO_URL = "https://github.com/github/awesome-copilot.git"
AWESOME_BRANCH = "main"
ZIP_FALLBACK_URL = "https://github.com/github/awesome-copilot/tree/main/skills"
CAVEMAN_REPO_URL = "https://github.com/juliusbrussee/caveman.git"
CAVEMAN_BRANCH = "main"
ADDY_REPO_URL = "https://github.com/addyosmani/agent-skills.git"
ADDY_BRANCH = "main"

BOTH = ("copilot", "claude")
# Also safe to vendor into a repo's .github/ for the whole team.
ANY = BOTH + ("repo",)

REPO_SKILLS_SUBDIR = Path(".github") / "skills"
REPO_PROMPTS_SUBDIR = Path(".github") / "prompts"

# Community sources. Per skill: targets it may install to, whether it is
# pre-selected (default) or an explicit cherry-pick, and an optional note
# shown when a target is skipped.
SOURCES = [
    {
        "label": "awesome-copilot",
        "url": AWESOME_REPO_URL,
        "branch": AWESOME_BRANCH,
        "cache": "awesome-copilot",
        "fallback": ZIP_FALLBACK_URL,
        "skills": {
            "code-tour": {"targets": ANY, "default": True},
            "acquire-codebase-knowledge": {"targets": ANY, "default": True},
            "context-map": {"targets": ANY, "default": True},
            "architecture-blueprint-generator": {"targets": ANY,
                                                 "default": True},
            "add-educational-comments": {"targets": ANY, "default": True},
        },
    },
    {
        "label": "caveman",
        "url": CAVEMAN_REPO_URL,
        "branch": CAVEMAN_BRANCH,
        "cache": "caveman",
        "fallback": "https://github.com/juliusbrussee/caveman/tree/main/skills",
        "skills": {
            "caveman": {"targets": ("copilot",), "default": True,
                        "note": "claude uses the caveman plugin"},
        },
    },
    {
        "label": "addy-agent-skills",
        "url": ADDY_REPO_URL,
        "branch": ADDY_BRANCH,
        "cache": "addy-agent-skills",
        "fallback": "https://github.com/addyosmani/agent-skills/tree/main/skills",
        "skills": {
            # Chained by investigate-issue on Copilot; Claude uses
            # superpowers:systematic-debugging instead.
            "debugging-and-error-recovery": {
                "targets": ("copilot",), "default": True,
                "note": "claude uses superpowers:systematic-debugging"},
            "observability-and-instrumentation": {"targets": BOTH,
                                                  "default": False},
            "ci-cd-and-automation": {"targets": BOTH, "default": False},
            "security-and-hardening": {"targets": BOTH, "default": False},
            "deprecation-and-migration": {"targets": BOTH, "default": False},
        },
    },
    {
        "label": "anthropics-skills",
        "url": "https://github.com/anthropics/skills.git",
        "branch": "main",
        "cache": "anthropics-skills",
        "fallback": "https://github.com/anthropics/skills/tree/main/skills",
        "skills": {
            "pdf": {"targets": BOTH, "default": False},
            "docx": {"targets": BOTH, "default": False},
            "pptx": {"targets": BOTH, "default": False},
            "xlsx": {"targets": BOTH, "default": False},
        },
    },
]

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


def all_community_names():
    return set(registry())


def default_community_names():
    return {n for n, (_, meta) in registry().items() if meta["default"]}


# Legacy constants, derived — external callers and tests rely on them.
COMMUNITY_SKILLS = list(source_by_label("awesome-copilot")["skills"])
CAVEMAN_SKILLS = list(source_by_label("caveman")["skills"])
ADDY_SKILLS = list(source_by_label("addy-agent-skills")["skills"])


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
        print("  1) GitHub Copilot   (~/.copilot/skills + VS Code prompts)")
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


def build_items(custom_skills, prompt_files):
    """Ordered installable items as (kind, name): custom skills, prompt
    files, community skills, then CLI-installed externals."""
    items = [("skill", n) for n in custom_skills]
    items += [("prompt", n) for n in prompt_files]
    items += [("community", n) for n in sorted(all_community_names())]
    items += [("external", n) for n in sorted(all_external_names())]
    return items


def item_tag(kind, name, targets, plugin_map):
    """Picker annotation: [installed] [update] [conflict], or ''."""
    tags = []
    if kind == "prompt":
        d = vscode_prompts_dir()
        cmd = claude_commands_dir() / f"{prompt_stem(name)}.md"
        if ((d and (d / name).is_file())
                or ("claude" in targets and cmd.is_file())):
            tags.append("[installed]")
    else:
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
                cand = (source_cache_dir(reg[name][0]) / "skills" / name)
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
    """Locate the VS Code user prompts dir, or None if VS Code is absent."""
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


def prompt_stem(path):
    """'create-sb.prompt.md' -> 'create-sb' (the slash command, and the
    name --uninstall prompt:<stem> expects)."""
    return Path(Path(path).stem).stem


def parse_prompt(path):
    """Split a .prompt.md into (description, body). Description falls back
    to the stem when the frontmatter has none or is malformed."""
    text = Path(path).read_text(encoding="utf-8")
    stem = prompt_stem(path)
    if not text.startswith("---"):
        return stem, text.strip()
    _, _, rest = text.partition("---")
    front, sep, body = rest.partition("---")
    if not sep:
        return stem, text.strip()
    description = stem
    for line in front.splitlines():
        key, _, value = line.partition(":")
        if key.strip() == "description":
            description = value.strip().strip("'\"") or stem
            break
    return description, body.strip()


def prompt_skill_text(path):
    """SKILL.md body for the skill generated from a prompt file. Copilot
    reads personal-scope skills from every project, so this is how a
    /create-sb-style command reaches JetBrains without seeding each repo."""
    stem = prompt_stem(path)
    description, body = parse_prompt(path)
    if not description.endswith("."):
        description += "."
    description += (f' Use when the user types "/{stem}", "/skill:{stem}",'
                    f' or asks for the {stem} workflow by name.')
    return (
        "---\n"
        f"name: {stem}\n"
        f"description: {json.dumps(description)}\n"
        "---\n\n"
        f"{body}\n\n"
        f"<!-- Generated from prompts/{Path(path).name} by install.py."
        " Edit the prompt file, not this copy. -->\n"
    )


def custom_skill_names():
    """Names of the skills in skills/ — also the directory names they take
    in every target root."""
    if not SKILLS_SRC.is_dir():
        return set()
    return {p.name for p in SKILLS_SRC.iterdir() if p.is_dir()}


def prompt_skill_names():
    """Stems of the prompts that ship as generated skills. A prompt named
    after a real skill is excluded: the skill owns that directory."""
    return ({prompt_stem(p) for p in PROMPTS_SRC.glob("*.prompt.md")}
            - custom_skill_names())


def install_prompt_skills(dest_root, dry_run, names=None):
    """Write one generated skill per prompt file into dest_root.
    names: optional set of prompt *file* names; None = all."""
    results = []
    own = custom_skill_names()
    for p in sorted(PROMPTS_SRC.glob("*.prompt.md")):
        if names is not None and p.name not in names:
            continue
        stem = prompt_stem(p)
        if stem in own:
            # The real skill already occupies dest_root/<stem>; generating
            # over it would replace its SKILL.md with the prompt stub.
            # JetBrains reaches it as /skill:<stem> either way.
            results.append(("copilot", stem, "skipped (real skill of "
                                             "same name)"))
            continue
        dest = dest_root / prompt_stem(p) / "SKILL.md"
        text = prompt_skill_text(p)
        if dest.is_file() and dest.read_text(encoding="utf-8") == text:
            status = "up to date"
        else:
            status = "updated" if dest.exists() else "installed"
            if not dry_run:
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_text(text, encoding="utf-8")
        results.append(("copilot", prompt_stem(p), status))
    return results


def claude_commands_dir():
    """Claude's personal slash-command scope. Both the VS Code and the
    JetBrains Claude extensions read it, so a command installed here is
    available in every project in every IDE."""
    return Path.home() / ".claude" / "commands"


def claude_command_text(path):
    """Slash-command body for a prompt file. Claude reads no .prompt.md, so
    each prompt ships as ~/.claude/commands/<stem>.md instead. `mode: agent`
    is dropped — it is a Copilot key — and $ARGUMENTS is appended so text
    typed after the command reaches the prompt."""
    description, body = parse_prompt(path)
    return (
        "---\n"
        f"description: {json.dumps(description)}\n"
        "---\n\n"
        f"{body}\n\n"
        "My request: $ARGUMENTS\n\n"
        f"<!-- Generated from prompts/{Path(path).name} by install.py."
        " Edit the prompt file, not this copy. -->\n"
    )


def install_claude_commands(dry_run, names=None):
    """Write one Claude slash command per prompt file.
    names: optional set of prompt *file* names; None = all."""
    results = []
    dest_root = claude_commands_dir()
    own = custom_skill_names()
    if not dry_run:
        dest_root.mkdir(parents=True, exist_ok=True)
    for p in sorted(PROMPTS_SRC.glob("*.prompt.md")):
        if names is not None and p.name not in names:
            continue
        stem = prompt_stem(p)
        if stem in own:
            # ~/.claude/skills/<stem> already answers to /<stem>; a command
            # of the same name would be a second entry for one workflow.
            results.append(("claude", f"command:{stem}",
                            "skipped (real skill of same name)"))
            continue
        dest = dest_root / f"{stem}.md"
        text = claude_command_text(p)
        if dest.is_file() and dest.read_text(encoding="utf-8") == text:
            status = "up to date"
        else:
            status = "updated" if dest.exists() else "installed"
            if not dry_run:
                dest.write_text(text, encoding="utf-8")
        results.append(("claude", f"command:{stem}", status))
    return results


def uninstall_claude_commands(names, dry_run):
    """Remove 'prompt:<stem>' entries from ~/.claude/commands."""
    results = []
    dest_root = claude_commands_dir()
    for n in names:
        if not n.startswith("prompt:"):
            continue
        stem = n[len("prompt:"):]
        f = dest_root / f"{stem}.md"
        if f.is_file():
            if not dry_run:
                f.unlink()
            results.append(("claude", f"command:{stem}", "removed"))
        else:
            results.append(("claude", f"command:{stem}", "not installed"))
    return results


def prompts_dir_for(target, repo=None):
    """Where *.prompt.md go for a target, or None when it has no prompts."""
    if target == "repo":
        return Path(repo) / REPO_PROMPTS_SUBDIR
    if target == "copilot":
        return vscode_prompts_dir()
    return None                      # claude does not use prompt files


def install_prompts(dry_run, names=None, target="copilot", repo=None):
    """Copy prompts/*.prompt.md into the target's prompts dir.
    names: optional set of file names to install; None = all."""
    results = []
    user_dir = prompts_dir_for(target, repo)
    if user_dir is None:
        warn("VS Code user dir not found — prompt files not installed.")
        warn("Per-repo alternative: install.py --repo <path> writes them "
             "into .github/prompts/")
        return results
    if not dry_run:
        user_dir.mkdir(parents=True, exist_ok=True)
    for p in sorted(PROMPTS_SRC.glob("*.prompt.md")):
        if names is not None and p.name not in names:
            continue
        dest = user_dir / p.name
        if dest.exists() and filecmp.cmp(p, dest, shallow=False):
            status = "up to date"
        else:
            status = "updated" if dest.exists() else "installed"
            if not dry_run:
                shutil.copy2(p, dest)
        results.append((target, f"prompt:{prompt_stem(p)}", status))
    return results


def uninstall_prompts(names, target, prompts_dir, dry_run):
    """Remove 'prompt:<stem>' entries from a target's prompts dir."""
    results = []
    for n in names:
        if not n.startswith("prompt:"):
            continue
        stem = n[len("prompt:"):]
        f = prompts_dir / f"{stem}.prompt.md" if prompts_dir else None
        if f and f.is_file():
            if not dry_run:
                f.unlink()
            results.append((target, n, "removed"))
        else:
            results.append((target, n, "not installed"))
    return results


def cache_dir():
    return Path.home() / ".agent-skills-cache" / "awesome-copilot"


def caveman_cache_dir():
    return Path.home() / ".agent-skills-cache" / "caveman"


def addy_cache_dir():
    return Path.home() / ".agent-skills-cache" / "addy-agent-skills"


# Legacy cache dirs pre-date the registry; keep them authoritative so
# existing caches (and tests that patch them) stay valid.
_LEGACY_CACHE_FUNCS = {"awesome-copilot": "cache_dir",
                       "caveman": "caveman_cache_dir",
                       "addy-agent-skills": "addy_cache_dir"}


def source_cache_dir(source):
    fn_name = _LEGACY_CACHE_FUNCS.get(source["label"])
    if fn_name:
        return globals()[fn_name]()
    return Path.home() / ".agent-skills-cache" / source["cache"]


def update_source_cache(source, dry_run, names=None):
    names = sorted(names) if names else sorted(source["skills"])
    return update_repo_cache(
        source_cache_dir(source), source["url"], source["branch"],
        [f"skills/{n}" for n in names], dry_run, source["label"],
        source["fallback"])


def run_git(args):
    subprocess.run(["git", *args], check=True)


def update_repo_cache(cache, url, branch, sparse, dry_run, label,
                      fallback_url):
    """Sparse-clone/refresh a skills repo. Returns cache path or None when
    no usable cache exists."""
    if dry_run:
        log(f"dry-run: would clone/update {url} into {cache}")
        return cache if (cache / "skills").is_dir() else None
    try:
        if (cache / ".git").is_dir():
            log(f"Updating {label} cache...")
            run_git(["-C", str(cache), "sparse-checkout", "set", *sparse])
            run_git(["-C", str(cache), "fetch", "--depth", "1",
                     "origin", branch])
            run_git(["-C", str(cache), "reset", "--hard",
                     f"origin/{branch}"])
        else:
            log(f"Cloning {label} (sparse, only needed skills)...")
            cache.parent.mkdir(parents=True, exist_ok=True)
            run_git(["clone", "--depth", "1", "--filter=blob:none", "--sparse",
                     "-b", branch, url, str(cache)])
            run_git(["-C", str(cache), "sparse-checkout", "set", *sparse])
        ok(f"{label} cache ready")
        return cache
    except (subprocess.CalledProcessError, FileNotFoundError):
        warn(f"Could not clone/update {label} (offline? proxy?).")
        if (cache / "skills").is_dir():
            warn("Using existing local cache instead.")
            return cache
        warn(f"Fallback: download the skill folders as ZIP from {fallback_url}")
        warn(f"and unzip into {cache / 'skills'}, then re-run this script.")
        return None


def update_community_cache(dry_run):
    return update_source_cache(source_by_label("awesome-copilot"), dry_run)


def update_caveman_cache(dry_run):
    return update_source_cache(source_by_label("caveman"), dry_run)


def update_addy_cache(dry_run):
    return update_source_cache(source_by_label("addy-agent-skills"), dry_run)


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
            src = cache / "skills" / name
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


def gather_status(target, dest_root, custom_names, plugin_map,
                  generated_names=frozenset()):
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
        if name in generated_names:
            kind = "custom (from prompt)"
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
    return rows, warnings


def show_status(targets, repo=None):
    custom_names = custom_skill_names()
    generated = prompt_skill_names()
    plugin_map = plugin_skills()
    all_warnings = []
    for target in targets:
        dest_root = target_root(target, repo)
        print(f"\n{target}: {dest_root}")
        rows, warnings = gather_status(target, dest_root, custom_names,
                                       plugin_map, generated)
        prompts_dir = prompts_dir_for(target, repo)
        prompts = (sorted(prompts_dir.glob("*.prompt.md"))
                   if prompts_dir and prompts_dir.is_dir() else [])
        if not rows and not prompts:
            print("  (nothing installed)")
        for name, kind, mech in rows:
            print(f"  {name:35} {kind:32} {mech}")
        for p in prompts:
            print(f"  {prompt_stem(p):35} {'prompt file':32} copy")
        if target == "claude":
            cmd_dir = claude_commands_dir()
            for c in sorted(cmd_dir.glob("*.md")) if cmd_dir.is_dir() else []:
                print(f"  {c.stem:35} {'slash command (from prompt)':32}"
                      f" copy")
        all_warnings.extend(warnings)
    print()
    if all_warnings:
        for w in all_warnings:
            warn(w)
    else:
        ok("no conflicts detected")


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
            "mode, type '/' — the prompt files list as slash commands")
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
                    help="remove skills (or prompt:<stem>) from the target")
    ap.add_argument("--force", action="store_true",
                    help="allow --uninstall of names the installer does "
                         "not know")
    ap.add_argument("--repo", metavar="PATH",
                    help="also seed <PATH>/.github/skills and "
                         "<PATH>/.github/prompts (repo scope — the only "
                         "scope JetBrains Copilot reads prompt files from)")
    args = ap.parse_args()
    repo = resolve_repo(args.repo) if args.repo else None

    if args.status:
        show_status(status_targets(args.target, repo), repo)
        return

    if args.uninstall:
        targets = pick_targets(args.target, repo)
        names = [n.strip() for n in args.uninstall.split(",") if n.strip()]
        known = (custom_skill_names() | all_community_names()
                 | prompt_skill_names() | all_external_names())
        results = []
        for target in targets:
            # Externals are removed by their own CLI in personal scope; in
            # repo scope they are ordinary copied directories.
            ext_names = [n for n in names if n in all_external_names()]
            results.extend(uninstall_externals(ext_names, target,
                                               args.dry_run))
            skills = [n for n in names
                      if not n.startswith("prompt:")
                      and (target == "repo" or n not in ext_names)]
            results.extend(uninstall_skills(
                skills, target, target_root(target, repo), known,
                args.force, args.dry_run))
            if target in ("copilot", "repo"):
                results.extend(uninstall_prompts(
                    names, target, prompts_dir_for(target, repo),
                    args.dry_run))
            if target == "claude":
                results.extend(uninstall_claude_commands(names,
                                                         args.dry_run))
        print_summary(results, targets, args.dry_run)
        return

    interactive = args.target is None and repo is None
    targets = pick_targets(args.target, repo)
    custom = sorted(p for p in SKILLS_SRC.iterdir() if p.is_dir())
    if not custom:
        sys.exit(f"No skills found in {SKILLS_SRC}")
    prompt_files = sorted(p.name for p in PROMPTS_SRC.glob("*.prompt.md"))

    if interactive:
        items = build_items([p.name for p in custom], prompt_files)
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
        sel_prompts = {n for k, n in chosen if k == "prompt"}
        sel_community = {n for k, n in chosen if k == "community"}
        sel_externals = {n for k, n in chosen if k == "external"}
        custom = [p for p in custom if p.name in sel_skills]
    else:
        sel_prompts = None
        sel_community = default_community_names()
        sel_externals = default_external_names()

    if args.skills_only:
        # Externals fetch from a package index, same network the community
        # sources need — --skills-only means neither is reachable.
        log("--skills-only: skipping community skills and externals")
        sel_externals = set()
        for source in SOURCES:
            source["_cache"] = None
    else:
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
        for skill in custom:
            if target == "claude":
                status = install_symlink(skill, dest_root / skill.name,
                                         args.dry_run)
            else:
                status = install_copy(skill, dest_root / skill.name,
                                      args.dry_run)
            results.append((target, skill.name, status))
        results.extend(install_community_for_target(
            target, dest_root, sel_community, args.dry_run))
        results.extend(install_externals_for_target(
            target, sel_externals, repo, args.dry_run))
        if target == "copilot":
            # Personal scope reaches every project; JetBrains has no global
            # prompts dir, so the prompts also ship as generated skills.
            results.extend(install_prompt_skills(dest_root, args.dry_run,
                                                 names=sel_prompts))
        if target in ("copilot", "repo"):
            results.extend(install_prompts(args.dry_run, names=sel_prompts,
                                           target=target, repo=repo))
        if target == "claude":
            # Claude reads no .prompt.md — the prompts reach it, in both
            # VS Code and JetBrains, as ~/.claude/commands/<stem>.md.
            results.extend(install_claude_commands(args.dry_run,
                                                   names=sel_prompts))

    print_summary(results, targets, args.dry_run)


if __name__ == "__main__":
    main()
