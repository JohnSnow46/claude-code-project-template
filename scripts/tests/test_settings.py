"""Behavioral tests for .claude/settings.json: each PreToolUse hook is run through the
exact `command` string from settings.json, the way Claude Code runs it, so a renamed
script, a wrong matcher or a broken path fails here — not only in the validator.
Run: python -m unittest discover -s scripts/tests"""
import json
import os
import re
import subprocess
import unittest

from helpers import ROOT, bash

SETTINGS = json.loads((ROOT / ".claude/settings.json").read_text(encoding="utf-8"))


def hook_commands(tool: str) -> list[str]:
    cmds = []
    for entry in SETTINGS["hooks"]["PreToolUse"]:
        matcher = entry.get("matcher", "")
        tools = {t.strip() for t in re.split(r"[|,]", matcher)}
        if tool in tools or matcher in ("", "*"):
            cmds += [h["command"] for h in entry["hooks"] if h.get("type") == "command"]
    return cmds


def run_hooks(tool: str, tool_input: dict, mode: str = "default") -> str:
    """Return the combined decision of every hook configured for `tool`: deny wins over ask."""
    payload = json.dumps({"session_id": "t", "hook_event_name": "PreToolUse", "permission_mode": mode,
                          "tool_name": tool, "tool_input": tool_input})
    env = dict(os.environ, CLAUDE_PROJECT_DIR=ROOT.as_posix())
    env.pop("CLAUDE_GUARD_STRICT", None)
    decisions = []
    commands = hook_commands(tool)
    assert commands, f"no PreToolUse hook configured for {tool}"
    for command in commands:
        r = subprocess.run([bash(), "-c", command], input=payload, capture_output=True, text=True, env=env, cwd=ROOT)
        if r.returncode == 2:
            decisions.append("deny")
        elif r.returncode != 0:
            decisions.append(f"error:{r.returncode}:{r.stderr.strip()}")
        elif '"permissionDecision":"ask"' in r.stdout.replace(" ", ""):
            decisions.append("ask")
        else:
            decisions.append("allow")
    for d in ("deny", "ask"):
        if d in decisions:
            return d
    errors = [d for d in decisions if d.startswith("error")]
    return errors[0] if errors else "allow"


class BashHookWiringTest(unittest.TestCase):
    def test_force_push_denied(self):
        self.assertEqual(run_hooks("Bash", {"command": "git -c x=y push origin main --force"}), "deny")

    def test_reading_nested_env_denied(self):
        self.assertEqual(run_hooks("Bash", {"command": "base64 services/api/.env"}), "deny")

    def test_reset_hard_asks(self):
        self.assertEqual(run_hooks("Bash", {"command": "git reset --hard"}), "ask")

    def test_reset_hard_denied_in_auto_mode(self):
        self.assertEqual(run_hooks("Bash", {"command": "git reset --hard"}, mode="auto"), "deny")

    def test_ordinary_command_allowed(self):
        self.assertEqual(run_hooks("Bash", {"command": "npm test && git status"}), "allow")


class FileHookWiringTest(unittest.TestCase):
    def test_every_file_tool_blocks_env(self):
        for tool, field in (("Read", "file_path"), ("Edit", "file_path"), ("Write", "file_path"),
                            ("MultiEdit", "file_path"), ("NotebookEdit", "notebook_path"), ("Grep", "path")):
            with self.subTest(tool=tool):
                self.assertEqual(run_hooks(tool, {field: str(ROOT / "apps" / "api" / ".env")}), "deny")

    def test_private_key_blocked(self):
        self.assertEqual(run_hooks("Read", {"file_path": "/srv/app/certs/tls.key"}), "deny")

    def test_template_and_source_allowed(self):
        self.assertEqual(run_hooks("Read", {"file_path": str(ROOT / ".env.example")}), "allow")
        self.assertEqual(run_hooks("Read", {"file_path": str(ROOT / "scripts" / "configure.py")}), "allow")


class PermissionRulesTest(unittest.TestCase):
    """Claude Code evaluates these rules itself; here we pin the rule set so a
    refactor can't silently drop one."""

    def setUp(self):
        self.perms = SETTINGS["permissions"]

    def test_secret_files_denied_at_any_depth(self):
        for rule in ("Read(**/.env)", "Read(**/.env.*)", "Edit(**/.env)", "Edit(**/.env.*)",
                     "Read(**/*.pem)", "Read(**/*.key)", "Read(~/.ssh/**)"):
            self.assertIn(rule, self.perms["deny"])

    def test_templates_carved_out_after_the_rules_they_open(self):
        deny = self.perms["deny"]
        for tool in ("Read", "Edit"):
            self.assertGreater(deny.index(f"{tool}(!**/.env.example)"), deny.index(f"{tool}(**/.env.*)"))

    def test_no_dangerous_preapproval(self):
        for rule in self.perms["allow"]:
            self.assertNotRegex(rule, r"^Bash(\(\*\))?$|git (push|add|reset|clean)|curl|wget|rm ")

    def test_push_and_destructive_git_ask(self):
        for rule in ("Bash(git push *)", "Bash(git reset --hard *)", "Bash(git clean *)"):
            self.assertIn(rule, self.perms["ask"])

    def test_hooks_fail_closed(self):
        for entry in SETTINGS["hooks"]["PreToolUse"]:
            for h in entry["hooks"]:
                self.assertEqual(h.get("onFailure"), "block", h["command"])


if __name__ == "__main__":
    unittest.main()
