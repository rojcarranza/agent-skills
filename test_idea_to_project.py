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


BRIEF_OK = """# Plants Brief
Status: Approved 2026-10-15
## Problem (2 to 3 sentences)
Plants die.
## Non-goals (at least 5)
- No social feed
- No marketplace
- No native app
1. No sensors
2. No multi-language UI
## Constraints (budget, cloud, compliance, timeline)
"""

REQ_OK = """# Requirements: Plants (v0.1, 2026-10-15)
Status: Approved 2026-10-15
## Functional requirements
### FR-1 Reminders
User story: As an owner, I want reminders so that plants live.
- FR-1.1 WHEN a plant is due THE SYSTEM SHALL send a reminder.
- FR-1.2 IF the reminder fails THEN THE SYSTEM SHALL retry once.
Verification: test_reminders
### FR-2 Plants
- FR-2.1 WHILE a plant exists THE SYSTEM SHALL show its next due date.
- Verification: tests/test_plants.py
## Non-functional requirements
- NFR-PERF: p95 < 200 ms at 10 rps
- NFR-SEC: authn magic link; authz owner only; input validated at API; secrets from env
## Traceability: requirement -> task -> test
- FR-2.1 -> Task 3 -> test_plants
"""

ADRS = {
    "0001-language.md": "# ADR-0001: Python 3.12\n",
    "0002-database.md": "# ADR-0002: SQLite\n",
    "0003-auth.md": "# ADR-0003: Magic links\n",
    "0004-hosting.md": "# ADR-0004: Fly.io\n",
    "0005-x.md": "# ADR-0005: Structured logging and metrics\n",
}


class CheckReadyTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.write("docs/brief.md", BRIEF_OK)
        self.write("docs/requirements.md", REQ_OK)
        self.write("docs/architecture.md", "# Architecture\n")
        for name, text in ADRS.items():
            self.write(f"docs/adr/{name}", text)
        self.write("CLAUDE.md", "# Plants\n" + "- line\n" * 40)

    def tearDown(self):
        self.tmp.cleanup()

    def write(self, rel, text, newline="\n"):
        p = self.root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text.replace("\n", newline), encoding="utf-8",
                     newline="")

    def run_ready(self, *args):
        return run_script(CHECK_READY, [*args, str(self.root)],
                          Path(self.tmp.name))

    def assert_fails_with(self, line, *args):
        p = self.run_ready(*args)
        self.assertEqual(p.returncode, 1, p.stdout)
        self.assertIn(line, p.stdout)
        self.assertIn("NOT READY", p.stdout)

    def test_help(self):
        p = run_script(CHECK_READY, ["--help"], self.root)
        self.assertEqual(p.returncode, 0)
        self.assertIn("--phase", p.stdout)

    def test_ready_project_passes(self):
        p = self.run_ready()
        self.assertEqual(p.returncode, 0, p.stdout)
        self.assertTrue(p.stdout.strip().endswith("READY"))

    def test_crlf_files_pass(self):
        self.write("docs/requirements.md", REQ_OK, newline="\r\n")
        self.write("docs/brief.md", BRIEF_OK, newline="\r\n")
        self.assertEqual(self.run_ready().returncode, 0)

    def test_two_non_goals(self):
        self.write("docs/brief.md",
                   "# B\n## Non-goals (at least 5)\n- a\n- b\n## Open questions\n")
        self.assert_fails_with(
            "docs/brief.md has 2 non-goals: add at least 3 more under "
            "## Non-goals", "--phase", "brief")

    def test_missing_verification(self):
        self.write("docs/requirements.md",
                   REQ_OK.replace("- Verification: tests/test_plants.py\n", ""))
        self.assert_fails_with(
            'FR-2 has no Verification line: add "Verification: '
            '<test name or command>"', "--phase", "requirements")

    def test_placeholder_verification(self):
        self.write("docs/requirements.md", REQ_OK.replace(
            "Verification: test_reminders",
            "Verification: <test name or command>"))
        self.assert_fails_with(
            "FR-1 Verification is still the template placeholder: name the "
            "test or command", "--phase", "requirements")

    def test_not_ears(self):
        self.write("docs/requirements.md", REQ_OK.replace(
            "- FR-1.2 IF the reminder fails THEN THE SYSTEM SHALL retry once.",
            "- FR-1.2 The system retries failed reminders."))
        self.assert_fails_with(
            "FR-1.2 is not in EARS form: use WHEN/IF/WHILE/WHERE ... "
            "THE SYSTEM SHALL ...", "--phase", "requirements")

    def test_traceability_mentions_are_not_checked(self):
        p = self.run_ready("--phase", "requirements")
        self.assertEqual(p.returncode, 0, p.stdout)

    def test_no_nfr_sec(self):
        self.write("docs/requirements.md", "\n".join(
            ln for ln in REQ_OK.splitlines() if "NFR-SEC" not in ln) + "\n")
        self.assert_fails_with("docs/requirements.md has no NFR-SEC line",
                               "--phase", "requirements")

    def test_adr_area_missing(self):
        (self.root / "docs/adr/0005-x.md").unlink()
        self.assert_fails_with("no ADR covers observability",
                               "--phase", "architecture")

    def test_adr_matched_by_title(self):
        # 0005-x.md matches observability only through its title.
        p = self.run_ready("--phase", "architecture")
        self.assertEqual(p.returncode, 0, p.stdout)

    def test_claude_md_too_long(self):
        self.write("CLAUDE.md", "- x\n" * 120)
        self.assert_fails_with(
            "CLAUDE.md has 120 lines: cut it to under 100",
            "--phase", "agent-config")

    def test_missing_file_names_template(self):
        (self.root / "CLAUDE.md").unlink()
        self.assert_fails_with(
            "CLAUDE.md is missing: write it from the skill's "
            "assets/claude-md-template.md", "--phase", "agent-config")

    def test_phase_limits_checks(self):
        (self.root / "CLAUDE.md").unlink()
        p = self.run_ready("--phase", "requirements")
        self.assertEqual(p.returncode, 0, p.stdout)

    def test_all_lists_every_issue(self):
        (self.root / "CLAUDE.md").unlink()
        (self.root / "docs/adr/0003-auth.md").unlink()
        p = self.run_ready()
        self.assertIn("NOT READY: 2 issues", p.stdout)

    def test_root_not_a_directory(self):
        p = run_script(CHECK_READY, [str(self.root / "nope")], self.root)
        self.assertEqual(p.returncode, 1)
        self.assertIn("is not a directory", p.stdout + p.stderr)


if __name__ == "__main__":
    unittest.main()
