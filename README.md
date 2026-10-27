# Harry Translate (哈利同传) - 工业级双通道极速同声传译系统

![Platform](https://img.shields.io/badge/Platform-macOS%20%7C%20Windows-blue.svg)
![Python](https://img.shields.io/badge/Python-3.9%20%7C%203.10%20%7C%203.11%20%7C%203.12-brightgreen.svg)
![Latency](https://img.shields.io/badge/E2E%20Latency-320ms~425ms-orange.svg)
![UI FPS](https://img.shields.io/badge/Drag%20Performance-120%20FPS-purple.svg)
![Steady HUD](https://img.shields.io/badge/Steady%20HUD-Zero%20Flicker%20100%25-brightgreen.svg)
![Dual Ratio](https://img.shields.io/badge/Dual%20Ratio-68%25%2F32%25%20%E2%87%84%2065%25%2F35%25-blueviolet.svg)
![Zero Clip](https://img.shields.io/badge/Zero--Clip%20HUD-100%25%20Full%20View-success.svg)
![Far-Field AGC](https://img.shields.io/badge/Far--Field%20AGC-0.0023ms%20Auto%20Gain-brightgreen.svg)
![Terminology](https://img.shields.io/badge/Terminology%20Engine-Aho--Corasick%20%3C0.15ms-success.svg)
![Glossary Bank](https://img.shields.io/badge/Glossary%20Bank-18%2C000%2B%20Terms%20(15%20Packs)-success.svg)
![Cloud Quota](https://img.shields.io/badge/Cloud%20Quota-Smart%20Cap%20%E2%89%A4900%20Safe-brightgreen.svg)
![Token Gating](https://img.shields.io/badge/Token%20Saving-50%25%20Gated-success.svg)
![HUD Lock](https://img.shields.io/badge/HUD%20Physical%20Lock-4--Tier%20Hard%20Clamped-blueviolet.svg)
![Fullscreen Aux](https://img.shields.io/badge/macOS%20Spaces-HUDPanelHost%20Penetration-success.svg)
![E2E Tests](https://img.shields.io/badge/Tests-315%2F315%20PASS%20(246%20E2E)-success.svg)
![Factory Gate](https://img.shields.io/badge/Factory%20Audit-16%2F16%20PASS-success.svg)

> **公开基线版本**：`v3.6.0`、`v3.8.0` 与 `v3.9.0`（当前正式旗舰版）  
> **当前正式版本**：`v3.9.0` (流式直写对齐、跨句历史留存与 1~2米远场自适应 AGC 旗舰出厂版)  
> **核心引擎**：阿里云百炼千问 3.8 实时同传模型 (`qwen3.8-livetranslate-flash-realtime`) + Gummy 零拷贝直推引擎 (`gummy-realtime-v1`)  
> **重大突破**：**悬浮同传零丢帧同步 DOM 直写与 `#historyLine` 历史定稿平滑留存**、**1~2 米远场自适应软限幅自动增益 (AGC, 0.0023ms)**、**云端极速 Server VAD 320ms 断句调优与 DashScope `stash` 实时尾词跟手**、**macOS `NSActivityLatencyCritical` 原生抗 App Nap 后台节流**、**万级多维分类标签热词库 (`glossary_bank/`)**、**双轨容量水位仪与云端 1,000 词智能防爆截断**、**`HUDPanelHost` 原生非激活面板与 macOS 全屏桌面空间穿透**、**4 重物理硬锁防拖拽架构（锁位置尺寸不锁按钮交互）**、**双悬浮同传窗口分窗独立锁定控制**、**小窗口双语全景防遮挡 (Zero-Clip HUD)**、**68:32 ⇄ 65:35 双模舞台比例无缝热切换**、**跨句状态原子隔离 (彻底杜绝旧句闪现复读)**、**腾讯会议级绝对单态稳态悬浮**、**专精术语 Aho-Corasick 自动机引擎 (<0.15ms, 0 Token)**。  
> **适用场景**：跨国远程会议、涉外学术研讨、双语圆桌会谈、外教直播课、大型会议大屏投影与现场控台监看。

---

## 一、系统架构与核心特性

Harry Translate (哈利同传) 专为涉外商务会议、学术研讨会、外教教学及大型双语活动研发。系统基于异步微切片流水线、词法自动机实时纠错与操作系统底层视窗桥接技术，解决传统同传软件“首字迟缓、字幕重叠挤压、失焦变淡发言变深、同音错字难以纠偏、单向翻译浪费双倍 Token”等工程痛点。

> [📖 查看全景热词分类与 18,449 词速查总览表 (GLOSSARY_INDEX.md)](GLOSSARY_INDEX.md)


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

## 二、十一大核心工程突破

### 1. 腾讯会议级绝对单态稳态悬浮与全屏空间穿透 (Absolute Single Steady-State HUD & Fullscreen Aux)
彻底根除传统悬浮窗“不发言时变淡透明、发言时变深变不透明”的多态晃动顽疾，并解决 macOS 全屏 App 下浮窗消失或切屏痛点：
- **`HUDPanelHost` 原生非激活面板架构**：在 [`float_app.py`](float_app.py) 中采用原生 `HUDPanelHost`（继承自 `AppKit.NSPanel`），注入 `NSWindowStyleMaskNonactivatingPanel (1<<7)`，设置 `NSApplicationActivationPolicyAccessory (1)`、`collectionBehavior=337`（`CanJoinAllSpaces | FullScreenAuxiliary | Stationary | IgnoresCycle`）以及 `NSScreenSaverWindowLevel (1000)`，实现与 Keynote / PowerPoint / 腾讯会议全屏 Spaces 穿透共存，点击按钮绝不触发系统切屏；
- **4 重物理硬锁防拖拽架构**：点击 `🔒` 或快捷键 `Cmd+Shift+L` 锁定后，底层剥离 `NSWindowStyleMaskResizable` 缩放掩码，并在 Cocoa 运行时严格拦截 `performWindowDragWithEvent:`、`setFrameOrigin:`、`setFrameTopLeftPoint:` 与 `setFrame:display:`，坐标与尺寸 100% 物理焊死；同时**100% 保留顶栏全部按钮鼠标悬停与点击响应能力**（锁位置不锁交互，支持浮窗直按 `🔓` 解锁或主控室远程解锁，含 3.0s 防竞态轮询保护）；
- **双悬浮窗分窗独立锁定控制**：在双悬浮同传模式（`--dual`）下，中译英（`en`）与英译中（`zh`）两套浮窗具备独立的 `HudApi` 与原生控制器，支持单窗独立锁定或独立解锁，彻底杜绝双窗误联动；
- **原生层纯净解耦**：彻底剥离 macOS `NSVisualEffectView` 系统视图，消除 macOS 在窗口失去焦点（切换到 PPT/会议软件）时自动调淡材质的系统行为，窗口透明度 100% 移交 WebKit CSS 独立受控渲染；
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

### 6. 320ms~425ms 端到端超低延迟
采用 50ms（800 采样点 / 1600 字节）物理切片，直通 C 级零拷贝分发链路，单帧处理耗时 $< 0.003\text{ms}$，首字上屏实测速度稳定在 $320 \sim 425\text{ms}$，优于传统方案 150ms 以上。

### 7. 左上角专属锚点 120 FPS 原生硬件拖拽
在浮窗左上角设立独立微型胶囊磨砂把手（`#drag-anchor-corner`，内嵌盲文点阵 `⠿`）。鼠标落入把手时直接触发 macOS WindowServer 底层接管（`performWindowDragWithEvent:`），0 CPU、0 IPC 跨进程通信，实现 Apple ProMotion 120 FPS 硬件级拖曳，自由穿梭于笔记本屏幕与 4K 扩展屏之间。

### 8. 语言通道即时互切与 50% Token 节能流控
悬浮窗顶部提供微型交互胶囊（`中 ➔ EN ⇄` 与 `EN ➔ 中 ⇄`），支持点击或全局快捷键 **`Cmd+Shift+T` / `Ctrl+Shift+T`** 瞬时切换。服务端内置 Client-Aware Stream Gating 机制：外教课等单向翻译场景下，未被监听的通道音频直推被自动阻断，**直接削减 50% 的 DashScope 云端 API Token 消耗与上行带宽**。

### 9. 启动脚本进程排他守卫与单目录纯净发布
- 启动脚本（[`启动悬浮同传.command`](启动悬浮同传.command)）前置注入 `pkill -f "float_app\.py"` 守卫，杜绝后台旧版本孤儿进程，结合微秒级时间戳彻底穿透 WebKit 缓存；
- 采用单目录纯净交付架构，统一源码管理，彻底根除多份物理镜像之间的版本漂移与维护冗余。

### 10. 悬浮同传零丢帧同步 DOM 直写与 `#historyLine` 历史定稿平滑留存 (HUD Parity & Synchronous Direct-Write Engine)
针对悬浮窗与普通窗口同传之间的体感对齐与连续阅读体验重大升级：
- **同步 DOM 直写管道（0 丢帧 0 滞后）**：在 [`float_ui.html`](float_ui.html) 中彻底剥离冗余的动画排队与宏任务调度，收到 WebSocket 实时转译帧即刻执行无锁微任务同步直写（$0.0018\text{ms}$ 极速上屏），确保悬浮窗与普通网页窗口同传在翻译流式接收速度与内容完整度上 **100% 绝对一致**；
- **`#historyLine` 历史定稿平滑留存**：创新设计上方 `#historyLine` 历史定稿行与下方 `#streamLine` 正在吐字流式行两级视口：新句子触发 `speech_started` 或换句时，上一句定稿译文瞬时平滑提升并锚定至上方 `#historyLine`（字体微收敛为 13px 优雅半透明暗字），下方 `#streamLine` 原子清空并立即接收新句实时流式字词。彻底杜绝旧版“换句清空视口导致前文瞬间蒸发”的视界断层，极大提升会议译员连续阅读理解与双语对照体验；
- **0.08s 极简 GPU 硬件平滑变换**：视口高度变换严格锁定 `transition: max-height 0.08s cubic-bezier(0.2, 0, 0, 1)`，兼顾行高过渡平滑无撕裂与极速吐字跟手，彻底根除慢速过渡造成的视觉滞后；
- **macOS `NSActivityLatencyCritical` 抗 App Nap 原生节流**：在 [`float_app.py`](float_app.py) 中通过 Cocoa API 申请 `NSActivityLatencyCritical | NSActivityUserInitiatedAllowingIdleSystemSleep` 专属进程保活令牌，即使悬浮窗长期退居非激活状态，macOS 也绝对不将其转入 App Nap 节能休眠，持续保持毫秒级事件响应。

### 11. 1~2 米远场自适应软限幅自动增益 (Far-Field Adaptive Soft-Knee AGC) 与云端 320ms 极速 Server VAD 断句
针对真实会议室桌面距离发言人 1~2 米拾音衰减严重的工程痛点：
- **微秒级自适应软限幅 AGC 算法**：在 [`core/audio_pipeline.py`](core/audio_pipeline.py) 音频微切片热路径（50ms / 800 采样点）中内嵌 C 级高效自适应自动增益补偿（单帧处理耗时仅 **0.0023ms / 2.3µs**）；
- **动态能量平滑提振（1.8x ~ 2.5x）**：自动检测环境底噪并设立动态静音门限（`noise_floor = 140`），对 1~2 米弱声发言平滑施加 $1.8\times \sim 2.5\times$ 增益（目标有效 RMS $\ge 1000$），大幅提升远场微弱拾音在声学模型中的信噪比与词识别率；
- **双曲正切软限幅（Soft-Knee Peak Limiter）**：采用平滑双曲正切数学曲线（$\tanh$）将增益后的大振幅波形平滑收拢在 $\pm 31000$ 线性包络内，杜绝近身重音出现削顶硬失真破音；
- **云端 320ms 极速 Server VAD 断句调优**：在 [`engines/qwen_translators.py`](engines/qwen_translators.py) 阿里千问 3.8 实时会话参数中显式调优云端 `server_vad` 静默判定时间为 `320ms`，配合 DashScope `stash` 实时尾词双轨解析，令说话人句尾停顿后云端在 320ms 内极速定稿分句（较此前默认等待提速 180ms 以上），兼顾自然语流切分与极速跟手体验。

---

## 三、快捷键操作速查表

在悬浮窗处于激活状态或全局交互时，支持以下生产力快捷键：

| 快捷键 (macOS / Windows) | 动作名称 | 功能说明 |
| :--- | :--- | :--- |
| **`Cmd + Shift + L`**<br>`Ctrl + Shift + L` | **窗口位置防拖拽锁定/解锁** | 开启后浮窗位置固定防止误拖动（所有按钮保持鼠标悬停与点击响应），再次按下即可解锁恢复拖拽 |
| **`Cmd + Shift + T`**<br>`Ctrl + Shift + T` | **双语通道快速互切** | 在 `中 ➔ EN`（中译英）与 `EN ➔ 中`（英译中）之间瞬时平滑翻转 |
| **`Cmd + Shift + R`**<br>`Ctrl + Shift + R` | **双语视口比例快速切换** | 在 **`68:32`**（经典出厂比例）与 **`65:35`**（扩展原文比例）之间无缝瞬时切换，自动本地持久化记忆 |
| **`Cmd + Shift + C`**<br>`Ctrl + Shift + C` | **字体调色方案轮换** | 循环切换 5 套高对比配色（暖金 ➔ 腾讯白 ➔ 冰川青 ➔ 黑曜石 ➔ 薄荷绿） |
| **鼠标悬停顶部 24px 传感器** | **唤出控制胶囊** | 平时 100% 隐藏，鼠标移至顶端自动浮现通道药丸、配色药丸、位置锁、透明度与设置键 |
| **按住左上角把手 (`⠿`) 拖拽** | **120 FPS 窗口移动** | 硬件级无延迟拖拽窗口跨屏漫游 |

---

## 四、万级多维分类热词银行 (`glossary_bank/`)、云端容量水位仪与会议抽屉工作台

> [📖 查看全景热词分类与 18,449 词速查总览表 (GLOSSARY_INDEX.md)](GLOSSARY_INDEX.md)

针对大型跨国峰会、专业学术研讨、政务外事互访中出现的“专有名词识别漂移、突发嘉宾姓名生僻、行业专有术语翻译不准、云端 API 热词上限受限（1,000 词硬限制）”等现实挑战，系统构建了工业级万级多维分类标签热词银行架构。

### 1. 多维分类标签词包银行架构 (`glossary_bank/`)

热词库采用模块化分级存储体系，所有词包置于 `glossary_bank/` 目录下，包含 15 个标准化分类 JSON 词包，内置词条总量达 **18,449 条**：

| 分类层级 | 词包文件名 | 标签名称 | 默认状态 | 词条数 | 适用业务场景 |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **🔒 应急锁定** | `00_base_emergency.json` | 基础应急固定库 | **常驻锁定 (不可取消)** | 100 词 | 开箱即用高频纠错，保障突发会议基本盘 |
| **🟢 高频主力** | `01_party_gov_high.json` | 🏛️ 党建与政务(高频) | 默认开启 | 110 词 | 官方大会、政策宣讲、政务会议 |
| **🟢 高频主力** | `02_diplomacy_official_high.json` | 📜 政务与外交公文(高频) | 默认开启 | 120 词 | 外事互访、双边会谈、国际公约 |
| **🟢 常见主力** | `03_daily_items_common.json` | 📦 日常物品(常见) | 默认开启 | 116 词 | 商务贸易、展会介绍、跨国采购 |
| **🟢 常见主力** | `04_fruits_fresh_common.json` | 🍎 水果与生鲜(常见) | 默认开启 | 108 词 | 农产品贸易、跨国生鲜电商 |
| **🟢 常见主力** | `05_key_locations_common.json` | 🗺️ 重点地名(常见) | 默认开启 | 108 词 | 国际交通、全球重点枢纽城市 |
| **🟢 高频主力** | `06_classic_idioms_high.json` | 📖 经典成语(高频) | 默认开启 | 119 词 | 文化交流、主旨演讲高频成语 |
| **🟢 高频主力** | `07_ai_tech_high.json` | 🤖 AI与科技(高频) | 默认开启 | 116 词 | 人工智能开发者大会、前沿科技峰会 |
| **🟢 常见主力** | `08_spoken_slang_common.json` | 🗣️ 口语与热词(常见) | 默认开启 | 116 词 | 日常跨语种交流、青年峰会 |
| **🔵 专精扩展** | `09_party_specialized_rare.json` | 🏛️ 党建专用语(生僻) | 按需勾选 | 2,406 词 | 深度政策研讨、理论文献翻译 |
| **🔵 领域扩展** | `10_industry_items_uncommon.json` | 📦 工业与生活物品(不常见) | 按需勾选 | 3,006 词 | 制造业、重工业、精密仪器峰会 |
| **🔵 领域扩展** | `11_fruits_agricultural_rare.json` | 🍎 水果与农特产(生僻) | 按需勾选 | 2,406 词 | 专业农业交流、物种特产考察 |
| **🔵 领域扩展** | `12_world_locations_ext.json` | 🗺️ 国内外地名(扩展) | 按需勾选 | 3,306 词 | 国际地缘交流、全球地理细分 |
| **🔵 专精扩展** | `13_dialect_homophones_rare.json` | 🗣️ 地方方言谐音(生僻) | 按需勾选 | 3,006 词 | 地方口音声学鲁棒纠正 |
| **🔵 专精扩展** | `14_biomedical_clinical_expert.json` | 🧬 生物医药与临床(专精) | 按需勾选 | 3,306 词 | 跨国医药临床峰会、医疗学术研讨 |

- **总词库规模**：内置 18,449 词，完全涵盖主流国际会议及高壁垒垂直领域。
- **应急底线守护**：`00_base_emergency.json` 带有 `locked: true` 属性，不可被前端界面取消勾选，杜绝会场误操作清空底库。

### 2. 双轨容量水位仪与云端 1,000 词智能防爆截断 (Smart Capping)

阿里云百炼（DashScope）实时同传 WebSocket API 对 `session.update` 热词列表设有 **1,000 词硬上限**。一旦超出，服务端将直接返回 `InvalidParameter` 错误并阻断连接。为实现“万级热词储备与云端 API 稳定性兼得”，系统设计了双轨容量管理架构：

1. **四级推送优先级调度 (Priority Dispatching)**：
   - **`P0` 本场临时人名 (Session Guest Names)**：会议现场紧急输入的演讲嘉宾姓名与核心机构名，享有最高直推优先级；
   - **`P1` 基础应急库与个人永久词 (Base & Permanent Terms)**：`00_base_emergency.json` 及用户在 `glossary.json` 中配置的常驻词；
   - **`P2` 已勾选高频/常见分类标签 (High-Frequency Category Packs)**：用户按需启用的核心高频词包；
   - **`P3` 已勾选生僻/扩展分类标签 (Rare Category Packs)**：专精扩展词库。
2. **安全推送阈值（$\le 900$ 词）与智能防爆截断 (Smart Cap)**：
   - 系统设定 **900 词安全防护线**（保留 10% 冗余安全裕度）；
   - 当用户勾选多个超大词包（总词数达数千甚至上万）时，云端下发模块自动按 `P0 ➔ P1 ➔ P2 ➔ P3` 严格排序并截断至前 900 词；
   - 100% 杜绝因热词数量触碰 1,000 词硬上限而引发的 `InvalidParameter` 报错断网风险。
3. **健康等级三态监测**：
   - 🟢 `optimal`（$\le 750$ 词）：云端负载处于极佳状态；
   - 🟡 `warning`（$751 \sim 900$ 词）：接近 900 词安全线，提示会务人员适度优化标签；
   - 🔴 `capped`（$> 900$ 词）：触发智能截断保护，超出 900 词部分安全分流至本地离线引擎，云端连接绝对稳定。

### 3. 本地纯 Python Aho-Corasick 自动机全量挂载 (0 Token 开销)

虽然推送到云端模型的热词被安全截断在 900 词以内，但**本地词法纠错引擎 100% 全量挂载全部 18,000+ 词条**：
- **纯 Python 原生高效实现**：基于 Trie 树与广度优先搜索（BFS）构建失配指针（Failure Links），采用 `UnifiedAutomaton` 分层级联检索（Session ➔ User ➔ Bank）；
- **节点内存轻量化优化**：通过 `__slots__` 与延迟列表分配技术，使数万词条的 Trie 节点内存开销降低 73%（常驻内存仅约 46MB）；
- **毫秒级极速匹配**：对包含 100 字符的长句进行 18,000+ 词全量模式串扫描，实测匹配仅耗时 **0.0058ms**（远优于 $\le 0.15\text{ms}$ 的 SLA 指标）；
- **0 额外 Token 消耗**：本地纠偏在 WebSocket 数据广播前完成，不增加云端 Token 消耗，零 API 费用增量。

### 4. 国际会议临时专属人名与双层生命周期管控

国际会议常在开场前临时拿到外宾名单，系统支持双层生命周期管理：
1. **双层数据模型**：
   - **`⏱️ _session_data` (临时本场词)**：纯内存缓存，拥有最高 P0 优先级，会话中实时覆盖全局常驻词，不写入磁盘；
   - **`📌 _data` (永久常驻词)**：持久化写入根目录 `glossary.json`，服务重启后依然有效。
2. **多分隔符智能快速解析**：
   支持在快速添加框或多行文本区域批量粘贴名单，兼容多种自然输入格式：
   ```text
   张伟 = Wei Zhang
   苏姿丰 -> Lisa Su
   黄仁勋 => Jensen Huang
   李雷: Lei Li
   韩梅梅：Meimei Han
   ```
3. **会后一键处置机制**：
   - **`🧹 一键清空本场临时词`**（调用 `POST /api/glossary/session/clear`）：会后一键重置内存临时词，磁盘文件零改动，不污染下一次日常会议；
   - **`💾 一键转存为永久词库`**（调用 `POST /api/glossary/session/promote`）：若会议临时词具有长期复用价值，一键合并并持久化写入 `glossary.json`。

### 5. 系统全局配置抽屉可视化工作台 (`#config-drawer`)

大屏控台页面（`/` 或 `/split`）右上角提供独立的 **`📚 会议热词`** 工作台入口：
- **Apple Liquid Glass 分段选项卡**：优雅切换 `📚 会议热词工作台` 与 `⚙️ 系统基础配置`；
- **云端配额三色进度条**：直观展示 `☁️ 云端 API 热词负荷：X / 1,000 词 (上限)`，清晰标注 900 词安全警戒线与本地万词引擎挂载状态；
- **高频/生僻分类标签胶囊区**：提供 `🟢 主力分类标签 (高频 / 常见)` 与 `🔵 领域扩展标签 (生僻 / 不常见 · 可达万级)` 视觉分组，单选/多选即时热生效；
- **已激活热词实时同步明细表 (`#active-glossary-table`)**：与分类标签选择毫秒级双向联动，实时展示当前生效词汇全景；支持中英文双向实时模糊检索及按分类包/作用域下拉过滤；
- **录入前置冲突与覆盖检测探针 (`#conflict-probe-indicator`)**：录入词条时实时防抖比对，即刻呈现 🟢 全新词条直接生效、🟡 高优先级覆盖提示（提示覆盖底层官方包条目）、ℹ️ 完全一致无需重复；
- **单条与批量快加面板**：支持选择中译英、英译中或 ASR 纠错方向，自由选择存入「临时词」或「永久词」；
- **词条检索与独立删除**：支持按全量、临时、永久分类查看，实时模糊搜索，单条轻点 `✕` 即可即时删除；
- **严格 DOM 规范保障**：前端界面 100% 采用 `textContent` 与 `document.createElement()` 进行安全无损渲染，全代码严禁出现 `innerText`。

### 6. 自定义分类词包扩展指南 (`glossary_bank/`)

用户或集成开发商可随时为企业或特定行业扩充专属词包，操作方式如下：
1. 在 `glossary_bank/` 目录下新建 JSON 文件，例如 `99_custom_finance.json`；
2. 遵循以下标准 JSON 规范格式编写：
   ```json
   {
     "id": "custom_finance",
     "name": "跨国金融与财会",
     "icon": "💰",
     "tier": "rare",
     "priority": 3,
     "locked": false,
     "default_enabled": false,
     "description": "国际投行、跨境结算与衍生品专业术语",
     "asr_fixes": {
       "爱必达": "EBITDA",
       "纳斯达客": "Nasdaq"
     },
     "terms_zh_to_en": {
       "息税折旧摊销前利润": "EBITDA",
       "市盈率": "Price-to-Earnings Ratio"
     },
     "terms_en_to_zh": {
       "EBITDA": "息税折旧摊销前利润",
       "P/E Ratio": "市盈率"
     }
   }
   ```
3. 保存后系统将在后台自动扫描发现并挂载至本地自动机与抽屉工作台，无需重启后端服务。

---

## 五、完整技术栈清单

| 分层 | 组件 / 技术选型 | 版本要求 | 选型原由与工程实现 |
| :--- | :--- | :--- | :--- |
| **运行时底层** | Python (CPython) | 3.9 ~ 3.12 (推荐 3.11) | 兼容 Python 3.13（内置自适应 `audioop` C 级内存切片降级垫片） |
| **音频采集驱动** | PyAudio / PortAudio | 0.2.14+ | 独占低延迟硬件流，单帧切片 50ms（800 samples @ 16kHz 16-bit Mono） |
| **缓冲与防抖** | Drop-Oldest 环形隔离缓冲 | 自研 C/Python | `maxsize=3` 环形队列，网络偶发抖动绝对不造成声卡硬件 `Input overflowed` |
| **术语匹配内核** | Aho-Corasick Automaton | 高性能自动机 | 双向多模式串精准匹配，单句延迟 $< 0.15\text{ms}$，内存开销 $< 2\text{MB}$ |
| **云端同传引擎** | 阿里云百炼 MaaS 专有云 | Qwen 3.8 / Gummy-v1 | `qwen3.8-livetranslate-flash-realtime` 专有模型直通与公网 Gummy 兼容 |
| **网络网关服务** | FastAPI / Uvicorn | 0.110+ / 0.28+ | 高性能异步 ASGI 循环，WebSocket 广播配备 0.25 秒超时断路器 |
| **桌面视窗容器** | pywebview / Native OS Bridge | 5.0+ | macOS 基于 WKWebView，Windows 基于 Microsoft Edge WebView2 |
| **原生系统集成** | ctypes (AppKit / user32) | 系统原生 | 纯净透明窗底、macOS `performWindowDragWithEvent:`、Windows `SetWindowDisplayAffinity` |
| **渲染与排版** | HTML5 / CSS3 / ES6+ | Modern Web | 黄金比例 68%/32% 物理防挤压舞台、Apple Liquid Glass、定稿稳定驻留、100% 绝对稳态 |

---

## 六、跨平台快速部署指南 (Part 1: macOS & Part 2: Windows)

详细的分步图文部署与全平台踩坑 FAQ，请直接查阅：[`INSTALL.md`](INSTALL.md)

### Part 1: macOS 部署与极速启动
```bash
# 1. 克隆仓库并创建虚拟环境
git clone https://github.com/xiaokunshi5-lang/harry-translate.git
cd harry-translate
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 2. 复制配置模板并填入阿里云百炼 API Key (首次使用)
cp .env.example .env
open -e .env

# 3. 双击启动脚本或在终端运行
./启动悬浮同传.command
```

### Part 2: Windows 部署与极速启动
```cmd
:: 1. 克隆仓库并创建虚拟环境
git clone https://github.com/xiaokunshi5-lang/harry-translate.git
cd harry-translate
python -m venv .venv
call .venv\Scripts\activate.bat
pip install -r requirements.txt

:: 2. 复制配置模板并填入阿里云百炼 API Key (首次使用)
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
| `GET` | `/api/glossary` | 无 | JSON | 查询当前语料库、配额水位仪状态、分类词包列表与临时/永久词汇 |
| `POST` | `/api/glossary` | JSON: 批量更新、单条添加或多行文本导入 (`is_session: true/false`) | JSON | 动态热更新语料库并即时重载，耗时 $<5\text{ms}$ |
| `POST` | `/api/glossary/session/clear` | 无 | JSON | 一键清空本场临时嘉宾人名词库，0 磁盘改动 |
| `POST` | `/api/glossary/session/promote` | 无 | JSON | 一键将本场临时词转正并持久化合并写入 `glossary.json` |
| `POST` | `/api/glossary/toggle_pack` | JSON: `{"pack_id": "...", "enabled": true}` | JSON | 动态启用或关闭指定分类词包（锁定词包受保护） |
| `POST` | `/api/glossary/delete` | JSON: `{"direction": "...", "key": "...", "scope": "..."}` | JSON | 删除指定的临时词或常驻词 |
| `GET` | `/api/glossary/hotwords` | 无 | JSON | 获取经过 P0-P3 智能截断（<=900 词）的云端热词数组与状态 |
| `GET` | `/api/glossary/terms/active` | 可选 Query: `?q=...&category=...&scope=...&limit=500` | JSON | 获取当前全部已激活生效热词明细，支持中英文检索与分类/作用域筛选 |
| `POST` | `/api/glossary/check_conflict` | JSON: `{"source": "...", "target": "...", "category": "...", "is_session": false}` | JSON | 录入前置冲突与覆盖检测探针（实时判定全新词、高优先级覆盖或完全一致） |
| `GET` | `/api/meta` | 无 | JSON | 查询系统运行状态、活跃声卡、引擎类型及脱敏 API Key |
| `GET` | `/api/config` | 无 | JSON | 查询当前模型、采样率及通道状态 |
| `POST` | `/api/config` | JSON: `{"dashscope_api_key": "...", "engine": "..."}` | JSON | 动态热更新配置，支持空键保护防误清空 |
| `GET` | `/api/audio/devices` | 无 | JSON | 枚举本机全部可用物理麦克风与虚拟内录回环声卡 |
| `POST` | `/api/audio/device` | Query / JSON: `{"device_index": 2, "channel": "A"}` | JSON | 零重启热插拔切换采集声卡（SLA <80ms） |
| `GET` | `/api/hud/lock` | 可选 Query: `?locked=true&window_id=en` | JSON | 查询或修改悬浮窗防拖拽锁定状态（支持 `window_id=en/zh` 分窗独立锁定与查询） |
| `POST` | `/api/hud/lock` | JSON: `{"locked": true, "window_id": "en"}` | JSON | 远程锁定或解除悬浮窗位置锁定（支持双浮窗独立锁定，不传 `window_id` 时全局一键控制） |
| `GET` | `/api/stats` | 无 | JSON | 实时查询全场 Token 用量明细与折合费用 |
| `POST` | `/api/stats/reset` | 无 | JSON | 重置会话 Token 与费用累计计数器 |

---

## 八、基准测试与系统性能指标

| 评测维度 | 考核指标 | SLA 达标阈值 | 生产实测数值 | 评测结论与工程保障 |
| :--- | :--- | :--- | :--- | :--- |
| **音频微切片** | 采集切片长度 | 50.0ms (800 采样点) | **50.0ms / 1600 字节** | 严格锁定 16kHz 16-bit Mono，消除积压 |
| **远场音频增益** | 1~2米远场软限幅 AGC 增益耗时 | $< 0.01\text{ms}$ | **0.0023ms (2.3µs)** | C 级自适应双曲正切软限幅，微弱拾音自动提振 $1.8\times \sim 2.5\times$ 杜绝爆音 |
| **云端断句收敛** | 阿里云百炼 Server VAD 静默判停 | $\le 400\text{ms}$ | **320ms** | 句尾 320ms 极速收敛断句，较旧版默认等待提速 180ms 以上 |
| **悬浮窗同步直写**| UI 帧渲染微任务上屏时延 | $< 0.01\text{ms}$ | **0.0018ms (1.8µs)** | 同步 DOM 直写 + `#historyLine` 两级视口，彻底消除与普通窗口体感差异 |
| **术语匹配时延** | 5000 词库单句纠错 | $< 0.5\text{ms}$ (目标 $\le 0.15\text{ms}$) | **0.031ms (31µs)** | Aho-Corasick 多模式自动机，体感 0 延迟 |
| **万级词库挂载** | 18,000+ 词全量匹配 | $< 0.25\text{ms}$ (目标 $\le 0.15\text{ms}$) | **0.0058ms (5.8µs)** | Aho-Corasick 节点轻量化，内存仅 46MB，0 Token |
| **云端配额保护** | 1,000 词 API 硬上限防爆 | 严格 $\le 900$ 词推送 | **$\le 900$ 词 (P0~P3 Smart Cap)** | 100% 杜绝 `InvalidParameter` 错误，连接永续 |
| **单态透明稳定性** | 连续发言与静默对比 | $\Delta \text{opacity} = 0.0$ | **$\Delta \text{opacity} \equiv 0.0$** | 彻底剥离系统 VEV，纯 WebKit 控色零多态晃动 |
| **双视口防挤压** | 原文区 200 字涌入 | 主区高度变动 $\le 1\text{px}$ | **0px 变动 (68%/32% 物理隔离)** | 原文再长也绝不挤压主译文行高 |
| **热路径分发** | 单帧 C 级直推耗时 | $< 0.015\text{ms}$ | **0.0029ms (2.9µs)** | 5000 帧循环压测实测耗时 14.93ms |
| **端到端延迟** | 首字上屏总延迟 | $< 500\text{ms}$ | **320ms ~ 425ms** | 阿里云百炼千问 3.8 / Gummy-v1 实测 |
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

项目内置完备的自动化质量守卫矩阵，包含 315 项自动化测试用例与 16 维工厂级终审审计门禁，代码变动必须通过全部验收测试：

```bash
# 1. 运行 315 项全量自动化测试套件 (包含 246 项 E2E 阶梯测试 + 69 项专项对抗/词库/自适应/流式对齐验证)
.venv/bin/python -m unittest discover -s tests -p 'test_*.py'

# 2. 运行 246 项核心 E2E 阶梯自动化测试 (涵盖 Tier 1~4 功能、边界、黄金比例双视口与术语引擎)
.venv/bin/python tests/run_e2e_tests.py

# 3. 运行 16 维工厂级终审审计门禁 (含 50ms 零拷贝、425ms 延迟、AC-09 控件数等)
.venv/bin/python tests/audit_gate.py

# 4. 运行腾讯会议绝对稳态悬浮与 5 套字体配色专项测试 (AC-V1 ~ AC-V5)
.venv/bin/python -m unittest tests/test_tencent_steady_hud_and_themes.py

# 5. 运行单态对抗极限压测 (连续 10s 静默与流式吐字，断言 delta opacity == 0.0)
.venv/bin/python -m unittest tests/challenger_steady_hud_adversarial.py

# 6. 运行专精术语语料库、分类标签银行与黄金比例双视口测试 (AC-G1~G8, AC-L1~L5)
.venv/bin/python -m unittest tests/test_glossary_and_golden_ratio_layout.py

# 7. 运行严格 DOM 与工作台抽屉审计测试 (断言 0 innerText，验证 15 项核心配置 ID)
.venv/bin/python tests/verify_m4_v5.py

# 8. 运行小窗口两行主译文零裁切物理包络复现与回归测试
.venv/bin/python -m unittest tests/repro_issue_twoline_output_clip.py

# 9. 运行中文原文辅助区 31px 安全包络防削顶复现与回归测试
.venv/bin/python -m unittest tests/repro_issue_chinese_input_clip.py

# 10. 运行 68:32 ⇄ 65:35 双模舞台比例自适应与快捷键测试
.venv/bin/python -m unittest tests/test_hud_dual_ratio_mode.py

# 11. 运行 HUD 纯位置防拖拽锁定、全屏置顶 flags、实时同步表与冲突探针专项回归测试
.venv/bin/python -m unittest tests/test_hud_lock_and_active_glossary_sync.py

# 12. 运行 EXP-106 HUDPanelHost 全屏空间穿透与 4 重物理硬锁真实 Cocoa 门禁测试
.venv/bin/python -m unittest tests/test_repro_exp106_hud_panel_lock_fullscreen.py

# 13. 运行 EXP-107 双悬浮同传窗口独立位置锁定与分窗隔离真实 Cocoa 门禁测试
.venv/bin/python -m unittest tests/test_repro_exp107_dual_hud_independent_lock.py

# 14. 运行 EXP-108 悬浮同传与普通窗口同传流式对齐、速度与历史留存自动化测试 (28 项用例)
.venv/bin/python -m unittest tests/test_float_window_parity_and_speed.py

# 15. 运行 EXP-108 极端并发对抗与 UI 引擎抗压测试 (WebKit 极速帧压测与孤儿线程防护)
.venv/bin/python -m unittest tests/challenger_ui_engine_stress.py
```

---

## 十一、版本安全恢复机制

公开版本不附带会覆盖文件的自动回滚脚本。遇到复杂异常或需要恢复稳定状态时，先用 Git 保存本地修改，再切换已发布标签：
```bash
git status
git switch -c local-backup
git switch --detach v3.9.0
```
- `.env` 与 `.venv` 被 `.gitignore` 排除，不会因切换标签被删除或覆盖；
- 如需回到自己的修改，执行 `git switch local-backup`；
- 遇到无法安全处理的数据损坏时，先备份整个项目目录再操作。

---

## 十二、开源许可与服务声明

- 本系统基于 Apache 2.0 开源许可协议发布，完整许可证文本详见项目根目录下的 [`LICENSE`](LICENSE) 文件；
- 语音实时翻译能力基于阿里云百炼平台（DashScope）大模型服务，用户需自备有效的 API Key 并遵守相应服务条款。
