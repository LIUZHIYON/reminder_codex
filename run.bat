@echo off
chcp 65001 >nul
echo ====================================
echo   DingDing Reminder - ???
echo ====================================
echo.

cd /d "C:\Users\29503\Desktop\reminder_codex\backend"
if errorlevel 1 (
    echo [ERROR] Cannot find project directory!
    pause
    exit /b 1
)

echo [1/3] Checking Python...
python --version
if errorlevel 1 (
    echo [ERROR] Python not found!
    pause
    exit /b 1
)

echo [2/3] Installing dependencies...
pip install -r requirements.txt -q
echo Done.

echo [3/3] Starting server...
echo.
echo ====================================
echo   Open your browser and visit:
echo.
echo   >>>  http://127.0.0.1:8000  <<<
echo   >>>  http://localhost:8000  <<<
echo.
echo   (If you get 502, your proxy software
echo    is intercepting localhost.
echo    Try http://127.0.0.1:8000 instead)
echo ====================================
echo.
echo Press Ctrl+C to stop the server
echo.

python main.py

echo.
echo [INFO] Server stopped (code: %errorlevel%)
pause
