# -*- coding: utf-8 -*-
"""主程序逻辑：右键轮盘 + 截图/选中文本翻译 + 区域录屏 + DeepSeek 余额。
入口（含 DPI 感知设置）见根目录 main.py。"""
import ctypes
import os
import queue
import sys
import threading
import time
import traceback
from ctypes import wintypes
from pathlib import Path

_user32 = ctypes.windll.user32
_user32.GetForegroundWindow.argtypes = []
_user32.GetForegroundWindow.restype = wintypes.HWND
_user32.GetWindowThreadProcessId.argtypes = [
    wintypes.HWND, ctypes.POINTER(wintypes.DWORD),
]
_user32.GetWindowThreadProcessId.restype = wintypes.DWORD
_user32.SetForegroundWindow.argtypes = [wintypes.HWND]
_user32.SetForegroundWindow.restype = wintypes.BOOL
_user32.SendMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
_user32.SendMessageW.restype = ctypes.c_ssize_t
_user32.GetClassNameW.argtypes = [wintypes.HWND, ctypes.c_wchar_p, ctypes.c_int]
_user32.GetClassNameW.restype = ctypes.c_int
_user32.mouse_event.argtypes = [
    wintypes.DWORD, wintypes.DWORD, wintypes.DWORD, wintypes.DWORD, ctypes.c_size_t,
]

from PySide6.QtCore import QEvent, QObject, QPoint, Qt, QTimer, Signal
from PySide6.QtGui import QCursor
from PySide6.QtWidgets import QApplication, QDialog, QWidget

from app.config import Config, CONFIG_DIR
from app.deepseek import BalanceProvider
from app.dpi import phys_to_logical, primary_dpr
from app.log_utils import configure as configure_logging
from app.log_utils import log
from app.mouse_hook import MouseHook
from app.native_hook import NativeHook
from app.ocr import OcrEngine
from app.result_window import ResultWindow
from app.recorder import Recorder
from app.screenshot import ScreenshotOverlay
from app.settings_dialog import SettingsDialog
from app.stop_button import StopButton
from app.text_grab import get_selected_text
from app.toast import Toast
from app.translate import translate_text
from app.tray import Tray, make_icon
from app.wheel import ANIM_SPEED_MS, WheelOverlay
from app.window_icon import apply_to_window, set_app_user_model_id


class Worker(QObject):
    """在工作线程执行任务，结果安全地回到 Qt 主线程。"""

    done = Signal(object)

    def run(self, fn, callback):
        def target():
            try:
                result = fn()
            except Exception as exc:  # noqa: BLE001
                result = ("error", str(exc))
            self.done.emit((callback, result))

        threading.Thread(target=target, daemon=True).start()


class _WindowIconFilter(QObject):
    """窗口显示时用 Win32 强灌托盘图标，确保任务栏不显示 Python 图标。"""

    def eventFilter(self, obj, ev):
        if ev.type() == QEvent.Type.Show and isinstance(obj, QWidget) and obj.isWindow():
            try:
                apply_to_window(int(obj.winId()))
            except Exception:  # noqa: BLE001
                pass
        return False


class ScreenTranslatorApp:
    def __init__(self, argv):
        # pythonw 下默认归入 Python 应用组导致任务栏显示 Python 图标
        set_app_user_model_id("cn.etranslate.wheel.1")
        self.qt = QApplication(argv)
        self.qt.setWindowIcon(make_icon())  # 所有窗口统一使用托盘图标
        self.qt.setQuitOnLastWindowClosed(False)
        self._icon_filter = _WindowIconFilter(self.qt)
        self.qt.installEventFilter(self._icon_filter)
        self.cfg = Config()
        configure_logging(self.cfg["enable_logging"])
        log("=== 轮盘翻译启动 ===")
        self.events = queue.Queue()
        self.balance = BalanceProvider(
            get_key=lambda: self.cfg["deepseek"]["api_key"],
            on_update=lambda: self.events.put(("balance",)),
        )
        self.worker = Worker()
        self.worker.done.connect(self._on_worker_done)
        self.ocr = OcrEngine(engine=self.cfg["ocr_engine"])
        self._busy = False
        self._capture_mode = "ocr"  # ocr | save

        hook_cls = NativeHook if NativeHook.available() else MouseHook
        log(f"hook backend: {'native C++' if hook_cls is NativeHook else 'python'}")
        self.hook = hook_cls(
            on_wheel_trigger=lambda x, y, ox, oy: self.events.put(("trigger", x, y, ox, oy)),
            on_wheel_release=lambda x, y: self.events.put(("release", x, y)),
            on_left_click=lambda x, y: self.events.put(("left_click", x, y)),
            on_mouse_move=lambda x, y: self.events.put(("mousemove", x, y)),
            on_normal_up=lambda x, y: self.events.put(("normal_up", x, y)),
        )
        self._apply_drag_threshold()

        self.wheel = WheelOverlay()
        self.wheel.action_chosen.connect(self.on_action)
        self.screenshot = ScreenshotOverlay()
        self.screenshot.region_captured.connect(self.on_region_captured)
        self.screenshot.region_rect_selected.connect(self.on_record_region)
        self.screenshot.cancelled.connect(self._on_screenshot_cancelled)
        self.recorder = Recorder()
        self.stop_btn = StopButton()
        self.stop_btn.stopped.connect(self._stop_recording)
        self.stop_btn.moved.connect(self._save_stop_pos)
        self.result = ResultWindow(self.cfg)
        self.toast = Toast()
        self.tray = Tray(self.qt, self)
        self._settings_dlg = None

        self.timer = QTimer()
        self.timer.timeout.connect(self._poll)
        self.timer.start(20)
        self._last_cursor = None
        self._last_hook_events = 0
        self._health_timer = QTimer()
        self._health_timer.timeout.connect(self._check_hook_health)
        self._health_timer.start(3000)

    # ---------- 入口 ----------
    def run(self):
        self.tray.show()
        self.hook.start()
        self.balance.refresh()
        self.ocr.preload()  # 后台预热 OCR 模型，首次截图不再干等
        self.tray.first_run_notice()
        if "--smoke" in sys.argv:
            QTimer.singleShot(4000, self.qt.quit)
        return self.qt.exec()

    # ---------- 钩子线程 -> Qt 主线程 ----------
    def _poll(self):
        try:
            while True:
                ev = self.events.get_nowait()
                kind = ev[0]
                if kind == "trigger":
                    if not self._busy:
                        # 圆心 = 按下右键的位置；方向判定以此为基准，严格对应拖动方向
                        p = phys_to_logical(ev[3], ev[4])
                        self._capture_focus()
                        self.wheel.show_at(
                            p, self.cfg["wheel_items"],
                            center_text=self.balance.display_text(),
                            usage_text=self._usage_text(),
                            theme=self.cfg["wheel_theme"],
                            escape_enabled=self.cfg["enable_outer_escape"],
                            escape_distance=self.cfg["outer_escape_distance"],
                            anim_duration=ANIM_SPEED_MS.get(
                                self.cfg["wheel_anim_speed"], 170
                            ),
                        )
                        self.balance.refresh(force=True)  # 打开轮盘即查最新余额
                elif kind == "release":
                    p = phys_to_logical(ev[1], ev[2])
                    self.wheel.resolve_release(p.x(), p.y())
                    self._restore_focus(clear=False)  # 保留原前台句柄，供后续动作恢复
                elif kind == "left_click":
                    p = phys_to_logical(ev[1], ev[2])
                    self._maybe_close_result(p.x(), p.y())
                elif kind == "normal_up":
                    self._replay_right_click()
                elif kind == "mousemove":
                    if not self._busy and self.wheel.isVisible():
                        p = phys_to_logical(ev[1], ev[2])
                        self.wheel.update_hover(p.x(), p.y())
                elif kind == "balance":
                    self.wheel.set_center_text(
                        self.balance.display_text(), self._usage_text()
                    )
                    if self._settings_dlg is not None:
                        try:
                            self._settings_dlg.update_usage(self.balance.consumption())
                        except Exception:
                            pass
        except queue.Empty:
            pass

    # ---------- 轮盘动作 ----------
    def on_action(self, index):
        self.hook.set_suppress(False)
        names = self.cfg["wheel_items"]
        if index >= len(names):
            return
        name = names[index]
        log(f"wheel action -> {name}")
        if name == "翻译":
            self.start_smart_translate()
        elif name in ("录屏", "截图"):
            self.start_record_flow()
        elif name == "设置":
            # 延迟到轮盘完全关闭、焦点归还之后再打开，避免嵌套事件循环/焦点混乱
            QTimer.singleShot(0, self.open_settings)
        elif name == "退出":
            self.qt.quit()

    # ---------- 智能翻译 ----------
    def start_smart_translate(self):
        self._busy = True
        self.worker.run(get_selected_text, self._on_text_probe)

    def _on_text_probe(self, result):
        if isinstance(result, tuple) and result and result[0] == "error":
            self._busy = False
            self._show_toast("获取文本失败：" + str(result[1]), 4000)
            return
        text = (result or "").strip()
        if text:
            self._do_translate(text)
        else:
            self.start_screenshot_capture(mode="ocr")

    def _do_translate(self, text):
        self._busy = True
        self._show_toast("翻译中…")
        cfg_snapshot = self.cfg.data
        self.worker.run(
            lambda: translate_text(text, cfg_snapshot),
            lambda r: self._finish_translate(text, r),
        )

    def _finish_translate(self, original, result):
        self._busy = False
        if isinstance(result, tuple) and result and result[0] == "error":
            self._show_toast("翻译失败：" + str(result[1]), 4000)
            return
        ok, translated, provider = result
        if ok:
            self.result.show_result(original, translated, provider)
        else:
            self._show_toast("翻译失败：" + translated, 4000)

    # ---------- 截图 ----------
    def start_screenshot_capture(self, mode="ocr"):
        self._busy = True
        self._capture_mode = mode
        self.toast.hide()  # 确保提示不会出现在截图中
        self.screenshot.start_capture()

    def start_record_flow(self):
        """录屏：框选区域 -> ffmpeg gdigrab 录制（参考 JamTools）。"""
        self._busy = True
        self._capture_mode = "record"
        self.toast.hide()
        self.screenshot.start_capture(record_mode=True)

    def on_record_region(self, rect):
        self._busy = False
        self._restore_focus()
        from app.dpi import logical_to_physical

        phys = logical_to_physical(rect)
        cfg_dir = str(self.cfg["record_dir"]).strip()
        folder = Path(cfg_dir) if cfg_dir else CONFIG_DIR / "recordings"
        fmt = self.cfg["record_format"]
        ext = "gif" if fmt == "gif" else "mp4"
        out = folder / f"录屏_{time.strftime('%Y%m%d_%H%M%S')}.{ext}"
        try:
            self.recorder.start(
                phys, out,
                fps=int(self.cfg["record_fps"]),
                draw_mouse=bool(self.cfg["record_mouse"]),
                fmt=fmt,
            )
        except Exception as exc:  # noqa: BLE001
            self._show_toast(f"录屏启动失败：{exc}", 4000)
            return
        saved = self.cfg["stop_button_pos"]
        pos = QPoint(saved[0], saved[1]) if isinstance(saved, list) and len(saved) == 2 else None
        self.stop_btn.show_at_saved(pos)
        self._show_toast("录制中… 点击红色 ■ 停止", 2500)

    def _save_stop_pos(self, pos):
        self.cfg["stop_button_pos"] = [pos.x(), pos.y()]
        self.cfg.save()

    def open_record_dir(self):
        """打开录屏文件保存位置（资源管理器）。"""
        cfg_dir = str(self.cfg["record_dir"]).strip()
        folder = Path(cfg_dir) if cfg_dir else CONFIG_DIR / "recordings"
        try:
            folder.mkdir(parents=True, exist_ok=True)
            os.startfile(str(folder))
        except Exception as exc:  # noqa: BLE001
            log(f"open record dir failed: {exc}")

    def _stop_recording(self):
        path = self.recorder.stop()
        if path:
            self._show_toast(f"已保存：{path}", 4000)
        return path

    def _on_screenshot_cancelled(self):
        self._busy = False
        self._show_toast("已取消")
        self._restore_focus()

    def on_region_captured(self, image):
        self._restore_focus()
        if self._capture_mode == "save":
            self._save_screenshot(image)
            return
        self._busy = True
        self.worker.run(lambda: self.ocr.recognize(image), self._on_ocr_done)

    def _on_ocr_done(self, result):
        if isinstance(result, tuple) and result and result[0] == "error":
            self._busy = False
            self._show_toast("识别失败：" + str(result[1]), 4000)
            return
        text = (result or "").strip()
        if not text:
            self._busy = False
            self._show_toast("未识别到文字", 3000)
            return
        self._do_translate(text)

    def _save_screenshot(self, image):
        self._busy = False
        folder = Path(os.environ.get("USERPROFILE", str(Path.home()))) / "Pictures" / "轮盘翻译"
        try:
            folder.mkdir(parents=True, exist_ok=True)
            path = folder / f"截图_{time.strftime('%Y%m%d_%H%M%S')}.png"
            image.save(str(path))
            QApplication.clipboard().setImage(image)
            self._show_toast(f"已保存并复制到剪贴板\n{path.name}", 3000)
        except Exception as exc:  # noqa: BLE001
            self._show_toast("保存截图失败：" + str(exc), 4000)

    # ---------- 其他 ----------
    def open_settings(self):
        self.hook.set_suppress(False)
        dlg = self._settings_dlg
        if dlg is not None and (dlg.isVisible() or self.cfg["close_to_tray"]):
            if not dlg.isVisible():
                dlg.show()
            dlg.raise_()
            dlg.activateWindow()
            return
        dlg = SettingsDialog(self.cfg, None, self.balance)
        dlg.setWindowFlag(Qt.WindowType.Window, True)  # 普通顶层窗口，避免弹出式/工具窗属性
        dlg.setWindowState(dlg.windowState() & ~Qt.WindowState.WindowMinimized)
        dlg.finished.connect(self._on_settings_finished)
        self._settings_dlg = dlg
        # ALT 键技巧：让本进程获得前台权限，确保设置窗口正常激活显示（不最小化、不藏在后面）
        try:
            _user32.keybd_event(0x12, 0, 0, 0)
            _user32.keybd_event(0x12, 0, 2, 0)
        except Exception:
            pass
        dlg.show()
        dlg.raise_()
        dlg.activateWindow()
        log("settings opened (non-modal)")

    def _on_settings_finished(self, result):
        dlg = self._settings_dlg
        self._settings_dlg = None
        if result == QDialog.DialogCode.Accepted:
            self._apply_drag_threshold()
            self.balance.refresh(force=True)  # Key 可能变了，立即刷新余额
            self.ocr.set_mode(self.cfg["ocr_engine"])
            self.ocr.preload()  # 切换引擎后后台预热
        self._restore_focus()
        log(f"settings closed result={result}")

    def _apply_drag_threshold(self):
        # 配置里是逻辑像素，钩子测的是物理像素，按主屏缩放换算
        self.hook.set_drag_threshold(
            int(self.cfg["drag_threshold"] * primary_dpr())
        )

    def _maybe_close_result(self, x, y):
        if self.result.isVisible():
            if not self.result.geometry().contains(QPoint(x, y)):
                self.result.hide()

    def _capture_focus(self):
        try:
            self._focus_hwnd = _user32.GetForegroundWindow()
        except Exception:
            self._focus_hwnd = 0

    def _restore_focus(self, clear=True):
        """轮盘/覆盖层可能抢走前台焦点，关闭后把焦点还给原来的窗口。"""
        if not getattr(self, "_focus_hwnd", 0):
            return
        try:
            cur = _user32.GetForegroundWindow()
            pid = ctypes.c_ulong()
            _user32.GetWindowThreadProcessId(cur, ctypes.byref(pid))
            if pid.value == os.getpid() and cur != self._focus_hwnd:
                # 先模拟一次 ALT 键，提高 SetForegroundWindow 的成功率
                _user32.keybd_event(0x12, 0, 0, 0)
                _user32.keybd_event(0x12, 0, 2, 0)
                _user32.SetForegroundWindow(self._focus_hwnd)
        except Exception:
            pass
        if clear:
            self._focus_hwnd = 0

    def _on_worker_done(self, payload):
        callback, result = payload
        try:
            callback(result)
        except Exception:  # noqa: BLE001
            self._busy = False

    def _show_toast(self, text, ms=1800):
        self.toast.show_message(text, ms)

    def _usage_text(self):
        c = self.balance.consumption()
        if c is None:
            return "--"
        return f"¥{c:.2f}"

    def _replay_right_click(self):
        """普通右键单击：在主线程重放一次完整点击（架构参考 StarPie）。"""
        try:
            self.hook.set_ignore_next_click()
            _user32.mouse_event(0x0008, 0, 0, 0, 0)  # MOUSEEVENTF_RIGHTDOWN
            _user32.mouse_event(0x0010, 0, 0, 0, 0)  # MOUSEEVENTF_RIGHTUP
        except Exception:
            pass

    def _check_hook_health(self):
        """光标移动了但钩子没有任何事件 -> 钩子可能失效，重启（参考 StarPie）。"""
        try:
            cur = QCursor.pos()
            if self._last_cursor is None:
                self._last_cursor = cur
                self._last_hook_events = self.hook.event_count()
                return
            if self._last_cursor == cur:
                return
            self._last_cursor = cur
            events = self.hook.event_count()
            if events == self._last_hook_events:
                log("hook health: cursor moved but hook silent -> restart hook")
                try:
                    self.hook.stop()
                except Exception:
                    pass
                self.hook.start()
            self._last_hook_events = events
        except Exception:
            pass

def _single_instance():
    kernel32 = ctypes.windll.kernel32
    kernel32.CreateMutexW(None, False, "Local\\WheelTranslateMutex")
    return kernel32.GetLastError() != 183  # ERROR_ALREADY_EXISTS


def main():
    if not _single_instance():
        return 0
    try:
        app = ScreenTranslatorApp(sys.argv)
        ret = app.run()
        # 先卸载钩子（尤其是 C++ DLL 钩子），再让解释器销毁回调对象，避免退出时访问冲突
        try:
            app.hook.stop()
        except Exception:
            pass
        try:
            app.recorder.stop()  # 退出时结束可能进行中的录屏
        except Exception:
            pass
        try:
            from app.native_ocr import NativeOcr
            NativeOcr.cleanup()
        except Exception:
            pass
        return ret
    except Exception:  # noqa: BLE001
        try:
            CONFIG_DIR.mkdir(parents=True, exist_ok=True)
            (CONFIG_DIR / "error.log").write_text(
                traceback.format_exc(), encoding="utf-8"
            )
        except Exception:
            pass
        raise

