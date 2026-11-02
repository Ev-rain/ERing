# -*- coding: utf-8 -*-
"""统一路径解析：兼容源码运行与 PyInstaller 打包（frozen）两种模式。

- 源码模式：app 包在 src/ERing/app，资源在 app/assets，数据在 src/ERing/data。
- 打包模式：代码在 _MEIPASS 临时目录，资源经 --add-data 打进 _MEIPASS；
  可写数据（data/）放在 exe 所在目录，ffmpeg/钩子 DLL 优先找 exe 目录。
"""
import os
import sys
from pathlib import Path


def is_frozen():
    return bool(getattr(sys, "frozen", False))


def app_dir():
    """app 包所在目录（源码下为 app/，打包后为 _MEIPASS）。"""
    if is_frozen():
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
    return Path(__file__).resolve().parent


def project_root():
    """运行根目录（源码下为 src/ERing；打包后为 exe 所在目录，可写）。"""
    if is_frozen():
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


def repo_root():
    """仓库根目录（源码模式下为 src/ERing 的上级；打包后与运行目录一致）。"""
    if is_frozen():
        return project_root()
    return Path(__file__).resolve().parent.parent.parent


def resource_path(rel):
    """只读资源路径：源码下 app/rel，打包后 _MEIPASS/rel。"""
    return app_dir() / rel


def recordings_dir(configured=""):
    """录屏输出目录：设置里填了就用它，否则落在 <运行根目录>/data/recordings。

    与 config.CONFIG_DIR 保持一致（不能 import config，会形成循环）。
    """
    text = str(configured or "").strip()
    return Path(text) if text else project_root() / "data" / "recordings"


def open_in_explorer(path):
    """在资源管理器里打开目录（顺带建好），失败只记日志，不抛给 UI。"""
    target = Path(path)
    try:
        target.mkdir(parents=True, exist_ok=True)
        os.startfile(str(target))
        return True
    except Exception as exc:  # noqa: BLE001
        try:
            from app.log_utils import log

            log(f"open dir failed: {target}: {exc!r}")
        except Exception:
            pass
        return False
