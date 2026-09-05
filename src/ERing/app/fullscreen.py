# -*- coding: utf-8 -*-
"""前台窗口检测：判断独占/全屏应用，供“全屏时隐藏”功能使用。"""
import ctypes
from ctypes import wintypes

_user32 = ctypes.windll.user32
_kernel32 = ctypes.windll.kernel32

# 窗口面积占所在监视器比例达到该值即视为全屏
_COVERAGE = 0.99

# 系统外壳窗口类（桌面/任务栏等，不算全屏应用）
_SHELL_CLASSES = {
    "Progman", "WorkerW", "Shell_TrayWnd", "Shell_SecondaryTrayWnd",
    "DV2ControlHost",
}


class _RECT(ctypes.Structure):
    _fields_ = [
        ("left", ctypes.c_long), ("top", ctypes.c_long),
        ("right", ctypes.c_long), ("bottom", ctypes.c_long),
    ]


class _MONITORINFO(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.DWORD),
        ("rcMonitor", _RECT),
        ("rcWork", _RECT),
        ("dwFlags", wintypes.DWORD),
    ]


def foreground_process_name():
    """返回前台窗口所属进程名（小写 exe 名），获取失败返回空串。"""
    hwnd = _user32.GetForegroundWindow()
    if not hwnd:
        return ""
    pid = wintypes.DWORD()
    _user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    if not pid.value:
        return ""
    try:
        h = _kernel32.OpenProcess(0x1000, False, pid.value)  # QUERY_LIMITED_INFORMATION
        if not h:
            return ""
        try:
            buf = ctypes.create_unicode_buffer(1024)
            size = wintypes.DWORD(ctypes.sizeof(buf))
            if _kernel32.QueryFullProcessImageNameW(h, 0, buf, ctypes.byref(size)):
                return buf.value.rsplit("\\", 1)[-1].lower()
        finally:
            _kernel32.CloseHandle(h)
    except Exception:
        pass
    return ""


def foreground_is_fullscreen():
    """前台窗口是否覆盖整个所在监视器（全屏/独占都适用）。"""
    hwnd = _user32.GetForegroundWindow()
    if not hwnd:
        return False
    cls = ctypes.create_unicode_buffer(64)
    _user32.GetClassNameW(hwnd, cls, 64)
    if cls.value in _SHELL_CLASSES:
        return False
    try:
        rect = _RECT()
        _user32.GetWindowRect(hwnd, ctypes.byref(rect))
        mon = _user32.MonitorFromWindow(hwnd, 0x2)  # MONITOR_DEFAULTTONEAREST
        info = _MONITORINFO()
        info.cbSize = ctypes.sizeof(info)
        if not _user32.GetMonitorInfoW(mon, ctypes.byref(info)):
            return False
        w = rect.right - rect.left
        h = rect.bottom - rect.top
        mw = info.rcMonitor.right - info.rcMonitor.left
        mh = info.rcMonitor.bottom - info.rcMonitor.top
        if w <= 0 or h <= 0 or mw <= 0 or mh <= 0:
            return False
        return (w * h) >= (mw * mh) * _COVERAGE
    except Exception:
        return False


def fullscreen_should_hide(whitelist=None):
    """全屏应用在前台且不在白名单时返回 True（触发“隐藏”）。"""
    try:
        if not foreground_is_fullscreen():
            return False
        name = foreground_process_name()
        if not name:
            # 识别不到进程名时保守处理：系统窗口通常不满足全屏条件
            return True
        wl = {str(x).strip().lower().removesuffix(".exe") + ".exe"
              for x in (whitelist or []) if str(x).strip()}
        return name not in wl
    except Exception:
        return False
