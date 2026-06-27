@echo off
cd /d "%~dp0"
echo Starting management server...
python server.py
if errorlevel 1 (
    echo [ERROR] Server failed with code %errorlevel%
    pause
)
