# 贡献指南

感谢你对 **AstrBot Desktop Assistant** 项目的关注！我们欢迎任何形式的贡献，包括但不限于：

- 🐛 Bug 报告和修复
- ✨ 新功能开发
- 📚 文档改进
- 🧪 测试用例编写
- 💡 建议和反馈

## 📋 目录

- [行为准则](#行为准则)
- [快速开始](#快速开始)
- [开发环境搭建](#开发环境搭建)
- [代码规范](#代码规范)
- [Git 工作流](#git-工作流)
- [提交 Pull Request](#提交-pull-request)
- [测试要求](#测试要求)
- [项目结构](#项目结构)
- [获取帮助](#获取帮助)

---

## 行为准则

参与本项目即表示你同意遵守以下准则：

- 尊重每一位贡献者
- 提供建设性的反馈
- 专注于对社区最有益的事情
- 保持开放和包容的心态

---

## 快速开始

```bash
# 1. Fork 本仓库到你的 GitHub 账号

# 2. 克隆你 Fork 的仓库
git clone https://github.com/YOUR_USERNAME/Astrbot-desktop-assistant.git
cd Astrbot-desktop-assistant

# 3. 添加上游仓库
git remote add upstream https://github.com/muyouzhi6/Astrbot-desktop-assistant.git

# 4. 创建虚拟环境并安装依赖
python -m venv venv
# Windows:
venv\Scripts\activate
# Linux/macOS:
source venv/bin/activate

pip install -r requirements.txt

# 5. 运行测试确保环境正常
pytest

# 6. 启动应用
python -m desktop_client
```

---

## 开发环境搭建

### 系统要求

| 要求 | 版本 |
|------|------|
| Python | 3.9+ (推荐 3.10+) |
| PySide6 | 6.5+ |
| 操作系统 | Windows 10+、macOS 10.15+、Linux (X11/Wayland) |

### 依赖安装

```bash
# 安装项目依赖
pip install -r requirements.txt

# Windows 用户如需完整的窗口信息检测功能
pip install pywin32
```

### 开发工具推荐

| 工具 | 用途 |
|------|------|
| VS Code / PyCharm | IDE |
| Black | 代码格式化 |
| Pylint / Flake8 | 代码检查 |
| pytest | 测试框架 |
| pre-commit | Git 钩子管理 |

### 可选：安装开发依赖

```bash
# 安装代码格式化和检查工具
pip install black flake8 pylint isort mypy

# 安装 pre-commit（推荐）
pip install pre-commit
pre-commit install
```

---

## 代码规范

本项目遵循 **PEP 8** Python 代码风格指南，并有以下额外约定：

### 基本规范

```python
# ✅ 正确示例

# 1. 类名使用 PascalCase
class MessageHandler:
    pass

# 2. 函数和变量名使用 snake_case
def handle_message(message_text: str) -> None:
    pass

# 3. 常量使用 UPPER_SNAKE_CASE
MAX_RETRY_COUNT = 3
DEFAULT_TIMEOUT = 30

# 4. 私有方法/属性使用单下划线前缀
class MyClass:
    def __init__(self):
        self._internal_state = {}
    
    def _private_method(self):
        pass

# 5. 模块导入顺序：标准库 → 第三方库 → 本地模块
import os
import sys
from typing import Optional

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QWidget

from .config import ClientConfig
from .handlers import MessageHandler
```

### 类型注解

```python
# ✅ 推荐使用类型注解
from typing import Optional, List, Dict, Callable

def process_messages(
    messages: List[str],
    callback: Optional[Callable[[str], None]] = None
) -> Dict[str, int]:
    """处理消息列表并返回统计信息"""
    result: Dict[str, int] = {"processed": 0, "failed": 0}
    for msg in messages:
        # 处理逻辑...
        result["processed"] += 1
    return result
```

### 文档字符串

```python
def get_active_window(self) -> WindowInfo:
    """
    获取当前活动窗口信息
    
    Returns:
        WindowInfo: 包含窗口标题、进程名、PID 的窗口信息对象
        
    Raises:
        PlatformNotSupportedError: 当前平台不支持此功能
        
    Example:
        >>> adapter = WindowsPlatformAdapter()
        >>> info = adapter.get_active_window()
        >>> print(f"当前窗口: {info.title}")
    """
    pass
```

### 代码格式化

```bash
# 使用 Black 格式化代码
black desktop_client/

# 使用 isort 排序导入
isort desktop_client/

# 检查代码风格
flake8 desktop_client/
```

---

## Git 工作流

### 分支策略

| 分支类型 | 命名规范 | 说明 |
|----------|----------|------|
| 主分支 | `main` | 稳定版本，保持可发布状态 |
| 功能分支 | `feature/功能描述` | 新功能开发 |
| 修复分支 | `fix/问题描述` | Bug 修复 |
| 文档分支 | `docs/文档描述` | 文档更新 |
| 重构分支 | `refactor/重构描述` | 代码重构 |

### 分支命名示例

```bash
# 新功能
git checkout -b feature/add-voice-input
git checkout -b feature/theme-customization

# Bug 修复
git checkout -b fix/connection-timeout
git checkout -b fix/memory-leak-in-chat

# 文档更新
git checkout -b docs/update-api-reference

# 代码重构
git checkout -b refactor/handler-architecture
```

### Commit 规范

使用 [Conventional Commits](https://www.conventionalcommits.org/) 规范：

```
<type>(<scope>): <subject>

<body>

<footer>
```

#### Type 类型

| 类型 | 说明 |
|------|------|
| `feat` | 新功能 |
| `fix` | Bug 修复 |
| `docs` | 文档更新 |
| `style` | 代码格式（不影响功能） |
| `refactor` | 代码重构 |
| `test` | 测试相关 |
| `chore` | 构建/工具链相关 |
| `perf` | 性能优化 |

#### Commit 示例

```bash
# 新功能
git commit -m "feat(gui): 添加主题自定义功能"

# Bug 修复
git commit -m "fix(bridge): 修复 WebSocket 断开后无法重连的问题"

# 文档更新
git commit -m "docs: 更新 README 安装说明"

# 带详细描述的提交
git commit -m "feat(platforms): 新增 Linux 平台适配器

- 实现窗口信息获取
- 支持 X11 和 Wayland
- 添加开机自启功能

Closes #42"
```

### 保持分支同步

```bash
# 获取上游最新代码
git fetch upstream

# 合并到本地 main 分支
git checkout main
git merge upstream/main

# 变基你的功能分支
git checkout feature/your-feature
git rebase main
```

---

## 提交 Pull Request

### PR 前检查清单

- [ ] 代码已通过所有测试 (`pytest`)
- [ ] 代码已格式化 (`black`, `isort`)
- [ ] 新功能已添加测试用例
- [ ] 文档已更新（如适用）
- [ ] Commit 信息符合规范
- [ ] 分支已与 main 同步

### PR 流程

1. **确保本地测试通过**
   ```bash
   pytest
   black --check desktop_client/
   flake8 desktop_client/
   ```

2. **推送分支到你的 Fork**
   ```bash
   git push origin feature/your-feature
   ```

3. **创建 Pull Request**
   - 前往 GitHub 创建 PR
   - 填写 PR 模板（见下文）
   - 关联相关 Issue

4. **等待 Code Review**
   - 及时响应审阅意见
   - 根据反馈进行修改

5. **合并**
   - 审阅通过后由维护者合并
   - 合并后删除功能分支

### PR 描述模板

```markdown
## 变更类型
- [ ] 新功能
- [ ] Bug 修复
- [ ] 文档更新
- [ ] 代码重构
- [ ] 其他

## 变更描述
简要描述此 PR 的主要变更内容...

## 相关 Issue
Fixes #123

## 测试说明
描述如何测试此变更...

## 截图（如适用）
附上 UI 变更的截图...
```

---

## 测试要求

### 测试框架

本项目使用 `pytest` 作为测试框架：

```bash
# 运行所有测试
pytest

# 运行特定测试文件
pytest tests/test_config.py

# 运行特定测试函数
pytest tests/test_config.py::test_config_load

# 显示详细输出
pytest -v

# 显示测试覆盖率
pytest --cov=desktop_client
```

### 测试文件结构

```
tests/
├── __init__.py
├── conftest.py          # pytest 配置和通用 fixtures
├── test_config.py       # 配置模块测试
├── test_bridge.py       # 消息桥接测试
├── test_platforms.py    # 平台适配器测试
└── test_handlers.py     # 处理器测试
```

### 编写测试用例

```python
# tests/test_example.py

import pytest
from desktop_client.config import ClientConfig, load_config

class TestClientConfig:
    """配置类测试"""
    
    def test_default_config(self):
        """测试默认配置加载"""
        config = ClientConfig()
        assert config.server.url == ""
        assert config.server.auto_reconnect is True
    
    def test_config_validation(self):
        """测试配置验证"""
        with pytest.raises(ValueError):
            ClientConfig(server={"reconnect_interval": -1})
    
    @pytest.mark.asyncio
    async def test_async_operation(self):
        """测试异步操作"""
        # 异步测试示例
        result = await some_async_function()
        assert result is not None
```

### 测试标记

```python
import pytest

# 单元测试
@pytest.mark.unit
def test_unit_example():
    pass

# 集成测试
@pytest.mark.integration
def test_integration_example():
    pass

# 需要 GUI 环境的测试
@pytest.mark.gui
def test_gui_example():
    pass

# 慢速测试
@pytest.mark.slow
def test_slow_example():
    pass
```

### 新功能测试要求

提交新功能时，请确保：

1. **单元测试覆盖**：核心逻辑需有对应测试
2. **边界条件**：测试边界情况和异常处理
3. **Mock 使用**：适当使用 mock 隔离外部依赖
4. **测试命名**：使用描述性命名，如 `test_功能_场景_预期结果`

---

## 项目结构

```
Astrbot-desktop-assistant/
├── desktop_client/              # 主程序包
│   ├── __init__.py
│   ├── __main__.py              # 入口点
│   ├── app.py                   # 应用主类
│   ├── api_client.py            # API 客户端
│   ├── bridge.py                # 消息桥接层
│   ├── config.py                # 配置管理
│   │
│   ├── gui/                     # GUI 组件
│   │   ├── floating_ball.py     # 悬浮球
│   │   ├── chat_widgets.py      # 聊天组件
│   │   ├── settings_window.py   # 设置窗口
│   │   ├── themes.py            # 主题系统
│   │   └── ...
│   │
│   ├── handlers/                # 消息处理器
│   │   ├── message_handler.py   # 消息处理
│   │   ├── screenshot_handler.py # 截图处理
│   │   ├── proactive_handler.py # 主动对话处理
│   │   └── media_handler.py     # 媒体处理
│   │
│   ├── platforms/               # 平台适配器
│   │   ├── base.py              # 抽象基类
│   │   ├── windows.py           # Windows 适配
│   │   ├── macos.py             # macOS 适配
│   │   └── linux.py             # Linux 适配
│   │
│   ├── services/                # 服务层
│   │   ├── desktop_monitor.py   # 桌面监控
│   │   ├── screen_capture.py    # 屏幕捕获
│   │   ├── chat_history.py      # 聊天历史
│   │   └── proactive_dialog.py  # 主动对话
│   │
│   ├── controllers/             # 控制器
│   │   └── settings_controller.py
│   │
│   └── utils/                   # 工具类
│       └── autostart.py         # 开机自启
│
├── tests/                       # 测试目录
│   ├── conftest.py
│   ├── test_config.py
│   ├── test_bridge.py
│   └── test_platforms.py
│
├── docs/                        # 文档目录
│   └── ARCHITECTURE.md          # 架构文档
│
├── .github/                     # GitHub 配置
│   ├── ISSUE_TEMPLATE/
│   └── PULL_REQUEST_TEMPLATE.md
│
├── requirements.txt             # 项目依赖
├── pyproject.toml               # 项目配置
├── CONTRIBUTING.md              # 贡献指南（本文件）
├── LICENSE                      # 许可证
└── README.md                    # 项目说明
```

详细架构说明请参阅 [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)。

---

## 获取帮助

如果你在贡献过程中遇到问题，可以：

- 📖 查阅 [项目文档](docs/)
- 💬 在 [Issue](https://github.com/muyouzhi6/Astrbot-desktop-assistant/issues) 中提问
- 🔍 搜索已有的 Issue 和 PR

### 常见问题

**Q: 如何在 Windows 上设置开发环境？**

```bash
# 确保 Python 3.9+ 已安装
python --version

# 创建虚拟环境
python -m venv venv
venv\Scripts\activate

# 安装依赖
pip install -r requirements.txt
pip install pywin32  # Windows 专用
```

**Q: 测试运行失败怎么办？**

```bash
# 确保在项目根目录
cd Astrbot-desktop-assistant

# 确保虚拟环境已激活
# 重新安装依赖
pip install -r requirements.txt

# 运行测试并显示详细信息
pytest -v --tb=long
```

**Q: 如何调试 GUI 相关问题？**

```bash
# 启用详细日志
python -m desktop_client --debug

# 或设置环境变量
set ASTRBOT_DEBUG=1  # Windows
export ASTRBOT_DEBUG=1  # Linux/macOS
```

---

## 致谢

感谢所有为本项目做出贡献的开发者！🎉

你的每一份贡献都让这个项目变得更好。

---

*最后更新：2024 年 12 月*