# -*- coding: utf-8 -*-
"""配置读写"""
import json
from pathlib import Path

from app.paths import project_root

APP_NAME = "ERing"
# 所有配置、调试日志都放在工程目录下的 data 文件夹里
CONFIG_DIR = project_root() / "data"

# ---- DeepSeek 接口常量 ----
# 官方 Change Log：deepseek-chat / deepseek-reasoner 已于 2026-07-24 停止服务；
# 2026-09-10 发布 V4.1-Flash 后，现行模型名统一为 deepseek-flash
# （V4-Flash / V4-Pro 系列已退役并路由到 V4.1-Flash）。
# BASE URL 未变，仍是 https://api.deepseek.com。
DEEPSEEK_BASE = "https://api.deepseek.com"
DEEPSEEK_MODEL = "deepseek-flash"
RETIRED_DEEPSEEK_MODELS = ("deepseek-chat", "deepseek-reasoner")

DEFAULTS = {
    "drag_threshold": 14,        # 右键拖动多少像素触发轮盘
    "wheel_items": ["翻译", "录屏", "设置"],   # 外圈功能；圆心固定为「退出」
    "target_lang": "zh-CN",
    "auto_direction": True,      # 中文 -> 英文，其他 -> 目标语言
    "provider": "auto",          # auto | edge | google | openai
    "openai": {"base_url": "", "model": "", "api_key": ""},
    "deepseek": {"api_key": ""},
    "enable_logging": True,      # 调试日志开关
    "ocr_engine": "native",      # native=Windows 原生(快) | rapid=RapidOCR(高精度)
    "wheel_theme": "dark",       # dark=暗色 | light=亮色（轮盘主题）
    "result_theme": "light",     # dark=暗色 | light=亮色（翻译结果面板主题）
    "wheel_anim_speed": "normal",# fast=快 | normal=标准 | slow=慢（弹出动画）
    "suppress_fullscreen": True, # 全屏/独占应用在前台时隐藏（避免游戏误用）
    "fullscreen_whitelist": [],  # 白名单：这些全屏应用仍可调用（进程名列表）
    "enable_outer_escape": True, # 外甩取消
    "outer_escape_distance": 160,# 外甩取消距离（px，140~320）
    "record_fps": 30,          # 录屏帧率
    "record_mouse": True,      # 录屏显示鼠标指针
    "record_format": "mp4",    # 录屏格式 mp4/gif
    "record_dir": "",          # 录屏文件保存目录（空 = data/recordings）
    "close_to_tray": True,     # 关闭设置窗口时最小化到托盘（False = 直接关闭）
    "remember_result_size": True,  # 记住翻译窗口大小（拖拽调整后自动保存）
    "result_size": [],         # 翻译窗口上次大小 [w, h]
    "stop_button_pos": [],     # 停止按钮上次位置 [x, y]
    "max_text_len": 5000,
}


def migrate(loaded):
    """把磁盘上的旧配置合并进默认值，并做历史字段迁移（纯函数，便于自检）。"""
    merged = dict(DEFAULTS)
    merged.update(loaded or {})
    merged["openai"] = {**DEFAULTS["openai"], **(merged.get("openai") or {})}
    merged["deepseek"] = {**DEFAULTS["deepseek"], **(merged.get("deepseek") or {})}
    # 迁移：DeepSeek 旧模型名（deepseek-chat / deepseek-reasoner）已停服，
    # 换成现行 deepseek-flash；仅当指向 DeepSeek 官方接口或未填地址时才改写，
    # 避免动到用户自建/第三方 OpenAI 兼容接口上的同名模型。
    oa = merged["openai"]
    oa_base = str(oa.get("base_url") or "").strip()
    if (not oa_base or "api.deepseek.com" in oa_base) and (
        str(oa.get("model") or "").strip() in RETIRED_DEEPSEEK_MODELS
    ):
        oa["model"] = DEEPSEEK_MODEL
    # 迁移：旧版「退出」在外圈 -> 移除；「截图」->「录屏」
    items = merged.get("wheel_items")
    if isinstance(items, list):
        merged["wheel_items"] = [
            ("录屏" if i == "截图" else i) for i in items if i != "退出"
        ] or DEFAULTS["wheel_items"]
    return merged


class Config:
    def __init__(self):
        self.path = CONFIG_DIR / "settings.json"
        self.data = dict(DEFAULTS)
        self.load()

    def load(self):
        try:
            if self.path.exists():
                loaded = json.loads(self.path.read_text(encoding="utf-8"))
                self.data = migrate(loaded)
        except Exception:
            pass

    def save(self):
        try:
            CONFIG_DIR.mkdir(parents=True, exist_ok=True)
            self.path.write_text(
                json.dumps(self.data, ensure_ascii=False, indent=2), encoding="utf-8"
            )
        except Exception:
            pass

    def __getitem__(self, key):
        return self.data[key]

    def __setitem__(self, key, value):
        self.data[key] = value
