"""Feature 17: Safe version recovery without destructive local scripts."""

import os

from tests.harness import BaseE2ETest, PROJECT_ROOT


class TestFeature17SafeRecovery(BaseE2ETest):
    tier = 1
    feature_id = 17
    milestone = "M4"

    def _read(self, name):
        with open(os.path.join(PROJECT_ROOT, name), encoding="utf-8") as handle:
            return handle.read()

    def test_f17_01_public_baseline_is_documented(self):
        self.assertIn("v3.6.0", self._read("README.md"))
        self.assertIn("v3.6.0", self._read("CHANGELOG.md"))

    def test_f17_02_environment_is_ignored(self):
        ignored = self._read(".gitignore").splitlines()
        self.assertIn(".env", ignored)
        self.assertIn(".venv/", ignored)

    def test_f17_03_private_key_template_is_safe(self):
        template = self._read(".env.example")
        self.assertIn("DASHSCOPE_API_KEY=replace-with-your-dashscope-api-key", template)

    def test_f17_04_recovery_uses_standard_git_without_forced_reset(self):
        readme = self._read("README.md")
        self.assertIn("git switch", readme)
        self.assertNotIn("git reset --hard", readme)

    def test_f17_05_public_distribution_excludes_local_env(self):
        self.assertFalse(os.path.exists(os.path.join(PROJECT_ROOT, ".env")))


if __name__ == "__main__":
    import unittest

    unittest.main()
