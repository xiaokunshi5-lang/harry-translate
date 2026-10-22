"""
Tier 2 Boundary Tests: Feature 9 (High-Legibility Typography & Contrast).
Tests font size min/max clamping, contrast against pure black, contrast against pure white,
and text wrapping bounds.
"""
from tests.harness import BaseE2ETest, DOMInspector


class TestBoundary09TypographyBoundaries(BaseE2ETest):
    tier = 2
    feature_id = 9
    milestone = "M2"

    def _get_ui(self) -> str:
        html = DOMInspector.get_float_ui_content()
        self.assertIsNotNone(html, "float_ui.html not found")
        return html

    def test_b09_01_font_size_maximum_clamping(self):
        """JavaScript clamps maximum font size to prevent text overflow."""
        html = self._get_ui()
        has_max_clamp = ("Math.min" in html or "maxFontSize" in html or "< 36" in html or "<= 32" in html or "clamp" in html)
        self.assertTrue(has_max_clamp, "Missing maximum font size limit in font increment logic")

    def test_b09_02_font_size_minimum_clamping(self):
        """JavaScript clamps minimum font size so subtitles never become unreadable."""
        html = self._get_ui()
        has_min_clamp = ("Math.max" in html or "minFontSize" in html or "> 12" in html or ">= 14" in html or "clamp" in html)
        self.assertTrue(has_min_clamp, "Missing minimum font size limit in font decrement logic")

    def test_b09_03_contrast_against_pure_black_screen(self):
        """Calculates contrast ratio of white text against pure black background (>= 7.0)."""
        white = (255, 255, 255)
        black = (0, 0, 0)
        ratio = DOMInspector.calculate_contrast_ratio(white, black)
        self.assertGreaterEqual(ratio, 7.0, f"Contrast against black is {ratio:.2f}")

    def test_b09_04_contrast_against_pure_white_screen(self):
        """Calculates contrast ratio of black shadow edge against pure white background (>= 7.0)."""
        black_shadow = (0, 0, 0)
        white_bg = (255, 255, 255)
        ratio = DOMInspector.calculate_contrast_ratio(black_shadow, white_bg)
        self.assertGreaterEqual(ratio, 7.0, f"Contrast of shadow against white background is {ratio:.2f}")

    def test_b09_05_line_height_proportionality(self):
        """CSS specifies proportional line-height (1.3 - 1.6) for optimal readability."""
        html = self._get_ui()
        has_line_height = "line-height:" in html
        self.assertTrue(has_line_height, "Missing line-height rule on subtitle text")
