# -*- coding: utf-8 -*-
"""日志：写入 %APPDATA%\\轮盘翻译\\app.log 与 mouse.log"""
import os
import threading
import time

from app.config import CONFIG_DIR

_enabled = True
_lock = threading.Lock()


def configure(enabled=True):
    global _enabled
    _enabled = bool(enabled) or os.environ.get("SCREEN_TRANSLATE_DEBUG") == "1"


def _write(name, msg):
    if not _enabled:
        return
    try:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        with _lock:
            with open(CONFIG_DIR / name, "a", encoding="utf-8") as f:
                f.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}\n")
    except Exception:
        pass


def log(msg):
    _write("app.log", msg)


def log_mouse(msg):
    _write("mouse.log", msg)
