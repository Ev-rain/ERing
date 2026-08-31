# -*- coding: utf-8 -*-
"""右键拖动呼出的轮盘菜单。
完全仿照 StarPie（ClassicRing）：暗/亮双主题、圆角扇区、扇区间隙、
圆心比内圈小一圈（留出间隙）、外圈虚线轨道 + 罗盘刻度 + 核心蓝环装饰、矢量图标。
"""
import math
import os

from PySide6.QtCore import (
    QEasingCurve, QPoint, QPointF, QRectF, Qt, QVariantAnimation, Signal,
)
from PySide6.QtGui import (
    QColor, QCursor, QFont, QGuiApplication, QPainter, QPainterPath, QPen,
    QPixmap,
)
from PySide6.QtWidgets import QWidget

from app.log_utils import log
from app.paths import resource_path

DEFAULT_LABELS = ["翻译", "录屏", "设置"]
CENTER_ZONE = -2  # 圆心（取消操作/余额）
ESCAPED = -3      # 外甩取消状态（无选中，释放不触发动作）
ANIM_SPEED_MS = {"fast": 100, "normal": 170, "slow": 260}  # 弹出动画时长

# StarPie ClassicRing 双主题配色
PALETTES = {
    "dark": {
        "sector": QColor(24, 24, 27, 240),           # #F018181B
        "sector_border": QColor(255, 255, 255, 40),
        "highlight": QColor(37, 99, 235, 255),       # #FF2563EB
        "highlight_border": QColor(147, 197, 253, 255),  # #FF93C5FD
        "glow": QColor(59, 130, 246, 55),
        "text": QColor(248, 250, 252, 245),          # #FFF8FAFC
        "sub_text": QColor(190, 210, 240, 220),
        "core": QColor(24, 24, 27, 245),
        "core_border": QColor(255, 255, 255, 60),
        "deco": QColor(255, 255, 255, 45),
        "tick": QColor(255, 255, 255, 70),
        "inner_ring": QColor(59, 130, 246, 50),
        "icon": QColor(248, 250, 252, 240),
        "hole": QColor(24, 24, 27, 245),
    },
    "light": {
        "sector": QColor(248, 250, 252, 245),        # #F5F8FAFC
        "sector_border": QColor(100, 116, 139, 53),  # #3564748B
        "highlight": QColor(37, 99, 235, 255),
        "highlight_border": QColor(147, 197, 253, 255),
        "glow": QColor(59, 130, 246, 45),
        "text": QColor(15, 23, 42, 255),             # #FF0F172A
        "sub_text": QColor(71, 85, 105, 220),
        "core": QColor(248, 250, 252, 250),
        "core_border": QColor(100, 116, 139, 90),
        "deco": QColor(100, 116, 139, 60),
        "tick": QColor(71, 85, 105, 110),
        "inner_ring": QColor(59, 130, 246, 60),
        "icon": QColor(15, 23, 42, 245),
        "hole": QColor(248, 250, 252, 250),
    },
}

SECTOR_CORNER = 6.0   # 扇区圆角半径（px）
SECTOR_GAP_DEG = 1.0  # 每个扇区两侧各留 1° 间隙


def _pt(cx, cy, angle_deg, r):
    """hover 角（0°=正上，顺时针）-> 屏幕点。"""
    a = math.radians(angle_deg)
    return QPointF(cx + math.sin(a) * r, cy - math.cos(a) * r)


class WheelOverlay(QWidget):
    action_chosen = Signal(int)  # 外圈功能下标

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
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)

        self._radius = 120
        self._inner = 52      # 扇区内圈半径
        self._core = 46       # 圆心半径（比内圈小，留出间隙）
        self._items = [(label, label) for label in DEFAULT_LABELS]
        self._origin = QPointF()
        self._center_text = "退出"
        self._usage_text = ""
        self._glyph_cache = {}
        self._theme = "dark"
        self._escape_enabled = True
        self._escape_distance = 180.0
        self._escaped = False
        self._active = False
        self._hover = -1
        self._scale = 1.0
        self._scale_anim = QVariantAnimation(self)
        self._scale_anim.setStartValue(0.55)
        self._scale_anim.setEndValue(1.0)
        self._scale_anim.setDuration(170)
        self._scale_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._scale_anim.valueChanged.connect(self._on_scale_changed)

    def _pal(self, key):
        return PALETTES.get(self._theme, PALETTES["dark"])[key]

    def show_at(self, pos, labels=None, center_text=None, usage_text=None,
                theme="dark", escape_enabled=True, escape_distance=180,
                anim_duration=170):
        """pos：圆心（按下右键的位置，逻辑坐标）。"""
        labels = labels or DEFAULT_LABELS
        self._items = [(label, label) for label in labels]
        self._center_text = center_text or "退出"
        self._usage_text = usage_text or ""
        self._theme = theme if theme in PALETTES else "dark"
        self._escape_enabled = bool(escape_enabled)
        self._escape_distance = max(100.0, float(escape_distance))
        self._escaped = False
        self._origin = QPointF(pos)
        self._active = True
        self._hover = -1
        size = (self._radius + 16) * 2 + 1  # 留出外圈装饰空间，奇数边长中心精确
        x = pos.x() - size // 2
        y = pos.y() - size // 2
        try:
            vg = QGuiApplication.primaryScreen().virtualGeometry()
            x = max(vg.left(), min(x, vg.right() - size + 1))
            y = max(vg.top(), min(y, vg.bottom() - size + 1))
        except Exception:
            pass
        self.setGeometry(x, y, size, size)
        self.show()
        self._scale = 0.55
        self._scale_anim.stop()
        self._scale_anim.setDuration(max(60, int(anim_duration)))
        self._scale_anim.start()
        # 原生层面确保不抢占前台焦点（SWP_NOACTIVATE + 置顶）
        try:
            import ctypes
            hwnd = int(self.winId())
            ctypes.windll.user32.SetWindowPos(
                hwnd, -1, 0, 0, 0, 0, 0x0001 | 0x0002 | 0x0010
            )
        except Exception:
            pass
        self.update_hover(QCursor.pos().x(), QCursor.pos().y())
        log(f"wheel show: center=({pos.x()},{pos.y()}) items={labels} theme={self._theme}")

    def set_center_text(self, text, usage_text=None):
        self._center_text = text or "退出"
        if usage_text is not None:
            self._usage_text = usage_text
        if self._active:
            self.update()

    def resolve_release(self, x, y):
        """右键抬起时调用（Qt 主线程），按方向/圆心决定选择。"""
        if not self._active:
            return
        self._active = False
        zone = self._zone_at(QPoint(x, y))
        dx = x - self._origin.x()
        dy = y - self._origin.y()
        dist = math.hypot(dx, dy)
        self.hide()
        # 取消：圆心 / 外甩（超阈值或超出轮盘边缘） / 未命中
        if (zone in (CENTER_ZONE, ESCAPED, -1)
                or (self._escape_enabled and dist > self._radius)):
            log("wheel release -> center (取消本轮操作)")
            return
        if 0 <= zone < len(self._items):
            log(f"wheel release ({x},{y}) -> {zone} {self._items[zone][0]}")
            self.action_chosen.emit(zone)
        else:
            log("wheel release -> 取消")

    def update_hover(self, x, y):
        """由鼠标钩子的移动事件驱动（事件驱动，无轮询）。"""
        if not self._active:
            return
        zone = self._zone_at(QPoint(x, y))
        escaped = zone == ESCAPED
        if escaped != self._escaped:
            self._escaped = escaped
            self.update()
        if escaped:
            zone = -1
        if zone != self._hover:
            self._hover = zone
            self.update()

    def _on_scale_changed(self, value):
        self._scale = value
        self.update()

    def _zone_at(self, global_pos):
        """0°=正上方，顺时针。圆心=CENTER_ZONE；外圈按方向返回下标。"""
        dx = global_pos.x() - self._origin.x()
        dy = global_pos.y() - self._origin.y()
        dist = math.hypot(dx, dy)
        n = len(self._items)
        if n == 0:
            return -1
        if self._escape_enabled and dist > self._escape_distance:
            return ESCAPED
        if dist < self._inner:
            return CENTER_ZONE
        seg = 360.0 / n
        ang = math.degrees(math.atan2(dx, -dy))
        return int(((ang + seg / 2) % 360) / seg) % n

    # ---------- 扇区路径（圆角环形扇区） ----------
    def _sector_path(self, cx, cy, r_in, r_out, h0, h1):
        """hover 角 h0..h1（顺时针）的环形扇区，四角圆角。"""
        cr = min(SECTOR_CORNER, (r_out - r_in) / 2.0)
        span = h1 - h0
        d_out = math.degrees(cr / r_out)
        d_in = math.degrees(cr / r_in)
        path = QPainterPath()

        def P(h, r):
            return _pt(cx, cy, h, r)

        # 角 A：外弧起点（径向边 -> 外弧）
        r0 = P(h0, r_out - cr)
        c0 = P(h0, r_out)
        q0 = P(h0 + d_out, r_out)
        path.moveTo(r0)
        path.quadTo(c0, q0)
        # 外弧（顺时针 h0+d_out -> h1-d_out）
        n = 48
        for i in range(1, n + 1):
            h = h0 + d_out + (h1 - d_out - h0 - d_out) * i / n
            path.lineTo(P(h, r_out))
        # 角 B：外弧终点 -> 径向边
        q1 = P(h1 - d_out, r_out)
        c1 = P(h1, r_out)
        r1 = P(h1, r_out - cr)
        path.quadTo(c1, r1)
        # 径向边向内
        i1 = P(h1, r_in + cr)
        path.lineTo(i1)
        # 角 C：径向边 -> 内弧
        c2 = P(h1, r_in)
        q2 = P(h1 - d_in, r_in)
        path.quadTo(c2, q2)
        # 内弧（逆时针 h1-d_in -> h0+d_in）
        for i in range(1, n + 1):
            h = h1 - d_in - (h1 - d_in - h0 - d_in) * i / n
            path.lineTo(P(h, r_in))
        # 角 D：内弧 -> 径向边
        q3 = P(h0 + d_in, r_in)
        c3 = P(h0, r_in)
        i0 = P(h0, r_in + cr)
        path.quadTo(c3, i0)
        path.lineTo(r0)
        path.closeSubpath()
        return path

    # ---------- 绘制 ----------
    def paintEvent(self, event):
        if not self._active:
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        if self._escaped:
            p.setOpacity(0.38)  # StarPie 外甩取消：半透明安全状态
        c = QPointF(self.width() / 2, self.height() / 2)
        n = len(self._items)
        if n == 0:
            return
        seg = 360.0 / n

        # 弹出缩放动画
        p.save()
        p.translate(c)
        p.scale(self._scale, self._scale)
        p.translate(-c)

        # 外圈装饰：虚线轨道 + 罗盘刻度
        deco_pen = QPen(self._pal("deco"), 1, Qt.PenStyle.DashLine)
        p.setPen(deco_pen)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawEllipse(c, self._radius + 8, self._radius + 8)
        p.setPen(QPen(self._pal("tick"), 1.2))
        for deg in (0, 90, 180, 270):
            p.drawLine(_pt(c.x(), c.y(), deg, self._radius + 4),
                       _pt(c.x(), c.y(), deg, self._radius + 11))

        # 外圈扇区（圆角 + 间隙 + 高亮）
        g = SECTOR_GAP_DEG
        for i in range(n):
            h0 = i * seg - seg / 2 + g
            h1 = i * seg + seg / 2 - g
            path = self._sector_path(c.x(), c.y(), self._inner, self._radius, h0, h1)
            if i == self._hover:
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(self._pal("glow"))
                p.drawPath(self._sector_path(c.x(), c.y(), self._inner - 2,
                                             self._radius + 2, h0, h1))
                p.setBrush(self._pal("highlight"))
                p.drawPath(path)
                pen = QPen(self._pal("highlight_border"), 2)
                p.setPen(pen)
                p.setBrush(Qt.BrushStyle.NoBrush)
                p.drawPath(path)
            else:
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(self._pal("sector"))
                p.drawPath(path)
                pen = QPen(self._pal("sector_border"), 1)
                p.setPen(pen)
                p.setBrush(Qt.BrushStyle.NoBrush)
                p.drawPath(path)

        # 核心外围蓝环（装饰，比内圈小）
        p.setPen(QPen(self._pal("inner_ring"), 1.2))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawEllipse(c, self._core + 4, self._core + 4)

        # 圆心：余额 或 退出（比内圈小一圈，留出间隙）
        if self._hover == CENTER_ZONE:
            core_fill = self._pal("highlight")
        else:
            core_fill = self._pal("core")
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(core_fill)
        p.drawEllipse(c, self._core, self._core)
        pen = QPen(self._pal("core_border"), 1)
        p.setPen(pen)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawEllipse(c, self._core, self._core)

        if self._center_text == "退出":
            self._draw_vector_icon(
                p, "退出", c.x(), c.y() - self._core * 0.12, self._core * 0.28
            )
            p.setFont(QFont("Microsoft YaHei UI", 10))
            p.setPen(self._pal("text"))
            p.drawText(QRectF(c.x() - self._core, c.y() + self._core - 24,
                              self._core * 2, 22),
                       Qt.AlignmentFlag.AlignCenter, "退出")
        else:
            # 两行（紧凑居中）：小字「总余额」+ 略大加粗数值；大字「今日消费」
            label = "总余额 "
            value = self._center_text or ""
            p.setFont(QFont("Microsoft YaHei UI", 8))
            w_label = p.fontMetrics().horizontalAdvance(label)
            p.setFont(QFont("Microsoft YaHei UI", 10, QFont.Weight.DemiBold))
            w_value = p.fontMetrics().horizontalAdvance(value)
            x0 = c.x() - (w_label + w_value) / 2
            row_y = c.y() - 24
            p.setFont(QFont("Microsoft YaHei UI", 8))
            p.setPen(self._pal("sub_text"))
            p.drawText(QRectF(x0, row_y, w_label + 4, 16),
                       Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, label)
            p.setFont(QFont("Microsoft YaHei UI", 10, QFont.Weight.DemiBold))
            p.setPen(self._pal("text"))
            p.drawText(QRectF(x0 + w_label, row_y, w_value + 4, 16),
                       Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, value)
            usage = self._usage_text or "--"
            label2 = "今日消费"
            p.setFont(QFont("Microsoft YaHei UI", 8))
            w_label2 = p.fontMetrics().horizontalAdvance(label2)
            p.setFont(QFont("Microsoft YaHei UI", 10, QFont.Weight.DemiBold))
            w_value2 = p.fontMetrics().horizontalAdvance(usage)
            x1 = c.x() - (w_label2 + w_value2) / 2
            row_y2 = c.y() - 6
            p.setFont(QFont("Microsoft YaHei UI", 8))
            p.setPen(self._pal("sub_text"))
            p.drawText(QRectF(x1, row_y2, w_label2 + 4, 26),
                       Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, label2)
            p.setFont(QFont("Microsoft YaHei UI", 10, QFont.Weight.DemiBold))
            p.setPen(self._pal("text"))
            p.drawText(QRectF(x1 + w_label2, row_y2, w_value2 + 4, 26),
                       Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, usage)

        # 外圈矢量图标（无文字，StarPie 图标模式）
        for i, (label, _kind) in enumerate(self._items):
            mid = i * seg
            icon_pos = _pt(c.x(), c.y(), mid, self._radius * 0.70)
            self._draw_vector_icon(
                p, label, icon_pos.x(), icon_pos.y(), self._radius * 0.17
            )

        p.restore()

    def _draw_vector_icon(self, p, kind, cx, cy, r):
        """StarPie 风格矢量图标（随主题变色）。"""
        color = self._pal("icon")
        pen = QPen(color)
        pen.setWidth(max(1.4, r * 0.15))
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        if kind == "翻译":  # vivo 翻译机真实图形
            glyph = self._translate_glyph_pixmap(self._theme)
            if glyph is not None:
                gw = r * 1.9
                gh = gw * glyph.height() / max(1, glyph.width())
                p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
                p.drawPixmap(QRectF(cx - gw / 2, cy - gh / 2, gw, gh),
                             glyph, QRectF(glyph.rect()))
        elif kind == "录屏":  # 录制圆点
            p.setPen(pen)
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawEllipse(QPointF(cx, cy), r, r)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(color)
            p.drawEllipse(QPointF(cx, cy), r * 0.42, r * 0.42)
        elif kind == "设置":  # 齿轮
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(color)
            for i in range(8):
                p.save()
                p.translate(cx, cy)
                p.rotate(i * 45)
                p.drawRect(QRectF(-r * 0.22, -r * 1.08, r * 0.44, r * 0.42))
                p.restore()
            p.drawEllipse(QPointF(cx, cy), r * 0.82, r * 0.82)
            p.setBrush(self._pal("hole"))
            p.drawEllipse(QPointF(cx, cy), r * 0.42, r * 0.42)
        elif kind == "退出":  # 电源
            p.setPen(pen)
            p.setBrush(Qt.BrushStyle.NoBrush)
            # 缺口朝上且只留 90°（标准电源图标），竖线从圆心穿出缺口
            p.drawArc(QRectF(cx - r, cy - r, r * 2, r * 2), 135 * 16, 270 * 16)
            p.drawLine(QPointF(cx, cy), QPointF(cx, cy - r * 0.55))
        else:
            p.setPen(pen)
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawEllipse(QPointF(cx, cy), r * 0.7, r * 0.7)

    def _translate_glyph_pixmap(self, theme):
        """vivo 翻译机图标图形（中A + 环绕箭头），按主题着色并缓存。"""
        if theme not in self._glyph_cache:
            path = str(resource_path("assets") / "vivo_translate.png")
            raw = QPixmap(path)
            if raw.isNull():
                log(f"translate glyph asset missing: {path}")
                self._glyph_cache[theme] = None
            else:
                tinted = QPixmap(raw.size())
                tinted.fill(Qt.GlobalColor.transparent)
                pt = QPainter(tinted)
                pt.drawPixmap(0, 0, raw)
                pt.setCompositionMode(
                    QPainter.CompositionMode.CompositionMode_SourceIn
                )
                pt.fillRect(tinted.rect(), PALETTES[theme]["icon"])
                pt.end()
                self._glyph_cache[theme] = tinted
        return self._glyph_cache.get(theme)
