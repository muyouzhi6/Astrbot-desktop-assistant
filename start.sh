#!/bin/bash
# =====================================================
# AstrBot Desktop Assistant - 通用启动脚本
# 
# 适用于 Linux 和 macOS
# 在终端中运行: ./start.sh
# =====================================================

set -e

# 获取脚本所在目录
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

# 检测操作系统
OS_TYPE="$(uname -s)"
case "$OS_TYPE" in
    Darwin*)    OS_NAME="macOS" ;;
    Linux*)     OS_NAME="Linux" ;;
    MINGW*|MSYS*|CYGWIN*)    
        echo "Windows 用户请使用 start.bat 启动"
        exit 1
        ;;
    *)          OS_NAME="Unknown" ;;
esac

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 打印带颜色的消息
print_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# 检查 Python 版本
check_python() {
    print_info "检查 Python 环境..."
    
    # 优先使用 python3
    if command -v python3 &> /dev/null; then
        PYTHON_CMD="python3"
    elif command -v python &> /dev/null; then
        PYTHON_CMD="python"
    else
        print_error "未找到 Python！请先安装 Python 3.10 或更高版本。"
        if [ "$OS_NAME" = "macOS" ]; then
            print_info "推荐使用 Homebrew 安装: brew install python@3.11"
        elif [ "$OS_NAME" = "Linux" ]; then
            print_info "Ubuntu/Debian: sudo apt install python3 python3-pip python3-venv"
            print_info "CentOS/RHEL: sudo yum install python3 python3-pip"
            print_info "Arch Linux: sudo pacman -S python python-pip"
        fi
        exit 1
    fi
    
    # 检查版本
    PYTHON_VERSION=$($PYTHON_CMD -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
    PYTHON_MAJOR=$($PYTHON_CMD -c "import sys; print(sys.version_info.major)")
    PYTHON_MINOR=$($PYTHON_CMD -c "import sys; print(sys.version_info.minor)")
    
    if [ "$PYTHON_MAJOR" -lt 3 ] || ([ "$PYTHON_MAJOR" -eq 3 ] && [ "$PYTHON_MINOR" -lt 10 ]); then
        print_error "Python 版本过低！需要 Python 3.10 或更高版本，当前版本: $PYTHON_VERSION"
        exit 1
    fi
    
    print_success "Python 版本: $PYTHON_VERSION ✓"
}

# 检查 Linux 系统依赖
check_linux_deps() {
    if [ "$OS_NAME" != "Linux" ]; then
        return
    fi
    
    print_info "检查系统依赖..."
    
    MISSING_DEPS=""
    
    # 检查 Qt 相关依赖
    if ! ldconfig -p 2>/dev/null | grep -q libGL.so; then
        MISSING_DEPS="$MISSING_DEPS libgl1-mesa-glx"
    fi
    
    if ! ldconfig -p 2>/dev/null | grep -q libxcb.so; then
        MISSING_DEPS="$MISSING_DEPS libxcb-xinerama0"
    fi
    
    if [ -n "$MISSING_DEPS" ]; then
        print_warning "可能缺少以下系统依赖: $MISSING_DEPS"
        print_info "Ubuntu/Debian 安装命令: sudo apt install$MISSING_DEPS libxcb-cursor0 libegl1"
    else
        print_success "系统依赖检查通过 ✓"
    fi
}

# 设置虚拟环境
setup_venv() {
    VENV_DIR="$SCRIPT_DIR/.venv"
    
    if [ ! -d "$VENV_DIR" ]; then
        print_info "创建虚拟环境..."
        $PYTHON_CMD -m venv "$VENV_DIR"
        print_success "虚拟环境创建成功 ✓"
        NEED_INSTALL=true
    else
        print_info "使用已存在的虚拟环境"
        NEED_INSTALL=false
    fi
    
    # 激活虚拟环境
    source "$VENV_DIR/bin/activate"
    print_success "虚拟环境已激活 ✓"
}

# 安装依赖
install_dependencies() {
    if [ "$NEED_INSTALL" = true ] || [ ! -f "$VENV_DIR/.installed" ]; then
        print_info "安装依赖..."
        
        # 升级 pip
        pip install --upgrade pip -q
        
        # 安装依赖
        if [ -f "$SCRIPT_DIR/requirements.txt" ]; then
            pip install -r "$SCRIPT_DIR/requirements.txt" -q
            print_success "依赖安装完成 ✓"
        else
            print_error "未找到 requirements.txt 文件！"
            exit 1
        fi
        
        # 标记已安装
        touch "$VENV_DIR/.installed"
    else
        print_info "依赖已安装，跳过安装步骤"
    fi
}

# 检查配置文件
check_config() {
    CONFIG_FILE="$SCRIPT_DIR/desktop_client/config.yaml"
    CONFIG_EXAMPLE="$SCRIPT_DIR/desktop_client/config.example.yaml"
    
    if [ ! -f "$CONFIG_FILE" ]; then
        if [ -f "$CONFIG_EXAMPLE" ]; then
            print_warning "配置文件不存在，从示例文件创建..."
            cp "$CONFIG_EXAMPLE" "$CONFIG_FILE"
            print_success "配置文件已创建: $CONFIG_FILE"
            print_warning "请根据需要修改配置文件后重新运行"
        else
            print_warning "未找到配置文件，将使用默认配置"
        fi
    else
        print_info "配置文件已存在 ✓"
    fi
}

# 启动应用
start_app() {
    print_info "启动 AstrBot Desktop Assistant..."
    echo ""
    echo "======================================"
    echo "  AstrBot Desktop Assistant"
    echo "  操作系统: $OS_NAME"
    echo "  按 Ctrl+C 退出"
    echo "======================================"
    echo ""
    
    # 设置 Qt 环境变量（解决某些 Linux 发行版的问题）
    if [ "$OS_NAME" = "Linux" ]; then
        export QT_QPA_PLATFORM="${QT_QPA_PLATFORM:-xcb}"
        # 如果在 Wayland 下运行，可能需要以下设置
        if [ "$XDG_SESSION_TYPE" = "wayland" ]; then
            export QT_QPA_PLATFORM="wayland;xcb"
        fi
    fi
    
    # 启动应用
    python -m desktop_client
    
    EXIT_CODE=$?
    if [ $EXIT_CODE -ne 0 ]; then
        print_error "应用程序异常退出 (退出码: $EXIT_CODE)"
    fi
}

# 显示帮助
show_help() {
    echo "AstrBot Desktop Assistant 启动脚本"
    echo ""
    echo "用法: $0 [选项]"
    echo ""
    echo "选项:"
    echo "  --help, -h      显示此帮助信息"
    echo "  --reinstall     重新安装依赖"
    echo "  --check         仅检查环境，不启动应用"
    echo ""
}

# 主函数
main() {
    # 解析命令行参数
    while [ $# -gt 0 ]; do
        case "$1" in
            --help|-h)
                show_help
                exit 0
                ;;
            --reinstall)
                NEED_INSTALL=true
                rm -f "$SCRIPT_DIR/.venv/.installed" 2>/dev/null || true
                shift
                ;;
            --check)
                CHECK_ONLY=true
                shift
                ;;
            *)
                print_error "未知选项: $1"
                show_help
                exit 1
                ;;
        esac
    done
    
    echo ""
    echo "======================================"
    echo "  AstrBot Desktop Assistant Launcher"
    echo "  Operating System: $OS_NAME"
    echo "======================================"
    echo ""
    
    check_python
    check_linux_deps
    setup_venv
    install_dependencies
    check_config
    
    if [ "${CHECK_ONLY:-false}" = true ]; then
        print_success "环境检查完成！"
        exit 0
    fi
    
    start_app
}

# 运行
main "$@"