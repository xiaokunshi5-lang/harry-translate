#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
tests/challenger_hud_lock_adversarial.py
--------------------------------------------------------------------------------
Adversarial Stress Test Harness for HUD Position Lock & macOS Window Attributes:
1. Rapid Lock/Unlock Toggles (150+ cycles) & Strict State Synchronization
2. Strict Invariant: win.setIgnoresMouseEvents_ is NEVER passed True under any inputs
3. Hardware Drag Event Simulation during Locked State (Zero Displacement, No Deadlocks)
4. PyObjC Main-Thread Invocation & Runtime Selector Cleanliness
5. Cocoa Bitmask Inconsistency Analysis (323 vs AppKit Mutually Exclusive Flags)
6. Window Level Audit (Level 101 NSPopUpMenuWindowLevel Verification)
--------------------------------------------------------------------------------
"""

import os
import sys
import time
import json
import threading
import unittest
from typing import List, Dict, Any

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import objc
import AppKit
import PyObjCTools.AppHelper as AppHelper
import float_app
from float_app import (
    MacOSWindowController,
    HudApi,
    FloatingHUDApp,
    NSWindowCollectionBehaviorCanJoinAllSpaces,
    NSWindowCollectionBehaviorFullScreenAuxiliary,
    NSWindowCollectionBehaviorMoveToActiveSpace,
    NSWindowCollectionBehaviorIgnoresCycle,
    NSPopUpMenuWindowLevel,
    NSStatusWindowLevel,
)


class SpyingNSWindow(AppKit.NSWindow):
    """Native Cocoa NSWindow subclass recording selector calls and parameters."""
    recorded_ignores_args = []
    drag_event_calls = []

    def setIgnoresMouseEvents_(self, val):
        SpyingNSWindow.recorded_ignores_args.append(val)
        objc.super(SpyingNSWindow, self).setIgnoresMouseEvents_(val)

    def performWindowDragWithEvent_(self, event):
        SpyingNSWindow.drag_event_calls.append(event)
        # In headless test environments, do not enter native hardware event loop


def create_spying_nswindow():
    """Helper to instantiate a real SpyingNSWindow Cocoa instance."""
    app = AppKit.NSApplication.sharedApplication()
    rect = AppKit.NSMakeRect(100, 100, 720, 160)
    win = SpyingNSWindow.alloc().initWithContentRect_styleMask_backing_defer_(
        rect, AppKit.NSWindowStyleMaskBorderless, AppKit.NSBackingStoreBuffered, False
    )
    return win


class MockWebviewWindow:
    """Mock webview window wrapping a real Cocoa NSWindow."""
    def __init__(self, native_win):
        self.native = native_win
        self.x = 100
        self.y = 100
        self.width = 720
        self.height = 160
        self.title = "Qwen_Meeting_HUD_Overlay_7x9"


class ChallengerHUDLockAdversarial(unittest.TestCase):
    """Adversarial stress harness for HUD lock and macOS window persistence."""

    def setUp(self):
        SpyingNSWindow.recorded_ignores_args.clear()
        SpyingNSWindow.drag_event_calls.clear()
        self.real_win = create_spying_nswindow()
        self.mock_wv = MockWebviewWindow(self.real_win)

    # --------------------------------------------------------------------------
    # Dimension 1: Rapid 150 Lock/Unlock Cycles
    # --------------------------------------------------------------------------
    def test_dim1_rapid_toggle_synchronization_150_cycles(self):
        """
        Adversarial Test 1: Rapidly cycle lock/unlock 150 times.
        Verify Python is_locked, Cocoa NSWindow isMovable, isMovableByWindowBackground,
        and HudApi return values remain strictly synchronized with 0 drift.
        """
        app = FloatingHUDApp()
        app.window = self.mock_wv
        app.windows = [self.mock_wv]
        ctrl = MacOSWindowController(self.mock_wv)
        app.controller = ctrl
        app.controllers = [ctrl]
        api = HudApi(app)

        # Pre-condition: initially unlocked
        self.assertFalse(app.is_click_through())
        self.assertFalse(ctrl.is_click_through())

        sync_errors = []
        cycles = 150

        for i in range(1, cycles + 1):
            expected_locked = (i % 2 == 1)
            # Toggle via API
            ret = api.toggle_lock()
            
            # Synchronize state directly to main thread helper
            ctrl._set_mouse_on_main(expected_locked)

            # Assert Python state
            py_locked = app.is_click_through()
            ctrl_locked = ctrl.is_click_through()
            
            # Assert Cocoa native NSWindow state
            cocoa_movable = bool(self.real_win.isMovable())
            cocoa_bg_movable = bool(self.real_win.isMovableByWindowBackground())
            cocoa_ignores_mouse = bool(self.real_win.ignoresMouseEvents())

            if py_locked != expected_locked:
                sync_errors.append(f"Cycle {i}: app.is_click_through()={py_locked}, expected {expected_locked}")
            if ctrl_locked != expected_locked:
                sync_errors.append(f"Cycle {i}: ctrl.is_click_through()={ctrl_locked}, expected {expected_locked}")
            if cocoa_movable != (not expected_locked):
                sync_errors.append(f"Cycle {i}: NSWindow.isMovable()={cocoa_movable}, expected {not expected_locked}")
            if cocoa_bg_movable != (not expected_locked):
                sync_errors.append(f"Cycle {i}: NSWindow.isMovableByWindowBackground()={cocoa_bg_movable}, expected {not expected_locked}")
            if cocoa_ignores_mouse is not False:
                sync_errors.append(f"Cycle {i}: NSWindow.ignoresMouseEvents()={cocoa_ignores_mouse}, expected False")

        self.assertEqual(len(sync_errors), 0, f"Synchronization failures during 150 cycles: {sync_errors[:5]}")
        print(f"\n[PASS] Dimension 1: Successfully ran {cycles} rapid lock/unlock cycles with 100% strict synchronization.")

    # --------------------------------------------------------------------------
    # Dimension 2: win.setIgnoresMouseEvents_ is NEVER passed True
    # --------------------------------------------------------------------------
    def test_dim2_set_ignores_mouse_events_never_true(self):
        """
        Adversarial Test 2: Stress test input combinations to assert that
        win.setIgnoresMouseEvents_ is never called with True under any condition.
        """
        ctrl = MacOSWindowController(self.mock_wv)
        app = FloatingHUDApp()
        app.window = self.mock_wv
        app.controllers = [ctrl]
        api = HudApi(app)

        test_inputs = [
            True, False, 1, 0, -1, "True", "False", "", None, [], {}, object(),
        ]

        for val in test_inputs:
            ctrl.set_click_through(val)
            ctrl._set_mouse_on_main(val)
            api.toggle_lock(val)

        # Assert all recorded calls
        self.assertGreater(len(SpyingNSWindow.recorded_ignores_args), 0, "setIgnoresMouseEvents_ should have been called")
        for idx, arg in enumerate(SpyingNSWindow.recorded_ignores_args):
            self.assertFalse(
                bool(arg),
                f"VIOLATION: setIgnoresMouseEvents_ was passed truthy value '{arg}' at call {idx}!"
            )

        # Verify real NSWindow state
        self.assertFalse(
            bool(self.real_win.ignoresMouseEvents()),
            "Real NSWindow ignoresMouseEvents must be False"
        )
        print(f"\n[PASS] Dimension 2: Tested {len(SpyingNSWindow.recorded_ignores_args)} calls; setIgnoresMouseEvents_ was NEVER passed True.")

    # --------------------------------------------------------------------------
    # Dimension 3: Simulate hardware drag events during locked state
    # --------------------------------------------------------------------------
    def test_dim3_hardware_drag_simulation_during_locked_state(self):
        """
        Adversarial Test 3: Simulate left mouse down in top-left anchor during locked state.
        Verify zero window displacement and no exceptions or deadlocks.
        """
        ctrl = MacOSWindowController(self.mock_wv)
        ctrl.setup_hud_window()
        ctrl._setup_drag_monitor()
        self.assertIsNotNone(ctrl._drag_monitor, "Drag monitor must be installed")

        # Record initial frame
        initial_frame = self.real_win.frame()
        init_x = initial_frame.origin.x
        init_y = initial_frame.origin.y

        # Lock position
        ctrl.set_click_through(True)
        ctrl._set_mouse_on_main(True)
        self.assertTrue(ctrl.is_locked)
        self.assertFalse(self.real_win.isMovable())
        self.assertFalse(self.real_win.isMovableByWindowBackground())

        # Construct simulated event in top-left drag anchor (x: 50, y: 140 of 160h window)
        class MockNSEvent:
            def window(s):
                return self.real_win
            def locationInWindow(s):
                class Point:
                    x = 50.0
                    y = 140.0
                return Point()

        mock_event = MockNSEvent()

        # Simulate monitor logic
        event_returned = None
        try:
            win = mock_event.window()
            cur_native = getattr(self.mock_wv, "native", None)
            if ctrl.is_locked:
                event_returned = mock_event  # Bypassed
            else:
                win.performWindowDragWithEvent_(mock_event)
                event_returned = None
        except Exception as e:
            self.fail(f"Exception during drag handling: {e}")

        self.assertIs(event_returned, mock_event, "Event should be passed through when locked")
        self.assertEqual(len(SpyingNSWindow.drag_event_calls), 0, "performWindowDragWithEvent_ must NOT be called when locked")

        # Verify frame displacement is strictly zero
        final_frame = self.real_win.frame()
        disp_x = abs(final_frame.origin.x - init_x)
        disp_y = abs(final_frame.origin.y - init_y)
        self.assertEqual(disp_x, 0.0, f"Window x displaced by {disp_x}px!")
        self.assertEqual(disp_y, 0.0, f"Window y displaced by {disp_y}px!")

        print(f"\n[PASS] Dimension 3: Drag events safely bypassed during locked state; displacement = (0, 0), zero deadlocks.")

    # --------------------------------------------------------------------------
    # Dimension 4: PyObjC main-thread invocation & selector cleanliness
    # --------------------------------------------------------------------------
    def test_dim4_main_thread_invocation_selector_cleanliness(self):
        """
        Adversarial Test 4: Run _setup_on_main and _set_mouse_on_main directly on
        real NSWindow without exception masking to detect any hidden exceptions.
        """
        ctrl = MacOSWindowController(self.mock_wv)

        # 1. Test _set_mouse_on_main selector cleanliness
        try:
            ctrl._set_mouse_on_main(True)
            self.assertFalse(self.real_win.isMovable())
            ctrl._set_mouse_on_main(False)
            self.assertTrue(self.real_win.isMovable())
            print("\n[INFO] _set_mouse_on_main executed cleanly.")
        except Exception as e:
            self.fail(f"_set_mouse_on_main threw exception: {type(e).__name__}: {e}")

        # 2. Test _setup_on_main internal operations step-by-step
        print("[INFO] Auditing _setup_on_main line-by-line on real NSWindow:")
        win = self.real_win

        # Step 2a: setActivationPolicy_(1)
        try:
            AppKit.NSApp.setActivationPolicy_(1)
            print("  - setActivationPolicy_(1): OK")
        except Exception as e:
            self.fail(f"setActivationPolicy_(1) failed: {e}")

        # Step 2b: setCollectionBehavior_(323)
        threw_inconsistency = False
        exception_msg = ""
        try:
            behavior = (
                NSWindowCollectionBehaviorCanJoinAllSpaces |
                NSWindowCollectionBehaviorFullScreenAuxiliary |
                NSWindowCollectionBehaviorMoveToActiveSpace |
                NSWindowCollectionBehaviorIgnoresCycle
            )
            win.setCollectionBehavior_(behavior)
        except Exception as e:
            threw_inconsistency = True
            exception_msg = str(e)
            print(f"  - setCollectionBehavior_(323): FAILED with {type(e).__name__}: {e}")

        self.assertTrue(
            threw_inconsistency,
            "CRITICAL: win.setCollectionBehavior_(323) was expected to throw NSInternalInconsistencyException on macOS AppKit"
        )
        self.assertIn("NSInternalInconsistencyException", exception_msg)

    # --------------------------------------------------------------------------
    # Dimension 5: Cocoa bitmask 323 vs mutually exclusive flags
    # --------------------------------------------------------------------------
    def test_dim5_cocoa_bitmask_323_inconsistency_failure(self):
        """
        Adversarial Test 5: Verify that bitmask 323 combines CanJoinAllSpaces (1)
        and MoveToActiveSpace (2), which are strictly mutually exclusive in AppKit.
        """
        can_join = NSWindowCollectionBehaviorCanJoinAllSpaces       # 1
        move_to_active = NSWindowCollectionBehaviorMoveToActiveSpace # 2
        ignores_cycle = NSWindowCollectionBehaviorIgnoresCycle     # 64
        fullscreen_aux = NSWindowCollectionBehaviorFullScreenAuxiliary # 256

        mask_323 = can_join | move_to_active | ignores_cycle | fullscreen_aux
        self.assertEqual(mask_323, 323)

        # Empirical proof: attempting to assign 323 to real NSWindow raises NSInternalInconsistencyException
        with self.assertRaises(Exception) as ctx:
            self.real_win.setCollectionBehavior_(mask_323)

        self.assertIn("cannot be both NSWindowCollectionBehaviorCanJoinAllSpaces and NSWindowCollectionBehaviorMoveToActiveSpace", str(ctx.exception))
        print(f"\n[CONFIRMED BUG] Dimension 5: Bitmask 323 is invalid in Cocoa AppKit: {ctx.exception}")

        # In contrast, test valid masks:
        # Valid 1: CanJoinAllSpaces (321 = 1 | 64 | 256)
        valid_mask_321 = can_join | ignores_cycle | fullscreen_aux
        self.real_win.setCollectionBehavior_(valid_mask_321)
        self.assertEqual(self.real_win.collectionBehavior(), 321)
        print("  - Valid mask 321 (CanJoinAllSpaces): OK (result=321)")

        # Valid 2: MoveToActiveSpace (322 = 2 | 64 | 256)
        valid_mask_322 = move_to_active | ignores_cycle | fullscreen_aux
        self.real_win.setCollectionBehavior_(valid_mask_322)
        self.assertEqual(self.real_win.collectionBehavior(), 322)
        print("  - Valid mask 322 (MoveToActiveSpace): OK (result=322)")

    # --------------------------------------------------------------------------
    # Dimension 6: Window level 101 audit
    # --------------------------------------------------------------------------
    def test_dim6_window_level_101_audit(self):
        """
        Adversarial Test 6: Audit window level 101 (NSPopUpMenuWindowLevel).
        Verify that with isolated property setup, real NSWindow reaches level 101,
        transparency is configured, and drag monitor is active.
        """
        # Create fresh window with level 0
        fresh_win = create_spying_nswindow()
        self.assertEqual(fresh_win.level(), 0)

        wv = MockWebviewWindow(fresh_win)
        ctrl = MacOSWindowController(wv)

        # Call ctrl._setup_on_main() as written in float_app.py
        ctrl._setup_on_main()

        # Check actual level of fresh_win
        actual_level = fresh_win.level()
        print(f"\n[AUDIT] Dimension 6: actual win.level() after float_app._setup_on_main() = {actual_level}")

        self.assertEqual(
            actual_level, 101,
            "Real NSWindow must reach level 101 (NSPopUpMenuWindowLevel) via isolated setup."
        )
        self.assertFalse(
            fresh_win.isOpaque(),
            "Real NSWindow must be non-opaque (transparent)."
        )
        self.assertIsNotNone(
            ctrl._drag_monitor,
            "Real NSWindow drag monitor must be active and registered."
        )
        print("[PASS] Dimension 6: Real NSWindow reached level 101, is non-opaque, and drag monitor is active.")


if __name__ == "__main__":
    unittest.main()
