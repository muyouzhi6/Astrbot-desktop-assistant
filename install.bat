@echo off
chcp 65001 >nul 2>&1
setlocal EnableDelayedExpansion

:: ============================================================================
:: AstrBot Desktop Assistant - Windows 一键部署脚本
:: ============================================================================
:: 功能：
::   1. 检测 Python 环境
::   2. 创建虚拟环境（可选）
::   3. 安装依赖包
::   4. 配置开机自启（可选）
::   5. 启动应用程序
:: ============================================================================

title AstrBot Desktop Assistant 安装程序

:: 颜色定义
set "GREEN=[92m"
set "YELLOW=[93m"
set "RED=[91m"
set "CYAN=[96m"
set "RESET=[0m"

echo.
echo %CYAN%╔══════════════════════════════════════════════════════════════╗%RESET%
echo %CYAN%║                                                              ║%RESET%
echo %CYAN%║       AstrBot Desktop Assistant 一键部署脚本                 ║%RESET%
echo %CYAN%║                                                              ║%RESET%
echo %CYAN%╚══════════════════════════════════════════════════════════════╝%RESET%
echo.

:: ============================================================================
:: 第一步：检测 Python 环境
:: ============================================================================
echo %CYAN%[1/5]%RESET% 检测 Python 环境...

:: 尝试多种方式查找 Python
set "PYTHON_CMD="

:: 方式1：直接使用 python 命令
python --version >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    set "PYTHON_CMD=python"
    goto :python_found
)

:: 方式2：使用 python3 命令
python3 --version >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    set "PYTHON_CMD=python3"
    goto :python_found
)

:: 方式3：使用 py 启动器
py --version >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    set "PYTHON_CMD=py"
    goto :python_found
)

:: 方式4：检查常见安装路径
for %%P in (
    "%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
    "%LOCALAPPDATA%\Programs\Python\Python311\python.exe"
    "%LOCALAPPDATA%\Programs\Python\Python310\python.exe"
    "%PROGRAMFILES%\Python312\python.exe"
    "%PROGRAMFILES%\Python311\python.exe"
    "%PROGRAMFILES%\Python310\python.exe"
) do (
    if exist %%P (
        set "PYTHON_CMD=%%~P"
        goto :python_found
    )
)

:: 未找到 Python
echo %RED%✗ 未检测到 Python 环境%RESET%
echo.
echo 请先安装 Python 3.10 或更高版本：
echo   下载地址：https://www.python.org/downloads/
echo   安装时请勾选 "Add Python to PATH"
echo.
pause
exit /b 1

:python_found
:: 获取 Python 版本
for /f "tokens=2" %%V in ('!PYTHON_CMD! --version 2^>^&1') do set "PYTHON_VERSION=%%V"
echo %GREEN%✓ 检测到 Python %PYTHON_VERSION%%RESET%

:: 检查版本是否满足要求 (>= 3.10)
for /f "tokens=1,2 delims=." %%A in ("%PYTHON_VERSION%") do (
    set "PY_MAJOR=%%A"
    set "PY_MINOR=%%B"
)
if %PY_MAJOR% LSS 3 (
    echo %RED%✗ Python 版本过低，需要 3.10 或更高版本%RESET%
    pause
    exit /b 1
)
if %PY_MAJOR% EQU 3 if %PY_MINOR% LSS 10 (
    echo %RED%✗ Python 版本过低，需要 3.10 或更高版本%RESET%
    pause
    exit /b 1
)

:: ============================================================================
:: 第二步：创建/激活虚拟环境
:: ============================================================================
echo.
echo %CYAN%[2/5]%RESET% 配置 Python 环境...

set "VENV_DIR=%~dp0venv"
set "USE_VENV=0"

if exist "%VENV_DIR%\Scripts\python.exe" (
    echo %GREEN%✓ 检测到已有虚拟环境%RESET%
    set "PYTHON_CMD=%VENV_DIR%\Scripts\python.exe"
    set "USE_VENV=1"
) else (
    echo.
    echo 是否创建虚拟环境？（推荐）
    echo   [1] 是 - 创建独立的虚拟环境（推荐）
    echo   [2] 否 - 使用系统 Python 环境
    echo.
    set /p "VENV_CHOICE=请选择 [1/2]: "
    
    if "!VENV_CHOICE!"=="1" (
        echo.
        echo 正在创建虚拟环境...
        !PYTHON_CMD! -m venv "%VENV_DIR%"
        if !ERRORLEVEL! NEQ 0 (
            echo %RED%✗ 创建虚拟环境失败%RESET%
            echo 将使用系统 Python 环境继续...
        ) else (
            echo %GREEN%✓ 虚拟环境创建成功%RESET%
            set "PYTHON_CMD=%VENV_DIR%\Scripts\python.exe"
            set "USE_VENV=1"
        )
    )
)

:: ============================================================================
:: 第三步：升级 pip 并安装依赖
:: ============================================================================
echo.
echo %CYAN%[3/5]%RESET% 安装依赖包...

:: 升级 pip
echo 正在升级 pip...
"!PYTHON_CMD!" -m pip install --upgrade pip -q 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo %YELLOW%⚠ pip 升级失败，继续使用现有版本%RESET%
)

:: 安装依赖
echo 正在安装项目依赖（这可能需要几分钟）...
"!PYTHON_CMD!" -m pip install -r "%~dp0requirements.txt" -q
if %ERRORLEVEL% NEQ 0 (
    echo %YELLOW%⚠ 部分依赖安装失败，尝试逐个安装...%RESET%
    
    :: 核心依赖列表
    for %%D in (
        "PySide6>=6.5.0"
        "qasync>=0.24.0"
        "httpx>=0.25.0"
        "websockets>=11.0"
        "Pillow>=10.0.0"
        "mss>=9.0.0"
        "pynput>=1.7.6"
    ) do (
        echo   安装 %%~D...
        "!PYTHON_CMD!" -m pip install %%~D -q 2>nul
    )
)

echo %GREEN%✓ 依赖安装完成%RESET%

:: ============================================================================
:: 第四步：配置开机自启
:: ============================================================================
echo.
echo %CYAN%[4/5]%RESET% 配置开机自启...

echo.
echo 是否设置开机自动启动？
echo   [1] 是 - 开机时自动启动 AstrBot Desktop Assistant
echo   [2] 否 - 稍后手动配置
echo.
set /p "AUTOSTART_CHOICE=请选择 [1/2]: "

if "!AUTOSTART_CHOICE!"=="1" (
    echo 正在配置开机自启...
    
    :: 使用 Python 调用自启动模块
    "!PYTHON_CMD!" -c "from desktop_client.platforms import get_platform_adapter; adapter = get_platform_adapter(); result = adapter.enable_autostart(); print(result.message if result else '配置失败')" 2>nul
    
    if !ERRORLEVEL! EQU 0 (
        echo %GREEN%✓ 开机自启已配置%RESET%
    ) else (
        echo %YELLOW%⚠ 开机自启配置失败，您可以稍后在设置中手动开启%RESET%
    )
) else (
    echo %YELLOW%跳过开机自启配置%RESET%
)

:: ============================================================================
:: 第五步：创建桌面快捷方式
:: ============================================================================
echo.
echo %CYAN%[5/5]%RESET% 创建快捷方式...

echo.
echo 是否创建桌面快捷方式？
echo   [1] 是
echo   [2] 否
echo.
set /p "SHORTCUT_CHOICE=请选择 [1/2]: "

if "!SHORTCUT_CHOICE!"=="1" (
    :: 创建 VBS 脚本来生成快捷方式
    set "SHORTCUT_VBS=%TEMP%\create_shortcut.vbs"
    set "DESKTOP=%USERPROFILE%\Desktop"
    
    :: 确定启动脚本路径
    if "!USE_VENV!"=="1" (
        set "TARGET_SCRIPT=%~dp0venv\Scripts\pythonw.exe"
        set "ARGUMENTS=-m desktop_client"
    ) else (
        set "TARGET_SCRIPT=%~dp0start.bat"
        set "ARGUMENTS="
    )
    
    echo Set oWS = WScript.CreateObject^("WScript.Shell"^) > "!SHORTCUT_VBS!"
    echo sLinkFile = "!DESKTOP!\AstrBot Desktop Assistant.lnk" >> "!SHORTCUT_VBS!"
    echo Set oLink = oWS.CreateShortcut^(sLinkFile^) >> "!SHORTCUT_VBS!"
    echo oLink.TargetPath = "!TARGET_SCRIPT!" >> "!SHORTCUT_VBS!"
    if not "!ARGUMENTS!"=="" (
        echo oLink.Arguments = "!ARGUMENTS!" >> "!SHORTCUT_VBS!"
    )
    echo oLink.WorkingDirectory = "%~dp0" >> "!SHORTCUT_VBS!"
    echo oLink.Description = "AstrBot Desktop Assistant" >> "!SHORTCUT_VBS!"
    echo oLink.Save >> "!SHORTCUT_VBS!"
    
    cscript //nologo "!SHORTCUT_VBS!" 2>nul
    del "!SHORTCUT_VBS!" 2>nul
    
    if exist "!DESKTOP!\AstrBot Desktop Assistant.lnk" (
        echo %GREEN%✓ 桌面快捷方式已创建%RESET%
    ) else (
        echo %YELLOW%⚠ 快捷方式创建失败%RESET%
    )
) else (
    echo %YELLOW%跳过创建快捷方式%RESET%
)

:: ============================================================================
:: 安装完成
:: ============================================================================
echo.
echo %CYAN%══════════════════════════════════════════════════════════════%RESET%
echo.
echo %GREEN%✓ 安装完成！%RESET%
echo.
echo 启动方式：
echo   • 双击桌面快捷方式
echo   • 或运行 start.bat
echo   • 或在命令行执行：!PYTHON_CMD! -m desktop_client
echo.

:: 询问是否立即启动
echo 是否立即启动 AstrBot Desktop Assistant？
echo   [1] 是
echo   [2] 否
echo.
set /p "START_CHOICE=请选择 [1/2]: "

if "!START_CHOICE!"=="1" (
    echo.
    echo 正在启动...
    
    :: 使用 start 命令在新窗口启动，避免阻塞
    if "!USE_VENV!"=="1" (
        start "" "!PYTHON_CMD!" -m desktop_client
    ) else (
        start "" "%~dp0start.bat"
    )
    
    echo %GREEN%✓ 应用已启动%RESET%
)

echo.
echo %CYAN%感谢使用 AstrBot Desktop Assistant！%RESET%
echo.
pause