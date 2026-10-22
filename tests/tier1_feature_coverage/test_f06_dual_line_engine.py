"""
Feature 6: Sub-Millisecond Dual-Line Engine (Milestone M2).
Verifies fixed-slot (#pastLine and #activeLine) subtitle display in float_ui.html,
elimination of 100-card scroll DOM, textContent usage, and requestAnimationFrame batching.
"""
import os
import re
from tests.harness import BaseE2ETest, DOMInspector, PROJECT_ROOT


class TestFeature06DualLineEngine(BaseE2ETest):
    tier = 1
    feature_id = 6
    milestone = "M2"

    def _get_ui(self) -> str:
        html = DOMInspector.get_float_ui_content()
        self.assertIsNotNone(html, "float_ui.html not found")
        return html

    def test_f06_01_fixed_slot_dom_structure(self):
        """float_ui.html contains #pastLine and #activeLine fixed slots inside #hud-container."""
        html = self._get_ui()
        self.assertTrue(DOMInspector.has_element_by_id(html, "hud-container"), "Missing #hud-container")
        self.assertTrue(DOMInspector.has_element_by_id(html, "pastLine"), "Missing #pastLine slot")
        self.assertTrue(DOMInspector.has_element_by_id(html, "activeLine"), "Missing #activeLine slot")

    def test_f06_02_no_card_scroll_dom_bloat(self):
        """Verifies absence of unbounded scroll list or 100-card DOM retention elements."""
        html = self._get_ui()
        # Should NOT contain scrollable multi-card container like card-list or overflow-y: scroll on body
        self.assertNotIn("card-list", html, "Forbidden multi-card DOM found in float_ui.html")
        self.assertNotIn("overflow-y: scroll", html.lower(), "Scrolling text list found; must be fixed slots")

    def test_f06_03_raf_streaming_update_pattern(self):
        """JavaScript uses requestAnimationFrame for streaming subtitle updates."""
        html = self._get_ui()
        self.assertIn("requestAnimationFrame", html, "requestAnimationFrame missing from float_ui.html streaming loop")

    def test_f06_04_text_content_usage_sub_millisecond(self):
        """JavaScript uses textContent rather than innerHTML for slot updates to prevent DOM thrashing."""
        html = self._get_ui()
        self.assertIn(".textContent", html, "Must use textContent for sub-millisecond slot updates")
        # Ensure innerHTML is not used for appending streaming cards
        self.assertNotIn(".innerHTML +=", html, "Unsafe innerHTML concatenation detected")

    def test_f06_05_sentence_transition_lifecycle(self):
        """JS logic shifts finished sentence to pastLine and resets activeLine."""
        html = self._get_ui()
        # Check presence of sentence finalization logic
        has_finalize = ("sentence_end" in html or "is_final" in html) and ("pastLine" in html and "activeLine" in html)
        self.assertTrue(has_finalize, "Missing sentence finalization and slot shifting logic")
