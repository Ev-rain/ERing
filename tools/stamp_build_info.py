# -*- coding: utf-8 -*-
"""打包时记录版本号与发行日期到 app/build_info.py。

用法：
    python tools/stamp_build_info.py            # 以最近 git tag 作为版本
    set ERING_VERSION=v1.0.3 && python tools/stamp_build_info.py

生成 src/ERing/app/build_info.py（自动生成，勿手动编辑，已加入 .gitignore）。
"""
import datetime
import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]  # 项目根
TARGET = ROOT / "src" / "ERing" / "app" / "build_info.py"
VERSION_FILE = ROOT / "VERSION"


def _git(*args):
    try:
        r = subprocess.run(
            ["git"] + list(args),
            capture_output=True,
            text=True,
            timeout=15,
            cwd=str(ROOT),
        )
        return r.stdout.strip()
    except Exception:
        return ""


def _read_version_file():
    """优先从项目根 VERSION 文件读版本与（可选的）发行日期。"""
    try:
        lines = VERSION_FILE.read_text(encoding="utf-8").splitlines()
        if lines:
            return lines[0].strip(), (lines[1].strip() if len(lines) > 1 else "")
    except Exception:
        pass
    return "", ""


def resolve_version():
    v = os.environ.get("ERING_VERSION", "").strip()
    if v:
        return v
    tag = _git("describe", "--tags", "--abbrev=0")
    if tag:
        return tag
    file_v, _ = _read_version_file()
    if file_v:
        return file_v
    return "dev"


def resolve_date(version):
    _, file_d = _read_version_file()
    if file_d:
        return file_d
    if version and version != "dev":
        d = _git("log", "-1", "--format=%cs", version)
        if d:
            return d
    return datetime.date.today().isoformat()


def main():
    version = resolve_version()
    date = resolve_date(version)
    content = (
        "# -*- coding: utf-8 -*-\n"
        "# 由 tools/stamp_build_info.py 在打包时自动生成，请勿手动编辑。\n"
        f"__version__ = {version!r}\n"
        f"release_date = {date!r}\n"
    )
    TARGET.parent.mkdir(parents=True, exist_ok=True)
    TARGET.write_text(content, encoding="utf-8")
    print(f"stamped build_info: version={version} date={date} -> {TARGET}")


if __name__ == "__main__":
    main()
