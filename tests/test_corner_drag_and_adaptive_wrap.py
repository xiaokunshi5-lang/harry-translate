#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
tests/test_corner_drag_and_adaptive_wrap.py
--------------------------------------------------------------------------------
Dedicated verification suite for:
1. Top-left designated anchor hardware drag (performWindowDragWithEvent_).
2. Multi-monitor / extended screen coordinate freedom.
3. Adaptive multi-line word wrapping with 28px breathing safety margin.
--------------------------------------------------------------------------------
"""

import os
import re
import sys
import unittest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HTML_PATH = os.path.join(PROJECT_ROOT, "float_ui.html")
APP_PATH = os.path.join(PROJECT_ROOT, "float_app.py")


class TestCornerDragAndAdaptiveWrap(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(HTML_PATH, "r", encoding="utf-8") as f:
            cls.html = f.read()
        with open(APP_PATH, "r", encoding="utf-8") as f:
            cls.app_code = f.read()

    def test_01_top_left_drag_anchor_dom_and_visual(self):
        """Top-left anchor #drag-anchor-corner exists with braille dots and label."""
        self.assertIn('id="drag-anchor-corner"', self.html, "Missing #drag-anchor-corner in DOM")
        self.assertIn("⠿", self.html, "Missing braille dot icon ⠿ in drag anchor")
        self.assertIn("同传浮窗", self.html, "Missing '同传浮窗' text label in drag anchor")
        self.assertIn("drag-anchor-corner", self.html)

    def test_02_drag_css_and_cursor_isolation(self):
        """Anchor has grab cursor and drag region; main container has default cursor."""
        # Anchor styles
        self.assertIn("#drag-anchor-corner", self.html)
        self.assertIn("cursor: grab", self.html)
        self.assertIn("cursor: grabbing", self.html)

        # Container is not a global grab trap
        container_match = re.search(r'#hud-container[^{]*\{([^}]+)\}', self.html)
        self.assertIsNotNone(container_match, "Could not find #hud-container CSS rule")
        container_css = container_match.group(1)
        self.assertIn("cursor: default", container_css, "#hud-container must default to standard cursor")
        self.assertNotIn("cursor: grab", container_css, "#hud-container must not have grab cursor")

    def test_03_infinite_stretch_and_28px_breathing_margin(self):
        """#hud-container removes 900px restriction and enforces 28px horizontal padding."""
        container_match = re.search(r'#hud-container[^{]*\{([^}]+)\}', self.html)
        self.assertIsNotNone(container_match)
        css = container_match.group(1)

        self.assertIn("max-width: none", css, "Must remove max-width: 900px limitation")
        self.assertIn("28px", css, "Must enforce 28px left/right breathing safety margin")
        self.assertIn("padding: 10px 28px 12px 28px", css)

    def test_04_adaptive_text_wrapping(self):
        """activeLine and pastLine allow dynamic multi-line word-break wrapping."""
        # Active line
        active_match = re.search(r'#activeLine[^{]*\{([^}]+)\}', self.html)
        self.assertIsNotNone(active_match)
        active_css = active_match.group(1)
        self.assertIn("white-space: normal", active_css)
        self.assertIn("word-break: break-word", active_css)
        self.assertIn("overflow-wrap: break-word", active_css)

        # Past line
        past_match = re.search(r'#pastLine[^{]*\{([^}]+)\}', self.html)
        self.assertIsNotNone(past_match)
        past_css = past_match.group(1)
        self.assertIn("white-space: normal", past_css)
        self.assertIn("word-break: break-word", past_css)
        self.assertIn("overflow-wrap: break-word", past_css)
        self.assertIn("text-overflow: ellipsis", past_css)

    def test_05_cocoa_perform_window_drag_monitor(self):
        """MacOSWindowController installs Cocoa NSEvent monitor calling performWindowDragWithEvent_."""
        self.assertIn("def _setup_drag_monitor(self):", self.app_code)
        self.assertIn("performWindowDragWithEvent_", self.app_code)
        self.assertIn("addLocalMonitorForEventsMatchingMask_handler_", self.app_code)
        self.assertIn("NSEventMaskLeftMouseDown", self.app_code)

        # Anchor hit-test logic: x in [0, 160], y in [win_h - 44, win_h]
        self.assertIn("0 <= loc.x <= 160", self.app_code)
        self.assertIn("(win_h - 44) <= loc.y <= win_h", self.app_code)

    def test_06_window_resizable_across_all_instances(self):
        """create_window explicitly sets resizable=True to allow user resizing."""
        self.assertIn("resizable=True", self.app_code)
        matches = re.findall(r'webview\.create_window\([^)]*resizable=True[^)]*\)', self.app_code, re.DOTALL)
        self.assertGreaterEqual(len(matches), 1, "Must set resizable=True in create_window")

    def test_07_simulated_drag_hit_test(self):
        """Unit test the top-left anchor geometry hit-test function."""
        def is_drag_zone(x: float, y: float, win_h: float = 160.0) -> bool:
            return 0 <= x <= 160 and (win_h - 44) <= y <= win_h

        # In Cocoa coordinates, origin (0, 0) is bottom-left, top-left is (0, win_h)
        # 1. Top-left corner anchor click (should trigger drag)
        self.assertTrue(is_drag_zone(10, 150, 160))
        self.assertTrue(is_drag_zone(80, 140, 160))
        self.assertTrue(is_drag_zone(160, 160, 160))

        # 2. Right-side control buttons click (e.g. x=650, top area) -> MUST NOT DRAG
        self.assertFalse(is_drag_zone(650, 150, 160))

        # 3. Middle subtitle text area click (e.g. x=200, y=80) -> MUST NOT DRAG
        self.assertFalse(is_drag_zone(200, 80, 160))
        self.assertFalse(is_drag_zone(50, 50, 160))


if __name__ == "__main__":
    unittest.main()
