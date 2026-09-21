"""语音合成：edge-tts 在线优先 → pyttsx3 系统本机 → sherpa-onnx 离线语音包兜底，
结果按 md5 磁盘缓存。

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
# 注意：音色以 `.venv\Scripts\python.exe -m edge_tts --list-voices` 实时列表为准，
# 晓辰(xiaochen)/晓墨(xiaomo) 已被微软下架，不得再使用。
VOICES = [
    {"id": "zh-CN-xiaoyiNeural", "name": "晓伊 · 活泼少女（默认）"},
    {"id": "zh-CN-xiaoxiaoNeural", "name": "晓晓 · 温暖亲切"},
    {"id": "zh-CN-yunxiNeural", "name": "云希 · 阳光少年"},
    {"id": "zh-CN-yunyangNeural", "name": "云扬 · 新闻播音"},
    {"id": "zh-CN-yunjianNeural", "name": "云健 · 磁性男声"},
    {"id": "zh-CN-yunxiaNeural", "name": "云夏 · 少年可爱"},
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
# emoji 及符号（朗读时不需要，还会被读成"表情"）：象形文字/杂项符号/旗帜/变体选择符等
_EMOJI_PATTERN = re.compile(
    "["
    "\U0001F000-\U0001FAFF"  # 🎉📋🎯💡🌸 等象形与表情符号
    "\U00002600-\U000027BF"  # ✅⚠️☀ 等杂项符号
    "\U00002B00-\U00002BFF"  # ⭐ 等
    "\U0001F1E6-\U0001F1FF"  # 旗帜
    "\U0000FE0F\U0000200D"   # 变体选择符 / 零宽连接符
    "]+"
)
_SENTENCE_END = "。！？；.!?"


def _clean_text(text: str) -> str:
    """去 markdown 符号与 emoji、压平空白；超长截断到最近的句末标点。"""
    text = _EMOJI_PATTERN.sub(" ", text)
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


# sherpa-onnx 离线语音包：懒加载实例按模型目录缓存（换目录自动重建）
_offline_tts = None
_offline_tts_dir: str | None = None


def _offline_model_file(model_dir: Path) -> Path | None:
    """取模型目录内第一个 .onnx 文件（缓存键与模型加载共用同一选择规则）。"""
    for p in sorted(model_dir.iterdir()):
        if p.is_file() and p.suffix.lower() == ".onnx":
            return p
    return None


def _espeak_data_dir(model_dir: Path, model_stem: str) -> str:
    """返回 espeak-ng-data 的可用路径。

    espeak-ng 用窄字节接口打开数据文件，路径含中文等非 ASCII 字符时加载失败
    （如项目放在桌面），此时把数据复制到 %TEMP%（纯 ASCII）再交给 sherpa-onnx；
    已是 ASCII 路径则原样返回，复制失败回退原路径（由在线链路兜底）。
    """
    data_dir = model_dir / "espeak-ng-data"
    if not data_dir.is_dir():
        return ""
    try:
        str(data_dir).encode("ascii")
        return str(data_dir)
    except UnicodeEncodeError:
        pass
    import shutil
    import tempfile

    dest = Path(tempfile.gettempdir()) / "eduragtutor_espeak" / model_stem
    try:
        if not (dest / "phontab").is_file():
            shutil.copytree(data_dir, dest, dirs_exist_ok=True)
        return str(dest)
    except Exception:
        return str(data_dir)


def _sherpa_tts(stem: Path, text: str, model_dir: Path) -> bytes:
    """离线语音包（sherpa-onnx vits 模型）合成 wav，失败抛异常由调用方降级在线。

    模型目录由 methods.find_offline_voice_dir 提供，内含 *.onnx + tokens.txt，
    piper 格式另有 espeak-ng-data/，词典格式另有 lexicon.txt + dict/，按存在性填充。
    """
    import sherpa_onnx

    global _offline_tts, _offline_tts_dir
    if _offline_tts is None or _offline_tts_dir != str(model_dir):
        model = _offline_model_file(model_dir)
        if model is None:
            raise RuntimeError("模型目录内没有 .onnx 文件")
        lexicon = model_dir / "lexicon.txt"
        dict_dir = model_dir / "dict"
        config = sherpa_onnx.OfflineTtsConfig(
            model=sherpa_onnx.OfflineTtsModelConfig(
                vits=sherpa_onnx.OfflineTtsVitsModelConfig(
                    model=str(model),
                    lexicon=str(lexicon) if lexicon.is_file() else "",
                    tokens=str(model_dir / "tokens.txt"),
                    data_dir=_espeak_data_dir(model_dir, model.stem),
                    dict_dir=str(dict_dir) if dict_dir.is_dir() else "",
                ),
            ),
        )
        _offline_tts = sherpa_onnx.OfflineTts(config)
        _offline_tts_dir = str(model_dir)
    audio = _offline_tts.generate(text, sid=0)  # 多说话人模型默认取第 1 个音色
    if not audio.samples:
        raise RuntimeError("离线语音包返回空音频")
    wav_path = stem.with_suffix(".wav")
    sherpa_onnx.write_wave(str(wav_path), audio.samples, audio.sample_rate)
    data = wav_path.read_bytes()
    if not data:
        raise RuntimeError("离线语音包返回空音频")
    return data


def synthesize(
    text: str, voice: str | None = None, model_dir: Path | None = None
) -> tuple[bytes, str]:
    """合成语音，返回 (音频字节, 扩展名 .mp3/.wav)。

    voice 可临时指定音色（设置界面试听场景）；缺省用 effective_voice()。
    model_dir 为学伴离线语音包目录（缓存 key 用 offline2:<模型名>）。
    合成顺序：edge-tts 在线（音质最佳）→ pyttsx3 系统本机 → 离线语音包兜底；
    任一级成功即返回，全部失败抛 RuntimeError。
    """
    text = _clean_text(text)
    if model_dir is not None:
        # 缓存维度按 onnx 模型文件名区分：不同学伴/换模型互不串音。
        # v2：离线包曾是最优先级，旧键 offline: 的缓存是那个时代的产物，
        # 改键使其全部作废，避免优先级改为最后后仍命中旧离线音频。
        mf = _offline_model_file(model_dir)
        use_voice = f"offline2:{mf.stem}" if mf else "offline2:invalid"
    else:
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
            return _edge_tts(stem, text, effective_voice(voice)), ".mp3"
        except Exception:
            pass
        try:
            return _pyttsx3(stem, text), ".wav"
        except Exception:
            pass
        if model_dir is not None:
            try:
                return _sherpa_tts(stem, text, model_dir), ".wav"
            except Exception:
                raise RuntimeError("TTS unavailable")
