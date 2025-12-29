"""
AstrBot 桌面助手独立客户端

一个独立运行的桌面悬浮球助手，通过 HTTP API 连接远程 AstrBot 服务器。

主要组件:
- AstrBotApiClient: HTTP API 客户端，处理与服务器的通信
- MessageBridge: 消息桥接器，管理 GUI 和 API 之间的消息传递
- DesktopAssistantClient: 应用主类，管理整个应用生命周期
- ClientConfig: 客户端配置管理

使用示例:
    from desktop_client import DesktopAssistantClient

    client = DesktopAssistantClient()
    client.run()
"""

__version__ = "1.0.0"
__author__ = "AstrBot Team"

from .config import (
    ClientConfig,
    ServerConfig,
    AppearanceConfig,
    ChatWindowConfig,
    VoiceConfig,
)
from .api_client import (
    AstrBotApiClient,
    ConnectionState,
    SSEEvent,
)
from .bridge import (
    MessageBridge,
    InputMessage,
    OutputMessage,
)


# 延迟导入应用类（避免循环导入）
def get_app_class():
    """获取应用主类"""
    from .app import DesktopClientApp

    return DesktopClientApp


__all__ = [
    # 版本信息
    "__version__",
    "__author__",
    # 配置
    "ClientConfig",
    "ServerConfig",
    "AppearanceConfig",
    "ChatWindowConfig",
    "VoiceConfig",
    # API 客户端
    "AstrBotApiClient",
    "ConnectionState",
    "SSEEvent",
    # 消息桥接
    "MessageBridge",
    "InputMessage",
    "OutputMessage",
    # 应用
    "get_app_class",
]
