"""
Feature 5: Baseline Dual-Screen Preservation (Milestone M1).
Verifies 100% backward compatibility for existing routes /, /en, /zh, /split,
start.sh, and 启动同传系统.command.
"""
import os
from tests.harness import BaseE2ETest, PROJECT_ROOT


class TestFeature05BaselineDualScreen(BaseE2ETest):
    tier = 1
    feature_id = 5
    milestone = "M1"

    def test_f05_01_root_dashboard_accessible(self):
        """GET / returns HTTP 200 and loads index.html dashboard."""
        client = self.get_client()
        resp = client.get("/")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("text/html", resp.headers.get("content-type", ""))
        self.assertIn("实时同传系统", resp.text)

    def test_f05_02_en_screen_accessible(self):
        """GET /en returns HTTP 200 and loads dedicated English screen."""
        client = self.get_client()
        resp = client.get("/en")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("text/html", resp.headers.get("content-type", ""))
        self.assertIn("<!DOCTYPE html>", resp.text)

    def test_f05_03_zh_screen_accessible(self):
        """GET /zh returns HTTP 200 and loads dedicated Chinese screen."""
        client = self.get_client()
        resp = client.get("/zh")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("text/html", resp.headers.get("content-type", ""))
        self.assertIn("<!DOCTYPE html>", resp.text)

    def test_f05_04_split_screen_accessible(self):
        """GET /split returns HTTP 200 and loads dual-column split monitor screen."""
        client = self.get_client()
        resp = client.get("/split")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("text/html", resp.headers.get("content-type", ""))
        self.assertIn("<!DOCTYPE html>", resp.text)

    def test_f05_05_start_script_preservation(self):
        """start.sh and 启动同传系统.command exist and are executable."""
        start_sh = os.path.join(PROJECT_ROOT, "start.sh")
        self.assertTrue(os.path.exists(start_sh), "start.sh is missing")
        with open(start_sh, "r", encoding="utf-8") as f:
            sh_content = f.read()
        self.assertIn("server.py", sh_content, "start.sh does not launch server.py")

        cmd_mac = os.path.join(PROJECT_ROOT, "启动同传系统.command")
        self.assertTrue(os.path.exists(cmd_mac), "启动同传系统.command is missing")
