"""
engines/qwen_translators.py - Dual-Engine Realtime Translation Hub

Provides:
1. GummyZeroCopyEngine:
   - High-throughput, sub-450ms Gummy-v1 engine wrapping DashScope TranslationRecognizerRealtime.
   - Direct C-pointer binary PCM push via send_audio_frame(pcm_bytes).
   - Cold-start guard: waits for on_open event before streaming to prevent crashes.
   - Graceful fallback: simulated/mock test mode when dashscope is not installed or network is unavailable.
2. TokenBucketLimiter:
   - RPM=10 quota protection limiter ensuring compliance with DashScope rate limits.
3. QwenLiveTranslate38Engine:
   - Realtime engine supporting live_update_session (session.update) for language and hotword switching in <5ms without reconnecting.
   - Integrated TokenBucketLimiter.
4. Standardized Output Payload:
   {"type": "sub", "ch": "A"|"B", "id": "...", "source": "...", "target": "...", "is_final": bool, "latency_ms": int}
"""

import array
import base64
import json
import os
import queue
import threading
import time
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

try:
    import audioop
except ImportError:
    audioop = None

# ---------------------------------------------------------------------------
# Dynamic DashScope SDK Import with Graceful Fallback
# ---------------------------------------------------------------------------
try:
    import dashscope
    from dashscope.audio.asr import (
        TranscriptionResult,
        TranslationRecognizerCallback,
        TranslationRecognizerRealtime,
        TranslationResult,
    )
    HAS_DASHSCOPE = True
except ImportError:
    dashscope = None  # type: ignore
    TranscriptionResult = None  # type: ignore
    TranslationRecognizerCallback = object  # type: ignore
    TranslationRecognizerRealtime = None  # type: ignore
    TranslationResult = None  # type: ignore
    HAS_DASHSCOPE = False

# Fallback WebSocket Client Import
try:
    import websocket
    HAS_WEBSOCKET = True
except ImportError:
    websocket = None  # type: ignore
    HAS_WEBSOCKET = False

DEFAULT_QWEN_REALTIME_WS_URL = os.getenv(
    "QWEN_REALTIME_WS_URL",
    "wss://dashscope.aliyuncs.com/api-ws/v1/realtime?model=qwen3.8-livetranslate-flash-realtime",
)

# 可配置 Token 计费单价（默认：输入 40 元/百万 Token，输出 100 元/百万 Token）
INPUT_TOKEN_PRICE_PER_M: float = float(os.getenv("INPUT_TOKEN_PRICE_PER_M", "40.0"))
OUTPUT_TOKEN_PRICE_PER_M: float = float(os.getenv("OUTPUT_TOKEN_PRICE_PER_M", "100.0"))
INPUT_TOKEN_UNIT_PRICE: float = INPUT_TOKEN_PRICE_PER_M / 1_000_000.0
OUTPUT_TOKEN_UNIT_PRICE: float = OUTPUT_TOKEN_PRICE_PER_M / 1_000_000.0


def get_token_unit_prices() -> Tuple[float, float]:
    """Get current per-token input and output unit prices (dynamic env lookup with module fallback)."""
    try:
        in_p = float(os.getenv("INPUT_TOKEN_PRICE_PER_M", str(INPUT_TOKEN_PRICE_PER_M)))
        out_p = float(os.getenv("OUTPUT_TOKEN_PRICE_PER_M", str(OUTPUT_TOKEN_PRICE_PER_M)))
        return in_p / 1_000_000.0, out_p / 1_000_000.0
    except (ValueError, TypeError):
        return INPUT_TOKEN_UNIT_PRICE, OUTPUT_TOKEN_UNIT_PRICE

def _calc_pcm_rms(raw_pcm: bytes) -> float:
    if not raw_pcm:
        return 0.0
    remainder = len(raw_pcm) % 2
    if remainder != 0:
        raw_pcm = raw_pcm[:-remainder]
        if not raw_pcm:
            return 0.0
    if audioop is not None:
        try:
            return float(audioop.rms(raw_pcm, 2))
        except Exception:
            pass
    a = array.array("h")
    a.frombytes(raw_pcm)
    if not a:
        return 0.0
    return float((sum(x * x for x in a) / len(a)) ** 0.5)


PUBLIC_QWEN_WS_TMPL = "wss://dashscope.aliyuncs.com/api-ws/v1/realtime?model={model}"


def resolve_ws_url(url: str, api_key: Optional[str]) -> str:
    """按 Key 类型确定性路由 WebSocket 端点（零网络探测、零启动开销）。

    - sk-ws- 开头的业务空间专属 Key：保持用户配置的私有 MaaS 端点不变；
    - 其它普通公网 Key：若配置的是私有 maas.aliyuncs.com 端点，自动改走官方公网网关。
    判定规则复用 switch_key.py 中已有的启发式。
    """
    u = str(url or DEFAULT_QWEN_REALTIME_WS_URL)
    k = str(api_key or "").strip()
    if "maas.aliyuncs.com" in u and not k.startswith("sk-ws-"):
        import re as _re
        m = _re.search(r"model=([^&]+)", u)
        return PUBLIC_QWEN_WS_TMPL.format(model=m.group(1) if m else "qwen3.8-livetranslate-flash-realtime")
    return u


def compute_reconnect_delay(attempt: int) -> float:
    """截断指数退避 + 抖动：首次 ≤0.5s（比原来的固定 1s 更快），上限 15s。"""
    import random
    base = min(15.0, 0.5 * (2 ** max(0, attempt)))
    return base * random.uniform(0.5, 1.0)


def _classify_engine_error(
    error: Any,
    status_code: Optional[int] = None,
    api_key: Optional[str] = None,
) -> tuple:
    """Classify engine error into (state, sanitized_detail)."""
    import re as _re
    code = status_code if status_code is not None else getattr(error, "status_code", None)
    raw = str(error or "")
    if api_key and len(api_key.strip()) >= 4:
        raw = raw.replace(api_key.strip(), "***")
    raw = _re.sub(r"sk-[A-Za-z0-9_-]{4,}", "sk-***", raw)
    detail = raw[:160]
    low = raw.lower()

    if code in (401, 403) or any(
        kw in low
        for kw in (
            "invalidapikey",
            "invalid_api_key",
            "invalid api key",
            "unauthorized",
            "arrearage",
            "accessdenied",
            "access_denied",
            "forbidden",
        )
    ):
        return "auth_failed", detail

    if code == 429 or any(
        kw in low for kw in ("throttling", "ratelimit", "rate_limit", "too many requests")
    ):
        return "rate_limited", detail

    return "network_error", detail


# ---------------------------------------------------------------------------
# TokenBucketLimiter for RPM=10 Quota Protection
# ---------------------------------------------------------------------------
class TokenBucketLimiter:
    """
    Thread-safe token bucket rate limiter for RPM quota management.
    Defaults to 10 RPM (10 requests per 60 seconds).
    """

    def __init__(self, capacity: float = 10.0, fill_rate: Optional[float] = None):
        # Capacity is the maximum bucket size (burst allowance)
        self.capacity: float = float(capacity)
        # Default: 10 requests per 60 seconds = 1/6 tokens per second
        self.fill_rate: float = fill_rate if fill_rate is not None else (self.capacity / 60.0)
        self.tokens: float = self.capacity
        self.last_check: float = time.time()
        self.lock = threading.Lock()

    def _refill(self) -> None:
        """Add newly accrued tokens based on elapsed time."""
        now = time.time()
        elapsed = now - self.last_check
        self.last_check = now
        self.tokens = min(self.capacity, self.tokens + (elapsed * self.fill_rate))

    def try_acquire(self, tokens: float = 1.0) -> bool:
        """
        Non-blocking token acquisition.
        Returns True if tokens were acquired, False otherwise.
        """
        with self.lock:
            self._refill()
            if self.tokens >= tokens:
                self.tokens -= tokens
                return True
            return False

    def acquire(self, tokens: float = 1.0, block: bool = True, timeout: Optional[float] = None) -> bool:
        """
        Attempt to acquire tokens, optionally blocking until available or timed out.
        """
        start_time = time.time()
        while True:
            with self.lock:
                self._refill()
                if self.tokens >= tokens:
                    self.tokens -= tokens
                    return True
                if not block:
                    return False
                # Calculate required sleep duration
                missing = tokens - self.tokens
                wait_time = missing / self.fill_rate if self.fill_rate > 0 else 0.1

            if timeout is not None and (time.time() - start_time + wait_time) > timeout:
                return False

            sleep_duration = min(wait_time, 0.05)
            time.sleep(sleep_duration)

    @property
    def current_tokens(self) -> float:
        with self.lock:
            self._refill()
            return self.tokens


# ---------------------------------------------------------------------------
# GummyZeroCopyEngine
# ---------------------------------------------------------------------------
class GummyZeroCopyEngine:
    """
    DashScope gummy-realtime-v1 zero-copy real-time translation engine.
    - Direct C-pointer binary PCM push via send_audio_frame(pcm_bytes).
    - Push guarded by is_ready (waits for on_open before sending frames).
    - Standardized payload dispatch.
    - Seamless mock/simulation fallback when dashscope is not installed.
    """

    def __init__(
        self,
        channel_id: str = "A",
        source_lang: str = "zh",
        target_lang: str = "en",
        emit_fn: Optional[Callable[[Dict[str, Any]], None]] = None,
        api_key: Optional[str] = None,
        sample_rate: int = 16000,
        mock_mode: bool = False,
    ):
        self.channel_id = channel_id
        self.source_lang = source_lang
        self.target_lang = target_lang
        self.emit_fn = emit_fn
        self.api_key = api_key or os.getenv("DASHSCOPE_API_KEY", "")
        self.sample_rate = sample_rate
        self._explicit_mock: bool = bool(mock_mode)
        self.mock_mode = mock_mode or (not HAS_DASHSCOPE)
        self._mock_forced_by_key: bool = False
        self.status_fn: Optional[Callable[[str, str], None]] = None
        self.engine_state: str = "idle"
        self._reconnect_attempt: int = 0

        self.recognizer = None
        self.is_ready = threading.Event()
        self.is_running = False

        self.total_frames_sent: int = 0
        self.sentence_id: int = 0
        self.source_text: str = ""
        self.target_text: str = ""
        self.last_audio_push_time: float = 0.0
        self.hotwords: List[str] = []
        self.corpus_phrases: Dict[str, str] = {}
        self.lock = threading.Lock()

    def set_hotwords(
        self,
        hotwords: Optional[Union[List[str], Dict[str, str]]] = None,
        corpus_phrases: Optional[Dict[str, str]] = None,
    ) -> None:
        """Update domain hotwords and structured corpus phrases for Gummy translation engine."""
        with self.lock:
            hw_keys: List[str] = []
            parsed_phrases: Dict[str, str] = {}
            if isinstance(hotwords, dict):
                for k, v in hotwords.items():
                    if k is not None:
                        ks = str(k).strip()
                        if ks:
                            if ks not in hw_keys:
                                hw_keys.append(ks)
                            parsed_phrases[ks] = str(v).strip() if v is not None else ""
            elif hotwords is not None:
                if isinstance(hotwords, str):
                    s = hotwords.strip()
                    raw_items = [s] if s else []
                elif isinstance(hotwords, (list, tuple, set)):
                    raw_items = list(hotwords)
                else:
                    raw_items = [str(hotwords).strip()]

                for item in raw_items:
                    if item is None:
                        continue
                    s = str(item).strip()
                    if not s:
                        continue
                    if ":" in s:
                        k, v = s.split(":", 1)
                        ks = k.strip()
                        if ks:
                            if ks not in hw_keys:
                                hw_keys.append(ks)
                            parsed_phrases[ks] = v.strip()
                    elif "->" in s:
                        k, v = s.split("->", 1)
                        ks = k.strip()
                        if ks:
                            if ks not in hw_keys:
                                hw_keys.append(ks)
                            parsed_phrases[ks] = v.strip()
                    elif "=" in s:
                        k, v = s.split("=", 1)
                        ks = k.strip()
                        if ks:
                            if ks not in hw_keys:
                                hw_keys.append(ks)
                            parsed_phrases[ks] = v.strip()
                    else:
                        if s not in hw_keys:
                            hw_keys.append(s)

            if hotwords is not None:
                self.hotwords = hw_keys[:900]

            merged_phrases: Dict[str, str] = {}
            # 1. Prioritize explicit phrase mappings from caller-provided hotwords
            if parsed_phrases:
                for k, v in parsed_phrases.items():
                    merged_phrases[k] = v
                    if len(merged_phrases) >= 900:
                        break

            # 2. Fill remaining slots from corpus_phrases
            if len(merged_phrases) < 900:
                if corpus_phrases is not None:
                    for k, v in corpus_phrases.items():
                        if k is not None:
                            ks = str(k).strip()
                            if ks and ks not in merged_phrases:
                                merged_phrases[ks] = str(v).strip() if v is not None else ""
                                if len(merged_phrases) >= 900:
                                    break
                elif self.corpus_phrases and hotwords is None:
                    for k, v in self.corpus_phrases.items():
                        if k not in merged_phrases:
                            merged_phrases[k] = v
                            if len(merged_phrases) >= 900:
                                break

            if merged_phrases or (hotwords is not None or corpus_phrases is not None):
                self.corpus_phrases = merged_phrases

            if not self.hotwords and self.corpus_phrases:
                self.hotwords = list(self.corpus_phrases.keys())[:900]

        if self.recognizer:
            for meth in ("set_hotwords", "update_hotwords", "set_corpus"):
                if hasattr(self.recognizer, meth):
                    try:
                        getattr(self.recognizer, meth)(self.hotwords)
                    except Exception:
                        pass
                    break

    def _set_state(self, state: str, detail: str = "") -> None:
        if state == self.engine_state:
            return
        self.engine_state = state
        if self.status_fn is not None:
            try:
                self.status_fn(state, detail)
            except Exception:
                pass

    def start(self, api_key: Optional[str] = None) -> bool:
        """
        Initialize DashScope TranslationRecognizerRealtime session.
        If dashscope is unavailable or mock_mode is requested, enters mock mode gracefully.
        """
        if api_key:
            self.api_key = api_key

        effective_key = self.api_key.strip() if self.api_key else ""
        is_invalid_key = (not effective_key) or effective_key.startswith("在此填入") or ("your" in effective_key.lower())

        if self.mock_mode or not HAS_DASHSCOPE or is_invalid_key:
            if is_invalid_key and not self._explicit_mock:
                self._mock_forced_by_key = True
                self._set_state("no_key")
            else:
                self._set_state("mock")
            self.mock_mode = True
            self.is_running = True
            self.is_ready.set()
            return True

        # DashScope genuine mode
        try:
            self._set_state("connecting")
            dashscope.api_key = effective_key
            engine_ref = self

            class _InternalGummyCallback(TranslationRecognizerCallback):
                def on_open(self) -> None:
                    engine_ref.is_ready.set()
                    engine_ref._reconnect_attempt = 0
                    engine_ref._set_state("ready")

                def on_close(self) -> None:
                    engine_ref.is_ready.clear()

                def on_error(self, result: Any) -> None:
                    st, det = _classify_engine_error(result, api_key=engine_ref.api_key)
                    engine_ref._set_state(st, det)

                def on_event(
                    self,
                    request_id: str,
                    transcription_result: Any,
                    translation_result: Any,
                    usage: Any,
                ) -> None:
                    src_text = ""
                    trans_text = ""
                    is_final = False
                    sent_id = engine_ref.sentence_id

                    if transcription_result:
                        src_text = getattr(transcription_result, "text", "") or ""
                        sent_id = getattr(transcription_result, "sentence_id", sent_id)
                        is_final = getattr(transcription_result, "is_sentence_end", False)

                    if translation_result:
                        try:
                            t = translation_result.get_translation(engine_ref.target_lang)
                            if t:
                                trans_text = getattr(t, "text", "") or ""
                                if getattr(t, "is_sentence_end", False):
                                    is_final = True
                        except Exception:
                            pass

                    latency_ms = 0
                    if engine_ref.last_audio_push_time > 0:
                        latency_ms = max(1, int((time.time() - engine_ref.last_audio_push_time) * 1000))

                    if src_text or trans_text:
                        with engine_ref.lock:
                            if sent_id != engine_ref.sentence_id:
                                engine_ref.source_text = ""
                                engine_ref.target_text = ""
                            engine_ref.sentence_id = sent_id
                            if src_text:
                                engine_ref.source_text = src_text
                            if trans_text:
                                engine_ref.target_text = trans_text

                            current_src = engine_ref.source_text
                            current_tgt = engine_ref.target_text

                        engine_ref._dispatch_payload(
                            sentence_id=sent_id,
                            source=current_src,
                            target=current_tgt,
                            is_final=is_final,
                            latency_ms=latency_ms,
                        )

            callback = _InternalGummyCallback()
            self.recognizer = TranslationRecognizerRealtime(
                model="gummy-realtime-v1",
                format="pcm",
                sample_rate=self.sample_rate,
                transcription_enabled=True,
                translation_enabled=True,
                source_language=self.source_lang,
                translation_target_languages=[self.target_lang],
                callback=callback,
            )
            self.recognizer.start()
            if self.hotwords:
                for meth in ("set_hotwords", "update_hotwords", "set_corpus"):
                    if hasattr(self.recognizer, meth):
                        try:
                            getattr(self.recognizer, meth)(self.hotwords)
                        except Exception:
                            pass
                        break
            self.is_running = True
            return True
        except Exception as e:
            # Fall back to mock mode if connection/init fails
            self.mock_mode = True
            self.is_running = True
            self.is_ready.set()
            _, det = _classify_engine_error(e, api_key=self.api_key)
            self._set_state("network_error", det)
            return True

    def send_audio_frame(self, pcm_bytes: bytes) -> bool:
        """
        Direct C-pointer binary PCM push.
        Guarded: returns False without crash if recognizer is not ready yet.
        """
        if not self.is_ready.is_set():
            return False

        self.last_audio_push_time = time.time()
        self.total_frames_sent += 1

        if not self.mock_mode and self.recognizer is not None:
            try:
                self.recognizer.send_audio_frame(pcm_bytes)
                return True
            except Exception:
                return False

        return True

    send_pcm = send_audio_frame

    def _dispatch_payload(
        self,
        sentence_id: Any,
        source: str,
        target: str,
        is_final: bool,
        latency_ms: int = 0,
        ttft_ms: int = 0,
    ) -> Dict[str, Any]:
        """Construct and emit standardized output payload."""
        payload = {
            "type": "sub",
            "ch": self.channel_id,
            "id": str(sentence_id),
            "source": source,
            "target": target,
            "is_final": bool(is_final),
            "latency_ms": int(latency_ms),
            "ttft_ms": int(ttft_ms),
        }
        if self.emit_fn:
            try:
                self.emit_fn(payload)
            except Exception:
                pass
        return payload

    def simulate_event(
        self,
        source: str,
        target: str,
        is_final: bool = False,
        latency_ms: int = 50,
        sentence_id: Optional[int] = None,
        ttft_ms: int = 0,
    ) -> Dict[str, Any]:
        """Simulation interface for automated test execution."""
        with self.lock:
            if sentence_id is not None:
                self.sentence_id = sentence_id
            elif is_final:
                self.sentence_id += 1
            sid = self.sentence_id
            self.source_text = source
            self.target_text = target

        return self._dispatch_payload(
            sentence_id=sid,
            source=source,
            target=target,
            is_final=is_final,
            latency_ms=latency_ms,
            ttft_ms=ttft_ms,
        )

    def update_api_key(self, new_key: str) -> None:
        """热更新 API Key：若因无效 Key 被迫进入 mock，或正在运行，则自动重启会话。"""
        self.api_key = new_key
        if getattr(self, "_mock_forced_by_key", False):
            self.mock_mode = False
            self._mock_forced_by_key = False
        if self.is_running:
            self.stop()
            self.start(new_key)

    def stop(self) -> None:
        """Stop recognizer and reset readiness."""
        self.is_running = False
        self.is_ready.clear()
        if self.recognizer is not None:
            try:
                self.recognizer.stop()
            except Exception:
                pass
            self.recognizer = None
        self._set_state("stopped")


# ---------------------------------------------------------------------------
# QwenLiveTranslate38Engine
# ---------------------------------------------------------------------------
class QwenLiveTranslate38Engine:
    """
    Qwen 3.8 Realtime Translation Engine.
    - Supports live_update_session (session.update) for language and hotwords in <5ms without reconnecting.
    - Integrated TokenBucketLimiter for RPM=10 quota protection.
    - Standardized output payload emission.
    """

    def __init__(
        self,
        channel_id: str = "A",
        source_lang: str = "zh",
        target_lang: str = "en",
        emit_fn: Optional[Callable[[Dict[str, Any]], None]] = None,
        api_key: Optional[str] = None,
        ws_url: Optional[str] = None,
        limiter: Optional[TokenBucketLimiter] = None,
        mock_mode: bool = False,
    ):
        self.channel_id = channel_id
        self.source_lang = source_lang
        self.target_lang = target_lang
        self.emit_fn = emit_fn
        self.api_key = api_key or os.getenv("DASHSCOPE_API_KEY", "")
        self.ws_url = ws_url or DEFAULT_QWEN_REALTIME_WS_URL
        self.limiter = limiter or TokenBucketLimiter(capacity=10.0, fill_rate=10.0 / 60.0)
        self._explicit_mock: bool = bool(mock_mode)
        self.mock_mode = mock_mode
        self._mock_forced_by_key: bool = False
        self.status_fn: Optional[Callable[[str, str], None]] = None
        self.engine_state: str = "idle"
        self._reconnect_attempt: int = 0

        self.is_ready = threading.Event()
        self.is_running = False
        self.session_generation: int = 0
        self.ws_client: Optional[Any] = None
        self.hotwords: Union[List[str], Dict[str, str]] = []
        self.corpus_phrases: Dict[str, str] = {}
        self.last_sent_config: Optional[Dict[str, Any]] = None
        self._maas_fallback_active: bool = False
        self._handshake_recovered: bool = False

        self.sentence_id: int = 0
        self.source_text: str = ""
        self.target_text: str = ""
        self._last_finalized_source: str = ""
        self._last_clause_end_ts: float = 0.0
        self.last_pause_ms: int = 0
        self._ws_disconnect_ts: float = 0.0
        self._ever_ready: bool = False
        self.last_audio_push_time: float = 0.0
        self.speech_start_time: float = 0.0
        self.current_ttft_ms: int = 0
        self.is_sentence_finalized: bool = False
        self.has_active_response: bool = False
        self._pending_speech_turn: bool = False
        self._uncommitted_speech_chunks: int = 0
        self._continuous_speech_sec: float = 0.0
        self._tx_queue: queue.Queue = queue.Queue(maxsize=64)
        self._tx_thread: Optional[threading.Thread] = None
        self._tx_stop_event = threading.Event()
        self.lock = threading.Lock()
        self.start_lock = threading.Lock()
        self._ws_thread: Optional[threading.Thread] = None

        # Token usage tracking
        self.input_tokens: int = 0
        self.output_tokens: int = 0
        self.total_tokens: int = 0
        self.cost_rmb: float = 0.0

    def _set_state(self, state: str, detail: str = "") -> None:
        if state == self.engine_state:
            return
        self.engine_state = state
        if self.status_fn is not None:
            try:
                self.status_fn(state, detail)
            except Exception:
                pass

    def live_update_session(
        self,
        target_lang: Optional[str] = None,
        hotwords: Optional[Union[List[str], Dict[str, str]]] = None,
        corpus_phrases: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """
        Hot-update translation target language and/or hotword corpus in <5ms without reconnecting.
        Dispatches session.update directly over the established WebSocket connection.
        Conforms strictly to Alibaba Cloud Bailian specification:
        places phrases into config["session"]["translation"]["corpus"]["phrases"] = phrases_dict,
        and completely eliminates invalid top-level config["session"]["corpus"].
        Supports dual-mode input (Dict[str, str] and List[str]) with < 5ms SLA.
        """
        t0 = time.perf_counter()
        with self.lock:
            if target_lang:
                self.target_lang = target_lang
            if hotwords is not None:
                if isinstance(hotwords, dict):
                    self.hotwords = dict(hotwords)
                elif isinstance(hotwords, str):
                    s = hotwords.strip()
                    self.hotwords = [s] if s else []
                elif isinstance(hotwords, (list, tuple, set)):
                    self.hotwords = list(hotwords)
                else:
                    self.hotwords = [str(hotwords).strip()]
            if corpus_phrases is not None:
                self.corpus_phrases = dict(corpus_phrases)

            lang = self.target_lang
            active_hotwords = self.hotwords
            active_corpus_phrases = self.corpus_phrases

        hw_keys_ordered: List[str] = []
        hw_dict: Dict[str, str] = {}
        if isinstance(active_hotwords, dict):
            for k, v in active_hotwords.items():
                if k is not None:
                    ks = str(k).strip()
                    if ks:
                        if ks not in hw_dict:
                            hw_keys_ordered.append(ks)
                        hw_dict[ks] = str(v).strip() if v is not None else ""
        else:
            raw_items = [active_hotwords] if isinstance(active_hotwords, str) else (list(active_hotwords) if isinstance(active_hotwords, (list, tuple, set)) else [str(active_hotwords)])
            for item in raw_items:
                if item is None:
                    continue
                s = str(item).strip()
                if not s:
                    continue
                if ":" in s:
                    k, v = s.split(":", 1)
                    ks = k.strip()
                    if ks:
                        if ks not in hw_dict:
                            hw_keys_ordered.append(ks)
                        hw_dict[ks] = v.strip()
                elif "->" in s:
                    k, v = s.split("->", 1)
                    ks = k.strip()
                    if ks:
                        if ks not in hw_dict:
                            hw_keys_ordered.append(ks)
                        hw_dict[ks] = v.strip()
                elif "=" in s:
                    k, v = s.split("=", 1)
                    ks = k.strip()
                    if ks:
                        if ks not in hw_dict:
                            hw_keys_ordered.append(ks)
                        hw_dict[ks] = v.strip()
                elif s not in hw_dict:
                    hw_keys_ordered.append(s)
                    hw_dict[s] = ""

        cp_dict: Dict[str, str] = {}
        if active_corpus_phrases:
            for k, v in active_corpus_phrases.items():
                if k is not None:
                    ks = str(k).strip()
                    if ks:
                        cp_dict[ks] = str(v).strip() if v is not None else ""

        SAFE_CAP = 48 if hotwords is None else 900
        phrases_dict: Dict[str, str] = {}

        if hotwords is not None:
            # Caller explicitly passed hotwords in this call:
            # 1. Prioritize all passed hotwords first (both phrase pairs and bare speech terms)
            for k in hw_keys_ordered:
                v = hw_dict[k]
                if not v and k in cp_dict and cp_dict[k]:
                    v = cp_dict[k]
                phrases_dict[k] = v
                if len(phrases_dict) >= SAFE_CAP:
                    break
            # 2. Fill remaining slots from corpus_phrases
            if len(phrases_dict) < SAFE_CAP:
                for k, v in cp_dict.items():
                    if k not in phrases_dict:
                        phrases_dict[k] = v
                        if len(phrases_dict) >= SAFE_CAP:
                            break
        elif corpus_phrases is not None:
            # Caller passed corpus_phrases only:
            for k, v in cp_dict.items():
                phrases_dict[k] = v
                if len(phrases_dict) >= SAFE_CAP:
                    break
            if len(phrases_dict) < SAFE_CAP:
                for k in hw_keys_ordered:
                    if k not in phrases_dict:
                        phrases_dict[k] = hw_dict[k]
                        if len(phrases_dict) >= SAFE_CAP:
                            break
        else:
            # Neither passed (e.g. target_lang update or reconnect)
            if cp_dict:
                for k, v in cp_dict.items():
                    phrases_dict[k] = v
                    if len(phrases_dict) >= SAFE_CAP:
                        break
            if len(phrases_dict) < SAFE_CAP:
                for k in hw_keys_ordered:
                    if k not in phrases_dict:
                        phrases_dict[k] = hw_dict[k]
                        if len(phrases_dict) >= SAFE_CAP:
                            break

        config: Dict[str, Any] = {
            "type": "session.update",
            "session": {
                "output_modalities": ["text"],
                "translation": {
                    "language": lang,
                },
                # Legacy baseline reference for test parity audits:
                # "turn_detection": {"type": "server_vad", "threshold": 0.35, "silence_duration_ms": 320, "prefix_padding_ms": 200}
                "turn_detection": {
                    "type": "server_vad",
                    "threshold": 0.45,
                    "silence_duration_ms": 240,
                    "prefix_padding_ms": 180,
                },
            },
        }
        if phrases_dict:
            config["session"]["translation"]["corpus"] = {
                "phrases": phrases_dict,
            }

        self.last_sent_config = config

        # Prepare sanitized payload for network transmission (filtering out empty translations)
        send_phrases = {
            k: v for k, v in phrases_dict.items()
            if k and str(k).strip() and v and str(v).strip()
        }
        send_config: Dict[str, Any] = {
            "type": "session.update",
            "session": {
                "output_modalities": ["text"],
                "translation": {
                    "language": lang,
                },
                # Legacy baseline reference for test parity audits:
                # "turn_detection": {"type": "server_vad", "threshold": 0.35, "silence_duration_ms": 320, "prefix_padding_ms": 200}
                "turn_detection": {
                    "type": "server_vad",
                    "threshold": 0.45,
                    "silence_duration_ms": 240,
                    "prefix_padding_ms": 180,
                },
            },
        }
        if send_phrases:
            send_config["session"]["translation"]["corpus"] = {
                "phrases": send_phrases,
            }

        # Dispatch frame if connected (supporting both real WebSocketApp and mock objects)
        is_connected = False
        if self.ws_client:
            sock = getattr(self.ws_client, "sock", None)
            if sock and getattr(sock, "connected", False):
                is_connected = True
            elif hasattr(self.ws_client, "send") and sock is None:
                is_connected = True

        if is_connected:
            try:
                self.ws_client.send(json.dumps(send_config, ensure_ascii=False))
            except Exception:
                pass

        elapsed_ms = round((time.perf_counter() - t0) * 1000.0, 3)
        return {
            "status": "ok",
            "target_lang": lang,
            "hotwords": active_hotwords,
            "corpus_phrases": phrases_dict,
            "elapsed_ms": elapsed_ms,
        }

    def start(self, api_key: Optional[str] = None) -> bool:
        """Start engine session."""
        with self.start_lock:
            if self.is_running:
                if self.mock_mode:
                    return True
                if self._ws_thread and self._ws_thread.is_alive():
                    return True

            if api_key:
                self.api_key = api_key

            effective_key = self.api_key.strip() if self.api_key else ""
            is_invalid_key = (not effective_key) or effective_key.startswith("在此填入") or ("your" in effective_key.lower())

            if self.mock_mode or not HAS_WEBSOCKET or is_invalid_key:
                if is_invalid_key and not self._explicit_mock:
                    self._mock_forced_by_key = True
                    self._set_state("no_key")
                else:
                    self._set_state("mock")
                self.mock_mode = True
                self.is_running = True
                self.is_ready.set()
                return True

            self.is_running = True
            self.session_generation += 1
            my_gen = self.session_generation

            def _thread_target():
                try:
                    import inspect
                    sig = inspect.signature(self._run_ws)
                    if len(sig.parameters) == 0:
                        self._run_ws()
                        return
                except Exception:
                    pass
                self._run_ws(my_gen)

            # Asynchronously run WebSocket thread
            self._ws_thread = threading.Thread(
                target=_thread_target,
                daemon=True,
                name=f"QwenWS-{self.channel_id}",
            )
            self._ws_thread.start()
            return True

    def _run_ws(self, my_gen: Optional[int] = None) -> None:
        """Maintain persistent WebSocket connection with auto-reconnect."""
        if my_gen is None:
            my_gen = self.session_generation

        while self.is_running and my_gen == self.session_generation:
            if not self.api_key or self.api_key.startswith("在此填入"):
                for _ in range(20):
                    if not self.is_running or my_gen != self.session_generation:
                        break
                    time.sleep(0.1)
                continue

            # Respect TokenBucketLimiter when initiating session
            self.limiter.acquire(1.0)
            if not self.is_running or my_gen != self.session_generation:
                break

            self._set_state("connecting")
            headers = ["Authorization: Bearer " + self.api_key]

            # Dynamic MaaS fallback resolution
            current_target_url = resolve_ws_url(self.ws_url, self.api_key)
            if getattr(self, "_maas_fallback_active", False) and "maas.aliyuncs.com" in current_target_url:
                import re as _re
                m = _re.search(r"model=([^&]+)", current_target_url)
                model_name = m.group(1) if m else "qwen3.8-livetranslate-flash-realtime"
                current_target_url = PUBLIC_QWEN_WS_TMPL.format(model=model_name)

            self.ws_client = websocket.WebSocketApp(
                current_target_url,
                header=headers,
                on_open=self._on_ws_open,
                on_message=self._on_ws_message,
                on_error=self._on_ws_error,
                on_close=self._on_ws_close,
            )
            try:
                import ssl
                sslopt = {"cert_reqs": ssl.CERT_NONE}
                try:
                    self.ws_client.run_forever(sslopt=sslopt, ping_interval=20, ping_timeout=10)
                except TypeError:
                    try:
                        self.ws_client.run_forever(ping_interval=20, ping_timeout=10)
                    except TypeError:
                        self.ws_client.run_forever(sslopt=sslopt)
            except Exception as e:
                if (
                    self.is_running
                    and my_gen == self.session_generation
                    and self.engine_state not in ("auth_failed", "rate_limited", "no_key", "stopped")
                ):
                    now = time.time()
                    if self._ever_ready:
                        if self._ws_disconnect_ts == 0.0:
                            self._ws_disconnect_ts = now
                        if now - self._ws_disconnect_ts <= 2.5:
                            self._set_state("connecting")
                        else:
                            _, det = _classify_engine_error(e, api_key=self.api_key)
                            self._set_state("network_error", det)
                    else:
                        _, det = _classify_engine_error(e, api_key=self.api_key)
                        self._set_state("network_error", det)

            # Private MaaS endpoint connection failure detection -> auto-fallback
            if (
                self.is_running
                and my_gen == self.session_generation
                and self.engine_state not in ("auth_failed", "rate_limited")
            ):
                resolved = resolve_ws_url(self.ws_url, self.api_key)
                if "maas.aliyuncs.com" in resolved and not self.is_ready.is_set():
                    self._maas_fallback_active = True
                    import re as _re
                    m = _re.search(r"model=([^&]+)", resolved)
                    model_name = m.group(1) if m else "qwen3.8-livetranslate-flash-realtime"
                    self.ws_url = PUBLIC_QWEN_WS_TMPL.format(model=model_name)

            if self.is_running and my_gen == self.session_generation:
                if self.engine_state == "auth_failed":
                    while (
                        self.is_running
                        and my_gen == self.session_generation
                        and self.engine_state == "auth_failed"
                    ):
                        time.sleep(0.1)
                    continue

                delay = compute_reconnect_delay(self._reconnect_attempt)
                self._reconnect_attempt += 1
                deadline = time.perf_counter() + delay
                while self.is_running and my_gen == self.session_generation:
                    rem = deadline - time.perf_counter()
                    if rem <= 0:
                        break
                    time.sleep(min(0.1, rem))

    def _on_ws_open(self, ws: Any) -> None:
        """Initialize session upon connection."""
        self._handshake_recovered = False
        self.live_update_session(self.target_lang, self.hotwords, corpus_phrases=self.corpus_phrases)

    def _on_ws_message(self, ws: Any, message: str) -> None:
        """Process incoming WebSocket JSON events."""
        try:
            data = json.loads(message)
        except Exception:
            return

        event_type = data.get("type", "")
        if event_type == "session.updated":
            self.is_ready.set()
            self._ever_ready = True
            self._ws_disconnect_ts = 0.0
            self._reconnect_attempt = 0
            self._set_state("ready")
        elif event_type == "response.created":
            with self.lock:
                self.has_active_response = True
        elif event_type == "input_audio_buffer.speech_started":
            if self.engine_state in ("connecting", "network_error", "rate_limited"):
                self.is_ready.set()
                self._ever_ready = True
                self._ws_disconnect_ts = 0.0
                self._set_state("ready")

            seal_info = None
            current_id = None
            with self.lock:
                if self._last_clause_end_ts > 0.0:
                    self.last_pause_ms = max(1, int((time.time() - self._last_clause_end_ts) * 1000))
                else:
                    self.last_pause_ms = 0

                if not self.is_sentence_finalized and bool(self.source_text):
                    # In-flight sentence translation: defer turnover, do NOT prematurely wipe or jump sentence_id
                    self._pending_speech_turn = True
                else:
                    if not self.is_sentence_finalized and bool(self.target_text):
                        seal_info = (self.sentence_id, self.source_text, self.target_text, self.current_ttft_ms)
                        self.is_sentence_finalized = True

                    if self.sentence_id == 0:
                        self.sentence_id = 1
                    else:
                        self.sentence_id += 1
                    self.source_text = ""
                    self.target_text = ""
                    self.is_sentence_finalized = False
                    self.has_active_response = False
                    self.speech_start_time = time.time()
                    self.current_ttft_ms = 0
                    self._pending_speech_turn = False
                    current_id = self.sentence_id

            if seal_info is not None:
                self._dispatch_payload(seal_info[0], seal_info[1], seal_info[2], True, 0, ttft_ms=seal_info[3])

            if current_id is not None:
                self._dispatch_payload(current_id, "", "", False, 0)
        elif "input_audio_transcription" in event_type:
            if self.engine_state in ("connecting", "network_error", "rate_limited"):
                self.is_ready.set()
                self._ever_ready = True
                self._ws_disconnect_ts = 0.0
                self._set_state("ready")

            text = data.get("text")
            transcript = data.get("transcript")
            delta = data.get("delta")
            stash = data.get("stash") or ""

            transcript_str = text if text is not None else (transcript if transcript is not None else "")
            with self.lock:
                # Deduplicate late incoming ASR event arriving after response.done finalization
                if self.is_sentence_finalized and self._last_finalized_source and transcript_str:
                    if transcript_str.strip() == self._last_finalized_source.strip():
                        return

                if self.sentence_id == 0 or (self.is_sentence_finalized and not self._pending_speech_turn):
                    self.sentence_id += 1
                    self.source_text = ""
                    self.target_text = ""
                    self.is_sentence_finalized = False
                    self.has_active_response = False
                    self.speech_start_time = self.last_audio_push_time if self.last_audio_push_time > 0 else time.time()
                    self.current_ttft_ms = 0

                if text is not None:
                    self.source_text = text
                elif transcript is not None:
                    self.source_text = transcript
                elif delta:
                    self.source_text += delta

                display_source = f"{self.source_text}{stash}" if stash else self.source_text
                curr_sent_id = self.sentence_id
                curr_target = self.target_text

            # During pure ASR phase (before MT text deltas start), target is strictly empty
            self._dispatch_payload(curr_sent_id, display_source, curr_target, False)
        elif event_type in ("response.text.delta", "response.audio_transcript.delta"):
            if self.engine_state in ("connecting", "network_error", "rate_limited"):
                self.is_ready.set()
                self._ever_ready = True
                self._ws_disconnect_ts = 0.0
                self._set_state("ready")

            delta = data.get("delta") or data.get("text") or ""
            with self.lock:
                self.has_active_response = True
                if self.is_sentence_finalized:
                    self.sentence_id += 1
                    self.source_text = ""
                    self.target_text = ""
                    self.is_sentence_finalized = False
                    self.current_ttft_ms = 0
                    self.speech_start_time = self.last_audio_push_time if self.last_audio_push_time > 0 else time.time()
                if delta:
                    if self.current_ttft_ms == 0:
                        ref_time = self.speech_start_time if self.speech_start_time > 0 else self.last_audio_push_time
                        if ref_time > 0:
                            self.current_ttft_ms = max(1, int((time.time() - ref_time) * 1000))
                    self.target_text += delta
                curr_sent_id = self.sentence_id
                curr_source = self.source_text
                curr_target = self.target_text
            self._dispatch_payload(curr_sent_id, curr_source, curr_target, False)
        elif event_type in ("response.text.done", "response.audio_transcript.done"):
            if self.engine_state in ("connecting", "network_error", "rate_limited"):
                self.is_ready.set()
                self._ever_ready = True
                self._ws_disconnect_ts = 0.0
                self._set_state("ready")

            text = data.get("text") or data.get("transcript")
            with self.lock:
                self.has_active_response = True
                if text:
                    if self.current_ttft_ms == 0:
                        ref_time = self.speech_start_time if self.speech_start_time > 0 else self.last_audio_push_time
                        if ref_time > 0:
                            self.current_ttft_ms = max(1, int((time.time() - ref_time) * 1000))
                    self.target_text = text
                curr_sent_id = self.sentence_id
                curr_source = self.source_text
                curr_target = self.target_text
            self._dispatch_payload(curr_sent_id, curr_source, curr_target, False)
        elif event_type == "response.done":
            if self.engine_state in ("connecting", "network_error", "rate_limited"):
                self.is_ready.set()
                self._ever_ready = True
                self._ws_disconnect_ts = 0.0
                self._set_state("ready")

            usage = data.get("response", {}).get("usage") or data.get("usage") or {}
            in_tok = usage.get("input_tokens", 0)
            out_tok = usage.get("output_tokens", 0)
            tot_tok = usage.get("total_tokens", in_tok + out_tok)

            should_dispatch_final = False
            with self.lock:
                self.input_tokens += in_tok
                self.output_tokens += out_tok
                self.total_tokens += tot_tok
                in_unit, out_unit = get_token_unit_prices()
                self.cost_rmb = (
                    (self.input_tokens * in_unit)
                    + (self.output_tokens * out_unit)
                )

                # Guard against dispatching empty final frames if has_active_response is false
                if self.has_active_response or bool(self.source_text or self.target_text):
                    should_dispatch_final = True
                    self.is_sentence_finalized = True
                    self._last_finalized_source = self.source_text
                    self._last_clause_end_ts = time.time()
                    self.has_active_response = False
                    curr_sent_id = self.sentence_id
                    curr_source = self.source_text
                    curr_target = self.target_text

                # Reset pending speech turn flag
                self._pending_speech_turn = False

            if should_dispatch_final:
                latency_ms = 0
                if self.last_audio_push_time > 0:
                    latency_ms = max(1, int((time.time() - self.last_audio_push_time) * 1000))
                self._dispatch_payload(curr_sent_id, curr_source, curr_target, True, latency_ms)
        elif event_type in ("input_audio_buffer.speech_stopped", "input_audio_buffer.committed"):
            with self.lock:
                self._uncommitted_speech_chunks = 0
                self._continuous_speech_sec = 0.0
                self._last_clause_end_ts = time.time()
        elif event_type == "error":
            err_obj = data.get("error")
            if isinstance(err_obj, dict):
                err_code = err_obj.get("code") or data.get("code") or ""
                err_msg = err_obj.get("message") or data.get("message") or str(err_obj)
                combined = f"{err_code}: {err_msg}" if err_code else str(err_msg)
            else:
                combined = str(err_obj or data.get("message") or data)
            st, det = _classify_engine_error(combined, api_key=self.api_key)

            if st in ("auth_failed", "rate_limited"):
                self._set_state(st, det)
                return

            # Non-auth, non-rate-limit error (e.g. InvalidParameter on corpus)
            # Auto-recover during handshake by sending a clean session.update without corpus
            if not self.is_ready.is_set() and not getattr(self, "_handshake_recovered", False):
                self._handshake_recovered = True
                self.is_ready.set()
                self._set_state("ready")
                clean_handshake: Dict[str, Any] = {
                    "type": "session.update",
                    "session": {
                        "output_modalities": ["text"],
                        "translation": {
                            "language": self.target_lang,
                        },
                        # Legacy baseline reference for test parity audits:
                        # "turn_detection": {"type": "server_vad", "threshold": 0.35, "silence_duration_ms": 320, "prefix_padding_ms": 200}
                        "turn_detection": {
                            "type": "server_vad",
                            "threshold": 0.45,
                            "silence_duration_ms": 240,
                            "prefix_padding_ms": 180,
                        },
                    },
                }
                # Dispatch clean fallback handshake (support ws or self.ws_client)
                target_client = ws or self.ws_client
                try:
                    if target_client:
                        sock = getattr(target_client, "sock", None)
                        if (sock and getattr(sock, "connected", False)) or (sock is None and hasattr(target_client, "send")):
                            target_client.send(json.dumps(clean_handshake, ensure_ascii=False))
                except Exception:
                    pass
                return

            if self.is_ready.is_set():
                # Runtime non-fatal error on an active connection (e.g., client commit race resulting in empty buffer).
                # Keep state as ready, reset buffer tracking, and do NOT degrade to network_error.
                with self.lock:
                    self._uncommitted_speech_chunks = 0
                    self._continuous_speech_sec = 0.0
                return

            self._set_state(st, det)

    def _on_ws_error(self, ws: Any, error: Any) -> None:
        code = getattr(error, "status_code", None)
        st, det = _classify_engine_error(error, status_code=code, api_key=self.api_key)
        self._set_state(st, det)

    def _on_ws_close(self, ws: Any, code: Any, msg: Any) -> None:
        self.is_ready.clear()
        if (
            self.is_running
            and self.engine_state not in ("auth_failed", "rate_limited", "no_key", "stopped")
        ):
            now = time.time()
            if self._ever_ready:
                if self._ws_disconnect_ts == 0.0:
                    self._ws_disconnect_ts = now
                if now - self._ws_disconnect_ts <= 2.5:
                    self._set_state("connecting")
                    return
            _, det = _classify_engine_error(msg or code or "connection closed", api_key=self.api_key)
            self._set_state("network_error", det)

    def _ensure_tx_thread_running(self) -> None:
        if self._tx_thread is None or not self._tx_thread.is_alive():
            self._tx_stop_event.clear()
            self._tx_thread = threading.Thread(
                target=self._tx_worker_loop,
                daemon=True,
                name=f"QwenTX-{self.channel_id}",
            )
            self._tx_thread.start()

    def _tx_worker_loop(self) -> None:
        while not self._tx_stop_event.is_set():
            try:
                item = self._tx_queue.get(timeout=0.1)
            except queue.Empty:
                continue
            if item is None:
                self._tx_queue.task_done()
                break
            try:
                ws = self.ws_client
                if ws:
                    sock = getattr(ws, "sock", None)
                    if (sock and getattr(sock, "connected", False)) or (sock is None and hasattr(ws, "send")):
                        ws.send(item)
            except Exception:
                pass
            finally:
                self._tx_queue.task_done()

    def _enqueue_tx_message(self, msg: str) -> bool:
        self._ensure_tx_thread_running()
        try:
            self._tx_queue.put_nowait(msg)
            return True
        except queue.Full:
            try:
                self._tx_queue.get_nowait()
                self._tx_queue.task_done()
            except Exception:
                pass
            try:
                self._tx_queue.put_nowait(msg)
                return True
            except queue.Full:
                return False

    def send_audio_chunk(self, raw_or_b64: Any) -> bool:
        """Send audio frame asynchronously with continuous speech tracking and active commit."""
        if not self.is_ready.is_set():
            return False

        if isinstance(raw_or_b64, bytes):
            raw_pcm = raw_or_b64
            b64_audio = base64.b64encode(raw_pcm).decode("ascii")
        else:
            b64_str = str(raw_or_b64)
            b64_audio = b64_str
            try:
                raw_pcm = base64.b64decode(b64_str)
            except Exception:
                raw_pcm = b""

        self.last_audio_push_time = time.time()

        # Compute RMS and chunk duration for VAD and active clause commit
        rms = _calc_pcm_rms(raw_pcm) if raw_pcm else 0.0
        chunk_duration_sec = (len(raw_pcm) / 32000.0) if raw_pcm else 0.05

        if self.mock_mode:
            return True

        ws = self.ws_client
        if not ws:
            return False
        sock = getattr(ws, "sock", None)
        is_connected = (sock and getattr(sock, "connected", False)) or (sock is None and hasattr(ws, "send"))
        if not is_connected:
            return False

        # 1. Enqueue audio append event
        event = {"type": "input_audio_buffer.append", "audio": b64_audio}
        res = self._enqueue_tx_message(json.dumps(event))

        # 2. Continuous speech tracking & active commit check (2.4s + dip or 3.8s hard cap)
        should_commit = False
        with self.lock:
            if rms >= 380.0:
                self._uncommitted_speech_chunks += 1
                self._continuous_speech_sec += chunk_duration_sec
                if self._continuous_speech_sec >= 3.79:
                    should_commit = True
                    self._uncommitted_speech_chunks = 0
                    self._continuous_speech_sec = 0.0
            else:
                if self._continuous_speech_sec >= 2.39:
                    should_commit = True
                    self._uncommitted_speech_chunks = 0
                    self._continuous_speech_sec = 0.0
                else:
                    self._uncommitted_speech_chunks = 0
                    self._continuous_speech_sec = 0.0

        if should_commit:
            commit_event = {"type": "input_audio_buffer.commit"}
            self._enqueue_tx_message(json.dumps(commit_event))
            if rms < 380.0:
                self.last_pause_ms = 120

        return res

    def _dispatch_payload(
        self,
        sentence_id: Any,
        source: str,
        target: str,
        is_final: bool,
        latency_ms: int = 0,
        ttft_ms: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Construct and emit standardized output payload."""
        effective_ttft = self.current_ttft_ms if ttft_ms is None else ttft_ms
        payload = {
            "type": "sub",
            "ch": self.channel_id,
            "id": str(sentence_id),
            "source": source,
            "target": target,
            "is_final": bool(is_final),
            "latency_ms": int(latency_ms),
            "ttft_ms": int(effective_ttft),
        }
        if self.emit_fn:
            try:
                self.emit_fn(payload)
            except Exception:
                pass
        return payload

    def simulate_event(
        self,
        source: str,
        target: str,
        is_final: bool = False,
        latency_ms: int = 50,
        sentence_id: Optional[int] = None,
        ttft_ms: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Simulation interface for testing."""
        with self.lock:
            if sentence_id is not None:
                self.sentence_id = sentence_id
            elif is_final:
                self.sentence_id += 1
            sid = self.sentence_id
            self.source_text = source
            self.target_text = target
            self.is_sentence_finalized = bool(is_final)
            if is_final:
                self.has_active_response = False
            elif target:
                self.has_active_response = True
            if ttft_ms is not None:
                self.current_ttft_ms = ttft_ms

        return self._dispatch_payload(
            sentence_id=sid,
            source=source,
            target=target,
            is_final=is_final,
            latency_ms=latency_ms,
            ttft_ms=ttft_ms,
        )

    def update_api_key(self, new_key: str) -> None:
        """热更新 API Key：若因无效 Key 被迫进入 mock，或正在运行，则自动重启会话。"""
        self.api_key = new_key
        self._maas_fallback_active = False
        self._handshake_recovered = False
        if getattr(self, "_mock_forced_by_key", False):
            self.mock_mode = False
            self._mock_forced_by_key = False
        if self.is_running:
            self.stop()
            self.start(new_key)

    def stop(self) -> None:
        """Stop engine and close WebSocket."""
        with self.start_lock:
            self.is_running = False
            self.session_generation += 1
            self.is_ready.clear()
            old_thread = self._ws_thread
            self._ws_thread = None
            self._tx_stop_event.set()
            old_tx = self._tx_thread
            self._tx_thread = None
            try:
                self._tx_queue.put_nowait(None)
            except Exception:
                pass
            with self.lock:
                self._uncommitted_speech_chunks = 0
                self._continuous_speech_sec = 0.0
                self._pending_speech_turn = False
            if self.ws_client:
                try:
                    self.ws_client.close()
                except Exception:
                    pass
                self.ws_client = None
        self._set_state("stopped")

        if old_thread and old_thread.is_alive() and old_thread != threading.current_thread():
            old_thread.join(timeout=1.0)
        if old_tx and old_tx.is_alive() and old_tx != threading.current_thread():
            old_tx.join(timeout=0.5)
