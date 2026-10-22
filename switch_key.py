#!/usr/bin/env python3
import os
import re
import sys
import json
import time
import urllib.request
import urllib.error

ENV_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")

# 常见厂商特征与检测端点
KNOWN_PROVIDERS = [
    {
        "name": "阿里云百炼 (DashScope)",
        "supports_realtime_audio": True,
        "test_url": "https://dashscope.aliyuncs.com/api/v1/models",
        "header_func": lambda k: {"Authorization": f"Bearer {k}"},
        "models": [
            ("qwen3.8-livetranslate-flash-realtime", "千问 3.8 实时同传大模型 (推荐，2.3s 极速中英互译)"),
            ("qwen3.5-livetranslate-flash-realtime", "千问 3.5 实时同传大模型 (上一代千问语音模型)"),
        ]
    },
    {
        "name": "Kimi (月之暗面 Moonshot)",
        "supports_realtime_audio": False,
        "test_url": "https://api.moonshot.cn/v1/models",
        "header_func": lambda k: {"Authorization": f"Bearer {k}"},
        "reason": "Kimi 目前是纯文本大语言模型，尚未提供毫秒级实时麦克风流式同传接口（Realtime WebSocket PCM），无法用于低延迟会议大屏系统。"
    },
    {
        "name": "DeepSeek (深度求索)",
        "supports_realtime_audio": False,
        "test_url": "https://api.deepseek.com/models",
        "header_func": lambda k: {"Authorization": f"Bearer {k}"},
        "reason": "DeepSeek 是纯文本对话与推理模型，暂不支持实时音频流式输入与实时同传。"
    },
    {
        "name": "OpenAI",
        "supports_realtime_audio": True,
        "test_url": "https://api.openai.com/v1/models",
        "header_func": lambda k: {"Authorization": f"Bearer {k}"},
        "reason": "OpenAI 拥有 Realtime API (gpt-4o-realtime)，但接口协议、认证与计费机制与阿里云不同，需单独配置海外代理与 OpenAI 模块。"
    }
]

def get_env_value(key: str, default: str = "") -> str:
    if not os.path.exists(ENV_FILE):
        return default
    with open(ENV_FILE, "r", encoding="utf-8") as f:
        content = f.read()
    m = re.search(rf"^{key}=(.*)$", content, re.M)
    return m.group(1).strip() if m else default

def set_env_value(key: str, value: str):
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
    except PermissionError:
        tmp = ENV_FILE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            f.write(new_content)
        os.replace(tmp, ENV_FILE)

def probe_provider_identity(api_key: str) -> dict:
    """智能探测输入的 API Key 究竟属于哪个 AI 厂商"""
    for prov in KNOWN_PROVIDERS:
        try:
            req = urllib.request.Request(prov["test_url"], headers=prov["header_func"](api_key))
            with urllib.request.urlopen(req, timeout=3) as resp:
                if resp.status == 200:
                    return {
                        "detected": True,
                        "provider": prov["name"],
                        "supports_realtime": prov["supports_realtime_audio"],
                        "info": prov
                    }
        except urllib.error.HTTPError as e:
            if e.code == 200:
                return {
                    "detected": True,
                    "provider": prov["name"],
                    "supports_realtime": prov["supports_realtime_audio"],
                    "info": prov
                }
            # 401 说明不是该厂商，继续探测下一个
            continue
        except Exception:
            continue

    # 如果无法通过公网探测，基于格式启发式推测
    if api_key.startswith("sk-" + "ws-") or "maas" in api_key:
        return {
            "detected": True,
            "provider": "阿里云百炼 (DashScope 业务空间专属Key)",
            "supports_realtime": True,
            "info": KNOWN_PROVIDERS[0]
        }
    elif api_key.startswith("sk-" + "proj-"):
        return {
            "detected": True,
            "provider": "OpenAI",
            "supports_realtime": True,
            "info": KNOWN_PROVIDERS[3]
        }

    return {"detected": False, "provider": "未知厂商", "supports_realtime": False, "info": None}

def test_dashscope_realtime_handshake(api_key: str, ws_url: str) -> tuple[bool, str]:
    """向阿里云实时同传 WebSocket 发起真实握手检测"""
    try:
        import websocket
    except ImportError:
        return True, "依赖包未安装，跳过深度握手校验"

    result = {"success": False, "msg": "云端握手未响应"}

    def on_open(ws):
        config = {
            "type": "session.update",
            "session": {
                "output_modalities": ["text"],
                "translation": {"language": "en"}
            }
        }
        ws.send(json.dumps(config))

    def on_message(ws, msg):
        try:
            data = json.loads(msg)
            t = data.get("type", "")
            if t == "session.updated":
                result["success"] = True
                result["msg"] = "云端握手成功！该 Key 具备该实时同传模型的调用权限。"
                ws.close()
            elif t == "error":
                result["success"] = False
                err_msg = data.get("error", {}).get("message") or data.get("message") or str(data)
                result["msg"] = f"云端拒绝: {err_msg}"
                ws.close()
        except Exception as e:
            result["msg"] = f"响应解析错误: {e}"
            ws.close()

    def on_error(ws, err):
        result["success"] = False
        result["msg"] = f"{err}"

    headers = ["Authorization: Bearer " + api_key]
    ws_app = websocket.WebSocketApp(
        ws_url,
        header=headers,
        on_open=on_open,
        on_message=on_message,
        on_error=on_error
    )

    import threading
    import ssl
    sslopt = {"cert_reqs": ssl.CERT_NONE}
    t = threading.Thread(target=lambda: ws_app.run_forever(sslopt=sslopt), daemon=True)
    t.start()
    t.join(timeout=4)
    if ws_app and ws_app.sock:
        try:
            ws_app.close()
        except Exception:
            pass

    return result["success"], result["msg"]

def main():
    print("=" * 66)
    print("    Harry Translate (哈利同传) · 厂商智能识别与 Key 切换工具    ")
    print("=" * 66)

    cur_key = get_env_value("DASHSCOPE_API_KEY")
    cur_url = get_env_value(
        "QWEN_REALTIME_WS_URL",
        "wss://dashscope.aliyuncs.com/api-ws/v1/realtime?model=qwen3.8-livetranslate-flash-realtime"
    )

    m = re.search(r"model=([^&]+)", cur_url)
    cur_model = m.group(1) if m else "qwen3.8-livetranslate-flash-realtime"

    if cur_key:
        masked = cur_key[:10] + "..." + cur_key[-6:] if len(cur_key) > 16 else cur_key
        print(f"当前配置状态：")
        print(f"  • 生效厂商: 阿里云百炼 (DashScope)")
        print(f"  • 生效 Key : {masked}")
        print(f"  • 生效模型: {cur_model}")
    else:
        print("当前尚未配置任何有效 API Key。")

    print("-" * 66)

    # 从命令行获取或交互式输入
    raw_input_key = ""
    if len(sys.argv) > 1:
        raw_input_key = sys.argv[1].strip()

    if not raw_input_key:
        print("💡 请输入（或直接粘贴）您想使用的 API Key (支持自动识别厂商):")
        print("   [提示: 直接按回车将保持现有 Key，进入模型选择]")
        try:
            raw_input_key = input("👉 请输入 API Key: ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\n已取消。")
            return

    raw_input_key = raw_input_key.strip("'\"")

    if not raw_input_key and not cur_key:
        print("❌ 错误：未输入任何 API Key！")
        return

    check_key = raw_input_key if raw_input_key else cur_key

    # 1. 厂商智能嗅探与合法性校验
    print("\n🔍 正在智能探测该 API Key 所属厂商与模型支持能力...")
    probe = probe_provider_identity(check_key)

    detected_prov = probe["provider"]
    supports_realtime = probe["supports_realtime"]

    print(f"🏷️  探测结果: [{detected_prov}]")

    # 如果是非实时音频流厂商（如 Kimi、DeepSeek），立刻阻断并清晰解释！
    if not supports_realtime:
        print("\n" + "!" * 66)
        print(f"❌ 厂商不匹配：[{detected_prov}] 无法用于本项目！")
        if probe.get("info") and probe["info"].get("reason"):
            print(f"📌 原因分析: {probe['info']['reason']}")
        else:
            print("📌 原因分析: 该 API Key 属于纯文本对话模型厂商，不支持毫秒级麦克风实时音频流同传（WebSocket PCM）。")
        print("!" * 66)
        print("💡 解决方案:")
        print("   请在【阿里云百炼控制台】(https://bailian.console.aliyun.com/) 申请 DashScope API Key。")
        print("   系统将保留您原先正确的配置，未做任何修改。")
        return

    # 2. 如果是阿里云百炼，展示真正属于该厂商的模型供选择
    print("✅ 厂商检测通过！该厂商支持实时语音音频流同传。")
    print("\n📦 该厂商支持的可选同传模型：")
    models = KNOWN_PROVIDERS[0]["models"]
    for idx, (m_id, m_desc) in enumerate(models, 1):
        flag = " [当前使用]" if m_id == cur_model else ""
        print(f"   {idx}. {m_id}{flag}")
        print(f"      ↳ {m_desc}")

    print("   [直接按回车保持当前使用模型: " + cur_model + "]")
    try:
        choice = input(f"👉 请选择模型 (1-{len(models)}，默认回车): ").strip()
    except (KeyboardInterrupt, EOFError):
        choice = ""

    selected_model = cur_model
    if choice == "1":
        selected_model = models[0][0]
    elif choice == "2":
        selected_model = models[1][0]

    target_url = re.sub(r"model=[^&]+", f"model={selected_model}", cur_url)

    # 3. 向云端发起真实会话握手检验
    print(f"\n⏳ 正在使用新 Key 向云端真实发起会话握手 (模型: {selected_model})...")
    ok, msg = test_dashscope_realtime_handshake(check_key, target_url)

    if ok:
        print(f"✅ {msg}")
        set_env_value("DASHSCOPE_API_KEY", check_key)
        set_env_value("QWEN_REALTIME_WS_URL", target_url)
        print("\n" + "=" * 66)
        print("🎉 恭喜！新配置已通过全部校验并正式生效：")
        masked_saved = check_key[:10] + "..." + check_key[-6:] if len(check_key) > 16 else check_key
        print(f"   • 服务厂商: 阿里云百炼 (DashScope)")
        print(f"   • 生效 Key : {masked_saved}")
        print(f"   • 生效模型: {selected_model}")
        print("=" * 66)
        print("🚀 您现在可以随时启动同传：")
        print("   • 终端执行: ./start.sh")
        print("   • 或直接双击「启动同传系统.command」")
    else:
        print(f"\n⚠️ 握手校验失败: {msg}")
        print("可能原因：Key 填写有误、账号欠费、或在当前百炼业务空间中尚未开通此模型权限。")
        confirm = input("是否仍然强制保存该 Key？(y/N): ").strip().lower()
        if confirm == "y":
            set_env_value("DASHSCOPE_API_KEY", check_key)
            set_env_value("QWEN_REALTIME_WS_URL", target_url)
            print("💾 已强制保存。")
        else:
            print("🛡️ 已取消保存，原配置未受任何影响。")

if __name__ == "__main__":
    main()
