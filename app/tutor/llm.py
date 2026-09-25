"""LLM 客户端：openai SDK 懒加载单例，提供流式/非流式/JSON 三种调用。

运行时配置优先级：prefs 表（用户在界面修改） > .env / 默认值。
修改设置后调用 reset_client() 重建单例，无需重启应用。
"""

import json
import logging
from typing import Iterator, Optional

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)

# 懒加载的客户端单例
_client = None

# 流式相邻 chunk 的最大等待秒数：所有调用统一走流式，读超时只约束
# chunk 间隔——生成期间 chunk 持续到达则长任务不受影响；而连接卡死/
# 网关挂起能在该时间内报错返回，而不是挂满 SDK 默认 600 秒再重试。
# 正常 chunk 间隔远小于 1 秒。
_STREAM_IDLE_TIMEOUT = 90.0

# prefs 表中的键名（与 Settings 字段同名加 llm_ 前缀）
_PREF_KEYS = ("llm_api_key", "llm_base_url", "llm_model")


def thinking_enabled() -> bool:
    """深度思考开关：prefs 覆盖 .env 默认（见 Settings.llm_thinking）。"""
    from app.db import models as db

    try:
        v = db.get_pref("llm_thinking")
    except Exception:  # 数据库不可用时退回默认值，不阻塞
        v = None
    if v is None or v == "":
        return get_settings().llm_thinking
    return str(v).strip().lower() in ("1", "true")


def effective_llm_config(overrides: Optional[dict] = None) -> dict:
    """返回当前生效的 LLM 配置：prefs 覆盖 .env 默认，overrides 再覆盖。

    overrides 中空值会被忽略（例如测试连接时 key 留空表示沿用已保存的）。
    """
    from app.db import models as db

    s = get_settings()
    cfg = {
        "api_key": s.llm_api_key,
        "base_url": s.llm_base_url,
        "model": s.llm_model,
    }
    for field, pref_key in zip(("api_key", "base_url", "model"), _PREF_KEYS):
        try:
            v = db.get_pref(pref_key)
        except Exception:  # 数据库不可用时退回默认值，不阻塞
            v = None
        if v:
            cfg[field] = v
    if overrides:
        for k, v in overrides.items():
            if v:
                cfg[k] = v
    return cfg


def _norm_base_url(base_url: str) -> str:
    """不以 /v1 结尾则补上（兼容不同网关写法）。"""
    base_url = (base_url or "").strip().rstrip("/")
    if not base_url:
        return ""
    if not base_url.endswith("/v1"):
        base_url += "/v1"
    return base_url


def _get_client():
    """懒加载创建 openai 客户端（进程内单例）。"""
    global _client
    if _client is None:
        from openai import OpenAI  # 延迟导入，避免启动开销

        cfg = effective_llm_config()
        _client = OpenAI(
            api_key=cfg["api_key"],
            base_url=_norm_base_url(cfg["base_url"]),
            timeout=httpx.Timeout(_STREAM_IDLE_TIMEOUT, connect=15.0),
            max_retries=1,  # SDK 默认重试 2 次，网络抖动会让等待时间翻三倍
        )
    return _client


def reset_client() -> None:
    """配置变更后重置单例，下次调用时按新配置重建。"""
    global _client
    _client = None


def test_connection(cfg: dict) -> str:
    """用给定配置发一条最小消息验证连通性，返回模型回复文本；失败抛异常。"""
    from openai import OpenAI

    client = OpenAI(api_key=cfg["api_key"], base_url=_norm_base_url(cfg["base_url"]), timeout=20)
    resp = client.chat.completions.create(
        model=cfg["model"],
        messages=[{"role": "user", "content": "请只回复四个字：连接成功"}],
        max_tokens=10,
    )
    return (resp.choices[0].message.content or "").strip()


def _defaults(temperature, max_tokens) -> dict:
    """组装公共请求参数：模型名 + 未显式指定时的默认采样参数。"""
    cfg = effective_llm_config()
    d = {
        "model": cfg["model"],
        "temperature": get_settings().llm_temperature if temperature is None else temperature,
        "max_tokens": get_settings().llm_max_tokens if max_tokens is None else max_tokens,
    }
    if not thinking_enabled():
        # 关闭深度思考：推理模型跳过思维链，回复显著提速；
        # 非思考模型（deepseek-chat 等）实测会忽略该参数
        d["extra_body"] = {"reasoning_effort": "none"}
    return d


def chat_stream(messages, temperature=None, max_tokens=None) -> Iterator[str]:
    """流式对话，逐段 yield 文本增量。"""
    stream = _get_client().chat.completions.create(
        messages=messages,
        stream=True,
        **_defaults(temperature, max_tokens),
    )
    for chunk in stream:
        if not chunk.choices:
            continue
        delta = chunk.choices[0].delta.content
        if delta:
            yield delta


def _stream_text(messages, temperature=None, max_tokens=None, response_format=None) -> str:
    """流式请求并聚合为完整文本（非流式调用的统一底层通道）。

    chat_once / chat_json 也走流式聚合：生成期间 chunk 持续到达，
    读超时只约束 chunk 间隔——长生成（如 8000 token 出题）不受影响，
    而连接卡死能在 90 秒内被发现并报错，避免"无响应干等几分钟"。
    """
    kwargs = dict(messages=messages, stream=True, **_defaults(temperature, max_tokens))
    if response_format is not None:
        kwargs["response_format"] = response_format
    parts: list[str] = []
    for chunk in _get_client().chat.completions.create(**kwargs):
        if not chunk.choices:
            continue
        delta = chunk.choices[0].delta.content
        if delta:
            parts.append(delta)
    return "".join(parts)


def chat_once(messages, temperature=None, max_tokens=None) -> str:
    """非流式对话，返回完整回复文本。"""
    return _stream_text(messages, temperature, max_tokens)


def _strip_fences(text: str) -> str:
    """剥掉 markdown 代码围栏（```json ... ```）。"""
    text = text.strip()
    if text.startswith("```"):
        end = text.find("\n")
        if end != -1:
            text = text[end + 1:]
        if text.rstrip().endswith("```"):
            text = text.rstrip()[:-3]
    return text.strip()


def chat_json_with_raw(messages, temperature=None, max_tokens=None) -> tuple[Optional[dict], str]:
    """请求 JSON 输出，返回 (解析结果或 None, 原始文本)。

    解析失败时剥掉围栏重试；仍失败返回 (None, 原文)——调用方可对原文做
    截断救捞（如推理模型 max_tokens 不足导致 JSON 写到一半被截断）。
    """
    content = _stream_text(
        messages, temperature, max_tokens, response_format={"type": "json_object"}
    )
    try:
        return json.loads(content), content
    except json.JSONDecodeError:
        pass
    try:
        # 二次尝试：剥掉可能的 markdown 围栏
        return json.loads(_strip_fences(content)), content
    except json.JSONDecodeError:
        logger.warning("LLM 返回内容无法解析为 JSON: %s", content[:200])
        return None, content


def chat_json(messages, temperature=None, max_tokens=None) -> Optional[dict]:
    """请求 JSON 输出并解析为 dict；失败返回 None。"""
    return chat_json_with_raw(messages, temperature, max_tokens)[0]
