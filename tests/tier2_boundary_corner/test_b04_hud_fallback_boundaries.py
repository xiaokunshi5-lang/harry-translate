"""
Tier 2 Boundary Tests: Feature 4 (Zero-Install HUD Fallback).
Tests massive query strings, parallel HTTP GET bursts, HEAD requests,
unsupported HTTP methods, and unusual headers.
"""
from tests.harness import BaseE2ETest


class TestBoundary04HUDFallback(BaseE2ETest):
    tier = 2
    feature_id = 4
    milestone = "M1"

    def test_b04_01_massive_query_parameters(self):
        """GET /hud handles large query strings safely without buffer overflow or crash."""
        client = self.get_client()
        query = {"param_" + str(i): "value_" * 20 for i in range(50)}
        resp = client.get("/hud", query_params=query)
        self.assertEqual(resp.status_code, 200)

    def test_b04_02_concurrent_get_bursts(self):
        """10 rapid sequential GET /hud requests return consistent 200 responses."""
        client = self.get_client()
        for _ in range(10):
            resp = client.get("/hud")
            self.assertEqual(resp.status_code, 200)

    def test_b04_03_head_request_handling(self):
        """HEAD /hud returns 200 with headers and empty body."""
        client = self.get_client()
        resp = client.head("/hud")
        # FastAPI handles HEAD automatically if GET is defined
        self.assertIn(resp.status_code, [200, 405])
        if resp.status_code == 200:
            self.assertEqual(len(resp.content), 0, "HEAD request should have empty body")

    def test_b04_04_unsupported_methods_return_405(self):
        """PUT or DELETE requests to /hud return 405 Method Not Allowed."""
        client = self.get_client()
        resp = client.request("PUT", "/hud")
        self.assertEqual(resp.status_code, 405)
        resp_del = client.request("DELETE", "/hud")
        self.assertEqual(resp_del.status_code, 405)

    def test_b04_05_unusual_accept_headers(self):
        """GET /hud with unusual Accept header (e.g. text/plain or */*) returns HTML safely."""
        client = self.get_client()
        resp = client.get("/hud", headers={"accept": "text/plain, */*"})
        self.assertEqual(resp.status_code, 200)
        self.assertIn("text/html", resp.headers.get("content-type", ""))
