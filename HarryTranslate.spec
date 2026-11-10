# PyInstaller onedir build. Explicit resources: never collect the project tree.
from pathlib import Path
import ssl
import sys
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

root = Path(SPECPATH)
resources = ['index.html', 'float_ui.html', 'onboarding.html', 'api-guide.html',
             'desktop-controls.js', 'meeting-hotwords.js', 'LICENSE', 'NOTICE']
datas = [(str(root / name), '.') for name in resources]
datas += collect_data_files('webview')
datas.append((str(root / 'build' / 'licenses'), 'licenses/dependencies'))
# This builder's Python retains a bundled CA rejection list in SSLContext.
# Preserve it rather than weakening TLS verification or depending on the builder's path.
ssl_policy = Path(ssl.__file__).with_name('codex-rejected-cas.pem')
if ssl_policy.is_file():
    datas.append((str(ssl_policy), '.'))
python_license = Path(sys.base_prefix) / 'LICENSE.txt'
if python_license.is_file():
    datas.append((str(python_license), 'licenses/Python'))
a = Analysis([str(root / 'desktop_app.py')], pathex=[str(root)],
             binaries=[], datas=datas,
             hiddenimports=collect_submodules('uvicorn') + ['webview.platforms.winforms'],
             hookspath=[], hooksconfig={}, runtime_hooks=[],
             excludes=['PyQt5', 'PyQt6', 'PySide2', 'PySide6', 'pytest', 'pip_audit'],
             noarchive=False)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name='HarryTranslate',
          debug=False, bootloader_ignore_signals=False, strip=False, upx=False,
          console=False)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name='HarryTranslate')
