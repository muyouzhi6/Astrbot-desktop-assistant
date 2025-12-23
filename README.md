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
```bash
# 克隆项目
git clone https://github.com/muyouzhi6/Astrbot-desktop-assistant.git
cd Astrbot-desktop-assistant

# 安装依赖
pip install -r requirements.txt
```

### 3. 运行
```bash
python -m desktop_client
```
首次运行需在设置中配置 AstrBot 服务器地址及账号信息。

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