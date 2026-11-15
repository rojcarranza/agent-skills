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
        results = [install.Row("claude", "graphify", "installed (by CLI)",
                               "missing")]
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
                mock.patch("install.instruction_path",
                           return_value=self.tmp / "instr.md"), \
                mock.patch("install.startup_note_path",
                           return_value=self.tmp / "note.md"), \
                mock.patch("install.jetbrains_instruction_path",
                           return_value=self.tmp / "jb.md"), \
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

    SKILL = install.SKILLS_SRC / "roj-explain-my-branch"
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
        others = install.custom_skill_names() - {"roj-explain-my-branch"}
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
    PLUGIN_PROVIDED = set()
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
                     "systematic-debugging", "find-skills"):
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

    def test_only_one_slide_targets_claude(self):
        # Copilot is the work agent; roj-one-slide is the one skill that also
        # targets Claude.
        both = ("claude", "copilot")   # the manifest's default targets
        def targets(d):
            return d["targets"] or both
        live = [d for d in install.manifest_deps() if d["active"]]
        self.assertEqual({d["name"] for d in live if "claude" in targets(d)},
                         {"roj-one-slide"})
        copilot = {d["name"] for d in live if "copilot" in targets(d)}
        self.assertLessEqual(install.custom_skill_names(), copilot)

    def test_every_skill_loads_on_demand(self):
        # cali.yaml is the list `cali setup` reads: cali's own entry is gone
        # (cali installs itself), so no skill is always-on.
        always = {d["name"] for d in install.manifest_deps()
                  if d["active"] and d["load"] == "always"}
        self.assertEqual(always, set())

    def test_load_field_is_read(self):
        parsed = install.parse_manifest(
            "skills:\n  a:\n    source: x\n    load: on-demand\n  b:\n"
            "    source: y\n")
        self.assertEqual([d["load"] for d in parsed], ["on-demand", "always"])

    def test_repo_keeps_no_lock(self):
        # loaders pin in their own cali.lock.
        self.assertFalse((install.REPO_ROOT / "cali.lock").exists())

    def test_header_says_cali_reads_the_list(self):
        head = (install.REPO_ROOT / "cali.yaml").read_text("utf-8").split("version:")[0]
        self.assertIn("cali setup github:rojcarranza/agent-skills", head)
        self.assertNotIn("cali sync", head)


class TestMcp(TempDirTest):
    """Intent: gh-axi replaces the GitHub MCP server, so install.py removes
    the entry it wrote and adds nothing."""

    MINE = {"claude": {"type": "http",
                       "url": "https://api.githubcopilot.com/mcp/"},
            "copilot": {"type": "http",
                        "url": "https://api.githubcopilot.com/mcp/",
                        "tools": ["*"]}}

    def setUp(self):
        super().setUp()
        self.paths = {"claude": self.tmp / ".claude.json",
                      "copilot": self.tmp / ".copilot" / "mcp-config.json"}
        p = mock.patch("install.mcp_config_path",
                       side_effect=lambda t: self.paths[t])
        p.start()
        self.addCleanup(p.stop)

    def retire(self, target, dry_run=False):
        err = io.StringIO()
        with mock.patch("sys.stderr", err):
            results = install.retire_mcp_servers(target, dry_run)
        return results, err.getvalue()

    def test_entry_removed_and_other_servers_and_keys_kept(self):
        for target in ("claude", "copilot"):
            with self.subTest(target=target):
                path = self.paths[target]
                path.parent.mkdir(exist_ok=True)
                path.write_text(json.dumps({"numStartups": 3, "mcpServers": {
                    "github-mcp-server": self.MINE[target],
                    "neon": {"command": "x"}}}))
                results, _ = self.retire(target)
                data = json.loads(path.read_text())
                self.assertEqual(data, {"numStartups": 3, "mcpServers": {
                    "neon": {"command": "x"}}})
                self.assertEqual(results, [(target, "mcp:github-mcp-server",
                                            "removed")])

    def test_nothing_is_added(self):
        for target in ("claude", "copilot"):
            results, _ = self.retire(target)
            self.assertEqual(results, [])
            self.assertFalse(self.paths[target].exists())
        self.paths["claude"].write_text('{"mcpServers": {}}')
        self.assertEqual(self.retire("claude")[0], [])
        self.assertEqual(self.paths["claude"].read_text(), '{"mcpServers": {}}')

    def test_edited_entry_kept(self):
        mine = {"mcpServers": {"github-mcp-server": {
            "type": "http", "url": "u", "headers": {"A": "b"}}}}
        self.paths["claude"].write_text(json.dumps(mine))
        before = self.paths["claude"].read_text()
        results, err = self.retire("claude")
        self.assertEqual(self.paths["claude"].read_text(), before)
        self.assertEqual([r[2] for r in results], ["kept (edited by you)"])
        self.assertIn("github-mcp-server", err)

    def test_invalid_json_is_never_overwritten(self):
        self.paths["claude"].write_text("{not json")
        results, err = self.retire("claude")
        self.assertEqual(self.paths["claude"].read_text(), "{not json")
        self.assertEqual([r[2] for r in results], ["kept (unreadable)"])
        self.assertIn("not valid JSON", err)

    def test_non_object_servers_are_never_overwritten(self):
        self.paths["claude"].write_text('{"mcpServers": []}')
        results, err = self.retire("claude")
        self.assertEqual(self.paths["claude"].read_text(), '{"mcpServers": []}')
        self.assertEqual([r[2] for r in results], ["kept (unreadable)"])
        self.assertIn("mcpServers", err)

    def test_dry_run_writes_nothing(self):
        self.paths["claude"].write_text(json.dumps(
            {"mcpServers": {"github-mcp-server": self.MINE["claude"]}}))
        before = self.paths["claude"].read_text()
        results, _ = self.retire("claude", dry_run=True)
        self.assertEqual(self.paths["claude"].read_text(), before)
        self.assertEqual(results, [("claude", "mcp:github-mcp-server",
                                    "removed")])


class TestMcpPaths(unittest.TestCase):
    def test_real_paths(self):
        with mock.patch("install.Path.home", return_value=Path("/h")):
            self.assertEqual(install.mcp_config_path("claude"),
                             Path("/h/.claude.json"))
            self.assertEqual(install.mcp_config_path("copilot"),
                             Path("/h/.copilot/mcp-config.json"))


OWNED = "---\nname: {}\ndescription: x\n---\n"


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
        self.note = self.tmp / "home" / ".copilot" / "instructions" \
            / "superpowers.instructions.md"
        self.jetbrains = self.tmp / "home" / "jetbrains" / "global.md"
        for p in (mock.patch("install.INSTRUCTIONS_SRC", self.src),
                  mock.patch("install.startup_note_path",
                             side_effect=lambda t: self.note),
                  mock.patch("install.jetbrains_instruction_path",
                             return_value=self.jetbrains),
                  mock.patch("install.instruction_path",
                             side_effect=lambda t: self.dest[t]),
                  mock.patch("install.shipped_instructions",
                             return_value={self.SRC, "old rules\n"})):
            p.start()
            self.addCleanup(p.stop)

    def deploy(self, target, dry_run=False, everything=False):
        err = io.StringIO()
        with mock.patch("sys.stderr", err):
            results = install.install_instructions(target, dry_run)
        if not everything:  # the personal file; the note has its own tests
            results = [r for r in results if r[1] == "personal.instructions.md"]
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
        self.assertEqual([r[2] for r in results], ["kept (edited by you)"])

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
        self.assertEqual([r[2] for r in results], ["kept (a link)"])
        self.assertIn("other than the dotfiles repo", err)

    def test_dry_run_writes_nothing(self):
        results, _ = self.deploy("copilot", dry_run=True)
        self.assertFalse(self.dest["copilot"].exists())
        self.assertEqual(results[0][2], "installed")


    # SCR-15 piece 1: the Superpowers start-up note and JetBrains' file.
    def test_startup_note_deployed_beside_the_personal_file(self):
        self.deploy("copilot")
        self.assertEqual(self.note.read_text(),
                         install.STARTUP_NOTE_SRC.read_text(encoding="utf-8"))

    def test_jetbrains_block_holds_note_then_personal_instructions(self):
        results, _ = self.deploy("copilot", everything=True)
        text = self.jetbrains.read_text()
        self.assertIn(("copilot", "global.md", "installed"), results)
        self.assertTrue(text.startswith(install.JETBRAINS_BEGIN))
        self.assertTrue(text.endswith(install.JETBRAINS_END + "\n"))
        self.assertLess(text.index("using-superpowers"), text.index("# Rules"))
        self.assertNotIn("applyTo", text)  # front matter is dropped

    def test_jetbrains_keeps_own_text_and_replaces_only_the_block(self):
        self.jetbrains.parent.mkdir(parents=True)
        self.jetbrains.write_text("Mine above.\n\n" + install.JETBRAINS_BEGIN
                                  + "\nstale\n" + install.JETBRAINS_END
                                  + "\n\nMine below.\n")
        self.deploy("copilot")
        text = self.jetbrains.read_text()
        self.assertTrue(text.startswith("Mine above.\n\n"))
        self.assertTrue(text.endswith(install.JETBRAINS_END + "\n\nMine below.\n"))
        self.assertNotIn("stale", text)
        self.assertEqual(text.count(install.JETBRAINS_BEGIN), 1)

    def test_jetbrains_appends_the_block_to_a_file_without_markers(self):
        self.jetbrains.parent.mkdir(parents=True)
        self.jetbrains.write_text("Mine only.\n")
        self.deploy("copilot")
        text = self.jetbrains.read_text()
        self.assertTrue(text.startswith("Mine only.\n"))
        self.assertIn(install.JETBRAINS_BEGIN, text)

    def test_jetbrains_second_run_is_silent(self):
        self.deploy("copilot")
        before = self.jetbrains.read_text()
        results, _ = self.deploy("copilot", everything=True)
        self.assertEqual(results, [])
        self.assertEqual(self.jetbrains.read_text(), before)

    def test_jetbrains_dry_run_writes_nothing(self):
        self.deploy("copilot", dry_run=True)
        self.assertFalse(self.jetbrains.exists())


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
        self.assertEqual([r[2] for r in results], ["kept (edited by you)"])
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
        self.assertEqual([r[2] for r in results], ["kept (a link)"])
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


    def test_jetbrains_paths(self):
        with mock.patch("install.Path.home", return_value=Path("/h")):
            self.assertEqual(
                install.jetbrains_instruction_path(windows=False),
                Path("/h/.config/github-copilot/intellij/global-copilot-instructions.md"))
            self.assertEqual(
                install.jetbrains_instruction_path(home=Path("/mnt/c/Users/me")),
                Path("/mnt/c/Users/me/AppData/Local/github-copilot/intellij/"
                     "global-copilot-instructions.md"))


class TestMain(TempDirTest):
    """main() end to end with externals and homes faked. install.py installs
    no skills and never runs cali."""

    def run_main(self, argv, wsl=False, externals=(), bootstrap=None,
                 userprofile=None):
        """Returns (exit code, subprocess commands, stdout, stderr)."""
        home = tmp_home = self.tmp / "home"
        home.mkdir(exist_ok=True)
        calls = []

        def fake_run(cmd, *args, **kwargs):
            calls.append(list(cmd))
            return mock.Mock(returncode=0, stdout="")

        def jetbrains(home=None, windows=None):
            return (home or tmp_home) / "jetbrains.md"

        out, err = io.StringIO(), io.StringIO()
        code = 0
        with contextlib.ExitStack() as stack:
            for p in (
                mock.patch("install.target_root",
                           side_effect=lambda t: home / t),
                mock.patch("install.instruction_path",
                           side_effect=lambda t: None if t == "claude"
                           else home / "instr" / f"{t}.md"),
                mock.patch("install.startup_note_path",
                           side_effect=lambda t: None if t == "claude"
                           else home / "instr" / "note.md"),
                mock.patch("install.jetbrains_instruction_path",
                           side_effect=jetbrains),
                mock.patch("install.mcp_config_path",
                           side_effect=lambda t: home / f"mcp-{t}.json"),
                mock.patch("install.claude_rules_path",
                           return_value=home / "rules" / "personal.md"),
                mock.patch("install.backup_dir",
                           side_effect=lambda h=None: (h or home) / "backups"),
                mock.patch("install.windows_userprofile",
                           return_value=userprofile),
                mock.patch("install.subprocess.run", side_effect=fake_run),
                mock.patch("install.EXTERNALS", list(externals)),
                mock.patch("install.bootstrap_cli",
                           side_effect=bootstrap or (lambda ext, dry: None)),
                mock.patch("install.is_wsl", return_value=wsl),
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

    def test_default_writes_the_extras_and_runs_no_cali(self):
        # no cali on PATH is fine, nothing runs cali, and
        # no skills folder is created.
        code, calls, out, _ = self.run_main([])
        home = self.tmp / "home"
        self.assertEqual(code, 0)
        self.assertEqual(calls, [])
        self.assertTrue((home / "instr" / "copilot.md").is_file())
        self.assertFalse((home / "instr" / "claude.md").exists())
        for t in ("claude", "copilot"):
            with self.subTest(target=t):
                self.assertFalse((home / f"mcp-{t}.json").exists())
                self.assertFalse((home / t).exists())
        self.assertIn("cali setup github:rojcarranza/agent-skills", out)

    def test_run_removes_the_github_entry_it_wrote(self):
        home = self.tmp / "home"
        home.mkdir(exist_ok=True)
        url = "https://api.githubcopilot.com/mcp/"
        (home / "mcp-claude.json").write_text(json.dumps({"mcpServers": {
            "github-mcp-server": {"type": "http", "url": url},
            "obsidian": {"command": "y"}}}))
        code, _, _, _ = self.run_main([])
        self.assertEqual(code, 0)
        data = json.loads((home / "mcp-claude.json").read_text())
        self.assertEqual(data, {"mcpServers": {"obsidian": {"command": "y"}}})

    def test_single_target_limits_everything(self):
        self.run_main(["--target", "copilot"])
        home = self.tmp / "home"
        self.assertFalse((home / "instr" / "claude.md").exists())

    def test_leaves_skill_folders_of_older_installs_alone(self):
        # install.py drops the clean-up: a link, a renamed skill, a retired one
        # and a current one stay, in both agents.
        home = self.tmp / "home"
        for t in ("claude", "copilot"):
            self.make_skill(f"home/{t}", name="roj-explain-logic",
                            content=OWNED.format("roj-explain-logic"))
            self.make_skill(f"home/{t}", name="explain-logic",
                            content=OWNED.format("explain-logic"))
            self.make_skill(f"home/{t}", name="roj-tour-codebase",
                            content=OWNED.format("roj-tour-codebase"))
        code, _, _, err = self.run_main([])
        self.assertEqual(code, 0)
        for t in ("claude", "copilot"):
            for n in ("roj-explain-logic", "explain-logic", "roj-tour-codebase"):
                with self.subTest(target=t, skill=n):
                    self.assertTrue((home / t / n / "SKILL.md").is_file())
        self.assertFalse((home / "backups").exists())
        self.assertNotIn("left over", err)

    def test_update_points_to_cali_and_runs_nothing(self):
        code, calls, out, _ = self.run_main(["--update"])
        self.assertEqual(code, 0)
        self.assertEqual(calls, [])
        self.assertIn("cali update -g", out)

    def test_status_points_to_cali_and_succeeds(self):
        self.run_main([])
        code, calls, out, _ = self.run_main(["--status"])
        self.assertEqual(code, 0)
        self.assertEqual(calls, [])
        self.assertIn("cali status -g", out)

    def test_dry_run_writes_nothing(self):
        code, calls, _, _ = self.run_main(["--dry-run"])
        self.assertEqual(code, 0)
        self.assertEqual(calls, [])
        self.assertFalse((self.tmp / "home" / "instr").exists())
        self.assertFalse((self.tmp / "home" / "mcp-copilot.json").exists())

    def test_skills_only_never_bootstraps_externals(self):
        ext = ExternalTest.fake_external(None)
        boots = []
        code, _, out, _ = self.run_main(
            ["--skills-only", "--target", "claude"], externals=[ext],
            bootstrap=lambda e, dry: boots.append(e["name"]))
        self.assertEqual(code, 0)
        self.assertEqual(boots, [])
        self.assertIn("--skills-only", out)

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
        self.assertIn("Run install.py from Git Bash for the other extras", out)

    def test_shipped_claude_rules_are_still_moved_aside(self):
        home = self.tmp / "home"
        rules = home / "rules" / "personal.md"
        rules.parent.mkdir(parents=True)
        rules.write_text(install.INSTRUCTIONS_SRC.read_text(encoding="utf-8"))
        code, _, _, _ = self.run_main(["--target", "claude"])
        self.assertEqual(code, 0)
        self.assertFalse(rules.exists())
        self.assertTrue((home / "backups" / "claude" / "personal.md").is_file())


class TestItemStates(TempDirTest):
    """AGS-11 machine 1: the real run, --dry-run and --status read one state
    per item, so none of them disagrees with the disk or with the others.
    Every case runs in a throwaway home, with the CLI faked."""

    run_main = TestMain.run_main

    def setUp(self):
        super().setUp()
        self.home = self.tmp / "home"
        self.ext = ExternalTest.fake_external(None)
        for p in (mock.patch("install.cli_version", return_value="1.2.3"),
                  mock.patch("install.find_cli", return_value="/bin/tool-y"),
                  mock.patch("install.cli_path_hint", return_value=None)):
            p.start()
            self.addCleanup(p.stop)

    def main(self, *argv, **kw):
        return self.run_main(list(argv), externals=[self.ext],
                             bootstrap=lambda e, dry: "/bin/tool-y", **kw)

    def stamp(self, target, version="1.2.3"):
        skill = self.home / target / "tool-y"
        skill.mkdir(parents=True, exist_ok=True)
        (skill / "SKILL.md").write_text("body")
        (skill / ".tool_y_version").write_text(version + "\n")
        return skill

    def clean_home(self):
        for t in ("claude", "copilot"):
            self.stamp(t)
        code, _, out, err = self.main()
        self.assertEqual(code, 0, err)
        code, _, out, _ = self.main("--status")
        self.assertEqual(code, 0)
        self.assertIn("no conflicts detected", out)

    def test_dry_run_says_up_to_date_when_the_real_run_would(self):
        self.clean_home()
        _, _, out, _ = self.main("--dry-run")
        self.assertIn("up to date", out)
        self.assertNotIn("would run", out)

    def test_status_flags_a_half_installed_external(self):
        self.clean_home()
        (self.home / "claude" / "tool-y" / "SKILL.md").write_text(
            "See references/a.md")
        code, calls, out, err = self.main("--status")
        self.assertEqual(code, 1)
        self.assertNotIn("no conflicts detected", out)
        self.assertIn("tool-y", err)

    def test_status_flags_a_leftover_claude_rules_file(self):
        self.clean_home()
        rules = self.home / "rules" / "personal.md"
        rules.parent.mkdir(parents=True)
        rules.write_text(install.INSTRUCTIONS_SRC.read_text(encoding="utf-8"))
        code, _, out, err = self.main("--status")
        self.assertEqual(code, 1)
        self.assertNotIn("no conflicts detected", out)
        self.assertIn("personal.md", err)
        self.assertTrue(rules.exists())

    def test_status_does_not_call_an_edited_instruction_file_clean(self):
        self.clean_home()
        edited = self.home / "instr" / "copilot.md"
        edited.write_text("my own words\n")
        code, _, out, err = self.main("--status")
        self.assertEqual(code, 1)
        self.assertNotIn("no conflicts detected", out)
        self.assertIn("differs", err)
        self.assertEqual(edited.read_text(), "my own words\n")

    def test_failed_external_install_exits_nonzero_without_a_verify_line(self):
        with mock.patch("install.run_cli", return_value=False):
            code, _, out, _ = self.main("--target", "claude")
        self.assertEqual(code, 3)
        self.assertIn("failed", out)
        self.assertNotIn("Verify tool-y", out)

    def test_run_and_dry_run_agree_on_every_state(self):
        # One table: the dry run names the same outcome the real run reports.
        cases = {
            "older": lambda: self.stamp("claude", "1.0.0"),
            "half": lambda: (self.stamp("claude") / "references.tmp").mkdir(),
            "missing": lambda: None,
        }
        for name, setup in cases.items():
            with self.subTest(state=name):
                shutil.rmtree(self.home, ignore_errors=True)
                setup()
                _, _, dry, _ = self.main("--dry-run", "--target", "claude")
                self.assertIn("would run tool-y install", dry)
                _, _, real, _ = self.main("--target", "claude")
                self.assertIn("installed (by CLI)", real)

    def test_edited_instruction_file_makes_the_run_exit_1(self):
        edited = self.home / "instr" / "copilot.md"
        edited.parent.mkdir(parents=True)
        edited.write_text("my own words\n")
        code, _, out, _ = self.main("--target", "copilot")
        self.assertEqual(code, 1)
        self.assertIn("kept", out)

    def test_exit_code_is_the_worst_state(self):
        self.assertEqual(install.worst_level([]), 0)
        rows = [install.Row("claude", "a", "installed", "missing"),
                install.Row("claude", "b", "kept", "edited")]
        self.assertEqual(install.worst_level(rows), 1)
        rows.append(install.Row("claude", "c", "failed", "failed"))
        self.assertEqual(install.worst_level(rows), 3)


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
    """A WSL run writes the JetBrains block into the Windows home; skills
    there come from cali, never from this script."""

    run_main = TestMain.run_main

    def setUp(self):
        super().setUp()
        self.win = self.tmp / "mnt-c" / "Users" / "rcarranz"
        self.win.mkdir(parents=True)

    def wsl_main(self, *argv, **kw):
        kw.setdefault("userprofile", str(self.win))
        return self.run_main(list(argv), wsl=True, **kw)

    def test_wsl_run_writes_jetbrains_block_and_no_skills_in_windows_home(self):
        code, calls, _, _ = self.wsl_main()
        self.assertEqual(code, 0)
        self.assertEqual(calls, [])
        self.assertIn("BEGIN agent-skills",
                      (self.win / "jetbrains.md").read_text(encoding="utf-8"))
        self.assertFalse((self.win / ".copilot").exists())

    def test_windows_home_flag_names_the_home(self):
        other = self.tmp / "d-drive" / "me"
        other.mkdir(parents=True)
        self.wsl_main("--windows-home", str(other), userprofile=None)
        self.assertTrue((other / "jetbrains.md").is_file())
        self.assertFalse((self.win / "jetbrains.md").exists())

    def test_unresolvable_home_is_loud_and_specific_but_linux_still_installs(self):
        code, _, _, err = self.wsl_main(userprofile=None)
        self.assertEqual(code, 0)
        self.assertTrue((self.tmp / "home" / "instr" / "copilot.md").is_file())
        self.assertIn("could not find the Windows home", err)
        self.assertIn("cmd.exe interop", err)
        self.assertIn("--windows-home /mnt/c/Users/", err)
        self.assertIn("Git Bash", err)

    def test_claude_only_run_skips_the_windows_leg(self):
        code, _, _, err = self.wsl_main("--target", "claude")
        self.assertEqual(code, 0)
        self.assertFalse((self.win / "jetbrains.md").exists())
        self.assertNotIn("Windows home", err)

    def test_not_wsl_never_touches_a_windows_home(self):
        self.run_main([], wsl=False, userprofile=str(self.win))
        self.assertEqual(list(self.win.iterdir()), [])

    def test_dry_run_writes_nothing_in_the_windows_home(self):
        code, _, _, _ = self.wsl_main("--dry-run")
        self.assertEqual(code, 0)
        self.assertEqual(list(self.win.iterdir()), [])

    def test_status_shows_the_windows_home(self):
        self.wsl_main()
        code, _, out, _ = self.wsl_main("--status")
        self.assertEqual(code, 0)
        self.assertIn(f"windows home: {self.win}", out)

    def test_status_reports_an_unresolvable_windows_home(self):
        _, _, _, err = self.wsl_main("--status", userprofile=None)
        self.assertIn("could not find the Windows home", err)


if __name__ == "__main__":
    unittest.main()
