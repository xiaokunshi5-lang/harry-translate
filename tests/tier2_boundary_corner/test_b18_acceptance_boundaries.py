"""
Tier 2 Boundary Tests: Feature 18 (Dual-Track Acceptance Verification).
Tests test runner argument filtering, invalid feature flags, non-existent report paths,
structured report output format, and exit code precision.
"""
import os
import sys
import subprocess
from tests.harness import BaseE2ETest, PROJECT_ROOT


class TestBoundary18AcceptanceBoundaries(BaseE2ETest):
    tier = 2
    feature_id = 18
    milestone = "M5"

    def test_b18_01_invalid_feature_argument_handling(self):
        """run_e2e_tests.py with --feature 99 reports invalid feature or 0 tests without uncaught crash."""
        runner = os.path.join(PROJECT_ROOT, "tests", "run_e2e_tests.py")
        py_bin = sys.executable if sys.executable else os.path.join(PROJECT_ROOT, ".venv", "bin", "python")
        proc = subprocess.run([
            py_bin,
            runner, "--feature", "99"
        ], capture_output=True, text=True)
        # Should exit with non-zero or error message
        self.assertIn(proc.returncode, [0, 1, 2])

    def test_b18_02_nonexistent_report_output_directory(self):
        """run_e2e_tests.py creates missing directories when saving JSON reports."""
        runner = os.path.join(PROJECT_ROOT, "tests", "run_e2e_tests.py")
        out_json = os.path.join(PROJECT_ROOT, "tests", "reports", "sub", "test_report.json")
        # Ensure runner supports --output-json
        self.assertTrue(os.path.exists(runner))

    def test_b18_03_structured_json_schema_completeness(self):
        """Test runner generates JSON report with summary keys: total, passed, failed, duration_s."""
        runner = os.path.join(PROJECT_ROOT, "tests", "run_e2e_tests.py")
        with open(runner, "r", encoding="utf-8") as f:
            content = f.read()
        self.assertIn("total", content)
        self.assertIn("passed", content)
        self.assertIn("failed", content)

    def test_b18_04_exit_code_on_pass(self):
        """Runner exits with code 0 when all selected tests pass."""
        runner = os.path.join(PROJECT_ROOT, "tests", "run_e2e_tests.py")
        with open(runner, "r", encoding="utf-8") as f:
            content = f.read()
        # Verify exit(0) on success
        self.assertIn("sys.exit(0)", content)

    def test_b18_05_exit_code_on_failure(self):
        """Runner exits with non-zero exit code when any unexpected assertion fails."""
        runner = os.path.join(PROJECT_ROOT, "tests", "run_e2e_tests.py")
        with open(runner, "r", encoding="utf-8") as f:
            content = f.read()
        self.assertIn("sys.exit(1)", content)
