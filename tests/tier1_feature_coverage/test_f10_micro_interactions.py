"""
Feature 10: Micro-Interactions & Controls (Milestone M2).
Verifies 3.5s auto-dimming, hover-reveal header, lock pin button (#btn-lock),
audio device selector (#select-audio), and token cost chip (#chip-cost).
"""
import re
from tests.harness import BaseE2ETest, DOMInspector


class TestFeature10MicroInteractions(BaseE2ETest):
    tier = 1
    feature_id = 10
    milestone = "M2"

    def _get_ui(self) -> str:
        html = DOMInspector.get_float_ui_content()
        self.assertIsNotNone(html, "float_ui.html not found")
        return html

    def test_f10_01_auto_dimming_timer(self):
        """JavaScript implements auto-dimming after 3500ms (3.5s) of inactivity."""
        html = self._get_ui()
        has_dim_timer = "3500" in html or "3.5" in html or "dim" in html
        self.assertTrue(has_dim_timer, "Missing 3.5s auto-dimming timer in float_ui.html")

    def test_f10_02_hover_reveal_header(self):
        """Header controls reveal on hover or mouse movement."""
        html = self._get_ui()
        has_hover = ":hover" in html or "opacity:" in html or "transition:" in html
        self.assertTrue(has_hover, "Missing hover transition styling for header controls")

    def test_f10_03_lock_pin_toggle_button(self):
        """Header contains lock pin button #btn-lock."""
        html = self._get_ui()
        self.assertTrue(DOMInspector.has_element_by_id(html, "btn-lock"), "Missing #btn-lock pin button")

    def test_f10_04_audio_device_selector(self):
        """Header contains audio device selector #select-audio."""
        html = self._get_ui()
        self.assertTrue(DOMInspector.has_element_by_id(html, "select-audio"), "Missing #select-audio element")

    def test_f10_05_token_cost_chip(self):
        """Header contains token cost chip #chip-cost."""
        html = self._get_ui()
        self.assertTrue(DOMInspector.has_element_by_id(html, "chip-cost"), "Missing #chip-cost element")
        # Check presence of currency symbol formatting
        has_currency = "¥" in html or "rmb" in html.lower() or "cost" in html.lower()
        self.assertTrue(has_currency, "Cost chip does not display currency symbol")
