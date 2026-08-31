# -*- coding: utf-8 -*-
"""纯 Python 鼠标钩子（WH_MOUSE_LL）回退实现，架构参考 StarPie：
右键按下立即吞掉；普通单击由主线程重放完整点击；手势走轮盘。"""
import ctypes
import threading
import time
from ctypes import wintypes

from app.log_utils import log_mouse

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

WH_MOUSE_LL = 14
HC_ACTION = 0
WM_MOUSEMOVE = 0x0200
WM_LBUTTONDOWN = 0x0201
WM_RBUTTONDOWN = 0x0204
WM_RBUTTONUP = 0x0205
WM_QUIT = 0x0012
LLMHF_INJECTED = 0x00000001


class MSLLHOOKSTRUCT(ctypes.Structure):
    _fields_ = [
        ("pt", wintypes.POINT),
        ("mouseData", wintypes.DWORD),
        ("flags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.c_size_t),
    ]


LowLevelMouseProc = ctypes.WINFUNCTYPE(
    ctypes.c_void_p, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM
)

user32.SetWindowsHookExW.argtypes = [
    ctypes.c_int, LowLevelMouseProc, wintypes.HINSTANCE, wintypes.DWORD,
]
user32.SetWindowsHookExW.restype = ctypes.c_void_p
user32.CallNextHookEx.argtypes = [
    ctypes.c_void_p, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM,
]
user32.CallNextHookEx.restype = ctypes.c_void_p
user32.UnhookWindowsHookEx.argtypes = [ctypes.c_void_p]
user32.GetMessageW.argtypes = [
    ctypes.POINTER(wintypes.MSG), wintypes.HWND, wintypes.UINT, wintypes.UINT,
]
user32.GetMessageW.restype = ctypes.c_int
user32.PostThreadMessageW.argtypes = [
    wintypes.DWORD, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM,
]


class MouseHook:
    def __init__(self, on_wheel_trigger=None, on_wheel_release=None, on_left_click=None,
                 on_mouse_move=None, on_normal_up=None):
        self.on_wheel_trigger = on_wheel_trigger
        self.on_wheel_release = on_wheel_release
        self.on_left_click = on_left_click
        self.on_mouse_move = on_mouse_move
        self.on_normal_up = on_normal_up
        self._hook = None
        self._proc_ref = None
        self._thread = None
        self._tid = None
        self._r_down = False
        self._down_pos = None
        self._down_time = 0.0
        self._threshold2 = 14 * 14
        self.wheel_active = False
        self._ignore_down = False
        self._ignore_up = False
        self._event_count = 0
        self.suppress = False

    def set_drag_threshold(self, px):
        self._threshold2 = max(4, int(px)) ** 2

    def set_suppress(self, value):
        self.suppress = bool(value)

    def set_ignore_next_click(self):
        self._ignore_down = True
        self._ignore_up = True

    def event_count(self):
        return self._event_count

    def start(self):
        if self._thread and self._thread.is_alive():
            return
        self._thread = threading.Thread(target=self._run, name="mouse-hook", daemon=True)
        self._thread.start()

    def stop(self):
        if self._hook:
            try:
                user32.UnhookWindowsHookEx(self._hook)
            except Exception:
                pass
            self._hook = None
        if self._tid:
            try:
                user32.PostThreadMessageW(self._tid, WM_QUIT, 0, 0)
            except Exception:
                pass

    def _run(self):
        self._tid = kernel32.GetCurrentThreadId()
        self._proc_ref = LowLevelMouseProc(self._proc)
        self._hook = user32.SetWindowsHookExW(WH_MOUSE_LL, self._proc_ref, None, 0)
        if not self._hook:
            return
        msg = wintypes.MSG()
        while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) != 0:
            user32.TranslateMessage(ctypes.byref(msg))
            user32.DispatchMessageW(ctypes.byref(msg))
        try:
            user32.UnhookWindowsHookEx(self._hook)
        except Exception:
            pass
        self._hook = None

    def _proc(self, nCode, wParam, lParam):
        if nCode != HC_ACTION:
            try:
                return user32.CallNextHookEx(self._hook, nCode, wParam, lParam)
            except Exception:
                return 0
        swallow = False
        try:
            self._event_count += 1  # 心跳
            data = ctypes.cast(lParam, ctypes.POINTER(MSLLHOOKSTRUCT)).contents
            x, y = data.pt.x, data.pt.y
            if wParam == WM_RBUTTONDOWN and self._ignore_down:
                self._ignore_down = False
                return user32.CallNextHookEx(self._hook, nCode, wParam, lParam)
            if wParam == WM_RBUTTONUP and self._ignore_up:
                self._ignore_up = False
                return user32.CallNextHookEx(self._hook, nCode, wParam, lParam)
            if data.flags & LLMHF_INJECTED:
                return user32.CallNextHookEx(self._hook, nCode, wParam, lParam)
            # 看门狗
            if (self._r_down and not self.wheel_active and self._down_time
                    and time.monotonic() - self._down_time > 10):
                self._r_down = False
                self._down_pos = None
                self._down_time = 0.0
            if wParam == WM_LBUTTONDOWN:
                if self.on_left_click:
                    try:
                        self.on_left_click(x, y)
                    except Exception:
                        pass
            elif wParam == WM_RBUTTONDOWN:
                # 立即吞掉按下：目标程序永远收不到
                self._r_down = True
                self._down_pos = (x, y)
                self._down_time = time.monotonic()
                swallow = True
            elif wParam == WM_RBUTTONUP:
                if self.wheel_active:
                    self.wheel_active = False
                    self._r_down = False
                    self._down_pos = None
                    self._down_time = 0.0
                    log_mouse(f"wheel release ({x},{y})")
                    if self.on_wheel_release:
                        try:
                            self.on_wheel_release(x, y)
                        except Exception:
                            pass
                    swallow = True
                elif self._r_down:
                    self._r_down = False
                    self._down_pos = None
                    self._down_time = 0.0
                    if self.on_normal_up:
                        try:
                            self.on_normal_up(x, y)
                        except Exception:
                            pass
                    swallow = True
            elif wParam == WM_MOUSEMOVE:
                if self.wheel_active:
                    if self.on_mouse_move:
                        try:
                            self.on_mouse_move(x, y)
                        except Exception:
                            pass
                elif self._r_down and self._down_pos:
                    dx = x - self._down_pos[0]
                    dy = y - self._down_pos[1]
                    if dx * dx + dy * dy >= self._threshold2:
                        self.wheel_active = True
                        log_mouse(
                            f"wheel trigger origin=({self._down_pos[0]},{self._down_pos[1]}) "
                            f"cur=({x},{y})"
                        )
                        if self.on_wheel_trigger:
                            try:
                                self.on_wheel_trigger(
                                    x, y, self._down_pos[0], self._down_pos[1]
                                )
                            except Exception:
                                pass
        except Exception:
            pass
        if swallow:
            return 1
        try:
            return user32.CallNextHookEx(self._hook, nCode, wParam, lParam)
        except Exception:
            return 0
