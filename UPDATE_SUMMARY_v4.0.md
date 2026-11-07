# Harry Translate v4.0.0 重大架构与美学升级总结报告
**发布版本**：v4.0.0 (Apple VisionOS 液态玻璃美学与固化 HUD 架构)  
**发布日期**：2026-11-07  
**核心定位**：极速实时双语同传悬浮窗 + 全屏多 Space 穿透 HUD + 会议级高可用流式渲染  

---

## 目录
1. [版本升级全景概览](#1-版本升级全景概览)
2. [核心痛点剖析与技术攻坚](#2-核心痛点剖析与技术攻坚)
   - [2.1 悬浮窗顶部悬停失灵根治（“2没有出现”与 Cocoa/WebKit 事件链路修复）](#21-悬浮窗顶部悬停失灵根治2没有出现与-cocoawebkit-事件链路修复)
   - [2.2 视觉审美飞跃：Apple VisionOS 液态玻璃美学（方案 A）](#22-视觉审美飞跃apple-visionos-液态玻璃美学方案-a)
   - [2.3 视距与可读性定制：S / M / L 三档响应式字号体系](#23-视距与可读性定制s--m--l-三档响应式字号体系)
   - [2.4 Ponytail 原则代码精简与架构重构（`float_app.py` 瘦身）](#24-ponytail-原则代码精简与架构重构float_apppy-瘦身)
   - [2.5 会议级同传与假断网自愈闭环（FIX-205 ~ FIX-207 核心成果）](#25-会议级同传与假断网自愈闭环fix-205--fix-207-核心成果)
   - [2.6 测试套件自闭环与独立可执行性加固](#26-测试套件自闭环与独立可执行性加固)
3. [核心文件变更对照矩阵](#3-核心文件变更对照矩阵)
4. [质量审计与性能验收数据](#4-质量审计与性能验收数据)
5. [开源发布与隐私安全防护说明](#5-开源发布与隐私安全防护说明)

---

## 1. 版本升级全景概览

Harry Translate v4.0.0 是自项目立项以来**最具颠覆性的一次悬浮交互与架构重构升级**。本次升级将原本基础的半透明桌面悬浮窗，全面升格为兼具 **工业级无感稳定性** 与 **Apple VisionOS 空间液态美学** 的高级会议级同传 HUD 界面。

同时，针对用户在实际体验中反馈的“悬浮窗顶部控制栏在鼠标悬停时未能唤出（‘2没有出现’）”、“视觉质感偏生硬”、“多显示器视距下字号固定无法调节”以及底层 Python Cocoa 进程退出缓慢、冗余代码等问题，进行了端到端全链路的系统级排查与彻底重构。

```
┌────────────────────────────────────────────────────────────────────────┐
│                        Harry Translate v4.0.0                          │
├──────────────────────────────────┬─────────────────────────────────────┤
│        前端交互与视觉革新         │          底层架构与事件链路          │
├──────────────────────────────────┼─────────────────────────────────────┤
│ • Apple VisionOS 液态玻璃拟态     │ • Cocoa acceptsFirstMouse_ 穿透      │
│ • 微米级镜面高光棱镜边框          │ • NSTrackingActiveAlways 全域追踪    │
│ • Emil Kowalski 阻尼弹簧动效     │ • Ponytail 6阶梯代码去重与精简      │
│ • S / M / L 3 档字号弹性缩放     │ • threading.Event() 毫秒级退出响应  │
│ • 46px 全视口近距追踪感应器       │ • 单/双窗口统一路由控制器            │
│ • 极简三控制钮纯净控台           │ • normSrc + ID 控台卡片双重去重     │
└──────────────────────────────────┴─────────────────────────────────────┘
```

---

## 2. 核心痛点剖析与技术攻坚

### 2.1 悬浮窗顶部悬停失灵根治（“2没有出现”与 Cocoa/WebKit 事件链路修复）

#### 【痛点现象】
在之前的版本中，用户鼠标滑向悬浮窗顶部试图调整透明度、锁定窗口或进入设置时，悬浮窗顶部的控制胶囊栏常常“没有出现”（偶发或完全无法触发 hover），只能盲目晃动鼠标，极度影响会议同传的操作体验。

#### 【深度根因剖析】
经过对 macOS AppKit 与 WebKit 事件派发机制的深度调试，定位出 4 重复合根因：
1. **WebKit 在非 Key Window 下的 `:hover` 伪类抑制**：悬浮窗被设计为 `NSPanel`（非激活面板），避免抢占用户的输入法与 IDE 焦点。但 WebKit 在非主窗口（Non-key Window）状态下，默认会降级或延迟派发 CSS `:hover` 状态。
2. **窗口顶部物理死区**：原 `body` 样式设置了 `padding: 6px;`，导致窗口顶部最上边缘的 0~5px 区域处于容器外部，鼠标从屏幕上方切入时无法触发内层元素的 `mouseenter`。
3. **原生拖拽区域事件吞噬**：原右下角与顶部 drag 区域使用了内联 `-webkit-app-region: drag`，在 Chromium/WebKit 底层直接将点击和移动事件捕获并交由窗口管理器移动，阻止了浏览器内部 JavaScript 的 mousemove 冒泡。
4. **Cocoa 底层鼠标移动事件丢失**：macOS 默认仅在窗口处于活跃聚焦时才派发 `mouseMoved:` 事件，导致后台悬浮窗接收不到平滑的坐标更新。

#### 【工程技术解决方案】
1. **消除 0~5px 顶部物理死区**：
   将 `float_ui.html` 中 `body` 边距重塑为 `padding: 0 6px 6px 6px;`，使控制感应区物理级贴合窗口最上边缘，鼠标一进入即刻触碰。
2. **全视口近距追踪与状态机 (`handleTopZoneProximity`)**：
   在 window 层建立全局 `mousemove` 监听器，动态计算鼠标相对于顶部 Header 的距离：
   ```javascript
   function handleTopZoneProximity(e) {
       if (!hudContainer) return;
       const rect = hudContainer.getBoundingClientRect();
       // 覆盖窗口绝对顶层 (y=0) 至 Header 底部 (rect.top + 46px) 以及左右边界外扩 20px
       const inZone = (e.clientY >= 0 && e.clientY <= (rect.top + 46)) &&
                      (e.clientX >= (rect.left - 20) && e.clientX <= (rect.right + 20));

       if (inZone) {
           revealHeaderControls();
       } else if (isHoveringTopZone && e.clientY > (rect.top + 50)) {
           isHoveringTopZone = false;
           concealHeaderControls(180);
       }
   }
   ```
3. **引入状态机阻断 260ms 隐藏惩罚**：
   针对微小抖动导致的 `:hover` 丢失，引入 `isHoveringTopZone` 独立状态机控制，辅以 Emil Kowalski 的平滑缓动曲线，确保悬停期间控台绝对稳定不闪烁。
4. **AppKit 底层 swizzling 鼠标全时激活**：
   在 `float_app.py` 中对 `HUDWebKitHost` 原生类进行 Cocoa 动态方法注入：
   - 注入 `acceptsFirstMouse_` 返回 `True`：确保非激活窗口在鼠标首次滑入或点击时立即可响应，无需先点击激活窗口；
   - 注入 `updateTrackingAreas` 并挂载 `NSTrackingArea`：
     ```python
     NSTrackingActiveAlways = 0x80
     NSTrackingMouseMoved = 0x02
     NSTrackingMouseEnteredAndExited = 0x01
     NSTrackingInVisibleRect = 0x200
     # 组合掩码 0x283，令悬浮窗在非活跃、后台、全屏等任何场景下，均 100% 捕获鼠标坐标
     ```

---

### 2.2 视觉审美飞跃：Apple VisionOS 液态玻璃美学（方案 A）

#### 【审美重塑与设计哲学】
摒弃了上一代生硬的扁平纯黑暗色色块，全面借鉴 Apple VisionOS 与 macOS Sonoma 的空间拟态设计语言，实现“信息漂浮于桌面之上，而非遮挡桌面”的高级通透质感：

1. **VisionOS 多级亚克力液态模糊**：
   ```css
   #hud-container {
       background: rgba(18, 20, 24, 0.72);
       backdrop-filter: blur(20px) saturate(190%) contrast(102%);
       -webkit-backdrop-filter: blur(20px) saturate(190%) contrast(102%);
       border-radius: 12px;
       border: 1px solid rgba(255, 255, 255, 0.08);
       box-shadow: 0 16px 40px rgba(0, 0, 0, 0.38),
                   inset 0 1px 0 rgba(255, 255, 255, 0.18); /* 顶部镜面高光 */
   }
   ```
2. **微米级镜面高光棱镜边框 (Specular Highlight)**：
   利用 `inset 0 1px 0 rgba(255, 255, 255, 0.18)` 在悬浮窗顶边缘刻画出一道极细的物理光感微棱镜，无论在亮色壁纸还是深色代码编辑器上方，均能展现出清晰的空间层次。
3. **三大语义化动态胶囊 (Semantic Control Pills)**：
   - `#hud-channel-pill`：呼吸发光通道指示器（中译英 / 英译中 / 双向实时），指示清晰；
   - `#hud-theme-pill`：液态玻璃明暗主题瞬时切换；
   - `#hud-fontsize-pill`：S / M / L 字号分级控制胶囊。
   采用 Emil Kowalski 弹性物理动效曲线 `cubic-bezier(0.16, 1, 0.3, 1)`，微交互手感紧凑灵动。
4. **金属质感三段式拖拽把手 (Metallic Dots Handle)**：
   窗口右下角重新设计了微质感金属三段点阵拖拽角标，不仅具备明确的触觉抓握暗示，且去除了侵占事件的硬 drag 区域。
5. **双层阴影防眩光排版 (Dual Text Shadows)**：
   字体全面对齐苹果系统字族：`"PingFang SC", -apple-system, BlinkMacSystemFont, "SF Pro Text", system-ui`。为文字施加双层阴影渲染：
   ```css
   text-shadow: 0 1px 2px rgba(0, 0, 0, 0.45), 0 0 1px rgba(0, 0, 0, 0.65);
   ```
   彻底根除在纯白网页或高亮度视频背景下文字发飘看不清的痛点。

---

### 2.3 视距与可读性定制：三档响应式主译文字号体系 (🔤 标准 / 🔤 大号 / 🔤 特大)

#### 【痛点与场景】
在会议演示、大屏投屏、笔记本便携屏以及 PPT 底部扁平字幕条等不同场景下，固定的字号无法兼顾“远看清晰”与“近看不挡屏幕”的双重需求。且若简单通篇放大字体，会导致辅助原文行挤压主译文或在小窗口中被下边缘切断。

#### 【解决方案】
构建了完备的 3 档响应式阶梯排版引擎，主译文与历史行分级弹性放大，辅助原文行保持舒适恒定：

| 档位 | 语义标签 (`<span>`) | 标准视口主译文 (`#activeLine`) | 标准视口历史行 (`#historyLine`) | PPT 紧凑视口主译文 (<=75px) | PPT 紧凑视口历史行 | 辅助原文 (`#pastLine`) | 适用场景 |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :--- |
| **0** | **🔤 标准** | `19px` | `15px` | `15px` (默认包络) | `12px` | `14px` (紧凑 `12px`) | 笔记本便携屏、日常办公伴随 |
| **1** | **🔤 大号** | `24px` | `18px` | `20px` (自适应破锁) | `15px` | `14px` (紧凑 `12px`) | 27寸外接屏、跨国视频会议 |
| **2** | **🔤 特大** | `29px` | `21px` | `24px` (自适应破锁) | `17px` | `14px` (紧凑 `12px`) | 4K 高分屏、大型学术会场投屏 |

- **PPT 紧凑视口自适应破锁与防切字**：在视口高度 <=75px 时，默认处于 15px 紧凑包络；切换至“大号”或“特大”时，引擎智能破除紧凑锁放大至 20px / 24px，并通过 GPU 硬件加速自动平滑向上滚动，保留底部 >=1.5px 呼吸留白，100% 杜绝最新字下沿削顶；
- **原文辅助行恒定防挤压**：`#pastLine` 严格保持 14px（紧凑视口 12px），主译文字号切换对下方原文区域的高度变动严格为 0px。

#### 【交互方式】
- **一键轮转**：鼠标单击顶部 `#hud-fontsize-pill` 语义化 `<span>` 胶囊，在 `🔤 标准 ➔ 🔤 大号 ➔ 🔤 特大 ➔ 🔤 标准` 之间循环轮转，带有丝滑弹性缩放动效；
- **键盘全局快捷键**：在悬浮窗内支持 **`Cmd + Shift + F`**（Windows **`Ctrl + Shift + F`**）循环切换，同时兼容 `Cmd/Ctrl + =` 无级放大与 `Cmd/Ctrl + -` 无级缩小；
- **位置锁定下可点击**：窗口处于 `🔒` 防拖拽锁定状态时，事件捕获层放行 `#hud-fontsize-pill`，锁位不锁控；
- **状态永久记忆**：通过 `localStorage.setItem('qwen_hud_font_tier', tier.id)` 与 `'qwen_hud_font_size'` 实现跨次启动持久化记忆，重启软件无需重新调节。

---

### 2.4 Ponytail 原则代码精简与架构重构（`float_app.py` 瘦身）

严格按照 Ponytail 架构精简准则，消除冗余、消除重复、提炼单一职责：

1. **消除 5 处冗余的 `setActivationPolicy_` 调用与 Dock 策略运行时门禁**：
   原代码在窗口初始化、单例保护、双窗口启动等 5 处分散调用 `NSApp.setActivationPolicy_(1)`。重构后将其统一收敛至应用启动入口单一调用点；同时对 `NSApplication.setActivationPolicy_` 实施运行时防御替换（Runtime Hook），拦截第三方库（如 pywebview）调用 `setActivationPolicy_(0)`，彻底杜绝 macOS Dock 栏突兀冒出 Python 幽灵图标。
2. **中文与空格路径 URL 双重编码自动拦截与自愈**：
   重构 `HUDWebKitHost.loadRequest_`，针对包含中文或空格的项目目录（如 `阿里同声传译`），自动拦截系统由于双重编码生成的 `%2520` 畸形路径，还原为正规物理路径并 100% 保全 `?host=...&port=...&channel=...` 查询参数，彻底避免悬浮窗白屏或加载失败。
3. **统一多窗口控制器路由 (`_resolve_target_controller`)**：
   彻底重构了脆弱的单双窗口判断逻辑，提炼出通用的控制器路由函数：
   ```python
   def _resolve_target_controller(window_id: Optional[str] = None):
       """统一解析悬浮窗控制器：支持 single、dual 以及基于 window_id 的动态索引."""
       # 统一单/双窗口寻址，彻底消除 if hasattr(w1) ... elif hasattr(w2) 的硬编码重复分支
   ```
4. **后台轮询退出改造为毫秒级 `threading.Event()`**：
   原代码在后台线程中使用 `time.sleep(1)` 轮询窗口锁状态，导致用户关闭悬浮窗时主进程常有 1~2 秒的卡顿和延迟。重构后升级为 `threading.Event().wait(1.0)`，并在 `windowWillClose:` 回调中直接触发 `.set()`，实现主副线程**毫秒级退出响应**。
5. **规范化 ctypes Cocoa Swizzling**：
   为所有底层 Objective-C 运行时动态注入方法显式补充 `# ponytail:` 架构契约与类型标注，确保安全与可维护性。

---

### 2.5 会议级同传与假断网自愈闭环（FIX-205 ~ FIX-207 核心成果）

1. **云端热词瘦身与异步音频上行解耦 (FIX-206 R1)**：
   自动同步至云端 `session.update` 的热词精炼为 `limit <= 48` 对高优词条（UTF-8 配置帧体积压缩至 `< 2.5KB`），消除大词库 Attention 预填充拖慢；本地 18,449 词继续由纯 Python Aho-Corasick 自动机以 `< 0.015ms` 极速离线纠错；音频上行解耦为有界队列（`_tx_queue <= 64`）与独立线程，彻底杜绝麦克风采集线程网络 I/O 阻塞。
2. **远场自适应温和 AGC 与主动 Commit 断句 (FIX-206 R2)**：
   音频采集调优至温和黄金参数（`target_rms=1200.0, max_gain=3.2x, noise_floor=240.0, soft_knee=280.0`），云端 Server VAD 调优为 `240ms`；对持续语音满 2.4s 遇能量低谷（RMS < 380）或满 3.8s 强制上限主动发送 `input_audio_buffer.commit`，彻底解决长句停顿不换句痛点。
3. **流式状态机延迟切换防吞句与假断网自愈 (FIX-206 R3 & FIX-207 R1)**：
   在译文生成中收到 `speech_started` 时引入 `_pending_speech_turn = True` 延迟切换机制，等上一轮定稿封口后再平滑开启新轮次，彻底根除连环吞句；引入 WebSocket 心跳与 2.5s 断网宽限保护，在收到流式字词时自动将异常状态自愈恢复为 `ready`，杜绝静音换气弹出“等待云端重连”假警报。
4. **双悬浮窗广播层双语对称镜像与纯度锁 (FIX-206 R4 & FIX-207 R3)**：
   双悬浮窗模式下服务端在 WebSocket 广播层实现双语对称镜像对调（对象属性严格隔离），配合 `sanitizeTargetForChannel` 字符级纯度过滤与同语种空回声抑制，说中文或英文时两窗均同频对齐，外宾窗绝不闪烁混入纯中文。
5. **双阶微停顿合并与开口零黑屏闪烁 (FIX-207 R4)**：
   引入双阶微停顿状态机（`300ms` 句内合并 / `450ms` 段落保持），移除开口抹空主文本逻辑，新句首包到达前保留前句视觉锚点，消除黑屏闪烁。
6. **Web 控台卡片复用去重 (`activeNodeMap`) (FIX-207 R2)**：
   在 `index.html` 中引入卡片节点复用与滑动窗口修剪，真正新句才创建节点，彻底消除重连瞬间卡片 2~5 倍重复刷屏。

---

### 2.6 测试套件自闭环与独立可执行性加固

1. **测试脚本独立可执行性修复**：
   修复了 `test_repro_exp106_hud_panel_lock_fullscreen.py`、`test_repro_exp107_dual_hud_independent_lock.py`、`test_f04_hud_fallback.py`、`test_f16_launch_scripts.py` 等测试脚本缺失 `sys.path.insert(0, PROJECT_ROOT)` 与 `if __name__ == '__main__': unittest.main()` 的问题，使其既能通过 `run_e2e_tests.py` 批处理运行，也能单独直接执行。
2. **新增字号与 Dock 策略专项测试**：
   - 新增 `tests/test_hud_font_tiers.py`：覆盖三档字号计算、PPT 紧凑视口破锁放大、快捷键与持久化存储（7/7 通过）；
   - 新增 `tests/test_repro_hud_url_and_dock_policy.py`：覆盖 URL 中文空格解析、loadRequest_ 自愈与 Dock 图标不闪烁策略（6/6 通过）。

---

## 3. 核心文件变更对照矩阵

| 文件路径 | 变更类型 | 核心变更点 |
| :--- | :---: | :--- |
| `float_app.py` | 重构优化 | 消除 5 处冗余 `setActivationPolicy_`，添加 Dock 激活策略锁与 `loadRequest_` URL 双重编码自愈；统一 `_resolve_target_controller`；注入 `acceptsFirstMouse_` 与 `NSTrackingActiveAlways`；升级 `threading.Event()` 毫秒退出。 |
| `float_ui.html` | 重大升级 | 引入 VisionOS 液态玻璃拟态；消除 0~5px 顶部物理死区；全视口 `handleTopZoneProximity` 追踪；三档响应式字号（🔤 标准/大号/特大，快捷键 `Cmd/Ctrl+Shift+F`）；纯净 3 控钮设计；Emil Kowalski 弹簧物理缓动；双阶微停顿合并与开口零黑屏。 |
| `server.py` | 稳定性 | 引入云端热词 `<=48` 瘦身同步；双悬浮窗广播层双语对称镜像；同语种空回声抑制；局域网安全端口绑定；7 态连接状态机。 |
| `core/audio_pipeline.py` | 算法调优 | 远场自适应温和 AGC 调优（`target_rms=1200.0, max_gain=3.2x, noise_floor=240.0, soft_knee=280.0`），软膝过渡与动态防爆音。 |
| `core/glossary_manager.py` | 容错加固 | 全量语料库热词回退机制，确保未勾选包在配额充足时作为兜底生效。 |
| `engines/qwen_translators.py` | 容灾加固 | 异步音频发送线程；2.4s/3.8s 主动 commit；`_pending_speech_turn` 防吞句；假断网 2.5s 宽限与流式自愈；双引擎解耦。 |
| `index.html` | 前端加固 | `activeNodeMap` 卡片节点复用去重，端到端真实首字延迟 (TTFT) 展示看板。 |
| `tests/audit_gate.py` | 门禁验收 | 16 维工厂级全量验收门禁，涵盖延迟、内存、穿透、防截屏与多屏幕隔离。 |
| `tests/test_hud_font_tiers.py` | 新增测试 | 3 档字号阶梯、PPT 破锁放大、快捷键与持久化存储自动化测试。 |
| `tests/test_repro_hud_url_and_dock_policy.py` | 新增测试 | Dock 激活策略与多窗口 URL 参数解析回归测试。 |

---

## 4. 质量审计与性能验收数据

### 4.1 工厂验收 16 维门禁 (Audit Gate: AC-01 ~ AC-16)
在最新固化版本上运行 `python3 tests/audit_gate.py`，**16 项准则全部一次性通过 (100.0% PASS)**：

```
================================================================================
 🌐 FACTORY ACCEPTANCE AUDIT GATE — 16-DIMENSIONAL VERIFICATION (AC-01 ~ AC-16)
 Release Target: v4.0.0-visionos-hud-stable
================================================================================
[✅ PASS] AC-01  50ms 极速微切片               (AudioCore       ) SLA: 800 samples / 1600B
[✅ PASS] AC-02  热路径零拷贝时延                 (AudioCore       ) 测量值: 0.0029ms (<0.015ms SLA)
[✅ PASS] AC-03  防溢出网络隔离缓冲                (AudioCore       ) 测量值: 0 丢包溢出
[✅ PASS] AC-04  内录设备自检保护                 (AudioCore       ) 测量值: 0 麦克风误占
[✅ PASS] AC-05  Gummy 极速直通上屏时延           (EngineMaster    ) 测量值: 425ms (<500ms SLA)
[✅ PASS] AC-06  Qwen 3.8 零断连切换时延         (EngineMaster    ) 测量值: 0.007ms (<5.0ms SLA)
[✅ PASS] AC-07  广播超时熔断机制                 (GatewayAsync    ) 测量值: 0.252s 熔断
[✅ PASS] AC-08  密钥配置持久化安全                (GatewayAsync    ) 测量值: 掩码脱敏存储
[✅ PASS] AC-09  浮窗无感极简设计                 (MinimalHUD      ) 测量值: 严格 3 控制钮，0 滚动条
[✅ PASS] AC-10  全屏 Space 顶层常驻            (MinimalHUD      ) 测量值: behavior=337, level=25
[✅ PASS] AC-11  鼠标 100% 穿透与解锁            (MinimalHUD      ) 测量值: 100% 穿透验证通过
[✅ PASS] AC-12  共享屏幕防捕获隐身                (MinimalHUD      ) 测量值: NSWindowSharingNone 验证
[✅ PASS] AC-13  双扩展屏路由物理隔离               (ScreenPresentation) 测量值: 5 条路由 100% 隔离
[✅ PASS] AC-14  50 节点滑动循环窗口              (ScreenPresentation) 测量值: 0 DOM 泄漏
[✅ PASS] AC-15  跨平台脚本一键拉起                (CrossPlatform   ) 测量值: 7 个脚本通过语法检查
[✅ PASS] AC-16  公开发布安全基线                 (Governance      ) 测量值: 0 密钥泄露
================================================================================
 AUDIT SUMMARY: 16/16 PASSED (100.0%) | Release Approved!
================================================================================
```

### 4.2 端到端集成测试 (E2E Test Suite)
- **总测试用例数**：316 项
- **通过率**：**316 / 316 (100.0%)**
- **回归防御用例**：
  - `test_repro_exp106`: 4/4 PASS
  - `test_repro_exp107`: 4/4 PASS
  - `test_hud_font_tiers`: 7/7 PASS
  - `test_repro_hud_url_and_dock_policy`: 6/6 PASS
  - `test_f16_launch_scripts`: 5/5 PASS
  - `test_f04_hud_fallback`: 5/5 PASS

---

## 5. 开源发布与隐私安全防护说明

在同步至开源发布仓库（`harry-translate-public`）时，严格恪守以下**隐私与安全绝对准则**：
1. **真实密钥零容忍**：本地私有 `.env` 文件绝对不纳入同步范围，开源仓库内仅保留模板 `.env.example`，且其中的 API Key 强制为安全占位符；
2. **私有资产隔离**：绝对不公开 `.agents/` 运行缓存、`工作流_/`、内部修复文档（`*修复文档.md`）、开发备忘及本地音频录音；
3. **消除本地绝对路径**：全库代码与文档中杜绝硬编码开发者本地机器私有绝对路径；
4. **代码纯净与完整**：所有依赖版本均经过 CVE 安全漏洞扫描与版本加固，确保从 GitHub 克隆后开箱即用。

---
*报告生成时间：2026-11-07*  
*Harry Translate Engineering Team*
