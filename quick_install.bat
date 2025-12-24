@echo off
chcp 65001 >nul 2>&1
setlocal EnableDelayedExpansion

:: ============================================================================
:: AstrBot Desktop Assistant - Windows 一键下载部署脚本
:: ============================================================================
:: 功能：
::   1. 自动检测最快的 GitHub 加速代理
::   2. 克隆/更新项目
::   3. 安装依赖
::   4. 配置开机自启
:: ============================================================================

title AstrBot Desktop Assistant 一键部署

:: 颜色定义
set "GREEN=[92m"
set "YELLOW=[93m"
set "RED=[91m"
set "CYAN=[96m"
set "RESET=[0m"

:: GitHub 加速代理列表（已验证可用的代理）
set "PROXY_LIST=https://gh.llkk.cc https://gh-proxy.com https://mirror.ghproxy.com https://ghproxy.net"
set "GITHUB_REPO=https://github.com/muyouzhi6/Astrbot-desktop-assistant.git"
set "PLUGIN_REPO=https://github.com/muyouzhi6/astrbot_plugin_desktop_assistant.git"

echo.
echo %CYAN%╔══════════════════════════════════════════════════════════════╗%RESET%
echo %CYAN%║                                                              ║%RESET%
echo %CYAN%║       AstrBot Desktop Assistant 一键下载部署脚本            ║%RESET%
echo %CYAN%║                                                              ║%RESET%
echo %CYAN%╚══════════════════════════════════════════════════════════════╝%RESET%
echo.

:: ============================================================================
:: 检测 Git 是否安装
:: ============================================================================
echo %CYAN%[1/6]%RESET% 检测 Git 环境...

git --version >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo %RED%✗ 未检测到 Git%RESET%
    echo.
    echo 请先安装 Git：
    echo   下载地址：https://git-scm.com/downloads
    echo.
    echo 或者手动下载项目 ZIP 包：
    echo   https://github.com/muyouzhi6/Astrbot-desktop-assistant/archive/refs/heads/main.zip
    echo.
    pause
    exit /b 1
)
echo %GREEN%✓ Git 已安装%RESET%

:: ============================================================================
:: 选择是否使用 GitHub 加速
:: ============================================================================
echo.
echo %CYAN%[2/6]%RESET% 配置下载源...
echo.
echo 是否使用 GitHub 加速代理？（国内用户推荐）
echo   [1] 是 - 自动选择最快的加速代理（推荐国内用户）
echo   [2] 否 - 直接从 GitHub 下载（需要良好的网络环境）
echo.
set /p "USE_PROXY=请选择 [1/2]: "

set "BEST_PROXY="
set "CLONE_URL=%GITHUB_REPO%"

if "!USE_PROXY!"=="1" (
    echo.
    echo 正在测试各加速代理的连接速度...
    echo.
    
    set "MIN_TIME=999999"
    
    for %%P in (%PROXY_LIST%) do (
        set "PROXY_URL=%%P"
        echo 测试 !PROXY_URL! ...
        
        :: 使用 PowerShell 测试连接延迟
        for /f %%T in ('powershell -Command "$sw = [System.Diagnostics.Stopwatch]::StartNew(); try { $response = Invoke-WebRequest -Uri '!PROXY_URL!' -TimeoutSec 5 -UseBasicParsing; $sw.Stop(); $sw.ElapsedMilliseconds } catch { 99999 }"') do (
            set "RESP_TIME=%%T"
        )
        
        if !RESP_TIME! LSS 99999 (
            echo   响应时间: !RESP_TIME! ms
            
            if !RESP_TIME! LSS !MIN_TIME! (
                set "MIN_TIME=!RESP_TIME!"
                set "BEST_PROXY=!PROXY_URL!"
            )
        ) else (
            echo   %RED%连接失败%RESET%
        )
    )
    
    if defined BEST_PROXY (
        echo.
        echo %GREEN%✓ 最快代理: !BEST_PROXY! (!MIN_TIME! ms)%RESET%
        
        :: 构建加速 URL
        :: 格式: https://proxy.com/https://github.com/user/repo.git
        set "CLONE_URL=!BEST_PROXY!/!GITHUB_REPO!"
        set "PLUGIN_CLONE_URL=!BEST_PROXY!/!PLUGIN_REPO!"
    ) else (
        echo %YELLOW%⚠ 所有代理均不可用，将使用直连%RESET%
    )
) else (
    echo %YELLOW%使用 GitHub 直连%RESET%
)

:: ============================================================================
:: 选择安装目录
:: ============================================================================
echo.
echo %CYAN%[3/6]%RESET% 选择安装目录...
echo.
echo 当前目录: %CD%
echo.
echo 安装目录选项：
echo   [1] 当前目录
echo   [2] 用户文档目录 (%USERPROFILE%\Documents)
echo   [3] 自定义目录
echo.
set /p "DIR_CHOICE=请选择 [1/2/3]: "

set "INSTALL_DIR=%CD%"

if "!DIR_CHOICE!"=="2" (
    set "INSTALL_DIR=%USERPROFILE%\Documents"
) else if "!DIR_CHOICE!"=="3" (
    echo.
    set /p "INSTALL_DIR=请输入安装目录路径: "
)

:: 创建目录
if not exist "!INSTALL_DIR!" (
    mkdir "!INSTALL_DIR!" 2>nul
    if !ERRORLEVEL! NEQ 0 (
        echo %RED%✗ 无法创建目录: !INSTALL_DIR!%RESET%
        pause
        exit /b 1
    )
)

cd /d "!INSTALL_DIR!"
echo.
echo 安装目录: !INSTALL_DIR!

:: ============================================================================
:: 克隆或更新项目
:: ============================================================================
echo.
echo %CYAN%[4/6]%RESET% 下载项目...
echo.

set "PROJECT_DIR=!INSTALL_DIR!\Astrbot-desktop-assistant"

if exist "!PROJECT_DIR!\.git" (
    echo 检测到已有项目，正在更新...
    cd /d "!PROJECT_DIR!"
    git pull
    if !ERRORLEVEL! NEQ 0 (
        echo %YELLOW%⚠ 更新失败，尝试重新克隆...%RESET%
        cd /d "!INSTALL_DIR!"
        rmdir /s /q "!PROJECT_DIR!" 2>nul
        goto :clone_project
    )
    echo %GREEN%✓ 项目更新完成%RESET%
) else (
    :clone_project
    if exist "!PROJECT_DIR!" (
        echo 清理旧目录...
        rmdir /s /q "!PROJECT_DIR!" 2>nul
    )
    
    echo 正在克隆项目...
    echo 克隆地址: !CLONE_URL!
    echo.
    
    git clone "!CLONE_URL!" "!PROJECT_DIR!"
    
    if !ERRORLEVEL! NEQ 0 (
        echo.
        echo %RED%✗ 克隆失败%RESET%
        
        if defined BEST_PROXY (
            echo 尝试使用 GitHub 直连...
            git clone "%GITHUB_REPO%" "!PROJECT_DIR!"
            
            if !ERRORLEVEL! NEQ 0 (
                echo %RED%✗ 直连也失败了，请检查网络%RESET%
                pause
                exit /b 1
            )
        ) else (
            pause
            exit /b 1
        )
    )
    
    echo %GREEN%✓ 项目下载完成%RESET%
)

cd /d "!PROJECT_DIR!"

:: ============================================================================
:: 运行安装脚本
:: ============================================================================
echo.
echo %CYAN%[5/6]%RESET% 运行安装程序...
echo.

if exist "install.bat" (
    call install.bat
) else (
    echo %RED%✗ 未找到 install.bat%RESET%
    pause
    exit /b 1
)

:: ============================================================================
:: 完成
:: ============================================================================
echo.
echo %CYAN%[6/6]%RESET% 部署完成！
echo.
echo %GREEN%╔══════════════════════════════════════════════════════════════╗%RESET%
echo %GREEN%║                                                              ║%RESET%
echo %GREEN%║                      部署成功！                              ║%RESET%
echo %GREEN%║                                                              ║%RESET%
echo %GREEN%╚══════════════════════════════════════════════════════════════╝%RESET%
echo.
echo 项目目录: !PROJECT_DIR!
echo.
pause