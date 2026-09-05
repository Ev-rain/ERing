# -*- coding: utf-8 -*-
"""程序入口：先设置 DPI 感知（必须在创建 QApplication 之前），再启动主程序。
主逻辑（ScreenTranslatorApp）见 app/application.py。"""
import ctypes
import shutil
import sys
from pathlib import Path

# 禁止生成 __pycache__，并清理历史遗留的字节码缓存
sys.dont_write_bytecode = True
try:
    _root = Path(__file__).resolve().parent
    for _pyc in _root.rglob("__pycache__"):
        try:
            shutil.rmtree(_pyc)
        except OSError:
            pass
except Exception:
    pass

# DPI 感知：优先设置与 Qt 默认一致的 PER_MONITOR_AWARE_V2，
# 避免 Qt 创建 QApplication 时再次设置失败而打印 “拒绝访问” 告警。
try:
    if ctypes.windll.user32.SetProcessDpiAwarenessContext(-4):
        pass  # 设置成功，Qt 不会再告警
    else:
        raise OSError("SetProcessDpiAwarenessContext 返回失败")
except Exception:
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass

from app.application import main

if __name__ == "__main__":
    sys.exit(main())
