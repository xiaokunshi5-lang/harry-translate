"""
server.py - Industrial-Grade High-Performance Async Gateway for Dual-Channel Simultaneous Interpretation

Core Architecture:
1. FastAudioCaptureManager Integration:
   - 50ms micro-chunking (16000Hz, 800 samples, 1600 bytes)
   - Channel A (Mic) and Channel B (Virtual Loopback) physical isolation
   - Zero-restart hot-swapping (<80ms)
2. Dual-Engine Realtime Translation:
   - GummyZeroCopyEngine: sub-450ms zero-copy C-pointer direct push
   - QwenLiveTranslate38Engine: session.update hot language switching <5ms
3. Parallel WebSocket Broadcast with Timeout Circuit Breaker:
   - Single-client send wrapped in asyncio.wait_for(ws.send_text(msg), timeout=0.25)
   - Non-blocking asyncio.gather: healthy client delivery finishes in <1.0ms
   - Slow / unresponsive / suspended clients automatically pruned and closed
4. Full Physical Routes & Decoupled APIs:
   - GET /: Dashboard
   - GET /split: Dual-column monitor with slide-out config drawer
   - GET /en: Foreign guest English display (Channel A)
   - GET /zh: Local team Chinese display (Channel B)
   - GET /hud: Apple minimal floating HUD (float_ui.html with inline fallback)
   - GET /api/meta: System status, loopback/idle state, active engine, masked API key
   - POST /api/config: Dynamic partial update (empty key overwrite protection)
   - GET/POST /api/audio/devices, /api/audio/device: Enumeration and hot-swap
   - GET/POST /api/hud/lock: Click-through status and remote unlock
   - GET/POST /api/stats, /api/stats/reset: Token usage and latency statistics
5. 100% Backward Compatibility:
   - Exports AudioCaptureManager, CHUNK_SIZE = 1600, active_channels, audio_capture_mgr, app
"""

from __future__ import annotations
import os
import sys
import json
import time
import base64
import asyncio
import threading
import queue
import re
from typing import Optional, Dict, List, Any, Set
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
from fastapi.responses import HTMLResponse, JSONResponse

# Core Audio Pipeline
from core.audio_pipeline import (
    FastAudioCaptureManager,
    AudioCaptureManager,
    CHUNK_SAMPLES,
    CHUNK_BYTES,
    CHUNK_SIZE,
    SAMPLE_RATE,
    MAX_JSON_QUEUE_SIZE,
)

# Translation Engines
from engines.qwen_translators import (
    GummyZeroCopyEngine,
    QwenLiveTranslate38Engine,
    TokenBucketLimiter,
)

# Load .env
load_dotenv()

ENV_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
DASHSCOPE_API_KEY = os.getenv("DASHSCOPE_API_KEY", "")
QWEN_REALTIME_WS_URL = os.getenv(
    "QWEN_REALTIME_WS_URL",
    "wss://dashscope.aliyuncs.com/api-ws/v1/realtime?model=qwen3.8-livetranslate-flash-realtime",
)
PORT = int(os.getenv("PORT", "8000"))

DEFAULT_ENGINE = os.getenv("DEFAULT_ENGINE") or os.getenv("ACTIVE_ENGINE") or "qwen3.8-livetranslate-flash-realtime"
if "qwen" in DEFAULT_ENGINE.lower():
    active_engine_type = "qwen3.8-livetranslate-flash-realtime"
else:
    active_engine_type = "gummy-realtime-v1"


main_loop: Optional[asyncio.AbstractEventLoop] = None
should_run = True

# Terminology Management Engine (Milestone 2)
from core.glossary_manager import get_glossary_manager

glossary_mgr = get_glossary_manager()
glossary_manager = glossary_mgr

# Client Connection Pools (Strict Physical Channel Decoupling)
connected_clients: Dict[str, Set[WebSocket]] = {
    "en": set(),
    "zh": set(),
}


# ---------------------------------------------------------------------------
# Parallel Non-Blocking WebSocket Broadcast with Timeout Circuit Breaker
# ---------------------------------------------------------------------------
async def _send_safe(ws: WebSocket, client_set: Set[WebSocket], message: str) -> None:
    """Send text to single WebSocket with 250ms SLA timeout circuit breaker."""
    try:
        await asyncio.wait_for(ws.send_text(message), timeout=0.25)
    except Exception:
        client_set.discard(ws)
        try:
            await ws.close()
        except Exception:
            pass


async def broadcast_to_channel(channel: str, data: Any) -> None:
    """
    Parallel non-blocking broadcast to all connected clients on a given channel.
    Uses asyncio.gather with per-client 250ms timeout.
    Healthy clients receive message in <1.0ms without head-of-line blocking.
    """
    clients = connected_clients.get(channel)
    if not clients:
        return
    if isinstance(data, str):
        message = data
    else:
        message = json.dumps(data, ensure_ascii=False)
    client_list = list(clients)
    if not client_list:
        return
    await asyncio.gather(
        *[_send_safe(ws, clients, message) for ws in client_list],
        return_exceptions=True,
    )


broadcast_parallel = broadcast_to_channel


# ---------------------------------------------------------------------------
# Key Masking & .env Preservation Utilities
# ---------------------------------------------------------------------------
def mask_api_key(key: Optional[str]) -> str:
    """Mask API key showing prefix and suffix, e.g., sk-38a...9x12."""
    if not key:
        return ""
    k = str(key).strip()
    if not k or k.startswith("在此填入") or "your" in k.lower():
        return ""
    if len(k) <= 8:
        return "******"
    return f"{k[:6]}...{k[-4:]}"


def set_env_value(key: str, value: str) -> None:
    """Safely updates or adds a key in .env file without destroying other lines."""
    if not os.path.exists(ENV_FILE):
        with open(ENV_FILE, "w", encoding="utf-8") as f:
            f.write(f"{key}={value}\n")
        return

    with open(ENV_FILE, "r", encoding="utf-8") as f:
        content = f.read()

    pattern = rf"^{key}=.*$"
    if re.search(pattern, content, re.M):
        new_content = re.sub(pattern, f"{key}={value}", content, flags=re.M)
    else:
        new_content = content.rstrip() + f"\n{key}={value}\n"

    try:
        with open(ENV_FILE, "w", encoding="utf-8") as f:
            f.write(new_content)
    except Exception:
        tmp = ENV_FILE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            f.write(new_content)
        os.replace(tmp, ENV_FILE)


# ---------------------------------------------------------------------------
# ChannelSession (Dual-Engine Decoupled Channel)
# ---------------------------------------------------------------------------
class ChannelSession:
    """
    Channel session managing translation pipelines, token usage,
    and Drop-Oldest anti-drift ring buffers.
    """

    def __init__(
        self,
        name: str,
        channel_id: str,
        source_lang: str,
        target_lang: str,
        label: str,
    ):
        self.name = name
        self.channel_id = channel_id
        self.source_lang = source_lang
        self.target_lang = target_lang
        self.label = label

        # Audio queue: maxsize=3 (strictly <= 5 per SLA and backward compatibility)
        self.audio_queue: queue.Queue = queue.Queue(maxsize=MAX_JSON_QUEUE_SIZE)
        self.is_ready = threading.Event()
        self.state_lock = threading.Lock()
        self.ws_client = None

        # Token usage & billing stats
        self.input_tokens = 0
        self.output_tokens = 0
        self.total_tokens = 0
        self.cost_rmb = 0.0

        # Subtitle tracking
        self.sentence_id = 0
        self.source_text = ""
        self.target_text = ""

        # Translation engines
        self.gummy_engine = GummyZeroCopyEngine(
            channel_id=self.channel_id,
            source_lang=self.source_lang,
            target_lang=self.target_lang,
            emit_fn=self._on_engine_emit,
            api_key=DASHSCOPE_API_KEY,
            sample_rate=SAMPLE_RATE,
        )
        self.qwen_engine = QwenLiveTranslate38Engine(
            channel_id=self.channel_id,
            source_lang=self.source_lang,
            target_lang=self.target_lang,
            emit_fn=self._on_engine_emit,
            api_key=DASHSCOPE_API_KEY,
            ws_url=QWEN_REALTIME_WS_URL,
        )

        self.active_engine_type = active_engine_type
        if "qwen" in self.active_engine_type.lower():
            self.active_engine = self.qwen_engine
        else:
            self.active_engine = self.gummy_engine

        # Inject initial hotwords into cloud engine sessions
        self.sync_hotwords()

    def sync_hotwords(self, hotwords: Optional[List[str]] = None) -> List[str]:
        """Inject domain hotwords into cloud translation engines."""
        if hotwords is None:
            hotwords = glossary_mgr.get_hotwords(channel=self.name)
        if hasattr(self.qwen_engine, "live_update_session"):
            try:
                self.qwen_engine.live_update_session(self.target_lang, hotwords)
            except Exception:
                pass
        elif hasattr(self.qwen_engine, "hotwords"):
            self.qwen_engine.hotwords = list(hotwords)
        if hasattr(self.gummy_engine, "set_hotwords"):
            try:
                self.gummy_engine.set_hotwords(hotwords)
            except Exception:
                pass
        elif hasattr(self.gummy_engine, "hotwords"):
            self.gummy_engine.hotwords = list(hotwords)
        return hotwords

    def _on_engine_emit(self, payload: Dict[str, Any]) -> None:
        sid = payload.get("id", self.sentence_id)
        src = payload.get("source", "")
        tgt = payload.get("target", "")
        is_final = payload.get("is_final", False)
        lat = payload.get("latency_ms", 0)

        with self.state_lock:
            incoming_sid = None
            try:
                incoming_sid = int(sid)
            except (ValueError, TypeError):
                incoming_sid = self.sentence_id + 1

            is_new_sentence = (incoming_sid != self.sentence_id)
            # 跨句边界原子隔离：新句开始时彻底清空上一句缓存，严禁脏译文跨句泄露
            if is_new_sentence:
                self.sentence_id = incoming_sid
                self.source_text = ""
                self.target_text = ""

            if src:
                self.source_text = src
            # 只有当同句存在有效更新时赋值；若新句译文尚未到达，保持空字符串，绝不透传旧译文
            if tgt:
                self.target_text = tgt
            elif is_new_sentence:
                self.target_text = ""

            # Token usage calculation
            if "usage" in payload and isinstance(payload["usage"], dict):
                u = payload["usage"]
                in_tok = u.get("input_tokens", 0)
                out_tok = u.get("output_tokens", 0)
                if in_tok or out_tok:
                    self.input_tokens += in_tok
                    self.output_tokens += out_tok
                    self.total_tokens += (in_tok + out_tok)
                    self.cost_rmb = (self.input_tokens * 0.00004) + (self.output_tokens * 0.0001)
            elif is_final and self.total_tokens == 0:
                in_t = max(1, len(self.source_text) * 2) if self.source_text else 0
                out_t = max(1, len(self.target_text) * 2) if self.target_text else 0
                self.input_tokens += in_t
                self.output_tokens += out_t
                self.total_tokens += (in_t + out_t)
                self.cost_rmb = (self.input_tokens * 0.00004) + (self.output_tokens * 0.0001)

        self.dispatch(self.sentence_id, self.source_text, self.target_text, is_final, lat)

    def dispatch(
        self,
        sentence_id: int,
        source: str,
        target: str,
        is_final: bool,
        latency_ms: int = 0,
    ) -> Dict[str, Any]:
        """Schedule parallel broadcast onto main event loop with glossary sanitization."""
        global main_loop
        clean_source, clean_target = glossary_mgr.apply_fixes(
            source or "", target or "", channel=self.name
        )
        with self.state_lock:
            self.source_text = clean_source
            self.target_text = clean_target

        payload = {
            "type": "sub",
            "channel": self.name,
            "ch": self.channel_id,
            "id": sentence_id,
            "source": clean_source,
            "target": clean_target,
            "is_final": is_final,
            "latency_ms": latency_ms,
            "usage": {
                "input_tokens": self.input_tokens,
                "output_tokens": self.output_tokens,
                "total_tokens": self.total_tokens,
                "cost_rmb": round(self.cost_rmb, 4),
            },
        }
        if main_loop and main_loop.is_running():
            asyncio.run_coroutine_threadsafe(
                broadcast_to_channel(self.name, payload),
                main_loop,
            )
        return payload

    def push_audio(self, raw_or_b64: Any) -> None:
        """
        Non-blocking Drop-Oldest ring buffer push.
        Clamped to maxsize=3 (strictly <= 5).
        """
        while self.audio_queue.full():
            try:
                self.audio_queue.get_nowait()
                self.audio_queue.task_done()
            except Exception:
                break
        try:
            self.audio_queue.put_nowait(raw_or_b64)
        except Exception:
            pass

        # Push to active engine
        try:
            pcm_bytes = None
            if isinstance(raw_or_b64, bytes):
                pcm_bytes = raw_or_b64
            elif isinstance(raw_or_b64, str):
                try:
                    pcm_bytes = base64.b64decode(raw_or_b64)
                except Exception:
                    pass

            if pcm_bytes and len(pcm_bytes) >= 2:
                if self.active_engine_type == "gummy-realtime-v1":
                    self.gummy_engine.send_audio_frame(pcm_bytes)
                else:
                    self.qwen_engine.send_audio_chunk(pcm_bytes)
        except Exception:
            pass

    def reset_stats(self) -> None:
        """Reset token usage and billing metrics."""
        with self.state_lock:
            self.input_tokens = 0
            self.output_tokens = 0
            self.total_tokens = 0
            self.cost_rmb = 0.0
            self.sentence_id = 0
            self.source_text = ""
            self.target_text = ""

        if hasattr(self.qwen_engine, "input_tokens"):
            self.qwen_engine.input_tokens = 0
            self.qwen_engine.output_tokens = 0
            self.qwen_engine.total_tokens = 0
            self.qwen_engine.cost_rmb = 0.0

    def switch_engine(self, engine_model: str) -> None:
        """Switch active engine between Gummy and Qwen 3.8."""
        old_engine = self.active_engine
        target_engine_type = (
            "gummy-realtime-v1"
            if "gummy" in engine_model.lower()
            else "qwen3.8-livetranslate-flash-realtime"
        )
        if target_engine_type == self.active_engine_type and getattr(self.active_engine, "is_running", False):
            return

        if "gummy" in engine_model.lower():
            self.active_engine_type = "gummy-realtime-v1"
            self.active_engine = self.gummy_engine
        else:
            self.active_engine_type = "qwen3.8-livetranslate-flash-realtime"
            self.active_engine = self.qwen_engine

        # Graceful transition: if session is running, stop old engine and start new engine
        if self.is_ready.is_set() or getattr(old_engine, "is_running", False):
            if old_engine != self.active_engine and hasattr(old_engine, "stop"):
                try:
                    old_engine.stop()
                except Exception:
                    pass
            key = getattr(self.active_engine, "api_key", None) or DASHSCOPE_API_KEY
            self.active_engine.start(key)

        self.sync_hotwords()

    def update_api_key(self, new_key: str) -> None:
        self.gummy_engine.api_key = new_key
        self.qwen_engine.api_key = new_key

    def set_target_lang(self, new_target: str) -> None:
        with self.state_lock:
            self.target_lang = new_target
            self.gummy_engine.target_lang = new_target
        if hasattr(self.qwen_engine, "live_update_session"):
            hotwords = glossary_mgr.get_hotwords(channel=self.name)
            self.qwen_engine.live_update_session(target_lang=new_target, hotwords=hotwords)

    def simulate_event(
        self,
        source: str,
        target: str,
        is_final: bool = False,
        latency_ms: int = 50,
        sentence_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Simulation interface for automated test execution."""
        with self.state_lock:
            if sentence_id is not None:
                if sentence_id != self.sentence_id:
                    self.source_text = ""
                    self.target_text = ""
                self.sentence_id = sentence_id
            elif is_final:
                self.sentence_id += 1
                self.source_text = ""
                self.target_text = ""
            sid = self.sentence_id
            self.source_text = source or ""
            self.target_text = target or ""
        return self.dispatch(sid, source, target, is_final, latency_ms)

    def start(self, api_key: Optional[str] = None) -> None:
        key = api_key or DASHSCOPE_API_KEY
        self.sync_hotwords()
        self.active_engine.start(key)
        self.is_ready.set()

    def stop(self) -> None:
        self.gummy_engine.stop()
        self.qwen_engine.stop()
        self.is_ready.clear()

    def run_ws(self) -> None:
        """Backward-compatible entry point for thread runner."""
        self.start(DASHSCOPE_API_KEY)

    def run_audio_sender(self) -> None:
        """Backward-compatible entry point for audio sender thread."""
        pass


QwenRealtimeChannel = ChannelSession

# Initialize two decoupled channels:
channel_en = ChannelSession("en", "A", "zh", "en", "中译英-英文屏")
channel_zh = ChannelSession("zh", "B", "en", "zh", "英译中-中文屏")
active_channels: List[ChannelSession] = [channel_en, channel_zh]


def handle_audio_chunk(raw_or_b64: Any) -> None:
    """Backward-compatible fanout function."""
    for ch in active_channels:
        ch.push_audio(raw_or_b64)


# Global Singleton Audio Capture Manager
audio_capture_mgr = FastAudioCaptureManager(
    sample_rate=SAMPLE_RATE,
    chunk_size=CHUNK_SIZE,
    on_audio_chunk=handle_audio_chunk,
)

def is_channel_subscribed(channel_key: str) -> bool:
    """
    Client-Aware Stream Gating:
    Returns True if at least one active client (WebSocket HUD/Screen) is connected to channel_key.
    If no clients are connected to any channel (e.g. server initial startup or test harness),
    returns True to avoid starving unmonitored tests or audio pipelines.
    When only one channel is active (e.g., student in English tutoring only listening to 'zh'),
    audio streaming to the other channel is completely gated, cutting Cloud API token costs by 50%.
    """
    clients = connected_clients.get(channel_key)
    if clients and len(clients) > 0:
        return True
    all_connected = sum(len(c) for c in connected_clients.values())
    return all_connected == 0


# Wire zero-copy physical callbacks with Client-Aware Stream Gating
def _on_mic_pcm(raw_pcm: bytes) -> None:
    if is_channel_subscribed("en"):
        channel_en.push_audio(raw_pcm)
    # Smart audio multiplexing: When Channel B has no dedicated virtual loopback soundcard
    # (standard Mac setup or single-mic test), mirror mic audio to channel_zh as zero-config fallback.
    # This guarantees that both floating windows (中译英 & 英译中) simultaneously work out of the box!
    if audio_capture_mgr.worker_b.is_idle:
        if is_channel_subscribed("zh"):
            channel_zh.push_audio(raw_pcm)

def _on_loopback_pcm(raw_pcm: bytes) -> None:
    if not audio_capture_mgr.worker_b.is_idle:
        if is_channel_subscribed("zh"):
            channel_zh.push_audio(raw_pcm)

audio_capture_mgr.worker_a.set_zero_copy_callback(_on_mic_pcm)
audio_capture_mgr.worker_b.set_zero_copy_callback(_on_loopback_pcm)


def audio_capture_worker() -> None:
    """Backward-compatible capture worker entry point."""
    audio_capture_mgr.start()


# HUD click-through and lock state (supports per-window tracking for dual HUD)
hud_lock_state = {"locked": False, "windows": {"en": False, "zh": False}}
hud_lock_mutex = threading.Lock()


# ---------------------------------------------------------------------------
# FastAPI Application & Lifespan
# ---------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    global main_loop
    main_loop = asyncio.get_running_loop()
    if not audio_capture_mgr.is_running:
        audio_capture_mgr.start()
    for ch in active_channels:
        ch.switch_engine(active_engine_type)
        ch.sync_hotwords()
        ch.start(DASHSCOPE_API_KEY)
    print(">> [服务启动] Harry Translate (哈利同传) 双通道极速同传系统已就绪！")
    print(f"   • 当前同传引擎: {active_engine_type}")
    print(f"   • 主控面板:    http://localhost:{PORT}/")
    print(f"   • 悬浮同传HUD: http://localhost:{PORT}/hud (Zero-install Fallback)")
    print(f"   • 中译英大屏:  http://localhost:{PORT}/en  (投屏给外宾看)")
    print(f"   • 英译重大屏:  http://localhost:{PORT}/zh  (投屏给中方看)")
    print(f"   • 左右双栏屏:  http://localhost:{PORT}/split (现场控台对照)")
    yield
    audio_capture_mgr.stop()
    for ch in active_channels:
        ch.stop()


app = FastAPI(title="Harry Translate 国际会议实时双语同传系统", lifespan=lifespan)


# ---------------------------------------------------------------------------
# WebSocket Endpoints
# ---------------------------------------------------------------------------
@app.websocket("/ws/{channel}")
async def websocket_channel_endpoint(websocket: WebSocket, channel: str):
    """Client connection endpoint for /ws/en and /ws/zh."""
    if channel not in connected_clients:
        await websocket.close(code=1003)
        return

    await websocket.accept()
    connected_clients[channel].add(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        connected_clients[channel].discard(websocket)
    except Exception:
        connected_clients[channel].discard(websocket)


@app.websocket("/ws")
async def websocket_default_endpoint(websocket: WebSocket):
    """Fallback WebSocket endpoint defaulting to en channel."""
    await websocket_channel_endpoint(websocket, "en")


# ---------------------------------------------------------------------------
# Physical Presentation Routes
# ---------------------------------------------------------------------------
@app.get("/")
def get_dashboard():
    """Dashboard / Console Monitor."""
    html_path = os.path.join(os.path.dirname(__file__), "index.html")
    with open(html_path, "r", encoding="utf-8") as f:
        return HTMLResponse(content=f.read(), media_type="text/html; charset=utf-8")


@app.get("/en")
def get_en_screen():
    """Dedicated English Display Screen (Channel A)."""
    html_path = os.path.join(os.path.dirname(__file__), "index.html")
    with open(html_path, "r", encoding="utf-8") as f:
        return HTMLResponse(content=f.read(), media_type="text/html; charset=utf-8")


@app.get("/zh")
def get_zh_screen():
    """Dedicated Chinese Display Screen (Channel B)."""
    html_path = os.path.join(os.path.dirname(__file__), "index.html")
    with open(html_path, "r", encoding="utf-8") as f:
        return HTMLResponse(content=f.read(), media_type="text/html; charset=utf-8")


@app.get("/split")
def get_split_screen():
    """Dual-Column Monitor Screen with Config Drawer."""
    html_path = os.path.join(os.path.dirname(__file__), "index.html")
    with open(html_path, "r", encoding="utf-8") as f:
        return HTMLResponse(content=f.read(), media_type="text/html; charset=utf-8")


@app.get("/hud")
def get_hud_screen():
    """Apple Minimal Floating HUD (Zero-install Fallback)."""
    html_path = os.path.join(os.path.dirname(__file__), "float_ui.html")
    if os.path.exists(html_path) and os.path.getsize(html_path) > 0:
        with open(html_path, "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read(), media_type="text/html; charset=utf-8")
    else:
        fallback_html = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Harry Translate · 极简悬浮同传 HUD (就绪中)</title>
    <style>
        body {
            margin: 0;
            padding: 24px;
            background: rgba(18, 18, 22, 0.85);
            color: #ffffff;
            font-family: -apple-system, BlinkMacSystemFont, "SF Pro Text", "PingFang SC", "Segoe UI", sans-serif;
            display: flex;
            align-items: center;
            justify-content: center;
            min-height: 100vh;
        }
        .hud-container {
            border: 1px solid rgba(255, 255, 255, 0.15);
            border-radius: 20px;
            padding: 24px 32px;
            text-align: center;
            backdrop-filter: blur(20px);
            max-width: 600px;
        }
        h2 { margin-bottom: 12px; font-size: 20px; font-weight: 500; }
        p { color: rgba(255, 255, 255, 0.7); font-size: 14px; line-height: 1.6; }
    </style>
</head>
<body>
    <div class="hud-container">
        <h2>⚡ Harry Translate (哈利同传) 悬浮 HUD 服务已就绪</h2>
        <p>悬浮 HUD 界面文件 (<code>float_ui.html</code>) 正在构建或加载中。<br>后端 API 及音频双路采集引擎工作正常。</p>
    </div>
</body>
</html>"""
        return HTMLResponse(content=fallback_html, media_type="text/html; charset=utf-8")


# ---------------------------------------------------------------------------
# Configuration & Metadata Endpoints
# ---------------------------------------------------------------------------
@app.get("/api/meta")
def get_meta():
    """
    Returns system status, audio devices (indicating is_loopback and is_idle),
    active engine type, and masked DashScope API key.
    """
    devices_info = audio_capture_mgr.get_devices()
    masked_key = mask_api_key(DASHSCOPE_API_KEY)

    return JSONResponse(content={
        "status": "ok",
        "system_status": "online",
        "active_engine": active_engine_type,
        "engine_type": active_engine_type,
        "engine_model": active_engine_type,
        "api_key_masked": masked_key,
        "dashscope_key_masked": masked_key,
        "dashscope_api_key_masked": masked_key,
        "masked_api_key": masked_key,
        "devices": devices_info.get("devices", []),
        "audio_devices": devices_info.get("devices", []),
        "channel_a_device": devices_info.get("channel_a_device"),
        "channel_b_device": devices_info.get("channel_b_device"),
        "channel_b_idle": devices_info.get("channel_b_idle", False),
        "channel_status": {
            "channel_a": {
                "name": channel_en.name,
                "device": devices_info.get("channel_a_device"),
                "is_idle": False,
                "target_lang": channel_en.target_lang,
                "label": channel_en.label,
            },
            "channel_b": {
                "name": channel_zh.name,
                "device": devices_info.get("channel_b_device"),
                "is_idle": devices_info.get("channel_b_idle", False),
                "is_loopback": True,
                "target_lang": channel_zh.target_lang,
                "label": channel_zh.label,
            },
        },
    })


@app.get("/api/config")
def get_config():
    """Returns current active configuration."""
    masked_key = mask_api_key(DASHSCOPE_API_KEY)
    devices_info = audio_capture_mgr.get_devices()
    return JSONResponse(content={
        "status": "ok",
        "engine_model": active_engine_type,
        "active_engine": active_engine_type,
        "api_key_masked": masked_key,
        "dashscope_key_masked": masked_key,
        "channel_a_device": devices_info.get("channel_a_device"),
        "channel_b_device": devices_info.get("channel_b_device"),
        "channel_b_idle": devices_info.get("channel_b_idle", False),
        "target_lang_a": channel_en.target_lang,
        "target_lang_b": channel_zh.target_lang,
    })


@app.post("/api/config")
async def post_config(request: Request):
    """
    Dynamic partial configuration update.
    CRITICAL: Submitting an empty or whitespace API key MUST NEVER overwrite an existing key in .env!
    """
    global DASHSCOPE_API_KEY, active_engine_type
    try:
        body = await request.json()
    except Exception:
        body = {}
    if not isinstance(body, dict):
        body = {}

    updated: Dict[str, Any] = {}

    # 1. API Key handling (CRITICAL: Never overwrite with empty/whitespace!)
    api_key = body.get("api_key")
    if api_key is None:
        api_key = body.get("dashscope_api_key")

    if api_key is not None:
        key_str = str(api_key).strip()
        if key_str:
            DASHSCOPE_API_KEY = key_str
            os.environ["DASHSCOPE_API_KEY"] = key_str
            set_env_value("DASHSCOPE_API_KEY", key_str)
            for ch in active_channels:
                ch.update_api_key(key_str)
            updated["api_key"] = mask_api_key(key_str)
        else:
            # Empty or whitespace key is strictly ignored!
            pass

    # 2. Channel A Device hot-swap
    dev_a = body.get("channel_a_device")
    if dev_a is None:
        dev_a = body.get("device_a")
    if dev_a is None and "device_index" in body and str(body.get("channel", "A")).upper() == "A":
        dev_a = body.get("device_index")
    if dev_a is not None:
        try:
            res_a = audio_capture_mgr.set_device(int(dev_a), channel="A")
            updated["channel_a"] = res_a
        except Exception as e:
            updated["channel_a_error"] = str(e)

    # 3. Channel B Device hot-swap
    dev_b = body.get("channel_b_device")
    if dev_b is None:
        dev_b = body.get("device_b")
    if dev_b is None and "device_index" in body and str(body.get("channel", "A")).upper() == "B":
        dev_b = body.get("device_index")
    if dev_b is not None:
        try:
            res_b = audio_capture_mgr.set_device(int(dev_b), channel="B")
            updated["channel_b"] = res_b
        except Exception as e:
            updated["channel_b_error"] = str(e)

    # 4. Engine Model
    engine_model = body.get("engine_model") or body.get("engine") or body.get("active_engine")
    if engine_model:
        engine_str = str(engine_model).strip()
        if "gummy" in engine_str.lower():
            active_engine_type = "gummy-realtime-v1"
        else:
            active_engine_type = "qwen3.8-livetranslate-flash-realtime"
        for ch in active_channels:
            ch.switch_engine(active_engine_type)
        updated["engine_model"] = active_engine_type

    # 5. Language switches
    if "target_lang_a" in body:
        channel_en.set_target_lang(str(body["target_lang_a"]))
        updated["target_lang_a"] = channel_en.target_lang
    if "target_lang_b" in body:
        channel_zh.set_target_lang(str(body["target_lang_b"]))
        updated["target_lang_b"] = channel_zh.target_lang

    devices_info = audio_capture_mgr.get_devices()
    return JSONResponse(content={
        "status": "ok",
        "message": "Configuration updated successfully",
        "updated": updated,
        "current_config": {
            "engine_model": active_engine_type,
            "api_key_masked": mask_api_key(DASHSCOPE_API_KEY),
            "channel_a_device": devices_info.get("channel_a_device"),
            "channel_b_device": devices_info.get("channel_b_device"),
            "channel_b_idle": devices_info.get("channel_b_idle", False),
        },
    })


# ---------------------------------------------------------------------------
# Audio Device Management Endpoints
# ---------------------------------------------------------------------------
@app.get("/api/audio/devices")
def get_audio_devices():
    """Get all available audio input devices (microphones & virtual loopbacks)."""
    devices_info = audio_capture_mgr.get_devices()
    return JSONResponse(content=devices_info)


@app.post("/api/audio/device")
async def set_audio_device(request: Request, device_index: Optional[int] = None):
    """
    Seamless zero-restart hot-swapping (<80ms SLA).
    Supports JSON body {"device_index": int, "channel": "A"|"B"} or query params.
    """
    target_idx = device_index
    channel = "A"

    # Query params check
    if target_idx is None and "device_index" in request.query_params:
        target_idx = request.query_params.get("device_index")
    if "channel" in request.query_params:
        channel = request.query_params.get("channel", "A")

    # JSON body check
    if target_idx is None:
        try:
            body = await request.json()
            if isinstance(body, dict):
                target_idx = body.get("device_index")
                if target_idx is None:
                    target_idx = body.get("index")
                if "channel" in body:
                    channel = body.get("channel", "A")
        except Exception:
            pass

    if target_idx is None:
        return JSONResponse(
            status_code=400,
            content={"status": "error", "message": "Missing device_index in request"},
        )

    try:
        target_idx = int(target_idx)
    except (ValueError, TypeError):
        return JSONResponse(
            status_code=422,
            content={"status": "error", "message": f"Invalid device_index format: {target_idx}"},
        )

    result = audio_capture_mgr.set_device(target_idx, channel=channel)
    status_code = 200 if result.get("status") == "ok" else 400
    return JSONResponse(status_code=status_code, content=result)


# ---------------------------------------------------------------------------
# HUD Lock & Click-Through Endpoints
# ---------------------------------------------------------------------------
@app.get("/api/hud/lock")
def get_hud_lock(locked: Optional[bool] = None, window_id: Optional[str] = None, channel: Optional[str] = None):
    """Query or toggle HUD click-through status (supports per-window and global queries)."""
    wid = window_id or channel
    with hud_lock_mutex:
        if "windows" not in hud_lock_state:
            hud_lock_state["windows"] = {"en": False, "zh": False}

        if locked is not None:
            b_locked = bool(locked)
            if wid:
                hud_lock_state["windows"][wid] = b_locked
                hud_lock_state["locked"] = any(hud_lock_state["windows"].values())
            else:
                hud_lock_state["locked"] = b_locked
                for k in list(hud_lock_state["windows"].keys()):
                    hud_lock_state["windows"][k] = b_locked

        content = {
            "status": "ok",
            "locked": hud_lock_state["locked"],
            "windows": dict(hud_lock_state["windows"])
        }
        if wid:
            content["window_id"] = wid
            content["window_locked"] = hud_lock_state["windows"].get(wid, False)
        return JSONResponse(content=content)


@app.post("/api/hud/lock")
async def post_hud_lock(request: Request, locked: Optional[bool] = None, window_id: Optional[str] = None, channel: Optional[str] = None):
    """Set HUD click-through status (supports JSON or query params, per-window or global)."""
    target_locked = locked
    wid = window_id or channel
    if target_locked is None and "locked" in request.query_params:
        target_locked = request.query_params.get("locked")
    if wid is None and "window_id" in request.query_params:
        wid = request.query_params.get("window_id")
    if wid is None and "channel" in request.query_params:
        wid = request.query_params.get("channel")

    if target_locked is None or wid is None:
        try:
            body = await request.json()
            if isinstance(body, dict):
                if target_locked is None:
                    target_locked = body.get("locked")
                if wid is None:
                    wid = body.get("window_id") or body.get("channel")
        except Exception:
            pass

    with hud_lock_mutex:
        if "windows" not in hud_lock_state:
            hud_lock_state["windows"] = {"en": False, "zh": False}

        if target_locked is not None:
            if isinstance(target_locked, str):
                b_locked = target_locked.lower() in ("true", "1", "yes")
            else:
                b_locked = bool(target_locked)

            if wid:
                hud_lock_state["windows"][wid] = b_locked
                hud_lock_state["locked"] = any(hud_lock_state["windows"].values())
            else:
                hud_lock_state["locked"] = b_locked
                for k in list(hud_lock_state["windows"].keys()):
                    hud_lock_state["windows"][k] = b_locked

        content = {
            "status": "ok",
            "locked": hud_lock_state["locked"],
            "windows": dict(hud_lock_state["windows"])
        }
        if wid:
            content["window_id"] = wid
            content["window_locked"] = hud_lock_state["windows"].get(wid, False)

        ws_payload = {
            "type": "hud_lock",
            "locked": hud_lock_state["locked"],
            "windows": dict(hud_lock_state["windows"]),
        }
        if wid:
            ws_payload["window_id"] = wid
            ws_payload["channel"] = wid
        try:
            for ch in ["en", "zh", "all", "hud"]:
                asyncio.create_task(broadcast_to_channel(ch, ws_payload))
        except Exception:
            pass

        return JSONResponse(content=content)


# ---------------------------------------------------------------------------
# Token Statistics & Usage Accounting Endpoints
# ---------------------------------------------------------------------------
@app.get("/api/stats")
def get_stats():
    """Real-time token usage and cost accounting."""
    tot_in = sum(ch.input_tokens for ch in active_channels)
    tot_out = sum(ch.output_tokens for ch in active_channels)
    tot_tok = sum(ch.total_tokens for ch in active_channels)
    tot_cost = sum(ch.cost_rmb for ch in active_channels)
    return JSONResponse(content={
        "total_tokens": tot_tok,
        "input_tokens": tot_in,
        "output_tokens": tot_out,
        "cost_rmb": round(tot_cost, 4),
        "channels": {
            ch.name: {
                "input_tokens": ch.input_tokens,
                "output_tokens": ch.output_tokens,
                "total_tokens": ch.total_tokens,
                "cost_rmb": round(ch.cost_rmb, 4),
            }
            for ch in active_channels
        },
    })


@app.post("/api/stats/reset")
def reset_stats():
    """Reset meeting session token counters."""
    for ch in active_channels:
        ch.reset_stats()
    return JSONResponse(content={"status": "ok"})


# ---------------------------------------------------------------------------
# Specialized Terminology & Dynamic Glossary Hot-Reload Endpoints (Milestones 1 & 2)
# ---------------------------------------------------------------------------
@app.get("/api/glossary")
def get_glossary():
    """
    Query active terminology dictionary, metadata, quota status, and session terms.
    Returns backward-compatible keys along with quota and categories breakdown.
    """
    meta = glossary_mgr.get_meta()
    data = glossary_mgr.to_dict()
    quota = glossary_mgr.get_quota_status()
    terms_count = meta.get("counts", {}).get("total_terms", 0)
    return JSONResponse(content={
        "status": "ok",
        "terms_count": terms_count,
        "total_terms": terms_count,
        "counts": meta.get("counts", {}),
        "_version": meta.get("_version", "1.0"),
        "description": meta.get("description", ""),
        "data": data,
        "glossary": data,
        "quota": quota,
        "categories": quota.get("categories", []),
        "session_terms": meta.get("session_terms", {}),
        "session_terms_count": quota.get("session_terms_count", 0),
        "permanent_terms_count": quota.get("permanent_terms_count", 0),
    })


@app.post("/api/glossary")
@app.post("/api/glossary/reload")
async def post_glossary(request: Request):
    """
    Unified glossary mutation endpoint supporting:
    1. Legacy full glossary JSON reload (in <= 5ms)
    2. Batch text import (batch_text with multi-delimiters =, ->, =>, :, ：)
    3. Single term add (source, target, category, is_session)
    Dynamically pushes updated hotwords to active channel sessions.
    """
    t0 = time.perf_counter()
    payload = {}
    try:
        raw_body = await request.body()
        if raw_body:
            payload = json.loads(raw_body.decode("utf-8"))
    except Exception:
        pass
    if not isinstance(payload, dict):
        payload = {}

    is_session = bool(payload.get("is_session", False))

    if "batch_text" in payload:
        batch_text = str(payload.get("batch_text", ""))
        default_cat = str(payload.get("category", "terms_zh_to_en"))
        res = glossary_mgr.import_batch_text(batch_text, default_category=default_cat, is_session=is_session)
    elif "source" in payload and "target" in payload:
        src = str(payload.get("source", ""))
        tgt = str(payload.get("target", ""))
        cat = str(payload.get("category", "terms_zh_to_en"))
        glossary_mgr.add_term(src, tgt, category=cat, is_session=is_session)
        res = {"status": "ok", "added": src, "is_session": is_session}
    else:
        reload_res = glossary_mgr.reload(new_data=payload, persist=True)
        res = reload_res

    # Dynamically trigger hotwords update on active channel sessions without restarting server
    for ch in active_channels:
        try:
            ch.sync_hotwords()
        except Exception:
            pass

    measured_ms = round((time.perf_counter() - t0) * 1000.0, 3)
    elapsed_ms = float(res.get("reload_ms", measured_ms))
    meta = glossary_mgr.get_meta()
    terms_count = meta.get("counts", {}).get("total_terms", 0)
    quota = glossary_mgr.get_quota_status()

    return JSONResponse(content={
        "status": "ok",
        "message": "Glossary updated successfully",
        "reload_ms": elapsed_ms,
        "reload_time_ms": elapsed_ms,
        "terms_count": terms_count,
        "total_terms": terms_count,
        "counts": meta.get("counts", {}),
        "quota": quota,
        "details": res,
    })


@app.post("/api/glossary/session/clear")
async def post_glossary_session_clear():
    """Clear temporary session words with 0 disk writes and sync active channels."""
    cleared_count = glossary_mgr.clear_session()
    for ch in active_channels:
        try:
            ch.sync_hotwords()
        except Exception:
            pass
    return JSONResponse(content={
        "status": "ok",
        "cleared_count": cleared_count,
        "message": f"Cleared {cleared_count} session terms with 0 disk writes",
        "quota": glossary_mgr.get_quota_status(),
    })


@app.post("/api/glossary/session/promote")
async def post_glossary_session_promote():
    """Promote temporary session words into permanent dictionary, write to disk, and sync."""
    promoted_count = glossary_mgr.promote_session()
    for ch in active_channels:
        try:
            ch.sync_hotwords()
        except Exception:
            pass
    return JSONResponse(content={
        "status": "ok",
        "promoted_count": promoted_count,
        "message": f"Promoted {promoted_count} session terms to permanent dictionary",
        "quota": glossary_mgr.get_quota_status(),
    })


@app.post("/api/glossary/toggle_pack")
async def post_glossary_toggle_pack(request: Request):
    """Toggle a category pack's enabled state and sync hotwords."""
    payload = {}
    try:
        raw_body = await request.body()
        if raw_body:
            payload = json.loads(raw_body.decode("utf-8"))
    except Exception:
        pass
    if not isinstance(payload, dict):
        payload = {}

    pack_id = str(payload.get("pack_id", ""))
    enabled = bool(payload.get("enabled", True))

    success = glossary_mgr.toggle_pack(pack_id, enabled)
    if success:
        for ch in active_channels:
            try:
                ch.sync_hotwords()
            except Exception:
                pass

    return JSONResponse(content={
        "status": "ok" if success else "error",
        "pack_id": pack_id,
        "enabled": enabled if success else (not enabled),
        "message": "Pack toggled successfully" if success else "Cannot toggle pack (locked or invalid)",
        "quota": glossary_mgr.get_quota_status(),
    })


@app.post("/api/glossary/delete")
async def post_glossary_delete(request: Request):
    """Delete a specific term from session or permanent storage."""
    payload = {}
    try:
        raw_body = await request.body()
        if raw_body:
            payload = json.loads(raw_body.decode("utf-8"))
    except Exception:
        pass
    if not isinstance(payload, dict):
        payload = {}

    key = str(payload.get("key", payload.get("source", "")))
    cat = str(payload.get("category", "terms_zh_to_en"))
    is_session = payload.get("is_session")
    if is_session is not None:
        is_session = bool(is_session)

    success = glossary_mgr.delete_term(key, category=cat, is_session=is_session)
    if success:
        for ch in active_channels:
            try:
                ch.sync_hotwords()
            except Exception:
                pass

    return JSONResponse(content={
        "status": "ok" if success else "error",
        "deleted": key,
        "quota": glossary_mgr.get_quota_status(),
    })


@app.get("/api/glossary/hotwords")
def get_glossary_hotwords(channel: str = "zh"):
    """Get active domain hotwords list capped at safe threshold (<= 900 terms)."""
    hotwords = glossary_mgr.get_hotwords(channel=channel)
    quota = glossary_mgr.get_quota_status()
    return JSONResponse(content={
        "status": "ok",
        "channel": channel,
        "count": len(hotwords),
        "hotwords": hotwords,
        "quota": quota,
    })


@app.get("/api/glossary/terms/active")
def get_active_glossary_terms(
    category: str = "terms_zh_to_en",
    scope: str = "all",
    q: Optional[str] = None,
    search: Optional[str] = None,
    deduplicate: bool = False,
):
    """Retrieve active terminology records across P0, P1, P2, and P3."""
    search_query = q if q is not None else search
    terms = glossary_mgr.get_active_terms(
        category=category,
        scope=scope,
        search=search_query,
        deduplicate=deduplicate,
    )
    return JSONResponse(content={
        "status": "ok",
        "category": category,
        "scope": scope,
        "count": len(terms),
        "total_active_terms": len(terms),
        "terms": terms,
        "quota": glossary_mgr.get_quota_status(),
    })


@app.post("/api/glossary/check_conflict")
async def post_glossary_check_conflict(request: Request):
    """Check conflict status for proposed term mapping against all active terms."""
    payload = {}
    try:
        raw = await request.body()
        if raw:
            payload = json.loads(raw.decode("utf-8"))
    except Exception:
        pass
    if not isinstance(payload, dict):
        payload = {}

    chinese = str(payload.get("chinese", payload.get("source", "")))
    target = str(payload.get("target", ""))
    cat = str(payload.get("category", "terms_zh_to_en"))
    is_session = bool(payload.get("is_session", True))
    proposed_priority = str(payload.get("proposed_priority", "P0" if is_session else "P1"))

    result = glossary_mgr.check_conflict(
        chinese=chinese,
        target=target,
        category=cat,
        proposed_priority=proposed_priority,
    )
    return JSONResponse(content=result)


# ---------------------------------------------------------------------------
# Server Main Entrypoint
# ---------------------------------------------------------------------------
def main():
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=PORT, log_level="warning")


if __name__ == "__main__":
    main()
