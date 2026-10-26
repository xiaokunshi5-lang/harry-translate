# tests/test_repro_exp107_dual_hud_independent_lock.py
"""
【复现测试】EXP-107: 双悬浮同传 HUD 窗口独立锁定与独立解锁真实 Cocoa 门禁
- 根因定位:
  1. FloatingHUDApp.create_window() 在 dual 模式下为 win_en 和 win_zh 传入相同的 self.api 实例
  2. HudApi.toggle_lock() 调用 self.app.set_click_through() 遍历所有 controllers 把两个窗口同时锁死
  3. POST /api/hud/lock 仅维护全局布尔值，单窗解锁导致后台轮询连带解锁另一窗口
- 修复前预期:
  在当前未修复代码上运行，出现 AssertionError / KeyError (稳定红灯 3/3)
- 修复后预期:
  100% 真实 Objective-C HUDPanelHost 实例断言通过，双窗独立锁定、独立解锁、后端分窗隔离全绿 (0 退出码)
"""
import sys
import unittest
import time
import json

if sys.platform != "darwin":
    raise unittest.SkipTest("EXP-107 门禁测试必须在真实 macOS 环境下执行")

import AppKit
import objc
from tests.harness import FastAPITestClient


class TestReproExp107DualHUDIndependentLock(unittest.TestCase):
    def setUp(self):
        import float_app
        import server
        self.float_app = float_app
        self.server = server
        self.HUDPanelHost = getattr(float_app, "HUDPanelHost", None)
        self.assertIsNotNone(self.HUDPanelHost, "float_app.HUDPanelHost 必须存在")

        # 实例化两个真实 Cocoa HUDPanelHost 窗口 (绝对零 MagicMock)
        rect_en = AppKit.NSMakeRect(100, 500, 480, 160)
        rect_zh = AppKit.NSMakeRect(100, 300, 480, 160)
        base_mask = (
            AppKit.NSWindowStyleMaskTitled
            | AppKit.NSWindowStyleMaskClosable
            | AppKit.NSWindowStyleMaskResizable
        )

        self.panel_en = self.HUDPanelHost.alloc().initWithContentRect_styleMask_backing_defer_(
            rect_en, base_mask, AppKit.NSBackingStoreBuffered, False
        )
        self.panel_zh = self.HUDPanelHost.alloc().initWithContentRect_styleMask_backing_defer_(
            rect_zh, base_mask, AppKit.NSBackingStoreBuffered, False
        )

        # 初始状态确认：两个 Cocoa 窗口均具备 Resizable 掩码
        self.assertNotEqual(
            self.panel_en.styleMask() & AppKit.NSWindowStyleMaskResizable, 0
        )
        self.assertNotEqual(
            self.panel_zh.styleMask() & AppKit.NSWindowStyleMaskResizable, 0
        )

    def test_a_single_window_independent_lock(self):
        """测试 A: 点击窗口 EN 锁定，仅 EN 物理焊死，ZH 必须保持完全自由 (移动与缩放均不受限)"""
        float_app = self.float_app
        app = float_app.FloatingHUDApp(dual=True)

        class DummyWinEn:
            def __init__(self, native):
                self.native = native
                self.title = "Qwen_Meeting_HUD_En_中译英"
                self.evaluated = []
            def evaluate_js(self, s):
                self.evaluated.append(s)

        class DummyWinZh:
            def __init__(self, native):
                self.native = native
                self.title = "Qwen_Meeting_HUD_Zh_英译中"
                self.evaluated = []
            def evaluate_js(self, s):
                self.evaluated.append(s)

        win_en = DummyWinEn(self.panel_en)
        win_zh = DummyWinZh(self.panel_zh)

        ctrl_en = float_app.MacOSWindowController(win_en)
        ctrl_zh = float_app.MacOSWindowController(win_zh)

        # 模拟 dual 模式窗口绑定
        app.windows = [win_en, win_zh]
        app.window = win_en
        app.controllers = [ctrl_en, ctrl_zh]
        app.controller = ctrl_en

        if hasattr(app, "api_en") and app.api_en is not None:
            app.controller_map = {"en": ctrl_en, "zh": ctrl_zh}
            app.window_map = {"en": win_en, "zh": win_zh}
            app.api_en.window = win_en
            app.api_en.controller = ctrl_en
            app.api_zh.window = win_zh
            app.api_zh.controller = ctrl_zh
            app.api_en.toggle_lock(True)
        elif hasattr(app, "set_click_through") and "window_id" in app.set_click_through.__code__.co_varnames:
            app.set_click_through(True, window_id="en")
        else:
            app.api.toggle_lock(True)

        # 泵送 Cocoa run loop 处理 AppHelper.callAfter
        AppKit.NSRunLoop.currentRunLoop().runUntilDate_(
            AppKit.NSDate.dateWithTimeIntervalSinceNow_(0.05)
        )

        # 1. 断言 EN 必须物理锁定
        self.assertEqual(
            self.panel_en.styleMask() & AppKit.NSWindowStyleMaskResizable,
            0,
            "EXP-107 缺陷: EN 窗口锁定后未剥离 NSWindowStyleMaskResizable 掩码！"
        )
        orig_en_pos = self.panel_en.frame().origin
        self.panel_en.setFrameOrigin_(AppKit.NSMakePoint(999, 888))
        self.assertEqual(
            self.panel_en.frame().origin.x,
            orig_en_pos.x,
            "EXP-107 缺陷: EN 锁定后物理位置被篡改！"
        )

        # 2. 断言 ZH 必须保持自由 (未被连锁锁死)
        self.assertNotEqual(
            self.panel_zh.styleMask() & AppKit.NSWindowStyleMaskResizable,
            0,
            "EXP-107 根因复现: 仅锁定了 EN 窗口，ZH 窗口却被错误地剥离了 Resizable 掩码（被联动锁死）！"
        )
        target_zh_pt = AppKit.NSMakePoint(350, 450)
        self.panel_zh.setFrameOrigin_(target_zh_pt)
        self.assertEqual(
            self.panel_zh.frame().origin.x,
            target_zh_pt.x,
            "EXP-107 根因复现: ZH 窗口无法移动，被 EN 窗口联动锁死！"
        )

    def test_b_single_window_independent_unlock(self):
        """测试 B: 两窗均锁定时，单独解锁 EN，EN 恢复自由，ZH 必须持续保持物理焊死"""
        float_app = self.float_app
        app = float_app.FloatingHUDApp(dual=True)

        class DummyWin:
            def __init__(self, native, title):
                self.native = native
                self.title = title
                self.evaluated = []
            def evaluate_js(self, s):
                self.evaluated.append(s)

        win_en = DummyWin(self.panel_en, "Qwen_Meeting_HUD_En_中译英")
        win_zh = DummyWin(self.panel_zh, "Qwen_Meeting_HUD_Zh_英译中")

        ctrl_en = float_app.MacOSWindowController(win_en)
        ctrl_zh = float_app.MacOSWindowController(win_zh)

        app.windows = [win_en, win_zh]
        app.window = win_en
        app.controllers = [ctrl_en, ctrl_zh]
        app.controller = ctrl_en

        # 步骤 1: 将两个窗口都置为锁定状态
        ctrl_en.set_click_through(True)
        ctrl_zh.set_click_through(True)
        AppKit.NSRunLoop.currentRunLoop().runUntilDate_(
            AppKit.NSDate.dateWithTimeIntervalSinceNow_(0.05)
        )

        self.assertEqual(self.panel_en.styleMask() & AppKit.NSWindowStyleMaskResizable, 0)
        self.assertEqual(self.panel_zh.styleMask() & AppKit.NSWindowStyleMaskResizable, 0)

        # 步骤 2: 单独解锁 EN
        if hasattr(app, "api_en") and app.api_en is not None:
            app.controller_map = {"en": ctrl_en, "zh": ctrl_zh}
            app.window_map = {"en": win_en, "zh": win_zh}
            app.api_en.window = win_en
            app.api_en.controller = ctrl_en
            app.api_zh.window = win_zh
            app.api_zh.controller = ctrl_zh
            app.api_en.toggle_lock(False)
        elif hasattr(app, "set_click_through") and "window_id" in app.set_click_through.__code__.co_varnames:
            app.set_click_through(False, window_id="en")
        else:
            # 未修复代码：调用全局 toggle_lock(False) 会将 ZH 一并解锁
            app.api.toggle_lock(False)

        AppKit.NSRunLoop.currentRunLoop().runUntilDate_(
            AppKit.NSDate.dateWithTimeIntervalSinceNow_(0.05)
        )

        # 3. 断言 EN 已解除锁定，恢复自由
        self.assertNotEqual(
            self.panel_en.styleMask() & AppKit.NSWindowStyleMaskResizable,
            0,
            "EXP-107 缺陷: EN 解锁后未恢复 Resizable 掩码！"
        )
        target_en_pt = AppKit.NSMakePoint(200, 600)
        self.panel_en.setFrameOrigin_(target_en_pt)
        self.assertEqual(self.panel_en.frame().origin.x, target_en_pt.x)

        # 4. 断言 ZH 必须 100% 保持锁定 (绝对不得被连带解锁)
        self.assertEqual(
            self.panel_zh.styleMask() & AppKit.NSWindowStyleMaskResizable,
            0,
            "EXP-107 根因复现: 解锁 EN 窗口导致 ZH 窗口也被错误连带解锁（失去锁定）！"
        )
        orig_zh_pos = self.panel_zh.frame().origin
        self.panel_zh.setFrameOrigin_(AppKit.NSMakePoint(888, 777))
        self.assertEqual(
            self.panel_zh.frame().origin.x,
            orig_zh_pos.x,
            "EXP-107 根因复现: ZH 窗口锁定失效，坐标被意外改变！"
        )

    def test_c_backend_per_window_lock_and_global_emergency_unlock(self):
        """测试 C: 后端 /api/hud/lock 分窗口独立维护状态与全局应急一键解锁"""
        client = FastAPITestClient(self.server.app)

        # 1. 初始重置全部窗口锁定
        resp = client.post("/api/hud/lock", json={"locked": False})
        self.assertEqual(resp.status_code, 200)

        # 2. 独立锁定 EN 窗口
        resp_en = client.post("/api/hud/lock", json={"locked": True, "window_id": "en"})
        self.assertEqual(resp_en.status_code, 200)
        data_en = resp_en.json()
        self.assertIn("windows", data_en, "EXP-107 根因复现: /api/hud/lock 响应缺少 windows 分窗字典！")
        self.assertTrue(data_en["windows"].get("en"), "EN 窗口应为锁定")
        self.assertFalse(data_en["windows"].get("zh"), "ZH 窗口不应被锁定")
        self.assertTrue(data_en.get("locked"), "全局状态应为 True (any)")

        # 3. 独立锁定 ZH 窗口
        resp_zh = client.post("/api/hud/lock", json={"locked": True, "window_id": "zh"})
        self.assertEqual(resp_zh.status_code, 200)
        data_zh = resp_zh.json()
        self.assertTrue(data_zh["windows"].get("en"))
        self.assertTrue(data_zh["windows"].get("zh"))

        # 4. 独立解锁 EN 窗口，ZH 必须保持 True
        resp_unen = client.post("/api/hud/lock", json={"locked": False, "window_id": "en"})
        self.assertEqual(resp_unen.status_code, 200)
        data_unen = resp_unen.json()
        self.assertFalse(data_unen["windows"].get("en"), "EN 窗口应已解锁")
        self.assertTrue(data_unen["windows"].get("zh"), "ZH 窗口必须保持锁定")
        self.assertTrue(data_unen.get("locked"), "因为 ZH 仍锁定，全局 locked 仍应为 True")

        # 5. 全局应急解锁 (不带 window_id) 必须一键解锁全部窗口
        resp_global = client.post("/api/hud/lock", json={"locked": False})
        self.assertEqual(resp_global.status_code, 200)
        data_global = resp_global.json()
        self.assertFalse(data_global.get("locked"))
        self.assertFalse(data_global["windows"].get("en"))
        self.assertFalse(data_global["windows"].get("zh"))

        # 6. GET 接口支持 window_id / channel 查询并返回 window_locked
        client.post("/api/hud/lock", json={"locked": True, "window_id": "en"})
        resp_get_en = client.get("/api/hud/lock?channel=en")
        self.assertEqual(resp_get_en.status_code, 200)
        data_get_en = resp_get_en.json()
        self.assertEqual(data_get_en.get("window_id"), "en")
        self.assertTrue(data_get_en.get("window_locked"))

        resp_get_zh = client.get("/api/hud/lock?window_id=zh")
        self.assertEqual(resp_get_zh.status_code, 200)
        data_get_zh = resp_get_zh.json()
        self.assertEqual(data_get_zh.get("window_id"), "zh")
        self.assertFalse(data_get_zh.get("window_locked"))

        # 清理重置
        client.post("/api/hud/lock", json={"locked": False})

    def test_d_api_explicit_window_id_routing_and_headless(self):
        """测试 D: 验证 api_en 显式指定 window_id='zh' 时精确操作 ZH 控制器，且无窗口无头模式状态保真"""
        float_app = self.float_app
        app = float_app.FloatingHUDApp(dual=True)

        class DummyWin:
            def __init__(self, native, title):
                self.native = native
                self.title = title
            def evaluate_js(self, s):
                pass

        win_en = DummyWin(self.panel_en, "Qwen_Meeting_HUD_En_中译英")
        win_zh = DummyWin(self.panel_zh, "Qwen_Meeting_HUD_Zh_英译中")
        ctrl_en = float_app.MacOSWindowController(win_en)
        ctrl_zh = float_app.MacOSWindowController(win_zh)

        app.windows = [win_en, win_zh]
        app.controllers = [ctrl_en, ctrl_zh]
        app.controller_map = {"en": ctrl_en, "zh": ctrl_zh}
        app.window_map = {"en": win_en, "zh": win_zh}

        api_en = float_app.HudApi(app, controller=ctrl_en, window=win_en, window_id="en")
        api_zh = float_app.HudApi(app, controller=ctrl_zh, window=win_zh, window_id="zh")
        app.api_en = api_en
        app.api_zh = api_zh

        # 显式调用 api_en.toggle_lock(True, window_id="zh") -> 必须精准操作 ctrl_zh，绝不能误动 ctrl_en
        api_en.toggle_lock(True, window_id="zh")
        self.assertTrue(ctrl_zh.is_click_through(), "显式路由失败: ctrl_zh 未被锁定！")
        self.assertFalse(ctrl_en.is_click_through(), "串扰缺陷: 调用 window_id='zh' 误将 ctrl_en 锁死！")

        # 解锁 zh
        api_en.toggle_lock(False, window_id="zh")
        self.assertFalse(ctrl_zh.is_click_through())

        # 无头/单元测试模式（无窗口、无原生控制器）下 set_click_through 保真
        headless_app = float_app.FloatingHUDApp(dual=True)
        self.assertFalse(headless_app.is_click_through())
        headless_app.set_click_through(True)
        self.assertTrue(headless_app.is_click_through(), "无头模式下 set_click_through(True) 状态丢失！")
        headless_app.set_click_through(False)
        self.assertFalse(headless_app.is_click_through())


if __name__ == "__main__":
    unittest.main()
