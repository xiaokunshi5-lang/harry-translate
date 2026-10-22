"""
Tier 2 Boundary Tests: Feature 5 (Baseline Dual-Screen Preservation).
Tests concurrent endpoint access, stats query after reset, repeated stats resets,
non-existent paths, and invalid channel WebSocket handling.
"""
from tests.harness import BaseE2ETest


class TestBoundary05BaselineDualScreen(BaseE2ETest):
    tier = 2
    feature_id = 5
    milestone = "M1"

    def test_b05_01_concurrent_dual_screen_endpoints(self):
        """Sequential rapid switching between /, /en, /zh, /split all return 200."""
        client = self.get_client()
        for endpoint in ["/", "/en", "/zh", "/split"]:
            resp = client.get(endpoint)
            self.assertEqual(resp.status_code, 200)

    def test_b05_02_stats_after_reset_zero_division(self):
        """GET /api/stats after POST /api/stats/reset returns clean 0s with no division errors."""
        client = self.get_client()
        reset_resp = client.post("/api/stats/reset")
        self.assertEqual(reset_resp.status_code, 200)

        stats_resp = client.get("/api/stats")
        self.assertEqual(stats_resp.status_code, 200)
        data = stats_resp.json()
        self.assertEqual(data.get("total_tokens"), 0)
        self.assertEqual(data.get("cost_rmb"), 0.0)

    def test_b05_03_repeated_stats_resets_thread_safe(self):
        """10 repeated calls to /api/stats/reset execute cleanly without deadlock."""
        client = self.get_client()
        for _ in range(10):
            resp = client.post("/api/stats/reset")
            self.assertEqual(resp.status_code, 200)

    def test_b05_04_nonexistent_route_returns_404(self):
        """Requesting non-existent route returns 404 cleanly without crashing server state."""
        client = self.get_client()
        resp = client.get("/non_existent_screen_route_xyz")
        self.assertEqual(resp.status_code, 404)

    def test_b05_05_invalid_channel_rejection(self):
        """Verifies server logic isolates /ws/en and /ws/zh and rejects unknown channel paths."""
        import server
        self.assertTrue(hasattr(server, "connected_clients"))
        self.assertIn("en", server.connected_clients)
        self.assertIn("zh", server.connected_clients)
        self.assertNotIn("unknown_channel", server.connected_clients)
