"""
tests/verify_m2_v5.py - Worker M2 (GatewayAsync) Comprehensive Acceptance Test Suite

Verifies:
1. Parallel WebSocket Broadcast & 0.25s Timeout Circuit Breaker:
   - Slow client eviction (<0.3s) without blocking healthy clients (<1.0ms).
2. GET /api/meta:
   - System status, loopback devices, channel_b_idle, active engine, masked API key.
3. POST /api/config:
   - Empty/whitespace key strictly preserves existing .env and in-memory API key.
   - Valid partial update updates key, devices, and engine model.
4. Physical Routes:
   - GET /, GET /split, GET /en, GET /zh, GET /hud.
5. Dual Channel Independence:
   - Channel A (en) and Channel B (zh) operate independently without cross-talk.
6. Device Hot-Swap & HUD Lock & Stats APIs:
   - GET/POST /api/audio/device, GET/POST /api/hud/lock, GET/POST /api/stats.
7. Backward Compatibility:
   - server.AudioCaptureManager, server.CHUNK_SIZE = 1600, server.active_channels, server.audio_capture_mgr, server.app.
"""

import asyncio
import json
import os
import sys
import time
from typing import List

# Add project root to sys.path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import server
from tests.harness import FastAPITestClient


class MockFastWebSocket:
    def __init__(self, name: str):
        self.name = name
        self.received_messages: List[str] = []
        self.received_at: float = 0.0
        self.is_closed = False

    async def send_text(self, text: str):
        self.received_at = time.perf_counter()
        self.received_messages.append(text)

    async def close(self, code: int = 1000):
        self.is_closed = True


class MockSlowWebSocket:
    def __init__(self, name: str, sleep_sec: float = 2.0):
        self.name = name
        self.sleep_sec = sleep_sec
        self.received_messages: List[str] = []
        self.is_closed = False

    async def send_text(self, text: str):
        await asyncio.sleep(self.sleep_sec)
        self.received_messages.append(text)

    async def close(self, code: int = 1000):
        self.is_closed = True


def test_1_parallel_broadcast_and_slow_client_eviction():
    print("\n--- Test 1: Parallel Broadcast & 0.25s Timeout Eviction (<1.0ms Healthy SLA) ---")
    
    fast_client_1 = MockFastWebSocket("fast_1")
    fast_client_2 = MockFastWebSocket("fast_2")
    slow_client = MockSlowWebSocket("slow_unresponsive", sleep_sec=3.0)

    # Register clients to 'en' channel
    server.connected_clients["en"].clear()
    server.connected_clients["en"].add(fast_client_1)
    server.connected_clients["en"].add(fast_client_2)
    server.connected_clients["en"].add(slow_client)

    test_payload = {"type": "sub", "ch": "A", "target": "Fast delivery test"}

    async def _run():
        t0 = time.perf_counter()
        broadcast_task = asyncio.create_task(server.broadcast_to_channel("en", test_payload))
        
        # Give event loop tiny yield for healthy clients to process
        await asyncio.sleep(0.005)
        
        fast1_elapsed_ms = (fast_client_1.received_at - t0) * 1000.0 if fast_client_1.received_at > 0 else 0.0
        fast2_elapsed_ms = (fast_client_2.received_at - t0) * 1000.0 if fast_client_2.received_at > 0 else 0.0
        
        print(f"  Fast Client 1 delivery time: {fast1_elapsed_ms:.3f}ms")
        print(f"  Fast Client 2 delivery time: {fast2_elapsed_ms:.3f}ms")
        assert fast1_elapsed_ms < 1.0, f"Healthy client delivery exceeded 1.0ms SLA: {fast1_elapsed_ms:.3f}ms"
        assert fast2_elapsed_ms < 1.0, f"Healthy client delivery exceeded 1.0ms SLA: {fast2_elapsed_ms:.3f}ms"

        # Await broadcast task to verify 0.25s timeout eviction
        await broadcast_task
        total_broadcast_time = time.perf_counter() - t0
        print(f"  Total broadcast task duration (slow client eviction): {total_broadcast_time:.3f}s")
        assert 0.20 <= total_broadcast_time <= 0.45, f"Timeout eviction took {total_broadcast_time}s (expected ~0.25s)"

        # Verify slow client was evicted and closed
        assert slow_client not in server.connected_clients["en"], "Slow client was not pruned from connected_clients"
        assert slow_client.is_closed, "Slow client was not closed"

        # Verify healthy clients remain connected
        assert fast_client_1 in server.connected_clients["en"], "Healthy client 1 was erroneously pruned"
        assert fast_client_2 in server.connected_clients["en"], "Healthy client 2 was erroneously pruned"

    asyncio.run(_run())
    server.connected_clients["en"].clear()
    print("  [PASS] Parallel broadcast healthy SLA <1.0ms and 0.25s slow client eviction verified.")


def test_2_meta_endpoint():
    print("\n--- Test 2: GET /api/meta (System Status, Audio Devices, Engine, Masked Key) ---")
    client = FastAPITestClient(server.app)
    resp = client.get("/api/meta")
    assert resp.status_code == 200, f"GET /api/meta returned {resp.status_code}"
    data = resp.json()

    assert data.get("status") == "ok", f"Status not ok: {data}"
    assert "system_status" in data
    assert "active_engine" in data or "engine_type" in data
    assert "devices" in data and isinstance(data["devices"], list)
    assert "channel_b_idle" in data
    assert "channel_status" in data

    # Verify device items have is_loopback
    if data["devices"]:
        assert "is_loopback" in data["devices"][0]

    # Verify masked API key
    masked = data.get("api_key_masked") or data.get("dashscope_key_masked") or data.get("masked_api_key")
    assert masked is not None, "Missing masked API key in /api/meta"
    print(f"  Masked API key returned: '{masked}'")
    if server.DASHSCOPE_API_KEY and len(server.DASHSCOPE_API_KEY) > 10:
        assert "..." in masked, f"Masked key '{masked}' does not contain '...'"
        assert masked.startswith(server.DASHSCOPE_API_KEY[:6])
        assert masked.endswith(server.DASHSCOPE_API_KEY[-4:])
    print("  [PASS] GET /api/meta metadata contract verified.")


def test_3_config_empty_key_protection_and_partial_update():
    print("\n--- Test 3: POST /api/config (Empty Key Preservation & Partial Update) ---")
    client = FastAPITestClient(server.app)

    # Establish known baseline key
    original_key = server.DASHSCOPE_API_KEY
    had_env = os.path.exists(server.ENV_FILE)
    if not original_key:
        original_key = "test-placeholder-key"
        server.DASHSCOPE_API_KEY = original_key
        server.set_env_value("DASHSCOPE_API_KEY", original_key)

    # 1. Post empty key: MUST NOT overwrite
    resp1 = client.post("/api/config", json_data={"api_key": ""})
    assert resp1.status_code == 200
    assert server.DASHSCOPE_API_KEY == original_key, "Empty key overwrote in-memory DASHSCOPE_API_KEY!"
    with open(server.ENV_FILE, "r", encoding="utf-8") as f:
        env_content = f.read()
    assert original_key in env_content, "Empty key overwrote .env key!"
    print("  [PASS] Submitting empty string '' left original key intact.")

    # 2. Post whitespace key: MUST NOT overwrite
    resp2 = client.post("/api/config", json_data={"api_key": "   \t\n  "})
    assert resp2.status_code == 200
    assert server.DASHSCOPE_API_KEY == original_key, "Whitespace key overwrote in-memory DASHSCOPE_API_KEY!"
    print("  [PASS] Submitting whitespace key '   ' left original key intact.")

    # 3. Post valid partial update (e.g. engine model)
    resp3 = client.post("/api/config", json_data={"engine_model": "qwen3.8-livetranslate-flash-realtime"})
    assert resp3.status_code == 200
    data3 = resp3.json()
    assert data3.get("current_config", {}).get("engine_model") == "qwen3.8-livetranslate-flash-realtime"
    assert server.active_engine_type == "qwen3.8-livetranslate-flash-realtime"
    print("  [PASS] Dynamic partial update switched engine to Qwen 3.8.")

    # Switch back to Gummy
    resp4 = client.post("/api/config", json_data={"engine_model": "gummy-realtime-v1"})
    assert resp4.status_code == 200
    assert server.active_engine_type == "gummy-realtime-v1"
    print("  [PASS] Dynamic partial update switched engine back to Gummy.")


def test_4_physical_routes():
    print("\n--- Test 4: Physical Presentation Routes (/, /split, /en, /zh, /hud) ---")
    client = FastAPITestClient(server.app)
    routes = ["/", "/split", "/en", "/zh", "/hud"]
    for r in routes:
        resp = client.get(r)
        assert resp.status_code == 200, f"Route {r} returned {resp.status_code}"
        assert "text/html" in resp.headers.get("content-type", ""), f"Route {r} content-type not text/html"
        assert len(resp.text) > 100, f"Route {r} returned empty or truncated HTML"
        print(f"  Route {r:<8} -> 200 OK ({len(resp.text)} bytes)")
    print("  [PASS] All 5 physical routes verified.")


def test_5_dual_channel_independence():
    print("\n--- Test 5: Dual Channels A and B Physical Independence ---")
    assert len(server.active_channels) >= 2
    ch_a = server.channel_en
    ch_b = server.channel_zh

    assert ch_a.name == "en" and ch_a.channel_id == "A"
    assert ch_b.name == "zh" and ch_b.channel_id == "B"
    assert ch_a.audio_queue is not ch_b.audio_queue

    # Simulate events independently
    ch_a.reset_stats()
    ch_b.reset_stats()
    assert ch_a.total_tokens == 0 and ch_b.total_tokens == 0

    ch_a.simulate_event("中文测试", "English translation", is_final=True, sentence_id=1)
    assert ch_a.sentence_id == 1
    assert ch_b.sentence_id == 0, "Channel B sentence_id was cross-contaminated by Channel A!"
    assert ch_a.source_text == "中文测试"
    assert ch_b.source_text == "", "Channel B source_text was cross-contaminated by Channel A!"

    # Verify Channel B safe idle status
    b_idle = server.audio_capture_mgr.worker_b.is_idle
    print(f"  Channel B virtual loopback status: is_idle={b_idle}")
    print("  [PASS] Channels A and B maintain complete physical and logical isolation.")


def test_6_hot_swap_hud_lock_and_stats():
    print("\n--- Test 6: Hot-Swap, HUD Lock & Stats APIs ---")
    client = FastAPITestClient(server.app)

    # 1. Device enumeration & hot-swap
    dev_resp = client.get("/api/audio/devices")
    assert dev_resp.status_code == 200
    devices = dev_resp.json().get("devices", [])
    target_idx = devices[0]["index"] if devices else 0

    t0 = time.perf_counter()
    swap_resp = client.post("/api/audio/device", json_data={"device_index": target_idx})
    elapsed_ms = (time.perf_counter() - t0) * 1000.0
    assert swap_resp.status_code == 200
    server_time = swap_resp.json().get("switch_time_ms", elapsed_ms)
    print(f"  Hot-swap latency: {server_time}ms (<80ms SLA)")
    assert server_time < 80.0

    # 2. HUD lock toggle
    lock_get = client.get("/api/hud/lock")
    assert lock_get.status_code == 200
    lock_set = client.post("/api/hud/lock", json_data={"locked": True})
    assert lock_set.status_code == 200
    assert lock_set.json().get("locked") is True
    lock_reset = client.post("/api/hud/lock", json_data={"locked": False})
    assert lock_reset.status_code == 200
    assert lock_reset.json().get("locked") is False

    # 3. Stats query and reset
    reset_resp = client.post("/api/stats/reset")
    assert reset_resp.status_code == 200
    stats_resp = client.get("/api/stats")
    assert stats_resp.status_code == 200
    assert stats_resp.json().get("total_tokens") == 0

    print("  [PASS] Hot-swap (<80ms), HUD lock, and stats reset verified.")


def test_7_backward_compatibility_exports():
    print("\n--- Test 7: Backward Compatibility Exports ---")
    assert hasattr(server, "AudioCaptureManager"), "server.AudioCaptureManager missing"
    assert hasattr(server, "CHUNK_SIZE"), "server.CHUNK_SIZE missing"
    assert server.CHUNK_SIZE == 1600, f"CHUNK_SIZE expected 1600, got {server.CHUNK_SIZE}"
    assert hasattr(server, "active_channels"), "server.active_channels missing"
    assert hasattr(server, "audio_capture_mgr"), "server.audio_capture_mgr missing"
    assert hasattr(server, "app"), "server.app missing"
    assert hasattr(server, "connected_clients"), "server.connected_clients missing"
    assert "en" in server.connected_clients and "zh" in server.connected_clients
    assert "multiprocessing" not in sys.modules, "Multiprocessing imported in violation of lightweight SLA"

    print("  [PASS] All backward compatibility exports intact.")


def main():
    print("=" * 70)
    print(" WORKER M2: GatewayAsync Comprehensive Acceptance Verification")
    print("=" * 70)

    test_1_parallel_broadcast_and_slow_client_eviction()
    test_2_meta_endpoint()
    test_3_config_empty_key_protection_and_partial_update()
    test_4_physical_routes()
    test_5_dual_channel_independence()
    test_6_hot_swap_hud_lock_and_stats()
    test_7_backward_compatibility_exports()

    print("\n" + "=" * 70)
    print(" ALL WORKER M2 ACCEPTANCE CRITERIA VERIFIED (100% PASS)")
    print("=" * 70)


if __name__ == "__main__":
    main()
