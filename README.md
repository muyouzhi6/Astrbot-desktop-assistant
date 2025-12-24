# 🖥️ AstrBot 桌面助手客户端 (Desktop Client)

[![CI](https://github.com/muyouzhi6/Astrbot-desktop-assistant/actions/workflows/ci.yml/badge.svg)](https://github.com/muyouzhi6/Astrbot-desktop-assistant/actions/workflows/ci.yml)
[![Release](https://github.com/muyouzhi6/Astrbot-desktop-assistant/actions/workflows/release.yml/badge.svg)](https://github.com/muyouzhi6/Astrbot-desktop-assistant/actions/workflows/release.yml)
[![Python](https://img.shields.io/badge/Python-3.9%2B-blue)](https://www.python.org/)
[![PySide6](https://img.shields.io/badge/PySide6-6.5%2B-green)](https://wiki.qt.io/Qt_for_Python)
[![License](https://img.shields.io/badge/License-MIT-yellow)](LICENSE)

基于 PySide6 构建的 AstrBot 轻量级桌面客户端，采用"悬浮球 + 对话窗口"的统一交互设计，提供流畅的桌面 AI 体验。

> ⚠️ **注意**：本项目需配合服务端插件 [astrbot_plugin_desktop_assistant](https://github.com/muyouzhi6/astrbot_plugin_desktop_assistant) 使用。

## ✨ 核心功能

### 🎈 智能悬浮球
- **灵动交互**：支持拖拽停靠，双击唤起对话，右键快捷菜单。
- **状态感知**：呼吸灯效提示消息接收与处理状态。
- **消息气泡**：单击快速预览最新消息回复。

### 💬 沉浸式对话窗口
- **富文本支持**：完整支持 Markdown 渲染（代码高亮、公式、表格）。
- **多模态输入**：
  - **图片/文件**：支持直接拖拽或粘贴发送。
  - **语音交互**：支持语音消息自动播放。
- **便捷操作**：支持快捷键发送（Enter/Shift+Enter）、图片缩放预览。

### ⚙️ 系统集成
- **系统托盘**：后台常驻，支持开机自启。
- **全局热键**：支持自定义快捷键唤起。
- **主题适配**：亮色/暗色模式自动切换。

## 🚀 快速开始

### 1. 安装服务端插件
请确保 AstrBot 服务端已安装配套插件：
```bash
git clone https://github.com/muyouzhi6/astrbot_plugin_desktop_assistant.git data/plugins/astrbot_plugin_desktop_assistant
```

### 2. 安装客户端

#### 🌟 方式一：一键下载部署（推荐国内新手用户）

> 🚀 **一键脚本特点**：自动检测最快的 GitHub 加速代理、下载项目、安装依赖、配置开机自启、创建桌面快捷方式。

**Windows 用户：**

1. 下载一键部署脚本：[quick_install.bat](https://gh.llkk.cc/https://raw.githubusercontent.com/muyouzhi6/Astrbot-desktop-assistant/main/quick_install.bat)
2. 双击运行，按提示操作即可

或使用 PowerShell 命令：
```powershell
# 下载并运行一键部署脚本
Invoke-WebRequest -Uri "https://gh.llkk.cc/https://raw.githubusercontent.com/muyouzhi6/Astrbot-desktop-assistant/main/quick_install.bat" -OutFile "quick_install.bat"; .\quick_install.bat
```

**macOS / Linux 用户：**
```bash
# 下载并运行一键部署脚本
curl -fsSL https://gh.llkk.cc/https://raw.githubusercontent.com/muyouzhi6/Astrbot-desktop-assistant/main/quick_install.sh -o quick_install.sh && chmod +x quick_install.sh && ./quick_install.sh
```

> 💡 **GitHub 加速说明**：脚本会自动测试以下加速代理并选择最快的：
> - `https://gh.llkk.cc`
> - `https://gh-proxy.com`
> - `https://mirror.ghproxy.com`
> - `https://ghproxy.net`
>
> 您也可以选择不使用加速，直接从 GitHub 下载。

#### 方式二：本地一键部署（已克隆项目）

如果已经克隆了项目到本地：

**Windows 用户：**
```bash
# 克隆项目
git clone https://github.com/muyouzhi6/Astrbot-desktop-assistant.git
cd Astrbot-desktop-assistant

# 双击 install.bat 或在命令行运行
install.bat
```

**macOS / Linux 用户：**
```bash
# 克隆项目
git clone https://github.com/muyouzhi6/Astrbot-desktop-assistant.git
cd Astrbot-desktop-assistant

# 授予执行权限并运行
chmod +x install.sh
./install.sh
```

安装完成后，可以通过以下方式启动：
- 🖱️ 双击桌面快捷方式
- 📟 运行 `start.bat`（Windows）或 `./start.sh`（macOS/Linux）
- ⌨️ 命令行：`python -m desktop_client`

#### 方式三：快速启动（已有 Python 环境）

**Windows 用户：**
```bash
# 克隆项目后，双击 start.bat 即可启动
git clone https://github.com/muyouzhi6/Astrbot-desktop-assistant.git
```

**macOS 用户：**
```bash
# 克隆项目后，双击 start.command 即可启动
git clone https://github.com/muyouzhi6/Astrbot-desktop-assistant.git
cd Astrbot-desktop-assistant

# 如果双击无法运行，请先授予执行权限
chmod +x start.command
```

**Linux 用户：**
```bash
git clone https://github.com/muyouzhi6/Astrbot-desktop-assistant.git
cd Astrbot-desktop-assistant
chmod +x start.sh
./start.sh
```

#### 方式四：手动安装

```bash
# 克隆项目
git clone https://github.com/muyouzhi6/Astrbot-desktop-assistant.git
cd Astrbot-desktop-assistant

# 创建虚拟环境（推荐）
python3 -m venv venv
source venv/bin/activate  # Linux/macOS
# 或 venv\Scripts\activate  # Windows

# 安装依赖
pip install -r requirements.txt
```

### 3. 运行
```bash
python -m desktop_client
```
首次运行需在设置中配置 AstrBot 服务器地址及账号信息。

### 4. 开机自启配置

#### 自动配置（推荐）
使用一键部署脚本 `install.bat` 或 `install.sh` 时，会提示是否配置开机自启。

#### 手动配置
也可以在应用内设置：
1. 右键点击悬浮球或系统托盘图标
2. 选择「设置」
3. 在「通用设置」中勾选「开机自启动」
4. 保存设置

#### 故障排查
如果开机自启不生效：

**Windows：**
- 检查注册表：`HKEY_CURRENT_USER\Software\Microsoft\Windows\CurrentVersion\Run` 是否有 `AstrBotDesktopClient` 项
- 查看配置目录下的 `autostart_info.txt` 和 `autostart_error.log`

**macOS：**
- 检查 `~/Library/LaunchAgents/com.astrbot.desktop-assistant.plist` 是否存在
- 运行 `launchctl list | grep astrbot` 查看服务状态

**Linux：**
- 检查 `~/.config/autostart/astrbot-desktop-assistant.desktop` 是否存在

## 🍎 macOS 特别说明

### 系统要求
- macOS 10.14 (Mojave) 或更高版本
- Python 3.10+（推荐使用 Homebrew 安装：`brew install python@3.11`）

### 悬浮球置顶功能
macOS 版本自动安装 `pyobjc-framework-Cocoa` 以实现窗口置顶功能。如果悬浮球无法正常置顶，请确保：
1. 依赖已正确安装：`pip install pyobjc-framework-Cocoa`
2. 授予应用必要的系统权限

### 常见问题

**Q: 启动脚本双击无反应？**
```bash
# 在终端中授予执行权限
chmod +x start.command
```

**Q: 依赖安装失败？**
```bash
# 确保 Xcode 命令行工具已安装
xcode-select --install
```

## 🐧 Linux 特别说明

### 系统依赖
部分 Linux 发行版可能需要安装 Qt 相关依赖：
```bash
# Ubuntu/Debian
sudo apt install libgl1-mesa-glx libxcb-xinerama0 libxcb-cursor0 libegl1

# Fedora
sudo dnf install mesa-libGL libxcb
```

### Wayland 支持
如果在 Wayland 环境下运行，启动脚本会自动设置 `QT_QPA_PLATFORM=wayland;xcb`。

## 📦 目录结构
```
desktop_client/
├── gui/                 # 界面组件 (悬浮球, 聊天窗口, 设置等)
├── handlers/            # 消息处理器 (消息, 截图, 主动对话, 媒体)
├── platforms/           # 平台适配器 (Windows, macOS, Linux)
├── services/            # 核心服务 (API通信, 截图, 桌面监控)
├── controllers/         # 控制器 (设置管理)
├── utils/               # 工具类
├── config.py            # 配置管理
├── bridge.py            # 消息桥接层
├── api_client.py        # API 客户端
└── main.py              # 程序入口
```

详细架构说明请参阅 [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)。

## 🤝 参与贡献

我们欢迎任何形式的贡献！无论是报告 Bug、提出新功能建议，还是直接提交代码。

### 快速开始

```bash
# Fork 并克隆项目
git clone https://github.com/YOUR_USERNAME/Astrbot-desktop-assistant.git
cd Astrbot-desktop-assistant

# 创建虚拟环境
python -m venv venv
source venv/bin/activate  # Linux/macOS
# 或 venv\Scripts\activate  # Windows

# 安装依赖
pip install -r requirements.txt

# 运行测试
pytest
```

### 贡献指南

- 📖 [贡献指南](CONTRIBUTING.md) - 开发环境搭建、代码规范、Git 工作流
- 🏗️ [架构文档](docs/ARCHITECTURE.md) - 项目结构、设计模式、模块说明
- 🐛 [报告 Bug](.github/ISSUE_TEMPLATE/bug_report.md) - 使用 Issue 模板报告问题
- ✨ [功能请求](.github/ISSUE_TEMPLATE/feature_request.md) - 提出新功能建议

### 开发者资源

| 资源 | 说明 |
|------|------|
| [CONTRIBUTING.md](CONTRIBUTING.md) | 完整的贡献指南 |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | 架构设计文档 |
| [tests/](tests/) | 测试用例目录 |

## 📄 许可证
本项目采用 MIT 许可证。

## 🙏 致谢

感谢所有为本项目做出贡献的开发者！

---

<p align="center">
  <a href="https://github.com/muyouzhi6/Astrbot-desktop-assistant/issues">报告问题</a> •
  <a href="https://github.com/muyouzhi6/Astrbot-desktop-assistant/discussions">参与讨论</a> •
  <a href="CONTRIBUTING.md">参与贡献</a>
</p>