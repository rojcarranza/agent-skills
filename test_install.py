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


class TestPromptsDirFor(TempDirTest):
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

    def retire(self, target="copilot", dry_run=False):
        with mock.patch.multiple(
                "install", RETIRED_PROMPTS=("roj-create-sb",
                                            "roj-code-review-pr"),
                claude_commands_dir=mock.Mock(return_value=self.cmds),
                vscode_prompts_dir=mock.Mock(return_value=self.pdir)):
            return install.retire_prompts(target, self.dest, dry_run)

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


class ExternalTest(TempDirTest):
    """Externals delegate to a CLI, so every test here fakes both the CLI
    lookup and the subprocess call — nothing may reach a real install."""

    def fake_external(self, **overrides):
        ext = {
            "name": "tool-y", "package": "tool-y-pkg", "cli": "tool-y",
            "targets": ("copilot", "claude"), "default": True,
            "doc": "does things",
            "install": {"claude": ["install"],
                        "copilot": ["vscode", "install"]},
            "uninstall": {"claude": ["claude", "uninstall"],
                          "copilot": ["vscode", "uninstall"]},
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
        err = io.StringIO()
        with mock.patch("install.EXTERNALS", [self.fake_external()]), \
                mock.patch("install.find_cli", return_value="/opt/bin/tool-y"), \
                mock.patch("install.run_apm", return_value=0), \
                mock.patch("install.apm_home", return_value=self.tmp / ".apm"), \
                mock.patch("install.target_root", return_value=dest), \
                mock.patch("install.shutil.which", return_value=None), \
                contextlib.redirect_stdout(io.StringIO()), \
                contextlib.redirect_stderr(err):
            install.show_status(["claude"])
        self.assertIn("/opt/bin", err.getvalue())


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
                "claude", self.fake_external(), "/bin/tool-y",
                dry_run=False)
        self.assertEqual(results, [("claude", "tool-y", "installed (by CLI)")])
        argv, cwd = calls[0]
        self.assertEqual(argv, ["/bin/tool-y", "install"])
        self.assertNotEqual(cwd, str(Path.cwd()))

    def test_copilot_uses_the_vscode_body(self):
        calls, patched = self.record_runs()
        with patched:
            install.install_external_for_target(
                "copilot", self.fake_external(), "/bin/tool-y",
                dry_run=False)
        self.assertEqual(calls[0][0],
                         ["/bin/tool-y", "vscode", "install"])

    def test_dry_run_plans_without_running(self):
        with mock.patch("install.run_cli") as run:
            results = install.install_external_for_target(
                "claude", self.fake_external(), None, dry_run=True)
        run.assert_not_called()
        self.assertEqual(results,
                         [("claude", "tool-y",
                           "dry-run: would run tool-y install")])

    def test_missing_cli_skips_instead_of_failing(self):
        with mock.patch("install.run_cli") as run:
            results = install.install_external_for_target(
                "claude", self.fake_external(), None, dry_run=False)
        run.assert_not_called()
        self.assertEqual(results,
                         [("claude", "tool-y", "skipped (CLI unavailable)")])

    def test_target_policy_respected(self):
        ext = self.fake_external(targets=("copilot",))
        with mock.patch("install.run_cli") as run:
            results = install.install_external_for_target(
                "claude", ext, "/bin/tool-y", dry_run=False)
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
                "copilot", self.fake_external(), "/bin/tool-y",
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
                "claude", {"tool-y"}, dry_run=False)
            skipped = install.install_externals_for_target(
                "claude", set(), dry_run=False)
        self.assertEqual(len(calls), 1)
        self.assertEqual(len(selected), 1)
        self.assertEqual(skipped, [])


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


class TestSkillDependencies(unittest.TestCase):
    """Every outside skill a custom skill names must be installable: in
    apm.yml, an external, another custom skill, or provided by a Claude
    plugin. A new chain to an unknown skill fails here, so it gets listed in
    apm.yml instead of silently relying on a manual install."""

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
                       | install.manifest_skill_names(active_only=False)
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
                                  "add it to apm.yml, "
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


OWNED = "---\nname: {}\ndescription: x\n---\n"


class TestLegacyCleanup(TempDirTest):
    LOCK = "deployed_files:\n  - .claude/skills/{}/SKILL.md\n"

    def setUp(self):
        super().setUp()
        self.clone_skills = self.tmp / "clone" / "skills"
        self.make_skill("clone/skills", name="roj-a")
        deps = [
            {"name": "roj-a", "path": "./skills/roj-a", "active": True,
             "targets": None},
            {"name": "code-tour", "path": "github/x/skills/code-tour",
             "active": True, "targets": None},
            {"name": "caveman", "path": "skills/caveman", "active": True,
             "targets": ("copilot",)},
            {"name": "pdf", "path": "anthropics/skills/skills/pdf",
             "active": False, "targets": None}]
        for p in (mock.patch("install.SKILLS_SRC", self.clone_skills),
                  mock.patch("install.manifest_deps", return_value=deps)):
            p.start()
            self.addCleanup(p.stop)

    def cleanup(self, target, root, lock_text=None, dry_run=False):
        err = io.StringIO()
        with mock.patch("sys.stderr", err):
            results = install.remove_installer_skills(
                target, root, dry_run, lock_text=lock_text)
        return results, err.getvalue()

    def link(self, entry, to):
        entry.parent.mkdir(parents=True, exist_ok=True)
        try:
            entry.symlink_to(to, target_is_directory=True)
        except OSError:
            self.skipTest("symlinks unsupported here")

    def test_legacy_names_are_custom_plus_community(self):
        self.assertEqual(install.legacy_skill_names(),
                         {"roj-a", "code-tour", "caveman", "pdf"})

    def test_managed_names_follow_active_deps_and_targets(self):
        self.assertEqual(install.managed_skill_names("claude"),
                         {"roj-a", "code-tour"})
        self.assertEqual(install.managed_skill_names("copilot"),
                         {"roj-a", "code-tour", "caveman"})

    def test_symlink_into_clone_always_removed(self):
        root = self.tmp / "claude"
        self.link(root / "roj-a", self.clone_skills / "roj-a")
        results, _ = self.cleanup("claude", root,
                                  lock_text=self.LOCK.format("roj-a"))
        self.assertFalse((root / "roj-a").is_symlink())
        self.assertEqual(results, [("claude", "roj-a", "removed (pre-APM link)")])

    def test_link_into_another_checkout_removed(self):
        other = self.tmp / "main-checkout"
        self.make_skill("main-checkout/skills", name="roj-a")
        (other / "install.py").write_text("")
        (other / ".claude-plugin").mkdir()
        (other / ".claude-plugin" / "marketplace.json").write_text("{}")
        root = self.tmp / "claude"
        self.link(root / "roj-a", other / "skills" / "roj-a")
        results, err = self.cleanup("claude", root)
        self.assertFalse((root / "roj-a").is_symlink())
        self.assertTrue((other / "skills" / "roj-a").is_dir())
        self.assertEqual(results, [("claude", "roj-a", "removed (pre-APM link)")])
        self.assertEqual(err, "")

    def test_link_into_unmarked_skills_dir_kept_with_warning(self):
        # skills/<name> alone does not make a checkout of this repo.
        self.make_skill("lookalike/skills", name="roj-a")
        (self.tmp / "lookalike" / "install.py").write_text("")
        root = self.tmp / "claude"
        self.link(root / "roj-a", self.tmp / "lookalike" / "skills" / "roj-a")
        results, err = self.cleanup("claude", root)
        self.assertTrue((root / "roj-a").is_symlink())
        self.assertEqual(results, [])
        self.assertIn("outside this clone", err)

    def test_claude_copies_removed_before_apm_owns_them(self):
        self.make_skill("claude", name="code-tour", content=OWNED.format("code-tour"))
        results, _ = self.cleanup("claude", self.tmp / "claude")
        self.assertFalse((self.tmp / "claude" / "code-tour").exists())
        self.assertEqual(results, [("claude", "code-tour", "removed (pre-APM copy)")])

    def test_claude_copy_kept_when_the_lockfile_lists_it(self):
        self.make_skill("claude", name="code-tour", content=OWNED.format("code-tour"))
        results, _ = self.cleanup("claude", self.tmp / "claude",
                                  lock_text=self.LOCK.format("code-tour"))
        self.assertTrue((self.tmp / "claude" / "code-tour").is_dir())
        self.assertEqual(results, [])

    def test_claude_copy_removed_when_lockfile_is_copilot_only(self):
        # A --target copilot run wrote the lockfile; APM never deployed to
        # ~/.claude/skills, so the copy is still ours.
        self.make_skill("claude", name="code-tour", content=OWNED.format("code-tour"))
        results, _ = self.cleanup(
            "claude", self.tmp / "claude",
            lock_text="deployed_files:\n  - .agents/skills/code-tour/SKILL.md\n")
        self.assertFalse((self.tmp / "claude" / "code-tour").exists())
        self.assertEqual(len(results), 1)

    def test_lockfile_prefix_match_does_not_count(self):
        self.make_skill("claude", name="code-tour", content=OWNED.format("code-tour"))
        results, _ = self.cleanup("claude", self.tmp / "claude",
                                  lock_text=self.LOCK.format("code-tour-x"))
        self.assertFalse((self.tmp / "claude" / "code-tour").exists())
        self.assertEqual(len(results), 1)

    def test_lockfile_windows_separators(self):
        self.make_skill("claude", name="code-tour", content=OWNED.format("code-tour"))
        results, _ = self.cleanup(
            "claude", self.tmp / "claude",
            lock_text="  - C:\\Users\\me\\.claude\\skills\\code-tour\\SKILL.md\n")
        self.assertTrue((self.tmp / "claude" / "code-tour").is_dir())
        self.assertEqual(results, [])

    def test_copilot_copies_always_removed(self):
        self.make_skill("copilot", name="code-tour", content=OWNED.format("code-tour"))
        self.cleanup("copilot", self.tmp / "copilot",
                     lock_text="  - .copilot/skills/code-tour/\n")
        self.assertFalse((self.tmp / "copilot" / "code-tour").exists())

    def test_optional_skill_copy_kept_with_warning(self):
        # pdf is commented out in apm.yml: APM would not put it back.
        self.make_skill("claude", name="pdf", content=OWNED.format("pdf"))
        results, err = self.cleanup("claude", self.tmp / "claude")
        self.assertTrue((self.tmp / "claude" / "pdf").is_dir())
        self.assertEqual(results, [])
        self.assertIn("APM does not manage pdf for claude", err)
        self.assertIn("uncomment it in apm.yml", err)
        self.assertEqual(err.count("[ warn ]"), 1)

    def test_copilot_only_skill_copy_kept_for_claude(self):
        self.make_skill("claude", name="caveman", content=OWNED.format("caveman"))
        results, err = self.cleanup("claude", self.tmp / "claude")
        self.assertTrue((self.tmp / "claude" / "caveman").is_dir())
        self.assertEqual(results, [])
        self.assertIn("APM does not manage caveman for claude", err)

    def test_copilot_only_skill_copy_removed_for_copilot(self):
        self.make_skill("copilot", name="caveman", content=OWNED.format("caveman"))
        results, _ = self.cleanup("copilot", self.tmp / "copilot")
        self.assertFalse((self.tmp / "copilot" / "caveman").exists())
        self.assertEqual(results, [("copilot", "caveman", "removed (pre-APM copy)")])

    def test_unmanaged_foreign_copy_kept_silently(self):
        self.make_skill("claude", name="pdf", content=OWNED.format("my-pdf"))
        results, err = self.cleanup("claude", self.tmp / "claude")
        self.assertTrue((self.tmp / "claude" / "pdf").is_dir())
        self.assertEqual((results, err), ([], ""))

    def test_copy_without_matching_name_kept(self):
        self.make_skill("copilot", name="code-tour", content=OWNED.format("my-tour"))
        results, _ = self.cleanup("copilot", self.tmp / "copilot")
        self.assertTrue((self.tmp / "copilot" / "code-tour").is_dir())
        self.assertEqual(results, [])

    def test_copy_with_undecodable_skill_md_is_not_a_crash(self):
        d = self.tmp / "copilot" / "code-tour"
        d.mkdir(parents=True)
        (d / "SKILL.md").write_bytes(b"---\nname: code-tour\n\xff\xfe\n---\n")
        results, _ = self.cleanup("copilot", self.tmp / "copilot")
        self.assertEqual(len(results), 1)

    def test_foreign_link_kept_with_warning(self):
        outside = self.tmp / "elsewhere" / "code-tour"
        outside.mkdir(parents=True)
        root = self.tmp / "copilot"
        self.link(root / "code-tour", outside)
        results, err = self.cleanup("copilot", root)
        self.assertTrue((root / "code-tour").is_symlink())
        self.assertEqual(results, [])
        self.assertIn("outside this clone", err)

    def test_dangling_link_removed(self):
        root = self.tmp / "claude"
        self.link(root / "roj-a", self.tmp / "gone" / "roj-a")
        results, _ = self.cleanup("claude", root,
                                  lock_text=self.LOCK.format("roj-a"))
        self.assertFalse((root / "roj-a").is_symlink())
        self.assertEqual(results, [("claude", "roj-a", "removed (pre-APM link)")])

    def test_unknown_and_graphify_untouched(self):
        self.make_skill("copilot", name="graphify")
        self.make_skill("copilot", name="my-own")
        results, _ = self.cleanup("copilot", self.tmp / "copilot")
        self.assertEqual(results, [])
        self.assertTrue((self.tmp / "copilot" / "graphify").is_dir())

    def test_dry_run_removes_nothing(self):
        self.make_skill("copilot", name="code-tour", content=OWNED.format("code-tour"))
        results, _ = self.cleanup("copilot", self.tmp / "copilot", dry_run=True)
        self.assertTrue((self.tmp / "copilot" / "code-tour").is_dir())
        self.assertEqual(len(results), 1)

    def test_missing_root_is_fine(self):
        self.assertEqual(self.cleanup("claude", self.tmp / "nope")[0], [])


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


class TestMain(TempDirTest):
    """main() end to end with apm, externals and homes faked."""

    def run_main(self, argv, apm="/bin/apm", apm_code=0, lock=False, wsl=False,
                 externals=(), bootstrap=None):
        home = self.tmp / "home"
        (home / ".apm").mkdir(parents=True, exist_ok=True)
        if lock:
            (home / ".apm" / "apm.lock.yaml").write_text(
                lock if isinstance(lock, str) else "x")
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
                           side_effect=lambda t: home / t),
                mock.patch("install.copilot_instruction_path",
                           return_value=home / "instr" / "p.instructions.md"),
                mock.patch("install.claude_commands_dir",
                           return_value=home / "commands"),
                mock.patch("install.find_cli",
                           side_effect=lambda n: apm if n == "apm" else None),
                mock.patch("install.run_apm", side_effect=fake_run),
                mock.patch("install.EXTERNALS", list(externals)),
                mock.patch("install.bootstrap_cli",
                           side_effect=bootstrap or (lambda ext, dry: None)),
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
        self.assertEqual(calls, [["/bin/apm", "install", "-g", "--update",
                                  "--target", "claude,copilot"]])
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
        self.assertIn("would run apm install -g --update --target "
                      "claude,copilot", out)
        self.assertFalse((self.tmp / "home" / ".apm" / "apm.yml").exists())

    def test_apm_failure_is_the_exit_code(self):
        code, _, _, err = self.run_main([], apm_code=2)
        self.assertEqual(code, 2)
        self.assertIn("apm install failed", err)
        self.assertIn("once a re-run of install.py succeeds", err)

    def test_update_without_apm_stops_with_hint(self):
        code, calls, _, err = self.run_main(["--update"], apm=None)
        self.assertEqual(code, 1)
        self.assertEqual(calls, [])
        self.assertIn("brew install apm", err)

    def test_update_dry_run_runs_nothing(self):
        code, calls, out, _ = self.run_main(["--update", "--dry-run"])
        self.assertEqual(code, 0)
        self.assertEqual(calls, [])
        self.assertIn("would run apm outdated -g", out)

    def test_foreign_manifest_stops_before_cleanup(self):
        apm_dir = self.tmp / "home" / ".apm"
        apm_dir.mkdir(parents=True)
        (apm_dir / "apm.yml").write_text("name: mine\n")
        self.make_skill("home/copilot", name="code-tour",
                        content="---\nname: code-tour\ndescription: x\n---\n")
        code, calls, _, _ = self.run_main(["--target", "copilot"], lock=True)
        self.assertNotEqual(code, 0)
        self.assertEqual(calls, [])
        self.assertTrue((self.tmp / "home" / "copilot" / "code-tour").exists())

    def test_update_reports_outdated(self):
        code, calls, _, _ = self.run_main(["--update"])
        self.assertEqual(calls, [["/bin/apm", "outdated", "-g"]])
        self.assertEqual(code, 0)

    def test_status_lists_apm_deps(self):
        _, calls, _, _ = self.run_main(["--status"])
        self.assertEqual(calls, [["/bin/apm", "deps", "list", "-g"]])

    def test_status_without_apm_warns_and_succeeds(self):
        code, calls, _, err = self.run_main(["--status"], apm=None)
        self.assertEqual(code, 0)
        self.assertEqual(calls, [])
        self.assertIn("apm is not installed", err)

    def test_skills_only_never_bootstraps_externals(self):
        ext = ExternalTest.fake_external(None)
        boots = []
        code, _, out, _ = self.run_main(
            ["--skills-only", "--target", "claude"], externals=[ext],
            bootstrap=lambda e, dry: boots.append(e["name"]))
        self.assertEqual(code, 0)
        self.assertEqual(boots, [])
        self.assertIn("--skills-only", out)

    def test_claude_copy_listed_in_lockfile_survives_install(self):
        self.make_skill("home/claude", name="code-tour",
                        content=OWNED.format("code-tour"))
        self.run_main(["--target", "claude"],
                      lock="  - .claude/skills/code-tour/SKILL.md\n")
        self.assertTrue((self.tmp / "home" / "claude" / "code-tour").is_dir())

    def test_claude_copy_removed_when_lockfile_is_copilot_only(self):
        self.make_skill("home/claude", name="code-tour",
                        content=OWNED.format("code-tour"))
        self.run_main(["--target", "claude"],
                      lock="  - .agents/skills/code-tour/SKILL.md\n")
        self.assertFalse((self.tmp / "home" / "claude" / "code-tour").exists())

    def test_status_warns_about_older_leftovers(self):
        home = self.tmp / "home"
        gen = home / "claude" / "roj-create-sb"
        gen.mkdir(parents=True)
        (gen / "SKILL.md").write_text("<!-- Generated from prompts/x -->\n")
        old = home / "claude" / "explain-logic"
        old.mkdir()
        (old / "SKILL.md").write_text("---\nname: explain-logic\n---\n")
        _, _, _, err = self.run_main(["--status", "--target", "claude"])
        for name in ("roj-create-sb", "explain-logic"):
            with self.subTest(name=name):
                self.assertIn(f"{name} left by an older install — re-run "
                              "install.py to remove", err)
        self.assertTrue(gen.is_dir())
        self.assertTrue(old.is_dir())

    def test_status_warns_about_dotfiles_instruction_copy(self):
        dest = self.tmp / "home" / "instr" / "p.instructions.md"
        dest.parent.mkdir(parents=True)
        dest.write_bytes(install.INSTRUCTIONS_SRC.read_bytes())
        _, _, _, err = self.run_main(["--status", "--target", "copilot"])
        self.assertIn("p.instructions.md left by an older install", err)
        self.assertTrue(dest.is_file())

    def test_removed_flags_are_rejected(self):
        for flag in (["--repo", "."], ["--skill", "x"], ["--list"],
                     ["--uninstall", "x"], ["--add-inventory", "a/b@c"],
                     ["--check-inventory-updates"]):
            with self.subTest(flag=flag):
                code, calls, _, _ = self.run_main(flag)
                self.assertEqual(code, 2)
                self.assertEqual(calls, [])

    def test_legacy_copilot_copy_cleared_before_apm(self):
        self.make_skill("home/copilot", name="code-tour",
                        content="---\nname: code-tour\ndescription: x\n---\n")
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


if __name__ == "__main__":
    unittest.main()
