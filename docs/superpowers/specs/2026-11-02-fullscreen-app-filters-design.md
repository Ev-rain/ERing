# 全屏应用名单：白名单 / 黑名单（按完整路径匹配）

日期：2026-11-02　规模：小改动（短版设计）

## 意图与理由

现有"全屏 / 独占应用"只有一个逗号分隔的文本框，用户得自己去任务管理器抄进程名。要做的是：拆成两条独立名单，都能用资源管理器的文件对话框挑 `.exe` 加入，并且按**完整路径**匹配（用户现有名单为空，没有迁移负担，路径能区分同名的不同程序）。黑名单的语义是**不论是否全屏，都不弹轮盘**。

## 现状（改动前）

- `src/ERing/app/fullscreen.py:88-99`：`fullscreen_should_hide(whitelist)`——全屏且不在白名单则压制；取不到进程名时保守返回 True。
- `src/ERing/app/application.py:120`：右键按下瞬间的 `set_isolated_check(self._fullscreen_suppressed)`（放行真实点击）。
- `src/ERing/app/application.py:145-148`：300ms 轮询 `_sync_fullscreen_suppress` → `hook.set_suppress()`。
- `src/ERing/app/settings_dialog.py:710-727` 构建单个文本框，`884-888` 保存时按逗号切分。
- `src/ERing/app/config.py:34-35`：`suppress_fullscreen`、`fullscreen_whitelist`。

## 目标

1. 白名单：全屏时仍可呼出轮盘（语义不变）
2. 黑名单：**任何时候都不弹轮盘**
3. 两条名单都能通过资源管理器（`QFileDialog.getOpenFileNames`，过滤 `*.exe`）添加，列表内可移除单项
4. 按完整路径匹配，大小写与路径写法差异不影响命中

## 非目标

- 不做"从当前前台窗口捕获"的入口（可作后续增量）
- 不改 C++ 钩子协议、不新增钩子事件
- 不支持通配符、目录、命令行参数匹配

## 反目标（做了就算失败）

- 黑名单受"全屏时隐藏"开关牵制（两条规则必须独立）
- 添加应用后仍需手抄进程名
- 改动破坏 `suppress_fullscreen` 关闭时的既有行为

## 方案比较

| 方案 | 存什么 | 结论 |
|---|---|---|
| A | exe 名 | 同名程序无法区分；本次无历史数据，放弃 |
| **B（采用）** | 完整路径 | 用户名单为空，迁移成本为零；能区分同名程序 |
| C | 保留文本框 + 浏览按钮 | 删单条、看内容都难受，不算优化 |

## 决定

- 配置键：`fullscreen_whitelist` / `fullscreen_blacklist`，值均为**绝对路径字符串列表**
- 归一化：`os.path.normcase(os.path.normpath(p))`
- **兼容旧条目**（我的判断，非用户决定）：条目里不含路径分隔符时按 exe 基名比较，使手填的 `chrome.exe` 仍可用
- 判定顺序：
  1. 命中黑名单 → 压制
  2. `suppress_fullscreen` 为假 → 不压制
  3. 非全屏 → 不压制
  4. 命中白名单 → 不压制
  5. 其余 → 压制（含取不到进程名的保守分支）
- 黑名单不受 `suppress_fullscreen` 开关影响

## 实现要点

- `src/ERing/app/fullscreen.py`
  - 新增 `foreground_process_path()`：`QueryFullProcessImageNameW` 保留全路径；`foreground_process_name()` 由路径派生，供兼容比较
  - 判定抽成纯函数（可离线测试）：`matches_entry(entry, path, name)`、`should_suppress(cfg, path=None, name=None)`
  - 保留 `fullscreen_should_hide()` 作为薄包装，避免外部调用点全部重写
- `src/ERing/app/config.py`：`DEFAULTS` 增加 `"fullscreen_blacklist": []`；`migrate()` 无须特殊处理（缺失键由合并补齐）
- `src/ERing/app/settings_dialog.py`
  - 用两个 `QListWidget` 替换文本框；每块配「添加应用…」「移除选中」
  - 列表项显示 exe 文件名，tooltip 显示完整路径，`Qt.UserRole` 存完整路径
  - 添加时按归一化路径去重；`getOpenFileNames` 支持多选
  - 保存时把两个列表的 `UserRole` 收成路径列表写回配置
- `src/ERing/app/application.py`：`_fullscreen_suppressed()` 与 `_sync_fullscreen_suppress()` 改调 `should_suppress(self.cfg)`（方法名一并改为 `_app_suppressed` / `_sync_app_suppress`，注释同步）
- `tests/test_app_filters.py`：离线纯函数测试（黑名单命中、非全屏不压制、白名单放行、黑名单优先于白名单、`suppress_fullscreen=False` 时黑名单仍生效、旧基名条目兼容、大小写差异命中）

## 风险与代价

- 程序更新换安装目录后条目失效，需要重新添加——在设置页提示文案里写明
- 每次右键与每 300ms 轮询都要取前台进程路径（现状已在做，开销不变）

## 留给实现者

- 列表项的视觉细节（高度、图标）沿用现有卡片风格
- 是否给列表加上"双击移除"快捷操作
