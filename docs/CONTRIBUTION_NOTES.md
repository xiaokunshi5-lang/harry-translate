# Windows desktop contribution preview

本贡献分支以原作者 v3.6 提交 d039a75 为基础。克隆时 main 已是 v4.0（6d256d4）；为避免覆盖其后续功能，本分支未合并 v4.0。维护者应评审后按功能移植到最新版，不应直接将该预览版当作 v4.0 替代品。

## 内容
- Windows 桌面入口、PyInstaller 构建、Inno Setup 安装器与 WebView2 引导。
- API Key 首次验证、地区/工作空间配置、申请教程、本机 DPAPI 加密保存。
- 麦克风检测、会话启动/暂停，以及原生采样率转换兼容。
- 分类会议热词、搜索、启停、导入导出、并发修改保护与云端生效状态。
- Windows 源码启动脚本、云端连接和热词修正、相关测试与文档。

本次整理未修改原工作目录中的应用。未包含个人 .env、个人 glossary.json、凭据、录音、日志、虚拟环境、历史备份或编译产物。glossary.json 保留上游公开示例。第三方许可证保留原文。旧界面测试 check_hotwords_ui.cjs 是历史测试，当前分类界面以 check_hotword_categories.cjs 为准；仅将历史测试中的本机依赖路径替换为标准模块引用。

## 本次贡献副本验证（2026-11-10，Windows）
- compileall：通过。
- 桌面、安全、原生采样率、分类热词、云端语料五组定向测试：30 项通过。
- check_desktop_ui.cjs、check_hotword_categories.cjs：通过（Playwright / Edge）。
- unittest discover：298 项，276 项通过、10 项失败、4 项错误、8 项跳过；并非全绿。
- 失败包括 3 项音频通道队列断言、3 项 Windows 下 POSIX 可执行位检查、3 项旧 BAT 内容断言，以及热词刷新 7.217ms 超出旧测试 5ms 阈值。
- 4 项错误涉及缺少 bash 和 Unix resource 模块。音频通道失败是否受测试共享状态影响仍需排查，不能直接归因于平台。
- 测试生成的词库迁移数据已还原，不随提交发布。

原开发目录此前的安装包和测试结果见 COMMERCIAL_IMPLEMENTATION.md。文中的 output/ 路径是本地历史验证记录，不包含在仓库；不代表本次副本全量测试已通过。

## 仍需解决
未签名；未在干净 Windows / 缺少 WebView2 的系统完整验收；会议内录仍依赖可用回环设备；桌面引导当前仅提供 Qwen；旧费用估算不是阿里云实际账单。云端调用仍需网络与用户自己的有效 API Key。本次没有重新构建或发布 EXE，也没有自动向上游提交合并请求。

## 复现
Python 3.12 环境安装 requirements.txt；Windows 构建参考 PACKAGING.md 和 build/requirements-windows.lock。运行：

```text
python -m compileall -q server.py float_app.py desktop_app.py core engines tests
python -m unittest tests.test_desktop_contract tests.test_desktop_service tests.test_audio_native_rate tests.test_glossary_categories tests.test_cloud_corpus
python -m unittest discover -s tests -p "test_*.py"
```

界面测试需要 Node.js、playwright 模块和 Microsoft Edge：

```text
node tests/check_desktop_ui.cjs
node tests/check_hotword_categories.cjs
```
