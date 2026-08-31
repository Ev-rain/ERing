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
