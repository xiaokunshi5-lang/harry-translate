# Harry Translate (哈利同传) - 工业级双通道极速同声传译系统

![Platform](https://img.shields.io/badge/Platform-macOS%20%7C%20Windows-blue.svg)
![Python](https://img.shields.io/badge/Python-3.10%20%7C%203.11%20%7C%203.12-brightgreen.svg)
![Latency](https://img.shields.io/badge/E2E%20Latency-425ms-orange.svg)
![UI FPS](https://img.shields.io/badge/Drag%20Performance-120%20FPS-purple.svg)
![Steady HUD](https://img.shields.io/badge/Steady%20HUD-Zero%20Flicker%20100%25-brightgreen.svg)
![Dual Ratio](https://img.shields.io/badge/Dual%20Ratio-68%25%2F32%25%20%E2%87%84%2065%25%2F35%25-blueviolet.svg)
![Zero Clip](https://img.shields.io/badge/Zero--Clip%20HUD-100%25%20Full%20View-success.svg)
![Terminology](https://img.shields.io/badge/Terminology%20Engine-Aho--Corasick%20%3C0.15ms-success.svg)
![Token Gating](https://img.shields.io/badge/Token%20Saving-50%25%20Gated-success.svg)
![E2E Tests](https://img.shields.io/badge/E2E%20Tests-277%20cases-success.svg)
![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)
![Security](https://img.shields.io/badge/Security-Policy%20Enabled-blueviolet.svg)

> **公开基线**：`v3.6.0`  
> **公开仓库说明**：本项目采用独立发布副本与单提交历史，原始本地 Git 历史和发布镜像不会进入公开仓库。  
> **核心引擎**：阿里云百炼千问 3.8 实时同传模型 (`qwen3.8-livetranslate-flash-realtime`) + Gummy 零拷贝直推引擎 (`gummy-realtime-v1`)  
> **重大突破**：**小窗口双语全景防遮挡 (Zero-Clip HUD)**、**68:32 ⇄ 65:35 双模舞台比例无缝热切换**、**跨句状态原子隔离 (彻底杜绝旧句闪现复读)**、**腾讯会议级绝对单态稳态悬浮**、**专精术语语料库 Aho-Corasick 引擎**、**5 档透明度循环与 5 套高对比字体配色**。  
> **适用场景**：跨国远程会议、涉外学术研讨、双语圆桌会谈、外教直播课、大型会议大屏投影与现场控台监看。

---

## 一、系统架构与核心特性

Harry Translate (哈利同传) 专为涉外商务会议、学术研讨会、外教教学及大型双语活动研发。系统基于异步微切片流水线、词法自动机实时纠错与操作系统底层视窗桥接技术，解决传统同传软件“首字迟缓、字幕重叠挤压、失焦变淡发言变深、同音错字难以纠偏、单向翻译浪费双倍 Token”等工程痛点。

```
                    ┌────────────────────────────────────────────────────────┐
                    │               Harry Translate 系统整体架构              │
                    └────────────────────────────────────────────────────────┘
                                                 │
            ┌────────────────────────────────────┴───────────────────────────────────┐
            ▼                                                                        ▼
   ┌─────────────────┐                                                      ┌─────────────────┐
   │ 通道 A: 麦克风发言 │                                                      │ 通道 B: 会议内录  │
   │ (Channel A: EN) │                                                      │ (Channel B: ZH) │
   └────────┬────────┘                                                      └────────┬────────┘
            │                                                                        │
            ├─► 50ms 零拷贝微切片 (800采样点 / 1600 bytes)                             ├─► 50ms 零拷贝微切片
            ├─► 防溢出 Drop-Oldest 隔离缓冲 (maxsize=3)                               ├─► 防溢出隔离缓冲
            │                                                                        │
            ▼                                                                        ▼
   ┌──────────────────────────────────────────────────────────────────────────────────────────┐
   │                     服务端客户端感知流控引擎 (Client-Aware Stream Gating)                   │
   │      • 仅有单向客户端连接时，自动挂起空跑通道，彻底削减 50% Cloud API Token 消耗与网络带宽      │
   └─────────────────────────────────────────┬────────────────────────────────────────────────┘
                                             │
            ┌────────────────────────────────┴────────────────────────────────┐
            ▼                                                                 ▼
   ┌─────────────────┐                                               ┌─────────────────┐
   │ Qwen / Gummy    │                                               │ Qwen / Gummy    │
   │ 中译英实时推理引擎 │                                               │ 英译中实时推理引擎 │
   └────────┬────────┘                                               └────────┬────────┘
            │                                                                 │
            ▼                                                                 ▼
   ┌──────────────────────────────────────────────────────────────────────────────────────────┐
   │              专精术语语料库与 ASR 同音词极速纠错引擎 (Aho-Corasick Automaton, <0.15ms)      │
   │      • 动态匹配 glossary.json，纠正 ASR 常见同音错字（如“落拉”➔ LoRA，“担抗”➔ 单抗）        │
   │      • 规范化专业机器翻译术语（如“反向传播”➔ Backpropagation，“提示词工程”➔ Prompt Eng）   │
   │      • 云端 DashScope 会话建立时自动注入领域热词，提升声学模型识别准确率                  │
   └─────────────────────────────────────────┬────────────────────────────────────────────────┘
                                             │
            ┌────────────────────────────────┴────────────────────────────────┐
            ▼                                                                 ▼
   ┌──────────────────────────────────────────────────────────────────────────────────────────┐
   │                  FastAPI / Uvicorn 高性能异步事件循环 (0.25s 广播超时熔断)                   │
   └─────────────────────────────────────────┬────────────────────────────────────────────────┘
                                             │
      ┌──────────────────┬───────────────────┼───────────────────┬──────────────────┐
      ▼                  ▼                   ▼                   ▼                  ▼
┌───────────┐      ┌───────────┐       ┌───────────┐       ┌───────────┐      ┌───────────┐
│  /hud     │      │  /en      │       │  /zh      │       │  /split   │      │  / (控台)  │
│ 稳态悬浮窗 │      │ 外宾投影屏 │       │ 中方副屏  │       │ 左右对照屏 │      │ 主控仪表盘 │
└───────────┘      └───────────┘       └───────────┘       └───────────┘      └───────────┘
```

---

## 二、九大核心工程突破

### 1. 腾讯会议级绝对单态稳态悬浮 (Absolute Single Steady-State HUD)
彻底根除传统悬浮窗“不发言时变淡透明、发言时变深变不透明”的多态晃动顽疾：
- **原生层纯净解耦**：在 [`float_app.py`](float_app.py) 中彻底剥离 macOS `NSVisualEffectView` 系统视图，消除 macOS 在窗口失去焦点（切换到 PPT/会议软件）时自动调淡材质的系统行为，窗口透明度 100% 移交 WebKit CSS 独立受控渲染；
- **状态机与时钟归零**：彻底物理移除 `dimTimer` 与 `resetInactivity()` 动态计时器，CSS 强制锁定 `#hud-container { opacity: 1 !important; transition: none !important; }`，全生命周期内透明度绝对恒等（$\Delta \text{opacity} \equiv 0.0$）；
- **定稿文字永久静止驻留**：严格对标腾讯会议——发言停顿后，定稿文字**永久静止保留在屏幕上**，绝不 3 秒后清空或淡化；新句子翻译到达时平滑覆盖，彻底消除大面积文字突现突灭造成的“暴晒透光”晃动感。

### 2. 黄金比例 68%/32% 独立双视口防挤压舞台 (Golden Ratio Dual-Zone Stage)
针对中译英、英译中主次语种排版进行了视口物理级重构：
- **68% 主译文区 (`#zonePrimary`) + 32% 原文辅助区 (`#zoneAuxiliary`)**：严格依照近似黄金比例（0.618 / 0.68:0.32）进行双区物理隔离；
- **0px 绝对防挤压侵占**：即便发言者说出 200+ 字符超长原句（在下方占据 4~6 行），下方辅助区产生的内容**对上方 68% 主译文区的高度影响严格为 0px**，主译文行数与视觉焦点永远不被挤压变形；
- **中细微暗光分割线 (`#zoneDivider`)**：1px 微光质感分割线，自然划分主次视觉层次；
- **语种互切自适应反转**：中译英时上方主区显示英文大字、下方显示中文小字；英译中时自动反转为上方显示中文大字、下方显示英文原句。

### 3. 小窗口双语全景防遮挡与 68:32 ⇄ 65:35 双模自适应架构 (v3.6 重大突破)
针对小窗口（如 720x120 或极限 400x120）与多行连续快速发言痛点彻底重构：
- **两行主译文零裁切物理包络 (`twoLinesEnvelope`)**：在小视口（高度 $\le 75\text{px}$）启用紧凑排版（15px / 1.25 行高），内容在两行包络内时顶部渐变遮罩尺寸动态归零（`--fade-mask-top-size: 0px`），彻底消除第一行发虚发淡被遮挡的玻璃感；
- **中文原文辅助区 31px 物理安全包络**：消除 `#zoneAuxiliary` 的 `padding-top: 2px`，设置 `min-height: 0` 与 12px / 1.2 行高，中文输入稳落 31px 安全带内，彻底根除汉字被 `#zoneDivider` 削顶；
- **68:32 ⇄ 65:35 双模比例瞬时热切**：支持出厂经典 `68:32` 模式与中文扩展 `65:35` 模式，通过全局快捷键 **`Cmd + Shift + R` / `Ctrl + Shift + R`** 秒级无缝切换，并自动在本地持久化记忆；
- **跨句状态原子隔离 (Atomic Sentence State Isolation)**：新句到来时服务端原子清空旧句缓存，纯 ASR 阶段译文字段严格置空，前端设置状态屏障锁，彻底杜绝“很高兴见到你”在新句开头闪现复读；
- **超长长句 7+ 行平滑滚动**：小窗口下单句累积多行时，视口自适应内部平滑平移，确保最新吐出的文字始终处于视觉焦点。

### 4. 专精术语语料库与 ASR 同音错字极速修正引擎 (Terminology Corpus Engine)
针对同传领域专业术语翻译不准、语音识别同音字飘移的痛点打造：
- **Aho-Corasick 多模式自动机**：单句修正耗时 $< 0.15\text{ms}$（实测 $0.03\text{ms}$），处理 5000+ 专业词条对实时流式延迟造成体感误差严格为 0；
- **ASR 同音错字智能纠正**：自动将常见语音识别谐音（如“落拉”➔ LoRA、“担抗”➔ 单抗、“库伯内特斯”➔ Kubernetes、“派托奇”➔ PyTorch）即时矫正为规范标准词；
- **领域术语双向对齐**：统一英汉术语规范（如“反向传播”➔ Backpropagation、“提示词工程”➔ Prompt Engineering）；
- **本地自由编辑与热重载**：根目录提供直观的 [`glossary.json`](glossary.json)，支持用户随时增删词条；开放 `GET /api/glossary` 与 `POST /api/glossary` RESTful 接口，无需重启服务，5ms 内热生效并同步至云端热词会话。

### 5. 5 档微透凝胶透明度与 5 套高对比字体调色方案
- **五档透明度循环 (`btn-opacity`)**：
  - `💧 15%`（默认出厂：微透凝胶，极佳通透感且不遮挡背景文档）；
  - `💧 35%`（经典毛玻璃）；
  - `💧 55%`（半深色沉浸）；
  - `💧 75%`（高对比暗夜）；
  - `💧 10%`（极限通透：轻薄如空气）。
- **五套高对比精选字体配色 (`hud-theme-pill` / 快捷键 `Cmd+Shift+C`)**：
  1. `🎨 暖金`（经典出厂：主字 `#facc15` 暖金，搭配白辅字与黑底深阴影）；
  2. `🎨 腾讯白`（商务会议对标：主字 `#ffffff` 纯白，搭配冰灰辅字）；
  3. `🎨 冰川青`（科技极客风：主字 `#38bdf8` 荧光青，夜间阅览极舒适）；
  4. `🎨 黑曜石`（高亮白底模式：主字 `#0f172a` 深黑，搭配白色光晕，适合浅色 PPT 衬底）；
  5. `🎨 薄荷绿`（清新护眼：主字 `#4ade80` 薄荷绿，长时间开会不疲倦）。

### 6. 425ms 端到端超低延迟
采用 50ms（800 采样点 / 1600 字节）物理切片，直通 C 级零拷贝分发链路，单帧处理耗时 $< 0.003\text{ms}$，首字上屏实测速度稳定在 $400 \sim 450\text{ms}$，优于传统方案 150ms 以上。

### 7. 左上角专属锚点 120 FPS 原生硬件拖拽
在浮窗左上角设立独立微型胶囊磨砂把手（`#drag-anchor-corner`，内嵌盲文点阵 `⠿`）。鼠标落入把手时直接触发 macOS WindowServer 底层接管（`performWindowDragWithEvent:`），0 CPU、0 IPC 跨进程通信，实现 Apple ProMotion 120 FPS 硬件级拖曳，自由穿梭于笔记本屏幕与 4K 扩展屏之间。

### 8. 语言通道即时互切与 50% Token 节能流控
悬浮窗顶部提供微型交互胶囊（`中 ➔ EN ⇄` 与 `EN ➔ 中 ⇄`），支持点击或全局快捷键 **`Cmd+Shift+T` / `Ctrl+Shift+T`** 瞬时切换。服务端内置 Client-Aware Stream Gating 机制：外教课等单向翻译场景下，未被监听的通道音频直推被自动阻断，**直接削减 50% 的 DashScope 云端 API Token 消耗与上行带宽**。

### 9. 启动脚本进程排他守卫与单目录发布
- 启动脚本（[`启动悬浮同传.command`](启动悬浮同传.command)）前置注入 `pkill -f "float_app\.py"` 守卫，杜绝后台旧版本孤儿进程，结合微秒级时间戳彻底穿透 WebKit 缓存；
- 公开仓库只保留一套可移植源码，避免多份发布镜像之间产生版本漂移；本地私有多目录发布流程不会进入公开历史。

---

## 三、快捷键操作速查表

在悬浮窗处于激活状态或全局交互时，支持以下生产力快捷键：

| 快捷键 (macOS / Windows) | 动作名称 | 功能说明 |
| :--- | :--- | :--- |
| **`Cmd + Shift + L`**<br>`Ctrl + Shift + L` | **鼠标穿透锁定/解锁** | 开启后浮窗完全不响应鼠标（可穿透点击下方 Word/PPT），再次按下解除穿透 |
| **`Cmd + Shift + T`**<br>`Ctrl + Shift + T` | **双语通道快速互切** | 在 `中 ➔ EN`（中译英）与 `EN ➔ 中`（英译中）之间瞬时平滑翻转 |
| **`Cmd + Shift + R`**<br>`Ctrl + Shift + R` | **双语视口比例快速切换** | 在 **`68:32`**（经典出厂比例）与 **`65:35`**（扩展原文比例）之间无缝瞬时切换，自动本地持久化记忆 |
| **`Cmd + Shift + C`**<br>`Ctrl + Shift + C` | **字体调色方案轮换** | 循环切换 5 套高对比配色（暖金 ➔ 腾讯白 ➔ 冰川青 ➔ 黑曜石 ➔ 薄荷绿） |
| **鼠标悬停顶部 24px 传感器** | **唤出控制胶囊** | 平时 100% 隐藏，鼠标移至顶端自动浮现通道药丸、配色药丸、穿透锁、透明度与设置键 |
| **按住左上角把手 (`⠿`) 拖拽** | **120 FPS 窗口移动** | 硬件级无延迟拖拽窗口跨屏漫游 |

---

## 四、专精术语语料库 (`glossary.json`) 配置指南

语料库文件位于项目根目录 [`glossary.json`](glossary.json)，纯 JSON 格式，可使用任意文本编辑器（VSCode、Sublime、记事本）直接修改：

```json
{
  "asr_fixes": {
    "落拉": "LoRA",
    "担抗": "单抗",
    "库伯内特斯": "Kubernetes",
    "派托奇": "PyTorch",
    "卡夫卡": "Kafka",
    "反向传播": "反向传播"
  },
  "mt_terms": {
    "LoRA": "LoRA (Low-Rank Adaptation)",
    "反向传播": "Backpropagation",
    "提示词工程": "Prompt Engineering",
    "同声传译": "Simultaneous Interpretation",
    "大语言模型": "Large Language Models (LLM)"
  },
  "hotwords": [
    "LoRA", "Transformer", "Kubernetes", "PyTorch", 
    "Backpropagation", "Prompt Engineering", "单抗"
  ]
}
```

### 字段说明：
1. **`asr_fixes` (ASR 谐音纠错映射)**：针对语音识别容易听错的领域同音字词，例如将“落拉”替换为正确的“LoRA”；
2. **`mt_terms` (机器翻译专业词库映射)**：针对大模型翻译时使用的行业标准译名，确保中英文术语 100% 专业统一；
3. **`hotwords` (阿里云百炼云端热词表)**：同传会话建立时自动注入云端声学模型，从识别源头提升特定专有名词的命中率。

> [!TIP]
> 修改 `glossary.json` 后，您可以通过调用 `POST /api/glossary` 或者重启服务立即生效，无需重新编译任何代码！

---

## 五、完整技术栈清单

| 分层 | 组件 / 技术选型 | 版本要求 | 选型原由与工程实现 |
| :--- | :--- | :--- | :--- |
| **运行时底层** | Python (CPython) | 3.10 ~ 3.12 (推荐 3.11) | 兼容 Python 3.13（内置自适应 `audioop` C 级内存切片降级垫片） |
| **音频采集驱动** | PyAudio / PortAudio | 0.2.14+ | 独占低延迟硬件流，单帧切片 50ms（800 samples @ 16kHz 16-bit Mono） |
| **缓冲与防抖** | Drop-Oldest 环形隔离缓冲 | 自研 C/Python | `maxsize=3` 环形队列，网络偶发抖动绝对不造成声卡硬件 `Input overflowed` |
| **术语匹配内核** | Aho-Corasick Automaton | 高性能自动机 | 双向多模式串精准匹配，单句延迟 $< 0.15\text{ms}$，内存开销 $< 2\text{MB}$ |
| **云端同传引擎** | 阿里云百炼 DashScope | Qwen 3.8 / Gummy-v1 | `qwen3.8-livetranslate-flash-realtime` 公网实时模型与 Gummy 兼容 |
| **网络网关服务** | FastAPI / Uvicorn | 0.110+ / 0.28+ | 高性能异步 ASGI 循环，WebSocket 广播配备 0.25 秒超时断路器 |
| **桌面视窗容器** | pywebview / Native OS Bridge | 5.0+ | macOS 基于 WKWebView，Windows 基于 Microsoft Edge WebView2 |
| **原生系统集成** | ctypes (AppKit / user32) | 系统原生 | 纯净透明窗底、macOS `performWindowDragWithEvent:`、Windows `SetWindowDisplayAffinity` |
| **渲染与排版** | HTML5 / CSS3 / ES6+ | Modern Web | 黄金比例 68%/32% 物理防挤压舞台、Apple Liquid Glass、定稿稳定驻留、100% 绝对稳态 |

---

## 六、跨平台快速部署指南 (Part 1: macOS & Part 2: Windows)

详细的分步图文部署与全平台踩坑 FAQ，请直接查阅：[`INSTALL.md`](INSTALL.md)；虚拟声卡与会议内录配置见 [`docs/AUDIO_SETUP_GUIDE.md`](docs/AUDIO_SETUP_GUIDE.md)。

### Part 1: macOS 部署与极速启动
```bash
# 1. 克隆项目并激活虚拟环境
git clone https://github.com/xiaokunshi5-lang/harry-translate.git
cd harry-translate
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 2. 配置阿里云百炼 API Key (首次使用)
cp .env.example .env
open -e .env

# 3. 双击启动脚本或在终端运行
./启动悬浮同传.command
```

### Part 2: Windows 部署与极速启动
```cmd
:: 1. 克隆项目并激活虚拟环境
git clone https://github.com/xiaokunshi5-lang/harry-translate.git
cd harry-translate
python -m venv .venv
call .venv\Scripts\activate.bat
pip install -r requirements.txt

:: 2. 配置阿里云百炼 API Key (首次使用)
copy .env.example .env
notepad .env

:: 3. 双击启动脚本
启动悬浮同传.bat
```

---

## 七、HTTP RESTful API 接口清单

| 请求方式 | 路由路径 | 参数说明 | 响应格式 | 功能说明 |
| :--- | :--- | :--- | :--- | :--- |
| `GET` | `/` | 无 | HTML | 主控大屏与仪表盘页面 |
| `GET` | `/en` | 无 | HTML | 外宾中译英独立投影大屏（50 节点滑动窗口） |
| `GET` | `/zh` | 无 | HTML | 中方英译中独立副屏大屏 |
| `GET` | `/split` | 无 | HTML | 会议主控室左右双栏并排监看对照屏 |
| `GET` | `/hud` | 无 | HTML | 纯网页版毛玻璃悬浮同传窗口（零安装兜底） |
| `GET` | `/api/glossary` | 无 | JSON | 查询当前语料库（ASR 谐音表、MT 术语表、云端热词） |
| `POST` | `/api/glossary` | JSON: `{"asr_fixes": {...}, "mt_terms": {...}, "hotwords": [...]}` | JSON | 动态热更新语料库并即时重载，耗时 $<5\text{ms}$ |
| `GET` | `/api/meta` | 无 | JSON | 查询系统运行状态、活跃声卡、引擎类型及脱敏 API Key |
| `GET` | `/api/config` | 无 | JSON | 查询当前模型、采样率及通道状态 |
| `POST` | `/api/config` | JSON: `{"dashscope_api_key": "...", "engine": "..."}` | JSON | 动态热更新配置，支持空键保护防误清空 |
| `GET` | `/api/audio/devices` | 无 | JSON | 枚举本机全部可用物理麦克风与虚拟内录回环声卡 |
| `POST` | `/api/audio/device` | Query / JSON: `{"device_index": 2, "channel": "A"}` | JSON | 零重启热插拔切换采集声卡（SLA <80ms） |
| `GET` | `/api/hud/lock` | 可选 Query: `?locked=true` | JSON | 查询或修改悬浮窗鼠标穿透锁定状态 |
| `POST` | `/api/hud/lock` | JSON: `{"locked": true}` | JSON | 远程锁定或解除悬浮窗鼠标穿透 |
| `GET` | `/api/stats` | 无 | JSON | 实时查询全场 Token 用量明细与折合费用 |
| `POST` | `/api/stats/reset` | 无 | JSON | 重置会话 Token 与费用累计计数器 |

---

## 八、基准测试与系统性能指标

| 评测维度 | 考核指标 | SLA 达标阈值 | 生产实测数值 | 评测结论与工程保障 |
| :--- | :--- | :--- | :--- | :--- |
| **音频微切片** | 采集切片长度 | 50.0ms (800 采样点) | **50.0ms / 1600 字节** | 严格锁定 16kHz 16-bit Mono，消除积压 |
| **术语匹配时延** | 5000 词库单句纠错 | $< 0.5\text{ms}$ (目标 $\le 0.15\text{ms}$) | **0.031ms (31µs)** | Aho-Corasick 多模式自动机，体感 0 延迟 |
| **单态透明稳定性** | 连续发言与静默对比 | $\Delta \text{opacity} = 0.0$ | **$\Delta \text{opacity} \equiv 0.0$** | 彻底剥离系统 VEV，纯 WebKit 控色零多态晃动 |
| **双视口防挤压** | 原文区 200 字涌入 | 主区高度变动 $\le 1\text{px}$ | **0px 变动 (68%/32% 物理隔离)** | 原文再长也绝不挤压主译文行高 |
| **热路径分发** | 单帧 C 级直推耗时 | $< 0.015\text{ms}$ | **0.0029ms (2.9µs)** | 5000 帧循环压测实测耗时 14.93ms |
| **端到端延迟** | 首字上屏总延迟 | $< 500\text{ms}$ | **425ms** | 阿里云百炼千问 3.8 / Gummy-v1 实测 |
| **广播断路器** | 慢速客户端剔除耗时 | $250\text{ms}$ 超时熔断 | **0.252s 熔断，健康端 0.227ms** | 彻底杜绝队头阻塞（Head-of-Line Blocking） |
| **UI 交互性能** | 左上角锚点拖拽帧率 | $\ge 60\text{ FPS}$ | **120 FPS 原生满帧** | WindowServer 硬件托管，0 IPC 通信损耗 |
| **长时运行内存** | 连续 10 小时流式推送 | $< 75\text{MB}$ | **$< 35\text{MB}$ 恒定** | 50 节点滑动循环窗口（DOM Ring Buffer） |
| **CPU 占用** | 待机与实时转译 | $\le 2.5\%$ | **0.8% ~ 1.9%** | 无任何重型 Electron / Qt 运行时开销 |
| **Token 节流** | 单向监听场景 Token 节约 | $\ge 40\%$ | **50.0% 阻断** | 客户端感知流控（Client-Aware Stream Gating） |

---

## 九、场景化启动脚本矩阵

| 脚本文件 (macOS / Windows) | 针对应用场景 | 通道工作状态与省钱流控 |
| :--- | :--- | :--- |
| **`启动同传系统.command`**<br>`启动同传系统.bat` | **主控室监看、双大屏投影、全功能管理** | 启动后台服务并在默认浏览器中唤起双栏对照大屏（`/split`） |
| **`启动悬浮同传.command`**<br>`启动悬浮同传.bat` | **个人桌面单浮窗、同传提词、外语视频观看** | 自适应单悬浮窗，记忆上次通道，防多开排他清理旧进程，支持快捷键瞬时切换 |
| **`启动双悬浮同传.command`**<br>`启动双悬浮同传.bat` | **双向国际圆桌会议、涉外商务谈判** | 垂直错落并排拉起上下两个浮窗（上窗中译英，下窗英译中），30px 明确空隙，零重叠遮挡 |
| **`启动悬浮同传_英译中.command`**<br>`启动悬浮同传_英译中.bat` | **外教直播课、听取学术讲座、英文汇报** | **中文大字主译（68%），英文原文辅助（32%）**；服务端流控挂起中译英，**立减 50% Token 费用** |
| **`启动悬浮同传_中译英.command`**<br>`启动悬浮同传_中译英.bat` | **对国际嘉宾演讲、中文发布会向外宾投屏** | **英文大字主译（68%），中文原文辅助（32%）**；英译中通道自动挂起，**立减 50% Token 费用** |
| **`切换API_Key.command`**<br>`切换API_Key.bat` | **密钥可视化更换** | 终端菜单化更换 DashScope API Key 并自动持久化保存 |

---

## 十、自动化测试与出厂验收套件

项目内置完备的自动化质量守卫矩阵，代码变动必须通过全部验收测试：

```bash
# 1. 运行 277 项全量自动化测试 (涵盖 Tier 1~4 功能、边界、黄金比例双视口与术语引擎)
.venv/bin/python -m unittest discover -s tests -p 'test_*.py'

# 2. 运行 16 维工厂级终审审计门禁 (含 50ms 零拷贝、425ms 延迟、AC-09 控件数等)
.venv/bin/python tests/audit_gate.py

# 3. 运行腾讯会议绝对稳态悬浮与 5 套字体配色专项测试 (AC-V1 ~ AC-V5)
.venv/bin/python -m unittest tests/test_tencent_steady_hud_and_themes.py

# 4. 运行单态对抗极限压测 (连续 10s 静默与流式吐字，断言 delta opacity == 0.0)
.venv/bin/python -m unittest tests/challenger_steady_hud_adversarial.py

# 5. 运行专精术语语料库与黄金比例独立双视口专项测试 (AC-G1~G4, AC-L1~L5)
.venv/bin/python -m unittest tests/test_glossary_and_golden_ratio_layout.py

# 6. 运行小窗口两行主译文零裁切物理包络复现与回归测试
.venv/bin/python -m unittest tests/repro_issue_twoline_output_clip.py

# 7. 运行中文原文辅助区 31px 安全包络防削顶复现与回归测试
.venv/bin/python -m unittest tests/repro_issue_chinese_input_clip.py

# 8. 运行 68:32 ⇄ 65:35 双模舞台比例自适应与快捷键测试
.venv/bin/python -m unittest tests/test_hud_dual_ratio_mode.py
```

---

## 十一、安全升级与恢复建议

公开版本不附带会执行 `git reset` 或覆盖本地文件的一键回滚脚本。建议升级前先提交或备份本地修改：

```bash
git status
git add -A
git commit -m "chore: save local changes before upgrade"
git fetch --tags
git switch v3.6.0
```

- `.env` 与 `.venv` 已被 `.gitignore` 排除，不会进入提交；
- 如需回到自己的修改，可从刚才创建的分支继续；
- 密钥泄露时请先在阿里云控制台轮换 Key，再按 [`SECURITY.md`](SECURITY.md) 私下报告。

---

## 十二、开源许可与服务声明

- 本系统基于 Apache 2.0 开源许可协议发布；
- 语音实时翻译能力基于阿里云百炼平台（DashScope）大模型服务，用户需自备有效的 API Key 并遵守相应服务条款。
