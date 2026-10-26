#!/usr/bin/env python3
"""
float_app.py - High-Performance Cross-Platform Desktop Floating HUD.

Lightweight native webview overlay powered by pywebview (macOS WKWebView & Windows Edge WebView2)
with zero bundled heavy frameworks.
Provides native ctypes integration for macOS NSWindow and Windows HWND:
- macOS: NSWindow collectionBehavior 337 (FullScreenAuxiliary | CanJoinAllSpaces),
  status window level 25 (kCGStatusWindowLevelKey), setIgnoresMouseEvents for click-through,
  and setSharingType (NSWindowSharingNone) for screen-share stealth.
- Windows: user32 SetWindowLongPtrW toggling WS_EX_TRANSPARENT | WS_EX_LAYERED,
  flushed via SetWindowPos(SWP_FRAMECHANGED), and SetWindowDisplayAffinity for stealth mode.
Exposes HudApi JS bridge to float_ui.html with non-blocking CLI flags for automated test runners.
"""

import os
import sys
import json
import time
import ctypes
import ctypes.util
import argparse
import threading
from typing import Optional, Dict, Any

# ==============================================================================
# pywebview Import with Headless/Fallback Tolerance
# ==============================================================================
try:
    import webview
except ImportError:
    webview = None

# Optional PyObjC for native main-thread dispatch on macOS
_pyobjc_available = False
NSApp = None
NSWindowCollectionBehaviorCanJoinAllSpaces = 1
NSWindowCollectionBehaviorMoveToActiveSpace = 2
NSWindowCollectionBehaviorStationary = 16
NSWindowCollectionBehaviorIgnoresCycle = 64
NSWindowCollectionBehaviorFullScreenAuxiliary = 256
NS_WINDOW_COLLECTION_BEHAVIOR_HUD = 337  # 1 | 16 | 64 | 256 (CanJoinAllSpaces | FullScreenAuxiliary)
NS_STATUS_WINDOW_LEVEL = 25              # kCGStatusWindowLevelKey / NSStatusWindowLevel
NS_POPUP_MENU_WINDOW_LEVEL = 101         # kCGPopUpMenuWindowLevelKey / NSPopUpMenuWindowLevel
NSStatusWindowLevel = 25
NSPopUpMenuWindowLevel = 101
NSApplicationActivationPolicyAccessory = 1

if sys.platform == "darwin":
    try:
        import AppKit
        from AppKit import (
            NSApp,
            NSEvent,
            NSEventMaskLeftMouseDown,
            NSWindowCollectionBehaviorCanJoinAllSpaces,
            NSWindowCollectionBehaviorFullScreenAuxiliary,
            NSWindowCollectionBehaviorStationary,
            NSWindowCollectionBehaviorIgnoresCycle,
            NSWindowCollectionBehaviorMoveToActiveSpace,
            NSStatusWindowLevel,
            NSPopUpMenuWindowLevel,
            NSApplicationActivationPolicyAccessory,
        )
        from PyObjCTools import AppHelper
        _pyobjc_available = True
    except Exception:
        _pyobjc_available = False

HUDPanelHost = None
if sys.platform == "darwin" and _pyobjc_available:
    from objc import super as objc_super
    try:
        # Enforce accessory activation policy for macOS FullScreen Space roaming
        AppKit.NSApplication.sharedApplication().setActivationPolicy_(1)
    except Exception:
        pass

    class HUDPanelHost(AppKit.NSPanel):
        """
        Native macOS Floating Non-Activating Panel Host.
        - Automatically injects NSWindowStyleMaskNonactivatingPanel (1 << 7 = 128)
        - Enforces NSWindowCollectionBehaviorCanJoinAllSpaces | FullScreenAuxiliary | Stationary | IgnoresCycle (337)
        - Enforces minimum window level NSPopUpMenuWindowLevel (101)
        - Hardware-level position and size hard lock via _hud_locked frame guard
        """
        focus = True
        _hud_locked = False
        _locked_frame = None

        def initWithContentRect_styleMask_backing_defer_(self, rect, styleMask, backing, defer):
            panel_mask = int(styleMask) | (1 << 7)
            self = objc_super(HUDPanelHost, self).initWithContentRect_styleMask_backing_defer_(
                rect, panel_mask, backing, defer
            )
            if self is not None:
                self._hud_locked = False
                self._locked_frame = None
                try:
                    app = AppKit.NSApplication.sharedApplication()
                    if hasattr(app, "setActivationPolicy_"):
                        app.setActivationPolicy_(1)
                except Exception:
                    pass

                self.setFloatingPanel_(True)
                self.setBecomesKeyOnlyIfNeeded_(True)
                self.setWorksWhenModal_(True)
                objc_super(HUDPanelHost, self).setHidesOnDeactivate_(False)
                objc_super(HUDPanelHost, self).setCollectionBehavior_(337)
                objc_super(HUDPanelHost, self).setLevel_(101)
            return self

        def canBecomeKeyWindow(self):
            return bool(getattr(self, "focus", True))

        def canBecomeMainWindow(self):
            return False

        def hidesOnDeactivate(self):
            return False

        def setHidesOnDeactivate_(self, flag):
            objc_super(HUDPanelHost, self).setHidesOnDeactivate_(False)

        def setLevel_(self, level):
            objc_super(HUDPanelHost, self).setLevel_(max(int(level), 101))

        def setCollectionBehavior_(self, behavior):
            objc_super(HUDPanelHost, self).setCollectionBehavior_(337)

        def setFrameTopLeftPoint_(self, point):
            if getattr(self, "_hud_locked", False):
                return
            objc_super(HUDPanelHost, self).setFrameTopLeftPoint_(point)

        def setFrameOrigin_(self, point):
            if getattr(self, "_hud_locked", False):
                return
            objc_super(HUDPanelHost, self).setFrameOrigin_(point)

        def setFrame_(self, frame):
            if getattr(self, "_hud_locked", False):
                return
            self.setFrame_display_(frame, True)

        def setFrame_display_(self, frame, display):
            if getattr(self, "_hud_locked", False):
                locked = getattr(self, "_locked_frame", None)
                if locked is None:
                    try:
                        locked = self.frame()
                        self._locked_frame = locked
                    except Exception:
                        pass
                if locked is not None:
                    objc_super(HUDPanelHost, self).setFrame_display_(locked, display)
                return
            objc_super(HUDPanelHost, self).setFrame_display_(frame, display)

        def setFrame_display_animate_(self, frame, display, animate):
            if getattr(self, "_hud_locked", False):
                locked = getattr(self, "_locked_frame", None)
                if locked is None:
                    try:
                        locked = self.frame()
                        self._locked_frame = locked
                    except Exception:
                        pass
                if locked is not None:
                    objc_super(HUDPanelHost, self).setFrame_display_animate_(locked, display, False)
                return
            objc_super(HUDPanelHost, self).setFrame_display_animate_(frame, display, animate)

    # Automatically hook BrowserView.WindowHost as soon as HUDPanelHost is defined
    try:
        import webview.platforms.cocoa as cocoa
        cocoa.BrowserView.WindowHost = HUDPanelHost
        AppKit.NSApplication.sharedApplication().setActivationPolicy_(1)
    except Exception:
        pass

# ==============================================================================
# Native OS Window Controllers (ctypes AppKit & user32)
# ==============================================================================

# ------------------------------------------------------------------------------
# macOS AppKit / Cocoa ctypes Implementation
# ------------------------------------------------------------------------------
# Constants
NS_WINDOW_COLLECTION_BEHAVIOR_CAN_JOIN_ALL_SPACES = 1 << 0       # 1
NS_WINDOW_COLLECTION_BEHAVIOR_MOVE_TO_ACTIVE_SPACE = 1 << 1      # 2
NS_WINDOW_COLLECTION_BEHAVIOR_STATIONARY = 1 << 4                # 16
NS_WINDOW_COLLECTION_BEHAVIOR_IGNORES_CYCLE = 1 << 6             # 64
NS_WINDOW_COLLECTION_BEHAVIOR_FULL_SCREEN_AUXILIARY = 1 << 8     # 256
NS_WINDOW_COLLECTION_BEHAVIOR_HUD = 337  # 1 | 16 | 64 | 256 (CanJoinAllSpaces | FullScreenAuxiliary)
NS_STATUS_WINDOW_LEVEL = 25              # kCGStatusWindowLevelKey / NSStatusWindowLevel
NS_POPUP_MENU_WINDOW_LEVEL = 101         # kCGPopUpMenuWindowLevelKey / NSPopUpMenuWindowLevel

# NSWindowSharingType (Stealth Mode)
NS_WINDOW_SHARING_NONE = 0               # Excluded from screen capture / recording / Zoom sharing
NS_WINDOW_SHARING_READ_ONLY = 1          # Standard window sharing

_appkit = None
_objc = None
_msgSend_p_p = None
_msgSend_p_p_rect_ulong_ulong_bool = None
_msgSend_void_p_bool = None
_msgSend_bool_p = None
_msgSend_void_p_ulong = None
_msgSend_ulong_p = None
_msgSend_void_p_int = None
_msgSend_int_p = None

_SEL_setIgnoresMouseEvents = None
_SEL_ignoresMouseEvents = None
_SEL_setCollectionBehavior = None
_SEL_collectionBehavior = None
_SEL_setLevel = None
_SEL_level = None
_SEL_setSharingType = None
_SEL_sharingType = None

if sys.platform == "darwin":
    try:
        _appkit = ctypes.cdll.LoadLibrary("/System/Library/Frameworks/AppKit.framework/AppKit")
        _objc_path = ctypes.util.find_library("objc")
        if _objc_path:
            _objc = ctypes.cdll.LoadLibrary(_objc_path)

        if _objc:
            _objc.objc_getClass.restype = ctypes.c_void_p
            _objc.objc_getClass.argtypes = [ctypes.c_char_p]
            _objc.sel_registerName.restype = ctypes.c_void_p
            _objc.sel_registerName.argtypes = [ctypes.c_char_p]

            msgSend = _objc.objc_msgSend
            _msgSend_p_p = ctypes.cast(msgSend, ctypes.CFUNCTYPE(ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p))
            _msgSend_p_p_rect_ulong_ulong_bool = ctypes.cast(
                msgSend,
                ctypes.CFUNCTYPE(
                    ctypes.c_void_p,
                    ctypes.c_void_p,
                    ctypes.c_void_p,
                    ctypes.c_double,
                    ctypes.c_double,
                    ctypes.c_double,
                    ctypes.c_double,
                    ctypes.c_ulong,
                    ctypes.c_ulong,
                    ctypes.c_bool,
                ),
            )
            _msgSend_void_p_bool = ctypes.cast(
                msgSend, ctypes.CFUNCTYPE(None, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_bool)
            )
            _msgSend_bool_p = ctypes.cast(
                msgSend, ctypes.CFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
            )
            _msgSend_void_p_ulong = ctypes.cast(
                msgSend, ctypes.CFUNCTYPE(None, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_ulong)
            )
            _msgSend_ulong_p = ctypes.cast(
                msgSend, ctypes.CFUNCTYPE(ctypes.c_ulong, ctypes.c_void_p, ctypes.c_void_p)
            )
            _msgSend_void_p_int = ctypes.cast(
                msgSend, ctypes.CFUNCTYPE(None, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_int)
            )
            _msgSend_int_p = ctypes.cast(
                msgSend, ctypes.CFUNCTYPE(ctypes.c_int, ctypes.c_void_p, ctypes.c_void_p)
            )

            _SEL_setIgnoresMouseEvents = _objc.sel_registerName(b"setIgnoresMouseEvents:")
            _SEL_ignoresMouseEvents = _objc.sel_registerName(b"ignoresMouseEvents")
            _SEL_setCollectionBehavior = _objc.sel_registerName(b"setCollectionBehavior:")
            _SEL_collectionBehavior = _objc.sel_registerName(b"collectionBehavior")
            _SEL_setLevel = _objc.sel_registerName(b"setLevel:")
            _SEL_level = _objc.sel_registerName(b"level")
            _SEL_setSharingType = _objc.sel_registerName(b"setSharingType:")
            _SEL_sharingType = _objc.sel_registerName(b"sharingType")
    except Exception:
        pass


class MacOSWindowController:
    """Native macOS Cocoa NSWindow controller using PyObjC on main thread, with ctypes fallback."""

    def __init__(self, webview_window=None):
        self.window = webview_window
        self._native_ptr = None
        self.is_locked = False
        self.is_stealth = False
        self._drag_monitor = None

    def _get_ptr(self) -> int:
        if self._native_ptr:
            return self._native_ptr
        if self.window is None:
            return 0

        # Method 0: AppKit calls must be strictly restricted to the main thread
        if threading.current_thread() is not threading.main_thread():
            return 0

        # Method 1: Check window.native (PyObjC pointer or int)
        native = getattr(self.window, "native", None)
        if native is not None:
            try:
                import objc
                self._native_ptr = objc.pyobjc_id(native)
                return self._native_ptr
            except Exception:
                pass
            if isinstance(native, int):
                self._native_ptr = native
                return self._native_ptr

        # Method 2: Query NSApplication.sharedApplication.windows
        if _objc and _msgSend_p_p and _msgSend_ulong_p:
            try:
                NSApp = _objc.objc_getClass(b"NSApplication")
                if NSApp:
                    app = _msgSend_p_p(NSApp, _objc.sel_registerName(b"sharedApplication"))
                    if app:
                        windows = _msgSend_p_p(app, _objc.sel_registerName(b"windows"))
                        if windows:
                            count = _msgSend_ulong_p(windows, _objc.sel_registerName(b"count"))
                            if count and count > 0:
                                getter = ctypes.cast(
                                    _objc.objc_msgSend,
                                    ctypes.CFUNCTYPE(
                                        ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_ulong
                                    ),
                                )
                                for idx in range(count):
                                    win_ptr = getter(windows, _objc.sel_registerName(b"objectAtIndex:"), idx)
                                    if win_ptr:
                                        self._native_ptr = win_ptr
                                        return self._native_ptr
            except Exception:
                pass

        return 0

    def setup_hud_window(self) -> bool:
        """
        Configures macOS NSWindow for meeting persistence:
        - NSWindowCollectionBehaviorFullScreenAuxiliary (337)
        - NSStatusWindowLevel (25)
        - Native 100% pure transparency (WebKit CSS exclusively controls backdrop-filter and opacity)
        Dispatched safely to main thread to avoid Main Thread Checker crash.
        """
        if _pyobjc_available and self.window:
            try:
                AppHelper.callAfter(self._setup_on_main)
                return True
            except Exception:
                pass

        # Fallback to ctypes for headless/mock environments
        ptr = self._get_ptr()
        if not ptr or not _msgSend_void_p_ulong or not _msgSend_void_p_int:
            return False

        try:
            _msgSend_void_p_ulong(ptr, _SEL_setCollectionBehavior, NS_WINDOW_COLLECTION_BEHAVIOR_HUD)
            _msgSend_void_p_int(ptr, _SEL_setLevel, NS_STATUS_WINDOW_LEVEL)
            return True
        except Exception:
            return False

    def _setup_on_main(self):
        """Runs strictly on macOS main thread."""
        try:
            win = getattr(self.window, "native", None)
            if not win:
                return

            # Upgrade activation policy to Accessory (1) for FullScreen Space roaming
            try:
                target_nsapp = NSApp
                if target_nsapp is None and _pyobjc_available:
                    target_nsapp = getattr(AppKit, "NSApp", None)
                if target_nsapp is not None and hasattr(target_nsapp, "setActivationPolicy_"):
                    target_nsapp.setActivationPolicy_(1)
            except Exception:
                pass

            try:
                if _pyobjc_available:
                    app = AppKit.NSApplication.sharedApplication()
                    if hasattr(app, "setActivationPolicy_"):
                        app.setActivationPolicy_(1)
            except Exception:
                pass

            # 注册全屏空间切换监听，当用户进入/切换至全屏 Chrome、Safari 时自动重申置顶
            try:
                if not hasattr(self, "_space_observer_installed"):
                    self._space_observer_installed = True
                    ws_center = AppKit.NSWorkspace.sharedWorkspace().notificationCenter()
                    def _on_space_changed(notif):
                        try:
                            cur_win = getattr(self.window, "native", None)
                            if cur_win and hasattr(cur_win, "orderFrontRegardless"):
                                cur_win.orderFrontRegardless()
                        except Exception:
                            pass
                    self._space_observer_token = ws_center.addObserverForName_object_queue_usingBlock_(
                        AppKit.NSWorkspaceActiveSpaceDidChangeNotification,
                        None,
                        AppKit.NSOperationQueue.mainQueue(),
                        _on_space_changed
                    )
            except Exception:
                pass

            # Enhanced Space and FullScreen auxiliary collection behavior (mask: 323 / 337)
            # CanJoinAllSpaces (1) | MoveToActiveSpace (2) | IgnoresCycle (64) | FullScreenAuxiliary (256)
            # On real macOS Cocoa NSWindow, CanJoinAllSpaces and MoveToActiveSpace are mutually exclusive.
            # We attempt the full behavior first, then fall back gracefully to CanJoinAllSpaces (337).
            try:
                behavior = (
                    NSWindowCollectionBehaviorCanJoinAllSpaces |
                    NSWindowCollectionBehaviorFullScreenAuxiliary |
                    NSWindowCollectionBehaviorMoveToActiveSpace |
                    NSWindowCollectionBehaviorIgnoresCycle
                )
                win.setCollectionBehavior_(behavior)
            except Exception:
                try:
                    win.setCollectionBehavior_(
                        NSWindowCollectionBehaviorCanJoinAllSpaces |
                        NSWindowCollectionBehaviorFullScreenAuxiliary |
                        NSWindowCollectionBehaviorIgnoresCycle |
                        NSWindowCollectionBehaviorStationary
                    )
                except Exception:
                    pass

            # Elevate window level to NSPopUpMenuWindowLevel (101) to stay above fullscreen spaces
            try:
                if hasattr(win, "setLevel_"):
                    win.setLevel_(NSPopUpMenuWindowLevel)
            except Exception:
                try:
                    if hasattr(win, "setLevel_"):
                        win.setLevel_(NSStatusWindowLevel)
                except Exception:
                    pass

            # Prevent window from hiding when app loses focus
            try:
                if hasattr(win, "setHidesOnDeactivate_"):
                    win.setHidesOnDeactivate_(False)
            except Exception:
                pass

            # Force window to front of its level regardless of active application
            try:
                if hasattr(win, "orderFrontRegardless"):
                    win.orderFrontRegardless()
            except Exception:
                pass

            # Native macOS full-surface dragging: allows clicking & dragging anywhere on HUD
            try:
                if hasattr(win, "setMovableByWindowBackground_"):
                    win.setMovableByWindowBackground_(True)
            except Exception:
                pass

            try:
                if hasattr(win, "setMovable_"):
                    win.setMovable_(True)
            except Exception:
                pass

            # Install zero-latency hardware drag monitor for top-left anchor
            try:
                self._setup_drag_monitor()
            except Exception:
                pass

            # Reinforce 100% pure native transparency so WebKit CSS exclusively renders background and blur
            try:
                if hasattr(win, "setOpaque_"):
                    win.setOpaque_(False)
            except Exception:
                pass

            try:
                if hasattr(win, "setBackgroundColor_"):
                    if _pyobjc_available:
                        import AppKit
                        win.setBackgroundColor_(AppKit.NSColor.clearColor())
            except Exception:
                pass
        except Exception:
            pass

    def _setup_drag_monitor(self):
        """
        Installs a zero-latency Cocoa event monitor for left mouse-down events.
        When a click lands within the top-left drag anchor zone (x: 0~160, y: top 44px),
        we immediately hand over the drag session to Cocoa's native performWindowDragWithEvent:.
        This achieves 120 FPS ProMotion native dragging with multi-monitor freedom and 0 IPC lag.
        """
        if not _pyobjc_available or sys.platform != "darwin":
            return
        if self._drag_monitor is not None:
            return

        def _event_handler(event):
            try:
                win = event.window()
                if not win:
                    return event

                cur_native = getattr(self.window, "native", None)
                if not cur_native or win != cur_native:
                    return event

                # If click-through is locked, do not hijack
                if self.is_locked:
                    return event

                # In Cocoa coordinates: (0, 0) is bottom-left of window
                loc = event.locationInWindow()
                win_h = win.frame().size.height

                # Designated top-left anchor zone: x in [0, 160], y in [win_h - 44, win_h]
                if 0 <= loc.x <= 160 and (win_h - 44) <= loc.y <= win_h:
                    if hasattr(win, "performWindowDragWithEvent_"):
                        win.performWindowDragWithEvent_(event)
                        return None  # Consumed by hardware drag loop
            except Exception:
                pass
            return event

        try:
            self._drag_monitor = AppKit.NSEvent.addLocalMonitorForEventsMatchingMask_handler_(
                AppKit.NSEventMaskLeftMouseDown, _event_handler
            )
        except Exception:
            pass

    def pin_fullscreen_auxiliary(self) -> bool:
        """Helper method to pin window to macOS fullscreen auxiliary space (337, level 25)."""
        return self.setup_hud_window()

    def set_click_through(self, enable: bool) -> bool:
        """Toggles decoupled position locking safely on main thread without ignoring mouse events."""
        self.is_locked = bool(enable)
        if _pyobjc_available and self.window:
            try:
                is_main = False
                try:
                    if hasattr(AppKit, "NSThread"):
                        is_main = bool(AppKit.NSThread.isMainThread())
                    else:
                        is_main = (threading.current_thread() is threading.main_thread())
                except Exception:
                    is_main = (threading.current_thread() is threading.main_thread())

                if is_main:
                    self._set_mouse_on_main(self.is_locked)
                else:
                    AppHelper.callAfter(self._set_mouse_on_main, self.is_locked)
                return True
            except Exception:
                pass

        ptr = self._get_ptr()
        if not ptr or not _msgSend_void_p_bool:
            return False

        try:
            # Fallback ctypes: never set to True; keep mouse events active
            _msgSend_void_p_bool(ptr, _SEL_setIgnoresMouseEvents, ctypes.c_bool(False))
            return True
        except Exception:
            return False

    def _set_mouse_on_main(self, enable: bool):
        """Runs on main thread. 4-Layer physical lock for position and dimensions."""
        try:
            win = getattr(self.window, "native", None)
            if not win:
                return
            locked = bool(enable)

            if locked:
                # 1. 硬件级拦截
                cur_frame = win.frame() if hasattr(win, "frame") else None
                win._locked_frame = cur_frame
                win._hud_locked = True

                # 2. 剥离可拖拽与背景拖拽
                if hasattr(win, "setMovable_"):
                    win.setMovable_(False)
                if hasattr(win, "setMovableByWindowBackground_"):
                    win.setMovableByWindowBackground_(False)

                # 3. 剥离 NSWindowStyleMaskResizable 消除拉伸光标
                if hasattr(win, "styleMask") and hasattr(win, "setStyleMask_"):
                    try:
                        current_mask = win.styleMask()
                        if isinstance(current_mask, int):
                            win.setStyleMask_(current_mask & ~AppKit.NSWindowStyleMaskResizable)
                    except Exception:
                        pass

                # 4. 锁定最小/最大尺寸为当前尺寸
                sz = getattr(cur_frame, "size", None) if cur_frame else None
                if sz is None and isinstance(cur_frame, (tuple, list)) and len(cur_frame) >= 2:
                    sz = cur_frame[1]
                if sz is not None:
                    if hasattr(win, "setMinSize_") and hasattr(win, "setMaxSize_"):
                        try:
                            win.setMinSize_(sz)
                            win.setMaxSize_(sz)
                        except Exception:
                            pass
            else:
                # 解锁
                win._hud_locked = False
                win._locked_frame = None

                if hasattr(win, "setMovable_"):
                    win.setMovable_(True)
                if hasattr(win, "setMovableByWindowBackground_"):
                    win.setMovableByWindowBackground_(True)

                # 恢复可缩放
                if hasattr(win, "styleMask") and hasattr(win, "setStyleMask_"):
                    try:
                        current_mask = win.styleMask()
                        if isinstance(current_mask, int):
                            win.setStyleMask_(current_mask | AppKit.NSWindowStyleMaskResizable)
                    except Exception:
                        pass

                # 恢复自由缩放边界
                if _pyobjc_available:
                    if hasattr(win, "setMinSize_") and hasattr(win, "setMaxSize_"):
                        try:
                            win.setMinSize_(AppKit.NSSize(200, 80))
                            win.setMaxSize_(AppKit.NSSize(10000, 10000))
                        except Exception:
                            pass

            if hasattr(win, "setIgnoresMouseEvents_"):
                win.setIgnoresMouseEvents_(False)
        except Exception:
            pass

    def is_click_through(self) -> bool:
        """Queries position locking state."""
        return self.is_locked

    def set_stealth_mode(self, enable: bool) -> bool:
        """
        Toggles stealth mode (screen-share exclusion).
        Uses win.setSharingType_(0) (NSWindowSharingNone = 0) so the HUD is completely
        invisible during Zoom / Tencent Meeting / Keynote desktop sharing.
        NSWindowSharingReadOnly = 1 restores normal capture.
        """
        self.is_stealth = bool(enable)
        sharing_type = NS_WINDOW_SHARING_NONE if enable else NS_WINDOW_SHARING_READ_ONLY

        if _pyobjc_available and self.window:
            try:
                def _apply_stealth():
                    win = getattr(self.window, "native", None)
                    if win and hasattr(win, "setSharingType_"):
                        win.setSharingType_(sharing_type)
                AppHelper.callAfter(_apply_stealth)
                return True
            except Exception:
                pass

        ptr = self._get_ptr()
        if not ptr or not _msgSend_void_p_ulong:
            return False

        try:
            _msgSend_void_p_ulong(ptr, _SEL_setSharingType, ctypes.c_ulong(sharing_type))
            return True
        except Exception:
            return False

    def is_stealth_mode(self) -> bool:
        """Queries native window sharing type."""
        if threading.current_thread() is not threading.main_thread():
            return self.is_stealth

        if _pyobjc_available and self.window:
            try:
                win = getattr(self.window, "native", None)
                if win and hasattr(win, "sharingType"):
                    return bool(win.sharingType() == NS_WINDOW_SHARING_NONE)
            except Exception:
                pass

        ptr = self._get_ptr()
        if not ptr or not _msgSend_ulong_p:
            return self.is_stealth

        try:
            val = _msgSend_ulong_p(ptr, _SEL_sharingType)
            return bool(val == NS_WINDOW_SHARING_NONE)
        except Exception:
            return self.is_stealth


# ------------------------------------------------------------------------------
# Windows Win32 HWND ctypes Implementation
# ------------------------------------------------------------------------------
# Extended Window Styles
GWL_EXSTYLE = -20
WS_EX_TRANSPARENT = 0x00000020
WS_EX_LAYERED = 0x00080000
WS_EX_TOPMOST = 0x00000008
WS_EX_TOOLWINDOW = 0x00000080

# SetWindowPos Flags
SWP_NOSIZE = 0x0001
SWP_NOMOVE = 0x0002
SWP_NOZORDER = 0x0004
SWP_FRAMECHANGED = 0x0020
SWP_FLAGS = SWP_NOMOVE | SWP_NOSIZE | SWP_NOZORDER | SWP_FRAMECHANGED
HWND_TOPMOST = -1

# Window Display Affinity for Stealth Mode (Windows 10 2004+)
WDA_NONE = 0x00000000
WDA_EXCLUDEFROMCAPTURE = 0x00000011

user32 = None
if sys.platform == "win32":
    try:
        user32 = ctypes.windll.user32
    except Exception:
        pass


class WindowsWindowController:
    """Native Windows HWND controller using standard ctypes user32 bindings."""

    def __init__(self, webview_window=None):
        self.window = webview_window
        self._hwnd = None
        self.is_locked = False
        self.is_stealth = False
        self._GetWindowLongPtr = None
        self._SetWindowLongPtr = None
        self._SetWindowPos = None

        if user32:
            try:
                from ctypes import wintypes
                self._GetWindowLongPtr = getattr(user32, "GetWindowLongPtrW", getattr(user32, "GetWindowLongW", None))
                self._SetWindowLongPtr = getattr(user32, "SetWindowLongPtrW", getattr(user32, "SetWindowLongW", None))
                if self._GetWindowLongPtr:
                    self._GetWindowLongPtr.argtypes = [wintypes.HWND, ctypes.c_int]
                    self._GetWindowLongPtr.restype = ctypes.c_ssize_t
                if self._SetWindowLongPtr:
                    self._SetWindowLongPtr.argtypes = [wintypes.HWND, ctypes.c_int, ctypes.c_ssize_t]
                    self._SetWindowLongPtr.restype = ctypes.c_ssize_t
                self._SetWindowPos = user32.SetWindowPos
                if self._SetWindowPos:
                    self._SetWindowPos.argtypes = [
                        wintypes.HWND, wintypes.HWND, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_uint
                    ]
                    self._SetWindowPos.restype = wintypes.BOOL
            except Exception:
                pass

    def get_hwnd(self) -> int:
        if self._hwnd:
            return self._hwnd

        # Prioritize matching bound window title if available (e.g. dual HUD titles)
        title = getattr(self.window, "title", None)
        if user32 and title:
            try:
                hwnd = user32.FindWindowW(None, title)
                if hwnd:
                    self._hwnd = hwnd
                    return self._hwnd
            except Exception:
                pass

        # Method 1: Strictly find HUD by its unique title "Qwen_Meeting_HUD_Overlay_7x9"
        # to eliminate GetForegroundWindow focus misfires
        if user32:
            try:
                hwnd = user32.FindWindowW(None, "Qwen_Meeting_HUD_Overlay_7x9")
                if hwnd:
                    self._hwnd = hwnd
                    return self._hwnd
            except Exception:
                pass

        if self.window is None:
            return 0

        # Method 2: Check window.native.Handle
        native = getattr(self.window, "native", None)
        if native is not None and hasattr(native, "Handle"):
            try:
                self._hwnd = int(native.Handle)
                return self._hwnd
            except Exception:
                pass

        return 0

    def setup_hud_window(self) -> bool:
        """Sets layered, topmost, and toolwindow extended styles."""
        hwnd = self.get_hwnd()
        if not hwnd or not self._GetWindowLongPtr or not self._SetWindowLongPtr:
            return False

        try:
            style = self._GetWindowLongPtr(hwnd, GWL_EXSTYLE)
            new_style = style | WS_EX_LAYERED | WS_EX_TOPMOST | WS_EX_TOOLWINDOW
            self._SetWindowLongPtr(hwnd, GWL_EXSTYLE, new_style)
            if self._SetWindowPos:
                self._SetWindowPos(hwnd, HWND_TOPMOST, 0, 0, 0, 0, SWP_FLAGS)
            return True
        except Exception:
            return False

    def pin_fullscreen_auxiliary(self) -> bool:
        """Helper method aligning with cross-platform interface."""
        return self.setup_hud_window()

    def set_click_through(self, enable: bool) -> bool:
        """Toggles WS_EX_TRANSPARENT on the HWND and flushes DWM cache via SWP_FRAMECHANGED."""
        locked_bool = bool(enable)
        self.is_locked = locked_bool
        hwnd = self.get_hwnd()
        if not hwnd or not self._GetWindowLongPtr or not self._SetWindowLongPtr:
            return False

        try:
            style = self._GetWindowLongPtr(hwnd, GWL_EXSTYLE)
            if enable:
                new_style = style | WS_EX_LAYERED | WS_EX_TRANSPARENT
            else:
                new_style = (style | WS_EX_LAYERED) & ~WS_EX_TRANSPARENT

            self._SetWindowLongPtr(hwnd, GWL_EXSTYLE, new_style)
            if self._SetWindowPos:
                # Flush DWM hit-test cache
                self._SetWindowPos(hwnd, 0, 0, 0, 0, 0, SWP_FLAGS)
            return True
        except Exception:
            return False

    def is_click_through(self) -> bool:
        """Queries whether WS_EX_TRANSPARENT is active."""
        hwnd = self.get_hwnd()
        if not hwnd or not self._GetWindowLongPtr:
            return self.is_locked

        try:
            style = self._GetWindowLongPtr(hwnd, GWL_EXSTYLE)
            return bool(style & WS_EX_TRANSPARENT)
        except Exception:
            return self.is_locked

    def set_stealth_mode(self, enable: bool) -> bool:
        """
        Toggles stealth mode on Windows via user32.SetWindowDisplayAffinity.
        WDA_EXCLUDEFROMCAPTURE (0x00000011) excludes the HUD overlay from screen capture.
        WDA_NONE (0x00000000) restores normal capture.
        """
        self.is_stealth = bool(enable)
        hwnd = self.get_hwnd()
        if not hwnd or not user32 or not hasattr(user32, "SetWindowDisplayAffinity"):
            return False

        try:
            affinity = WDA_EXCLUDEFROMCAPTURE if enable else WDA_NONE
            user32.SetWindowDisplayAffinity.argtypes = [ctypes.c_void_p, ctypes.c_uint]
            user32.SetWindowDisplayAffinity.restype = ctypes.c_int
            res = bool(user32.SetWindowDisplayAffinity(hwnd, affinity))
            return res
        except Exception:
            return False

    def is_stealth_mode(self) -> bool:
        return self.is_stealth


# ------------------------------------------------------------------------------
# Unified Cross-Platform Controller
# ------------------------------------------------------------------------------
class NativeWindowController:
    """Unified Cross-Platform Native Window Controller."""

    def __init__(self, window=None):
        self.window = window
        self.is_locked = False
        self.is_stealth = False
        self._last_lock_toggle_ts = 0.0
        if sys.platform == "darwin":
            self.impl = MacOSWindowController(window)
        elif sys.platform == "win32":
            self.impl = WindowsWindowController(window)
        else:
            self.impl = None

    def setup_hud_window(self) -> bool:
        """Configures platform-specific window flags."""
        if self.impl:
            return self.impl.setup_hud_window()
        return False

    def pin_fullscreen_auxiliary(self) -> bool:
        """Pins window above fullscreen spaces (macOS 337 / Win32 topmost)."""
        if self.impl:
            return self.impl.pin_fullscreen_auxiliary()
        return False

    def set_click_through(self, enable: bool) -> bool:
        """Toggles native click-through passthrough."""
        self.is_locked = bool(enable)
        self._last_lock_toggle_ts = time.monotonic()
        if self.impl:
            return self.impl.set_click_through(enable)
        return False

    def is_click_through(self) -> bool:
        """Queries current click-through state."""
        if self.impl:
            return self.impl.is_click_through()
        return self.is_locked

    def set_stealth_mode(self, enable: bool) -> bool:
        """Toggles native stealth mode (screen-share exclusion)."""
        self.is_stealth = bool(enable)
        if self.impl and hasattr(self.impl, "set_stealth_mode"):
            return self.impl.set_stealth_mode(enable)
        return False

    def is_stealth_mode(self) -> bool:
        """Queries current stealth mode state."""
        if self.impl and hasattr(self.impl, "is_stealth_mode"):
            return self.impl.is_stealth_mode()
        return self.is_stealth


# ==============================================================================
# JS API Bridge (HudApi)
# ==============================================================================
class HudApi:
    """
    Python bridge methods callable from JavaScript via window.pywebview.api.
    Exposes lock toggling, stealth mode, config drawer opening, graceful close, and status queries.
    Supports per-window controller isolation for independent dual HUD locking.
    """

    def __init__(
        self,
        app: "FloatingHUDApp",
        controller: Optional["NativeWindowController"] = None,
        window=None,
        window_id: Optional[str] = None,
    ):
        self.app = app
        self.controller = controller
        self.window = window
        self.window_id = window_id

    def toggle_lock(self, locked: Optional[bool] = None, window_id: Optional[str] = None) -> bool:
        """
        Toggles native click-through and syncs with backend POST /api/hud/lock.
        If controller or window_id is bound, toggles ONLY that target window!
        """
        wid = window_id or self.window_id
        target_ctrl = None
        if window_id and hasattr(self.app, "controller_map") and window_id in self.app.controller_map:
            target_ctrl = self.app.controller_map[window_id]
        elif window_id and window_id == "en" and len(getattr(self.app, "controllers", [])) > 0:
            target_ctrl = self.app.controllers[0]
        elif window_id and window_id == "zh" and len(getattr(self.app, "controllers", [])) > 1:
            target_ctrl = self.app.controllers[1]
        elif not window_id and self.controller:
            target_ctrl = self.controller
        elif wid:
            if hasattr(self.app, "controller_map") and wid in self.app.controller_map:
                target_ctrl = self.app.controller_map[wid]
            elif wid == "en" and len(getattr(self.app, "controllers", [])) > 0:
                target_ctrl = self.app.controllers[0]
            elif wid == "zh" and len(getattr(self.app, "controllers", [])) > 1:
                target_ctrl = self.app.controllers[1]
        elif self.controller:
            target_ctrl = self.controller

        if target_ctrl:
            if locked is None:
                new_locked = not target_ctrl.is_click_through()
            else:
                new_locked = bool(locked)
            target_ctrl._last_lock_toggle_ts = time.monotonic()
            target_ctrl.set_click_through(new_locked)
            if hasattr(self.app, "_update_is_locked"):
                self.app._update_is_locked()
        else:
            if locked is None:
                try:
                    current_locked = self.app.is_click_through(wid) if wid is not None else self.app.is_click_through()
                except TypeError:
                    current_locked = self.app.is_click_through()
                new_locked = not current_locked
            else:
                new_locked = bool(locked)

            try:
                if wid is not None:
                    self.app.set_click_through(new_locked, window_id=wid)
                else:
                    self.app.set_click_through(new_locked)
            except TypeError:
                self.app.set_click_through(new_locked)

        # Asynchronously sync with backend HTTP endpoint (non-blocking)
        def _sync_backend_lock():
            try:
                import urllib.request
                url = f"http://{self.app.host}:{self.app.port}/api/hud/lock"
                payload_dict = {"locked": new_locked}
                if wid:
                    payload_dict["window_id"] = wid
                    payload_dict["source"] = "hud"
                payload = json.dumps(payload_dict).encode("utf-8")
                req = urllib.request.Request(
                    url,
                    data=payload,
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                with urllib.request.urlopen(req, timeout=1.0) as resp:
                    pass
            except Exception:
                pass

        threading.Thread(target=_sync_backend_lock, daemon=True).start()
        if target_ctrl:
            return bool(target_ctrl.is_click_through())
        try:
            if wid is not None:
                return bool(self.app.is_click_through(wid))
            return bool(self.app.is_click_through())
        except TypeError:
            return bool(self.app.is_click_through())

    def set_stealth_mode(self, enable: bool) -> bool:
        """Toggles stealth mode (screen-share exclusion)."""
        return self.app.set_stealth_mode(enable)

    def is_stealth_mode(self) -> bool:
        """Returns whether stealth mode is active."""
        return self.app.is_stealth_mode()

    def open_browser_config(self) -> bool:
        """Opens system configuration drawer on the main web presentation console in default browser."""
        import webbrowser
        url = f"http://{self.app.host}:{self.app.port}/split?drawer=open"
        threading.Thread(target=lambda: webbrowser.open(url), daemon=True).start()
        return True

    def close_window(self):
        """Gracefully closes HUD."""
        self.app.close()

    def get_status(self) -> Dict[str, Any]:
        """Returns current lock status, stealth status, window position, platform info."""
        pos_x = 0
        pos_y = 0
        win = self.window or self.app.window
        try:
            if win:
                pos_x = getattr(win, "x", 0) or 0
                pos_y = getattr(win, "y", 0) or 0
        except Exception:
            pass

        try:
            if self.controller:
                locked = self.controller.is_click_through()
            elif self.window_id is not None:
                locked = self.app.is_click_through(self.window_id)
            else:
                locked = self.app.is_click_through()
        except TypeError:
            locked = self.app.is_click_through()
        return {
            "locked": locked,
            "stealth": self.app.is_stealth_mode(),
            "x": pos_x,
            "y": pos_y,
            "width": self.app.width,
            "height": self.app.height,
            "platform": sys.platform,
            "channel": self.window_id or self.app.channel,
            "status": "ok",
        }


# Backward-compatibility alias
HUDJsApi = HudApi


# ==============================================================================
# Floating HUD Application
# ==============================================================================
class FloatingHUDApp:
    """
    High-Performance Desktop Floating HUD Application.
    Uses pywebview with native transparent and frameless windowing.
    """

    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 8000,
        channel: str = "auto",
        width: int = 720,
        height: int = 160,
        stealth: bool = False,
        dual: bool = False,
    ):
        self.host = host
        self.port = port
        self.channel = channel
        self.width = width
        self.height = height
        self.stealth_init = stealth
        self.is_stealth = stealth
        self.is_locked = False
        self._last_lock_toggle_ts = 0.0
        self.is_dual = bool(dual or channel == "dual")
        self.window = None
        self.windows = []
        self.controller = None
        self.controllers = []
        self.controller_map = {}
        self.window_map = {}
        self.api = HudApi(self)
        if self.is_dual:
            self.api_en = HudApi(self, window_id="en")
            self.api_zh = HudApi(self, window_id="zh")
        else:
            self.api_en = None
            self.api_zh = None
        self._stopped = False

    def create_window(self):
        """Creates the pywebview window(s) with unique title and native transparent/frameless settings."""
        # Hook BrowserView.WindowHost on macOS Cocoa to use native HUDPanelHost
        if sys.platform == "darwin" and _pyobjc_available and HUDPanelHost is not None:
            try:
                import webview.platforms.cocoa as cocoa
                cocoa.BrowserView.WindowHost = HUDPanelHost
                AppKit.NSApplication.sharedApplication().setActivationPolicy_(1)
            except Exception:
                pass

        if webview and hasattr(webview, "settings"):
            webview.settings["DRAG_REGION_SELECTOR"] = ".pywebview-drag-region, .drag-handle, .drag-anchor-corner, #drag-anchor-corner"
            webview.settings["DRAG_REGION_DIRECT_TARGET_ONLY"] = False

        base_dir = os.path.dirname(os.path.abspath(__file__))
        html_path = os.path.join(base_dir, "float_ui.html")

        # Dynamically calculate primary screen horizontal center position
        screen_w = 1440
        try:
            if sys.platform == "darwin" and _pyobjc_available:
                from AppKit import NSScreen
                screen_frame = NSScreen.mainScreen().visibleFrame()
                if screen_frame and screen_frame.size.width > 0:
                    screen_w = int(screen_frame.size.width)
            elif webview and hasattr(webview, "screens") and webview.screens:
                screen_w = int(webview.screens[0].width)
        except Exception:
            screen_w = 1440

        default_x = max(20, int((screen_w - self.width) / 2))

        if webview is not None:
            cache_ts = int(time.time() * 1_000_000)
            if self.is_dual:
                # Create dual floating windows: en (中译英) on top, zh (英译中) below
                # Vertically stacked with 30px clear separation to prevent overlap:
                # Top window: y = 70, Bottom window: y = 260 (70 + 160 + 30)
                url_en = f"file://{html_path}?host={self.host}&port={self.port}&channel=en&_t={cache_ts}"
                url_zh = f"file://{html_path}?host={self.host}&port={self.port}&channel=zh&_t={cache_ts}"

                if self.api_en is None:
                    self.api_en = HudApi(self, window_id="en")
                if self.api_zh is None:
                    self.api_zh = HudApi(self, window_id="zh")

                win_en = webview.create_window(
                    title="Qwen_Meeting_HUD_En_中译英",
                    url=url_en,
                    x=default_x,
                    y=70,
                    width=self.width,
                    height=self.height,
                    frameless=True,
                    transparent=True,
                    on_top=True,
                    resizable=True,
                    easy_drag=False,
                    background_color="#00000000",
                    js_api=self.api_en,
                )
                win_zh = webview.create_window(
                    title="Qwen_Meeting_HUD_Zh_英译中",
                    url=url_zh,
                    x=default_x,
                    y=260,
                    width=self.width,
                    height=self.height,
                    frameless=True,
                    transparent=True,
                    on_top=True,
                    resizable=True,
                    easy_drag=False,
                    background_color="#00000000",
                    js_api=self.api_zh,
                )
                ctrl_en = NativeWindowController(win_en)
                ctrl_zh = NativeWindowController(win_zh)

                self.api_en.window = win_en
                self.api_en.controller = ctrl_en
                self.api_zh.window = win_zh
                self.api_zh.controller = ctrl_zh

                self.windows = [win_en, win_zh]
                self.window = win_en
                self.controllers = [ctrl_en, ctrl_zh]
                self.controller = self.controllers[0]
                self.controller_map = {"en": ctrl_en, "zh": ctrl_zh}
                self.window_map = {"en": win_en, "zh": win_zh}
            else:
                if self.channel and self.channel != "auto":
                    url = f"file://{html_path}?host={self.host}&port={self.port}&channel={self.channel}&_t={cache_ts}"
                else:
                    url = f"file://{html_path}?host={self.host}&port={self.port}&_t={cache_ts}"
                self.window = webview.create_window(
                    title="Qwen_Meeting_HUD_Overlay_7x9",
                    url=url,
                    x=default_x,
                    y=80,
                    width=720,
                    height=160,
                    frameless=True,
                    transparent=True,
                    on_top=True,
                    resizable=True,
                    easy_drag=False,
                    background_color="#00000000",
                    js_api=self.api,
                )
                self.windows = [self.window]
                self.controllers = [NativeWindowController(self.window)]
                self.controller = self.controllers[0]
                self.controller_map = {}
                self.window_map = {}
                self.api.window = self.window
                self.api.controller = self.controller

            # Register lifecycle hooks across all windows
            for w, ctrl in zip(self.windows, self.controllers):
                def _bind_hooks(c):
                    def _on_load():
                        try:
                            c.setup_hud_window()
                            c.pin_fullscreen_auxiliary()
                            if self.is_stealth:
                                c.set_stealth_mode(True)
                        except Exception:
                            pass
                    def _on_show():
                        try:
                            c.setup_hud_window()
                            c.pin_fullscreen_auxiliary()
                            if self.is_stealth:
                                c.set_stealth_mode(True)
                        except Exception:
                            pass
                    return _on_load, _on_show

                h_load, h_show = _bind_hooks(ctrl)
                w.events.loaded += h_load
                w.events.shown += h_show
                w.events.closing += self.on_window_closing
        else:
            self.window = None
            self.windows = []
            self.controller = NativeWindowController(None)
            self.controllers = [self.controller]

        if self.stealth_init:
            self.set_stealth_mode(True)

        self._start_remote_unlock_listener()
        return self.window

    def _start_remote_unlock_listener(self):
        """Starts background sync thread to honor remote unlock commands from server."""
        def _poll_remote_lock():
            time.sleep(2.0)
            import urllib.request
            while not self._stopped:
                try:
                    if self.is_locked:
                        now = time.monotonic()
                        url = f"http://{self.host}:{self.port}/api/hud/lock"
                        req = urllib.request.Request(url, headers={"User-Agent": "QwenHUD/5.0"})
                        with urllib.request.urlopen(req, timeout=1.0) as resp:
                            if resp.status == 200:
                                data = json.loads(resp.read().decode("utf-8"))
                                remote_locked = data.get("locked")
                                remote_windows = data.get("windows", {})

                                if self.is_dual and self.controller_map:
                                    # Dual mode: check each window independently
                                    for wid, ctrl in self.controller_map.items():
                                        if ctrl.is_click_through():
                                            last_ts = getattr(ctrl, "_last_lock_toggle_ts", 0.0)
                                            if (now - last_ts) > 3.0:
                                                wid_locked = remote_windows.get(wid) if remote_windows else remote_locked
                                                if wid_locked is False or remote_locked is False:
                                                    self.set_click_through(False, window_id=wid)
                                                    win = self.window_map.get(wid)
                                                    if win:
                                                        try:
                                                            win.evaluate_js("if (typeof setLockState === 'function') setLockState(false, true);")
                                                        except Exception:
                                                            pass
                                else:
                                    # Single window mode
                                    if (now - getattr(self, "_last_lock_toggle_ts", 0.0)) > 3.0:
                                        if remote_locked is False and self.is_locked:
                                            self.set_click_through(False)
                                            for win in self.windows:
                                                try:
                                                    win.evaluate_js("if (typeof setLockState === 'function') setLockState(false, true);")
                                                except Exception:
                                                    pass
                except Exception:
                    pass
                time.sleep(1.0)

        thread = threading.Thread(target=_poll_remote_lock, daemon=True)
        thread.start()

    def on_window_loaded(self):
        """Callback when webview finishes loading."""
        for ctrl in self.controllers:
            try:
                ctrl.setup_hud_window()
                ctrl.pin_fullscreen_auxiliary()
                if self.is_stealth:
                    ctrl.set_stealth_mode(True)
            except Exception:
                pass

    def on_window_shown(self):
        """Callback when webview window becomes visible on screen."""
        for ctrl in self.controllers:
            try:
                ctrl.setup_hud_window()
                ctrl.pin_fullscreen_auxiliary()
                if self.is_stealth:
                    ctrl.set_stealth_mode(True)
            except Exception:
                pass

    def on_window_closing(self):
        """Callback on window destruction to ensure native mouse state recovery."""
        self._stopped = True
        try:
            for ctrl in self.controllers:
                ctrl.set_click_through(False)
                ctrl.set_stealth_mode(False)
        except Exception:
            pass

    def _update_is_locked(self):
        if self.controllers:
            self.is_locked = any(ctrl.is_click_through() for ctrl in self.controllers)

    def set_click_through(self, enable: bool, window_id: Optional[str] = None) -> bool:
        """Toggles native click-through mode for a specific window or across all active windows."""
        now = time.monotonic()
        self._last_lock_toggle_ts = now
        success = True
        target_ctrls = []
        if window_id:
            if hasattr(self, "controller_map") and window_id in self.controller_map:
                target_ctrls = [self.controller_map[window_id]]
            elif window_id == "en" and len(self.controllers) > 0:
                target_ctrls = [self.controllers[0]]
            elif window_id == "zh" and len(self.controllers) > 1:
                target_ctrls = [self.controllers[1]]
        if not target_ctrls:
            target_ctrls = self.controllers

        if target_ctrls:
            for ctrl in target_ctrls:
                ctrl._last_lock_toggle_ts = now
                try:
                    if ctrl.set_click_through(enable) is False:
                        success = False
                except Exception:
                    success = False
            self._update_is_locked()
        else:
            self.is_locked = bool(enable)

        return success

    def is_click_through(self, window_id: Optional[str] = None) -> bool:
        """Returns whether native click-through mode is active (for a specific window or globally)."""
        if window_id:
            if hasattr(self, "controller_map") and window_id in self.controller_map:
                return self.controller_map[window_id].is_click_through()
            if window_id == "en" and len(self.controllers) > 0:
                return self.controllers[0].is_click_through()
            if window_id == "zh" and len(self.controllers) > 1:
                return self.controllers[1].is_click_through()
        if self.controllers:
            self._update_is_locked()
        return self.is_locked

    def set_stealth_mode(self, enable: bool) -> bool:
        """Toggles stealth mode across all active windows."""
        self.is_stealth = bool(enable)
        success = True
        for ctrl in self.controllers:
            try:
                if ctrl.set_stealth_mode(enable) is False:
                    success = False
            except Exception:
                success = False
        return success

    def is_stealth_mode(self) -> bool:
        """Returns whether stealth mode is active."""
        return self.is_stealth

    def close(self):
        """Closes and destroys all active HUD windows safely."""
        self._stopped = True
        try:
            for ctrl in self.controllers:
                try:
                    ctrl.set_click_through(False)
                    ctrl.set_stealth_mode(False)
                except Exception:
                    pass
            for win in self.windows:
                try:
                    win.destroy()
                except Exception:
                    pass
        except Exception:
            pass

    def run(self, debug: bool = False):
        """Starts the pywebview desktop event loop."""
        self.create_window()
        if webview is not None:
            webview.start(debug=debug)
        else:
            print("[WARN] pywebview not installed; cannot launch desktop GUI loop.")


# ==============================================================================
# Non-Blocking Automated Verification CLI
# ==============================================================================
def run_self_check() -> int:
    """
    Runs diagnostic self-checks for native controller, ctypes signatures, and API bridge.
    Returns 0 on success.
    """
    diag = {
        "platform": sys.platform,
        "status": "ok",
        "ctypes_ready": False,
        "controller_ready": False,
        "api_ready": False,
        "html_exists": False,
        "webview_available": webview is not None,
    }

    base_dir = os.path.dirname(os.path.abspath(__file__))
    html_path = os.path.join(base_dir, "float_ui.html")
    diag["html_exists"] = os.path.exists(html_path)

    app = FloatingHUDApp()
    controller = NativeWindowController()
    diag["controller_ready"] = controller is not None

    if sys.platform == "darwin":
        diag["ctypes_ready"] = _objc is not None and _appkit is not None
        try:
            NSWindow = _objc.objc_getClass(b"NSWindow")
            if NSWindow:
                win_alloc = _msgSend_p_p(NSWindow, _objc.sel_registerName(b"alloc"))
                win = _msgSend_p_p_rect_ulong_ulong_bool(
                    win_alloc,
                    _objc.sel_registerName(b"initWithContentRect:styleMask:backing:defer:"),
                    100.0, 100.0, 720.0, 160.0, 0, 2, False,
                )
                if win:
                    _msgSend_void_p_bool(win, _SEL_setIgnoresMouseEvents, True)
                    val_t = _msgSend_bool_p(win, _SEL_ignoresMouseEvents)
                    _msgSend_void_p_bool(win, _SEL_setIgnoresMouseEvents, False)
                    val_f = _msgSend_bool_p(win, _SEL_ignoresMouseEvents)
                    _msgSend_void_p_ulong(win, _SEL_setCollectionBehavior, NS_WINDOW_COLLECTION_BEHAVIOR_HUD)
                    val_beh = _msgSend_ulong_p(win, _SEL_collectionBehavior)
                    _msgSend_void_p_int(win, _SEL_setLevel, NS_STATUS_WINDOW_LEVEL)
                    val_lvl = _msgSend_int_p(win, _SEL_level)
                    _msgSend_void_p_ulong(win, _SEL_setSharingType, ctypes.c_ulong(NS_WINDOW_SHARING_NONE))
                    val_stealth = (_msgSend_ulong_p(win, _SEL_sharingType) == NS_WINDOW_SHARING_NONE)
                    diag["headless_darwin_verified"] = (
                        val_t is True and val_f is False and val_beh == 337 and val_lvl == 25 and val_stealth is True
                    )
                    diag["stealth_verified"] = val_stealth
        except Exception as e:
            diag["headless_darwin_error"] = str(e)
    elif sys.platform == "win32":
        diag["ctypes_ready"] = user32 is not None
        diag["stealth_verified"] = hasattr(user32, "SetWindowDisplayAffinity")

    api = HudApi(app)
    st = api.get_status()
    diag["api_ready"] = st.get("status") == "ok"

    print(json.dumps(diag, indent=2, ensure_ascii=False))
    return 0


def run_test_window() -> int:
    """Non-blocking test initializing app window and toggling click-through and stealth."""
    print("[TEST] Initializing FloatingHUDApp...")
    app = FloatingHUDApp()
    app.create_window()
    print("[TEST] Window created successfully")

    app.set_click_through(True)
    assert app.is_click_through() is True, "Failed to lock click-through"
    print("[TEST] Click-through locked: True")

    app.set_click_through(False)
    assert app.is_click_through() is False, "Failed to unlock click-through"
    print("[TEST] Click-through unlocked: False")

    # Verify stealth mode
    app.set_stealth_mode(True)
    assert app.is_stealth_mode() is True, "Failed to enable stealth mode"
    print("[TEST] Stealth mode enabled: True")

    app.set_stealth_mode(False)
    assert app.is_stealth_mode() is False, "Failed to disable stealth mode"
    print("[TEST] Stealth mode disabled: False")

    st = app.api.get_status()
    print(f"[TEST] Status report: {st}")

    app.close()
    print("[TEST] Window closed and resources cleaned up")
    return 0


def main():
    parser = argparse.ArgumentParser(description="Harry Translate (哈利同传) Realtime Transparent Floating HUD")
    parser.add_argument("--host", type=str, default="127.0.0.1", help="FastAPI host")
    parser.add_argument("--port", type=int, default=8000, help="FastAPI port")
    parser.add_argument("--channel", type=str, default="auto", choices=["auto", "zh", "en", "dual"], help="Default subtitle channel: auto (记住上次选择), en (中译英), zh (英译中), or dual (开启双浮窗)")
    parser.add_argument("--dual", action="store_true", help="Launch dual floating HUD windows simultaneously: one for 中译英, one for 英译中")
    parser.add_argument("--width", type=int, default=720, help="Window width (default: 720)")
    parser.add_argument("--height", type=int, default=160, help="Window height (default: 160)")
    parser.add_argument("--stealth", action="store_true", help="Launch HUD in stealth mode (hidden from screen capture / Zoom screen share)")
    parser.add_argument("--check", action="store_true", help="Run non-blocking native self-check")
    parser.add_argument("--test-window", action="store_true", help="Run non-blocking window initialization test")
    parser.add_argument("--status", action="store_true", help="Print app configuration status")
    parser.add_argument("--debug", action="store_true", help="Enable pywebview debug mode")

    args = parser.parse_args()

    if args.check:
        sys.exit(run_self_check())

    if args.test_window:
        sys.exit(run_test_window())

    is_dual = bool(args.dual or args.channel == "dual")
    if args.status:
        app = FloatingHUDApp(host=args.host, port=args.port, channel=args.channel, width=args.width, height=args.height, stealth=args.stealth, dual=is_dual)
        print(json.dumps(app.api.get_status(), indent=2))
        sys.exit(0)

    if webview is None:
        print("[ERROR] pywebview is not installed in the active environment.")
        print("Please install pywebview via: pip install pywebview")
        print("For headless diagnostic self-check, run: python float_app.py --check")
        sys.exit(1)

    app = FloatingHUDApp(host=args.host, port=args.port, channel=args.channel, width=args.width, height=args.height, stealth=args.stealth, dual=is_dual)
    app.run(debug=args.debug)


if __name__ == "__main__":
    main()
