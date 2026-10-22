"""
Feature 16: Cross-Platform Launch Scripts (Milestone M4).
Verifies double-clickable launch scripts: macOS 启动悬浮同传.command,
Windows 启动悬浮同传.bat, 启动同传系统.bat, and 切换API_Key.bat.
"""
import os
import stat
from tests.harness import BaseE2ETest, ScriptInspector, PROJECT_ROOT


class TestFeature16LaunchScripts(BaseE2ETest):
    tier = 1
    feature_id = 16
    milestone = "M4"

    def test_f16_01_macos_hud_command_exists(self):
        """macOS 启动悬浮同传.command exists and has executable permissions."""
        path = os.path.join(PROJECT_ROOT, "启动悬浮同传.command")
        self.assertTrue(os.path.exists(path), "Missing 启动悬浮同传.command")
        file_stat = os.stat(path)
        is_executable = bool(file_stat.st_mode & (stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH))
        self.assertTrue(is_executable, "启动悬浮同传.command must have executable permission (+x)")

    def test_f16_02_macos_hud_command_content(self):
        """启动悬浮同传.command launches float_app.py using .venv python."""
        content = ScriptInspector.get_content("启动悬浮同传.command")
        self.assertIsNotNone(content, "启动悬浮同传.command not found")
        self.assertIn("float_app.py", content, "Script does not reference float_app.py")
        has_venv = ".venv" in content or "venv" in content
        self.assertTrue(has_venv, "Script should activate or reference .venv")

    def test_f16_03_windows_hud_bat_exists(self):
        """Windows 启动悬浮同传.bat exists and launches float_app.py."""
        path = os.path.join(PROJECT_ROOT, "启动悬浮同传.bat")
        self.assertTrue(os.path.exists(path), "Missing Windows 启动悬浮同传.bat")
        content = ScriptInspector.get_content("启动悬浮同传.bat")
        self.assertIn("float_app.py", content)

    def test_f16_04_windows_dual_screen_bat_exists(self):
        """Windows 启动同传系统.bat exists and launches server.py."""
        path = os.path.join(PROJECT_ROOT, "启动同传系统.bat")
        self.assertTrue(os.path.exists(path), "Missing Windows 启动同传系统.bat")
        content = ScriptInspector.get_content("启动同传系统.bat")
        self.assertIn("server.py", content)

    def test_f16_05_windows_switch_key_bat_exists(self):
        """Windows 切换API_Key.bat exists and launches switch_key.py."""
        path = os.path.join(PROJECT_ROOT, "切换API_Key.bat")
        self.assertTrue(os.path.exists(path), "Missing Windows 切换API_Key.bat")
        content = ScriptInspector.get_content("切换API_Key.bat")
        self.assertIn("switch_key.py", content)
