# -*- coding: utf-8 -*-
"""系统托盘（图标配色参考 StarPie：深色底 + 蓝系轮盘扇区）"""
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtCore import QPointF, QRectF
from PySide6.QtGui import QColor, QIcon, QPainter, QPen, QPixmap
from PySide6.QtWidgets import QMenu, QSystemTrayIcon

from app.autostart import is_enabled, set_enabled


def _render_icon(size):
    """按指定尺寸原生绘制托盘图标（透明底）。"""
    pm = QPixmap(size, size)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    s = float(size)
    c = QPointF(s / 2, s / 2)
    # 深色圆底 + 细描边
    p.setPen(QPen(QColor(255, 255, 255, 46), max(1.0, s * 0.023)))
    p.setBrush(QColor(15, 23, 42, 255))  # #0F172A
    p.drawEllipse(c, s * 0.469, s * 0.469)
    # 三个蓝系扇区（轮盘）
    inset = s * 0.047
    ring = QRectF(inset, inset, s - inset * 2, s - inset * 2)
    p.setPen(Qt.PenStyle.NoPen)
    for i, color in enumerate(
        [QColor(37, 99, 235), QColor(59, 130, 246), QColor(147, 197, 253)]
    ):
        p.setBrush(color)
        p.drawPie(ring, int((-90 + i * 120) * 16), int(120 * 16))
    # 深色核心
    p.setBrush(QColor(15, 23, 42, 255))
    p.setPen(QPen(QColor(255, 255, 255, 70), max(1.0, s * 0.016)))
    p.drawEllipse(c, s * 0.141, s * 0.141)
    # 中心叠加 vivo 翻译机图形（中A + 环绕箭头）
    glyph_path = Path(__file__).resolve().parent / "assets" / "vivo_translate.png"
    glyph = QPixmap(str(glyph_path))
    if not glyph.isNull():
        gw = s * 0.594
        gh = gw * glyph.height() / max(1, glyph.width())
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
        p.drawPixmap(QRectF(c.x() - gw / 2, c.y() - gh / 2, gw, gh),
                     glyph, QRectF(glyph.rect()))
    p.end()
    return pm


def make_icon():
    icon = QIcon()
    # 常见逻辑尺寸 + 1x/2x（HiDPI），保证托盘/任务栏任意缩放都清晰
    for logical in (16, 24, 32):
        for dpr in (1, 2):
            pm = _render_icon(logical * dpr)
            pm.setDevicePixelRatio(dpr)
            icon.addPixmap(pm)
    return icon


class Tray(QSystemTrayIcon):
    def __init__(self, qt_app, app_ref):
        super().__init__(make_icon(), qt_app)
        self.app_ref = app_ref
        self.setToolTip("轮盘翻译：按住鼠标右键拖动呼出轮盘")
        menu = QMenu()
        self.autostart_action = menu.addAction("开机自启动")
        self.autostart_action.setCheckable(True)
        self.autostart_action.setChecked(is_enabled())
        self.autostart_action.triggered.connect(self._toggle_autostart)
        menu.addAction("设置", self.app_ref.open_settings)
        menu.addAction("打开录屏文件位置", self.app_ref.open_record_dir)
        menu.addSeparator()
        menu.addAction("退出", self.app_ref.qt.quit)
        self.setContextMenu(menu)
        self.activated.connect(self._on_activated)

    def _toggle_autostart(self, checked):
        try:
            set_enabled(checked)
            self.autostart_action.setChecked(is_enabled())
        except Exception as exc:  # noqa: BLE001
            from app.log_utils import log

            log(f"autostart toggle failed: {exc}")

    def _on_activated(self, reason):
        # 双击打开设置；单击不做任何事
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self.app_ref.open_settings()

    def first_run_notice(self):
        self.showMessage(
            "轮盘翻译已启动",
            "按住鼠标右键拖动即可呼出轮盘",
            QSystemTrayIcon.MessageIcon.Information,
            5000,
        )
