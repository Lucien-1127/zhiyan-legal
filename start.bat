@echo off
chcp 65001 >nul
rem ══════════════════════════════════════════════════
rem 智研 AI 法律系統 · SaaS 版 — 啟動腳本 (Windows)
rem ══════════════════════════════════════════════════

title 智研 AI 法律系統 · SaaS 版
setlocal enabledelayedexpansion

echo.
echo   ╔═══════════════════════════════════════════╗
echo   ║   ⚖️  智研 AI 法律系統 · SaaS 版         ║
echo   ║       啟動中...                          ║
echo   ╚═══════════════════════════════════════════╝
echo.

set SCRIPT_DIR=%~dp0
set BACKEND_DIR=%SCRIPT_DIR%backend
set FRONTEND_DIR=%SCRIPT_DIR%frontend

rem ─── 檢查 .env ──────────────────────────────────
if not exist "%BACKEND_DIR%\.env" (
    echo ⚠️  未發現 .env 設定檔
    echo    複製範本並填入 API 金鑰：
    echo    copy %BACKEND_DIR%\.env.example %BACKEND_DIR%\.env
    echo    然後編輯 %BACKEND_DIR%\.env
    echo.
    echo    使用預設值 ^(DeepSeek^) 繼續啟動...
)

rem ─── Python 檢查 ───────────────────────────────
where python >nul 2>&1
if errorlevel 1 (
    echo ❌ 找不到 Python，請先安裝 Python 3.10+
    pause
    exit /b 1
)

rem ─── 虛擬環境 ─────────────────────────────────
set VENV_DIR=%BACKEND_DIR%\.venv
if not exist "%VENV_DIR%\Scripts\python.exe" (
    echo 📦 建立虛擬環境...
    python -m venv "%VENV_DIR%"
    echo ✅ 虛擬環境已建立
)

rem ─── 安裝依賴 ──────────────────────────────────
echo 📦 安裝相依套件...
call "%VENV_DIR%\Scripts\activate.bat"
pip install -q -r "%BACKEND_DIR%\requirements.txt"
echo ✅ 相依套件已安裝

rem ─── 啟動服務 ──────────────────────────────────
cd /d "%BACKEND_DIR%"
echo.
echo   🌐 服務位址：http://localhost:8000
echo   🛑 Ctrl+C 停止服務
echo.
echo ═══════════════════════════════════════════════
echo.

rem 載入 .env（若有）
if exist ".env" (
    for /f "usebackq delims=" %%a in (".env") do (
        set "%%a"
    )
)

set ZHIYAN_API_BASE_URL=%ZHIYAN_API_BASE_URL%
if "%ZHIYAN_API_BASE_URL%"=="" set ZHIYAN_API_BASE_URL=https://api.deepseek.com/v1

set ZHIYAN_MODEL=%ZHIYAN_MODEL%
if "%ZHIYAN_MODEL%"=="" set ZHIYAN_MODEL=deepseek-chat

python -m uvicorn main:app --host %APP_HOST% --port %APP_PORT% --reload

pause
