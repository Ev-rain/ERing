# -*- coding: utf-8 -*-
"""RapidOCR 安装/卸载逻辑（app/ocr_install.py）离线测试。

运行：.venv/Scripts/python.exe tests/test_ocr_install.py
不联网：把 subprocess.run 换成假实现，只验证命令行构造与结果处理。
"""
import sys
import types
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src" / "ERing"))

from app import ocr_install

ROOT = Path(__file__).resolve().parent.parent


class _FakeProc:
    def __init__(self, code=0, out="", err=""):
        self.returncode = code
        self.stdout = out
        self.stderr = err


def _with_run(fake, fn):
    real = ocr_install.subprocess.run
    ocr_install.subprocess.run = fake
    try:
        return fn()
    finally:
        ocr_install.subprocess.run = real


def _with_frozen(value, fn):
    real = ocr_install._is_frozen
    ocr_install._is_frozen = lambda: value
    try:
        return fn()
    finally:
        ocr_install._is_frozen = real


def test_install_runs_pip_with_requirements_file():
    seen = {}

    def fake_run(args, **kw):
        seen["args"] = args
        return _FakeProc(0, out="Successfully installed")

    ok, detail = _with_run(fake_run, lambda: ocr_install.install_rapid())
    assert ok is True, (ok, detail)
    assert seen["args"][1:5] == ["-m", "pip", "install", "-r"], seen["args"]
    assert seen["args"][5].endswith("requirements-ocr.txt"), seen["args"][5]


def test_install_reports_tail_of_output_on_failure():
    def fake_run(args, **kw):
        return _FakeProc(1, err="ERROR: Could not find a version that satisfies")

    ok, detail = _with_run(fake_run, lambda: ocr_install.install_rapid())
    assert ok is False
    assert "Could not find a version" in detail


def test_install_swallows_exceptions_into_message():
    def fake_run(args, **kw):
        raise TimeoutError("boom")

    ok, detail = _with_run(fake_run, lambda: ocr_install.install_rapid())
    assert ok is False
    assert "boom" in detail


def test_install_refuses_in_frozen_build():
    called = []
    ok, detail = _with_frozen(True, lambda: _with_run(
        lambda *a, **k: called.append(1), lambda: ocr_install.install_rapid()))
    assert ok is False
    assert called == [], "打包版不该真的去调 pip"
    assert "源码" in detail or "打包" in detail, detail


def test_uninstall_runs_pip_uninstall_for_known_packages():
    seen = {}

    def fake_run(args, **kw):
        seen["args"] = args
        return _FakeProc(0, out="Successfully uninstalled")

    ok, _ = _with_run(fake_run, lambda: ocr_install.uninstall_rapid())
    assert ok is True
    assert seen["args"][1:4] == ["-m", "pip", "uninstall"], seen["args"]
    assert "-y" in seen["args"]
    for pkg in ("rapidocr-onnxruntime", "onnxruntime"):
        assert pkg in seen["args"], (pkg, seen["args"])


def test_uninstall_refuses_in_frozen_build():
    called = []
    ok, detail = _with_frozen(True, lambda: _with_run(
        lambda *a, **k: called.append(1), lambda: ocr_install.uninstall_rapid()))
    assert ok is False
    assert called == []
    assert detail


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
    print("ALL TESTS PASSED")
