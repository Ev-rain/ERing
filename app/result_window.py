# -*- coding: utf-8 -*-
"""翻译结果浮窗：跟随轮盘主题（浅/暗），可拖拽边缘调大小并长期记忆。"""
from PySide6.QtCore import QPoint, QRectF, Qt, QTimer
from PySide6.QtGui import QColor, QCursor, QFont, QGuiApplication, QPainter, QPen
from PySide6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from app.tray import make_icon

_QSS = {
    "light": """
QLabel#resultTitle { color:#64748B; font-size:12px; }
QLabel#srcLabel { color:#475569; font-size:12px; font-weight:600; }
QLabel#dstLabel { color:#2563EB; font-size:12px; font-weight:600; }
QTextEdit#srcEdit { background:#F8FAFC; color:#0F172A; border:1px solid #E2E8F0;
                    border-radius:8px; padding:8px; font-size:13px;
                    selection-background-color:#BFDBFE; selection-color:#0F172A; }
QTextEdit#srcEdit:focus { border:1px solid #2563EB; }
QTextEdit#dstEdit { background:#EFF6FF; color:#0F172A; border:1px solid #BFDBFE;
                    border-radius:8px; padding:8px; font-size:13px;
                    selection-background-color:#BFDBFE; selection-color:#0F172A; }
QTextEdit#dstEdit:focus { border:1px solid #2563EB; }
QPushButton#primaryBtn { background:#2563EB; color:#FFFFFF; border:none;
                         border-radius:6px; padding:6px 14px;
                         font-size:13px; font-weight:600; }
QPushButton#primaryBtn:hover { background:#1D4ED8; }
QPushButton#normalBtn { background:#FFFFFF; color:#334155;
                        border:1px solid #CBD5E1; border-radius:6px;
                        padding:6px 14px; font-size:13px; }
QPushButton#normalBtn:hover { background:#F1F5F9; }
""",
    "dark": """
QLabel#resultTitle { color:#8FA3C8; font-size:12px; }
QLabel#srcLabel { color:#94A3B8; font-size:12px; font-weight:600; }
QLabel#dstLabel { color:#60A5FA; font-size:12px; font-weight:600; }
QTextEdit#srcEdit { background:#1E1E24; color:#F8FAFC; border:1px solid #2E3440;
                    border-radius:8px; padding:8px; font-size:13px;
                    selection-background-color:#2563EB; selection-color:#FFFFFF; }
QTextEdit#srcEdit:focus { border:1px solid #3B82F6; }
QTextEdit#dstEdit { background:#131C2E; color:#F8FAFC; border:1px solid #2563EB;
                    border-radius:8px; padding:8px; font-size:13px;
                    selection-background-color:#2563EB; selection-color:#FFFFFF; }
QTextEdit#dstEdit:focus { border:1px solid #60A5FA; }
QPushButton#primaryBtn { background:#2563EB; color:#FFFFFF; border:none;
                         border-radius:6px; padding:6px 14px;
                         font-size:13px; font-weight:600; }
QPushButton#primaryBtn:hover { background:#1D4ED8; }
QPushButton#normalBtn { background:#262C36; color:#E2E8F0; border:none;
                        border-radius:6px; padding:6px 14px; font-size:13px; }
QPushButton#normalBtn:hover { background:#313A4E; }
""",
}

_MIN_W, _MIN_H = 420, 360
_DEFAULT_W, _DEFAULT_H = 520, 540
_EDGE = 8
_RADIUS = 12
_THEME_COLORS = {
    "light": {"bg": QColor("#FFFFFF"), "border": QColor("#2563EB")},
    "dark": {"bg": QColor("#18181B"), "border": QColor("#3B82F6")},
}


class ResultWindow(QWidget):
    def __init__(self, cfg):
        super().__init__(None)
        self.cfg = cfg
        self.setWindowIcon(make_icon())
        self.setObjectName("resultPanel")
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowDoesNotAcceptFocus
        )
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setMinimumSize(_MIN_W, _MIN_H)
        self.resize(_DEFAULT_W, _DEFAULT_H)
        self._drag_off = None
        self._resize_mode = None
        self._resize_base = None
        self._theme = "light"

        root = QVBoxLayout(self)
        root.setContentsMargins(18, 16, 18, 16)
        root.setSpacing(8)

        self.title = QLabel("翻译结果")
        self.title.setObjectName("resultTitle")
        self.title.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)

        self.src_label = QLabel("原文")
        self.src_label.setObjectName("srcLabel")
        self.src_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)

        self.src = QTextEdit()
        self.src.setObjectName("srcEdit")
        self.src.setReadOnly(True)
        self.src.setMaximumHeight(130)
        self.src.setPlaceholderText("原文")

        self.dst_label = QLabel("译文")
        self.dst_label.setObjectName("dstLabel")
        self.dst_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)

        self.dst = QTextEdit()
        self.dst.setObjectName("dstEdit")
        self.dst.setReadOnly(True)
        self.dst.setPlaceholderText("译文")
        self.dst.setFont(QFont("Microsoft YaHei UI", 11))

        btn_row = QHBoxLayout()
        self.copy_dst = QPushButton("复制译文")
        self.copy_src = QPushButton("复制原文")
        self.close_btn = QPushButton("关闭")
        self.copy_dst.setObjectName("primaryBtn")
        self.copy_src.setObjectName("normalBtn")
        self.close_btn.setObjectName("normalBtn")
        for b in (self.copy_dst, self.copy_src, self.close_btn):
            b.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_row.addWidget(self.copy_dst)
        btn_row.addWidget(self.copy_src)
        btn_row.addStretch(1)
        btn_row.addWidget(self.close_btn)

        root.addWidget(self.title)
        root.addWidget(self.src_label)
        root.addWidget(self.src)
        root.addWidget(self.dst_label)
        root.addWidget(self.dst)
        root.addLayout(btn_row)

        self.copy_dst.clicked.connect(lambda: self._copy(self.dst.toPlainText()))
        self.copy_src.clicked.connect(lambda: self._copy(self.src.toPlainText()))
        self.close_btn.clicked.connect(self.hide)

        self.apply_theme(self.cfg["result_theme"])

    def apply_theme(self, theme):
        self._theme = theme if theme in _THEME_COLORS else "light"
        self.setStyleSheet(_QSS.get(theme, _QSS["light"]))
        self.update()

    def paintEvent(self, event):
        """整体圆角矩形 + 外侧 1px 蓝色边框（透明窗口下可靠绘制）。"""
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        colors = _THEME_COLORS.get(self._theme, _THEME_COLORS["light"])
        rect = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        p.setPen(QPen(colors["border"], 1))
        p.setBrush(colors["bg"])
        p.drawRoundedRect(rect, _RADIUS, _RADIUS)

    def show_result(self, original, translated, provider):
        self.src.setPlainText(original)
        self.dst.setPlainText(translated)
        self.title.setText(f"翻译结果 · {provider}")
        self.apply_theme(self.cfg["result_theme"])
        w, h = self._saved_size()
        self.resize(w, h)
        pos = QCursor.pos() + QPoint(24, 24)
        try:
            vg = QGuiApplication.primaryScreen().virtualGeometry()
            x = max(vg.left() + 12, min(pos.x(), vg.right() - w - 12))
            y = max(vg.top() + 12, min(pos.y(), vg.bottom() - h - 12))
        except Exception:
            x, y = pos.x(), pos.y()
        self.move(x, y)
        self.show()

    def _saved_size(self):
        if not self.cfg["remember_result_size"]:
            return _DEFAULT_W, _DEFAULT_H
        saved = self.cfg["result_size"]
        if isinstance(saved, (list, tuple)) and len(saved) == 2:
            return max(_MIN_W, int(saved[0])), max(_MIN_H, int(saved[1]))
        return _DEFAULT_W, _DEFAULT_H

    def _save_size(self):
        if not self.cfg["remember_result_size"]:
            return
        self.cfg["result_size"] = [self.width(), self.height()]
        self.cfg.save()

    def _copy(self, text):
        if not text:
            return
        QApplication.clipboard().setText(text)
        btn = self.sender()
        if isinstance(btn, QPushButton):
            old = btn.text()
            btn.setText("已复制 ✓")
            QTimer.singleShot(900, lambda: btn.setText(old))

    # ---------- 拖动 / 调整大小 ----------
    def _edge_at(self, pos):
        r = self.rect()
        x, y = pos.x(), pos.y()
        left = x <= r.left() + _EDGE
        right = x >= r.right() - _EDGE
        top = y <= r.top() + _EDGE
        bottom = y >= r.bottom() - _EDGE
        if top and left:
            return "tl"
        if top and right:
            return "tr"
        if bottom and left:
            return "bl"
        if bottom and right:
            return "br"
        if left:
            return "l"
        if right:
            return "r"
        if top:
            return "t"
        if bottom:
            return "b"
        return None

    def _edge_cursor(self, mode):
        cursors = {
            "tl": Qt.CursorShape.SizeFDiagCursor,
            "br": Qt.CursorShape.SizeFDiagCursor,
            "tr": Qt.CursorShape.SizeBDiagCursor,
            "bl": Qt.CursorShape.SizeBDiagCursor,
            "l": Qt.CursorShape.SizeHorCursor,
            "r": Qt.CursorShape.SizeHorCursor,
            "t": Qt.CursorShape.SizeVerCursor,
            "b": Qt.CursorShape.SizeVerCursor,
        }
        self.setCursor(cursors.get(mode, Qt.CursorShape.ArrowCursor))

    def _do_resize(self, gp):
        g, start = self._resize_base
        dx, dy = gp.x() - start.x(), gp.y() - start.y()
        x, y, w, h = g.x(), g.y(), g.width(), g.height()
        m = self._resize_mode
        if "r" in m:
            w = max(_MIN_W, g.width() + dx)
        if "b" in m:
            h = max(_MIN_H, g.height() + dy)
        if "l" in m:
            w2 = max(_MIN_W, g.width() - dx)
            x = g.x() + g.width() - w2
            w = w2
        if "t" in m:
            h2 = max(_MIN_H, g.height() - dy)
            y = g.y() + g.height() - h2
            h = h2
        self.setGeometry(x, y, w, h)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            mode = self._edge_at(event.position().toPoint())
            if mode:
                self._resize_mode = mode
                self._resize_base = (self.geometry(), event.globalPosition().toPoint())
            else:
                self._drag_off = (
                    event.globalPosition().toPoint() - self.frameGeometry().topLeft()
                )
                self.setCursor(Qt.CursorShape.ArrowCursor)

    def mouseMoveEvent(self, event):
        if self._resize_mode and self._resize_base:
            self._do_resize(event.globalPosition().toPoint())
        elif self._drag_off is not None:
            self.move(event.globalPosition().toPoint() - self._drag_off)
        else:
            self._edge_cursor(self._edge_at(event.position().toPoint()))

    def mouseReleaseEvent(self, event):
        if self._resize_mode:
            self._resize_mode = None
            self._resize_base = None
            self._save_size()
        self._drag_off = None
