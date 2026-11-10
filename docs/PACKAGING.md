# Windows 安装包构建与验收

目标：Windows 10/11 x64。PyInstaller onedir 包含 Python 运行时；Inno Setup 生成安装、快捷方式与卸载程序。用户不需要 Python、Codex 或 BAT。开发工具不随产品发布。

构建入口：`build/build-windows.ps1 -Python <构建环境python> -ISCC <ISCC.exe>`。需要先安装并锁定 PyInstaller，以及 Inno Setup。安装器会检测 WebView2，缺失时运行微软官方在线引导程序；因此首次安装可能需要联网。下载引导程序的构建脚本检查 Authenticode 状态与微软发布者，不通过则停止。

已使用 PyInstaller 6.22.3 和 Inno Setup 6.7.4 生成 EXE 与安装器。精确版本/官方哈希见 build/requirements-windows.lock，第三方许可在 build/licenses 并随包发布。pip-audit 复核未发现已知漏洞（output/dependency-audit.json）。

发行资源使用显式白名单，包括界面、meeting-hotwords.js、desktop-controls.js、LICENSE、NOTICE 和依赖许可。严禁打包开发者 .env、私人词库、日志、备份或录音。

本机冻结后的 --smoke-test、--native-smoke-test 以及隔离目录安装后的原生界面测试均通过。首次冻结试跑曾发现构建运行时 SSL 依赖的证书策略文件缺失，已在 spec 中显式包含，未降低 TLS 校验。此构建使用现有 Python 3.12 运行时；改用官方 Python 构建时必须重新验证依赖与冻结后行为。

验收必须覆盖：冻结后 --smoke-test、--native-smoke-test，普通用户安装，干净 Windows（无 Python/Codex），缺少 WebView2，中文用户名，网络不可用，升级保留用户设置，卸载不误删用户数据。只有开发机通过不能声称所有客户机器均可运行。

安装包未配置商业代码签名证书，SmartScreen/杀毒提示不能保证消除。发布前由产品方提供证书并执行签名和干净机器测试。

官方来源：
- https://pyinstaller.org/en/stable/license.html （商业打包例外）
- https://pywebview.flowrl.com/guide/freezing.html
- https://jrsoftware.org/files/is/license.txt （允许商业用途，保留相关版权；官网请求商业用户购买支持）
- https://learn.microsoft.com/en-us/microsoft-edge/webview2/concepts/distribution
