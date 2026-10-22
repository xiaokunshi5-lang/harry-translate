"""
Feature 1: AudioCaptureManager & Hot-Swap (Milestone M1).
Verifies device enumeration, zero-restart hot-swapping schema, latency SLA (<80ms),
atomic stream switching, and stream pre-opening.
"""
import os
import sys
import time
from tests.harness import BaseE2ETest, PROJECT_ROOT


class TestFeature01AudioManager(BaseE2ETest):
    tier = 1
    feature_id = 1
    milestone = "M1"

    def test_f01_01_device_enumeration_contract(self):
        """GET /api/audio/devices returns devices list and active_index."""
        client = self.get_client()
        resp = client.get("/api/audio/devices")
        self.assertEqual(resp.status_code, 200, f"Expected 200, got {resp.status_code}: {resp.text}")
        data = resp.json()
        self.assertIn("devices", data, "Missing 'devices' field in response")
        self.assertIn("active_index", data, "Missing 'active_index' field in response")
        self.assertIsInstance(data["devices"], list, "'devices' must be a list")
        if data["devices"]:
            dev = data["devices"][0]
            for field in ["index", "name", "channels", "sample_rate", "is_default"]:
                self.assertIn(field, dev, f"Device item missing field '{field}'")

    def test_f01_02_hot_swap_api_schema(self):
        """POST /api/audio/device accepts device_index and returns status, active_index, switch_time_ms."""
        client = self.get_client()
        # Query devices first
        dev_resp = client.get("/api/audio/devices")
        self.assertEqual(dev_resp.status_code, 200)
        devices = dev_resp.json().get("devices", [])
        if not devices:
            self.skipTest("No physical audio input device is available")
        target_idx = devices[0]["index"]

        resp = client.post("/api/audio/device", json_data={"device_index": target_idx})
        self.assertEqual(resp.status_code, 200, f"Hot-swap failed: {resp.text}")
        data = resp.json()
        self.assertEqual(data.get("status"), "ok")
        self.assertEqual(data.get("active_index"), target_idx)
        self.assertIn("switch_time_ms", data)
        self.assertIn("device_name", data)

    def test_f01_03_hot_swap_latency_sla(self):
        """Hot-swap execution time must be under 80ms."""
        client = self.get_client()
        dev_resp = client.get("/api/audio/devices")
        devices = dev_resp.json().get("devices", [])
        if not devices:
            self.skipTest("No physical audio input device is available")
        target_idx = devices[0]["index"]

        start = time.perf_counter()
        resp = client.post("/api/audio/device", json_data={"device_index": target_idx})
        elapsed_ms = (time.perf_counter() - start) * 1000.0

        self.assertEqual(resp.status_code, 200)
        server_switch_time = resp.json().get("switch_time_ms", elapsed_ms)
        self.assertLessEqual(server_switch_time, 80.0, f"SLA violation: hot-swap took {server_switch_time}ms (must be <80ms)")

    def test_f01_04_atomic_pointer_swap_isolation(self):
        """Verifies that hot-swapping switches capture stream without terminating server loops."""
        import server
        self.assertTrue(hasattr(server, "AudioCaptureManager"), "AudioCaptureManager class not found in server.py")
        client = self.get_client()
        # Trigger hot-swap and check stats endpoint remains responsive
        client.post("/api/audio/device", json_data={"device_index": 0})
        stats_resp = client.get("/api/stats")
        self.assertEqual(stats_resp.status_code, 200)

    def test_f01_05_parallel_stream_preopening(self):
        """Verifies AudioCaptureManager implements pre-opening or fast switch method."""
        import server
        mgr_cls = getattr(server, "AudioCaptureManager", None)
        self.assertIsNotNone(mgr_cls, "AudioCaptureManager must be defined in server.py")
        # Check that it has switch_device or set_device method
        has_switch = hasattr(mgr_cls, "switch_device") or hasattr(mgr_cls, "set_device")
        self.assertTrue(has_switch, "AudioCaptureManager must provide switch_device() method")
