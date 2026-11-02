# -*- coding: utf-8 -*-
"""设置页「全屏应用名单」列表控件离屏测试。

运行：.venv/Scripts/python.exe tests/test_settings_app_lists.py
"""
import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src" / "ERing"))

from PySide6.QtWidgets import QApplication, QListWidget

import app.config as config
from app.settings_dialog import SettingsDialog

A = r"C:\Tools\obs64.exe"
B = r"C:\Games\game.exe"


def make_dialog():
    cfg = config.migrate({"fullscreen_whitelist": [B], "fullscreen_blacklist": [A]})
    return SettingsDialog(cfg)


def test_lists_are_populated_from_config():
    app = QApplication.instance() or QApplication([])
    dlg = make_dialog()
    assert dlg.whitelist_list.count() == 1
    assert dlg.blacklist_list.count() == 1
    assert SettingsDialog._list_paths(dlg.whitelist_list) == [B]
    assert SettingsDialog._list_paths(dlg.blacklist_list) == [A]
    assert dlg.blacklist_list.item(0).toolTip() == A
    assert dlg.blacklist_list.item(0).text().lower() == "obs64.exe"
    dlg.deleteLater()
    app.processEvents()


def test_add_paths_dedupes_and_ignores_empty():
    app = QApplication.instance() or QApplication([])
    w = QListWidget()
    SettingsDialog._add_paths(w, [A, A.upper(), "", "  "])
    assert SettingsDialog._list_paths(w) == [A]
    app.processEvents()


if __name__ == "__main__":
    test_lists_are_populated_from_config()
    test_add_paths_dedupes_and_ignores_empty()
    print("ALL TESTS PASSED")
