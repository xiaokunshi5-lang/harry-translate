#!/usr/bin/env python3
"""
tests/verify_m3_v5.py - Verification Suite for Worker M3: MinimalHUD v5.0.

Asserts:
1. Visible controls in header strictly <= 3 (#btn-lock, #btn-opacity, #btn-config).
2. Header hidden (opacity: 0) outside top sensor, reveals on 24px top sensor hover.
3. Default background opacity is 35% (rgba(18, 18, 22, 0.35)) with 3.5s auto-dimming.
4. Subtitle stage has 0 vertical scrollbars (overflow: hidden).
5. Window title is "Qwen_Meeting_HUD_Overlay_7x9" and hwnd lookup is strictly by title.
6. Stealth mode (screen-share exclusion) is functional and returns true on native controller.
7. Bridge method open_browser_config exists on HudApi.
8. CLI supports --stealth flag.
"""

import os
import re
import sys
import unittest
from html.parser import HTMLParser

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)


class HeaderButtonParser(HTMLParser):
    """Parses buttons, selects, and inputs inside .hud-header."""
    def __init__(self):
        super().__init__()
        self.in_header = False
        self.in_legacy = False
        self.header_controls = []
        self.legacy_controls = []

    def handle_starttag(self, tag, attrs):
        attr_dict = dict(attrs)
        tag_id = attr_dict.get("id", "")
        tag_class = attr_dict.get("class", "")

        if tag == "header" and ("hud-header" in tag_class or tag_id == "hud-header"):
            self.in_header = True
        elif tag_id == "legacy-compat-container":
            self.in_legacy = True

        if tag in ("button", "select", "input"):
            ctrl_info = {"tag": tag, "id": tag_id, "class": tag_class}
            if self.in_header and not self.in_legacy:
                self.header_controls.append(ctrl_info)
            elif self.in_legacy:
                self.legacy_controls.append(ctrl_info)

    def handle_endtag(self, tag):
        if tag == "header" and self.in_header:
            self.in_header = False
        elif tag == "div" and self.in_legacy:
            self.in_legacy = False


class TestMinimalHUDv5Verification(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html_path = os.path.join(PROJECT_ROOT, "float_ui.html")
        cls.app_path = os.path.join(PROJECT_ROOT, "float_app.py")

        with open(cls.html_path, "r", encoding="utf-8") as f:
            cls.html_content = f.read()

        with open(cls.app_path, "r", encoding="utf-8") as f:
            cls.app_content = f.read()

    def test_01_visible_controls_count_strictly_le_3(self):
        """Visible interactive controls in header strictly <= 3."""
        parser = HeaderButtonParser()
        parser.feed(self.html_content)

        header_control_ids = [c["id"] for c in parser.header_controls]
        print(f"[TEST 01] Header controls found ({len(header_control_ids)}): {header_control_ids}")

        self.assertLessEqual(len(parser.header_controls), 3,
            f"Header controls count ({len(parser.header_controls)}) exceeds limit of 3: {header_control_ids}")
        self.assertEqual(len(parser.header_controls), 3,
            f"Expected exactly 3 controls (#btn-lock, #btn-opacity, #btn-config), got: {header_control_ids}")
        self.assertIn("btn-lock", header_control_ids)
        self.assertIn("btn-opacity", header_control_ids)
        self.assertIn("btn-config", header_control_ids)

        # Verify legacy compat controls are safely hidden
        self.assertIn('id="legacy-compat-container"', self.html_content)
        self.assertIn('display: none !important;', self.html_content)
        legacy_ids = [c["id"] for c in parser.legacy_controls]
        print(f"[TEST 01] Legacy hidden controls: {legacy_ids}")
        self.assertIn("select-audio", legacy_ids)
        self.assertIn("btn-lang", legacy_ids)
        self.assertIn("btn-font-dec", legacy_ids)
        self.assertIn("btn-font-inc", legacy_ids)
        self.assertIn("btn-close", legacy_ids)

    def test_02_header_hidden_outside_top_sensor(self):
        """Header is opacity: 0 by default, reveals only when hovering 24px top sensor or header."""
        # 1. Base header style has opacity: 0 and pointer-events: none
        header_css_match = re.search(r'\.hud-header\s*\{([^}]+)\}', self.html_content)
        self.assertIsNotNone(header_css_match, "Could not find .hud-header CSS block")
        header_rules = header_css_match.group(1)
        self.assertIn("opacity: 0", header_rules, ".hud-header must have opacity: 0 by default")
        self.assertIn("pointer-events: none", header_rules, ".hud-header must have pointer-events: none by default")

        # 2. Top sensor exists with height: 24px
        sensor_css_match = re.search(r'\.hud-top-sensor\s*\{([^}]+)\}', self.html_content)
        self.assertIsNotNone(sensor_css_match, "Could not find .hud-top-sensor CSS block")
        sensor_rules = sensor_css_match.group(1)
        self.assertTrue(bool(re.search(r'height:\s*24px', sensor_rules)),
            "Missing height: 24px on .hud-top-sensor")

        # 3. Top sensor hover reveals header
        self.assertTrue(
            bool(re.search(r'\.hud-top-sensor:hover\s*[+~]\s*\.hud-header', self.html_content)),
            "Missing hover rule connecting .hud-top-sensor:hover to .hud-header"
        )

        # 4. Moving mouse over subtitle stage must NOT trigger header
        self.assertNotIn("#hud-container:hover .hud-header", self.html_content,
            "Forbidden #hud-container:hover .hud-header found; hovering subtitles must not reveal header")

    def test_03_default_background_opacity_35_percent(self):
        """Default background opacity is 35% (rgba(18, 18, 22, 0.35)) with 3.5s auto-dimming."""
        # Container background contains 0.35
        self.assertIn("rgba(18, 18, 22, 0.35)", self.html_content,
            "Missing default 35% background opacity rgba(18, 18, 22, 0.35)")

        # JS opacities array starts with 35%
        self.assertTrue(bool(re.search(r"{\s*label:\s*['\"]💧 35%['\"],\s*bg:\s*['\"]rgba\(18,\s*18,\s*22,\s*0\.35\)['\"]\s*}", self.html_content)),
            "Missing default 35% item as first entry in opacities array")

        # Inactivity auto-dimming at 3500ms
        self.assertIn("3500", self.html_content, "Missing 3500ms auto-dimming timeout")
        self.assertIn(".dimmed", self.html_content, "Missing .dimmed CSS rule")

    def test_04_subtitle_stage_zero_vertical_scrollbars(self):
        """Subtitle stage has 0 vertical scrollbars (overflow: hidden)."""
        stage_css_match = re.search(r'\.subtitle-stage\s*\{([^}]+)\}', self.html_content)
        self.assertIsNotNone(stage_css_match, "Could not find .subtitle-stage CSS block")
        stage_rules = stage_css_match.group(1)
        self.assertIn("overflow: hidden", stage_rules, ".subtitle-stage must have overflow: hidden")

        # Ensure no auto or scroll overflow
        self.assertNotIn("overflow-y: scroll", self.html_content)
        self.assertNotIn("overflow-y: auto", self.html_content)

        # Fixed slot styles
        past_match = re.search(r'#pastLine\s*\{([^}]+)\}', self.html_content)
        self.assertIsNotNone(past_match, "Could not find #pastLine CSS block")
        self.assertIn("text-overflow: ellipsis", past_match.group(1))

        # Active line bold high-contrast yellow
        self.assertIn("#facc15", self.html_content, "Active line should use bright high-contrast yellow #facc15")

    def test_05_window_title_and_hwnd_unique_lookup(self):
        """Window title is 'Qwen_Meeting_HUD_Overlay_7x9' and Windows HWND lookup uses title."""
        self.assertIn('title="Qwen_Meeting_HUD_Overlay_7x9"', self.app_content,
            "create_window must use title='Qwen_Meeting_HUD_Overlay_7x9'")
        self.assertIn('FindWindowW(None, "Qwen_Meeting_HUD_Overlay_7x9")', self.app_content,
            "WindowsWindowController.get_hwnd must strictly find window by title 'Qwen_Meeting_HUD_Overlay_7x9'")

    def test_06_stealth_mode_implementation_and_functionality(self):
        """Stealth mode methods exist and function correctly."""
        from float_app import FloatingHUDApp, MacOSWindowController, WindowsWindowController, NativeWindowController, HudApi

        # 1. Inspect class definitions for stealth methods
        for cls in (MacOSWindowController, WindowsWindowController, NativeWindowController, HudApi, FloatingHUDApp):
            self.assertTrue(hasattr(cls, "set_stealth_mode"), f"{cls.__name__} missing set_stealth_mode")
            self.assertTrue(hasattr(cls, "is_stealth_mode"), f"{cls.__name__} missing is_stealth_mode")

        # 2. Test instantiation and toggle
        app = FloatingHUDApp(stealth=False)
        app.create_window()

        # Test enable stealth mode
        app.set_stealth_mode(True)
        self.assertTrue(app.is_stealth_mode(), "Failed to enable stealth mode on FloatingHUDApp")

        # Test disable stealth mode
        app.set_stealth_mode(False)
        self.assertFalse(app.is_stealth_mode(), "Failed to disable stealth mode on FloatingHUDApp")

        # Test status dictionary includes stealth key
        status = app.api.get_status()
        self.assertIn("stealth", status, "Status dictionary missing 'stealth' key")

        app.close()

    def test_07_open_browser_config_bridge_method(self):
        """HudApi exposes open_browser_config bridge method."""
        from float_app import FloatingHUDApp, HudApi
        app = FloatingHUDApp()
        api = HudApi(app)
        self.assertTrue(hasattr(api, "open_browser_config"), "HudApi missing open_browser_config method")

    def test_08_cli_stealth_flag_support(self):
        """CLI arguments include --stealth flag."""
        self.assertIn('"--stealth"', self.app_content, "CLI missing --stealth argument")


if __name__ == "__main__":
    unittest.main(verbosity=2)
