# -*- coding: utf-8 -*-
"""全屏截图选区覆盖层（多显示器支持）"""
import mss
from PySide6.QtCore import QRect, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QFont, QGuiApplication, QImage, QPainter, QPen, QPixmap
from PySide6.QtWidgets import QWidget

from app.dpi import logical_to_physical


class ScreenshotOverlay(QWidget):
    region_captured = Signal(object)  # QImage
    region_rect_selected = Signal(object)  # QRect（逻辑坐标，录屏选区用）
    cancelled = Signal()

    def __init__(self):
        super().__init__(None)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint
        )
        self.setCursor(Qt.CursorShape.CrossCursor)
        self._pixmap = None
        self._start = None
        self._current = None
        self._auto_cancel = QTimer(self)
        self._auto_cancel.setSingleShot(True)
        self._auto_cancel.timeout.connect(self._cancel)
        self._record_mode = False

    def start_capture(self, record_mode=False):
        self._record_mode = bool(record_mode)
        with mss.MSS() as sct:
            mon = sct.monitors[0]  # 所有显示器的并集
            shot = sct.grab(mon)
        w, h = shot.width, shot.height
        img = QImage(shot.bgra, w, h, QImage.Format.Format_RGB32).copy()
        self._pixmap = QPixmap.fromImage(img)
        # 覆盖层用 Qt 逻辑坐标铺满虚拟桌面，背景图是物理像素，绘制时缩放到窗口
        self.setGeometry(QGuiApplication.primaryScreen().virtualGeometry())
        self._start = None
        self._current = None
        self._auto_cancel.start(90000)  # 90 秒无人操作自动退出，避免挡住桌面
        self.show()
        self.raise_()
        self.activateWindow()

    def _cancel(self):
        self.hide()
        self._auto_cancel.stop()
        self._pixmap = None  # 释放整屏位图
        self.cancelled.emit()

    def paintEvent(self, event):
        p = QPainter(self)
        if self._pixmap:
            p.drawPixmap(self.rect(), self._pixmap)
        p.fillRect(self.rect(), QColor(0, 0, 0, 90))
        if self._start and self._current:
            rect = QRect(self._start, self._current).normalized()
            p.fillRect(rect, QColor(30, 120, 255, 40))
            p.setPen(QPen(QColor(30, 160, 255), 2))
            p.drawRect(rect)
            p.setFont(QFont("Microsoft YaHei UI", 12))
            p.setPen(QColor(255, 255, 255))
            info = f"{rect.width()} x {rect.height()}   ({rect.x()}, {rect.y()})"
            y = rect.top() - 22
            if y < 10:
                y = rect.bottom() + 22
            p.drawText(rect.left() + 8, y, info)

        # 顶部常驻提示
        hint = ("单击=全屏 · 拖拽框选区域 · Esc/右键取消" if self._record_mode
                else "按住左键拖拽选择区域 · Esc / 右键取消")
        p.setFont(QFont("Microsoft YaHei UI", 14))
        fm = p.fontMetrics()
        tw = fm.horizontalAdvance(hint)
        hint_rect = QRect(self.width() // 2 - tw // 2 - 20, 18, tw + 40, 38)
        p.fillRect(hint_rect, QColor(0, 0, 0, 170))
        p.setPen(QColor(255, 255, 255))
        p.drawText(hint_rect, Qt.AlignmentFlag.AlignCenter, hint)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._start = event.position().toPoint()
            self._current = self._start
            self.update()
        elif event.button() == Qt.MouseButton.RightButton:
            self._cancel()

    def mouseMoveEvent(self, event):
        if self._start:
            self._current = event.position().toPoint()
            self.update()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self._start:
            self._current = event.position().toPoint()
            rect = QRect(self._start, self._current).normalized()
            self._start = None
            self._current = None
            if rect.width() >= 6 and rect.height() >= 6 and self._pixmap:
                self._auto_cancel.stop()
                if self._record_mode:
                    self.hide()
                    self.region_rect_selected.emit(rect)
                else:
                    crop = self._pixmap.copy(logical_to_physical(rect)).toImage()
                    self.hide()
                    self.region_captured.emit(crop)
                self._pixmap = None  # 释放整屏位图，降低常驻内存
            else:
                if self._record_mode:
                    # 单击（未拖拽）= 全屏录制
                    self._auto_cancel.stop()
                    full = QRect(self.rect())
                    self.hide()
                    self.region_rect_selected.emit(full)
                else:
                    self._cancel()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self._cancel()
