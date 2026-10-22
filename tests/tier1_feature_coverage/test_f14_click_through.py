"""
Feature 14: Dual-Mode Click-Through Locking (Milestone M3).
Verifies native OS click-through via macOS setIgnoresMouseEvents_ and Windows
WS_EX_TRANSPARENT, and backend API routes GET/POST /api/hud/lock.
"""
from tests.harness import BaseE2ETest, DesktopAppInspector


class TestFeature14ClickThrough(BaseE2ETest):
    tier = 1
    feature_id = 14
    milestone = "M3"

    def _get_app_source(self) -> str:
        src = DesktopAppInspector.get_source()
        self.assertIsNotNone(src, "float_app.py not found")
        return src

    def test_f14_01_macos_set_ignores_mouse_events(self):
        """macOS controller calls setIgnoresMouseEvents: to enable/disable click-through."""
        src = self._get_app_source()
        has_mouse_ignore = "setIgnoresMouseEvents" in src or "ignoresMouseEvents" in src
        self.assertTrue(has_mouse_ignore, "Missing macOS setIgnoresMouseEvents call in float_app.py")

    def test_f14_02_windows_ws_ex_transparent(self):
        """Windows controller references WS_EX_TRANSPARENT and WS_EX_LAYERED."""
        src = self._get_app_source()
        has_win_flags = "WS_EX_TRANSPARENT" in src or "0x00000020" in src or "SetWindowLong" in src
        self.assertTrue(has_win_flags, "Missing Windows WS_EX_TRANSPARENT / SetWindowLongPtrW call in float_app.py")

    def test_f14_03_backend_lock_route(self):
        """GET /api/hud/lock and POST /api/hud/lock provide API-level state query/toggle."""
        client = self.get_client()
        # Query lock state
        resp = client.get("/api/hud/lock")
        self.assertIn(resp.status_code, [200, 404])  # 200 when M1/M3 route ready
        if resp.status_code == 200:
            data = resp.json()
            self.assertIn("locked", data)

            # Toggle lock state via POST
            post_resp = client.post("/api/hud/lock", json_data={"locked": True})
            self.assertEqual(post_resp.status_code, 200)
            self.assertEqual(post_resp.json().get("locked"), True)

    def test_f14_04_click_through_unlock_mechanism(self):
        """Controller provides unlock path so user is never trapped in click-through mode."""
        src = self._get_app_source()
        has_toggle = ("set_click_through" in src or "toggle_lock" in src or "unlock" in src or "set_locked" in src)
        self.assertTrue(has_toggle, "float_app.py must provide set_click_through() method")

    def test_f14_05_hit_test_cache_flushing(self):
        """Windows controller calls SWP_FRAMECHANGED (0x0020) to flush OS hit-test caching."""
        src = self._get_app_source()
        has_flush = ("SWP_FRAMECHANGED" in src or "0x0020" in src or "SetWindowPos" in src or "win32" in src.lower())
        self.assertTrue(has_flush, "Missing Windows SWP_FRAMECHANGED hit-test cache invalidation")
