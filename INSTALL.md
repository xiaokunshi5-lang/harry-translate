# Harry Translate (哈利同传) 零门槛部署与全平台使用手册 (v3.6-bilingual-adaptive-hd-hud)

本手册专为会务现场人员、同传译员及个人用户编写。按照本指南操作，可在 5 分钟内完成环境准备、系统运行以及专精词库、字体调色和透明度个性化配置。

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

# 创建专属隔离虚拟环境
python3 -m venv .venv
source .venv/bin/activate

# 安装生产依赖包
pip install --upgrade pip
pip install -r requirements.txt
```

### 3. 配置虚拟内录回环声卡（BlackHole 2ch + 多输出设备）

> **说明**：如果您只需翻译自己的麦克风发言，此步骤可跳过；如果需要同时录制并翻译 Zoom、腾讯会议、Teams 中对方的声音，需要配置虚拟内录。
> 完整的 macOS / Windows 双轨内录配置见 [`docs/AUDIO_SETUP_GUIDE.md`](docs/AUDIO_SETUP_GUIDE.md)。

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
3. 在访达中双击运行脚本：
   - **`启动悬浮同传.command`**：直接唤起极简单态悬浮同传提词窗口（自带防多开守卫）；
   - **`启动同传系统.command`**：启动服务并在浏览器中打开双大屏监看控台（`http://localhost:8000/split`）；
   - **`启动双悬浮同传.command`**：拉起上下错落双悬浮窗口。

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

- **`启动悬浮同传.bat`**：启动桌面悬浮提词 HUD 窗口；
- **`启动同传系统.bat`**：启动同传服务并在浏览器中打开大屏监看控台；
- **`启动双悬浮同传.bat`**：启动上下错落双悬浮窗口。

---

## 四、专精术语语料库配置与日常定制指南

为解决特定行业会议（如医疗生物、人工智能、金融法务）专业专有名词翻译不准、ASR 听错谐音的问题，系统内置了专精语料库引擎。

### 1. 配置文件路径

项目根目录下的 [`glossary.json`](glossary.json) 纯文本配置文件，可用 VS Code 或记事本直接修改：

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

### 2. 字段三大功用说明

- **`asr_fixes` (ASR 语音识别谐音矫正)**：左侧为语音识别容易听错的错别字/同音词，右侧为标准词。系统会在 $<0.15\text{ms}$ 内自动纠错（如把“落拉”替换为“LoRA”）；
- **`mt_terms` (机器翻译专业术语映射)**：左侧为源文词汇，右侧为目标语言规范翻译。保证翻译结果符合行业专业要求；
- **`hotwords` (阿里云百炼云端热词)**：启动同传会话时，自动作为模型先验知识下发到云端声学模型，提升专有名词的首字识别准确率。

### 3. 如何使新词库立即生效？

- **方式一（免重启热重载）**：向 `POST http://localhost:8000/api/glossary` 发送包含新 JSON 的请求，系统将在 5ms 内热重载；
- **方式二（重启生效）**：直接修改保存 `glossary.json` 后，重新运行 `./启动悬浮同传.command` 即可。

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

- **特性保证**：Harry Translate 原生悬浮窗基于 macOS `NSWindowCollectionBehaviorCanJoinAllSpaces | NSWindowCollectionBehaviorFullScreenAuxiliary` 与 Windows 置顶架构构建，天然悬浮于全屏播放的 Keynote、PowerPoint、腾讯会议及 Zoom 界面之上，不会被全屏 Spaces 吞没。

### Q11: 升级后出现异常，如何安全恢复？

- 先保存当前本地修改，再查看仓库中的可用版本：
  ```bash
  git status
  git switch -c local-backup
  ```
- 公开基线为 `v3.6.0`。`.env` 与 `.venv` 不会进入 Git，切换版本时不会删除本地凭证或环境。
- 如需报告问题，请附上脱敏日志；不要提交 API Key、`.env`、录音或包含个人信息的截图。

### Q12: 在小窗口下看中文输入或双行英译，感觉字号太挤或想让中文原文更大一些怎么办？

- **解决方案**：
  - 按下全局快捷键 **`Cmd + Shift + R`**（Windows 按 **`Ctrl + Shift + R`**），可在 **`68:32`** 与 **`65:35`** 比例之间一键切换；
  - `65:35` 模式将辅助区空间提升至 35%，结合小窗口 31px 安全包络，中文原文与两行英译均舒展开阔、字字清晰，偏好配置自动记忆保存。

---

## 七、部署完成测试验收指引

在首次安装或环境配置完成后，可通过运行自动化测试套件快速验证系统完整性与硬件兼容性：

```bash
# 激活项目专属虚拟环境 (Windows 使用 call .venv\Scripts\activate.bat)
source .venv/bin/activate

# 1. 验证 238 项全量 E2E 自动化测试 (基线功能全量回归)
python tests/run_e2e_tests.py

# 2. 验证 16 维工厂级终审审计门禁 (验证声卡 50ms 切片、425ms 延迟等核心性能)
python tests/audit_gate.py

# 3. 验证腾讯会议绝对稳态悬浮与 5 套字体配色方案 (AC-V1 ~ AC-V5)
python -m unittest tests/test_tencent_steady_hud_and_themes.py

# 4. 验证单态对抗极限压测 (连续 10s 静默与流式吐字，断言 delta opacity == 0.0)
python -m unittest tests/challenger_steady_hud_adversarial.py

# 5. 验证专精术语语料库与黄金比例 68%/32% 双视口防挤压布局
python -m unittest tests/test_glossary_and_golden_ratio_layout.py

# 6. 验证小窗口两行主译文零裁切物理包络专项测试
python -m unittest tests/repro_issue_twoline_output_clip.py

# 7. 验证中文原文辅助区 31px 安全包络防削顶专项测试
python -m unittest tests/repro_issue_chinese_input_clip.py

# 8. 验证 68:32 ⇄ 65:35 双模舞台比例自适应与快捷键专项测试
python -m unittest tests/test_hud_dual_ratio_mode.py
```

全部测试输出 PASS 即表明当前系统环境部署成功，处于工业级可交付状态。
