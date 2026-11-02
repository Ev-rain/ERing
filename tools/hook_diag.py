# -*- coding: utf-8 -*-
"""鼠标钩子诊断（低干扰版）：判断原生钩子在本机能否收到事件。

用法（在仓库根目录）：
    .venv\\Scripts\\python.exe tools\\hook_diag.py

只安装应用自己用的 wheelhook.dll 钩子，并且**不注册任何 Python 回调**
（回调传 NULL，DLL 内部会跳过），所以运行期间鼠标不会卡。
运行后请来回移动鼠标 5 秒，脚本会打印这段时间钩子收到的事件数。

判读：
- install ok / events > 0  -> 原生钩子正常，问题在应用侧接线
- install ok / events = 0  -> 钩子装上了但系统不派发事件（被安全软件/系统拦）
- install FAILED (winerror) -> SetWindowsHookExW 直接失败，看错误码

想看「直接调用 Win32 装钩子」的对照结果：加 --direct 参数
（这条会注册 Python 回调，运行期间鼠标会明显变卡，属正常现象）。
"""
import ctypes
import sys
import time
from ctypes import wintypes
from pathlib import Path

WH_MOUSE_LL = 14
HC_ACTION = 0


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

CB4 = ctypes.WINFUNCTYPE(None, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int)
CB2 = ctypes.WINFUNCTYPE(None, ctypes.c_int, ctypes.c_int)


def dll_path():
    return Path(__file__).resolve().parent.parent / "src" / "ERing" / "native" / "wheelhook.dll"


def test_dll():
    """只测应用自己的 DLL 钩子，回调全部传 None（不惊动 Python）。"""
    path = dll_path()
    if not path.exists():
        print(f"[1] 找不到 {path}")
        return None
    dll = ctypes.CDLL(str(path))
    dll.start_hook.argtypes = [CB4, CB2, CB2, CB2, CB2]
    dll.start_hook.restype = ctypes.c_int
    dll.get_event_count.argtypes = []
    dll.get_event_count.restype = ctypes.c_long
    dll.stop_hook.argtypes = []

    has_probe = hasattr(dll, "is_hooked") and hasattr(dll, "get_hook_error")
    if has_probe:
        dll.is_hooked.restype = ctypes.c_int
        dll.get_hook_error.restype = ctypes.c_ulong

    ret = dll.start_hook(None, None, None, None, None)
    if has_probe:
        print(f"[1] dll.start_hook -> {ret}  is_hooked={dll.is_hooked()}  "
              f"winerror={dll.get_hook_error()}")
    else:
        print(f"[1] dll.start_hook -> {ret}（老 DLL：1 只代表线程创建成功，不代表钩子装上了）")
    return dll


def test_direct():
    """对照组：直接调 SetWindowsHookExW + Python 回调（会卡，需要 --direct）。"""
    user32 = ctypes.WinDLL("user32", use_last_error=True)
    user32.SetWindowsHookExW.restype = ctypes.c_void_p
    user32.SetWindowsHookExW.argtypes = [ctypes.c_int, CB4, ctypes.c_void_p, wintypes.DWORD]
    counter = {"n": 0}

    def _proc(n_code, w_param, l_param):
        if n_code == HC_ACTION:
            counter["n"] += 1
        return user32.CallNextHookEx(None, n_code, w_param, l_param)

    cb = ctypes.WINFUNCTYPE(ctypes.c_ssize_t, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM)(_proc)
    handle = user32.SetWindowsHookExW(WH_MOUSE_LL, cb, None, 0)
    print(f"[D] direct SetWindowsHookExW -> handle={handle} winerror={ctypes.get_last_error()}")
    return handle, cb, counter, user32


def main():
    print("=== ERing 鼠标钩子诊断（低干扰版）===")
    dll = test_dll()
    direct = test_direct() if "--direct" in sys.argv else None

    print("[2] 请现在开始来回移动鼠标，持续 5 秒 ...")
    counts = []
    for _ in range(10):
        time.sleep(0.5)
        try:
            counts.append(int(dll.get_event_count()) if dll else -1)
        except Exception:
            counts.append(-1)
    move_events = counts[-1] if counts else -1
    print(f"[3] DLL 钩子事件数（每 0.5 秒采样）= {counts}")

    if direct is not None:
        handle, _cb, counter, user32 = direct
        print(f"[4] 直接钩子收到事件 = {counter['n']}")
        if handle:
            try:
                user32.UnhookWindowsHookEx(ctypes.c_void_p(handle))
            except Exception:
                pass

    if dll is not None:
        try:
            dll.stop_hook()
        except Exception:
            pass

    print()
    if move_events > 0:
        print("结论：原生钩子能收到鼠标事件 -> 钩子本身没问题，是应用侧的问题。")
    elif move_events == 0:
        print("结论：钩子装上了但一个事件都没收到 -> 系统/安全软件没有把事件派发给本进程。")
    else:
        print("结论：DLL 没测成，把上面的输出整段发给我。")


if __name__ == "__main__":
    main()
