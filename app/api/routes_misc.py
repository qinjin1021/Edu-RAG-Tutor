"""TTS 语音合成与健康检查路由。"""

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel

from app.tts.speaker import synthesize

router = APIRouter()


class TtsBody(BaseModel):
    text: str
    voice: str = ""  # 可选：临时指定音色（设置弹窗试听）；留空用已保存音色


@router.post("/api/tts")
def tts(body: TtsBody):
    text = (body.text or "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="text 不能为空")
    try:
        audio, ext = synthesize(text, voice=body.voice.strip() or None)
    except RuntimeError:
        raise HTTPException(status_code=503, detail="TTS unavailable")
    media_type = "audio/mpeg" if ext == ".mp3" else "audio/wav"
    return Response(content=audio, media_type=media_type)


@router.get("/api/health")
def health():
    return {"ok": True}
