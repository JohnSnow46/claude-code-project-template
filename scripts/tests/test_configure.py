"""Tests for scripts/configure.py (profiles and agent models), run on a temporary copy.
Run: python -m unittest discover -s scripts/tests"""
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from helpers import ROOT

CONFIGURE = ROOT / "scripts" / "configure.py"


class ConfigureTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        shutil.copytree(ROOT / ".claude", self.tmp / ".claude")
        self.settings = self.tmp / ".claude/settings.json"

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def cfg(self, *args, ok=True) -> subprocess.CompletedProcess:
        r = subprocess.run([sys.executable, str(CONFIGURE), "--root", str(self.tmp), *args],
                           capture_output=True, text=True)
        if ok:
            self.assertEqual(r.returncode, 0, r.stderr)
        return r

    def load(self) -> dict:
        return json.loads(self.settings.read_text(encoding="utf-8"))

    def test_round_trip_through_every_profile_is_lossless(self):
        original = self.settings.read_bytes()
        for name in ("team", "high-security", "solo", "high-security", "team", "solo"):
            self.cfg("profile", name)
        self.assertEqual(self.settings.read_bytes(), original)

    def test_high_security_applies_overlay(self):
        self.cfg("profile", "high-security")
        s = self.load()
        self.assertEqual(s["env"]["CLAUDE_TEMPLATE_PROFILE"], "high-security")
        self.assertEqual(s["env"]["CLAUDE_GUARD_STRICT"], "1")
        self.assertIn("WebFetch", s["permissions"]["deny"])
        self.assertEqual(s["permissions"]["disableBypassPermissionsMode"], "disable")
        self.assertTrue(s["sandbox"]["enabled"])
        # Base rules survive.
        self.assertIn("Read(**/.env)", s["permissions"]["deny"])

    def test_switching_down_removes_stricter_rules(self):
        self.cfg("profile", "high-security")
        self.cfg("profile", "team")
        s = self.load()
        self.assertNotIn("WebFetch", s["permissions"]["deny"])
        self.assertNotIn("sandbox", s)
        self.assertNotIn("CLAUDE_GUARD_STRICT", s["env"])
        self.assertIn("Bash(git push * main)", s["permissions"]["deny"])

    def test_user_rules_are_kept(self):
        s = self.load()
        s["permissions"]["allow"].append("Bash(npm test *)")
        self.settings.write_text(json.dumps(s, indent=2), encoding="utf-8")
        self.cfg("profile", "high-security")
        self.cfg("profile", "solo")
        self.assertIn("Bash(npm test *)", self.load()["permissions"]["allow"])

    def test_user_rules_overlapping_a_profile_survive_switching(self):
        # The user already denies curl and runs the sandbox (with their own settings)
        # before ever picking high-security, which sets the same things.
        s = self.load()
        s["permissions"]["deny"].append("Bash(curl *)")
        s["sandbox"] = {"enabled": True, "autoAllowBashIfSandboxed": False}
        self.settings.write_text(json.dumps(s, indent=2), encoding="utf-8")
        self.cfg("profile", "high-security")
        self.cfg("profile", "solo")
        after = self.load()
        self.assertIn("Bash(curl *)", after["permissions"]["deny"])
        self.assertEqual(after["sandbox"], {"enabled": True, "autoAllowBashIfSandboxed": False})
        self.assertNotIn("WebFetch", after["permissions"]["deny"])

    def test_user_value_replaced_by_profile_is_restored(self):
        s = self.load()
        s["permissions"]["disableBypassPermissionsMode"] = "custom"
        self.settings.write_text(json.dumps(s, indent=2), encoding="utf-8")
        self.cfg("profile", "high-security")
        self.assertEqual(self.load()["permissions"]["disableBypassPermissionsMode"], "disable")
        self.cfg("profile", "team")
        self.assertEqual(self.load()["permissions"]["disableBypassPermissionsMode"], "custom")

    def test_works_without_a_state_file(self):
        (self.tmp / ".claude/profile-state.json").unlink(missing_ok=True)
        original = self.settings.read_bytes()
        self.cfg("profile", "team")
        self.cfg("profile", "solo")
        self.assertEqual(self.settings.read_bytes(), original)

    def test_unknown_profile_fails_without_writing(self):
        before = self.settings.read_bytes()
        r = self.cfg("profile", "paranoid", ok=False)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("unknown profile", r.stderr)
        self.assertEqual(self.settings.read_bytes(), before)

    def model(self, agent: str) -> str:
        text = (self.tmp / f".claude/agents/{agent}.md").read_text(encoding="utf-8")
        return next(line.split(":", 1)[1].strip() for line in text.splitlines() if line.startswith("model:"))

    def test_models_by_tier(self):
        self.cfg("models", "--strong", "sonnet", "--standard", "haiku")
        self.assertEqual(self.model("architect"), "sonnet")
        self.assertEqual(self.model("security-auditor"), "sonnet")
        self.assertEqual(self.model("builder"), "haiku")
        self.assertEqual(self.model("performance-analyst"), "haiku")

    def test_models_all_inherit(self):
        self.cfg("models", "--all", "inherit")
        for agent in (self.tmp / ".claude/agents").glob("*.md"):
            self.assertEqual(self.model(agent.stem), "inherit")

    def test_invalid_model_rejected(self):
        r = self.cfg("models", "--all", "gpt-4", ok=False)
        self.assertNotEqual(r.returncode, 0)
        self.assertEqual(self.model("builder"), "sonnet")

    def test_fallback_chain(self):
        self.cfg("models", "--fallback", "sonnet,haiku")
        self.assertEqual(self.load()["fallbackModel"], ["sonnet", "haiku"])
        self.cfg("models", "--fallback", "")
        self.assertNotIn("fallbackModel", self.load())

    def test_fallback_limits(self):
        self.assertNotEqual(self.cfg("models", "--fallback", "opus,sonnet,haiku,fable", ok=False).returncode, 0)
        self.assertNotEqual(self.cfg("models", "--fallback", "inherit", ok=False).returncode, 0)


if __name__ == "__main__":
    unittest.main()
