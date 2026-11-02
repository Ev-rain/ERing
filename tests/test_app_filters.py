# -*- coding: utf-8 -*-
"""全屏应用名单判定（白名单/黑名单）离线测试。

运行：.venv/Scripts/python.exe tests/test_app_filters.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src" / "ERing"))

from app.fullscreen import matches_entry, normalize_path, should_suppress

GAME = r"C:\Games\game.exe"
OBS = r"C:\Tools\obs64.exe"
CHROME = r"C:\Program Files\Google\Chrome\Application\chrome.exe"


def cfg(wl=(), bl=(), on=True):
    return {"suppress_fullscreen": on, "fullscreen_whitelist": list(wl),
            "fullscreen_blacklist": list(bl)}


def test_blacklist_suppresses_regardless_of_fullscreen():
    c = cfg(bl=[OBS])
    assert should_suppress(c, path=OBS, fullscreen=False) is True
    assert should_suppress(c, path=OBS, fullscreen=True) is True


def test_blacklist_ignores_master_switch():
    c = cfg(bl=[OBS], on=False)
    assert should_suppress(c, path=OBS, fullscreen=False) is True


def test_fullscreen_without_list_hit_suppresses():
    c = cfg()
    assert should_suppress(c, path=CHROME, fullscreen=True) is True
    assert should_suppress(c, path=CHROME, fullscreen=False) is False


def test_whitelist_allows_when_fullscreen():
    c = cfg(wl=[GAME])
    assert should_suppress(c, path=GAME, fullscreen=True) is False


def test_blacklist_beats_whitelist():
    c = cfg(wl=[GAME], bl=[GAME])
    assert should_suppress(c, path=GAME, fullscreen=True) is True


def test_path_case_and_separator_insensitive():
    c = cfg(bl=[OBS])
    assert should_suppress(c, path=r"C:\TOOLS\OBS64.EXE", fullscreen=False) is True
    assert normalize_path(r"C:\Tools\..\Tools\obs64.exe") == normalize_path(OBS)


def test_legacy_basename_entry_still_matches():
    c = cfg(wl=["chrome.exe"])
    assert should_suppress(c, path=CHROME, fullscreen=True) is False
    assert matches_entry("obs64.exe", OBS) is True


def test_unknown_foreground_is_conservative_only_when_fullscreen():
    c = cfg(bl=[OBS])
    assert should_suppress(c, path="", name="", fullscreen=True) is True
    assert should_suppress(c, path="", name="", fullscreen=False) is False


def test_chinese_and_space_in_path():
    p = r"D:\学习 资料\工具\截图.exe"
    c = cfg(bl=[p])
    assert should_suppress(c, path=p, fullscreen=False) is True


def test_config_always_gives_lists():
    import app.config as config

    c = config.migrate({})
    assert c["fullscreen_blacklist"] == []
    assert c["fullscreen_whitelist"] == []

    c = config.migrate({"fullscreen_blacklist": None, "fullscreen_whitelist": "C:\\a.exe"})
    assert c["fullscreen_blacklist"] == []
    assert c["fullscreen_whitelist"] == []      # 非列表一律丢弃，避免字符串被逐字符遍历

    c = config.migrate({"fullscreen_blacklist": ["  C:\\a.exe  ", ""]})
    assert c["fullscreen_blacklist"] == [r"C:\a.exe"]   # 剥空白、丢空串


if __name__ == "__main__":
    test_blacklist_suppresses_regardless_of_fullscreen()
    test_blacklist_ignores_master_switch()
    test_fullscreen_without_list_hit_suppresses()
    test_whitelist_allows_when_fullscreen()
    test_blacklist_beats_whitelist()
    test_path_case_and_separator_insensitive()
    test_legacy_basename_entry_still_matches()
    test_unknown_foreground_is_conservative_only_when_fullscreen()
    test_chinese_and_space_in_path()
    test_config_always_gives_lists()
    print("ALL TESTS PASSED")
