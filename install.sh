#!/bin/bash

# ============================================================================
# AstrBot Desktop Assistant - macOS/Linux 一键部署脚本
# ============================================================================
# 功能：
#   1. 检测 Python 环境
#   2. 创建虚拟环境（可选）
#   3. 安装依赖包
#   4. 配置开机自启（可选）
#   5. 启动应用程序
# ============================================================================

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# 获取脚本所在目录
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo ""
echo -e "${CYAN}╔══════════════════════════════════════════════════════════════╗${NC}"
echo -e "${CYAN}║                                                              ║${NC}"
echo -e "${CYAN}║       AstrBot Desktop Assistant 一键部署脚本                 ║${NC}"
echo -e "${CYAN}║                                                              ║${NC}"
echo -e "${CYAN}╚══════════════════════════════════════════════════════════════╝${NC}"
echo ""

# ============================================================================
# 检测操作系统
# ============================================================================
detect_os() {
    if [[ "$OSTYPE" == "darwin"* ]]; then
        OS="macos"
        echo -e "${GREEN}✓ 检测到 macOS 系统${NC}"
    elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
        OS="linux"
        echo -e "${GREEN}✓ 检测到 Linux 系统${NC}"
    else
        echo -e "${RED}✗ 不支持的操作系统: $OSTYPE${NC}"
        exit 1
    fi
}

# ============================================================================
# 第一步：检测 Python 环境
# ============================================================================
check_python() {
    echo ""
    echo -e "${CYAN}[1/5]${NC} 检测 Python 环境..."
    
    PYTHON_CMD=""
    
    # 尝试多种方式查找 Python
    for cmd in python3 python; do
        if command -v $cmd &> /dev/null; then
            version=$($cmd --version 2>&1 | grep -oE '[0-9]+\.[0-9]+')
            major=$(echo $version | cut -d. -f1)
            minor=$(echo $version | cut -d. -f2)
            
            if [[ $major -ge 3 && $minor -ge 10 ]]; then
                PYTHON_CMD=$cmd
                echo -e "${GREEN}✓ 检测到 Python $($cmd --version 2>&1 | grep -oE '[0-9]+\.[0-9]+\.[0-9]+')${NC}"
                return 0
            fi
        fi
    done
    
    # 未找到合适的 Python
    echo -e "${RED}✗ 未检测到 Python 3.10+ 环境${NC}"
    echo ""
    
    if [[ "$OS" == "macos" ]]; then
        echo "请使用以下方式安装 Python："
        echo "  方式1 (Homebrew): brew install python@3.11"
        echo "  方式2 (官网): https://www.python.org/downloads/"
    else
        echo "请使用以下方式安装 Python："
        echo "  Ubuntu/Debian: sudo apt install python3.11 python3.11-venv python3-pip"
        echo "  CentOS/RHEL: sudo dnf install python3.11"
        echo "  Arch: sudo pacman -S python"
    fi
    echo ""
    exit 1
}

# ============================================================================
# 第二步：创建/激活虚拟环境
# ============================================================================
setup_venv() {
    echo ""
    echo -e "${CYAN}[2/5]${NC} 配置 Python 环境..."
    
    VENV_DIR="$SCRIPT_DIR/venv"
    USE_VENV=0
    
    if [[ -f "$VENV_DIR/bin/python" ]]; then
        echo -e "${GREEN}✓ 检测到已有虚拟环境${NC}"
        PYTHON_CMD="$VENV_DIR/bin/python"
        USE_VENV=1
    else
        echo ""
        echo "是否创建虚拟环境？（推荐）"
        echo "  [1] 是 - 创建独立的虚拟环境（推荐）"
        echo "  [2] 否 - 使用系统 Python 环境"
        echo ""
        read -p "请选择 [1/2]: " VENV_CHOICE
        
        if [[ "$VENV_CHOICE" == "1" ]]; then
            echo ""
            echo "正在创建虚拟环境..."
            $PYTHON_CMD -m venv "$VENV_DIR"
            
            if [[ $? -eq 0 ]]; then
                echo -e "${GREEN}✓ 虚拟环境创建成功${NC}"
                PYTHON_CMD="$VENV_DIR/bin/python"
                USE_VENV=1
            else
                echo -e "${RED}✗ 创建虚拟环境失败${NC}"
                echo "将使用系统 Python 环境继续..."
            fi
        fi
    fi
}

# ============================================================================
# 第三步：安装依赖
# ============================================================================
install_dependencies() {
    echo ""
    echo -e "${CYAN}[3/5]${NC} 安装依赖包..."
    
    # 升级 pip
    echo "正在升级 pip..."
    "$PYTHON_CMD" -m pip install --upgrade pip -q 2>/dev/null
    
    # 安装依赖
    echo "正在安装项目依赖（这可能需要几分钟）..."
    "$PYTHON_CMD" -m pip install -r "$SCRIPT_DIR/requirements.txt" -q 2>/dev/null
    
    if [[ $? -ne 0 ]]; then
        echo -e "${YELLOW}⚠ 部分依赖安装失败，尝试逐个安装...${NC}"
        
        # 核心依赖列表
        for dep in "PySide6>=6.5.0" "qasync>=0.24.0" "httpx>=0.25.0" "websockets>=11.0" "Pillow>=10.0.0" "mss>=9.0.0" "pynput>=1.7.6"; do
            echo "  安装 $dep..."
            "$PYTHON_CMD" -m pip install "$dep" -q 2>/dev/null
        done
    fi
    
    echo -e "${GREEN}✓ 依赖安装完成${NC}"
}

# ============================================================================
# 第四步：配置开机自启
# ============================================================================
setup_autostart() {
    echo ""
    echo -e "${CYAN}[4/5]${NC} 配置开机自启..."
    
    echo ""
    echo "是否设置开机自动启动？"
    echo "  [1] 是 - 开机时自动启动 AstrBot Desktop Assistant"
    echo "  [2] 否 - 稍后手动配置"
    echo ""
    read -p "请选择 [1/2]: " AUTOSTART_CHOICE
    
    if [[ "$AUTOSTART_CHOICE" == "1" ]]; then
        echo "正在配置开机自启..."
        
        if [[ "$OS" == "macos" ]]; then
            setup_macos_autostart
        else
            setup_linux_autostart
        fi
    else
        echo -e "${YELLOW}跳过开机自启配置${NC}"
    fi
}

# macOS 开机自启配置
setup_macos_autostart() {
    PLIST_DIR="$HOME/Library/LaunchAgents"
    PLIST_FILE="$PLIST_DIR/com.astrbot.desktop-assistant.plist"
    
    mkdir -p "$PLIST_DIR"
    
    # 确定 Python 路径
    if [[ $USE_VENV -eq 1 ]]; then
        PYTHON_PATH="$VENV_DIR/bin/python"
    else
        PYTHON_PATH=$(which $PYTHON_CMD)
    fi
    
    cat > "$PLIST_FILE" << EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.astrbot.desktop-assistant</string>
    <key>ProgramArguments</key>
    <array>
        <string>$PYTHON_PATH</string>
        <string>-m</string>
        <string>desktop_client</string>
        <string>--autostart</string>
    </array>
    <key>WorkingDirectory</key>
    <string>$SCRIPT_DIR</string>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <false/>
    <key>StandardOutPath</key>
    <string>$HOME/.astrbot/autostart.log</string>
    <key>StandardErrorPath</key>
    <string>$HOME/.astrbot/autostart_error.log</string>
</dict>
</plist>
EOF
    
    # 加载 LaunchAgent
    launchctl unload "$PLIST_FILE" 2>/dev/null
    launchctl load "$PLIST_FILE" 2>/dev/null
    
    if [[ $? -eq 0 ]]; then
        echo -e "${GREEN}✓ macOS 开机自启已配置${NC}"
    else
        echo -e "${YELLOW}⚠ 开机自启配置失败，您可以稍后在设置中手动开启${NC}"
    fi
}

# Linux 开机自启配置
setup_linux_autostart() {
    AUTOSTART_DIR="$HOME/.config/autostart"
    DESKTOP_FILE="$AUTOSTART_DIR/astrbot-desktop-assistant.desktop"
    
    mkdir -p "$AUTOSTART_DIR"
    
    # 确定 Python 路径
    if [[ $USE_VENV -eq 1 ]]; then
        PYTHON_PATH="$VENV_DIR/bin/python"
    else
        PYTHON_PATH=$(which $PYTHON_CMD)
    fi
    
    cat > "$DESKTOP_FILE" << EOF
[Desktop Entry]
Type=Application
Name=AstrBot Desktop Assistant
Comment=AstrBot Desktop Assistant
Exec=$PYTHON_PATH -m desktop_client --autostart
Path=$SCRIPT_DIR
Terminal=false
StartupNotify=false
X-GNOME-Autostart-enabled=true
EOF
    
    chmod +x "$DESKTOP_FILE"
    
    if [[ -f "$DESKTOP_FILE" ]]; then
        echo -e "${GREEN}✓ Linux 开机自启已配置${NC}"
    else
        echo -e "${YELLOW}⚠ 开机自启配置失败，您可以稍后在设置中手动开启${NC}"
    fi
}

# ============================================================================
# 第五步：创建桌面快捷方式
# ============================================================================
create_shortcut() {
    echo ""
    echo -e "${CYAN}[5/5]${NC} 创建快捷方式..."
    
    echo ""
    echo "是否创建桌面快捷方式？"
    echo "  [1] 是"
    echo "  [2] 否"
    echo ""
    read -p "请选择 [1/2]: " SHORTCUT_CHOICE
    
    if [[ "$SHORTCUT_CHOICE" == "1" ]]; then
        if [[ "$OS" == "macos" ]]; then
            create_macos_shortcut
        else
            create_linux_shortcut
        fi
    else
        echo -e "${YELLOW}跳过创建快捷方式${NC}"
    fi
}

# macOS 快捷方式（应用程序别名）
create_macos_shortcut() {
    # 创建启动脚本
    LAUNCH_SCRIPT="$SCRIPT_DIR/AstrBot Desktop Assistant.command"
    
    if [[ $USE_VENV -eq 1 ]]; then
        PYTHON_PATH="$VENV_DIR/bin/python"
    else
        PYTHON_PATH=$(which $PYTHON_CMD)
    fi
    
    cat > "$LAUNCH_SCRIPT" << EOF
#!/bin/bash
cd "$SCRIPT_DIR"
"$PYTHON_PATH" -m desktop_client
EOF
    
    chmod +x "$LAUNCH_SCRIPT"
    
    # 复制到桌面
    DESKTOP="$HOME/Desktop"
    if [[ -d "$DESKTOP" ]]; then
        cp "$LAUNCH_SCRIPT" "$DESKTOP/"
        echo -e "${GREEN}✓ 桌面快捷方式已创建${NC}"
    else
        echo -e "${YELLOW}⚠ 未找到桌面目录${NC}"
    fi
}

# Linux 快捷方式（.desktop 文件）
create_linux_shortcut() {
    DESKTOP="$HOME/Desktop"
    
    if [[ ! -d "$DESKTOP" ]]; then
        # 尝试从 XDG 获取桌面目录
        DESKTOP=$(xdg-user-dir DESKTOP 2>/dev/null || echo "$HOME/Desktop")
    fi
    
    if [[ -d "$DESKTOP" ]]; then
        if [[ $USE_VENV -eq 1 ]]; then
            PYTHON_PATH="$VENV_DIR/bin/python"
        else
            PYTHON_PATH=$(which $PYTHON_CMD)
        fi
        
        DESKTOP_FILE="$DESKTOP/astrbot-desktop-assistant.desktop"
        
        cat > "$DESKTOP_FILE" << EOF
[Desktop Entry]
Type=Application
Name=AstrBot Desktop Assistant
Comment=AstrBot Desktop Assistant
Exec=$PYTHON_PATH -m desktop_client
Path=$SCRIPT_DIR
Terminal=false
Icon=$SCRIPT_DIR/desktop_client/resources/icon.png
Categories=Utility;
EOF
        
        chmod +x "$DESKTOP_FILE"
        
        # 某些桌面环境需要 gio 设置
        gio set "$DESKTOP_FILE" "metadata::trusted" true 2>/dev/null
        
        echo -e "${GREEN}✓ 桌面快捷方式已创建${NC}"
    else
        echo -e "${YELLOW}⚠ 未找到桌面目录${NC}"
    fi
}

# ============================================================================
# 完成安装
# ============================================================================
finish_install() {
    echo ""
    echo -e "${CYAN}══════════════════════════════════════════════════════════════${NC}"
    echo ""
    echo -e "${GREEN}✓ 安装完成！${NC}"
    echo ""
    echo "启动方式："
    echo "  • 双击桌面快捷方式"
    echo "  • 或运行 ./start.sh"
    echo "  • 或在命令行执行：$PYTHON_CMD -m desktop_client"
    echo ""
    
    # 询问是否立即启动
    echo "是否立即启动 AstrBot Desktop Assistant？"
    echo "  [1] 是"
    echo "  [2] 否"
    echo ""
    read -p "请选择 [1/2]: " START_CHOICE
    
    if [[ "$START_CHOICE" == "1" ]]; then
        echo ""
        echo "正在启动..."
        
        # 后台启动应用
        "$PYTHON_CMD" -m desktop_client &
        
        echo -e "${GREEN}✓ 应用已启动${NC}"
    fi
    
    echo ""
    echo -e "${CYAN}感谢使用 AstrBot Desktop Assistant！${NC}"
    echo ""
}

# ============================================================================
# 主流程
# ============================================================================
main() {
    detect_os
    check_python
    setup_venv
    install_dependencies
    setup_autostart
    create_shortcut
    finish_install
}

# 运行主流程
main