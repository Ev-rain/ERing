# -*- coding: utf-8 -*-
"""前台窗口检测：判断独占/全屏应用，供“全屏时隐藏”功能使用。

判定逻辑集中在这里的纯函数 `should_suppress(cfg, ...)`：
黑名单命中一律压制（不论是否全屏），白名单命中则放行，其余按是否全屏决定。
"""
import ctypes
import os
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


def foreground_process_path():
    """返回前台窗口所属进程的完整路径，获取失败返回空串。"""
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
                return buf.value
        finally:
            _kernel32.CloseHandle(h)
    except Exception:
        pass
    return ""


def foreground_process_name():
    """返回前台窗口所属进程名（小写 exe 名），获取失败返回空串。"""
    path = foreground_process_path()
    return os.path.basename(path).lower() if path else ""


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


def normalize_path(p):
    """路径归一化：统一分隔符、去掉 ..、忽略大小写（Windows）。"""
    return os.path.normcase(os.path.normpath(str(p)))


def _base_name(p):
    """取小写 exe 名，去掉空的尾部。"""
    return os.path.basename(str(p).strip()).lower()


def matches_entry(entry, path):
    """名单条目是否命中给定进程路径。

    条目含路径分隔符时按归一化全路径比较；否则按 exe 基名比较
    （兼容用户早期手填的 `chrome.exe` / `chrome`）。
    """
    e = str(entry or "").strip()
    p = str(path or "").strip()
    if not e or not p:
        return False
    if os.sep in e or "/" in e:
        return normalize_path(e) == normalize_path(p)
    want = _base_name(e)
    if not want.endswith(".exe"):
        want += ".exe"
    return _base_name(p) == want


def _cfg_mapping(cfg):
    """兼容两种配置形态：普通 dict 与 `app.config.Config`（只有 __getitem__）。"""
    data = getattr(cfg, "data", None)
    if isinstance(data, dict):
        return data
    return cfg if isinstance(cfg, dict) else {}


_warned = False


def _log_once(exc):
    """判定失败只记一次日志，避免 300ms 轮询刷屏。"""
    global _warned
    if _warned:
        return
    _warned = True
    try:
        from app.log_utils import log

        log(f"should_suppress failed: {exc!r}")
    except Exception:
        pass


def should_suppress(cfg, path=None, name=None, fullscreen=None):
    """是否需要压制轮盘（隐藏）。

    判定顺序：黑名单命中 → 压制；「全屏时隐藏」关闭 → 不压制；
    非全屏 → 不压制；白名单命中 → 不压制；其余（含取不到进程信息）→ 压制。
    三个可选参数为 None 时现场取前台窗口信息。
    """
    try:
        cfg = _cfg_mapping(cfg)
        if fullscreen is None:
            fullscreen = foreground_is_fullscreen()
        if path is None:
            path = foreground_process_path()
        if name is None:
            name = _base_name(path)
        # 黑名单独立于「全屏时隐藏」开关：不论是否全屏都不弹轮盘
        for entry in cfg.get("fullscreen_blacklist") or []:
            if matches_entry(entry, path) or (
                not path and name and _base_name(entry) == name
            ):
                return True
        if not bool(cfg.get("suppress_fullscreen", True)):
            return False
        if not fullscreen:
            return False
        if not path and not name:
            # 识别不到前台进程时保守处理：系统窗口通常不满足全屏条件
            return True
        for entry in cfg.get("fullscreen_whitelist") or []:
            if matches_entry(entry, path):
                return False
        return True
    except Exception as exc:
        _log_once(exc)
        return False


def fullscreen_should_hide(whitelist=None):
    """兼容旧调用点：全屏应用在前台且不在白名单时返回 True。"""
    return should_suppress(
        {"suppress_fullscreen": True, "fullscreen_whitelist": list(whitelist or [])}
    )
