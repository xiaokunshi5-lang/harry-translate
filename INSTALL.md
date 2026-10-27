# Harry Translate (哈利同传) 零门槛部署与全平台使用手册 (v3.9-hud-parity-history-line-farfield-agc)

本手册专为会务现场人员、同传译员及个人用户编写。按照本指南操作，可在 5 分钟内完成环境准备、系统运行以及万级热词银行、云端容量水位仪、字体调色和透明度个性化配置。

---

## 一、4 步极速通关指南（速查路线）

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│ 步骤 1: 安装 Python│ ──► │ 步骤 2: 安装依赖包│ ──► │ 步骤 3: 填入 APIKey│ ──► │ 步骤 4: 双击脚本启动│
│ (3.10+ 环境准备)  │     │ (运行 requirements)│    │ (配置 .env 凭证) │     │ (双击 .command/.bat)│
└─────────────────┘     └─────────────────┘     └─────────────────┘     └─────────────────┘
```

---

## 二、macOS 平台 5 分钟极速部署流程

### 1. 基础环境安装

打开 macOS「终端」（Terminal，可在 Spotlight 搜索或在“应用程序” -> “实用工具”中找到）：

```bash
# 1. 安装 Homebrew 包管理器 (若已安装请跳过)
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# 2. 安装稳定版 Python 3.11 及音频底层库
brew install python@3.11 portaudio git
```

### 2. 初始化项目运行环境

克隆公开仓库并进入项目目录：

```bash
git clone https://github.com/xiaokunshi5-lang/harry-translate.git
cd harry-translate
python3 -m venv .venv
source .venv/bin/activate

# 安装生产依赖包
pip install --upgrade pip
pip install -r requirements.txt
```

### 3. 配置虚拟内录回环声卡（BlackHole 2ch + 多输出设备）

> **说明**：如果您只需翻译自己的麦克风发言，此步骤可跳过；如果需要同时录制并翻译 Zoom、腾讯会议、Teams 中对方的声音，需要配置虚拟内录。

1. 通过 Homebrew 一键安装 BlackHole 2ch 虚拟声卡：
   ```bash
   brew install blackhole-2ch
   ```
2. 打开系统「音频 MIDI 设置」（Audio MIDI Setup，可通过 Spotlight 搜索）：
   - 点击左下角 `+` 号，选择 **「创建多输出设备 (Create Multi-Output Device)」**；
   - 在右侧列表中，同时勾选 **「BlackHole 2ch」** 与您平时听音的 **「耳机或扬声器」**（确保耳机为主设备并开启漂移校正）；
   - 在 Mac 顶部状态栏或系统设置将声音输出切换为此「多输出设备」；
   - 会议软件（如 Zoom、腾讯会议）的声音输出也选择此「多输出设备」即可。

### 4. 授权麦克风与配置 API Key

1. 打开 Mac「系统设置」 -> 「隐私与安全性」 -> 「麦克风」，确保勾选允许「终端」或「Python」访问；
2. 复制配置文件模板并写入您的 DashScope API Key：
   ```bash
   cp .env.example .env
   open -e .env
   ```
3. 在访达中双击运行脚本（或在终端运行）：
   - **`启动悬浮同传.command`**：直接唤起极简单态悬浮同传提词窗口（推荐通用，自带防多开守卫）；
   - **`启动悬浮同传_中译英.command`**：涉外演讲与对外宣讲专用（上英下中，自动挂起英译中，**立省 50% Token**）；
   - **`启动悬浮同传_英译中.command`**：外教课与国际会议听讲专用（上中下英，自动挂起中译英，**立省 50% Token**）；
   - **`启动双悬浮同传.command`**：国际商务与圆桌会谈专用（拉起上下错落双悬浮窗口，垂直间隔 30px，零重叠）；
   - **`启动同传系统.command`**：启动服务并在浏览器中打开双大屏监看控台（`http://localhost:8000/split`）；
   - **`切换API_Key.command`**：终端交互式菜单更换与校验 DashScope API 密钥。

---

## 三、Windows 10/11 平台 5 分钟极速部署流程

### 1. 安装 Python 官方环境

1. 访问 Python 官网下载并运行安装包：[Python 3.11.9 64-bit 下载](https://www.python.org/downloads/)；
2. **核心步骤**：在安装界面第一页勾选下方的 **`Add python.exe to PATH`**（将 Python 添加到系统环境变量）；
3. 点击 `Install Now` 等待安装完成。

### 2. 检查 Microsoft Edge WebView2 运行库

- Windows 11 已自带该组件；
- Windows 10 用户如启动时提示缺少组件，请安装微软官方运行库：[WebView2 Evergreen Bootstrapper 官方下载](https://go.microsoft.com/fwlink/p/?LinkId=2124703)。

### 3. 初始化项目与安装依赖

打开命令提示符（CMD）或 PowerShell，依次执行：

```cmd
git clone https://github.com/xiaokunshi5-lang/harry-translate.git
cd harry-translate
python -m venv .venv
call .venv\Scripts\activate.bat
python -m pip install --upgrade pip
pip install -r requirements.txt
```

> **Windows PyAudio 安装避坑说明**：  
> 若直接 `pip install pyaudio` 提示缺少 C++ Build Tools，可通过预编译 wheel 极速安装：  
> `pip install pipwin && pipwin install pyaudio`

### 4. 安装免费虚拟内录声卡（Stereo Mix 或 VB-CABLE）

1. 访问官网下载驱动包：[VB-CABLE Driver 下载](https://vb-audio.com/Cable/)；
2. 解压 ZIP 压缩包，右键 `VBCABLE_Setup_x64.exe` 选择 **「以管理员身份运行」** 并完成安装，随后重启电脑；
3. 进入 Windows「控制面板」 -> 「声音」 -> 「录制」选项卡：
   - 找到 `CABLE Output`，双击打开属性，切换至 **「侦听」** 选项卡；
   - 勾选 **「侦听此设备」**，在下方下拉列表中选择您的 **实际耳机或扬声器**；
   - 会议软件（Zoom/腾讯会议）中的音频输出设备选择 `CABLE Input`。

### 5. 填入 API Key 并双击运行

在项目文件夹内将 `.env.example` 复制为 `.env`，使用记事本打开填入您的 Key：

```cmd
copy .env.example .env
notepad .env
```

双击运行以下脚本：

- **`启动悬浮同传.bat`**：启动桌面悬浮提词 HUD 窗口（通用推荐，自动排他防多开）；
- **`启动悬浮同传_中译英.bat`**：涉外宣讲中译英单向窗口（上英下中，自动挂起英译中，省 50% Token）；
- **`启动悬浮同传_英译中.bat`**：外教课与讲座英译中单向窗口（上中下英，自动挂起中译英，省 50% Token）；
- **`启动双悬浮同传.bat`**：启动上下错落双悬浮窗口（双向圆桌会谈，30px 防遮挡间隔）；
- **`启动同传系统.bat`**：启动同传服务并在浏览器中打开大屏监看控台；
- **`切换API_Key.bat`**：终端交互式更换 DashScope API 密钥。

---

## 四、万级多维分类热词银行 (`glossary_bank/`)、容量水位仪与会议抽屉工作台使用指南

> [📖 查看全景热词分类与 18,449 词速查总览表 (GLOSSARY_INDEX.md)](GLOSSARY_INDEX.md)

为解决涉外政务、高端学术研讨及各垂直行业会议中专业词汇识别漂移、突发外宾名字生僻、云端 API 1,000 词硬限制等会务现场痛点，系统内置了万级多维分类热词银行与抽屉工作台。

### 1. 多维分类标签词包银行架构 (`glossary_bank/`)

系统在 `glossary_bank/` 目录下内置了 15 个模块化 JSON 分类词包，总词汇量达 **18,449 词**（详见 `GLOSSARY_INDEX.md`）：

- **🔒 基础应急固定库 (`00_base_emergency.json`)**：内置 100 个最高频政治、外交与通用纠错词条，系统默认强制常驻锁定，界面无法关闭，确保突发会议底线稳固；
- **🟢 主力分类标签 (高频 / 常见，默认开启)**：涵盖党建政务高频、外交公文、日常物品、水果生鲜、重点地名、经典成语、AI科技、口语热词等 8 个标签（每个词包 100~120 词）；
- **🔵 领域扩展标签 (生僻 / 专精，按需勾选)**：涵盖党建专用语、工业生活物品、水果农特产、国内外地名、方言谐音、生物医药临床等 6 个大体量标签（每个词包 2,400~3,300 词，总计超 17,000 词）；
- **自动发现与动态挂载**：只需在 `glossary_bank/` 目录下新增合规 JSON 文件，系统无需重启即可自动扫描识别并呈现于界面。

### 2. 双轨容量水位仪与云端 1,000 词智能防爆截断 (Smart Capping)

阿里云百炼实时同传 WebSocket API 对热词列表设有 **1,000 词硬上限**，超出将返回 `InvalidParameter` 错误并导致断网。为保障万级词库使用安全，系统构建了双轨容量管理与防爆机制：

1. **四级推送优先级排序**：
   - **`P0` 本场临时人名**：现场紧急导入的外宾与主讲人名单，最高优先级确保直达云端；
   - **`P1` 基础应急库与常驻词**：`00_base_emergency.json` 与 `glossary.json` 用户词汇；
   - **`P2` 已勾选高频主力标签**：党建、外交、成语、科技等高频词包；
   - **`P3` 已勾选生僻扩展标签**：医药、方言、工业等扩展词包。
2. **安全阈值与智能截断**：
   - 设定 **$\le 900$ 词安全推送上限**（预留 10% 冗余安全裕度）；
   - 当会务人员勾选多个生僻大词包导致总词数突破 900 词时，系统自动触发智能截断（Smart Cap），仅推前 900 词至云端模型，100% 杜绝云端接口报错；
3. **健康状态三态显示**：
   - 🟢 `optimal`（$\le 750$ 词）：云端负载处于极佳状态；
   - 🟡 `warning`（$751 \sim 900$ 词）：接近 900 词安全线；
   - 🔴 `capped`（$> 900$ 词）：已触发智能截断保护，超出部分自动转入本地引擎离线处理。

### 3. 本地纯 Python Aho-Corasick 自动机离线挂载 (0 Token 消耗)

所有勾选分类词包及临时/永久词条（无论 50 词还是 18,000+ 词），**100% 全量挂载至本地纯 Python Aho-Corasick 自动机**：
- **极速低耗**：单句扫描匹配耗时仅需 **0.0058ms**（目标 $\le 0.15\text{ms}$），内存常驻仅约 46MB；
- **0 额外 Token 消耗**：本地纠偏在 WebSocket 数据广播前完成，不需要向云端发送多余 Token，零 API 费用增量。

### 4. 国际会议临时专属人名与双层生命周期管控

国际会议常在开场前拿到演讲嘉宾临时名单，系统支持快速导入与生命周期隔离：
1. **双层生命周期**：
   - **`⏱️ 临时本场词` (`_session_data`)**：保存在内存中，拥有最高优先级，会话中覆盖常驻词，不写入磁盘；
   - **`📌 永久常驻词` (`_data`)**：持久化写入 `glossary.json`，永久复用。
2. **单条与批量多格式导入**：
   在工作台中支持单条快速录入，或在文本框中批量粘贴，支持多种分隔符：
   ```text
   张伟 = Wei Zhang
   苏姿丰 -> Lisa Su
   黄仁勋 => Jensen Huang
   李雷: Lei Li
   韩梅梅：Meimei Han
   ```
3. **会后一键处置**：
   - **`🧹 一键清空本场临时词`**：会议结束后点击，内存临时名单瞬时清空，磁盘零修改，不影响日常使用；
   - **`💾 一键转存为永久词库`**：若临时名单有长期沉淀价值，点击后一键合并写入 `glossary.json`。

### 5. 系统全局配置抽屉可视化工作台操作指南

在大屏控台页面（`http://localhost:8000/` 或 `/split`）中：
1. **唤出工作台**：点击顶部控制栏绿色高亮按钮 **`📚 会议热词`**（或点击 `⚙️ 系统配置` 切换至热词选项卡）；
2. **观察配额水位仪**：顶部清晰查看云端配额水位进度条、当前健康度及本地万词引擎挂载词数；
3. **按需勾选标签**：在标签区勾选本场会议适用的领域分类（如勾选「🧬 生物医药与临床」），即刻热生效；
4. **导入嘉宾名单**：切换至「批量快加」面板，粘贴外宾姓名对，点击「批量导入至本场临时词」；
5. **检索与删除**：在下方词条列表中可输入关键词实时搜索，点击单条右侧 `✕` 即可即时删除；
6. **会后归档**：散会后轻点「🧹 一键清空本场临时词」恢复纯净环境。

### 6. 自定义分类词包扩展指南 (`glossary_bank/`)

如需为您的组织建立专属业务分类词包（如金融、法律、海关），只需在 `glossary_bank/` 目录下新建 JSON 文件（例如 `99_custom_legal.json`）：
```json
{
  "id": "custom_legal",
  "name": "涉外法务与知识产权",
  "icon": "⚖️",
  "tier": "rare",
  "priority": 3,
  "locked": false,
  "default_enabled": false,
  "description": "涉外仲裁、知识产权与商业合同专有词汇",
  "asr_fixes": {
    "不可抗利": "不可抗力"
  },
  "terms_zh_to_en": {
    "不可抗力": "Force Majeure",
    "商业秘密": "Trade Secret"
  },
  "terms_en_to_zh": {
    "Force Majeure": "不可抗力",
    "Trade Secret": "商业秘密"
  }
}
```
保存后，刷新抽屉工作台即可自动识别并呈现该扩展标签。

---

## 五、悬浮同传个性化视觉与交互调节指南

### 1. 字体颜色方案调节 (5 套高对比配色)

针对不同参会背景（深色背景、浅色 PPT、白底文档），系统提供了 5 套精选调色方案：

| 方案名称                       | 主译文颜色          | 辅原文颜色                    | 阴影设计        | 最适应用场景                           |
| :------------------------- | :------------- | :----------------------- | :---------- | :------------------------------- |
| **🎨 暖金** (Classic Amber)  | `#facc15` 琥珀暖金 | `rgba(255,255,255,0.72)` | 双层深黑扩散投影    | **出厂默认**，深色桌面或会议视频，视觉焦点极醒目       |
| **🎨 腾讯白** (Tencent White) | `#ffffff` 纯净晶白 | `rgba(226,232,240,0.70)` | 高对比暗黑轮廓     | **对标腾讯会议**，极简优雅，长时间观看最自然         |
| **🎨 冰川青** (Glacier Cyan)  | `#38bdf8` 荧光冰蓝 | `rgba(186,230,253,0.72)` | 科技光晕深阴影     | 科技峰会、学术报告、夜间暗光环境下极舒适             |
| **🎨 黑曜石** (Obsidian Dark) | `#0f172a` 沉稳玄黑 | `rgba(51,65,85,0.85)`    | **纯白柔光外发光** | **专门适配白色/浅色背景**（如浅色 Word、白底 PPT） |
| **🎨 薄荷绿** (Mint Neon)     | `#4ade80` 柔和薄荷 | `rgba(187,247,208,0.70)` | 软调暗黑投影      | 护眼模式，适合 3 小时以上长时间连轴会谈            |

#### 切换方式：

1. **快捷键切换**：按下 **`Cmd + Shift + C`** (macOS) 或 **`Ctrl + Shift + C`** (Windows)，即可在 5 套方案之间秒级无缝循环；
2. **鼠标点击切换**：鼠标移动到悬浮窗顶部边缘（顶端 24px 微感知区），点击浮现的 **`🎨 暖金`** 微型药丸即可循环；
3. **自动持久记忆**：选定的配色方案会自动存储在本地，下次启动保持不变。

---

### 2. 窗口背景透明度调节 (5 档循环切换)

为满足“既能看清字幕，又不遮挡下方会议胶片”的诉求，系统支持 5 档微调：

- **`💧 15%` (出厂默认)**：微透凝胶质感，轻盈通透，文字极具浮空感；
- **`💧 35%`**：经典液态毛玻璃，背景适度压暗；
- **`💧 55%`**：半深色沉浸，强光线下字幕清晰；
- **`💧 75%`**：高对比暗夜，极度醒目防反光；
- **`💧 10%`**：极限通透，薄如蝉翼。

#### 切换方式：

- 鼠标悬停在悬浮窗顶部，点击 **`💧 15%`** 按钮即可一键循环切档，自动记忆。
- **绝对稳态保证**：无论您选择哪一档透明度，在说话流式输出还是静默停顿时，**窗口背景透明度严格恒定不变（$\Delta \text{opacity} \equiv 0.0$）**，彻底消除忽明忽暗的频闪。

---

### 3. 双模自适应舞台 (68:32 ⇄ 65:35) 与小窗口双语全景防遮挡

- **双模比例瞬时热切 (`Cmd + Shift + R` / `Ctrl + Shift + R`)**：
  - **`68:32` 模式（出厂默认黄金比例）**：上方主译文占 68%，下方原文占 32%，为目标翻译提供最大化视觉空间；
  - **`65:35` 模式（原文扩展模式）**：上方主译文占 65%，下方原文占 35%，为较长中文发言或辅助原文提供额外垂直净空；
  - 按下全局快捷键秒级无缝热切，配置自动通过 `localStorage` 记忆并持久化保存。
- **主译文两行零裁切物理包络 (`twoLinesEnvelope`)**：
  - 在小视口（高度 $\le 75\text{px}$）下启用紧凑排版（15px / 1.25 行高）；
  - 动态解耦顶端渐变遮罩（`--fade-mask-top-size`），两行包络内遮罩尺寸归零，首行字字清晰，绝无毛玻璃半透明发虚遮挡。
- **中文原文辅助区 31px 物理安全包络**：
  - 彻底移除 `#zoneAuxiliary` 的 `padding-top: 2px`，紧凑字号 12px / 1.2 行高，汉字稳落在 31px 安全带内，彻底根除顶部被 `#zoneDivider` 微光分割线削顶。
- **跨句状态原子隔离与长句平滑滚动**：
  - 说话开启新句时，译文状态原子重置并加锁，严格杜绝上一句旧翻译在新句开头闪现复读；
  - 单句发言累积达到 7 行以上时，视口自适应内部平滑平移，最新吐出的文字始终处于视觉焦点。
- **通道即时翻转**：按下 **`Cmd + Shift + T`**（或点击顶部 `中 ➔ EN ⇄` 药丸），中译英与英译中主次内容瞬间平滑对调。

---

### 4. 鼠标穿透锁定与 120 FPS 拖拽

- **穿透模式 (`Cmd + Shift + L` / 点击 `🔒`)**：开启后，鼠标点击直接穿透浮窗，可随意圈选下方的 PPT 文字、点击网页链接或编辑文档。浮窗静静悬浮提词，完全不干扰日常办公；
- **硬件级原生拖拽**：鼠标按住左上角把手（`⠿`）即可在 120 FPS 下顺滑拖动浮窗至屏幕任意角落或外接扩展大屏。

---

### 5. 全局生产力快捷键速查表 (Cheat Sheet)

在悬浮窗处于激活状态或桌面交互时，可直接使用以下生产力快捷键：

| 快捷键 (macOS / Windows) | 动作名称 | 响应行为与技术特性 |
| :--- | :--- | :--- |
| **`Cmd + Shift + L`**<br>`Ctrl + Shift + L` | **鼠标穿透锁定/解锁** | 开启后浮窗完全不响应鼠标（可穿透点击下方 Word/PPT），再次按下解除穿透 |
| **`Cmd + Shift + T`**<br>`Ctrl + Shift + T` | **双语通道快速互切** | 在 `中 ➔ EN`（中译英）与 `EN ➔ 中`（英译中）之间瞬时平滑翻转 |
| **`Cmd + Shift + R`**<br>`Ctrl + Shift + R` | **双语视口比例快速切换** | 在 **`68:32`**（经典出厂比例）与 **`65:35`**（扩展原文比例）之间无缝瞬时切换，自动本地持久化记忆 |
| **`Cmd + Shift + C`**<br>`Ctrl + Shift + C` | **字体调色方案轮换** | 循环切换 5 套高对比配色（暖金 ➔ 腾讯白 ➔ 冰川青 ➔ 黑曜石 ➔ 薄荷绿） |
| **鼠标悬停顶部 24px 传感器** | **唤出控制胶囊** | 平时 100% 隐藏，鼠标移至顶端自动浮现通道药丸、配色药丸、穿透锁、透明度与设置键 |
| **按住左上角把手 (`⠿`) 拖拽** | **120 FPS 窗口移动** | 硬件级无延迟拖拽窗口跨屏漫游 |

---

## 六、全平台常见避坑 FAQ 与排障速查

### Q1: Mac 双击 `.command` 脚本闪退，提示“权限被拒绝”？

- **原因**：通过网盘或聊天软件下载的文件丢失了 Unix 可执行权限（`+x`）。
- **解决方式**：打开终端，运行赋予权限命令：
  ```bash
  chmod +x ~/harry-translate/*.command ~/harry-translate/*.sh
  ```

### Q2: 为什么启动时提示 `Address already in use: 8000`（端口被占用）？

- **原因**：上次关闭时残留了未完全退出的后台服务或本机的其他 Web 服务占用了 8000 端口。
- **解决方式**：
  - **macOS**：在终端执行一行强制清理命令：
    ```bash
    lsof -ti :8000 | xargs kill -9
    ```
  - **Windows**：在 CMD 中执行：
    ```cmd
    for /f "tokens=5" %a in ('netstat -aon ^| findstr :8000') do taskkill /f /pid %a
    ```

### Q3: 为什么我说话没有任何字幕出来？

- **排查步骤**：
  1. 检查 `.env` 文件中的 `DASHSCOPE_API_KEY` 是否填写正确，有无首尾空格；
  2. 检查电脑麦克风权限：Mac 运行 `tccutil reset Microphone` 并重新授权；Windows 检查系统设置中是否允许桌面应用访问麦克风；
  3. 浏览器访问 `http://localhost:8000/api/meta`，查看 `devices` 列表是否识别到麦克风。

### Q4: 提示 API Key 无效、配额不足或余额欠费（Quota Exceeded / Invalid API Key）？

- **原因**：填写的 DashScope API Key 已过期、欠费或触发了 RPM/TPM 频率限制。
- **解决方式**：
  1. 登录阿里云百炼控制台（DashScope Console），核对 API Key 是否处于启用状态且账户有余额；
  2. 运行项目内置的密钥切换工具更新 Key：
     - macOS: `./切换API_Key.command`
     - Windows: `切换API_Key.bat`
  3. 也可在浏览器访问 `http://localhost:8000/`，在右上角「系统配置」抽屉中输入新 Key 并点击保存（具备防清空校验机制）。

### Q5: 为什么只有中译英有字，英译中（外宾发言）没有字？

- **原因**：Channel B 需要捕捉系统内录声音。如果未安装虚拟声卡（BlackHole 或 VB-CABLE），系统无法监听电脑扬声器的输出。
- **解决方式**：
  - 若为临时自测或单向发言，Harry Translate 会**自动镜像麦克风声音至英译中**；
  - 若正式开会，请按照上述教程配置 BlackHole 或 VB-CABLE 虚拟内录声卡。

### Q6: 为什么我的悬浮窗有时候字变淡、首行发虚遮挡，或者上一句文字残留？

- **原因分析**：
  1. 背景忽明忽暗是历史旧版本残留孤儿进程或 macOS 系统毛玻璃冲突；
  2. 首行字体现玻璃发虚感是旧版渐变羽化遮罩过大且小窗口未做两行包络保护；
  3. 连续快速说话时上一句文字先蹦出来是旧版跨句没有原子隔离清空。
- **解决方案**：最新版 `v3.6`（`v3.6-bilingual-adaptive-hd-hud`）已彻底解决上述所有问题：
  - 在 [`float_app.py`](float_app.py) 中彻底解耦 `NSVisualEffectView` 并移除 `dimTimer`，启动脚本自带 `pkill -f float_app.py` 守卫，背景透明度 100% 恒定静止；
  - 引入 `twoLinesEnvelope` 两行物理包络与动态遮罩解耦，紧凑窗口下首行两行零裁切、零遮挡；
  - 引入跨句原子状态隔离（`sentence_id` 原子重置 + `sentenceHasTranslation` 状态锁），彻底根除上一句译文闪现复读。

### Q7: 会议文档背景是白色的，黄色字体看不清怎么办？

- **解决方案**：
  1. 按下快捷键 **`Cmd + Shift + C`**（Windows 按 `Ctrl + Shift + C`），切换到 **`🎨 黑曜石`** 配色方案。该方案使用高纯度深黑粗体配合纯白柔和外发光，专为浅色与白底 PPT 打造；
  2. 或者点击顶部 `💧 15%` 按钮切换到 `55%` 或 `75%`，将浮窗底板适度加深。

### Q8: 遇到特定行业专业词汇识别不准怎么办？

- **解决方案**：直接打开项目根目录下的 [`glossary.json`](glossary.json)，在 `asr_fixes` 中添加谐音替换对，在 `mt_terms` 中添加英文术语标准译名，保存后重启浮窗或调用 API 热重载即可立即生效。

### Q9: 外教直播课只想看英译中，如何最省钱、最省 Token？

- **操作方式**：
  - 直接双击 **`启动悬浮同传_英译中.command`**（Windows 双击 **`启动悬浮同传_英译中.bat`**）；
  - 系统启动后自动锁定英译中通道，服务端流控引擎将完全挂起中译英云端推流，**立即节约 50% 的 API Token 费用**。

### Q10: 悬浮窗被全屏 PPT / Keynote 遮挡怎么办？

- **特性保证**：Harry Translate 原生悬浮窗基于 `HUDPanelHost`（macOS 原生 `NSPanel` + `NSApplicationActivationPolicyAccessory (1)` + `collectionBehavior=337` + `level=1000`）与 Windows 顶层架构构建，天然跨越并穿透全屏播放的 Keynote、PowerPoint、腾讯会议及 Zoom 界面，点击浮窗按钮绝不切屏；点击 `🔒` 即可通过 4 重物理硬锁将浮窗坐标尺寸 100% 焊死在屏幕上防误触，同时双悬浮窗模式下支持上下两窗独立锁定。

### Q11: 遇到未知异常如何一键恢复到出厂状态？

- 在终端执行秒级无损回滚命令：
  ```bash
  git switch --detach v3.9.0
  ```
  使用 Git 保存本地修改后安全切换至已发布的稳定标签基线。

### Q12: 在小窗口下看中文输入或双行英译，感觉字号太挤或想让中文原文更大一些怎么办？

- **解决方案**：
  - 按下全局快捷键 **`Cmd + Shift + R`**（Windows 按 **`Ctrl + Shift + R`**），可在 **`68:32`** 与 **`65:35`** 比例之间一键切换；
  - `65:35` 模式将辅助区空间提升至 35%，结合小窗口 31px 安全包络，中文原文与两行英译均舒展开阔、字字清晰，偏好配置自动记忆保存。

### Q13: 会议导入了几百个人名，会超标导致阿里云报 InvalidParameter 错误吗？

- **解决方案与安全保障**：
  - 绝不会发生。系统内置了双轨容量管理与 Smart Cap 智能防爆截断机制；
  - 针对阿里云百炼 WebSocket API 1,000 词硬上限，系统设有严格的 **$\le 900$ 词安全推送阈值**；
  - 系统按照 `P0 本场临时人名 ➔ P1 基础应急库与常驻词 ➔ P2 高频主力标签 ➔ P3 生僻扩展标签` 优先级智能排序，若总词数超过 900 词，超出部分自动截断，100% 杜绝接口报错；
  - 与此同时，**本地纯 Python Aho-Corasick 自动机仍 100% 全量挂载全部 18,000+ 词条**，所有词汇在本地均可实现 $\le 0.15\text{ms}$ 极速纠错，不额外消耗任何 Token。

### Q14: 临时嘉宾名字在会议结束后如何快速清理，避免污染以后的会议？

- **解决方案**：
  - 临时导入的嘉宾名字保存在纯内存级 `_session_data` 中；
  - 会议结束后在工作台中轻点 **「🧹 一键清空本场临时词」** 即可瞬间重置，磁盘文件零修改；
  - 如果某场会议沉淀的术语有长期价值，点击 **「💾 一键转存为永久词库」**，即可永久合并保存至 `glossary.json`。

### Q15: 悬浮同传窗口与普通网页窗口翻译速度和内容会有体感差异吗？ (v3.9 升级)

- **出厂保障**：系统在 `v3.9` 彻底重构了流式传输与渲染管道：
  1. 悬浮窗 WebKit 前端采用与浏览器完全一致的同步无锁 DOM 直写机制，耗时仅 $0.0018\text{ms}$，首字上屏与连续字词吐出绝不丢帧、绝无排队滞后；
  2. 新增 `#historyLine` 历史定稿留存视口，说话人换句或停顿时，上一句译文稳固锚定在上方，当前句在下方实时流式推进，阅读体验超越普通浏览器单行字幕；
  3. 后台进程通过 macOS `NSActivityLatencyCritical` 保持最高调度优先级，退居后台也绝对不被系统 App Nap 节流。

### Q16: 电脑放在会议桌中间距离发言人 1~2 米拾音发弱怎么办？ (v3.9 升级)

- **自适应远场 AGC 赋能**：系统底层内嵌 C 级自适应软限幅自动增益（Far-Field Adaptive AGC）：
  1. 自动根据输入声压 RMS 评估讲话距离，对 1~2 米远场微弱拾音自动动态提振 $1.8\times \sim 2.5\times$ 能量倍率；
  2. 智能门限（`noise_floor = 140`）过滤桌面杂音与空调底噪，配合双曲正切软限幅（Soft-Knee Peak Limiter）杜绝近身偶发爆音；
  3. 云端 Server VAD 参数精调至 320ms 极速断句，远距离发音停顿时云端迅速定稿，自然跟手。

---

## 七、部署完成测试验收指引

在首次安装或环境配置完成后，可通过运行自动化测试套件快速验证系统完整性与硬件兼容性：

```bash
# 激活项目专属虚拟环境 (Windows 使用 call .venv\Scripts\activate.bat)
source .venv/bin/activate

# 1. 验证 315 项全量自动化测试套件 (包含 246 项 E2E 阶梯测试 + 69 项专项单元与对抗测试)
python -m unittest discover -s tests -p 'test_*.py'

# 2. 验证 246 项核心 E2E 阶梯自动化测试 (基线功能全量回归)
python tests/run_e2e_tests.py

# 3. 验证 16 维工厂级终审审计门禁 (验证声卡 50ms 切片、425ms 延迟等核心性能)
python tests/audit_gate.py

# 4. 验证腾讯会议绝对稳态悬浮与 5 套字体配色方案 (AC-V1 ~ AC-V5)
python -m unittest tests/test_tencent_steady_hud_and_themes.py

# 5. 验证单态对抗极限压测 (连续 10s 静默与流式吐字，断言 delta opacity == 0.0)
python -m unittest tests/challenger_steady_hud_adversarial.py

# 6. 验证专精术语语料库、分类标签银行与黄金比例双视口测试 (AC-G1~G8, AC-L1~L5)
python -m unittest tests/test_glossary_and_golden_ratio_layout.py

# 7. 验证严格 DOM 规范与工作台抽屉审计测试 (验证 0 innerText，15 项核心配置 ID)
python tests/verify_m4_v5.py

# 8. 验证小窗口两行主译文零裁切物理包络专项测试
python -m unittest tests/repro_issue_twoline_output_clip.py

# 9. 验证中文原文辅助区 31px 安全包络防削顶专项测试
python -m unittest tests/repro_issue_chinese_input_clip.py

# 10. 验证 68:32 ⇄ 65:35 双模舞台比例自适应与快捷键专项测试
python -m unittest tests/test_hud_dual_ratio_mode.py

# 11. 验证 HUD 纯位置防拖拽锁定、全屏置顶 flags、实时同步表与冲突探针专项回归测试
python -m unittest tests/test_hud_lock_and_active_glossary_sync.py

# 12. 验证 EXP-106 HUDPanelHost 全屏空间穿透与 4 重物理硬锁真实 Cocoa 门禁测试
python -m unittest tests/test_repro_exp106_hud_panel_lock_fullscreen.py

# 13. 验证 EXP-107 双悬浮同传窗口独立位置锁定与分窗隔离真实 Cocoa 门禁测试
python -m unittest tests/test_repro_exp107_dual_hud_independent_lock.py

# 14. 验证 EXP-108 悬浮同传与普通窗口同传流式对齐、速度与历史留存专项测试 (28 项用例)
python -m unittest tests/test_float_window_parity_and_speed.py

# 15. 验证 EXP-108 极端并发对抗与 UI 引擎抗压测试 (WebKit 极速帧压测与孤儿线程防护)
python -m unittest tests/challenger_ui_engine_stress.py
```

> **热词索引参考**：全量 15 个词包分类、18,449 词条明细及 4 级优先级覆盖规则请查阅 [`GLOSSARY_INDEX.md`](GLOSSARY_INDEX.md)。全部测试输出 PASS 即表明当前系统环境部署成功，处于工业级可交付状态。
