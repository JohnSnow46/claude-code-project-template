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
        for item in ("CLAUDE.md", "README.md", "USAGE.md", "LICENSE", "THIRD_PARTY_NOTICES.md", "docs", ".claude", ".github", "scripts"):
            src = ROOT / item
            dst = self.tmp / item
            if src.is_dir():
                shutil.copytree(src, dst, ignore=shutil.ignore_patterns("__pycache__"))
            else:
                shutil.copy(src, dst)

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
        self.edit("CLAUDE.md", "| You implement →", "| `builder` → `reviewer-lite`. You implement →")
        self.assertFails("Fast workflow must run without subagents")

    def test_trivial_mode_must_not_spawn_agents(self):
        self.edit("CLAUDE.md", "| You edit →", "| `reviewer-lite`. You edit →")
        self.assertFails("Trivial workflow must run without subagents")

    def test_loop_cap_required(self):
        self.edit(".claude/skills/workflow/SKILL.md", "Max **2**", "Up to a few")
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

    def test_copy_passes(self):
        # Negative tests only mean something if the untouched copy is valid.
        result = run(self.tmp)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_nested_env_deny_required(self):
        self.edit(".claude/settings.json", '"Read(**/.env)",', "")
        self.assertFails("permissions.deny missing Read(**/.env)")

    def test_env_edit_deny_required(self):
        self.edit(".claude/settings.json", '"Edit(**/.env.*)",', "")
        self.assertFails("permissions.deny missing Edit(**/.env.*)")

    def test_file_guard_must_cover_read(self):
        self.edit(".claude/settings.json", '"matcher": "Read|Edit|', '"matcher": "Edit|')
        self.assertFails("guard-files.sh must cover Read")

    def test_file_guard_hook_required(self):
        self.edit(".claude/settings.json", "guard-files.sh", "missing-guard.sh")
        self.assertFails("hook runs missing .claude/hooks/missing-guard.sh")

    def test_hooks_must_fail_closed(self):
        self.edit(".claude/settings.json", '"onFailure": "block"', '"onFailure": "allow"')
        self.assertFails("must set \"onFailure\": \"block\"")

    def test_analyst_must_be_read_only(self):
        self.edit(".claude/agents/performance-analyst.md", "tools: Read, Grep, Glob, Bash", "tools: Read, Edit, Bash")
        self.assertFails("must be read-only")

    def test_unknown_model(self):
        self.edit(".claude/agents/builder.md", "model: sonnet", "model: gpt-4")
        self.assertFails("unknown model 'gpt-4'")

    def test_quality_gates_section_required(self):
        self.edit("CLAUDE.md", "## Quality gates", "## Checks")
        self.assertFails("quality gates section")

    def test_gate_line_required(self):
        self.edit(".claude/quality-gates.conf", "typecheck=none", "")
        self.assertFails("missing 'typecheck=' line")

    def test_ci_must_run_gitleaks(self):
        path = self.tmp / ".github/workflows/checks.yml"
        path.write_text(path.read_text(encoding="utf-8").replace("gitleaks", "scanner"), encoding="utf-8")
        self.assertFails("CI must run gitleaks")

    def test_ci_must_run_quality_gates(self):
        self.edit(".github/workflows/checks.yml", "run: bash scripts/quality-gates.sh", "run: echo skipped")
        self.assertFails("CI must run the quality gates")

    def test_settings_out_of_sync_with_profile(self):
        self.edit(".claude/settings.json", '"CLAUDE_TEMPLATE_PROFILE": "solo"', '"CLAUDE_TEMPLATE_PROFILE": "team"')
        self.assertFails("out of sync with profile 'team'")

    def test_unknown_profile(self):
        self.edit(".claude/settings.json", '"CLAUDE_TEMPLATE_PROFILE": "solo"', '"CLAUDE_TEMPLATE_PROFILE": "paranoid"')
        self.assertFails("'paranoid' is not a profile")

    def test_profile_name_must_match_file(self):
        self.edit(".claude/profiles/team.json", '"CLAUDE_TEMPLATE_PROFILE": "team"', '"CLAUDE_TEMPLATE_PROFILE": "teams"')
        self.assertFails("must be 'team'")

    def test_claude_md_size_budget(self):
        with open(self.tmp / "CLAUDE.md", "a", encoding="utf-8") as f:
            f.write("\n" * 200)
        self.assertFails("over 130 lines")


if __name__ == "__main__":
    unittest.main()
