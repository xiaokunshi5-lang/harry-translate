# Harry Translate (哈利同传) 30 秒现场极速排障速查手册 (TROUBLESHOOTING.md)

本手册专为涉外会议、重大发布会现场会务技术人员编写。按故障现象分类，提供可在 30 秒内定位根因并执行的单行修复命令。

---

## 一、30 秒现场排障速查总表

| 序号 | 故障现象 (Symptom) | 可能根因 (Root Cause) | 平台 | 30 秒快速修复命令 / 操作方案 (Rapid Fix Command) |
| :---: | :--- | :--- | :---: | :--- |
| **01** | **启动提示端口占用**<br>`Address already in use: 8000` | 上次未正常退出残留了孤儿进程，或本地其他 Web 服务占用了 8000 端口 | **Mac**<br><br>**Win** | `lsof -ti :8000 \| xargs kill -9`<br><br>`for /f "tokens=5" %a in ('netstat -aon ^\| findstr :8000') do taskkill /f /pid %a` |
| **02** | **双击脚本闪退**<br>提示“权限被拒绝”或无反应 | 下载或网盘同步导致 Unix 可执行权限（`+x`）丢失 | **Mac** | `chmod +x ~/harry-translate/*.command ~/harry-translate/*.sh` |
| **03** | **对着麦克风说话无字幕**<br>状态灯为绿但无反应 | 1. 麦克风系统隐私权限被拒；<br>2. 系统声音输入设备被静音；<br>3. 默认声卡选择错误 | **Mac**<br><br>**Win** | `tccutil reset Microphone` 并重启终端；<br><br>系统「设置」 -> 「隐私和安全性」 -> 开启「允许桌面应用访问麦克风」 |
| **04** | **只有我说话有字幕**<br>外宾/会议对方发言无字 | Channel B 虚拟内录未配置，无法从电脑音频总线回环捕获 Zoom/腾讯会议外音 | **Mac**<br><br>**Win** | `brew install blackhole-2ch`，在「音频 MIDI 设置」中创建多输出设备；<br><br>安装 VB-CABLE 驱动，在「录制」属性中勾选「侦听此设备」输出到耳机 |
| **05** | **提示 API Key 鉴权失败**<br>`Invalid API Key` / `401` | `.env` 文件未配置 Key、Key 存在首尾多余空格或已在控制台被吊销 | **Mac**<br><br>**Win** | `./切换API_Key.command` 重新粘贴有效 Key；<br><br>`切换API_Key.bat` 重新粘贴有效 Key，或访问 `http://localhost:8000/` 右上角抽屉配置 |
| **06** | **提示额度耗尽 / 欠费**<br>`Quota Exceeded` / `429` | 阿里云百炼账户余额不足，或触发了单账号并发限速 | **通用** | 登录阿里云百炼控制台（DashScope）充值或更换新 Key；单向听课时建议使用 `启动悬浮同传_英译中` 立省 50% 额度 |
| **07** | **浮窗无法点击或移动**<br>鼠标完全穿透到了下层 | 浮窗处于「鼠标穿透锁定状态（Click-Through Locked）」 | **Mac**<br><br>**Win** | 按下键盘快捷键 **`Cmd + Shift + L`** 解锁；<br><br>按下键盘快捷键 **`Ctrl + Shift + L`** 解锁，或在浏览器访问 `http://localhost:8000/api/hud/lock?locked=false` |
| **08** | **浮窗找不到 / 跑出屏幕**<br>外接显示器断开后视窗丢失 | 拔掉外接扩展屏后，视窗坐标仍停留在已断开的虚拟坐标区 | **通用** | 访问 `http://localhost:8000/api/hud/reset_pos` 或在终端重启浮窗脚本，窗口将自动重置于主屏居中偏下位置 |
| **09** | **Python 3.13 报错**<br>`No module named 'audioop'` | Python 3.13 官方移除了旧版 `audioop` C 模块 | **通用** | 系统自带自适应降级垫片；如需启用底层加速，运行：`pip install audioop-lts` |
| **10** | **Windows 安装 PyAudio 报错**<br>`Visual C++ 14.0 required` | Windows 系统缺少本地 C++ 编译器 | **Win** | 运行免编译预构建安装：<br>`pip install pipwin && pipwin install pyaudio` |
| **11** | **字幕出现明显滞后延时**<br>说话结束 2~3 秒才出字 | 1. 路由器 Wi-Fi 抖动严重；<br>2. 电脑开启了系统级低电量省电模式导致后台线程降频 | **通用** | 1. 会务现场建议插网线（Ethernet）；<br>2. 接入电源适配器，在主控大屏检查端到端延迟指示器（正常 $\le 450\text{ms}$） |
| **12** | **全屏演讲时浮窗消失**<br>被 PPT / Keynote 遮挡 | 使用了第三方浏览器网页全屏，而非原生 App 窗口 | **Mac** | 使用原生悬浮窗（`float_app.py` 具备 337 / FullScreenAuxiliary 顶层常驻能力），勿使用普通浏览器小窗全屏 |
| **13** | **未知代码变动或环境损坏**<br>系统无法正常拉起 | 误删或误改了核心文件 | **通用** | 先执行 `git status` 保存本地修改，再切换到 `v3.8.0` 基线；不要删除 `.env` 与 `.venv` |
| **14** | **悬浮窗缩放或长句被截断**<br>担心文字被窗口下沿切半 | 传统固定行高视口缺少动态滚动，或窗口拉伸未自适应 | **通用** | 系统已内置 GPU 加速平滑跟随与 ResizeObserver，超长自动向上滚动并保留底部 $\ge 8\text{px}$ 呼吸区；测试命令：<br>`.venv/bin/python3 -m unittest tests/test_viewport_scroll_and_bilingual_stack.py` |
| **15** | **小窗口输出两行时首行发虚遮挡**<br>像被毛玻璃遮住一半 | 旧版固定 28px 渐变羽化遮罩过大，且小窗口缺少两行包络保护 | **通用** | `v3.6` 引入 `twoLinesEnvelope` 两行物理包络与动态解耦遮罩，内容两行内遮罩尺寸动态归零，字字清晰零发虚；测试命令：<br>`.venv/bin/python -m unittest tests/repro_issue_twoline_output_clip.py` |
| **16** | **中文输入原文辅助区被分割线削顶**<br>汉字上半部分被裁切 | 辅助区旧版存在内边距与行高偏大，产生负向溢出 | **通用** | `v3.6` 移除 `padding-top` 并引入 12px/1.2 紧凑字号与 31px 安全包络，汉字稳落安全区零削顶；测试命令：<br>`.venv/bin/python -m unittest tests/repro_issue_chinese_input_clip.py` |
| **17** | **快速发言时上一句译文先蹦出来**<br>新句开头突兀复读闪现 | 跨句未做原子隔离，纯 ASR 转写阶段复用了旧句历史译文 | **通用** | `v3.6` 服务端接收新 `sentence_id` 时原子清空缓存，前端建立 `sentenceHasTranslation` 状态锁屏障，彻底根除跨句复读闪现；测试命令：<br>`.venv/bin/python -m unittest tests/repro_issue_stale_sentence_leak.py` |
| **18** | **希望中文原文有更大展示空间**<br>在小窗口看中文原文字号偏小 | 默认 68:32 比例优先倾向主译文，辅助区垂直净空有限 | **通用** | 按下 **`Cmd + Shift + R`**（Windows 按 **`Ctrl + Shift + R`**）秒级无缝切换为 **`65:35`** 模式，辅助区扩展至 35%，自动持久化记忆；测试命令：<br>`.venv/bin/python -m unittest tests/test_hud_dual_ratio_mode.py` |
| **19** | **浅色或白底 PPT 下字体看不清**<br>黄色字体在白底下对比度弱 | 会议胶片为浅色或高亮背景 | **通用** | 按下 **`Cmd + Shift + C`**（Windows 按 **`Ctrl + Shift + C`**）切换为 **`🎨 黑曜石`** 配色方案（深黑粗体加纯白发光轮廓），专为纯白 PPT 打造；测试命令：<br>`.venv/bin/python -m unittest tests/test_tencent_steady_hud_and_themes.py` |

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

### 4. 安全恢复代码基线

公开版本不附带会覆盖文件的自动回滚脚本。遇到复杂异常时，先保存当前工作，再切换已发布标签：
```bash
git status
git switch -c local-backup
git switch --detach v3.8.0
```
- `.env` 与 `.venv` 被 `.gitignore` 排除，不会因切换标签被删除或覆盖；
- 如需回到自己的修改，执行 `git switch local-backup`；
- 遇到无法安全处理的数据损坏时，先备份整个项目目录再操作。
