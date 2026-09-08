"""全局配置：通过 pydantic-settings 从 .env / 环境变量读取。

打包（PyInstaller frozen）模式下的差异：
- 数据目录（数据库/向量库/音频/上传）放到用户目录 %APPDATA%/SiXiaoJie/data，
  安装目录（Program Files）只读不可写；
- Embedding 模型从打包内置的 models/ 目录加载，不再联网下载。
"""

import os
import sys
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings

# 是否运行在 PyInstaller 打包后的 exe 中
IS_FROZEN = bool(getattr(sys, "frozen", False))

# 项目根目录（开发模式：app/config.py 的上一级；打包模式：exe 所在目录）
if IS_FROZEN:
    PROJECT_ROOT = Path(sys.executable).resolve().parent
else:
    PROJECT_ROOT = Path(__file__).resolve().parent.parent

# 打包资源目录（PyInstaller onedir 模式下 datas 解包位置）
BUNDLE_DIR = Path(getattr(sys, "_MEIPASS", PROJECT_ROOT))


class Settings(BaseSettings):
    """应用配置项，均可通过同名环境变量或 .env 覆盖。"""

    # ---------- LLM ----------
    llm_api_key: str = ""
    llm_base_url: str = "https://api.deepseek.com"
    llm_model: str = "deepseek-chat"
    llm_temperature: float = 0.5
    llm_max_tokens: int = 2048

    # ---------- Embedding / 检索 ----------
    embedding_model: str = "BAAI/bge-small-zh-v1.5"
    embedding_dimension: int = 512
    chunk_size: int = 500
    chunk_overlap: int = 80
    top_k: int = 4

    # ---------- 学习/掌握度 ----------
    mastery_threshold: float = 80.0

    # ---------- TTS ----------
    tts_voice: str = "zh-CN-xiaoyiNeural"
    tts_timeout: float = 10.0

    # ---------- 会话 ----------
    history_limit: int = 20

    # ---------- 存储/服务 ----------
    data_dir: str = "data"
    host: str = "127.0.0.1"
    port: int = 8760

    model_config = {
        "env_file": str(PROJECT_ROOT / ".env"),
        "env_file_encoding": "utf-8",
        "extra": "ignore",
    }


@lru_cache
def get_settings() -> Settings:
    """返回单例 Settings（进程内缓存）。"""
    return Settings()


def _resolve_data_dir() -> Path:
    """数据目录：开发模式在项目根下，打包模式在用户目录（可写）。"""
    if IS_FROZEN:
        # 环境变量优先（Windows 常规路径），兼容非标准环境
        env_appdata = os.environ.get("APPDATA")
        appdata = Path(env_appdata) if env_appdata else Path.home() / "AppData" / "Roaming"
        return appdata / "SiXiaoJie" / "data"
    return PROJECT_ROOT / get_settings().data_dir


def get_paths() -> dict:
    """返回数据相关路径并确保目录存在。

    路径基于 Settings.data_dir（相对项目根）解析，
    调用时自动创建所需目录（parents=True）。
    """
    data_dir = _resolve_data_dir()
    chroma_dir = data_dir / "chroma"
    audio_dir = data_dir / "audio"
    uploads_dir = data_dir / "uploads"
    db_path = data_dir / "app.db"

    for directory in (data_dir, chroma_dir, audio_dir, uploads_dir):
        directory.mkdir(parents=True, exist_ok=True)

    return {
        "db_path": str(db_path),
        "chroma_dir": str(chroma_dir),
        "audio_dir": str(audio_dir),
        "uploads_dir": str(uploads_dir),
    }


def get_embedding_model_path() -> str:
    """Embedding 模型路径：打包模式用内置 models/，开发模式用模型名（走 HF 缓存）。"""
    if IS_FROZEN:
        local = BUNDLE_DIR / "models" / "bge-small-zh-v1.5"
        if (local / "config.json").exists():
            return str(local)
    return get_settings().embedding_model
