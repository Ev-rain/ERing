# -*- coding: utf-8 -*-
"""DeepSeek API：余额查询与缓存（供轮盘圆心显示）"""
import json
import threading
import time

import requests

from app.config import CONFIG_DIR, DEEPSEEK_BASE
from app.log_utils import log

BASE = DEEPSEEK_BASE
# 官方文档的余额接口是 GET /user/balance；/v1/user/balance 作为兜底（部分环境下
# 网关会把 OpenAI 兼容前缀也映射一份），仅在首个路径返回 404 时尝试。
BALANCE_PATHS = ("/user/balance", "/v1/user/balance")

UA = {"Accept": "application/json", "User-Agent": "wheel-translator"}


def _http_error_text(resp):
    """把 HTTP 错误翻译成能直接照做的提示，并带上服务端返回的原因。"""
    status = resp.status_code
    hint = {
        401: "（API Key 无效或已删除，请到 platform.deepseek.com 重新生成）",
        402: "（账户余额不足）",
        403: "（该 Key 无权查询余额）",
        429: "（请求过于频繁，请稍后再试）",
    }.get(status, "")
    if not hint and status >= 500:
        hint = "（DeepSeek 服务端异常，请稍后再试）"
    detail = ""
    try:
        body = resp.json()
        detail = (body.get("error") or {}).get("message") or body.get("message") or ""
    except Exception:  # noqa: BLE001
        detail = (resp.text or "").strip()[:160]
    text = f"查询失败：HTTP {status}{hint}"
    if detail:
        text += f"｜{detail}"
    return text


def _fetch_data(api_key):
    if not api_key or not api_key.strip():
        return False, None, "请先填写 DeepSeek API Key"
    key = api_key.strip()
    last_err = "查询失败：未获得有效响应"
    for path in BALANCE_PATHS:
        url = f"{BASE}{path}"
        try:
            r = requests.get(
                url,
                headers={"Authorization": f"Bearer {key}", **UA},
                timeout=15,
            )
        except requests.exceptions.SSLError:
            # 余额查询带 API Key，不做「跳过证书校验」的降级；只把原因说清楚
            return False, None, (
                "证书校验失败：HTTPS 被本机代理/安全软件重新签发，而其根证书不在信任库中。"
                "程序会自动合并 Windows 证书库；若仍失败，请把该软件的根证书导入"
                "「受信任的根证书颁发机构」，或让 api.deepseek.com 直连。"
            )
        except Exception as exc:  # noqa: BLE001
            last_err = f"网络错误：{exc}"
            continue
        if r.status_code == 404:
            last_err = f"接口不存在（404）：{url}"
            continue
        try:
            r.raise_for_status()
        except Exception:  # noqa: BLE001
            return False, None, _http_error_text(r)
        try:
            return True, r.json(), ""
        except ValueError:
            return False, None, f"返回内容无法解析（HTTP {r.status_code}）"
    return False, None, last_err


def pick_balance_info(infos, prefer="CNY"):
    """余额接口可能同时返回 CNY 与 USD，优先取人民币，避免圆心显示成美元。"""
    items = [i for i in (infos or []) if isinstance(i, dict)]
    if not items:
        return None
    for info in items:
        if str(info.get("currency") or "").upper() == prefer:
            return info
    return items[0]


def format_balance_short(data):
    """返回圆心用的简短余额，如 ¥7.5。"""
    info = pick_balance_info(data.get("balance_infos"))
    if not info:
        return None
    try:
        num = float(info.get("total_balance") or 0)
    except (TypeError, ValueError):
        return None
    text = f"{num:.2f}".rstrip("0").rstrip(".")
    currency = info.get("currency") or ""
    sym = "¥" if currency == "CNY" else ("$" if currency == "USD" else currency)
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
            info = pick_balance_info(data.get("balance_infos"))
            if info:
                try:
                    num = float(info.get("total_balance") or 0)
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
