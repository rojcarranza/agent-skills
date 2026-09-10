# explain-feature-changes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add the `explain-feature-changes` agent skill, which explains the author's own feature branch against its base and writes PR-ready text, and make `install.py` install the skills it calls wherever it is installed.

**Architecture:** A standard Agent Skills folder (`SKILL.md` workflow + two `references/` files + one example) under `agent-skills/skills/`, plus a same-name Copilot prompt file. The installer gains a per-source `subdir` key (to fetch `write-pr-description` from `warpdotdev/common-skills`, which keeps skills under `.agents/skills/`) and a `REQUIRES` map that pulls a skill's dependencies into every install mode.

**Tech Stack:** Python 3.8+ stdlib (`install.py`, `unittest`), Markdown skill files, Git.

**Spec:** `agent-skills/docs/superpowers/specs/2026-09-10-explain-feature-changes-design.md`

## Global Constraints

- Work on branch `feat/explain-feature-changes` (already created; the spec commits are on it).
- Commits use Roj's Git identity only. **No** `Co-Authored-By`, `Claude-Session`, or "Generated with Claude" lines in any commit message (user's global `CLAUDE.md` overrides the harness attribution reminder).
- No runtime dependency on, or mention of, the user's custom skills (`explain-logic`, `code-review-pr`, `code-review-pr-fast`, `investigate-issue`, `soundboarding`, `tour-codebase`, `interview-prep`) inside the new skill's files.
- Skill frontmatter holds exactly `name` and `description`.
- Every `git` command written in the skill or prompt is shell-neutral: no `$(`, no `|`, no bare `grep`/`sed`/`awk`. Code search uses `git grep -n`.
- The prompt file uses no `${selection}` or `${input:...}` variables.
- File references in skill output are plain `path/from/repo/root:start-end` text, never `#L` anchors.
- The skill is read-only: it writes only `<branch-slug>-changes.md` at the repository root and `.tours/changes-<branch-slug>.tour`.
- Base branch order: argument → `develop` (`origin/develop`, else local) → `main` (`origin/main`, else local) → ask. No sanity gate.
- Only committed work is explained (`<base>...HEAD`); uncommitted files are listed in the report header.
- `install.py` stays stdlib-only; sources without `subdir` behave exactly as before.
- Test command: `cd agent-skills && python3 -m unittest test_install -v` (170 tests pass at the start).
- Scratch files (fixture repositories) go in the session scratchpad: `/tmp/claude-1745305124/-home-rcarranza-Development--dotfiles/b2190cfd-599d-4e20-84ac-b0b631c0200e/scratchpad` — referred to below as `$SCRATCH`. Shell state does not persist between commands: start every command that uses it with `SCRATCH=/tmp/claude-1745305124/-home-rcarranza-Development--dotfiles/b2190cfd-599d-4e20-84ac-b0b631c0200e/scratchpad;`, and write the expanded path into subagent prompts.

## File map

| File | Responsibility |
|---|---|
| `agent-skills/install.py` | `subdir` support, `warp-common-skills` source, `REQUIRES` map and its helpers, wiring into install / status / uninstall |
| `agent-skills/test_install.py` | Tests for the above, plus skill frontmatter and shell-portability tests |
| `agent-skills/skills/explain-feature-changes/SKILL.md` | Workflow, phases 1–8 |
| `agent-skills/skills/explain-feature-changes/references/tracing.md` | Symbol card, tracing method, language trace paths, architecture checklist, tests |
| `agent-skills/skills/explain-feature-changes/references/output-template.md` | Report skeleton, evidence and style rules, PR comment format, fallback PR rules |
| `agent-skills/skills/explain-feature-changes/examples/example-run.md` | Worked output on the fixture repository |
| `agent-skills/skills/explain-feature-changes/USAGE.md` | Per-IDE invocation, dependencies, JetBrains checklist, skills-considered table |
| `agent-skills/prompts/explain-feature-changes.prompt.md` | Copilot VS Code `/explain-feature-changes` (and repo-seeded JetBrains) |
| `agent-skills/README.md` | Layout entry, warp source, dependencies section, stale-line fix, counts |
| `agent-skills/docs/community-skills.md` | `write-pr-description` entry |

---

### Task 1: Installer — per-source `subdir` and the `warp-common-skills` source

**Files:**
- Modify: `agent-skills/install.py` (constants near line 58, `SOURCES` near line 117, helpers after `source_by_label` near line 185, `item_tag` near line 385, `update_source_cache`/`update_repo_cache` near lines 682–724, `install_community_for_target` near line 758)
- Test: `agent-skills/test_install.py`

**Interfaces:**
- Produces: `install.source_skills_subdir(source) -> str`; `install.update_repo_cache(cache, url, branch, sparse, dry_run, label, fallback_url, skills_subdir="skills")`; registry entry `"write-pr-description"` in source labelled `"warp-common-skills"` with `{"targets": ANY, "default": True}`; constant `install.WARP_REPO_URL`.

- [ ] **Step 1: Write the failing tests**

In `test_install.py`, update the existing assertion in `TestRegistry.test_default_names_match_legacy_constants` to:

```python
    def test_default_names_match_legacy_constants(self):
        self.assertEqual(
            install.default_community_names(),
            set(install.COMMUNITY_SKILLS + install.CAVEMAN_SKILLS
                + ["debugging-and-error-recovery", "write-pr-description"]))
```

Then add this class after `TestRegistry`:

```python
class TestSourceSubdir(TempDirTest):
    """Sources may keep their skill folders somewhere other than skills/ —
    warpdotdev/common-skills uses .agents/skills/."""

    def test_default_subdir_is_skills(self):
        source = install.source_by_label("addy-agent-skills")
        self.assertEqual(install.source_skills_subdir(source), "skills")

    def test_warp_source_registers_write_pr_description(self):
        source, meta = install.registry()["write-pr-description"]
        self.assertEqual(source["label"], "warp-common-skills")
        self.assertEqual(source["url"], install.WARP_REPO_URL)
        self.assertEqual(install.source_skills_subdir(source),
                         ".agents/skills")
        self.assertEqual(meta, {"targets": install.ANY, "default": True})

    def test_sparse_paths_and_cache_check_use_the_subdir(self):
        source = install.source_by_label("warp-common-skills")
        with mock.patch("install.update_repo_cache") as m:
            install.update_source_cache(source, dry_run=False)
        self.assertEqual(m.call_args[0][3],
                         [".agents/skills/write-pr-description"])
        self.assertEqual(m.call_args.kwargs["skills_subdir"],
                         ".agents/skills")

    def test_failed_fetch_reuses_an_existing_subdir_cache(self):
        cache = self.tmp / "warp"
        (cache / ".git").mkdir(parents=True)
        (cache / ".agents" / "skills" / "write-pr-description").mkdir(
            parents=True)
        boom = subprocess.CalledProcessError(128, ["git", "fetch"])
        with mock.patch("install.run_git", side_effect=boom):
            result = install.update_repo_cache(
                cache, "u", "main", [], False, "warp", "f",
                skills_subdir=".agents/skills")
        self.assertEqual(result, cache)

    def test_community_install_reads_from_the_subdir(self):
        cache = self.tmp / "cache"
        skill = cache / ".agents" / "skills" / "tool-w"
        skill.mkdir(parents=True)
        (skill / "SKILL.md").write_text("w")
        sources = [{
            "label": "fake", "url": "u", "branch": "main", "cache": "fake",
            "fallback": "f", "subdir": ".agents/skills", "_cache": cache,
            "skills": {"tool-w": {"targets": install.ANY, "default": True}},
        }]
        dest = self.tmp / "dest"
        with mock.patch("install.SOURCES", sources):
            results = install.install_community_for_target(
                "claude", dest, {"tool-w"}, dry_run=False)
        self.assertEqual(results, [("claude", "tool-w", "installed")])
        self.assertTrue((dest / "tool-w" / "SKILL.md").is_file())

    def test_picker_update_tag_reads_from_the_subdir(self):
        cache = self.tmp / "cache"
        src = cache / ".agents" / "skills" / "write-pr-description"
        src.mkdir(parents=True)
        (src / "SKILL.md").write_text("new")
        root = self.tmp / "claude" / "skills"
        (root / "write-pr-description").mkdir(parents=True)
        (root / "write-pr-description" / "SKILL.md").write_text("old")
        with mock.patch("install.target_root", return_value=root), \
             mock.patch("install.source_cache_dir", return_value=cache):
            tag = install.item_tag("community", "write-pr-description",
                                   ["claude"], {})
        self.assertEqual(tag, "[installed] [update]")
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd agent-skills && python3 -m unittest test_install.TestSourceSubdir test_install.TestRegistry -v`
Expected: FAIL / ERROR — `AttributeError: module 'install' has no attribute 'source_skills_subdir'`, `KeyError: 'write-pr-description'`, and the default-names assertion fails.

- [ ] **Step 3: Implement**

In `install.py`, after `ADDY_BRANCH = "main"` add:

```python
WARP_REPO_URL = "https://github.com/warpdotdev/common-skills.git"
WARP_BRANCH = "main"
```

In `SOURCES`, insert this entry between the `addy-agent-skills` entry and the `anthropics-skills` entry:

```python
    {
        "label": "warp-common-skills",
        "url": WARP_REPO_URL,
        "branch": WARP_BRANCH,
        "cache": "warp-common-skills",
        # warpdotdev keeps its skills under .agents/skills, not skills/.
        "subdir": ".agents/skills",
        "fallback": ("https://github.com/warpdotdev/common-skills/tree/main/"
                     ".agents/skills"),
        "skills": {
            # Shapes the PR Explanation section of explain-feature-changes.
            "write-pr-description": {"targets": ANY, "default": True},
        },
    },
```

After `def source_by_label(label): ...` add:

```python
def source_skills_subdir(source):
    """Directory inside a source's cache that holds its skill folders."""
    return source.get("subdir", "skills")
```

In `item_tag`, replace:

```python
            elif name in reg:
                cand = (source_cache_dir(reg[name][0]) / "skills" / name)
```

with:

```python
            elif name in reg:
                source = reg[name][0]
                cand = (source_cache_dir(source)
                        / source_skills_subdir(source) / name)
```

Replace `update_source_cache` with:

```python
def update_source_cache(source, dry_run, names=None):
    names = sorted(names) if names else sorted(source["skills"])
    subdir = source_skills_subdir(source)
    return update_repo_cache(
        source_cache_dir(source), source["url"], source["branch"],
        [f"{subdir}/{n}" for n in names], dry_run, source["label"],
        source["fallback"], skills_subdir=subdir)
```

Replace the whole `update_repo_cache` function with:

```python
def update_repo_cache(cache, url, branch, sparse, dry_run, label,
                      fallback_url, skills_subdir="skills"):
    """Sparse-clone/refresh a skills repo. Returns cache path or None when
    no usable cache exists. skills_subdir: where the skill folders live
    inside the repo."""
    skills_dir = cache / skills_subdir
    if dry_run:
        log(f"dry-run: would clone/update {url} into {cache}")
        return cache if skills_dir.is_dir() else None
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
        if skills_dir.is_dir():
            warn("Using existing local cache instead.")
            return cache
        warn(f"Fallback: download the skill folders as ZIP from {fallback_url}")
        warn(f"and unzip into {skills_dir}, then re-run this script.")
        return None
```

In `install_community_for_target`, replace:

```python
            src = cache / "skills" / name
```

with:

```python
            src = cache / source_skills_subdir(source) / name
```

- [ ] **Step 4: Run the full suite**

Run: `cd agent-skills && python3 -m unittest test_install 2>&1 | grep -E "^(Ran|OK|FAILED)"`
Expected: `Ran 176 tests` and `OK`.

- [ ] **Step 5: Check the real fetch once**

Run: `cd agent-skills && python3 -c "import install; s = install.source_by_label('warp-common-skills'); print(install.update_source_cache(s, dry_run=False))"`
Then: `ls ~/.agent-skills-cache/warp-common-skills/.agents/skills/write-pr-description`
Expected: the cache path is printed and the listing shows `SKILL.md`. If the clone fails, stop and report the `git` error — do not continue with a guessed path.

- [ ] **Step 6: Commit**

```bash
git add agent-skills/install.py agent-skills/test_install.py
git commit -m "feat(agent-skills): fetch community skills from a per-source subdir

warpdotdev/common-skills keeps its skills under .agents/skills. Add a
subdir key and install its write-pr-description skill by default."
```

---

### Task 2: Installer — `REQUIRES` dependencies in install, status and uninstall

**Files:**
- Modify: `agent-skills/install.py` (`REQUIRES` after `EXTERNALS`; helpers after the `ADDY_SKILLS = ...` line; `gather_status`; `main`)
- Test: `agent-skills/test_install.py` (add `import io` and `import re` to the imports)

**Interfaces:**
- Consumes: `all_community_names()`, `all_external_names()`, `custom_skill_names()`, `target_root(target, repo)`, `log`, `warn` (existing).
- Produces:
  - `install.REQUIRES: dict[str, tuple[str, ...]]` — starts as `{}`; Task 3 adds the real entry.
  - `install.required_by(skills, requires=None) -> dict[str, list[str]]`
  - `install.add_requirements(custom_names, sel_community, sel_externals, requires=None) -> tuple[set, set, set]`
  - `install.missing_requirements(dest_root, requires=None) -> list[tuple[str, str]]` — `(skill, requirement)`
  - `install.uninstall_dependents(names, dest_root, requires=None) -> list[tuple[str, str]]` — `(requirement_being_removed, dependent)`
  - Warning strings (exact, tests match them):
    - install: `f"{target}: {skill} requires {dep}, which is not installed{hint}"` with `hint` = `" — re-run without --skills-only when online"` or `" — see the fetch warnings above"`
    - status: `f"{target}: {skill} requires {dep}, which is not installed here — re-run install.py"`
    - uninstall: `f"{target}: removing {dep}, but {skill} still requires it — {skill} will run on its fallback"`
    - picker/flag addition log: `f"{name} (required by {', '.join(dependents)})"`

- [ ] **Step 1: Write the failing tests**

Add `import io` and `import re` to the import block at the top of `test_install.py`. Then append:

```python
class TestRequiredBy(unittest.TestCase):
    def test_direct_requirements(self):
        self.assertEqual(
            install.required_by(["a"], {"a": ("x", "y")}),
            {"x": ["a"], "y": ["a"]})

    def test_chains_through_skills_with_their_own_requirements(self):
        self.assertEqual(
            install.required_by(["a"], {"a": ("b",), "b": ("x",)}),
            {"b": ["a"], "x": ["b"]})

    def test_shared_requirement_lists_every_dependent(self):
        self.assertEqual(
            install.required_by(["a", "b"], {"a": ("x",), "b": ("x",)}),
            {"x": ["a", "b"]})

    def test_nothing_required(self):
        self.assertEqual(install.required_by(["a"], {}), {})


class TestAddRequirements(unittest.TestCase):
    def test_unticked_community_requirement_comes_back_and_is_logged(self):
        with mock.patch("sys.stdout", new_callable=io.StringIO) as out:
            names, community, externals = install.add_requirements(
                {"needs-dep"}, set(), set(), {"needs-dep": ("code-tour",)})
        self.assertEqual(community, {"code-tour"})
        self.assertEqual(names, {"needs-dep"})
        self.assertEqual(externals, set())
        self.assertIn("code-tour (required by needs-dep)", out.getvalue())

    def test_external_requirement_goes_to_externals(self):
        with mock.patch("sys.stdout", new_callable=io.StringIO):
            _, community, externals = install.add_requirements(
                {"needs-dep"}, set(), set(), {"needs-dep": ("graphify",)})
        self.assertEqual(externals, {"graphify"})
        self.assertEqual(community, set())

    def test_custom_requirement_goes_to_custom_skills(self):
        with mock.patch("install.custom_skill_names",
                        return_value={"needs-dep", "helper"}), \
             mock.patch("sys.stdout", new_callable=io.StringIO):
            names, _, _ = install.add_requirements(
                {"needs-dep"}, set(), set(), {"needs-dep": ("helper",)})
        self.assertEqual(names, {"needs-dep", "helper"})

    def test_already_selected_is_not_logged(self):
        with mock.patch("sys.stdout", new_callable=io.StringIO) as out:
            install.add_requirements({"needs-dep"}, {"code-tour"}, set(),
                                     {"needs-dep": ("code-tour",)})
        self.assertNotIn("required by", out.getvalue())

    def test_inputs_are_not_mutated(self):
        community = set()
        with mock.patch("sys.stdout", new_callable=io.StringIO):
            install.add_requirements({"needs-dep"}, community, set(),
                                     {"needs-dep": ("code-tour",)})
        self.assertEqual(community, set())


class TestMissingRequirements(TempDirTest):
    REQ = {"needs-dep": ("code-tour", "context-map")}

    def test_reports_each_missing_requirement(self):
        (self.tmp / "needs-dep").mkdir()
        (self.tmp / "code-tour").mkdir()
        self.assertEqual(install.missing_requirements(self.tmp, self.REQ),
                         [("needs-dep", "context-map")])

    def test_dependent_not_installed_reports_nothing(self):
        self.assertEqual(install.missing_requirements(self.tmp, self.REQ), [])

    def test_symlinked_requirement_counts_as_present(self):
        (self.tmp / "needs-dep").mkdir()
        target = self.tmp / "elsewhere"
        target.mkdir()
        (self.tmp / "code-tour").symlink_to(target)
        (self.tmp / "context-map").mkdir()
        self.assertEqual(install.missing_requirements(self.tmp, self.REQ), [])

    def test_status_warns_about_a_missing_requirement(self):
        (self.tmp / "needs-dep").mkdir()
        with mock.patch("install.REQUIRES", {"needs-dep": ("code-tour",)}):
            _, warnings = install.gather_status("claude", self.tmp,
                                                {"needs-dep"}, {})
        self.assertIn("claude: needs-dep requires code-tour, which is not "
                      "installed here — re-run install.py", warnings)


class TestUninstallDependents(TempDirTest):
    REQ = {"needs-dep": ("code-tour",)}

    def test_removing_a_requirement_of_an_installed_skill(self):
        (self.tmp / "needs-dep").mkdir()
        self.assertEqual(
            install.uninstall_dependents(["code-tour"], self.tmp, self.REQ),
            [("code-tour", "needs-dep")])

    def test_removing_both_is_silent(self):
        (self.tmp / "needs-dep").mkdir()
        self.assertEqual(
            install.uninstall_dependents(["code-tour", "needs-dep"],
                                         self.tmp, self.REQ), [])

    def test_dependent_absent_is_silent(self):
        self.assertEqual(
            install.uninstall_dependents(["code-tour"], self.tmp, self.REQ),
            [])


class TestRequiresInvariants(unittest.TestCase):
    """REQUIRES must track the real skill names — a rename that forgets the
    map fails here instead of silently dropping dependencies."""

    def test_keys_are_custom_skills(self):
        for skill in install.REQUIRES:
            with self.subTest(skill=skill):
                self.assertIn(skill, install.custom_skill_names())

    def test_values_are_known_names(self):
        known = (install.custom_skill_names() | install.all_community_names()
                 | install.all_external_names())
        for skill, deps in install.REQUIRES.items():
            for dep in deps:
                with self.subTest(skill=skill, dep=dep):
                    self.assertIn(dep, known)

    def test_requirements_install_everywhere_the_dependent_does(self):
        reg, ext = install.registry(), install.externals()
        for skill, deps in install.REQUIRES.items():
            for dep in deps:
                targets = (reg[dep][1]["targets"] if dep in reg
                           else ext[dep]["targets"] if dep in ext
                           else install.ANY)
                for target in install.ANY:
                    with self.subTest(skill=skill, dep=dep, target=target):
                        self.assertIn(target, targets)


class TestMainRequirements(TempDirTest):
    """Through main(): requirements ride along with their skill, a run that
    cannot fetch them says so, and uninstalling one warns."""

    REQ = {"needs-dep": ("code-tour",)}

    def run_main(self, argv):
        skills = self.tmp / "skills"
        if not (skills / "needs-dep").exists():
            self.make_skill("skills", name="needs-dep")
        prompts = self.tmp / "prompts"
        prompts.mkdir(exist_ok=True)
        home = self.tmp / "home"

        def root(target, repo=None):
            return home / target

        out, err = io.StringIO(), io.StringIO()
        with mock.patch("install.SKILLS_SRC", skills), \
             mock.patch("install.PROMPTS_SRC", prompts), \
             mock.patch("install.REQUIRES", self.REQ), \
             mock.patch("install.EXTERNALS", []), \
             mock.patch("install.target_root", side_effect=root), \
             mock.patch("install.claude_commands_dir",
                        return_value=self.tmp / "commands"), \
             mock.patch("install.update_source_cache", return_value=None), \
             mock.patch("sys.argv", ["install.py", *argv]), \
             mock.patch("sys.stdout", out), mock.patch("sys.stderr", err):
            install.main()
        return out.getvalue(), err.getvalue()

    def test_skills_only_warns_about_a_missing_requirement(self):
        _, err = self.run_main(["--target", "claude", "--skills-only"])
        self.assertIn("claude: needs-dep requires code-tour, which is not "
                      "installed — re-run without --skills-only when online",
                      err)

    def test_present_requirement_does_not_warn(self):
        (self.tmp / "home" / "claude" / "code-tour").mkdir(parents=True)
        _, err = self.run_main(["--target", "claude", "--skills-only"])
        self.assertNotIn("requires code-tour", err)

    def test_uninstalling_a_requirement_warns_and_still_removes(self):
        claude = self.tmp / "home" / "claude"
        (claude / "needs-dep").mkdir(parents=True)
        (claude / "code-tour").mkdir()
        _, err = self.run_main(["--uninstall", "code-tour",
                                "--target", "claude"])
        self.assertIn("claude: removing code-tour, but needs-dep still "
                      "requires it — needs-dep will run on its fallback", err)
        self.assertFalse((claude / "code-tour").exists())
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd agent-skills && python3 -m unittest test_install.TestRequiredBy test_install.TestAddRequirements test_install.TestMissingRequirements test_install.TestUninstallDependents test_install.TestRequiresInvariants test_install.TestMainRequirements -v`
Expected: ERROR — `AttributeError: module 'install' has no attribute 'required_by'` (and `REQUIRES`, `add_requirements`, `missing_requirements`, `uninstall_dependents`).

- [ ] **Step 3: Implement the map and helpers**

In `install.py`, directly after the closing `]` of `EXTERNALS`, add:

```python
# Skills a custom skill calls at runtime. Installing the key installs every
# value alongside it, to the same targets, in every install mode. Values may
# be community skills, externals or other custom skills; chains are followed.
REQUIRES = {}
```

Directly after the line `ADDY_SKILLS = list(source_by_label("addy-agent-skills")["skills"])`, add:

```python
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
            if dep in removing:
                hits.append((dep, skill))
    return hits
```

- [ ] **Step 4: Wire status**

In `gather_status`, replace the final `    return rows, warnings` (the one after the `for entry in sorted(dest_root.iterdir()):` loop, not the early return) with:

```python
    for skill, dep in missing_requirements(dest_root):
        warnings.append(f"{target}: {skill} requires {dep}, which is not "
                        f"installed here — re-run install.py")
    return rows, warnings
```

- [ ] **Step 5: Wire uninstall**

In `main`, inside the `if args.uninstall:` block, change the start of the loop from:

```python
        for target in targets:
            # Externals are removed by their own CLI in personal scope; in
```

to:

```python
        for target in targets:
            for dep, skill in uninstall_dependents(
                    names, target_root(target, repo)):
                warn(f"{target}: removing {dep}, but {skill} still requires "
                     f"it — {skill} will run on its fallback")
            # Externals are removed by their own CLI in personal scope; in
```

- [ ] **Step 6: Wire install**

In `main`, directly before `    if args.skills_only:` (after the `if interactive: ... else: ...` block), add:

```python
    names, sel_community, sel_externals = add_requirements(
        {p.name for p in custom}, sel_community, sel_externals)
    custom = sorted(p for p in SKILLS_SRC.iterdir()
                    if p.is_dir() and p.name in names)
```

At the very end of `main`, after `    print_summary(results, targets, args.dry_run)`, add:

```python
    if not args.dry_run:
        # Last, so a missing dependency cannot scroll out of view.
        hint = (" — re-run without --skills-only when online"
                if args.skills_only else " — see the fetch warnings above")
        for target in targets:
            for skill, dep in missing_requirements(target_root(target, repo)):
                warn(f"{target}: {skill} requires {dep}, which is not "
                     f"installed{hint}")
```

- [ ] **Step 7: Run the full suite**

Run: `cd agent-skills && python3 -m unittest test_install 2>&1 | grep -E "^(Ran|OK|FAILED)"`
Expected: `Ran 198 tests` and `OK`.

- [ ] **Step 8: Commit**

```bash
git add agent-skills/install.py agent-skills/test_install.py
git commit -m "feat(agent-skills): install the skills a custom skill requires

A REQUIRES map pulls each skill's dependencies into flag, picker and
--repo runs. --skills-only, --status and --uninstall warn when a
requirement is missing or about to be removed."
```

---

### Task 3: Fixture repository and baseline run (RED)

Skill TDD per `superpowers:writing-skills`: record what an agent does today, before the skill exists. Nothing is committed in this task.

**Files:**
- Create: `$SCRATCH/make-fixture.sh` (throwaway)
- Create: `$SCRATCH/fixture/` (throwaway Git repository)
- Create: `$SCRATCH/baseline-score.md` (throwaway notes)

**Interfaces:**
- Produces: the fixture at `$SCRATCH/fixture` on branch `feature/LISA-123-integration-decision`, and the 12-item scorecard below, used again in Task 5.

- [ ] **Step 1: Write the fixture builder**

Create `$SCRATCH/make-fixture.sh`:

```bash
#!/usr/bin/env bash
# Builds a small Python repo whose feature branch mirrors the idea's
# should_trigger_integration() scenario. Usage: make-fixture.sh <dir>
set -euo pipefail
dir="$1"
rm -rf "$dir"
mkdir -p "$dir"
cd "$dir"
git init -q -b develop
g() { git -c user.name=fixture -c user.email=fixture@example.com "$@"; }

mkdir -p app config tests
cat > app/__init__.py <<'EOF'
EOF
cat > app/integration.py <<'EOF'
def trigger_integration(event):
    print(f"sending {event['id']} to partner")
EOF
cat > app/processor.py <<'EOF'
from app.integration import trigger_integration


def process_event(event, config):
    """Handle one incoming event."""
    if event.get("type") in ("order.created", "order.updated") and not event.get("test"):
        trigger_integration(event)
    return {"id": event["id"], "handled": True}
EOF
cat > app/main.py <<'EOF'
import json
import sys

import yaml

from app.processor import process_event


def main():
    with open("config/settings.yaml") as f:
        config = yaml.safe_load(f)
    for line in sys.stdin:
        process_event(json.loads(line), config)


if __name__ == "__main__":
    main()
EOF
cat > config/settings.yaml <<'EOF'
integration:
  endpoint: https://partner.example/api
EOF
cat > tests/test_processor.py <<'EOF'
from app.processor import process_event


def test_returns_handled():
    assert process_event({"id": "1", "type": "order.created"}, {}) == {"id": "1", "handled": True}
EOF
echo "# Order events service" > README.md
g add -A
g commit -q -m "Initial order event processor"

git switch -q -c feature/LISA-123-integration-decision
cat > app/decision.py <<'EOF'
def should_trigger_integration(event, config):
    """Decide whether this event goes to the partner integration."""
    if event.get("test"):
        return False
    allowed = config.get("integration", {}).get("event_types", [])
    if event.get("type") not in allowed:
        return False
    return True
EOF
cat > app/processor.py <<'EOF'
from app.decision import should_trigger_integration
from app.integration import trigger_integration


def process_event(event, config):
    """Handle one incoming event."""
    if should_trigger_integration(event, config):
        trigger_integration(event)
    return {"id": event["id"], "handled": True}
EOF
cat > config/settings.yaml <<'EOF'
integration:
  endpoint: https://partner.example/api
  event_types:
    - order.created
    - order.updated
    - order.shipped
EOF
g add -A
g commit -q -m "LISA-123 move integration decision into should_trigger_integration"

cat > app/decision.py <<'EOF'
def should_trigger_integration(event, config):
    """Decide whether this event goes to the partner integration."""
    if event.get("test"):
        return False
    allowed = config.get("integration", {}).get("event_types", [])
    if event.get("type") not in allowed:
        return False
    return validate_conditions(event)


def validate_conditions(event):
    """An event must have an id and must not be cancelled."""
    return bool(event.get("id")) and event.get("status") != "cancelled"
EOF
g add -A
g commit -q -m "LISA-123 skip cancelled orders and events without an id"

cat > tests/test_decision.py <<'EOF'
from app.decision import should_trigger_integration

CONFIG = {"integration": {"event_types": ["order.created", "order.shipped"]}}


def test_allowed_type_triggers():
    assert should_trigger_integration({"id": "1", "type": "order.shipped"}, CONFIG)


def test_test_events_never_trigger():
    assert not should_trigger_integration({"id": "1", "type": "order.created", "test": True}, CONFIG)


def test_cancelled_orders_do_not_trigger():
    assert not should_trigger_integration({"id": "1", "type": "order.created", "status": "cancelled"}, CONFIG)
EOF
g add -A
g commit -q -m "LISA-123 add tests for the integration decision"

# develop moves on after the branch point: a two-dot diff would wrongly
# show this README change as part of the feature.
git switch -q develop
echo "Run locally: python -m app.main < events.jsonl" >> README.md
g commit -q -am "docs: describe local run"
git switch -q feature/LISA-123-integration-decision

# Uncommitted work the report must list but not explain.
echo "# WIP metrics" > app/metrics.py
```

- [ ] **Step 2: Build it and verify its shape**

Run: `bash "$SCRATCH/make-fixture.sh" "$SCRATCH/fixture" && git -C "$SCRATCH/fixture" log --oneline develop..HEAD && git -C "$SCRATCH/fixture" status --porcelain`
Expected: three `LISA-123 ...` commits, and `?? app/metrics.py`.

Run: `git -C "$SCRATCH/fixture" diff --name-status develop...HEAD`
Expected exactly: `A app/decision.py`, `M app/processor.py`, `M config/settings.yaml`, `A tests/test_decision.py` — no `README.md`.

- [ ] **Step 3: The scorecard**

Create `$SCRATCH/baseline-score.md` with this checklist (the same 12 items score Task 5):

```markdown
| # | Expected in the output | Owning phase |
|---|---|---|
| 1 | Comparison line `feature/LISA-123-integration-decision → develop` with a merge-base SHA | 1 |
| 2 | `app/metrics.py` listed as uncommitted and not explained | 2 |
| 3 | The develop-only README change is NOT described as a branch change | 2 |
| 4 | `should_trigger_integration()` at `app/decision.py:1-8`, called by `process_event()` at `app/processor.py:7`, which is called by `main()` at `app/main.py:13` | 4 |
| 5 | Before: inline condition at `app/processor.py:6` (merge base) with hard-coded `order.created` / `order.updated` and the test-event check | 4 |
| 6 | After: types from `integration.event_types` (adds `order.shipped`); cancelled orders and events without `id` no longer trigger (`app/decision.py:11-13`) | 4 |
| 7 | Intent labelled: extraction and skip-cancelled confirmed by commits; `order.shipped` reason likely/unknown | 5 |
| 8 | Tests: `tests/test_decision.py` covers allowed type, test events, cancelled; missing-id path untested | 4 |
| 9 | Observation: config without `integration.event_types` triggers nothing (before, two types always triggered) | 6 |
| 10 | Copy/paste-ready PR Explanation with file:line references, plus per-change PR comments | 6 |
| 11 | No generic review, style or refactoring advice | 6 |
| 12 | Report at `feature-LISA-123-integration-decision-changes.md` and tour at `.tours/changes-feature-LISA-123-integration-decision.tour` | 6, 8 |
```

- [ ] **Step 4: Baseline run**

Dispatch a `general-purpose` subagent with exactly this prompt (no mention of the new skill):

```
You are working in the Git repository at <$SCRATCH/fixture, expanded>. Run
all commands with `git -C <that path>` or from that directory. The user
says: "Explain my changes compared to develop, and give me something I can
paste into my PR." Do what the user asks. Do not modify any source file.
Reply with your full answer.
```

- [ ] **Step 5: Score the baseline**

Mark each of the 12 items pass/fail in `$SCRATCH/baseline-score.md`, quoting the output line that decides each one. Keep the notes; Task 5 compares against them. Expected: several fails — typically items 2, 4 (full caller chain), 7, 9 and 12.

---

### Task 4: Write the skill (GREEN)

**Files:**
- Create: `agent-skills/skills/explain-feature-changes/SKILL.md`
- Create: `agent-skills/skills/explain-feature-changes/references/tracing.md`
- Create: `agent-skills/skills/explain-feature-changes/references/output-template.md`
- Create: `agent-skills/skills/explain-feature-changes/examples/example-run.md`
- Modify: `agent-skills/install.py` (`REQUIRES`)
- Test: `agent-skills/test_install.py`

**Interfaces:**
- Consumes: `install.REQUIRES`, `install.SKILLS_SRC`, `TestRequiresInvariants` (Task 2).
- Produces: skill directory `explain-feature-changes`; `REQUIRES["explain-feature-changes"] == ("code-tour", "context-map", "write-pr-description")`; test class `TestExplainFeatureChangesSkill` with a `FILES` list that Task 6 extends.

- [ ] **Step 1: Write the failing tests**

In `install.py`, change `REQUIRES = {}` to:

```python
REQUIRES = {
    "explain-feature-changes": ("code-tour", "context-map",
                                "write-pr-description"),
}
```

Append to `test_install.py`:

```python
class TestExplainFeatureChangesSkill(unittest.TestCase):
    """The skill must load in every agent and its commands must run the same
    in bash, PowerShell and cmd — the JetBrains terminal on the Windows VDI
    may be any of them."""

    SKILL = install.SKILLS_SRC / "explain-feature-changes"
    FILES = [SKILL / "SKILL.md", SKILL / "references" / "tracing.md"]

    def snippets(self, text):
        fenced = re.findall(r"```[^\n]*\n(.*?)```", text, re.S)
        lines = [line.strip() for block in fenced
                 for line in block.splitlines()]
        prose = re.sub(r"```.*?```", "", text, flags=re.S)
        spans = re.findall(r"`([^`\n]+)`", prose)
        return [s.strip() for s in lines + spans if s.strip()]

    def test_frontmatter_is_name_and_description_only(self):
        text = (self.SKILL / "SKILL.md").read_text(encoding="utf-8")
        head = text.split("---")[1]
        keys = [line.split(":", 1)[0] for line in head.splitlines()
                if line.strip() and not line.startswith(" ")]
        self.assertEqual(keys, ["name", "description"])
        self.assertIn("name: explain-feature-changes", head)

    def test_description_fits_the_agent_skills_limit(self):
        text = (self.SKILL / "SKILL.md").read_text(encoding="utf-8")
        line = next(l for l in text.split("---")[1].splitlines()
                    if l.startswith("description:"))
        self.assertLessEqual(len(line[len("description:"):].strip()), 1024)

    def test_git_commands_are_shell_neutral(self):
        for f in self.FILES:
            for s in self.snippets(f.read_text(encoding="utf-8")):
                with self.subTest(file=f.name, snippet=s):
                    if s.startswith("git "):
                        self.assertNotIn("$(", s)
                        self.assertNotIn("|", s)
                    self.assertFalse(s.startswith(("grep ", "sed ", "awk ")))

    def test_no_custom_skill_is_named(self):
        others = install.custom_skill_names() - {"explain-feature-changes"}
        for f in self.SKILL.rglob("*.md"):
            text = f.read_text(encoding="utf-8")
            for name in others:
                with self.subTest(file=f.name, skill=name):
                    self.assertNotIn(name, text)
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd agent-skills && python3 -m unittest test_install.TestRequiresInvariants test_install.TestExplainFeatureChangesSkill -v`
Expected: FAIL — `explain-feature-changes` not in `custom_skill_names()`, and `FileNotFoundError` for `SKILL.md`.

- [ ] **Step 3: Create `SKILL.md`**

Create `agent-skills/skills/explain-feature-changes/SKILL.md` with exactly:

~~~markdown
---
name: explain-feature-changes
description: Explain the changes on the user's own Git feature branch compared with its base branch (develop or main) so they understand them and can explain them confidently in PR review. Covers what changed, why, how the new code works, before and after behavior, callers and code flow, and writes copy/paste-ready PR text plus per-change PR comments. Use when the user says "explain my changes compared to develop", "help me understand what I changed in this branch", "explain the new functions and code flow in my branch", "generate something I can paste into my PR", "help me explain these changes to my reviewer", or types /explain-feature-changes with an optional base branch. Not a code review. Not for a single file, a single function, or a branch the user did not write.
---

# Explain Feature Changes

Help the developer understand the changes on their own feature branch and
explain them to a reviewer. Do not summarize the diff. Trace the changed code
until its behavior is clear, then explain it.

This is not a code review. Report an issue only when it changes how the
feature should be understood (Important Observations in
`references/output-template.md`).

## Rules for the whole run

- Read-only. Run `git` commands and read files. The only other command is
  the tour validator in phase 8. Never commit, push, reset, rebase,
  checkout, switch, stash, fetch or edit source code unless the user asks.
- Write only two files: the report (phase 6) and the tour (phase 8).
- One plain `git` command per call. No `$(...)`, no pipes, no `grep`,
  `sed` or `awk`: the terminal may be PowerShell or cmd. Search code with
  `git grep -n`.
- Never invent intent, requirements or behavior. Label every intent claim
  confirmed, likely or unknown (phase 5).
- Reference code as `path/from/repo/root:start-end`. Quote code, commands
  and error text verbatim.

No terminal (agent mode off, or a Copilot setup without command access): say
so, ask the user to paste the output of `git diff <base>...HEAD` and
`git log --oneline <base>..HEAD`, explain from that, and name the skipped
phases in the report header.

## Companion skills

| Skill | Used in | If missing |
|---|---|---|
| `context-map` | phase 2, large branches | group the files yourself |
| `write-pr-description` | phase 6, PR Explanation | fallback rules in `references/output-template.md` |
| `code-tour` | phase 8 | write the tour inline |

A missing companion is not an error. Name it once in chat with its skills.sh
source (`github/awesome-copilot/context-map`,
`warpdotdev/common-skills/write-pr-description`,
`github/awesome-copilot/code-tour`) and continue with the fallback.

## Phase 1 — Resolve the base branch

First hit wins:

1. The user's argument (`/explain-feature-changes release/2.4`).
2. `develop`: use `origin/develop` if
   `git rev-parse --verify --quiet origin/develop` prints a SHA, else local
   `develop` if `git rev-parse --verify --quiet develop` does.
3. `main`: the same check for `origin/main`, then local `main`.
4. Nothing resolves: ask which branch to compare against. Never guess.

Run `git branch --show-current`. If it prints the base branch itself, or
nothing (detached HEAD), ask which branch to explain.

Run `git merge-base <base> HEAD` and keep the printed SHA as `<merge-base>`
for later commands. State the comparison before anything else:

> Comparing `feature/x → develop` (merge base `a1b2c3d`)

The base ref may be stale. Say so if it matters; do not fetch.

## Phase 2 — Collect the diff

Run, in order:

1. `git status --porcelain` — uncommitted files are not explained. List
   them in the report header, so the reader knows what the PR text leaves
   out.
2. `git log --oneline <base>..HEAD` — commit messages are intent evidence.
3. `git diff --name-status <base>...HEAD` — added, modified, deleted,
   renamed. A rename is not new code.
4. `git diff --stat <base>...HEAD` — size decides depth.
5. `git diff -U15 <base>...HEAD -- <file>` for each meaningful file.
6. Read the whole current file for anything non-trivial. A hunk alone hides
   what the surrounding code already does.

Always three-dot for `git diff`. Two-dot pulls in everything merged into the
base since the branch point.

List without explaining, one line each: vendored code, generated files,
lockfiles, binaries, and changes that only touch formatting, whitespace or
import order.

Large branch — more than about 15 meaningful files or 1000 changed lines: run
`context-map` over the changed files first, write the executive summary
before the details, and group files by responsibility (for example decision
logic, event processing, messaging, configuration, tests), never
alphabetically.

## Phase 3 — Build the change inventory

Load `references/tracing.md` from this skill's directory.

For each changed file record its status, what the file is for, what changed,
and one category: behavior, API/interface, configuration, dependency, test,
or trivial. For each function, method, class or configuration key record
whether it is new, modified or removed.

Rank by behavioral impact. Trivial changes get one line in the report and no
tracing.

## Phase 4 — Trace

For every new or behavior-changing symbol, follow `references/tracing.md`:
callers, callees, inputs, outputs, what the caller does with the result, the
code that did this job before, the tests that exercise it, and the
configuration that changes it. Then run its architecture checklist, limited
to what the diff touches.

Stop when you can state the behavior before and after in one or two
sentences each, with line references.

## Phase 5 — Establish intent

Evidence, strongest first: commit messages, ticket IDs in the branch name or
commits, test names and assertions, docs or comments changed in the diff,
naming. Label every intent claim:

- **Confirmed** — stated in a commit message, ticket reference, doc or test.
- **Likely** — "The likely purpose is …", followed by the evidence.
- **Unknown** — "The exact reason is not explicit in the code."

Never present a likely or unknown reason as confirmed.

## Phase 6 — Write

Load `references/output-template.md` and follow its skeleton, evidence rules
and style rules. Leave out any section that would be empty. Consult
`examples/example-run.md` if the depth or tone needs grounding; never copy
its facts.

PR Explanation: if `write-pr-description` is installed, follow it for this
section, with three overrides:

- The verified facts from phases 2–5 are its input. Skip its `gh` steps.
- A PR template in the repository wins, if one exists
  (`.github/pull_request_template.md`, `.github/PULL_REQUEST_TEMPLATE/`,
  `docs/pull_request_template.md`).
- Keep the `path:start-end` references this skill requires.

Otherwise use the fallback rules in `references/output-template.md`.

Write the report to `<branch-slug>-changes.md` at the repository root, where
`<branch-slug>` is the current branch name with `/` replaced by `-`. Replace
an earlier report of the same name.

In chat, print only: the comparison line, the Feature Change Overview, Key
Things to Understand, and the report path. Then say the report is untracked
and offer to add it to `.git/info/exclude` so it is never committed. Never
edit `.gitignore`.

## Phase 7 — Self-check

Confirm each item and fix the report where one fails:

- The comparison names the right base and merge base.
- Every behavior claim has a `path:start-end` reference that matches the
  current file.
- Every new or changed symbol lists its callers, or says it has none.
- Before and after are both stated for each behavior change.
- Every intent claim carries confirmed, likely or unknown.
- Tests are tied to the behavior they cover.
- No generic review findings, style advice or refactoring suggestions.
- The PR Explanation and PR Comments paste cleanly: no chat wording, no
  mention of this conversation.

## Phase 8 — Tour

Write `.tours/changes-<branch-slug>.tour` in the repository, persona
`pr-reviewer`, through the `code-tour` skill. If `code-tour` is missing,
write the JSON inline: `$schema`, `title`, `description`, and `steps` of
`{file, line, description}` is enough for the CodeTour extension to open it.

Steps follow the End-to-End Flow order and reuse only `file:line` references
already cited in the report. Never investigate again to build the tour.

Validate with `scripts/validate_tour.py` from the installed `code-tour`
skill directory: `~/.claude/skills/code-tour/`,
`~/.copilot/skills/code-tour/`, or `<repo>/.github/skills/code-tour/`. Its
own SKILL.md names an `~/.agents/...` path that usually does not exist. Skip
validation if the script is not found.

Skip the tour only when the branch changes one file and the tour would have
fewer than about three steps; say so in one line with the reason. Never add
`.tours/` to `.gitignore` and never commit the tour.
~~~

- [ ] **Step 4: Create `references/tracing.md`**

Create `agent-skills/skills/explain-feature-changes/references/tracing.md` with exactly:

~~~markdown
# Tracing changed code

Loaded at phase 3. Goal: know what each changed symbol does in the running
system, not only what its body says.

## Symbol card

Fill one card for each new or behavior-changing function, method, class,
component or configuration key.

| Field | What to write |
|---|---|
| File / lines | `path:start-end` of the current definition |
| Purpose | what it decides, computes or does — not its name restated |
| Inputs | parameters, plus state it reads (config, env vars, fields, DB) |
| Outputs | return value, plus side effects (writes, calls, messages, logs, exceptions) |
| Important conditions | the branches that change the outcome |
| Called by | each caller as `path:line`, or "no callers in the repository" |
| Calls | the downstream calls that matter |
| Return value use | what each caller does with the result |
| Before | the code that did this job at `<merge-base>`, or "new behavior" |
| Tests | the tests that exercise it, as `path:line` |

## Finding callers and callees

- Callers: `git grep -n "<name>("`, and for methods also
  `git grep -n "\.<name>("`. Search the bare name too, for references passed
  as values: callbacks, handlers, registries, config strings.
- Callees: read the body and open each call that affects the outcome.
- Stop rule: one caller level up and one callee level down. Go further only
  while the return value or side effect keeps flowing into code that changes
  behavior.
- No caller found: say so. It may be an entry point (route, CLI command,
  scheduled job, message consumer) or test-only code; find what registers
  it.

## Before and after

- Old version of a file: `git show <merge-base>:<path>`.
- Logic moved from elsewhere: `git log -S "<distinctive text>" --oneline <base>..HEAD`,
  then `git show <commit> -- <path>`. Also read the deleted lines in the
  caller's diff.
- Deleted code deserves the same attention as added code. Say which
  behavior disappeared.

## Trace paths by language

- **Java:** class → method → interface → implementation → caller. Wiring is
  often invisible: `git grep -n` for `@Component`, `@Service`, `@Bean`,
  `@Autowired`, `implements <Interface>`, and for configuration keys the
  `@Value` or `@ConfigurationProperties` that reads them. A changed
  `pom.xml` dependency is a behavior change when code uses it.
- **Python:** module → function → caller. Search
  `from <module> import <name>` and `<module>.<name>`. Unwrap decorators
  before describing a function. Click or argparse wiring shows the CLI
  entry point.
- **Go:** package → function → interface → implementation. Interfaces are
  satisfied implicitly, so search the method signature:
  `git grep -n "func (.*) <Method>("`. For goroutines and channels, state
  who sends, who receives, and who closes.
- **JavaScript / TypeScript:** export → import sites
  (`git grep -n "from '.*<module>'"`) → usage.
- **Bash:** script → function → external command. Find who runs the
  script: CI specs, other scripts, Dockerfiles, cron. State what happens
  when a command fails under the script's `set` options.
- **YAML / JSON / properties configuration:** key → code that reads the key
  → runtime behavior. Search the key's last segment as well as its full
  path. A key that nothing reads is dead configuration; say so.
- **SQL and migrations:** migration → tables and columns → the queries,
  entities or repositories that use them.
- **Pipelines (Bamboo specs, Dockerfiles, Helm, Kubernetes):** what changes
  about when or how things build, deploy or run.

## Architecture and technology checklist

Mention an item only when the diff touches it. Say how this change uses or
affects it; never explain the technology in general.

- Component responsibilities: did a job move between classes, modules or
  services?
- APIs and interfaces: signatures, request and response shapes, status
  codes, public methods, and who consumes them.
- Dependency injection and wiring.
- Messaging (Kafka topics, queues, events): producers, consumers, message
  shape, keys, ordering.
- Databases: schema, queries, transactions.
- Configuration: new keys, changed defaults, behavior when a key is absent.
- External integrations: calls to other systems, timeouts, retries.
- Concurrency and asynchronous processing.
- Error handling: new exceptions, swallowed errors, changed error flow.
- Processing pipelines and CI/CD: what runs, when, and in what order.

## Tests

For each new or changed test: the behavior it pins, the new scenarios, and
the implementation lines it exercises. Say whether each new behavior path
has a test. Mention a gap only when it matters for understanding the
feature, for example a new branch that no test reaches.
~~~

- [ ] **Step 5: Create `references/output-template.md`**

Create `agent-skills/skills/explain-feature-changes/references/output-template.md` with exactly:

~~~markdown
# Report template

Loaded at phase 6. The report serves the developer first and the reviewer
second. Leave out any section that would be empty; never write "N/A".

## Skeleton

    # <branch> — change explanation

    Comparing `<branch> → <base>` (merge base `<sha>`), <n> commits.
    Uncommitted, not covered: <files, or "none">.
    Listed only (generated, vendored, formatting): <files, or "none">.
    Skipped phases: <only when there was no terminal>.

    # Feature Change Overview
    2–5 sentences: what the branch does, the main mechanism, the visible
    behavior change.

    # Why This Change Exists
    One bullet per reason, each labelled Confirmed, Likely or Unknown, with
    its evidence.

    # Changes by File
    ## `path/to/file` (added | modified | deleted | renamed)
    ### What changed
    ### Why
    ### Important functions/classes
    ### Before → After

    # New Functions / Classes
    ## `name()`
    The symbol card from references/tracing.md as an indented block.

    # End-to-End Flow
    From the entry point to the final effect, in run order, one hop per
    line, each with `path:line`.

    # Key Things to Understand
    3–7 numbered points the developer must be able to say out loud in review.

    # PR Explanation

    # PR Comments

    # Important Observations

Large branch: replace "Changes by File" with "Changes by Area", one `##` per
responsibility, listing its files under it. Put a five-line executive
summary before the overview.

A file with only a trivial change gets one line under its heading, not the
four subsections.

## Evidence rules

- Every behavior claim carries a `path:start-end` (or `path:line`)
  reference to the current file. Old code is referenced with "at the merge
  base".
- Every intent claim carries Confirmed, Likely or Unknown.
- No impact claim without evidence. Write "removes the repeated lookup
  previously performed by the caller", not "improves performance". If the
  impact depends on runtime conditions, say that.
- When code you could not read decides the behavior (a library, a service
  outside the repository), say so instead of guessing.

## Style

Write like a senior engineer explaining the change to another engineer:
factual, concise, tied to the code.

- Prefer: "Added", "Moved", "Changed", "Removed", "The function now",
  "Previously", "The caller now", "This separates", "This allows".
- Do not write, unless the code proves it: "elegantly", "robustly",
  "seamlessly", "enhances", "significantly improves", "comprehensive".
- Do not restate the diff line by line, explain language syntax, or teach
  the technology in general.

## PR Explanation — fallback rules

Used when `write-pr-description` is not installed.

- Open with 1–3 sentences: what changed and why.
- Then "Behavior changes" as bullets, each with a `path:start-end`
  reference. Include removed behavior.
- Then the flow on one line: `a()` → `b()` → `c()`.
- Then "Tests": what the tests cover, in one or two lines.
- No file inventory, no history of how the branch evolved, no padding.
- Short: a paragraph for a mechanical change, a few hundred words for a
  behavior change.

## PR Comments

One comment per meaningful change. Group related hunks into one comment;
never comment on trivial lines.

    ### `path:start-end` — <short title>
    What was added or changed, in one sentence.
    What happened before.
    The resulting flow or behavior, and why it matters to the reader.

## Important Observations

At most about five. Only items that change how the feature should be
understood:

- an unexpected behavior change,
- suspicious control flow,
- missing handling on a new path,
- dependency or configuration implications,
- tests that do not match the implementation.

Each item names the lines and the concrete consequence. For a full review,
tell the user to run a dedicated code-review skill.
~~~

- [ ] **Step 6: Create `examples/example-run.md`**

Create `agent-skills/skills/explain-feature-changes/examples/example-run.md` with exactly:

~~~markdown
# Example run

Worked example on a small Python service. The branch
`feature/LISA-123-integration-decision` moves the decision "should this
event go to the partner integration?" out of `process_event()` into its own
module. Use it to calibrate depth and tone. Never copy its facts into a real
report.

## Chat output

    Comparing `feature/LISA-123-integration-decision → develop` (merge base `3f9c2e1`)

    <Feature Change Overview, as in the report>
    <Key Things to Understand, as in the report>

    Full report: feature-LISA-123-integration-decision-changes.md (untracked).
    Add it to .git/info/exclude so it is never committed?

## Report

# feature/LISA-123-integration-decision — change explanation

Comparing `feature/LISA-123-integration-decision → develop` (merge base
`3f9c2e1`), 3 commits.
Uncommitted, not covered: `app/metrics.py` (untracked).
Listed only (generated, vendored, formatting): none.

# Feature Change Overview

The branch moves the integration decision out of `process_event()` into a
new function, `should_trigger_integration()` (`app/decision.py:1-8`). The
event types that trigger the integration now come from configuration
(`integration.event_types`) instead of a hard-coded tuple, and the list adds
`order.shipped`. Two new conditions stop the trigger: cancelled orders and
events without an `id` (`app/decision.py:11-13`).

# Why This Change Exists

- Confirmed: the decision moved into its own function — commit "LISA-123
  move integration decision into should_trigger_integration".
- Confirmed: cancelled orders and events without an id are skipped — commit
  "LISA-123 skip cancelled orders and events without an id".
- Likely: the event types moved to configuration so they can change without
  a code change. The new key sits next to `integration.endpoint` in
  `config/settings.yaml`.
- Unknown: why `order.shipped` was added. The exact reason is not explicit
  in the code.

# Changes by File

## `app/decision.py` (added)

### What changed
New module with `should_trigger_integration()` (`app/decision.py:1-8`) and
`validate_conditions()` (`app/decision.py:11-13`).

### Why
Holds the whole trigger decision in one place (confirmed by commit message).

### Important functions/classes
- `should_trigger_integration(event, config)` returns `False` for test
  events and for types not in `integration.event_types`, otherwise defers to
  `validate_conditions()`.
- `validate_conditions(event)` requires a truthy `id` and a `status` other
  than `cancelled`.

### Before → After
Before, the decision was one inline condition in `process_event()`. After,
the caller asks this module and acts only on the answer.

## `app/processor.py` (modified)

### What changed
`process_event()` (`app/processor.py:5-9`) calls
`should_trigger_integration(event, config)` at `app/processor.py:7` instead
of evaluating the condition inline.

### Before → After
Before (`app/processor.py:6` at the merge base): trigger when the type is
`order.created` or `order.updated` and the event is not a test. After:
trigger when `should_trigger_integration()` returns `True`. The `config`
parameter, previously unused, now drives the decision.

## `config/settings.yaml` (modified)

### What changed
Adds `integration.event_types` with `order.created`, `order.updated` and
`order.shipped` (`config/settings.yaml:3-6`).

### Before → After
Before, the key did not exist and the types were hard-coded. After,
`app/decision.py:5` reads the list.

## `tests/test_decision.py` (added)

Covers an allowed type (`tests/test_decision.py:6-7`), test events
(`tests/test_decision.py:10-11`) and cancelled orders
(`tests/test_decision.py:14-15`). No test covers a missing `id` or a config
without `integration.event_types`.

# New Functions / Classes

## `should_trigger_integration()`

    File / lines:       app/decision.py:1-8
    Purpose:            decides whether one event is sent to the partner integration
    Inputs:             event (dict), config (dict loaded from config/settings.yaml)
    Outputs:            bool; no side effects
    Conditions:         test event → False; type not in integration.event_types → False
    Called by:          process_event() at app/processor.py:7
    Calls:              validate_conditions() at app/decision.py:8
    Return value use:   True → trigger_integration(event) at app/processor.py:8
    Before:             inline condition at app/processor.py:6 (merge base)
    Tests:              tests/test_decision.py:6-15

## `validate_conditions()`

    File / lines:       app/decision.py:11-13
    Purpose:            rejects events without an id and cancelled orders
    Called by:          should_trigger_integration() at app/decision.py:8
    Before:             new behavior — no equivalent check existed

# End-to-End Flow

    main()                              app/main.py:9-13     loads config/settings.yaml, one event per stdin line
      → process_event()                 app/processor.py:5
        → should_trigger_integration()  app/decision.py:1
          → validate_conditions()       app/decision.py:11
        → trigger_integration()         app/integration.py:1  only when the decision is True

# Key Things to Understand

1. The decision lives in `app/decision.py`; `process_event()` only acts on
   its answer.
2. Allowed event types come from `integration.event_types`;
   `order.shipped` is new.
3. Cancelled orders and events without an `id` no longer trigger. That is
   new behavior, not part of the refactor.
4. With no `integration.event_types` in the config, nothing triggers
   (`app/decision.py:5` defaults to `[]`). Before, the two hard-coded types
   always triggered.
5. Tests pin the allowed-type, test-event and cancelled paths. The
   missing-id path is untested.

# PR Explanation

Moves the partner-integration decision out of `process_event()` into
`should_trigger_integration()` (`app/decision.py:1-8`) and makes the
triggering event types configurable.

**Behavior changes**
- Event types come from `integration.event_types` in `config/settings.yaml`
  instead of a hard-coded tuple; `order.shipped` is added
  (`config/settings.yaml:3-6`).
- Cancelled orders and events without an `id` no longer trigger the
  integration (`app/decision.py:11-13`).
- A config without `integration.event_types` triggers nothing
  (`app/decision.py:5`).

**Flow:** `process_event()` → `should_trigger_integration()` →
`validate_conditions()` → `trigger_integration()`

**Tests:** `tests/test_decision.py` covers allowed types, test events and
cancelled orders.

# PR Comments

### `app/decision.py:1-8` — integration decision
Added `should_trigger_integration()` to hold the whole decision.
Previously `process_event()` evaluated the condition inline
(`app/processor.py:6` at the merge base). The caller now acts only on the
result, so the conditions can change without touching the processing flow.

### `app/decision.py:11-13` — new skip conditions
`validate_conditions()` is new behavior: events without an `id` and orders
with `status: cancelled` are no longer sent to the partner.

### `config/settings.yaml:3-6` — configurable event types
The allowed types moved from code to `integration.event_types`, adding
`order.shipped`. If the key is missing, the list defaults to empty and no
event triggers.

# Important Observations

- A config without `integration.event_types` disables the integration
  silently (`app/decision.py:5`). Before, `order.created` and
  `order.updated` always triggered. Any environment whose config lacks the
  key changes behavior on deploy.
~~~

- [ ] **Step 7: Run the tests**

Run: `cd agent-skills && python3 -m unittest test_install 2>&1 | grep -E "^(Ran|OK|FAILED)"`
Expected: `Ran 202 tests` and `OK`. If `test_git_commands_are_shell_neutral` fails, fix the quoted command in the skill file — never weaken the test.

- [ ] **Step 8: Commit**

```bash
git add agent-skills/skills/explain-feature-changes agent-skills/install.py agent-skills/test_install.py
git commit -m "feat(skills): add explain-feature-changes

Explains the author's own feature branch against develop or main:
traced before/after behavior, labelled intent, a report with PR-ready
text and per-change comments, and a CodeTour. Requires code-tour,
context-map and write-pr-description."
```

---

### Task 5: Run the skill against the fixture (GREEN check, then REFACTOR)

**Files:**
- Modify (only if a scenario fails): `agent-skills/skills/explain-feature-changes/SKILL.md`, `references/tracing.md`, `references/output-template.md`
- Create: `$SCRATCH/green-score.md` (throwaway)

**Interfaces:**
- Consumes: fixture builder and 12-item scorecard (Task 3); skill files (Task 4).

- [ ] **Step 1: Rebuild a clean fixture**

Run: `bash "$SCRATCH/make-fixture.sh" "$SCRATCH/fixture"`
Expected: exits 0 (the builder deletes and recreates the directory).

- [ ] **Step 2: With-skill run**

Dispatch a `general-purpose` subagent with exactly:

```
You are working in the Git repository at <$SCRATCH/fixture, expanded>. Run
git commands from that directory or with `git -C <that path>`.

Read /home/rcarranza/Development/.dotfiles/agent-skills/skills/explain-feature-changes/SKILL.md
and follow it exactly. Its references/ and examples/ paths are relative to
that SKILL.md's directory. The companion skills live in
/home/rcarranza/.claude/skills/<name>/SKILL.md when installed;
write-pr-description is in
/home/rcarranza/.agent-skills-cache/warp-common-skills/.agents/skills/write-pr-description/SKILL.md.

The user says: "/explain-feature-changes — explain my changes compared to
develop and give me something I can paste into my PR."

Reply with your chat output, then the full report file content, then the
tour file path.
```

- [ ] **Step 3: Score**

Score the 12 items in `$SCRATCH/green-score.md`, quoting the deciding line for each, next to the baseline result. Also check:
- `git -C "$SCRATCH/fixture" status --porcelain` shows only `?? app/metrics.py`, `?? feature-LISA-123-integration-decision-changes.md`, and `.tours/` — no source edits.
- Every line reference in the report matches the fixture (for example `app/decision.py:1-8`, `app/processor.py:7`, `app/main.py:13`, `config/settings.yaml:3-6`).

Expected: all 12 pass.

- [ ] **Step 4: Refactor loop (only for failures)**

For each failed item, strengthen the instruction in its owning phase (column "Owning phase" in the scorecard) — say what to do, not what to avoid. Rebuild the fixture (Step 1) and re-run Step 2. Repeat until all 12 pass. Record each wording change and the item it fixed in `$SCRATCH/green-score.md`.

- [ ] **Step 5: Edge case — no develop or main**

Run: `bash "$SCRATCH/make-fixture.sh" "$SCRATCH/fixture-nobase" && git -C "$SCRATCH/fixture-nobase" branch -m develop trunk`

Dispatch the Step 2 prompt with the path changed to `$SCRATCH/fixture-nobase` and the user message `"Explain my changes and give me PR text."`.
Expected: the agent stops at phase 1 and asks which branch to compare against. It must not pick `trunk` by itself, and must not write a report.

- [ ] **Step 6: Edge case — explicit base argument**

Dispatch the Step 2 prompt against `$SCRATCH/fixture-nobase` with the user message `"/explain-feature-changes trunk"`.
Expected: comparison line `feature/LISA-123-integration-decision → trunk`, and the report is written.

- [ ] **Step 7: Edge case — no terminal**

Dispatch a `general-purpose` subagent:

```
Read /home/rcarranza/Development/.dotfiles/agent-skills/skills/explain-feature-changes/SKILL.md
and follow it. You cannot run any commands in this session and cannot read
repository files. The user says: "/explain-feature-changes develop".
```

Expected: the agent says it has no terminal and asks for the output of `git diff develop...HEAD` and `git log --oneline develop..HEAD`.

- [ ] **Step 8: Run the tests and commit (only if files changed in Step 4)**

Run: `cd agent-skills && python3 -m unittest test_install 2>&1 | grep -E "^(Ran|OK|FAILED)"`
Expected: `OK`.

```bash
git add agent-skills/skills/explain-feature-changes
git commit -m "fix(skills): tighten explain-feature-changes after fixture runs"
```

---

### Task 6: Prompt file, USAGE, README and community docs

**Files:**
- Create: `agent-skills/prompts/explain-feature-changes.prompt.md`
- Create: `agent-skills/skills/explain-feature-changes/USAGE.md`
- Modify: `agent-skills/README.md`
- Modify: `agent-skills/docs/community-skills.md`
- Test: `agent-skills/test_install.py`

**Interfaces:**
- Consumes: `TestExplainFeatureChangesSkill.FILES` (Task 4); `prompt_skill_names()` and `install_claude_commands` (existing — both skip a prompt whose stem matches a real skill).

- [ ] **Step 1: Write the failing test**

In `TestExplainFeatureChangesSkill`, change `FILES` to:

```python
    FILES = [SKILL / "SKILL.md", SKILL / "references" / "tracing.md",
             install.PROMPTS_SRC / "explain-feature-changes.prompt.md"]
```

and add:

```python
    def test_prompt_uses_no_vscode_only_variables(self):
        text = (install.PROMPTS_SRC
                / "explain-feature-changes.prompt.md").read_text(
                    encoding="utf-8")
        self.assertNotIn("${", text)

    def test_prompt_generates_no_stub_over_the_real_skill(self):
        self.assertNotIn("explain-feature-changes",
                         install.prompt_skill_names())
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd agent-skills && python3 -m unittest test_install.TestExplainFeatureChangesSkill -v`
Expected: ERROR — `FileNotFoundError` for `explain-feature-changes.prompt.md`.

- [ ] **Step 3: Create the prompt file**

Create `agent-skills/prompts/explain-feature-changes.prompt.md` with exactly:

~~~markdown
---
mode: agent
description: 'Explain my feature branch against its base — what changed, why, how it works, before/after, code flow — plus PR-ready text and a CodeTour'
---

Use the **explain-feature-changes** skill for this task. Follow its full workflow.

Base branch (in priority order):
1. If I name a base branch in my message, compare against that
2. Otherwise `develop` (`origin/develop`, then local), then `main`
   (`origin/main`, then local)
3. If neither exists, ask me — do not guess

Requirements:
- Read-only: only `git` commands and file reads; never commit, push, reset,
  rebase, checkout or edit code
- Plain `git` commands only — no `$(...)`, pipes, `grep` or `sed` (the
  terminal may be PowerShell or cmd)
- Three-dot diff: `git diff <base>...HEAD`; committed work only — list
  uncommitted files in the report header
- Trace callers, callees, tests and configuration — do not just summarize
  the diff
- Label intent as confirmed, likely or unknown; never invent it
- Not a code review — only observations that change how the feature should
  be understood
- Write `<branch-slug>-changes.md` at the repository root and the CodeTour
~~~

- [ ] **Step 4: Check for a JetBrains CodeTour viewer**

Fetch `https://plugins.jetbrains.com/search?search=codetour` (WebFetch) and note any plugin that opens `.tour` files: name, vendor, last update date, compatible IDE builds. "Maintained" means updated within the last 12 months and compatible with the 2025.x or later builds. Use the result in Step 5.

- [ ] **Step 5: Create `USAGE.md`**

Create `agent-skills/skills/explain-feature-changes/USAGE.md` with the content below. Replace the single line marked `TOURS-IN-JETBRAINS` with one of the two sentences given under it, based on Step 4, and delete the other sentence and the marker.

~~~markdown
# explain-feature-changes — usage

Explains the changes on your own feature branch compared with its base, so
you understand them and can explain them in PR review. It traces callers,
callees, tests and configuration instead of summarizing the diff, labels
intent as confirmed, likely or unknown, and writes PR-ready text.

Not a code review. For a review, use a dedicated code-review skill.

## When to use

- Before opening a PR, to understand and describe what the branch does.
- Before a review meeting, to be able to explain every change.
- To get a PR description and per-change PR comments you can paste.

Not for a single file or function, and not for someone else's branch.

## Invoking

Plain English works in every agent — the skill triggers from its
description:

    explain my changes compared to develop
    help me understand what I changed in this branch
    explain the new functions and code flow in my branch
    generate something I can paste into my PR
    help me explain these changes to my reviewer

Explicit invocation:

| Agent | VS Code | IntelliJ / PyCharm / GoLand |
| --- | --- | --- |
| Claude Code | `/explain-feature-changes [base]` | `/explain-feature-changes [base]` |
| Copilot | `/explain-feature-changes [base]` (prompt file) | `/skill:explain-feature-changes [base]` |
| Copilot, repo seeded with `install.py --repo .` | same | `/explain-feature-changes [base]` |

Examples: `/explain-feature-changes`, `/explain-feature-changes develop`,
`/skill:explain-feature-changes main`.

Base branch without an argument: `develop` (`origin/develop`, then local),
then `main` (`origin/main`, then local). If neither exists, the skill asks.

## What it does

1. Resolves the base and prints `feature/x → develop (merge base <sha>)`.
2. Collects the committed diff with `git diff <base>...HEAD`. Uncommitted
   files are listed in the report header, not explained.
3. Builds a change inventory and ranks changes by behavioral impact.
4. Traces each new or changed symbol: callers (`git grep -n`), callees,
   inputs, outputs, the code it replaced (`git show <merge-base>:<path>`),
   tests and configuration.
5. Labels intent as confirmed, likely or unknown, from commit messages,
   ticket IDs, tests and naming.
6. Writes the report and a CodeTour.

It runs only `git` commands and reads files. It never commits, pushes,
checks out or edits code. Every command is plain `git`, so it behaves the
same in bash, PowerShell and cmd.

## Output

- Chat: the comparison line, the overview, Key Things to Understand, and
  the report path.
- `<branch-slug>-changes.md` at the repository root (branch name with `/`
  replaced by `-`). Untracked; the skill offers to add it to
  `.git/info/exclude`.
- `.tours/changes-<branch-slug>.tour`, persona `pr-reviewer`.

Report sections: Feature Change Overview, Why This Change Exists, Changes by
File, New Functions / Classes, End-to-End Flow, Key Things to Understand, PR
Explanation, PR Comments, Important Observations. Empty sections are left
out.

TOURS-IN-JETBRAINS
- If a maintained viewer was found: "In JetBrains IDEs, open the tour with the <plugin name> plugin (JetBrains Marketplace); the report's `path:line` references work in any IDE."
- If not: "The tour opens in VS Code with the CodeTour extension. No maintained JetBrains viewer was found (checked 2026-09-10); in IntelliJ, PyCharm and GoLand use the report's `path:line` references to navigate."

## Dependencies

`install.py` installs these with the skill, to the same targets, in every
install mode. The skill still runs without them, on its own fallback.

| Skill | Source (skills.sh) | Used for |
| --- | --- | --- |
| `code-tour` | `github/awesome-copilot` | writing the tour |
| `context-map` | `github/awesome-copilot` | mapping related files on large branches |
| `write-pr-description` | `warpdotdev/common-skills` | shaping the PR Explanation |

`python3 install.py --status` lists any requirement that is missing.
`--skills-only` cannot fetch them; the run ends with a warning naming what
is missing.

## JetBrains checklist

1. Copilot plugin up to date and signed in.
2. **Settings → Languages & Frameworks → GitHub Copilot → Chat → Agent** —
   agent mode on. Without it Copilot cannot run `git`, and the skill asks
   you to paste the diff instead.
3. `python install.py --target copilot` (both skills and dependencies land
   in `~/.copilot/skills`, which JetBrains reads).
4. Reopen the IDE, open a feature branch, type
   `/skill:explain-feature-changes develop` in agent-mode chat.
5. Approve the `git` commands it proposes in the IDE terminal. The report
   appears at the repository root.

## Skills considered

Found through the skills.sh search API. Only skills published there were
considered for reuse.

| Skill | Relevance | Decision | Reason |
| --- | --- | --- | --- |
| `github/awesome-copilot/code-tour` | High | Compose | Writes the tour |
| `github/awesome-copilot/context-map` | Medium | Compose | Maps related files on large branches |
| `warpdotdev/common-skills/write-pr-description` | High | Compose | PR body rules: facts first, repo template wins, cut hard, no padding |
| `warpdotdev/common-skills/pr-walkthrough` | Low | Not used | Branded D3 HTML page, needs `gh`, publishes to Cloudflare |
| `chris-graffagnino/explain-diff` | High overlap | Pattern only | Stated-vs-inferred intent and analysis lenses informed the tracing rules; installing it would add a competing explainer |
| `sjunepark/agent-scripts/change-explainer` | Low | Not used | Written for a cold reader, not the author |
| `mryll/skills/explain-pr`, `aymericderbois/skills/explain-your-changes` | Low | Not used | Shallow, few installs |
| `amplitude/mcp-marketplace/diff-intake`, `ruvnet/ruflo/diff-analyze` | Low | Not used | Different purpose |
| `mattpocock/skills/code-review`, `coderabbitai/skills/code-review` | Low | Not used | Code review is a different purpose |
~~~

- [ ] **Step 6: Update `README.md`**

Make these edits in `agent-skills/README.md`:

1. In `## Layout`, after the `skills/tour-codebase/` bullet (it ends with "`.tour` writing."), add:

```markdown
- `skills/explain-feature-changes/` — explains your own feature branch
  against `develop` or `main`: traced before/after behavior, intent labelled
  confirmed / likely / unknown, a `-changes.md` report with PR-ready text and
  per-change PR comments, and a tour. Requires `code-tour`, `context-map` and
  `write-pr-description` (see [Skill dependencies](#skill-dependencies)).
```

2. In the same section, in the `prompts/` bullet, replace `` `/tour-codebase`). `` with `` `/tour-codebase`, `/explain-feature-changes`). ``

3. After the `**Default (both targets, unless noted):**` addy bullet (ends "investigate-issue chains it\n  when present."), add:

```markdown
- From `warpdotdev/common-skills`: write-pr-description (fetched from its
  `.agents/skills/` folder). explain-feature-changes uses it for the PR
  Explanation.
```

4. Replace:

```markdown
`./install.py install agent-skills` from the repo root runs the custom-skill
install (no community fetch) as part of normal dotfiles setup — Claude only on
macOS/Linux, **both** Claude and Copilot on Windows (Git Bash).
```

with:

```markdown
`./install.py install agent-skills` from the repo root runs a flag install —
custom skills, default community skills and externals — as part of normal
dotfiles setup: Claude only on macOS/Linux, **both** Claude and Copilot on
Windows (Git Bash).

### Skill dependencies

`REQUIRES` in `install.py` lists the skills a custom skill calls. Installing
the skill installs its requirements to the same targets in every mode — flag,
interactive and `--repo`. An item unticked in the picker comes back with a
`(required by …)` log line.

| Skill | Requires |
| --- | --- |
| `explain-feature-changes` | `code-tour`, `context-map`, `write-pr-description` |

`--skills-only` cannot fetch requirements; the run ends with a warning for
each one missing. `--status` lists missing requirements per target.
`--uninstall` of a requirement that an installed skill still needs warns,
then removes it. A test fails if a `REQUIRES` key stops matching a
directory under `skills/`, so a rename cannot silently drop dependencies.
```

5. Replace `` `code-review-pr-fast` and `tour-codebase` exist in both `skills/` and `` with `` `code-review-pr-fast`, `tour-codebase` and `explain-feature-changes` exist in both `skills/` and ``.

6. Replace `with the prompt stub. Those three install as prompt files only, and` with `with the prompt stub. Those four install as prompt files only, and`.

7. Replace `seeding — except for the three prompts that share a name with a real skill,` with `seeding — except for the four prompts that share a name with a real skill,`.

8. Replace `4. Reopen the IDE. In agent-mode chat type `/skill:` — the seven custom` with `4. Reopen the IDE. In agent-mode chat type `/skill:` — the eight custom`.

9. In `## Usage`, after `- [tour-codebase](skills/tour-codebase/USAGE.md)` add `- [explain-feature-changes](skills/explain-feature-changes/USAGE.md)`.

- [ ] **Step 7: Update `docs/community-skills.md`**

Replace:

```markdown
alongside the custom skills. Sources: `github/awesome-copilot` and
`juliusbrussee/caveman`.
```

with:

```markdown
alongside the custom skills. Sources: `github/awesome-copilot`,
`juliusbrussee/caveman` and `warpdotdev/common-skills`.
```

Append at the end of the file:

```markdown

## write-pr-description
Writes a PR body that gives the reviewer what the diff cannot: motivation,
behavior changes, decisions and blast radius. Repository PR templates win.
From `warpdotdev/common-skills` (MIT), fetched from its `.agents/skills/`
folder.
- `Write the PR description for this branch`

`explain-feature-changes` requires it and hands it verified facts for the
PR Explanation section, skipping its `gh` steps. Without it,
`explain-feature-changes` uses its own fallback rules.
```

- [ ] **Step 8: Run the tests**

Run: `cd agent-skills && python3 -m unittest test_install 2>&1 | grep -E "^(Ran|OK|FAILED)"`
Expected: `Ran 204 tests` and `OK`.

- [ ] **Step 9: Commit**

```bash
git add agent-skills/prompts/explain-feature-changes.prompt.md agent-skills/skills/explain-feature-changes/USAGE.md agent-skills/README.md agent-skills/docs/community-skills.md agent-skills/test_install.py
git commit -m "docs(agent-skills): usage and prompt for explain-feature-changes

Copilot gets /explain-feature-changes in VS Code and
/skill:explain-feature-changes in JetBrains. Document the dependency
map and fix the stale root-install note."
```

---

### Task 7: Install for real and verify

**Files:** none changed (verification only). If a check fails, fix in the file that owns the behavior and commit with a `fix(...)` message.

- [ ] **Step 1: Full test suite**

Run: `cd agent-skills && python3 -m unittest test_install -v 2>&1 | tail -3`
Expected: `Ran 204 tests` … `OK`.

- [ ] **Step 2: Dry run for both targets**

Run: `cd agent-skills && python3 install.py --target both --dry-run`
Expected, in "Planned actions (dry run)": `copilot  explain-feature-changes`, `claude   explain-feature-changes linked`, `write-pr-description` for both targets, and `prompt:explain-feature-changes` for copilot; for claude, `command:explain-feature-changes  skipped (real skill of same name)`.

- [ ] **Step 3: Real install for Claude on this laptop**

Run: `cd agent-skills && python3 install.py --target claude`
Expected: `claude   explain-feature-changes  linked`, `claude   write-pr-description  installed`, `code-tour` and `context-map` `up to date`, and no `requires ... which is not installed` warning at the end.

- [ ] **Step 4: Status**

Run: `cd agent-skills && python3 install.py --status --target claude`
Expected rows: `explain-feature-changes  custom  symlink`, `write-pr-description  community (warp-common-skills)  copy`; no warning mentioning `requires`.

Run: `readlink -f ~/.claude/skills/explain-feature-changes`
Expected: `/home/rcarranza/Development/.dotfiles/agent-skills/skills/explain-feature-changes`.

- [ ] **Step 5: Uninstall warning smoke test (nothing removed)**

Run: `cd agent-skills && python3 install.py --uninstall code-tour --target claude --dry-run`
Expected: stderr line `claude: removing code-tour, but explain-feature-changes still requires it — explain-feature-changes will run on its fallback`, and `~/.claude/skills/code-tour` still exists (`ls -d ~/.claude/skills/code-tour`).

- [ ] **Step 6: Live trigger check**

Rebuild the fixture: `bash "$SCRATCH/make-fixture.sh" "$SCRATCH/fixture"`. From `$SCRATCH/fixture`, run a fresh headless Claude session:

Run: `cd "$SCRATCH/fixture" && claude -p "Explain my changes compared to develop and give me something to paste into my PR." --allowedTools "Bash(git:*),Read,Write,Glob,Skill"`
Expected: the output names the `explain-feature-changes` skill (or follows its format: comparison line, overview, Key Things to Understand, report path), and `feature-LISA-123-integration-decision-changes.md` exists in the fixture. If the installed `explain-logic` skill is chosen instead, record it in the final report as the known trigger overlap — do not edit `explain-logic`.

- [ ] **Step 7: Report**

Summarize for the user: tests run and passed (with counts), baseline vs with-skill scores (12 items each), edge-case results, install and status output, the JetBrains CodeTour finding, and whether the live trigger check picked the new skill. Then use `superpowers:finishing-a-development-branch`.
