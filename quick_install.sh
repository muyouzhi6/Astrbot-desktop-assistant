#!/bin/bash

# ============================================================================
# AstrBot Desktop Assistant - macOS/Linux 傻瓜式一键安装脚本
# ============================================================================
# 特点：
#   1. 只需选择网络环境（海外/国内）
#   2. 自动测试并选择最快的加速代理
#   3. 全自动完成所有安装步骤
#   4. 自动创建桌面快捷方式和开机自启
# ============================================================================

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
WHITE='\033[1;37m'
NC='\033[0m' # No Color

# GitHub 仓库地址
GITHUB_REPO="https://github.com/muyouzhi6/Astrbot-desktop-assistant.git"

# 加速代理列表
PROXY_HOSTS=("gh.llkk.cc" "gh-proxy.com" "mirror.ghproxy.com" "ghproxy.net")

# 获取脚本所在目录
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INSTALL_DIR="$(pwd)"

echo ""
echo -e "${CYAN}╔══════════════════════════════════════════════════════════════════════╗${NC}"
echo -e "${CYAN}║                                                                      ║${NC}"
echo -e "${CYAN}║          ${WHITE}AstrBot Desktop Assistant 一键安装脚本${CYAN}                      ║${NC}"
echo -e "${CYAN}║                                                                      ║${NC}"
echo -e "${CYAN}║          ${GREEN}✓ 傻瓜式安装，只需一个选择！${CYAN}                                ║${NC}"
echo -e "${CYAN}║                                                                      ║${NC}"
echo -e "${CYAN}╚══════════════════════════════════════════════════════════════════════╝${NC}"
echo ""

# ============================================================================
# 检测操作系统
# ============================================================================
detect_os() {
    if [[ "$OSTYPE" == "darwin"* ]]; then
        OS="macos"
    elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
        OS="linux"
    else
        echo -e "${RED}✗ 不支持的操作系统: $OSTYPE${NC}"
        exit 1
    fi
}

# ============================================================================
# 唯一的用户选择：网络环境
# ============================================================================
echo -e "${WHITE}请选择您的网络环境：${NC}"
echo ""
echo -e "  ${CYAN}[1]${NC} 我有海外网络环境（可直接访问 GitHub）"
echo -e "  ${CYAN}[2]${NC} 我没有海外网络（使用国内加速，推荐大多数用户）"
echo ""
read -p "请输入选择 [1/2]: " NETWORK_CHOICE

USE_PROXY=0
BEST_PROXY=""
CLONE_URL="$GITHUB_REPO"

if [[ "$NETWORK_CHOICE" == "1" ]]; then
    echo ""
    echo -e "${GREEN}✓ 将使用 GitHub 直连${NC}"
else
    USE_PROXY=1
    echo ""
    echo -e "${CYAN}正在自动测试加速代理，请稍候...${NC}"
    echo ""
    
    MIN_TIME=9999
    
    for host in "${PROXY_HOSTS[@]}"; do
        echo -n "  测试 $host ... "
        
        # 使用 ping 测试延迟
        if ping -c 1 -W 3 "$host" &>/dev/null; then
            # 获取延迟时间
            latency=$(ping -c 1 -W 3 "$host" 2>/dev/null | grep -oE 'time=[0-9.]+' | cut -d= -f2 | head -1)
            if [[ -n "$latency" ]]; then
                latency_int=${latency%.*}
                echo -e "${GREEN}✓ 可用 (${latency} ms)${NC}"
                
                if [[ $latency_int -lt $MIN_TIME ]]; then
                    MIN_TIME=$latency_int
                    BEST_PROXY="$host"
                fi
            else
                echo -e "${GREEN}✓ 可用${NC}"
                if [[ -z "$BEST_PROXY" ]]; then
                    BEST_PROXY="$host"
                fi
            fi
        else
            echo -e "${RED}✗ 不可用${NC}"
        fi
    done
    
    if [[ -n "$BEST_PROXY" ]]; then
        echo ""
        echo -e "${GREEN}✓ 已选择最快代理: $BEST_PROXY${NC}"
        CLONE_URL="https://$BEST_PROXY/$GITHUB_REPO"
    else
        echo ""
        echo -e "${YELLOW}⚠ 所有代理均不可用，将尝试直连 GitHub${NC}"
        CLONE_URL="$GITHUB_REPO"
    fi
fi

# ============================================================================
# 检测 Git
# ============================================================================
echo ""
echo -e "${CYAN}[1/6]${NC} 检测 Git 环境..."

if ! command -v git &>/dev/null; then
    echo ""
    echo -e "${RED}╔══════════════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${RED}║  ✗ 未检测到 Git，请先安装 Git 后重试                                 ║${NC}"
    echo -e "${RED}╠══════════════════════════════════════════════════════════════════════╣${NC}"
    echo -e "${RED}║                                                                      ║${NC}"
    
    if [[ "$OS" == "macos" ]]; then
        echo -e "${RED}║  macOS 安装方式：                                                    ║${NC}"
        echo -e "${RED}║    方式1: xcode-select --install                                    ║${NC}"
        echo -e "${RED}║    方式2: brew install git                                          ║${NC}"
    else
        echo -e "${RED}║  Linux 安装方式：                                                    ║${NC}"
        echo -e "${RED}║    Ubuntu/Debian: sudo apt install git                              ║${NC}"
        echo -e "${RED}║    CentOS/RHEL: sudo yum install git                                ║${NC}"
        echo -e "${RED}║    Arch: sudo pacman -S git                                         ║${NC}"
    fi
    
    echo -e "${RED}║                                                                      ║${NC}"
    echo -e "${RED}╚══════════════════════════════════════════════════════════════════════╝${NC}"
    echo ""
    exit 1
fi

echo -e "${GREEN}✓ Git 已安装${NC}"

# ============================================================================
# 检测 Python
# ============================================================================
echo ""
echo -e "${CYAN}[2/6]${NC} 检测 Python 环境..."

detect_os

PYTHON_CMD=""

# 尝试多种方式查找 Python
for cmd in python3 python; do
    if command -v $cmd &>/dev/null; then
        version=$($cmd --version 2>&1 | grep -oE '[0-9]+\.[0-9]+')
        major=$(echo $version | cut -d. -f1)
        minor=$(echo $version | cut -d. -f2)
        
        if [[ $major -ge 3 && $minor -ge 10 ]]; then
            PYTHON_CMD=$cmd
            echo -e "${GREEN}✓ Python $($cmd --version 2>&1 | grep -oE '[0-9]+\.[0-9]+\.[0-9]+') 已安装${NC}"
            break
        fi
    fi
done

if [[ -z "$PYTHON_CMD" ]]; then
    echo ""
    echo -e "${RED}╔══════════════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${RED}║  ✗ 未检测到 Python 3.10+，请先安装 Python 后重试                     ║${NC}"
    echo -e "${RED}╠══════════════════════════════════════════════════════════════════════╣${NC}"
    echo -e "${RED}║                                                                      ║${NC}"
    
    if [[ "$OS" == "macos" ]]; then
        echo -e "${RED}║  macOS 安装方式：                                                    ║${NC}"
        echo -e "${RED}║    方式1 (Homebrew): brew install python@3.11                       ║${NC}"
        echo -e "${RED}║    方式2 (官网): https://www.python.org/downloads/                  ║${NC}"
    else
        echo -e "${RED}║  Linux 安装方式：                                                    ║${NC}"
        echo -e "${RED}║    Ubuntu/Debian: sudo apt install python3.11 python3.11-venv      ║${NC}"
        echo -e "${RED}║    CentOS/RHEL: sudo dnf install python3.11                        ║${NC}"
        echo -e "${RED}║    Arch: sudo pacman -S python                                     ║${NC}"
    fi
    
    echo -e "${RED}║                                                                      ║${NC}"
    echo -e "${RED}╚══════════════════════════════════════════════════════════════════════╝${NC}"
    echo ""
    exit 1
fi

# ============================================================================
# 克隆项目函数定义
# ============================================================================
clone_project() {
    echo "正在下载项目（使用浅克隆加速）..."
    echo "下载地址: $CLONE_URL"
    echo ""
    
    if git clone --depth 1 "$CLONE_URL" "$PROJECT_DIR"; then
        echo -e "${GREEN}✓ 项目下载完成${NC}"
    else
        echo ""
        echo -e "${YELLOW}⚠ 下载失败，尝试直连 GitHub...${NC}"
        
        if git clone --depth 1 "$GITHUB_REPO" "$PROJECT_DIR"; then
            echo -e "${GREEN}✓ 项目下载完成（直连）${NC}"
        else
            echo -e "${RED}✗ 下载失败，请检查网络连接${NC}"
            exit 1
        fi
    fi
}

# ============================================================================
# 克隆项目
# ============================================================================
echo ""
echo -e "${CYAN}[3/6]${NC} 下载项目..."

PROJECT_DIR="$INSTALL_DIR/Astrbot-desktop-assistant"

if [[ -d "$PROJECT_DIR/.git" ]]; then
    echo "检测到已有项目，正在更新..."
    cd "$PROJECT_DIR"
    
    if git pull; then
        echo -e "${GREEN}✓ 项目更新完成${NC}"
    else
        echo -e "${YELLOW}⚠ 更新失败，尝试重新克隆...${NC}"
        cd "$INSTALL_DIR"
        rm -rf "$PROJECT_DIR"
        clone_project
    fi
else
    if [[ -d "$PROJECT_DIR" ]]; then
        rm -rf "$PROJECT_DIR"
    fi
    clone_project
fi

cd "$PROJECT_DIR"

# 显示版本信息
echo ""
echo -e "${CYAN}版本信息：${NC}"
commit_info=$(git log -1 --format="%h %ci %s" 2>/dev/null)
if [[ -n "$commit_info" ]]; then
    echo "  最新提交: $commit_info"
fi

# ============================================================================
# 创建虚拟环境并安装依赖
# ============================================================================
echo ""
echo -e "${CYAN}[4/6]${NC} 配置 Python 环境..."

VENV_DIR="$PROJECT_DIR/venv"

if [[ -f "$VENV_DIR/bin/python" ]]; then
    echo -e "${GREEN}✓ 虚拟环境已存在${NC}"
else
    echo "正在创建虚拟环境..."
    $PYTHON_CMD -m venv "$VENV_DIR"
    
    if [[ $? -eq 0 ]]; then
        echo -e "${GREEN}✓ 虚拟环境创建成功${NC}"
    else
        echo -e "${YELLOW}⚠ 创建虚拟环境失败，将使用系统 Python${NC}"
    fi
fi

# 设置 Python 路径
if [[ -f "$VENV_DIR/bin/python" ]]; then
    PYTHON_CMD="$VENV_DIR/bin/python"
fi

echo ""
echo -e "${CYAN}[5/6]${NC} 安装依赖包（这可能需要几分钟）..."

# 升级 pip
"$PYTHON_CMD" -m pip install --upgrade pip -q 2>/dev/null

# 安装依赖
"$PYTHON_CMD" -m pip install -r "$PROJECT_DIR/requirements.txt" -q 2>/dev/null

if [[ $? -ne 0 ]]; then
    echo -e "${YELLOW}⚠ 部分依赖安装失败，尝试逐个安装核心依赖...${NC}"
    
    for dep in "PySide6>=6.5.0" "qasync>=0.27.1" "httpx[http2]>=0.24.0" "websockets>=11.0.0" "Pillow>=9.0.0" "mss>=9.0.0" "pynput>=1.7.0"; do
        echo "  安装 $dep..."
        "$PYTHON_CMD" -m pip install "$dep" -q 2>/dev/null
    done
fi

echo -e "${GREEN}✓ 依赖安装完成${NC}"

# ============================================================================
# 自动配置（桌面快捷方式 + 开机自启）
# ============================================================================
echo ""
echo -e "${CYAN}[6/6]${NC} 自动配置..."

# 确定 Python 路径
if [[ -f "$VENV_DIR/bin/python" ]]; then
    PYTHON_PATH="$VENV_DIR/bin/python"
else
    PYTHON_PATH=$(which $PYTHON_CMD)
fi

# macOS 配置
if [[ "$OS" == "macos" ]]; then
    # 创建桌面快捷方式
    LAUNCH_SCRIPT="$PROJECT_DIR/AstrBot Desktop Assistant.command"
    
    cat > "$LAUNCH_SCRIPT" << EOF
#!/bin/bash
cd "$PROJECT_DIR"
"$PYTHON_PATH" -m desktop_client
EOF
    
    chmod +x "$LAUNCH_SCRIPT"
    
    DESKTOP="$HOME/Desktop"
    if [[ -d "$DESKTOP" ]]; then
        cp "$LAUNCH_SCRIPT" "$DESKTOP/"
        echo -e "${GREEN}✓ 桌面快捷方式已创建${NC}"
    fi
    
    # 配置开机自启
    PLIST_DIR="$HOME/Library/LaunchAgents"
    PLIST_FILE="$PLIST_DIR/com.astrbot.desktop-assistant.plist"
    
    mkdir -p "$PLIST_DIR"
    
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
    <string>$PROJECT_DIR</string>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <false/>
</dict>
</plist>
EOF
    
    launchctl unload "$PLIST_FILE" 2>/dev/null
    launchctl load "$PLIST_FILE" 2>/dev/null
    
    if [[ $? -eq 0 ]]; then
        echo -e "${GREEN}✓ 开机自启已配置${NC}"
    else
        echo -e "${YELLOW}⚠ 开机自启配置失败${NC}"
    fi

# Linux 配置
else
    # 创建桌面快捷方式
    DESKTOP=$(xdg-user-dir DESKTOP 2>/dev/null || echo "$HOME/Desktop")
    
    if [[ -d "$DESKTOP" ]]; then
        DESKTOP_FILE="$DESKTOP/astrbot-desktop-assistant.desktop"
        
        cat > "$DESKTOP_FILE" << EOF
[Desktop Entry]
Type=Application
Name=AstrBot Desktop Assistant
Comment=AstrBot Desktop Assistant
Exec=$PYTHON_PATH -m desktop_client
Path=$PROJECT_DIR
Terminal=false
Icon=$PROJECT_DIR/desktop_client/resources/icon.png
Categories=Utility;
EOF
        
        chmod +x "$DESKTOP_FILE"
        gio set "$DESKTOP_FILE" "metadata::trusted" true 2>/dev/null
        
        echo -e "${GREEN}✓ 桌面快捷方式已创建${NC}"
    fi
    
    # 配置开机自启
    AUTOSTART_DIR="$HOME/.config/autostart"
    mkdir -p "$AUTOSTART_DIR"
    
    AUTOSTART_FILE="$AUTOSTART_DIR/astrbot-desktop-assistant.desktop"
    
    cat > "$AUTOSTART_FILE" << EOF
[Desktop Entry]
Type=Application
Name=AstrBot Desktop Assistant
Comment=AstrBot Desktop Assistant
Exec=$PYTHON_PATH -m desktop_client --autostart
Path=$PROJECT_DIR
Terminal=false
StartupNotify=false
X-GNOME-Autostart-enabled=true
EOF
    
    chmod +x "$AUTOSTART_FILE"
    
    if [[ -f "$AUTOSTART_FILE" ]]; then
        echo -e "${GREEN}✓ 开机自启已配置${NC}"
    else
        echo -e "${YELLOW}⚠ 开机自启配置失败${NC}"
    fi
fi

# ============================================================================
# 安装完成
# ============================================================================
echo ""
echo -e "${GREEN}╔══════════════════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║                                                                      ║${NC}"
echo -e "${GREEN}║                    ✓ 安装成功！                                      ║${NC}"
echo -e "${GREEN}║                                                                      ║${NC}"
echo -e "${GREEN}╠══════════════════════════════════════════════════════════════════════╣${NC}"
echo -e "${GREEN}║                                                                      ║${NC}"
echo -e "${GREEN}║  项目目录: $PROJECT_DIR${NC}"
echo -e "${GREEN}║                                                                      ║${NC}"
echo -e "${GREEN}║  启动方式:                                                           ║${NC}"
echo -e "${GREEN}║    • 双击桌面快捷方式                                                ║${NC}"
echo -e "${GREEN}║    • 或运行 ./start.sh                                               ║${NC}"
echo -e "${GREEN}║                                                                      ║${NC}"
echo -e "${GREEN}╚══════════════════════════════════════════════════════════════════════╝${NC}"
echo ""

# 询问是否立即启动
echo "是否立即启动 AstrBot Desktop Assistant？"
echo -e "  ${CYAN}[1]${NC} 是"
echo -e "  ${CYAN}[2]${NC} 否"
echo ""
read -p "请选择 [1/2]: " START_CHOICE

if [[ "$START_CHOICE" == "1" ]]; then
    echo ""
    echo "正在启动..."
    "$PYTHON_CMD" -m desktop_client &
    echo -e "${GREEN}✓ 应用已启动${NC}"
fi

echo ""
echo -e "${CYAN}感谢使用 AstrBot Desktop Assistant！${NC}"
echo ""