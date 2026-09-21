"""离线语音识别：sherpa-onnx SenseVoice 模型，纯本地、不联网。

模型放在 models/asr/（model.int8.onnx + tokens.txt），与离线语音包同模式：
放下即用、删除即恢复"未配置"状态。识别 16kHz 单声道 WAV。
"""

import logging
import tempfile
from pathlib import Path

from app.config import BUNDLE_DIR, IS_FROZEN, PROJECT_ROOT

logger = logging.getLogger(__name__)

# 模型目录（打包后随 _internal/models 分发，但 asr/ 被打包排除——由用户自行下载放入）
ASR_DIR = (BUNDLE_DIR if IS_FROZEN else PROJECT_ROOT) / "models" / "asr"

# 懒加载单例
_recognizer = None


def find_asr_model_dir() -> Path | None:
    """models/asr/ 下含任一 *.onnx 即视为已配置识别模型，返回该目录。"""
    if not ASR_DIR.is_dir():
        return None
    for p in ASR_DIR.iterdir():
        if p.is_file() and p.suffix.lower() == ".onnx":
            return ASR_DIR
    return None


def _get_recognizer():
    """懒加载 OfflineRecognizer（SenseVoice），失败抛异常由调用方转 503。"""
    global _recognizer
    if _recognizer is None:
        import sherpa_onnx

        model_dir = find_asr_model_dir()
        if model_dir is None:
            raise RuntimeError("asr model not configured")
        model = next(
            p for p in sorted(model_dir.iterdir())
            if p.is_file() and p.suffix.lower() == ".onnx"
        )
        tokens = model_dir / "tokens.txt"
        if not tokens.is_file():
            raise RuntimeError("asr tokens.txt missing")
        _recognizer = sherpa_onnx.OfflineRecognizer.from_sense_voice(
            model=str(model),
            tokens=str(tokens),
            use_itn=True,  # 数字/日期规整并带标点
        )
        logger.info("ASR 模型已加载：%s", model.name)
    return _recognizer


def _read_wav(path: Path):
    """读 16bit 单/多声道 WAV，返回 (采样率, float32 [-1,1] 单声道)。

    sherpa-onnx 1.13+ 无 read_wave，用标准库 wave 自行解码；
    非 16k 输入线性重采样到 16k（SenseVoice 特征提取要求）。
    """
    import wave as wave_mod

    import numpy as np

    with wave_mod.open(str(path), "rb") as w:
        sr = w.getframerate()
        channels = w.getnchannels()
        width = w.getsampwidth()
        raw = w.readframes(w.getnframes())
    if width != 2:
        raise RuntimeError("only 16bit wav supported")
    audio = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
    if channels > 1:
        audio = audio.reshape(-1, channels).mean(axis=1)
    if sr != 16000 and len(audio) > 0:
        target = int(len(audio) * 16000 / sr)
        audio = np.interp(
            np.linspace(0, len(audio) - 1, target), np.arange(len(audio)), audio
        )
        sr = 16000
    return sr, audio


def recognize_wav(wav_bytes: bytes) -> str:
    """识别 16kHz 单声道 WAV 字节，返回文本（无空格分隔的中文为连续串）。

    模型未配置或识别失败抛 RuntimeError。
    """
    recognizer = _get_recognizer()
    tmp = Path(tempfile.gettempdir()) / "eduragtutor_asr_in.wav"
    tmp.write_bytes(wav_bytes)
    try:
        sample_rate, samples = _read_wav(tmp)
        stream = recognizer.create_stream()
        stream.accept_waveform(sample_rate, samples)
        recognizer.decode_stream(stream)
        return stream.result.text.strip()
    finally:
        try:
            tmp.unlink()
        except OSError:
            pass
