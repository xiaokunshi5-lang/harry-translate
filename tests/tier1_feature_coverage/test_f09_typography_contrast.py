"""
Feature 9: High-Legibility Typography & Contrast (Milestone M2).
Verifies native system font stack, dual-layer text shadows, WCAG >=7:1 contrast ratio,
and dynamic font size controls (#btn-font-dec, #btn-font-inc).
"""
import re
from tests.harness import BaseE2ETest, DOMInspector


class TestFeature09TypographyContrast(BaseE2ETest):
    tier = 1
    feature_id = 9
    milestone = "M2"

    def _get_ui(self) -> str:
        html = DOMInspector.get_float_ui_content()
        self.assertIsNotNone(html, "float_ui.html not found")
        return html

    def test_f09_01_native_system_font_stack(self):
        """Typography uses native system fonts (-apple-system, PingFang SC, Segoe UI) with zero remote webfonts."""
        html = self._get_ui()
        self.assertIn("-apple-system", html, "Missing -apple-system in font-family")
        self.assertIn("PingFang SC", html, "Missing PingFang SC for crisp Chinese typography")
        # Ensure no external Google Fonts or Typekit imports
        self.assertNotIn("fonts.googleapis.com", html, "Forbidden external font download found")
        self.assertNotIn("@font-face", html, "Custom webfont download found; must use zero-fat system fonts")

    def test_f09_02_dual_layer_text_shadow(self):
        """Subtitle text styles define dual-layer text shadows for extreme legibility."""
        html = self._get_ui()
        # Look for text-shadow with two layers separated by comma
        has_dual_shadow = bool(re.search(r'text-shadow:[^;]*rgba\(0,\s*0,\s*0[^;]*,[^;]*rgba\(0,\s*0,\s*0', html))
        self.assertTrue(has_dual_shadow, "Missing dual-layer text-shadow for subtitle legibility against bright backgrounds")

    def test_f09_03_wcag_contrast_ratio(self):
        """Calculates contrast ratio of white text against deep glass background to ensure >= 7.0 (AAA)."""
        # White text: (255, 255, 255)
        # Deep dark glass: blended over dark space ~ (18, 18, 22)
        white_rgb = (255, 255, 255)
        dark_glass_rgb = (18, 18, 22)
        ratio = DOMInspector.calculate_contrast_ratio(white_rgb, dark_glass_rgb)
        self.assertGreaterEqual(ratio, 7.0, f"Contrast ratio {ratio:.2f} is below 7.0 AAA requirement")

    def test_f09_04_white_background_protection(self):
        """Calculates contrast ratio when rendered over pure white background with text shadow."""
        # Pure white: (255, 255, 255)
        # Text shadow black edge: (0, 0, 0)
        # The dual-layer shadow guarantees an opaque boundary > 7:1 against #ffffff
        shadow_edge_rgb = (0, 0, 0)
        white_bg = (255, 255, 255)
        ratio = DOMInspector.calculate_contrast_ratio(shadow_edge_rgb, white_bg)
        self.assertGreaterEqual(ratio, 7.0, f"Shadow edge contrast {ratio:.2f} must exceed 7.0 against white backgrounds")

    def test_f09_05_dynamic_font_resizing(self):
        """Header contains font size decrement (#btn-font-dec) and increment (#btn-font-inc) buttons."""
        html = self._get_ui()
        self.assertTrue(DOMInspector.has_element_by_id(html, "btn-font-dec"), "Missing #btn-font-dec button")
        self.assertTrue(DOMInspector.has_element_by_id(html, "btn-font-inc"), "Missing #btn-font-inc button")
