# -*- coding: utf-8 -*-
"""检查更新逻辑（app/updater.py）离线测试。

运行：.venv/Scripts/python.exe tests/test_updater.py
不联网、不依赖 PySide6：把 requests.get 换成假实现再验证判定结果。
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src" / "ERing"))

import requests

from app import updater


class _FakeResp:
    def __init__(self, data, status=200):
        self._data = data
        self.status_code = status

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")

    def json(self):
        return self._data


def _with_get(fake, fn):
    """临时替换 requests.get，跑完恢复。"""
    real = updater.requests.get
    updater.requests.get = fake
    try:
        return fn()
    finally:
        updater.requests.get = real


RELEASE = {
    "tag_name": "v1.2.0",
    "published_at": "2026-11-02T10:00:00Z",
    "html_url": "https://github.com/Ev-rain/ERing/releases/tag/v1.2.0",
}


def test_version_key_parses_tags():
    assert updater.version_key("v1.1.2") == (1, 1, 2)
    assert updater.version_key("1.1") == (1, 1, 0)
    assert updater.version_key("v2") == (2, 0, 0)
    assert updater.version_key("nightly") is None
    assert updater.version_key("") is None
    assert updater.version_key(None) is None


def test_version_key_orders_numerically_not_lexically():
    # "1.10.0" 在字符串比较下小于 "1.9.0"，必须按数字比较
    assert updater.version_key("v1.10.0") > updater.version_key("v1.9.0")


def test_fetch_latest_reads_release_fields():
    def fake_get(url, **kw):
        assert url == updater.RELEASES_URL
        return _FakeResp(RELEASE)

    ok, tag, published, html = _with_get(fake_get, lambda: updater.fetch_latest())
    assert ok == "ok", (ok, tag)
    assert tag == "v1.2.0"
    assert published.startswith("2026-11-02")
    assert html.endswith("/v1.2.0")


def test_fetch_latest_retries_without_verify_on_ssl_error():
    seen = []

    def fake_get(url, **kw):
        seen.append(dict(kw))
        if len(seen) == 1:
            raise requests.exceptions.SSLError("certificate verify failed")
        return _FakeResp(RELEASE)

    ok, tag, _, _ = _with_get(fake_get, lambda: updater.fetch_latest())
    assert ok == "ok", ok
    assert tag == "v1.2.0"
    assert len(seen) == 2, seen
    assert seen[1].get("verify") is False


def test_fetch_latest_reports_error_text():
    def fake_get(url, **kw):
        raise requests.exceptions.ConnectionError("boom")

    ok, msg = _with_get(fake_get, lambda: updater.fetch_latest())
    assert ok == "error"
    assert "boom" in msg


def test_check_reports_update_when_remote_is_newer():
    def fake_get(url, **kw):
        return _FakeResp(RELEASE)

    info = _with_get(fake_get, lambda: updater.check("v1.1.2"))
    assert info.status == "update", info
    assert info.tag == "v1.2.0"
    assert info.url.endswith("/v1.2.0")


def test_check_reports_current_when_versions_match():
    def fake_get(url, **kw):
        return _FakeResp(RELEASE)

    info = _with_get(fake_get, lambda: updater.check("v1.2.0"))
    assert info.status == "current", info


def test_check_reports_remote_older_when_local_is_ahead():
    def fake_get(url, **kw):
        return _FakeResp(RELEASE)

    info = _with_get(fake_get, lambda: updater.check("v1.3.0"))
    assert info.status == "remote_older", info


def test_check_treats_unparsable_local_version_as_current():
    def fake_get(url, **kw):
        return _FakeResp(RELEASE)

    info = _with_get(fake_get, lambda: updater.check("dev"))
    assert info.status == "current", info


def test_check_surfaces_error_status():
    def fake_get(url, **kw):
        raise requests.exceptions.Timeout("slow")

    info = _with_get(fake_get, lambda: updater.check("v1.1.2"))
    assert info.status == "error"
    assert "slow" in info.message


def test_check_handles_missing_tag():
    def fake_get(url, **kw):
        return _FakeResp({"tag_name": "", "published_at": "", "html_url": ""})

    info = _with_get(fake_get, lambda: updater.check("v1.1.2"))
    assert info.status == "no_tag", info


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
    print("ALL TESTS PASSED")
