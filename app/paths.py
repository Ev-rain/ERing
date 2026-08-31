# -*- coding: utf-8 -*-
"""统一路径解析：兼容源码运行与 PyInstaller 打包（frozen）两种模式。

- 源码模式：app 包在工程根目录下，资源在 app/assets，数据在工程根/data。
- 打包模式：代码在 _MEIPASS 临时目录，资源经 --add-data 打进 _MEIPASS；
  可写数据（data/）放在 exe 所在目录，ffmpeg/钩子 DLL 优先找 exe 目录。
"""
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
    """工程根目录（源码下为项目根；打包后为 exe 所在目录，可写）。"""
    if is_frozen():
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


def resource_path(rel):
    """只读资源路径：源码下 app/rel，打包后 _MEIPASS/rel。"""
    return app_dir() / rel
