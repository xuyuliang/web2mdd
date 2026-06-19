@echo off
chcp 65001 >nul

cd /d "%~dp0"

echo ====================================
echo   查词词典 - 正在启动...
echo ====================================
echo.

call venv\Scripts\activate

if errorlevel 1 (
    echo [ERROR] 虚拟环境激活失败
    echo 请确认项目目录下有 venv 文件夹
    pause
    exit /b 1
)

echo 正在打开浏览器...
start http://localhost:8000

echo.
echo 启动服务器（按 Ctrl+C 停止）...
echo.
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

pause
