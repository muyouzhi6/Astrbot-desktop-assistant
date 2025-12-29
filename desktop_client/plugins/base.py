"""
插件基类定义

提供插件系统的核心抽象：
- IPlugin: 插件接口，所有插件必须继承此类
- PluginMetadata: 插件元数据
- PluginState: 插件状态枚举
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from .hooks import HookType, HookPriority
    from .manager import PluginManager


class PluginState(Enum):
    """插件状态枚举"""

    UNLOADED = "unloaded"
    """未加载"""

    LOADED = "loaded"
    """已加载"""

    ENABLED = "enabled"
    """已启用"""

    DISABLED = "disabled"
    """已禁用"""

    ERROR = "error"
    """错误状态"""


@dataclass
class PluginMetadata:
    """
    插件元数据

    描述插件的基本信息，用于插件发现和管理。

    Attributes:
        name: 插件唯一标识符，用于内部引用
        version: 插件版本号，遵循语义化版本规范
        author: 插件作者
        description: 插件功能描述
        homepage: 插件主页或仓库地址
        dependencies: 依赖的其他插件列表
        min_app_version: 最低兼容的应用版本
        max_app_version: 最高兼容的应用版本
        tags: 插件标签，用于分类和搜索
    """

    name: str = field(metadata={"description": "插件唯一标识符"})
    version: str = field(default="1.0.0", metadata={"description": "插件版本号"})
    author: str = field(default="", metadata={"description": "插件作者"})
    description: str = field(default="", metadata={"description": "插件功能描述"})
    homepage: str = field(default="", metadata={"description": "插件主页"})
    dependencies: List[str] = field(
        default_factory=list, metadata={"description": "依赖插件列表"}
    )
    min_app_version: Optional[str] = field(
        default=None, metadata={"description": "最低兼容版本"}
    )
    max_app_version: Optional[str] = field(
        default=None, metadata={"description": "最高兼容版本"}
    )
    tags: List[str] = field(default_factory=list, metadata={"description": "插件标签"})

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "name": self.name,
            "version": self.version,
            "author": self.author,
            "description": self.description,
            "homepage": self.homepage,
            "dependencies": self.dependencies,
            "min_app_version": self.min_app_version,
            "max_app_version": self.max_app_version,
            "tags": self.tags,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PluginMetadata":
        """从字典创建"""
        return cls(
            name=data.get("name", ""),
            version=data.get("version", "1.0.0"),
            author=data.get("author", ""),
            description=data.get("description", ""),
            homepage=data.get("homepage", ""),
            dependencies=data.get("dependencies", []),
            min_app_version=data.get("min_app_version"),
            max_app_version=data.get("max_app_version"),
            tags=data.get("tags", []),
        )


class IPlugin(ABC):
    """
    插件接口抽象基类

    所有插件必须继承此类并实现必要的抽象方法。
    插件通过生命周期方法与应用交互，通过钩子系统扩展功能。

    生命周期:
        1. __init__: 构造函数，初始化插件实例
        2. on_load: 插件加载时调用
        3. on_enable: 插件启用时调用
        4. on_disable: 插件禁用时调用
        5. on_unload: 插件卸载时调用

    Example:
        ```python
        class MyPlugin(IPlugin):
            @property
            def metadata(self) -> PluginMetadata:
                return PluginMetadata(
                    name="my_plugin",
                    version="1.0.0",
                    author="开发者",
                    description="示例插件"
                )

            def on_load(self) -> bool:
                # 注册钩子
                self.register_hook(HookType.PRE_MESSAGE, self._on_pre_message)
                return True

            async def _on_pre_message(self, context: HookContext) -> HookResult:
                # 处理消息前的逻辑
                return HookResult.CONTINUE
        ```
    """

    def __init__(self):
        """初始化插件"""
        self._state: PluginState = PluginState.UNLOADED
        self._manager: Optional["PluginManager"] = None
        self._config: Dict[str, Any] = {}
        self._registered_hooks: List[tuple] = []

    # ==================== 抽象属性 ====================

    @property
    @abstractmethod
    def metadata(self) -> PluginMetadata:
        """
        获取插件元数据

        Returns:
            PluginMetadata: 插件元数据对象
        """
        pass

    # ==================== 便捷属性 ====================

    @property
    def name(self) -> str:
        """获取插件名称"""
        return self.metadata.name

    @property
    def version(self) -> str:
        """获取插件版本"""
        return self.metadata.version

    @property
    def state(self) -> PluginState:
        """获取插件状态"""
        return self._state

    @property
    def is_enabled(self) -> bool:
        """检查插件是否已启用"""
        return self._state == PluginState.ENABLED

    @property
    def config(self) -> Dict[str, Any]:
        """获取插件配置"""
        return self._config

    # ==================== 生命周期方法 ====================

    def on_load(self) -> bool:
        """
        插件加载时调用

        在此方法中执行插件初始化逻辑，如：
        - 注册钩子
        - 加载配置
        - 初始化资源

        Returns:
            bool: 加载是否成功，返回 False 将阻止插件加载
        """
        return True

    def on_unload(self) -> None:
        """
        插件卸载时调用

        在此方法中执行清理逻辑，如：
        - 注销钩子
        - 保存配置
        - 释放资源
        """
        # 自动注销所有注册的钩子
        self._unregister_all_hooks()

    def on_enable(self) -> bool:
        """
        插件启用时调用

        在此方法中激活插件功能。

        Returns:
            bool: 启用是否成功
        """
        return True

    def on_disable(self) -> None:
        """
        插件禁用时调用

        在此方法中暂停插件功能，但不释放资源。
        """
        pass

    # ==================== 钩子注册 ====================

    def register_hook(
        self,
        hook_type: "HookType",
        callback: Callable,
        priority: Optional["HookPriority"] = None,
    ) -> bool:
        """
        注册钩子处理函数

        Args:
            hook_type: 钩子类型
            callback: 回调函数，签名为 async def callback(context: HookContext) -> HookResult
            priority: 钩子优先级，默认为 NORMAL

        Returns:
            bool: 注册是否成功
        """
        if self._manager is None:
            return False

        from .hooks import HookPriority

        if priority is None:
            priority = HookPriority.NORMAL

        success = self._manager.register_hook(
            hook_type=hook_type, plugin=self, callback=callback, priority=priority
        )

        if success:
            self._registered_hooks.append((hook_type, callback))

        return success

    def unregister_hook(self, hook_type: "HookType", callback: Callable) -> bool:
        """
        注销钩子处理函数

        Args:
            hook_type: 钩子类型
            callback: 回调函数

        Returns:
            bool: 注销是否成功
        """
        if self._manager is None:
            return False

        success = self._manager.unregister_hook(
            hook_type=hook_type, plugin=self, callback=callback
        )

        if success and (hook_type, callback) in self._registered_hooks:
            self._registered_hooks.remove((hook_type, callback))

        return success

    def _unregister_all_hooks(self) -> None:
        """注销所有已注册的钩子"""
        for hook_type, callback in self._registered_hooks[:]:
            self.unregister_hook(hook_type, callback)
        self._registered_hooks.clear()

    # ==================== 配置管理 ====================

    def load_config(self) -> Dict[str, Any]:
        """
        加载插件配置

        从插件管理器获取持久化的配置。

        Returns:
            Dict[str, Any]: 插件配置字典
        """
        if self._manager is None:
            return {}

        self._config = self._manager.get_plugin_config(self.name)
        return self._config

    def save_config(self) -> bool:
        """
        保存插件配置

        将当前配置持久化到插件管理器。

        Returns:
            bool: 保存是否成功
        """
        if self._manager is None:
            return False

        return self._manager.save_plugin_config(self.name, self._config)

    def get_config_value(self, key: str, default: Any = None) -> Any:
        """
        获取配置值

        Args:
            key: 配置键
            default: 默认值

        Returns:
            Any: 配置值
        """
        return self._config.get(key, default)

    def set_config_value(self, key: str, value: Any) -> None:
        """
        设置配置值

        Args:
            key: 配置键
            value: 配置值
        """
        self._config[key] = value

    # ==================== 内部方法 ====================

    def _set_manager(self, manager: "PluginManager") -> None:
        """设置插件管理器引用（由管理器调用）"""
        self._manager = manager

    def _set_state(self, state: PluginState) -> None:
        """设置插件状态（由管理器调用）"""
        self._state = state

    # ==================== 魔术方法 ====================

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__}({self.name}@{self.version}) state={self.state.value}>"

    def __str__(self) -> str:
        return f"{self.name} v{self.version}"
