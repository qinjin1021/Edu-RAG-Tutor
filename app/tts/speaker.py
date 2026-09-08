"""语音合成：edge-tts 优先、pyttsx3 本地降级，结果按 md5 磁盘缓存。

仅在被 FastAPI 同步路由（线程池线程）调用，无嵌套事件循环问题；
模块级锁保证同一时刻只有一次合成。
"""

import asyncio
import hashlib
import re
import threading
from pathlib import Path

from app.config import get_paths, get_settings
from app.db import models as db

# 精选 edge-tts 中文音色（供设置界面选择/试听；pyttsx3 离线降级不适用音色）
VOICES = [
    {"id": "zh-CN-xiaoyiNeural", "name": "晓伊 · 活泼少女（默认）"},
    {"id": "zh-CN-xiaoxiaoNeural", "name": "晓晓 · 温暖亲切"},
    {"id": "zh-CN-xiaomoNeural", "name": "晓墨 · 多角色"},
    {"id": "zh-CN-xiaochenNeural", "name": "晓辰 · 沉稳清晰"},
    {"id": "zh-CN-yunxiNeural", "name": "云希 · 阳光少年"},
    {"id": "zh-CN-yunyangNeural", "name": "云扬 · 新闻播音"},
]


def effective_voice(voice: str | None = None) -> str:
    """实际使用音色：临时指定 > prefs(tts_voice) > 配置默认。"""
    if voice:
        return voice
    return db.get_pref("tts_voice") or get_settings().tts_voice


# 串行化合成，防止并发调用 pyttsx3/edge-tts 出问题
_lock = threading.Lock()

_MAX_CHARS = 600
_MD_PATTERN = re.compile(r"[*#`>]")  # 需去除的 markdown 符号
_SENTENCE_END = "。！？；.!?"


def _clean_text(text: str) -> str:
    """去 markdown 符号、压平空白；超长截断到最近的句末标点。"""
    text = _MD_PATTERN.sub("", text)
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) <= _MAX_CHARS:
        return text
    cut = text[:_MAX_CHARS]
    for i in range(len(cut) - 1, -1, -1):
        if cut[i] in _SENTENCE_END:
            return cut[: i + 1]
    return cut


def _cache_stem(text: str, voice: str) -> Path:
    """返回缓存文件路径（不含扩展名），key=md5(文本+实际音色)。"""
    digest = hashlib.md5(f"{text}{voice}".encode("utf-8")).hexdigest()
    return Path(get_paths()["audio_dir"]) / digest


def _read_cache(stem: Path) -> tuple[bytes, str] | None:
    """命中缓存则返回 (音频字节, 扩展名)。"""
    for ext in (".mp3", ".wav"):
        cached = stem.with_suffix(ext)
        if cached.exists() and cached.stat().st_size > 0:
            return cached.read_bytes(), ext
    return None


def _edge_tts(stem: Path, text: str, voice: str) -> bytes:
    """在线合成 mp3，超时或失败抛异常。"""
    import edge_tts

    settings = get_settings()

    async def _collect() -> bytes:
        chunks = []
        async for chunk in edge_tts.Communicate(text, voice).stream():
            if chunk["type"] == "audio":
                chunks.append(chunk["data"])
        return b"".join(chunks)

    data = asyncio.run(asyncio.wait_for(_collect(), timeout=settings.tts_timeout))
    if not data:
        raise RuntimeError("edge-tts 返回空音频")
    stem.with_suffix(".mp3").write_bytes(data)
    return data


def _pyttsx3(stem: Path, text: str) -> bytes:
    """本地降级合成 wav，失败抛异常。"""
    import pyttsx3

    wav_path = stem.with_suffix(".wav")
    engine = pyttsx3.init()
    try:
        engine.setProperty("rate", 175)
        engine.save_to_file(text, str(wav_path))
        engine.runAndWait()
    finally:
        engine.stop()
    data = wav_path.read_bytes()
    if not data:
        raise RuntimeError("pyttsx3 返回空音频")
    return data


def synthesize(text: str, voice: str | None = None) -> tuple[bytes, str]:
    """合成语音，返回 (音频字节, 扩展名 .mp3/.wav)。

    voice 可临时指定音色（设置界面试听场景）；缺省用 effective_voice()。
    两级失败抛 RuntimeError。
    """
    text = _clean_text(text)
    use_voice = effective_voice(voice)
    stem = _cache_stem(text, use_voice)
    cached = _read_cache(stem)
    if cached:
        return cached
    with _lock:
        cached = _read_cache(stem)  # 拿到锁后再查一次，避免重复合成
        if cached:
            return cached
        try:
            return _edge_tts(stem, text, use_voice), ".mp3"
        except Exception:
            pass
        try:
            return _pyttsx3(stem, text), ".wav"
        except Exception:
            raise RuntimeError("TTS unavailable")
