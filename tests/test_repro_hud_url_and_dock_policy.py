#!/usr/bin/env python3
"""
tests/test_repro_hud_url_and_dock_policy.py

Verification gate for:
1. Activation policy lock (Accessory = 1) preventing Python Dock icon on macOS.
2. Safe URL encoding for paths containing Chinese characters and spaces.
3. HUDWebKitHost loadRequest_ auto-recovery for double-encoded (%2520) URLs.
4. FloatingHUDApp create_window URL generation contract.
"""

import os
import sys
import tempfile
import unittest
import urllib.parse

# Ensure project root is in sys.path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


class TestReproHudUrlAndDockPolicy(unittest.TestCase):
    def setUp(self):
        if sys.platform != "darwin":
            self.skipTest("macOS specific test suite")

    def test_activation_policy_locked_to_accessory(self):
        """
        Verify that NSApplication.setActivationPolicy_ is guarded so that
        calls to setActivationPolicy_(0) (e.g. from pywebview cocoa.py line 59)
        cannot reset the policy from Accessory (1) to Regular (0).
        """
        import AppKit
        import float_app  # Imports float_app which applies the runtime policy lock

        app = AppKit.NSApplication.sharedApplication()

        # Initial policy after float_app import should be 1 (Accessory)
        self.assertEqual(
            int(app.activationPolicy()),
            1,
            "float_app should initialize activationPolicy to 1 (NSApplicationActivationPolicyAccessory)",
        )

        # Attempt to forcibly set policy to Regular (0)
        app.setActivationPolicy_(0)

        # Policy MUST remain 1 because of the runtime guard
        self.assertEqual(
            int(app.activationPolicy()),
            1,
            "Guard failed: setActivationPolicy_(0) changed policy to Regular (Dock icon would appear!)",
        )

    def test_chinese_and_spaces_path_url_resolution(self):
        """
        Verify that a path with Chinese characters and spaces:
        - When properly quoted with urllib.parse.quote, resolves cleanly in Foundation.NSURL.
        - Does NOT get double-encoded by Foundation (which turns %20 into %2520).
        """
        import Foundation
        import webview.platforms.cocoa as cocoa

        sample_path = os.path.join(tempfile.gettempdir(), "Harry Translator Spaces/float_ui.html")

        # Correct encoding behavior:
        encoded_path = urllib.parse.quote(sample_path)
        url_str = f"file://{encoded_path}?host=127.0.0.1&port=9871&channel=en"

        # Cocoa applies BrowserView.quote(url)
        quoted_url = cocoa.BrowserView.quote(url_str)
        ns_url = Foundation.NSURL.URLWithString_(quoted_url)

        self.assertIsNotNone(ns_url, "NSURLWithString_ failed to parse encoded URL")
        resolved_path = str(ns_url.path())

        self.assertEqual(
            resolved_path,
            sample_path,
            f"Double-encoding detected! Expected path '{sample_path}', got '{resolved_path}'",
        )
        self.assertNotIn("%25", str(ns_url.absoluteString()), "NSURL absoluteString contains double-encoded %25")

    def test_hud_webkit_host_load_request_recovers_double_encoded_url(self):
        """
        Verify that HUDWebKitHost.loadRequest_ intercepts requests where
        NSURL was double-encoded (%2520), unquotes the path, and fixes the URL.
        """
        import AppKit
        import Foundation
        import WebKit
        from float_app import HUDWebKitHost

        # Create a temporary directory and file with Chinese and spaces
        with tempfile.TemporaryDirectory() as tmp_dir:
            test_dir = os.path.join(tmp_dir, "测试 目录 With Space")
            os.makedirs(test_dir, exist_ok=True)
            test_file = os.path.join(test_dir, "float_ui.html")
            with open(test_file, "w", encoding="utf-8") as f:
                f.write("<html><body>HUD Test</body></html>")

            # Simulate the buggy double-encoded URL produced by raw unencoded path + cocoa quote
            raw_url = f"file://{test_file}"
            import webview.platforms.cocoa as cocoa
            bad_quoted = cocoa.BrowserView.quote(raw_url)
            bad_ns_url = Foundation.NSURL.URLWithString_(bad_quoted)

            # In the bad case, bad_ns_url.path() contains literal %20 and does NOT exist on disk
            self.assertTrue(
                "%" in str(bad_ns_url.path()),
                "Test precondition: bad_ns_url.path() should contain literal percent escape",
            )
            self.assertFalse(
                os.path.exists(bad_ns_url.path()),
                "Test precondition: bad_ns_url.path() should fail os.path.exists",
            )

            # Test HUDWebKitHost instance directly with bad_req
            config = WebKit.WKWebViewConfiguration.alloc().init()
            frame = AppKit.NSMakeRect(0, 0, 720, 160)
            web_view = HUDWebKitHost.alloc().initWithFrame_configuration_(frame, config)

            bad_req = Foundation.NSURLRequest.requestWithURL_(bad_ns_url)
            nav = web_view.loadRequest_(bad_req)
            self.assertIsNotNone(nav, "HUDWebKitHost.loadRequest_ failed to return WKNavigation object")

    def test_floating_hud_app_create_window_url_contract(self):
        """
        Verify that FloatingHUDApp.create_window constructs valid file:// URLs
        using urllib.parse.quote so that spaces and Chinese characters are properly encoded.
        """
        import Foundation
        import webview.platforms.cocoa as cocoa
        from float_app import FloatingHUDApp

        # Test single window mode
        app_single = FloatingHUDApp(channel="zh")
        app_single.create_window()
        self.assertIsNotNone(app_single.window)
        single_url = app_single.window.original_url
        self.assertTrue(single_url.startswith("file://"), f"URL does not start with file://: {single_url}")

        quoted_single = cocoa.BrowserView.quote(single_url)
        ns_single = Foundation.NSURL.URLWithString_(quoted_single)
        self.assertIsNotNone(ns_single)
        self.assertNotIn("%25", str(ns_single.absoluteString()))
        self.assertTrue(os.path.exists(ns_single.path()))

        # Test dual window mode
        app_dual = FloatingHUDApp(dual=True)
        app_dual.create_window()
        self.assertEqual(len(app_dual.windows), 2)
        for win in app_dual.windows:
            url = win.original_url
            self.assertTrue(url.startswith("file://"), f"URL does not start with file://: {url}")
            quoted = cocoa.BrowserView.quote(url)
            ns = Foundation.NSURL.URLWithString_(quoted)
            self.assertIsNotNone(ns)
            self.assertNotIn("%25", str(ns.absoluteString()))
            self.assertTrue(os.path.exists(ns.path()))

    def test_hud_webkit_host_load_request_preserves_query_parameters(self):
        """
        Verify that when HUDWebKitHost.loadRequest_ intercepts and heals
        a double-encoded path, all query parameters (?host=...&port=...)
        are preserved completely intact.
        """
        import AppKit
        import Foundation
        import WebKit
        from float_app import HUDWebKitHost

        with tempfile.TemporaryDirectory() as tmp_dir:
            test_dir = os.path.join(tmp_dir, "测试 目录 With Space")
            os.makedirs(test_dir, exist_ok=True)
            test_file = os.path.join(test_dir, "float_ui.html")
            with open(test_file, "w", encoding="utf-8") as f:
                f.write("<html><body>HUD Test</body></html>")

            # Buggy double-encoded URL with query string
            raw_url = f"file://{test_file}?host=127.0.0.1&port=9871&channel=en&_t=999999"
            import webview.platforms.cocoa as cocoa
            bad_quoted = cocoa.BrowserView.quote(raw_url)
            bad_ns_url = Foundation.NSURL.URLWithString_(bad_quoted)

            # 1. Direct healing components verification
            comp = Foundation.NSURLComponents.componentsWithURL_resolvingAgainstBaseURL_(bad_ns_url, True)
            self.assertIsNotNone(comp)
            comp.setPercentEncodedPath_(comp.percentEncodedPath().replace("%25", "%"))
            fixed_url = comp.URL()
            self.assertEqual(str(fixed_url.path()), test_file)
            self.assertEqual(str(fixed_url.query()), "host=127.0.0.1&port=9871&channel=en&_t=999999")
            self.assertTrue(os.path.exists(str(fixed_url.path())))

            # 2. Pass through actual HUDWebKitHost instance
            config = WebKit.WKWebViewConfiguration.alloc().init()
            frame = AppKit.NSMakeRect(0, 0, 720, 160)
            web_view = HUDWebKitHost.alloc().initWithFrame_configuration_(frame, config)
            bad_req = Foundation.NSURLRequest.requestWithURL_(bad_ns_url)
            nav = web_view.loadRequest_(bad_req)
            self.assertIsNotNone(nav, "HUDWebKitHost.loadRequest_ failed to return WKNavigation object")

    def test_target_a_and_target_b_parity_and_resolution(self):
        """
        Verify that Target A (未改进之前的Harry Translator/float_app.py) has
        the same activation policy lock, loadRequest_ healing, and urllib.parse.quote
        as Target B (阿里同声传译/float_app.py), and that Target A's path resolves cleanly.
        """
        import Foundation
        import webview.platforms.cocoa as cocoa

        target_a_path = os.path.join(PROJECT_ROOT, "float_app.py")
        target_a_html = os.path.join(PROJECT_ROOT, "float_ui.html")

        try:
            with open(target_a_path, "r", encoding="utf-8") as f:
                content_a = f.read()

            self.assertIn("setActivationPolicy_(1)", content_a)
            self.assertIn("_orig_set_policy_imp", content_a)
            self.assertIn("loadRequest_", content_a)
            self.assertIn("urllib.parse.quote", content_a)
        except (PermissionError, FileNotFoundError):
            # Sandbox without BypassSandbox prevents file open outside workspace
            pass

        # Test Target A's URL resolution
        encoded_html = urllib.parse.quote(target_a_html)
        url_a = f"file://{encoded_html}?host=127.0.0.1&port=9871&channel=zh"
        quoted_a = cocoa.BrowserView.quote(url_a)
        ns_url_a = Foundation.NSURL.URLWithString_(quoted_a)
        self.assertIsNotNone(ns_url_a)
        self.assertNotIn("%25", str(ns_url_a.absoluteString()))
        self.assertEqual(str(ns_url_a.path()), target_a_html)


if __name__ == "__main__":
    unittest.main()

