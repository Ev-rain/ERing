# -*- coding: utf-8 -*-
"""把托盘图标强制应用到所有窗口。

pythonw 托管的程序默认会被 Windows 归入「Python」应用组，任务栏只显示
Python 图标；即使 setWindowIcon 已生效（标题栏/任务栏 WM_SETICON 已设置），
任务栏仍可能显示 pythonw 的图标。这里设置独立 AppUserModelID，并直接用
Win32 API 把 .ico 灌到每个窗口（兼容 Windows 11 KB5051987 之后的行为）。
"""
import ctypes
from ctypes import wintypes

from app.paths import resource_path

WM_SETICON = 0x0080
ICON_BIG = 1
ICON_SMALL = 0
GCL_HICON = -14
IMAGE_ICON = 1
LR_LOADFROMFILE = 0x00000010

_user32 = ctypes.windll.user32
_shell32 = ctypes.windll.shell32

_user32.LoadImageW.argtypes = [
    wintypes.HINSTANCE, wintypes.LPCWSTR, wintypes.UINT,
    ctypes.c_int, ctypes.c_int, wintypes.UINT,
]
_user32.LoadImageW.restype = wintypes.HANDLE
_user32.SendMessageW.argtypes = [
    wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM,
]
_user32.SendMessageW.restype = wintypes.LPARAM
_user32.SetClassLongPtrW.argtypes = [wintypes.HWND, ctypes.c_int, ctypes.c_ssize_t]
_user32.SetClassLongPtrW.restype = ctypes.c_ssize_t
_shell32.SetCurrentProcessExplicitAppUserModelID.argtypes = [wintypes.LPCWSTR]
_shell32.SetCurrentProcessExplicitAppUserModelID.restype = ctypes.c_long

_hicon = None


def set_app_user_model_id(app_id):
    """让 Windows 把本进程当作独立应用，不再归入 Python 组。"""
    try:
        _shell32.SetCurrentProcessExplicitAppUserModelID(app_id)
    except Exception:  # noqa: BLE001
        pass


def _load_hicon():
    global _hicon
    if _hicon:
        return _hicon
    ico = resource_path("assets") / "tray.ico"
    if not ico.exists():
        return None
    # 加载 256px 大图，让系统在任意 DPI 下向下缩放，避免小图放大发虚
    _hicon = _user32.LoadImageW(
        None, str(ico), IMAGE_ICON, 256, 256, LR_LOADFROMFILE
    )
    return _hicon


def apply_to_window(hwnd):
    """用原生 API 覆盖窗口大/小图标和类图标。"""
    h = _load_hicon()
    if not h:
        return
    _user32.SendMessageW(hwnd, WM_SETICON, ICON_BIG, h)
    _user32.SendMessageW(hwnd, WM_SETICON, ICON_SMALL, h)
    _user32.SetClassLongPtrW(hwnd, GCL_HICON, h)
