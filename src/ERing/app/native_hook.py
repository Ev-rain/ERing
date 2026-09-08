# -*- coding: utf-8 -*-
"""C++ 钩子 DLL 封装（架构参考 StarPie）：
钩子吞掉右键按下；普通单击由主线程重放完整点击；手势走轮盘。
加载失败时由主程序回退到纯 Python 钩子。"""
import ctypes
from pathlib import Path

from app.log_utils import log
from app.paths import project_root, resource_path


def _find_dll():
    candidates = [
        project_root() / "native" / "wheelhook.dll",
        resource_path("native") / "wheelhook.dll",
    ]
    for c in candidates:
        if c.exists():
            return c
    return candidates[0]


DLL_PATH = _find_dll()

TriggerCb = ctypes.WINFUNCTYPE(
    None, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int
)
ReleaseCb = ctypes.WINFUNCTYPE(None, ctypes.c_int, ctypes.c_int)
NormalUpCb = ctypes.WINFUNCTYPE(None, ctypes.c_int, ctypes.c_int)
LeftClickCb = ctypes.WINFUNCTYPE(None, ctypes.c_int, ctypes.c_int)
MoveCb = ctypes.WINFUNCTYPE(None, ctypes.c_int, ctypes.c_int)
IsolatedCb = ctypes.WINFUNCTYPE(ctypes.c_int)


class NativeHook:
    def __init__(self, on_wheel_trigger=None, on_wheel_release=None, on_left_click=None,
                 on_mouse_move=None, on_normal_up=None):
        self.on_wheel_trigger = on_wheel_trigger
        self.on_wheel_release = on_wheel_release
        self.on_left_click = on_left_click
        self.on_mouse_move = on_mouse_move
        self.on_normal_up = on_normal_up
        self._dll = None
        self._cbs = []  # 保持回调引用，防止被 GC
        self._threshold = 14
        self.suppress = False
        self._isolated_check = None
        self._iso_cb = None

    @classmethod
    def available(cls):
        try:
            ctypes.CDLL(str(DLL_PATH))
            return True
        except Exception:
            return False

    def _load(self):
        if self._dll is None:
            self._dll = ctypes.CDLL(str(DLL_PATH))
            self._dll.configure.argtypes = [TriggerCb, ReleaseCb, NormalUpCb, LeftClickCb, MoveCb]
            self._dll.start_hook.argtypes = [TriggerCb, ReleaseCb, NormalUpCb, LeftClickCb, MoveCb]
            self._dll.start_hook.restype = ctypes.c_int
            self._dll.stop_hook.argtypes = []
            self._dll.set_drag_threshold.argtypes = [ctypes.c_int]
            self._dll.set_suppress.argtypes = [ctypes.c_int]
            self._dll.set_isolated.argtypes = [IsolatedCb]
            self._dll.set_ignore_next_click.argtypes = []
            self._dll.get_event_count.argtypes = []
            self._dll.get_event_count.restype = ctypes.c_long
            self._dll.debug_feed.argtypes = [
                ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
            ]
        return self._dll

    def set_drag_threshold(self, px):
        self._threshold = max(4, int(px))
        if self._dll:
            self._dll.set_drag_threshold(self._threshold)

    def set_suppress(self, value):
        self.suppress = bool(value)
        if self._dll:
            try:
                self._dll.set_suppress(1 if value else 0)
            except Exception:
                pass

    def set_ignore_next_click(self):
        if self._dll:
            try:
                self._dll.set_ignore_next_click()
            except Exception:
                pass

    def set_isolated_check(self, fn):
        """设置前台是否处于「独占/全屏且不在白名单」的判定回调（返回真则钩子放行真实点击）。"""
        self._isolated_check = fn

    def event_count(self):
        if self._dll:
            try:
                return int(self._dll.get_event_count())
            except Exception:
                pass
        return 0

    def start(self):
        dll = self._load()
        self._cbs = [
            TriggerCb(self._on_trigger),
            ReleaseCb(self._on_release),
            NormalUpCb(self._on_normal_up),
            LeftClickCb(self._on_left),
            MoveCb(self._on_move),
        ]
        self._iso_cb = IsolatedCb(self._on_isolated)
        self._cbs.append(self._iso_cb)
        dll.set_drag_threshold(self._threshold)
        dll.set_isolated(self._iso_cb)
        self.set_suppress(self.suppress)
        ok = dll.start_hook(*self._cbs)
        log(f"native hook start: {bool(ok)}")

    def stop(self):
        if self._dll:
            try:
                self._dll.stop_hook()
            except Exception:
                pass
        self._cbs = []
        self._iso_cb = None

    def _on_trigger(self, x, y, ox, oy):
        if self.on_wheel_trigger:
            try:
                self.on_wheel_trigger(x, y, ox, oy)
            except Exception:
                pass

    def _on_release(self, x, y):
        if self.on_wheel_release:
            try:
                self.on_wheel_release(x, y)
            except Exception:
                pass

    def _on_normal_up(self, x, y):
        if self.on_normal_up:
            try:
                self.on_normal_up(x, y)
            except Exception:
                pass

    def _on_left(self, x, y):
        if self.on_left_click:
            try:
                self.on_left_click(x, y)
            except Exception:
                pass

    def _on_move(self, x, y):
        if self.on_mouse_move:
            try:
                self.on_mouse_move(x, y)
            except Exception:
                pass

    def _on_isolated(self):
        try:
            if self._isolated_check and self._isolated_check():
                return 1
        except Exception:
            pass
        return 0
