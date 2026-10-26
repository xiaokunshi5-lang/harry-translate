"""
Test Harness for Apple-Style Floating Simultaneous Translation HUD E2E Test Suite.
Provides lightweight, zero-bloat ASGI client, DOM inspectors, native window inspectors,
and mathematical WCAG contrast calculators.
"""
import os
import sys
import re
import json
import time
import math
import asyncio
import unittest
from typing import Dict, Any, Optional, Tuple, List

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


class ASGIResponse:
    """Represents an HTTP response from an ASGI application."""
    def __init__(self, status_code: int, headers: List[Tuple[bytes, bytes]], body: bytes):
        self.status_code = status_code
        self.raw_headers = headers
        self.headers = {k.decode("utf-8").lower(): v.decode("utf-8") for k, v in headers}
        self.content = body
        self.text = body.decode("utf-8", errors="replace")

    def json(self) -> Any:
        return json.loads(self.text)


class FastAPITestClient:
    """
    Lightweight, synchronous wrapper around FastAPI ASGI app.
    Executes in-memory without spawning network sockets or background server threads.
    """
    def __init__(self, app):
        self.app = app

    def request(
        self,
        method: str,
        path: str,
        headers: Optional[Dict[str, str]] = None,
        query_params: Optional[Dict[str, Any]] = None,
        json_data: Optional[Any] = None,
        body_bytes: Optional[bytes] = None,
        **kwargs
    ) -> ASGIResponse:
        if "json" in kwargs and kwargs["json"] is not None:
            json_data = kwargs["json"]
        method = method.upper()
        norm_headers = []
        if headers:
            for k, v in headers.items():
                norm_headers.append((k.lower().encode("utf-8"), v.encode("utf-8")))

        norm_headers.append((b"host", b"testserver"))

        if json_data is not None:
            body_bytes = json.dumps(json_data).encode("utf-8")
            norm_headers.append((b"content-type", b"application/json"))

        if body_bytes is None:
            body_bytes = b""

        query_string = b""
        if query_params:
            from urllib.parse import urlencode
            query_string = urlencode(query_params).encode("utf-8")
        elif "?" in path:
            path_part, qs = path.split("?", 1)
            path = path_part
            query_string = qs.encode("utf-8")

        scope = {
            "type": "http",
            "asgi": {"version": "3.0"},
            "http_version": "1.1",
            "method": method,
            "path": path,
            "raw_path": path.encode("utf-8"),
            "query_string": query_string,
            "headers": norm_headers,
            "server": ("127.0.0.1", 8000),
            "client": ("127.0.0.1", 50000),
        }

        response_status = 500
        response_headers = []
        response_body_chunks = []

        async def receive():
            nonlocal body_bytes
            data = body_bytes
            body_bytes = b""
            return {
                "type": "http.request",
                "body": data,
                "more_body": False,
            }

        async def send(message):
            nonlocal response_status, response_headers, response_body_chunks
            msg_type = message.get("type")
            if msg_type == "http.response.start":
                response_status = message.get("status", 500)
                response_headers = message.get("headers", [])
            elif msg_type == "http.response.body":
                response_body_chunks.append(message.get("body", b""))

        async def runner():
            await self.app(scope, receive, send)

        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        if loop.is_running():
            # If called inside an existing running loop (e.g. pytest-asyncio)
            # Create a new loop in another thread or task
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                pool.submit(lambda: asyncio.run(runner())).result()
        else:
            loop.run_until_complete(runner())

        full_body = b"".join(response_body_chunks)
        return ASGIResponse(response_status, response_headers, full_body)

    def get(self, path: str, **kwargs) -> ASGIResponse:
        return self.request("GET", path, **kwargs)

    def post(self, path: str, **kwargs) -> ASGIResponse:
        return self.request("POST", path, **kwargs)

    def head(self, path: str, **kwargs) -> ASGIResponse:
        return self.request("HEAD", path, **kwargs)


class DOMInspector:
    """Parses and inspects HTML/CSS DOM structures for floating HUD."""
    @staticmethod
    def get_float_ui_content() -> Optional[str]:
        path = os.path.join(PROJECT_ROOT, "float_ui.html")
        if not os.path.exists(path):
            return None
        with open(path, "r", encoding="utf-8") as f:
            return f.read()

    @staticmethod
    def get_index_content() -> str:
        path = os.path.join(PROJECT_ROOT, "index.html")
        with open(path, "r", encoding="utf-8") as f:
            return f.read()

    @classmethod
    def has_element_by_id(cls, html_content: str, element_id: str) -> bool:
        pattern = rf'id=[\'"]{re.escape(element_id)}[\'"]'
        return bool(re.search(pattern, html_content))

    @classmethod
    def has_class(cls, html_content: str, class_name: str) -> bool:
        pattern = rf'class=[\'"][^\'"]*\b{re.escape(class_name)}\b[^\'"]*[\'"]'
        return bool(re.search(pattern, html_content))

    @staticmethod
    def calculate_relative_luminance(r: int, g: int, b: int) -> float:
        """Calculates WCAG 2.1 relative luminance for sRGB."""
        def channel_lum(c: int) -> float:
            c_norm = c / 255.0
            if c_norm <= 0.03928:
                return c_norm / 12.92
            else:
                return ((c_norm + 0.055) / 1.055) ** 2.4

        rl = channel_lum(r)
        gl = channel_lum(g)
        bl = channel_lum(b)
        return 0.2126 * rl + 0.7152 * gl + 0.0722 * bl

    @classmethod
    def calculate_contrast_ratio(cls, rgb1: Tuple[int, int, int], rgb2: Tuple[int, int, int]) -> float:
        """Calculates WCAG 2.1 contrast ratio between two colors (>= 7.0 for AAA)."""
        lum1 = cls.calculate_relative_luminance(*rgb1)
        lum2 = cls.calculate_relative_luminance(*rgb2)
        brightest = max(lum1, lum2)
        darkest = min(lum1, lum2)
        return (brightest + 0.05) / (darkest + 0.05)


class DesktopAppInspector:
    """Inspects float_app.py and native desktop window configuration."""
    @staticmethod
    def get_source() -> Optional[str]:
        path = os.path.join(PROJECT_ROOT, "float_app.py")
        if not os.path.exists(path):
            return None
        with open(path, "r", encoding="utf-8") as f:
            return f.read()


class ScriptInspector:
    """Inspects launch and maintenance scripts."""
    @staticmethod
    def get_content(filename: str) -> Optional[str]:
        path = os.path.join(PROJECT_ROOT, filename)
        if not os.path.exists(path):
            return None
        with open(path, "r", encoding="utf-8") as f:
            return f.read()


class BaseE2ETest(unittest.TestCase):
    """Base class for all E2E test cases with metadata tagging."""
    tier: int = 1
    feature_id: int = 1
    milestone: str = "M1"

    @classmethod
    def get_client(cls) -> FastAPITestClient:
        import server
        return FastAPITestClient(server.app)

    def is_milestone_implemented(self) -> bool:
        """Determines if the target milestone deliverable is present."""
        if self.milestone == "M1":
            # Feature 1-4: AudioCaptureManager and GET /hud in server.py
            import server
            return hasattr(server, "AudioCaptureManager") or os.path.exists(os.path.join(PROJECT_ROOT, "docs", "AUDIO_SETUP_GUIDE.md"))
        elif self.milestone == "M2":
            return os.path.exists(os.path.join(PROJECT_ROOT, "float_ui.html"))
        elif self.milestone == "M3":
            return os.path.exists(os.path.join(PROJECT_ROOT, "float_app.py"))
        elif self.milestone == "M4":
            return os.path.exists(os.path.join(PROJECT_ROOT, "start.sh"))
        elif self.milestone == "M5":
            return True
        return True
