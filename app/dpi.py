# -*- coding: utf-8 -*-
"""物理像素 <-> Qt 逻辑像素 换算（高 DPI 缩放，含多显示器）"""
from PySide6.QtCore import QPoint, QRect, QRectF
from PySide6.QtGui import QGuiApplication


def _dpr_at(phys_x: float, phys_y: float) -> float:
    """根据物理坐标找到所在屏幕的缩放比例。"""
    for s in QGuiApplication.screens():
        dpr = s.devicePixelRatio()
        if dpr <= 0:
            continue
        g = s.geometry()
        phys_rect = QRectF(
            g.x() * dpr, g.y() * dpr, g.width() * dpr, g.height() * dpr
        )
        if phys_rect.contains(phys_x, phys_y):
            return dpr
    return QGuiApplication.primaryScreen().devicePixelRatio() or 1.0


def primary_dpr() -> float:
    return QGuiApplication.primaryScreen().devicePixelRatio() or 1.0


def phys_to_logical(x: int, y: int) -> QPoint:
    """鼠标钩子等系统 API 返回的物理坐标 -> Qt 逻辑坐标。"""
    dpr = _dpr_at(x, y)
    return QPoint(round(x / dpr), round(y / dpr))


def logical_to_physical(rect: QRect) -> QRect:
    """Qt 逻辑坐标矩形 -> 物理像素矩形（用于从截图里裁剪）。"""
    if rect is None:
        return rect
    cx, cy = rect.center().x(), rect.center().y()
    dpr = primary_dpr()
    for s in QGuiApplication.screens():
        dpr_s = s.devicePixelRatio()
        if dpr_s > 0 and s.geometry().contains(cx, cy):
            dpr = dpr_s
            break
    return QRect(
        round(rect.x() * dpr),
        round(rect.y() * dpr),
        round(rect.width() * dpr),
        round(rect.height() * dpr),
    )
