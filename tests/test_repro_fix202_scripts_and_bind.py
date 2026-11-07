#!/usr/bin/env python3
"""
【复现测试】FIX-202:
- R1: Windows .bat 括号块内未转义括号语法炸弹检测
- R3: Windows 5 个启动 .bat 自动复制 .env.example、自动初始化 .venv 及 wmic/powershell 兼容
- R4: macOS 启动脚本 PyAudio/portaudio 安装失败 brew 自愈兜底
- R7: server.py 默认监听 127.0.0.1 (支持 HOST 环境变量覆盖)
"""
import os
import re
import subprocess
import unittest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

WIN_LAUNCH_BATS = [
    "启动悬浮同传.bat",
    "启动双悬浮同传.bat",
    "启动悬浮同传_中译英.bat",
    "启动悬浮同传_英译中.bat",
    "启动同传系统.bat",
]

MAC_INSTALL_SCRIPTS = [
    "start.sh",
    "启动悬浮同传.command",
    "启动悬浮同传_中译英.command",
    "启动悬浮同传_英译中.command",
    "启动双悬浮同传.command",
]


class TestReproFix202(unittest.TestCase):
    def test_r1_no_unescaped_parens_inside_bat_if_blocks(self):
        """R1: .bat 文件的 (...) 代码块内部的 echo 语句不得包含未用 ^ 转义的括号。"""
        for name in WIN_LAUNCH_BATS:
            path = os.path.join(PROJECT_ROOT, name)
            with open(path, "r", encoding="utf-8") as f:
                lines = f.readlines()

            depth = 0
            for lineno, raw in enumerate(lines, 1):
                line = raw.strip()
                if not line or line.upper().startswith("REM ") or line.startswith("::"):
                    continue
                if depth > 0 and line.lower().startswith("echo "):
                    # 去掉已转义的 ^( 和 ^) 后，不得再出现裸 ( 或 )
                    cleaned = line.replace("^(", "").replace("^)", "")
                    self.assertNotIn(
                        ")",
                        cleaned,
                        f"{name}:{lineno} 在括号块内部含有未转义的 ')': {line}",
                    )
                # 统计块级括号深度（忽略已转义的 ^( ^)）
                structural = line.replace("^(", "").replace("^)", "")
                depth += structural.count("(") - structural.count(")")

    def test_r3_windows_bats_auto_bootstrap_env_and_venv(self):
        """R3: 全部 5 个 Windows 启动 .bat 必须支持自动复制 .env.example 与自动创建 .venv。"""
        for name in WIN_LAUNCH_BATS:
            path = os.path.join(PROJECT_ROOT, name)
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()
            self.assertIn(
                ".env.example",
                content,
                f"{name} 缺少从 .env.example 自动复制生成 .env 的逻辑",
            )
            self.assertIn(
                "venv .venv",
                content,
                f"{name} 缺少自动创建 .venv 虚拟环境的逻辑",
            )
            self.assertIn(
                "requirements.txt",
                content,
                f"{name} 缺少自动安装 requirements.txt 的逻辑",
            )

    def test_r3_wmic_has_win11_24h2_fallback(self):
        """R3: 启动悬浮同传.bat 等脚本清理孤儿进程需兼容 Win11 24H2 (where wmic 或 powershell 兜底)。"""
        for name in [
            "启动悬浮同传.bat",
            "启动双悬浮同传.bat",
            "启动悬浮同传_中译英.bat",
            "启动悬浮同传_英译中.bat",
        ]:
            path = os.path.join(PROJECT_ROOT, name)
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()
            self.assertTrue(
                "where wmic" in content.lower() or "powershell" in content.lower(),
                f"{name} 缺少 Win11 24H2 兼容的进程清理逻辑",
            )

    def test_r4_mac_scripts_have_portaudio_auto_heal_and_valid_syntax(self):
        """R4: macOS 5 个含 pip install 的脚本需具备 portaudio 自愈逻辑，且全部通过 bash -n / zsh -n。"""
        for name in MAC_INSTALL_SCRIPTS:
            path = os.path.join(PROJECT_ROOT, name)
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()
            self.assertIn(
                "portaudio",
                content,
                f"{name} 缺少 brew install portaudio 自愈兜底逻辑",
            )
            for shell in ("bash", "zsh"):
                p = subprocess.run([shell, "-n", path], capture_output=True, text=True)
                self.assertEqual(p.returncode, 0, f"{shell} -n 语法检查失败 ({name}): {p.stderr}")

    def test_r7_server_default_host_is_loopback_configurable(self):
        """R7: server.py 默认监听 127.0.0.1 且支持 HOST 环境变量覆盖；.env.example 包含 HOST 说明。"""
        server_path = os.path.join(PROJECT_ROOT, "server.py")
        with open(server_path, "r", encoding="utf-8") as f:
            srv = f.read()
        self.assertRegex(
            srv,
            r'HOST\s*=\s*os\.getenv\(\s*["\']HOST["\']\s*,\s*["\']127\.0\.0\.1["\']\s*\)',
            "server.py 必须定义 HOST = os.getenv('HOST', '127.0.0.1')",
        )
        self.assertNotIn(
            'uvicorn.run(app, host="0.0.0.0"',
            srv,
            "server.py 不得硬编码 uvicorn.run(..., host='0.0.0.0')",
        )

        env_ex_path = os.path.join(PROJECT_ROOT, ".env.example")
        with open(env_ex_path, "r", encoding="utf-8") as f:
            env_ex = f.read()
        self.assertIn("HOST=127.0.0.1", env_ex, ".env.example 必须包含 HOST=127.0.0.1 默认配置")


if __name__ == "__main__":
    unittest.main()
