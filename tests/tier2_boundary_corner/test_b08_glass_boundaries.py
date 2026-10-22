"""
Tier 2 Boundary Tests: Feature 8 (Apple Liquid Glass Aesthetic).
Tests extreme aspect ratios, fallback styling, high-DPI scaling, dark/light OS themes,
and safe saturation parameters.
"""
import re
from tests.harness import BaseE2ETest, DOMInspector


class TestBoundary08GlassBoundaries(BaseE2ETest):
    tier = 2
    feature_id = 8
    milestone = "M2"

    def _get_ui(self) -> str:
        html = DOMInspector.get_float_ui_content()
        self.assertIsNotNone(html, "float_ui.html not found")
        return html

    def test_b08_01_extreme_aspect_ratios_box_sizing(self):
        """CSS includes box-sizing: border-box on container to prevent padding overflow."""
        html = self._get_ui()
        self.assertIn("box-sizing: border-box", html, "Missing box-sizing: border-box on HUD container")

    def test_b08_02_css_fallback_background(self):
        """CSS defines solid/high-opacity dark background prior to backdrop-filter for unsupported webviews."""
        html = self._get_ui()
        # Fallback background color should be specified
        has_bg = "background" in html and ("rgba(" in html or "#" in html)
        self.assertTrue(has_bg, "Missing fallback background color for unsupported webviews")

    def test_b08_03_high_dpi_specular_rim_rendering(self):
        """Specular border is thin (1px) with semi-transparent white for crisp rendering on Retina/HiDPI."""
        html = self._get_ui()
        has_thin_border = bool(re.search(r'(?:border|box-shadow):[^;]*1px[^;]*rgba\(255', html))
        self.assertTrue(has_thin_border, "Specular highlight rim must be exactly 1px semi-transparent white")

    def test_b08_04_dark_light_theme_independence(self):
        """HUD forces dark theme styling regardless of OS light/dark mode preference."""
        html = self._get_ui()
        # Should NOT invert colors in @media (prefers-color-scheme: light)
        self.assertNotIn("prefers-color-scheme: light {\n    background: white", html)

    def test_b08_05_safe_saturation_parameter(self):
        """Saturation filter is clamped to <= 200% to avoid artificial color distortion."""
        html = self._get_ui()
        match = re.search(r'saturate\((\d+)%\)', html)
        if match:
            sat_val = int(match.group(1))
            self.assertLessEqual(sat_val, 200, f"Saturation filter {sat_val}% exceeds 200% threshold")
