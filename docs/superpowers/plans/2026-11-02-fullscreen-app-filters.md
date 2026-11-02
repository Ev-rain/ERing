# 全屏应用名单（白名单/黑名单）实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use subagent-driven-development (recommended) or executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把「全屏 / 独占应用」的单文本框升级为白名单 + 黑名单两条独立名单，支持用资源管理器挑 `.exe`，按完整路径匹配。

**Architecture:** 判定逻辑收敛成 `fullscreen.py` 里的纯函数（`should_suppress(cfg, path, name, fullscreen)`），Windows API 调用只负责取前台路径；设置页用两个 `QListWidget` + `QFileDialog` 替换文本框；`application.py` 的两处调用点整体替换为新函数。

**Tech Stack:** Python 3.12（`.venv`，PySide6 6.11.2）、ctypes 调 user32/kernel32。测试用仓库现有风格：纯脚本 + `assert`，不依赖 pytest。

**Spec:** `docs/superpowers/specs/2026-11-02-fullscreen-app-filters-design.md`

## Global Constraints

- 版本号本次升到 **1.1.2**，属于**未发布**改动：**只做本地提交，绝不 `git push`、不打 tag、不建 Release**（用户核验后再定）。
- 所有面向用户的文案、注释、CHANGELOG 用中文。
- 不改 `src/ERing/native/wheelhook.cpp` 与钩子协议，只在 Python 侧接线。
- 解释器固定用 `.venv/Scripts/python.exe`（系统 `python` 没有 PySide6）。
- 仓库没有 pytest，测试文件写成可直接执行的脚本：`test_*` 函数 + 文件末尾 `if __name__ == "__main__":` 逐条调用并 `print("ALL TESTS PASSED")`。
- 配置键名固定为 `fullscreen_whitelist`、`fullscreen_blacklist`，值均为字符串列表。
- 提交信息格式：`[月份.日期]改动描述`，本次为 `[11.2]`。

## Review Focus

按最可能咬到用户的顺序：

1. **窗口化的游戏/全屏应用**（进程在前台但窗口没占满显示器）→ 黑名单必须仍然压制，不受"是否全屏"影响。
2. **程序更新换来安装目录** → 旧路径条目失效，轮盘在该应用里重新出现；这是预期行为，设置页文案必须写清楚"程序更新后需要重新添加"。
3. **路径含中文、空格或大小写差异** → 仍要命中。
4. **用户手填的旧基名条目**（`chrome.exe`）→ 仍要命中，不能因为改成路径匹配就全废。
5. **前台是桌面/任务栏或取不到进程名** → 不能被误判成"永久压制"，轮盘在其他应用里要照常可用。

## 文件结构

| 文件 | 职责 |
|---|---|
| `src/ERing/app/fullscreen.py` | 取前台窗口/进程路径；名单判定纯函数 |
| `src/ERing/app/config.py` | 默认值与合并归一化 |
| `src/ERing/app/settings_dialog.py` | 两个名单列表控件、文件对话框、保存 |
| `src/ERing/app/application.py` | 钩子接线，调用新判定函数 |
| `tests/test_app_filters.py` | 判定与配置的离线测试 |
| `tests/test_settings_app_lists.py` | 设置页列表控件的离屏测试 |

---

### Task 1: 名单判定纯函数

**Files:**
- Modify: `src/ERing/app/fullscreen.py:35-101`
- Test: `tests/test_app_filters.py`（新建）

**Interfaces:**
- Produces:
  - `normalize_path(p: str) -> str` —— `os.path.normcase(os.path.normpath(p))`
  - `matches_entry(entry: str, path: str) -> bool` —— 条目含路径分隔符时比归一化全路径，否则比 exe 基名
  - `should_suppress(cfg: dict, path: str | None = None, name: str | None = None, fullscreen: bool | None = None) -> bool` —— 三个可选参数为 `None` 时现场取前台窗口信息
  - `foreground_process_path() -> str` —— 前台进程完整路径，失败返回 `""`
- Consumes: 现有 `foreground_is_fullscreen()` 保持不变。

- [ ] **Step 1: 写失败的测试**

```python
# tests/test_app_filters.py
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src" / "ERing"))

from app.fullscreen import matches_entry, normalize_path, should_suppress

GAME = r"C:\Games\game.exe"
OBS = r"C:\Tools\obs64.exe"
CHROME = r"C:\Program Files\Google\Chrome\Application\chrome.exe"


def cfg(wl=(), bl=(), on=True):
    return {"suppress_fullscreen": on, "fullscreen_whitelist": list(wl),
            "fullscreen_blacklist": list(bl)}


def test_blacklist_suppresses_regardless_of_fullscreen():
    c = cfg(bl=[OBS])
    assert should_suppress(c, path=OBS, fullscreen=False) is True
    assert should_suppress(c, path=OBS, fullscreen=True) is True


def test_blacklist_ignores_master_switch():
    c = cfg(bl=[OBS], on=False)
    assert should_suppress(c, path=OBS, fullscreen=False) is True


def test_fullscreen_without_list_hit_suppresses():
    c = cfg()
    assert should_suppress(c, path=CHROME, fullscreen=True) is True
    assert should_suppress(c, path=CHROME, fullscreen=False) is False


def test_whitelist_allows_when_fullscreen():
    c = cfg(wl=[GAME])
    assert should_suppress(c, path=GAME, fullscreen=True) is False


def test_blacklist_beats_whitelist():
    c = cfg(wl=[GAME], bl=[GAME])
    assert should_suppress(c, path=GAME, fullscreen=True) is True


def test_path_case_and_separator_insensitive():
    c = cfg(bl=[OBS])
    assert should_suppress(c, path=r"C:\TOOLS\OBS64.EXE", fullscreen=False) is True
    assert normalize_path(r"C:\Tools\..\Tools\obs64.exe") == normalize_path(OBS)


def test_legacy_basename_entry_still_matches():
    c = cfg(wl=["chrome.exe"])
    assert should_suppress(c, path=CHROME, fullscreen=True) is False
    assert matches_entry("obs64.exe", OBS) is True


def test_unknown_foreground_is_conservative_only_when_fullscreen():
    c = cfg(bl=[OBS])
    assert should_suppress(c, path="", name="", fullscreen=True) is True
    assert should_suppress(c, path="", name="", fullscreen=False) is False


def test_chinese_and_space_in_path():
    p = r"D:\学习 资料\工具\截图.exe"
    c = cfg(bl=[p])
    assert should_suppress(c, path=p, fullscreen=False) is True


if __name__ == "__main__":
    test_blacklist_suppresses_regardless_of_fullscreen()
    test_blacklist_ignores_master_switch()
    test_fullscreen_without_list_hit_suppresses()
    test_whitelist_allows_when_fullscreen()
    test_blacklist_beats_whitelist()
    test_path_case_and_separator_insensitive()
    test_legacy_basename_entry_still_matches()
    test_unknown_foreground_is_conservative_only_when_fullscreen()
    test_chinese_and_space_in_path()
    print("ALL TESTS PASSED")
```

- [ ] **Step 2: 运行确认失败**

Run: `.venv/Scripts/python.exe tests/test_app_filters.py`
Expected: `ImportError: cannot import name 'should_suppress'`

- [ ] **Step 3: 实现**

在 `src/ERing/app/fullscreen.py` 中：
- `foreground_process_path()`：沿用 `OpenProcess` + `QueryFullProcessImageNameW`，**保留完整路径**；`foreground_process_name()` 改为 `foreground_process_path().rsplit("\\", 1)[-1].lower()`，行为不变。
- `matches_entry(entry, path)`：`entry` 归一化后若含 `os.sep` 或 `/`，与 `normalize_path(path)` 相等即命中；否则与 `path` 的基名比（都过 `normcase`）。
- `should_suppress(...)` 判定顺序：黑名单命中 → True；`cfg` 取不到 `suppress_fullscreen` 视为 True；非全屏 → False；白名单命中 → False；其余 True。参数为 `None` 的字段现场取前台（`foreground_process_path()` / `foreground_is_fullscreen()`），异常一律返回 False。
- `fullscreen_should_hide(whitelist=None)` 保留为薄包装（白名单转成 cfg 调 `should_suppress`），避免遗漏的旧调用点报错。

- [ ] **Step 4: 运行确认通过**

Run: `.venv/Scripts/python.exe tests/test_app_filters.py`
Expected: `ALL TESTS PASSED`

- [ ] **Step 5: 提交**

```bash
git add src/ERing/app/fullscreen.py tests/test_app_filters.py
git commit -m "[11.2]新增应用名单判定（白名单/黑名单，按路径匹配）"
```

---

### Task 2: 配置默认值与归一化

**Files:**
- Modify: `src/ERing/app/config.py:34-35`（DEFAULTS）、`src/ERing/app/config.py:50-71`（migrate）
- Test: `tests/test_app_filters.py`（追加）

**Interfaces:**
- Produces: `config.migrate(loaded: dict) -> dict`，保证两个名单键**永远是字符串列表**（`None`、字符串、数字一律归一为空列表）。
- Consumes: Task 1 无依赖。

- [ ] **Step 1: 追加失败的测试**

```python
def test_config_always_gives_lists():
    import app.config as config

    c = config.migrate({})
    assert c["fullscreen_blacklist"] == []
    assert c["fullscreen_whitelist"] == []

    c = config.migrate({"fullscreen_blacklist": None, "fullscreen_whitelist": "C:\\a.exe"})
    assert c["fullscreen_blacklist"] == []
    assert c["fullscreen_whitelist"] == []      # 非列表一律丢弃，避免字符串被逐字符遍历

    c = config.migrate({"fullscreen_blacklist": ["  C:\\a.exe  ", ""]})
    assert c["fullscreen_blacklist"] == [r"C:\a.exe"]   # 剥空白、丢空串
```

- [ ] **Step 2: 运行确认失败**

Run: `.venv/Scripts/python.exe tests/test_app_filters.py`
Expected: `KeyError: 'fullscreen_blacklist'`（或断言失败）

- [ ] **Step 3: 实现**

- `DEFAULTS` 增加 `"fullscreen_blacklist": [],`，并把 `fullscreen_whitelist` 的注释改成"绝对路径列表（不含路径分隔符时按 exe 名兼容）"。
- `migrate()` 末尾加一个局部辅助：两个键各自过滤成"非空字符串列表"——`isinstance(v, list)` 为假则 `[]`，元素 `str(x).strip()` 后丢弃空串。

- [ ] **Step 4: 运行确认通过**

Run: `.venv/Scripts/python.exe tests/test_app_filters.py`
Expected: `ALL TESTS PASSED`

- [ ] **Step 5: 提交**

```bash
git add src/ERing/app/config.py tests/test_app_filters.py
git commit -m "[11.2]配置新增黑名单并归一化名单字段"
```

---

### Task 3: 设置页两个名单 + 资源管理器选择

**Files:**
- Modify: `src/ERing/app/settings_dialog.py:710-727`（构建）、`src/ERing/app/settings_dialog.py:884-888`（保存）
- Test: `tests/test_settings_app_lists.py`（新建）

**Interfaces:**
- Produces:
  - `SettingsDialog._add_paths(widget: QListWidget, paths: list[str]) -> None`（staticmethod，按 `normalize_path` 去重，`Qt.UserRole` 存完整路径，显示基名，tooltip 为完整路径）
  - `SettingsDialog._list_paths(widget: QListWidget) -> list[str]`（staticmethod，按行序取回路径）
  - 实例属性 `self.whitelist_list`、`self.blacklist_list`（均为 `QListWidget`）
- Consumes: `normalize_path`（Task 1）、`config.migrate` 的列表保证（Task 2）。

- [ ] **Step 1: 写失败的测试**

```python
# tests/test_settings_app_lists.py
import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src" / "ERing"))

from PySide6.QtWidgets import QApplication, QListWidget, QListWidgetItem

import app.config as config
from app.settings_dialog import SettingsDialog

A = r"C:\Tools\obs64.exe"
B = r"C:\Games\game.exe"


def make_dialog():
    cfg = config.migrate({"fullscreen_whitelist": [B], "fullscreen_blacklist": [A]})
    return SettingsDialog(cfg)


def test_lists_are_populated_from_config():
    app = QApplication.instance() or QApplication([])
    dlg = make_dialog()
    assert dlg.whitelist_list.count() == 1
    assert dlg.blacklist_list.count() == 1
    assert SettingsDialog._list_paths(dlg.whitelist_list) == [B]
    assert SettingsDialog._list_paths(dlg.blacklist_list) == [A]
    assert dlg.blacklist_list.item(0).toolTip() == A
    assert dlg.blacklist_list.item(0).text().lower() == "obs64.exe"
    dlg.deleteLater()
    app.processEvents()


def test_add_paths_dedupes_and_ignores_empty():
    app = QApplication.instance() or QApplication([])
    w = QListWidget()
    SettingsDialog._add_paths(w, [A, A.upper(), "", "  "])
    assert SettingsDialog._list_paths(w) == [A]
    app.processEvents()


if __name__ == "__main__":
    test_lists_are_populated_from_config()
    test_add_paths_dedupes_and_ignores_empty()
    print("ALL TESTS PASSED")
```

- [ ] **Step 2: 运行确认失败**

Run: `.venv/Scripts/python.exe tests/test_settings_app_lists.py`
Expected: `AttributeError: type object 'SettingsDialog' has no attribute '_add_paths'`

- [ ] **Step 3: 实现**

- 用 private helper `_app_list_block(parent_layout, label, paths)` 生成"标签 + 列表 + 添加/移除按钮"的竖排块；两个块放进现有 `fs_card`，替代 `fullscreen_edit`。
- 「添加应用…」调 `QFileDialog.getOpenFileNames(self, "选择应用程序", start_dir, "应用程序 (*.exe)")`，`start_dir` 取上一次选择目录（实例属性，初始为空）；结果交给 `_add_paths`。
- 「移除选中」按 `selectedItems()` 删除，多选可用。
- 提示文案改为两句：白名单"全屏时仍可呼出"；黑名单"不论是否全屏都不弹轮盘；程序更新换了安装目录后需要重新添加"。
- 保存（原 884-888）改为 `self.cfg["fullscreen_whitelist"] = self._list_paths(self.whitelist_list)`，黑名单同理。

- [ ] **Step 4: 运行确认通过**

Run: `.venv/Scripts/python.exe tests/test_settings_app_lists.py`
Expected: `ALL TESTS PASSED`

- [ ] **Step 5: 提交**

```bash
git add src/ERing/app/settings_dialog.py tests/test_settings_app_lists.py
git commit -m "[11.2]设置页改用名单列表并支持资源管理器选择应用"
```

---

### Task 4: 钩子接线

**Files:**
- Modify: `src/ERing/app/application.py:118-120`、`src/ERing/app/application.py:145-148`、`src/ERing/app/application.py:214-244`
- Test: 无新增单测（走 `--smoke` 冒烟）

**Interfaces:**
- Consumes: `should_suppress(cfg)`（Task 1）。
- Produces: 方法名 `_app_suppressed()` / `_sync_app_suppress()`，供定时器与钩子回调引用。

- [ ] **Step 1: 改接线**

- `set_isolated_check(self._app_suppressed)`。
- `_fs_suppress_timer.timeout.connect(self._sync_app_suppress)`，定时器 300ms 不变。
- 两个方法体统一为 `return should_suppress(self.cfg)` / `target = bool(should_suppress(self.cfg))`，异常兜底返回 False。
- 注释同步为"白名单/黑名单 + 全屏判定"。

- [ ] **Step 2: 冒烟验证**

Run: `.venv/Scripts/python.exe src/ERing/main.py --smoke`（4 秒后自动退出）
Expected: 无 traceback；`data/` 日志里出现 `hook backend:` 与 `fullscreen suppress -> ...` 字样。

- [ ] **Step 3: 提交**

```bash
git add src/ERing/app/application.py
git commit -m "[11.2]钩子改用名单判定（黑名单不受全屏限制）"
```

---

### Task 5: 版本号与 CHANGELOG（本地，不推送）

**Files:**
- Modify: `VERSION`、`CHANGELOG.md:1-6`
- 生成（不入库）：`src/ERing/app/build_info.py`

- [ ] **Step 1: 改版本**

`VERSION` 写入 `v1.1.2`。

- [ ] **Step 2: 写 CHANGELOG**

在 `## [1.1.1]` 之前插入：

```markdown
## [1.1.2] - 2026-11-02（未发布）

### 新增
- **全屏应用名单**：「全屏 / 独占应用」由单个文本框升级为白名单 + 黑名单两条独立名单，
  可用 Windows 资源管理器直接选择 `.exe` 加入，按完整路径匹配（大小写、路径写法差异不影响命中）；
- **黑名单**：名单内的应用不论是否全屏都不弹出轮盘，不受「全屏时隐藏」开关影响；
- 旧的手填进程名（如 `chrome.exe`）仍然有效，无需重新录入。
```

- [ ] **Step 3: 本地冒烟版本信息**

Run: `ERING_VERSION=v1.1.2 .venv/Scripts/python.exe tools/stamp_build_info.py`（`build_info.py` 在 `.gitignore` 内）
Expected: 命令退出码 0。

- [ ] **Step 4: 提交（不推送）**

```bash
git add VERSION CHANGELOG.md
git commit -m "[11.2]版本号 1.1.2（未发布，待核验）"
```

---

## 验证清单（交付前）

- `.venv/Scripts/python.exe tests/test_app_filters.py` → `ALL TESTS PASSED`
- `.venv/Scripts/python.exe tests/test_settings_app_lists.py` → `ALL TESTS PASSED`
- `.venv/Scripts/python.exe src/ERing/main.py --smoke` → 4 秒退出、无 traceback
- `git status` 干净、`git log --oneline -5` 只有本地提交，**`git log origin/main..HEAD` 显示未推送**
