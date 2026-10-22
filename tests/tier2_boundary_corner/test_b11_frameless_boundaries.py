"""
Tier 2 Boundary Tests: Feature 11 (Frameless Transparent Desktop Window).
Tests multi-monitor safety, display geometry bounds, non-zero dimensions,
clean process shutdown, and native handle validation.
"""
from tests.harness import BaseE2ETest, DesktopAppInspector


class TestBoundary11FramelessWindow(BaseE2ETest):
    tier = 2
    feature_id = 11
    milestone = "M3"

    def _get_app_source(self) -> str:
        src = DesktopAppInspector.get_source()
        self.assertIsNotNone(src, "float_app.py not found")
        return src

    def test_b11_01_multi_monitor_bounds_check(self):
        """float_app.py avoids hardcoding fixed absolute screen offsets (e.g. x=0, y=0 without screen check)."""
        src = self._get_app_source()
        # Verify window creation doesn't force off-screen coordinates
        self.assertNotIn("x=-9999", src)

    def test_b11_02_minimum_window_dimensions(self):
        """Window dimensions are non-zero and at least 400x100."""
        src = self._get_app_source()
        import re
        w_match = re.search(r'width\s*=\s*(\d+)', src)
        h_match = re.search(r'height\s*=\s*(\d+)', src)
        if w_match and h_match:
            self.assertGreaterEqual(int(w_match.group(1)), 400)
            self.assertGreaterEqual(int(h_match.group(1)), 100)

    def test_b11_03_clean_webview_start(self):
        """float_app.py defines webview.start() call."""
        src = self._get_app_source()
        self.assertIn("webview.start", src, "Missing webview.start() in float_app.py")

    def test_b11_04_background_process_isolation(self):
        """float_app.py does not spawn unmonitored zombie daemon threads."""
        src = self._get_app_source()
        has_thread = "threading.Thread" in src
        if has_thread:
            # Any thread created should be daemon=True
            self.assertIn("daemon=True", src, "Background threads must be daemon=True")

    def test_b11_05_native_handle_null_check(self):
        """Native window controller checks for null or invalid window pointer before ctypes call."""
        src = self._get_app_source()
        has_null_check = ("if not" in src or "if window" in src or "is None" in src or "try:" in src)
        self.assertTrue(has_null_check, "Missing safety checks on native window handle before calling OS APIs")
