#!/usr/bin/env python3
"""
tests/verify_m4_v5.py - Verification Suite for Worker M4: ScreenPresentation & 50-Node Sliding Window (v5.0).

Asserts:
1. MAX_CARDS is strictly 50 in index.html (AC-14).
2. Sliding window eviction logic exists and activeNodeMap.delete unmaps evicted node IDs.
3. Node references are cached on card creation (_srcNode, _transNode) and text is updated via textContent.
4. textContent is used instead of innerText across index.html (0 instances of innerText).
5. Autoscroll is throttled via requestAnimationFrame (rafScrollPending).
6. Configuration drawer elements exist in DOM (#config-drawer, #drawer-api-key, #drawer-save-btn, etc.).
7. Auto-open drawer detection logic exists (?drawer=open and #drawer).
8. Physical routing isolation logic is intact (/, /en, /zh, /split).
9. Simulation: Appending 1,000 subtitle nodes in a DOM container strictly caps child count at <= 50.
"""

import os
import re
import sys
import unittest
from html.parser import HTMLParser

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)


class DOMIdCollector(HTMLParser):
    """Collects all element IDs and tag attributes from an HTML file."""
    def __init__(self):
        super().__init__()
        self.ids = set()
        self.elements = {}

    def handle_starttag(self, tag, attrs):
        attr_dict = dict(attrs)
        tag_id = attr_dict.get("id")
        if tag_id:
            self.ids.add(tag_id)
            self.elements[tag_id] = {"tag": tag, "attrs": attr_dict}


class SimulatedDOMElement:
    """Lightweight DOM Node mock for simulating sliding window buffer logic."""
    def __init__(self, tag_name="div", class_name=""):
        self.tagName = tag_name.upper()
        self.className = class_name
        self.children = []
        self.dataset = {}
        self.textContent = ""
        self.scrollTop = 0
        self.scrollHeight = 0
        self._srcNode = None
        self._transNode = None

    @property
    def firstElementChild(self):
        return self.children[0] if self.children else None

    def appendChild(self, child):
        self.children.append(child)
        self.scrollHeight += 40
        return child

    def removeChild(self, child):
        if child in self.children:
            self.children.remove(child)
            return child
        raise ValueError("Child not found in container")

    def querySelector(self, selector):
        # Emulate empty-placeholder check
        if selector == ".empty-placeholder":
            for c in self.children:
                if "empty-placeholder" in getattr(c, "className", ""):
                    return c
        return None


class SimulatedChannelStreamHandler:
    """
    Python reproduction of index.html ChannelStreamHandler.
    Used for simulating high-throughput streaming workloads.
    """
    def __init__(self, channel_name, container_element, max_cards=50):
        self.channel = channel_name
        self.container = container_element
        self.max_cards = max_cards
        self.activeCard = None
        self.currentSentenceId = None
        self.activeNodeMap = {}
        self.rafScrollPending = False

    def handleSubtitle(self, data):
        placeholder = self.container.querySelector(".empty-placeholder")
        if placeholder:
            self.container.removeChild(placeholder)

        # 1. New sentence lifecycle
        if data.get("id") != self.currentSentenceId or not self.activeCard:
            if self.activeCard:
                self.activeCard.className = self.activeCard.className.replace("current-active", "").strip()

            self.currentSentenceId = data.get("id")
            self.activeCard = SimulatedDOMElement("div", "sentence-card current-active")
            card_id = str(data.get("id") or ("sent_" + str(len(self.activeNodeMap))))
            self.activeCard.dataset["id"] = card_id

            src_div = SimulatedDOMElement("div", "source-text")
            trans_div = SimulatedDOMElement("div", "target-text")
            self.activeCard.appendChild(src_div)
            self.activeCard.appendChild(trans_div)
            self.activeCard._srcNode = src_div
            self.activeCard._transNode = trans_div

            self.container.appendChild(self.activeCard)
            self.activeNodeMap[card_id] = self.activeCard

            # Sliding window eviction (AC-14)
            while len(self.container.children) > self.max_cards:
                oldest = self.container.firstElementChild
                if oldest and oldest.dataset and oldest.dataset.get("id"):
                    old_id = oldest.dataset["id"]
                    if old_id in self.activeNodeMap:
                        del self.activeNodeMap[old_id]
                self.container.removeChild(oldest)

        # 2. Direct textContent writes
        if data.get("source") is not None:
            self.activeCard._srcNode.textContent = data["source"]
        if data.get("target") is not None:
            self.activeCard._transNode.textContent = data["target"]

        # 3. Finalization
        if data.get("is_final"):
            self.activeCard.className = self.activeCard.className.replace("current-active", "").strip()
            self.activeCard = None

        # 4. RAF autoscroll
        if not self.rafScrollPending:
            self.rafScrollPending = True
            self.container.scrollTop = self.container.scrollHeight
            self.rafScrollPending = False


class TestScreenPresentationM4Verification(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html_path = os.path.join(PROJECT_ROOT, "index.html")
        with open(cls.html_path, "r", encoding="utf-8") as f:
            cls.html_content = f.read()

        cls.collector = DOMIdCollector()
        cls.collector.feed(cls.html_content)

    def test_01_max_cards_strictly_50(self):
        """AC-14: MAX_CARDS is strictly 50 in index.html."""
        match = re.search(r"const\s+MAX_CARDS\s*=\s*(\d+)\s*;", self.html_content)
        self.assertIsNotNone(match, "Could not find 'const MAX_CARDS = ...;' definition in index.html")
        max_cards_val = int(match.group(1))
        self.assertEqual(max_cards_val, 50,
            f"MAX_CARDS must be strictly 50 (AC-14), but found {max_cards_val}")
        print(f"  [PASS] MAX_CARDS strictly defined as {max_cards_val}")

    def test_02_sliding_window_eviction_and_map_deletion(self):
        """AC-14: Sliding window removes oldest card and deletes its key from activeNodeMap."""
        # Check while loop on container.children.length > MAX_CARDS
        self.assertIn("while (this.container.children.length > MAX_CARDS)", self.html_content,
            "Missing sliding window eviction loop: while (this.container.children.length > MAX_CARDS)")

        # Check activeNodeMap.delete
        self.assertIn("this.activeNodeMap.delete(oldest.dataset.id)", self.html_content,
            "Missing activeNodeMap.delete(oldest.dataset.id) on eviction")

        # Check removeChild
        self.assertIn("this.container.removeChild(oldest)", self.html_content,
            "Missing this.container.removeChild(oldest) on eviction")
        print("  [PASS] Sliding window eviction loop and activeNodeMap.delete verified.")

    def test_03_direct_node_cache_and_text_content(self):
        """AC-14: Child nodes cached on creation (_srcNode, _transNode) and textContent used."""
        self.assertIn("this.activeCard._srcNode = srcDiv;", self.html_content,
            "Missing node caching for _srcNode")
        self.assertIn("this.activeCard._transNode = transDiv;", self.html_content,
            "Missing node caching for _transNode")
        self.assertIn("this.activeCard._srcNode.textContent = data.source;", self.html_content,
            "Missing textContent direct write for _srcNode")
        self.assertIn("this.activeCard._transNode.textContent = data.target;", self.html_content,
            "Missing textContent direct write for _transNode")
        print("  [PASS] Direct node caching and textContent direct-writes verified.")

    def test_04_zero_inner_text_occurrences(self):
        """AC-14: textContent is used exclusively; innerText is 100% eliminated from index.html."""
        matches = re.findall(r"\binnerText\b", self.html_content)
        self.assertEqual(len(matches), 0,
            f"Forbidden 'innerText' found {len(matches)} times in index.html; must use textContent exclusively.")
        self.assertIn("textContent", self.html_content, "index.html should use textContent")
        print("  [PASS] 0 occurrences of innerText; textContent used exclusively across index.html.")

    def test_05_raf_scroll_throttling(self):
        """AC-14: Autoscroll is throttled via requestAnimationFrame."""
        self.assertIn("rafScrollPending", self.html_content, "Missing rafScrollPending variable")
        self.assertIn("requestAnimationFrame", self.html_content, "Missing requestAnimationFrame throttle call")
        self.assertIn("this.container.scrollTop = this.container.scrollHeight;", self.html_content,
            "Missing scrollTop assignment inside RAF")
        print("  [PASS] requestAnimationFrame autoscroll throttling verified.")

    def test_06_configuration_drawer_dom_elements(self):
        """System configuration drawer contains all mandatory controls and IDs."""
        required_ids = [
            "config-drawer",            # Main drawer container
            "drawer-backdrop",          # Modal backdrop
            "drawer-close-btn",         # Close button
            "drawer-masked-key",        # Masked DashScope API key display
            "drawer-api-key",           # Password input for new key
            "btn-toggle-key",           # Password eye toggle button
            "drawer-device-a",          # Channel A Microphone selector
            "drawer-device-b",          # Channel B Loopback selector
            "drawer-loopback-badge",    # Channel B loopback autodetection badge
            "drawer-engine",            # Engine model selector
            "drawer-btn-unlock-hud",    # Remote click-through unlock button
            "drawer-btn-stealth-hud",   # Remote stealth toggle button
            "drawer-save-btn",          # Save configuration button
            "btn-open-drawer",          # Header button to trigger drawer
            "toast-notification",       # Toast notification element
        ]

        found_ids = self.collector.ids
        missing = [elem_id for elem_id in required_ids if elem_id not in found_ids]
        self.assertEqual(missing, [],
            f"Missing required drawer DOM elements in index.html: {missing}")

        # Check API key field note
        self.assertIn("留空保持当前 Key 不变", self.html_content,
            "Missing note '留空保持当前 Key 不变' in drawer")

        # Check Loopback badge texts
        self.assertIn("绝不盗用麦克风", self.html_content,
            "Missing safe idle statement '绝不盗用麦克风' in loopback selector")

        # Check engine options
        self.assertIn("gummy-realtime-v1", self.html_content, "Missing gummy-realtime-v1 engine option")
        self.assertIn("qwen3.8-livetranslate-flash-realtime", self.html_content,
            "Missing qwen3.8-livetranslate-flash-realtime engine option")
        print(f"  [PASS] All {len(required_ids)} configuration drawer DOM elements present.")

    def test_07_auto_open_drawer_detection_logic(self):
        """Configuration drawer automatically opens when URL has ?drawer=open or #drawer."""
        self.assertIn('params.get("drawer") === "open"', self.html_content,
            "Missing ?drawer=open parameter check")
        self.assertIn('window.location.hash === "#drawer"', self.html_content,
            "Missing #drawer hash check")
        self.assertIn("openConfigDrawer()", self.html_content,
            "Missing openConfigDrawer() function call on drawer parameter trigger")
        print("  [PASS] Auto-open drawer detection logic verified (?drawer=open / #drawer).")

    def test_08_routing_isolation_intact(self):
        """AC-13: Physical presentation routes /, /en, /zh, /split are preserved."""
        self.assertIn('pathname === "/en"', self.html_content)
        self.assertIn('pathname === "/zh"', self.html_content)
        self.assertIn('pathname === "/split"', self.html_content)
        self.assertIn('mode = "dashboard"', self.html_content)
        self.assertIn('new ChannelStreamHandler("en"', self.html_content)
        self.assertIn('new ChannelStreamHandler("zh"', self.html_content)
        print("  [PASS] Physical routing isolation logic verified.")

    def test_09_thousand_sentences_dom_capping_simulation(self):
        """Simulate 1,000 streamed sentences; assert container child count <= 50 and activeNodeMap size <= 50."""
        container = SimulatedDOMElement("div", "subtitle-panel")
        placeholder = SimulatedDOMElement("div", "empty-placeholder")
        container.appendChild(placeholder)

        handler = SimulatedChannelStreamHandler("en", container, max_cards=50)

        # Feed 1,000 distinct sentences with multiple streaming tokens each
        for i in range(1, 1001):
            sent_id = f"sent_{i:04d}"
            # Word 1
            handler.handleSubtitle({
                "id": sent_id,
                "source": f"这是第 {i} 句测试发言。",
                "target": f"This is test sentence number {i}",
                "is_final": False,
            })
            # Word 2
            handler.handleSubtitle({
                "id": sent_id,
                "source": f"这是第 {i} 句测试发言，包含实时追加信息。",
                "target": f"This is test sentence number {i}, including streaming updates.",
                "is_final": False,
            })
            # Finalize
            handler.handleSubtitle({
                "id": sent_id,
                "source": f"这是第 {i} 句测试发言，包含实时追加信息，现已定稿。",
                "target": f"This is test sentence number {i}, including streaming updates, now finalized.",
                "is_final": True,
            })

            # Invariant check: children count must never exceed 50
            self.assertLessEqual(len(container.children), 50,
                f"Container exceeded 50 cards at sentence {i}: had {len(container.children)}")
            self.assertLessEqual(len(handler.activeNodeMap), 50,
                f"activeNodeMap exceeded 50 entries at sentence {i}: had {len(handler.activeNodeMap)}")

        self.assertEqual(len(container.children), 50,
            f"Expected exactly 50 cards remaining after 1000 sentences, got {len(container.children)}")
        self.assertEqual(len(handler.activeNodeMap), 50,
            f"Expected exactly 50 activeNodeMap entries after 1000 sentences, got {len(handler.activeNodeMap)}")

        # Verify the surviving 50 cards are sentences 951 to 1000
        oldest_surviving = container.children[0]
        newest_surviving = container.children[-1]
        self.assertEqual(oldest_surviving.dataset["id"], "sent_0951",
            f"Oldest card should be sent_0951, got {oldest_surviving.dataset['id']}")
        self.assertEqual(newest_surviving.dataset["id"], "sent_1000",
            f"Newest card should be sent_1000, got {newest_surviving.dataset['id']}")

        print(f"  [PASS] 1,000 sentence simulation verified: exactly 50 cards retained (sent_0951 ~ sent_1000).")


if __name__ == "__main__":
    unittest.main(verbosity=2)
