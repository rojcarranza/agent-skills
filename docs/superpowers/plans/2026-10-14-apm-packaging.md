# APM Packaging Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Declare every skill, instruction and MCP server Roj installs for Claude Code and Copilot in one `apm.yml` in this repo, installed by `python3 install.py` through `apm install -g`, on macOS, Linux, Windows Git Bash and WSL Ubuntu.

**Architecture:** The repo's `apm.yml` is a package manifest. `install.py` generates a tiny `~/.apm/apm.yml` whose only dependency is the clone's absolute path (wiring W2), so APM resolves `./skills/...` against the repo. `install.py` keeps only what APM cannot do: cleaning up its own pre-APM installs and bootstrapping graphify. The inventory, picker, `--repo`, `--skill` and `--uninstall` code is deleted.

**Tech Stack:** Python >= 3.8 standard library only (`install.py`, `unittest`), APM CLI, GitHub Actions.

**Spec:** `docs/superpowers/specs/2026-10-14-apm-packaging-design.md` (revision 2). Issue: rojcarranza/agent-skills#24. Branch: `feat/apm-install` (already created; the spec commits are on it).

## Global Constraints

- Python >= 3.8, standard library only — no PyYAML; `apm.yml` is read by a line parser in `install.py`.
- Platforms: macOS, Linux, Windows Git Bash (Windows Python, run as `python install.py`), WSL Ubuntu.
- Files the installer writes: UTF-8, `\n` line endings (`newline="\n"`).
- Paths written into `~/.apm/apm.yml`: absolute, forward slashes (`Path.as_posix()`), JSON-quoted.
- Every community dependency ref in `apm.yml` is a full 40-char commit SHA.
- No personal paths, ticket IDs or employer details in `skills/` or `.apm/` (`PRIVATE_PATTERNS` in `test_skills.py`).
- Owner in every install command and link: `rojcarranza/agent-skills`.
- Commits: author and committer Roj Carranza <rojjamescarranza@gmail.com>; no Claude attribution, no `Co-Authored-By`, no `Claude-Session` trailer. Messages `<type>(<scope>): <summary>`, lowercase, imperative, body `Refs #24`.
- Before pushing: `python3 -m unittest test_install test_skills` and `python3 tools/sync_shared.py --check` pass.

## Review Focus

1. **A `~/.apm/apm.yml` the user wrote by hand** — install.py must refuse to overwrite it without `--force`, and say how to proceed (Task 4 test `test_foreign_manifest_refused`).
2. **A second run after APM has installed** — legacy cleanup must not delete APM-deployed copies in `~/.claude/skills` once `~/.apm/apm.lock.yaml` exists (Task 5 test `test_claude_copies_kept_after_apm_owns_them`).
3. **Windows paths** — a `C:\Users\...` clone must land in the manifest as `"C:/Users/..."` (Task 4 test `test_windows_path_is_forward_slashed`).
4. **The dotfiles instruction file edited locally** — a `~/.copilot/instructions/personal.instructions.md` copy that differs from the repo's must be left alone with a warning, not deleted (Task 5 test `test_edited_instruction_copy_kept`).
5. **`apm` missing on a dry run** — `--dry-run` must still print the plan and exit 0 instead of failing the preflight (Task 6 test `test_dry_run_without_apm_prints_plan`).

---

### Task 1: Step 0 — throwaway check of `apm install -g` (no commit)

This task is a gate. Nothing from it is committed. Its findings decide whether Tasks 2–9 run as written.

**Files:**
- Create (scratch only): `$SCRATCH/home/`, `$SCRATCH/pkg/` where `SCRATCH` is the session scratchpad directory.
- Create: `$SCRATCH/step0-findings.md` (pasted into the PR description in Task 9).

- [ ] **Step 1: Install APM if missing (ask Roj first — it installs a tool on the machine)**

Run: `apm --version || brew install apm`
Expected: a version string.

- [ ] **Step 2: Build the probe package**

```bash
SCRATCH=<session scratchpad>
mkdir -p "$SCRATCH/home" "$SCRATCH/pkg/skills" "$SCRATCH/pkg/.apm/instructions"
cp -R skills/roj-explain-logic "$SCRATCH/pkg/skills/"
DOTFILES="$(dirname "$(dirname "$(readlink -f ~/.claude/CLAUDE.md)")")"
cp "$DOTFILES/copilot/personal.instructions.md" "$SCRATCH/pkg/.apm/instructions/"
cat > "$SCRATCH/pkg/apm.yml" <<'EOF'
name: probe
version: 1.0.0
targets: [claude, copilot]
includes: auto
dependencies:
  apm:
    - ./skills/roj-explain-logic
    - github/awesome-copilot/skills/code-tour#7cce7cfb4b61196c36d7e8eb8475ae84b356b126
    - git: https://github.com/juliusbrussee/caveman.git
      path: skills/caveman
      ref: 2e08b9177c07bb7249a8a2d1a6758e5db281d002
      targets: [copilot]
  mcp:
    - io.github.github/github-mcp-server
EOF
mkdir -p "$SCRATCH/home/.apm"
printf 'name: user\nversion: 1.0.0\ndependencies:\n  apm:\n    - "%s"\n' "$SCRATCH/pkg" > "$SCRATCH/home/.apm/apm.yml"
```

- [ ] **Step 3: Run the install against the scratch home**

Run: `cd "$SCRATCH/home" && HOME="$SCRATCH/home" apm install -g --target claude,copilot; echo "exit=$?"`
Expected: exit 0.

- [ ] **Step 4: Record the seven spec checks**

Run: `cd "$SCRATCH/home" && find . -path ./.apm/apm_modules -prune -o -type f -print | sort; ls -la .claude/skills .agents/skills .copilot/skills 2>/dev/null; cat .apm/apm.lock.yaml`

Write `$SCRATCH/step0-findings.md` answering, each with the observed path or output:
1. Where `roj-explain-logic`, `code-tour`, `caveman`, the instruction and the GitHub MCP server landed for Claude and for Copilot.
2. Repeat Step 3 after `ln -s "$PWD/skills/roj-explain-logic" "$SCRATCH/home/.claude/skills/roj-explain-logic"` (after removing the APM copy): does APM refuse? (Expected: yes — confirms legacy cleanup must run first.)
3. Is `caveman` absent from `.claude/skills`?
4. Is `roj-explain-logic` a copy or a link? Edit `$SCRATCH/pkg/skills/roj-explain-logic/SKILL.md`; does the deployed copy change without a re-run?
5. Did W2 work: transitive deps of the local package installed and `.apm/instructions/` deployed?
6. Comment out `code-tour` in `$SCRATCH/pkg/apm.yml`, re-run Step 3: is `code-tour` removed?
7. `apm search github` / `apm search playwright` (or `apm install -g --mcp <name> --dry-run`): exact registry names of the GitHub and Playwright MCP servers.

- [ ] **Step 5: Apply the gate**

- All seven as the spec expects → continue to Task 2 unchanged.
- Item 1 shows Copilot skills somewhere other than `~/.agents/skills` → change `APM_COPILOT_SKILLS` in Task 5 to the observed path.
- Item 5 fails (W2) → stop; amend the spec's W1 section into Task 4 (`render_user_manifest` copies the repo manifest and rewrites `./` paths to absolute ones) and get Roj's approval before Task 4.
- Item 6 fails → in Task 8's README text, replace "edit `apm.yml` and re-run" for removals with `apm uninstall -g <name>` per the observed behavior.
- Item 7 names differ → use the observed names in Task 3's `apm.yml`.
- APM refuses user-scope skills entirely → stop; report to Roj (fallback approach B needs a new spec).

- [ ] **Step 6: Clean up**

Run: `rm -rf "$SCRATCH/home" "$SCRATCH/pkg"` — keep `step0-findings.md`.

---

### Task 2: `apm.yml` line parser in `install.py`

**Files:**
- Modify: `install.py` (new section after the `REQUIRES` block, around line 120)
- Test: `test_install.py` (new class `TestParseManifest` at the end, before `if __name__`)

**Interfaces:**
- Produces: `MANIFEST_PATH: Path`; `parse_manifest(text: str) -> dict` with keys `"apm"`, `"mcp"`, each a list of dep dicts `{"path": str, "ref": str|None, "targets": tuple|None, "name": str, "active": bool, ...raw keys}`; `manifest_deps(path=None, section="apm") -> list[dict]`; `manifest_skill_names(active_only=True) -> set[str]`.

- [ ] **Step 1: Write the failing tests**

```python
class TestParseManifest(unittest.TestCase):
    TEXT = """\
name: roj-ai-setup
version: 1.0.0
targets: [claude, copilot]
dependencies:
  apm:
    # Own skills.
    - ./skills/roj-explain-logic
    - github/awesome-copilot/skills/code-tour#7cce7cfb4b61196c36d7e8eb8475ae84b356b126
    - git: https://github.com/juliusbrussee/caveman.git     # Claude: plugin
      path: skills/caveman
      ref: 2e08b9177c07bb7249a8a2d1a6758e5db281d002
      targets: [copilot]
    # Optional — uncomment and re-run install.py:
    # - anthropics/skills/skills/pdf#683bc88e56f3e09ba94f7055977f3d3aa499f202
  mcp:
    - io.github.github/github-mcp-server
    # - io.github.microsoft/playwright-mcp   # only for UI projects
"""

    def setUp(self):
        self.parsed = install.parse_manifest(self.TEXT)

    def test_local_dependency(self):
        dep = self.parsed["apm"][0]
        self.assertEqual((dep["path"], dep["ref"], dep["name"], dep["active"]),
                         ("./skills/roj-explain-logic", None,
                          "roj-explain-logic", True))

    def test_shorthand_splits_ref(self):
        dep = self.parsed["apm"][1]
        self.assertEqual(dep["path"], "github/awesome-copilot/skills/code-tour")
        self.assertEqual(dep["ref"], "7cce7cfb4b61196c36d7e8eb8475ae84b356b126")
        self.assertEqual(dep["name"], "code-tour")
        self.assertIsNone(dep["targets"])

    def test_object_form_with_targets_and_inline_comment(self):
        dep = self.parsed["apm"][2]
        self.assertEqual(dep["git"], "https://github.com/juliusbrussee/caveman.git")
        self.assertEqual((dep["path"], dep["name"], dep["targets"]),
                         ("skills/caveman", "caveman", ("copilot",)))
        self.assertEqual(dep["ref"], "2e08b9177c07bb7249a8a2d1a6758e5db281d002")

    def test_commented_dependency_is_inactive(self):
        dep = self.parsed["apm"][3]
        self.assertEqual((dep["name"], dep["active"]), ("pdf", False))
        self.assertEqual(len(self.parsed["apm"]), 4)

    def test_mcp_section(self):
        names = [(d["name"], d["active"]) for d in self.parsed["mcp"]]
        self.assertEqual(names, [("github-mcp-server", True),
                                 ("playwright-mcp", False)])

    def test_top_level_keys_end_a_section(self):
        parsed = install.parse_manifest(self.TEXT + "compilation:\n  exclude: [x]\n")
        self.assertEqual(len(parsed["mcp"]), 2)

    def test_crlf_input(self):
        parsed = install.parse_manifest(self.TEXT.replace("\n", "\r\n"))
        self.assertEqual(parsed["apm"][1]["name"], "code-tour")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m unittest test_install.TestParseManifest -v`
Expected: FAIL — `AttributeError: module 'install' has no attribute 'parse_manifest'`.

- [ ] **Step 3: Implement**

Add after the `REQUIRES` dict in `install.py`:

```python
# apm.yml: the manifest APM installs from (https://microsoft.github.io/apm/).
# Read here only for names — status, legacy cleanup and tests — with a line
# parser for the shapes this repo's apm.yml uses, so no YAML dependency.
MANIFEST_PATH = REPO_ROOT / "apm.yml"
_DEP_ITEM_RE = re.compile(r"^\s*(#\s*)?-\s+(.*)$")
_OBJECT_KEY_RE = re.compile(r"^[\w-]+:\s")


def _strip_comment(value):
    return re.sub(r"\s+#.*$", "", value).strip()


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
    dep["name"] = dep["path"].rstrip("/").rsplit("/", 1)[-1]
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
                current[key.strip()] = _strip_comment(value)
            else:
                current["spec"] = body
            out[section].append(current)
        elif not stripped.startswith("#") and current is not None:
            key, _, value = stripped.partition(":")
            current[key.strip()] = _strip_comment(value)
    return {name: [_normalise_dep(d) for d in deps]
            for name, deps in out.items()}


def manifest_deps(path=None, section="apm"):
    text = Path(path or MANIFEST_PATH).read_text(encoding="utf-8")
    return parse_manifest(text)[section]


def manifest_skill_names(active_only=True):
    """Skill folder names apm.yml installs (or lists, with active_only off)."""
    return {d["name"] for d in manifest_deps()
            if d["active"] or not active_only}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m unittest test_install.TestParseManifest -v`
Expected: 7 tests OK.

- [ ] **Step 5: Commit**

```bash
git add install.py test_install.py
git commit -m "feat(install): read apm.yml dependencies without a yaml dependency" -m "Refs #24"
```

---

### Task 3: `apm.yml`, the instructions file, and manifest tests

**Files:**
- Create: `apm.yml`
- Create: `.apm/instructions/personal.instructions.md` (copied verbatim from the dotfiles repo's `copilot/personal.instructions.md`)
- Modify: `test_skills.py` (new class `TestManifest`; extend `test_no_private_paths_or_employer_details` to `.apm/`)

**Interfaces:**
- Consumes: `install.parse_manifest`, `install.manifest_deps`, `install.manifest_skill_names`, `install.REQUIRES` (Task 2).
- Produces: `apm.yml` with the shape below; later tasks read it via `manifest_deps()`.

- [ ] **Step 1: Write the failing tests** — add `import install  # noqa: E402` on the line after `import sync_shared  # noqa: E402` at the top of `test_skills.py`, then append before `if __name__`:

```python
SHA_RE = re.compile(r"[0-9a-f]{40}")


class TestManifest(unittest.TestCase):
    """apm.yml is the one list of what install.py installs."""

    def setUp(self):
        self.deps = install.manifest_deps()

    def test_every_skill_is_a_live_local_dependency(self):
        live = {d["path"] for d in self.deps if d["active"]}
        for d in skill_dirs():
            with self.subTest(skill=d.name):
                self.assertIn(f"./skills/{d.name}", live)

    def test_every_requirement_is_live(self):
        live = install.manifest_skill_names()
        for skill, deps in install.REQUIRES.items():
            for dep in deps:
                with self.subTest(skill=skill, dep=dep):
                    self.assertIn(dep, live)

    def test_community_refs_are_full_shas(self):
        for d in self.deps:
            if d["path"].startswith("./"):
                continue
            with self.subTest(dep=d["name"]):
                self.assertRegex(d["ref"] or "", SHA_RE)

    def test_names_are_unique(self):
        names = [d["name"] for d in self.deps]
        self.assertEqual(len(names), len(set(names)))

    def test_github_mcp_is_live(self):
        mcp = {d["name"]: d["active"]
               for d in install.manifest_deps(section="mcp")}
        self.assertTrue(mcp.get("github-mcp-server"))

    def test_instructions_apply_everywhere(self):
        text = (ROOT / ".apm" / "instructions"
                / "personal.instructions.md").read_text(encoding="utf-8")
        self.assertTrue(text.startswith("---\n"))
        self.assertIn('applyTo: "**"', text.split("---", 2)[1])
```

And change the loop in `TestPublishable.test_no_private_paths_or_employer_details` from `for f in sorted(SKILLS.rglob("*.md")):` to:

```python
        for f in sorted([*SKILLS.rglob("*.md"),
                         *(ROOT / ".apm").rglob("*.md"),
                         ROOT / "apm.yml"]):
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m unittest test_skills.TestManifest -v`
Expected: ERROR — `FileNotFoundError: ... apm.yml`.

- [ ] **Step 3: Create `apm.yml`** (MCP names per Task 1 item 7 if they differed)

```yaml
# Everything install.py installs for Claude Code and Copilot, through APM
# (https://microsoft.github.io/apm/). Edit here, then re-run install.py.
# Community refs are full commit SHAs: a version bump is a reviewed diff.
name: roj-ai-setup
version: 1.0.0
description: Roj's skills, community skills, instructions and MCP servers for Claude Code and Copilot
targets: [claude, copilot]
includes: auto
dependencies:
  apm:
    # Own skills. Local paths, so skills/ stays where npx skills and the
    # Claude plugin marketplace expect it.
    - ./skills/roj-code-review-pr
    - ./skills/roj-code-review-pr-fast
    - ./skills/roj-explain-feature-changes
    - ./skills/roj-explain-logic
    - ./skills/roj-interview-prep
    - ./skills/roj-investigate-issue
    - ./skills/roj-review-pr-comment
    - ./skills/roj-soundboarding
    - ./skills/roj-tour-codebase
    # Community skills our skills chain to (docs/community-skills.md).
    - github/awesome-copilot/skills/code-tour#7cce7cfb4b61196c36d7e8eb8475ae84b356b126
    - github/awesome-copilot/skills/acquire-codebase-knowledge#7cce7cfb4b61196c36d7e8eb8475ae84b356b126
    - github/awesome-copilot/skills/context-map#7cce7cfb4b61196c36d7e8eb8475ae84b356b126
    - warpdotdev/common-skills/.agents/skills/write-pr-description#2a03b403b4f8d42cb54b8953697737193b2e8306
    - vercel-labs/skills/skills/find-skills#87a266971d9460a3d2606075b8e91edc83325472
    # Copilot only: Claude gets the equivalent from a plugin.
    - git: https://github.com/juliusbrussee/caveman.git     # Claude: caveman plugin
      path: skills/caveman
      ref: 2e08b9177c07bb7249a8a2d1a6758e5db281d002
      targets: [copilot]
    - git: https://github.com/addyosmani/agent-skills.git   # Claude: superpowers:systematic-debugging
      path: skills/debugging-and-error-recovery
      ref: 1401c8b8030e023baeebb31781a6653fe8e93026
      targets: [copilot]
    # Optional — uncomment and re-run install.py:
    # - github/awesome-copilot/skills/architecture-blueprint-generator#7cce7cfb4b61196c36d7e8eb8475ae84b356b126
    # - github/awesome-copilot/skills/add-educational-comments#7cce7cfb4b61196c36d7e8eb8475ae84b356b126
    # - github/awesome-copilot/skills/arch-linux-triage#7cce7cfb4b61196c36d7e8eb8475ae84b356b126
    # - github/awesome-copilot/skills/centos-linux-triage#7cce7cfb4b61196c36d7e8eb8475ae84b356b126
    # - github/awesome-copilot/skills/debian-linux-triage#7cce7cfb4b61196c36d7e8eb8475ae84b356b126
    # - github/awesome-copilot/skills/fedora-linux-triage#7cce7cfb4b61196c36d7e8eb8475ae84b356b126
    # - addyosmani/agent-skills/skills/observability-and-instrumentation#1401c8b8030e023baeebb31781a6653fe8e93026
    # - addyosmani/agent-skills/skills/ci-cd-and-automation#1401c8b8030e023baeebb31781a6653fe8e93026
    # - addyosmani/agent-skills/skills/security-and-hardening#1401c8b8030e023baeebb31781a6653fe8e93026
    # - addyosmani/agent-skills/skills/deprecation-and-migration#1401c8b8030e023baeebb31781a6653fe8e93026
    # - anthropics/skills/skills/pdf#683bc88e56f3e09ba94f7055977f3d3aa499f202
    # - anthropics/skills/skills/docx#683bc88e56f3e09ba94f7055977f3d3aa499f202
    # - anthropics/skills/skills/pptx#683bc88e56f3e09ba94f7055977f3d3aa499f202
    # - anthropics/skills/skills/xlsx#683bc88e56f3e09ba94f7055977f3d3aa499f202
  mcp:
    - io.github.github/github-mcp-server
    # Optional — for projects with a UI to drive:
    # - io.github.microsoft/playwright-mcp
```

Verify each community subpath before committing (the inventory's `subdir` was `skills` unless stated):

Run: `for p in github/awesome-copilot:skills/code-tour addyosmani/agent-skills:skills/debugging-and-error-recovery juliusbrussee/caveman:skills/caveman anthropics/skills:skills/pdf vercel-labs/skills:skills/find-skills warpdotdev/common-skills:.agents/skills/write-pr-description; do r=${p%%:*}; d=${p#*:}; gh api "repos/$r/contents/$d/SKILL.md" --jq .path >/dev/null && echo "ok $r/$d" || echo "MISSING $r/$d"; done`
Expected: every line `ok`. Fix any `MISSING` path in `apm.yml`.

- [ ] **Step 4: Create the instructions file**

Run: `mkdir -p .apm/instructions && cp "$(dirname "$(dirname "$(readlink -f ~/.claude/CLAUDE.md)")")/copilot/personal.instructions.md" .apm/instructions/`

- [ ] **Step 5: Run tests to verify they pass**

Run: `python3 -m unittest test_skills -v 2>&1 | tail -5`
Expected: `OK`. If the private-paths scan flags the instructions file, replace the flagged string with a placeholder and note it for Roj.

- [ ] **Step 6: Commit**

```bash
git add apm.yml .apm/instructions/personal.instructions.md test_skills.py
git commit -m "feat(install): declare skills, instructions and mcp servers in apm.yml" -m "Refs #24"
```

---

### Task 4: User manifest and the `apm` runner

**Files:**
- Modify: `install.py` (new section after the manifest parser from Task 2)
- Test: `test_install.py` (new class `TestApm`)

**Interfaces:**
- Consumes: `find_cli(name) -> str|None`, `warn`, `log` (existing).
- Produces: `apm_home() -> Path`; `USER_MANIFEST_MARKER: str`; `APM_INSTALL_HINT: str`; `render_user_manifest(repo_root=None) -> str`; `write_user_manifest(text: str, force=False, dry_run=False) -> str` (`"written"|"updated"|"up to date"`, exits on a foreign file); `apm_install_argv(exe: str, targets: list[str]) -> list[str]`; `run_apm(argv: list[str]) -> int`; `is_wsl() -> bool`; `WSL_HINT: str`.

- [ ] **Step 1: Write the failing tests**

```python
class TestApm(TempDirTest):
    def setUp(self):
        super().setUp()
        patcher = mock.patch("install.apm_home",
                             return_value=self.tmp / "home" / ".apm")
        patcher.start()
        self.addCleanup(patcher.stop)
        self.dest = self.tmp / "home" / ".apm" / "apm.yml"

    def test_render_points_at_the_clone(self):
        text = install.render_user_manifest(self.tmp / "clone")
        self.assertTrue(text.startswith(install.USER_MANIFEST_MARKER))
        self.assertIn(f'    - "{(self.tmp / "clone").resolve().as_posix()}"\n',
                      text)
        parsed = install.parse_manifest(text)
        self.assertEqual(len(parsed["apm"]), 1)

    def test_windows_path_is_forward_slashed(self):
        fake = mock.Mock()
        fake.resolve.return_value.as_posix.return_value = "C:/Users/me/agent-skills"
        with mock.patch("install.Path", return_value=fake):
            text = install.render_user_manifest("C:\\Users\\me\\agent-skills")
        self.assertIn('- "C:/Users/me/agent-skills"', text)
        self.assertNotIn("\\", text)

    def test_write_new(self):
        status = install.write_user_manifest("x\n")
        self.assertEqual(status, "written")
        self.assertEqual(self.dest.read_bytes(), b"x\n")

    def test_write_is_idempotent(self):
        text = install.USER_MANIFEST_MARKER + "\nname: user\n"
        install.write_user_manifest(text)
        self.assertEqual(install.write_user_manifest(text), "up to date")

    def test_ours_is_updated(self):
        install.write_user_manifest(install.USER_MANIFEST_MARKER + "\nold\n")
        new = install.USER_MANIFEST_MARKER + "\nnew\n"
        self.assertEqual(install.write_user_manifest(new), "updated")
        self.assertEqual(self.dest.read_text(), new)

    def test_foreign_manifest_refused(self):
        self.dest.parent.mkdir(parents=True)
        self.dest.write_text("name: mine\n")
        with self.assertRaises(SystemExit) as cm:
            install.write_user_manifest(install.USER_MANIFEST_MARKER + "\n")
        self.assertIn("--force", str(cm.exception))
        self.assertEqual(self.dest.read_text(), "name: mine\n")

    def test_force_replaces_foreign(self):
        self.dest.parent.mkdir(parents=True)
        self.dest.write_text("name: mine\n")
        text = install.USER_MANIFEST_MARKER + "\n"
        self.assertEqual(install.write_user_manifest(text, force=True), "updated")
        self.assertEqual(self.dest.read_text(), text)

    def test_dry_run_writes_nothing(self):
        install.write_user_manifest("x\n", dry_run=True)
        self.assertFalse(self.dest.exists())

    def test_install_argv_per_target(self):
        for targets, value in ((["claude"], "claude"), (["copilot"], "copilot"),
                               (["copilot", "claude"], "claude,copilot")):
            with self.subTest(targets=targets):
                self.assertEqual(install.apm_install_argv("apm", targets),
                                 ["apm", "install", "-g", "--target", value])

    def test_run_apm_returns_exit_code(self):
        with mock.patch("install.subprocess.run",
                        return_value=mock.Mock(returncode=3)) as run:
            self.assertEqual(install.run_apm(["apm", "x"]), 3)
        run.assert_called_once_with(["apm", "x"])

    def test_run_apm_reports_missing_binary(self):
        with mock.patch("install.subprocess.run", side_effect=OSError("nope")):
            self.assertEqual(install.run_apm(["apm"]), 127)

    def test_is_wsl(self):
        for platform, text, expected in (("linux", "Linux 5.15 microsoft-standard-WSL2", True),
                                         ("linux", "Linux 6.1 generic", False),
                                         ("darwin", "microsoft", False)):
            with self.subTest(platform=platform, text=text), \
                    mock.patch("install.sys.platform", platform), \
                    mock.patch("install.Path.read_text", return_value=text):
                self.assertEqual(install.is_wsl(), expected)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m unittest test_install.TestApm -v`
Expected: FAIL — `AttributeError: ... 'apm_home'`.

- [ ] **Step 3: Implement** — add after `manifest_skill_names`:

```python
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
    return [exe, "install", "-g", "--target", value]


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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m unittest test_install.TestApm -v`
Expected: 12 tests OK.

- [ ] **Step 5: Commit**

```bash
git add install.py test_install.py
git commit -m "feat(install): write the user apm manifest and run apm install" -m "Refs #24"
```

---

### Task 5: Legacy cleanup of pre-APM installs

**Files:**
- Modify: `install.py` (new section after Task 4's code)
- Test: `test_install.py` (new class `TestLegacyCleanup`)

**Interfaces:**
- Consumes: `custom_skill_names()`, `manifest_deps()`, `apm_home()`, `_remove(path, dry_run)`, `target_root(target)` (existing; `target_root(target, repo=None)` keeps its signature).
- Produces: `legacy_skill_names() -> set[str]`; `remove_installer_skills(target: str, dest_root: Path, apm_owns: bool, dry_run: bool) -> list[tuple]`; `copilot_instruction_path() -> Path`; `remove_instruction_copy(dry_run: bool) -> list[tuple]`; `INSTRUCTIONS_SRC: Path`. Result tuples are `(target, name, status)` like the rest of `install.py`.

Rules (from the spec): APM never writes `~/.copilot/skills` (it uses `~/.agents/skills`), so legacy names there are always removed. In `~/.claude/skills`, a symlink into this clone is always ours (APM rejects symlinked destinations); a copy is ours only until APM owns the directory, which is when `~/.apm/apm.lock.yaml` exists.

- [ ] **Step 1: Write the failing tests**

```python
class TestLegacyCleanup(TempDirTest):
    def setUp(self):
        super().setUp()
        self.clone_skills = self.tmp / "clone" / "skills"
        self.make_skill("clone/skills", name="roj-a")
        for p in (mock.patch("install.SKILLS_SRC", self.clone_skills),
                  mock.patch("install.manifest_deps", return_value=[
                      {"name": "roj-a", "path": "./skills/roj-a"},
                      {"name": "code-tour", "path": "github/x/skills/code-tour"},
                      {"name": "pdf", "path": "anthropics/skills/skills/pdf"}])):
            p.start()
            self.addCleanup(p.stop)

    def test_legacy_names_are_custom_plus_community(self):
        self.assertEqual(install.legacy_skill_names(),
                         {"roj-a", "code-tour", "pdf"})

    def test_symlink_into_clone_always_removed(self):
        root = self.tmp / "claude"
        root.mkdir()
        try:
            (root / "roj-a").symlink_to(self.clone_skills / "roj-a",
                                        target_is_directory=True)
        except OSError:
            self.skipTest("symlinks unsupported here")
        results = install.remove_installer_skills("claude", root, apm_owns=True,
                                                  dry_run=False)
        self.assertFalse((root / "roj-a").is_symlink())
        self.assertEqual(results, [("claude", "roj-a", "removed (pre-APM link)")])

    def test_claude_copies_removed_before_apm_owns_them(self):
        self.make_skill("claude", name="code-tour")
        results = install.remove_installer_skills(
            "claude", self.tmp / "claude", apm_owns=False, dry_run=False)
        self.assertFalse((self.tmp / "claude" / "code-tour").exists())
        self.assertEqual(results, [("claude", "code-tour", "removed (pre-APM copy)")])

    def test_claude_copies_kept_after_apm_owns_them(self):
        self.make_skill("claude", name="code-tour")
        results = install.remove_installer_skills(
            "claude", self.tmp / "claude", apm_owns=True, dry_run=False)
        self.assertTrue((self.tmp / "claude" / "code-tour").is_dir())
        self.assertEqual(results, [])

    def test_copilot_copies_always_removed(self):
        self.make_skill("copilot", name="pdf")
        install.remove_installer_skills("copilot", self.tmp / "copilot",
                                        apm_owns=True, dry_run=False)
        self.assertFalse((self.tmp / "copilot" / "pdf").exists())

    def test_unknown_and_graphify_untouched(self):
        self.make_skill("copilot", name="graphify")
        self.make_skill("copilot", name="my-own")
        results = install.remove_installer_skills(
            "copilot", self.tmp / "copilot", apm_owns=False, dry_run=False)
        self.assertEqual(results, [])
        self.assertTrue((self.tmp / "copilot" / "graphify").is_dir())

    def test_dry_run_removes_nothing(self):
        self.make_skill("copilot", name="pdf")
        results = install.remove_installer_skills(
            "copilot", self.tmp / "copilot", apm_owns=False, dry_run=True)
        self.assertTrue((self.tmp / "copilot" / "pdf").is_dir())
        self.assertEqual(len(results), 1)

    def test_missing_root_is_fine(self):
        self.assertEqual(install.remove_installer_skills(
            "claude", self.tmp / "nope", apm_owns=False, dry_run=False), [])


class TestInstructionCopy(TempDirTest):
    def setUp(self):
        super().setUp()
        self.src = self.tmp / "clone" / "personal.instructions.md"
        self.src.parent.mkdir(parents=True)
        self.src.write_text("rules\n")
        self.dest = self.tmp / "home" / ".copilot" / "instructions" / "personal.instructions.md"
        self.dest.parent.mkdir(parents=True)
        for p in (mock.patch("install.INSTRUCTIONS_SRC", self.src),
                  mock.patch("install.copilot_instruction_path",
                             return_value=self.dest)):
            p.start()
            self.addCleanup(p.stop)

    def test_symlink_removed(self):
        other = self.tmp / "dotfiles" / "personal.instructions.md"
        other.parent.mkdir()
        other.write_text("rules\n")
        try:
            self.dest.symlink_to(other)
        except OSError:
            self.skipTest("symlinks unsupported here")
        results = install.remove_instruction_copy(dry_run=False)
        self.assertFalse(self.dest.is_symlink())
        self.assertTrue(other.exists())
        self.assertEqual(results[0][2], "removed (dotfiles link — APM deploys it now)")

    def test_identical_copy_removed(self):
        self.dest.write_text("rules\n")
        install.remove_instruction_copy(dry_run=False)
        self.assertFalse(self.dest.exists())

    def test_edited_instruction_copy_kept(self):
        self.dest.write_text("my local edits\n")
        err = io.StringIO()
        with mock.patch("sys.stderr", err):
            results = install.remove_instruction_copy(dry_run=False)
        self.assertEqual(self.dest.read_text(), "my local edits\n")
        self.assertIn("differs", err.getvalue())
        self.assertEqual(results, [])

    def test_absent_is_fine(self):
        self.assertEqual(install.remove_instruction_copy(dry_run=False), [])
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m unittest test_install.TestLegacyCleanup test_install.TestInstructionCopy -v`
Expected: FAIL — `AttributeError: ... 'legacy_skill_names'`.

- [ ] **Step 3: Implement** — add after Task 4's code:

```python
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
        elif entry.is_dir() and (target == "copilot" or not apm_owns):
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m unittest test_install.TestLegacyCleanup test_install.TestInstructionCopy -v`
Expected: 12 tests OK (symlink tests may report `skipped` on Windows).

- [ ] **Step 5: Commit**

```bash
git add install.py test_install.py
git commit -m "feat(install): clear pre-apm skill installs before apm takes over" -m "Refs #24"
```

---

### Task 6: New `main()`, status, and deleting the inventory machinery

**Files:**
- Modify: `install.py` — module docstring, `main()`, `show_status`, `print_summary`; delete the functions listed in Step 4.
- Delete: `skills-inventory.json`
- Modify: `test_install.py` — delete the classes listed in Step 5; add `TestMain`; rewrite `TestRequiresInvariants` and `TestSkillDependencies.test_every_referenced_skill_is_installable` to use the manifest.

**Interfaces:**
- Consumes: everything from Tasks 2, 4, 5; existing `EXTERNALS`, `bootstrap_cli`, `upgrade_cli`, `install_externals_for_target(target, sel_externals, repo, dry_run)`, `remove_legacy`, `retire_prompts`, `target_root`, `external_version`, `find_cli`, `cli_path_hint`.
- Produces: CLI `install.py [--target claude|copilot|both] [--dry-run] [--force] [--status] [--update] [--upgrade] [--skills-only]`; default target `both`.

- [ ] **Step 1: Write the failing tests**

```python
class TestMain(TempDirTest):
    """main() end to end with apm, externals and homes faked."""

    def run_main(self, argv, apm="/bin/apm", apm_code=0, lock=False, wsl=False):
        home = self.tmp / "home"
        (home / ".apm").mkdir(parents=True, exist_ok=True)
        if lock:
            (home / ".apm" / "apm.lock.yaml").write_text("x")
        calls = []

        def fake_run(cmd):
            calls.append(list(cmd))
            return apm_code

        out, err = io.StringIO(), io.StringIO()
        code = 0
        with contextlib.ExitStack() as stack:
            for p in (
                mock.patch("install.apm_home", return_value=home / ".apm"),
                mock.patch("install.target_root",
                           side_effect=lambda t, repo=None: home / t),
                mock.patch("install.copilot_instruction_path",
                           return_value=home / "instr" / "p.instructions.md"),
                mock.patch("install.claude_commands_dir",
                           return_value=home / "commands"),
                mock.patch("install.find_cli",
                           side_effect=lambda n: apm if n == "apm" else None),
                mock.patch("install.run_apm", side_effect=fake_run),
                mock.patch("install.EXTERNALS", []),
                mock.patch("install.is_wsl", return_value=wsl),
                mock.patch("install.vscode_prompts_dir", return_value=None),
                mock.patch("sys.argv", ["install.py", *argv]),
                mock.patch("sys.stdout", out),
                mock.patch("sys.stderr", err),
            ):
                stack.enter_context(p)
            try:
                install.main()
            except SystemExit as exc:
                code = exc.code if isinstance(exc.code, int) else 1
                err.write(str(exc.code))
        return code, calls, out.getvalue(), err.getvalue()

    def test_default_installs_both(self):
        code, calls, out, _ = self.run_main([])
        self.assertEqual(code, 0)
        self.assertEqual(calls, [["/bin/apm", "install", "-g", "--target",
                                  "claude,copilot"]])
        manifest = (self.tmp / "home" / ".apm" / "apm.yml").read_text()
        self.assertIn(install.REPO_ROOT.resolve().as_posix(), manifest)

    def test_single_target(self):
        _, calls, _, _ = self.run_main(["--target", "copilot"])
        self.assertEqual(calls[0][-1], "copilot")

    def test_missing_apm_stops_with_hint(self):
        code, calls, _, err = self.run_main(["--target", "claude"], apm=None)
        self.assertEqual(code, 1)
        self.assertEqual(calls, [])
        self.assertIn("brew install apm", err)

    def test_dry_run_without_apm_prints_plan(self):
        code, calls, out, _ = self.run_main(["--dry-run"], apm=None)
        self.assertEqual(code, 0)
        self.assertEqual(calls, [])
        self.assertIn("would run apm install -g --target claude,copilot", out)
        self.assertFalse((self.tmp / "home" / ".apm" / "apm.yml").exists())

    def test_apm_failure_is_the_exit_code(self):
        code, _, _, _ = self.run_main([], apm_code=2)
        self.assertEqual(code, 2)

    def test_update_reports_outdated(self):
        code, calls, _, _ = self.run_main(["--update"])
        self.assertEqual(calls, [["/bin/apm", "outdated", "-g"]])
        self.assertEqual(code, 0)

    def test_status_lists_apm_deps(self):
        _, calls, _, _ = self.run_main(["--status"])
        self.assertEqual(calls, [["/bin/apm", "deps", "list", "-g"]])

    def test_removed_flags_are_rejected(self):
        for flag in (["--repo", "."], ["--skill", "x"], ["--list"],
                     ["--uninstall", "x"], ["--add-inventory", "a/b@c"],
                     ["--check-inventory-updates"]):
            with self.subTest(flag=flag):
                code, calls, _, _ = self.run_main(flag)
                self.assertEqual(code, 2)
                self.assertEqual(calls, [])

    def test_legacy_copilot_copy_cleared_before_apm(self):
        self.make_skill("home/copilot", name="code-tour")
        self.run_main(["--target", "copilot"], lock=True)
        self.assertFalse((self.tmp / "home" / "copilot" / "code-tour").exists())

    def test_wsl_hint_printed(self):
        _, _, out, _ = self.run_main([], wsl=True)
        self.assertIn("run install.py from Git Bash too", out)

    def test_status_flags_leftover_links(self):
        root = self.tmp / "home" / "claude"
        root.mkdir(parents=True)
        try:
            (root / "roj-explain-logic").symlink_to(
                install.SKILLS_SRC / "roj-explain-logic",
                target_is_directory=True)
        except OSError:
            self.skipTest("symlinks unsupported here")
        _, _, _, err = self.run_main(["--status", "--target", "claude"])
        self.assertIn("roj-explain-logic", err)
        self.assertIn("re-run install.py", err)
```

Rewrite `TestRequiresInvariants` (replace the whole class):

```python
class TestRequiresInvariants(unittest.TestCase):
    """REQUIRES must track real names, and apm.yml must install every
    requirement wherever its dependent goes."""

    def test_keys_are_custom_skills(self):
        for skill in install.REQUIRES:
            with self.subTest(skill=skill):
                self.assertIn(skill, install.custom_skill_names())

    def test_requirements_are_live_for_every_target(self):
        deps = {d["name"]: d for d in install.manifest_deps() if d["active"]}
        for skill, needs in install.REQUIRES.items():
            for dep in needs:
                with self.subTest(skill=skill, dep=dep):
                    self.assertIn(dep, deps)
                    self.assertIsNone(deps[dep]["targets"])
```

In `TestSkillDependencies.test_every_referenced_skill_is_installable`, replace `install.all_community_names()` with `install.manifest_skill_names(active_only=False)`, and the assertion message `"add it with install.py --add-inventory, "` with `"add it to apm.yml, "`.

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m unittest test_install.TestMain -v`
Expected: FAIL — e.g. `test_update_reports_outdated` calls bump code, `test_removed_flags_are_rejected` exits 0.

- [ ] **Step 3: Replace `main()`, `show_status()` and `print_summary()`**

```python
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
    if not exe and not args.dry_run:
        sys.exit(APM_INSTALL_HINT)
    if args.update:
        sys.exit(run_apm([exe, "outdated", "-g"]))

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
        render_user_manifest(), args.force, args.dry_run)))
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
```

Replace the module docstring's usage block with:

```python
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
```

- [ ] **Step 4: Delete dead code from `install.py`**

Delete these definitions entirely (they served the inventory, picker, `--repo`, `--skill`, `--list` and `--uninstall`):
`SOURCES`, `INVENTORY_PATH`, `INVENTORY_REQUIRED`, `INVENTORY_KEYS`, `_PART_RE`, `_SKILL_RE`, `_SHA_RE`, `InventoryError`, `_safe_path`, `load_inventory`, `inventory_sources`, `check_inventory_names`, `_inventory_sources` and the module-level call that fills `SOURCES` from it, `all_external_names`, `registry`, `source_by_label`, `source_skills_subdir`, `all_community_names`, `default_community_names`, `required_by`, `add_requirements`, `_present`, `missing_requirements`, `uninstall_dependents`, `symlinks_supported`, `_SYMLINK_SUPPORT`, `install_symlink`, `resolve_repo`, `pick_targets`, `status_targets`, `build_items`, `item_tag`, `pick_items`, `CACHE_ROOT`, `LEGACY_CACHES`, `source_cache_dir`, `remove_legacy_caches`, `skill_folder`, `update_source_cache`, `run_git`, `git_head`, `fetch_pinned`, `update_repo_cache`, `remote_head`, `check_inventory_updates`, `_SKILLS_SH_RE`, `_CLI_SPEC_RE`, `parse_skill_spec`, `frontmatter_name`, `with_remote_tree`, `locate_skill`, `add_inventory`, `relocate_skills`, `bump_inventory`, `check_checkout_current`, `installed_names`, `install_community_for_target`, `uninstall_externals`, `enabled_plugins`, `plugin_skills`, `gather_status`, `skill_description`, `show_list`, `resolve_skill_args`, `uninstall_skills`.

Keep: `BOTH`, `ANY`, `REPO_SKILLS_SUBDIR` (used by `target_root`), `EXTERNALS`, `REQUIRES`, `LEGACY_PREFIX`, `RETIRED_PROMPTS`, `GENERATED_MARKER`, `legacy_name`, `externals`, `default_external_names`, `log`, `ok`, `warn`, `dirs_equal`, `install_copy`, `target_root`, `vscode_prompts_dir`, `custom_skill_names`, `claude_commands_dir`, `prompts_dir_for`, `legacy_names`, `is_ours`, `is_generated`, `_remove`, `remove_legacy`, `retire_prompts`, every external/CLI helper from `user_script_dirs` through `install_externals_for_target`.

Then delete the file: `git rm skills-inventory.json`.

Run: `python3 -c "import ast,sys; t=ast.parse(open('install.py').read()); print('ok')" && python3 -m pyflakes install.py 2>/dev/null || python3 -W error -c "import install"`
Expected: `ok`, and no `NameError`/import errors. If `pyflakes` is installed, it must report no undefined names.

- [ ] **Step 5: Delete tests of deleted code from `test_install.py`**

Delete these classes entirely: `TestInstallSymlink`, `TestSymlinkFallback`, `TestPickTargets`, `TestCommunityCache`, `TestBuildItems`, `TestPickItems`, `TestRegistry`, `TestSourceSubdir`, `TestInstallCommunityForTarget`, `TestStatus`, `TestPickerTags`, `TestUninstall`, `TestResolveRepo`, `TestTargetRootRepo`, `TestPickTargetsRepo`, `TestStatusTargets`, `TestCommunityRepoPolicy`, `TestUninstallExternals`, `TestExternalStatus`, `TestExternalRegistry`, `TestRequiredBy`, `TestAddRequirements`, `TestMissingRequirements`, `TestUninstallDependents`, `MainHarness`, `TestMainRequirements`, `InventoryTest`, `TestLoadInventory`, `TestInventorySources`, `TestRepoInventory`, `TestBumpInventory`, `TestCheckCheckoutCurrent`, `TestMainUpdate`, `TestPinnedCache`, `TestCheckInventoryUpdates`, `TestParseSkillSpec`, `TestAddInventory`.

In `TestPromptsDirFor` and `TestRetirePrompts`, delete only the test methods that pass `"repo"` as a target or a `repo=` argument.

- [ ] **Step 6: Run the whole suite**

Run: `python3 -m unittest test_install test_skills 2>&1 | tail -5`
Expected: `OK` (some `skipped` allowed). Any `AttributeError: module 'install' has no attribute X` means a kept test still uses deleted code — delete that test if it covers deleted behavior, otherwise restore the function.

- [ ] **Step 7: Commit**

```bash
git add -A install.py test_install.py skills-inventory.json
git commit -m "feat(install): install through apm and retire the skills inventory" -m "Refs #24"
```

---

### Task 7: CI on macOS, Linux and Windows Git Bash, plus an APM smoke job

**Files:**
- Modify: `.github/workflows/test.yml`

**Interfaces:**
- Consumes: `install.py --dry-run`, `apm.yml` (Tasks 3, 6).

- [ ] **Step 1: Replace the `unittest` job and add `apm-smoke`**

```yaml
  unittest:
    strategy:
      fail-fast: false
      matrix:
        os: [ubuntu-latest, macos-latest, windows-latest]
    runs-on: ${{ matrix.os }}
    defaults:
      run:
        shell: bash   # Git Bash on windows-latest — the shell the VDI uses
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - name: Installer
        run: python -m unittest test_install
      - name: Skills follow the Agent Skills spec
        run: python -m unittest test_skills
      - name: Shared files are in sync
        run: python tools/sync_shared.py --check

  apm-smoke:
    # Real apm, scratch HOME: does apm.yml resolve from this clone?
    strategy:
      fail-fast: false
      matrix:
        os: [ubuntu-latest, macos-latest, windows-latest]
    runs-on: ${{ matrix.os }}
    defaults:
      run:
        shell: bash
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - name: Install apm
        run: python -m pip install apm-cli
      - name: install.py writes the user manifest
        run: |
          export HOME="$RUNNER_TEMP/home" USERPROFILE="$RUNNER_TEMP/home"
          mkdir -p "$HOME"
          python install.py --dry-run --skills-only
          python - <<'EOF'
          import install, pathlib
          install.write_user_manifest(install.render_user_manifest())
          print(pathlib.Path.home().joinpath(".apm", "apm.yml").read_text())
          EOF
      - name: apm resolves it
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
        run: |
          export HOME="$RUNNER_TEMP/home" USERPROFILE="$RUNNER_TEMP/home"
          cd "$HOME" && apm install -g --target claude,copilot --dry-run
```

Also update the `discoverable` job comment from `r0jjames/agent-skills` to `rojcarranza/agent-skills`.

- [ ] **Step 2: Lint the workflow locally**

Run: `python3 -c "import yaml" 2>/dev/null && python3 -c "import yaml;yaml.safe_load(open('.github/workflows/test.yml'))" && echo ok || ruby -ryaml -e 'YAML.load_file(".github/workflows/test.yml"); puts "ok"'`
Expected: `ok`.

- [ ] **Step 3: Commit**

```bash
git add .github/workflows/test.yml
git commit -m "ci: test the installer on macos, linux and windows git bash" -m "Refs #24"
```

(The jobs run when the branch is pushed in Task 9; a Windows-only failure there is fixed in `install.py`/tests, not skipped, unless it is a symlink-permission test, which already calls `skipTest`.)

---

### Task 8: README, installer reference and community-skills docs

**Files:**
- Modify: `README.md` (`## Install` section, `## Repository layout` block, the graphify/community paragraphs that mention `install.py` flags)
- Modify: `docs/installer.md`
- Modify: `docs/community-skills.md`

**Interfaces:**
- Consumes: final flag set from Task 6; Task 1 findings (removal behavior, Copilot path).

- [ ] **Step 1: Replace README `## Install`** (everything from `## Install` up to `## Skills`) with the spec's "Target text" block verbatim (spec section "README and docs"), which already uses `rojcarranza` and the Git Bash / WSL lines. If Task 1 item 6 failed, change its "edit `apm.yml` and re-run" sentence for removals to `apm uninstall -g <name>`.

- [ ] **Step 2: Update README `## Repository layout`**

Replace the line `skills-inventory.json  every community skill, pinned to a commit` with:

```text
apm.yml           every skill, community skill and MCP server install.py installs (APM manifest)
.apm/instructions/  personal instructions APM deploys to Copilot and Claude
```

and replace `install.py        full installer (see docs/installer.md)` with `install.py        writes ~/.apm/apm.yml, runs apm install -g, installs graphify (docs/installer.md)`.

- [ ] **Step 3: Rewrite `docs/installer.md`**

- Title stays `# install.py reference`. Replace `## Flags and modes` with a table of exactly the Task 6 flags (`--target`, `--dry-run`, `--force`, `--status`, `--update`, `--upgrade`, `--skills-only`) and one paragraph on the run order (legacy cleanup → `~/.apm/apm.yml` → `apm install -g` → graphify).
- Delete `### Skill dependencies`, `## Skills inventory (skills.sh)` and `## Updating everything`; add `## The APM manifest` covering: the two dependency forms with an example each, `targets: [copilot]`, optional (commented) entries, bumping a SHA after `--update`, and where things land (Claude `~/.claude/skills`, Copilot `~/.agents/skills` or the path Task 1 observed, instructions `~/.copilot/instructions/`, MCP config per agent).
- Add `## Platforms` with the spec's platform table.
- Keep `## External skills`, `### How our skills use the graph`, `### Updating an external`, `## Work VDI (Windows, Git Bash)`, `## JetBrains`; in the VDI and JetBrains sections replace any `--repo`/`--skill`/copy-path instructions with the APM route and note Copilot's `~/.agents/skills`.
- `## History`: add one paragraph — "Before APM (2026-10), install.py copied community skills from skills-inventory.json and linked our skills; the first APM run removes those entries."

- [ ] **Step 4: Update `docs/community-skills.md`**

Replace the intro's install instructions with: "Every skill here is listed in [`apm.yml`](../apm.yml) — live ones install by default, commented ones are optional: uncomment and re-run `install.py`." Keep every per-skill section.

- [ ] **Step 5: Check no stale references remain**

Run: `grep -rnE "skills-inventory|--add-inventory|--check-inventory|--repo |--skill |--list|--uninstall|r0jjames" README.md docs/installer.md docs/community-skills.md install.py .github .claude-plugin`
Expected: no output (history paragraph wording must avoid these tokens, or the match is reviewed and accepted as history).

- [ ] **Step 6: Run the suite and commit**

Run: `python3 -m unittest test_install test_skills 2>&1 | tail -3 && python3 tools/sync_shared.py --check`
Expected: `OK`, sync check clean.

```bash
git add README.md docs/installer.md docs/community-skills.md
git commit -m "docs: document installing everything through apm" -m "Refs #24"
```

---

### Task 9: Manual verification on the Mac, then the pull request

**Files:**
- None committed (verification only).

- [ ] **Step 1: Dry run against the real home**

Run: `python3 install.py --dry-run`
Expected: removals of pre-APM links/copies listed, `~/.apm/apm.yml written`, `dry-run: would run apm install -g --target claude,copilot`, graphify line. Show this output to Roj and get a yes before Step 2 — it modifies `~/.claude`, `~/.copilot` and `~/.agents`.

- [ ] **Step 2: Real run and status**

Run: `python3 install.py && python3 install.py --status`
Expected: exit 0; `--status` shows the 9 `roj-*` skills, 7 community skills (5 for Claude), no leftover warnings.

- [ ] **Step 3: Check each agent**

- `ls ~/.claude/skills ~/.agents/skills ~/.copilot/instructions` — `caveman` and `debugging-and-error-recovery` only under the Copilot path.
- New `claude` session: "what skills are available?" lists `roj-*`, `code-tour`, `find-skills`; `/mcp` lists the GitHub server.
- Copilot CLI: `/skills list`; VS Code agent mode: "What skills do you have available?"; confirm the personal instruction is applied (ask "what are your output style rules?").

Record results in `$SCRATCH/step0-findings.md` under "Manual check".

- [ ] **Step 4: Push and open the PR**

```bash
git push -u origin feat/apm-install
gh pr create --title "feat(install): manage skills, instructions and mcp through apm" --body-file "$SCRATCH/pr-body.md"
```

`pr-body.md` starts with `Closes #24`, then: summary (one paragraph), what moved where, Step 0 findings, manual check results, the platform matrix CI result, and the follow-up dotfiles change (spec Step 2). Use the `write-pr-description` skill to draft it. No Claude attribution.

- [ ] **Step 5: Link the PR in the issue**

Run: `gh issue comment 24 --body "PR: <url>"`

- [ ] **Step 6: Bind the PR and read CI** (desktop app `ccd_pr` tools: `get_status`, `bind_pr` if needed). Fix any matrix failure on the branch.

---

## Not in this plan

The dotfiles change (spec Step 2: drop `copilot/personal.instructions.md` and its install step) gets its own issue and PR in the dotfiles repo after this merges.
