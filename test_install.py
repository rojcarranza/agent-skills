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
    lookup and the subprocess call — nothing may reach a real install.
    install.log(), ok() and warn() print, so both streams are captured."""

    def setUp(self):
        super().setUp()
        for stream in ("stdout", "stderr"):
            patcher = mock.patch(f"sys.{stream}", io.StringIO())
            patcher.start()
            self.addCleanup(patcher.stop)

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
                mock.patch("install.pip_externally_managed",
                           return_value=False), \
                mock.patch("install.subprocess.run") as run:
            path = install.bootstrap_cli(self.fake_external(), dry_run=False)
        self.assertEqual(path, "/bin/tool-y")
        run.assert_called_once_with([*pip, "tool-y-pkg"], check=True)

    def bootstrap_on_managed_python(self, on_path, run_error=None):
        pip = [sys.executable, "-m", "pip", "install", "--user"]
        with mock.patch("install.find_cli", return_value=None), \
                mock.patch("install.shutil.which",
                           side_effect=lambda name: name if name in on_path
                           else None), \
                mock.patch("install.BOOTSTRAP_CMDS",
                           (["uv", "tool", "install"], ["pipx", "install"],
                            pip)), \
                mock.patch("install.pip_externally_managed",
                           return_value=True), \
                mock.patch("install.warn") as warn, \
                mock.patch("install.subprocess.run",
                           side_effect=run_error) as run:
            path = install.bootstrap_cli(self.fake_external(), dry_run=False)
        self.assertIsNone(path)
        return run, warn.call_args[0][0]

    def test_externally_managed_python_skips_pip_and_names_pipx(self):
        run, message = self.bootstrap_on_managed_python({"apt"})
        run.assert_not_called()
        self.assertIn("sudo apt install pipx", message)
        self.assertIn("pipx ensurepath", message)
        self.assertIn("python3 install.py", message)

    def test_externally_managed_python_without_apt_gets_generic_advice(self):
        run, message = self.bootstrap_on_managed_python(set())
        run.assert_not_called()
        self.assertNotIn("apt", message)
        self.assertIn("uv tool install tool-y-pkg", message)
        self.assertIn("pipx install tool-y-pkg", message)
        self.assertNotIn("pip install --user", message)

    def test_failed_pipx_on_managed_python_gets_generic_advice(self):
        run, message = self.bootstrap_on_managed_python(
            {"apt", "pipx"},
            run_error=subprocess.CalledProcessError(1, "pipx"))
        run.assert_called_once_with(["pipx", "install", "tool-y-pkg"],
                                    check=True)
        self.assertNotIn("apt", message)
        self.assertIn("uv tool install tool-y-pkg", message)
        self.assertNotIn("pip install --user", message)
        self.assertNotIn("no uv/pipx/pip to install", message)

    def test_unmanaged_python_keeps_the_pip_hint(self):
        with mock.patch("install.find_cli", return_value=None), \
                mock.patch("install.shutil.which", return_value=None), \
                mock.patch("install.BOOTSTRAP_CMDS", ()), \
                mock.patch("install.pip_externally_managed",
                           return_value=False), \
                mock.patch("install.warn") as warn:
            install.bootstrap_cli(self.fake_external(), dry_run=False)
        self.assertIn("python -m pip install --user tool-y-pkg",
                      warn.call_args[0][0])

    def test_no_installer_available_returns_none(self):
        with mock.patch("install.find_cli", return_value=None), \
                mock.patch("install.shutil.which", return_value=None), \
                mock.patch("install.BOOTSTRAP_CMDS",
                           (["uv", "tool", "install"],)), \
                mock.patch("install.subprocess.run") as run:
            self.assertIsNone(install.bootstrap_cli(self.fake_external(),
                                                    dry_run=False))
        run.assert_not_called()


class TestPipExternallyManaged(ExternalTest):
    def stdlib(self, marker):
        stdlib = self.tmp / "stdlib"
        stdlib.mkdir()
        if marker:
            (stdlib / "EXTERNALLY-MANAGED").write_text("[externally-managed]\n")
        return stdlib

    def test_marker_outside_venv_is_managed(self):
        with mock.patch("install.sysconfig.get_path",
                        return_value=str(self.stdlib(True))), \
                mock.patch("install.sys.prefix", "/usr"), \
                mock.patch("install.sys.base_prefix", "/usr"):
            self.assertTrue(install.pip_externally_managed())

    def test_no_marker_is_not_managed(self):
        with mock.patch("install.sysconfig.get_path",
                        return_value=str(self.stdlib(False))), \
                mock.patch("install.sys.prefix", "/usr"), \
                mock.patch("install.sys.base_prefix", "/usr"):
            self.assertFalse(install.pip_externally_managed())

    def test_venv_is_never_managed(self):
        with mock.patch("install.sysconfig.get_path",
                        return_value=str(self.stdlib(True))), \
                mock.patch("install.sys.prefix", "/home/x/venv"), \
                mock.patch("install.sys.base_prefix", "/usr"):
            self.assertFalse(install.pip_externally_managed())


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

    def upgrade_after_uv_fails(self, managed):
        pip = [sys.executable, "-m", "pip", "install", "--user", "--upgrade"]
        calls = []

        def run(argv, check=False):
            calls.append(argv)
            if argv[0] == "uv":
                raise subprocess.CalledProcessError(1, argv)
            return subprocess.CompletedProcess(argv, 0)

        with mock.patch("install.cli_version", return_value="1.0.0"), \
                mock.patch("install.shutil.which", return_value="/bin/uv"), \
                mock.patch("install.find_cli", return_value="/bin/tool-y"), \
                mock.patch("install.UPGRADE_CMDS",
                           (["uv", "tool", "upgrade"], pip)), \
                mock.patch("install.pip_externally_managed",
                           return_value=managed), \
                mock.patch("install.warn") as warn, \
                mock.patch("install.subprocess.run", side_effect=run):
            status = install.upgrade_cli(self.fake_external(), "/bin/tool-y",
                                         dry_run=False)
        return status, [c[0] for c in calls], warn

    def test_managed_python_never_upgrades_with_pip(self):
        status, ran, warn = self.upgrade_after_uv_fails(managed=True)
        self.assertEqual(ran, ["uv"])
        self.assertEqual(status, "upgrade unavailable")
        self.assertNotIn("available", warn.call_args[0][0])

    def test_unmanaged_python_still_upgrades_with_pip(self):
        status, ran, warn = self.upgrade_after_uv_fails(managed=False)
        self.assertEqual(ran, ["uv", sys.executable])
        self.assertEqual(status, "already latest (1.0.0)")
        warn.assert_not_called()

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
                mock.patch("install.run_cali", return_value=0), \
                mock.patch("install.cali_status_rows", return_value=None), \
                mock.patch("install.apm_home", return_value=self.tmp / ".apm"), \
                mock.patch("install.apm_skills_root",
                           return_value=self.tmp / "agents"), \
                mock.patch("install.instruction_path",
                           return_value=self.tmp / "instr.md"), \
                mock.patch("install.claude_rules_path",
                           return_value=self.tmp / "rules.md"), \
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
    """REQUIRES must track real names, and cali.yaml must install every
    requirement wherever its dependent goes."""

    def test_keys_are_custom_skills(self):
        for skill in install.REQUIRES:
            with self.subTest(skill=skill):
                self.assertIn(skill, install.custom_skill_names())

    def test_requirements_are_live_for_every_target(self):
        deps = {d["name"]: d for d in install.manifest_deps() if d["active"]}
        both = {"claude", "copilot"}
        for skill, needs in install.REQUIRES.items():
            for dep in needs:
                with self.subTest(skill=skill, dep=dep):
                    self.assertIn(dep, deps)
                    self.assertLessEqual(
                        set(deps[skill]["targets"] or both),
                        set(deps[dep]["targets"] or both))


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
    cali.yaml, an external, another custom skill, or provided by a Claude
    plugin. A new chain to an unknown skill fails here, so it gets listed in
    cali.yaml instead of silently relying on a manual install."""

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
                self.assertIn(name, installable,
                              "add it to cali.yaml, "
                              "or list it in PLUGIN_PROVIDED/NOT_SKILLS")

    def test_scanner_still_sees_the_known_chains(self):
        # Guards the scanner itself: if a regex stops matching, the test
        # above would pass vacuously.
        found = self.referenced()
        for name in ("code-tour", "context-map", "caveman",
                     "acquire-codebase-knowledge", "write-pr-description",
                     "debugging-and-error-recovery", "find-skills"):
            with self.subTest(name):
                self.assertIn(name, found)


class TestParseManifest(unittest.TestCase):
    TEXT = """\
# header comment
version: 1
targets: [claude, copilot]
skills:
  # Own skills, from this clone.
  roj-explain-logic:
    source: .//skills/roj-explain-logic
  code-tour:
    source: github:github/awesome-copilot//skills/code-tour
    ref: 7cce7cfb4b61196c36d7e8eb8475ae84b356b126
  # Copilot only: Claude gets the equivalent from a plugin.
  caveman:  # Claude: caveman plugin
    source: https://github.com/juliusbrussee/caveman//skills/caveman
    ref: 2e08b9177c07bb7249a8a2d1a6758e5db281d002
    targets: [copilot]
  # Optional — uncomment the two lines and re-run install.py:
  # pdf:
  #   source: github:anthropics/skills//skills/pdf@683bc88e56f3e09ba94f7055977f3d3aa499f202
  # grill-me:  # Claude only: also uncomment the targets line
  #   source: github:mattpocock/skills//skills/productivity/grill-me@49dd158d1076134a641b33efb035946536778336
  #   targets: [claude]
"""

    def setUp(self):
        self.parsed = install.parse_manifest(self.TEXT)

    def test_own_skill_without_ref(self):
        dep = self.parsed[0]
        self.assertEqual(
            (dep["name"], dep["source"], dep["ref"], dep["targets"], dep["active"]),
            ("roj-explain-logic",
             ".//skills/roj-explain-logic",
             None, None, True))

    def test_ref_field(self):
        dep = self.parsed[1]
        self.assertEqual((dep["name"], dep["ref"]),
                         ("code-tour", "7cce7cfb4b61196c36d7e8eb8475ae84b356b126"))

    def test_targets_and_inline_comment(self):
        dep = self.parsed[2]
        self.assertEqual((dep["name"], dep["targets"], dep["active"]),
                         ("caveman", ("copilot",), True))
        self.assertEqual(dep["source"],
                         "https://github.com/juliusbrussee/caveman//skills/caveman")

    def test_commented_skill_is_inactive_and_ref_comes_from_the_source(self):
        dep = self.parsed[3]
        self.assertEqual((dep["name"], dep["active"], dep["ref"]),
                         ("pdf", False, "683bc88e56f3e09ba94f7055977f3d3aa499f202"))

    def test_commented_skill_keeps_its_targets(self):
        dep = self.parsed[4]
        self.assertEqual((dep["name"], dep["active"], dep["targets"]),
                         ("grill-me", False, ("claude",)))
        self.assertEqual(len(self.parsed), 5)

    def test_prose_comments_are_not_skills(self):
        names = [d["name"] for d in self.parsed]
        self.assertEqual(names, ["roj-explain-logic", "code-tour", "caveman",
                                 "pdf", "grill-me"])

    def test_top_level_key_ends_the_section(self):
        parsed = install.parse_manifest(self.TEXT + "sources:\n  - github:x/y\n")
        self.assertEqual(len(parsed), 5)

    def test_crlf_input(self):
        parsed = install.parse_manifest(self.TEXT.replace("\n", "\r\n"))
        self.assertEqual(parsed[1]["ref"],
                         "7cce7cfb4b61196c36d7e8eb8475ae84b356b126")

    def test_quoted_values_are_unquoted(self):
        parsed = install.parse_manifest(
            'skills:\n  tool:\n    source: "github:x/y//skills/tool"\n'
            "    ref: '2e08b9177c07bb7249a8a2d1a6758e5db281d002'\n")
        self.assertEqual((parsed[0]["source"], parsed[0]["ref"]),
                         ("github:x/y//skills/tool",
                          "2e08b9177c07bb7249a8a2d1a6758e5db281d002"))

    def test_only_roj_idea_to_project_installs_for_claude(self):
        # Copilot is the work agent; roj-idea-to-project alone serves both.
        self.assertEqual(install.managed_skill_names("claude"),
                         {"roj-idea-to-project"})
        self.assertLessEqual(install.custom_skill_names(),
                             install.managed_skill_names("copilot"))

    def test_repo_manifest_matches_its_lock(self):
        # cali sync --frozen would pass: every live skill is locked, nothing else.
        lock = json.loads((install.REPO_ROOT / "cali.lock").read_text("utf-8"))
        self.assertEqual(set(lock["skills"]), install.manifest_skill_names())

    def test_own_skills_are_locked_at_head(self):
        # The cali sync --frozen tree check, without cali: run
        # `cali update -g --manifest cali.yaml --apply` when this fails.
        lock = json.loads((install.REPO_ROOT / "cali.lock").read_text("utf-8"))
        for name, entry in lock["skills"].items():
            if entry["source"] != ".":
                continue
            with self.subTest(skill=name):
                tree = subprocess.run(
                    ["git", "rev-parse", "HEAD:" + entry["path"]],
                    cwd=install.REPO_ROOT, capture_output=True, text=True,
                    check=True).stdout.strip()
                self.assertEqual(entry["tree"], tree)


class TestCali(TempDirTest):
    def test_argv_points_at_the_repo_manifest(self):
        self.assertEqual(install.cali_argv("/bin/cali", "sync"),
                         ["/bin/cali", "sync", "-g", "--manifest",
                          str(install.MANIFEST_PATH)])

    def test_run_cali_returns_exit_code(self):
        with mock.patch("install.subprocess.run",
                        return_value=mock.Mock(returncode=3)) as run:
            self.assertEqual(install.run_cali(["cali", "x"]), 3)
        run.assert_called_once_with(["cali", "x"])

    def test_run_cali_reports_missing_binary(self):
        with mock.patch("install.subprocess.run", side_effect=OSError("nope")):
            self.assertEqual(install.run_cali(["cali"]), 127)

    def test_status_rows_from_json(self):
        out = json.dumps({"schema_version": 1, "rows": [
            {"skill": "a", "target": "claude", "states": ["ok"], "detail": ""},
            {"skill": "a", "target": "copilot", "states": ["base-lost"],
             "detail": "run cali sync"}], "warnings": []})
        with mock.patch("install.subprocess.run", return_value=mock.Mock(
                returncode=0, stdout=out)) as run:
            rows = install.cali_status_rows("/bin/cali")
        self.assertEqual(rows, {("a", "claude"): ("ok",),
                                ("a", "copilot"): ("base-lost",)})
        self.assertEqual(run.call_args[0][0],
                         install.cali_argv("/bin/cali", "status", "--offline",
                                           "--json"))

    def test_status_rows_none_when_cali_fails(self):
        for result in (mock.Mock(returncode=1, stdout=""),
                       mock.Mock(returncode=0, stdout="not json"),
                       OSError("nope")):
            with self.subTest(result=result), mock.patch(
                    "install.subprocess.run",
                    side_effect=result if isinstance(result, Exception) else None,
                    return_value=result):
                self.assertIsNone(install.cali_status_rows("/bin/cali"))

    def test_github_token_prefers_env(self):
        with mock.patch.dict(install.os.environ, {"token": "from-env"}), \
                mock.patch("install.subprocess.run") as run:
            self.assertEqual(install.github_token(), "from-env")
        run.assert_not_called()

    def test_github_token_from_gh_cli(self):
        env = {k: v for k, v in install.os.environ.items() if k != "token"}
        with mock.patch.dict(install.os.environ, env, clear=True), \
                mock.patch("install.shutil.which", return_value="/bin/gh"), \
                mock.patch("install.subprocess.run", return_value=mock.Mock(
                    returncode=0, stdout="gho_abc\n")):
            self.assertEqual(install.github_token(), "gho_abc")

    def test_github_token_none_without_login(self):
        env = {k: v for k, v in install.os.environ.items() if k != "token"}
        for which, run in ((None, None),
                           ("/bin/gh", mock.Mock(returncode=1, stdout="")),
                           ("/bin/gh", OSError("boom"))):
            with self.subTest(which=which, run=run), \
                    mock.patch.dict(install.os.environ, env, clear=True), \
                    mock.patch("install.shutil.which", return_value=which), \
                    mock.patch("install.subprocess.run",
                               side_effect=run if isinstance(run, Exception)
                               else None, return_value=run):
                self.assertIsNone(install.github_token())

    def test_is_wsl(self):
        for platform, text, expected in (("linux", "Linux 5.15 microsoft-standard-WSL2", True),
                                         ("linux", "Linux 6.1 generic", False),
                                         ("darwin", "microsoft", False)):
            with self.subTest(platform=platform, text=text), \
                    mock.patch("install.sys.platform", platform), \
                    mock.patch("install.Path.read_text", return_value=text):
                self.assertEqual(install.is_wsl(), expected)


class TestMcp(TempDirTest):
    def setUp(self):
        super().setUp()
        self.paths = {"claude": self.tmp / ".claude.json",
                      "copilot": self.tmp / ".copilot" / "mcp-config.json"}
        p = mock.patch("install.mcp_config_path",
                       side_effect=lambda t: self.paths[t])
        p.start()
        self.addCleanup(p.stop)

    def register(self, target, dry_run=False):
        err = io.StringIO()
        with mock.patch("sys.stderr", err):
            results = install.register_mcp_servers(target, dry_run)
        return results, err.getvalue()

    def test_claude_entry_added_and_other_keys_kept(self):
        self.paths["claude"].write_text(json.dumps(
            {"numStartups": 3, "mcpServers": {"other": {"command": "x"}}}))
        results, _ = self.register("claude")
        data = json.loads(self.paths["claude"].read_text())
        self.assertEqual(data["numStartups"], 3)
        self.assertEqual(data["mcpServers"]["other"], {"command": "x"})
        self.assertEqual(data["mcpServers"]["github-mcp-server"],
                         {"type": "http",
                          "url": "https://api.githubcopilot.com/mcp/"})
        self.assertEqual(results, [("claude", "mcp:github-mcp-server", "added")])

    def test_copilot_file_created_with_tools(self):
        results, _ = self.register("copilot")
        data = json.loads(self.paths["copilot"].read_text())
        self.assertEqual(data, {"mcpServers": {"github-mcp-server": {
            "type": "http", "url": "https://api.githubcopilot.com/mcp/",
            "tools": ["*"]}}})
        self.assertEqual(results, [("copilot", "mcp:github-mcp-server", "added")])

    def test_existing_entry_left_alone(self):
        mine = {"mcpServers": {"github-mcp-server": {"type": "http", "url": "u",
                                                     "headers": {"A": "b"}}}}
        self.paths["claude"].write_text(json.dumps(mine))
        before = self.paths["claude"].read_text()
        results, _ = self.register("claude")
        self.assertEqual(self.paths["claude"].read_text(), before)
        self.assertEqual(results, [("claude", "mcp:github-mcp-server",
                                    "already configured")])

    def test_invalid_json_is_never_overwritten(self):
        self.paths["claude"].write_text("{not json")
        results, err = self.register("claude")
        self.assertEqual(self.paths["claude"].read_text(), "{not json")
        self.assertEqual(results, [])
        self.assertIn("not valid JSON", err)

    def test_non_object_servers_are_never_overwritten(self):
        self.paths["claude"].write_text('{"mcpServers": []}')
        results, err = self.register("claude")
        self.assertEqual(self.paths["claude"].read_text(), '{"mcpServers": []}')
        self.assertEqual(results, [])
        self.assertIn("mcpServers", err)

    def test_dry_run_writes_nothing(self):
        results, _ = self.register("copilot", dry_run=True)
        self.assertFalse(self.paths["copilot"].exists())
        self.assertEqual(results, [("copilot", "mcp:github-mcp-server", "added")])



class TestMcpPaths(unittest.TestCase):
    def test_real_paths(self):
        with mock.patch("install.Path.home", return_value=Path("/h")):
            self.assertEqual(install.mcp_config_path("claude"),
                             Path("/h/.claude.json"))
            self.assertEqual(install.mcp_config_path("copilot"),
                             Path("/h/.copilot/mcp-config.json"))


OWNED = "---\nname: {}\ndescription: x\n---\n"


def rows(state, *names, targets=("claude", "copilot")):
    """cali_status_rows() output: every name in every target in one state."""
    return {(n, t): (state,) for n in names for t in targets}


class TestLegacyCleanup(TempDirTest):
    def setUp(self):
        super().setUp()
        self.clone_skills = self.tmp / "clone" / "skills"
        self.make_skill("clone/skills", name="roj-a")
        deps = [
            {"name": "roj-a", "source": "github:o/r//skills/roj-a",
             "ref": None, "active": True, "targets": None},
            {"name": "code-tour", "source": "github:x/y//skills/code-tour",
             "ref": "a" * 40, "active": True, "targets": None},
            {"name": "caveman", "source": "https://x/caveman//skills/caveman",
             "ref": "b" * 40, "active": True, "targets": ("copilot",)},
            {"name": "roj-b", "source": "github:o/r//skills/roj-b",
             "ref": None, "active": True, "targets": ("copilot",)},
            {"name": "pdf", "source": "github:a/s//skills/pdf@" + "c" * 40,
             "ref": "c" * 40, "active": False, "targets": None}]
        # Every move lands in the temp dir, never the real ~/.agent-skills-backups.
        self.backups = self.tmp / "backups"
        for p in (mock.patch("install.SKILLS_SRC", self.clone_skills),
                  mock.patch("install.manifest_deps", return_value=deps),
                  mock.patch("install.backup_dir", return_value=self.backups)):
            p.start()
            self.addCleanup(p.stop)

    NOT_INSTALLED = rows("base-lost", "roj-a", "code-tour", "caveman")

    def cleanup(self, target, root, cali_rows=NOT_INSTALLED, dry_run=False):
        err = io.StringIO()
        with mock.patch("sys.stderr", err):
            results = install.remove_installer_skills(
                target, root, dry_run, cali_rows=cali_rows)
        return results, err.getvalue()

    def link(self, entry, to):
        entry.parent.mkdir(parents=True, exist_ok=True)
        try:
            entry.symlink_to(to, target_is_directory=True)
        except OSError:
            self.skipTest("symlinks unsupported here")

    def test_stale_names_are_other_target_skills_and_retired_ones(self):
        retired = {"add-educational-comments", "arch-linux-triage",
                   "architecture-blueprint-generator", "centos-linux-triage",
                   "debian-linux-triage", "fedora-linux-triage",
                   "roj-code-review-pr-fast", "roj-tour-codebase"}
        # caveman was Copilot only before: no install put it in Claude.
        self.assertEqual(install.stale_skill_names("claude"), {"roj-b"} | retired)
        self.assertEqual(install.stale_skill_names("copilot"), retired)

    def test_legacy_names_are_custom_plus_manifest(self):
        self.assertEqual(install.legacy_skill_names(),
                         {"roj-a", "code-tour", "caveman", "roj-b", "pdf"})

    def test_managed_names_follow_active_deps_and_targets(self):
        self.assertEqual(install.managed_skill_names("claude"),
                         {"roj-a", "code-tour"})
        self.assertEqual(install.managed_skill_names("copilot"),
                         {"roj-a", "code-tour", "caveman", "roj-b"})

    def test_symlink_into_clone_always_removed(self):
        root = self.tmp / "claude"
        self.link(root / "roj-a", self.clone_skills / "roj-a")
        results, _ = self.cleanup("claude", root, cali_rows=None)
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

    def test_copy_cali_did_not_install_is_moved_to_a_backup(self):
        # base-lost also means a Cali folder whose data dir was wiped, so the
        # copy may hold local edits: it is moved aside, never deleted.
        for target in ("claude", "copilot"):
            with self.subTest(target=target):
                self.make_skill(target, name="code-tour",
                                content=OWNED.format("code-tour") + "my edit\n")
                results, _ = self.cleanup(target, self.tmp / target)
                self.assertFalse((self.tmp / target / "code-tour").exists())
                kept = self.backups / target / "code-tour" / "SKILL.md"
                self.assertEqual(kept.read_text(encoding="utf-8"),
                                 OWNED.format("code-tour") + "my edit\n")
                self.assertEqual(results, [(target, "code-tour",
                                            f"moved to {kept.parent} (not installed by Cali)")])

    def test_dry_run_moves_nothing(self):
        self.make_skill("claude", name="code-tour", content=OWNED.format("code-tour"))
        self.cleanup("claude", self.tmp / "claude", dry_run=True)
        self.assertTrue((self.tmp / "claude" / "code-tour").is_dir())
        self.assertFalse(self.backups.exists())

    def test_unlocked_copy_is_removed(self):
        # A skill just uncommented in cali.yaml: Cali would refuse to replace
        # an old copy that differs, so it goes first.
        self.make_skill("claude", name="code-tour", content=OWNED.format("code-tour"))
        results, _ = self.cleanup("claude", self.tmp / "claude",
                                  cali_rows=rows("unlocked", "code-tour"))
        self.assertFalse((self.tmp / "claude" / "code-tour").exists())
        self.assertEqual(len(results), 1)

    def test_copy_cali_installed_is_kept(self):
        for state in ("ok", "modified", "outdated"):
            with self.subTest(state=state):
                self.make_skill(f"claude-{state}", name="code-tour",
                                content=OWNED.format("code-tour"))
                results, err = self.cleanup(
                    "claude", self.tmp / f"claude-{state}",
                    cali_rows=rows(state, "code-tour"))
                self.assertTrue((self.tmp / f"claude-{state}" / "code-tour").is_dir())
                self.assertEqual((results, err), ([], ""))

    def test_copies_kept_without_cali_status(self):
        self.make_skill("copilot", name="code-tour", content=OWNED.format("code-tour"))
        results, _ = self.cleanup("copilot", self.tmp / "copilot", cali_rows=None)
        self.assertTrue((self.tmp / "copilot" / "code-tour").is_dir())
        self.assertEqual(results, [])

    def test_optional_skill_copy_kept_with_warning(self):
        # pdf is commented out in cali.yaml: Cali would not put it back.
        self.make_skill("claude", name="pdf", content=OWNED.format("pdf"))
        results, err = self.cleanup("claude", self.tmp / "claude")
        self.assertTrue((self.tmp / "claude" / "pdf").is_dir())
        self.assertEqual(results, [])
        self.assertIn("Cali does not manage pdf for claude", err)
        self.assertIn("uncomment it in cali.yaml", err)
        self.assertEqual(err.count("[ warn ]"), 1)

    def test_stale_copy_kept_and_listed_with_its_path(self):
        # cali status drops a host's row once cali.yaml drops the host, so
        # nothing shows who put a real folder there: it is only reported.
        # (A retired skill that declares its own name is moved: see below.)
        for target, name, content in (
                ("claude", "roj-b", OWNED.format("roj-b")),
                ("claude", "roj-b", OWNED.format("my-roj-b")),
                ("claude", "debian-linux-triage", OWNED.format("my-debian")),
                ("copilot", "debian-linux-triage", OWNED.format("my-debian")),
                ("copilot", "roj-code-review-pr-fast", OWNED.format("mine"))):
            with self.subTest(target=target, name=name, content=content):
                root = self.tmp / "roots" / f"{target}-{len(content)}"
                shutil.rmtree(root, ignore_errors=True)
                self.make_skill(f"roots/{target}-{len(content)}", name=name,
                                content=content)
                results, err = self.cleanup(target, root,
                                            cali_rows=rows("ok", name))
                self.assertTrue((root / name / "SKILL.md").is_file())
                self.assertEqual(results, [])
                self.assertIn(f"{root / name} is left over", err)
                self.assertIn("delete it if it is stale", err)
                self.assertEqual(err.count("[ warn ]"), 1)
                self.assertFalse(self.backups.exists())

    def test_retired_skill_we_installed_is_moved_to_a_backup(self):
        for target, name in (("copilot", "roj-tour-codebase"),
                             ("copilot", "roj-code-review-pr-fast"),
                             ("claude", "debian-linux-triage")):
            with self.subTest(target=target, name=name):
                root = self.tmp / "roots" / f"{target}-{name}"
                self.make_skill(f"roots/{target}-{name}", name=name,
                                content=OWNED.format(name) + "body\n")
                results, err = self.cleanup(target, root,
                                            cali_rows=rows("ok", name))
                kept = self.backups / target / name
                self.assertFalse((root / name).exists())
                self.assertEqual((kept / "SKILL.md").read_text(encoding="utf-8"),
                                 OWNED.format(name) + "body\n")
                self.assertEqual(results, [(target, name,
                                            f"moved to {kept} (retired skill)")])
                self.assertEqual(err, "")

    def test_retired_skill_dry_run_lists_the_move_and_moves_nothing(self):
        root = self.tmp / "copilot"
        self.make_skill("copilot", name="roj-tour-codebase",
                        content=OWNED.format("roj-tour-codebase"))
        results, err = self.cleanup("copilot", root, dry_run=True)
        self.assertTrue((root / "roj-tour-codebase" / "SKILL.md").is_file())
        self.assertFalse(self.backups.exists())
        self.assertEqual(results, [(
            "copilot", "roj-tour-codebase",
            f"moved to {self.backups / 'copilot' / 'roj-tour-codebase'} "
            "(retired skill)")])
        self.assertEqual(err, "")

    def test_retired_move_leaves_other_folders_untouched(self):
        root = self.tmp / "copilot"
        for name in ("roj-tour-codebase", "my-own", "graphify", "roj-a"):
            self.make_skill("copilot", name=name, content=OWNED.format(name))
        self.make_skill("copilot", name="roj-tour-codebase-2",
                        content=OWNED.format("roj-tour-codebase-2"))
        results, _ = self.cleanup("copilot", root, cali_rows=rows("ok", "roj-a"))
        self.assertEqual([n for _, n, _ in results], ["roj-tour-codebase"])
        for name in ("my-own", "graphify", "roj-a", "roj-tour-codebase-2"):
            self.assertTrue((root / name / "SKILL.md").is_file(), name)

    def test_copilot_only_skill_copy_kept_for_claude(self):
        self.make_skill("claude", name="caveman", content=OWNED.format("caveman"))
        results, err = self.cleanup("claude", self.tmp / "claude")
        self.assertTrue((self.tmp / "claude" / "caveman").is_dir())
        self.assertEqual(results, [])
        self.assertIn("Cali does not manage caveman for claude", err)
        self.assertFalse(self.backups.exists())

    def test_link_of_a_stale_skill_moved_aside(self):
        root = self.tmp / "claude"
        self.link(root / "roj-b", self.tmp / "gone" / "roj-b")
        results, _ = self.cleanup("claude", root, cali_rows=None)
        self.assertFalse((root / "roj-b").is_symlink())
        kept = self.backups / "claude" / "roj-b"
        self.assertTrue(kept.is_symlink())
        self.assertEqual(results, [("claude", "roj-b",
                                    f"moved to {kept} (not installed for claude)")])

    def test_unknown_folders_never_touched_for_claude(self):
        for name in ("no-mistakes", "synced"):
            self.make_skill("claude", name=name, content=OWNED.format(name))
        results, err = self.cleanup("claude", self.tmp / "claude",
                                    cali_rows=rows("ok", "no-mistakes", "synced"))
        self.assertEqual((results, err), ([], ""))
        for name in ("no-mistakes", "synced"):
            self.assertTrue((self.tmp / "claude" / name / "SKILL.md").is_file())
        self.assertFalse(self.backups.exists())

    def test_dry_run_moves_no_stale_link(self):
        root = self.tmp / "claude"
        self.link(root / "roj-b", self.tmp / "gone" / "roj-b")
        results, _ = self.cleanup("claude", root, dry_run=True)
        self.assertTrue((root / "roj-b").is_symlink())
        self.assertFalse(self.backups.exists())
        self.assertTrue(results[0][2].startswith("moved to "))

    def test_copilot_only_skill_copy_removed_for_copilot(self):
        self.make_skill("copilot", name="caveman", content=OWNED.format("caveman"))
        results, _ = self.cleanup("copilot", self.tmp / "copilot")
        self.assertFalse((self.tmp / "copilot" / "caveman").exists())
        self.assertEqual(len(results), 1)
        self.assertTrue(results[0][2].startswith("moved to "))

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
        results, _ = self.cleanup("claude", root, cali_rows=None)
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


class TestApmLeftovers(TempDirTest):
    """APM deployed Copilot skills to ~/.agents/skills; Cali deploys them to
    ~/.copilot/skills, so APM's copies would load twice."""

    LOCK = "deployed_files:\n  - .agents/skills/{}/SKILL.md\n"

    def setUp(self):
        super().setUp()
        self.root = self.tmp / "agents"
        for p in (mock.patch("install.apm_skills_root", return_value=self.root),
                  mock.patch("install.managed_skill_names",
                             return_value={"code-tour", "caveman"})):
            p.start()
            self.addCleanup(p.stop)

    def test_copy_the_lockfile_lists_is_removed(self):
        self.make_skill("agents", name="code-tour")
        results = install.remove_apm_skills(False, self.LOCK.format("code-tour"))
        self.assertFalse((self.root / "code-tour").exists())
        self.assertEqual(results, [("copilot", "code-tour",
                                    "removed (APM copy in ~/.agents/skills)")])

    def test_copy_the_lockfile_does_not_list_is_kept(self):
        self.make_skill("agents", name="code-tour")
        for lock in (None, self.LOCK.format("caveman"),
                     self.LOCK.format("code-tour-x"),
                     "  - .claude/skills/code-tour/SKILL.md\n"):
            with self.subTest(lock=lock):
                self.assertEqual(install.remove_apm_skills(False, lock), [])
                self.assertTrue((self.root / "code-tour").is_dir())

    def test_windows_separators_count(self):
        self.make_skill("agents", name="code-tour")
        install.remove_apm_skills(
            False, "  - C:\\Users\\me\\.agents\\skills\\code-tour\\SKILL.md\n")
        self.assertFalse((self.root / "code-tour").exists())

    def test_unmanaged_name_is_kept(self):
        self.make_skill("agents", name="orca-cli")
        self.assertEqual(install.remove_apm_skills(
            False, self.LOCK.format("orca-cli")), [])
        self.assertTrue((self.root / "orca-cli").is_dir())

    def test_symlink_is_kept(self):
        target = self.make_skill("elsewhere", name="code-tour")
        self.root.mkdir()
        try:
            (self.root / "code-tour").symlink_to(target, target_is_directory=True)
        except OSError:
            self.skipTest("symlinks unsupported here")
        self.assertEqual(install.remove_apm_skills(
            False, self.LOCK.format("code-tour")), [])
        self.assertTrue((self.root / "code-tour").is_symlink())

    def test_dry_run_removes_nothing(self):
        self.make_skill("agents", name="code-tour")
        results = install.remove_apm_skills(True, self.LOCK.format("code-tour"))
        self.assertTrue((self.root / "code-tour").is_dir())
        self.assertEqual(len(results), 1)

    def test_missing_root_is_fine(self):
        self.assertEqual(install.remove_apm_skills(
            False, self.LOCK.format("code-tour")), [])


class TestInstructions(TempDirTest):
    SRC = '---\napplyTo: "**"\ndescription: Mine.\n---\n\n# Rules\n'

    def setUp(self):
        super().setUp()
        self.src = self.tmp / "clone" / "personal.instructions.md"
        self.src.parent.mkdir(parents=True)
        self.src.write_text(self.SRC)
        self.dest = {
            "copilot": self.tmp / "home" / ".copilot" / "instructions"
                       / "personal.instructions.md",
            "claude": None}
        for p in (mock.patch("install.INSTRUCTIONS_SRC", self.src),
                  mock.patch("install.instruction_path",
                             side_effect=lambda t: self.dest[t]),
                  mock.patch("install.shipped_instructions",
                             return_value={self.SRC, "old rules\n"})):
            p.start()
            self.addCleanup(p.stop)

    def deploy(self, target, dry_run=False):
        err = io.StringIO()
        with mock.patch("sys.stderr", err):
            results = install.install_instructions(target, dry_run)
        return results, err.getvalue()

    def test_claude_gets_no_instructions(self):
        results, err = self.deploy("claude")
        self.assertEqual((results, err), ([], ""))

    def test_installed_when_absent(self):
        results, _ = self.deploy("copilot")
        self.assertEqual(self.dest["copilot"].read_text(), self.SRC)
        self.assertEqual(results, [("copilot", self.dest["copilot"].name,
                                    "installed")])

    def test_up_to_date_is_silent(self):
        self.deploy("copilot")
        self.assertEqual(self.deploy("copilot"), ([], ""))

    def test_older_shipped_version_is_updated(self):
        self.dest["copilot"].parent.mkdir(parents=True)
        self.dest["copilot"].write_text("old rules\n")
        results, _ = self.deploy("copilot")
        self.assertEqual(self.dest["copilot"].read_text(), self.SRC)
        self.assertEqual(results[0][2], "updated")

    def test_edited_copy_kept_with_warning(self):
        self.dest["copilot"].parent.mkdir(parents=True)
        self.dest["copilot"].write_text("my local edits\n")
        results, err = self.deploy("copilot")
        self.assertEqual(self.dest["copilot"].read_text(), "my local edits\n")
        self.assertIn("differs", err)
        self.assertEqual(results, [])

    def test_dotfiles_link_replaced(self):
        other = self.tmp / "dotfiles" / "copilot" / "personal.instructions.md"
        other.parent.mkdir(parents=True)
        other.write_text("rules\n")
        (self.tmp / "dotfiles" / "install.py").write_text("")
        self.dest["copilot"].parent.mkdir(parents=True)
        try:
            self.dest["copilot"].symlink_to(other)
        except OSError:
            self.skipTest("symlinks unsupported here")
        results, _ = self.deploy("copilot")
        self.assertFalse(self.dest["copilot"].is_symlink())
        self.assertEqual(self.dest["copilot"].read_text(), self.SRC)
        self.assertEqual(other.read_text(), "rules\n")
        self.assertEqual(results[0][2], "replaced dotfiles link")

    def test_unrelated_symlink_kept_with_warning(self):
        mine = self.tmp / "mine" / "personal.instructions.md"
        mine.parent.mkdir()
        mine.write_text("my rules\n")
        self.dest["copilot"].parent.mkdir(parents=True)
        try:
            self.dest["copilot"].symlink_to(mine)
        except OSError:
            self.skipTest("symlinks unsupported here")
        results, err = self.deploy("copilot")
        self.assertTrue(self.dest["copilot"].is_symlink())
        self.assertEqual(results, [])
        self.assertIn("other than the dotfiles repo", err)

    def test_dry_run_writes_nothing(self):
        results, _ = self.deploy("copilot", dry_run=True)
        self.assertFalse(self.dest["copilot"].exists())
        self.assertEqual(results[0][2], "installed")


class TestRetireClaudeRules(TempDirTest):
    SRC = '---\napplyTo: "**"\ndescription: Mine.\n---\n\n# Rules\n'
    # What earlier versions deployed: applyTo turned into paths, description
    # dropped.
    DEPLOYED = '---\npaths:\n  - "**"\n---\n\n# Rules\n'

    def setUp(self):
        super().setUp()
        self.rules = self.tmp / "home" / ".claude" / "rules" / "personal.md"
        self.rules.parent.mkdir(parents=True)
        self.backups = self.tmp / "backups"
        for p in (mock.patch("install.claude_rules_path", return_value=self.rules),
                  mock.patch("install.backup_dir", return_value=self.backups),
                  mock.patch("install.shipped_instructions",
                             return_value={self.SRC, "old rules\n"})):
            p.start()
            self.addCleanup(p.stop)

    def retire(self, dry_run=False):
        err = io.StringIO()
        with mock.patch("sys.stderr", err):
            results = install.retire_claude_rules(dry_run)
        return results, err.getvalue()

    def test_shipped_versions_moved_aside(self):
        for text in (self.DEPLOYED, "\n# Rules\n", "old rules\n"):
            with self.subTest(text=text):
                self.rules.write_text(text)
                results, err = self.retire()
                kept = self.backups / "claude" / "personal.md"
                self.assertFalse(self.rules.exists())
                self.assertEqual(kept.read_text(), text)
                self.assertEqual(results, [("claude", "personal.md",
                                            f"moved to {kept} (Claude gets none)")])
                self.assertEqual(err, "")
                shutil.rmtree(self.backups)

    def test_edited_copy_kept_with_warning(self):
        self.rules.write_text(self.DEPLOYED + "my rule\n")
        results, err = self.retire()
        self.assertEqual(self.rules.read_text(), self.DEPLOYED + "my rule\n")
        self.assertEqual(results, [])
        self.assertIn("differs from every version", err)
        self.assertFalse(self.backups.exists())

    def test_link_kept_with_warning(self):
        mine = self.tmp / "mine.md"
        mine.write_text(self.DEPLOYED)
        try:
            self.rules.symlink_to(mine)
        except OSError:
            self.skipTest("symlinks unsupported here")
        results, err = self.retire()
        self.assertTrue(self.rules.is_symlink())
        self.assertEqual(results, [])
        self.assertIn("is a link", err)

    def test_dry_run_moves_nothing(self):
        self.rules.write_text(self.DEPLOYED)
        results, _ = self.retire(dry_run=True)
        self.assertTrue(self.rules.is_file())
        self.assertFalse(self.backups.exists())
        self.assertEqual(len(results), 1)

    def test_missing_file_is_fine(self):
        self.assertEqual(self.retire(), ([], ""))

    def test_real_path(self):
        mock.patch.stopall()
        with mock.patch("install.Path.home", return_value=Path("/h")):
            self.assertEqual(install.claude_rules_path(),
                             Path("/h/.claude/rules/personal.md"))



class TestInstructionSources(unittest.TestCase):
    def test_shipped_versions_include_the_current_file(self):
        shipped = install.shipped_instructions()
        self.assertIn(install.INSTRUCTIONS_SRC.read_text(encoding="utf-8"),
                      shipped)

    def test_real_paths(self):
        with mock.patch("install.Path.home", return_value=Path("/h")):
            self.assertIsNone(install.instruction_path("claude"))
            self.assertEqual(install.instruction_path("copilot"),
                             Path("/h/.copilot/instructions/personal.instructions.md"))


class TestMain(TempDirTest):
    """main() end to end with cali, externals and homes faked."""

    def run_main(self, argv, cali="/bin/cali", cali_code=0, lock=False,
                 wsl=False, externals=(), bootstrap=None, token="tok",
                 cali_rows=None, userprofile=None):
        home = self.tmp / "home"
        (home / ".apm").mkdir(parents=True, exist_ok=True)
        if lock:
            (home / ".apm" / "apm.lock.yaml").write_text(
                lock if isinstance(lock, str) else "x")
        calls = []

        def fake_run(cmd):
            calls.append(list(cmd))
            return cali_code

        out, err = io.StringIO(), io.StringIO()
        code = 0
        with contextlib.ExitStack() as stack:
            for p in (
                mock.patch("install.apm_home", return_value=home / ".apm"),
                mock.patch("install.apm_skills_root", return_value=home / "agents"),
                mock.patch("install.target_root",
                           side_effect=lambda t: home / t),
                mock.patch("install.instruction_path",
                           side_effect=lambda t: None if t == "claude"
                           else home / "instr" / f"{t}.md"),
                mock.patch("install.mcp_config_path",
                           side_effect=lambda t: home / f"mcp-{t}.json"),
                mock.patch("install.claude_commands_dir",
                           return_value=home / "commands"),
                mock.patch("install.claude_rules_path",
                           return_value=home / "rules" / "personal.md"),
                mock.patch("install.backup_dir",
                           side_effect=lambda h=None: (h or home) / "backups"),
                mock.patch("install.windows_userprofile",
                           return_value=userprofile),
                mock.patch("install.find_cli",
                           side_effect=lambda n: cali if n == "cali" else None),
                mock.patch("install.run_cali", side_effect=fake_run),
                mock.patch("install.cali_status_rows",
                           return_value={} if cali_rows is None else cali_rows),
                mock.patch("install.github_token", return_value=token),
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

    def cali(self, *args):
        return install.cali_argv("/bin/cali", *args)

    def test_default_installs_both(self):
        code, calls, _, _ = self.run_main([])
        home = self.tmp / "home"
        self.assertEqual(code, 0)
        self.assertEqual(calls, [self.cali("sync")])
        self.assertTrue((home / "instr" / "copilot.md").is_file())
        self.assertFalse((home / "instr" / "claude.md").exists())
        for t in ("claude", "copilot"):
            with self.subTest(target=t):
                servers = json.loads((home / f"mcp-{t}.json").read_text())
                self.assertIn("github-mcp-server", servers["mcpServers"])

    def test_no_token_skips_mcp(self):
        code, calls, out, _ = self.run_main([], token=None)
        self.assertEqual(code, 0)
        self.assertEqual(calls, [self.cali("sync")])
        self.assertIn("skipping MCP servers", out)
        self.assertFalse((self.tmp / "home" / "mcp-claude.json").exists())

    def test_single_target_limits_everything_but_cali(self):
        # cali sync has no --target: it installs every target cali.yaml names.
        _, calls, _, _ = self.run_main(["--target", "copilot"])
        home = self.tmp / "home"
        self.assertEqual(calls, [self.cali("sync")])
        self.assertTrue((home / "mcp-copilot.json").exists())
        self.assertFalse((home / "mcp-claude.json").exists())
        self.assertFalse((home / "instr" / "claude.md").exists())

    def test_missing_cali_stops_with_hint_before_cleanup(self):
        self.make_skill("home/copilot", name="code-tour",
                        content=OWNED.format("code-tour"))
        code, calls, _, err = self.run_main(
            ["--target", "copilot"], cali=None,
            cali_rows=rows("base-lost", "code-tour"))
        self.assertEqual(code, 1)
        self.assertEqual(calls, [])
        self.assertIn("https://github.com/rojcarranza/cali", err)
        self.assertTrue((self.tmp / "home" / "copilot" / "code-tour").exists())

    def test_dry_run_without_cali_prints_plan(self):
        code, calls, out, err = self.run_main(["--dry-run"], cali=None)
        self.assertEqual(code, 0)
        self.assertEqual(calls, [])
        self.assertIn("cali is not installed", err)
        self.assertIn("would run cali sync -g --manifest", out)
        self.assertFalse((self.tmp / "home" / "instr").exists())
        self.assertFalse((self.tmp / "home" / "mcp-claude.json").exists())

    def test_cali_failure_is_the_exit_code(self):
        code, _, _, err = self.run_main([], cali_code=2)
        self.assertEqual(code, 2)
        self.assertIn("cali sync failed", err)
        self.assertIn("once a re-run of install.py succeeds", err)

    def test_update_reports_through_cali_status(self):
        for cali_code in (0, 1):
            with self.subTest(cali_code=cali_code):
                code, calls, _, _ = self.run_main(["--update"],
                                                  cali_code=cali_code)
                self.assertEqual(calls, [self.cali("status")])
                self.assertEqual(code, cali_code)

    def test_update_without_cali_stops_with_hint(self):
        code, calls, _, err = self.run_main(["--update"], cali=None)
        self.assertEqual(code, 1)
        self.assertEqual(calls, [])
        self.assertIn("https://github.com/rojcarranza/cali", err)

    def test_update_dry_run_runs_nothing(self):
        code, calls, out, _ = self.run_main(["--update", "--dry-run"])
        self.assertEqual(code, 0)
        self.assertEqual(calls, [])
        self.assertIn("would run cali status -g --manifest", out)

    def test_status_lists_cali_skills(self):
        _, calls, _, _ = self.run_main(["--status"])
        self.assertEqual(calls, [self.cali("list")])

    def test_status_without_cali_warns_and_succeeds(self):
        code, calls, _, err = self.run_main(["--status"], cali=None)
        self.assertEqual(code, 0)
        self.assertEqual(calls, [])
        self.assertIn("cali is not installed", err)

    def test_skills_only_never_bootstraps_externals(self):
        ext = ExternalTest.fake_external(None)
        boots = []
        code, _, out, _ = self.run_main(
            ["--skills-only", "--target", "claude"], externals=[ext],
            bootstrap=lambda e, dry: boots.append(e["name"]))
        self.assertEqual(code, 0)
        self.assertEqual(boots, [])
        self.assertIn("--skills-only", out)

    def test_copy_cali_installed_survives_install(self):
        self.make_skill("home/claude", name="roj-idea-to-project",
                        content=OWNED.format("roj-idea-to-project"))
        self.run_main(["--target", "claude"],
                      cali_rows=rows("ok", "roj-idea-to-project"))
        self.assertTrue((self.tmp / "home" / "claude" / "roj-idea-to-project").is_dir())

    def test_copy_cali_did_not_install_is_cleared_before_sync(self):
        self.make_skill("home/copilot", name="code-tour",
                        content=OWNED.format("code-tour"))
        self.run_main(["--target", "copilot"],
                      cali_rows=rows("base-lost", "code-tour"))
        self.assertFalse((self.tmp / "home" / "copilot" / "code-tour").exists())
        self.assertTrue((self.tmp / "home" / "backups" / "copilot" / "code-tour"
                         / "SKILL.md").is_file())

    def test_apm_copilot_copies_removed_for_copilot_only(self):
        lock = "  - .agents/skills/code-tour/SKILL.md\n"
        self.make_skill("home/agents", name="code-tour")
        self.run_main(["--target", "claude"], lock=lock)
        self.assertTrue((self.tmp / "home" / "agents" / "code-tour").is_dir())
        self.run_main(["--target", "copilot"], lock=lock)
        self.assertFalse((self.tmp / "home" / "agents" / "code-tour").exists())

    def test_status_warns_about_apm_copies(self):
        self.make_skill("home/agents", name="code-tour")
        _, _, _, err = self.run_main(
            ["--status", "--target", "copilot"],
            lock="  - .agents/skills/code-tour/SKILL.md\n")
        self.assertIn("code-tour left by an older install", err)
        self.assertTrue((self.tmp / "home" / "agents" / "code-tour").is_dir())

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

    def test_status_warns_about_dotfiles_instruction_link(self):
        dotfiles = self.tmp / "dotfiles"
        (dotfiles / "copilot").mkdir(parents=True)
        (dotfiles / "install.py").write_text("")
        linked = dotfiles / "copilot" / "copilot.md"
        linked.write_text("x\n")
        dest = self.tmp / "home" / "instr" / "copilot.md"
        dest.parent.mkdir(parents=True)
        try:
            dest.symlink_to(linked)
        except OSError:
            self.skipTest("symlinks unsupported here")
        _, _, _, err = self.run_main(["--status", "--target", "copilot"])
        self.assertIn("copilot.md left by an older install", err)
        self.assertTrue(dest.is_symlink())

    def test_status_warns_about_undeployed_instructions(self):
        _, _, _, err = self.run_main(["--status", "--target", "copilot"])
        self.assertIn("copilot.md is not deployed or out of date — re-run "
                      "install.py", err)
        self.assertFalse((self.tmp / "home" / "instr").exists())

    def test_removed_flags_are_rejected(self):
        for flag in (["--repo", "."], ["--skill", "x"], ["--list"],
                     ["--uninstall", "x"], ["--add-inventory", "a/b@c"],
                     ["--check-inventory-updates"], ["--force"]):
            with self.subTest(flag=flag):
                code, calls, _, _ = self.run_main(flag)
                self.assertEqual(code, 2)
                self.assertEqual(calls, [])

    def test_wsl_hint_printed(self):
        _, _, out, _ = self.run_main([], wsl=True)
        self.assertIn("run install.py from Git Bash for those", out)

    def write_shipped_rules(self):
        rules = self.tmp / "home" / "rules" / "personal.md"
        rules.parent.mkdir(parents=True)
        rules.write_text(install.INSTRUCTIONS_SRC.read_text(encoding="utf-8"))
        return rules

    def test_claude_leftovers_listed_rules_moved_and_unknown_kept(self):
        home = self.tmp / "home"
        self.make_skill("home/claude", name="roj-explain-logic",
                        content=OWNED.format("roj-explain-logic"))
        self.make_skill("home/claude", name="no-mistakes",
                        content=OWNED.format("no-mistakes"))
        rules = self.write_shipped_rules()
        code, _, _, err = self.run_main(["--target", "claude"])
        self.assertEqual(code, 0)
        left = home / "claude" / "roj-explain-logic"
        self.assertTrue((left / "SKILL.md").is_file())
        self.assertIn(f"{left} is left over", err)
        self.assertFalse((home / "backups" / "claude" / "roj-explain-logic").exists())
        self.assertFalse(rules.exists())
        self.assertTrue((home / "backups" / "claude" / "personal.md").is_file())
        self.assertTrue((home / "claude" / "no-mistakes" / "SKILL.md").is_file())
        self.assertNotIn("no-mistakes", err)

    def test_status_and_dry_run_report_claude_leftovers_without_moving(self):
        home = self.tmp / "home"
        self.make_skill("home/claude", name="code-tour",
                        content=OWNED.format("code-tour"))
        rules = self.write_shipped_rules()
        left = home / "claude" / "code-tour"
        _, _, _, err = self.run_main(["--status", "--target", "claude"])
        self.assertIn(f"{left} is left over", err)
        self.assertIn("personal.md left by an older install", err)
        _, _, out, err = self.run_main(["--dry-run", "--target", "claude"])
        self.assertIn(f"{left} is left over", err)
        self.assertIn("personal.md", out)
        self.assertTrue((left / "SKILL.md").is_file())
        self.assertTrue(rules.is_file())
        self.assertFalse((home / "backups").exists())

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

class TestWindowsHomeResolution(TempDirTest):
    def fake_run(self, stdout=b"", code=0):
        return mock.Mock(stdout=stdout, returncode=code)

    def test_userprofile_read_through_cmd_exe(self):
        cmd = self.tmp / "cmd.exe"
        cmd.write_text("")
        for out in (b"C:\\Users\\rcarranz\r\n",
                    b"Active code page: 65001\r\nC:\\Users\\rcarranz\r\n"):
            with self.subTest(out=out), \
                 mock.patch("install.shutil.which", return_value=str(cmd)), \
                 mock.patch("install.subprocess.run",
                            return_value=self.fake_run(out)) as run:
                self.assertEqual(install.windows_userprofile(),
                                 "C:\\Users\\rcarranz")
                self.assertEqual(run.call_args[0][0][:2], [str(cmd), "/c"])

    def test_userprofile_none_without_interop_or_when_cmd_fails(self):
        with mock.patch("install.shutil.which", return_value=None), \
             mock.patch("install.os.path.isfile", return_value=False):
            self.assertIsNone(install.windows_userprofile())
        cmd = self.tmp / "cmd.exe"
        cmd.write_text("")
        with mock.patch("install.shutil.which", return_value=str(cmd)):
            for run in (mock.Mock(return_value=self.fake_run(b"%USERPROFILE%\r\n")),
                        mock.Mock(return_value=self.fake_run(b"x", code=1)),
                        mock.Mock(side_effect=OSError("no interop"))):
                with mock.patch("install.subprocess.run", run), \
                     mock.patch("install.os.path.isfile",
                                side_effect=lambda f: f == str(cmd)):
                    self.assertIsNone(install.windows_userprofile())

    def test_wsl_path_converts_through_wslpath(self):
        with mock.patch("install.shutil.which", return_value="/bin/wslpath"), \
             mock.patch("install.subprocess.run", return_value=mock.Mock(
                 stdout="/mnt/c/Users/rcarranz\n", returncode=0)) as run:
            self.assertEqual(install.wsl_path("C:\\Users\\rcarranz"),
                             Path("/mnt/c/Users/rcarranz"))
            self.assertEqual(run.call_args[0][0],
                             ["/bin/wslpath", "-u", "C:\\Users\\rcarranz"])
        with mock.patch("install.shutil.which", return_value=None):
            self.assertIsNone(install.wsl_path("C:\\Users\\x"))

    def test_resolve_converts_windows_paths_and_accepts_posix_ones(self):
        win = self.tmp / "Users" / "rcarranz"
        win.mkdir(parents=True)
        with mock.patch("install.wsl_path", return_value=win) as conv:
            self.assertEqual(install.resolve_windows_home("C:\\Users\\r"),
                             (win, None))
            conv.assert_called_once_with("C:\\Users\\r")
        self.assertEqual(install.resolve_windows_home(str(win)), (win, None))
        with mock.patch("install.windows_userprofile", return_value=str(win)):
            self.assertEqual(install.resolve_windows_home(), (win, None))

    def test_resolve_explains_each_failure(self):
        for override, userprofile, wsl, expect in (
                (None, None, None, "cmd.exe interop"),
                ("C:\\Users\\r", None, None, "wslpath could not convert"),
                (str(self.tmp / "nope"), None, None, "is not a directory"),
                (str(self.tmp), None, None, "is the Linux home")):
            with self.subTest(expect=expect), \
                 mock.patch("install.windows_userprofile", return_value=userprofile), \
                 mock.patch("install.wsl_path", return_value=wsl), \
                 mock.patch("install.Path.home", return_value=self.tmp):
                home, why = install.resolve_windows_home(override)
                self.assertIsNone(home)
                self.assertIn(expect, why)


class TestWindowsLeg(TempDirTest):
    """A WSL run delivers the Copilot skills to the Windows home."""

    run_main = TestMain.run_main
    cali = TestMain.cali

    def setUp(self):
        super().setUp()
        self.win = self.tmp / "mnt-c" / "Users" / "rcarranz"
        self.win.mkdir(parents=True)
        self.skills = self.win / ".copilot" / "skills"
        self.linux = self.tmp / "home" / "copilot"
        # What `cali sync` leaves in the Linux home, per the real cali.yaml.
        self.managed = sorted(install.managed_skill_names("copilot"))
        for name in self.managed:
            self.make_skill("home/copilot", name=name,
                            content=OWNED.format(name) + "new\n")
        (self.linux / "roj-onboard-repo" / "references").mkdir()
        (self.linux / "roj-onboard-repo" / "references" / "map.md").write_text("m")

    def wsl_main(self, *argv, **kw):
        kw.setdefault("userprofile", str(self.win))
        return self.run_main(list(argv), wsl=True, **kw)

    def test_regression_windows_home_gets_onboard_repo_and_loses_tour_codebase(self):
        # The captain's report: the Windows home had no roj-onboard-repo and
        # still had the retired roj-tour-codebase, so JetBrains showed old skills.
        self.skills.mkdir(parents=True)
        self.make_skill("mnt-c/Users/rcarranz/.copilot/skills",
                        name="roj-tour-codebase",
                        content=OWNED.format("roj-tour-codebase"))
        self.make_skill("mnt-c/Users/rcarranz/.copilot/skills", name="my-own",
                        content=OWNED.format("my-own"))
        code, _, out, err = self.wsl_main()
        self.assertEqual(code, 0)
        self.assertEqual((self.skills / "roj-onboard-repo" / "SKILL.md").read_text(
            encoding="utf-8"), OWNED.format("roj-onboard-repo") + "new\n")
        self.assertEqual((self.skills / "roj-onboard-repo" / "references"
                          / "map.md").read_text(), "m")
        for name in self.managed:
            self.assertTrue((self.skills / name / "SKILL.md").is_file(), name)
        self.assertFalse((self.skills / "roj-tour-codebase").exists())
        self.assertTrue((self.win / "backups" / "copilot" / "roj-tour-codebase"
                         / "SKILL.md").is_file())
        self.assertTrue((self.skills / "my-own" / "SKILL.md").is_file())
        self.assertIn("windows  roj-onboard-repo", out)
        self.assertEqual(err, "")
        # Claude stays on the Linux side.
        self.assertFalse((self.win / ".claude").exists())

    def test_rerun_changes_nothing(self):
        self.wsl_main()
        before = {p: p.stat().st_mtime_ns for p in self.skills.rglob("*")}
        _, _, out, _ = self.wsl_main()
        self.assertEqual({p: p.stat().st_mtime_ns for p in self.skills.rglob("*")},
                         before)
        self.assertNotIn("windows ", out)
        self.assertFalse((self.win / "backups").exists())

    def test_differing_windows_copy_is_backed_up_then_replaced(self):
        old = self.make_skill("mnt-c/Users/rcarranz/.copilot/skills",
                              name="roj-onboard-repo", content="old and edited")
        code, _, out, _ = self.wsl_main()
        self.assertEqual(code, 0)
        self.assertEqual((old / "SKILL.md").read_text(encoding="utf-8"),
                         OWNED.format("roj-onboard-repo") + "new\n")
        self.assertEqual((self.win / "backups" / "copilot" / "roj-onboard-repo"
                          / "SKILL.md").read_text(), "old and edited")
        self.assertIn("updated (old copy moved to", out)

    def test_crlf_copy_of_an_unchanged_skill_is_not_recopied_or_backed_up(self):
        # A Git Bash clone with core.autocrlf=true installs CRLF copies.
        crlf = self.make_skill("mnt-c/Users/rcarranz/.copilot/skills",
                               name="roj-onboard-repo")
        (crlf / "SKILL.md").write_bytes(
            (OWNED.format("roj-onboard-repo") + "new\n").replace("\n", "\r\n")
            .encode())
        (crlf / "references").mkdir()
        (crlf / "references" / "map.md").write_text("m")
        code, _, out, _ = self.wsl_main()
        self.assertEqual(code, 0)
        self.assertIn(b"\r\n", (crlf / "SKILL.md").read_bytes())
        self.assertNotIn("windows  roj-onboard-repo", out)
        self.assertFalse((self.win / "backups" / "copilot"
                          / "roj-onboard-repo").exists())

    def test_second_wsl_run_makes_no_new_backup(self):
        self.make_skill("mnt-c/Users/rcarranz/.copilot/skills",
                        name="roj-onboard-repo", content="from git bash")
        self.wsl_main()
        backups = sorted((self.win / "backups").rglob("*"))
        self.assertTrue(backups)
        _, _, out, _ = self.wsl_main()
        self.assertEqual(sorted((self.win / "backups").rglob("*")), backups)
        self.assertNotIn("windows ", out)

    def git_bash_main(self, *argv):
        """A WSL run, then a Git Bash run whose home is that Windows home."""
        self.wsl_main()
        self.assertTrue((self.skills / install.WSL_OWNER_MARKER).is_file())
        shutil.rmtree(self.linux)
        shutil.copytree(str(self.skills), str(self.linux))
        (self.linux / "roj-onboard-repo" / "SKILL.md").write_text("wsl copy")
        self.claude_dir = self.tmp / "clone" / ".cali-claude"
        self.claude_dir.parent.mkdir()
        with mock.patch("install.CLAUDE_MANIFEST_DIR", self.claude_dir):
            return self.run_main(list(argv), wsl=False,
                                 cali_rows=rows("unlocked", *self.managed))

    def assert_copilot_left_alone(self):
        self.assertEqual((self.linux / "roj-onboard-repo" / "SKILL.md")
                         .read_text(), "wsl copy")
        self.assertFalse((self.tmp / "home" / "backups").exists())

    def test_git_bash_run_syncs_claude_only_when_wsl_owns_copilot(self):
        code, calls, _, _ = self.git_bash_main()
        self.assertEqual(code, 0)
        self.assertEqual(calls, [install.cali_argv(
            "/bin/cali", "sync", manifest=self.claude_dir / "cali.yaml")])
        self.assert_copilot_left_alone()
        home = self.tmp / "home"
        self.assertTrue((home / "instr" / "copilot.md").is_file())
        self.assertTrue((home / "mcp-copilot.json").is_file())
        self.assertTrue((home / "mcp-claude.json").is_file())
        # cali.yaml: "only roj-idea-to-project also targets Claude".
        deps = install.parse_manifest(
            (self.claude_dir / "cali.yaml").read_text(encoding="utf-8"))
        self.assertEqual([(d["name"], d["source"], d["targets"]) for d in deps],
                         [("roj-idea-to-project", ".//skills/roj-idea-to-project",
                           ("claude",))])
        lock = json.loads((self.claude_dir / "cali.lock").read_text())
        repo_lock = json.loads((install.REPO_ROOT / "cali.lock").read_text())
        self.assertEqual(lock["skills"], {"roj-idea-to-project":
                                          repo_lock["skills"]["roj-idea-to-project"]})

    def test_git_bash_claude_target_still_syncs_when_wsl_owns_copilot(self):
        code, calls, out, _ = self.git_bash_main("--target", "claude")
        self.assertEqual(code, 0)
        self.assertEqual(calls, [install.cali_argv(
            "/bin/cali", "sync", manifest=self.claude_dir / "cali.yaml")])
        self.assertNotIn("skipped", out)
        self.assert_copilot_left_alone()

    def test_git_bash_copilot_target_skips_sync_when_wsl_owns_copilot(self):
        code, calls, out, _ = self.git_bash_main("--target", "copilot")
        self.assertEqual(code, 0)
        self.assertEqual(calls, [])
        self.assertIn("skipped (Copilot skills come from WSL)", out)
        self.assertFalse(self.claude_dir.exists())
        self.assert_copilot_left_alone()
        self.assertTrue((self.tmp / "home" / "mcp-copilot.json").is_file())

    def test_windows_home_flag_names_the_home(self):
        other = self.tmp / "d-drive" / "me"
        other.mkdir(parents=True)
        self.wsl_main("--windows-home", str(other), userprofile=None)
        self.assertTrue((other / ".copilot" / "skills" / "roj-onboard-repo"
                         / "SKILL.md").is_file())

    def test_unresolvable_home_is_loud_and_specific_but_linux_still_installs(self):
        code, calls, out, err = self.wsl_main(userprofile=None)
        self.assertEqual(code, 0)
        self.assertEqual(calls, [self.cali("sync")])
        self.assertIn("could not find the Windows home", err)
        self.assertIn("cmd.exe interop", err)
        self.assertIn("--windows-home /mnt/c/Users/", err)
        self.assertIn("Git Bash", err)
        self.assertFalse((self.win / ".copilot").exists())

    def test_claude_only_run_skips_the_windows_leg(self):
        code, _, _, err = self.wsl_main("--target", "claude")
        self.assertEqual(code, 0)
        self.assertFalse((self.win / ".copilot").exists())
        self.assertNotIn("Windows home", err)

    def test_not_wsl_never_touches_a_windows_home(self):
        self.run_main([], wsl=False, userprofile=str(self.win))
        self.assertFalse((self.win / ".copilot").exists())

    def test_cali_failure_skips_the_windows_leg(self):
        code, _, _, _ = self.wsl_main(cali_code=2)
        self.assertEqual(code, 2)
        self.assertFalse((self.win / ".copilot").exists())

    def test_dry_run_lists_both_moves_and_writes_nothing(self):
        self.make_skill("mnt-c/Users/rcarranz/.copilot/skills",
                        name="roj-tour-codebase",
                        content=OWNED.format("roj-tour-codebase"))
        before = sorted(p.relative_to(self.win) for p in self.win.rglob("*"))
        code, _, out, _ = self.wsl_main("--dry-run")
        self.assertEqual(code, 0)
        self.assertEqual(sorted(p.relative_to(self.win) for p in self.win.rglob("*")),
                         before)
        self.assertIn("windows  roj-tour-codebase", out)
        self.assertIn("retired skill", out)
        self.assertIn("windows  roj-onboard-repo", out)
        self.assertIn("would be copied", out)

    def test_status_shows_both_homes(self):
        self.make_skill("mnt-c/Users/rcarranz/.copilot/skills",
                        name="roj-tour-codebase",
                        content=OWNED.format("roj-tour-codebase"))
        code, _, out, err = self.wsl_main("--status")
        self.assertEqual(code, 0)
        self.assertIn(f"windows home: {self.win}", out)
        self.assertRegex(err, r"windows: \d+ skill\(s\) missing or out of date "
                              r"\(.*roj-onboard-repo.*\)")
        self.assertIn(f"windows: roj-tour-codebase left over in {self.skills}"
                      " - re-run install.py to move it", err)
        self.assertTrue((self.skills / "roj-tour-codebase").is_dir())
        self.assertFalse((self.skills / "roj-onboard-repo").exists())
        self.wsl_main()
        _, _, out, err = self.wsl_main("--status")
        self.assertIn("no conflicts detected", out)

    def test_status_reports_an_unresolvable_windows_home(self):
        _, _, _, err = self.wsl_main("--status", userprofile=None)
        self.assertIn("could not find the Windows home", err)

    def test_copy_failure_is_reported_and_keeps_the_old_copy(self):
        old = self.make_skill("mnt-c/Users/rcarranz/.copilot/skills",
                              name="roj-onboard-repo", content="old")
        real = os.replace

        def locked(src, dest):
            if str(self.skills) in str(dest):
                raise PermissionError("locked")
            return real(src, dest)

        with mock.patch("install.os.replace", side_effect=locked):
            code, _, out, err = self.wsl_main()
        self.assertEqual(code, 0)
        self.assertEqual((old / "SKILL.md").read_text(), "old")
        self.assertIn("could not copy roj-onboard-repo", err)
        self.assertRegex(out, r"windows  roj-onboard-repo +failed")
        self.assertFalse((self.skills / ".roj-onboard-repo.tmp").exists())

    def test_partial_copy_leaves_no_half_skill(self):
        def disk_full(src, dest):
            Path(dest).mkdir()
            (Path(dest) / "SKILL.md").write_text("half")
            raise shutil.Error("disk full")

        with mock.patch("install.shutil.copytree", side_effect=disk_full):
            code, _, out, err = self.wsl_main()
        self.assertEqual(code, 0)
        self.assertRegex(out, r"windows  roj-onboard-repo +failed")
        self.assertEqual([p.name for p in self.skills.iterdir()
                          if p.name.endswith(".tmp")], [])


if __name__ == "__main__":
    unittest.main()
