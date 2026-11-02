"""Tests for scripts/quality-gates.sh in a throwaway repo: a failing gate fails the run,
strict mode refuses unconfigured gates, `none` is an allowed skip, the security gate
always runs. Run: python -m unittest discover -s scripts/tests"""
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from helpers import ROOT, bash


class QualityGatesTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        (self.tmp / "scripts").mkdir()
        (self.tmp / ".claude/hooks").mkdir(parents=True)
        for rel in ("scripts/quality-gates.sh", "scripts/check-deps.sh",
                    ".claude/hooks/scan-secrets.sh", ".claude/settings.json"):
            shutil.copy(ROOT / rel, self.tmp / rel)
        subprocess.run(["git", "init", "-q"], cwd=self.tmp, check=True)
        self.conf = self.tmp / ".claude/quality-gates.conf"

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def gates(self, conf: str, *args, **env) -> subprocess.CompletedProcess:
        self.conf.write_text(conf, encoding="utf-8")
        full_env = dict(os.environ)
        for key in ("QUALITY_GATES_STRICT", "REQUIRE_GITLEAKS", "REQUIRE_DEP_AUDIT"):
            full_env.pop(key, None)
        full_env.update({"QUALITY_GATES_STRICT": "0", "REQUIRE_GITLEAKS": "0", "REQUIRE_DEP_AUDIT": "0"})
        full_env.update(env)
        return subprocess.run([bash(), "scripts/quality-gates.sh", *args], cwd=self.tmp,
                              capture_output=True, text=True, env=full_env)

    def test_all_pass(self):
        r = self.gates("test=true\nlint=true\ntypecheck=none\nbuild=true\n")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("RESULT: PASS", r.stdout)

    def test_failing_gate_fails_run(self):
        r = self.gates("test=exit 3\nlint=true\ntypecheck=none\nbuild=none\n")
        self.assertEqual(r.returncode, 1)
        self.assertRegex(r.stdout, r"test\s+FAIL")
        self.assertIn("RESULT: FAIL", r.stdout)

    def test_later_gates_still_reported_after_a_failure(self):
        r = self.gates("test=false\nlint=true\ntypecheck=none\nbuild=none\n")
        self.assertRegex(r.stdout, r"lint\s+PASS")

    def test_unconfigured_gate_skips_by_default(self):
        r = self.gates("test=true\nlint=\ntypecheck=none\nbuild=none\n")
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertRegex(r.stdout, r"lint\s+SKIP\s+not configured")

    def test_unconfigured_gate_fails_in_strict_mode(self):
        r = self.gates("test=true\nlint=\ntypecheck=none\nbuild=none\n", QUALITY_GATES_STRICT="1")
        self.assertEqual(r.returncode, 1)
        self.assertRegex(r.stdout, r"lint\s+FAIL\s+not configured")

    def test_none_is_allowed_in_strict_mode(self):
        r = self.gates("test=true\nlint=true\ntypecheck=none\nbuild=none\n", QUALITY_GATES_STRICT="1")
        self.assertEqual(r.returncode, 0, r.stdout)

    def test_security_gate_catches_committed_secret_file(self):
        (self.tmp / ".env").write_text("X=1\n", encoding="utf-8")
        subprocess.run(["git", "add", "-f", ".env"], cwd=self.tmp, check=True)
        r = self.gates("test=none\nlint=none\ntypecheck=none\nbuild=none\n", "security")
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertRegex(r.stdout, r"security\s+FAIL")

    def test_only_selected_gates_run(self):
        r = self.gates("test=false\nlint=true\ntypecheck=none\nbuild=none\n", "lint")
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertNotIn("test ", r.stdout.split("Quality gates")[1])

    def test_unknown_gate_is_usage_error(self):
        self.assertEqual(self.gates("test=true\n", "deploy").returncode, 2)

    def test_detect_node_project(self):
        (self.tmp / "package.json").write_text('{"scripts": {"test": "vitest", "lint": "eslint ."}}', encoding="utf-8")
        (self.tmp / "tsconfig.json").write_text("{}", encoding="utf-8")
        r = self.gates("", "--detect")
        self.assertIn("test=npm test", r.stdout)
        self.assertIn("lint=npm run lint", r.stdout)
        self.assertIn("typecheck=npx tsc --noEmit", r.stdout)
        self.assertIn("build=none", r.stdout)


if __name__ == "__main__":
    unittest.main()
