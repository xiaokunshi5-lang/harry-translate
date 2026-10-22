#!/usr/bin/env python3
"""Portable checks for the public repository contract."""

import os
import re
import stat
import subprocess
import unittest


PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

PUBLIC_DOCUMENTS = [
    "README.md",
    "INSTALL.md",
    "USER_MANUAL.md",
    "TROUBLESHOOTING.md",
    "SECURITY.md",
    "CONTRIBUTING.md",
    "CHANGELOG.md",
    "LICENSE",
    "NOTICE",
]

FORBIDDEN_PRIVATE_PATHS = [
    "/Users/",
    "/var/folders/",
    "C:\\Users\\",
]

PLACEHOLDER_KEY_PATTERN = re.compile(r"sk-(?:your|actual|dashscope)[A-Za-z0-9_-]*", re.I)


class TestPublicReleasePolicy(unittest.TestCase):
    def test_public_documents_exist(self):
        for name in PUBLIC_DOCUMENTS:
            path = os.path.join(PROJECT_ROOT, name)
            self.assertTrue(os.path.isfile(path), f"Missing public document: {name}")
            self.assertGreater(os.path.getsize(path), 100, f"Public document is unexpectedly short: {name}")

    def test_readme_has_portable_macos_and_windows_steps(self):
        with open(os.path.join(PROJECT_ROOT, "README.md"), encoding="utf-8") as handle:
            content = handle.read()
        self.assertIn("Part 1: macOS", content)
        self.assertIn("Part 2: Windows", content)
        self.assertIn("git clone", content)
        self.assertIn(".env.example", content)
        self.assertNotIn("YOUR_GITHUB_USERNAME", content)

    def test_brand_consistency(self):
        for name in ("README.md", "server.py", "float_ui.html"):
            with open(os.path.join(PROJECT_ROOT, name), encoding="utf-8") as handle:
                self.assertIn("Harry Translate", handle.read(), f"Brand missing from {name}")

    def test_launch_scripts_are_executable_and_valid(self):
        for name in sorted(os.listdir(PROJECT_ROOT)):
            if not (name.endswith(".command") or name.endswith(".sh")):
                continue
            path = os.path.join(PROJECT_ROOT, name)
            self.assertTrue(os.stat(path).st_mode & stat.S_IXUSR, f"{name} is not executable")
            with open(path, encoding="utf-8") as handle:
                content = handle.read()
            self.assertNotIn("../.env", content, f"{name} must not inherit a parent .env")
            self.assertNotIn("../.venv", content, f"{name} must not inherit a parent .venv")
            for shell in ("bash", "zsh"):
                result = subprocess.run(
                    [shell, "-n", path],
                    capture_output=True,
                    text=True,
                    check=False,
                )
                self.assertEqual(result.returncode, 0, f"{shell} syntax failed for {name}: {result.stderr}")

    def test_no_private_absolute_paths_in_source(self):
        violations = []
        for root, dirs, files in os.walk(PROJECT_ROOT):
            dirs[:] = [name for name in dirs if name not in {".git", ".venv", "__pycache__"}]
            for name in files:
                if not name.endswith((".py", ".html", ".md", ".json", ".sh", ".command", ".bat", ".txt")):
                    continue
                path = os.path.join(root, name)
                if os.path.abspath(path) == os.path.abspath(__file__):
                    continue
                with open(path, encoding="utf-8", errors="replace") as handle:
                    content = handle.read()
                for needle in FORBIDDEN_PRIVATE_PATHS:
                    if needle in content:
                        violations.append(f"{os.path.relpath(path, PROJECT_ROOT)} contains {needle}")
        self.assertEqual(violations, [], "\n".join(violations))

    def test_no_env_file_or_placeholder_secret_is_tracked_content(self):
        with open(os.path.join(PROJECT_ROOT, ".gitignore"), encoding="utf-8") as handle:
            self.assertIn(".env", handle.read().splitlines())
        example_path = os.path.join(PROJECT_ROOT, ".env.example")
        self.assertTrue(os.path.isfile(example_path))
        with open(example_path, encoding="utf-8") as handle:
            self.assertIsNone(PLACEHOLDER_KEY_PATTERN.search(handle.read()))


if __name__ == "__main__":
    unittest.main()
