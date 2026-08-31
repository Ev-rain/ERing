# -*- coding: utf-8 -*-
"""获取当前选中的文本：UI Automation 优先，剪贴板探测兜底"""
import ctypes
import time

import pyperclip


def _send_ctrl_c():
    user32 = ctypes.windll.user32
    KEYEVENTF_KEYUP = 0x0002
    try:
        user32.keybd_event(0x11, 0, 0, 0)  # Ctrl down
        user32.keybd_event(0x43, 0, 0, 0)  # C down
        time.sleep(0.03)
        user32.keybd_event(0x43, 0, KEYEVENTF_KEYUP, 0)
        user32.keybd_event(0x11, 0, KEYEVENTF_KEYUP, 0)
    except Exception:
        pass


def get_selected_text_via_uia():
    try:
        import uiautomation as auto

        focus = auto.GetFocusedControl()
        if focus is None:
            return None
        node = focus
        for _ in range(16):
            try:
                pattern = node.GetTextPattern()
                if pattern:
                    texts = []
                    for rng in pattern.GetSelection():
                        t = rng.GetText(8192)
                        if t:
                            texts.append(t)
                    if texts:
                        return "\n".join(texts).strip() or None
            except Exception:
                pass
            parent = node.GetParentControl()
            if parent is None:
                break
            node = parent
    except Exception:
        pass
    return None


def get_selected_text_via_clipboard():
    """清空剪贴板 -> 发送 Ctrl+C -> 读回文本 -> 恢复剪贴板。"""
    saved = None
    try:
        try:
            saved = pyperclip.paste()
        except Exception:
            saved = None
        try:
            pyperclip.copy("")
        except Exception:
            return None
        time.sleep(0.06)
        _send_ctrl_c()
        time.sleep(0.22)
        try:
            text = pyperclip.paste() or ""
        except Exception:
            text = ""
        return text.strip() or None
    finally:
        try:
            pyperclip.copy(saved if saved is not None else "")
        except Exception:
            pass


def get_selected_text():
    try:
        text = get_selected_text_via_uia()
        if text:
            return text
    except Exception:
        pass
    return get_selected_text_via_clipboard()
