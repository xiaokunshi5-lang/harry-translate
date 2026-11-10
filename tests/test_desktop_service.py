import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch
from fastapi import FastAPI
from fastapi.testclient import TestClient
from core.desktop_service import install_desktop_routes


class DesktopServiceTests(unittest.TestCase):
    def setUp(self):
        self.app = FastAPI()
        self.server = SimpleNamespace(audio_capture_mgr=Mock(), active_channels=[],
                                      DASHSCOPE_API_KEY='', QWEN_REALTIME_WS_URL='', active_engine_type='')
        self.server.audio_capture_mgr.get_devices.return_value = {'devices': []}
        @self.app.get('/')
        def home():
            return {'secret_business_page': True}
        with patch('core.desktop_service.load_credentials', return_value=({}, '')):
            install_desktop_routes(self.app, self.server)
        self.client = TestClient(self.app, base_url='http://127.0.0.1')

    def boot(self):
        ticket = self.app.state.desktop.ticket
        response = self.client.get('/desktop/open', params={'ticket': ticket}, follow_redirects=False)
        self.assertEqual(response.status_code, 303)
        self.assertIn('HttpOnly', response.headers['set-cookie'])
        return ticket

    def test_unauthenticated_pages_and_api_are_denied(self):
        for path in ('/', '/api/desktop/status', '/desktop/setup'):
            self.assertEqual(self.client.get(path).status_code, 401)

    def test_empty_and_replayed_boot_ticket_rejected(self):
        self.assertEqual(self.client.get('/desktop/open').status_code, 403)
        ticket = self.boot()
        self.assertEqual(self.client.get('/desktop/open', params={'ticket': ticket}).status_code, 403)

    def test_business_page_redirected_before_key_validation(self):
        self.boot()
        response = self.client.get('/', follow_redirects=False)
        self.assertEqual(response.status_code, 303)
        self.assertEqual(response.headers['location'], '/desktop/setup')
        self.assertEqual(self.client.post('/api/desktop/start', json={}).status_code, 401)
        self.server.audio_capture_mgr.start.assert_not_called()

    def test_foreign_origin_and_host_denied(self):
        self.boot()
        self.assertEqual(self.client.post('/api/desktop/stop', headers={'Origin': 'https://evil.example'}).status_code, 403)
        self.assertEqual(self.client.get('/', headers={'Host': 'evil.example'}).status_code, 403)

    def test_failed_validation_remains_locked(self):
        self.boot()
        with patch('core.desktop_service.validate_key', side_effect=ValueError('无效密钥')):
            response = self.client.post('/api/desktop/validate', json={'api_key': 'invalid'})
        self.assertEqual(response.status_code, 400)
        self.assertFalse(self.app.state.desktop.validated)
        self.server.audio_capture_mgr.start.assert_not_called()

    def test_success_unlocks_but_does_not_record(self):
        self.boot()
        with patch('core.desktop_service.validate_key', return_value={'ws_url': 'wss://example', 'region': 'beijing', 'workspace': ''}), patch('core.desktop_service.save_credentials'):
            response = self.client.post('/api/desktop/validate', json={'api_key': 'valid-test-key'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.client.get('/').status_code, 200)
        self.assertFalse(self.app.state.desktop.running)
        self.server.audio_capture_mgr.start.assert_not_called()

    def test_persistence_failure_does_not_unlock(self):
        self.boot()
        with patch('core.desktop_service.validate_key', return_value={'ws_url': 'wss://example'}), patch('core.desktop_service.save_credentials', side_effect=OSError('disk full')):
            response = self.client.post('/api/desktop/validate', json={'api_key': 'private-test'})
        self.assertEqual(response.status_code, 500)
        self.assertFalse(self.app.state.desktop.validated)
        self.assertNotIn('private-test', response.text)

    def test_config_never_accepts_unvalidated_falsy_keys(self):
        self.boot()
        self.app.state.desktop.validated = True
        self.app.state.desktop.running = True
        for key in (0, False, None, '', 'unverified'):
            response = self.client.post('/api/config', json={'api_key': key})
            self.assertEqual(response.status_code, 400)

    def test_paused_legacy_device_change_cannot_open_audio(self):
        self.boot()
        self.app.state.desktop.validated = True
        response = self.client.post('/api/audio/device', json={'device_index': 0})
        self.assertEqual(response.status_code, 409)
        self.server.audio_capture_mgr.set_device.assert_not_called()

    def test_authorization_rechecked_after_waiting_for_operation_lock(self):
        import asyncio
        import httpx
        self.boot()
        async def check():
            state = self.app.state.desktop
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=self.app), base_url='http://127.0.0.1', cookies=self.client.cookies) as client:
                for route in ('start', 'test-mic'):
                    state.validated = True
                    await state.lock.acquire()
                    task = asyncio.create_task(client.post('/api/desktop/' + route, json={'device': 0}))
                    await asyncio.sleep(.05)
                    state.validated = False
                    state.lock.release()
                    response = await task
                    self.assertEqual(response.status_code, 401)
            self.server.audio_capture_mgr.set_device.assert_not_called()
        asyncio.run(check())


if __name__ == '__main__':
    unittest.main()
