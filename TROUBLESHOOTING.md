# Harry Translate (哈利同传) 30 秒现场极速排障速查手册 (TROUBLESHOOTING.md)

本手册专为涉外会议、重大发布会现场会务技术人员编写。按故障现象分类，提供可在 30 秒内定位根因并执行的单行修复命令。

---

## 一、30 秒现场排障速查总表

| 序号 | 故障现象 (Symptom) | 可能根因 (Root Cause) | 平台 | 30 秒快速修复命令 / 操作方案 (Rapid Fix Command) |
| :---: | :--- | :--- | :---: | :--- |
| **01** | **启动提示端口占用**<br>`Address already in use: 8000` | 上次未正常退出残留了孤儿进程，或本地其他 Web 服务占用了 8000 端口 | **Mac**<br><br>**Win** | `lsof -ti :8000 \| xargs kill -9`<br><br>`for /f "tokens=5" %a in ('netstat -aon ^\| findstr :8000') do taskkill /f /pid %a` |
| **02** | **双击脚本闪退**<br>提示“权限被拒绝”或无反应 | 下载或网盘同步导致 Unix 可执行权限（`+x`）丢失 | **Mac** | `chmod +x ~/Desktop/阿里同声传译/*.command ~/Desktop/阿里同声传译/*.sh` |
| **03** | **对着麦克风说话无字幕**<br>状态灯为绿但无反应 | 1. 麦克风系统隐私权限被拒；<br>2. 系统声音输入设备被静音；<br>3. 默认声卡选择错误 | **Mac**<br><br>**Win** | `tccutil reset Microphone` 并重启终端；<br><br>系统「设置」 -> 「隐私和安全性」 -> 开启「允许桌面应用访问麦克风」 |
| **04** | **只有我说话有字幕**<br>外宾/会议对方发言无字 | Channel B 虚拟内录未配置，无法从电脑音频总线回环捕获 Zoom/腾讯会议外音 | **Mac**<br><br>**Win** | `brew install blackhole-2ch`，在「音频 MIDI 设置」中创建多输出设备；<br><br>安装 VB-CABLE 驱动，在「录制」属性中勾选「侦听此设备」输出到耳机 |
| **05** | **提示 API Key 鉴权失败**<br>`Invalid API Key` / `401` | `.env` 文件未配置 Key、Key 存在首尾多余空格或已在控制台被吊销 | **Mac**<br><br>**Win** | `./切换API_Key.command` 重新粘贴有效 Key；<br><br>`切换API_Key.bat` 重新粘贴有效 Key，或访问 `http://localhost:8000/` 右上角抽屉配置 |
| **06** | **提示额度耗尽 / 欠费**<br>`Quota Exceeded` / `429` | 阿里云百炼账户余额不足，或触发了单账号并发限速 | **通用** | 登录阿里云百炼控制台（DashScope）充值或更换新 Key；单向听课时建议使用 `启动悬浮同传_英译中` 立省 50% 额度 |
| **07** | **浮窗无法拖动或调整大小**<br>把手与边缘拉伸无反应 | 浮窗处于「4 重物理位置硬锁状态（Physical Locked）」防误触 | **Mac**<br><br>**Win** | 按下键盘快捷键 **`Cmd + Shift + L`** 解锁（顶部功能药丸始终可点击）；<br><br>按下键盘快捷键 **`Ctrl + Shift + L`** 解锁，或在浏览器访问 `http://localhost:8000/api/hud/lock?locked=false` |
| **08** | **浮窗找不到 / 跑出屏幕**<br>外接显示器断开后视窗丢失 | 拔掉外接扩展屏后，视窗坐标仍停留在已断开的虚拟坐标区 | **通用** | 访问 `http://localhost:8000/api/hud/reset_pos` 或在终端重启浮窗脚本，窗口将自动重置于主屏居中偏下位置 |
| **09** | **Python 3.13 报错**<br>`No module named 'audioop'` | Python 3.13 官方移除了旧版 `audioop` C 模块 | **通用** | 系统自带自适应降级垫片；如需启用底层加速，运行：`pip install audioop-lts` |
| **10** | **Windows 安装 PyAudio 报错**<br>`Visual C++ 14.0 required` | Windows 系统缺少本地 C++ 编译器 | **Win** | 运行免编译预构建安装：<br>`pip install pipwin && pipwin install pyaudio` |
| **11** | **字幕出现明显滞后延时**<br>说话结束 2~3 秒才出字 | 1. 路由器 Wi-Fi 抖动严重；<br>2. 电脑开启了系统级低电量省电模式导致后台线程降频 | **通用** | 1. 会务现场建议插网线（Ethernet）；<br>2. 接入电源适配器，在主控大屏检查端到端延迟指示器（正常 $\le 450\text{ms}$） |
| **12** | **全屏演讲时浮窗消失**<br>被 PPT / Keynote 遮挡 | 使用了第三方浏览器网页全屏，而非原生 App 窗口 | **Mac** | 使用原生悬浮窗（`float_app.py` 具备 337 / FullScreenAuxiliary 顶层常驻能力），勿使用普通浏览器小窗全屏 |
| **13** | **未知代码变动或环境损坏**<br>系统无法正常拉起 | 误删或误改了核心文件 | **通用** | 先执行 `git status` 保存本地修改，再安全切换到稳定发布标签（`git switch --detach v4.0.0`）；不会触碰 `.env` 与 `.venv` |
| **14** | **悬浮窗缩放或长句被截断**<br>担心文字被窗口下沿切半 | 传统固定行高视口缺少动态滚动，或窗口拉伸未自适应 | **通用** | 系统已内置 GPU 加速平滑跟随与 ResizeObserver，超长自动向上滚动并保留底部 $\ge 8\text{px}$ 呼吸区；测试命令：<br>`.venv/bin/python3 -m unittest tests/test_viewport_scroll_and_bilingual_stack.py` |
| **15** | **小窗口输出两行时首行发虚遮挡**<br>像被毛玻璃遮住一半 | 旧版固定 28px 渐变羽化遮罩过大，且小窗口缺少两行包络保护 | **通用** | `v3.6` 引入 `twoLinesEnvelope` 两行物理包络与动态解耦遮罩，内容两行内遮罩尺寸动态归零，字字清晰零发虚；测试命令：<br>`.venv/bin/python -m unittest tests/repro_issue_twoline_output_clip.py` |
| **16** | **中文输入原文辅助区被分割线削顶**<br>汉字上半部分被裁切 | 辅助区旧版存在内边距与行高偏大，产生负向溢出 | **通用** | `v3.6` 移除 `padding-top` 并引入 12px/1.2 紧凑字号与 31px 安全包络，汉字稳落安全区零削顶；测试命令：<br>`.venv/bin/python -m unittest tests/repro_issue_chinese_input_clip.py` |
| **17** | **快速发言时上一句译文先蹦出来**<br>新句开头突兀复读闪现 | 跨句未做原子隔离，纯 ASR 转写阶段复用了旧句历史译文 | **通用** | `v3.6` 服务端接收新 `sentence_id` 时原子清空缓存，前端建立 `sentenceHasTranslation` 状态锁屏障，彻底根除跨句复读闪现；测试命令：<br>`.venv/bin/python -m unittest tests/repro_issue_stale_sentence_leak.py` |
| **18** | **希望中文原文有更大展示空间**<br>在小窗口看中文原文字号偏小 | 默认 68:32 比例优先倾向主译文，辅助区垂直净空有限 | **通用** | 按下 **`Cmd + Shift + R`**（Windows 按 **`Ctrl + Shift + R`**）秒级无缝切换为 **`65:35`** 模式，辅助区扩展至 35%，自动持久化记忆；测试命令：<br>`.venv/bin/python -m unittest tests/test_hud_dual_ratio_mode.py` |
| **19** | **浅色或白底 PPT 下字体看不清**<br>黄色字体在白底下对比度弱 | 会议胶片为浅色或高亮背景 | **通用** | 按下 **`Cmd + Shift + C`**（Windows 按 **`Ctrl + Shift + C`**）切换为 **`🎨 黑曜石`** 配色方案（深黑粗体加纯白发光轮廓），专为纯白 PPT 打造；测试命令：<br>`.venv/bin/python -m unittest tests/test_tencent_steady_hud_and_themes.py` |
| **20** | **会议桌距离发言人 1~2 米拾音偏弱**<br>说话声音小导致识别漏字 | 物理距离导致声压衰减，或环境空调微弱底噪干扰 | **通用** | `v4.0.0` 增强 C 级自适应 AGC（`target_rms=1200.0`, 最大增益 `3.2x`, `soft_knee=280`），云端 240ms 极速断句与 2.4s/3.8s 活跃提交；测试命令：<br>`.venv/bin/python -m unittest tests/test_repro_fix206_realtime_speed_and_dual_sync.py` |
| **21** | **悬浮窗退居后台时偶发滞后**<br>长时间切到其他窗口后吐字变慢 | macOS 系统 App Nap 机制对非激活进程施加 CPU 降频节能节流 | **Mac** | `v3.9` 已在 `float_app.py` 注入原生 `NSActivityLatencyCritical` 活性锁，保证退居后台仍维持高优先级毫秒级调度；测试命令：<br>`.venv/bin/python -m unittest tests/challenger_ui_engine_stress.py` |
| **22** | **Windows 双击 `.bat` 语法报错闪退**<br>`8000) was unexpected at this time` | 早期批处理脚本未转义括号语法炸弹 | **Win** | 当前最新版本已 100% 修复括号转义，且 5 个 `.bat` 具备零配置自举，双击直接启动 |
| **23** | **Windows 11 24H2 提示找不到 wmic**<br>`'wmic' is not recognized` | 微软在 Win11 24H2 中移除了旧版 `wmic.exe` | **Win** | 当前最新脚本已内置兼容判断，自动平滑回退至 PowerShell 进行残留进程清理 |
| **24** | **提示 API Key 鉴权失败但不想重启**<br>`401 / InvalidApiKey` | 填错了 Key 或账户过期，以往需要杀进程重启 | **通用** | 访问 `http://localhost:8000/` 右上角抽屉设置，填入新 Key 保存，后台线程平滑重载激活引擎 |
| **25** | **拔掉 USB 麦克风导致服务闪退**<br>硬件 I/O 异常 | 硬件物理断开导致音频采集抛出底层异常 | **通用** | 系统内置异常捕获与设备重枚举机制，自动重新扫描并平滑回退至系统默认麦克风 |
| **26** | **局域网设备无法访问大屏页面**<br>手机/iPad 无法打开 8000 端口 | 服务端默认绑定安全回环地址 `127.0.0.1` | **通用** | 在 `.env` 中添加 `HOST=0.0.0.0`，重启服务后即可在同一 Wi-Fi 下通过本机内网 IP 访问 |
| **27** | **短英文词（AI/PR）误伤了其他单词**<br>`rain` 变成 `r人工智能n` | 词法扫描未做英文单词边界保护 | **通用** | Aho-Corasick 自动机增加 ASCII 单词边界保护，短词仅在独立成词或中英混排时替换 |
| **28** | **Windows 快捷方式启动找不到热词库**<br>`glossary.json` 未加载 | 工作目录与工程根目录不一致 | **Win** | 系统采用项目绝对路径硬锚定（`_PROJECT_ROOT`），任意工作目录下均 100% 稳定读取 |
| **29** | **鼠标移到顶部控制栏不浮现**<br>未激活窗口悬停无反应 | macOS 原生窗口在非 Key Window 状态下默认丢弃鼠标移动事件 | **Mac** | `v4.0.0` 原生注入 `NSTrackingActiveAlways` 追踪区域配合 `handleTopZoneProximity` 动态感知，无需激活窗口即可秒显控制栏；测试命令：<br>`.venv/bin/python -m unittest tests/test_repro_hud_url_and_dock_policy.py` |
| **30** | **提词字体太小看不清**<br>外接 4K 大屏或远距离演讲 | 默认标准字号在远距离视距下辨识度受限 | **通用** | 按下 **`Cmd + Shift + F`**（Win 按 **`Ctrl + Shift + F`**）一键循环切至 **`🔤 大号`** (24px) 或 **`🔤 特大`** (29px)，亦可按 `Cmd/Ctrl + =/-` 缩放，历史行恒定 14px 零挤压；测试命令：<br>`.venv/bin/python -m unittest tests/test_hud_font_tiers.py` |
| **31** | **偶发虚假网络断开报警**<br>同传正常却频繁提示重连 | WebSocket 短暂抖动心跳探针判定过敏 | **通用** | `v4.0.0` 优化双向心跳容错窗口，引入指数退避重试，彻底消除虚假断网告警；测试命令：<br>`.venv/bin/python -m unittest tests/test_repro_fix207_reconnect_and_web_dedup.py` |
| **32** | **中文或带空格路径启动白屏**<br>终端或双击拉起无内容 | 目录包含中文（如“阿里同声传译”）或空格导致 `file:///` 转义异常 | **通用** | `v4.0.0` 原生层内置 URL 自愈机制（自动校验并修复 `%2520` 双重转义），100% 稳定加载本地 UI；测试命令：<br>`.venv/bin/python -m unittest tests/test_repro_hud_url_and_dock_policy.py` |
| **33** | **macOS Dock 栏出现多余图标**<br>悬浮窗启动后抢占 Dock 与菜单栏 | 普通 App 窗口策略导致系统生成标准 Dock 图标与抢焦 | **Mac** | `v4.0.0` 注入 `NSApplicationActivationPolicyAccessory` 严密锁定，彻底隐藏 Dock 图标与菜单栏，实现零干扰极光悬浮；测试命令：<br>`.venv/bin/python -m unittest tests/test_repro_hud_url_and_dock_policy.py` |

---

## 二、四大典型高频场景深度排查步骤

### 1. 声音采集异常（有声无字）排查流

```
                    ┌─────────────────────────┐
                    │ 现象: 说话完全无字幕输出  │
                    └────────────┬────────────┘
                                 │
                                 ▼
                     浏览器访问 http://localhost:8000/api/meta
                                 │
                 ┌───────────────┴───────────────┐
                 ▼                               ▼
       devices 列表为空                devices 正常识别麦克风
                 │                               │
                 ▼                               ▼
       执行系统麦克风重置:              检查 .env 中 DASHSCOPE_API_KEY
       Mac: tccutil reset Microphone    是否有效、账户是否有余额
       Win: 开启系统应用隐私权限
```

### 2. 虚拟回环（Channel B 英译中无字）排查流

1. **第一步：判断是否需要回环**：
   - 如果只是您本人对着电脑讲中文、翻译给外宾看，**无需虚拟回环声卡**，单麦克风即可正常工作；
   - 如果需要翻译 Zoom、Teams、腾讯会议中外宾讲话的声音，**必须安装并配置虚拟回环声卡**。
2. **第二步：检查多输出设备与监听状态**：
   - **macOS**：打开「音频 MIDI 设置」，确认已创建「多输出设备」，且同时勾选了「BlackHole 2ch」与您的「物理耳机/扬声器」；
   - **Windows**：打开声音设置的「录制」属性，确认在 `CABLE Output` 的「侦听」选项卡中勾选了「侦听此设备」，输出指向耳机。

### 3. 端口占用极速解除（30 秒自愈）

若提示 `Address already in use: 8000`：
- **macOS / Linux 一行命令**：
  ```bash
  lsof -ti :8000 | xargs kill -9
  ```
- **Windows CMD 一行命令**：
  ```cmd
  for /f "tokens=5" %a in ('netstat -aon ^| findstr :8000') do taskkill /f /pid %a
  ```
清理完成后，重新双击脚本即可秒级拉起。

### 4. 彻底还原出厂状态（秒级无损回滚）

在现场遇到复杂未知系统异常时，不要盲目修改源代码。直接执行项目自带的安全回滚脚本：
```bash
./rollback.sh v3.0-harry-translate-release
```
- **耗时**：实测 $< 5\text{ms}$；
- **安全性**：完全恢复所有经过 281 项测试验证的稳定代码，同时**绝对不会删除或覆盖**您的 `.env` 密钥配置和 `.venv` 虚拟运行环境。

### 5. 悬浮窗尺寸拉伸与多行视口跟随验证

遇到悬浮窗在非标准分辨率屏幕显示或长句子展示疑问时，按以下步骤验证：
1. **视口跟随专项自检**：运行专项测试套件检验平滑视口滚动、渐变淡出遮罩与双语立体分层：
   ```bash
   .venv/bin/python3 -m unittest tests/test_viewport_scroll_and_bilingual_stack.py
   ```
2. **多行生成防截断与动态解耦遮罩验证**：系统预留底部 $\ge 8\text{px}$ 呼吸区，随着发言持续吐字，轨道容器自动执行 `transform: translateY` 向上平滑滚动；`v3.6` 采用动态解耦遮罩（`--fade-mask-top-size`），两行包络内顶部遮罩归零，文字 100% 清晰露出，超长内容平滑过渡，无需任何手动滚动操作；
3. **窗口拖拽缩放自适应**：悬浮窗边缘支持无级缩放（300px~1920px 宽度），排版引擎依托 `ResizeObserver` 实时自适应折行且左右严格锁定 28px 安全留白。
