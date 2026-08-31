# -*- coding: utf-8 -*-
"""DeepSeek API：余额查询与缓存（供轮盘圆心显示）"""
import json
import threading
import time

import requests

from app.config import CONFIG_DIR
from app.log_utils import log

BASE = "https://api.deepseek.com"
UA = {"Accept": "application/json", "User-Agent": "wheel-translator"}


def _fetch_data(api_key):
    if not api_key or not api_key.strip():
        return False, None, "请先填写 DeepSeek API Key"
    try:
        r = requests.get(
            f"{BASE}/user/balance",
            headers={"Authorization": f"Bearer {api_key.strip()}", **UA},
            timeout=15,
        )
        r.raise_for_status()
        return True, r.json(), ""
    except Exception as exc:  # noqa: BLE001
        return False, None, f"查询失败：{exc}"


def format_balance_short(data):
    """返回圆心用的简短余额，如 ¥7.5。"""
    infos = data.get("balance_infos") or []
    if not infos:
        return None
    info = infos[0]
    try:
        num = float(info.get("total_balance") or 0)
    except (TypeError, ValueError):
        return None
    text = f"{num:.2f}".rstrip("0").rstrip(".")
    currency = info.get("currency") or ""
    sym = "¥" if currency == "CNY" else (currency or "")
    return f"{sym}{text}"


def fetch_balance(api_key):
    """设置面板用：完整余额文本。返回 (ok, 文本)。"""
    ok, data, err = _fetch_data(api_key)
    if not ok:
        return False, err
    lines = []
    lines.append("账户状态：" + ("可用" if data.get("is_available") else "不可用 / 余额不足"))
    infos = data.get("balance_infos") or []
    if not infos:
        lines.append("（无余额信息）")
    for b in infos:
        currency = b.get("currency", "")
        total = b.get("total_balance", "?")
        granted = b.get("granted_balance", "?")
        topped = b.get("topped_up_balance", "?")
        lines.append(f"{currency} 总额：{total}（充值 {topped} / 赠送 {granted}）")
    return True, "\n".join(lines)


def fetch_balance_short(api_key):
    ok, data, err = _fetch_data(api_key)
    if not ok:
        return False, None
    return True, format_balance_short(data)


class BalanceProvider:
    """后台刷新余额；轮盘圆心显示用。
    今日消费 = 当天最早开启程序时查到的余额 + 当日充值 - 当前余额（持久化跨重启）。"""

    STALE_SEC = 60    # 余额缓存 1 分钟
    RETRY_SEC = 30    # 失败后至少 30 秒再试
    STATE_FILE = CONFIG_DIR / "consumption_state.json"

    def __init__(self, get_key, on_update=None):
        self._get_key = get_key
        self.on_update = on_update
        self._short = None
        self._state = self._load_state()
        self._last_success = 0.0
        self._last_attempt = 0.0
        self._thread = None
        self._lock = threading.Lock()

    @staticmethod
    def _today():
        return time.strftime("%Y-%m-%d")

    def _load_state(self):
        try:
            if self.STATE_FILE.exists():
                d = json.loads(self.STATE_FILE.read_text(encoding="utf-8"))
                if isinstance(d, dict) and d.get("date"):
                    return d
        except Exception:
            pass
        return {"date": "", "start_balance": None, "last_balance": None, "recharges": 0.0}

    def _save_state(self):
        try:
            CONFIG_DIR.mkdir(parents=True, exist_ok=True)
            self.STATE_FILE.write_text(
                json.dumps(self._state, ensure_ascii=False), encoding="utf-8"
            )
        except Exception:
            pass

    def current_key(self):
        return (self._get_key() or "").strip()

    def display_text(self):
        """圆心显示：未绑定 Key -> 退出；有缓存 -> 余额；否则 -> 余额…"""
        if not self.current_key():
            return "退出"
        if self._short:
            return self._short
        return "余额…"

    def consumption(self):
        """今日消费 = 当日基准余额 + 当日充值 - 当前余额（未获取时为 None）。"""
        with self._lock:
            st = self._state
            if st.get("start_balance") is None or st.get("last_balance") is None:
                return None
            consumed = (
                st["start_balance"] + st.get("recharges", 0.0) - st["last_balance"]
            )
            return max(0.0, round(consumed, 2))

    def refresh(self, force=False):
        key = self.current_key()
        if not key:
            with self._lock:
                self._short = None
            return
        now = time.monotonic()
        with self._lock:
            if self._thread and self._thread.is_alive() and not force:
                return
            if not force and self._last_success and now - self._last_success < self.STALE_SEC:
                return
            if not force and now - self._last_attempt < self.RETRY_SEC:
                return
            self._last_attempt = now
            self._thread = threading.Thread(target=self._fetch, args=(key,), daemon=True)
            self._thread.start()

    def _fetch(self, key):
        ok, data, _err = _fetch_data(key)
        short = format_balance_short(data) if ok else None
        num = None
        if ok and data:
            infos = data.get("balance_infos") or []
            if infos:
                try:
                    num = float(infos[0].get("total_balance") or 0)
                except (TypeError, ValueError):
                    num = None
        consumed = None
        with self._lock:
            if ok and num is not None:
                st = self._state
                today = self._today()
                if st.get("date") != today or st.get("start_balance") is None:
                    # 新的一天 / 首次成功查询：以本次余额为当日基准
                    st.update({
                        "date": today,
                        "start_balance": num,
                        "last_balance": num,
                        "recharges": 0.0,
                    })
                    log(f"今日基准余额: {num}")
                else:
                    last = st.get("last_balance")
                    if last is not None and num > last:
                        # 余额比上次还多 => 充值/退款，增长部分忽略
                        st["recharges"] = round(
                            st.get("recharges", 0.0) + (num - last), 2
                        )
                    st["last_balance"] = num
                consumed = max(
                    0.0,
                    round(
                        st["start_balance"] + st.get("recharges", 0.0) - num, 2
                    ),
                )
                self._save_state()
            if ok and short:
                self._short = short
                self._last_success = time.monotonic()
            else:
                self._short = None
        log(f"balance fetch: ok={ok} num={num} 今日消费={consumed}")
        if self.on_update:
            try:
                self.on_update()
            except Exception:
                pass
