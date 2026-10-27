# -*- coding: utf-8 -*-
"""发布版查询：atom 取最新 tag，expanded_assets 取真实 zip 名。

不用 REST API：GitHub 未认证 API 限额 60 次/小时，atom 与网页资源列表不受该限制。
"""
import re
import socket
import urllib.request
from dataclasses import dataclass

from .errors import ReleaseError

GH_ATOM = "https://github.com/Merserk/dlss5-visual-enhancer/releases.atom"
GH_EXPANDED = ("https://github.com/Merserk/dlss5-visual-enhancer/releases/"
               "expanded_assets/")


@dataclass(frozen=True)
class Release:
    tag: str
    asset: str
    url: str


FALLBACK = Release(
    tag="v19.5",
    asset="Visual.Enhancer.v19.5.zip",
    url=("https://github.com/Merserk/dlss5-visual-enhancer/releases/download/"
         "v19.5/Visual.Enhancer.v19.5.zip"),
)


def detect_proxy(timeout=0.35):
    """内部使用：只在下载时自动找本机代理，不在界面暴露端口。"""
    for port in (7890, 7891, 10809, 1080):
        try:
            with socket.create_connection(("127.0.0.1", port), timeout):
                return "http://127.0.0.1:%d" % port
        except OSError:
            continue
    return ""


def http_get(url, proxy="", timeout=20):
    opener = (urllib.request.build_opener(
        urllib.request.ProxyHandler({"http": proxy, "https": proxy}))
        if proxy else urllib.request.build_opener())
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 VEHelper"})
    with opener.open(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8", "replace")


def parse_latest_tag(atom_html):
    tags = re.findall(r"/releases/tag/([^\"'<]+)", atom_html or "")
    if not tags:
        raise ReleaseError("atom 里没找到 tag")
    return tags[0]


def parse_asset(html, tag):
    names = [n for n in re.findall(r"Visual\.Enhancer[^\"'<> ]*?\.zip", html or "", re.I)
             if "archive/refs" not in n]
    names = sorted(set(names))
    if not names:
        raise ReleaseError("发布页里没找到 Visual Enhancer zip")
    prefer = "Visual.Enhancer.%s.zip" % tag
    return prefer if prefer in names else names[0]


def resolve_latest(proxy=None):
    if proxy is None:
        proxy = detect_proxy()
    tag = parse_latest_tag(http_get(GH_ATOM, proxy))
    asset = parse_asset(http_get(GH_EXPANDED + tag, proxy), tag)
    url = ("https://github.com/Merserk/dlss5-visual-enhancer/releases/download/"
           "%s/%s" % (tag, asset))
    return Release(tag=tag, asset=asset, url=url)
