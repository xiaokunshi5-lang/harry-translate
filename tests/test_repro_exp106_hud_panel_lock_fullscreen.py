# tests/test_repro_exp106_hud_panel_lock_fullscreen.py
"""
【复现测试】EXP-106: HUD 物理级位置/尺寸锁定与 macOS 全屏空间置顶穿透真实 Cocoa 运行时门禁
- 根因定位:
  1. NSApp 未成功设置 Accessory 模式 (1)，普通 NSWindow 无法穿透至第三方全屏空间
  2. 窗口未剥离 NSWindowStyleMaskResizable，且 pywebview customize.js 直接调用 setFrameTopLeftPoint_ 导致锁定被绕过
  3. 未对 NSPanel/NSWindow 的 setFrameOrigin_/setFrameTopLeftPoint_/setFrame_display_ 进行硬锁保护
- 修复前预期: 真实 Cocoa 运行时抛出 AssertionError / AttributeError，退出码 != 0 (稳定红灯)
- 修复后预期: 100% 真实 Objective-C 对象断言通过，退出码 == 0 (绿灯)
"""
import sys
import unittest

# 严禁使用 unittest.mock.MagicMock 伪造 macOS Cocoa 对象
if sys.platform != "darwin":
    raise unittest.SkipTest("EXP-106 门禁测试必须在真实 macOS 环境下执行")

import AppKit
import objc


class TestReproExp106HUDPanelLockFullscreen(unittest.TestCase):
    def test_a_activation_policy_accessory(self):
        """测试 A: 验证 NSApplication activationPolicy 必须为 Accessory (1) 以支持全屏空间跨越"""
        import float_app
        # 必须由 float_app 明确确保 NSApplication.sharedApplication() 设置为 Accessory (1)
        app = AppKit.NSApplication.sharedApplication()
        self.assertEqual(
            app.activationPolicy(),
            1,
            f"EXP-106 缺陷: NSApplication activationPolicy 为 {app.activationPolicy()}，不是 Accessory (1)，全屏穿透将失效！"
        )

    def test_b_hud_panel_host_attributes(self):
        """测试 B: 验证 HUDPanelHost 真实 Cocoa 属性 (NSPanel, NonActivating, Space=337, Level>=101)"""
        import float_app
        self.assertTrue(
            hasattr(float_app, "HUDPanelHost"),
            "EXP-106 缺陷: float_app 缺少 HUDPanelHost 原生类定义！"
        )
        HUDPanelHost = getattr(float_app, "HUDPanelHost")
        self.assertTrue(
            issubclass(HUDPanelHost, AppKit.NSPanel),
            "EXP-106 缺陷: HUDPanelHost 必须继承自 AppKit.NSPanel！"
        )

        # 实例化真实 Cocoa Panel
        rect = AppKit.NSMakeRect(100, 100, 480, 240)
        # 基础 styleMask: Titled (1) | Closable (2) | Resizable (8)
        base_mask = AppKit.NSWindowStyleMaskTitled | AppKit.NSWindowStyleMaskClosable | AppKit.NSWindowStyleMaskResizable
        panel = HUDPanelHost.alloc().initWithContentRect_styleMask_backing_defer_(
            rect, base_mask, AppKit.NSBackingStoreBuffered, False
        )
        self.assertIsNotNone(panel, "HUDPanelHost 实例化失败")

        # 1. 验证必须注入 NSWindowStyleMaskNonactivatingPanel (1 << 7 = 128)
        non_activating_mask = 1 << 7
        self.assertTrue(
            bool(panel.styleMask() & non_activating_mask),
            f"EXP-106 缺陷: styleMask ({panel.styleMask()}) 缺少 NSWindowStyleMaskNonactivatingPanel (128)！"
        )

        # 2. 验证 CollectionBehavior 必须为 337 (CanJoinAllSpaces | FullScreenAuxiliary | Stationary | IgnoresCycle)
        self.assertEqual(
            panel.collectionBehavior(),
            337,
            f"EXP-106 缺陷: collectionBehavior ({panel.collectionBehavior()}) 必须为 337！"
        )

        # 3. 验证 Window Level 必须 >= 101 (NSPopUpMenuWindowLevel)
        self.assertGreaterEqual(
            panel.level(),
            101,
            f"EXP-106 缺陷: level ({panel.level()}) 低于 NSPopUpMenuWindowLevel (101)！"
        )

        # 4. 验证 hidesOnDeactivate 必须为 False
        self.assertFalse(
            panel.hidesOnDeactivate(),
            "EXP-106 缺陷: hidesOnDeactivate 必须恒为 False，失去焦点不得隐藏！"
        )

    def test_c_hud_physical_lock_frame_and_style_mask(self):
        """测试 C: 锁定状态下，调用 setFrameOrigin_ / setFrameTopLeftPoint_ / setFrame_display_ 坐标与尺寸 100% 焊死"""
        import float_app
        HUDPanelHost = getattr(float_app, "HUDPanelHost", None)
        self.assertIsNotNone(HUDPanelHost, "float_app.HUDPanelHost 不存在")

        rect = AppKit.NSMakeRect(200, 300, 500, 260)
        base_mask = AppKit.NSWindowStyleMaskTitled | AppKit.NSWindowStyleMaskClosable | AppKit.NSWindowStyleMaskResizable
        panel = HUDPanelHost.alloc().initWithContentRect_styleMask_backing_defer_(
            rect, base_mask, AppKit.NSBackingStoreBuffered, False
        )

        # 模拟进入锁定模式
        class DummyWindow:
            native = panel
        ctrl = float_app.MacOSWindowController(DummyWindow())
        ctrl._set_mouse_on_main(True)

        # 1. 验证剥离了 NSWindowStyleMaskResizable
        self.assertEqual(
            panel.styleMask() & AppKit.NSWindowStyleMaskResizable,
            0,
            "EXP-106 缺陷: 锁定状态下未剥离 NSWindowStyleMaskResizable，边缘依然可以缩放拉伸！"
        )

        # 2. 记录当前 frame
        locked_frame = panel.frame()
        orig_x = locked_frame.origin.x
        orig_y = locked_frame.origin.y
        orig_w = locked_frame.size.width
        orig_h = locked_frame.size.height

        # 3. 尝试调用 setFrameOrigin_ 试图移动
        panel.setFrameOrigin_(AppKit.NSMakePoint(999, 888))
        cur_frame = panel.frame()
        self.assertEqual(cur_frame.origin.x, orig_x, "EXP-106 缺陷: 锁定状态下 setFrameOrigin_ 未被拦截！")
        self.assertEqual(cur_frame.origin.y, orig_y, "EXP-106 缺陷: 锁定状态下 setFrameOrigin_ 未被拦截！")

        # 4. 尝试调用 setFrameTopLeftPoint_ 试图移动 (pywebview 内部移动方式)
        panel.setFrameTopLeftPoint_(AppKit.NSMakePoint(999, 888))
        cur_frame = panel.frame()
        self.assertEqual(cur_frame.origin.x, orig_x, "EXP-106 缺陷: 锁定状态下 setFrameTopLeftPoint_ 未被拦截！")
        self.assertEqual(cur_frame.origin.y, orig_y, "EXP-106 缺陷: 锁定状态下 setFrameTopLeftPoint_ 未被拦截！")

        # 5. 尝试调用 setFrame_display_ 试图改变尺寸与坐标
        illegal_rect = AppKit.NSMakeRect(10, 10, 800, 600)
        panel.setFrame_display_(illegal_rect, True)
        cur_frame = panel.frame()
        self.assertEqual(cur_frame.origin.x, orig_x, "EXP-106 缺陷: 锁定状态下 setFrame_display_ 坐标被篡改！")
        self.assertEqual(cur_frame.origin.y, orig_y, "EXP-106 缺陷: 锁定状态下 setFrame_display_ 坐标被篡改！")
        self.assertEqual(cur_frame.size.width, orig_w, "EXP-106 缺陷: 锁定状态下 setFrame_display_ 宽度被篡改！")
        self.assertEqual(cur_frame.size.height, orig_h, "EXP-106 缺陷: 锁定状态下 setFrame_display_ 高度被篡改！")

        # 6. 尝试调用 setFrame_ 试图改变尺寸与坐标 (验证无 AttributeError 且完全被焊死)
        panel.setFrame_(illegal_rect)
        cur_frame = panel.frame()
        self.assertEqual(cur_frame.origin.x, orig_x, "EXP-106 缺陷: 锁定状态下 setFrame_ 坐标被篡改！")
        self.assertEqual(cur_frame.size.width, orig_w, "EXP-106 缺陷: 锁定状态下 setFrame_ 宽度被篡改！")

        # 7. 尝试调用 setFrame_display_animate_ 试图改变尺寸与坐标
        panel.setFrame_display_animate_(illegal_rect, True, True)
        cur_frame = panel.frame()
        self.assertEqual(cur_frame.origin.x, orig_x, "EXP-106 缺陷: 锁定状态下 setFrame_display_animate_ 坐标被篡改！")
        self.assertEqual(cur_frame.size.width, orig_w, "EXP-106 缺陷: 锁定状态下 setFrame_display_animate_ 宽度被篡改！")

        # 8. 边界测试: 当 _hud_locked=True 但 _locked_frame 为 None 时，setFrame_display_ 绝对不得穿透篡改坐标
        panel._locked_frame = None
        panel.setFrame_display_(illegal_rect, True)
        cur_frame = panel.frame()
        self.assertEqual(cur_frame.origin.x, orig_x, "EXP-106 缺陷: _locked_frame 为 None 时硬锁被绕过！")
        self.assertEqual(cur_frame.size.width, orig_w, "EXP-106 缺陷: _locked_frame 为 None 时硬锁被绕过！")

    def test_d_hud_unlock_freedom(self):
        """测试 D: 解锁状态下，窗口可自由移动且恢复缩放掩码"""
        import float_app
        HUDPanelHost = getattr(float_app, "HUDPanelHost", None)
        self.assertIsNotNone(HUDPanelHost, "float_app.HUDPanelHost 不存在")

        rect = AppKit.NSMakeRect(200, 300, 500, 260)
        base_mask = AppKit.NSWindowStyleMaskTitled | AppKit.NSWindowStyleMaskClosable | AppKit.NSWindowStyleMaskResizable
        panel = HUDPanelHost.alloc().initWithContentRect_styleMask_backing_defer_(
            rect, base_mask, AppKit.NSBackingStoreBuffered, False
        )

        class DummyWindow:
            native = panel
        ctrl = float_app.MacOSWindowController(DummyWindow())
        # 先锁再解
        ctrl._set_mouse_on_main(True)
        ctrl._set_mouse_on_main(False)

        # 1. 恢复可缩放
        self.assertNotEqual(
            panel.styleMask() & AppKit.NSWindowStyleMaskResizable,
            0,
            "EXP-106 缺陷: 解锁状态下未恢复 NSWindowStyleMaskResizable 缩放掩码！"
        )

        # 2. 允许自由移动通过 setFrameOrigin_
        target_point = AppKit.NSMakePoint(350, 450)
        panel.setFrameOrigin_(target_point)
        cur_frame = panel.frame()
        self.assertEqual(cur_frame.origin.x, target_point.x, "解锁状态下 setFrameOrigin_ 无法自由移动！")
        self.assertEqual(cur_frame.origin.y, target_point.y, "解锁状态下 setFrameOrigin_ 无法自由移动！")

        # 3. 允许自由移动与缩放通过 setFrame_ (验证 setFrame_ 无 AttributeError 且正常生效)
        new_rect = AppKit.NSMakeRect(400, 500, 600, 300)
        panel.setFrame_(new_rect)
        cur_frame = panel.frame()
        self.assertEqual(cur_frame.origin.x, new_rect.origin.x, "解锁状态下 setFrame_ 无法自由移动！")
        self.assertEqual(cur_frame.size.width, new_rect.size.width, "解锁状态下 setFrame_ 无法自由缩放！")

        # 4. 验证 setLevel_ 强制最低下限 101
        panel.setLevel_(25)
        self.assertGreaterEqual(panel.level(), 101, "setLevel_ 未能维持 101 最低下限！")

        # 5. 验证 setCollectionBehavior_ 强制维持 337
        panel.setCollectionBehavior_(123)
        self.assertEqual(panel.collectionBehavior(), 337, "setCollectionBehavior_ 未能强制维持 337！")


if __name__ == "__main__":
    unittest.main()
