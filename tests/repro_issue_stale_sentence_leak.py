#!/usr/bin/env python3
"""
【复现与验证脚本 1】tests/repro_issue_stale_sentence_leak.py
验证病灶 3：快速连续发言时，第二句开始（大模型尚未返回第二句译文，target=""）时，
后端状态机或前端视口错误复用并广播第一句的旧译文（"很高兴见到你"），导致前端复读机式重复蹦出第一句。

覆盖全链路防御：
1. server.py: _on_engine_emit 跨句边界原子隔离
2. server.py: simulate_event 跨句模拟事件边界隔离
3. engines/qwen_translators.py: QwenLiveTranslate38Engine 跨句 ASR 阶段译文隔离
4. float_ui.html: 视觉锚点与第二句语音启动时旧译文清空及流式光标校验
"""
import os
import sys
import json
import time

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

try:
    import Cocoa
    import WebKit
    HAS_WEBKIT = True
except ImportError:
    HAS_WEBKIT = False


def test_server_emit_leak():
    from server import ChannelSession
    session = ChannelSession(name="zh", channel_id="ch_zh", source_lang="en", target_lang="zh", label="英译中")

    # 1. 第一句定稿派发
    session._on_engine_emit({
        "id": 1,
        "source": "Nice to meet you",
        "target": "很高兴见到你",
        "is_final": True
    })

    assert session.sentence_id == 1, f"Expected sentence_id 1, got {session.sentence_id}"
    assert session.target_text == "很高兴见到你", f"Expected target_text '很高兴见到你', got '{session.target_text}'"

    # 2. 第二句迅速开始：语音识别出原文 "Did you eat?"，此时大模型翻译未就绪 (target="")
    session._on_engine_emit({
        "id": 2,
        "source": "Did you eat?",
        "target": "",
        "is_final": False
    })

    if session.target_text == "很高兴见到你":
        raise AssertionError(
            f"❌ 捕获到目标病灶 [Issue 3]: 第二句 (id=2) 未返回译文时，target_text 严重泄漏上一句旧译文: '{session.target_text}'"
        )
    
    assert session.target_text == "", f"新句未有译文到达时，target_text 必须为空字符串，实际为 '{session.target_text}'"
    print("✅ 后端 ChannelSession._on_engine_emit 跨句隔离原子性生效。")


def test_server_simulate_event_leak():
    from server import ChannelSession
    session = ChannelSession(name="zh", channel_id="ch_zh", source_lang="en", target_lang="zh", label="英译中")

    session.simulate_event("Nice to meet you", "很高兴见到你", is_final=True, sentence_id=1)
    assert session.target_text == "很高兴见到你"

    # simulate_event for sentence 2 before MT arrives
    session.simulate_event("Did you eat?", "", is_final=False, sentence_id=2)
    assert session.target_text == "", f"simulate_event 跨句目标译文未重置，实际为 '{session.target_text}'"
    print("✅ 后端 ChannelSession.simulate_event 跨句隔离生效。")


def test_qwen_engine_transition():
    from engines.qwen_translators import QwenLiveTranslate38Engine
    dispatched = []

    def mock_emit(p):
        dispatched.append(p)

    engine = QwenLiveTranslate38Engine(
        channel_id="A",
        source_lang="en",
        target_lang="zh",
        emit_fn=mock_emit,
        mock_mode=True
    )

    # 1. Simulate sentence 1 completion
    engine.sentence_id = 1
    engine.source_text = "Nice to meet you"
    engine.target_text = "很高兴见到你"
    engine._on_ws_message(None, json.dumps({
        "type": "response.done",
        "response": {"usage": {"input_tokens": 10, "output_tokens": 10}}
    }))
    assert engine.is_sentence_finalized is True

    # 2. Simulate sentence 2 speech arrival without prior speech_started
    engine._on_ws_message(None, json.dumps({
        "type": "input_audio_transcription.delta",
        "delta": "Did you"
    }))

    assert engine.sentence_id == 2, f"Sentence id should advance to 2, got {engine.sentence_id}"
    assert engine.target_text == "", f"Target text must be empty for new sentence before MT, got '{engine.target_text}'"
    assert len(dispatched) >= 1
    last_p = dispatched[-1]
    assert int(last_p["id"]) == 2
    assert last_p["source"] == "Did you"
    assert last_p["target"] == "", f"Dispatched target must be empty string, got '{last_p['target']}'"
    print("✅ 引擎层 QwenLiveTranslate38Engine 跨句纯 ASR 译文隔离生效。")


def test_frontend_lifecycle():
    if not HAS_WEBKIT:
        print("⚠️ 无 WebKit 环境，跳过前端 DOM 生命周期验证。")
        return

    html_path = os.path.join(REPO_ROOT, "float_ui.html")
    with open(html_path, "r", encoding="utf-8") as f:
        content = f.read()

    app = Cocoa.NSApplication.sharedApplication()
    cfg = WebKit.WKWebViewConfiguration.alloc().init()
    cfg.setWebsiteDataStore_(WebKit.WKWebsiteDataStore.nonPersistentDataStore())
    wv = WebKit.WKWebView.alloc().initWithFrame_configuration_(Cocoa.NSMakeRect(0, 0, 720, 160), cfg)
    wv.loadHTMLString_baseURL_(content, Cocoa.NSURL.fileURLWithPath_(html_path))

    t0 = time.time()
    while time.time() - t0 < 0.25:
        pool = Cocoa.NSAutoreleasePool.alloc().init()
        Cocoa.NSRunLoop.currentRunLoop().runMode_beforeDate_(Cocoa.NSDefaultRunLoopMode, Cocoa.NSDate.dateWithTimeIntervalSinceNow_(0.01))
        del pool

    def eval_js(code):
        holder = {}
        wv.evaluateJavaScript_completionHandler_(code, lambda r, e: holder.update({"r": r, "e": e}))
        st = time.time()
        while "r" not in holder and time.time() - st < 2.0:
            Cocoa.NSRunLoop.currentRunLoop().runMode_beforeDate_(Cocoa.NSDefaultRunLoopMode, Cocoa.NSDate.dateWithTimeIntervalSinceNow_(0.01))
        return holder.get("r")

    eval_js("window.requestAnimationFrame = (cb) => { cb(); return 1; };")

    # Step 1: Sentence 1 finalized
    eval_js("""
    window.scheduleSubtitleUpdate({
        id: 1,
        source: "Nice to meet you",
        target: "很高兴见到你",
        is_final: true
    });
    """)
    assert eval_js("document.getElementById('activeLine').textContent") == "很高兴见到你"

    # Step 2: Empty boundary frame during pause (anchor preserved)
    eval_js("""
    window.scheduleSubtitleUpdate({
        id: 2
    });
    """)
    assert eval_js("document.getElementById('activeLine').textContent") == "很高兴见到你"

    # Step 3: Sentence 2 speech arrives, MT not ready yet
    eval_js("""
    window.scheduleSubtitleUpdate({
        id: 2,
        source: "Did you eat?",
        target: "",
        is_final: false
    });
    """)
    active2 = eval_js("document.getElementById('activeLine').textContent")
    past2 = eval_js("document.getElementById('pastLine').textContent")
    streaming2 = eval_js("document.getElementById('activeLine').classList.contains('streaming')")

    if active2 == "很高兴见到你":
        raise AssertionError("❌ 前端 Bug 复现: 第二句发言到达时，activeLine 仍错误显示第一句旧译文 '很高兴见到你'")

    assert active2 == "", f"activeLine 必须清空以展示流式光标，实际为 '{active2}'"
    assert past2 == "Did you eat?"
    assert streaming2 is True
    print("✅ 前端 float_ui.html 跨句边界过渡与单光标流式防闪烁生效。")


if __name__ == "__main__":
    try:
        test_server_emit_leak()
        test_server_simulate_event_leak()
        test_qwen_engine_transition()
        test_frontend_lifecycle()
        print("✅ 状态：绿灯 (PASS)")
        sys.exit(0)
    except AssertionError as e:
        print(f"🔴 确立红灯基准 (FAIL): {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"💥 异常退出: {e}", file=sys.stderr)
        sys.exit(2)
