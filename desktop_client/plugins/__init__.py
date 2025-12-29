"""
插件系统模块

提供桌面客户端的扩展能力：
- IPlugin: 插件基类，定义插件接口
- PluginManager: 插件管理器，负责插件生命周期
- Hook: 钩子定义，定义扩展点

使用示例:
    from desktop_client.plugins import IPlugin, PluginManager, HookType

    # 创建自定义插件
    class MyPlugin(IPlugin):
        @property
        def name(self) -> str:
            return "my_plugin"

        def on_load(self) -> bool:
            print("插件加载")
            return True
"""

from .base import IPlugin, PluginMetadata, PluginState
from .hooks import HookType, HookPriority, HookContext, HookResult
from .manager import PluginManager

__all__ = [
    # 基类
    "IPlugin",
    "PluginMetadata",
    "PluginState",
    # 钩子
    "HookType",
    "HookPriority",
    "HookContext",
    "HookResult",
    # 管理器
    "PluginManager",
]
