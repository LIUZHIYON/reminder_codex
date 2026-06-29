@echo off
chcp 65001 >nul
title 提醒行为树 - Windows 本地测试

echo ========================================
echo  🤖 提醒行为树 - Windows 本地测试
echo ========================================
echo.

:: 检查 Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [错误] 未找到 Python，请安装 Python 3.8+
    pause
    exit /b 1
)

:: 检查依赖
echo [检查] 安装依赖...
python -c "import requests" >nul 2>&1
if errorlevel 1 (
    echo [安装] requests...
    pip install requests -q
)

echo.
echo [1] 测试行为树结构 + 模拟提醒流程
echo [2] 测试提醒系统真实 API（需提醒服务运行中）
echo [3] 全部测试
echo [4] 退出
echo.

choice /c 1234 /n /m "请选择 (1/2/3/4): "
echo.

if errorlevel 4 exit /b 0
if errorlevel 3 goto all
if errorlevel 2 goto real
if errorlevel 1 goto local

:local
echo 【本地测试 - 模拟模式】
python test\test_bt_local.py
if errorlevel 1 (
    echo [错误] 测试失败
    pause
)
goto end

:real
echo 【真实 API 测试】
python test\test_bt_local.py
if errorlevel 1 (
    echo [错误] 测试失败
    pause
)
goto end

:all
echo 【全部测试】
python test\test_bt_local.py
if errorlevel 1 (
    echo [错误] 测试失败
    pause
)
goto end

:end
echo.
echo 测试完成。
pause
