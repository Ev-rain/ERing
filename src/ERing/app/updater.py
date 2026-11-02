# -*- coding: utf-8 -*-
"""检查更新：查询 GitHub 最新 release，并与当前版本比较。

这里只做网络请求与版本判定，不依赖 Qt；设置面板只负责把结果渲染成文字，
因此这套逻辑可以离线单测（见 tests/test_updater.py）。
"""
from __future__ import annotations

import re
import warnings
from typing import NamedTuple, Optional, Tuple

import requests

RELEASES_URL = "https://api.github.com/repos/Ev-rain/ERing/releases/latest"
TIMEOUT = 15

_VER_RE = re.compile(r"(\d+)(?:\.(\d+))?(?:\.(\d+))?")


class UpdateInfo(NamedTuple):
    """一次检查更新的结论。status 取值见 check()。"""

    status: str = "error"
    tag: str = ""
    date: str = ""
    url: str = ""
    message: str = ""


def version_key(text) -> Optional[Tuple[int, int, int]]:
    """把 'v1.2.3' / '1.2' 解析成可比较的数字元组；解析不出来返回 None。

    按整数比较而不是字符串：'1.10.0' 必须大于 '1.9.0'。
    """
    m = _VER_RE.search(str(text or ""))
    if not m:
        return None
    return tuple(int(g) if g else 0 for g in m.groups())


def _get(url, timeout=TIMEOUT):
    try:
        return requests.get(url, timeout=timeout)
    except requests.exceptions.SSLError:
        # 代理/杀毒软件环境证书链不全时，仅这一次版本查询降级为不校验；
        # 该请求只读公开的版本号，不含任何凭据。
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            return requests.get(url, timeout=timeout, verify=False)


def fetch_latest(url=RELEASES_URL, timeout=TIMEOUT):
    """返回 ('ok', tag, published_at, html_url) 或 ('error', 原因)。"""
    try:
        resp = _get(url, timeout)
        resp.raise_for_status()
        data = resp.json()
        tag = str(data.get("tag_name", "")).strip()
        published = str(data.get("published_at", "")).strip()
        html = str(data.get("html_url", "")).strip()
        return ("ok", tag, published, html)
    except Exception as e:  # noqa: BLE001 —— 任何网络/解析问题都只影响这次查询
        return ("error", str(e))


def check(current, url=RELEASES_URL, timeout=TIMEOUT) -> UpdateInfo:
    """对比当前版本与远端最新发布。

    status:
        update      远端更新，应提示并打开下载页
        current     相同（或当前版本无法解析），已是最新
        remote_older  当前版本比远端还新（本地领先于已发布版本）
        no_tag      远端没有可用的版本号
        error       查询失败，message 里是原因
    """
    ok, *rest = fetch_latest(url, timeout)
    if ok == "error":
        return UpdateInfo("error", message=rest[0])
    tag, published, html = rest
    if not tag:
        return UpdateInfo("no_tag")
    latest_key = version_key(tag)
    if latest_key is None:
        return UpdateInfo("no_tag", tag=tag, date=published[:10], url=html)
    cur_key = version_key(current)
    date = published[:10]
    if cur_key is None or latest_key == cur_key:
        return UpdateInfo("current", tag, date, html)
    if latest_key > cur_key:
        return UpdateInfo("update", tag, date, html)
    return UpdateInfo("remote_older", tag, date, html)
