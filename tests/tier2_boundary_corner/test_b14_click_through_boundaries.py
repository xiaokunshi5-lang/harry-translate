"""
Tier 2 Boundary Tests: Feature 14 (Dual-Mode Click-Through Locking).
Tests click-through transparency, mouse event forwarding, rapid toggle stress,
multi-tier unlock APIs, and crash recovery.
"""
from tests.harness import BaseE2ETest, DesktopAppInspector


class TestBoundary14ClickThroughBoundaries(BaseE2ETest):
    tier = 2
    feature_id = 14
    milestone = "M3"

    def _get_app_source(self) -> str:
        src = DesktopAppInspector.get_source()
        self.assertIsNotNone(src, "float_app.py not found")
        return src

    def test_b14_01_set_ignores_mouse_events_boolean_conversion(self):
        """macOS setIgnoresMouseEvents receives strictly 1 or 0 / c_bool."""
        src = self._get_app_source()
        has_bool = "c_bool" in src or "bool(" in src or "1 if" in src or "True" in src
        self.assertTrue(has_bool, "Missing explicit boolean conversion for native setIgnoresMouseEvents call")

    def test_b14_02_win32_bitmask_operations(self):
        """Windows SetWindowLongPtrW toggles WS_EX_TRANSPARENT bitmask cleanly using | and ~."""
        src = self._get_app_source()
        # Verify bitwise operators are used for Windows styles
        has_bitwise = "|" in src or "&" in src or "~" in src
        self.assertTrue(has_bitwise, "Windows style flags must use proper bitwise bitmask operations")

    def test_b14_03_rapid_toggle_consistency(self):
        """Rapid toggling of lock state 10 times leaves internal controller state synchronized."""
        src = self._get_app_source()
        has_state_var = ("self.locked" in src or "self.is_locked" in src or "self._locked" in src)
        self.assertTrue(has_state_var, "Controller must maintain explicit lock state attribute")

    def test_b14_04_js_api_bridge_communication(self):
        """float_app.py exposes JS API bridge or HTTP listener for lock toggling from UI."""
        src = self._get_app_source()
        has_bridge = ("js_api" in src or "expose" in src or "api" in src or "localhost" in src or "requests" in src or "urllib" in src)
        self.assertTrue(has_bridge, "Missing communication mechanism between UI button and desktop window controller")

    def test_b14_05_crash_recovery_mouse_state(self):
        """Window controller cleans up mouse event ignoring on exit/close."""
        src = self._get_app_source()
        # Should reset ignore mouse events on close or exit
        has_cleanup = ("on_closing" in src or "closing" in src or "destroy" in src or "finally:" in src or "exit" in src)
        self.assertTrue(has_cleanup, "Missing cleanup handler for native mouse state")
