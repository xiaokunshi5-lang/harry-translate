# Changelog

All notable changes are documented here. The project follows Semantic
Versioning for public releases.

## [4.0.0] - 2026-11-07

### Added

- **Apple VisionOS 液态玻璃美学 HUD（方案 A）**：
  - 深度集成现代空间拟态：`backdrop-filter: blur(20px) saturate(190%) contrast(102%)`，在保留桌面背景通透感的同时提供顶级文字沉浸度；
  - 顶部微米级镜面高光棱镜边框（`inset 0 1px 0 rgba(255, 255, 255, 0.18)`），深浅色背景自适应；
  - 三大语义化动态胶囊：`#hud-channel-pill`（呼吸发光通道指示）、`#hud-theme-pill`（明暗玻璃随心切）、`#hud-fontsize-pill`（字号档位指示）；
  - 引入 Emil Kowalski 弹性物理动效曲线 `cubic-bezier(0.16, 1, 0.3, 1)`，微交互手感紧凑灵动；
  - 金属质感三段式点阵拖拽角标，优化视觉抓握暗示，移除侵占事件的原生拖拽限制。
- **三档响应式主译文字号排版系统（🔤 标准 / 🔤 大号 / 🔤 特大）**：
  - 标准视口下主译文与历史行弹性分级：`🔤 标准`（19px / 15px）、`🔤 大号`（24px / 18px）、`🔤 特大`（29px / 21px）；
  - PPT 扁平紧凑视口（<=75px 高度）智能破锁放大：默认 15px/12px，大号自适应破锁至 20px/15px，特大破锁至 24px/17px，且最新吐字自动平滑滚动保留 >=1.5px 下沿呼吸区绝不切字；
  - 辅助对照原文行（`#pastLine`）恒定保持 14px（紧凑视口 12px），无论主字如何放大均 0px 挤压原文；
  - 交互支持点击 `#hud-fontsize-pill` 胶囊循环轮转、全局快捷键 **`Cmd + Shift + F`**（Windows **`Ctrl + Shift + F`**）及 `Cmd/Ctrl + =` / `Cmd/Ctrl + -` 弹性微调，并通过 `localStorage` 键名 `qwen_hud_font_tier` 永久记忆。
- **Cocoa & WebKit 全时事件穿透与追踪（根治顶部 Hover 失灵）**：
  - 彻底移除 `body` 顶部 6px padding 边距死区，实现 0px 贴顶物理级即时捕获；
  - 新增全视口近距追踪感应器 `handleTopZoneProximity`，结合 `isHoveringTopZone` 独立状态机，消除 WebKit 在非激活窗口下的 `:hover` 伪类抑制；
  - AppKit 原生层注入 `acceptsFirstMouse_ -> YES` 与 `NSTrackingActiveAlways`（`0x80`）全时追踪区，确保后台悬浮状态下鼠标滑入即刻响应。
- **Ponytail 架构精简、Dock 策略锁与路径自愈**：
  - 消除 5 处冗余的 `setActivationPolicy_` 调用，统一步伐；
  - 锁定 `NSApplicationActivationPolicyAccessory (1)`，彻底拦截 pywebview 等第三方库重置常规激活策略导致的 macOS Dock 幽灵 Python 图标；
  - `HUDWebKitHost.loadRequest_` 自动拦截并自愈含中文或空格路径的 `%2520` 双重编码异常，完好保留 query 参数；
  - 重构控制器寻址逻辑，提炼通用的 `_resolve_target_controller(window_id)` 支持单/双/动态窗口；
  - 升级后台线程退出机制为 `threading.Event().wait(1.0)` 与 `.set()` 信号，实现窗口销毁时毫秒级瞬时退出。
- **会议级同传流式渲染与去重加固 (FIX-205 ~ FIX-207)**：
  - 云端热词自动同步帧瘦身至 `<= 48` 高优词（UTF-8 配置帧 `< 2.5KB`），本地 18,449 词全量由纯 Python Aho-Corasick 自动机以微秒级离线纠错；
  - 远场温和自适应 AGC 黄金调优（`target_rms=1200.0, max_gain=3.2, noise_floor=240.0, soft_knee=280.0`），云端 VAD 判停优化至 240ms，辅以连续语音 2.4s 遇能量低谷（RMS < 380）或 3.8s 强制上限主动发送 `commit`；
  - 音频上行解耦为有界无锁队列（`_tx_queue <= 64`）与独立工作线程，零阻塞声卡采集；
  - 双阶微停顿合并状态机（`300ms` 意群合并 / `450ms` 段落保持），移除开口清空主字体逻辑，新句首包到达前保留前句视觉锚点，消除黑屏闪烁；
  - 双悬浮窗广播层双语对称镜像（中译英广播至 `/ws/en` 同时对调镜像至 `/ws/zh`，对象属性严格隔离），配合 `sanitizeTargetForChannel` 高性能语种纯度锁与同语种空回声抑制；
  - 网页控制台（`index.html`）引入 `activeNodeMap` 映射与 DOM 卡片节点复用机制，彻底根除网络重连多帧推送导致的重复刷屏。

## [3.9.1] - 2026-10-30

### Added

- **官方公网 WebSocket 直连与智能路由**：移除内部专有 MaaS 实例强依赖，`.env.example` 默认走阿里云百炼官方公网 WebSocket 网关（`wss://dashscope.aliyuncs.com/...`），普通 DashScope API Key 开箱即用；保留 `sk-ws-` 前缀业务空间 Key 专用端点兼容性。
- **Web 控台 ⚙️ 动态更新 API Key 零重启热生效**：解决无 Key 首次启动后更新密钥必须杀掉程序重启的痛点，新增 `update_api_key` 并在后台线程异步平滑重载激活引擎。
- **7 态细粒度连接状态机与假绿灯清零**：服务端与前端精准定义并暴露 `ready`、`connecting`、`auth_failed`（401/403 明确报错并停止无谓重试）、`rate_limited`（429 自适应退避）、`network_error`、`mock`、`no_key` 状态，主控大屏与悬浮窗告警透明化。
- **音频硬件热拔插自愈与安全降级**：USB 麦克风拔出或底层声卡断开时，系统底层自动捕获 I/O 故障并重新枚举有效设备，安全回退至系统默认麦克风，杜绝服务端闪退。
- **Windows 启动脚本 100% 语法稳定与零配置自举 (Zero-Config Bootstrap)**：
  - 彻底转义 Windows 批处理 `if/else` 括号块内的中文括号语法炸弹；
  - 5 个 `.bat` 启动脚本全面实现自动化自愈：首次启动若无 `.env` 自动从 `.env.example` 复制生成，若无 `.venv` 自动创建虚拟环境并一键安装 `requirements.txt`；
  - 完美兼容 Win11 24H2（智能检测 `wmic` 是否可用，并在缺失时平滑回退 PowerShell 清理孤儿进程）；
  - 新增 `.gitattributes` 锁定 Windows 换行符（CRLF）与 Unix 换行符（LF）。
- **macOS `portaudio` C 底层库缺失智能自愈**：`start.sh` 与 5 个 `.command` 脚本在编译安装 `PyAudio` 报错时，自动检测 Homebrew 并自愈安装 `portaudio`。
- **服务端默认 `127.0.0.1` 本机安全监听与 `HOST=0.0.0.0` 局域网大屏广播**：默认绑定本地回环地址，严防公共 Wi-Fi 下未授权访问与字幕泄露；提供 `.env` 环境变量 `HOST` 供用户按需开启局域网投屏。
- **真实端到端单句首字延迟（TTFT，`ttft_ms`）度量**：精准记录从人声开口（VAD 检出）到首个译文增量返回的生理延迟，与定稿延迟 `latency_ms` 构成双轨度量矩阵。
- **Token 计费单价环境变量动态配置**：新增 `INPUT_TOKEN_PRICE_PER_M` 与 `OUTPUT_TOKEN_PRICE_PER_M`，随阿里云官方模型调价灵活配置，计费看板金额精确无误。
- **Aho-Corasick 自动机 ASCII 英文单词边界保护**：短英文词（如 `AI`、`PR`、`IT`）仅在独立成词或中英混排时触发替换，杜绝在普通英文单词内部（如 `rain`、`spring`、`OpenAI`）误截断替换，同时保持 $<0.02\text{ms}$ 的极致匹配性能。
- **Windows 热词库跨目录绝对路径硬锚定与云端优先注入**：
  - 基于工程根目录绝对路径硬锚定（`_PROJECT_ROOT`），解决 Windows 快捷方式及跨目录启动时找不到 `glossary.json` 与 `glossary_bank/` 的问题；
  - 实现了中英双向结构化语料包（Corpus Phrases）向云端模型的流式注入；
  - 900 词配额满额时，严格优先保全用户在现场临时指定的即时热词（speech-only 与 phrase mapping），杜绝因云端配额满载导致现场热词被静默丢弃；
  - 增强 WebSocket 连接网络诊断与本地地址回退机制。

## [3.9.0] - 2026-10-27

### Added

- 悬浮同传零丢帧同步 DOM 直写机制：彻底剥离动画微任务排队与宏任务调度，收到 WebSocket 实时帧即刻执行无锁同步直写（$0.0018\text{ms}$ 极速上屏），消除悬浮同传与普通窗口同传之间的速度与内容体感差异。
- `#historyLine` 历史定稿平滑留存两级视口：说话人停顿或换句时，上一句定稿译文瞬时平滑提升并稳固锚定在上方 `#historyLine`（字体微收敛为 13px 半透明暗字），下方 `#streamLine` 原子清空并即刻承接新一句话流式吐字，彻底根除前文瞬间蒸发断层。
- 1~2 米远场自适应软限幅自动增益 (Far-Field Adaptive Soft-Knee AGC)：在 50ms 音频微切片热路径中内嵌微秒级算法（$0.0023\text{ms}$），动态提振微弱拾音 $1.8\times \sim 2.5\times$ 能量并过滤底噪，双曲正切软限幅平滑防爆音。
- 云端 320ms 极速 Server VAD 断句调优：阿里千问 3.8 实时会话显式调优 `server_vad` 静默判定时间为 `320ms`，配合 DashScope `stash` 尾词双轨解析，令句尾停顿后极速定稿分句。
- macOS `NSActivityLatencyCritical` 原生抗 App Nap 后台节流保活令牌，确保浮窗长期非激活状态下仍维持最高事件调度优先级。
- 开箱即用出厂配置加固：统一端口默认 8000、50ms 零拷贝微切片（1600 字节）、默认千问 3.8 实时同传模型。
- 全量自动化质量防护矩阵：扩充至 315 项全绿用例（包含 246 项 E2E 阶梯测试与 28 项流式对齐专项测试）。

## [3.8.0] - 2026-10-26

### Added

- 万级多维分类热词银行 (`glossary_bank/`)：内置 15 个标准化分类 JSON 词包，涵盖 18,449 真实专业词条与 ASR 谐音纠正。
- 全景热词速查与索引指南 (`GLOSSARY_INDEX.md`) 及 4 级优先级级联调度体系 (`P0 > P1 > P2 > P3`)。
- 双轨容量水位仪与云端 1,000 词硬上限智能防爆截断 (`Smart Cap <= 900`)，本地纯 Python Aho-Corasick 自动机全量挂载 0 Token 开销。
- 会议主控室抽屉工作台已激活热词实时同步明细表 (`#active-glossary-table`) 与前置冲突探针 (`#conflict-probe-indicator`)。
- `HUDPanelHost` 原生非激活面板架构：基于 macOS `NSPanel` + `Accessory` + `collectionBehavior=337` + `level=1000`，实现 Keynote / PPT / 腾讯会议全屏 Spaces 穿透常驻且点击不切屏。
- 4 重物理硬锁防拖拽架构：点击锁定键剥离缩放掩码并物理拦截窗口位移指令，同时保持顶栏按钮 100% 鼠标悬停与点击交互能力。
- 双悬浮同传窗口（`--dual`）分窗独立锁定控制：中译英与英译中悬浮窗支持独立加锁与独立解锁，互不干扰。

## [3.6.0] - 2026-10-22

### Added

- Initial public baseline for Harry Translate.
- Dual-channel real-time meeting interpretation HUD.
- Qwen live translation and glossary support.
- macOS and Windows launch scripts.
- Portable installation, security, contribution, and licensing documents.
- GitHub Actions validation and Dependabot configuration.

### Security

- The public repository starts from a clean single-commit history.
- Local `.env`, virtual environments, mirrors, snapshots, recordings, and
  generated test reports are excluded.
- Security-sensitive dependencies are pinned at or above patched releases.

[4.0.0]: https://github.com/xiaokunshi5-lang/harry-translate/releases/tag/v4.0.0
[3.9.1]: https://github.com/xiaokunshi5-lang/harry-translate/releases/tag/v3.9.1
[3.9.0]: https://github.com/xiaokunshi5-lang/harry-translate/releases/tag/v3.9.0
[3.8.0]: https://github.com/xiaokunshi5-lang/harry-translate/releases/tag/v3.8.0
[3.6.0]: https://github.com/xiaokunshi5-lang/harry-translate/releases/tag/v3.6.0
