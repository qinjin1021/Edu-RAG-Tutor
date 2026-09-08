"""模型设置路由：读取 / 保存 / 测试连接 + 形象皮肤 / 语音音色。

API Key 只回传掩码，前端修改时留空表示保持不变。
配置持久化在 SQLite prefs 表，热生效（重置 LLM 客户端单例）。
皮肤：static/assets/character/<皮肤ID>/ 目录即一套皮肤，扫描自动发现。
"""

import json

from fastapi import APIRouter
from pydantic import BaseModel

from app.config import BUNDLE_DIR, IS_FROZEN, PROJECT_ROOT, get_settings
from app.db import models as db
from app.tts import speaker
from app.tutor import llm

router = APIRouter()

# 5 种表情（与前端 EMOTIONS 一致）；图件支持 .gif/.png/.webp/.apng 混用
EMOTIONS = ("idle", "think", "happy", "encourage", "surprise")
IMAGE_EXTS = (".gif", ".png", ".webp", ".apng")
CHARACTER_DIR = (BUNDLE_DIR if IS_FROZEN else PROJECT_ROOT) / "static" / "assets" / "character"


def _scan_skins() -> list[dict]:
    """扫描皮肤目录。每套皮肤 = character/ 下一个子目录 + 5 表情图；skin.json 可选声明显示名。"""
    skins: list[dict] = []
    if not CHARACTER_DIR.is_dir():
        return skins
    for d in sorted(CHARACTER_DIR.iterdir()):
        if not d.is_dir() or d.name.startswith("."):
            continue
        files = {}
        for emo in EMOTIONS:
            for ext in IMAGE_EXTS:
                if (d / f"{emo}{ext}").is_file():
                    files[emo] = f"{emo}{ext}"
                    break
        if not files:
            continue
        name = d.name
        meta = d / "skin.json"
        if meta.is_file():
            try:
                # utf-8-sig：兼容记事本保存的带 BOM 文件
                name = json.loads(meta.read_text(encoding="utf-8-sig")).get("name") or name
            except Exception:
                pass
        skins.append({"id": d.name, "name": name, "files": files})
    return skins


def _current_skin(skins: list[dict]) -> dict | None:
    """prefs 保存的皮肤；无效/未设置时回退第一套。"""
    skin_id = db.get_pref("ui_skin") or "default"
    for s in skins:
        if s["id"] == skin_id:
            return s
    return skins[0] if skins else None


class SettingsBody(BaseModel):
    api_key: str = ""
    base_url: str = ""
    model: str = ""
    clear_api_key: bool = False  # True = 清除已保存的 Key（回到未配置状态）
    skin: str = ""   # 皮肤 ID；留空 = 保持不变
    voice: str = ""  # edge-tts 音色 ID；留空 = 保持不变


def _mask(key: str) -> str:
    """API Key 打码：保留头尾，中间用 ***。"""
    if not key:
        return ""
    if len(key) <= 8:
        return "***"
    return f"{key[:5]}***{key[-4:]}"


@router.get("/api/settings")
def get_settings_route():
    """返回当前生效的模型配置（Key 打码）、皮肤与音色信息。"""
    cfg = llm.effective_llm_config()
    skins = _scan_skins()
    skin = _current_skin(skins)
    return {
        "configured": bool(cfg["api_key"]),
        "api_key_masked": _mask(cfg["api_key"]),
        "base_url": cfg["base_url"],
        "model": cfg["model"],
        "skins": skins,
        "skin": skin["id"] if skin else "default",
        "skin_files": skin["files"] if skin else {},
        "voices": speaker.VOICES,
        "voice": speaker.effective_voice(),
    }


@router.put("/api/settings")
def put_settings(body: SettingsBody):
    """保存配置。api_key 留空 = 保持现有 Key；base_url/model 留空 = 恢复默认；
    clear_api_key=True 时清除已保存的 Key。"""
    settings = get_settings()
    if body.clear_api_key:
        db.set_pref("llm_api_key", "")
    elif body.api_key.strip():
        db.set_pref("llm_api_key", body.api_key.strip())
    db.set_pref("llm_base_url", body.base_url.strip())
    db.set_pref("llm_model", body.model.strip())
    # 皮肤/音色：留空 = 保持不变；填了但无效则忽略
    if body.skin.strip() and any(s["id"] == body.skin.strip() for s in _scan_skins()):
        db.set_pref("ui_skin", body.skin.strip())
    if body.voice.strip() and any(v["id"] == body.voice.strip() for v in speaker.VOICES):
        db.set_pref("tts_voice", body.voice.strip())
    llm.reset_client()  # 热生效
    cfg = llm.effective_llm_config()
    return {
        "ok": True,
        "configured": bool(cfg["api_key"]),
        "api_key_masked": _mask(cfg["api_key"]),
        "skin": db.get_pref("ui_skin") or "default",
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
