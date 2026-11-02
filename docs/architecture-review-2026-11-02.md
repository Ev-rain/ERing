# 架构审查记录（2026-11-02）

审查范围：`src/ERing` 全量（约 4.6k 行 Python + 一份 C++ 钩子）。
方式：静态通读 + 逐条核对调用点 + 可复现的小实验；结论按「本次已改 / 留到以后」分开，
留到以后的每一条都带路径和行号，下次接着做不用重新查。

## 一、本次已改

| 问题 | 位置 | 处理 |
| --- | --- | --- |
| 设置面板同时管 QSS、pip 安装、名单控件、更新检查、配置回写（998 行） | `src/ERing/app/settings_dialog.py` | 抽出 `app/updater.py`、`app/ocr_install.py`、`app/qtasync.py`，文件降到约 900 行 |
| 三套重复的后台线程封装，语义还不一致 | `application.py` / `settings_dialog.py` | 合并到 `app/qtasync.py` 的 `AsyncWorker` / `CallbackWorker` |
| 钩子回退/重启时丢掉「当前该不该压制」，全屏游戏里仍会吞右键 | `application.py` 的 `_start_hook`、`_check_hook_health` | 新增 `_install_hook()`，一次性补齐阈值、放行判定、压制状态 |
| `MouseHook.stop()` 不等线程退出，紧接着的 `start()` 静默空转 | `src/ERing/app/mouse_hook.py` | `stop(timeout=1.0)` join 后清引用并复位 `installed` |
| 回调异常只复位 `_busy`，日志里零痕迹 | `application.py` 的 `_on_worker_done`、`_check_hook_health` | 记 `callback failed: ...` + traceback，并提示「详情见日志」 |
| 配置没有类型/范围校验，一个坏值就让程序起不来 | `src/ERing/app/config.py` | 新增 `SCHEMA` + `_coerce()` + `sanitize()`，`Config.__setitem__` 复用同一套规则 |
| 录屏目录解析与 `startfile` 重复四处，错误处理口径不一 | `application.py`、`settings_dialog.py` | 收敛到 `app/paths.py` 的 `recordings_dir()` / `open_in_explorer()` |
| 无引用代码与重复初始化 | `deepseek.py` / `translate.py` / `fullscreen.py` / `main.py` | 删 `fetch_balance_short`、`clear_cache`、`fullscreen_should_hide` 与重复的 `install_tls()` |
| 测试各自为战，没有统一入口 | `tests/` | 新增 `tests/run_all.py`，9 个脚本一次跑完并汇总 |

回归入口：`.venv\Scripts\python.exe tests\run_all.py`。

## 二、留到以后（按收益排序）

1. **录屏停止阻塞 GUI 线程最长 8 秒** — `src/ERing/app/recorder.py:89-105`，调用点
   `src/ERing/app/application.py`（`_stop_recording`、退出路径）。
   建议拆 `request_stop()`（写 `"q"`）+ `wait_finished(timeout)`，把等待挪进 `CallbackWorker`。
2. **`_save()` 手抄 20 多个配置键** — `settings_dialog.py`（保存段）。
   建议每页实现 `collect() -> dict`，`Config.update()` 只接受已知键并复用新的校验层。
3. **截屏在 GUI 线程抓整屏** — `src/ERing/app/screenshot.py:30-37`、`:95-117`。
   录屏模式其实只要矩形，却仍整屏 `mss.grab`；建议 `record_mode=True` 时跳过抓图。
4. **余额请求可能叠加** — `settings_dialog.py` 的 `_query_balance` 与 `deepseek.py:195-211`。
   建议 provider 增加 `_inflight/_pending`，force 只置 pending，设置页改为监听 `on_update`。
5. **事件用 20ms 轮询队列** — `application.py` 的 `_poll`/`self.events`。
   可改成钩子线程直接 `emit` 信号（`Worker` 已证明跨线程 emit 可用），需真机验证 C++ 回调线程。
6. **`ScreenTranslatorApp` 是上帝对象**（30+ 方法）— `application.py:85-593`。
   建议先抽 `HookRuntime`（start/ensure_alive/set_suppressed/install），把上面第 3、4 类问题圈进一个可测单元。
7. **设置面板按页拆模块** — `settings_dialog.py` 仍是最大单文件，页面装配与业务混杂。
8. **`tests/` 样板重复** — 9 个脚本各自 `sys.path.insert` + `_utf8_console()`；
   可再抽 `tests/_support.py`，并把名单逻辑的测试从「构造整个对话框」降级为纯函数测试。

## 三、两条容易再踩的坑

- **打包上下文**：新模块都是包内静态 import，PyInstaller 会自动跟随，不需要加 `--hidden-import`；
  但别改成 `importlib` 动态导入，否则要同步改 `build.bat`。
- **低完整性沙箱**：从沙箱化宿主（DSH 工作区等）启动的进程是 Low IL，
  托盘图标注册与低层鼠标钩子都会被 UIPI 拦掉，此时「没图标 / 轮盘呼不出」不是代码问题——
  要从资源管理器、Win+R 或以管理员身份启动再验证。程序启动自检会弹窗提示（见 `app/integrity.py`）。
