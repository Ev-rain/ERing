# -*- coding: utf-8 -*-
"""当前打包版本与发行时间。

打包时由 tools/stamp_build_info.py 生成 app/build_info.py（记录版本号与日期），
本模块负责读取；未打包（源码运行）时回退到占位，避免依赖外部查询。
"""

DEFAULT_VERSION = "dev"
DEFAULT_DATE = "—"


def _read():
    """读取生成文件 build_info.py。优先 import（冻结打包后也能用），失败再直接读文件。"""
    version, date = DEFAULT_VERSION, DEFAULT_DATE
    try:
        from app import build_info  # 打包前生成

        version = str(getattr(build_info, "__version__", version) or version)
        date = str(getattr(build_info, "release_date", date) or date)
        return version, date
    except Exception:
        pass
    try:
        from pathlib import Path

        p = Path(__file__).resolve().parent / "build_info.py"
        if p.exists():
            ns = {}
            exec(compile(p.read_text(encoding="utf-8"), str(p), "exec"), ns)
            version = str(ns.get("__version__") or version)
            date = str(ns.get("release_date") or date)
    except Exception:
        pass
    return version, date


def current():
    """返回 (版本号, 发行日期)。"""
    return _read()
