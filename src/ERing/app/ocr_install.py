# -*- coding: utf-8 -*-
"""RapidOCR 可选依赖的安装 / 卸载。

设置面板只负责按钮与文案，真正的 pip 调用集中在这里，便于离线测试
（见 tests/test_ocr_install.py）。

注意：打包后的 ERing.exe 里没有 Python + pip，`sys.executable` 指向 exe 本身，
所以冻结环境下直接返回可读的失败原因，而不是让 pip 报一堆看不懂的错。
"""
from __future__ import annotations

import subprocess
import sys

from app.paths import is_frozen, project_root

# 卸载时一起清掉的包：RapidOCR 及其被一起装进来的依赖
RAPID_PACKAGES = (
    "rapidocr-onnxruntime",
    "opencv-python",
    "onnxruntime",
    "numpy",
    "shapely",
)

FROZEN_HINT = "打包版不带 pip，无法在线安装；请用源码模式（python src/ERing/main.py）安装后再打包"


def _is_frozen():
    """薄包装，方便测试替换。"""
    return is_frozen()


def _tail(text, limit=300):
    return (text or "")[-limit:]


def _pip(args, timeout):
    """跑一次 pip，返回 (ok, 输出尾部或异常信息)。"""
    try:
        proc = subprocess.run(
            [sys.executable, "-m", "pip", *args],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except Exception as exc:  # noqa: BLE001 —— 任何异常都转成可读文字
        return False, str(exc)
    ok = proc.returncode == 0
    return ok, _tail(proc.stderr or proc.stdout)


def install_rapid(timeout=900):
    """按 requirements-ocr.txt 安装 RapidOCR，返回 (ok, 详情)。"""
    if _is_frozen():
        return False, FROZEN_HINT
    req = project_root() / "requirements-ocr.txt"
    return _pip(["install", "-r", str(req)], timeout)


def uninstall_rapid(timeout=300):
    """卸载 RapidOCR 及其依赖，返回 (ok, 详情)。"""
    if _is_frozen():
        return False, FROZEN_HINT
    return _pip(["uninstall", "-y", *RAPID_PACKAGES], timeout)
