"""Authenticated local desktop endpoints; legacy development server stays compatible."""
import asyncio
import json
import secrets
import time
from urllib.parse import urlsplit

from fastapi import Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response
from core.app_paths import atomic_json, data_path, resource_path
from core.desktop_security import MODEL, load_credentials, save_credentials, validate_key


class DesktopState:
    def __init__(self):
        self.token = secrets.token_urlsafe(32)
        self.ticket = secrets.token_urlsafe(32)
        self.validated = False
        self.running = False
        self.key = ''
        self.config = {'region': 'beijing', 'workspace': ''}
        self.lock = asyncio.Lock()
        self.notice = ''
        try:
            config, self.key = load_credentials()
            self.config.update(config)
        except Exception:
            self.notice = '无法读取之前保存的密钥，请重新输入。原文件未删除。'
        self.remembered = bool(self.key)

    def authenticated(self, connection):
        return secrets.compare_digest(connection.cookies.get('harry_session', ''), self.token)


def install_desktop_routes(app, server):
    state = DesktopState()
    app.state.desktop = state

    def stop():
        state.running = False
        server.audio_capture_mgr.stop()
        for channel in server.active_channels:
            channel.stop()

    app.state.desktop_stop = stop

    @app.middleware('http')
    async def desktop_guard(request, call_next):
        # Bind to loopback AND defend against browser DNS-rebinding / cross-site requests.
        host = request.headers.get('host', '').split(':')[0]
        origin = request.headers.get('origin')
        if host not in ('127.0.0.1', 'localhost'):
            return JSONResponse({'message': '不允许的主机'}, status_code=403)
        if origin and urlsplit(origin).netloc != request.headers.get('host'):
            return JSONResponse({'message': '不允许的跨站请求'}, status_code=403)
        if request.url.path != '/desktop/open' and not state.authenticated(request):
            return JSONResponse({'message': '请从 Harry Translate 桌面程序打开。'}, status_code=401)
        public = ('/desktop/', '/api/desktop/')
        if not state.validated and not request.url.path.startswith(public):
            if request.url.path.startswith('/api/'):
                return JSONResponse({'message': '请先验证 API Key'}, status_code=401)
            return RedirectResponse('/desktop/setup', status_code=303)
        if request.method == 'POST' and request.url.path == '/api/config':
            try:
                body = await request.json()
            except Exception:
                return JSONResponse({'message': '配置内容无效'}, status_code=400)
            if not isinstance(body, dict):
                return JSONResponse({'message': '配置必须是对象'}, status_code=400)
            if any(k in body for k in ('api_key', 'dashscope_api_key')):
                return JSONResponse({'message': '请点击“账户与麦克风”重新验证密钥。'}, status_code=400)
            model = body.get('engine_model') or body.get('engine') or body.get('active_engine')
            if model and model != MODEL:
                return JSONResponse({'message': '当前桌面试用版仅开放已验证的千问同传模型。'}, status_code=400)
            if not state.running:
                return JSONResponse({'message': '暂停时请在“账户与麦克风”中设置设备，然后开始翻译。'}, status_code=409)
        if request.method == 'POST' and not request.url.path.startswith('/api/desktop/'):
            async with state.lock:
                if not state.validated:
                    return JSONResponse({'message': '请先验证 API Key'}, status_code=401)
                if request.url.path in ('/api/config', '/api/audio/device') and not state.running:
                    return JSONResponse({'message': '暂停时请在“账户与麦克风”中选择设备。'}, status_code=409)
                response = await call_next(request)
        else:
            response = await call_next(request)
        response.headers['Cache-Control'] = 'no-store'
        response.headers['Referrer-Policy'] = 'no-referrer'
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'DENY'
        return response

    @app.get('/desktop/open')
    def open_desktop(ticket: str = ''):
        if not state.ticket or not secrets.compare_digest(ticket, state.ticket):
            return JSONResponse({'message': '启动链接已失效，请重新打开程序。'}, status_code=403)
        state.ticket = ''
        response = RedirectResponse('/desktop/setup', status_code=303)
        response.set_cookie('harry_session', state.token, httponly=True, samesite='strict')
        return response

    @app.get('/desktop/setup')
    def setup():
        return HTMLResponse(resource_path('onboarding.html').read_text(encoding='utf-8'))

    @app.get('/desktop/api-guide')
    def guide():
        return HTMLResponse(resource_path('api-guide.html').read_text(encoding='utf-8'))

    @app.get('/desktop/controls.js')
    def controls():
        return Response(resource_path('desktop-controls.js').read_text(encoding='utf-8'), media_type='text/javascript')

    @app.get('/api/desktop/status')
    def status():
        devices = server.audio_capture_mgr.get_devices() if state.validated else {}
        settings_file = data_path('audio-settings.json')
        try:
            audio = json.loads(settings_file.read_text(encoding='utf-8')) if settings_file.exists() else {}
        except (OSError, ValueError):
            audio = {}
        return {'validated': state.validated, 'running': state.running,
                'has_saved_key': state.remembered, 'has_key': bool(state.key), 'region': state.config['region'],
                'workspace': state.config.get('workspace', ''), 'notice': state.notice,
                'devices': devices.get('devices', []), 'audio': audio}

    @app.post('/api/desktop/validate')
    async def validate(request: Request):
        async with state.lock:
            if state.running:
                await asyncio.to_thread(stop)
            state.validated = False
            try:
                body = await request.json()
                if not isinstance(body, dict):
                    raise ValueError('请提交有效的账户配置。')
                key = str(body.get('api_key') or state.key).strip()
                region = body.get('region', 'beijing')
                workspace = body.get('workspace', '')
                config = await asyncio.to_thread(validate_key, key, region, workspace)
                await asyncio.to_thread(save_credentials, key, config, bool(body.get('remember', True)))
                state.config, state.key = config, key
                state.remembered = bool(body.get('remember', True))
                state.notice = ''
                server.DASHSCOPE_API_KEY = key
                server.QWEN_REALTIME_WS_URL = config['ws_url']
                server.active_engine_type = MODEL
                for channel in server.active_channels:
                    channel.qwen_engine.api_key = key
                    channel.qwen_engine.ws_url = config['ws_url']
                    channel.gummy_engine.api_key = key
                    channel.switch_engine(MODEL)
                state.validated = True
                return {'status': 'ok'}
            except ValueError as error:
                return JSONResponse({'message': str(error)}, status_code=400)
            except Exception:
                return JSONResponse({'message': '无法保存本机配置。请取消“记住密钥”重试，并检查用户目录写入权限。'}, status_code=500)

    def choose_audio(body):
        devices = server.audio_capture_mgr.get_devices()['devices']
        available = {int(d['index']): d for d in devices}
        try:
            index = int(body['device'])
        except (KeyError, ValueError, TypeError):
            raise ValueError('请选择实际使用的麦克风。')
        if index not in available:
            raise ValueError('麦克风已断开，请刷新列表后重新选择。')
        mode = body.get('mode', 'shared_mic')
        if mode not in ('shared_mic', 'meeting'):
            raise ValueError('请选择现场对话或远程会议。')
        loopback = None
        if mode == 'meeting':
            try:
                loopback = int(body.get('loopback'))
            except (TypeError, ValueError):
                raise ValueError('远程会议需要选择可用的系统声音输入，不能用普通麦克风替代。')
            if loopback not in available or not available[loopback]['is_loopback']:
                raise ValueError('未找到系统声音输入。当前设备尚不能录制远程会议声音，请先使用现场对话模式。')
        return index, mode, loopback, available[index]

    @app.post('/api/desktop/test-mic')
    async def test_mic(request: Request):
        if not state.validated:
            return JSONResponse({'message': '请先验证密钥'}, status_code=401)
        async with state.lock:
            if not state.validated:
                return JSONResponse({'message': '请先验证密钥'}, status_code=401)
            if state.running:
                return JSONResponse({'message': '请先暂停翻译再检测麦克风。'}, status_code=409)
            try:
                body = await request.json()
                if not isinstance(body, dict):
                    raise ValueError('请选择有效的麦克风。')
                index, _, _, device = choose_audio(dict(body, mode='shared_mic'))
                def sample():
                    import audioop
                    import pyaudio
                    audio = server.audio_capture_mgr.p
                    rate = int(device['sample_rate'])
                    stream = audio.open(format=pyaudio.paInt16, channels=1, rate=rate, input=True,
                                        input_device_index=index, frames_per_buffer=rate // 10)
                    peak = 0
                    try:
                        for _ in range(20):
                            peak = max(peak, audioop.rms(stream.read(rate // 10, exception_on_overflow=False), 2))
                    finally:
                        stream.stop_stream()
                        stream.close()
                    return peak
                peak = await asyncio.to_thread(sample)
                return {'status': 'ok', 'level': min(100, round(peak / 32768 * 300)),
                        'heard': peak > 100, 'message': '检测到声音，可以开始翻译。' if peak > 100 else '设备可打开，但声音太小。请靠近麦克风说话，检查静音开关和 Windows 麦克风权限。'}
            except ValueError as error:
                return JSONResponse({'message': str(error)}, status_code=400)
            except Exception:
                return JSONResponse({'message': '无法打开此麦克风。请在 Windows 设置→隐私和安全性→麦克风允许桌面应用访问，或选择其他设备。'}, status_code=400)

    @app.post('/api/desktop/start')
    async def start(request: Request):
        if not state.validated:
            return JSONResponse({'message': '请先验证密钥'}, status_code=401)
        async with state.lock:
            if not state.validated:
                return JSONResponse({'message': '请先验证密钥'}, status_code=401)
            if state.running:
                return {'status': 'ok'}
            try:
                body = await request.json()
                if not isinstance(body, dict):
                    raise ValueError('请选择有效的麦克风配置。')
                index, mode, loopback, device = choose_audio(body)
                manager = server.audio_capture_mgr
                result = await asyncio.to_thread(manager.set_device, index, 'A')
                if result.get('status') != 'ok':
                    raise ValueError('此麦克风无法用于实时翻译，请更换输入设备或检查麦克风权限。')
                if mode == 'meeting':
                    result = await asyncio.to_thread(manager.set_device, loopback, 'B')
                    if result.get('status') != 'ok' or manager.worker_b.is_idle:
                        raise ValueError('系统声音输入无法开启，请选择其他设备。')
                server.AUDIO_INPUT_MODE = mode
                for channel in server.active_channels:
                    channel.start(state.key)
                # Do not upload until both requested translation sessions are ready.
                deadline = time.monotonic() + 15
                while not all(c.active_engine.is_ready.is_set() for c in server.active_channels):
                    errors = [c.active_engine.last_error for c in server.active_channels if c.active_engine.last_error]
                    if errors or time.monotonic() >= deadline:
                        from core.desktop_security import friendly_error
                        raise ValueError(friendly_error(' '.join(errors)))
                    await asyncio.sleep(.1)
                atomic_json(data_path('audio-settings.json'), {'device_name': device['name'], 'mode': mode,
                            'loopback': loopback})
                state.running = True
                manager.worker_a.start()
                if mode == 'meeting':
                    manager.worker_b.start()
                return {'status': 'ok'}
            except ValueError as error:
                await asyncio.to_thread(stop)
                return JSONResponse({'message': str(error)}, status_code=400)
            except Exception:
                await asyncio.to_thread(stop)
                return JSONResponse({'message': '启动失败，已停止音频采集。请检查设备和网络后重试。'}, status_code=500)

    @app.post('/api/desktop/stop')
    async def pause():
        async with state.lock:
            await asyncio.to_thread(stop)
        return {'status': 'ok'}

    @app.post('/api/desktop/forget')
    async def forget():
        async with state.lock:
            await asyncio.to_thread(stop)
            save_credentials('', state.config, False)
            state.key = ''
            state.remembered = False
            state.validated = False
            server.DASHSCOPE_API_KEY = ''
            for channel in server.active_channels:
                channel.qwen_engine.api_key = ''
                channel.gummy_engine.api_key = ''
        return {'status': 'ok'}
