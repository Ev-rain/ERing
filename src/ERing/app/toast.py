# -*- coding: utf-8 -*-
"""轻量提示气泡"""
from PySide6.QtCore import QPoint, Qt, QTimer
from PySide6.QtGui import QCursor, QFont, QGuiApplication
from PySide6.QtWidgets import QLabel, QWidget

from app.capture_exclude import set_exclude_from_capture


class Toast(QWidget):
    def __init__(self):
        super().__init__(None)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowDoesNotAcceptFocus
        )
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self._label = QLabel(self)
        self._label.setStyleSheet(
            "background: rgba(22,22,28,225); color: #ffffff;"
            "border-radius: 8px; padding: 8px 14px;"
        )
        self._label.setFont(QFont("Microsoft YaHei UI", 10))
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self.hide)

    def show_message(self, text, ms=1800):
        self._label.setText(text)
        self._label.adjustSize()
        w, h = self._label.width() + 4, self._label.height() + 4
        self.setFixedSize(w, h)
        # 固定在屏幕顶部居中
        pos = QPoint(0, 18)
        try:
            vg = QGuiApplication.primaryScreen().virtualGeometry()
            pos.setX(vg.left() + (vg.width() - w) // 2)
            pos.setY(vg.top() + 18)
        except Exception:
            pass
        self.move(pos)
        self.show()
        set_exclude_from_capture(self)  # 可见但不入镜
        self._timer.start(max(600, int(ms)))
