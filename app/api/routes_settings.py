"""模型设置路由：读取 / 保存 / 测试连接 + 语音音色。

API Key 只回传掩码，前端修改时留空表示保持不变。
配置持久化在 SQLite prefs 表，热生效（重置 LLM 客户端单例）。
"""

from fastapi import APIRouter
from pydantic import BaseModel

from app.db import models as db
from app.tts import speaker
from app.tutor import llm

router = APIRouter()


class SettingsBody(BaseModel):
    api_key: str = ""
    base_url: str = ""
    model: str = ""
    clear_api_key: bool = False  # True = 清除已保存的 Key（回到未配置状态）
    voice: str = ""  # edge-tts 音色 ID；留空 = 保持不变
    thinking: bool | None = None  # 深度思考开关；None = 保持不变


def _mask(key: str) -> str:
    """API Key 打码：保留头尾，中间用 ***。"""
    if not key:
        return ""
    if len(key) <= 8:
        return "***"
    return f"{key[:5]}***{key[-4:]}"


@router.get("/api/settings")
def get_settings_route():
    """返回当前生效的模型配置（Key 打码）与音色信息。"""
    cfg = llm.effective_llm_config()
    return {
        "configured": bool(cfg["api_key"]),
        "api_key_masked": _mask(cfg["api_key"]),
        "base_url": cfg["base_url"],
        "model": cfg["model"],
        "voices": speaker.VOICES,
        "voice": speaker.effective_voice(),
        "thinking": llm.thinking_enabled(),
    }


@router.put("/api/settings")
def put_settings(body: SettingsBody):
    """保存配置。api_key 留空 = 保持现有 Key；base_url/model 留空 = 恢复默认；
    clear_api_key=True 时清除已保存的 Key。"""
    if body.clear_api_key:
        db.set_pref("llm_api_key", "")
    elif body.api_key.strip():
        db.set_pref("llm_api_key", body.api_key.strip())
    db.set_pref("llm_base_url", body.base_url.strip())
    db.set_pref("llm_model", body.model.strip())
    # 深度思考开关：显式传入才更新
    if body.thinking is not None:
        db.set_pref("llm_thinking", "1" if body.thinking else "0")
    # 音色：留空 = 保持不变；填了但无效则忽略
    if body.voice.strip() and any(v["id"] == body.voice.strip() for v in speaker.VOICES):
        db.set_pref("tts_voice", body.voice.strip())
    llm.reset_client()  # 热生效
    cfg = llm.effective_llm_config()
    return {
        "ok": True,
        "configured": bool(cfg["api_key"]),
        "api_key_masked": _mask(cfg["api_key"]),
        "voice": speaker.effective_voice(),
    }


@router.post("/api/settings/test")
def test_settings(body: SettingsBody):
    """用提交的配置（空字段沿用已保存值）发一条最小消息测试连通性。"""
    cfg = llm.effective_llm_config(
        {"api_key": body.api_key, "base_url": body.base_url, "model": body.model}
    )
    if not cfg["api_key"]:
        return {"ok": False, "message": "请先填写 API Key"}
    if not cfg["base_url"]:
        return {"ok": False, "message": "请填写接口地址（Base URL）"}
    if not cfg["model"]:
        return {"ok": False, "message": "请填写模型名称"}
    try:
        reply = llm.test_connection(cfg)
        return {"ok": True, "reply": reply or "（模型已响应）"}
    except Exception as exc:  # noqa: BLE001 —— 各类网络/鉴权错误统一回传给前端
        return {"ok": False, "message": str(exc)[:300]}
