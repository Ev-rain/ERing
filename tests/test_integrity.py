# -*- coding: utf-8 -*-
"""启动环境自检：低完整性（沙箱）进程里，托盘图标与低层鼠标钩子都会被拦截。"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src" / "ERing"))

from app.integrity import current_integrity, describe, is_sandboxed, sandbox_notice


def test_current_integrity_returns_known_level():
    rid = current_integrity()
    assert rid is None or rid in (0x0, 0x1000, 0x2000, 0x3000, 0x4000), rid


def test_current_integrity_is_readable():
    """ctypes 不加 argtypes 时 OpenProcessToken 会静默失败，自检就永远看不出沙箱。"""
    assert current_integrity() is not None


def test_describe_maps_known_levels():
    assert "低" in describe(0x1000)
    assert "普通" in describe(0x2000)
    assert describe(None) == "未知"
    assert describe(0x3000)


def test_is_sandboxed_only_below_medium():
    assert is_sandboxed(0x0) is True
    assert is_sandboxed(0x1000) is True
    assert is_sandboxed(0x2000) is False
    assert is_sandboxed(0x3000) is False
    assert is_sandboxed(None) is False


def test_notice_explains_both_symptoms_and_the_way_out():
    text = sandbox_notice()
    assert "托盘" in text
    assert "钩子" in text
    assert "资源管理器" in text


if __name__ == "__main__":
    for _name, _fn in sorted(globals().items()):
        if _name.startswith("test_") and callable(_fn):
            _fn()
    print("ALL TESTS PASSED")
