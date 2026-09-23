@echo off
chcp 65001 >nul
REM ============================================================
REM  Edu-RAG-Tutor 学习助手 - 一键打包脚本
REM  产物1: dist\EduRAGTutor\EduRAGTutor.exe            (绿色版，可直接运行)
REM  产物2: installer\EduRAGTutor-Setup-1.2.0.exe (安装包，分发用)
REM  依赖:   .venv (已装 requirements.txt + pyinstaller) / Inno Setup 6
REM ============================================================
setlocal enabledelayedexpansion
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo [错误] 未找到虚拟环境 .venv，请先执行: python -m venv .venv ^&^& .venv\Scripts\pip install -r requirements.txt pyinstaller
    pause
    exit /b 1
)

echo [1/2] PyInstaller 构建中（首次约需 5-15 分钟，请耐心等待）...
".venv\Scripts\python.exe" -m PyInstaller EduRAGTutor.spec --noconfirm --clean --distpath dist --workpath build
if errorlevel 1 (
    echo [错误] PyInstaller 构建失败，请检查上方日志
    pause
    exit /b 1
)
echo       构建完成: dist\EduRAGTutor\EduRAGTutor.exe

set "ISCC="
if exist "%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe" set "ISCC=%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
if exist "%ProgramFiles%\Inno Setup 6\ISCC.exe" set "ISCC=%ProgramFiles%\Inno Setup 6\ISCC.exe"
if exist "%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe" set "ISCC=%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe"
if "%ISCC%"=="" (
    echo [提示] 未检测到 Inno Setup 6，跳过安装包生成。
    echo        安装 Inno Setup 后重新运行本脚本即可: https://jrsoftware.org/isdl.php
    pause
    exit /b 0
)

echo [2/2] Inno Setup 生成安装包中...
"%ISCC%" installer.iss
if errorlevel 1 (
    echo [错误] 安装包编译失败，请检查上方日志
    pause
    exit /b 1
)

echo.
echo ============================================================
echo  打包完成！
echo    安装包: installer\EduRAGTutor-Setup-1.2.0.exe
echo    绿色版: dist\EduRAGTutor\EduRAGTutor.exe
echo ============================================================
pause
