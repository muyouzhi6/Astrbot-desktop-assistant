#!/bin/bash
# =====================================================
# AstrBot Desktop Assistant - macOS 启动脚本
# 
# 双击此文件即可启动应用程序
# 首次运行时会自动安装依赖
# =====================================================

set -e

# 获取脚本所在目录
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

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
        print_info "推荐使用 Homebrew 安装: brew install python@3.11"
        echo ""
        read -p "按回车键退出..."
        exit 1
    fi
    
    # 检查版本
    PYTHON_VERSION=$($PYTHON_CMD -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
    PYTHON_MAJOR=$($PYTHON_CMD -c "import sys; print(sys.version_info.major)")
    PYTHON_MINOR=$($PYTHON_CMD -c "import sys; print(sys.version_info.minor)")
    
    if [ "$PYTHON_MAJOR" -lt 3 ] || ([ "$PYTHON_MAJOR" -eq 3 ] && [ "$PYTHON_MINOR" -lt 10 ]); then
        print_error "Python 版本过低！需要 Python 3.10 或更高版本，当前版本: $PYTHON_VERSION"
        print_info "推荐使用 Homebrew 安装: brew install python@3.11"
        echo ""
        read -p "按回车键退出..."
        exit 1
    fi
    
    print_success "Python 版本: $PYTHON_VERSION ✓"
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
            echo ""
            read -p "按回车键退出..."
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
    echo "  按 Ctrl+C 退出"
    echo "======================================"
    echo ""
    
    # 启动应用
    python -m desktop_client
    
    EXIT_CODE=$?
    if [ $EXIT_CODE -ne 0 ]; then
        print_error "应用程序异常退出 (退出码: $EXIT_CODE)"
        echo ""
        read -p "按回车键退出..."
    fi
}

# 主函数
main() {
    echo ""
    echo "======================================"
    echo "  AstrBot Desktop Assistant Launcher"
    echo "======================================"
    echo ""
    
    check_python
    setup_venv
    install_dependencies
    check_config
    start_app
}

# 运行
main