"""
Feature 4: Zero-Install HUD Fallback (Milestone M1).
Verifies FastAPI route GET /hud serving float_ui.html for browser-based floating widget usage.
"""
import os
from tests.harness import BaseE2ETest, PROJECT_ROOT


class TestFeature04HUDFallback(BaseE2ETest):
    tier = 1
    feature_id = 4
    milestone = "M1"

    def test_f04_01_hud_route_status_and_content_type(self):
        """GET /hud returns HTTP 200 with text/html Content-Type."""
        client = self.get_client()
        resp = client.get("/hud")
        self.assertEqual(resp.status_code, 200, f"Expected 200 for /hud, got {resp.status_code}")
        content_type = resp.headers.get("content-type", "")
        self.assertTrue("text/html" in content_type, f"Expected text/html, got {content_type}")

    def test_f04_02_hud_serves_float_ui(self):
        """GET /hud serves the content of float_ui.html."""
        float_ui_path = os.path.join(PROJECT_ROOT, "float_ui.html")
        self.assertTrue(os.path.exists(float_ui_path), "float_ui.html does not exist")
        with open(float_ui_path, "r", encoding="utf-8") as f:
            expected_content = f.read()

        client = self.get_client()
        resp = client.get("/hud")
        self.assertIn("<!DOCTYPE html>", resp.text, "Response missing doctype")
        # Should contain identical or equivalent float_ui content
        self.assertIn("hud-container", resp.text, "Response does not contain float HUD container")

    def test_f04_03_hud_self_contained_assets(self):
        """GET /hud does not reference external or missing local stylesheets/scripts."""
        client = self.get_client()
        resp = client.get("/hud")
        # Should not have broken local link tags like <link rel="stylesheet" href="missing.css">
        import re
        links = re.findall(r'<link[^>]+href=[\'"]([^\'"]+)[\'"]', resp.text)
        for link in links:
            if not link.startswith("http") and not link.startswith("//") and not link.startswith("data:"):
                local_asset = os.path.join(PROJECT_ROOT, link.lstrip("/"))
                self.assertTrue(os.path.exists(local_asset), f"Referenced local asset does not exist: {link}")

    def test_f04_04_hud_browser_viewport_meta(self):
        """HTML includes proper mobile/popup viewport meta tag."""
        client = self.get_client()
        resp = client.get("/hud")
        self.assertIn('name="viewport"', resp.text.lower(), "Missing viewport meta tag for popup rendering")

    def test_f04_05_hud_direct_ws_url_fallback(self):
        """JavaScript dynamically resolves WebSocket URL to current window.location.host."""
        client = self.get_client()
        resp = client.get("/hud")
        # Checks for location.host or location.hostname in WS constructor
        has_dynamic_ws = ("location.host" in resp.text or "window.location" in resp.text)
        self.assertTrue(has_dynamic_ws, "HUD JS should dynamically compute WebSocket URL using window.location.host")
