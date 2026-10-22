"""
Tier 2 Boundary Tests: Feature 16 (Cross-Platform Launch Scripts).
Tests space/special characters in directory paths, arbitrary working directory execution,
missing .venv handling, and Windows batch file path quoting.
"""
import os
import subprocess
from tests.harness import BaseE2ETest, ScriptInspector, PROJECT_ROOT


class TestBoundary16LaunchBoundaries(BaseE2ETest):
    tier = 2
    feature_id = 16
    milestone = "M4"

    def test_b16_01_script_path_with_spaces_and_chinese(self):
        """Scripts properly quote path variables to handle Chinese characters and spaces."""
        mac_script = ScriptInspector.get_content("启动悬浮同传.command")
        self.assertIsNotNone(mac_script)
        # Should have quotes around "$DIR" or equivalent variable
        has_quoted_dir = ('"$DIR"' in mac_script or '"$(dirname' in mac_script or '"$0"' in mac_script)
        self.assertTrue(has_quoted_dir, "macOS script must quote directory paths to support spaces in path")

    def test_b16_02_script_resolves_own_directory(self):
        """macOS .command script computes absolute directory via dirname "$0"."""
        mac_script = ScriptInspector.get_content("启动悬浮同传.command")
        self.assertIsNotNone(mac_script)
        self.assertIn("dirname", mac_script, "Script must use dirname $0 to resolve working directory")

    def test_b16_03_windows_bat_dp0_path_resolution(self):
        """Windows .bat script uses %~dp0 to resolve its own execution directory."""
        win_hud = ScriptInspector.get_content("启动悬浮同传.bat")
        self.assertIsNotNone(win_hud)
        self.assertIn("%~dp0", win_hud, "Windows bat file must use %~dp0 for directory resolution")

    def test_b16_04_missing_venv_guidance(self):
        """Scripts check for .venv existence before running."""
        mac_script = ScriptInspector.get_content("启动悬浮同传.command")
        self.assertIsNotNone(mac_script)
        # Should check if .venv exists
        has_check = (".venv" in mac_script)
        self.assertTrue(has_check, "Script must check for .venv presence")

    def test_b16_05_windows_cmd_powershell_neutrality(self):
        """Windows bat files start with @echo off and use standard cmd syntax."""
        win_bat = ScriptInspector.get_content("启动悬浮同传.bat")
        self.assertIsNotNone(win_bat)
        self.assertTrue(win_bat.strip().startswith("@echo off"), "Windows bat files must start with @echo off")
