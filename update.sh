#!/bin/bash

# ============================================================================
# AstrBot Desktop Assistant - macOS/Linux 一键更新脚本
# ============================================================================
# 特点：
#   1. 支持双模式更新：Git（最新版）/ Release（稳定版）
#   2. 只需选择网络环境（海外/国内）
#   3. 自动检测项目目录
#   4. 自动更新代码和依赖
#   5. 显示版本变化
# ============================================================================
# 用法：
#   ./update.sh                    - 默认使用 Git 模式更新到最新代码
#   ./update.sh git                - 使用 Git 模式更新到最新代码
#   ./update.sh release v1.0.0     - 使用 Release 模式更新到指定版本
# ============================================================================

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
WHITE='\033[1;37m'
NC='\033[0m' # No Color

# 解析命令行参数
UPDATE_MODE="${1:-git}"
TARGET_VERSION="${2:-}"

# 验证参数
if [[ "$UPDATE_MODE" == "release" && -z "$TARGET_VERSION" ]]; then
    echo ""
    echo -e "${RED}错误: Release 模式需要指定版本号${NC}"
    echo "用法: ./update.sh release v1.0.0"
    echo ""
    exit 1
fi

# 加速代理列表
PROXY_HOSTS=("gh.llkk.cc" "gh-proxy.com" "mirror.ghproxy.com" "ghproxy.net")

echo ""
echo -e "${CYAN}╔══════════════════════════════════════════════════════════════════════╗${NC}"
echo -e "${CYAN}║                                                                      ║${NC}"
echo -e "${CYAN}║          ${WHITE}AstrBot Desktop Assistant 一键更新脚本${CYAN}                      ║${NC}"
echo -e "${CYAN}║                                                                      ║${NC}"
echo -e "${CYAN}╚══════════════════════════════════════════════════════════════════════╝${NC}"
echo ""

# 显示更新模式
if [[ "$UPDATE_MODE" == "release" ]]; then
    echo -e "${YELLOW}更新模式: Release（稳定版）- 目标版本: $TARGET_VERSION${NC}"
else
    echo -e "${GREEN}更新模式: Git（最新版）${NC}"
fi
echo ""

# ============================================================================
# 检测项目目录
# ============================================================================
echo -e "${CYAN}[1/5]${NC} 检测项目目录..."

PROJECT_DIR=""

# 检查当前目录
if [[ -d ".git" && -d "desktop_client" ]]; then
    PROJECT_DIR="$(pwd)"
fi

# 检查当前目录下的 Astrbot-desktop-assistant 子目录
if [[ -z "$PROJECT_DIR" && -d "Astrbot-desktop-assistant/.git" ]]; then
    PROJECT_DIR="$(pwd)/Astrbot-desktop-assistant"
fi

# 检查父目录
if [[ -z "$PROJECT_DIR" && -d "../.git" && -d "../desktop_client" ]]; then
    PROJECT_DIR="$(cd .. && pwd)"
fi

# 检查脚本所在目录
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [[ -z "$PROJECT_DIR" && -d "$SCRIPT_DIR/.git" && -d "$SCRIPT_DIR/desktop_client" ]]; then
    PROJECT_DIR="$SCRIPT_DIR"
fi

if [[ -z "$PROJECT_DIR" ]]; then
    echo ""
    echo -e "${RED}╔══════════════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${RED}║  ✗ 未找到 AstrBot Desktop Assistant 项目                             ║${NC}"
    echo -e "${RED}╠══════════════════════════════════════════════════════════════════════╣${NC}"
    echo -e "${RED}║                                                                      ║${NC}"
    echo -e "${RED}║  请确保：                                                            ║${NC}"
    echo -e "${RED}║    • 在项目目录中运行此脚本                                          ║${NC}"
    echo -e "${RED}║    • 或在包含 Astrbot-desktop-assistant 文件夹的目录中运行           ║${NC}"
    echo -e "${RED}║                                                                      ║${NC}"
    echo -e "${RED}║  如果尚未安装，请先运行 quick_install.sh                             ║${NC}"
    echo -e "${RED}║                                                                      ║${NC}"
    echo -e "${RED}╚══════════════════════════════════════════════════════════════════════╝${NC}"
    echo ""
    exit 1
fi

echo -e "${GREEN}✓ 找到项目目录: $PROJECT_DIR${NC}"
cd "$PROJECT_DIR"

# ============================================================================
# 显示当前版本
# ============================================================================
echo ""
echo -e "${CYAN}[2/5]${NC} 获取版本信息..."

# 保存当前版本
OLD_COMMIT=$(git log -1 --format="%h" 2>/dev/null)
OLD_DATE=$(git log -1 --format="%ci" 2>/dev/null)
OLD_MSG=$(git log -1 --format="%s" 2>/dev/null)

echo ""
echo -e "${WHITE}当前版本：${NC}"
echo "  提交: $OLD_COMMIT"
echo "  日期: $OLD_DATE"
echo "  说明: $OLD_MSG"

# ============================================================================
# 选择网络环境
# ============================================================================
echo ""
echo -e "${WHITE}请选择您的网络环境：${NC}"
echo ""
echo -e "  ${CYAN}[1]${NC} 我有海外网络环境（可直接访问 GitHub）"
echo -e "  ${CYAN}[2]${NC} 我没有海外网络（使用国内加速，推荐大多数用户）"
echo ""
read -p "请输入选择 [1/2]: " NETWORK_CHOICE

BEST_PROXY=""

if [[ "$NETWORK_CHOICE" == "1" ]]; then
    echo ""
    echo -e "${GREEN}✓ 将使用 GitHub 直连${NC}"
else
    echo ""
    echo -e "${CYAN}正在自动测试加速代理，请稍候...${NC}"
    echo ""
    
    for host in "${PROXY_HOSTS[@]}"; do
        echo -n "  测试 $host ... "
        
        if ping -c 1 -W 3 "$host" &>/dev/null; then
            echo -e "${GREEN}✓ 可用${NC}"
            if [[ -z "$BEST_PROXY" ]]; then
                BEST_PROXY="$host"
            fi
        else
            echo -e "${RED}✗ 不可用${NC}"
        fi
    done
    
    if [[ -n "$BEST_PROXY" ]]; then
        echo ""
        echo -e "${GREEN}✓ 已选择代理: $BEST_PROXY${NC}"
        
        # 配置 Git 代理
        git config --local url."https://$BEST_PROXY/https://github.com".insteadOf "https://github.com"
    else
        echo ""
        echo -e "${YELLOW}⚠ 所有代理均不可用，将尝试直连${NC}"
    fi
fi

# ============================================================================
# 更新代码
# ============================================================================
echo ""
echo -e "${CYAN}[3/5]${NC} 更新代码..."

update_failed() {
    echo ""
    echo -e "${RED}更新失败，请检查网络连接或版本号是否正确${NC}"
    # 清理代理配置
    if [[ -n "$BEST_PROXY" ]]; then
        git config --local --unset url."https://$BEST_PROXY/https://github.com".insteadOf 2>/dev/null
    fi
    exit 1
}

if [[ "$UPDATE_MODE" == "release" ]]; then
    # ========================================================================
    # Release 模式：切换到指定版本标签
    # ========================================================================
    echo "正在获取版本标签..."
    if ! git fetch --tags 2>/dev/null; then
        echo -e "${RED}✗ 获取标签失败${NC}"
        update_failed
    fi
    
    # 检查目标版本是否存在
    if ! git tag -l "$TARGET_VERSION" | grep -q .; then
        echo -e "${RED}✗ 版本 $TARGET_VERSION 不存在${NC}"
        echo ""
        echo -e "${WHITE}可用版本列表：${NC}"
        git tag -l --sort=-v:refname | head -10 2>/dev/null
        update_failed
    fi
    
    # 切换到指定版本
    echo "正在切换到版本 $TARGET_VERSION..."
    if ! git checkout "$TARGET_VERSION" 2>/dev/null; then
        echo -e "${YELLOW}⚠ 切换失败，尝试强制切换...${NC}"
        if ! git checkout -f "$TARGET_VERSION" 2>/dev/null; then
            echo -e "${RED}✗ 切换版本失败${NC}"
            update_failed
        fi
    fi
    
    echo -e "${GREEN}✓ 已切换到版本 $TARGET_VERSION${NC}"
    
else
    # ========================================================================
    # Git 模式：拉取最新代码
    # ========================================================================
    # 先 fetch
    git fetch origin main --depth 1 2>/dev/null || git fetch origin master --depth 1 2>/dev/null

    # 执行 pull
    echo "正在拉取最新代码..."
    if ! git pull --rebase 2>/dev/null; then
        # 尝试不带 rebase
        if ! git pull 2>/dev/null; then
            echo -e "${YELLOW}⚠ 常规更新失败，尝试强制更新...${NC}"
            git fetch origin main --depth 1 2>/dev/null && git reset --hard origin/main 2>/dev/null || \
            (git fetch origin master --depth 1 2>/dev/null && git reset --hard origin/master 2>/dev/null)
        fi
    fi
fi

# 清理代理配置
if [[ -n "$BEST_PROXY" ]]; then
    git config --local --unset url."https://$BEST_PROXY/https://github.com".insteadOf 2>/dev/null
fi

# 获取新版本
NEW_COMMIT=$(git log -1 --format="%h" 2>/dev/null)
NEW_DATE=$(git log -1 --format="%ci" 2>/dev/null)
NEW_MSG=$(git log -1 --format="%s" 2>/dev/null)

# 获取当前标签（如果有）
NEW_TAG=$(git describe --tags --exact-match 2>/dev/null)

echo ""
echo -e "${WHITE}更新后版本：${NC}"
echo "  提交: $NEW_COMMIT"
if [[ -n "$NEW_TAG" ]]; then
    echo "  标签: $NEW_TAG"
fi
echo "  日期: $NEW_DATE"
echo "  说明: $NEW_MSG"

# 比较版本
if [[ "$OLD_COMMIT" == "$NEW_COMMIT" ]]; then
    echo ""
    echo -e "${GREEN}✓ 已是最新版本，无需更新${NC}"
else
    echo ""
    echo -e "${GREEN}✓ 代码已更新 ($OLD_COMMIT → $NEW_COMMIT)${NC}"
fi

# ============================================================================
# 更新依赖
# ============================================================================
echo ""
echo -e "${CYAN}[4/5]${NC} 更新依赖包..."

# 检测 Python
PYTHON_CMD=""

if [[ -f "$PROJECT_DIR/venv/bin/python" ]]; then
    PYTHON_CMD="$PROJECT_DIR/venv/bin/python"
else
    for cmd in python3 python; do
        if command -v $cmd &>/dev/null; then
            version=$($cmd --version 2>&1 | grep -oE '[0-9]+\.[0-9]+')
            major=$(echo $version | cut -d. -f1)
            minor=$(echo $version | cut -d. -f2)
            
            if [[ $major -ge 3 && $minor -ge 10 ]]; then
                PYTHON_CMD=$cmd
                break
            fi
        fi
    done
fi

if [[ -z "$PYTHON_CMD" ]]; then
    echo -e "${YELLOW}⚠ 未检测到 Python，跳过依赖更新${NC}"
else
    # 升级 pip
    "$PYTHON_CMD" -m pip install --upgrade pip -q 2>/dev/null
    
    # 安装/更新依赖
    "$PYTHON_CMD" -m pip install -r "$PROJECT_DIR/requirements.txt" -q 2>/dev/null
    
    if [[ $? -eq 0 ]]; then
        echo -e "${GREEN}✓ 依赖更新完成${NC}"
    else
        echo -e "${YELLOW}⚠ 部分依赖更新可能失败${NC}"
    fi
fi

# ============================================================================
# 完成
# ============================================================================
echo ""
echo -e "${CYAN}[5/5]${NC} 更新完成！"
echo ""
echo -e "${GREEN}╔══════════════════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║                                                                      ║${NC}"
echo -e "${GREEN}║                    ✓ 更新成功！                                      ║${NC}"
echo -e "${GREEN}║                                                                      ║${NC}"
echo -e "${GREEN}╠══════════════════════════════════════════════════════════════════════╣${NC}"
echo -e "${GREEN}║                                                                      ║${NC}"

if [[ "$UPDATE_MODE" == "release" ]]; then
    echo -e "${GREEN}║  模式: Release（稳定版）                                             ║${NC}"
    echo -e "${GREEN}║  目标版本: $TARGET_VERSION                                                    ║${NC}"
else
    echo -e "${GREEN}║  模式: Git（最新版）                                                 ║${NC}"
fi
if [[ "$OLD_COMMIT" == "$NEW_COMMIT" ]]; then
    echo -e "${GREEN}║  状态: 已是最新版本                                                  ║${NC}"
else
    echo -e "${GREEN}║  版本变化: $OLD_COMMIT → $NEW_COMMIT                                           ║${NC}"
fi

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
    
    if [[ -n "$PYTHON_CMD" ]]; then
        "$PYTHON_CMD" -m desktop_client &
    elif [[ -f "$PROJECT_DIR/start.sh" ]]; then
        bash "$PROJECT_DIR/start.sh" &
    fi
    
    echo -e "${GREEN}✓ 应用已启动${NC}"
fi

echo ""
echo -e "${CYAN}感谢使用 AstrBot Desktop Assistant！${NC}"
echo ""