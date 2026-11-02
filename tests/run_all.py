# -*- coding: utf-8 -*-
"""一次性跑完所有回归脚本，失败时用非零退出码收场。

跑法：.venv\\Scripts\\python.exe tests\\run_all.py
之所以用 subprocess 而不是 import：每个脚本都会自己插 sys.path、改控制台编码、
甚至要在 import PySide6 之前设 QT_QPA_PLATFORM，放在同一个进程里会互相污染。
"""
import subprocess
import sys
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent
# 顺序：纯逻辑在前，需要 Qt/真实 DLL 的在后，早失败早停
SKIP = {"run_all.py", "selftest.py"}


def discover():
    return sorted(
        p for p in TESTS_DIR.glob("test_*.py") if p.name not in SKIP
    )


def run(path):
    cmd = [sys.executable, str(path)]
    cwd = str(TESTS_DIR.parent)
    try:
        proc = subprocess.run(
            cmd,
            cwd=cwd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
    except OSError:
        # 受限环境（例如沙箱）不允许创建管道，退化成直接继承控制台输出
        code = subprocess.call(cmd, cwd=cwd)
        return code == 0, ""
    output = (proc.stdout or "") + (proc.stderr or "")
    passed = proc.returncode == 0 and "ALL TESTS PASSED" in output
    return passed, output


def main():
    scripts = discover()
    if not scripts:
        print("no test scripts found")
        return 1
    failed = []
    for path in scripts:
        passed, output = run(path)
        mark = "PASS" if passed else "FAIL"
        print(f"[{mark}] {path.name}")
        if not passed:
            failed.append(path.name)
            tail = "\n".join(output.strip().splitlines()[-25:])
            print(tail)
    print()
    print(f"{len(scripts) - len(failed)}/{len(scripts)} passed")
    if failed:
        print("failed: " + ", ".join(failed))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
