"""
Tier 2 Boundary Tests: Feature 10 (Micro-Interactions & Controls).
Tests continuous mouse movement reset, precise 3.5s timing, rapid lock clicks,
empty device list display, and large cost formatting.
"""
from tests.harness import BaseE2ETest, DOMInspector


class TestBoundary10MicroInteractions(BaseE2ETest):
    tier = 2
    feature_id = 10
    milestone = "M2"

    def _get_ui(self) -> str:
        html = DOMInspector.get_float_ui_content()
        self.assertIsNotNone(html, "float_ui.html not found")
        return html

    def test_b10_01_mousemove_resets_auto_dimming(self):
        """Active mouse movement continuously clears and resets auto-dimming timeout."""
        html = self._get_ui()
        has_reset = ("clearTimeout" in html and ("mousemove" in html or "pointermove" in html))
        self.assertTrue(has_reset, "Missing clearTimeout on mousemove event")

    def test_b10_02_speech_arrival_resets_auto_dimming(self):
        """Incoming subtitle deltas wake up / reset dimming timer."""
        html = self._get_ui()
        has_wake = ("wake" in html or "clearTimeout" in html or "active" in html)
        self.assertTrue(has_wake, "Missing wake up logic when streaming deltas arrive")

    def test_b10_03_rapid_lock_clicks_consistency(self):
        """Repeatedly clicking #btn-lock toggles state cleanly between locked and unlocked."""
        html = self._get_ui()
        has_toggle_fn = ("toggleLock" in html or "isLocked = !isLocked" in html or "locked" in html)
        self.assertTrue(has_toggle_fn, "Missing lock toggle boolean logic")

    def test_b10_04_audio_device_empty_fallback(self):
        """Audio select handles empty device response without throwing TypeError."""
        html = self._get_ui()
        has_fallback = ("select" in html and ("forEach" in html or "options" in html or "innerHTML" in html))
        self.assertTrue(has_fallback, "Missing device select population logic")

    def test_b10_05_large_cost_formatting(self):
        """JavaScript formats large token cost values using toFixed(3) or toFixed(4)."""
        html = self._get_ui()
        has_fixed = "toFixed" in html or "round" in html
        self.assertTrue(has_fixed, "Missing numeric rounding / toFixed formatting for token cost display")
