"""The roj-idea-to-project scripts: check_superpowers.py and check_ready.py.

  python3 -m unittest test_idea_to_project -v
"""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SCRIPTS = ROOT / "skills" / "roj-idea-to-project" / "scripts"
CHECK_SP = SCRIPTS / "check_superpowers.py"
CHECK_READY = SCRIPTS / "check_ready.py"


def fake_cli(bin_dir: Path, name: str, stdout: str = "", code: int = 0,
             stderr: str = "") -> None:
    """Write a stand-in CLI called `name` into bin_dir that prints stdout,
    prints stderr, logs its arguments to calls.log and exits with code."""
    body = (
        "import sys\n"
        f"open({str(bin_dir / 'calls.log')!r}, 'a', encoding='utf-8')"
        f".write({name!r} + ' ' + ' '.join(sys.argv[1:]) + '\\n')\n"
        f"sys.stdout.write({stdout!r})\n"
        f"sys.stderr.write({stderr!r})\n"
        f"sys.exit({code})\n")
    script = bin_dir / f"{name}.py"
    script.write_text(body, encoding="utf-8")
    if os.name == "nt":
        (bin_dir / f"{name}.cmd").write_text(
            f'@"{sys.executable}" "%~dp0{name}.py" %*\n', encoding="utf-8")
    else:
        exe = bin_dir / name
        exe.write_text(f"#!{sys.executable}\n{body}", encoding="utf-8")
        exe.chmod(0o755)


def run_script(script: Path, args, path_dir: Path):
    env = dict(os.environ, PATH=str(path_dir))
    return subprocess.run([sys.executable, str(script), *args], env=env,
                          capture_output=True, text=True, encoding="utf-8")


def plugin(pid: str, version: str, enabled: bool = True,
           scope: str = "user") -> dict:
    return {"id": pid, "version": version, "scope": scope,
            "enabled": enabled, "installPath": "/tmp/plugins/x"}


class CheckSuperpowersTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.bin = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def claude_list(self, plugins, code=0, stderr=""):
        fake_cli(self.bin, "claude", json.dumps(plugins), code, stderr)

    def run_check(self, *args):
        p = run_script(CHECK_SP, args, self.bin)
        report = json.loads(p.stdout) if p.stdout.strip() else None
        return p, report

    def test_help(self):
        p = run_script(CHECK_SP, ["--help"], self.bin)
        self.assertEqual(p.returncode, 0)
        self.assertIn("never installs", p.stdout.lower())

    def test_ok_when_enabled_and_current(self):
        self.claude_list([plugin("superpowers@claude-plugins-official",
                                 "7.0.0")])
        p, r = self.run_check()
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertEqual(r["status"], "ok")
        self.assertEqual(r["client"], "claude")
        self.assertEqual(r["version"], "7.0.0")
        self.assertTrue(r["version_comparable"])
        self.assertEqual(r["next"], [])

    def test_missing_names_the_install_command(self):
        self.claude_list([plugin("caveman@caveman", "4.0.1")])
        p, r = self.run_check()
        self.assertEqual(p.returncode, 1)
        self.assertEqual(r["status"], "missing")
        self.assertFalse(r["installed"])
        self.assertEqual(r["next"], [
            "claude plugin install superpowers@claude-plugins-official"])

    def test_disabled_names_the_enable_command(self):
        self.claude_list([plugin("superpowers@superpowers-marketplace",
                                 "7.0.0", enabled=False)])
        p, r = self.run_check()
        self.assertEqual(p.returncode, 1)
        self.assertEqual(r["status"], "disabled")
        self.assertEqual(r["next"], [
            "claude plugin enable superpowers@superpowers-marketplace"])

    def test_outdated_passes_with_update_command(self):
        self.claude_list([plugin("superpowers@claude-plugins-official",
                                 "6.4.1")])
        p, r = self.run_check()
        self.assertEqual(p.returncode, 0)
        self.assertEqual(r["status"], "outdated")
        self.assertEqual(r["next"], [
            "claude plugin update superpowers@claude-plugins-official"])
        self.assertIn("6.4.1", p.stderr)
        self.assertIn("/reload-plugins", p.stderr)

    def test_min_version_flag(self):
        self.claude_list([plugin("superpowers@claude-plugins-official",
                                 "6.4.1")])
        p, r = self.run_check("--min-version", "6.0.0")
        self.assertEqual(r["status"], "ok")

    def test_sha_version_is_not_comparable_and_not_outdated(self):
        self.claude_list([plugin("superpowers@claude-plugins-official",
                                 "8f814f49002f")])
        p, r = self.run_check()
        self.assertEqual(p.returncode, 0)
        self.assertEqual(r["status"], "ok")
        self.assertFalse(r["version_comparable"])
        self.assertIn("cannot compare", p.stderr)

    def test_enabled_install_wins_over_disabled_one(self):
        self.claude_list([
            plugin("superpowers@superpowers-marketplace", "7.0.0",
                   enabled=False, scope="project"),
            plugin("superpowers@claude-plugins-official", "7.0.0")])
        p, r = self.run_check()
        self.assertEqual(r["status"], "ok")

    def test_similar_plugin_name_is_not_superpowers(self):
        self.claude_list([plugin("superpowers-lab@obra", "1.0.0")])
        p, r = self.run_check()
        self.assertEqual(r["status"], "missing")

    def test_cli_failure_is_undetectable_not_a_traceback(self):
        fake_cli(self.bin, "claude", "", 1, "error: unknown option '--json'")
        p, r = self.run_check()
        self.assertEqual(p.returncode, 1)
        self.assertEqual(r["status"], "undetectable")
        self.assertIn("unknown option", p.stderr)
        self.assertNotIn("Traceback", p.stderr)

    def test_non_json_output_is_undetectable(self):
        fake_cli(self.bin, "claude", "Installed plugins:\n  none\n")
        p, r = self.run_check()
        self.assertEqual(r["status"], "undetectable")

    def test_no_cli_is_undetectable_and_points_at_skill_list(self):
        p, r = self.run_check()
        self.assertEqual(p.returncode, 1)
        self.assertEqual(r["status"], "undetectable")
        self.assertIsNone(r["client"])
        self.assertIn("superpowers:brainstorming", p.stderr)

    def test_copilot_missing_needs_two_commands(self):
        fake_cli(self.bin, "copilot", "No plugins installed.\n\n"
                 "Use 'copilot plugin install <source>' to install a plugin.\n")
        p, r = self.run_check()
        self.assertEqual(r["client"], "copilot")
        self.assertEqual(r["status"], "missing")
        self.assertEqual(r["next"], [
            "copilot plugin marketplace add obra/superpowers-marketplace",
            "copilot plugin install superpowers@superpowers-marketplace"])

    def test_copilot_installed_with_version(self):
        fake_cli(self.bin, "copilot", "Installed plugins:\n"
                 "  superpowers@superpowers-marketplace (v7.0.0)\n")
        p, r = self.run_check("--client", "copilot")
        self.assertEqual(r["status"], "ok")
        self.assertEqual(r["version"], "7.0.0")

    def test_copilot_unparsed_version_is_unknown(self):
        fake_cli(self.bin, "copilot", "superpowers  enabled\n")
        p, r = self.run_check("--client", "copilot")
        self.assertEqual(r["status"], "ok")
        self.assertEqual(r["version"], "unknown")
        self.assertFalse(r["version_comparable"])

    def test_copilot_disabled(self):
        fake_cli(self.bin, "copilot",
                 "superpowers@superpowers-marketplace 7.0.0 (disabled)\n")
        p, r = self.run_check("--client", "copilot")
        self.assertEqual(r["status"], "disabled")
        self.assertEqual(r["next"], [
            "copilot plugin enable superpowers@superpowers-marketplace"])

    def test_auto_prefers_claude(self):
        self.claude_list([plugin("superpowers@claude-plugins-official",
                                 "7.0.0")])
        fake_cli(self.bin, "copilot", "No plugins installed.\n")
        p, r = self.run_check()
        self.assertEqual(r["client"], "claude")

    def test_never_runs_an_install(self):
        self.claude_list([])
        self.run_check()
        calls = (self.bin / "calls.log").read_text("utf-8")
        self.assertEqual(calls.strip(), "claude plugin list --json")


if __name__ == "__main__":
    unittest.main()
