# -*- coding: utf-8 -*-
"""启动环境自检：当前进程是不是被沙箱化（低完整性级别）。

Windows 的 UIPI（用户界面特权隔离）会拦下低完整性进程的两件事：

* ``Shell_NotifyIcon`` 注册托盘图标 —— 托盘区归中完整性的 explorer.exe 管；
* ``WH_MOUSE_LL`` 一类的低层钩子收不到发往中完整性窗口的输入。

表现就是「托盘里看不到图标，右键拖动也呼不出轮盘」，而且日志里看不出任何
异常（钩子装上了、Qt 也说托盘可用）。常见来源是被沙箱化的宿主（例如某些
IDE / 助手 / 便携环境的终端）拉起，而不是从资源管理器双击。
"""
import ctypes
import struct
from ctypes import wintypes

from app.log_utils import log

UNTRUSTED = 0x0
LOW = 0x1000
MEDIUM = 0x2000
HIGH = 0x3000
SYSTEM = 0x4000

_LEVELS = {
    UNTRUSTED: "不受信任（Untrusted）",
    LOW: "低完整性沙箱（Low）",
    MEDIUM: "普通权限（Medium）",
    HIGH: "管理员权限（High）",
    SYSTEM: "系统权限（System）",
}

_TOKEN_QUERY = 0x0008
_TOKEN_MANDATORY_LABEL = 25  # TokenIntegrityLevel


def _bind_api():
    """显式声明参数类型——不加 argtypes 时 GetCurrentProcess() 的伪句柄会被截断，
    OpenProcessToken 直接失败（返回 0），自检就永远"看不出来"。"""
    advapi32 = ctypes.windll.advapi32
    kernel32 = ctypes.windll.kernel32
    kernel32.GetCurrentProcess.restype = wintypes.HANDLE
    advapi32.OpenProcessToken.argtypes = [
        wintypes.HANDLE,
        wintypes.DWORD,
        ctypes.POINTER(wintypes.HANDLE),
    ]
    advapi32.OpenProcessToken.restype = wintypes.BOOL
    advapi32.GetTokenInformation.argtypes = [
        wintypes.HANDLE,
        ctypes.c_int,
        ctypes.c_void_p,
        wintypes.DWORD,
        ctypes.POINTER(wintypes.DWORD),
    ]
    advapi32.GetTokenInformation.restype = wintypes.BOOL


def _own_integrity_rid():
    """读当前进程令牌的完整性级别 RID；失败返回 None。"""
    try:
        _bind_api()
        advapi32 = ctypes.windll.advapi32
        kernel32 = ctypes.windll.kernel32
        handle = wintypes.HANDLE()
        if not advapi32.OpenProcessToken(
            kernel32.GetCurrentProcess(), _TOKEN_QUERY, ctypes.byref(handle)
        ):
            return None
        try:
            size = wintypes.DWORD(0)
            advapi32.GetTokenInformation(
                handle, _TOKEN_MANDATORY_LABEL, None, 0, ctypes.byref(size)
            )
            if not size.value:
                return None
            buf = ctypes.create_string_buffer(size.value)
            if not advapi32.GetTokenInformation(
                handle, _TOKEN_MANDATORY_LABEL, buf, size.value, ctypes.byref(size)
            ):
                return None
            sid = ctypes.c_void_p.from_buffer(buf).value
            if not sid:
                return None
            # SID: 1 字节修订号 + 1 字节子权威个数 + 6 字节标识权威 + n*4 字节子权威
            count = ctypes.string_at(sid, 2)[1]
            if count < 1:
                return None
            raw = ctypes.string_at(sid, 8 + 4 * count)
            return struct.unpack_from("<I", raw, 8 + 4 * (count - 1))[0]
        finally:
            kernel32.CloseHandle(handle)
    except Exception:  # noqa: BLE001
        return None


def current_integrity():
    """当前进程的完整性级别 RID（0x1000=Low、0x2000=Medium…），失败返回 None。"""
    return _own_integrity_rid()


def describe(rid):
    if rid is None:
        return "未知"
    return _LEVELS.get(rid, f"未知（{rid:#x}）")


def is_sandboxed(rid):
    """低于中完整性即为沙箱化：托盘图标与低层钩子都不可用。"""
    return rid is not None and rid < MEDIUM


def sandbox_notice():
    return (
        "ERing 现在跑在低完整性的沙箱环境里，Windows 会因此拦下两件事：\n\n"
        "  · 托盘图标的注册（托盘区归资源管理器管）；\n"
        "  · 低层鼠标钩子（右键拖动呼出轮盘收不到输入）。\n\n"
        "所以你现在看不到托盘图标，也呼不出轮盘——不是程序装坏了。\n\n"
        "请关掉这个进程，然后按下面任一方式重新启动：\n"
        "  · 在 Windows 资源管理器里双击 ERing.exe；\n"
        "  · 按 Win+R，输入 ERing.exe 的完整路径后回车。"
    )


def warn_if_sandboxed(smoke=False):
    """启动自检：沙箱环境下写日志并弹窗说明，返回是否命中了沙箱。"""
    rid = _own_integrity_rid()
    log(f"integrity: {describe(rid)}")
    if not is_sandboxed(rid):
        return False
    log("低完整性环境：托盘图标注册与低层鼠标钩子都会被 UIPI 拦截")
    if smoke:
        return True
    try:
        ctypes.windll.user32.MessageBoxW(
            None, sandbox_notice(), "ERing：启动环境受限", 0x00000030  # MB_ICONWARNING
        )
    except Exception:  # noqa: BLE001
        pass
    return True
