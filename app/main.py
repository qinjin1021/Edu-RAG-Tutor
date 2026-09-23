"""应用入口：组装 FastAPI，并以 pywebview 桌面窗口方式启动。

运行方式：python -m app.main
"""

import os

# 必须在任何 HF 相关库（chromadb/sentence-transformers）导入之前设置：
# 本机直连 huggingface.co 会超时，模型已缓存，镜像端点仅作保险。
os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")

import sys
import threading
import time
import urllib.request
import webbrowser
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.api import (
    routes_asr,
    routes_assessment,
    routes_chat,
    routes_material,
    routes_misc,
    routes_quiz,
    routes_search,
    routes_session,
    routes_settings,
)
from app.config import BUNDLE_DIR, IS_FROZEN, PROJECT_ROOT, get_settings
from app.db.database import init_db

# 静态资源目录：开发模式在项目根 static/；打包模式在 bundle 内 static/
STATIC_DIR = (BUNDLE_DIR if IS_FROZEN else PROJECT_ROOT) / "static"


@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_db()
    yield


app = FastAPI(title="Edu-RAG-Tutor", lifespan=lifespan)

app.include_router(routes_session.router)
app.include_router(routes_chat.router)
app.include_router(routes_assessment.router)
app.include_router(routes_quiz.router)
app.include_router(routes_material.router)
app.include_router(routes_search.router)
app.include_router(routes_misc.router)
app.include_router(routes_asr.router)
app.include_router(routes_settings.router)


@app.get("/")
def index():
    return FileResponse(STATIC_DIR / "index.html")


# 前端以相对路径（css/ js/ assets/）引用静态资源，故挂根路径兜底
app.mount("/", StaticFiles(directory=str(STATIC_DIR)), name="static")


def _wait_until_ready(url: str, timeout: float = 60.0) -> bool:
    """轮询健康检查直到后端就绪。"""
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(f"{url}/api/health", timeout=2) as resp:
                if resp.status == 200:
                    return True
        except Exception:
            time.sleep(0.5)
    return False


def _fallback_browser(url: str) -> None:
    """pywebview 不可用时：Edge 应用模式 → 默认浏览器，进程常驻。"""
    import shutil
    import subprocess

    edge = shutil.which("msedge")
    if not edge:
        for candidate in (
            r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
            r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
        ):
            if Path(candidate).exists():
                edge = candidate
                break
    if edge:
        subprocess.Popen([edge, f"--app={url}"])
    else:
        webbrowser.open(url)
    threading.Event().wait()  # 常驻；关闭控制台窗口即退出


def main() -> None:
    # 窗口（打包）模式下 stdout/stderr 可能为 None：uvicorn 日志格式化器会调
    # isatty()、print 也会崩。run.py 已做重定向，这里导入完成后再兜底一次。
    if sys.stdout is None:
        sys.stdout = open(os.devnull, "a", encoding="utf-8")
    if sys.stderr is None:
        sys.stderr = open(os.devnull, "a", encoding="utf-8")

    settings = get_settings()
    url = f"http://{settings.host}:{settings.port}"

    import uvicorn

    server = uvicorn.Server(
        # use_colors=False：避免日志格式化器调用 sys.stdout.isatty()（窗口模式为 None 会崩）
        uvicorn.Config(
            app,
            host=settings.host,
            port=settings.port,
            log_level="warning",
            use_colors=False,
        )
    )
    threading.Thread(target=server.run, daemon=True).start()

    # 无窗口模式：仅启动后端服务（用于打包产物自动化测试等场景）
    if os.environ.get("EDURAGTUTOR_NO_WINDOW") == "1":
        print(f"服务已启动：{url}（无窗口模式，Ctrl+C 退出）")
        try:
            while True:
                time.sleep(3600)
        except KeyboardInterrupt:
            return

    if not _wait_until_ready(url):
        print("警告：后端服务启动超时，仍将尝试打开窗口…")

    try:
        import webview

        webview.create_window(
            "Edu-RAG-Tutor",
            url,
            width=1280,
            height=820,
            min_size=(1000, 680),
        )
        webview.start()
        os._exit(0)  # 窗口关闭后强制退出（uvicorn 线程为 daemon）
    except Exception:
        _fallback_browser(url)


if __name__ == "__main__":
    main()
