"""打包/启动入口：PyInstaller 以此脚本为起点追踪 app 包。

开发模式运行：python run.py
（等价于 python -m app.main，但保证项目根目录在 sys.path 首位，
便于 PyInstaller 正确发现并打包 app 包内全部模块）

打包（窗口）模式下 sys.stdout/stderr 为 None：任何 print / 日志写入都会抛异常，
uvicorn 日志配置也会因 isatty() 崩溃。此处统一重定向到用户目录日志文件
（%APPDATA%\\SiXiaoJie\\sixiaojie.log）；失败则退回 devnull，绝不让流为 None。
"""

import sys

if getattr(sys, "frozen", False):
    import os
    from pathlib import Path

    _base = Path(os.environ.get("APPDATA") or Path.home()) / "SiXiaoJie"
    _diag = []
    try:
        _base.mkdir(parents=True, exist_ok=True)
        _stream = open(_base / "sixiaojie.log", "a", encoding="utf-8", buffering=1)
        _diag.append(f"stdout redirect OK -> {_base / 'sixiaojie.log'}")
    except BaseException as e:  # noqa: BLE001 —— 诊断目的，任何异常都兜住
        _diag.append(f"stdout redirect FAIL ({type(e).__name__}: {e!r}), fallback devnull")
        _stream = open(os.devnull, "a", encoding="utf-8")

    # 赋值放在 try 外：无论成败都保证 stdout/stderr 非 None
    sys.stdout = _stream
    sys.stderr = _stream

    # 诊断信息落盘（不依赖 stdout；失败静默，不影响启动）
    try:
        (_base / "startup_debug.txt").write_text("\n".join(_diag) + "\n", encoding="utf-8")
    except BaseException:
        pass

from app.main import main

if __name__ == "__main__":
    try:
        main()
    except BaseException:
        # 未捕获异常：完整 traceback 写入日志。窗口（打包）模式下 PyInstaller
        # 引导层的错误对话框不经过 Python 层 stderr，必须在此自行落盘便于排查。
        import traceback

        try:
            print("=== 未捕获异常 ===", file=sys.stderr, flush=True)
            traceback.print_exc(file=sys.stderr)
        except Exception:
            pass
        raise
