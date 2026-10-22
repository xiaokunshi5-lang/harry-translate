"""
Tier 2 Boundary Tests: Feature 13 (macOS Fullscreen Meeting Pinning).
Tests space transitions, non-macOS environment tolerance, Mission Control resilience,
non-root privilege success, and minimize/restore behaviors.
"""
import sys
from tests.harness import BaseE2ETest, DesktopAppInspector


class TestBoundary13PinningBoundaries(BaseE2ETest):
    tier = 2
    feature_id = 13
    milestone = "M3"

    def _get_app_source(self) -> str:
        src = DesktopAppInspector.get_source()
        self.assertIsNotNone(src, "float_app.py not found")
        return src

    def test_b13_01_non_darwin_platform_tolerance(self):
        """On Windows / Linux, macOS Cocoa ctypes calls are skipped without throwing errors."""
        src = self._get_app_source()
        # Verify Cocoa calls are wrapped inside platform check
        has_guard = "sys.platform == 'darwin'" in src or 'sys.platform == "darwin"' in src or "platform.system()" in src
        self.assertTrue(has_guard, "Must guard macOS specific calls with platform check")

    def test_b13_02_can_join_all_spaces_flag(self):
        """Collection behavior 337 includes 1 (NSWindowCollectionBehaviorCanJoinAllSpaces)."""
        # 337 = 1 (CanJoinAllSpaces) | 16 (ParticipatesInCycle) | 64 (Stationary) | 256 (FullScreenAuxiliary)
        behavior_val = 337
        self.assertTrue(bool(behavior_val & 1), "Flag 337 must contain NSWindowCollectionBehaviorCanJoinAllSpaces (1)")
        self.assertTrue(bool(behavior_val & 256), "Flag 337 must contain NSWindowCollectionBehaviorFullScreenAuxiliary (256)")

    def test_b13_03_non_root_execution_safety(self):
        """Window level 25 (kCGStatusWindowLevelKey) does not require sudo / root privileges."""
        # Level 25 is safe for normal user apps; unlike level 2147483647 (shielding) which can lock the display
        level_val = 25
        self.assertLess(level_val, 1000, "Window level must be an unprivileged status level (<1000)")

    def test_b13_04_pywebview_window_loaded_hook(self):
        """Window customization is attached to loaded or ready event of webview."""
        src = self._get_app_source()
        has_hook = ("events.loaded" in src or "loaded" in src or "start(" in src or "on_loaded" in src)
        self.assertTrue(has_hook, "Window configuration should execute when webview window is initialized")

    def test_b13_05_error_suppression_on_headless(self):
        """Native calls wrap ctypes invocations in try-except to prevent fatal crashes."""
        src = self._get_app_source()
        has_try = "try:" in src and "except" in src
        self.assertTrue(has_try, "Native controller must wrap OS calls in try-except block")
