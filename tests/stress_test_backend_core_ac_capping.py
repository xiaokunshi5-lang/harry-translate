#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
tests/stress_test_backend_core_ac_capping.py
--------------------------------------------------------------------------------
Adversarial Stress-Test & Performance Benchmark Harness for Milestone 8:
- Backend Core & Pure-Python Aho-Corasick Automaton (18,000+ words mount, 1,000 sentences latency benchmark <= 0.15ms)
- Extreme Volume Smart Capping (up to 25,000 terms, strict <= 900 limit, strict P0 > P1 > P2 > P3 priority)
- Session Lifecycle Concurrency & Race Conditions (Streaming + Insert + Batch Import + Clear + Promote)
--------------------------------------------------------------------------------
"""

import os
import sys
import time
import json
import random
import string
import shutil
import tempfile
import threading
import statistics
import concurrent.futures
from typing import Dict, List, Tuple, Any, Optional

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from core.glossary_manager import (
    ACNode,
    AhoCorasickAutomaton,
    UnifiedAutomaton,
    GlossaryManager,
    get_glossary_manager,
)


class BackendCoreStressHarness:
    """Adversarial stress and verification harness for AC Automaton, Smart Capping, and Session Lifecycle."""

    def __init__(self):
        self.results: Dict[str, Any] = {}
        self.temp_dir = tempfile.mkdtemp(prefix="harry_stress_")
        self.temp_glossary_path = os.path.join(self.temp_dir, "glossary_stress.json")
        self.bank_dir = os.path.join(PROJECT_ROOT, "glossary_bank")

        # Initialize base glossary file
        base_data = {
            "_version": "1.0",
            "description": "Stress testing temp dictionary",
            "asr_fixes": {},
            "terms_zh_to_en": {},
            "terms_en_to_zh": {},
            "_enabled_packs": [],
        }
        with open(self.temp_glossary_path, "w", encoding="utf-8") as f:
            json.dump(base_data, f, ensure_ascii=False, indent=2)

    def cleanup(self):
        """Clean up temporary test artifacts."""
        if os.path.exists(self.temp_dir):
            try:
                shutil.rmtree(self.temp_dir)
            except Exception:
                pass

    # =========================================================================
    # PART 1: AC Automaton Mounting 18,000+ Words & 1,000-Sentence Benchmark
    # =========================================================================
    def run_part1_ac_latency_benchmark(self) -> Dict[str, Any]:
        print("\n" + "="*75)
        print(" [PART 1] AC Automaton 18,000+ Words Mounting & 1,000 Sentence Latency")
        print("="*75)

        # 1. Load all bank packs to extract real-world words
        mgr = GlossaryManager(dict_path=self.temp_glossary_path, bank_dir=self.bank_dir)
        mgr.scan_and_load_bank()

        bank_packs = getattr(mgr, "_bank_packs", {})
        all_terms: Dict[str, str] = {}
        for pid, pack in bank_packs.items():
            for k, v in pack.get("asr_fixes", {}).items():
                all_terms[str(k)] = str(v)
            for k, v in pack.get("terms_zh_to_en", {}).items():
                all_terms[str(k)] = str(v)
            for k, v in pack.get("terms_en_to_zh", {}).items():
                all_terms[str(k)] = str(v)

        initial_count = len(all_terms)
        print(f"[*] Extracted {initial_count} terms from {len(bank_packs)} glossary_bank packs.")

        # If below 18,500, augment with synthetic realistic domain terms to reach 18,500+
        target_mount = 18500
        if initial_count < target_mount:
            needed = target_mount - initial_count
            print(f"[*] Augmenting {needed} synthetic terms to exceed 18,000-word target...")
            for i in range(needed):
                synthetic_key = f"术语标签_{i:05d}_专有特征"
                synthetic_val = f"TermLabel_{i:05d}_Feature"
                all_terms[synthetic_key] = synthetic_val

        total_mounted_words = len(all_terms)
        print(f"[*] Total words to mount into AC Automaton: {total_mounted_words}")

        # 2. Build AC Automaton and measure build time
        t_build_start = time.perf_counter()
        ac = AhoCorasickAutomaton()
        ac.load_words(all_terms)
        ac.build()
        t_build_ms = (time.perf_counter() - t_build_start) * 1000.0
        print(f"[*] AC Automaton built with {len(ac)} patterns in {t_build_ms:.2f} ms.")

        # 3. Generate 1,000 Diverse Adversarial Sentences
        print("[*] Generating 1,000 diverse and adversarial sentences...")
        sample_keys = list(all_terms.keys())
        sentences: List[Dict[str, Any]] = []

        # Category 1: Realistic conference sentences with 1-3 matching terms (400 sentences)
        for i in range(400):
            t1 = random.choice(sample_keys)
            t2 = random.choice(sample_keys)
            text = f"在今天的全员大会上，专家重点指出了{t1}对于系统稳定性的重要性，并结合{t2}提出了后续落地策略与实施路径。"
            sentences.append({"id": f"sent_c1_{i}", "category": "natural_domain", "text": text})

        # Category 2: Zero-match negative sentences (200 sentences)
        for i in range(200):
            # Characters chosen from random unicode ranges unlikely to match domain dictionary
            random_chars = "".join(random.choices("abcdefghijklmnopqrstuvwxyz0123456789 -_.,!?", k=60))
            text = f"Unrelated non matching streaming payload #{i}: {random_chars}"
            sentences.append({"id": f"sent_c2_{i}", "category": "zero_match_negative", "text": text})

        # Category 3: Pathological overlapping & prefix/suffix collisions (150 sentences)
        # Adding overlapping patterns to test BFS failure link traversals
        for i in range(150):
            t_base = random.choice(sample_keys)
            t_sub = t_base[:max(1, len(t_base)//2)] if len(t_base) > 2 else t_base
            text = f"深入研讨{t_base}及其分词子集{t_sub}与衍生架构{t_base}{t_sub}的高并发匹配效率。"
            sentences.append({"id": f"sent_c3_{i}", "category": "overlapping_prefix", "text": text})

        # Category 4: Dense match sentences with high term density (100 sentences)
        for i in range(100):
            terms_cluster = [random.choice(sample_keys) for _ in range(8)]
            text = "，".join(terms_cluster) + "。"
            sentences.append({"id": f"sent_c4_{i}", "category": "dense_match", "text": text})

        # Category 5: Super long sentences (200~500 chars) (100 sentences)
        for i in range(100):
            parts = [f"发言片段{k}阐述了{random.choice(sample_keys)}的实践价值" for k in range(8)]
            text = "，同时".join(parts) + "，以上为完整总结。"
            sentences.append({"id": f"sent_c5_{i}", "category": "super_long", "text": text})

        # Category 6: Boundary & extreme short/symbol sentences (50 sentences)
        boundary_samples = [
            "",
            "   ",
            "\t\n\r",
            "A",
            "测",
            "🚀🔥💡🎉✨",
            "1234567890!@#$%^&*()_+",
            "《》【】「」（）“”‘’",
            sample_keys[0],
            sample_keys[0] * 3,
            "落拉" * 20,
        ]
        for i in range(50):
            s = boundary_samples[i % len(boundary_samples)]
            sentences.append({"id": f"sent_c6_{i}", "category": "boundary_edge", "text": s})

        assert len(sentences) == 1000, f"Expected 1,000 sentences, got {len(sentences)}"

        # 4. Warm-up
        for s in sentences[:50]:
            _ = ac.replace_all(s["text"])

        # 5. Benchmark 1,000 sentences using time.perf_counter_ns
        print("[*] Executing high-precision latency benchmark across 1,000 sentences...")
        latencies_ms: List[float] = []
        replaced_counts = 0

        t_total_start = time.perf_counter()
        for s in sentences:
            txt = s["text"]
            t0 = time.perf_counter_ns()
            out = ac.replace_all(txt)
            t1 = time.perf_counter_ns()
            elapsed_ms = (t1 - t0) / 1_000_000.0
            latencies_ms.append(elapsed_ms)
            if out != txt:
                replaced_counts += 1
        t_total_s = time.perf_counter() - t_total_start

        avg_latency = statistics.mean(latencies_ms)
        median_latency = statistics.median(latencies_ms)
        p90_latency = sorted(latencies_ms)[int(len(latencies_ms) * 0.90)]
        p95_latency = sorted(latencies_ms)[int(len(latencies_ms) * 0.95)]
        p99_latency = sorted(latencies_ms)[int(len(latencies_ms) * 0.99)]
        max_latency = max(latencies_ms)
        min_latency = min(latencies_ms)

        sla_pass = avg_latency <= 0.15
        print(f"\n[*] Benchmark Results ({total_mounted_words} words mounted, 1,000 sentences):")
        print(f"    - Mean Latency:   {avg_latency:.4f} ms  (SLA <= 0.15ms: {'PASS' if sla_pass else 'FAIL'})")
        print(f"    - Median (P50):   {median_latency:.4f} ms")
        print(f"    - P90 Latency:    {p90_latency:.4f} ms")
        print(f"    - P95 Latency:    {p95_latency:.4f} ms")
        print(f"    - P99 Latency:    {p99_latency:.4f} ms")
        print(f"    - Max Latency:    {max_latency:.4f} ms")
        print(f"    - Min Latency:    {min_latency:.4f} ms")
        print(f"    - Total Time:     {t_total_s*1000.0:.2f} ms for 1,000 sentences")
        print(f"    - Throughput:     {len(sentences)/t_total_s:.1f} sentences/sec")
        print(f"    - Matches found:  {replaced_counts}/1000 sentences had replacements")

        # Also benchmark through GlossaryManager.apply_fixes with all packs enabled
        print("\n[*] Benchmarking full GlossaryManager.apply_fixes() with full bank mounted...")
        mgr_latencies_ms = []
        for s in sentences:
            txt = s["text"]
            t0 = time.perf_counter_ns()
            _ = mgr.apply_fixes(source_text=txt, target_text="Target translation sentence", channel="en")
            t1 = time.perf_counter_ns()
            mgr_latencies_ms.append((t1 - t0) / 1_000_000.0)

        mgr_avg = statistics.mean(mgr_latencies_ms)
        mgr_p95 = sorted(mgr_latencies_ms)[int(len(mgr_latencies_ms) * 0.95)]
        print(f"    - Full apply_fixes() Mean: {mgr_avg:.4f} ms | P95: {mgr_p95:.4f} ms")

        res = {
            "total_mounted_words": total_mounted_words,
            "sentence_count": len(sentences),
            "build_time_ms": round(t_build_ms, 3),
            "mean_latency_ms": round(avg_latency, 5),
            "median_latency_ms": round(median_latency, 5),
            "p90_latency_ms": round(p90_latency, 5),
            "p95_latency_ms": round(p95_latency, 5),
            "p99_latency_ms": round(p99_latency, 5),
            "max_latency_ms": round(max_latency, 5),
            "min_latency_ms": round(min_latency, 5),
            "total_time_ms": round(t_total_s * 1000.0, 2),
            "throughput_sentences_per_sec": round(len(sentences) / t_total_s, 1),
            "sla_pass": sla_pass,
            "mgr_apply_fixes_mean_ms": round(mgr_avg, 5),
            "mgr_apply_fixes_p95_ms": round(mgr_p95, 5),
        }
        self.results["part1_ac_latency"] = res
        return res

    # =========================================================================
    # PART 2: Extreme Term Volumes (up to 25,000 terms) & Smart Capping
    # =========================================================================
    def run_part2_smart_capping_and_priority(self) -> Dict[str, Any]:
        print("\n" + "="*75)
        print(" [PART 2] Extreme Term Volumes (Up to 25,000) & Smart Capping Priority")
        print("="*75)

        test_runs: Dict[str, Any] = {}

        # ---------------------------------------------------------------------
        # Scenario 2.1: P0 Overflow (P0=1,500, P1=3,500, P2=10,000, P3=10,000 = 25,000)
        # ---------------------------------------------------------------------
        print("\n[*] Scenario 2.1: P0 Overflow (P0: 1,500 > 900 safe cap, Total: 25,000)")
        mgr = GlossaryManager(dict_path=self.temp_glossary_path, bank_dir=self.bank_dir)
        mgr._bank_packs.clear()
        mgr.enabled_packs.clear()

        # Inject P0: 1,500 terms in _session_data
        for i in range(1500):
            mgr._session_data["terms_zh_to_en"][f"P0_临时词_{i:04d}"] = f"P0_Session_{i:04d}"

        # Inject P1: 3,500 terms in _data
        for i in range(3500):
            mgr._data["terms_zh_to_en"][f"P1_永久词_{i:04d}"] = f"P1_Permanent_{i:04d}"

        # Inject P2: 10,000 terms in high_frequency pack
        p2_pack = {
            "id": "p2_high_pack",
            "tier": "high_frequency",
            "priority": 2,
            "terms_zh_to_en": {f"P2_高频词_{i:05d}": f"P2_High_{i:05d}" for i in range(10000)},
        }
        mgr._bank_packs["p2_high_pack"] = p2_pack
        mgr.enabled_packs.add("p2_high_pack")

        # Inject P3: 10,000 terms in rare pack
        p3_pack = {
            "id": "p3_rare_pack",
            "tier": "rare",
            "priority": 3,
            "terms_zh_to_en": {f"P3_生僻词_{i:05d}": f"P3_Rare_{i:05d}" for i in range(10000)},
        }
        mgr._bank_packs["p3_rare_pack"] = p3_pack
        mgr.enabled_packs.add("p3_rare_pack")

        total_injected = (
            len(mgr._session_data["terms_zh_to_en"])
            + len(mgr._data["terms_zh_to_en"])
            + len(p2_pack["terms_zh_to_en"])
            + len(p3_pack["terms_zh_to_en"])
        )
        assert total_injected == 25000, f"Expected 25,000 terms, got {total_injected}"

        hw_21 = mgr.get_hotwords()
        capping_pass_21 = len(hw_21) == 900
        # When P0 has 1,500 terms, ALL 900 words MUST be from P0!
        p0_all_pass = all(w.startswith("P0_") for w in hw_21)
        p1_leaked = any(w.startswith("P1_") for w in hw_21)
        p2_leaked = any(w.startswith("P2_") for w in hw_21)
        p3_leaked = any(w.startswith("P3_") for w in hw_21)

        print(f"    - Total Injected: {total_injected} terms")
        print(f"    - Hotwords count: {len(hw_21)} (Expected strictly <= 900: {'PASS' if capping_pass_21 else 'FAIL'})")
        print(f"    - 100% P0 source: {'PASS' if p0_all_pass else 'FAIL'}")
        print(f"    - P1 leaked: {p1_leaked} | P2 leaked: {p2_leaked} | P3 leaked: {p3_leaked}")
        test_runs["scenario_2_1"] = {
            "injected": total_injected,
            "hotwords_count": len(hw_21),
            "cap_ok": capping_pass_21,
            "pure_p0": p0_all_pass,
            "leak_p1": p1_leaked,
            "leak_p2": p2_leaked,
            "leak_p3": p3_leaked,
        }

        # ---------------------------------------------------------------------
        # Scenario 2.2: P0 (300) + P1 (800) Overflow (P0: 300, P1: 800, P2: 12,000, P3: 11,900 = 25,000)
        # ---------------------------------------------------------------------
        print("\n[*] Scenario 2.2: P0 (300) + P1 (800) Overflow (Expected: 300 P0 + 600 P1, 0 P2/P3)")
        mgr = GlossaryManager(dict_path=self.temp_glossary_path, bank_dir=self.bank_dir)
        mgr._bank_packs.clear()
        mgr.enabled_packs.clear()

        for i in range(300):
            mgr._session_data["terms_zh_to_en"][f"P0_词_{i:04d}"] = f"P0_{i:04d}"
        for i in range(800):
            mgr._data["terms_zh_to_en"][f"P1_词_{i:04d}"] = f"P1_{i:04d}"
        p2_pack = {
            "id": "p2_pack", "tier": "high_frequency", "priority": 2,
            "terms_zh_to_en": {f"P2_词_{i:05d}": f"P2_{i:05d}" for i in range(12000)},
        }
        p3_pack = {
            "id": "p3_pack", "tier": "rare", "priority": 3,
            "terms_zh_to_en": {f"P3_词_{i:05d}": f"P3_{i:05d}" for i in range(11900)},
        }
        mgr._bank_packs["p2_pack"] = p2_pack
        mgr._bank_packs["p3_pack"] = p3_pack
        mgr.enabled_packs.add("p2_pack")
        mgr.enabled_packs.add("p3_pack")

        hw_22 = mgr.get_hotwords()
        p0_in_hw = [w for w in hw_22 if w.startswith("P0_")]
        p1_in_hw = [w for w in hw_22 if w.startswith("P1_")]
        p2_in_hw = [w for w in hw_22 if w.startswith("P2_")]
        p3_in_hw = [w for w in hw_22 if w.startswith("P3_")]

        p0_count_ok = len(p0_in_hw) == 300
        p1_count_ok = len(p1_in_hw) == 600
        p2_count_ok = len(p2_in_hw) == 0
        p3_count_ok = len(p3_in_hw) == 0
        total_ok_22 = len(hw_22) == 900

        print(f"    - Hotwords count: {len(hw_22)} (Expected 900: {'PASS' if total_ok_22 else 'FAIL'})")
        print(f"    - P0 count: {len(p0_in_hw)}/300 ({'PASS' if p0_count_ok else 'FAIL'})")
        print(f"    - P1 count: {len(p1_in_hw)}/600 ({'PASS' if p1_count_ok else 'FAIL'})")
        print(f"    - P2 count: {len(p2_in_hw)}/0   ({'PASS' if p2_count_ok else 'FAIL'})")
        print(f"    - P3 count: {len(p3_in_hw)}/0   ({'PASS' if p3_count_ok else 'FAIL'})")
        test_runs["scenario_2_2"] = {
            "hotwords_count": len(hw_22),
            "p0_count": len(p0_in_hw),
            "p1_count": len(p1_in_hw),
            "p2_count": len(p2_in_hw),
            "p3_count": len(p3_in_hw),
            "pass": total_ok_22 and p0_count_ok and p1_count_ok and p2_count_ok and p3_count_ok,
        }

        # ---------------------------------------------------------------------
        # Scenario 2.3: P0 (200) + P1 (300) + P2 Overflow (Expected: 200 P0 + 300 P1 + 400 P2, 0 P3)
        # ---------------------------------------------------------------------
        print("\n[*] Scenario 2.3: P0 (200) + P1 (300) + P2 Overflow (Expected: 200 P0 + 300 P1 + 400 P2, 0 P3)")
        mgr = GlossaryManager(dict_path=self.temp_glossary_path, bank_dir=self.bank_dir)
        mgr._bank_packs.clear()
        mgr.enabled_packs.clear()

        for i in range(200):
            mgr._session_data["terms_zh_to_en"][f"P0_词_{i:04d}"] = f"P0_{i:04d}"
        for i in range(300):
            mgr._data["terms_zh_to_en"][f"P1_词_{i:04d}"] = f"P1_{i:04d}"
        p2_pack = {
            "id": "p2_pack", "tier": "high_frequency", "priority": 2,
            "terms_zh_to_en": {f"P2_词_{i:05d}": f"P2_{i:05d}" for i in range(1500)},
        }
        p3_pack = {
            "id": "p3_pack", "tier": "rare", "priority": 3,
            "terms_zh_to_en": {f"P3_词_{i:05d}": f"P3_{i:05d}" for i in range(23000)},
        }
        mgr._bank_packs["p2_pack"] = p2_pack
        mgr._bank_packs["p3_pack"] = p3_pack
        mgr.enabled_packs.add("p2_pack")
        mgr.enabled_packs.add("p3_pack")

        hw_23 = mgr.get_hotwords()
        p0_in_hw = [w for w in hw_23 if w.startswith("P0_")]
        p1_in_hw = [w for w in hw_23 if w.startswith("P1_")]
        p2_in_hw = [w for w in hw_23 if w.startswith("P2_")]
        p3_in_hw = [w for w in hw_23 if w.startswith("P3_")]

        p0_ok_23 = len(p0_in_hw) == 200
        p1_ok_23 = len(p1_in_hw) == 300
        p2_ok_23 = len(p2_in_hw) == 400
        p3_ok_23 = len(p3_in_hw) == 0
        total_ok_23 = len(hw_23) == 900

        print(f"    - Hotwords count: {len(hw_23)} (Expected 900: {'PASS' if total_ok_23 else 'FAIL'})")
        print(f"    - P0: {len(p0_in_hw)}/200 ({'PASS' if p0_ok_23 else 'FAIL'})")
        print(f"    - P1: {len(p1_in_hw)}/300 ({'PASS' if p1_ok_23 else 'FAIL'})")
        print(f"    - P2: {len(p2_in_hw)}/400 ({'PASS' if p2_ok_23 else 'FAIL'})")
        print(f"    - P3: {len(p3_in_hw)}/0   ({'PASS' if p3_ok_23 else 'FAIL'})")
        test_runs["scenario_2_3"] = {
            "hotwords_count": len(hw_23),
            "p0_count": len(p0_in_hw),
            "p1_count": len(p1_in_hw),
            "p2_count": len(p2_in_hw),
            "p3_count": len(p3_in_hw),
            "pass": total_ok_23 and p0_ok_23 and p1_ok_23 and p2_ok_23 and p3_ok_23,
        }

        # ---------------------------------------------------------------------
        # Scenario 2.4: P3 Fills Remainder (100 P0 + 200 P1 + 300 P2 + 300 P3 = 900)
        # ---------------------------------------------------------------------
        print("\n[*] Scenario 2.4: P3 Fills Remainder (Expected: 100 P0 + 200 P1 + 300 P2 + 300 P3 = 900)")
        mgr = GlossaryManager(dict_path=self.temp_glossary_path, bank_dir=self.bank_dir)
        mgr._bank_packs.clear()
        mgr.enabled_packs.clear()

        for i in range(100):
            mgr._session_data["terms_zh_to_en"][f"P0_词_{i:04d}"] = f"P0_{i:04d}"
        for i in range(200):
            mgr._data["terms_zh_to_en"][f"P1_词_{i:04d}"] = f"P1_{i:04d}"
        p2_pack = {
            "id": "p2_pack", "tier": "high_frequency", "priority": 2,
            "terms_zh_to_en": {f"P2_词_{i:05d}": f"P2_{i:05d}" for i in range(300)},
        }
        p3_pack = {
            "id": "p3_pack", "tier": "rare", "priority": 3,
            "terms_zh_to_en": {f"P3_词_{i:05d}": f"P3_{i:05d}" for i in range(24400)},
        }
        mgr._bank_packs["p2_pack"] = p2_pack
        mgr._bank_packs["p3_pack"] = p3_pack
        mgr.enabled_packs.add("p2_pack")
        mgr.enabled_packs.add("p3_pack")

        hw_24 = mgr.get_hotwords()
        p0_in_hw = [w for w in hw_24 if w.startswith("P0_")]
        p1_in_hw = [w for w in hw_24 if w.startswith("P1_")]
        p2_in_hw = [w for w in hw_24 if w.startswith("P2_")]
        p3_in_hw = [w for w in hw_24 if w.startswith("P3_")]

        p0_ok_24 = len(p0_in_hw) == 100
        p1_ok_24 = len(p1_in_hw) == 200
        p2_ok_24 = len(p2_in_hw) == 300
        p3_ok_24 = len(p3_in_hw) == 300
        total_ok_24 = len(hw_24) == 900

        print(f"    - Hotwords count: {len(hw_24)} (Expected 900: {'PASS' if total_ok_24 else 'FAIL'})")
        print(f"    - P0: {len(p0_in_hw)}/100 ({'PASS' if p0_ok_24 else 'FAIL'})")
        print(f"    - P1: {len(p1_in_hw)}/200 ({'PASS' if p1_ok_24 else 'FAIL'})")
        print(f"    - P2: {len(p2_in_hw)}/300 ({'PASS' if p2_ok_24 else 'FAIL'})")
        print(f"    - P3: {len(p3_in_hw)}/300 ({'PASS' if p3_ok_24 else 'FAIL'})")
        test_runs["scenario_2_4"] = {
            "hotwords_count": len(hw_24),
            "p0_count": len(p0_in_hw),
            "p1_count": len(p1_in_hw),
            "p2_count": len(p2_in_hw),
            "p3_count": len(p3_in_hw),
            "pass": total_ok_24 and p0_ok_24 and p1_ok_24 and p2_ok_24 and p3_ok_24,
        }

        # ---------------------------------------------------------------------
        # Scenario 2.5: Cross-Tier Collision & Deduplication
        # ---------------------------------------------------------------------
        print("\n[*] Scenario 2.5: Cross-Tier Collision & Deduplication (Same words in P3, P2, P1, P0)")
        mgr = GlossaryManager(dict_path=self.temp_glossary_path, bank_dir=self.bank_dir)
        mgr._bank_packs.clear()
        mgr.enabled_packs.clear()

        # Ingest 500 collided words into all 4 tiers
        collided_keys = [f"重合共享词汇_{i:04d}" for i in range(500)]
        for k in collided_keys:
            mgr._session_data["terms_zh_to_en"][k] = "P0_Val"
            mgr._data["terms_zh_to_en"][k] = "P1_Val"

        p2_pack = {
            "id": "p2_pack", "tier": "high_frequency", "priority": 2,
            "terms_zh_to_en": {k: "P2_Val" for k in collided_keys},
        }
        p3_pack = {
            "id": "p3_pack", "tier": "rare", "priority": 3,
            "terms_zh_to_en": {k: "P3_Val" for k in collided_keys},
        }
        # Add 12,000 unique terms to P2 and P3
        for i in range(12000):
            p2_pack["terms_zh_to_en"][f"P2_独有_{i:05d}"] = "Val"
            p3_pack["terms_zh_to_en"][f"P3_独有_{i:05d}"] = "Val"

        mgr._bank_packs["p2_pack"] = p2_pack
        mgr._bank_packs["p3_pack"] = p3_pack
        mgr.enabled_packs.add("p2_pack")
        mgr.enabled_packs.add("p3_pack")

        hw_25 = mgr.get_hotwords()
        # Verify no duplicates in hw_25
        dedup_pass = len(hw_25) == len(set(hw_25))
        capping_pass_25 = len(hw_25) == 900
        # The first 500 terms MUST be the collided words from P0
        collided_at_p0 = all(hw_25[i] == collided_keys[i] for i in range(500))
        # The remaining 400 terms must be from P2 unique (next priority)
        remainder_p2 = all(hw_25[i].startswith("P2_独有_") for i in range(500, 900))

        print(f"    - Hotwords count: {len(hw_25)} <= 900 ({'PASS' if capping_pass_25 else 'FAIL'})")
        print(f"    - Deduplicated strictly: {'PASS' if dedup_pass else 'FAIL'}")
        print(f"    - Collided terms claimed by P0: {'PASS' if collided_at_p0 else 'FAIL'}")
        print(f"    - Remainder filled by P2: {'PASS' if remainder_p2 else 'FAIL'}")
        test_runs["scenario_2_5"] = {
            "hotwords_count": len(hw_25),
            "dedup_pass": dedup_pass,
            "collided_at_p0": collided_at_p0,
            "remainder_p2": remainder_p2,
            "pass": capping_pass_25 and dedup_pass and collided_at_p0 and remainder_p2,
        }

        # ---------------------------------------------------------------------
        # Scenario 2.6: Massive Duplicate Ingestion (25,000 Identical Terms)
        # ---------------------------------------------------------------------
        print("\n[*] Scenario 2.6: 25,000 Identical Terms Ingestion")
        mgr = GlossaryManager(dict_path=self.temp_glossary_path, bank_dir=self.bank_dir)
        mgr._bank_packs.clear()
        mgr.enabled_packs.clear()

        # In dict, keys are deduplicated, but values in asr_fixes can have 25,000 entries
        mgr._data["asr_fixes"] = {f"misspell_{i:05d}": "固定统一词汇" for i in range(25000)}
        hw_26 = mgr.get_hotwords()
        print(f"    - Returned hotwords: {hw_26}")
        pass_26 = len(hw_26) == 1 and hw_26[0] == "固定统一词汇"
        print(f"    - Hotwords count: {len(hw_26)} (Expected exactly 1: {'PASS' if pass_26 else 'FAIL'})")
        test_runs["scenario_2_6"] = {"count": len(hw_26), "pass": pass_26}

        # ---------------------------------------------------------------------
        # Scenario 2.7: Adversarial Dirty Data (Empty, Whitespace, None)
        # ---------------------------------------------------------------------
        print("\n[*] Scenario 2.7: Adversarial Dirty Data (Empty, Whitespace, None, Newlines)")
        mgr = GlossaryManager(dict_path=self.temp_glossary_path, bank_dir=self.bank_dir)
        mgr._bank_packs.clear()
        mgr.enabled_packs.clear()

        dirty_dict: Dict[str, Any] = {
            "": "",
            "   ": "   ",
            "\n\t": "\r\n",
            "NormalKey1": None,
            "NormalKey2": "   ",
            "有效词1": "ValidTarget1",
            "有效词2": "ValidTarget2",
        }
        mgr._data["terms_zh_to_en"] = dirty_dict
        mgr._data["asr_fixes"] = {"bad1": "", "bad2": "  ", "good_asr": "正常修复"}
        hw_27 = mgr.get_hotwords()
        print(f"    - Filtered hotwords: {hw_27}")
        pass_27 = all(w and w.strip() for w in hw_27) and len(hw_27) > 0
        print(f"    - 0 empty/whitespace words: {'PASS' if pass_27 else 'FAIL'}")
        test_runs["scenario_2_7"] = {"hotwords": hw_27, "pass": pass_27}

        # ---------------------------------------------------------------------
        # Scenario 2.8: Exact Boundary Values (0, 1, 899, 900, 901, 1000, 25000)
        # ---------------------------------------------------------------------
        print("\n[*] Scenario 2.8: Exact Boundary Thresholds (0, 1, 899, 900, 901, 1000, 25000)")
        boundaries = [0, 1, 899, 900, 901, 1000, 25000]
        boundary_results = {}
        for b in boundaries:
            mgr = GlossaryManager(dict_path=self.temp_glossary_path, bank_dir=self.bank_dir)
            mgr._bank_packs.clear()
            mgr.enabled_packs.clear()
            mgr._data["terms_zh_to_en"] = {f"Term_{i:05d}": f"Val_{i:05d}" for i in range(b)}
            hw = mgr.get_hotwords()
            expected = min(b, 900)
            ok = len(hw) == expected
            boundary_results[f"vol_{b}"] = {"got": len(hw), "expected": expected, "ok": ok}
            print(f"    - Volume {b:5d}: got {len(hw):3d} (expected {expected:3d}) -> {'PASS' if ok else 'FAIL'}")

        all_boundaries_ok = all(v["ok"] for v in boundary_results.values())
        test_runs["scenario_2_8"] = {"boundaries": boundary_results, "pass": all_boundaries_ok}

        # ---------------------------------------------------------------------
        # Scenario 2.9: Quota Status Under 25,000 Terms
        # ---------------------------------------------------------------------
        print("\n[*] Scenario 2.9: Quota Status API Validation Under 25,000 Terms")
        mgr = GlossaryManager(dict_path=self.temp_glossary_path, bank_dir=self.bank_dir)
        mgr._bank_packs.clear()
        mgr.enabled_packs.clear()
        mgr._data["terms_zh_to_en"] = {f"T_{i:05d}": f"V_{i:05d}" for i in range(25000)}
        quota = mgr.get_quota_status()
        quota_pass = (
            quota["cloud_quota_used"] == 900
            and quota["cloud_limit"] == 1000
            and quota["smart_capped"] is True
            and quota["health_level"] == "capped"
            and quota["safe_threshold"] == 900
        )
        print(f"    - Quota used: {quota['cloud_quota_used']}/1000 (Safe threshold: {quota['safe_threshold']})")
        print(f"    - Smart capped: {quota['smart_capped']} | Health: {quota['health_level']}")
        print(f"    - Overall Quota Pass: {'PASS' if quota_pass else 'FAIL'}")
        test_runs["scenario_2_9"] = {"quota": quota, "pass": quota_pass}

        all_scenarios_pass = all(run.get("pass", run.get("cap_ok", False)) for run in test_runs.values())
        self.results["part2_smart_capping"] = {
            "all_pass": all_scenarios_pass,
            "scenarios": test_runs,
        }
        return self.results["part2_smart_capping"]

    # =========================================================================
    # PART 3: Session Lifecycle Concurrency & Race Conditions
    # =========================================================================
    def run_part3_concurrency_stress(self) -> Dict[str, Any]:
        print("\n" + "="*75)
        print(" [PART 3] Session Lifecycle Concurrency & Race Condition Stress")
        print("="*75)

        mgr = GlossaryManager(dict_path=self.temp_glossary_path, bank_dir=self.bank_dir)
        mgr.scan_and_load_bank()

        stop_event = threading.Event()
        errors: List[Dict[str, Any]] = []

        stats = {
            "streaming_reads": 0,
            "temporary_inserts": 0,
            "batch_imports": 0,
            "clears": 0,
            "promotes": 0,
            "hotwords_queries": 0,
            "quota_queries": 0,
        }
        stats_lock = threading.Lock()

        # Thread 1 & 2: Continuous streaming readers calling apply_fixes()
        def streamer_worker(worker_id: int):
            local_reads = 0
            while not stop_event.is_set():
                try:
                    src = f"这是并发测试句子_{local_reads}，嘉宾张伟和李娜正在发言。"
                    tgt = f"This is concurrent speech sentence {local_reads} by guests."
                    f_src, f_tgt = mgr.apply_fixes(source_text=src, target_text=tgt, channel="en")
                    assert isinstance(f_src, str) and isinstance(f_tgt, str)
                    local_reads += 1
                except Exception as e:
                    errors.append({"worker": f"streamer_{worker_id}", "error": type(e).__name__, "msg": str(e)})
                    break
            with stats_lock:
                stats["streaming_reads"] += local_reads

        # Thread 3 & 4: Temporary word insertion (add_term is_session=True)
        def insert_worker(worker_id: int):
            local_inserts = 0
            while not stop_event.is_set():
                try:
                    term_idx = local_inserts
                    src = f"临时嘉宾_{worker_id}_{term_idx}"
                    tgt = f"Guest_{worker_id}_{term_idx}"
                    ok = mgr.add_term(source=src, target=tgt, category="terms_zh_to_en", is_session=True)
                    assert ok is True
                    local_inserts += 1
                    time.sleep(0.001)  # tiny pause
                except Exception as e:
                    errors.append({"worker": f"insert_{worker_id}", "error": type(e).__name__, "msg": str(e)})
                    break
            with stats_lock:
                stats["temporary_inserts"] += local_inserts

        # Thread 5: Batch text import (import_batch_text is_session=True)
        def batch_import_worker():
            local_batches = 0
            while not stop_event.is_set():
                try:
                    batch_text = "\n".join([
                        f"嘉宾A_{local_batches}_{k} -> GuestA_{local_batches}_{k}"
                        for k in range(5)
                    ]) + "\n" + "\n".join([
                        f"错别字_{local_batches}_{k} = 正常词_{local_batches}_{k}"
                        for k in range(5)
                    ])
                    res = mgr.import_batch_text(text=batch_text, is_session=True)
                    assert res["status"] == "ok"
                    assert res["imported_count"] == 10
                    local_batches += 1
                    time.sleep(0.002)
                except Exception as e:
                    errors.append({"worker": "batch_importer", "error": type(e).__name__, "msg": str(e)})
                    break
            with stats_lock:
                stats["batch_imports"] += local_batches

        # Thread 6: clear_session() caller
        def clear_worker():
            local_clears = 0
            while not stop_event.is_set():
                try:
                    time.sleep(0.015)
                    cnt = mgr.clear_session()
                    assert isinstance(cnt, int)
                    local_clears += 1
                except Exception as e:
                    errors.append({"worker": "clear_session", "error": type(e).__name__, "msg": str(e)})
                    break
            with stats_lock:
                stats["clears"] += local_clears

        # Thread 7: promote_session() caller
        def promote_worker():
            local_promotes = 0
            while not stop_event.is_set():
                try:
                    time.sleep(0.025)
                    cnt = mgr.promote_session()
                    assert isinstance(cnt, int)
                    local_promotes += 1
                except Exception as e:
                    errors.append({"worker": "promote_session", "error": type(e).__name__, "msg": str(e)})
                    break
            with stats_lock:
                stats["promotes"] += local_promotes

        # Thread 8: get_hotwords() concurrent reader
        def hotwords_query_worker():
            local_queries = 0
            while not stop_event.is_set():
                try:
                    hw = mgr.get_hotwords()
                    assert isinstance(hw, list)
                    assert len(hw) <= 900
                    local_queries += 1
                    time.sleep(0.003)
                except Exception as e:
                    errors.append({"worker": "hotwords_query", "error": type(e).__name__, "msg": str(e)})
                    break
            with stats_lock:
                stats["hotwords_queries"] += local_queries

        # Thread 9: get_quota_status() concurrent reader
        def quota_query_worker():
            local_queries = 0
            while not stop_event.is_set():
                try:
                    q = mgr.get_quota_status()
                    assert isinstance(q, dict)
                    assert q["status"] == "ok"
                    local_queries += 1
                    time.sleep(0.003)
                except Exception as e:
                    errors.append({"worker": "quota_query", "error": type(e).__name__, "msg": str(e)})
                    break
            with stats_lock:
                stats["quota_queries"] += local_queries

        # Launch all 9 threads
        threads = [
            threading.Thread(target=streamer_worker, args=(1,), name="streamer_1"),
            threading.Thread(target=streamer_worker, args=(2,), name="streamer_2"),
            threading.Thread(target=insert_worker, args=(1,), name="insert_1"),
            threading.Thread(target=insert_worker, args=(2,), name="insert_2"),
            threading.Thread(target=batch_import_worker, name="batch_import"),
            threading.Thread(target=clear_worker, name="clear_session"),
            threading.Thread(target=promote_worker, name="promote_session"),
            threading.Thread(target=hotwords_query_worker, name="hotwords_query"),
            threading.Thread(target=quota_query_worker, name="quota_query"),
        ]

        print(f"[*] Starting {len(threads)} concurrent threads for 4.0 seconds stress workload...")
        t0 = time.perf_counter()
        for t in threads:
            t.daemon = True
            t.start()

        # Let the stress test run for 4.0 seconds
        time.sleep(4.0)
        stop_event.set()

        # Join all threads with 3.0s timeout to detect deadlocks
        deadlocks = []
        for t in threads:
            t.join(timeout=3.0)
            if t.is_alive():
                deadlocks.append(t.name)

        total_time_s = time.perf_counter() - t0
        print(f"[*] Concurrency run completed in {total_time_s:.2f}s.")
        print(f"    - Streaming Reads:       {stats['streaming_reads']} calls")
        print(f"    - Temporary Word Inserts:{stats['temporary_inserts']} calls")
        print(f"    - Batch Text Imports:    {stats['batch_imports']} calls")
        print(f"    - Clear Session Calls:   {stats['clears']} calls")
        print(f"    - Promote Session Calls: {stats['promotes']} calls")
        print(f"    - Hotwords Queries:      {stats['hotwords_queries']} calls")
        print(f"    - Quota Status Queries:  {stats['quota_queries']} calls")
        print(f"    - Deadlocked Threads:    {deadlocks} ({'PASS' if len(deadlocks)==0 else 'FAIL'})")
        print(f"    - Thread Errors/Crashes: {errors} ({'PASS' if len(errors)==0 else 'FAIL'})")

        # Post-concurrency sanity check: Verify manager remains completely intact and functional
        sanity_check_ok = True
        try:
            # 1. Clear session
            mgr.clear_session()
            assert len(mgr._session_data["asr_fixes"]) == 0
            assert len(mgr._session_data["terms_zh_to_en"]) == 0
            # 2. Add word
            mgr.add_term("测试词汇", "TestWord", is_session=True)
            res_str = mgr.apply_fixes("测试词汇在发言中")
            assert "TestWord" in res_str
            # 3. Promote word
            mgr.promote_session()
            assert len(mgr._session_data["terms_zh_to_en"]) == 0
            assert "测试词汇" in mgr._data["terms_zh_to_en"]
            # 4. Check hotwords
            hw = mgr.get_hotwords()
            assert len(hw) <= 900
        except Exception as ex:
            sanity_check_ok = False
            errors.append({"worker": "post_sanity", "error": type(ex).__name__, "msg": str(ex)})

        concurrency_pass = (len(deadlocks) == 0) and (len(errors) == 0) and sanity_check_ok
        print(f"    - Post-stress Sanity:    {'PASS' if sanity_check_ok else 'FAIL'}")
        print(f"    - Overall Concurrency:   {'PASS' if concurrency_pass else 'FAIL'}")

        res = {
            "concurrency_pass": concurrency_pass,
            "deadlocks": deadlocks,
            "errors": errors,
            "stats": stats,
            "duration_s": round(total_time_s, 2),
            "sanity_check_ok": sanity_check_ok,
        }
        self.results["part3_concurrency"] = res
        return res

    def run_all(self) -> Dict[str, Any]:
        t0 = time.perf_counter()
        print("\n" + "#"*75)
        print(" MILESTONE 8 EMPIRICAL CHALLENGER ADVERSARIAL STRESS SUITE")
        print(" Target: Backend Core, AC Automaton, and Smart Capping")
        print("#"*75)

        try:
            p1 = self.run_part1_ac_latency_benchmark()
            p2 = self.run_part2_smart_capping_and_priority()
            p3 = self.run_part3_concurrency_stress()

            total_elapsed = time.perf_counter() - t0
            all_passed = (
                p1.get("sla_pass", False)
                and p2.get("all_pass", False)
                and p3.get("concurrency_pass", False)
            )

            print("\n" + "#"*75)
            print(f" FINAL VERDICT: {'ALL PASS (100%)' if all_passed else 'FAILURES DETECTED'}")
            print(f" Total Duration: {total_elapsed:.2f} seconds")
            print("#"*75)

            final_report = {
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "verdict": "PASS" if all_passed else "FAIL",
                "total_duration_s": round(total_elapsed, 2),
                "part1": p1,
                "part2": p2,
                "part3": p3,
            }
            return final_report
        finally:
            self.cleanup()


if __name__ == "__main__":
    harness = BackendCoreStressHarness()
    results = harness.run_all()
    # Write json output to tests/challenger_stress_results.json
    out_file = os.path.join(PROJECT_ROOT, "tests", "challenger_stress_results.json")
    with open(out_file, "w", encoding="utf-8") as fp:
        json.dump(results, fp, indent=2, ensure_ascii=False)
    print(f"\n[+] Benchmark output written to: {out_file}")
    sys.exit(0 if results.get("verdict") == "PASS" else 1)
