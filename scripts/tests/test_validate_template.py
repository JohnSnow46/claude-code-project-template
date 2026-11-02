"""Negative tests for scripts/validate_template.py: each breaks one rule in a copy of
the repo and asserts the validator catches it. Run: python -m unittest discover scripts/tests"""
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
VALIDATOR = ROOT / "scripts" / "validate_template.py"


def run(root: Path) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(VALIDATOR), str(root)], capture_output=True, text=True)


class ValidateTemplateTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        for item in ("CLAUDE.md", "README.md", "USAGE.md", "docs", ".claude"):
            src = ROOT / item
            dst = self.tmp / item
            shutil.copytree(src, dst) if src.is_dir() else shutil.copy(src, dst)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def edit(self, rel: str, old: str, new: str):
        path = self.tmp / rel
        text = path.read_text(encoding="utf-8")
        self.assertIn(old, text, f"fixture text not found in {rel}")
        path.write_text(text.replace(old, new, 1), encoding="utf-8")

    def assertFails(self, needle: str):
        result = run(self.tmp)
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn(needle, result.stderr)

    def test_repo_passes(self):
        result = run(ROOT)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_unknown_agent_reference(self):
        (self.tmp / ".claude/agents/builder.md").unlink()
        self.assertFails("unknown agent `builder`")

    def test_agent_name_mismatch(self):
        self.edit(".claude/agents/builder.md", "name: builder", "name: coder")
        self.assertFails("doesn't match file name")

    def test_reviewer_must_be_read_only(self):
        self.edit(".claude/agents/reviewer.md", "tools: Read, Grep, Glob, Bash", "tools: Read, Edit, Bash")
        self.assertFails("must be read-only")

    def test_broken_link(self):
        (self.tmp / "USAGE.md").unlink()
        self.assertFails("broken link")

    def test_fast_mode_must_not_spawn_agents(self):
        self.edit("CLAUDE.md", "| **Fast** | You implement", "| **Fast** | `builder` → `reviewer-lite`. You implement")
        self.assertFails("Fast workflow must run without subagents")

    def test_loop_cap_required(self):
        self.edit("CLAUDE.md", "Max **2**", "Up to a few")
        self.assertFails("2-cycle cap")

    def test_security_override_required(self):
        self.edit("CLAUDE.md", "**Security override:**", "**Note:**")
        self.assertFails("security override")

    def test_bulk_add_deny_required(self):
        self.edit(".claude/settings.json", '"Bash(git add -A)",', "")
        self.assertFails("permissions.deny missing Bash(git add -A)")

    def test_push_must_not_be_preapproved(self):
        self.edit(".claude/settings.json", '"Bash(git log *)"', '"Bash(git log *)", "Bash(git push *)"')
        self.assertFails("must not pre-approve")

    def test_guard_hook_required(self):
        self.edit(".claude/settings.json", "guard-bash.sh", "other.sh")
        self.assertFails("guard-bash.sh")

    def test_claude_md_size_budget(self):
        with open(self.tmp / "CLAUDE.md", "a", encoding="utf-8") as f:
            f.write("\n" * 200)
        self.assertFails("over 130 lines")


if __name__ == "__main__":
    unittest.main()
