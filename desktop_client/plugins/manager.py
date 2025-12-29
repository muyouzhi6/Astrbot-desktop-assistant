"""
插件管理器

负责插件的完整生命周期管理：
- 插件发现与加载
- 插件启用/禁用
- 钩子调度
- 配置管理
"""

import asyncio
import importlib
import importlib.util
import json
import logging
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set, Type

from .base import IPlugin, PluginMetadata, PluginState
from .hooks import HookType, HookPriority, HookContext, HookResult


logger = logging.getLogger(__name__)


@dataclass
class HookRegistration:
    """钩子注册信息"""

    plugin: IPlugin = field(metadata={"description": "插件实例"})
    callback: Callable = field(metadata={"description": "回调函数"})
    priority: HookPriority = field(
        default=HookPriority.NORMAL, metadata={"description": "优先级"}
    )

    @property
    def plugin_name(self) -> str:
        """获取插件名称"""
        return self.plugin.name


@dataclass
class PluginError:
    """插件错误信息"""

    plugin_name: str = field(metadata={"description": "插件名称"})
    error_type: str = field(metadata={"description": "错误类型"})
    message: str = field(metadata={"description": "错误消息"})
    traceback: Optional[str] = field(default=None, metadata={"description": "堆栈跟踪"})

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "plugin_name": self.plugin_name,
            "error_type": self.error_type,
            "message": self.message,
            "traceback": self.traceback,
        }


class PluginManager:
    """
    插件管理器

    管理所有插件的生命周期，包括：
    - 发现和加载插件
    - 启用和禁用插件
    - 钩子注册和调度
    - 插件配置管理

    Example:
        ```python
        manager = PluginManager(plugins_dir="./plugins")

        # 发现并加载所有插件
        await manager.discover_plugins()

        # 启用特定插件
        await manager.enable_plugin("my_plugin")

        # 触发钩子
        context = HookContext(
            hook_type=HookType.PRE_MESSAGE_SEND,
            data={"message": "Hello"}
        )
        await manager.dispatch_hook(context)
        ```
    """

    def __init__(
        self, plugins_dir: Optional[str] = None, config_dir: Optional[str] = None
    ):
        """
        初始化插件管理器

        Args:
            plugins_dir: 插件目录路径
            config_dir: 配置目录路径
        """
        # 目录配置
        if plugins_dir is None:
            plugins_dir = os.path.join(os.path.dirname(__file__), "installed")
        self._plugins_dir = Path(plugins_dir)

        if config_dir is None:
            config_dir = os.path.join(os.path.dirname(__file__), "configs")
        self._config_dir = Path(config_dir)

        # 确保目录存在
        self._plugins_dir.mkdir(parents=True, exist_ok=True)
        self._config_dir.mkdir(parents=True, exist_ok=True)

        # 插件存储
        self._plugins: Dict[str, IPlugin] = {}
        self._plugin_classes: Dict[str, Type[IPlugin]] = {}

        # 钩子注册表
        self._hooks: Dict[HookType, List[HookRegistration]] = {
            hook_type: [] for hook_type in HookType
        }

        # 错误记录
        self._errors: List[PluginError] = []

        # 已启用的插件（用于持久化）
        self._enabled_plugins: Set[str] = set()

        logger.info(f"插件管理器初始化: plugins_dir={self._plugins_dir}")

    # ==================== 属性 ====================

    @property
    def plugins_dir(self) -> Path:
        """获取插件目录"""
        return self._plugins_dir

    @property
    def plugins(self) -> Dict[str, IPlugin]:
        """获取所有已加载的插件"""
        return self._plugins.copy()

    @property
    def enabled_plugins(self) -> List[IPlugin]:
        """获取所有已启用的插件"""
        return [p for p in self._plugins.values() if p.is_enabled]

    @property
    def errors(self) -> List[PluginError]:
        """获取错误列表"""
        return self._errors.copy()

    # ==================== 插件发现与加载 ====================

    async def discover_plugins(self) -> List[str]:
        """
        发现并加载所有插件

        扫描插件目录，加载所有符合规范的插件。

        Returns:
            List[str]: 成功加载的插件名称列表
        """
        loaded = []

        if not self._plugins_dir.exists():
            logger.warning(f"插件目录不存在: {self._plugins_dir}")
            return loaded

        # 扫描插件目录
        for entry in self._plugins_dir.iterdir():
            if entry.is_dir() and not entry.name.startswith("_"):
                # 目录形式的插件
                plugin_file = entry / "__init__.py"
                if plugin_file.exists():
                    result = await self._load_plugin_from_path(entry)
                    if result:
                        loaded.append(result)
            elif (
                entry.is_file()
                and entry.suffix == ".py"
                and not entry.name.startswith("_")
            ):
                # 单文件插件
                result = await self._load_plugin_from_path(entry)
                if result:
                    loaded.append(result)

        logger.info(f"发现并加载了 {len(loaded)} 个插件: {loaded}")
        return loaded

    async def _load_plugin_from_path(self, path: Path) -> Optional[str]:
        """
        从路径加载插件

        Args:
            path: 插件文件或目录路径

        Returns:
            Optional[str]: 成功时返回插件名称，失败返回 None
        """
        try:
            # 确定模块名和文件路径
            if path.is_dir():
                module_name = f"desktop_client.plugins.installed.{path.name}"
                file_path = path / "__init__.py"
            else:
                module_name = f"desktop_client.plugins.installed.{path.stem}"
                file_path = path

            # 动态导入模块
            spec = importlib.util.spec_from_file_location(module_name, file_path)
            if spec is None or spec.loader is None:
                raise ImportError(f"无法加载模块规范: {file_path}")

            module = importlib.util.module_from_spec(spec)
            sys.modules[module_name] = module
            spec.loader.exec_module(module)

            # 查找插件类
            plugin_class = None
            for attr_name in dir(module):
                attr = getattr(module, attr_name)
                if (
                    isinstance(attr, type)
                    and issubclass(attr, IPlugin)
                    and attr is not IPlugin
                ):
                    plugin_class = attr
                    break

            if plugin_class is None:
                logger.warning(f"在 {path} 中未找到插件类")
                return None

            # 实例化插件
            plugin = plugin_class()
            plugin._set_manager(self)

            # 调用 on_load
            if not plugin.on_load():
                logger.warning(f"插件 {plugin.name} 加载失败 (on_load 返回 False)")
                plugin._set_state(PluginState.ERROR)
                return None

            # 注册插件
            self._plugins[plugin.name] = plugin
            self._plugin_classes[plugin.name] = plugin_class
            plugin._set_state(PluginState.LOADED)

            # 自动注册带 @hook 装饰器的方法
            self._auto_register_hooks(plugin)

            logger.info(f"成功加载插件: {plugin.name} v{plugin.version}")
            return plugin.name

        except Exception as e:
            import traceback

            error = PluginError(
                plugin_name=str(path),
                error_type=type(e).__name__,
                message=str(e),
                traceback=traceback.format_exc(),
            )
            self._errors.append(error)
            logger.error(f"加载插件失败 {path}: {e}")
            return None

    def _auto_register_hooks(self, plugin: IPlugin) -> None:
        """自动注册带 @hook 装饰器的方法"""
        for attr_name in dir(plugin):
            if attr_name.startswith("_"):
                continue

            attr = getattr(plugin, attr_name)
            if callable(attr) and hasattr(attr, "_hook_type"):
                hook_type = attr._hook_type
                priority = getattr(attr, "_hook_priority", HookPriority.NORMAL)
                self.register_hook(hook_type, plugin, attr, priority)

    async def load_plugin(self, plugin_class: Type[IPlugin]) -> bool:
        """
        手动加载插件类

        Args:
            plugin_class: 插件类

        Returns:
            bool: 是否成功加载
        """
        try:
            plugin = plugin_class()
            plugin._set_manager(self)

            if not plugin.on_load():
                logger.warning(f"插件 {plugin.name} 加载失败")
                plugin._set_state(PluginState.ERROR)
                return False

            self._plugins[plugin.name] = plugin
            self._plugin_classes[plugin.name] = plugin_class
            plugin._set_state(PluginState.LOADED)

            self._auto_register_hooks(plugin)

            logger.info(f"手动加载插件: {plugin.name}")
            return True

        except Exception as e:
            logger.error(f"手动加载插件失败: {e}")
            return False

    async def unload_plugin(self, plugin_name: str) -> bool:
        """
        卸载插件

        Args:
            plugin_name: 插件名称

        Returns:
            bool: 是否成功卸载
        """
        if plugin_name not in self._plugins:
            logger.warning(f"插件不存在: {plugin_name}")
            return False

        plugin = self._plugins[plugin_name]

        try:
            # 如果已启用，先禁用
            if plugin.is_enabled:
                await self.disable_plugin(plugin_name)

            # 调用 on_unload
            plugin.on_unload()

            # 移除所有钩子
            self._remove_plugin_hooks(plugin)

            # 移除插件
            del self._plugins[plugin_name]
            if plugin_name in self._plugin_classes:
                del self._plugin_classes[plugin_name]

            plugin._set_state(PluginState.UNLOADED)

            logger.info(f"成功卸载插件: {plugin_name}")
            return True

        except Exception as e:
            logger.error(f"卸载插件失败 {plugin_name}: {e}")
            return False

    def _remove_plugin_hooks(self, plugin: IPlugin) -> None:
        """移除插件的所有钩子"""
        for hook_type in HookType:
            self._hooks[hook_type] = [
                reg for reg in self._hooks[hook_type] if reg.plugin is not plugin
            ]

    # ==================== 插件启用/禁用 ====================

    async def enable_plugin(self, plugin_name: str) -> bool:
        """
        启用插件

        Args:
            plugin_name: 插件名称

        Returns:
            bool: 是否成功启用
        """
        if plugin_name not in self._plugins:
            logger.warning(f"插件不存在: {plugin_name}")
            return False

        plugin = self._plugins[plugin_name]

        if plugin.is_enabled:
            logger.debug(f"插件已启用: {plugin_name}")
            return True

        try:
            # 检查依赖
            if not self._check_dependencies(plugin):
                logger.error(f"插件依赖检查失败: {plugin_name}")
                return False

            # 调用 on_enable
            if not plugin.on_enable():
                logger.warning(f"插件启用失败: {plugin_name}")
                return False

            plugin._set_state(PluginState.ENABLED)
            self._enabled_plugins.add(plugin_name)

            logger.info(f"成功启用插件: {plugin_name}")
            return True

        except Exception as e:
            logger.error(f"启用插件失败 {plugin_name}: {e}")
            plugin._set_state(PluginState.ERROR)
            return False

    async def disable_plugin(self, plugin_name: str) -> bool:
        """
        禁用插件

        Args:
            plugin_name: 插件名称

        Returns:
            bool: 是否成功禁用
        """
        if plugin_name not in self._plugins:
            logger.warning(f"插件不存在: {plugin_name}")
            return False

        plugin = self._plugins[plugin_name]

        if not plugin.is_enabled:
            logger.debug(f"插件未启用: {plugin_name}")
            return True

        try:
            # 调用 on_disable
            plugin.on_disable()

            plugin._set_state(PluginState.DISABLED)
            self._enabled_plugins.discard(plugin_name)

            logger.info(f"成功禁用插件: {plugin_name}")
            return True

        except Exception as e:
            logger.error(f"禁用插件失败 {plugin_name}: {e}")
            return False

    def _check_dependencies(self, plugin: IPlugin) -> bool:
        """检查插件依赖"""
        for dep_name in plugin.metadata.dependencies:
            if dep_name not in self._plugins:
                logger.error(f"缺少依赖插件: {dep_name}")
                return False

            dep_plugin = self._plugins[dep_name]
            if not dep_plugin.is_enabled:
                logger.error(f"依赖插件未启用: {dep_name}")
                return False

        return True

    # ==================== 钩子管理 ====================

    def register_hook(
        self,
        hook_type: HookType,
        plugin: IPlugin,
        callback: Callable,
        priority: HookPriority = HookPriority.NORMAL,
    ) -> bool:
        """
        注册钩子

        Args:
            hook_type: 钩子类型
            plugin: 插件实例
            callback: 回调函数
            priority: 优先级

        Returns:
            bool: 是否成功注册
        """
        try:
            registration = HookRegistration(
                plugin=plugin, callback=callback, priority=priority
            )

            # 添加到钩子列表
            self._hooks[hook_type].append(registration)

            # 按优先级排序
            self._hooks[hook_type].sort(key=lambda r: r.priority.value)

            logger.debug(
                f"注册钩子: {hook_type.name} <- {plugin.name} "
                f"(priority={priority.name})"
            )
            return True

        except Exception as e:
            logger.error(f"注册钩子失败: {e}")
            return False

    def unregister_hook(
        self, hook_type: HookType, plugin: IPlugin, callback: Callable
    ) -> bool:
        """
        注销钩子

        Args:
            hook_type: 钩子类型
            plugin: 插件实例
            callback: 回调函数

        Returns:
            bool: 是否成功注销
        """
        try:
            hooks = self._hooks[hook_type]
            for i, reg in enumerate(hooks):
                if reg.plugin is plugin and reg.callback is callback:
                    hooks.pop(i)
                    logger.debug(f"注销钩子: {hook_type.name} <- {plugin.name}")
                    return True

            return False

        except Exception as e:
            logger.error(f"注销钩子失败: {e}")
            return False

    async def dispatch_hook(self, context: HookContext) -> HookContext:
        """
        调度钩子

        按优先级顺序执行所有注册的钩子回调。

        Args:
            context: 钩子上下文

        Returns:
            HookContext: 处理后的上下文
        """
        hook_type = context.hook_type
        registrations = self._hooks.get(hook_type, [])

        if not registrations:
            return context

        logger.debug(f"调度钩子 {hook_type.name}: {len(registrations)} 个回调")

        for reg in registrations:
            # 检查插件是否启用
            if not reg.plugin.is_enabled:
                continue

            # 检查是否已取消
            if context.is_cancelled():
                break

            try:
                # 执行回调
                if asyncio.iscoroutinefunction(reg.callback):
                    result = await reg.callback(context)
                else:
                    result = reg.callback(context)

                # 处理结果
                if result is None:
                    result = HookResult.CONTINUE

                context.add_result(reg.plugin_name, result)

                # 检查是否中止
                if result == HookResult.ABORT:
                    context.cancel()
                    break
                elif result == HookResult.SKIP:
                    break

            except Exception as e:
                logger.error(
                    f"钩子回调执行失败 {reg.plugin_name}.{reg.callback.__name__}: {e}"
                )
                context.add_result(reg.plugin_name, HookResult.CONTINUE)

        return context

    def get_hook_registrations(self, hook_type: HookType) -> List[HookRegistration]:
        """获取指定钩子类型的所有注册"""
        return self._hooks.get(hook_type, []).copy()

    # ==================== 配置管理 ====================

    def get_plugin_config(self, plugin_name: str) -> Dict[str, Any]:
        """
        获取插件配置

        Args:
            plugin_name: 插件名称

        Returns:
            Dict[str, Any]: 插件配置字典
        """
        config_file = self._config_dir / f"{plugin_name}.json"

        if not config_file.exists():
            return {}

        try:
            with open(config_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"读取插件配置失败 {plugin_name}: {e}")
            return {}

    def save_plugin_config(self, plugin_name: str, config: Dict[str, Any]) -> bool:
        """
        保存插件配置

        Args:
            plugin_name: 插件名称
            config: 配置字典

        Returns:
            bool: 是否成功保存
        """
        config_file = self._config_dir / f"{plugin_name}.json"

        try:
            with open(config_file, "w", encoding="utf-8") as f:
                json.dump(config, f, indent=2, ensure_ascii=False)
            return True
        except Exception as e:
            logger.error(f"保存插件配置失败 {plugin_name}: {e}")
            return False

    # ==================== 插件查询 ====================

    def get_plugin(self, plugin_name: str) -> Optional[IPlugin]:
        """获取插件实例"""
        return self._plugins.get(plugin_name)

    def get_plugin_metadata(self, plugin_name: str) -> Optional[PluginMetadata]:
        """获取插件元数据"""
        plugin = self._plugins.get(plugin_name)
        return plugin.metadata if plugin else None

    def list_plugins(self) -> List[Dict[str, Any]]:
        """
        列出所有插件信息

        Returns:
            List[Dict[str, Any]]: 插件信息列表
        """
        result = []
        for plugin in self._plugins.values():
            result.append(
                {
                    "name": plugin.name,
                    "version": plugin.version,
                    "state": plugin.state.value,
                    "metadata": plugin.metadata.to_dict(),
                }
            )
        return result

    def get_plugins_by_state(self, state: PluginState) -> List[IPlugin]:
        """获取指定状态的插件"""
        return [p for p in self._plugins.values() if p.state == state]

    # ==================== 热加载/卸载 ====================

    async def reload_plugin(self, plugin_name: str) -> bool:
        """
        重新加载插件

        用于热更新插件代码。

        Args:
            plugin_name: 插件名称

        Returns:
            bool: 是否成功重载
        """
        if plugin_name not in self._plugins:
            logger.warning(f"插件不存在: {plugin_name}")
            return False

        plugin = self._plugins[plugin_name]
        was_enabled = plugin.is_enabled

        # 获取插件类
        plugin_class = self._plugin_classes.get(plugin_name)
        if plugin_class is None:
            logger.error(f"找不到插件类: {plugin_name}")
            return False

        # 卸载
        if not await self.unload_plugin(plugin_name):
            return False

        # 重新导入模块
        module = sys.modules.get(plugin_class.__module__)
        if module:
            try:
                importlib.reload(module)
                # 重新获取插件类
                for attr_name in dir(module):
                    attr = getattr(module, attr_name)
                    if (
                        isinstance(attr, type)
                        and issubclass(attr, IPlugin)
                        and attr is not IPlugin
                    ):
                        plugin_class = attr
                        break
            except Exception as e:
                logger.error(f"重新导入模块失败: {e}")
                return False

        # 重新加载
        if not await self.load_plugin(plugin_class):
            return False

        # 如果之前是启用的，重新启用
        if was_enabled:
            await self.enable_plugin(plugin_name)

        logger.info(f"成功重载插件: {plugin_name}")
        return True

    # ==================== 生命周期 ====================

    async def start(self) -> None:
        """
        启动插件管理器

        执行插件发现和加载。
        """
        logger.info("启动插件管理器...")

        # 发现插件
        await self.discover_plugins()

        # 加载已启用插件列表
        self._load_enabled_plugins_state()

        # 自动启用之前启用的插件
        for plugin_name in list(self._enabled_plugins):
            if plugin_name in self._plugins:
                await self.enable_plugin(plugin_name)

    async def stop(self) -> None:
        """
        停止插件管理器

        禁用和卸载所有插件。
        """
        logger.info("停止插件管理器...")

        # 保存启用状态
        self._save_enabled_plugins_state()

        # 禁用所有插件
        for plugin_name in list(self._plugins.keys()):
            await self.disable_plugin(plugin_name)

        # 卸载所有插件
        for plugin_name in list(self._plugins.keys()):
            await self.unload_plugin(plugin_name)

    def _load_enabled_plugins_state(self) -> None:
        """加载已启用插件状态"""
        state_file = self._config_dir / "_enabled_plugins.json"

        if not state_file.exists():
            return

        try:
            with open(state_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                self._enabled_plugins = set(data.get("enabled", []))
        except Exception as e:
            logger.error(f"加载启用状态失败: {e}")

    def _save_enabled_plugins_state(self) -> None:
        """保存已启用插件状态"""
        state_file = self._config_dir / "_enabled_plugins.json"

        try:
            with open(state_file, "w", encoding="utf-8") as f:
                json.dump({"enabled": list(self._enabled_plugins)}, f, indent=2)
        except Exception as e:
            logger.error(f"保存启用状态失败: {e}")


# ==================== 全局实例 ====================

_plugin_manager: Optional[PluginManager] = None


def get_plugin_manager() -> PluginManager:
    """
    获取全局插件管理器实例

    Returns:
        PluginManager: 插件管理器实例
    """
    global _plugin_manager
    if _plugin_manager is None:
        _plugin_manager = PluginManager()
    return _plugin_manager


def set_plugin_manager(manager: PluginManager) -> None:
    """
    设置全局插件管理器实例

    Args:
        manager: 插件管理器实例
    """
    global _plugin_manager
    _plugin_manager = manager
