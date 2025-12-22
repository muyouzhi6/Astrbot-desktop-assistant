@echo off
chcp 65001 >nul
title AstrBot 桌面助手

echo ============================================
echo    AstrBot 桌面助手启动器
echo ============================================
echo.

:: 检查 Python 是否安装
python --version >nul 2>&1
if errorlevel 1 (
    echo [错误] 未检测到 Python，请先安装 Python 3.10+
    echo 下载地址: https://www.python.org/downloads/
    pause
    exit /b 1
)

:: 切换到脚本所在目录
cd /d "%~dp0"

:: 检查是否已安装依赖
echo [1/3] 检查依赖...
pip show PySide6 >nul 2>&1
if errorlevel 1 (
    echo [2/3] 安装依赖中，请稍候...
    pip install -r requirements.txt
    if errorlevel 1 (
        echo [错误] 依赖安装失败，请检查网络连接
        pause
        exit /b 1
    )
    echo [2/3] 依赖安装完成!
) else (
    echo [2/3] 依赖已就绪
)

echo [3/3] 启动应用...
echo.

:: 启动应用
python -m desktop_client

:: 如果程序异常退出，显示错误信息
if errorlevel 1 (
    echo.
    echo [错误] 应用异常退出，错误代码: %errorlevel%
    pause
)