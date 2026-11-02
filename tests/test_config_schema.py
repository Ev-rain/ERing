# -*- coding: utf-8 -*-
"""配置校验回归测试：手改坏 settings.json 不该让程序打不开。

跑法：.venv\\Scripts\\python.exe tests\\test_config_schema.py
"""
import ctypes
import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src" / "ERing"))


def _utf8_console():
    if sys.platform == "win32":
        try:
            ctypes.windll.kernel32.SetConsoleOutputCP(65001)
        except Exception:
            pass
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


_utf8_console()

from app import config  # noqa: E402


def test_bad_int_falls_back_or_clamps():
    data = config.migrate({"drag_threshold": "14", "record_fps": "abc"})
    assert data["drag_threshold"] == 14, "数字字符串应该被转成整数"
    assert data["record_fps"] == config.DEFAULTS["record_fps"], "认不出的数字要退回默认值"
    huge = config.migrate({"drag_threshold": 9999})
    assert huge["drag_threshold"] == 60, "超范围的值要收敛到上限"
    print("ok: 整数键会转换/收敛/回落")


def test_bad_enum_falls_back():
    data = config.migrate({"provider": "BING", "ocr_engine": "RAPID", "record_format": "avi"})
    assert data["provider"] == "auto"
    assert data["ocr_engine"] == "rapid", "枚举匹配应忽略大小写"
    assert data["record_format"] == "mp4"
    print("ok: 枚举键坏值回落，大小写不敏感")


def test_bad_bool_multiple_spellings():
    data = config.migrate(
        {"auto_direction": "false", "suppress_fullscreen": 0, "record_mouse": "maybe"}
    )
    assert data["auto_direction"] is False
    assert data["suppress_fullscreen"] is False
    assert data["record_mouse"] is config.DEFAULTS["record_mouse"]
    print("ok: 布尔键接受常见写法，认不出就用默认值")


def test_bad_lists_never_become_strings():
    """名单/尺寸写成字符串时按字符遍历是最典型的坑。"""
    data = config.migrate(
        {
            "fullscreen_blacklist": "C:/Windows/System32/notepad.exe",
            "fullscreen_whitelist": [" ", "C:/a.exe", ""],
            "result_size": [1920],
            "stop_button_pos": ["100", "200"],
            "wheel_items": "翻译",
        }
    )
    assert data["fullscreen_blacklist"] == [], "字符串要整条丢弃，不能逐字符拆"
    assert data["fullscreen_whitelist"] == ["C:/a.exe"]
    assert data["result_size"] == []
    assert data["stop_button_pos"] == [100, 200]
    assert data["wheel_items"] == config.DEFAULTS["wheel_items"]
    print("ok: 列表键坏值不逐字符展开")


def test_unknown_keys_are_kept():
    data = config.migrate({"some_future_key": 1})
    assert data["some_future_key"] == 1, "新版本写入的未知键不应被这次校验清掉"
    print("ok: 未知键原样保留")


def test_sections_stay_strings():
    data = config.migrate({"openai": {"base_url": None, "model": 3}, "deepseek": "oops"})
    assert data["openai"] == {"base_url": "", "model": "3", "api_key": ""}
    assert data["deepseek"] == {"api_key": ""}
    print("ok: openai/deepseek 段落始终是字符串字典")


def test_defaults_pass_through_unchanged():
    data = config.migrate({})
    for key, value in config.DEFAULTS.items():
        assert data[key] == value, f"默认值 {key} 被校验改动了"
    print("ok: 默认配置原样通过校验")


def test_setitem_coerces():
    cfg = config.Config.__new__(config.Config)
    cfg.data = dict(config.DEFAULTS)
    cfg["drag_threshold"] = "20"
    assert cfg["drag_threshold"] == 20
    cfg["provider"] = "nope"
    assert cfg["provider"] == "auto"
    print("ok: Config.__setitem__ 复用同一套校验")


def main():
    test_bad_int_falls_back_or_clamps()
    test_bad_enum_falls_back()
    test_bad_bool_multiple_spellings()
    test_bad_lists_never_become_strings()
    test_unknown_keys_are_kept()
    test_sections_stay_strings()
    test_defaults_pass_through_unchanged()
    test_setitem_coerces()
    print("ALL TESTS PASSED")


if __name__ == "__main__":
    main()
