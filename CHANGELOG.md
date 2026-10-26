# Changelog

All notable changes are documented here. The project follows Semantic
Versioning for public releases.

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

[3.6.0]: https://github.com/xiaokunshi5-lang/harry-translate/releases/tag/v3.6.0
