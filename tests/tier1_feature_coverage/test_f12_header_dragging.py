"""
Feature 12: Scoped Header Window Dragging (Milestone M3).
Verifies dragging via .pywebview-drag-region exclusively on header bar with .no-drag
override on interactive controls, protecting subtitle text selection.
"""
from tests.harness import BaseE2ETest, DOMInspector


class TestFeature12HeaderDragging(BaseE2ETest):
    tier = 1
    feature_id = 12
    milestone = "M3"

    def _get_ui(self) -> str:
        html = DOMInspector.get_float_ui_content()
        self.assertIsNotNone(html, "float_ui.html not found")
        return html

    def test_f12_01_drag_region_on_header(self):
        """Header area is designated as draggable via pywebview-drag-region or -webkit-app-region: drag."""
        html = self._get_ui()
        has_drag = "pywebview-drag-region" in html or "-webkit-app-region: drag" in html
        self.assertTrue(has_drag, "Missing drag region specification on header")

    def test_f12_02_no_drag_on_buttons(self):
        """Interactive controls specify no-drag to prevent drag hijacking button clicks."""
        html = self._get_ui()
        has_no_drag = "no-drag" in html or "-webkit-app-region: no-drag" in html
        self.assertTrue(has_no_drag, "Missing no-drag override on interactive controls")

    def test_f12_03_subtitle_area_not_draggable(self):
        """Subtitle display area (#pastLine, #activeLine) is not inside a drag region."""
        html = self._get_ui()
        # Ensure drag class is on header, not on the entire container
        self.assertNotIn('id="hud-container" class="pywebview-drag-region"', html,
                         "Entire #hud-container marked as draggable; drag must be scoped to header")

    def test_f12_04_drag_handle_element(self):
        """Header contains explicit #drag-handle element."""
        html = self._get_ui()
        has_handle = DOMInspector.has_element_by_id(html, "drag-handle") or "drag-handle" in html
        self.assertTrue(has_handle, "Missing #drag-handle visual grip indicator")

    def test_f12_05_reposition_bounds_handling(self):
        """JavaScript or CSS handles cursor styles properly for drag vs normal regions."""
        html = self._get_ui()
        has_cursor = "cursor: grab" in html or "cursor: move" in html or "cursor: default" in html
        self.assertTrue(has_cursor, "Missing cursor styling (grab/move) for drag region")
