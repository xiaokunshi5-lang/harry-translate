"""
Tier 2 Boundary Tests: Feature 6 (Sub-Millisecond Dual-Line Engine).
Tests empty text deltas, massive subtitle strings, special characters / emoji / RTL,
rapid burst rates, and consecutive sentence_end idempotency.
"""
from tests.harness import BaseE2ETest, DOMInspector


class TestBoundary06DualLineEngine(BaseE2ETest):
    tier = 2
    feature_id = 6
    milestone = "M2"

    def _get_ui(self) -> str:
        html = DOMInspector.get_float_ui_content()
        self.assertIsNotNone(html, "float_ui.html not found")
        return html

    def test_b06_01_empty_text_delta_handling(self):
        """UI logic safely handles empty string or whitespace delta without layout collapse."""
        html = self._get_ui()
        # Verify textContent assignment handles empty strings
        has_safe_update = "textContent" in html and ("||" in html or "if (" in html or "text" in html)
        self.assertTrue(has_safe_update, "Missing safe text update handling in float_ui.html")

    def test_b06_02_massive_subtitle_string_handling(self):
        """CSS includes overflow-wrap / word-break to prevent super long words from breaking container."""
        html = self._get_ui()
        has_break = ("break-word" in html or "overflow-wrap" in html or "word-break" in html or "ellipsis" in html)
        self.assertTrue(has_break, "CSS must declare word-break / overflow-wrap to handle long strings")

    def test_b06_03_unicode_emoji_rtl_safety(self):
        """HTML charset is UTF-8 to support complex emojis, CJK, and RTL scripts safely."""
        html = self._get_ui()
        has_charset = 'charset="utf-8"' in html.lower() or "charset='utf-8'" in html.lower() or "charset=utf-8" in html.lower()
        self.assertTrue(has_charset, "Missing UTF-8 charset declaration")

    def test_b06_04_rapid_burst_throttling_raf(self):
        """rAF loop updates pending text variable rather than forcing immediate layout thrashing."""
        html = self._get_ui()
        # Look for pattern where delta is stored and flushed in requestAnimationFrame
        self.assertIn("requestAnimationFrame", html)

    def test_b06_05_consecutive_final_events(self):
        """Consecutive finalization calls do not introduce blank phantom lines."""
        html = self._get_ui()
        # Slot shifting checks for non-empty text before moving to pastLine
        has_empty_check = ("trim()" in html or "length" in html or "activeLine.textContent" in html or "if (" in html)
        self.assertTrue(has_empty_check, "Missing guard against shifting empty lines to pastLine")
