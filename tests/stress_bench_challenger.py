#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
tests/stress_bench_challenger.py
--------------------------------------------------------------------------------
Empirical Challenger Adversarial Stress-Test & Performance Benchmark Harness.

Dimensions Challenged:
1. Dimension A: Aho-Corasick Algorithm & Edge Cases (Rebuild, Substrings, Emojis, Pathological)
2. Dimension B: AC-G1 Latency Benchmark (100-char vs 5,000 terms, SLA <= 0.5ms / target <= 0.15ms)
3. Dimension C: AC-G4 Dynamic Reload Benchmark (Latency vs Dictionary Scale, SLA <= 5.0ms)
4. Dimension D: Concurrency & Thread-Safety Stress (Readers + Writers Race Condition / Deadlock)
5. Dimension E: Malformed, Corrupted, and Boundary Dictionaries
6. Dimension F: Concurrent WebSocket Streaming & Broadcast Circuit-Breaker
--------------------------------------------------------------------------------
"""

import os
import sys
import time
import json
import random
import string
import asyncio
import threading
import statistics
from typing import Dict, List, Tuple, Any

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from core.glossary_manager import AhoCorasickAutomaton, GlossaryManager, get_glossary_manager
import server
from tests.harness import FastAPITestClient


class ChallengerHarness:
    def __init__(self):
        self.results: Dict[str, Any] = {}
        self.client = FastAPITestClient(server.app)
        self.mgr = get_glossary_manager()
        self.mgr.load()
        self.orig_data = json.loads(json.dumps(self.mgr.to_dict()))

    def restore_glossary(self):
        self.mgr.reload(new_data=self.orig_data, persist=True)

    # --------------------------------------------------------------------------
    # Dimension A: Aho-Corasick Algorithm & Edge Cases
    # --------------------------------------------------------------------------
    def test_dim_a_aho_corasick_edge_cases(self) -> Dict[str, Any]:
        print("\n" + "="*70)
        print(" [DIMENSION A] Aho-Corasick Automaton & Edge Case Analysis")
        print("="*70)
        findings = []

        # A1: Test duplicate build / re-build on same instance
        auto = AhoCorasickAutomaton()
        auto.add_word("abc", "1")
        auto.add_word("bc", "2")
        auto.build()
        res1 = auto.replace_all("abc")

        # Now re-build without adding words
        auto.build()
        res2 = auto.replace_all("abc")

        # Now add new word and build again
        auto.add_word("c", "3")
        auto.build()
        res3 = auto.replace_all("abc")

        # Check if outputs duplicate in nodes
        dup_outputs = False
        queue = [auto.root]
        while queue:
            curr = queue.pop(0)
            pats = [p for p, _ in curr.outputs]
            if len(pats) != len(set(pats)):
                dup_outputs = True
                break
            for child in curr.children.values():
                queue.append(child)

        a1_status = (res1 == "1" and res2 == "1" and res3 == "1" and not dup_outputs)
        findings.append({
            "test": "A1_Rebuild_Idempotence",
            "pass": a1_status,
            "details": f"res1={res1}, res2={res2}, res3={res3}, duplicate_outputs={dup_outputs}"
        })
        print(f"  [A1] Re-build Idempotence & Output Deduplication: {'PASS' if a1_status else 'FAIL (Bug found: duplicate outputs)'}")

        # A2: Leftmost-longest & nested prefix/suffix matching
        auto2 = AhoCorasickAutomaton()
        auto2.add_word("Transformer", "TF")
        auto2.add_word("Transformer架构", "TF_ARCH")
        auto2.add_word("Former", "FM")
        auto2.build()

        t_text = "我们采用Transformer架构进行训练，而不是单纯的Transformer或Former模型。"
        res_t = auto2.replace_all(t_text)
        expected_t = "我们采用TF_ARCH进行训练，而不是单纯的TF或FM模型。"
        a2_status = (res_t == expected_t)
        findings.append({
            "test": "A2_Leftmost_Longest_Nested",
            "pass": a2_status,
            "details": f"output={res_t}, expected={expected_t}"
        })
        print(f"  [A2] Leftmost-Longest & Nested Matching: {'PASS' if a2_status else 'FAIL'}")

        # A3: Chain of substrings: "a", "aa", "aaa"
        auto3 = AhoCorasickAutomaton()
        auto3.add_word("a", "1")
        auto3.add_word("aa", "2")
        auto3.add_word("aaa", "3")
        auto3.build()
        res_chain = auto3.replace_all("aaaaa")
        # Greedy leftmost longest: at index 0, matches "aaa" (len 3, 0..3) -> replaced by "3"
        # at index 3, remaining "aa" (len 2, 3..5) -> replaced by "2". Output: "32"
        a3_status = (res_chain == "32")
        findings.append({
            "test": "A3_Chain_Substrings",
            "pass": a3_status,
            "details": f"input='aaaaa', output='{res_chain}', expected='32'"
        })
        print(f"  [A3] Substring Chain Greedy Partition: {'PASS' if a3_status else 'FAIL'}")

        # A4: Special Characters, Regex Metacharacters, Emojis, Surrogates, RTL
        auto4 = AhoCorasickAutomaton()
        auto4.add_word(".*+?^${}()|[]\\", "REGEX_META")
        auto4.add_word("🤖🚀🔥", "EMOJI_TRIO")
        auto4.add_word("مرحبا", "ARABIC_HELLO")
        auto4.add_word("Привет", "RUSSIAN_HELLO")
        auto4.add_word("line1\nline2\tline3\0null", "CONTROL_CHARS")
        auto4.build()

        test_complex = "Test .*+?^${}()|[]\\ and 🤖🚀🔥 with مرحبا and Привет plus line1\nline2\tline3\0null end."
        res_complex = auto4.replace_all(test_complex)
        expected_complex = "Test REGEX_META and EMOJI_TRIO with ARABIC_HELLO and RUSSIAN_HELLO plus CONTROL_CHARS end."
        a4_status = (res_complex == expected_complex)
        findings.append({
            "test": "A4_Complex_Unicode_Control_Regex",
            "pass": a4_status,
            "details": f"match={a4_status}"
        })
        print(f"  [A4] Complex Unicode, Control Chars & Regex Literals: {'PASS' if a4_status else 'FAIL'}")

        # A5: Pathological text: repeated 'a' with long pattern 'a'*50
        auto5 = AhoCorasickAutomaton()
        for k in range(5, 55, 5):
            auto5.add_word("a" * k, f"[{k}]")
        auto5.build()

        pathological_text = "a" * 10000
        t0 = time.perf_counter()
        res_path = auto5.replace_all(pathological_text)
        path_ms = (time.perf_counter() - t0) * 1000.0
        # 10,000 chars should complete in < 50ms in pure Python
        a5_status = (path_ms < 50.0 and len(res_path) > 0)
        findings.append({
            "test": "A5_Pathological_Text_Repeats",
            "pass": a5_status,
            "details": f"10k chars took {path_ms:.3f}ms"
        })
        print(f"  [A5] Pathological 10,000-char Repetitive Sequence: {'PASS' if a5_status else 'FAIL'} ({path_ms:.3f}ms)")

        self.results["dim_a"] = findings
        return {"dimension": "A", "findings": findings}

    # --------------------------------------------------------------------------
    # Dimension B: AC-G1 Latency & Scaling Benchmark
    # --------------------------------------------------------------------------
    def test_dim_b_ac_g1_latency_benchmark(self) -> Dict[str, Any]:
        print("\n" + "="*70)
        print(" [DIMENSION B] AC-G1 Latency & Algorithmic Scaling Benchmark")
        print("="*70)

        # 1. Official AC-G1: 100-character test sentence against 5,000 terms
        auto = AhoCorasickAutomaton()
        for i in range(5000):
            auto.add_word(f"专有行业术语_{i:04d}", f"DomainTerm_{i:04d}")
        auto.add_word("落拉", "LoRA")
        auto.add_word("反向传播", "Backpropagation")
        auto.add_word("注意力机制", "Attention Mechanism")
        auto.add_word("提示词工程", "Prompt Engineering")
        auto.add_word("单克隆抗体", "Monoclonal Antibody")
        auto.build()

        test_sentence = (
            "在现代深度学习系统架构中，落拉微调技术与自注意力机制以及反向传播算法被深度结合，"
            "专有行业术语_2500与提示词工程在大模型开发上表现出了优越的通用扩展能力与工业级鲁棒性！"
        )
        assert len(test_sentence) >= 70

        # Warmup
        for _ in range(100):
            auto.replace_all(test_sentence)

        # Measure 1,000 iterations
        latencies_ms = []
        for _ in range(1000):
            t0 = time.perf_counter()
            auto.replace_all(test_sentence)
            latencies_ms.append((time.perf_counter() - t0) * 1000.0)

        latencies_ms.sort()
        p50 = statistics.median(latencies_ms)
        p95 = latencies_ms[int(len(latencies_ms) * 0.95)]
        p99 = latencies_ms[int(len(latencies_ms) * 0.99)]
        mean = statistics.mean(latencies_ms)
        max_lat = max(latencies_ms)

        sla_pass = (mean <= 0.5 and p95 <= 0.5)
        target_pass = (mean <= 0.15)

        print(f"  [AC-G1 Official Benchmark: 5,000 Terms vs 100-char Text]")
        print(f"    - Mean Latency:   {mean:.4f} ms  (Target <= 0.15ms, SLA <= 0.5ms)")
        print(f"    - p50 (Median):   {p50:.4f} ms")
        print(f"    - p95 Latency:   {p95:.4f} ms")
        print(f"    - p99 Latency:   {p99:.4f} ms")
        print(f"    - Max Latency:   {max_lat:.4f} ms")
        print(f"    - Verdict:       {'PASS' if sla_pass else 'FAIL'} (Exceeds SLA: {not sla_pass})")

        # 2. Scaling with Dictionary Size (100 to 20,000 terms)
        scaling_results = {}
        for dict_size in [100, 1000, 5000, 10000, 20000]:
            a_scale = AhoCorasickAutomaton()
            for i in range(dict_size):
                a_scale.add_word(f"术语_{i}", f"Term_{i}")
            a_scale.add_word("落拉", "LoRA")
            a_scale.build()

            t_samples = []
            for _ in range(200):
                t0 = time.perf_counter()
                a_scale.replace_all(test_sentence)
                t_samples.append((time.perf_counter() - t0) * 1000.0)
            avg_scale_ms = statistics.mean(t_samples)
            scaling_results[dict_size] = round(avg_scale_ms, 4)
            print(f"    * Dict Size {dict_size:5d}: {avg_scale_ms:.4f} ms")

        # 3. Scaling with Text Length (100 to 100,000 chars)
        text_scaling = {}
        base_chunk = "在深度学习架构中落拉与反向传播及注意力机制被广泛应用。"
        for text_len in [100, 1000, 5000, 10000, 50000]:
            long_text = (base_chunk * ((text_len // len(base_chunk)) + 1))[:text_len]
            t_samples = []
            for _ in range(50):
                t0 = time.perf_counter()
                auto.replace_all(long_text)
                t_samples.append((time.perf_counter() - t0) * 1000.0)
            avg_text_ms = statistics.mean(t_samples)
            text_scaling[text_len] = round(avg_text_ms, 4)
            print(f"    * Text Length {text_len:6d} chars: {avg_text_ms:.4f} ms (Throughput: {text_len / avg_text_ms * 1000:,.0f} chars/sec)")

        res = {
            "mean_ms": mean,
            "p50_ms": p50,
            "p95_ms": p95,
            "p99_ms": p99,
            "max_ms": max_lat,
            "sla_pass": sla_pass,
            "target_pass": target_pass,
            "dict_scaling": scaling_results,
            "text_scaling": text_scaling,
        }
        self.results["dim_b"] = res
        return res

    # --------------------------------------------------------------------------
    # Dimension C: AC-G4 Dynamic Reload Latency & Scale
    # --------------------------------------------------------------------------
    def test_dim_c_ac_g4_dynamic_reload(self) -> Dict[str, Any]:
        print("\n" + "="*70)
        print(" [DIMENSION C] AC-G4 Dynamic Hot-Reload SLA Benchmark")
        print("="*70)

        reload_results = []
        # Test reload times across different dictionary sizes
        sizes = [10, 50, 100, 500, 1000, 2000, 5000]
        for sz in sizes:
            payload = {
                "_version": "1.0",
                "asr_fixes": {f"错别音_{i}": f"正确词_{i}" for i in range(sz // 3)},
                "terms_zh_to_en": {f"中文术语_{i}": f"EnglishTerm_{i}" for i in range(sz // 3)},
                "terms_en_to_zh": {f"EngTerm_{i}": f"中文映射_{i}" for i in range(sz // 3)},
            }
            times = []
            for _ in range(10):
                t0 = time.perf_counter()
                resp = self.client.post("/api/glossary", json_data=payload)
                t_dur = (time.perf_counter() - t0) * 1000.0
                assert resp.status_code == 200
                times.append(t_dur)

            mean_reload_ms = statistics.mean(times)
            p95_reload_ms = sorted(times)[int(len(times) * 0.95)]
            is_pass = mean_reload_ms <= 5.0
            reload_results.append({
                "terms_count": sz,
                "mean_ms": round(mean_reload_ms, 3),
                "p95_ms": round(p95_reload_ms, 3),
                "pass_5ms_sla": is_pass,
            })
            print(f"  * Reload {sz:5d} terms: Mean {mean_reload_ms:.3f} ms | p95 {p95_reload_ms:.3f} ms | SLA <= 5ms: {'PASS' if is_pass else 'EXCEEDED'}")

        self.restore_glossary()
        self.results["dim_c"] = reload_results
        return {"reload_benchmarks": reload_results}

    # --------------------------------------------------------------------------
    # Dimension D: Concurrency, Thread Safety, and Race Conditions
    # --------------------------------------------------------------------------
    def test_dim_d_concurrency_and_race_conditions(self) -> Dict[str, Any]:
        print("\n" + "="*70)
        print(" [DIMENSION D] High-Concurrency Race Condition & Deadlock Stress")
        print("="*70)

        num_readers = 16
        num_writers = 4
        iterations_per_reader = 500
        iterations_per_writer = 25

        errors = []
        read_successes = [0] * num_readers
        write_successes = [0] * num_writers
        stop_event = threading.Event()

        # Shared manager instance
        mgr = self.mgr

        def reader_worker(worker_id: int):
            test_sentences = [
                ("在测试落拉微调算法中", "Testing LoRA fine tuning"),
                ("关于反向穿破和库伯内特斯", "Regarding Backpropagation and Kubernetes"),
                ("由于单抗与百炼平台算力", "Due to mAb and DashScope compute"),
                ("提示词工程与注意力机制应用", "Prompt Engineering and Attention Mechanism"),
            ]
            try:
                for it in range(iterations_per_reader):
                    if stop_event.is_set():
                        break
                    src, tgt = test_sentences[it % len(test_sentences)]
                    channel = "en" if it % 2 == 0 else "zh"
                    f_src, f_tgt = mgr.apply_fixes(src, tgt, channel=channel)
                    if not isinstance(f_src, str) or not isinstance(f_tgt, str):
                        errors.append(f"Invalid return type from apply_fixes: {type(f_src)}")
                    read_successes[worker_id] += 1
                    # Tiny sleep to induce context switches
                    if it % 50 == 0:
                        time.sleep(0.0001)
            except Exception as e:
                errors.append(f"Reader {worker_id} crashed: {e}")

        def writer_worker(worker_id: int):
            try:
                for it in range(iterations_per_writer):
                    if stop_event.is_set():
                        break
                    patch = {
                        "asr_fixes": {f"动态错音_{worker_id}_{it}": f"动态校正_{worker_id}_{it}"},
                        "terms_zh_to_en": {f"动态术语_{worker_id}_{it}": f"DynamicTerm_{worker_id}_{it}"},
                    }
                    res = mgr.reload(new_data=patch, persist=False)
                    if res.get("status") != "ok":
                        errors.append(f"Writer {worker_id} reload failed: {res}")
                    write_successes[worker_id] += 1
                    time.sleep(0.002)
            except Exception as e:
                errors.append(f"Writer {worker_id} crashed: {e}")

        threads = []
        t0 = time.perf_counter()
        for i in range(num_readers):
            t = threading.Thread(target=reader_worker, args=(i,))
            threads.append(t)
        for i in range(num_writers):
            t = threading.Thread(target=writer_worker, args=(i,))
            threads.append(t)

        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10.0)

        total_elapsed = time.perf_counter() - t0
        alive = [t for t in threads if t.is_alive()]
        if alive:
            stop_event.set()
            errors.append(f"Deadlock detected! {len(alive)} threads still hung after 10s timeout.")

        total_reads = sum(read_successes)
        total_writes = sum(write_successes)
        concurrency_pass = (len(errors) == 0 and len(alive) == 0 and total_reads == num_readers * iterations_per_reader)

        print(f"  * Readers: {num_readers} threads x {iterations_per_reader} = {total_reads} reads completed")
        print(f"  * Writers: {num_writers} threads x {iterations_per_writer} = {total_writes} reloads completed")
        print(f"  * Elapsed Time: {total_elapsed:.3f} s (Total throughput: {total_reads / total_elapsed:,.0f} reads/s)")
        print(f"  * Deadlocks: {len(alive)}")
        print(f"  * Errors Caught: {len(errors)}")
        print(f"  * Verdict: {'PASS' if concurrency_pass else 'FAIL'}")

        self.restore_glossary()
        res = {
            "readers": total_reads,
            "writes": total_writes,
            "elapsed_s": total_elapsed,
            "deadlocks": len(alive),
            "errors": errors,
            "pass": concurrency_pass,
        }
        self.results["dim_d"] = res
        return res

    # --------------------------------------------------------------------------
    # Dimension E: Malformed, Corrupted, and Boundary Inputs
    # --------------------------------------------------------------------------
    def test_dim_e_malformed_and_boundary_inputs(self) -> Dict[str, Any]:
        print("\n" + "="*70)
        print(" [DIMENSION E] Malformed Payloads & Boundary Defense")
        print("="*70)

        tests = []

        # 1. Non-dict payloads to reload
        res1 = self.mgr.reload(new_data=None, persist=False)
        t1_pass = (res1.get("status") == "ok")
        tests.append({"case": "None payload", "pass": t1_pass})

        # 2. Corrupted raw body via HTTP API
        resp2 = self.client.post("/api/glossary", body_bytes=b"\xff\xfe\x00\x00BAD_UTF32")
        t2_pass = (resp2.status_code == 200 and resp2.json().get("status") == "ok")
        tests.append({"case": "Corrupted non-UTF8 bytes HTTP POST", "pass": t2_pass})

        # 3. Payload with non-string values
        weird_payload = {
            "asr_fixes": {"bad_int": 12345, "bad_list": ["a", "b"], "bad_none": None},
            "terms_zh_to_en": {123: "valid_val", "valid_key": {"nested": "dict"}},
        }
        try:
            res3 = self.mgr.reload(new_data=weird_payload, persist=False)
            t3_reload_ok = (res3.get("status") == "ok")
            out_src, out_tgt = self.mgr.apply_fixes("测试bad_int和123", "Target text", channel="en")
            t3_apply_pass = isinstance(out_src, str) and isinstance(out_tgt, str)
            t3_pass = t3_reload_ok and t3_apply_pass
            t3_err = None
        except Exception as e:
            t3_pass = False
            t3_err = f"{type(e).__name__}: {e}"
            self.restore_glossary()

        tests.append({
            "case": "Weird/non-string dictionary values",
            "pass": t3_pass,
            "error": t3_err,
        })

        # 4. Empty string keys and replacements
        empty_key_payload = {
            "asr_fixes": {"": "empty_val", "   ": "whitespace_val"},
            "terms_zh_to_en": {"target_empty": ""},
        }
        res4 = self.mgr.reload(new_data=empty_key_payload, persist=False)
        out_e = self.mgr.apply_asr_fixes("Normal text without empty matches")
        t4_pass = (res4.get("status") == "ok" and out_e == "Normal text without empty matches")
        tests.append({"case": "Empty string keys and replacements", "pass": t4_pass})

        # 5. Very long keys (e.g. 5,000 char pattern)
        giant_key = "长" * 5000
        res5 = self.mgr.reload(new_data={"terms_zh_to_en": {giant_key: "GIANT"}}, persist=False)
        out_g = self.mgr.apply_fixes("短文本", "短目标", channel="en")
        t5_pass = (res5.get("status") == "ok" and out_g[0] == "短文本")
        tests.append({"case": "Giant 5,000-character key", "pass": t5_pass})

        all_e_pass = all(t["pass"] for t in tests)
        for t in tests:
            print(f"  * Case '{t['case']}': {'PASS' if t['pass'] else 'FAIL'}")
        print(f"  * Overall Dimension E: {'PASS' if all_e_pass else 'FAIL'}")

        self.restore_glossary()
        self.results["dim_e"] = {"tests": tests, "all_pass": all_e_pass}
        return self.results["dim_e"]

    # --------------------------------------------------------------------------
    # Dimension F: WebSocket Streaming & Circuit Breaker Under Load
    # --------------------------------------------------------------------------
    def test_dim_f_websocket_streaming_and_circuit_breaker(self) -> Dict[str, Any]:
        print("\n" + "="*70)
        print(" [DIMENSION F] Concurrent WebSocket Streaming & Broadcast Circuit-Breaker")
        print("="*70)

        class MockWSClient:
            def __init__(self, slow: bool = False, delay: float = 0.0):
                self.slow = slow
                self.delay = delay
                self.received = []
                self.closed = False

            async def send_text(self, data: str):
                if self.slow:
                    await asyncio.sleep(self.delay)
                self.received.append(data)

            async def close(self, code: int = 1000):
                self.closed = True

        async def _run_stream_test():
            fast_clients = [MockWSClient(slow=False) for _ in range(30)]
            # 2 slow clients that exceed the 0.25s broadcast timeout
            slow_clients = [MockWSClient(slow=True, delay=0.5) for _ in range(2)]

            server.connected_clients["en"].clear()
            for c in fast_clients:
                server.connected_clients["en"].add(c)
            for c in slow_clients:
                server.connected_clients["en"].add(c)

            # Trigger 20 broadcast dispatches in rapid succession
            t0 = time.perf_counter()
            for i in range(20):
                server.channel_en.simulate_event(
                    source=f"测试落拉演讲第_{i}句",
                    target=f"LoRA keynote turn {i}",
                    is_final=True,
                    sentence_id=i + 1
                )
                await asyncio.sleep(0.005)

            # Allow loop to finish pending broadcasts
            await asyncio.sleep(0.6)
            total_time = time.perf_counter() - t0

            # Verify fast clients received all 20 messages
            fast_ok = all(len(c.received) == 20 for c in fast_clients)
            # Verify slow clients were evicted by circuit breaker
            evicted = [c for c in slow_clients if c not in server.connected_clients["en"]]
            circuit_breaker_ok = len(evicted) > 0

            return {
                "fast_ok": fast_ok,
                "fast_count": len(fast_clients),
                "messages_per_fast": [len(c.received) for c in fast_clients[:5]],
                "slow_evicted": len(evicted),
                "total_time_s": total_time,
                "circuit_breaker_pass": circuit_breaker_ok and fast_ok,
            }

        loop = asyncio.new_event_loop()
        server.main_loop = loop
        try:
            asyncio.set_event_loop(loop)
            f_res = loop.run_until_complete(_run_stream_test())
        finally:
            loop.close()
            server.main_loop = None
            asyncio.set_event_loop(None)
            server.connected_clients["en"].clear()

        cb_pass = f_res.get("circuit_breaker_pass", False)
        print(f"  * Fast Clients (30): Received 20/20 events each -> {'PASS' if f_res['fast_ok'] else 'FAIL'}")
        print(f"  * Slow Clients Eviction: {f_res['slow_evicted']}/2 slow clients evicted via 0.25s circuit-breaker")
        print(f"  * Total Broadcast Time: {f_res['total_time_s']:.3f} s")
        print(f"  * Overall Dimension F: {'PASS' if cb_pass else 'FAIL'}")

        self.results["dim_f"] = f_res
        return f_res

    def run_all(self):
        t0 = time.perf_counter()
        print("\n" + "#"*70)
        print(" HARRY TRANSLATE EMPIRICAL CHALLENGER STRESS & BENCHMARK SUITE")
        print(" Author: challenger_v6_1 (Critic / Specialist)")
        print("#"*70)

        self.test_dim_a_aho_corasick_edge_cases()
        self.test_dim_b_ac_g1_latency_benchmark()
        self.test_dim_c_ac_g4_dynamic_reload()
        self.test_dim_d_concurrency_and_race_conditions()
        self.test_dim_e_malformed_and_boundary_inputs()
        self.test_dim_f_websocket_streaming_and_circuit_breaker()

        elapsed = time.perf_counter() - t0
        print("\n" + "#"*70)
        print(f" BENCHMARK & ADVERSARIAL STRESS COMPLETE in {elapsed:.3f}s")
        print("#"*70 + "\n")

        # Save results to scratch / temporary json for documentation
        report_path = os.path.join(PROJECT_ROOT, "tests", "challenger_stress_results.json")
        with open(report_path, "w", encoding="utf-8") as f:
            json.dump(self.results, f, indent=2, ensure_ascii=False)
        print(f"Detailed stress metrics saved to: {report_path}")


if __name__ == "__main__":
    harness = ChallengerHarness()
    harness.run_all()
