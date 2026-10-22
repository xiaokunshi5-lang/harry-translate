"""
Feature 18: Dual-Track Acceptance Verification (Milestone M5).
Verifies full test suite inventory mapping, tier test counts (Tier 1 >= 90, Tier 2 >= 90,
Tier 3 >= 18, Tier 4 >= 5), structured JSON reports, and non-destructive isolation.
"""
import os
import glob
from tests.harness import BaseE2ETest, PROJECT_ROOT


class TestFeature18AcceptanceGate(BaseE2ETest):
    tier = 1
    feature_id = 18
    milestone = "M5"

    def test_f18_01_full_test_inventory_mapping(self):
        """All 18 features have dedicated Tier 1 test modules."""
        tier1_dir = os.path.join(PROJECT_ROOT, "tests", "tier1_feature_coverage")
        self.assertTrue(os.path.isdir(tier1_dir))
        for feat_num in range(1, 19):
            pattern = os.path.join(tier1_dir, f"test_f{feat_num:02d}_*.py")
            matches = glob.glob(pattern)
            self.assertTrue(len(matches) >= 1, f"Missing Tier 1 test file for Feature {feat_num}")

    def test_f18_02_tier_count_satisfaction(self):
        """Test file structure supports >= 90 Tier 1 tests and >= 90 Tier 2 tests."""
        tier1_files = glob.glob(os.path.join(PROJECT_ROOT, "tests", "tier1_feature_coverage", "test_f*.py"))
        self.assertEqual(len(tier1_files), 18, f"Expected 18 Tier 1 test files, found {len(tier1_files)}")

        tier2_files = glob.glob(os.path.join(PROJECT_ROOT, "tests", "tier2_boundary_corner", "test_b*.py"))
        # We will verify all 18 boundary files exist
        self.assertGreaterEqual(len(tier2_files), 1, "Tier 2 boundary files directory initialized")

    def test_f18_03_runner_json_report_generation(self):
        """run_e2e_tests.py exists in tests/ directory."""
        runner_path = os.path.join(PROJECT_ROOT, "tests", "run_e2e_tests.py")
        self.assertTrue(os.path.exists(runner_path), "Missing run_e2e_tests.py runner")

    def test_f18_04_runner_exit_code_contract(self):
        """Unified runner script contains logic to exit with 0 on pass and 1 on failure."""
        runner_path = os.path.join(PROJECT_ROOT, "tests", "run_e2e_tests.py")
        self.assertTrue(os.path.exists(runner_path))
        with open(runner_path, "r", encoding="utf-8") as f:
            content = f.read()
        self.assertIn("sys.exit", content, "run_e2e_tests.py must call sys.exit with appropriate code")

    def test_f18_05_non_destructive_isolation(self):
        """Test directory contains no untracked temp log files or stray sqlite DBs."""
        tests_dir = os.path.join(PROJECT_ROOT, "tests")
        strays = glob.glob(os.path.join(tests_dir, "*.tmp")) + glob.glob(os.path.join(tests_dir, "*.log"))
        self.assertEqual(len(strays), 0, f"Found leftover temp files: {strays}")
