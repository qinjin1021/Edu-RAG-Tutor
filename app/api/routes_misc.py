"""TTS 语音合成、健康检查与打开外部链接路由。"""

import webbrowser

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel

from app.tutor.methods import find_offline_voice_dir, get_method
from app.tts.speaker import synthesize

router = APIRouter()


class TtsBody(BaseModel):
    text: str
    voice: str = ""  # 可选：临时指定音色（设置弹窗试听）；留空用已保存音色
    method: str = ""  # 可选：学伴方法 id；该学伴目录有离线语音包时优先离线合成


class OpenUrlBody(BaseModel):
    url: str


@router.post("/api/tts")
def tts(body: TtsBody):
    text = (body.text or "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="text 不能为空")
    model_dir = None
    if body.method.strip():
        model_dir = find_offline_voice_dir(get_method(body.method).skin_dir)
    try:
        audio, ext = synthesize(
            text, voice=body.voice.strip() or None, model_dir=model_dir
        )
    except RuntimeError:
        raise HTTPException(status_code=503, detail="TTS unavailable")
    media_type = "audio/mpeg" if ext == ".mp3" else "audio/wav"
    return Response(content=audio, media_type=media_type)


@router.get("/api/health")
def health():
    return {"ok": True}


@router.post("/api/open_url")
def open_url(body: OpenUrlBody):
    """用系统默认浏览器打开链接（pywebview 下前端 window.open 会占用应用窗口）。"""
    url = (body.url or "").strip()
    if not url.lower().startswith(("http://", "https://")):
        raise HTTPException(status_code=400, detail="仅支持 http/https 链接")
    webbrowser.open(url)
    return {"ok": True}
