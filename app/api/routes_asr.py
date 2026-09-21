"""语音输入识别路由：接收前端录制的 WAV，返回识别文本。"""

from fastapi import APIRouter, HTTPException, Request

from app.asr import recognizer

router = APIRouter()

_MAX_WAV_BYTES = 15 * 1024 * 1024  # 60s 16k 单声道 16bit 约 1.9MB，留足余量


@router.post("/api/asr")
async def asr(request: Request):
    """离线识别请求体里的 WAV（16kHz 单声道，裸字节流，非 multipart）。

    模型未配置返回 503；请求体为空/过大返回 400。
    """
    data = await request.body()
    if not data:
        raise HTTPException(status_code=400, detail="未收到音频数据")
    if len(data) > _MAX_WAV_BYTES:
        raise HTTPException(status_code=400, detail="音频过大，请控制在 60 秒内")
    try:
        text = recognizer.recognize_wav(data)
    except RuntimeError as exc:
        msg = str(exc)
        if "not configured" in msg or "missing" in msg:
            raise HTTPException(
                status_code=503,
                detail="语音识别模型未配置：请按 语音包说明.txt 下载 SenseVoice 模型放入 models/asr/",
            )
        raise HTTPException(status_code=503, detail="识别失败，请重试")
    return {"text": text}
