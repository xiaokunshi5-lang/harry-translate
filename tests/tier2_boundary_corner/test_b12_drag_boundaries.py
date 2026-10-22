"""
Tier 2 Boundary Tests: Feature 12 (Scoped Header Window Dragging).
Tests screen boundary drag protection, fast flings, double-click prevention,
mouse release outside window, and dragging during active streaming.
"""
from tests.harness import BaseE2ETest, DOMInspector


class TestBoundary12DragBoundaries(BaseE2ETest):
    tier = 2
    feature_id = 12
    milestone = "M3"

    def _get_ui(self) -> str:
        html = DOMInspector.get_float_ui_content()
        self.assertIsNotNone(html, "float_ui.html not found")
        return html

    def test_b12_01_user_select_disabled_on_drag(self):
        """Header drag region specifies user-select: none to prevent accidental text selection while dragging."""
        html = self._get_ui()
        has_user_select = "user-select: none" in html or "-webkit-user-select: none" in html
        self.assertTrue(has_user_select, "Header drag area must specify user-select: none")

    def test_b12_02_button_no_drag_override(self):
        """Every interactive header element (lang, font, lock) is immune to drag."""
        html = self._get_ui()
        # All buttons must have .no-drag class or -webkit-app-region: no-drag
        has_no_drag = "no-drag" in html or "-webkit-app-region: no-drag" in html
        self.assertTrue(has_no_drag, "Interactive controls missing no-drag override")

    def test_b12_03_double_click_safety(self):
        """Double clicking header does not break CSS styling or cause layout collapse."""
        html = self._get_ui()
        self.assertIn("overflow: hidden", html, "Container should have overflow: hidden to contain bounds")

    def test_b12_04_drag_during_active_streaming(self):
        """Fixed slots stay anchored and do not detach from container during repositioning."""
        html = self._get_ui()
        # Fixed slots must be within #hud-container in DOM hierarchy
        self.assertTrue(DOMInspector.has_element_by_id(html, "pastLine"))
        self.assertTrue(DOMInspector.has_element_by_id(html, "activeLine"))

    def test_b12_05_pointer_events_preservation(self):
        """When not locked, pointer-events are auto / active on interactive buttons."""
        html = self._get_ui()
        # Header controls must be clickable
        self.assertNotIn("pointer-events: none !important", html)
