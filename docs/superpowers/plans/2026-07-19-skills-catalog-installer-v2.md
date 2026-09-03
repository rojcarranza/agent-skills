# Skills Catalog + Installer v2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Registry-driven installer with `--status`/`--uninstall`/conflict warnings, live caveman-duplicate cleanup, and a filled-in Agent Skills Catalog note.

**Architecture:** `install.py` stays a single stdlib-only script. The three hardcoded community-source constants become one `SOURCES` registry (per-skill target policy + default flag); legacy constants and cache functions stay as thin derived wrappers so existing tests keep passing. New pure-ish helpers (`gather_status`, `install_community_for_target`, `uninstall_skills`, `item_tag`) carry the new behavior and are unit-tested with tmp dirs and `mock.patch`.

**Tech Stack:** Python ≥ 3.8 stdlib only (`argparse`, `pathlib`, `shutil`, `filecmp`, `json`, `subprocess`), `unittest` + `unittest.mock`.

## Global Constraints

- `install.py` and `test_install.py` stay stdlib-only, Python ≥ 3.8.
- Back-compat CLI: `--target {copilot,claude,both}`, `--dry-run`, `--skills-only`, bare interactive run must keep working unchanged.
- Existing tests in `test_install.py` must keep passing unmodified.
- Verified upstream skill folder names (2026-07-19): addyosmani — `debugging-and-error-recovery`, `observability-and-instrumentation`, `ci-cd-and-automation`, `security-and-hardening`, `deprecation-and-migration`; anthropics/skills — `skills/pdf`, `skills/docx`, `skills/pptx`, `skills/xlsx`.
- Verified local layout: enabled plugins map at `~/.claude/settings.json` key `enabledPlugins` (`{"name@marketplace": bool}`); plugin skills at `~/.claude/plugins/cache/<marketplace>/<plugin>/<version>/skills/<skill>/`.
- caveman never installs to the claude target (plugin covers it). `debugging-and-error-recovery` is copilot-only. Cherry-pick skills (addyosmani ops ×4, anthropics document ×4) are never selected by default.
- Test command: `cd /Users/roj/Dev/.dotfiles/agent-skills && python3 -m unittest test_install -v`.
- Commits from repo root `/Users/roj/Dev/.dotfiles`; conventional-commit style matching recent history (`feat(installer): ...`, `docs(agent-skills): ...`).

---

### Task 1: Source registry + generic cache updater

**Files:**
- Modify: `agent-skills/install.py` (constants block lines 28–47, cache functions lines 215–283)
- Test: `agent-skills/test_install.py` (append `TestRegistry`)

**Interfaces:**
- Produces: `SOURCES` (list of source dicts), `registry()` → `{skill_name: (source, meta)}`, `source_by_label(label)`, `source_cache_dir(source)`, `update_source_cache(source, dry_run, names=None)`, `default_community_names()`, `all_community_names()`. Meta dict: `{"targets": tuple, "default": bool, "note": str (optional)}`.
- Consumes: existing `update_repo_cache`, `cache_dir`, `caveman_cache_dir`, `addy_cache_dir` (all kept).

- [ ] **Step 1: Write failing tests**

Append to `test_install.py`:

```python
class TestRegistry(unittest.TestCase):
    def test_caveman_is_copilot_only(self):
        source, meta = install.registry()["caveman"]
        self.assertEqual(meta["targets"], ("copilot",))
        self.assertEqual(source["label"], "caveman")

    def test_debugging_is_copilot_only_default(self):
        _, meta = install.registry()["debugging-and-error-recovery"]
        self.assertEqual(meta["targets"], ("copilot",))
        self.assertTrue(meta["default"])

    def test_cherry_picks_not_default(self):
        reg = install.registry()
        for name in ("observability-and-instrumentation", "ci-cd-and-automation",
                     "security-and-hardening", "deprecation-and-migration",
                     "pdf", "docx", "pptx", "xlsx"):
            self.assertFalse(reg[name][1]["default"], name)

    def test_default_names_match_legacy_constants(self):
        self.assertEqual(
            install.default_community_names(),
            set(install.COMMUNITY_SKILLS + install.CAVEMAN_SKILLS
                + ["debugging-and-error-recovery"]))

    def test_legacy_cache_dir_used_for_awesome(self):
        source = install.source_by_label("awesome-copilot")
        with mock.patch("install.cache_dir",
                        return_value=Path("/tmp/xyz")) as m:
            self.assertEqual(install.source_cache_dir(source), Path("/tmp/xyz"))
            m.assert_called_once()

    def test_new_source_gets_registry_cache_path(self):
        source = install.source_by_label("anthropics-skills")
        self.assertEqual(install.source_cache_dir(source),
                         Path.home() / ".agent-skills-cache" / "anthropics-skills")

    def test_update_source_cache_sparse_names(self):
        source = install.source_by_label("addy-agent-skills")
        with mock.patch("install.update_repo_cache") as m:
            install.update_source_cache(source, dry_run=False,
                                        names=["security-and-hardening"])
        sparse = m.call_args[0][3]
        self.assertEqual(sparse, ["skills/security-and-hardening"])
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/roj/Dev/.dotfiles/agent-skills && python3 -m unittest test_install.TestRegistry -v`
Expected: FAIL / ERROR with `AttributeError: module 'install' has no attribute 'registry'`

- [ ] **Step 3: Implement registry**

In `install.py`, replace the block from `AWESOME_REPO_URL = ...` through `ADDY_SKILLS = ...` (lines 28–47) with:

```python
AWESOME_REPO_URL = "https://github.com/github/awesome-copilot.git"
AWESOME_BRANCH = "main"
ZIP_FALLBACK_URL = "https://github.com/github/awesome-copilot/tree/main/skills"
CAVEMAN_REPO_URL = "https://github.com/juliusbrussee/caveman.git"
CAVEMAN_BRANCH = "main"
ADDY_REPO_URL = "https://github.com/addyosmani/agent-skills.git"
ADDY_BRANCH = "main"

BOTH = ("copilot", "claude")

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
            "code-tour": {"targets": BOTH, "default": True},
            "acquire-codebase-knowledge": {"targets": BOTH, "default": True},
            "context-map": {"targets": BOTH, "default": True},
            "architecture-blueprint-generator": {"targets": BOTH,
                                                 "default": True},
            "add-educational-comments": {"targets": BOTH, "default": True},
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
```

After the existing `addy_cache_dir()` definition, add:

```python
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
```

Rewrite the three legacy updaters as wrappers (replace their bodies):

```python
def update_community_cache(dry_run):
    return update_source_cache(source_by_label("awesome-copilot"), dry_run)


def update_caveman_cache(dry_run):
    return update_source_cache(source_by_label("caveman"), dry_run)


def update_addy_cache(dry_run):
    return update_source_cache(source_by_label("addy-agent-skills"), dry_run)
```

- [ ] **Step 4: Run full suite**

Run: `python3 -m unittest test_install -v`
Expected: all PASS (old cache tests still green — `globals()` lookup sees `mock.patch("install.cache_dir")`).

- [ ] **Step 5: Commit**

```bash
cd /Users/roj/Dev/.dotfiles && git add agent-skills/install.py agent-skills/test_install.py && git commit -m "feat(installer): source registry with per-skill target policy"
```

---

### Task 2: Target-filtered community install flow

**Files:**
- Modify: `agent-skills/install.py` (`main()` community fetch + install loop, lines 330–380)
- Test: `agent-skills/test_install.py` (append `TestInstallCommunityForTarget`)

**Interfaces:**
- Produces: `install_community_for_target(target, dest_root, sel_community, dry_run)` → list of `(target, name, status)`; sources carry fetched cache path under key `"_cache"`.
- Consumes: `SOURCES`, `registry()`, `update_source_cache`, `install_copy` (Task 1 + existing).

- [ ] **Step 1: Write failing tests**

```python
class TestInstallCommunityForTarget(TempDirTest):
    def fake_sources(self, with_cache=True):
        cache = self.tmp / "cache"
        (cache / "skills" / "tool-x").mkdir(parents=True)
        (cache / "skills" / "tool-x" / "SKILL.md").write_text("x")
        return [{
            "label": "fake", "url": "u", "branch": "main", "cache": "fake",
            "fallback": "f",
            "_cache": cache if with_cache else None,
            "skills": {
                "tool-x": {"targets": ("copilot", "claude"), "default": True},
                "cop-only": {"targets": ("copilot",), "default": True,
                             "note": "claude uses plugin"},
            },
        }]

    def test_installs_allowed_skill(self):
        dest = self.tmp / "dest"
        with mock.patch("install.SOURCES", self.fake_sources()):
            results = install.install_community_for_target(
                "claude", dest, {"tool-x"}, dry_run=False)
        self.assertEqual(results, [("claude", "tool-x", "installed")])
        self.assertTrue((dest / "tool-x" / "SKILL.md").is_file())

    def test_skips_wrong_target_with_note(self):
        dest = self.tmp / "dest"
        with mock.patch("install.SOURCES", self.fake_sources()):
            results = install.install_community_for_target(
                "claude", dest, {"cop-only"}, dry_run=False)
        self.assertEqual(results,
                         [("claude", "cop-only",
                           "skipped (claude uses plugin)")])
        self.assertFalse((dest / "cop-only").exists())

    def test_missing_in_cache_reported(self):
        sources = self.fake_sources()
        sources[0]["skills"]["ghost"] = {"targets": ("claude",),
                                         "default": True}
        dest = self.tmp / "dest"
        with mock.patch("install.SOURCES", sources):
            results = install.install_community_for_target(
                "claude", dest, {"ghost"}, dry_run=False)
        self.assertEqual(results,
                         [("claude", "ghost", "missing in cache — skipped")])

    def test_no_cache_skips_silently(self):
        dest = self.tmp / "dest"
        with mock.patch("install.SOURCES", self.fake_sources(with_cache=False)):
            results = install.install_community_for_target(
                "claude", dest, {"tool-x"}, dry_run=False)
        self.assertEqual(results, [])
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m unittest test_install.TestInstallCommunityForTarget -v`
Expected: ERROR `AttributeError: ... no attribute 'install_community_for_target'`

- [ ] **Step 3: Implement**

Add to `install.py` (after `update_addy_cache`):

```python
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
                note = meta.get("note", "not for " + target)
                results.append((target, name, f"skipped ({note})"))
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
```

In `main()`, replace everything from `community_src = None` down to the end of the per-target community loop (the `for src_root, names in (...)` block) with:

```python
    if interactive:
        ...  # unchanged custom/prompt selection lines stay as-is
    else:
        sel_prompts = None
        sel_community = default_community_names()

    if args.skills_only:
        log("--skills-only: skipping community skills")
        for source in SOURCES:
            source["_cache"] = None
    else:
        for source in SOURCES:
            wanted = sel_community & set(source["skills"])
            source["_cache"] = (update_source_cache(source, args.dry_run,
                                                    names=wanted)
                                if wanted else None)

    results = []
    for target in targets:
        dest_root = target_root(target)
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
        if target == "copilot":
            results.extend(install_prompts(args.dry_run, names=sel_prompts))
```

Add helper near `pick_targets`:

```python
def target_root(target):
    return Path.home() / (".copilot" if target == "copilot"
                          else ".claude") / "skills"
```

Update `build_items` community line to cover all registry skills:

```python
    items += [("community", n) for n in sorted(all_community_names())]
```

(Old `TestBuildItems` asserts legacy names are present — sorted superset still passes.)

- [ ] **Step 4: Run full suite**

Run: `python3 -m unittest test_install -v`
Expected: all PASS

- [ ] **Step 5: Sanity dry-run**

Run: `python3 install.py --target both --dry-run`
Expected: caveman + debugging-and-error-recovery show `skipped (...)` under claude, normal statuses under copilot; cherry-picks (pdf, security-and-hardening, …) absent.

- [ ] **Step 6: Commit**

```bash
cd /Users/roj/Dev/.dotfiles && git add agent-skills/install.py agent-skills/test_install.py && git commit -m "feat(installer): per-target community install with policy skips"
```

---

### Task 3: `--status`

**Files:**
- Modify: `agent-skills/install.py` (new status functions + argparse flag + main dispatch)
- Test: `agent-skills/test_install.py` (append `TestStatus`)

**Interfaces:**
- Produces: `enabled_plugins(settings_path=None)` → `{plugin_id: True}`; `plugin_skills(cache_root=None, settings_path=None)` → `{skill_name: plugin_id}`; `gather_status(target, dest_root, custom_names, plugin_map)` → `(rows, warnings)` where a row is `(name, kind, mechanism)`; `show_status(targets)` prints.
- Consumes: `registry()`, `target_root` (Tasks 1–2).

- [ ] **Step 1: Write failing tests**

```python
class TestStatus(TempDirTest):
    def make_dest(self):
        dest = self.tmp / "claude-skills"
        dest.mkdir(parents=True)
        return dest

    def test_classifies_custom_community_unknown(self):
        dest = self.make_dest()
        src = self.make_skill("repo", name="explain-logic")
        (dest / "explain-logic").symlink_to(src)
        (dest / "code-tour").mkdir()
        (dest / "mystery").mkdir()
        rows, warnings = install.gather_status(
            "claude", dest, {"explain-logic"}, {})
        by_name = {r[0]: r for r in rows}
        self.assertEqual(by_name["explain-logic"][1:],
                         ("custom", "symlink"))
        self.assertEqual(by_name["code-tour"][1:],
                         ("community (awesome-copilot)", "copy"))
        self.assertEqual(by_name["mystery"][1:], ("unknown", "copy"))
        self.assertEqual(warnings, [])

    def test_broken_symlink_warns(self):
        dest = self.make_dest()
        (dest / "explain-logic").symlink_to(self.tmp / "gone")
        _, warnings = install.gather_status(
            "claude", dest, {"explain-logic"}, {})
        self.assertIn("claude: explain-logic is a broken symlink", warnings)

    def test_wrong_target_warns(self):
        dest = self.make_dest()
        (dest / "caveman").mkdir()
        _, warnings = install.gather_status("claude", dest, set(), {})
        self.assertTrue(any("caveman" in w and "claude" in w
                            for w in warnings))

    def test_plugin_duplicate_warns(self):
        dest = self.make_dest()
        (dest / "brainstorming").mkdir()
        _, warnings = install.gather_status(
            "claude", dest, set(),
            {"brainstorming": "superpowers@claude-plugins-official"})
        self.assertTrue(any("superpowers@claude-plugins-official" in w
                            for w in warnings))

    def test_plugin_duplicate_ignored_on_copilot(self):
        dest = self.make_dest()
        (dest / "brainstorming").mkdir()
        _, warnings = install.gather_status(
            "copilot", dest, set(),
            {"brainstorming": "superpowers@claude-plugins-official"})
        self.assertEqual(warnings, [])

    def test_plugin_skills_reads_enabled_only(self):
        settings = self.tmp / "settings.json"
        settings.write_text(
            '{"enabledPlugins": {"good@mp": true, "off@mp": false}}')
        cache = self.tmp / "plugcache"
        for plug, skill in (("good", "alpha"), ("off", "beta")):
            (cache / "mp" / plug / "1.0.0" / "skills" / skill).mkdir(
                parents=True)
        result = install.plugin_skills(cache_root=cache,
                                       settings_path=settings)
        self.assertEqual(result, {"alpha": "good@mp"})

    def test_plugin_skills_missing_config_empty(self):
        result = install.plugin_skills(
            cache_root=self.tmp / "nope",
            settings_path=self.tmp / "nope.json")
        self.assertEqual(result, {})
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m unittest test_install.TestStatus -v`
Expected: ERROR `no attribute 'gather_status'`

- [ ] **Step 3: Implement**

Add `import json` to the imports. Add after `install_community_for_target`:

```python
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
    rows, warnings = [], []
    if not dest_root.is_dir():
        return rows, warnings
    for entry in sorted(dest_root.iterdir()):
        if not (entry.is_dir() or entry.is_symlink()):
            continue
        name = entry.name
        if name in custom_names:
            kind = "custom"
        elif name in reg:
            kind = f"community ({reg[name][0]['label']})"
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


def show_status(targets):
    custom_names = {p.name for p in SKILLS_SRC.iterdir() if p.is_dir()}
    plugin_map = plugin_skills()
    all_warnings = []
    for target in targets:
        dest_root = target_root(target)
        print(f"\n{target}: {dest_root}")
        rows, warnings = gather_status(target, dest_root, custom_names,
                                       plugin_map)
        if not rows:
            print("  (nothing installed)")
        for name, kind, mech in rows:
            print(f"  {name:35} {kind:32} {mech}")
        all_warnings.extend(warnings)
    print()
    if all_warnings:
        for w in all_warnings:
            warn(w)
    else:
        ok("no conflicts detected")
```

In `main()` argparse block add:

```python
    ap.add_argument("--status", action="store_true",
                    help="show installed skills per target and conflicts")
```

Right after `args = ap.parse_args()`:

```python
    if args.status:
        show_status(["copilot", "claude"] if args.target in (None, "both")
                    else [args.target])
        return
```

- [ ] **Step 4: Run full suite**

Run: `python3 -m unittest test_install -v`
Expected: all PASS

- [ ] **Step 5: Live smoke test**

Run: `python3 install.py --status`
Expected: lists copilot + claude installs; warns `claude: caveman also provided by enabled plugin caveman@caveman` (cleanup happens in Task 7).

- [ ] **Step 6: Commit**

```bash
cd /Users/roj/Dev/.dotfiles && git add agent-skills/install.py agent-skills/test_install.py && git commit -m "feat(installer): --status with plugin/target conflict warnings"
```

---

### Task 4: `--uninstall`

**Files:**
- Modify: `agent-skills/install.py` (new `uninstall_skills` + argparse + dispatch)
- Test: `agent-skills/test_install.py` (append `TestUninstall`)

**Interfaces:**
- Produces: `uninstall_skills(names, target, dest_root, known_names, force, dry_run)` → list of `(target, name, status)`; statuses: `"removed"`, `"removed (symlink)"`, `"not installed"`, `"unknown — use --force"`. Prompt entries use `prompt:<stem>` naming and are handled in the dispatch, not this function.
- Consumes: `target_root`, `registry()`, `vscode_prompts_dir` (existing).

- [ ] **Step 1: Write failing tests**

```python
class TestUninstall(TempDirTest):
    def test_removes_copy_and_symlink(self):
        dest = self.tmp / "skills"
        src = self.make_skill("repo", name="explain-logic")
        dest.mkdir()
        (dest / "explain-logic").symlink_to(src)
        (dest / "code-tour").mkdir()
        results = install.uninstall_skills(
            ["explain-logic", "code-tour"], "claude", dest,
            {"explain-logic", "code-tour"}, force=False, dry_run=False)
        self.assertEqual(results,
                         [("claude", "explain-logic", "removed (symlink)"),
                          ("claude", "code-tour", "removed")])
        self.assertFalse((dest / "explain-logic").is_symlink())
        self.assertFalse((dest / "code-tour").exists())
        self.assertTrue(src.exists())  # repo source untouched

    def test_unknown_refused_without_force(self):
        dest = self.tmp / "skills"
        (dest / "mystery").mkdir(parents=True)
        results = install.uninstall_skills(
            ["mystery"], "claude", dest, set(), force=False, dry_run=False)
        self.assertEqual(results,
                         [("claude", "mystery", "unknown — use --force")])
        self.assertTrue((dest / "mystery").exists())

    def test_unknown_removed_with_force(self):
        dest = self.tmp / "skills"
        (dest / "mystery").mkdir(parents=True)
        results = install.uninstall_skills(
            ["mystery"], "claude", dest, set(), force=True, dry_run=False)
        self.assertEqual(results, [("claude", "mystery", "removed")])
        self.assertFalse((dest / "mystery").exists())

    def test_not_installed(self):
        dest = self.tmp / "skills"
        dest.mkdir()
        results = install.uninstall_skills(
            ["ghost"], "claude", dest, {"ghost"}, force=False,
            dry_run=False)
        self.assertEqual(results, [("claude", "ghost", "not installed")])

    def test_dry_run_removes_nothing(self):
        dest = self.tmp / "skills"
        (dest / "code-tour").mkdir(parents=True)
        results = install.uninstall_skills(
            ["code-tour"], "claude", dest, {"code-tour"}, force=False,
            dry_run=True)
        self.assertEqual(results, [("claude", "code-tour", "removed")])
        self.assertTrue((dest / "code-tour").exists())
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m unittest test_install.TestUninstall -v`
Expected: ERROR `no attribute 'uninstall_skills'`

- [ ] **Step 3: Implement**

Add after `show_status`:

```python
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
```

Argparse additions:

```python
    ap.add_argument("--uninstall", metavar="NAME[,NAME...]",
                    help="remove skills (or prompt:<stem>) from the target")
    ap.add_argument("--force", action="store_true",
                    help="allow --uninstall of names the installer does "
                         "not know")
```

Dispatch in `main()` after the `--status` branch:

```python
    if args.uninstall:
        targets = pick_targets(args.target)
        names = [n.strip() for n in args.uninstall.split(",") if n.strip()]
        known = ({p.name for p in SKILLS_SRC.iterdir() if p.is_dir()}
                 | all_community_names())
        results = []
        for target in targets:
            skills = [n for n in names if not n.startswith("prompt:")]
            results.extend(uninstall_skills(
                skills, target, target_root(target), known,
                args.force, args.dry_run))
            if target == "copilot":
                prompts_dir = vscode_prompts_dir()
                for n in names:
                    if not n.startswith("prompt:"):
                        continue
                    stem = n[len("prompt:"):]
                    f = (prompts_dir / f"{stem}.prompt.md"
                         if prompts_dir else None)
                    if f and f.is_file():
                        if not args.dry_run:
                            f.unlink()
                        results.append((target, n, "removed"))
                    else:
                        results.append((target, n, "not installed"))
        print_summary(results, targets, args.dry_run)
        return
```

- [ ] **Step 4: Run full suite**

Run: `python3 -m unittest test_install -v`
Expected: all PASS

- [ ] **Step 5: Commit**

```bash
cd /Users/roj/Dev/.dotfiles && git add agent-skills/install.py agent-skills/test_install.py && git commit -m "feat(installer): --uninstall with known-name guard"
```

---

### Task 5: Picker preselection + tags

**Files:**
- Modify: `agent-skills/install.py` (`pick_items` signature, new `item_tag`, interactive branch of `main()`)
- Test: `agent-skills/test_install.py` (append `TestPickerTags`)

**Interfaces:**
- Produces: `pick_items(items, preselected=None, tags=None)` (back-compat: both optional); `item_tag(kind, name, targets, plugin_map)` → string like `"[installed] [conflict]"` or `""`.
- Consumes: `registry()`, `target_root`, `source_cache_dir`, `dirs_equal`, `vscode_prompts_dir`, `plugin_skills`.

- [ ] **Step 1: Write failing tests**

```python
class TestPickerTags(TempDirTest):
    def test_installed_tag(self):
        root = self.tmp / "claude" / "skills"
        (root / "code-tour").mkdir(parents=True)
        with mock.patch("install.target_root", return_value=root):
            tag = install.item_tag("community", "code-tour", ["claude"], {})
        self.assertEqual(tag, "[installed]")

    def test_conflict_tag_from_plugin(self):
        root = self.tmp / "claude" / "skills"
        root.mkdir(parents=True)
        with mock.patch("install.target_root", return_value=root):
            tag = install.item_tag("community", "caveman", ["claude"],
                                   {"caveman": "caveman@caveman"})
        self.assertEqual(tag, "[conflict]")

    def test_update_tag_for_stale_custom_copy(self):
        src = self.make_skill("repo", name="explain-logic",
                              content="new")
        root = self.tmp / "copilot" / "skills"
        (root / "explain-logic").mkdir(parents=True)
        (root / "explain-logic" / "SKILL.md").write_text("old")
        with mock.patch("install.target_root", return_value=root), \
             mock.patch("install.SKILLS_SRC", src.parent):
            tag = install.item_tag("skill", "explain-logic",
                                   ["copilot"], {})
        self.assertEqual(tag, "[installed] [update]")

    def test_no_tag_when_absent(self):
        root = self.tmp / "claude" / "skills"
        root.mkdir(parents=True)
        with mock.patch("install.target_root", return_value=root):
            self.assertEqual(
                install.item_tag("community", "pdf", ["claude"], {}), "")

    def test_pick_items_preselected_and_tags_render(self):
        items = [("community", "pdf"), ("community", "code-tour")]
        with mock.patch("builtins.input", side_effect=["1", ""]):
            chosen = install.pick_items(
                items, preselected=[False, True],
                tags={("community", "code-tour"): "[installed]"})
        self.assertEqual(chosen, items)  # 'pdf' toggled on by input "1"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m unittest test_install.TestPickerTags -v`
Expected: ERROR `no attribute 'item_tag'` (and TypeError for new kwargs)

- [ ] **Step 3: Implement**

Replace `pick_items` signature/body top:

```python
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
        ...  # rest of the loop unchanged
```

Add `item_tag`:

```python
def item_tag(kind, name, targets, plugin_map):
    """Picker annotation: [installed] [update] [conflict], or ''."""
    tags = []
    if kind == "prompt":
        d = vscode_prompts_dir()
        if d and (d / name).is_file():
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
```

Interactive branch of `main()` becomes:

```python
    if interactive:
        items = build_items([p.name for p in custom], prompt_files)
        reg = registry()
        plugin_map = plugin_skills()
        preselected = [reg[n][1]["default"] if k == "community" else True
                       for k, n in items]
        tags = {(k, n): item_tag(k, n, targets, plugin_map)
                for k, n in items}
        tags = {kn: t for kn, t in tags.items() if t}
        chosen = pick_items(items, preselected=preselected, tags=tags)
        sel_skills = {n for k, n in chosen if k == "skill"}
        sel_prompts = {n for k, n in chosen if k == "prompt"}
        sel_community = {n for k, n in chosen if k == "community"}
        custom = [p for p in custom if p.name in sel_skills]
```

- [ ] **Step 4: Run full suite**

Run: `python3 -m unittest test_install -v`
Expected: all PASS (old `TestPickItems` uses positional list only — still valid).

- [ ] **Step 5: Commit**

```bash
cd /Users/roj/Dev/.dotfiles && git add agent-skills/install.py agent-skills/test_install.py && git commit -m "feat(installer): picker tags and cherry-pick preselection"
```

---

### Task 6: README update

**Files:**
- Modify: `agent-skills/README.md`

**Interfaces:** none (docs).

- [ ] **Step 1: Edit README**

- Install section gains:

```bash
python3 install.py --status                     # what is installed where + conflicts
python3 install.py --uninstall caveman --target claude
python3 install.py --uninstall prompt:create-sb --target copilot
```

- Community list rewritten: default set (awesome-copilot five, caveman → Copilot only, debugging-and-error-recovery → Copilot only) vs cherry-picks selectable in interactive mode (addyosmani: observability-and-instrumentation, ci-cd-and-automation, security-and-hardening, deprecation-and-migration; anthropics/skills: pdf, docx, pptx, xlsx).
- New rule stated: caveman never installs to Claude — the caveman plugin covers it.
- Work VDI section: add step `python3 install.py --status` before and after install.

- [ ] **Step 2: Verify tests still green + commit**

Run: `python3 -m unittest test_install -v` — all PASS.

```bash
cd /Users/roj/Dev/.dotfiles && git add agent-skills/README.md && git commit -m "docs(agent-skills): installer v2 usage (status, uninstall, cherry-picks)"
```

---

### Task 7: Live cleanup + verification (Mac)

**Files:** none in repo — live `~/.claude/skills` operation.

- [ ] **Step 1: Remove the caveman duplicate**

Run: `rm -rf ~/.claude/skills/caveman`

- [ ] **Step 2: Verify with the new status command**

Run: `cd /Users/roj/Dev/.dotfiles/agent-skills && python3 install.py --status`
Expected: claude list has no `caveman`; final line `[  ok  ] no conflicts detected`. If other warnings appear, report them — do not auto-fix.

---

### Task 8: Catalog note update

**Files:**
- Modify: `/Users/roj/Dev/second-brain/1-Notes/Agent Skills Catalog.md`

**Interfaces:** none (docs). Second-brain is a separate vault — edit the file; do not commit from the dotfiles repo. Follow the note's own entry template (defined at its bottom).

- [ ] **Step 1: Fill "My custom skills"**

Replace `*(none yet)*` with four entries using the note's template plus **Lives at:** and **Chains:**:

- **explain-logic** — guided code-comprehension walkthroughs (PR/branch diffs, files, functions), language lenses for Java/Python/Go/shell/Bamboo. Install: `python3 install.py --target claude|copilot`. Usage: auto-trigger on Claude ("explain this PR"); `/explain-code`, `/explain-and-review` on Copilot. Chains: context-map → acquire-codebase-knowledge → explain-logic → code-tour (optional); caveman when terse output requested. Lives at: `~/Dev/.dotfiles/agent-skills/skills/explain-logic/SKILL.md`.
- **investigate-issue** — problem `.md` in, validated root cause + fix-steps `-investigation.md` out (Bamboo plans/agents, Java, Python, Bash, Go, Docker, k8s). Chains: context-map → explain-logic (when failing logic unclear) → debugging-and-error-recovery on Copilot / superpowers:systematic-debugging on Claude; every chain step has an inline fallback. Lives at: `.../investigate-issue/SKILL.md`.
- **soundboarding** — user story (LISA-<id>.md) → SB document → task-by-task implementation with review stops; two flows (create-SB, implement-SB) chained or standalone. Copilot: `/create-sb`, `/implement-sb`, `/create-implement-sb`. Lives at: `.../soundboarding/SKILL.md`.
- **interview-prep** — DevOps interview doc from CV, bundled calibration references. Standalone, no chain. Lives at: `.../interview-prep/SKILL.md`.

- [ ] **Step 2: Add "Current install state" section**

New section before "Overlaps and conflicts": intro line "Snapshot from `install.py --status`, refresh after installs." + table:

| Machine / target | Custom | Community | Plugins |
|---|---|---|---|
| Mac / Claude (`~/.claude/skills`, plugins) | explain-logic, soundboarding, interview-prep, investigate-issue (symlinks) | code-tour, context-map, acquire-codebase-knowledge, architecture-blueprint-generator, add-educational-comments (copies) | superpowers, caveman, skill-creator, code-simplifier, claude-md-management, claude-code-setup |
| Mac / Copilot (`~/.copilot/skills`) | same four (copies) | same five + caveman + debugging-and-error-recovery (copies) | n/a |
| Work VDI / Copilot (Windows) | unverified — run `install.py --status` there | unverified | n/a |

Dated 2026-07-19. Note under table: caveman removed from `~/.claude/skills` (plugin wins); rule recorded in installer.

- [ ] **Step 3: Verdict tags + quick-reference row**

- Quick reference table: add row `| agent-skills (mine) | Custom skills | explain-logic, soundboarding, interview-prep, investigate-issue + installer | Both | Auto (Claude) + prompts (Copilot) | Low |` linking to `~/Dev/.dotfiles/agent-skills`.
- Prefix each existing entry's **Overlaps** verdict with a bold status: **Installed** (superpowers, caveman, anthropics — partial: spec/template reference only), **Cherry-pick via installer** (addyosmani ops skills, anthropics document skills), **Skip / browse only** (mattpocock, karpathy, VoltAgent, alirezarezvani, graphify, skills-manage, agentic-awesome-skills).
- caveman entry: add line "Claude: plugin only; installer refuses `~/.claude/skills` copy (duplicate context)."

- [ ] **Step 4: Verify note renders**

Read the modified note top-to-bottom once; check wiki-links (`[[#Overlaps and conflicts]]`, `[[#My custom skills]]`) still resolve to existing headings.

---

## Self-Review (done at write time)

- **Spec coverage:** registry+policy (T1–2), status (T3), uninstall (T4), picker tags (T5), README (T6), conflict fix (T7), catalog (T8). Error handling: cache fallback unchanged (T1 wrappers), missing plugin config → `{}` (T3 test), symlink uninstall never touches repo (T4 test). Success criteria all mapped.
- **Placeholders:** the two `...` in Task 2/5 main() snippets mark explicitly unchanged existing lines, not omitted new code.
- **Type consistency:** `registry()` returns `(source, meta)` tuples everywhere; statuses are plain strings; `item_tag` and `gather_status` consume the same `plugin_skills()` map shape.
