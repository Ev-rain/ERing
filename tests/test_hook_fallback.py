# -*- coding: utf-8 -*-
"""钩子后端回归测试：安装失败必须能被上层看见，而不是假装成功。

跑法：.venv\\Scripts\\python.exe tests\\test_hook_fallback.py
"""
import ctypes
import os
import sys
import time
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src" / "ERing"))


def _utf8_console():
    if sys.platform == "win32":
        try:
            ctypes.windll.kernel32.SetConsoleOutputCP(65001)
        except Exception:
            pass
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


_utf8_console()

from app.native_hook import DLL_PATH, NativeHook  # noqa: E402
from app.mouse_hook import MouseHook  # noqa: E402


def test_dll_exposes_hook_probe():
    """DLL 必须导出 is_hooked / get_hook_error，否则上层无法区分「没装上」和「没事件」。"""
    dll = ctypes.CDLL(str(DLL_PATH))
    assert hasattr(dll, "is_hooked"), f"{DLL_PATH} 缺少 is_hooked 导出"
    assert hasattr(dll, "get_hook_error"), f"{DLL_PATH} 缺少 get_hook_error 导出"
    print("ok: DLL 导出 is_hooked / get_hook_error")


class _FakeDll:
    """模拟一个「线程起来了但钩子没装上」的 DLL。"""

    def __init__(self, ok=False, err=5):
        self.ok = ok
        self.err = err
        self.started = None
        for name in ("set_drag_threshold", "set_suppress", "set_isolated"):
            setattr(self, name, lambda *a, **k: None)

    def start_hook(self, *cbs):
        self.started = True
        return 1 if self.ok else 0

    def is_hooked(self):
        return 1 if self.ok else 0

    def get_hook_error(self):
        return 0 if self.ok else self.err

    def get_event_count(self):
        return 0

    def stop_hook(self):
        self.started = False


def test_native_hook_reports_failure():
    hook = NativeHook()
    hook._dll = _FakeDll(ok=False, err=5)
    hook.start()
    assert hook.installed is False, "钩子没装上，installed 必须是 False"
    assert hook.hook_error() == 5, "失败码要能透出来"
    print("ok: 原生钩子安装失败 -> installed=False, error=5")


def test_native_hook_reports_success():
    hook = NativeHook()
    hook._dll = _FakeDll(ok=True)
    hook.start()
    assert hook.installed is True, "钩子装上了，installed 必须是 True"
    assert hook.hook_error() == 0
    print("ok: 原生钩子安装成功 -> installed=True")


def test_mouse_hook_exposes_installed():
    hook = MouseHook()
    hook.start()
    for _ in range(20):
        if hook.installed:
            break
        time.sleep(0.05)
    assert hook.installed is True, "Python 兜底钩子装不上，installed 必须是 False 而不是 None"
    count = hook.event_count()
    assert isinstance(count, int)
    hook.stop()
    print("ok: Python 兜底钩子 installed=True")


def main():
    test_dll_exposes_hook_probe()
    test_native_hook_reports_failure()
    test_native_hook_reports_success()
    test_mouse_hook_exposes_installed()
    print("ALL TESTS PASSED")


if __name__ == "__main__":
    main()
