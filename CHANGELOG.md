# Changelog

All notable changes are documented here. The project follows Semantic
Versioning for public releases.

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

[3.9.0]: https://github.com/xiaokunshi5-lang/harry-translate/releases/tag/v3.9.0
[3.8.0]: https://github.com/xiaokunshi5-lang/harry-translate/releases/tag/v3.8.0
[3.6.0]: https://github.com/xiaokunshi5-lang/harry-translate/releases/tag/v3.6.0
