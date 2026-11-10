#!/bin/bash

# 获取当前脚本所在绝对目录（支持空格与中文字符）
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
cd "$DIR"

echo "=========================================================="
echo "    Harry Translate (哈利同传) · 中译英专属通道 (EN)      "
echo "    适用场景: 中文发表演讲、向外宾投屏翻译 (节省50% Token)  "
echo "=========================================================="

# 智能检测与激活 Python 运行环境 (本地 .venv 优先，自动初始化/系统环境兜底)
PYTHON=""
if [ -f ".venv/bin/python" ]; then
    PYTHON=".venv/bin/python"
elif command -v python3 >/dev/null 2>&1; then
    if python3 -c "import fastapi, uvicorn, pywebview, pyaudio" >/dev/null 2>&1; then
        echo ">> [提示] 未发现 .venv，但系统 Python3 依赖完备，使用系统 Python3..."
        PYTHON="python3"
    else
        echo ">> [初始化] 未检测到 .venv 虚拟环境，正在为您自动创建并安装依赖..."
        python3 -m venv .venv
        if [ -f ".venv/bin/python" ]; then
            .venv/bin/pip install -r requirements.txt
            PYTHON=".venv/bin/python"
            echo ">> [就绪] 虚拟环境已成功初始化！"
        else
            echo ">> [错误] 自动创建 .venv 失败，请检查 Python3 环境。"
            exit 1
        fi
    fi
else
    echo ">> [错误] 未检测到 Python3 运行环境，请先安装 Python 3.10+。"
    exit 1
fi

# 检查并自动同步 .env 配置文件
if [ ! -f ".env" ]; then
    if [ -f ".env.example" ]; then
        echo ">> [配置] 正在基于 .env.example 自动生成 .env 初始配置..."
        cp ".env.example" ".env"
    fi
fi

# 检查 DASHSCOPE_API_KEY
if [ -f ".env" ]; then
    if ! grep -q "DASHSCOPE_API_KEY=" ".env" || grep -E -q "DASHSCOPE_API_KEY=($|your_key_here)" ".env"; then
        echo ">> [提示] .env 中未检测到有效的 DASHSCOPE_API_KEY，您可在启动后于界面配置，或运行 ./切换API_Key.command 进行配置。"
    fi
fi

# 检查 8000 端口并按需后台拉起同传服务端
SERVER_PID=""
if ! lsof -i :8000 > /dev/null 2>&1; then
    echo ">> 正在后台启动同传服务端 (端口 8000)..."
    $PYTHON server.py &
    SERVER_PID=$!
    
    # 轮询探测服务端健康状态直至就绪
    READY=0
    for i in {1..30}; do
        if curl -s http://localhost:8000/ > /dev/null 2>&1; then
            READY=1
            break
        fi
        sleep 0.2
    done

    if [ "$READY" -eq 1 ]; then
        echo ">> [就绪] 同传服务端启动成功。"
    else
        echo ">> [警告] 服务端就绪探测超时，尝试继续唤起桌面 HUD..."
    fi
else
    echo ">> [检测] 同传服务端已在运行 (端口 8000)。"
fi

# 退出时清理自己拉起的后台服务
cleanup() {
    if [ -n "$SERVER_PID" ]; then
        echo ">> 正在停止后台同传服务 (PID: $SERVER_PID)..."
        kill "$SERVER_PID" 2>/dev/null || true
    fi
}
trap cleanup EXIT INT TERM

# 启动原生桌面悬浮 HUD 窗口 (中译英专属通道 --channel en)
echo ">> [防重] 检测并终止历史孤儿悬浮窗进程..."
pkill -f "float_app\.py" 2>/dev/null || true
sleep 0.2

echo ">> 正在启动桌面悬浮 HUD (float_app.py --channel en)..."
if ! $PYTHON float_app.py --channel en "$@"; then
    echo ">> [提示] 原生悬浮窗口启动异常或不可用，正在启动网页版悬浮窗作为零门槛兜底..."
    open "http://localhost:8000/hud?channel=en"
    echo ">> 网页版悬浮窗已在浏览器中打开：http://localhost:8000/hud?channel=en"
    echo ">> 按 Ctrl+C 退出并停止后台服务。"
    wait
fi
