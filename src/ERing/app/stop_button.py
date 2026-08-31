# -*- coding: utf-8 -*-
"""录屏中的浮动停止控件：白底蓝框圆角外壳 + 红色■按钮 + 录屏时间计时器。
可拖拽、记住上次位置、对屏幕可见但不会入镜。"""
import time

from PySide6.QtCore import QPoint, QPointF, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QFont, QGuiApplication, QPainter, QPen
from PySide6.QtWidgets import QWidget

from app.capture_exclude import set_exclude_from_capture


class StopButton(QWidget):
    stopped = Signal()
    moved = Signal(object)  # QPoint 新位置

    def __init__(self):
        super().__init__(None)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowDoesNotAcceptFocus
        )
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedSize(148, 48)
        self.setToolTip("停止录屏")
        self._drag_off = None
        self._press_pos = None
        self._started = 0.0
        self._tick = QTimer(self)
        self._tick.setInterval(500)
        self._tick.timeout.connect(self.update)

    def show_at_saved(self, pos=None):
        if pos is not None:
            self.move(pos)
        else:
            try:
                vg = QGuiApplication.primaryScreen().virtualGeometry()
                self.move(vg.right() - self.width() - 20, vg.top() + 12)
            except Exception:
                self.move(1200, 20)
        self._started = time.monotonic()
        self._tick.start()
        self.show()
        set_exclude_from_capture(self)  # 可见可点，但不会入镜

    def stop_timer(self):
        self._tick.stop()

    def hideEvent(self, event):
        self.stop_timer()
        super().hideEvent(event)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        # 外壳：白底 + 蓝色描边圆角矩形
        p.setPen(QPen(QColor(37, 99, 235), 1.5))
        p.setBrush(QColor(255, 255, 255, 248))
        p.drawRoundedRect(QRectF(0.75, 0.75, w - 1.5, h - 1.5), 14, 14)
        # 红色圆形停止按钮 + 白色方块
        c = QPointF(24, h / 2)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(225, 45, 45, 245))
        p.drawEllipse(c, 15, 15)
        p.setPen(QPen(QColor(255, 255, 255, 150), 1))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawEllipse(c, 15, 15)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(255, 255, 255, 250))
        p.drawRoundedRect(QRectF(c.x() - 6, c.y() - 6, 12, 12), 2, 2)
        # 计时文字 MM:SS
        secs = int(time.monotonic() - self._started) if self._started else 0
        mm, ss = divmod(max(0, secs), 60)
        p.setFont(QFont("Microsoft YaHei UI", 15, QFont.Weight.DemiBold))
        p.setPen(QColor(30, 41, 59, 245))
        p.drawText(
            QRectF(48, 0, w - 54, h),
            Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
            f"{mm:02d}:{ss:02d}",
        )

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_off = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            self._press_pos = event.globalPosition().toPoint()

    def mouseMoveEvent(self, event):
        if self._drag_off is not None:
            self.move(event.globalPosition().toPoint() - self._drag_off)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            moved_dist = (event.globalPosition().toPoint() - self._press_pos).manhattanLength()
            self._drag_off = None
            if moved_dist > 6:
                self.moved.emit(QPoint(self.pos()))  # 拖动结束：记住位置
            else:
                self.hide()
                self.stopped.emit()  # 单击：停止录屏
