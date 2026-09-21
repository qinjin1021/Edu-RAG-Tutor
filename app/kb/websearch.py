"""联网搜索学习资料：Bing 网页解析（免 Key，国内直连）。

原理：请求 Bing 搜索结果页，用正则提取 b_algo 结果块中的标题、
真实链接与摘要。必应链接多为 /ck/a 跳转包装，其中真实地址以
base64url 藏在 u 参数里（前缀 a1），此处解包还原，便于展示域名
与后续直接下载。若必应改版页面结构，仅需调整 _RE_* 正则。
"""

import base64
import html
import re
from urllib.parse import parse_qs, unquote, urlparse

import httpx

_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)

_HEADERS = {
    "User-Agent": _UA,
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.6",
}

# 资料类型 → 追加到查询词的过滤语法
_TYPE_SUFFIX = {
    "pdf": " filetype:pdf",
    "ppt": " filetype:pptx",
    "doc": " filetype:docx",
}

# 结果块 / 标题链接 / 摘要
_RE_ALGO = re.compile(r'<li class="b_algo".*?</li>', re.S)
_RE_H2A = re.compile(r'<h2[^>]*>\s*<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>', re.S)
_RE_P = re.compile(r'<p[^>]*>(.*?)</p>', re.S)
_RE_TAG = re.compile(r"<[^>]+>")
_RE_SPACE = re.compile(r"\s+")


def _clean(fragment: str) -> str:
    """剥 HTML 标签 + 实体还原 + 压缩空白。"""
    text = _RE_SPACE.sub(" ", _RE_TAG.sub("", fragment)).strip()
    return html.unescape(text)


def _unwrap(url: str) -> str:
    """还原 Bing /ck/a 跳转链接中包装的真实地址。"""
    try:
        parsed = urlparse(url)
        if "bing.com" not in parsed.netloc or not parsed.path.startswith("/ck/"):
            return url
        u = parse_qs(parsed.query).get("u", [""])[0]
        if not u.startswith("a1"):
            return url
        raw = u[2:]
        raw += "=" * (-len(raw) % 4)  # base64url 补位
        real = base64.urlsafe_b64decode(raw).decode("utf-8", "ignore")
        return real if real.startswith(("http://", "https://")) else url
    except Exception:
        return url


def search_web(query: str, file_type: str = "all") -> list[dict]:
    """搜索并返回 [{title, url, snippet, host}]，最多 10 条。"""
    q = (query or "").strip() + _TYPE_SUFFIX.get(file_type, "")
    resp = httpx.get(
        "https://www.bing.com/search",
        params={"q": q, "mkt": "zh-CN", "count": "15"},
        headers=_HEADERS,
        timeout=10,
        follow_redirects=True,  # www.bing.com 会按地区 302 到 cn.bing.com 等
    )
    resp.raise_for_status()
    page = resp.text

    results: list[dict] = []
    seen: set[str] = set()
    for block in _RE_ALGO.findall(page):
        m = _RE_H2A.search(block)
        if not m:
            continue
        url = _unwrap(html.unescape(m.group(1))).strip()
        title = _clean(m.group(2))
        if not title or not url.startswith(("http://", "https://")):
            continue
        if url in seen:
            continue
        seen.add(url)
        p = _RE_P.search(block)
        snippet = _clean(p.group(1))[:200] if p else ""
        results.append(
            {"title": title, "url": url, "snippet": snippet, "host": urlparse(url).netloc}
        )
        if len(results) >= 10:
            break
    return results


def suggest_filename(url: str) -> str:
    """从 URL 末段推测资料文件名（解码、去非法字符、限长）。"""
    path = unquote(urlparse(url).path)
    stem = path.rstrip("/").rsplit("/", 1)[-1] if path.rstrip("/") else ""
    stem = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "", stem).strip().rstrip(".")
    if len(stem) > 76:
        stem = stem[-76:]
    return stem or "网络资料"
