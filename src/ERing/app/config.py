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
    "fullscreen_whitelist": [],  # 白名单：这些应用全屏时仍可呼出（绝对路径；不含分隔符时按 exe 名兼容）
    "fullscreen_blacklist": [],  # 黑名单：这些应用不论是否全屏都不弹轮盘（绝对路径；同上兼容）
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


PROVIDERS = ("auto", "edge", "google", "openai")
OCR_ENGINES = ("native", "rapid")
THEMES = ("dark", "light")
ANIM_SPEEDS = ("fast", "normal", "slow")
RECORD_FORMATS = ("mp4", "gif")

# 每个键的「可接受形状」。settings.json 是明文文件，用户（或旧版本残留）
# 写出一个类型不对的值时，与其让程序在别处 int() 崩掉，不如在这里收敛回默认值。
# 格式：kind, (参数...)
SCHEMA = {
    "drag_threshold": ("int", 4, 60),
    "record_fps": ("int", 1, 120),
    "max_text_len": ("int", 100, 100000),
    "outer_escape_distance": ("int", 60, 800),
    "target_lang": ("text", "zh-CN"),
    "record_dir": ("text", ""),
    "provider": ("enum", PROVIDERS),
    "ocr_engine": ("enum", OCR_ENGINES),
    "wheel_theme": ("enum", THEMES),
    "result_theme": ("enum", THEMES),
    "wheel_anim_speed": ("enum", ANIM_SPEEDS),
    "record_format": ("enum", RECORD_FORMATS),
    "auto_direction": ("bool",),
    "enable_logging": ("bool",),
    "suppress_fullscreen": ("bool",),
    "enable_outer_escape": ("bool",),
    "record_mouse": ("bool",),
    "close_to_tray": ("bool",),
    "remember_result_size": ("bool",),
    "wheel_items": ("textlist",),
    "fullscreen_whitelist": ("textlist",),
    "fullscreen_blacklist": ("textlist",),
    "result_size": ("pair",),
    "stop_button_pos": ("pair",),
}

_TRUE = {"1", "true", "yes", "on", "是"}
_FALSE = {"0", "false", "no", "off", "否", ""}


def _as_bool(value, default):
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    text = str(value).strip().lower()
    if text in _TRUE:
        return True
    if text in _FALSE:
        return False
    return default


def _as_textlist(value):
    if not isinstance(value, (list, tuple)):
        return None
    items = [str(x).strip() for x in value]
    return [x for x in items if x]


def _coerce(key, value):
    """把单个值收敛成合法形状；认不出来就返回 None（调用方用默认值兜底）。"""
    spec = SCHEMA.get(key)
    if spec is None:
        return value
    kind = spec[0]
    if kind == "int":
        try:
            number = int(value)
        except (TypeError, ValueError):
            return None
        low, high = spec[1], spec[2]
        return min(max(number, low), high)
    if kind == "bool":
        sentinel = object()
        result = _as_bool(value, sentinel)
        return None if result is sentinel else result
    if kind == "enum":
        text = str(value).strip().lower()
        return text if text in spec[1] else None
    if kind == "text":
        text = str(value).strip()
        return text or None
    if kind == "textlist":
        return _as_textlist(value)
    if kind == "pair":
        if isinstance(value, (list, tuple)) and len(value) == 2:
            try:
                return [int(value[0]), int(value[1])]
            except (TypeError, ValueError):
                return None
        return None
    return value


def sanitize(data):
    """逐键校验已合并的配置，坏值退回默认值（纯函数）。"""
    result = dict(data)
    for key in SCHEMA:
        if key not in result:
            result[key] = DEFAULTS[key]
            continue
        fixed = _coerce(key, result[key])
        if fixed is None:
            result[key] = DEFAULTS[key]
        else:
            result[key] = fixed
    # wheel_items 允许为空时会被 _as_textlist 折成 []，这里补回默认功能项
    if not result.get("wheel_items"):
        result["wheel_items"] = list(DEFAULTS["wheel_items"])
    for key in ("openai", "deepseek"):
        section = result.get(key)
        if not isinstance(section, dict):
            section = dict(DEFAULTS[key])
        result[key] = {
            name: str(section.get(name) or "").strip()
            for name in DEFAULTS[key]
        }
    return result


def migrate(loaded):
    """把磁盘上的旧配置合并进默认值，并做历史字段迁移（纯函数，便于自检）。"""
    merged = dict(DEFAULTS)
    merged.update(loaded if isinstance(loaded, dict) else {})
    for section in ("openai", "deepseek"):
        value = merged.get(section)
        merged[section] = {
            **DEFAULTS[section], **(value if isinstance(value, dict) else {})
        }
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
    # 迁移：白名单/黑名单统一成「非空字符串列表」，
    # 防止手改配置写成字符串后被逐字符遍历，也顺手剥掉空白与空串
    for key in ("fullscreen_whitelist", "fullscreen_blacklist"):
        value = merged.get(key)
        if not isinstance(value, list):
            merged[key] = []
        else:
            merged[key] = [str(x).strip() for x in value if str(x).strip()]
    return sanitize(merged)


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
        except Exception as exc:  # noqa: BLE001
            # 配置坏了不能让程序起不来，但必须在日志里留下线索
            try:
                from app.log_utils import log

                log(f"配置读取失败，改用默认值: {exc!r}")
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
        fixed = _coerce(key, value)
        self.data[key] = DEFAULTS.get(key) if fixed is None else fixed
