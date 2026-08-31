# -*- coding: utf-8 -*-
"""设置窗口：左侧导航 + 卡片式内容页，配色与排版参考 StarPie。
只保留本工具需要的功能：翻译 / 轮盘 / DeepSeek / 日志。"""
import os
import threading

from PySide6.QtCore import QObject, Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QSlider,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from app.config import CONFIG_DIR
from app.autostart import is_enabled as autostart_enabled
from app.autostart import set_enabled as autostart_set_enabled
from app.deepseek import fetch_balance
from app.log_utils import configure as configure_logging
from app.tray import make_icon

PROVIDERS = [
    ("自动（MyMemory → Google → Edge → OpenAI）", "auto"),
    ("MyMemory（免费无 Key）", "mymemory"),
    ("Google", "google"),
    ("微软 Edge", "edge"),
    ("OpenAI 兼容接口 / DeepSeek", "openai"),
]

LANGS = ["zh-CN", "en", "ja", "ko", "fr", "de", "es", "ru", "zh-TW"]

NAV_ITEMS = [
    ("🌐  翻译", "翻译设置"),
    ("🎯  轮盘", "轮盘与识别"),
    ("🎬  录屏", "录屏设置"),
    ("💰  DeepSeek", "账户与消费"),
    ("📝  通用", "通用设置"),
]

def _ensure_check_images():
    """生成自绘勾选框图片（蓝底白勾），避免默认“蓝底黑勾”难看样式。"""
    from PySide6.QtCore import QPointF, QRectF
    from PySide6.QtGui import QColor, QPainter, QPen, QPixmap

    checked = CONFIG_DIR / "cb_checked.png"
    unchecked = CONFIG_DIR / "cb_unchecked.png"
    if checked.exists() and unchecked.exists():
        return str(checked), str(unchecked)
    try:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        pm = QPixmap(16, 16)
        pm.fill(Qt.GlobalColor.transparent)
        p = QPainter(pm)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor("#2563EB"))
        p.drawRoundedRect(QRectF(0.5, 0.5, 15, 15), 4, 4)
        p.setPen(QPen(QColor("#FFFFFF"), 2, Qt.PenStyle.SolidLine,
                      Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
        p.drawLine(QPointF(4, 8), QPointF(7, 11))
        p.drawLine(QPointF(7, 11), QPointF(12, 5))
        p.end()
        pm.save(str(checked))

        pm2 = QPixmap(16, 16)
        pm2.fill(Qt.GlobalColor.transparent)
        p = QPainter(pm2)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setBrush(QColor("#FFFFFF"))
        p.setPen(QPen(QColor("#CBD5E1"), 1))
        p.drawRoundedRect(QRectF(0.5, 0.5, 15, 15), 4, 4)
        p.end()
        pm2.save(str(unchecked))
    except Exception:
        pass
    return str(checked), str(unchecked)


def _ensure_combo_arrow():
    """StarPie 风格下拉箭头：细线倒 V 形，右侧灰色小箭头。"""
    from PySide6.QtCore import QPointF
    from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen, QPixmap

    normal = CONFIG_DIR / "combo_arrow.png"
    if normal.exists():
        return str(normal)
    try:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        pm = QPixmap(20, 12)
        pm.fill(Qt.GlobalColor.transparent)
        p = QPainter(pm)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        pen = QPen(QColor("#64748B"), 2.4)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        p.setPen(pen)
        path_q = QPainterPath()
        path_q.moveTo(QPointF(3.5, 3.5))
        path_q.lineTo(QPointF(10, 9.5))
        path_q.lineTo(QPointF(16.5, 3.5))
        p.drawPath(path_q)
        p.end()
        pm.save(str(normal))
    except Exception:
        pass
    return str(normal)


QSS_TEMPLATE = """
QDialog { background:#F8FAFC; }
QLabel#sideTitle { font-size:17px; font-weight:700; color:#0F172A; }
QLabel#sideSub { font-size:11px; color:#64748B; }
QListWidget#nav { background:transparent; border:none; outline:0; font-size:13px; }
QListWidget#nav::item { color:#475569; padding:9px 12px; border-radius:6px; margin:1px 8px; }
QListWidget#nav::item:hover { background:#F1F5F9; color:#0F172A; }
QListWidget#nav::item:selected { background:#EFF6FF; color:#2563EB; font-weight:600; }
QLabel#pageTitle { font-size:20px; font-weight:700; color:#0F172A; }
QLabel#pageSub { font-size:12px; color:#64748B; }
QGroupBox { background:#FFFFFF; border:1px solid #E2E8F0; border-radius:8px;
            margin-top:12px; padding:14px 12px 14px 12px; font-size:13px; color:#0F172A; }
QGroupBox::title { subcontrol-origin: margin; left:14px; padding:0 4px; font-weight:600; color:#0F172A; }
QLabel { color:#334155; font-size:13px; }
QLineEdit { background:#FFFFFF; border:1px solid #CBD5E1;
            border-radius:6px; padding:6px 8px; color:#0F172A; }
QLineEdit:focus { border:1px solid #2563EB; }
QComboBox { background:#FFFFFF; border:1px solid #CBD5E1; border-radius:6px;
            padding:6px 30px 6px 10px; color:#0F172A; }
QComboBox:hover, QComboBox:focus, QComboBox:on { border:1px solid #2563EB; }
QComboBox::drop-down { border:none; width:28px; }
QComboBox::down-arrow { image: url(__ARROW__); width:10px; height:6px; }
QComboBox QAbstractItemView { background:#FFFFFF; border:1px solid #E2E8F0;
                              border-radius:8px; padding:4px; outline:0; }
QComboBox QAbstractItemView::item { min-height:28px; padding:2px 10px;
                                    border-radius:6px; color:#334155; }
QComboBox QAbstractItemView::item:hover { background:#F1F5F9; color:#0F172A; }
QComboBox QAbstractItemView::item:selected { background:#EFF6FF; color:#2563EB; }
QSlider { background:transparent; }
QSlider::groove:horizontal { height:5px; background:#CBD5E1; border-radius:2.5px; }
QSlider::handle:horizontal { width:18px; height:18px; margin:-7px 0;
                             border-radius:9px; background:#2563EB; }
QSlider::handle:horizontal:hover { background:#1D4ED8; }
QCheckBox { color:#334155; spacing:6px; }
QCheckBox::indicator { width:16px; height:16px; }
QCheckBox::indicator:unchecked { image: url(__UNCHECKED__); }
QCheckBox::indicator:checked { image: url(__CHECKED__); }
QPushButton { background:#FFFFFF; border:1px solid #CBD5E1; border-radius:6px;
              padding:7px 16px; color:#334155; }
QPushButton:hover { background:#F1F5F9; }
QPushButton#primary { background:#2563EB; color:#FFFFFF; border:none; font-weight:600; }
QPushButton#primary:hover { background:#1D4ED8; }
"""


def _build_qss():
    checked, unchecked = _ensure_check_images()
    arrow = _ensure_combo_arrow()
    # Qt 样式表的 url() 不能识别 Windows 反斜杠路径，必须转成正斜杠
    checked = checked.replace("\\", "/")
    unchecked = unchecked.replace("\\", "/")
    arrow = arrow.replace("\\", "/")
    return (
        QSS_TEMPLATE
        .replace("__CHECKED__", checked)
        .replace("__UNCHECKED__", unchecked)
        .replace("__ARROW__", arrow)
    )


class _BalanceWorker(QObject):
    done = Signal(object)


class _InstallWorker(QObject):
    done = Signal(object)

    def start(self, fn):
        threading.Thread(target=lambda: self.done.emit(fn()), daemon=True).start()


class SettingsDialog(QDialog):
    def __init__(self, cfg, parent=None, balance_provider=None):
        super().__init__(parent)
        self.cfg = cfg
        self._balance_provider = balance_provider
        self.setWindowTitle("轮盘翻译 - 设置")
        self.setWindowIcon(make_icon())
        self.setMinimumSize(900, 600)
        self.resize(920, 640)
        self.setStyleSheet(_build_qss())

        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        root.addWidget(self._build_sidebar())

        right = QVBoxLayout()
        right.setContentsMargins(28, 24, 28, 20)
        right.setSpacing(0)
        self.stack = QStackedWidget()
        self.pages = [
            self._build_translate_page(),
            self._build_wheel_page(),
            self._build_record_page(),
            self._build_deepseek_page(),
            self._build_log_page(),
        ]
        for page in self.pages:
            self.stack.addWidget(page)
        right.addWidget(self.stack, 1)
        right.addLayout(self._build_buttons())
        root.addLayout(right, 1)

        self.nav.currentRowChanged.connect(self.stack.setCurrentIndex)
        self.nav.setCurrentRow(0)

        self._balance_worker = _BalanceWorker()
        self._balance_worker.done.connect(self._on_balance_result)

    # ---------- 左侧导航 ----------
    def _build_sidebar(self):
        side = QWidget()
        side.setObjectName("sidebar")
        side.setFixedWidth(230)
        side.setStyleSheet("#sidebar { background:#FFFFFF; border-right:1px solid #E2E8F0; }")
        v = QVBoxLayout(side)
        v.setContentsMargins(16, 22, 16, 16)
        v.setSpacing(2)
        title = QLabel("轮盘翻译")
        title.setObjectName("sideTitle")
        sub = QLabel("截图 / 选中文本 即译")
        sub.setObjectName("sideSub")
        v.addWidget(title)
        v.addWidget(sub)
        v.addSpacing(18)
        self.nav = QListWidget()
        self.nav.setObjectName("nav")
        for text, _ in NAV_ITEMS:
            item = QListWidgetItem(text)
            self.nav.addItem(item)
        v.addWidget(self.nav, 1)
        ver = QLabel("v1.0 · 参考 StarPie 交互")
        ver.setStyleSheet("color:#94A3B8; font-size:11px;")
        v.addWidget(ver)
        return side

    # ---------- 页面骨架 ----------
    @staticmethod
    def _page(title, subtitle):
        page = QWidget()
        v = QVBoxLayout(page)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(12)
        t = QLabel(title)
        t.setObjectName("pageTitle")
        s = QLabel(subtitle)
        s.setObjectName("pageSub")
        s.setWordWrap(True)
        v.addWidget(t)
        v.addWidget(s)
        return page, v

    @staticmethod
    def _card(title):
        box = QGroupBox(title)
        v = QVBoxLayout(box)
        v.setSpacing(14)
        return box, v

    @staticmethod
    def _form_row(layout, label, widget, wrap=True):
        row = QHBoxLayout()
        row.setSpacing(12)
        lab = QLabel(label)
        lab.setFixedWidth(150 if wrap else 120)
        lab.setWordWrap(True)
        row.addWidget(lab)
        row.addWidget(widget, 1)
        layout.addLayout(row)

    @staticmethod
    def _make_slider(lo, hi, value, suffix):
        """StarPie 风格：滑块 + 右侧蓝色数值标签。"""
        s = QSlider(Qt.Orientation.Horizontal)
        s.setRange(lo, hi)
        s.setValue(value)
        s.setSingleStep(1)
        lab = QLabel(f"{value} {suffix}".strip())
        lab.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        lab.setFixedWidth(76)
        lab.setStyleSheet(
            "color:#2563EB; font-weight:600; font-size:13px; background:transparent;"
        )
        s.valueChanged.connect(lambda v: lab.setText(f"{v} {suffix}".strip()))
        return s, lab

    def _slider_row(self, layout, label, slider, value_label, wrap=True):
        row = QHBoxLayout()
        row.setSpacing(12)
        lab = QLabel(label)
        lab.setFixedWidth(150 if wrap else 120)
        lab.setWordWrap(True)
        row.addWidget(lab)
        row.addWidget(slider, 1)
        row.addWidget(value_label)
        layout.addLayout(row)

    # ---------- 翻译页 ----------
    def _build_translate_page(self):
        page, v = self._page("翻译设置", "配置翻译方向、翻译源与 AI 接口。")

        card, cv = self._card("基本")
        self.lang = QComboBox()
        self.lang.addItems(LANGS)
        self.lang.setCurrentText(self.cfg["target_lang"])
        self.auto = QCheckBox("自动判断方向（中文→英文，其他→目标语言）")
        self.auto.setChecked(self.cfg["auto_direction"])
        self.result_theme = QComboBox()
        self.result_theme.addItem("暗色", "dark")
        self.result_theme.addItem("亮色", "light")
        ridx = self.result_theme.findData(self.cfg["result_theme"])
        self.result_theme.setCurrentIndex(max(0, ridx))
        self.provider = QComboBox()
        for label, val in PROVIDERS:
            self.provider.addItem(label, val)
        idx = self.provider.findData(self.cfg["provider"])
        self.provider.setCurrentIndex(max(0, idx))
        self._form_row(cv, "目标语言", self.lang)
        self._form_row(cv, "方向", self.auto)
        self._form_row(cv, "翻译面板主题", self.result_theme)
        self._form_row(cv, "翻译源", self.provider)
        v.addWidget(card)

        oai_card, ov = self._card("OpenAI 兼容接口（可选，也可用 DeepSeek）")
        self.base = QLineEdit(self.cfg["openai"]["base_url"])
        self.base.setPlaceholderText("https://api.deepseek.com 或 https://api.openai.com/v1")
        self.model = QLineEdit(self.cfg["openai"]["model"])
        self.model.setPlaceholderText("deepseek-chat / gpt-4o-mini")
        self.key = QLineEdit(self.cfg["openai"]["api_key"])
        self.key.setPlaceholderText("sk-...（留空则用下方 DeepSeek Key）")
        self.key.setEchoMode(QLineEdit.EchoMode.Password)
        self._form_row(ov, "Base URL", self.base)
        self._form_row(ov, "模型", self.model)
        self._form_row(ov, "API Key", self.key)
        v.addWidget(oai_card)
        v.addStretch(1)
        return page

    # ---------- 轮盘页 ----------
    def _build_wheel_page(self):
        page, v = self._page("轮盘与识别", "轮盘手势触发距离与截图文字识别引擎。")

        wheel_card, wv = self._card("轮盘")
        self.threshold, self.threshold_label = self._make_slider(
            4, 60, int(self.cfg["drag_threshold"]), "px"
        )
        self._slider_row(wv, "右键拖动触发距离", self.threshold, self.threshold_label)
        self.theme = QComboBox()
        self.theme.addItem("暗色", "dark")
        self.theme.addItem("亮色", "light")
        idx = self.theme.findData(self.cfg["wheel_theme"])
        self.theme.setCurrentIndex(max(0, idx))
        self._form_row(wv, "轮盘主题", self.theme)
        self.anim_speed = QComboBox()
        self.anim_speed.addItem("快", "fast")
        self.anim_speed.addItem("标准", "normal")
        self.anim_speed.addItem("慢", "slow")
        aidx = self.anim_speed.findData(self.cfg["wheel_anim_speed"])
        self.anim_speed.setCurrentIndex(max(0, aidx))
        self._form_row(wv, "弹出动画", self.anim_speed)
        self.escape_check = QCheckBox("外甩取消（拖出轮盘边缘即取消，松开不触发）")
        self.escape_check.setChecked(bool(self.cfg["enable_outer_escape"]))
        self._form_row(wv, "外甩取消", self.escape_check)
        self.escape_dist, self.escape_dist_label = self._make_slider(
            140, 320, int(self.cfg["outer_escape_distance"]), "px"
        )
        # 子设置：缩进到勾选框文字对齐，表示它属于「外甩取消」
        sub_row = QHBoxLayout()
        sub_row.setSpacing(12)
        sub_row.addSpacing(184)
        dist_lab = QLabel("外甩距离")
        sub_row.addWidget(dist_lab)
        sub_row.addWidget(self.escape_dist, 1)
        sub_row.addWidget(self.escape_dist_label)
        wv.addLayout(sub_row)
        v.addWidget(wheel_card)

        ocr_card, ov = self._card("文字识别（OCR）")
        self.ocr_engine = QComboBox()
        self.ocr_engine.addItem("Windows 原生 OCR（快，推荐）", "native")
        self.ocr_engine.addItem("RapidOCR（高精度，离线）", "rapid")
        try:
            import importlib.util

            rapid_installed = (
                importlib.util.find_spec("rapidocr_onnxruntime") is not None
            )
        except Exception:
            rapid_installed = False
        if not rapid_installed:
            item = self.ocr_engine.model().item(1)
            item.setEnabled(False)
            item.setToolTip("未安装：pip install -r requirements-ocr.txt")
        idx = self.ocr_engine.findData(self.cfg["ocr_engine"])
        if idx == 1 and not rapid_installed:
            idx = 0  # 未安装 RapidOCR 时回退到原生
        self.ocr_engine.setCurrentIndex(max(0, idx))
        self._form_row(ov, "OCR 引擎", self.ocr_engine)

        self.rapid_installed = rapid_installed
        if not rapid_installed:
            install_row = QHBoxLayout()
            install_row.setSpacing(10)
            self.rapid_btn = QPushButton("安装 RapidOCR（离线高精度，约 240MB）")
            self.rapid_btn.clicked.connect(self._install_rapid)
            self.rapid_status = QLabel("")
            self.rapid_status.setStyleSheet("color:#64748B; font-size:12px;")
            install_row.addWidget(self.rapid_btn)
            install_row.addWidget(self.rapid_status, 1)
            ov.addLayout(install_row)

        hint = QLabel(
            "提示：截图识别效果与文字大小、清晰度有关。Windows 原生 OCR 快但准确率一般；"
            "RapidOCR 使用离线模型，小字/模糊字识别率更高。程序已对小截图自动放大 2 倍"
            "后再识别，仍不理想时可安装 RapidOCR 并切到该引擎。"
        )
        hint.setWordWrap(True)
        hint.setStyleSheet("color:#64748B; font-size:12px;")
        ov.addWidget(hint)
        v.addWidget(ocr_card)
        v.addStretch(1)
        return page

    def _install_rapid(self):
        import subprocess
        import sys
        from pathlib import Path

        req = Path(__file__).resolve().parent.parent / "requirements-ocr.txt"
        self.rapid_btn.setEnabled(False)
        self.rapid_status.setText("正在安装（约 1~3 分钟）…")

        def work():
            try:
                proc = subprocess.run(
                    [sys.executable, "-m", "pip", "install", "-r", str(req)],
                    capture_output=True,
                    text=True,
                    timeout=900,
                )
                ok = proc.returncode == 0
                detail = (proc.stderr or proc.stdout or "")[-300:]
                return ok, detail
            except Exception as exc:  # noqa: BLE001
                return False, str(exc)

        self._rapid_worker = _InstallWorker()
        self._rapid_worker.done.connect(self._on_install_done)
        self._rapid_worker.start(work)

    def _on_install_done(self, result):
        ok, _detail = result
        self.rapid_btn.setEnabled(True)
        if ok:
            self.rapid_status.setText("安装成功 ✓（已启用 RapidOCR 选项）")
            item = self.ocr_engine.model().item(1)
            item.setEnabled(True)
            item.setToolTip("")
            self.rapid_btn.setText("RapidOCR 已安装")
            self.rapid_btn.setEnabled(False)
            self.rapid_installed = True
        else:
            self.rapid_status.setText("安装失败，请检查网络后重试")

    # ---------- 录屏页 ----------
    def _build_record_page(self):
        page, v = self._page("录屏设置", "帧率、鼠标指针与保存格式。")

        card, cv = self._card("录屏")
        self.rec_fps = QComboBox()
        for fps in (15, 30, 60):
            self.rec_fps.addItem(f"{fps} FPS", fps)
        idx = self.rec_fps.findData(int(self.cfg["record_fps"]))
        self.rec_fps.setCurrentIndex(max(0, idx))
        self.rec_mouse = QCheckBox("显示鼠标指针")
        self.rec_mouse.setChecked(bool(self.cfg["record_mouse"]))
        self.rec_fmt = QComboBox()
        self.rec_fmt.addItem("MP4", "mp4")
        self.rec_fmt.addItem("GIF", "gif")
        fidx = self.rec_fmt.findData(self.cfg["record_format"])
        self.rec_fmt.setCurrentIndex(max(0, fidx))
        self._form_row(cv, "帧率", self.rec_fps)
        self._form_row(cv, "鼠标指针", self.rec_mouse)
        self._form_row(cv, "保存格式", self.rec_fmt)

        row = QHBoxLayout()
        row.setSpacing(12)
        lab = QLabel("保存位置")
        lab.setFixedWidth(150)
        row.addWidget(lab)
        dir_box = QHBoxLayout()
        dir_box.setSpacing(8)
        self.rec_dir_edit = QLineEdit(
            self.cfg["record_dir"].strip() or str(CONFIG_DIR / "recordings")
        )
        self.rec_dir_edit.setReadOnly(True)
        browse_btn = QPushButton("浏览…")
        browse_btn.clicked.connect(self._pick_record_dir)
        dir_box.addWidget(self.rec_dir_edit, 1)
        dir_box.addWidget(browse_btn)
        row.addLayout(dir_box, 1)
        cv.addLayout(row)

        open_row = QHBoxLayout()
        open_btn = QPushButton("打开录屏文件")
        open_btn.clicked.connect(self._open_record_dir)
        open_row.addWidget(open_btn)
        open_row.addStretch(1)
        cv.addLayout(open_row)

        v.addWidget(card)
        v.addStretch(1)
        return page

    def _pick_record_dir(self):
        start = self.rec_dir_edit.text().strip() or str(CONFIG_DIR / "recordings")
        d = QFileDialog.getExistingDirectory(self, "选择录屏保存位置", start)
        if d:
            self.rec_dir_edit.setText(d)

    def _open_record_dir(self):
        d = self.rec_dir_edit.text().strip() or str(CONFIG_DIR / "recordings")
        try:
            os.makedirs(d, exist_ok=True)
            os.startfile(d)
        except Exception as exc:  # noqa: BLE001
            from app.log_utils import log

            log(f"open record dir failed: {exc}")

    # ---------- DeepSeek 页 ----------
    def _build_deepseek_page(self):
        page, v = self._page("DeepSeek 账户", "查询余额与今日消费（按余额差值统计，充值增长自动忽略）。")

        card, cv = self._card("API Key 与余额")
        self.ds_key = QLineEdit(self.cfg["deepseek"]["api_key"])
        self.ds_key.setPlaceholderText("sk-...")
        self.ds_key.setEchoMode(QLineEdit.EchoMode.Password)
        self._form_row(cv, "API Key", self.ds_key)

        btn_row = QHBoxLayout()
        self.balance_btn = QPushButton("查询余额")
        self.balance_btn.setObjectName("primary")
        self.balance_btn.clicked.connect(self._query_balance)
        btn_row.addWidget(self.balance_btn)
        btn_row.addStretch(1)
        cv.addLayout(btn_row)

        self.balance_label = QLabel("尚未查询。")
        self.balance_label.setWordWrap(True)
        self.balance_label.setStyleSheet(
            "background:#F0FDF4; color:#166534; border:1px solid #BBF7D0;"
            "border-radius:6px; padding:8px 10px;"
        )
        cv.addWidget(self.balance_label)

        self.usage_label = QLabel("今日已消耗：--")
        self.usage_label.setStyleSheet("color:#475569; font-size:12px;")
        cv.addWidget(self.usage_label)
        v.addWidget(card)
        v.addStretch(1)

        if self._balance_provider is not None:
            self.update_usage(self._balance_provider.consumption())
        return page

    # ---------- 日志页 ----------
    def _build_log_page(self):
        page, v = self._page("通用设置", "开机自启动与调试日志。")

        gen_card, gv = self._card("通用")
        self.autostart_check = QCheckBox("开机自启动（登录 Windows 后自动运行）")
        self.autostart_check.setChecked(autostart_enabled())
        self._form_row(gv, "开机自启动", self.autostart_check)
        self.close_behavior = QComboBox()
        self.close_behavior.addItem("最小化到托盘", "tray")
        self.close_behavior.addItem("直接关闭", "close")
        idx = self.close_behavior.findData(
            "tray" if self.cfg["close_to_tray"] else "close"
        )
        self.close_behavior.setCurrentIndex(max(0, idx))
        self._form_row(gv, "关闭设置窗口", self.close_behavior)
        self.remember_size_check = QCheckBox(
            "记住翻译窗口大小（拖拽调整后自动保存）"
        )
        self.remember_size_check.setChecked(bool(self.cfg["remember_result_size"]))
        self._form_row(gv, "翻译窗口", self.remember_size_check)
        v.addWidget(gen_card)

        card, cv = self._card("调试日志")
        self.log_check = QCheckBox("启用调试日志（data\\app.log / mouse.log）")
        self.log_check.setChecked(bool(self.cfg["enable_logging"]))
        cv.addWidget(self.log_check)
        open_btn = QPushButton("打开日志文件夹")
        open_btn.clicked.connect(lambda: os.startfile(str(CONFIG_DIR)))
        cv.addWidget(open_btn)
        v.addWidget(card)
        v.addStretch(1)
        return page

    # ---------- 底部按钮 ----------
    def _build_buttons(self):
        row = QHBoxLayout()
        row.setSpacing(10)
        row.addStretch(1)
        cancel = QPushButton("取消")
        save = QPushButton("保存")
        save.setObjectName("primary")
        cancel.clicked.connect(self.reject)
        save.clicked.connect(self._save)
        row.addWidget(cancel)
        row.addWidget(save)
        return row

    # ---------- 余额查询 ----------
    def _query_balance(self):
        key = self.ds_key.text().strip()
        if not key:
            self.balance_label.setText("请先填写 DeepSeek API Key。")
            return
        self.balance_btn.setEnabled(False)
        self.balance_label.setText("正在查询余额…")
        if self._balance_provider is not None:
            self._balance_provider.refresh(force=True)

        def work():
            self._balance_worker.done.emit(fetch_balance(key))

        threading.Thread(target=work, daemon=True).start()

    def _on_balance_result(self, result):
        ok, text = result
        self.balance_label.setText(text)
        self.balance_btn.setEnabled(True)

    def update_usage(self, consumption):
        if consumption is None:
            self.usage_label.setText("今日已消耗：--（余额尚未获取）")
        else:
            self.usage_label.setText(
                f"今日已消耗：¥{consumption:.2f}（已忽略充值增长）"
            )

    # ---------- 保存 ----------
    def _save(self):
        self.cfg["target_lang"] = self.lang.currentText()
        self.cfg["auto_direction"] = self.auto.isChecked()
        self.cfg["provider"] = self.provider.currentData()
        self.cfg["drag_threshold"] = self.threshold.value()
        self.cfg["ocr_engine"] = self.ocr_engine.currentData()
        self.cfg["wheel_theme"] = self.theme.currentData()
        self.cfg["result_theme"] = self.result_theme.currentData()
        self.cfg["wheel_anim_speed"] = self.anim_speed.currentData()
        self.cfg["enable_outer_escape"] = self.escape_check.isChecked()
        self.cfg["outer_escape_distance"] = self.escape_dist.value()
        self.cfg["record_fps"] = self.rec_fps.currentData()
        self.cfg["record_mouse"] = self.rec_mouse.isChecked()
        self.cfg["record_format"] = self.rec_fmt.currentData()
        self.cfg["record_dir"] = self.rec_dir_edit.text().strip()
        self.cfg["openai"] = {
            "base_url": self.base.text().strip(),
            "model": self.model.text().strip(),
            "api_key": self.key.text().strip(),
        }
        self.cfg["deepseek"] = {"api_key": self.ds_key.text().strip()}
        self.cfg["enable_logging"] = self.log_check.isChecked()
        configure_logging(self.cfg["enable_logging"])
        self.cfg["close_to_tray"] = self.close_behavior.currentData() == "tray"
        self.cfg["remember_result_size"] = self.remember_size_check.isChecked()
        try:
            autostart_set_enabled(self.autostart_check.isChecked())
        except Exception:  # noqa: BLE001
            pass

        if self.cfg["provider"] == "openai":
            oa = self.cfg["openai"]
            if not oa.get("base_url") and self.cfg["deepseek"]["api_key"]:
                oa["base_url"] = "https://api.deepseek.com"
                oa["model"] = oa.get("model") or "deepseek-chat"
                oa["api_key"] = self.cfg["deepseek"]["api_key"]
                self.cfg["openai"] = oa

        self.cfg.save()
        self.accept()

    def closeEvent(self, event):
        # 开启「最小化到托盘」时，点 X 只隐藏窗口，不销毁
        if self.cfg["close_to_tray"]:
            event.ignore()
            self.hide()
        else:
            super().closeEvent(event)
