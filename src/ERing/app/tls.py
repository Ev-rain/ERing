# -*- coding: utf-8 -*-
"""HTTPS 信任库：certifi + Windows 系统证书存储，合并后全局生效。

为什么需要：开着系统代理（Clash / Steam++ / 公司代理 / 安全软件等）时，
本地代理会用自己的根证书重新签发 HTTPS 流量。该根证书装在 Windows 证书库里
（所以浏览器访问正常），但**不在** Python 的 certifi 包里，于是 requests 报：
    certificate verify failed: unable to get local issuer certificate
余额查询、翻译接口、检查更新会一起失败——看起来像「接口换了」，
实际是本机信任库与系统证书库不一致。

这里把 Windows 的 ROOT / CA 存储并进 certifi，写成一个 PEM，并通过
REQUESTS_CA_BUNDLE / CURL_CA_BUNDLE / SSL_CERT_FILE 指向它：
证书校验保持完整（不降级成 verify=False），同时让代理环境可用。
"""
import os
import ssl
import time
from pathlib import Path

from app.config import CONFIG_DIR

BUNDLE_FILE = CONFIG_DIR / "ca_bundle.pem"
REBUILD_AFTER_SEC = 24 * 3600  # 系统证书库会变化，一天重建一次足够

_installed = False


def _certifi_pem():
    try:
        import certifi

        return Path(certifi.where()).read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return ""


def _windows_store_pem():
    """导出 Windows ROOT / CA 存储里的证书（DER -> PEM）。"""
    parts = []
    for store in ("ROOT", "CA"):
        try:
            items = ssl.enum_certificates(store)
        except Exception:
            continue
        for cert, encoding, _trust in items:
            if encoding != "x509_asn":
                continue
            try:
                parts.append(ssl.DER_cert_to_PEM_cert(cert))
            except Exception:
                pass
    return "".join(parts)


def build_bundle(force=False):
    """生成合并信任库并返回路径；无法生成时返回 None（沿用 certifi）。"""
    try:
        if not force and BUNDLE_FILE.exists():
            if time.time() - BUNDLE_FILE.stat().st_mtime < REBUILD_AFTER_SEC:
                return BUNDLE_FILE
        base = _certifi_pem()
        extra = _windows_store_pem()
        if not extra:
            return BUNDLE_FILE if BUNDLE_FILE.exists() else None
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        BUNDLE_FILE.write_text(base + "\n" + extra, encoding="utf-8")
        return BUNDLE_FILE
    except Exception:
        return BUNDLE_FILE if BUNDLE_FILE.exists() else None


def install():
    """进程启动时调用一次：让 requests 等使用合并后的信任库。

    已由用户/环境显式指定信任库时不覆盖（用 setdefault）。返回生效的路径或 None。
    """
    global _installed
    if _installed:
        return os.environ.get("REQUESTS_CA_BUNDLE") or None
    _installed = True
    path = build_bundle()
    if not path:
        return None
    value = str(path)
    for key in ("REQUESTS_CA_BUNDLE", "CURL_CA_BUNDLE", "SSL_CERT_FILE"):
        os.environ.setdefault(key, value)
    return value
