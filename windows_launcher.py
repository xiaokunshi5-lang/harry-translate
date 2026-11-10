"""Windows launcher using the project's isolated Python environment."""
import argparse
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time
import urllib.request
import webbrowser

ROOT = Path(__file__).resolve().parent
BASE = 'http://127.0.0.1:8000'

def ready():
    try:
        with urllib.request.build_opener(urllib.request.ProxyHandler({})).open(BASE + '/api/meta', timeout=2) as response:
            data = json.load(response)
        return data.get('status') == 'ok' and 'channel_status' in data and 'active_engine' in data
    except Exception:
        return False

def ensure_server():
    if ready():
        return
    with socket.socket() as probe:
        if probe.connect_ex(('127.0.0.1', 8000)) == 0:
            raise RuntimeError('Port 8000 is occupied by another service. Close it and retry.')
    env = dict(os.environ, PYTHONUTF8='1', PYTHONUNBUFFERED='1')
    with (ROOT / 'windows-server.log').open('a', encoding='utf-8') as log:
        proc = subprocess.Popen([sys.executable, '-u', str(ROOT / 'server.py')], cwd=ROOT,
                                env=env, stdout=log, stderr=log, stdin=subprocess.DEVNULL,
                                creationflags=subprocess.CREATE_NO_WINDOW)
    for _ in range(60):
        if proc.poll() is not None:
            raise RuntimeError('Server exited. See windows-server.log for details.')
        if ready():
            print('Local service is ready: ' + BASE)
            return
        time.sleep(0.5)
    proc.terminate()
    proc.wait(timeout=10)
    raise RuntimeError('Server startup timed out. See windows-server.log.')

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--dashboard', action='store_true')
    parser.add_argument('--check-server', action='store_true')
    parser.add_argument('--dual', action='store_true')
    parser.add_argument('--channel', default='auto', choices=['auto', 'en', 'zh'])
    args = parser.parse_args()
    os.chdir(ROOT)
    from dotenv import dotenv_values
    key = dotenv_values(ROOT / '.env').get('DASHSCOPE_API_KEY', '')
    if not key or 'your' in key.lower():
        print('API Key is not configured: local interface testing only; real translation is unavailable.')
        print('Fill DASHSCOPE_API_KEY in .env, then restart the service.')
    ensure_server()
    if args.check_server:
        return 0
    if args.dashboard:
        webbrowser.open(BASE + '/split')
        return 0
    command = [sys.executable, str(ROOT / 'float_app.py'), '--channel', args.channel]
    if args.dual:
        command.append('--dual')
    result = subprocess.call(command)
    if result:
        print('Native window failed; opening the browser interface.')
        webbrowser.open(BASE + ('/split' if args.dual else '/hud?channel=' + args.channel))
    return result

if __name__ == '__main__':
    try:
        sys.exit(main())
    except Exception as error:
        print('Startup failed: ' + str(error))
        sys.exit(1)
