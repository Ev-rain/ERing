# -*- coding: utf-8 -*-
"""tools/stamp_build_info.py 的版本来源优先级测试（脚本式，无 pytest）。

背景：仓库里存在 v1.0.0 ~ v1.1.0 的旧 tag，而 VERSION 文件已经写到 v1.1.2。
打包脚本若先取 tag，产出的 exe 会一直显示旧版本号。
"""
import importlib.util
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "tools" / "stamp_build_info.py"


def _load_tool():
    spec = importlib.util.spec_from_file_location("stamp_build_info_under_test", TOOL)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _version_file_value():
    return (ROOT / "VERSION").read_text(encoding="utf-8").splitlines()[0].strip()


def test_version_file_wins_over_git_tag():
    """VERSION 文件是版本号的唯一来源，旧 tag 不能覆盖它。

    这里显式让 git 返回旧 tag，模拟用户在 cmd 里打包时 git 在 PATH 上的情形；
    开发机上的 python 子进程未必能找到 git，所以必须打桩才测得出这个问题。
    """
    mod = _load_tool()
    os.environ.pop("ERING_VERSION", None)
    mod._git = lambda *args: "v1.1.0"
    expected = _version_file_value()
    got = mod.resolve_version()
    assert got == expected, f"VERSION 文件是 {expected}，工具却算出 {got}"


def test_env_overrides_version_file():
    """ERING_VERSION 环境变量优先级最高（用于临时构建）。"""
    mod = _load_tool()
    os.environ["ERING_VERSION"] = "v9.9.9"
    try:
        assert mod.resolve_version() == "v9.9.9"
    finally:
        os.environ.pop("ERING_VERSION", None)


if __name__ == "__main__":
    test_version_file_wins_over_git_tag()
    test_env_overrides_version_file()
    print("ALL TESTS PASSED")
