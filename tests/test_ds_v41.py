# -*- coding: utf-8 -*-
"""离线回归测试：DeepSeek V4.1-Flash 相关变更。

覆盖：旧模型名迁移（deepseek-chat -> deepseek-flash）、翻译请求实际发出的模型名、
余额查询的路径回退 / 币种优选 / 错误提示。全部用假响应打桩，不联网。
"""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src" / "ERing"))

import app.config as config  # noqa: E402
from app import deepseek, translate  # noqa: E402


def test_config_migration_retired_model():
    """旧配置里的 deepseek-chat 应自动迁移为 deepseek-flash。"""
    cfg = config.migrate({"openai": {"base_url": "", "model": "deepseek-chat"}})
    assert cfg["openai"]["model"] == config.DEEPSEEK_MODEL, cfg["openai"]["model"]

    # 显式指向 DeepSeek 官方接口时同样迁移
    cfg = config.migrate({
        "openai": {"base_url": "https://api.deepseek.com", "model": "deepseek-reasoner"}
    })
    assert cfg["openai"]["model"] == config.DEEPSEEK_MODEL, cfg["openai"]["model"]

    # 自建/第三方兼容接口上的同名模型不应被改写
    cfg = config.migrate({
        "openai": {"base_url": "https://api.siliconflow.cn/v1", "model": "deepseek-chat"}
    })
    assert cfg["openai"]["model"] == "deepseek-chat", cfg["openai"]["model"]
    print("ok: 配置迁移")


def test_translate_sends_current_model():
    """走 DeepSeek 时，请求体里的 model 必须是 deepseek-flash。"""
    captured = {}

    class FakeResp:
        status_code = 200

        def raise_for_status(self):
            pass

        def json(self):
            return {"choices": [{"message": {"content": "你好"}}]}

    def fake_post(url, headers=None, json=None, timeout=None):
        captured.update(url=url, payload=json)
        return FakeResp()

    orig_post = translate._session.post
    translate._session.post = fake_post
    try:
        translate._cache.clear()
        cfg = {
            "auto_direction": False,
            "target_lang": "zh-CN",
            "provider": "openai",
            "max_text_len": 500,
            # 老用户配置里残留的旧模型名
            "openai": {"base_url": "", "model": "deepseek-chat", "api_key": ""},
            "deepseek": {"api_key": "sk-test"},
        }
        ok, res, provider = translate.translate_text("Hello world", cfg)
    finally:
        translate._session.post = orig_post

    assert ok and res == "你好", (ok, res)
    assert provider == "DeepSeek", provider
    assert captured["url"] == f"{config.DEEPSEEK_BASE}/chat/completions", captured["url"]
    assert captured["payload"]["model"] == "deepseek-flash", captured["payload"]["model"]
    print("ok: 翻译请求模型名 =", captured["payload"]["model"])


def _fake_response(status, payload=None, text=""):
    class R:
        def __init__(self):
            self.status_code = status
            self._payload = payload
            self.text = text

        def raise_for_status(self):
            if self.status_code >= 400:
                raise RuntimeError(f"HTTP {self.status_code}")

        def json(self):
            if self._payload is None:
                raise ValueError("not json")
            return self._payload

    return R()


def _with_fake_get(handler, fn):
    """临时替换 requests.get（deepseek 模块与 requests 共享同一个模块对象）。"""
    orig = deepseek.requests.get
    deepseek.requests.get = handler
    try:
        return fn()
    finally:
        deepseek.requests.get = orig


def test_balance_404_falls_back_and_prefers_cny():
    """首个路径 404 时回退到 /v1，且多币种优先取人民币。"""
    calls = []

    def fake_get(url, headers=None, timeout=None):
        calls.append(url)
        if url == f"{config.DEEPSEEK_BASE}/user/balance":
            return _fake_response(404, {"error": {"message": "Not Found"}})
        return _fake_response(200, {
            "is_available": True,
            "balance_infos": [
                {"currency": "USD", "total_balance": "1.50",
                 "granted_balance": "0", "topped_up_balance": "1.50"},
                {"currency": "CNY", "total_balance": "53.50",
                 "granted_balance": "3.50", "topped_up_balance": "50.00"},
            ],
        })

    ok, data, err = _with_fake_get(fake_get, lambda: deepseek._fetch_data("sk-test"))
    assert ok, err
    assert calls == [
        f"{config.DEEPSEEK_BASE}/user/balance",
        f"{config.DEEPSEEK_BASE}/v1/user/balance",
    ], calls
    assert deepseek.format_balance_short(data) == "¥53.5", deepseek.format_balance_short(data)
    print("ok: 404 回退 + 币种优选 ->", deepseek.format_balance_short(data))


def test_balance_401_message_is_actionable():
    """401 应给出可照做的提示，并带上服务端原因。"""
    def fake_get(url, headers=None, timeout=None):
        return _fake_response(401, {"error": {"message": "Authentication Fails"}})

    ok, data, err = _with_fake_get(fake_get, lambda: deepseek._fetch_data("sk-bad"))
    assert not ok and data is None
    assert "HTTP 401" in err and "重新生成" in err and "Authentication Fails" in err, err
    print("ok: 401 提示 ->", err)


def test_balance_ssl_error_message():
    """证书链问题应给出明确提示，而不是抛原始 SSL 堆栈。"""
    def fake_get(url, headers=None, timeout=None):
        raise deepseek.requests.exceptions.SSLError("certificate verify failed")

    ok, data, err = _with_fake_get(fake_get, lambda: deepseek._fetch_data("sk-test"))
    assert not ok and "证书校验失败" in err, err
    print("ok: 证书错误提示 ->", err)


def test_tls_bundle_merges_windows_store():
    """合并信任库必须真的把 Windows 证书库并进来，否则代理环境仍会校验失败。"""
    from app import tls

    path = tls.install()
    assert path, "未能生成合并信任库"
    assert os.environ.get("REQUESTS_CA_BUNDLE") == path, os.environ.get("REQUESTS_CA_BUNDLE")
    merged = Path(path).read_text(encoding="utf-8", errors="ignore")
    assert "BEGIN CERTIFICATE" in merged
    store = tls._windows_store_pem()
    if store:  # Windows 上应有系统证书
        assert len(merged) > len(tls._certifi_pem()), "合并包未包含系统证书"
    print("ok: 信任库合并 ->", path)


if __name__ == "__main__":
    test_config_migration_retired_model()
    test_translate_sends_current_model()
    test_balance_404_falls_back_and_prefers_cny()
    test_balance_401_message_is_actionable()
    test_balance_ssl_error_message()
    test_tls_bundle_merges_windows_store()
    print("ALL TESTS PASSED")
