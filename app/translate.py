# -*- coding: utf-8 -*-
"""免费翻译：MyMemory（国内可用）优先，Google / Edge 兜底；可配置 OpenAI 兼容接口"""
import re
import threading

import requests

_session = requests.Session()  # 复用连接，减少 TLS/握手开销
_cache = {}
_cache_lock = threading.Lock()
CACHE_MAX = 256

UA = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
}
TIMEOUT = 12

LANG_NAMES = {
    "zh-CN": "简体中文", "zh-TW": "繁体中文", "en": "英文", "ja": "日文",
    "ko": "韩文", "fr": "法文", "de": "德文", "es": "西班牙文", "ru": "俄文",
}

CJK_RE = re.compile(r"[\u4e00-\u9fff\u3040-\u30ff\uac00-\ud7af]")


def _pick_target(text, cfg):
    if cfg.get("auto_direction"):
        cjk = len(CJK_RE.findall(text))
        latin = len(re.findall(r"[A-Za-z]", text))
        return "en" if cjk > latin else cfg.get("target_lang", "zh-CN")
    return cfg.get("target_lang", "zh-CN")


def translate_text(text, cfg):
    text = (text or "").strip()
    if not text:
        return False, "没有可翻译的内容", ""
    max_len = int(cfg.get("max_text_len", 5000))
    if len(text) > max_len:
        text = text[:max_len]
    to = _pick_target(text, cfg)
    provider = cfg.get("provider", "auto")

    cache_key = (provider, to, text)
    with _cache_lock:
        hit = _cache.get(cache_key)
        if hit:
            return True, hit[0], hit[1]

    errors = []

    if provider in ("auto", "mymemory"):
        try:
            result = _mymemory(text, to)
            _cache_put(cache_key, result, "MyMemory")
            return True, result, "MyMemory"
        except Exception as exc:  # noqa: BLE001
            errors.append(f"MyMemory: {exc}")
    if provider in ("auto", "google"):
        try:
            result = _google(text, to)
            _cache_put(cache_key, result, "Google")
            return True, result, "Google"
        except Exception as exc:  # noqa: BLE001
            errors.append(f"Google: {exc}")
    if provider in ("auto", "edge"):
        try:
            result = _edge(text, to)
            _cache_put(cache_key, result, "Edge")
            return True, result, "Edge"
        except Exception as exc:  # noqa: BLE001
            errors.append(f"Edge: {exc}")
    if provider in ("auto", "openai") and (
        cfg.get("openai", {}).get("base_url") or cfg.get("deepseek", {}).get("api_key")
    ):
        try:
            deepseek_key = cfg.get("deepseek", {}).get("api_key", "")
            used_deepseek = not cfg.get("openai", {}).get("base_url") and deepseek_key
            result = _openai(text, to, cfg["openai"], deepseek_key)
            provider_used = "DeepSeek" if used_deepseek else "OpenAI 兼容"
            _cache_put(cache_key, result, provider_used)
            return True, result, provider_used
        except Exception as exc:  # noqa: BLE001
            errors.append(f"OpenAI: {exc}")

    return False, "；".join(errors) or "未配置可用的翻译源", ""


def _cache_put(key, translated, provider_used):
    with _cache_lock:
        if len(_cache) >= CACHE_MAX:
            _cache.clear()
        _cache[key] = (translated, provider_used)


def clear_cache():
    with _cache_lock:
        _cache.clear()


def _mymemory(text, to):
    pair = f"Autodetect|{to}"
    results = []
    for chunk in _chunk(text, size=450):
        r = _session.get(
            "https://api.mymemory.translated.net/get",
            params={"q": chunk, "langpair": pair},
            headers=UA,
            timeout=TIMEOUT,
        )
        r.raise_for_status()
        data = r.json()
        if data.get("responseStatus") != 200:
            raise RuntimeError(data.get("responseDetails") or data.get("responseStatus"))
        translated = data.get("responseData", {}).get("translatedText", "")
        if not translated or translated.upper().startswith("QUERY LENGTH"):
            raise RuntimeError("MyMemory 请求过长或被限流")
        results.append(translated)
    return "\n".join(results)


def _google(text, to):
    results = []
    for chunk in _chunk(text):
        r = _session.get(
            "https://translate.googleapis.com/translate_a/single",
            params={"client": "gtx", "sl": "auto", "tl": to, "dt": "t", "q": chunk},
            headers=UA,
            timeout=TIMEOUT,
        )
        r.raise_for_status()
        data = r.json()
        results.append("".join(seg[0] for seg in data[0] if seg and seg[0]))
    return "\n".join(results)


def _edge(text, to):
    token = _session.get(
        "https://edge.microsoft.com/translate/auth", headers=UA, timeout=TIMEOUT
    ).text.strip()
    to_code = {"zh-CN": "zh-Hans", "zh-TW": "zh-Hant"}.get(to, to)
    results = []
    for chunk in _chunk(text):
        r = _session.post(
            "https://api-edge.cognitive.microsofttranslator.com/translate",
            params={"api-version": "3.0", "to": to_code},
            headers={"Authorization": f"Bearer {token}",
                     "Content-Type": "application/json", **UA},
            json=[{"Text": chunk}],
            timeout=TIMEOUT,
        )
        r.raise_for_status()
        results.append(r.json()[0]["translations"][0]["text"])
    return "\n".join(results)


def _openai(text, to, conf, deepseek_key=""):
    base = (conf.get("base_url") or "").rstrip("/")
    key = conf.get("api_key") or ""
    model = conf.get("model") or ""
    if not base and deepseek_key:
        base = "https://api.deepseek.com"
        key = deepseek_key
        model = model or "deepseek-chat"
    if not base:
        base = "https://api.openai.com/v1"
    if not model:
        model = "gpt-4o-mini"
    lang = LANG_NAMES.get(to, to)
    headers = {"Content-Type": "application/json", **UA}
    if key:
        headers["Authorization"] = f"Bearer {key}"
    payload = {
        "model": model,
        "messages": [
            {"role": "system",
             "content": "你是一名专业翻译。只输出译文，不要任何解释、引号或多余内容。"},
            {"role": "user", "content": f"请把下面的内容翻译成{lang}：\n\n{text}"},
        ],
        "temperature": 0.1,
    }
    r = _session.post(base + "/chat/completions", headers=headers, json=payload, timeout=30)
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"].strip()


def _chunk(text, size=950):
    if len(text) <= size:
        return [text]
    chunks, cur = [], ""
    for part in re.split(r"(?<=[。！？!?.;；\n])", text):
        while len(part) > size:
            if cur:
                chunks.append(cur)
                cur = ""
            chunks.append(part[:size])
            part = part[size:]
        if len(cur) + len(part) > size and cur:
            chunks.append(cur)
            cur = ""
        cur += part
    if cur:
        chunks.append(cur)
    return chunks
