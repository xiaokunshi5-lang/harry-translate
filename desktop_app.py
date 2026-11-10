"""Windows GUI entry point, also used by the frozen executable."""
import argparse
import os
import socket
import sys
import threading
import time


def run_desktop():
    parser = argparse.ArgumentParser()
    parser.add_argument('--smoke-test', action='store_true', help='Check packaged resources and gated server, then exit.')
    parser.add_argument('--native-smoke-test', action='store_true', help='Render the gated page in WebView2, then exit.')
    args = parser.parse_args()
    os.environ['HARRY_DESKTOP'] = '1'
    os.environ['DEFAULT_ENGINE'] = 'qwen3.8-livetranslate-flash-realtime'
    os.environ['AUDIO_INPUT_MODE'] = 'shared_mic'
    from core.app_paths import data_path, resource_path
    # A windowed PyInstaller process has no stdout; legacy diagnostics need a safe sink.
    log = data_path('desktop.log').open('a', encoding='utf-8')
    if sys.stdout is None:
        sys.stdout = log
    if sys.stderr is None:
        sys.stderr = log
    for name in ('index.html', 'float_ui.html', 'onboarding.html', 'api-guide.html', 'desktop-controls.js', 'meeting-hotwords.js'):
        if not resource_path(name).is_file():
            raise RuntimeError('安装文件缺失：' + name + '。请重新安装。')
    import uvicorn
    import server
    # Keep the bound socket: no free-port selection race, no fixed-port collision.
    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    listener.bind(('127.0.0.1', 0))
    port = listener.getsockname()[1]
    config = uvicorn.Config(server.app, host='127.0.0.1', port=port, log_level='warning', access_log=False)
    service = uvicorn.Server(config)
    thread = threading.Thread(target=service.run, kwargs={'sockets': [listener]}, daemon=True)
    thread.start()
    try:
        deadline = time.monotonic() + 20
        while not service.started:
            if not thread.is_alive() or time.monotonic() > deadline:
                raise RuntimeError('本机服务启动失败，请查看用户目录中的 desktop.log。')
            time.sleep(.05)
        if args.smoke_test:
            import urllib.request
            import urllib.error
            opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
            try:
                opener.open(f'http://127.0.0.1:{port}/api/config', timeout=3)
            except urllib.error.HTTPError as error:
                assert error.code == 401
            else:
                raise AssertionError('Desktop authentication guard missing')
            assert not server.audio_capture_mgr.is_running
            assert server.audio_capture_mgr.worker_a.stream is None
            assert not any(ch.active_engine.is_running for ch in server.active_channels)
            data_path('smoke-test.ok').write_text('resources, loopback server, auth gate, microphone off: PASS', encoding='utf-8')
            return 0
        import webview
        webview.settings['ALLOW_DOWNLOADS'] = True
        url = f'http://127.0.0.1:{port}/desktop/open?ticket={server.app.state.desktop.ticket}'
        window = webview.create_window('Harry Translate · 会议同传', url, width=1180, height=820,
                                       min_size=(760, 600), confirm_close=not args.native_smoke_test,
                                       hidden=args.native_smoke_test)
        native_errors = []
        def native_check():
            try:
                deadline = time.monotonic() + 20
                while time.monotonic() < deadline:
                    try:
                        if window.evaluate_js("Boolean(document.getElementById('key-form'))"):
                            assert window.evaluate_js("document.getElementById('audio-card').hidden")
                            assert not server.audio_capture_mgr.is_running
                            data_path('native-smoke-test.ok').write_text('WebView2 rendered API gate; audio off: PASS', encoding='utf-8')
                            return
                    except Exception:
                        pass
                    time.sleep(.2)
                raise RuntimeError('WebView2 failed to render the API gate')
            except Exception as error:
                native_errors.append(error)
            finally:
                window.destroy()
        webview.start(native_check if args.native_smoke_test else None, gui='edgechromium', private_mode=True)
        if native_errors:
            raise native_errors[0]
        return 0
    finally:
        server.app.state.desktop_stop()
        service.should_exit = True
        thread.join(timeout=10)
        server.audio_capture_mgr.terminate()
        listener.close()
        log.flush()


def main():
    from core.app_paths import instance_lock, AlreadyRunning
    try:
        with instance_lock():
            return run_desktop()
    except AlreadyRunning as error:
        import ctypes
        ctypes.windll.user32.MessageBoxW(None, str(error), 'Harry Translate', 0x40)
        return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except Exception as error:
        import traceback
        from core.app_paths import data_path
        with data_path('desktop.log').open('a', encoding='utf-8') as handle:
            traceback.print_exc(file=handle)
        if os.name == 'nt' and not any(flag in sys.argv for flag in ('--smoke-test', '--native-smoke-test')):
            import ctypes
            ctypes.windll.user32.MessageBoxW(None,
                '程序未能启动。请确认已安装 Microsoft Edge WebView2 Runtime，然后重试。\n'
                '详细诊断保存在：' + str(data_path('desktop.log')) + '\n' + type(error).__name__,
                'Harry Translate 启动失败', 0x10)
        raise SystemExit(1)
