# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller 打包配置：Edu-RAG-Tutor（onedir + 窗口模式）

构建：.venv\Scripts\python.exe -m PyInstaller EduRAGTutor.spec --noconfirm --clean
产物：dist/EduRAGTutor/EduRAGTutor.exe（static/ 与 models/ 位于同目录 _internal/ 下）

不打包 .env —— 安装后用户在首启向导中填写自己的 API Key。
"""

from PyInstaller.utils.hooks import (
    collect_data_files,
    collect_dynamic_libs,
    collect_submodules,
)

datas = [
    ("static", "static"),   # 前端页面/JS/CSS/立绘
    ("models", "models"),   # 内置 bge-small-zh-v1.5 Embedding 模型（离线可用）
]

# pythonnet：pywebview 所需的 .NET 绑定（Python.Runtime.dll 等运行时组件）
datas += collect_data_files("pythonnet")
datas += collect_data_files("clr_loader")

# sherpa-onnx：离线语音包引擎，自带 onnxruntime DLL / .pyd 运行库需一并收集
binaries = collect_dynamic_libs("sherpa_onnx")

hiddenimports = (
    # chromadb 的 Rust API / SqliteDB / 遥测(posthog) / Segment 管理器 / 执行器等
    # 组件全部通过 importlib 按配置字符串动态加载，静态分析发现不了 → 收齐全部子模块
    collect_submodules("chromadb")
    # sentence-transformers 按 modules.json 动态 import 模型子模块，静态分析发现不了
    + collect_submodules("sentence_transformers")
    # pywebview 按平台动态 import 后端（Windows → EdgeChromium/WinForms）
    + collect_submodules("webview")
    # sherpa-onnx 离线语音包（speaker 内函数级懒加载，收齐子模块兜底）
    + collect_submodules("sherpa_onnx")
    + [
        "chromadb_rust_bindings",  # rust 扩展（独立顶层包）
        # pyttsx3 按系统动态加载语音驱动
        "pyttsx3.drivers",
        "pyttsx3.drivers.sapi5",
        # uvicorn 按配置动态加载协议实现（hooks-contrib 已有钩子，此处兜底）
        "uvicorn.logging",
        "uvicorn.loops.auto",
        "uvicorn.loops.asyncio",
        "uvicorn.protocols.http.auto",
        "uvicorn.protocols.http.h11_impl",
        "uvicorn.protocols.http.httptools_impl",
        "uvicorn.lifespan.on",
        "uvicorn.lifespan.off",
    ]
)

a = Analysis(
    ["run.py"],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # onnxruntime 仅被 chromadb 默认 Embedding 函数使用（本项目显式传入向量，
        # 不会触发），排除可减小体积约 400MB
        "onnxruntime",
        "tkinter",
        "matplotlib",
        "IPython",
        "jupyter",
    ],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="EduRAGTutor",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,  # 桌面应用：不显示控制台窗口（日志见 %APPDATA%\EduRAGTutor\eduragtutor.log）
    disable_windowed_traceback=False,
    icon="app.ico",  # 应用图标：项目根目录 app.ico（含 256/128/64/48/32/16 多尺寸）
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="EduRAGTutor",
)
