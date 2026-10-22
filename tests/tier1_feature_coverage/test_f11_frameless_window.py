"""
Feature 11: Frameless Transparent Desktop Window (Milestone M3).
Verifies pywebview.create_window with frameless=True, transparent=True, on_top=True,
easy_drag=False, and dimensions 720x160.
"""
import re
from tests.harness import BaseE2ETest, DesktopAppInspector


class TestFeature11FramelessWindow(BaseE2ETest):
    tier = 1
    feature_id = 11
    milestone = "M3"

    def _get_app_source(self) -> str:
        src = DesktopAppInspector.get_source()
        self.assertIsNotNone(src, "float_app.py not found")
        return src

    def test_f11_01_pywebview_import_and_window(self):
        """float_app.py imports webview and calls create_window."""
        src = self._get_app_source()
        has_import = "import webview" in src or "from webview" in src or "pywebview" in src
        self.assertTrue(has_import, "float_app.py must import webview")
        self.assertIn("create_window", src, "float_app.py must call webview.create_window")

    def test_f11_02_frameless_and_transparent_flags(self):
        """Window is initialized with frameless=True and transparent=True."""
        src = self._get_app_source()
        self.assertTrue(bool(re.search(r'frameless\s*=\s*True', src)), "Missing frameless=True in create_window")
        self.assertTrue(bool(re.search(r'transparent\s*=\s*True', src)), "Missing transparent=True in create_window")

    def test_f11_03_on_top_and_easy_drag_flags(self):
        """Window is initialized with on_top=True and easy_drag=False (to scope drag)."""
        src = self._get_app_source()
        self.assertTrue(bool(re.search(r'on_top\s*=\s*True', src)), "Missing on_top=True in create_window")
        self.assertTrue(bool(re.search(r'easy_drag\s*=\s*False', src)), "Missing easy_drag=False (needed for scoped header drag)")

    def test_f11_04_initial_dimensions(self):
        """Initial dimensions are 720px width and 160px height."""
        src = self._get_app_source()
        self.assertTrue(bool(re.search(r'width\s*=\s*720', src)), "Window width should be 720")
        self.assertTrue(bool(re.search(r'height\s*=\s*160', src)), "Window height should be 160")

    def test_f11_05_background_color_transparency(self):
        """Window background color is configured transparent or headless."""
        src = self._get_app_source()
        has_trans_bg = ("#00000000" in src or "transparent" in src.lower() or "background_color" in src)
        self.assertTrue(has_trans_bg, "Window background should be set to transparent")
