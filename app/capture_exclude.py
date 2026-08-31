# -*- coding: utf-8 -*-
"""让窗口“可见但不可被录制/截图”：SetWindowDisplayAffinity(WDA_EXCLUDEFROMCAPTURE)。"""
import ctypes

WDA_EXCLUDEFROMCAPTURE = 0x11


def set_exclude_from_capture(widget):
    try:
        hwnd = int(widget.winId())
        ctypes.windll.user32.SetWindowDisplayAffinity(hwnd, WDA_EXCLUDEFROMCAPTURE)
        return True
    except Exception:
        return False
