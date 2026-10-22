"""Regression guard for dependency versions with known security advisories."""

import os
import re
import unittest


PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

MINIMUM_SAFE_VERSIONS = {
    "anyio": (4, 14, 2),
    "fastapi": (0, 140, 0),
    "python-dotenv": (1, 2, 2),
    "starlette": (1, 3, 1),
}


def parse_version(value):
    match = re.match(r"^(\d+)\.(\d+)\.(\d+)", value.strip())
    if not match:
        raise AssertionError(f"Version is not pinned to X.Y.Z: {value}")
    return tuple(int(part) for part in match.groups())


class TestDependencySecurity(unittest.TestCase):
    def test_requirements_are_at_or_above_patched_versions(self):
        requirements = {}
        with open(os.path.join(PROJECT_ROOT, "requirements.txt"), encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line or line.startswith("#") or "==" not in line:
                    continue
                name, version = line.split("==", 1)
                requirements[name.lower()] = version

        for name, minimum in MINIMUM_SAFE_VERSIONS.items():
            self.assertIn(name, requirements, f"Missing security-sensitive dependency: {name}")
            actual = parse_version(requirements[name])
            self.assertGreaterEqual(actual, minimum, f"{name} {requirements[name]} is below {minimum}")


if __name__ == "__main__":
    unittest.main()
