"""
【复现与回归测试】FIX-204: 百炼实时同传热词封装合规、云端注入闭环与词库路径鲁棒性
覆盖需求: R1 / R2 / R3
验收标准: AC-1 ~ AC-5 及全量门禁 AC-6

- AC-1 (无顶层非法字段): live_update_session 配置中 100% 不含 session.corpus，嵌套于 session.translation.corpus.phrases。
- AC-2 (双模输入与 SLA): List[str] 与 Dict[str, str] 均能正确序列化且耗时严格 < 5.0ms。
- AC-3 (P0-P3 优先级与截断): get_corpus_phrases() 正确按优先级覆盖冲突词条，且返回词对数量 <= 900。
- AC-4 (Gummy 引擎注入闭环): GummyZeroCopyEngine 拥有 set_hotwords 方法且调用无异常。
- AC-5 (绝对路径寻址): 无论工作目录为何处，GlossaryManager() 均能正确加载 15 个词包，本地挂载总词数 >= 18,449。
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import MagicMock

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from core.glossary_manager import GlossaryManager, get_glossary_manager
from engines.qwen_translators import GummyZeroCopyEngine, QwenLiveTranslate38Engine
import server


class TestReproFix204CloudHotwordsInjection(unittest.TestCase):
    tier = 1
    feature_id = 6
    milestone = "M2"

    @classmethod
    def setUpClass(cls):
        cls.mgr = server.glossary_mgr

    # =========================================================================
    # AC-1: 协议规范化 (无顶层 session.corpus，嵌套于 translation.corpus.phrases)
    # =========================================================================
    def test_ac1_no_top_level_corpus_and_correct_nested_phrases(self):
        """AC-1: live_update_session 发送的 session.update 100% 不含 session.corpus，嵌套于 session.translation.corpus.phrases"""
        qwen = QwenLiveTranslate38Engine(target_lang="en", mock_mode=True)
        fake_ws = MagicMock()
        fake_sock = MagicMock()
        fake_sock.connected = True
        fake_ws.sock = fake_sock
        qwen.ws_client = fake_ws

        res = qwen.live_update_session(
            target_lang="en",
            hotwords={"大语言模型": "LLM", "反向传播": "Backpropagation"},
        )

        self.assertEqual(res["status"], "ok")
        config = qwen.last_sent_config
        self.assertIsNotNone(config, "last_sent_config must be recorded")

        # 1. 严格断言顶层无 session.corpus
        self.assertNotIn(
            "corpus",
            config["session"],
            "FATAL PROTOCOL VIOLATION: Top-level session.corpus must NOT exist in session.update config!",
        )

        # 2. 严格断言正确嵌套于 session.translation.corpus.phrases
        self.assertIn("translation", config["session"])
        self.assertIn("corpus", config["session"]["translation"])
        self.assertIn("phrases", config["session"]["translation"]["corpus"])
        phrases = config["session"]["translation"]["corpus"]["phrases"]
        self.assertEqual(phrases["大语言模型"], "LLM")
        self.assertEqual(phrases["反向传播"], "Backpropagation")

        # 3. 验证 WebSocket 发送的 JSON 字符串与配置完全一致
        fake_ws.send.assert_called_once()
        sent_str = fake_ws.send.call_args[0][0]
        sent_payload = json.loads(sent_str)
        self.assertNotIn("corpus", sent_payload["session"])
        self.assertEqual(
            sent_payload["session"]["translation"]["corpus"]["phrases"]["大语言模型"],
            "LLM",
        )

    # =========================================================================
    # AC-2: 双模输入兼容性与严格 < 5.0ms SLA 延迟
    # =========================================================================
    def test_ac2_dual_mode_input_and_sub_5ms_sla(self):
        """AC-2: 传入 List[str] 与 Dict[str, str] 均能正确序列化且耗时严格小于 5.0ms"""
        qwen = QwenLiveTranslate38Engine(target_lang="zh", mock_mode=True)

        # Mode A: Dict[str, str] 输入
        t0 = time.perf_counter()
        res_dict = qwen.live_update_session(
            target_lang="zh",
            hotwords={
                "Artificial Intelligence": "人工智能",
                "Transformer": "变换器架构",
                "Zero-Shot": "零样本",
            },
        )
        elapsed_dict_ms = (time.perf_counter() - t0) * 1000.0
        self.assertEqual(res_dict["status"], "ok")
        self.assertLess(
            elapsed_dict_ms,
            5.0,
            f"Dict mode SLA violated: took {elapsed_dict_ms:.3f}ms >= 5.0ms",
        )
        dict_phrases = qwen.last_sent_config["session"]["translation"]["corpus"]["phrases"]
        self.assertEqual(dict_phrases["Artificial Intelligence"], "人工智能")
        self.assertEqual(dict_phrases["Transformer"], "变换器架构")

        # Mode B: List[str] 输入 (包含纯词与 key:value / key->value 自动安全包装)
        t1 = time.perf_counter()
        res_list = qwen.live_update_session(
            target_lang="en",
            hotwords=[
                "大模型",
                "思维链:Chain of Thought",
                "低秩自适应->LoRA",
                "单抗",
            ],
        )
        elapsed_list_ms = (time.perf_counter() - t1) * 1000.0
        self.assertEqual(res_list["status"], "ok")
        self.assertLess(
            elapsed_list_ms,
            5.0,
            f"List mode SLA violated: took {elapsed_list_ms:.3f}ms >= 5.0ms",
        )
        list_phrases = qwen.last_sent_config["session"]["translation"]["corpus"]["phrases"]
        self.assertEqual(list_phrases["大模型"], "")
        self.assertEqual(list_phrases["思维链"], "Chain of Thought")
        self.assertEqual(list_phrases["低秩自适应"], "LoRA")
        self.assertEqual(list_phrases["单抗"], "")

        # 循环序列化验证稳定性
        for _ in range(10):
            t_iter = time.perf_counter()
            r = qwen.live_update_session(
                hotwords={"Term": "Translation"},
            )
            lat = (time.perf_counter() - t_iter) * 1000.0
            self.assertLess(lat, 5.0)

    # =========================================================================
    # AC-3: P0 > P1 > P2 > P3 优先级级联与 <= 900 词对截断
    # =========================================================================
    def test_ac3_priority_cascade_p0_to_p3_and_capping_limit(self):
        """AC-3: get_corpus_phrases() 正确按优先级覆盖冲突词条，且返回词对数量不超过 900"""
        mgr = self.mgr
        conflict_key = "测试级联冲突词_AlphaBeta"

        # 构造 4 层优先级冲突词条
        with mgr._lock:
            # P3 (Rare pack)
            mgr._bank_packs["09_party_specialized_rare"]["terms_zh_to_en"][conflict_key] = "P3_Rare_Val"
            # P2 (Emergency pack in bank)
            mgr._bank_packs["00_base_emergency"]["terms_zh_to_en"][conflict_key] = "P2_Emergency_Val"
            # P1 (User permanent)
            mgr._data["terms_zh_to_en"][conflict_key] = "P1_User_Val"
            # P0 (Session temporary VIP)
            mgr._session_data["terms_zh_to_en"][conflict_key] = "P0_Session_VIP_Val"

        try:
            # 1. 四层全在 -> P0 胜出
            phrases_0 = mgr.get_corpus_phrases(channel="en", target_lang="en", limit=10000)
            self.assertEqual(phrases_0[conflict_key], "P0_Session_VIP_Val", "P0 must strictly override P1, P2, P3")

            # 2. 移除 P0 -> P1 胜出
            with mgr._lock:
                del mgr._session_data["terms_zh_to_en"][conflict_key]
            phrases_1 = mgr.get_corpus_phrases(channel="en", target_lang="en", limit=10000)
            self.assertEqual(phrases_1[conflict_key], "P1_User_Val", "P1 must strictly override P2, P3")

            # 3. 移除 P1 -> P2 胜出
            with mgr._lock:
                del mgr._data["terms_zh_to_en"][conflict_key]
            phrases_2 = mgr.get_corpus_phrases(channel="en", target_lang="en", limit=10000)
            self.assertEqual(phrases_2[conflict_key], "P2_Emergency_Val", "P2 must strictly override P3")

            # 4. 移除 P2 -> P3 胜出
            with mgr._lock:
                del mgr._bank_packs["00_base_emergency"]["terms_zh_to_en"][conflict_key]
            phrases_3 = mgr.get_corpus_phrases(channel="en", target_lang="en", limit=10000)
            self.assertEqual(phrases_3[conflict_key], "P3_Rare_Val", "P3 must win when sole tier")

            # 5. 验证容量智能截断 <= 900
            default_phrases = mgr.get_corpus_phrases(channel="en", target_lang="en", limit=900)
            self.assertLessEqual(len(default_phrases), 900, "Capping must strictly not exceed 900")
            self.assertGreater(len(default_phrases), 100, "Should load active base terms")

            # 验证自定义微截断
            custom_phrases = mgr.get_corpus_phrases(channel="en", target_lang="en", limit=42)
            self.assertEqual(len(custom_phrases), 42, "Limit parameter must be strictly enforced")

            # 验证英译中方向
            phrases_zh = mgr.get_corpus_phrases(channel="zh", target_lang="zh", limit=900)
            self.assertLessEqual(len(phrases_zh), 900)
            self.assertGreater(len(phrases_zh), 0)

        finally:
            with mgr._lock:
                mgr._session_data["terms_zh_to_en"].pop(conflict_key, None)
                mgr._data["terms_zh_to_en"].pop(conflict_key, None)
                mgr._bank_packs["00_base_emergency"]["terms_zh_to_en"].pop(conflict_key, None)
                mgr._bank_packs["09_party_specialized_rare"]["terms_zh_to_en"].pop(conflict_key, None)

    # =========================================================================
    # AC-4: Gummy 引擎注入闭环与 ChannelSession 云端同步链路
    # =========================================================================
    def test_ac4_gummy_set_hotwords_and_cloud_injection(self):
        """AC-4: GummyZeroCopyEngine 拥有 set_hotwords 方法且调用无异常，ChannelSession 链路打通"""
        gummy = GummyZeroCopyEngine(channel_id="A", mock_mode=True)
        self.assertTrue(hasattr(gummy, "set_hotwords"), "GummyZeroCopyEngine must implement set_hotwords()")

        # 1. 独立调用 set_hotwords
        gummy.set_hotwords(
            hotwords=["全球国际会议", "低秩自适应"],
            corpus_phrases={"全球国际会议": "Global International Conference"},
        )
        self.assertEqual(gummy.hotwords, ["全球国际会议", "低秩自适应"])
        self.assertEqual(
            gummy.corpus_phrases,
            {"全球国际会议": "Global International Conference"},
        )

        # 2. 传入 dict 形式
        gummy.set_hotwords(hotwords={"单克隆抗体": "Monoclonal Antibody"})
        self.assertIn("单克隆抗体", gummy.hotwords)
        self.assertEqual(gummy.corpus_phrases["单克隆抗体"], "Monoclonal Antibody")

        # 3. 验证 server.ChannelSession.sync_hotwords 闭环打通
        ch = server.channel_en
        hotwords_returned = ch.sync_hotwords()
        self.assertIsInstance(hotwords_returned, list)
        self.assertGreater(len(hotwords_returned), 0)
        self.assertGreater(len(ch.gummy_engine.hotwords), 0)
        self.assertGreater(len(ch.gummy_engine.corpus_phrases), 0)
        self.assertIsNotNone(ch.qwen_engine.last_sent_config)
        self.assertNotIn("corpus", ch.qwen_engine.last_sent_config["session"])
        self.assertIn("phrases", ch.qwen_engine.last_sent_config["session"]["translation"]["corpus"])
        # 严格断言云端安全容量水位：绝对不可突破 900 词安全门禁（严防突破 1000 词导致 InvalidParameter 熔断）
        phrases_in_config = ch.qwen_engine.last_sent_config["session"]["translation"]["corpus"]["phrases"]
        self.assertLessEqual(
            len(phrases_in_config),
            900,
            f"FATAL CLOUD QUOTA DEFECT: Generated {len(phrases_in_config)} phrases, exceeding 900 safe threshold!",
        )
        self.assertLessEqual(
            len(ch.gummy_engine.corpus_phrases),
            900,
            f"Gummy corpus_phrases count {len(ch.gummy_engine.corpus_phrases)} exceeds 900!",
        )

    # =========================================================================
    # AC-5: 无论工作目录为何处，GlossaryManager 绝对路径寻址加载 15 个词包且总词数 >= 18,449
    # =========================================================================
    def test_ac5_windows_robustness_path_anchoring(self):
        """AC-5: 无论在何种非根工作目录下启动，GlossaryManager() 均能正确加载 15 个词包，本地挂载总词数 >= 18,449"""
        temp_dir = tempfile.mkdtemp(prefix="harry_test_cwd_")

        try:
            env = dict(os.environ)
            env["PYTHONPATH"] = PROJECT_ROOT
            subproc_code = (
                "import sys, os\n"
                "from core.glossary_manager import GlossaryManager, get_glossary_manager\n"
                "gm = GlossaryManager()\n"
                "bank_packs = getattr(gm, '_bank_packs', {})\n"
                "assert len(bank_packs) == 15, f'Expected 15 packs, got {len(bank_packs)}'\n"
                "total = sum(\n"
                "    len(p.get('asr_fixes', {}))\n"
                "    + len(p.get('terms_zh_to_en', {}))\n"
                "    + len(p.get('terms_en_to_zh', {}))\n"
                "    for p in bank_packs.values()\n"
                ")\n"
                "assert total >= 18449, f'Total bank terms {total} < 18449'\n"
                "sgm = get_glossary_manager()\n"
                "assert len(sgm._bank_packs) == 15\n"
                "print('OK')\n"
            )
            res = subprocess.run(
                [sys.executable, "-c", subproc_code],
                cwd=temp_dir,
                env=env,
                capture_output=True,
                text=True,
            )
            self.assertEqual(
                res.returncode,
                0,
                f"Subprocess GlossaryManager failed in external directory {temp_dir}: {res.stderr}",
            )
            self.assertIn("OK", res.stdout)

        finally:
            if os.path.exists(temp_dir):
                shutil.rmtree(temp_dir, ignore_errors=True)

    # =========================================================================
    # R3 前端加固测试: file:// 协议诊断与 localhost -> 127.0.0.1 自动回退
    # =========================================================================
    def test_r3_frontend_protocol_and_network_fallback(self):
        """R3 前端诊断: index.html 包含 file:// 告警横幅、127.0.0.1 回退机制与 0 innerText"""
        index_file = os.path.join(PROJECT_ROOT, "index.html")
        self.assertTrue(os.path.exists(index_file), "index.html must exist")

        with open(index_file, "r", encoding="utf-8") as f:
            html = f.read()

        # 1. 验证 file:// 告警横幅 DOM 与文本
        self.assertIn('id="protocol-warning-banner"', html, "index.html must contain #protocol-warning-banner")
        self.assertIn("file://", html, "index.html must explicitly diagnose file:// protocol")
        self.assertIn("127.0.0.1:8000", html, "index.html must provide http://127.0.0.1:8000 guide")

        # 2. 验证 localhost -> 127.0.0.1 智能回退机制
        self.assertIn("_localhostFallbackActive", html, "index.html must maintain localhost fallback state")
        self.assertIn("127.0.0.1", html, "index.html must fall back to 127.0.0.1")

        # 3. 严格断言全文件 0 innerText (AC-14 / 大厂出厂规范)
        self.assertNotIn("innerText", html, "Forbidden 'innerText' found in index.html; textContent must be used exclusively!")

    # =========================================================================
    # 对抗性测试 1: 恶劣与畸形输入防御 (空串、空格、None、无键分隔符、超长容量截断)
    # =========================================================================
    def test_adversarial_malformed_inputs_and_sanitization(self):
        """对抗测试: 恶劣入参下严格杜绝空键与 'None' 字符串翻译，并且超过 1000 词严格截断至 900 安全水位"""
        qwen = QwenLiveTranslate38Engine(target_lang="en", mock_mode=True)

        # 1. 传入各类恶劣畸形热词格式
        malformed_list = ["", "   ", None, ":", " : ", ":value", "key:", "->", "=", "ValidTerm:ValidTrans"]
        res = qwen.live_update_session(hotwords=malformed_list)
        self.assertEqual(res["status"], "ok")
        phrases = qwen.last_sent_config["session"]["translation"]["corpus"]["phrases"]

        self.assertNotIn("", phrases, "Empty string key must never exist in phrases!")
        self.assertNotIn(" ", phrases, "Whitespace key must never exist in phrases!")
        self.assertIn("ValidTerm", phrases)
        self.assertEqual(phrases["ValidTerm"], "ValidTrans")
        self.assertIn("key", phrases)
        self.assertEqual(phrases["key"], "")

        # 2. 传入包含 None 和空键的字典
        malformed_dict = {"": "bad", "  ": "bad2", "good_term": None, None: "none_val"}
        res2 = qwen.live_update_session(corpus_phrases=malformed_dict)
        phrases2 = qwen.last_sent_config["session"]["translation"]["corpus"]["phrases"]
        self.assertNotIn("", phrases2)
        self.assertIn("good_term", phrases2)
        self.assertNotEqual(phrases2["good_term"], "None", "None translation must not become string 'None'")
        self.assertEqual(phrases2["good_term"], "")

        # 3. 压测 1500 词超大词典，严格截断至 <= 900 安全水位且时延严格 < 5ms
        huge_dict = {f"huge_term_{i}": f"huge_trans_{i}" for i in range(1500)}
        t0 = time.perf_counter()
        res_huge = qwen.live_update_session(hotwords=huge_dict)
        lat = (time.perf_counter() - t0) * 1000.0
        self.assertLess(lat, 5.0, f"Huge dict live_update_session took {lat:.3f}ms >= 5.0ms SLA")
        phrases_huge = qwen.last_sent_config["session"]["translation"]["corpus"]["phrases"]
        self.assertEqual(len(phrases_huge), 900, "Phrases must be capped at exactly 900 safe threshold")

    # =========================================================================
    # 对抗性测试 2: 语言方向别名与语种动态切换自动重新同步
    # =========================================================================
    def test_adversarial_language_direction_aliases_and_channel_switch(self):
        """对抗测试: 语种全别名解析 (chinese/中文/english/英文) 与 ChannelSession.set_target_lang 双引擎自同步"""
        mgr = self.mgr

        # 1. 测试各语种与方向别名
        phrases_zh_alias = mgr.get_corpus_phrases(target_lang="chinese")
        self.assertGreater(len(phrases_zh_alias), 0)
        phrases_cn_alias = mgr.get_corpus_phrases(target_lang="中文")
        self.assertEqual(phrases_zh_alias.keys(), phrases_cn_alias.keys())

        phrases_en_alias = mgr.get_corpus_phrases(target_lang="english")
        self.assertGreater(len(phrases_en_alias), 0)
        phrases_eng_alias = mgr.get_corpus_phrases(target_lang="英文")
        self.assertEqual(phrases_en_alias.keys(), phrases_eng_alias.keys())

        # 2. 验证 ChannelSession.set_target_lang 切换时自动重新同步词库短语
        ch = server.channel_en
        ch.set_target_lang("zh")
        self.assertEqual(ch.target_lang, "zh")
        self.assertEqual(ch.gummy_engine.target_lang, "zh")
        self.assertLessEqual(len(ch.qwen_engine.last_sent_config["session"]["translation"]["corpus"]["phrases"]), 900)

        # 切回 en
        ch.set_target_lang("en")
        self.assertEqual(ch.target_lang, "en")
        self.assertEqual(ch.gummy_engine.target_lang, "en")

    def setUp(self):
        self.mgr = server.glossary_mgr

    # =========================================================================
    # 对抗性测试 3: 词库空路径与边界参数鲁棒性
    # =========================================================================
    def test_adversarial_empty_path_robustness(self):
        """对抗测试: GlossaryManager(dict_path='') 绝不将 dict_path 误绑定为根目录文件夹"""
        temp_dir = tempfile.mkdtemp(prefix="harry_test_empty_")
        try:
            env = dict(os.environ)
            env["PYTHONPATH"] = PROJECT_ROOT
            subproc_code = (
                "from core.glossary_manager import GlossaryManager\n"
                "gm = GlossaryManager(dict_path='', bank_dir='')\n"
                "assert gm.dict_path.endswith('glossary.json'), 'dict_path must fall back to glossary.json'\n"
                "assert gm.bank_dir.endswith('glossary_bank'), 'bank_dir must fall back to glossary_bank'\n"
                "assert len(gm._bank_packs) == 15\n"
                "print('OK')\n"
            )
            res = subprocess.run(
                [sys.executable, "-c", subproc_code],
                cwd=temp_dir,
                env=env,
                capture_output=True,
                text=True,
            )
            self.assertEqual(res.returncode, 0)
            self.assertIn("OK", res.stdout)
        finally:
            if os.path.exists(temp_dir):
                shutil.rmtree(temp_dir, ignore_errors=True)

    # =========================================================================
    # 对抗性测试 4: 900满额语料下显式热词永不被淘汰 (防止静默截断丢失)
    # =========================================================================
    def test_adversarial_live_update_preserves_explicit_hotwords_when_cached_corpus_full(self):
        """对抗测试: 当引擎已缓存 900 满额词库短语时，新调用 live_update_session 传入的显式热词必须优先保留，绝不可被静默截断丢弃"""
        qwen = QwenLiveTranslate38Engine(target_lang="en", mock_mode=True)
        # 预先填充 900 条词库短语
        qwen.corpus_phrases = {f"bank_term_{i}": f"trans_{i}" for i in range(900)}

        # 1. 显式传入 dict 形式热词
        res_dict = qwen.live_update_session(hotwords={"新显式术语_A": "NewTerm_A"})
        self.assertEqual(res_dict["status"], "ok")
        phrases = qwen.last_sent_config["session"]["translation"]["corpus"]["phrases"]
        self.assertIn("新显式术语_A", phrases, "Explicit hotwords in dict mode must be retained even if corpus is at 900 limit!")
        self.assertEqual(phrases["新显式术语_A"], "NewTerm_A")
        self.assertLessEqual(len(phrases), 900, "Total phrases must never exceed 900 safe quota!")

        # 2. 显式传入 list 形式热词 (包含翻译与纯词)
        res_list = qwen.live_update_session(hotwords=["显式词对:ExplicitTrans", "纯显式词条"])
        self.assertEqual(res_list["status"], "ok")
        phrases_list = qwen.last_sent_config["session"]["translation"]["corpus"]["phrases"]
        self.assertIn("显式词对", phrases_list, "Explicit phrase pair in list mode must be retained!")
        self.assertEqual(phrases_list["显式词对"], "ExplicitTrans")
        self.assertIn("纯显式词条", phrases_list, "Explicit bare term in list mode must be retained!")
        self.assertLessEqual(len(phrases_list), 900)

    # =========================================================================
    # 对抗性测试 5: Gummy 引擎同时传入 hotwords 与 corpus_phrases 映射无损合并
    # =========================================================================
    def test_adversarial_gummy_combined_hotwords_and_corpus_phrases(self):
        """对抗测试: GummyZeroCopyEngine.set_hotwords 同时传入 hotwords 词对与 corpus_phrases 词典时，两者映射无损合并"""
        gummy = GummyZeroCopyEngine(channel_id="A", mock_mode=True)
        gummy.set_hotwords(
            hotwords=["动态热词_G:DynamicTrans_G", "纯热词_G"],
            corpus_phrases={"专业银行词": "ProfessionalBankTrans"},
        )
        self.assertIn("动态热词_G", gummy.corpus_phrases, "hotwords phrase mapping must be merged into gummy.corpus_phrases!")
        self.assertEqual(gummy.corpus_phrases["动态热词_G"], "DynamicTrans_G")
        self.assertIn("专业银行词", gummy.corpus_phrases, "corpus_phrases must be preserved in gummy.corpus_phrases!")
        self.assertEqual(gummy.corpus_phrases["专业银行词"], "ProfessionalBankTrans")
        self.assertIn("动态热词_G", gummy.hotwords)
        self.assertIn("纯热词_G", gummy.hotwords)

    # =========================================================================
    # 对抗性测试 6: get_corpus_phrases 边界参数 limit=None 与 limit<=0 鲁棒性
    # =========================================================================
    def test_adversarial_get_corpus_phrases_none_and_zero_limit(self):
        """对抗测试: get_corpus_phrases 处理 limit=None 与 limit<=0 绝不崩溃"""
        mgr = self.mgr
        # limit=None 自动使用默认 900
        phrases_none = mgr.get_corpus_phrases(channel="en", target_lang="en", limit=None)
        self.assertIsInstance(phrases_none, dict)
        self.assertLessEqual(len(phrases_none), 900)
        self.assertGreater(len(phrases_none), 0)

        # limit=0 返回空字典
        phrases_zero = mgr.get_corpus_phrases(channel="en", target_lang="en", limit=0)
        self.assertEqual(phrases_zero, {})

        # limit < 0 返回空字典
        phrases_neg = mgr.get_corpus_phrases(channel="en", target_lang="en", limit=-5)
        self.assertEqual(phrases_neg, {})

    # =========================================================================
    # 对抗性测试 7: 900 满额词库下纯语音热词与 ChannelSession 显式注入无损保留
    # =========================================================================
    def test_adversarial_bare_hotwords_preserved_under_full_quota_and_sync_hotwords(self):
        """对抗测试: 当背景词库满 900 额度时，调用 channel_en.sync_hotwords 或 live_update_session 传入的纯语音热词绝不可被挤出"""
        # 1. 直接测试 Qwen 引擎在 900 满额词库下传入纯语音热词
        qwen = QwenLiveTranslate38Engine(target_lang="en", mock_mode=True)
        large_cp = {f"bank_k_{i}": f"bank_v_{i}" for i in range(900)}
        res = qwen.live_update_session(
            hotwords=["CustomSpeechTerm_R3", "AnotherSpeechTerm_R3"],
            corpus_phrases=large_cp,
        )
        self.assertEqual(res["status"], "ok")
        phrases = qwen.last_sent_config["session"]["translation"]["corpus"]["phrases"]
        self.assertIn("CustomSpeechTerm_R3", phrases, "Bare speech hotword must be preserved even under 900 full corpus!")
        self.assertIn("AnotherSpeechTerm_R3", phrases, "Second bare speech hotword must also be preserved!")
        self.assertEqual(phrases["CustomSpeechTerm_R3"], "")
        self.assertLessEqual(len(phrases), 900, "Phrases must strictly cap at 900 safe threshold")

        # 2. 测试 ChannelSession.sync_hotwords 注入纯语音热词闭环
        ch = server.channel_en
        ch.sync_hotwords(["InjectedSpeechTerm_R3"])
        sent_phrases = ch.qwen_engine.last_sent_config["session"]["translation"]["corpus"]["phrases"]
        self.assertIn(
            "InjectedSpeechTerm_R3",
            sent_phrases,
            "ChannelSession.sync_hotwords must preserve explicit bare speech hotword in Qwen payload!",
        )
        self.assertIn(
            "InjectedSpeechTerm_R3",
            ch.gummy_engine.hotwords,
            "ChannelSession.sync_hotwords must preserve explicit hotword in Gummy engine!",
        )
        self.assertLessEqual(len(sent_phrases), 900)

    # =========================================================================
    # 对抗性测试 8: Gummy 引擎在 900 满额词库下显式热词永不被切除
    # =========================================================================
    def test_adversarial_gummy_preserves_explicit_hotwords_under_full_quota(self):
        """对抗测试: GummyZeroCopyEngine.set_hotwords 在 corpus_phrases 达到 900 满额时，显式传入的热词映射必须被保留在 corpus_phrases 中"""
        gummy = GummyZeroCopyEngine(channel_id="A", mock_mode=True)
        large_cp = {f"bank_term_{i}": f"bank_trans_{i}" for i in range(900)}

        # 1. Dict 形式显式热词在 900 满额词库下必须保留
        gummy.set_hotwords(
            hotwords={"新专属词汇_R3": "NewExclusiveTrans_R3"},
            corpus_phrases=large_cp,
        )
        self.assertIn("新专属词汇_R3", gummy.corpus_phrases, "Explicit hotwords in dict mode must be retained in Gummy corpus_phrases under full quota!")
        self.assertEqual(gummy.corpus_phrases["新专属词汇_R3"], "NewExclusiveTrans_R3")
        self.assertLessEqual(len(gummy.corpus_phrases), 900)

        # 2. List 形式带翻译的显式热词在 900 满额词库下必须保留
        gummy.set_hotwords(
            hotwords=["专属词对_R3:ExclusivePairTrans_R3"],
            corpus_phrases=large_cp,
        )
        self.assertIn("专属词对_R3", gummy.corpus_phrases, "Explicit phrase pair in list mode must be retained in Gummy corpus_phrases under full quota!")
        self.assertEqual(gummy.corpus_phrases["专属词对_R3"], "ExclusivePairTrans_R3")
        self.assertLessEqual(len(gummy.corpus_phrases), 900)

    # =========================================================================
    # 对抗性测试 9: get_corpus_phrases 极限浮点边界 (inf, -inf, nan) 鲁棒性
    # =========================================================================
    def test_adversarial_get_corpus_phrases_inf_and_nan_limits(self):
        """对抗测试: get_corpus_phrases 处理 float('inf'), -float('inf') 与 float('nan') 绝不抛出 OverflowError"""
        mgr = self.mgr
        # 正无穷大安全回退至 <= 900
        res_inf = mgr.get_corpus_phrases(limit=float("inf"))
        self.assertIsInstance(res_inf, dict)
        self.assertLessEqual(len(res_inf), 900)
        self.assertGreater(len(res_inf), 0)

        # 负无穷大安全返回空字典
        res_neginf = mgr.get_corpus_phrases(limit=-float("inf"))
        self.assertEqual(res_neginf, {})

        # NaN 安全回退至 <= 900
        res_nan = mgr.get_corpus_phrases(limit=float("nan"))
        self.assertIsInstance(res_nan, dict)
        self.assertLessEqual(len(res_nan), 900)
        self.assertGreater(len(res_nan), 0)


if __name__ == "__main__":
    unittest.main()


