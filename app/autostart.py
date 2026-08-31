# -*- coding: utf-8 -*-
"""开机自启动：写入 HKCU\\...\\Run 注册表项（无需管理员权限）。"""
import sys
import winreg
from pathlib import Path

RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
VALUE_NAME = "Etranslate"


def startup_command():
    root = Path(__file__).resolve().parent.parent
    pyw = root / ".venv" / "Scripts" / "pythonw.exe"
    if not pyw.exists():
        pyw = Path(sys.executable)
    main = root / "main.py"
    return f'"{pyw}" "{main}"'


def is_enabled():
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
            winreg.QueryValueEx(key, VALUE_NAME)
            return True
    except OSError:
        return False


def set_enabled(on):
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
        if on:
            winreg.SetValueEx(
                key, VALUE_NAME, 0, winreg.REG_SZ, startup_command()
            )
        else:
            try:
                winreg.DeleteValue(key, VALUE_NAME)
            except OSError:
                pass
