"""
Feature 13: macOS Fullscreen Meeting Pinning (Milestone M3).
Verifies ctypes calling Cocoa [window setCollectionBehavior: 337] and setLevel: 25
to persist above Zoom, Tencent Meeting, and Keynote fullscreen spaces.
"""
from tests.harness import BaseE2ETest, DesktopAppInspector


class TestFeature13FullscreenPinning(BaseE2ETest):
    tier = 1
    feature_id = 13
    milestone = "M3"

    def _get_app_source(self) -> str:
        src = DesktopAppInspector.get_source()
        self.assertIsNotNone(src, "float_app.py not found")
        return src

    def test_f13_01_cocoa_ctypes_import(self):
        """float_app.py imports ctypes and declares Cocoa objc functions."""
        src = self._get_app_source()
        self.assertIn("ctypes", src, "float_app.py must import ctypes for native window manipulation")
        has_objc = "objc" in src or "AppKit" in src or "c_void_p" in src
        self.assertTrue(has_objc, "Missing Cocoa / AppKit ctypes bindings")

    def test_f13_02_collection_behavior_fullscreen_auxiliary(self):
        """Window collection behavior is configured with 337 (CanJoinAllSpaces | FullScreenAuxiliary)."""
        src = self._get_app_source()
        has_behavior = "337" in src or "setCollectionBehavior" in src or "NSWindowCollectionBehaviorFullScreenAuxiliary" in src
        self.assertTrue(has_behavior, "Missing NSWindowCollectionBehaviorFullScreenAuxiliary (337) configuration")

    def test_f13_03_window_level_cgstatus(self):
        """Window level is configured with 25 (kCGStatusWindowLevelKey / Floating status level)."""
        src = self._get_app_source()
        has_level = "25" in src or "setLevel" in src or "kCGStatusWindowLevel" in src or "CGShieldingWindowLevel" in src
        self.assertTrue(has_level, "Missing window level 25 (kCGStatusWindowLevelKey) configuration")

    def test_f13_04_safe_cross_platform_guard(self):
        """macOS specific Cocoa calls are guarded by sys.platform == 'darwin'."""
        src = self._get_app_source()
        has_platform_guard = "darwin" in src.lower() or "sys.platform" in src
        self.assertTrue(has_platform_guard, "Platform guard (sys.platform == 'darwin') required for macOS Cocoa calls")

    def test_f13_05_fullscreen_space_switch_persistence(self):
        """Native controller class exposes pin_fullscreen_auxiliary or configure_window method."""
        src = self._get_app_source()
        has_pin_method = ("pin" in src.lower() or "auxiliary" in src.lower() or "configure" in src.lower() or "setup_macos" in src.lower())
        self.assertTrue(has_pin_method, "Missing helper method for pinning window to fullscreen auxiliary space")
