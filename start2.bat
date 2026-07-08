

echo.
echo 启动服务器（按 Ctrl+C 停止）...
echo.
echo python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
pause
