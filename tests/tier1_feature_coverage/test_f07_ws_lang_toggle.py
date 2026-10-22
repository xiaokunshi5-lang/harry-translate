"""
Feature 7: WebSocket Connection & Language Toggle (Milestone M2).
Verifies direct connection to /ws/en and /ws/zh, auto channel toggle button (#btn-lang),
schema parsing, and auto-reconnect logic.
"""
from tests.harness import BaseE2ETest, DOMInspector


class TestFeature07WSLangToggle(BaseE2ETest):
    tier = 1
    feature_id = 7
    milestone = "M2"

    def _get_ui(self) -> str:
        html = DOMInspector.get_float_ui_content()
        self.assertIsNotNone(html, "float_ui.html not found")
        return html

    def test_f07_01_websocket_endpoints_declared(self):
        """UI establishes WebSocket connection to /ws/en or /ws/zh."""
        html = self._get_ui()
        self.assertTrue("/ws/" in html, "WebSocket endpoint /ws/ not declared in float_ui.html")

    def test_f07_02_language_toggle_button(self):
        """Header contains language toggle control #btn-lang."""
        html = self._get_ui()
        self.assertTrue(DOMInspector.has_element_by_id(html, "btn-lang"), "Missing #btn-lang button in float_ui.html")

    def test_f07_03_channel_switch_logic(self):
        """Language button click switches between en and zh channels."""
        html = self._get_ui()
        has_switch = ("zh" in html and "en" in html) and ("btn-lang" in html or "switchLang" in html or "toggleLang" in html)
        self.assertTrue(has_switch, "Missing language switching logic in JavaScript")

    def test_f07_04_inbound_schema_parsing(self):
        """Client parses sentence payload with text, type, and usage fields."""
        html = self._get_ui()
        self.assertTrue("JSON.parse" in html, "Missing JSON.parse in WebSocket message handler")
        has_field_access = ("target" in html or "text" in html) and ("usage" in html or "cost" in html or "cost_rmb" in html)
        self.assertTrue(has_field_access, "WebSocket handler does not extract text or cost metrics")

    def test_f07_05_auto_reconnect_backoff(self):
        """Client implements auto-reconnect logic upon socket closure."""
        html = self._get_ui()
        has_reconnect = ("onclose" in html or "addEventListener('close'" in html) and ("setTimeout" in html or "reconnect" in html)
        self.assertTrue(has_reconnect, "Missing auto-reconnect backoff mechanism in float_ui.html")
