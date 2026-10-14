import contextlib
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import install


class TempDirTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)

    def make_skill(self, root, name="skill-a", content="hello"):
        d = self.tmp / root / name
        d.mkdir(parents=True)
        (d / "SKILL.md").write_text(content)
        return d


class TestDirsEqual(TempDirTest):
    def test_identical_trees_equal(self):
        a = self.make_skill("a")
        b = self.make_skill("b")
        self.assertTrue(install.dirs_equal(a, b))

    def test_different_file_content_not_equal(self):
        a = self.make_skill("a", content="one")
        b = self.make_skill("b", content="two")
        self.assertFalse(install.dirs_equal(a, b))

    def test_extra_file_not_equal(self):
        a = self.make_skill("a")
        b = self.make_skill("b")
        (b / "extra.md").write_text("x")
        self.assertFalse(install.dirs_equal(a, b))

    def test_nested_difference_detected(self):
        a = self.make_skill("a")
        b = self.make_skill("b")
        (a / "sub").mkdir()
        (a / "sub" / "f.txt").write_text("1")
        (b / "sub").mkdir()
        (b / "sub" / "f.txt").write_text("2")
        self.assertFalse(install.dirs_equal(a, b))


class TestInstallCopy(TempDirTest):
    def test_new_install(self):
        src = self.make_skill("src")
        dest = self.tmp / "dest" / "skill-a"
        status = install.install_copy(src, dest, dry_run=False)
        self.assertEqual(status, "installed")
        self.assertEqual((dest / "SKILL.md").read_text(), "hello")

    def test_up_to_date(self):
        src = self.make_skill("src")
        dest = self.tmp / "dest" / "skill-a"
        install.install_copy(src, dest, dry_run=False)
        self.assertEqual(install.install_copy(src, dest, dry_run=False), "up to date")

    def test_updated(self):
        src = self.make_skill("src")
        dest = self.tmp / "dest" / "skill-a"
        install.install_copy(src, dest, dry_run=False)
        (src / "SKILL.md").write_text("changed")
        self.assertEqual(install.install_copy(src, dest, dry_run=False), "updated")
        self.assertEqual((dest / "SKILL.md").read_text(), "changed")

    def test_dry_run_writes_nothing(self):
        src = self.make_skill("src")
        dest = self.tmp / "dest" / "skill-a"
        status = install.install_copy(src, dest, dry_run=True)
        self.assertEqual(status, "installed")
        self.assertFalse(dest.exists())

    def test_replaces_symlink_with_copy(self):
        src = self.make_skill("src")
        other = self.make_skill("other", name="skill-b")
        dest = self.tmp / "dest" / "skill-a"
        dest.parent.mkdir(parents=True)
        dest.symlink_to(other)
        status = install.install_copy(src, dest, dry_run=False)
        self.assertEqual(status, "updated")
        self.assertFalse(dest.is_symlink())
        self.assertEqual((dest / "SKILL.md").read_text(), "hello")


class TestInstallSymlink(TempDirTest):
    def test_creates_link(self):
        src = self.make_skill("src")
        dest = self.tmp / "dest" / "skill-a"
        status = install.install_symlink(src, dest, dry_run=False)
        self.assertEqual(status, "linked")
        self.assertTrue(dest.is_symlink())
        self.assertEqual(dest.resolve(), src.resolve())

    def test_already_linked(self):
        src = self.make_skill("src")
        dest = self.tmp / "dest" / "skill-a"
        install.install_symlink(src, dest, dry_run=False)
        self.assertEqual(install.install_symlink(src, dest, dry_run=False),
                         "already linked")

    def test_wrong_link_replaced(self):
        src = self.make_skill("src")
        other = self.make_skill("other", name="skill-b")
        dest = self.tmp / "dest" / "skill-a"
        dest.parent.mkdir(parents=True)
        dest.symlink_to(other)
        status = install.install_symlink(src, dest, dry_run=False)
        self.assertEqual(status, "linked")
        self.assertEqual(dest.resolve(), src.resolve())

    def test_broken_link_replaced(self):
        src = self.make_skill("src")
        dest = self.tmp / "dest" / "skill-a"
        dest.parent.mkdir(parents=True)
        dest.symlink_to(self.tmp / "gone")
        status = install.install_symlink(src, dest, dry_run=False)
        self.assertEqual(status, "linked")
        self.assertEqual(dest.resolve(), src.resolve())

    def test_real_dir_backed_up(self):
        src = self.make_skill("src")
        dest = self.make_skill("dest", content="old local copy")
        status = install.install_symlink(src, dest, dry_run=False)
        self.assertEqual(status, "linked")
        self.assertTrue(dest.is_symlink())
        backup = dest.parent / (dest.name + ".bak")
        self.assertEqual((backup / "SKILL.md").read_text(), "old local copy")

    def test_dry_run_writes_nothing(self):
        src = self.make_skill("src")
        dest = self.tmp / "dest" / "skill-a"
        status = install.install_symlink(src, dest, dry_run=True)
        self.assertEqual(status, "linked")
        self.assertFalse(dest.exists())


class TestSymlinkFallback(TempDirTest):
    """Windows/Git Bash: symlinks need Developer Mode or admin."""

    def setUp(self):
        super().setUp()
        install._SYMLINK_SUPPORT.clear()
        self.addCleanup(install._SYMLINK_SUPPORT.clear)

    def no_symlinks(self):
        return mock.patch.object(Path, "symlink_to",
                                 side_effect=OSError("WinError 1314"))

    def test_falls_back_to_copy(self):
        src = self.make_skill("src")
        dest = self.tmp / "dest" / "skill-a"
        with self.no_symlinks():
            status = install.install_symlink(src, dest, dry_run=False)
        self.assertEqual(status, "installed (copy fallback)")
        self.assertFalse(dest.is_symlink())
        self.assertEqual((dest / "SKILL.md").read_text(), "hello")

    def test_second_run_is_up_to_date_without_backup(self):
        src = self.make_skill("src")
        dest = self.tmp / "dest" / "skill-a"
        with self.no_symlinks():
            install.install_symlink(src, dest, dry_run=False)
            status = install.install_symlink(src, dest, dry_run=False)
        self.assertEqual(status, "up to date (copy fallback)")
        self.assertFalse((dest.parent / "skill-a.bak").exists())

    def test_edited_skill_refreshes_copy(self):
        src = self.make_skill("src")
        dest = self.tmp / "dest" / "skill-a"
        with self.no_symlinks():
            install.install_symlink(src, dest, dry_run=False)
            (src / "SKILL.md").write_text("edited")
            status = install.install_symlink(src, dest, dry_run=False)
        self.assertEqual(status, "updated (copy fallback)")
        self.assertEqual((dest / "SKILL.md").read_text(), "edited")

    def test_probe_is_cached_and_leaves_nothing_behind(self):
        dest_dir = self.tmp / "dest"
        with self.no_symlinks() as patched:
            self.assertFalse(install.symlinks_supported(dest_dir))
            self.assertFalse(install.symlinks_supported(dest_dir))
            self.assertEqual(patched.call_count, 1)
        self.assertEqual(list(dest_dir.iterdir()), [])

    def test_dry_run_skips_probe(self):
        src = self.make_skill("src")
        dest = self.tmp / "dest" / "skill-a"
        with self.no_symlinks():
            status = install.install_symlink(src, dest, dry_run=True)
        self.assertEqual(status, "linked")
        self.assertFalse(dest.parent.exists())


class TestPickTargets(unittest.TestCase):
    def test_explicit_targets(self):
        self.assertEqual(install.pick_targets("copilot"), ["copilot"])
        self.assertEqual(install.pick_targets("claude"), ["claude"])
        self.assertEqual(install.pick_targets("both"), ["copilot", "claude"])

    def test_interactive_menu(self):
        with mock.patch("builtins.input", return_value="2"):
            self.assertEqual(install.pick_targets(None), ["claude"])

    def test_interactive_invalid_exits(self):
        with mock.patch("builtins.input", return_value="9"):
            with self.assertRaises(SystemExit):
                install.pick_targets(None)


class TestVscodePromptsDir(TempDirTest):
    def test_appdata_windows_layout(self):
        user = self.tmp / "AppData" / "Code" / "User"
        user.mkdir(parents=True)
        with mock.patch.dict(os.environ, {"APPDATA": str(self.tmp / "AppData")}):
            self.assertEqual(install.vscode_prompts_dir(), user / "prompts")

    def test_none_when_no_vscode(self):
        with mock.patch.dict(os.environ, {}, clear=True), \
             mock.patch("install.Path.home", return_value=self.tmp):
            self.assertIsNone(install.vscode_prompts_dir())


class TestCommunityCache(TempDirTest):
    """Registry sources fetch through update_source_cache at their pin."""

    def cache_for(self, label):
        source = install.source_by_label(label)
        cache = self.tmp / "cache" / source["cache"]
        return source, cache

    def test_clone_failure_without_cache_returns_none(self):
        source, cache = self.cache_for("github/awesome-copilot")
        boom = subprocess.CalledProcessError(128, ["git", "clone"])
        with mock.patch("install.source_cache_dir", return_value=cache), \
             mock.patch("install.run_git", side_effect=boom), \
             contextlib.redirect_stderr(io.StringIO()):
            self.assertIsNone(install.update_source_cache(source, False))

    def test_clone_failure_reuses_a_cache_at_the_pin(self):
        source, cache = self.cache_for("github/awesome-copilot")
        (cache / "skills" / "code-tour").mkdir(parents=True)
        boom = subprocess.CalledProcessError(128, ["git", "fetch"])
        with mock.patch("install.source_cache_dir", return_value=cache), \
             mock.patch("install.run_git", side_effect=boom), \
             mock.patch("install.git_head", return_value=source["ref"]), \
             contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(install.update_source_cache(source, False),
                             cache)

    def test_fresh_clone_uses_the_source_repo_and_pin(self):
        for label, sparse in (
                ("juliusbrussee/caveman", "skills/caveman"),
                ("addyosmani/agent-skills",
                 "skills/debugging-and-error-recovery")):
            with self.subTest(label):
                source, cache = self.cache_for(label)
                calls = []
                with mock.patch("install.source_cache_dir",
                                return_value=cache), \
                     mock.patch("install.run_git",
                                side_effect=lambda a: calls.append(a)), \
                     contextlib.redirect_stdout(io.StringIO()):
                    result = install.update_source_cache(source, False)
                self.assertEqual(result, cache)
                self.assertIn(source["url"], calls[0])
                self.assertIn(sparse, calls[1])
                self.assertEqual(calls[2][-1], source["ref"])

    def test_cache_dir_is_named_after_the_repo(self):
        source = install.source_by_label("anthropics/skills")
        self.assertEqual(install.source_cache_dir(source),
                         install.CACHE_ROOT / "anthropics--skills")

    def test_legacy_caches_removed_once(self):
        root = self.tmp / "cache-root"
        (root / "awesome-copilot" / ".git").mkdir(parents=True)
        (root / "unrelated").mkdir()
        with mock.patch("install.CACHE_ROOT", root), \
             contextlib.redirect_stdout(io.StringIO()):
            install.remove_legacy_caches(dry_run=True)
            self.assertTrue((root / "awesome-copilot").exists())
            install.remove_legacy_caches(dry_run=False)
        self.assertFalse((root / "awesome-copilot").exists())
        self.assertTrue((root / "unrelated").exists())


class TestBuildItems(unittest.TestCase):
    def test_orders_skills_community_externals(self):
        items = install.build_items(
            custom_skills=["roj-explain-logic", "roj-soundboarding"])
        kinds = [k for k, _ in items]
        self.assertEqual(kinds[:2], ["skill", "skill"])
        community = len(install.all_community_names())
        self.assertTrue(all(k == "community"
                            for k in kinds[2:2 + community]))
        self.assertTrue(all(k == "external"
                            for k in kinds[2 + community:]))
        names = [n for _, n in items]
        for s in install.all_community_names():
            self.assertIn(s, names)


class TestPickItems(unittest.TestCase):
    ITEMS = [("skill", "roj-explain-logic"), ("skill", "roj-soundboarding"),
             ("skill", "roj-tour-codebase"), ("community", "caveman")]

    def pick(self, inputs):
        it = iter(inputs)
        with mock.patch("builtins.input", side_effect=lambda *_: next(it)):
            return install.pick_items(list(self.ITEMS))

    def test_enter_confirms_all_preselected(self):
        self.assertEqual(self.pick([""]), self.ITEMS)

    def test_number_toggles_off(self):
        result = self.pick(["2", ""])
        self.assertNotIn(("skill", "roj-soundboarding"), result)
        self.assertEqual(len(result), 3)

    def test_toggle_twice_back_on(self):
        self.assertEqual(self.pick(["2", "2", ""]), self.ITEMS)

    def test_a_toggles_all_then_one_on(self):
        result = self.pick(["a", "3", ""])
        self.assertEqual(result, [("skill", "roj-tour-codebase")])

    def test_zero_selected_exits(self):
        with self.assertRaises(SystemExit):
            self.pick(["a", ""])

    def test_invalid_input_reprompts(self):
        self.assertEqual(self.pick(["zzz", "99", ""]), self.ITEMS)


class TestRegistry(unittest.TestCase):
    def test_caveman_is_copilot_only(self):
        source, meta = install.registry()["caveman"]
        self.assertEqual(meta["targets"], ("copilot",))
        self.assertEqual(source["label"], "juliusbrussee/caveman")

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

    def test_default_names_match_the_inventory(self):
        self.assertEqual(
            install.default_community_names(),
            {e["skill"] for e in install.load_inventory() if e["default"]})

    def test_skills_kept_through_the_migration(self):
        # Everything install.py hardcoded before skills-inventory.json.
        self.assertLessEqual(
            {"code-tour", "acquire-codebase-knowledge", "context-map",
             "architecture-blueprint-generator", "add-educational-comments",
             "caveman", "debugging-and-error-recovery",
             "observability-and-instrumentation", "ci-cd-and-automation",
             "security-and-hardening", "deprecation-and-migration",
             "write-pr-description", "pdf", "docx", "pptx", "xlsx"},
            install.all_community_names())

    def test_update_source_cache_sparse_names(self):
        source = install.source_by_label("addyosmani/agent-skills")
        with mock.patch("install.update_repo_cache") as m:
            install.update_source_cache(source, dry_run=False,
                                        names=["security-and-hardening"])
        sparse = m.call_args[0][3]
        self.assertEqual(sparse, ["skills/security-and-hardening"])


class TestSourceSubdir(TempDirTest):
    """Sources may keep their skill folders somewhere other than skills/ —
    warpdotdev/common-skills uses .agents/skills/."""

    def test_default_subdir_is_skills(self):
        source = install.source_by_label("addyosmani/agent-skills")
        self.assertEqual(install.source_skills_subdir(source), "skills")

    def test_warp_source_registers_write_pr_description(self):
        source, meta = install.registry()["write-pr-description"]
        self.assertEqual(source["label"], "warpdotdev/common-skills")
        self.assertEqual(source["url"],
                         "https://github.com/warpdotdev/common-skills.git")
        self.assertEqual(install.source_skills_subdir(source),
                         ".agents/skills")
        self.assertEqual(meta, {"targets": install.ANY, "default": True})

    def test_sparse_paths_and_cache_check_use_the_subdir(self):
        source = install.source_by_label("warpdotdev/common-skills")
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
        with mock.patch("install.run_git", side_effect=boom), \
             mock.patch("install.git_head", return_value=SHA_A), \
             contextlib.redirect_stderr(io.StringIO()):
            result = install.update_repo_cache(
                cache, "u", SHA_A, [], False, "warp", "f",
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


class TestStatus(TempDirTest):
    def make_dest(self):
        dest = self.tmp / "claude-skills"
        dest.mkdir(parents=True)
        return dest

    def test_classifies_custom_community_unknown(self):
        dest = self.make_dest()
        src = self.make_skill("repo", name="roj-explain-logic")
        (dest / "roj-explain-logic").symlink_to(src)
        (dest / "code-tour").mkdir()
        (dest / "mystery").mkdir()
        rows, warnings = install.gather_status(
            "claude", dest, {"roj-explain-logic"}, {})
        by_name = {r[0]: r for r in rows}
        self.assertEqual(by_name["roj-explain-logic"][1:],
                         ("custom", "symlink"))
        self.assertEqual(by_name["code-tour"][1:],
                         ("community (github/awesome-copilot)", "copy"))
        self.assertEqual(by_name["mystery"][1:], ("unknown", "copy"))
        self.assertEqual(warnings, [])

    def test_broken_symlink_warns(self):
        dest = self.make_dest()
        (dest / "roj-explain-logic").symlink_to(self.tmp / "gone")
        _, warnings = install.gather_status(
            "claude", dest, {"roj-explain-logic"}, {})
        self.assertIn("claude: roj-explain-logic is a broken symlink", warnings)

    def test_leftover_backup_warns(self):
        dest = self.make_dest()
        (dest / "roj-explain-logic.bak").mkdir()
        _, warnings = install.gather_status(
            "claude", dest, {"roj-explain-logic"}, {})
        self.assertTrue(any("roj-explain-logic.bak" in w and "delete it" in w
                            for w in warnings))

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


class TestPickerTags(TempDirTest):
    def test_installed_tag(self):
        root = self.tmp / "claude" / "skills"
        (root / "code-tour").mkdir(parents=True)
        with mock.patch("install.target_root", return_value=root), \
             mock.patch("install.source_cache_dir", return_value=self.tmp / "cache"):
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
        src = self.make_skill("repo", name="roj-explain-logic",
                              content="new")
        root = self.tmp / "copilot" / "skills"
        (root / "roj-explain-logic").mkdir(parents=True)
        (root / "roj-explain-logic" / "SKILL.md").write_text("old")
        with mock.patch("install.target_root", return_value=root), \
             mock.patch("install.SKILLS_SRC", src.parent):
            tag = install.item_tag("skill", "roj-explain-logic",
                                   ["copilot"], {})
        self.assertEqual(tag, "[installed] [update]")

    def test_update_tag_for_stale_community_copy(self):
        cache = self.tmp / "cache"
        (cache / "skills" / "code-tour").mkdir(parents=True)
        (cache / "skills" / "code-tour" / "SKILL.md").write_text("new")
        root = self.tmp / "claude" / "skills"
        (root / "code-tour").mkdir(parents=True)
        (root / "code-tour" / "SKILL.md").write_text("old")
        with mock.patch("install.target_root", return_value=root), \
             mock.patch("install.source_cache_dir", return_value=cache):
            tag = install.item_tag("community", "code-tour", ["claude"], {})
        self.assertEqual(tag, "[installed] [update]")

    def test_update_tag_follows_the_upstream_folder(self):
        cache = self.tmp / "cache"
        (cache / "skills" / "tool").mkdir(parents=True)
        (cache / "skills" / "tool" / "SKILL.md").write_text("new")
        root = self.tmp / "claude" / "skills"
        (root / "tool-i").mkdir(parents=True)
        (root / "tool-i" / "SKILL.md").write_text("old")
        sources = install.inventory_sources([inventory_entry(folder="tool")])
        with mock.patch("install.SOURCES", sources), \
             mock.patch("install.target_root", return_value=root), \
             mock.patch("install.source_cache_dir", return_value=cache):
            tag = install.item_tag("community", "tool-i", ["claude"], {})
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


class TestUninstall(TempDirTest):
    def test_removes_copy_and_symlink(self):
        dest = self.tmp / "skills"
        src = self.make_skill("repo", name="roj-explain-logic")
        dest.mkdir()
        (dest / "roj-explain-logic").symlink_to(src)
        (dest / "code-tour").mkdir()
        results = install.uninstall_skills(
            ["roj-explain-logic", "code-tour"], "claude", dest,
            {"roj-explain-logic", "code-tour"}, force=False, dry_run=False)
        self.assertEqual(results,
                         [("claude", "roj-explain-logic", "removed (symlink)"),
                          ("claude", "code-tour", "removed")])
        self.assertFalse((dest / "roj-explain-logic").is_symlink())
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


class TestResolveRepo(TempDirTest):
    def test_missing_dir_exits(self):
        with self.assertRaises(SystemExit):
            install.resolve_repo(self.tmp / "nope")

    def test_file_path_exits(self):
        f = self.tmp / "a-file"
        f.write_text("x")
        with self.assertRaises(SystemExit):
            install.resolve_repo(f)

    def test_git_dir_does_not_warn(self):
        (self.tmp / ".git").mkdir()
        with mock.patch("install.warn") as warned:
            self.assertEqual(install.resolve_repo(self.tmp),
                             self.tmp.resolve())
        warned.assert_not_called()

    def test_git_file_worktree_does_not_warn(self):
        (self.tmp / ".git").write_text("gitdir: /elsewhere")
        with mock.patch("install.warn") as warned:
            install.resolve_repo(self.tmp)
        warned.assert_not_called()

    def test_plain_dir_warns_but_returns_path(self):
        with mock.patch("install.warn") as warned:
            self.assertEqual(install.resolve_repo(self.tmp),
                             self.tmp.resolve())
        warned.assert_called_once()


class TestTargetRootRepo(TempDirTest):
    def test_repo_root_is_dot_github_skills(self):
        self.assertEqual(install.target_root("repo", repo=self.tmp),
                         self.tmp / ".github" / "skills")

    def test_home_targets_unchanged(self):
        with mock.patch("install.Path.home", return_value=self.tmp):
            self.assertEqual(install.target_root("copilot"),
                             self.tmp / ".copilot" / "skills")
            self.assertEqual(install.target_root("claude"),
                             self.tmp / ".claude" / "skills")


class TestPickTargetsRepo(TempDirTest):
    def test_repo_only_skips_menu(self):
        # No input mock: a prompt here would raise OSError, not hang.
        self.assertEqual(install.pick_targets(None, repo=self.tmp), ["repo"])

    def test_repo_appended_to_explicit_target(self):
        self.assertEqual(install.pick_targets("copilot", repo=self.tmp),
                         ["copilot", "repo"])
        self.assertEqual(install.pick_targets("both", repo=self.tmp),
                         ["copilot", "claude", "repo"])


class TestStatusTargets(TempDirTest):
    def test_table(self):
        cases = [
            ((None, None), ["copilot", "claude"]),
            ((None, self.tmp), ["repo"]),
            (("both", self.tmp), ["copilot", "claude", "repo"]),
            (("claude", None), ["claude"]),
            (("copilot", self.tmp), ["copilot", "repo"]),
        ]
        for (target, repo), expected in cases:
            with self.subTest(target=target, repo=bool(repo)):
                self.assertEqual(install.status_targets(target, repo),
                                 expected)


class TestPromptsDirFor(TempDirTest):
    def test_repo_dir(self):
        self.assertEqual(install.prompts_dir_for("repo", repo=self.tmp),
                         self.tmp / ".github" / "prompts")

    def test_copilot_delegates_to_vscode_dir(self):
        with mock.patch("install.vscode_prompts_dir",
                        return_value=self.tmp / "prompts"):
            self.assertEqual(install.prompts_dir_for("copilot"),
                             self.tmp / "prompts")

    def test_claude_is_none(self):
        self.assertIsNone(install.prompts_dir_for("claude"))


class TestRemoveLegacy(TempDirTest):
    def setUp(self):
        super().setUp()
        self.skills = self.tmp / "skills"
        (self.skills / "roj-explain-logic").mkdir(parents=True)
        self.dest = self.tmp / "dest"
        self.dest.mkdir()

    def patched(self):
        return mock.patch.multiple("install", SKILLS_SRC=self.skills,
                                   RETIRED_PROMPTS=("roj-create-sb",))

    def run_remove(self, target="copilot", dry_run=False):
        with self.patched():
            return install.remove_legacy(target, self.dest, dry_run)

    def test_legacy_names(self):
        with self.patched():
            self.assertEqual(install.legacy_names(), ["explain-logic"])

    def test_removes_copy_declaring_old_name(self):
        old = self.dest / "explain-logic"
        old.mkdir()
        (old / "SKILL.md").write_text("---\nname: explain-logic\n---\n")
        results = self.run_remove()
        self.assertEqual(results, [("copilot", "explain-logic",
                                    "removed (renamed to roj-explain-logic)")])
        self.assertFalse(old.exists())

    def test_removes_dangling_symlink(self):
        link = self.dest / "explain-logic"
        link.symlink_to(self.tmp / "gone")
        self.run_remove(target="claude")
        self.assertFalse(link.is_symlink())

    def test_keeps_foreign_skill_of_same_name(self):
        other = self.dest / "explain-logic"
        other.mkdir()
        (other / "SKILL.md").write_text("---\nname: something-else\n---\n")
        self.assertEqual(self.run_remove(), [])
        self.assertTrue(other.exists())

    def test_dry_run_keeps_everything(self):
        old = self.dest / "explain-logic"
        old.mkdir()
        (old / "SKILL.md").write_text("name: explain-logic\n")
        self.assertEqual(len(self.run_remove(dry_run=True)), 1)
        self.assertTrue(old.exists())


class TestRetirePrompts(TempDirTest):
    """Everything earlier installs generated from prompts/ goes; real
    skills and hand-written files of the same name stay."""

    GEN = "x\n<!-- Generated from prompts/roj-create-sb.prompt.md -->\n"

    def setUp(self):
        super().setUp()
        self.dest = self.tmp / "skills"
        self.dest.mkdir()
        self.cmds = self.tmp / "commands"
        self.cmds.mkdir()
        self.pdir = self.tmp / "Code" / "User" / "prompts"
        self.pdir.mkdir(parents=True)

    def retire(self, target="copilot", dry_run=False, repo=None):
        with mock.patch.multiple(
                "install", RETIRED_PROMPTS=("roj-create-sb",
                                            "roj-code-review-pr"),
                claude_commands_dir=mock.Mock(return_value=self.cmds),
                vscode_prompts_dir=mock.Mock(return_value=self.pdir)):
            return install.retire_prompts(target, self.dest, dry_run,
                                          repo=repo)

    def test_removes_generated_skill_dir(self):
        gen = self.dest / "roj-create-sb"
        gen.mkdir()
        (gen / "SKILL.md").write_text(self.GEN)
        results = self.retire()
        self.assertEqual([r[1] for r in results], ["roj-create-sb"])
        self.assertFalse(gen.exists())

    def test_keeps_real_skill_of_a_retired_name(self):
        real = self.dest / "roj-code-review-pr"
        real.mkdir()
        (real / "SKILL.md").write_text("---\nname: roj-code-review-pr\n---\n")
        self.assertEqual(self.retire(), [])
        self.assertTrue(real.exists())

    def test_keeps_symlinked_skill(self):
        src = self.make_skill("repo", name="roj-create-sb", content=self.GEN)
        (self.dest / "roj-create-sb").symlink_to(src)
        self.assertEqual(self.retire(), [])

    def test_removes_generated_backup_dir(self):
        bak = self.dest / "roj-create-sb.bak"
        bak.mkdir()
        (bak / "SKILL.md").write_text(self.GEN)
        results = self.retire()
        self.assertEqual([r[1] for r in results], ["roj-create-sb.bak"])
        self.assertFalse(bak.exists())

    def test_keeps_symlinked_claude_command(self):
        target = self.tmp / "dotfiles-cmd.md"
        target.write_text(self.GEN)
        (self.cmds / "roj-create-sb.md").symlink_to(target)
        self.assertEqual(self.retire(target="claude"), [])
        self.assertTrue((self.cmds / "roj-create-sb.md").is_symlink())
        self.assertTrue(target.is_file())

    def test_keeps_symlinked_prompt_file(self):
        target = self.tmp / "mine.prompt.md"
        target.write_text("user's own")
        (self.pdir / "roj-create-sb.prompt.md").symlink_to(target)
        self.assertEqual(self.retire(), [])
        self.assertTrue((self.pdir / "roj-create-sb.prompt.md").is_symlink())

    def test_removes_generated_claude_commands_new_and_legacy(self):
        (self.cmds / "roj-create-sb.md").write_text(self.GEN)
        (self.cmds / "create-sb.md").write_text(self.GEN)
        results = self.retire(target="claude")
        self.assertEqual(sorted(r[1] for r in results),
                         ["command:create-sb", "command:roj-create-sb"])
        self.assertEqual(list(self.cmds.iterdir()), [])

    def test_keeps_hand_written_claude_command(self):
        (self.cmds / "create-sb.md").write_text("my own command")
        self.assertEqual(self.retire(target="claude"), [])

    def test_commands_untouched_for_copilot(self):
        (self.cmds / "roj-create-sb.md").write_text(self.GEN)
        self.retire(target="copilot")
        self.assertTrue((self.cmds / "roj-create-sb.md").is_file())

    def test_removes_prompt_files_and_empty_dir(self):
        (self.pdir / "roj-create-sb.prompt.md").write_text("old")
        (self.pdir / "create-sb.prompt.md").write_text("older")
        results = self.retire()
        self.assertEqual(sorted(r[1] for r in results),
                         ["prompt:create-sb", "prompt:roj-create-sb"])
        self.assertFalse(self.pdir.exists())

    def test_leaves_foreign_prompt_files(self):
        (self.pdir / "roj-create-sb.prompt.md").write_text("old")
        (self.pdir / "mine.prompt.md").write_text("user's own")
        self.retire()
        self.assertTrue((self.pdir / "mine.prompt.md").is_file())

    def test_repo_scope_uses_dot_github_prompts(self):
        repo = self.tmp / "work-repo"
        pdir = repo / ".github" / "prompts"
        pdir.mkdir(parents=True)
        (pdir / "roj-create-sb.prompt.md").write_text("sb body")
        results = self.retire(target="repo", repo=repo)
        self.assertEqual([r[:2] for r in results],
                         [("repo", "prompt:roj-create-sb")])
        self.assertFalse(pdir.exists())

    def test_dry_run_keeps_everything(self):
        gen = self.dest / "roj-create-sb"
        gen.mkdir()
        (gen / "SKILL.md").write_text(self.GEN)
        (self.pdir / "roj-create-sb.prompt.md").write_text("old")
        self.assertEqual(len(self.retire(dry_run=True)), 2)
        self.assertTrue(gen.exists())
        self.assertTrue((self.pdir / "roj-create-sb.prompt.md").is_file())

    def test_no_vscode_dir(self):
        with mock.patch("install.vscode_prompts_dir", return_value=None):
            self.assertEqual(install.retire_prompts("copilot", self.dest,
                                                    False), [])

    def test_status_classifies_generated_dir_as_stale(self):
        gen = self.dest / "roj-create-sb"
        gen.mkdir()
        (gen / "SKILL.md").write_text(self.GEN)
        rows, warnings = install.gather_status("copilot", self.dest, set(),
                                               {})
        self.assertEqual(rows, [("roj-create-sb", "retired prompt (stale)",
                                 "copy")])
        self.assertTrue(any("re-run install.py" in w for w in warnings))


class TestCommunityRepoPolicy(TestInstallCommunityForTarget):
    def test_repo_skipped_without_the_personal_scope_note(self):
        dest = self.tmp / "dest"
        with mock.patch("install.SOURCES", self.fake_sources()):
            results = install.install_community_for_target(
                "repo", dest, {"cop-only"}, dry_run=False)
        self.assertEqual(results,
                         [("repo", "cop-only", "skipped (not for repo)")])

    def test_repo_installs_when_eligible(self):
        sources = self.fake_sources()
        sources[0]["skills"]["tool-x"]["targets"] = install.ANY
        dest = self.tmp / "dest"
        with mock.patch("install.SOURCES", sources):
            results = install.install_community_for_target(
                "repo", dest, {"tool-x"}, dry_run=False)
        self.assertEqual(results, [("repo", "tool-x", "installed")])
        self.assertTrue((dest / "tool-x" / "SKILL.md").is_file())


class ExternalTest(TempDirTest):
    """Externals delegate to a CLI, so every test here fakes both the CLI
    lookup and the subprocess call — nothing may reach a real install."""

    def fake_external(self, **overrides):
        ext = {
            "name": "tool-y", "package": "tool-y-pkg", "cli": "tool-y",
            "targets": ("copilot", "claude", "repo"), "default": True,
            "doc": "does things",
            "install": {"claude": ["install"],
                        "copilot": ["vscode", "install"]},
            "uninstall": {"claude": ["claude", "uninstall"],
                          "copilot": ["vscode", "uninstall"]},
            "repo_cwd": True,
            "version_file": ".tool_y_version",
        }
        ext.update(overrides)
        return ext

    def record_runs(self):
        """Patch run_cli to record argv + cwd instead of running anything."""
        calls = []

        def fake(argv, cwd):
            calls.append((list(argv), str(cwd)))
            return True

        return calls, mock.patch("install.run_cli", side_effect=fake)


class TestFindCli(ExternalTest):
    def test_prefers_path(self):
        with mock.patch("install.shutil.which", return_value="/usr/bin/tool-y"):
            self.assertEqual(install.find_cli("tool-y"), "/usr/bin/tool-y")

    def test_falls_back_to_user_bin(self):
        bin_dir = self.tmp / "bin"
        bin_dir.mkdir()
        shim = bin_dir / "tool-y"
        shim.write_text("#!/bin/sh\n")
        with mock.patch("install.shutil.which", return_value=None), \
                mock.patch("install.USER_BIN_DIRS", (bin_dir,)):
            self.assertEqual(install.find_cli("tool-y"), str(shim))

    def test_missing_returns_none(self):
        with mock.patch("install.shutil.which", return_value=None), \
                mock.patch("install.USER_BIN_DIRS", (self.tmp / "nope",)):
            self.assertIsNone(install.find_cli("tool-y"))


class TestBootstrapCli(ExternalTest):
    def test_present_cli_is_not_reinstalled(self):
        with mock.patch("install.find_cli", return_value="/bin/tool-y") as f, \
                mock.patch("install.subprocess.run") as run:
            path = install.bootstrap_cli(self.fake_external(), dry_run=False)
        self.assertEqual(path, "/bin/tool-y")
        run.assert_not_called()
        f.assert_called_once_with("tool-y")

    def test_dry_run_never_installs(self):
        with mock.patch("install.find_cli", return_value=None), \
                mock.patch("install.subprocess.run") as run:
            self.assertIsNone(install.bootstrap_cli(self.fake_external(),
                                                    dry_run=True))
        run.assert_not_called()

    def test_installs_with_uv_then_finds_shim(self):
        with mock.patch("install.find_cli",
                        side_effect=[None, "/home/x/.local/bin/tool-y"]), \
                mock.patch("install.shutil.which",
                           side_effect=lambda c: "/bin/uv" if c == "uv"
                           else None), \
                mock.patch("install.subprocess.run") as run:
            path = install.bootstrap_cli(self.fake_external(), dry_run=False)
        self.assertEqual(path, "/home/x/.local/bin/tool-y")
        run.assert_called_once_with(["uv", "tool", "install", "tool-y-pkg"],
                                    check=True)

    def test_falls_back_to_pipx_when_uv_absent(self):
        with mock.patch("install.find_cli", side_effect=[None, "/bin/tool-y"]), \
                mock.patch("install.shutil.which",
                           side_effect=lambda c: "/bin/pipx" if c == "pipx"
                           else None), \
                mock.patch("install.subprocess.run") as run:
            install.bootstrap_cli(self.fake_external(), dry_run=False)
        run.assert_called_once_with(["pipx", "install", "tool-y-pkg"],
                                    check=True)

    def test_falls_back_to_pip_when_uv_and_pipx_absent(self):
        # pip is never looked up on PATH — it runs as `<this python> -m pip`,
        # which is the one interpreter guaranteed to exist here.
        pip = [sys.executable, "-m", "pip", "install", "--user"]
        with mock.patch("install.find_cli", side_effect=[None, "/bin/tool-y"]), \
                mock.patch("install.shutil.which", return_value=None), \
                mock.patch("install.BOOTSTRAP_CMDS",
                           (["uv", "tool", "install"], pip)), \
                mock.patch("install.subprocess.run") as run:
            path = install.bootstrap_cli(self.fake_external(), dry_run=False)
        self.assertEqual(path, "/bin/tool-y")
        run.assert_called_once_with([*pip, "tool-y-pkg"], check=True)

    def test_no_installer_available_returns_none(self):
        with mock.patch("install.find_cli", return_value=None), \
                mock.patch("install.shutil.which", return_value=None), \
                mock.patch("install.BOOTSTRAP_CMDS",
                           (["uv", "tool", "install"],)), \
                mock.patch("install.subprocess.run") as run:
            self.assertIsNone(install.bootstrap_cli(self.fake_external(),
                                                    dry_run=False))
        run.assert_not_called()



class TestCliVersion(ExternalTest):
    def result(self, stdout="", stderr=""):
        return subprocess.CompletedProcess([], 0, stdout, stderr)

    def test_parses_trailing_version_from_stdout(self):
        with mock.patch("install.subprocess.run",
                        return_value=self.result("tool-y 1.2.3\n")):
            self.assertEqual(install.cli_version("/bin/tool-y"), "1.2.3")

    def test_falls_back_to_stderr(self):
        with mock.patch("install.subprocess.run",
                        return_value=self.result("", "tool-y 4.5.6")):
            self.assertEqual(install.cli_version("/bin/tool-y"), "4.5.6")

    def test_missing_exe_is_none(self):
        self.assertIsNone(install.cli_version(None))
        with mock.patch("install.subprocess.run", side_effect=OSError):
            self.assertIsNone(install.cli_version("/bin/tool-y"))


class TestUpgradeCli(ExternalTest):
    def versions(self, *values):
        return mock.patch("install.cli_version", side_effect=list(values))

    def test_reports_the_version_change(self):
        with self.versions("1.0.0", "2.0.0"), \
                mock.patch("install.shutil.which", return_value="/bin/uv"), \
                mock.patch("install.find_cli", return_value="/bin/tool-y"), \
                mock.patch("install.subprocess.run") as run:
            status = install.upgrade_cli(self.fake_external(), "/bin/tool-y",
                                         dry_run=False)
        self.assertEqual(status, "upgraded (1.0.0 -> 2.0.0)")
        run.assert_called_once_with(["uv", "tool", "upgrade", "tool-y-pkg"],
                                    check=True)

    def test_same_version_reads_as_already_latest(self):
        with self.versions("2.0.0", "2.0.0"), \
                mock.patch("install.shutil.which", return_value="/bin/uv"), \
                mock.patch("install.find_cli", return_value="/bin/tool-y"), \
                mock.patch("install.subprocess.run"):
            status = install.upgrade_cli(self.fake_external(), "/bin/tool-y",
                                         dry_run=False)
        self.assertEqual(status, "already latest (2.0.0)")

    def test_falls_through_to_a_manager_that_owns_the_package(self):
        # uv is present but did not install it, so `uv tool upgrade` fails and
        # the next manager gets a turn.
        calls = []

        def run(argv, check=False):
            calls.append(argv)
            if argv[0] == "uv":
                raise subprocess.CalledProcessError(1, argv)
            return subprocess.CompletedProcess(argv, 0)

        with self.versions("1.0.0", "1.1.0"), \
                mock.patch("install.shutil.which", return_value="/bin/x"), \
                mock.patch("install.find_cli", return_value="/bin/tool-y"), \
                mock.patch("install.subprocess.run", side_effect=run):
            status = install.upgrade_cli(self.fake_external(), "/bin/tool-y",
                                         dry_run=False)
        self.assertEqual([c[0] for c in calls], ["uv", "pipx"])
        self.assertEqual(status, "upgraded (1.0.0 -> 1.1.0)")

    def test_no_manager_available(self):
        with mock.patch("install.cli_version", return_value="1.0.0"), \
                mock.patch("install.shutil.which", return_value=None), \
                mock.patch("install.UPGRADE_CMDS",
                           (["uv", "tool", "upgrade"],)), \
                mock.patch("install.subprocess.run") as run:
            status = install.upgrade_cli(self.fake_external(), "/bin/tool-y",
                                         dry_run=False)
        run.assert_not_called()
        self.assertEqual(status, "upgrade unavailable")

    def test_dry_run_plans_without_running(self):
        with mock.patch("install.subprocess.run") as run:
            status = install.upgrade_cli(self.fake_external(), "/bin/tool-y",
                                         dry_run=True)
        run.assert_not_called()
        self.assertEqual(status, "dry-run: would upgrade tool-y-pkg")

class TestCliPathHint(ExternalTest):
    def test_hint_when_found_but_not_callable_by_name(self):
        with mock.patch("install.find_cli",
                        return_value="/home/x/.local/bin/tool-y"), \
                mock.patch("install.shutil.which", return_value=None):
            hint = install.cli_path_hint(self.fake_external())
        self.assertIn("/home/x/.local/bin", hint)
        self.assertIn("~/.bashrc", hint)

    def test_no_hint_when_on_path(self):
        with mock.patch("install.find_cli", return_value="/usr/bin/tool-y"), \
                mock.patch("install.shutil.which",
                           return_value="/usr/bin/tool-y"):
            self.assertIsNone(install.cli_path_hint(self.fake_external()))

    def test_no_hint_when_not_installed(self):
        with mock.patch("install.find_cli", return_value=None), \
                mock.patch("install.shutil.which", return_value=None):
            self.assertIsNone(install.cli_path_hint(self.fake_external()))

    def test_summary_repeats_the_hint_so_it_cannot_scroll_away(self):
        results = [("claude", "graphify", "installed (by CLI)")]
        with mock.patch("install.cli_path_hint",
                        return_value="tool-y is installed at X"), \
                mock.patch("install.warn") as warned:
            install.print_summary(results, ["claude"], dry_run=False)
        self.assertTrue(any("installed at X" in c.args[0]
                            for c in warned.call_args_list))

    def test_status_reports_an_off_path_cli(self):
        dest = self.tmp / "claude-skills"
        (dest / "tool-y").mkdir(parents=True)
        with mock.patch("install.EXTERNALS", [self.fake_external()]), \
                mock.patch("install.find_cli", return_value="/opt/bin/tool-y"), \
                mock.patch("install.shutil.which", return_value=None):
            _, warnings = install.gather_status("claude", dest, set(), {})
        self.assertTrue(any("/opt/bin" in w for w in warnings))



class TestUserScriptDirs(ExternalTest):
    def test_includes_local_bin_and_the_user_scheme(self):
        dirs = install.user_script_dirs()
        self.assertIn(Path.home() / ".local" / "bin", dirs)
        self.assertEqual(len(set(dirs)), len(dirs))

    def test_pip_cmd_drops_user_flag_inside_a_venv(self):
        with mock.patch.object(sys, "prefix", "/venv"), \
                mock.patch.object(sys, "base_prefix", "/usr"):
            self.assertNotIn("--user", install.pip_install_cmd())
        with mock.patch.object(sys, "prefix", "/usr"), \
                mock.patch.object(sys, "base_prefix", "/usr"):
            self.assertIn("--user", install.pip_install_cmd())


class TestInstallExternalForTarget(ExternalTest):
    def test_claude_runs_cli_outside_the_cwd(self):
        calls, patched = self.record_runs()
        with patched:
            results = install.install_external_for_target(
                "claude", self.fake_external(), "/bin/tool-y", None,
                dry_run=False)
        self.assertEqual(results, [("claude", "tool-y", "installed (by CLI)")])
        argv, cwd = calls[0]
        self.assertEqual(argv, ["/bin/tool-y", "install"])
        self.assertNotEqual(cwd, str(Path.cwd()))

    def test_copilot_uses_the_vscode_body(self):
        calls, patched = self.record_runs()
        with patched:
            install.install_external_for_target(
                "copilot", self.fake_external(), "/bin/tool-y", None,
                dry_run=False)
        self.assertEqual(calls[0][0],
                         ["/bin/tool-y", "vscode", "install"])

    def test_repo_runs_in_repo_then_copies_personal_skill(self):
        home_skill = self.tmp / "copilot-skills" / "tool-y"
        home_skill.mkdir(parents=True)
        (home_skill / "SKILL.md").write_text("body")
        repo = self.tmp / "proj"
        (repo / ".github" / "skills").mkdir(parents=True)
        calls, patched = self.record_runs()
        with patched, mock.patch(
                "install.target_root",
                side_effect=lambda t, r=None: (
                    home_skill.parent if t == "copilot"
                    else repo / ".github" / "skills")):
            results = install.install_external_for_target(
                "repo", self.fake_external(), "/bin/tool-y", repo,
                dry_run=False)
        self.assertEqual(calls[0][1], str(repo))
        self.assertEqual(results, [("repo", "tool-y", "installed")])
        self.assertTrue(
            (repo / ".github" / "skills" / "tool-y" / "SKILL.md").is_file())

    def test_repo_reports_failure_when_personal_skill_missing(self):
        repo = self.tmp / "proj"
        repo.mkdir()
        calls, patched = self.record_runs()
        with patched, mock.patch("install.target_root",
                                 side_effect=lambda t, r=None:
                                 self.tmp / "ghost"):
            results = install.install_external_for_target(
                "repo", self.fake_external(), "/bin/tool-y", repo,
                dry_run=False)
        self.assertIn("failed", results[0][2])

    def test_dry_run_plans_without_running(self):
        with mock.patch("install.run_cli") as run:
            results = install.install_external_for_target(
                "claude", self.fake_external(), None, None, dry_run=True)
        run.assert_not_called()
        self.assertEqual(results,
                         [("claude", "tool-y",
                           "dry-run: would run tool-y install")])

    def test_missing_cli_skips_instead_of_failing(self):
        with mock.patch("install.run_cli") as run:
            results = install.install_external_for_target(
                "claude", self.fake_external(), None, None, dry_run=False)
        run.assert_not_called()
        self.assertEqual(results,
                         [("claude", "tool-y", "skipped (CLI unavailable)")])

    def test_target_policy_respected(self):
        ext = self.fake_external(targets=("copilot",))
        with mock.patch("install.run_cli") as run:
            results = install.install_external_for_target(
                "claude", ext, "/bin/tool-y", None, dry_run=False)
        run.assert_not_called()
        self.assertEqual(results,
                         [("claude", "tool-y", "skipped (not for claude)")])


class TestExternalSkipAndRetry(ExternalTest):
    """Re-running a CLI's installer is skipped when the stamp already
    matches; on Windows a failed install is retried once."""

    def setUp(self):
        super().setUp()
        self.root = self.tmp / "copilot-skills"
        self.skill = self.root / "tool-y"
        out = contextlib.ExitStack()
        out.enter_context(contextlib.redirect_stdout(io.StringIO()))
        self.err = out.enter_context(contextlib.redirect_stderr(io.StringIO()))
        self.addCleanup(out.close)

    def install(self, version="1.2.3", runs=(True,), windows=False):
        outcomes = list(runs)
        calls = []

        def fake(argv, cwd):
            calls.append(argv)
            return outcomes.pop(0)

        with mock.patch("install.target_root", return_value=self.root), \
             mock.patch("install.cli_version", return_value=version), \
             mock.patch("install.run_cli", side_effect=fake), \
             mock.patch("install.IS_WINDOWS", windows), \
             mock.patch("install.time.sleep") as sleep:
            results = install.install_external_for_target(
                "copilot", self.fake_external(), "/bin/tool-y", None,
                dry_run=False)
        return results, calls, sleep

    def stamp(self, version):
        self.skill.mkdir(parents=True)
        (self.skill / "SKILL.md").write_text("body")
        (self.skill / ".tool_y_version").write_text(version + "\n")

    def test_skips_when_stamp_matches_the_cli(self):
        self.stamp("1.2.3")
        results, calls, _ = self.install()
        self.assertEqual(results, [("copilot", "tool-y", "up to date")])
        self.assertEqual(calls, [])

    def test_half_finished_install_is_not_current(self):
        # The WinError 5 failure: references/ deleted, rename never done,
        # stamp left at the current version.
        self.stamp("1.2.3")
        (self.skill / "SKILL.md").write_text(
            "See references/github-and-merge.md")
        _, calls, _ = self.install()
        self.assertEqual(len(calls), 1)

    def test_leftover_staging_dir_is_not_current(self):
        self.stamp("1.2.3")
        (self.skill / "references.tmp").mkdir()
        _, calls, _ = self.install()
        self.assertEqual(len(calls), 1)

    def test_complete_install_with_references_is_current(self):
        self.stamp("1.2.3")
        (self.skill / "SKILL.md").write_text(
            "See references/github-and-merge.md")
        (self.skill / "references").mkdir()
        (self.skill / "references" / "github-and-merge.md").write_text("x")
        results, calls, _ = self.install()
        self.assertEqual(calls, [])
        self.assertEqual(results[0][2], "up to date")

    def test_runs_when_the_cli_is_newer(self):
        self.stamp("1.2.2")
        results, calls, _ = self.install()
        self.assertEqual(len(calls), 1)
        self.assertEqual(results[0][2], "installed (by CLI)")

    def test_runs_when_the_version_is_unknown(self):
        self.stamp("1.2.3")
        _, calls, _ = self.install(version=None)
        self.assertEqual(len(calls), 1)

    def test_windows_retries_once_and_clears_staging(self):
        (self.skill / "references.tmp").mkdir(parents=True)
        results, calls, sleep = self.install(runs=(False, True),
                                             windows=True)
        self.assertEqual(len(calls), 2)
        sleep.assert_called_once()
        self.assertFalse((self.skill / "references.tmp").exists())
        self.assertEqual(results[0][2], "installed (by CLI)")

    def test_windows_second_failure_reports_with_a_hint(self):
        results, calls, _ = self.install(runs=(False, False), windows=True)
        self.assertEqual(len(calls), 2)
        self.assertEqual(results[0][2], "failed")
        self.assertIn("close VS Code and JetBrains", self.err.getvalue())

    def test_repo_scope_reinstalls_when_a_repo_file_is_missing(self):
        repo = self.tmp / "proj"
        self.stamp("1.2.3")
        ext = self.fake_external(
            repo_files=(".github/copilot-instructions.md",))
        calls = []

        def fake(argv, cwd):
            calls.append(argv)
            return True

        def run():
            with mock.patch("install.target_root", return_value=self.root), \
                 mock.patch("install.cli_version", return_value="1.2.3"), \
                 mock.patch("install.run_cli", side_effect=fake):
                return install.install_external_for_target(
                    "repo", ext, "/bin/tool-y", repo, dry_run=False)

        run()
        self.assertEqual(len(calls), 1)
        (repo / ".github").mkdir(parents=True)
        (repo / ".github" / "copilot-instructions.md").write_text("x")
        results = run()
        self.assertEqual(len(calls), 1)
        self.assertEqual(results, [("repo", "tool-y", "up to date")])

    def test_no_retry_off_windows(self):
        results, calls, sleep = self.install(runs=(False,), windows=False)
        self.assertEqual(len(calls), 1)
        sleep.assert_not_called()
        self.assertEqual(results[0][2], "failed")


class TestInstallExternalsForTarget(ExternalTest):
    def test_only_selected_externals_run(self):
        ext = self.fake_external()
        ext["_exe"] = "/bin/tool-y"
        calls, patched = self.record_runs()
        with patched, mock.patch("install.EXTERNALS", [ext]):
            selected = install.install_externals_for_target(
                "claude", {"tool-y"}, None, dry_run=False)
            skipped = install.install_externals_for_target(
                "claude", set(), None, dry_run=False)
        self.assertEqual(len(calls), 1)
        self.assertEqual(len(selected), 1)
        self.assertEqual(skipped, [])


class TestUninstallExternals(ExternalTest):
    def test_delegates_to_cli_per_target(self):
        ext = self.fake_external()
        calls, patched = self.record_runs()
        with patched, mock.patch("install.EXTERNALS", [ext]), \
                mock.patch("install.find_cli", return_value="/bin/tool-y"):
            results = install.uninstall_externals(["tool-y"], "copilot",
                                                  dry_run=False)
        self.assertEqual(calls[0][0],
                         ["/bin/tool-y", "vscode", "uninstall"])
        self.assertEqual(results,
                         [("copilot", "tool-y", "removed (by CLI)")])

    def test_repo_scope_left_to_uninstall_skills(self):
        with mock.patch("install.EXTERNALS", [self.fake_external()]), \
                mock.patch("install.run_cli") as run:
            self.assertEqual(
                install.uninstall_externals(["tool-y"], "repo", False), [])
        run.assert_not_called()

    def test_without_cli_removes_the_directory(self):
        dest_root = self.tmp / "skills"
        (dest_root / "tool-y").mkdir(parents=True)
        with mock.patch("install.EXTERNALS", [self.fake_external()]), \
                mock.patch("install.find_cli", return_value=None), \
                mock.patch("install.target_root",
                           side_effect=lambda t, r=None: dest_root):
            results = install.uninstall_externals(["tool-y"], "claude", False)
        self.assertEqual(results,
                         [("claude", "tool-y", "removed (no CLI — dir only)")])
        self.assertFalse((dest_root / "tool-y").exists())

    def test_dry_run_plans_without_running(self):
        with mock.patch("install.EXTERNALS", [self.fake_external()]), \
                mock.patch("install.find_cli", return_value="/bin/tool-y"), \
                mock.patch("install.run_cli") as run:
            results = install.uninstall_externals(["tool-y"], "claude", True)
        run.assert_not_called()
        self.assertEqual(
            results,
            [("claude", "tool-y",
              "dry-run: would run tool-y claude uninstall")])


class TestExternalStatus(ExternalTest):
    def test_classified_with_version_and_missing_cli_warning(self):
        dest = self.tmp / "claude-skills"
        (dest / "tool-y").mkdir(parents=True)
        (dest / "tool-y" / ".tool_y_version").write_text("9.9.9\n")
        with mock.patch("install.EXTERNALS", [self.fake_external()]), \
                mock.patch("install.find_cli", return_value=None):
            rows, warnings = install.gather_status("claude", dest, set(), {})
        self.assertEqual(rows, [("tool-y", "external (tool-y-pkg 9.9.9)",
                                 "copy")])
        self.assertTrue(any("CLI is missing" in w for w in warnings))

    def test_no_warning_when_cli_present(self):
        dest = self.tmp / "claude-skills"
        (dest / "tool-y").mkdir(parents=True)
        with mock.patch("install.EXTERNALS", [self.fake_external()]), \
                mock.patch("install.find_cli", return_value="/bin/tool-y"), \
                mock.patch("install.shutil.which",
                           return_value="/bin/tool-y"):
            rows, warnings = install.gather_status("claude", dest, set(), {})
        self.assertEqual(rows, [("tool-y", "external (tool-y-pkg)", "copy")])
        self.assertEqual(warnings, [])


class TestExternalRegistry(unittest.TestCase):
    def test_graphify_is_a_default_external_for_every_target(self):
        ext = install.externals()["graphify"]
        self.assertIn("graphify", install.default_external_names())
        self.assertEqual(set(ext["targets"]), {"copilot", "claude", "repo"})

    def test_copilot_installs_the_vscode_skill_body(self):
        # Both bodies write ~/.copilot/skills/graphify/SKILL.md; only the
        # vscode one works without a parallel Agent tool (JetBrains, VS Code).
        self.assertEqual(install.externals()["graphify"]["install"]["copilot"],
                         ["vscode", "install"])

    def test_externals_appear_in_the_picker(self):
        items = install.build_items([])
        self.assertIn(("external", "graphify"), items)


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

    def test_custom_skills_never_require_each_other(self):
        """Each skill must also install alone via `npx skills add -s`;
        shared files are copied in by tools/sync_shared.py instead."""
        custom = install.custom_skill_names()
        for skill, deps in install.REQUIRES.items():
            with self.subTest(skill=skill):
                self.assertFalse(set(deps) & custom)


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
        (self.tmp / "code-tour").mkdir()
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

    def test_requirement_not_installed_here_is_silent(self):
        (self.tmp / "needs-dep").mkdir()
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


class MainHarness(TempDirTest):
    """Runs install.main() against a temp skills dir and temp targets."""

    REQ = {"needs-dep": ("code-tour",)}

    def run_main(self, argv, fetch=None, extra_patches=()):
        skills = self.tmp / "skills"
        if not (skills / "needs-dep").exists():
            self.make_skill("skills", name="needs-dep")
        home = self.tmp / "home"

        def root(target, repo=None):
            return home / target

        if fetch is None:
            fetch = lambda source, dry_run, names=None: None

        out, err = io.StringIO(), io.StringIO()
        with contextlib.ExitStack() as stack:
            stack.enter_context(mock.patch("install.SKILLS_SRC", skills))
            stack.enter_context(mock.patch("install.REQUIRES", self.REQ))
            stack.enter_context(mock.patch("install.EXTERNALS", []))
            stack.enter_context(mock.patch("install.target_root",
                                           side_effect=root))
            stack.enter_context(mock.patch(
                "install.claude_commands_dir",
                return_value=self.tmp / "commands"))
            stack.enter_context(mock.patch("install.update_source_cache",
                                           side_effect=fetch))
            stack.enter_context(mock.patch("sys.argv",
                                           ["install.py", *argv]))
            stack.enter_context(mock.patch("sys.stdout", out))
            stack.enter_context(mock.patch("sys.stderr", err))
            for patch in extra_patches:
                stack.enter_context(patch)
            install.main()
        return out.getvalue(), err.getvalue()



class TestMainRequirements(MainHarness):
    """Through main(): requirements ride along with their skill, a run that
    cannot fetch them says so, and uninstalling one warns."""

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

    def test_flag_run_fetches_a_requirement(self):
        fetched = []

        def fetch(source, dry_run, names=None):
            fetched.append(names)
            return None

        extra = [mock.patch("install.default_community_names",
                            return_value=set())]
        out, _ = self.run_main(["--target", "claude"], fetch=fetch,
                               extra_patches=extra)
        self.assertTrue(any("code-tour" in (names or ())
                            for names in fetched))
        self.assertIn("code-tour (required by needs-dep)", out)

    def test_skill_flag_installs_only_the_named_skill(self):
        self.make_skill("skills", name="other")
        self.run_main(["--target", "claude", "--skill", "needs-dep",
                       "--skills-only"])
        claude = self.tmp / "home" / "claude"
        self.assertTrue((claude / "needs-dep").exists())
        self.assertFalse((claude / "other").exists())

    def test_skill_flag_pulls_requirements_but_no_defaults(self):
        fetched = []

        def fetch(source, dry_run, names=None):
            fetched.append(set(names or ()))
            return None

        out, _ = self.run_main(["--target", "claude", "--skill",
                                "needs-dep"], fetch=fetch)
        self.assertEqual(set().union(*fetched), {"code-tour"})
        self.assertIn("code-tour (required by needs-dep)", out)

    def test_skill_flag_rejects_unknown_names(self):
        with self.assertRaises(SystemExit) as cm:
            self.run_main(["--target", "claude", "--skill", "nope"])
        self.assertIn("unknown nope", str(cm.exception))

    def test_list_prints_custom_and_community(self):
        out, _ = self.run_main(["--list"])
        self.assertIn("needs-dep", out)
        self.assertIn("code-tour", out)
        self.assertIn("npx skills add", out)

    def test_interactive_run_fetches_a_requirement(self):
        fetched = []

        def fetch(source, dry_run, names=None):
            fetched.append(names)
            return None

        extra = [
            mock.patch("install.pick_targets", return_value=["claude"]),
            mock.patch("install.pick_items",
                       return_value=[("skill", "needs-dep")]),
            mock.patch("install.plugin_skills", return_value={}),
            mock.patch("install.item_tag", return_value=""),
        ]
        out, _ = self.run_main([], fetch=fetch, extra_patches=extra)
        self.assertTrue(any("code-tour" in (names or ())
                            for names in fetched))
        self.assertIn("code-tour (required by needs-dep)", out)


class TestExplainFeatureChangesSkill(unittest.TestCase):
    """The skill must load in every agent and its commands must run the same
    in bash, PowerShell and cmd — the JetBrains terminal on the Windows VDI
    may be any of them."""

    SKILL = install.SKILLS_SRC / "roj-explain-feature-changes"
    FILES = [SKILL / "SKILL.md", SKILL / "references" / "tracing.md"]

    def snippets(self, text):
        fenced = re.findall(r"```[^\n]*\n(.*?)```", text, re.S)
        lines = [line.strip() for block in fenced
                 for line in block.splitlines()]
        prose = re.sub(r"```.*?```", "", text, flags=re.S)
        spans = re.findall(r"`([^`\n]+)`", prose)
        return [s.strip() for s in lines + spans if s.strip()]

    def test_git_commands_are_shell_neutral(self):
        for f in self.FILES:
            for s in self.snippets(f.read_text(encoding="utf-8")):
                with self.subTest(file=f.name, snippet=s):
                    if s.startswith("git "):
                        self.assertNotIn("$(", s)
                        self.assertNotIn("|", s)
                    self.assertFalse(s.startswith(("grep ", "sed ", "awk ")))

    def test_no_custom_skill_is_named(self):
        others = install.custom_skill_names() - {"roj-explain-feature-changes"}
        for f in self.SKILL.rglob("*.md"):
            text = f.read_text(encoding="utf-8")
            for name in others:
                with self.subTest(file=f.name, skill=name):
                    self.assertNotIn(name, text)


SHA_A = "a" * 40
SHA_B = "b" * 40


def inventory_entry(**overrides):
    entry = {"source": "acme/skills", "skill": "tool-i", "ref": SHA_A,
             "targets": ["claude", "copilot"], "default": False}
    entry.update(overrides)
    return entry


class InventoryTest(TempDirTest):
    def write_inventory(self, *entries, raw=None):
        path = self.tmp / "skills-inventory.json"
        path.write_text(raw if raw is not None
                        else json.dumps({"skills": list(entries)}))
        return path

    def quiet(self):
        """Silence log/ok/warn for the duration of a test."""
        out = contextlib.ExitStack()
        out.enter_context(contextlib.redirect_stdout(io.StringIO()))
        out.enter_context(contextlib.redirect_stderr(io.StringIO()))
        self.addCleanup(out.close)


class TestLoadInventory(InventoryTest):
    def test_missing_file_is_empty(self):
        self.assertEqual(install.load_inventory(self.tmp / "none.json"), [])

    def test_valid_entry_loads(self):
        path = self.write_inventory(inventory_entry())
        self.assertEqual(install.load_inventory(path), [inventory_entry()])

    def test_optional_keys_accepted(self):
        path = self.write_inventory(
            inventory_entry(subdir=".agents/skills", folder="tool",
                            note="why"),
            inventory_entry(source="me/.dotfiles", skill="tool-j"))
        self.assertEqual(len(install.load_inventory(path)), 2)

    def test_rejects_malformed_files_and_entries(self):
        cases = {
            "not json": dict(raw="{"),
            "no skills list": dict(raw='{"other": []}'),
            "missing ref": dict(entries=[{k: v for k, v in
                                          inventory_entry().items()
                                          if k != "ref"}]),
            "unknown key": dict(entries=[inventory_entry(branch="main")]),
            "short ref": dict(entries=[inventory_entry(ref="abc1234")]),
            "bad source": dict(entries=[inventory_entry(source="acme")]),
            "dotdot source": dict(entries=[inventory_entry(source="../..")]),
            "dotdot subdir": dict(entries=[inventory_entry(subdir="a/../..")]),
            "nested folder": dict(entries=[inventory_entry(folder="a/b")]),
            "dotdot folder": dict(entries=[inventory_entry(folder="..")]),
            "number folder": dict(entries=[inventory_entry(folder=1)]),
            "number source": dict(entries=[inventory_entry(source=7)]),
            "bad skill": dict(entries=[inventory_entry(skill="Tool I")]),
            "bad target": dict(entries=[inventory_entry(targets=["vim"])]),
            "no targets": dict(entries=[inventory_entry(targets=[])]),
            "default str": dict(entries=[inventory_entry(default="yes")]),
            "duplicate": dict(entries=[inventory_entry(), inventory_entry()]),
        }
        for label, case in cases.items():
            with self.subTest(label):
                path = self.write_inventory(*case.get("entries", ()),
                                            raw=case.get("raw"))
                with self.assertRaises(install.InventoryError):
                    install.load_inventory(path)


class TestInventorySources(unittest.TestCase):
    def test_one_source_per_repo(self):
        sources = install.inventory_sources([
            inventory_entry(), inventory_entry(skill="tool-j", default=True),
            inventory_entry(source="other/repo", skill="tool-k",
                            ref=SHA_B, targets=["repo"])])
        self.assertEqual([s["label"] for s in sources],
                         ["acme/skills", "other/repo"])
        acme = sources[0]
        self.assertEqual(acme["url"], "https://github.com/acme/skills.git")
        self.assertEqual(acme["ref"], SHA_A)
        self.assertEqual(acme["cache"], "acme--skills")
        self.assertTrue(acme["inventory"])
        self.assertEqual(acme["skills"]["tool-j"],
                         {"targets": ("copilot", "claude"), "default": True})
        self.assertEqual(sources[1]["skills"]["tool-k"]["targets"], ("repo",))

    def test_folder_and_note_carried_into_meta(self):
        [source] = install.inventory_sources([inventory_entry(
            folder="tool", note="claude uses a plugin")])
        self.assertEqual(source["skills"]["tool-i"]["folder"], "tool")
        self.assertEqual(install.skill_folder(source, "tool-i"), "tool")

    def test_repo_entries_must_share_ref_and_subdir(self):
        for other in (dict(ref=SHA_B), dict(subdir=".agents/skills")):
            with self.subTest(other):
                with self.assertRaises(install.InventoryError):
                    install.inventory_sources([
                        inventory_entry(),
                        inventory_entry(skill="tool-j", **other)])

    def test_name_clash_rejected(self):
        sources = install.inventory_sources([inventory_entry()])
        with self.assertRaises(install.InventoryError):
            install.check_inventory_names(sources, {"tool-i"})
        install.check_inventory_names(sources, {"something-else"})


class TestRepoInventory(unittest.TestCase):
    """The checked-in skills-inventory.json."""

    def test_find_skills_registered_pinned_and_default(self):
        source, meta = install.registry()["find-skills"]
        self.assertEqual(source["label"], "vercel-labs/skills")
        self.assertRegex(source["ref"], r"^[0-9a-f]{40}$")
        self.assertTrue(meta["default"])
        self.assertEqual(set(meta["targets"]), {"claude", "copilot"})

    def test_every_inventory_skill_is_documented(self):
        doc = (install.REPO_ROOT / "docs" / "community-skills.md").read_text(
            encoding="utf-8")
        for entry in install.load_inventory():
            with self.subTest(entry["skill"]):
                self.assertIn(f"\n## {entry['skill']}\n", doc)


class TestSkillDependencies(unittest.TestCase):
    """Every outside skill a custom skill names must be installable: in
    skills-inventory.json, an external, another custom skill, or provided
    by a Claude plugin. A new chain to an unknown skill fails here, so it
    gets an inventory entry instead of silently relying on a manual
    install."""

    # Claude plugins (not skills.sh skills) that our skills chain to.
    PLUGIN_PROVIDED = {"systematic-debugging"}
    # Matches of the scanner below that are not skill names.
    NOT_SKILLS = {"code-review", "file:line", "git", "path:start-end",
                  "target", "yield"}

    SKILL_TABLE = re.compile(r"\|\s*Skill\s*\|")
    NAMED_SKILL = re.compile(
        r"(?<![\w>-])`?([a-z][a-z0-9]*(?:[-:][a-z0-9]+)+)`?\s+skill\b"
        r"|\bskill\s+`([a-z][a-z0-9:-]+)`")
    BACKTICKED = re.compile(r"`([a-z][a-z0-9]*(?:-[a-z0-9]+)+)`")
    # `<distro>-linux-triage`: one installable skill per placeholder value.
    TEMPLATED = re.compile(r"`<[a-z]+>(-[a-z0-9-]+)`")

    def referenced(self):
        """{name: {custom skill, ...}} for outside-looking skill names."""
        found = {}
        for f in sorted(install.SKILLS_SRC.rglob("*.md")):
            if "examples" in f.parts:
                continue
            skill = f.relative_to(install.SKILLS_SRC).parts[0]
            in_table = False
            for line in f.read_text(encoding="utf-8").splitlines():
                if self.SKILL_TABLE.match(line):
                    in_table = True
                    continue
                if in_table and line.startswith("|"):
                    cell = line.split("|")[1].strip().strip("`")
                    if re.fullmatch(r"[a-z][a-z0-9:-]*", cell):
                        found.setdefault(cell, set()).add(skill)
                    continue
                in_table = False
                names = [next(g for g in m.groups() if g)
                         for m in self.NAMED_SKILL.finditer(line)]
                if re.search(r"skill|chain", line, re.I):
                    names += self.BACKTICKED.findall(line)
                names += ["*" + s for s in self.TEMPLATED.findall(line)]
                for name in names:
                    found.setdefault(name, set()).add(skill)
        return found

    def test_every_referenced_skill_is_installable(self):
        installable = (install.custom_skill_names()
                       | install.all_community_names()
                       | install.all_external_names()
                       | self.PLUGIN_PROVIDED)
        for name, users in sorted(self.referenced().items()):
            if name in self.NOT_SKILLS:
                continue
            with self.subTest(name=name, used_by=sorted(users)):
                if name.startswith("*"):
                    self.assertTrue(
                        any(n.endswith(name[1:]) for n in installable),
                        f"no installable skill matches {name}")
                else:
                    self.assertIn(name, installable,
                                  "add it with install.py --add-inventory, "
                                  "or list it in PLUGIN_PROVIDED/NOT_SKILLS")

    def test_scanner_still_sees_the_known_chains(self):
        # Guards the scanner itself: if a regex stops matching, the test
        # above would pass vacuously.
        found = self.referenced()
        for name in ("code-tour", "context-map", "caveman",
                     "acquire-codebase-knowledge", "write-pr-description",
                     "debugging-and-error-recovery", "find-skills",
                     "*-linux-triage"):
            with self.subTest(name):
                self.assertIn(name, found)


class TestBumpInventory(InventoryTest):
    def setUp(self):
        super().setUp()
        self.quiet()
        self.path = self.write_inventory(
            inventory_entry(), inventory_entry(skill="tool-j"),
            inventory_entry(source="other/repo", skill="tool-k",
                            folder="k"))

    def bump(self, heads, trees=None, **kwargs):
        trees = trees or {}

        def tree(repo, ref, fn):
            files = trees.get(repo, {"skills/tool-i/SKILL.md": "",
                                     "skills/tool-j/SKILL.md": "",
                                     "skills/k/SKILL.md": ""})
            return fn(sorted(files), files.get)

        with mock.patch("install.remote_head",
                        side_effect=lambda url: heads.get(url)), \
             mock.patch("install.with_remote_tree", side_effect=tree):
            return install.bump_inventory(self.path, **kwargs)

    def refs(self):
        return {e["skill"]: e["ref"]
                for e in install.load_inventory(self.path)}

    def test_moves_every_entry_of_a_repo_to_the_tip(self):
        _, bumped = self.bump({"https://github.com/acme/skills.git": SHA_B,
                               "https://github.com/other/repo.git": SHA_A})
        self.assertEqual(bumped, [("acme/skills", SHA_A, SHA_B)])
        self.assertEqual(self.refs(), {"tool-i": SHA_B, "tool-j": SHA_B,
                                       "tool-k": SHA_A})

    def test_unreachable_upstream_keeps_the_pin(self):
        _, bumped = self.bump({})
        self.assertEqual(bumped, [])
        self.assertEqual(set(self.refs().values()), {SHA_A})

    def test_skill_gone_upstream_keeps_the_repo_pin(self):
        heads = {"https://github.com/acme/skills.git": SHA_B}
        _, bumped = self.bump(heads, trees={
            "acme/skills": {"skills/tool-i/SKILL.md": "",
                            "other/tool-j/SKILL.md": ""}})
        self.assertEqual(bumped, [])
        self.assertEqual(self.refs()["tool-j"], SHA_A)

    def test_follows_a_renamed_upstream_folder(self):
        heads = {"https://github.com/acme/skills.git": SHA_B}
        self.bump(heads, trees={"acme/skills": {
            "skills/tool-i/SKILL.md": "",
            "skills/renamed-j/SKILL.md": "---\nname: tool-j\n---\n"}})
        entries = {e["skill"]: e for e in install.load_inventory(self.path)}
        self.assertEqual(entries["tool-j"]["ref"], SHA_B)
        self.assertEqual(entries["tool-j"]["folder"], "renamed-j")
        self.assertNotIn("folder", entries["tool-i"])

    def test_drops_folder_once_upstream_matches_the_name(self):
        heads = {"https://github.com/other/repo.git": SHA_B}
        self.bump(heads, trees={"other/repo": {
            "skills/tool-k/SKILL.md": "---\nname: tool-k\n---\n"}})
        entries = {e["skill"]: e for e in install.load_inventory(self.path)}
        self.assertNotIn("folder", entries["tool-k"])

    def test_dry_run_reports_but_writes_nothing(self):
        before = self.path.read_text()
        entries, bumped = self.bump(
            {"https://github.com/acme/skills.git": SHA_B}, dry_run=True)
        self.assertEqual(len(bumped), 1)
        self.assertEqual(entries[0]["ref"], SHA_B)
        self.assertEqual(self.path.read_text(), before)


class TestCheckCheckoutCurrent(TempDirTest):
    """Against real local git repos: an upstream and a clone of it."""

    def git(self, cwd, *args):
        subprocess.run(["git", "-C", str(cwd), "-c", "user.name=t",
                        "-c", "user.email=t@t", *args], check=True,
                       capture_output=True)

    def setUp(self):
        super().setUp()
        self.upstream = self.tmp / "upstream"
        self.git(self.tmp, "init", "-q", "-b", "main", str(self.upstream))
        self.git(self.upstream, "commit", "-q", "--allow-empty", "-m", "a")
        self.clone = self.tmp / "clone"
        self.git(self.tmp, "clone", "-q", str(self.upstream),
                 str(self.clone))
        out = contextlib.ExitStack()
        out.enter_context(contextlib.redirect_stdout(io.StringIO()))
        out.enter_context(contextlib.redirect_stderr(io.StringIO()))
        self.addCleanup(out.close)

    def test_current(self):
        self.assertEqual(install.check_checkout_current(self.clone),
                         "current")

    def test_behind_when_upstream_moved(self):
        self.git(self.upstream, "commit", "-q", "--allow-empty", "-m", "b")
        self.assertEqual(install.check_checkout_current(self.clone),
                         "behind")

    def test_ahead_with_local_commits(self):
        self.git(self.clone, "commit", "-q", "--allow-empty", "-m", "c")
        self.assertEqual(install.check_checkout_current(self.clone),
                         "ahead")

    def test_detached_checkout_is_not_checked(self):
        self.git(self.clone, "checkout", "-q", "--detach")
        self.assertIsNone(install.check_checkout_current(self.clone))


class TestMainUpdate(MainHarness):
    """--update refreshes only what each target already has."""

    def update(self, argv, entries=None):
        self.make_skill("skills", name="other")
        bump = mock.patch("install.bump_inventory",
                          return_value=(entries or [], []))
        current = mock.patch("install.check_checkout_current")
        return self.run_main(["--update", *argv],
                             extra_patches=[bump, current])

    def test_refreshes_installed_custom_skill_only(self):
        claude = self.tmp / "home" / "claude"
        (claude / "needs-dep").mkdir(parents=True)
        self.update(["--target", "claude", "--skills-only"])
        self.assertTrue((claude / "needs-dep").is_symlink())
        self.assertFalse((claude / "other").exists())
        # A requirement is not pulled in: --update never installs new.
        self.assertFalse((claude / "code-tour").exists())

    def test_fetches_only_installed_community_skills(self):
        claude = self.tmp / "home" / "claude"
        (claude / "tool-i").mkdir(parents=True)
        fetched = []
        entries = [inventory_entry(), inventory_entry(skill="tool-j",
                                                      default=True)]

        def fetch(source, dry_run, names=None):
            fetched.append(set(names))
            return None

        bump = mock.patch("install.bump_inventory",
                          return_value=(entries, []))
        with mock.patch("install.SOURCES", []):
            self.run_main(["--update", "--target", "claude"], fetch=fetch,
                          extra_patches=[bump, mock.patch(
                              "install.check_checkout_current")])
        self.assertEqual(fetched, [{"tool-i"}])

    def test_skills_only_leaves_pins_alone(self):
        with mock.patch("install.bump_inventory") as m, \
             mock.patch("install.check_checkout_current"):
            self.run_main(["--update", "--target", "claude",
                           "--skills-only"])
        m.assert_not_called()


class TestPinnedCache(InventoryTest):
    def setUp(self):
        super().setUp()
        self.quiet()
        self.cache = self.tmp / "cache"

    def update(self, calls=None, **kwargs):
        side = (lambda a: calls.append(a)) if calls is not None else None
        with mock.patch("install.run_git", side_effect=side):
            return install.update_repo_cache(
                self.cache, "u", SHA_A, ["skills/tool"], False, "acme", "f",
                **kwargs)

    def test_fresh_clone_fetches_the_pinned_commit(self):
        calls = []
        self.assertEqual(self.update(calls), self.cache)
        self.assertEqual(calls[0][0], "clone")
        self.assertIn("--no-checkout", calls[0])
        self.assertNotIn("-b", calls[0])
        self.assertIn("sparse-checkout", calls[1])
        self.assertIn("fetch", calls[2])
        self.assertEqual(calls[2][-2:], ["origin", SHA_A])
        self.assertEqual(calls[3][-2:], ["--hard", "FETCH_HEAD"])

    def test_existing_cache_refetches_without_clone(self):
        (self.cache / ".git").mkdir(parents=True)
        calls = []
        self.update(calls)
        self.assertNotIn("clone", [c[0] for c in calls])
        self.assertEqual(calls[-1][-1], "FETCH_HEAD")

    def test_failed_fetch_skips_a_cache_at_another_commit(self):
        (self.cache / "skills" / "tool").mkdir(parents=True)
        boom = subprocess.CalledProcessError(128, ["git", "fetch"])
        for head, expected in ((SHA_B, None), (SHA_A, self.cache)):
            with self.subTest(head=head), \
                 mock.patch("install.git_head", return_value=head), \
                 mock.patch("install.run_git", side_effect=boom):
                self.assertEqual(install.update_repo_cache(
                    self.cache, "u", SHA_A, [], False, "acme", "f"),
                    expected)

    def test_source_cache_uses_folder_and_ref(self):
        [source] = install.inventory_sources([inventory_entry(
            folder="tool")])
        with mock.patch("install.update_repo_cache") as m:
            install.update_source_cache(source, dry_run=False)
        self.assertEqual(m.call_args[0][3], ["skills/tool"])
        self.assertEqual(m.call_args[0][2], SHA_A)

    def test_install_copies_the_folder_under_the_skill_name(self):
        [source] = install.inventory_sources([inventory_entry(
            folder="tool")])
        self.make_skill("cache/skills", "tool")
        source["_cache"] = self.cache
        dest = self.tmp / "dest"
        with mock.patch("install.SOURCES", [source]):
            results = install.install_community_for_target(
                "claude", dest, {"tool-i"}, dry_run=False)
        self.assertEqual(results, [("claude", "tool-i", "installed")])
        self.assertTrue((dest / "tool-i" / "SKILL.md").is_file())


class TestCheckInventoryUpdates(InventoryTest):
    def test_counts_sources_behind_upstream(self):
        self.quiet()
        sources = install.inventory_sources([
            inventory_entry(),
            inventory_entry(source="other/repo", skill="tool-k")])
        heads = {"https://github.com/acme/skills.git": SHA_A,
                 "https://github.com/other/repo.git": SHA_B}
        with mock.patch("install.remote_head", side_effect=heads.get):
            self.assertEqual(install.check_inventory_updates(sources), 1)

    def test_unreachable_upstream_is_not_counted(self):
        self.quiet()
        sources = install.inventory_sources([inventory_entry()])
        with mock.patch("install.remote_head", return_value=None):
            self.assertEqual(install.check_inventory_updates(sources), 0)


class TestParseSkillSpec(unittest.TestCase):
    def test_accepted_forms(self):
        for spec in ("https://skills.sh/vercel-labs/skills/find-skills",
                     "https://www.skills.sh/vercel-labs/skills/find-skills/",
                     "vercel-labs/skills@find-skills",
                     "  vercel-labs/skills@find-skills\n"):
            with self.subTest(spec):
                self.assertEqual(install.parse_skill_spec(spec),
                                 ("vercel-labs/skills", "find-skills"))

    def test_rejected_forms(self):
        for spec in ("find-skills", "vercel-labs/skills", "../..@x",
                     "https://github.com/vercel-labs/skills",
                     "https://skills.sh/vercel-labs/skills"):
            with self.subTest(spec):
                with self.assertRaises(install.InventoryError):
                    install.parse_skill_spec(spec)

    def test_frontmatter_name(self):
        self.assertEqual(install.frontmatter_name(
            "---\nname: 'tool-i'\ndescription: x\n---\nbody"), "tool-i")
        self.assertIsNone(install.frontmatter_name("no frontmatter"))


class TestAddInventory(InventoryTest):
    def setUp(self):
        super().setUp()
        self.quiet()
        self.path = self.write_inventory(inventory_entry())

    def add(self, spec, located=("skills", "tool-new"), head=SHA_B,
            **kwargs):
        with mock.patch("install.remote_head", return_value=head) as rh, \
             mock.patch("install.locate_skill", return_value=located):
            entry = install.add_inventory(spec, path=self.path, **kwargs)
        self.remote_head = rh
        return entry

    def test_appends_pinned_non_default_entry(self):
        entry = self.add("https://skills.sh/other/repo/tool-new")
        self.assertEqual(entry, {"source": "other/repo", "skill": "tool-new",
                                 "ref": SHA_B,
                                 "targets": ["claude", "copilot"],
                                 "default": False})
        self.assertEqual(install.load_inventory(self.path)[-1], entry)

    def test_records_subdir_and_folder_when_they_differ(self):
        entry = self.add("other/repo@tool-new",
                         located=(".agents/skills", "new"))
        self.assertEqual(entry["subdir"], ".agents/skills")
        self.assertEqual(entry["folder"], "new")

    def test_same_repo_reuses_the_pinned_ref(self):
        entry = self.add("acme/skills@tool-new")
        self.assertEqual(entry["ref"], SHA_A)
        self.remote_head.assert_not_called()

    def test_same_repo_with_another_subdir_rejected(self):
        with self.assertRaises(install.InventoryError):
            self.add("acme/skills@tool-new",
                     located=(".agents/skills", "tool-new"))

    def test_duplicates_and_clashes_rejected(self):
        for spec in ("acme/skills@tool-i", "other/repo@roj-code-review-pr",
                     "other/repo@graphify"):
            with self.subTest(spec):
                with self.assertRaises(install.InventoryError):
                    self.add(spec)

    def test_unreachable_upstream_rejected(self):
        with self.assertRaises(install.InventoryError):
            self.add("other/repo@tool-new", head=None)

    def test_dry_run_writes_nothing(self):
        before = self.path.read_text()
        self.add("other/repo@tool-new", dry_run=True)
        self.assertEqual(self.path.read_text(), before)


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

    def test_quoted_shorthand_is_unquoted(self):
        parsed = install.parse_manifest(
            'dependencies:\n  apm:\n'
            '    - "C:/Users/me/agent-skills"\n'
            '    - "/Users/x/agent-skills"\n')
        for dep, path in zip(parsed["apm"],
                             ("C:/Users/me/agent-skills",
                              "/Users/x/agent-skills")):
            self.assertEqual((dep["path"], dep["name"], dep["ref"]),
                             (path, "agent-skills", None))

    def test_quoted_object_values_are_unquoted(self):
        parsed = install.parse_manifest(
            'dependencies:\n  apm:\n'
            '    - git: "https://github.com/x/tool.git"\n'
            '      path: "skills/tool"\n'
            "      ref: '2e08b9177c07bb7249a8a2d1a6758e5db281d002'\n")
        dep = parsed["apm"][0]
        self.assertEqual((dep["path"], dep["name"], dep["ref"]),
                         ("skills/tool", "tool",
                          "2e08b9177c07bb7249a8a2d1a6758e5db281d002"))

    def test_git_dependency_without_path_drops_dot_git(self):
        parsed = install.parse_manifest(
            "dependencies:\n  apm:\n"
            "    - git: https://github.com/addyosmani/agent-skills.git\n")
        dep = parsed["apm"][0]
        self.assertEqual((dep["path"], dep["name"]),
                         ("https://github.com/addyosmani/agent-skills.git",
                          "agent-skills"))

    def test_realistic_generated_manifest(self):
        text = (
            "# Generated by agent-skills install.py. Edit apm.yml in the clone, not this file.\n"
            "name: roj-ai-setup\n"
            "version: 1.0.0\n"
            "description: x\n"
            "includes: auto\n"
            "targets: [claude, copilot]\n"
            "dependencies:\n"
            "  apm:\n"
            "    - ./skills/roj-explain-logic\n"
            "    # Copilot only: Claude gets the equivalent from a plugin.\n"
            "    - git: https://github.com/addyosmani/agent-skills.git   # Claude: superpowers:systematic-debugging\n"
            "      path: skills/debugging-and-error-recovery\n"
            "      ref: 1401c8b8030e023baeebb31781a6653fe8e93026\n"
            "      targets: [copilot]\n"
            "    # Optional — uncomment and re-run install.py:\n"
            "    # - anthropics/skills/skills/pdf#683bc88e56f3e09ba94f7055977f3d3aa499f202\n"
            "  mcp:\n"
            "    - io.github.github/github-mcp-server\n")
        parsed = install.parse_manifest(text)
        got = [(d["name"], d["path"], d["ref"], d["targets"], d["active"])
               for d in parsed["apm"]]
        self.assertEqual(got, [
            ("roj-explain-logic", "./skills/roj-explain-logic", None, None, True),
            ("debugging-and-error-recovery", "skills/debugging-and-error-recovery",
             "1401c8b8030e023baeebb31781a6653fe8e93026", ("copilot",), True),
            ("pdf", "anthropics/skills/skills/pdf",
             "683bc88e56f3e09ba94f7055977f3d3aa499f202", None, False),
        ])
        self.assertEqual([(d["name"], d["active"]) for d in parsed["mcp"]],
                         [("github-mcp-server", True)])


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
                                 ["apm", "install", "-g", "--update", "--target", value])

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


if __name__ == "__main__":
    unittest.main()


