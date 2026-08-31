# -*- coding: utf-8 -*-
"""开机自启动：写入 HKCU\\...\\Run 注册表项（无需管理员权限）。"""
import sys
import winreg
from pathlib import Path

from app.paths import is_frozen, project_root, repo_root

RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
VALUE_NAME = "ERing"
LEGACY_NAME = "Etranslate"  # 旧版本注册表项，检测到后自动迁移


def startup_command():
    if is_frozen():
        return f'"{sys.executable}"'
    pyw = repo_root() / ".venv" / "Scripts" / "pythonw.exe"
    if not pyw.exists():
        pyw = Path(sys.executable)
    main = project_root() / "main.py"
    return f'"{pyw}" "{main}"'


def is_enabled():
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
            winreg.QueryValueEx(key, VALUE_NAME)
            return True
    except OSError:
        pass
    # 迁移旧名称：旧项存在时视为已启用，并改名为新名称
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
            data, kind = winreg.QueryValueEx(key, LEGACY_NAME)
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
            winreg.SetValueEx(key, VALUE_NAME, 0, kind, data)
            winreg.DeleteValue(key, LEGACY_NAME)
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
