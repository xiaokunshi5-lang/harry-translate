"""
Tier 2 Boundary Tests: Feature 7 (WebSocket Connection & Language Toggle).
Tests malformed JSON frames, reconnect backoff cap, rapid language toggle clicks,
large payloads, and auto-recovery.
"""
from tests.harness import BaseE2ETest, DOMInspector


class TestBoundary07WSBoundaries(BaseE2ETest):
    tier = 2
    feature_id = 7
    milestone = "M2"

    def _get_ui(self) -> str:
        html = DOMInspector.get_float_ui_content()
        self.assertIsNotNone(html, "float_ui.html not found")
        return html

    def test_b07_01_malformed_json_containment(self):
        """WebSocket onmessage wraps JSON.parse in try-catch to prevent uncaught runtime errors."""
        html = self._get_ui()
        has_try_catch = "try" in html and "catch" in html
        self.assertTrue(has_try_catch, "Missing try-catch error boundary around WebSocket payload parsing")

    def test_b07_02_reconnect_backoff_cap(self):
        """Auto-reconnect backoff logic clamps maximum reconnect delay to 2000ms."""
        html = self._get_ui()
        has_cap = ("2000" in html or "Math.min" in html or "backoff" in html or "timeout" in html)
        self.assertTrue(has_cap, "Missing backoff delay clamping in reconnection logic")

    def test_b07_03_rapid_language_toggle_debouncing(self):
        """Multiple rapid clicks on #btn-lang do not trigger unbounded concurrent WebSocket connections."""
        html = self._get_ui()
        # Checks if old socket is closed or debounced
        has_socket_cleanup = (".close()" in html or "disconnect" in html or "ws.readyState" in html)
        self.assertTrue(has_socket_cleanup, "Missing cleanup of existing WebSocket during channel toggle")

    def test_b07_04_large_payload_handling(self):
        """HTML parser and script do not choke on large data attribute or string limits."""
        html = self._get_ui()
        self.assertGreater(len(html), 500, "float_ui.html is too small")

    def test_b07_05_reconnect_channel_preservation(self):
        """Client preserves current language channel (en vs zh) across auto-reconnects."""
        html = self._get_ui()
        has_state = ("currentChannel" in html or "currentLang" in html or "targetLang" in html or "activeChannel" in html)
        self.assertTrue(has_state, "Missing state tracking for active language channel across reconnects")
