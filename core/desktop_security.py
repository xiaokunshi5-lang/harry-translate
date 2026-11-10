"""Local credential encryption and bounded, audio-free realtime validation."""
import ctypes
from ctypes import wintypes
import json
import os
import re
import time

from core.app_paths import atomic_json, data_path

MODEL = 'qwen3.8-livetranslate-flash-realtime'


def endpoint_for(region, workspace):
    hosts = {'beijing': 'dashscope.aliyuncs.com', 'singapore': 'dashscope-intl.aliyuncs.com'}
    if region not in hosts:
        raise ValueError('请选择支持的地域：北京或新加坡。')
    workspace = str(workspace).strip()
    if workspace and not re.fullmatch(r'[A-Za-z0-9-]{1,80}', workspace):
        raise ValueError('业务空间 ID 只能包含字母、数字和短横线，请不要粘贴网址。')
    if workspace:
        suffix = 'cn-beijing' if region == 'beijing' else 'ap-southeast-1'
        host = f'{workspace}.{suffix}.maas.aliyuncs.com'
    else:
        host = hosts[region]
    return f'wss://{host}/api-ws/v1/realtime?model={MODEL}'


def friendly_error(message):
    message = str(message).lower()
    if any(x in message for x in ('401', 'invalid_api_key', 'invalidapikey', 'unauthorized', 'authentication')):
        return 'API Key 验证失败。请重新复制完整密钥，并确认地域和业务空间一致。'
    if any(x in message for x in ('403', 'permission', 'accessdenied', 'not authorized')):
        return '账户没有该同传模型的调用权限。请在百炼检查模型授权和业务空间。'
    if any(x in message for x in ('404', 'model not', 'modelnot', 'not found')):
        return '当前地域或账户无法使用此同传模型。请核对地域、业务空间和模型权限。'
    if any(x in message for x in ('balance', 'arrear', 'payment', 'quota', '429', 'insufficient')):
        return '账户余额、额度或调用频率受限，请检查百炼账单和模型配额后重试。'
    return '未能完成同传服务验证。请检查网络、地域、业务空间以及账户权限后重试；密钥没有保存。'


def validate_key(key, region, workspace, timeout=12):
    import websocket
    from engines.qwen_translators import QwenLiveTranslate38Engine
    key = str(key).strip()
    if not key or len(key) > 512 or any(c.isspace() for c in key):
        raise ValueError('请粘贴完整 API Key，不能留空或包含空格。')
    url = endpoint_for(region, workspace)
    connection = None
    try:
        connection = websocket.create_connection(url, header=['Authorization: Bearer ' + key], timeout=timeout)
        engine = QwenLiveTranslate38Engine(api_key=key, ws_url=url)
        from types import SimpleNamespace
        # Production uses WebSocketApp.sock (a WebSocket); this validator owns a
        # synchronous WebSocket directly, so adapt its public connected flag.
        engine.ws_client = SimpleNamespace(sock=connection, send=connection.send)
        # Reuse the production session format, without starting capture/reconnect threads.
        engine.live_update_session(target_lang='en', phrases={})
        if engine.corpus_status == 'error':
            raise ValueError(engine.last_error)
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            connection.settimeout(max(.1, deadline - time.monotonic()))
            raw = connection.recv()
            if not raw:
                raise ValueError('connection closed')
            event = json.loads(raw)
            if event.get('type') == 'error':
                raise ValueError(str(event.get('error', {})))
            if event.get('type') == 'session.updated':
                connection.send(json.dumps({'type': 'session.finish'}))
                return {'ws_url': url, 'region': region, 'workspace': str(workspace).strip()}
        raise TimeoutError('validation timeout')
    except Exception as error:
        raise ValueError(friendly_error(error)) from None
    finally:
        if connection is not None:
            connection.close()


class _Blob(ctypes.Structure):
    _fields_ = [('cbData', wintypes.DWORD), ('pbData', ctypes.POINTER(ctypes.c_ubyte))]


def _crypt(data, decrypt=False):
    if os.name != 'nt':
        raise OSError('本机密钥保存目前仅支持 Windows；可取消“记住密钥”。')
    buffer = ctypes.create_string_buffer(data)
    source = _Blob(len(data), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_ubyte)))
    destination = _Blob()
    crypt = ctypes.WinDLL('crypt32', use_last_error=True)
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    fn = crypt.CryptUnprotectData if decrypt else crypt.CryptProtectData
    fn.argtypes = [ctypes.POINTER(_Blob), ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p,
                   ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(_Blob)]
    fn.restype = wintypes.BOOL
    kernel.LocalFree.argtypes = [ctypes.c_void_p]
    kernel.LocalFree.restype = ctypes.c_void_p
    if not fn(ctypes.byref(source), None, None, None, None, 1, ctypes.byref(destination)):
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        return ctypes.string_at(destination.pbData, destination.cbData)
    finally:
        kernel.LocalFree(destination.pbData)


def save_credentials(key, config, remember):
    import base64
    # One atomic file means a failed write cannot pair a new endpoint with an old key.
    record = dict(config)
    record['secret'] = base64.b64encode(_crypt(key.encode())).decode() if remember else ''
    atomic_json(data_path('credentials.json'), record)


def load_credentials():
    import base64
    path = data_path('credentials.json')
    if not path.exists():
        return {}, ''
    record = json.loads(path.read_text(encoding='utf-8'))
    secret = record.pop('secret', '')
    key = _crypt(base64.b64decode(secret), decrypt=True).decode() if secret else ''
    return record, key
