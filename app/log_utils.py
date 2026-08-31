# -*- coding: utf-8 -*-
"""日志：写入 data\\app.log 与 mouse.log，启动时轮转、最多保留 5 份。"""
import os
import threading
import time

from app.config import CONFIG_DIR

_enabled = True
_lock = threading.Lock()
KEEP_BACKUPS = 4  # 备份 4 份 + 当前日志 = 共保留 5 份


def configure(enabled=True):
    global _enabled
    _enabled = bool(enabled) or os.environ.get("SCREEN_TRANSLATE_DEBUG") == "1"
    _rotate("app.log")
    _rotate("mouse.log")


def _rotate(name):
    """启动时把旧日志改名归档，只保留最近 KEEP_BACKUPS 份备份。"""
    try:
        p = CONFIG_DIR / name
        if p.exists() and p.stat().st_size > 0:
            ts = time.strftime("%Y%m%d_%H%M%S")
            backup = CONFIG_DIR / f"{p.stem}_{ts}{p.suffix}"
            n = 1
            while backup.exists():
                backup = CONFIG_DIR / f"{p.stem}_{ts}_{n}{p.suffix}"
                n += 1
            os.replace(str(p), str(backup))
        backups = sorted(
            CONFIG_DIR.glob(f"{p.stem}_[0-9]*{p.suffix}"),
            key=lambda x: x.name,
            reverse=True,
        )
        for old in backups[KEEP_BACKUPS:]:
            try:
                old.unlink()
            except OSError:
                pass
    except Exception:
        pass


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
