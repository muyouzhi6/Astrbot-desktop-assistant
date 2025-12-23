# AstrBot Desktop Client

AstrBot 桌面助手客户端，提供悬浮球界面和桌面监控功能。

## 功能特性

### 核心功能

- **悬浮球界面**: 可拖动的悬浮球，快速访问 AI 助手
- **聊天窗口**: 支持 Markdown 渲染、代码高亮的对话界面
- **屏幕截图**: 全屏截图和区域截图功能
- **WebSocket 通信**: 与 AstrBot 服务端实时双向通信

### 桌面监控（新增）

- **活动窗口检测**: 实时监控当前活动窗口和进程
- **状态上报**: 通过 WebSocket 定期上报桌面状态至服务端
- **跨平台支持**: 支持 Windows、macOS 和 Linux

## 项目结构

```
desktop_client/
├── __init__.py          # 包初始化
├── __main__.py          # 入口点
├── app.py               # 应用主类
├── api_client.py        # HTTP/WebSocket API 客户端
├── config.py            # 配置管理
├── gui/                 # GUI 组件
│   ├── floating_ball.py # 悬浮球
│   ├── chat_widgets.py  # 聊天组件
│   └── ...
└── services/            # 服务层
    ├── screen_capture.py    # 屏幕捕获
    ├── desktop_monitor.py   # 桌面监控（新增）
    ├── chat_history.py      # 聊天历史
    └── proactive_dialog.py  # 主动对话
```

## 安装依赖

```bash
pip install -r requirements.txt

# Windows 用户如需窗口信息检测，额外安装：
pip install pywin32
```

## 运行

```bash
python -m desktop_client
# 或
python main.py
```

## 桌面监控模块

### DesktopMonitorService

客户端桌面监控服务，负责收集本地桌面状态并上报至服务端。

```python
from services import DesktopMonitorService, ScreenCaptureService

# 初始化
screen_capture = ScreenCaptureService()
monitor = DesktopMonitorService(
    screen_capture_service=screen_capture,
    report_interval=60,  # 上报间隔（秒）
    screenshot_enabled=True,
    screenshot_width=800,
    screenshot_height=600,
    on_state_captured=handle_state,  # 状态捕获回调
)

# 启动
await monitor.start()

# 手动捕获
state = await monitor.capture_state()
print(f"当前窗口: {state.active_window_title}")
print(f"进程: {state.active_window_process}")
```

### DesktopState 数据结构

```python
@dataclass
class DesktopState:
    timestamp: str                    # ISO 格式时间戳
    active_window_title: str          # 活动窗口标题
    active_window_process: str        # 进程名
    active_window_pid: int            # 进程 ID
    screenshot_base64: str            # Base64 编码的截图
    screenshot_width: int             # 截图宽度
    screenshot_height: int            # 截图高度
    running_apps: list                # 运行中的应用列表
    window_changed: bool              # 窗口是否变化
    previous_window_title: str        # 上一个窗口标题
```

### WebSocket 上报格式

```json
{
    "type": "desktop_state",
    "data": {
        "timestamp": "2024-01-01T12:00:00",
        "active_window_title": "Visual Studio Code",
        "active_window_process": "Code.exe",
        "active_window_pid": 12345,
        "screenshot_base64": "iVBORw0KGgo...",
        "running_apps": [
            {"pid": 12345, "name": "Code.exe"},
            {"pid": 67890, "name": "chrome.exe"}
        ],
        "window_changed": true,
        "previous_window_title": "Chrome"
    }
}
```

## 配置说明

配置文件位于：
- Windows: `%APPDATA%/AstrBotDesktopClient/config.json`
- Linux/macOS: `~/.config/astrbot-desktop-client/config.json`

### 主动对话配置

```json
{
    "proactive": {
        "enabled": true,
        "check_interval": 600,
        "trigger_probability": 0.2,
        "screenshot_width": 800,
        "screenshot_height": 600
    }
}
```

## 许可证

MIT License