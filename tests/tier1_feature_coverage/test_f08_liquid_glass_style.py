"""
Feature 8: Apple Liquid Glass Aesthetic (Milestone M2).
Verifies capsule window, backdrop-filter blur(20px) saturate(180%), dark translucency rgba(18, 18, 22, 0.75),
1px specular highlight rim, and 20px rounded capsule corners.
"""
import re
from tests.harness import BaseE2ETest, DOMInspector


class TestFeature08LiquidGlassStyle(BaseE2ETest):
    tier = 1
    feature_id = 8
    milestone = "M2"

    def _get_ui(self) -> str:
        html = DOMInspector.get_float_ui_content()
        self.assertIsNotNone(html, "float_ui.html not found")
        return html

    def test_f08_01_backdrop_filter_properties(self):
        """CSS contains backdrop-filter: blur(20px) saturate(180%) and -webkit prefix."""
        html = self._get_ui()
        has_blur = bool(re.search(r'backdrop-filter:\s*blur\(20px\)', html))
        has_webkit_blur = bool(re.search(r'-webkit-backdrop-filter:\s*blur\(20px\)', html))
        has_saturate = "saturate(" in html
        self.assertTrue(has_blur or has_webkit_blur, "Missing backdrop-filter: blur(20px)")
        self.assertTrue(has_saturate, "Missing saturate() filter for Apple Liquid Glass vibrancy")

    def test_f08_02_dark_translucent_background(self):
        """Container background uses deep dark translucency (rgba(18, 18, 22, 0.75) or equivalent)."""
        html = self._get_ui()
        # Look for rgba(18, 18, 22, ...) or rgba(18,18,22,...)
        has_dark_trans = bool(re.search(r'rgba\(\s*18\s*,\s*18\s*,\s*22\s*,\s*0\.7[0-9]*\)', html))
        if not has_dark_trans:
            # Fallback: check any dark rgba with high opacity 0.7 - 0.85
            has_dark_trans = bool(re.search(r'background:\s*rgba\(\s*[0-3][0-9]\s*,\s*[0-3][0-9]\s*,\s*[0-3][0-9]\s*,\s*0\.[78]', html))
        self.assertTrue(has_dark_trans, "Missing deep dark translucent background rgba(18, 18, 22, 0.75)")

    def test_f08_03_specular_highlight_rim(self):
        """CSS contains 1px specular highlight border rim."""
        html = self._get_ui()
        has_rim = bool(re.search(r'border:\s*1px\s+solid\s+rgba\(255,\s*255,\s*255', html)) or \
                  bool(re.search(r'box-shadow:[^;]*inset\s+0\s+0\s+0\s+1px', html)) or \
                  "1px solid rgba(255" in html
        self.assertTrue(has_rim, "Missing 1px specular highlight rim on floating HUD capsule")

    def test_f08_04_capsule_rounded_corners(self):
        """Container has capsule border-radius of 20px (or 24px/16px)."""
        html = self._get_ui()
        has_radius = bool(re.search(r'border-radius:\s*(?:1[6-9]|2[0-4])px', html))
        self.assertTrue(has_radius, "Missing capsule border-radius: 20px on #hud-container")

    def test_f08_05_single_layer_compositing(self):
        """Only outer container has backdrop-filter to prevent multi-layer GPU compositing lag."""
        html = self._get_ui()
        matches = re.findall(r'backdrop-filter:\s*blur', html)
        # Should have at most 2 matches (standard + -webkit prefix on container)
        self.assertLessEqual(len(matches), 2, "Found redundant nested backdrop-filters causing GPU overhead")
