#!/bin/bash

# ============================================================================
# AstrBot Desktop Assistant - macOS/Linux 一键下载部署脚本
# ============================================================================
# 功能：
#   1. 自动检测最快的 GitHub 加速代理
#   2. 克隆/更新项目
#   3. 安装依赖
#   4. 配置开机自启
# ============================================================================

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# GitHub 加速代理列表（已验证可用的代理）
PROXY_LIST=(
    "https://gh.llkk.cc"
    "https://gh-proxy.com"
    "https://mirror.ghproxy.com"
    "https://ghproxy.net"
)

GITHUB_REPO="https://github.com/muyouzhi6/Astrbot-desktop-assistant.git"
PLUGIN_REPO="https://github.com/muyouzhi6/astrbot_plugin_desktop_assistant.git"

echo ""
echo -e "${CYAN}╔══════════════════════════════════════════════════════════════╗${NC}"
echo -e "${CYAN}║                                                              ║${NC}"
echo -e "${CYAN}║       AstrBot Desktop Assistant 一键下载部署脚本            ║${NC}"
echo -e "${CYAN}║                                                              ║${NC}"
echo -e "${CYAN}╚══════════════════════════════════════════════════════════════╝${NC}"
echo ""

# ============================================================================
# 检测 Git 是否安装
# ============================================================================
check_git() {
    echo -e "${CYAN}[1/6]${NC} 检测 Git 环境..."
    
    if ! command -v git &> /dev/null; then
        echo -e "${RED}✗ 未检测到 Git${NC}"
        echo ""
        
        if [[ "$OSTYPE" == "darwin"* ]]; then
            echo "请安装 Git："
            echo "  方式1: xcode-select --install"
            echo "  方式2: brew install git"
        else
            echo "请安装 Git："
            echo "  Ubuntu/Debian: sudo apt install git"
            echo "  CentOS/RHEL: sudo yum install git"
            echo "  Arch: sudo pacman -S git"
        fi
        echo ""
        exit 1
    fi
    
    echo -e "${GREEN}✓ Git 已安装${NC}"
}

# ============================================================================
# 测试代理延迟
# ============================================================================
test_proxy_latency() {
    local url=$1
    local start_time end_time elapsed
    
    start_time=$(date +%s%3N 2>/dev/null || python3 -c "import time; print(int(time.time()*1000))")
    
    # 使用 curl 测试连接，超时 5 秒
    if curl -s --connect-timeout 5 --max-time 5 -o /dev/null -w "%{http_code}" "$url" | grep -q "^[23]"; then
        end_time=$(date +%s%3N 2>/dev/null || python3 -c "import time; print(int(time.time()*1000))")
        elapsed=$((end_time - start_time))
        echo $elapsed
    else
        echo "99999"
    fi
}

# ============================================================================
# 选择 GitHub 加速代理
# ============================================================================
select_proxy() {
    echo ""
    echo -e "${CYAN}[2/6]${NC} 配置下载源..."
    echo ""
    echo "是否使用 GitHub 加速代理？（国内用户推荐）"
    echo "  [1] 是 - 自动选择最快的加速代理（推荐国内用户）"
    echo "  [2] 否 - 直接从 GitHub 下载（需要良好的网络环境）"
    echo ""
    read -p "请选择 [1/2]: " USE_PROXY
    
    BEST_PROXY=""
    CLONE_URL="$GITHUB_REPO"
    
    if [[ "$USE_PROXY" == "1" ]]; then
        echo ""
        echo "正在测试各加速代理的连接速度..."
        echo ""
        
        MIN_TIME=999999
        
        for proxy in "${PROXY_LIST[@]}"; do
            echo -n "测试 $proxy ... "
            
            latency=$(test_proxy_latency "$proxy")
            
            if [[ $latency -lt 99999 ]]; then
                echo "响应时间: ${latency} ms"
                
                if [[ $latency -lt $MIN_TIME ]]; then
                    MIN_TIME=$latency
                    BEST_PROXY="$proxy"
                fi
            else
                echo -e "${RED}连接失败${NC}"
            fi
        done
        
        if [[ -n "$BEST_PROXY" ]]; then
            echo ""
            echo -e "${GREEN}✓ 最快代理: $BEST_PROXY ($MIN_TIME ms)${NC}"
            
            # 构建加速 URL
            CLONE_URL="$BEST_PROXY/$GITHUB_REPO"
            PLUGIN_CLONE_URL="$BEST_PROXY/$PLUGIN_REPO"
        else
            echo -e "${YELLOW}⚠ 所有代理均不可用，将使用直连${NC}"
        fi
    else
        echo -e "${YELLOW}使用 GitHub 直连${NC}"
    fi
}

# ============================================================================
# 选择安装目录
# ============================================================================
select_install_dir() {
    echo ""
    echo -e "${CYAN}[3/6]${NC} 选择安装目录..."
    echo ""
    echo "当前目录: $(pwd)"
    echo ""
    echo "安装目录选项："
    echo "  [1] 当前目录"
    echo "  [2] 用户主目录 ($HOME)"
    echo "  [3] 自定义目录"
    echo ""
    read -p "请选择 [1/2/3]: " DIR_CHOICE
    
    case "$DIR_CHOICE" in
        2)
            INSTALL_DIR="$HOME"
            ;;
        3)
            read -p "请输入安装目录路径: " INSTALL_DIR
            ;;
        *)
            INSTALL_DIR="$(pwd)"
            ;;
    esac
    
    # 创建目录
    if [[ ! -d "$INSTALL_DIR" ]]; then
        mkdir -p "$INSTALL_DIR" 2>/dev/null
        if [[ $? -ne 0 ]]; then
            echo -e "${RED}✗ 无法创建目录: $INSTALL_DIR${NC}"
            exit 1
        fi
    fi
    
    cd "$INSTALL_DIR"
    echo ""
    echo "安装目录: $INSTALL_DIR"
}

# ============================================================================
# 克隆或更新项目
# ============================================================================
clone_or_update() {
    echo ""
    echo -e "${CYAN}[4/6]${NC} 下载项目..."
    echo ""
    
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
            echo "清理旧目录..."
            rm -rf "$PROJECT_DIR"
        fi
        clone_project
    fi
    
    cd "$PROJECT_DIR"
}

clone_project() {
    echo "正在克隆项目..."
    echo "克隆地址: $CLONE_URL"
    echo ""
    
    if git clone "$CLONE_URL" "$PROJECT_DIR"; then
        echo -e "${GREEN}✓ 项目下载完成${NC}"
    else
        echo ""
        echo -e "${RED}✗ 克隆失败${NC}"
        
        if [[ -n "$BEST_PROXY" ]]; then
            echo "尝试使用 GitHub 直连..."
            
            if git clone "$GITHUB_REPO" "$PROJECT_DIR"; then
                echo -e "${GREEN}✓ 项目下载完成（直连）${NC}"
            else
                echo -e "${RED}✗ 直连也失败了，请检查网络${NC}"
                exit 1
            fi
        else
            exit 1
        fi
    fi
}

# ============================================================================
# 运行安装脚本
# ============================================================================
run_install() {
    echo ""
    echo -e "${CYAN}[5/6]${NC} 运行安装程序..."
    echo ""
    
    if [[ -f "install.sh" ]]; then
        chmod +x install.sh
        ./install.sh
    else
        echo -e "${RED}✗ 未找到 install.sh${NC}"
        exit 1
    fi
}

# ============================================================================
# 完成
# ============================================================================
finish() {
    echo ""
    echo -e "${CYAN}[6/6]${NC} 部署完成！"
    echo ""
    echo -e "${GREEN}╔══════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║                                                              ║${NC}"
    echo -e "${GREEN}║                      部署成功！                              ║${NC}"
    echo -e "${GREEN}║                                                              ║${NC}"
    echo -e "${GREEN}╚══════════════════════════════════════════════════════════════╝${NC}"
    echo ""
    echo "项目目录: $PROJECT_DIR"
    echo ""
}

# ============================================================================
# 主流程
# ============================================================================
main() {
    check_git
    select_proxy
    select_install_dir
    clone_or_update
    run_install
    finish
}

# 运行主流程
main