# -*- coding: utf-8 -*-
"""把耗时任务丢到工作线程，结果通过 Qt 信号回到主线程。

原来 application.py 与 settings_dialog.py 各写了一份几乎相同的
「threading.Thread + Signal.emit」样板，线程生命周期和异常行为分散在几处；
集中到这里之后，插件式改动只需要看一个文件。
"""
import threading

from PySide6.QtCore import QObject, Signal


class AsyncWorker(QObject):
    """执行 fn()，返回值通过 done 信号发回主线程。

    约定：fn 自己负责把失败转成可展示的结果（例如返回 (False, 原因)）；
    这里不吞异常，保证「悄悄失败」不会被误当成成功。
    """

    done = Signal(object)

    def start(self, fn):
        threading.Thread(target=self._run, args=(fn,), daemon=True).start()

    def _run(self, fn):
        self.done.emit(fn())


class CallbackWorker(QObject):
    """执行 fn() 后带回一个回调标记，异常统一转成 ("error", 文本)。"""

    done = Signal(object)

    def run(self, fn, callback):
        def target():
            try:
                result = fn()
            except Exception as exc:  # noqa: BLE001
                result = ("error", str(exc))
            self.done.emit((callback, result))

        threading.Thread(target=target, daemon=True).start()
