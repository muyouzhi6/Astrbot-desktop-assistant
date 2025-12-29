"""
示例插件

这是一个完整的示例插件，演示如何：
1. 创建插件类并继承 IPlugin
2. 定义插件元数据
3. 实现生命周期方法
4. 注册和使用钩子
5. 管理插件配置

你可以将此文件复制到 plugins/installed/ 目录作为开发新插件的模板。
"""

import logging
from datetime import datetime
from typing import Any, Dict

from .base import IPlugin, PluginMetadata
from .hooks import (
    HookType,
    HookPriority,
    HookContext,
    HookResult,
)


# 配置日志
logger = logging.getLogger(__name__)


class ExamplePlugin(IPlugin):
    """
    示例插件

    这个插件展示了插件系统的所有核心功能：

    功能说明:
        1. 消息增强 - 在发送消息前添加时间戳前缀
        2. 消息统计 - 统计发送和接收的消息数量
        3. 截图通知 - 在截图完成后显示通知
        4. 连接状态追踪 - 记录连接和断开事件

    使用方法:
        1. 将此文件复制到 plugins/installed/ 目录
        2. 重启应用或使用热加载
        3. 在插件管理器中启用此插件

    配置选项:
        - add_timestamp: bool - 是否在消息前添加时间戳
        - timestamp_format: str - 时间戳格式
        - log_messages: bool - 是否记录消息日志
    """

    def __init__(self):
        """初始化插件"""
        super().__init__()

        # 统计数据
        self._message_count = {
            "sent": 0,
            "received": 0,
        }
        self._screenshot_count = 0
        self._connection_events: list = []

    # ==================== 元数据 ====================

    @property
    def metadata(self) -> PluginMetadata:
        """
        返回插件元数据

        元数据用于描述插件的基本信息，包括：
        - name: 插件唯一标识符（必须唯一）
        - version: 版本号（建议遵循语义化版本）
        - author: 作者信息
        - description: 功能描述
        - tags: 分类标签
        """
        return PluginMetadata(
            name="example_plugin",
            version="1.0.0",
            author="AstrBot Desktop Team",
            description="示例插件，演示插件系统的核心功能",
            homepage="https://github.com/Soulter/AstrBot",
            dependencies=[],  # 无依赖
            tags=["示例", "教程", "基础"],
        )

    # ==================== 生命周期方法 ====================

    def on_load(self) -> bool:
        """
        插件加载时调用

        在此方法中执行初始化逻辑：
        - 加载配置
        - 注册钩子
        - 初始化资源

        Returns:
            bool: 返回 True 表示加载成功，False 将阻止插件加载
        """
        logger.info(f"[{self.name}] 插件加载中...")

        # 加载配置
        self.load_config()

        # 设置默认配置
        if "add_timestamp" not in self.config:
            self.set_config_value("add_timestamp", True)
        if "timestamp_format" not in self.config:
            self.set_config_value("timestamp_format", "[%H:%M:%S]")
        if "log_messages" not in self.config:
            self.set_config_value("log_messages", False)

        # 手动注册钩子（也可以使用 @hook 装饰器）
        self.register_hook(
            HookType.PRE_MESSAGE_SEND, self._on_pre_message_send, HookPriority.NORMAL
        )

        self.register_hook(
            HookType.POST_MESSAGE_RECEIVE,
            self._on_post_message_receive,
            HookPriority.NORMAL,
        )

        self.register_hook(
            HookType.POST_SCREENSHOT, self._on_post_screenshot, HookPriority.LOW
        )

        logger.info(f"[{self.name}] 插件加载完成")
        return True

    def on_unload(self) -> None:
        """
        插件卸载时调用

        在此方法中执行清理逻辑：
        - 保存配置
        - 释放资源
        - 注销钩子（基类会自动处理）
        """
        logger.info(f"[{self.name}] 插件卸载中...")

        # 保存配置
        self.save_config()

        # 记录统计信息
        logger.info(
            f"[{self.name}] 统计: "
            f"发送消息 {self._message_count['sent']} 条, "
            f"接收消息 {self._message_count['received']} 条, "
            f"截图 {self._screenshot_count} 次"
        )

        # 调用父类方法（会自动注销钩子）
        super().on_unload()

        logger.info(f"[{self.name}] 插件卸载完成")

    def on_enable(self) -> bool:
        """
        插件启用时调用

        在此方法中激活插件功能。

        Returns:
            bool: 返回 True 表示启用成功
        """
        logger.info(f"[{self.name}] 插件已启用")
        return True

    def on_disable(self) -> None:
        """
        插件禁用时调用

        在此方法中暂停插件功能，但不释放资源。
        """
        logger.info(f"[{self.name}] 插件已禁用")

    # ==================== 钩子处理方法 ====================

    async def _on_pre_message_send(self, context: HookContext) -> HookResult:
        """
        消息发送前的钩子处理

        这个方法展示如何：
        - 读取上下文数据
        - 修改上下文数据
        - 返回适当的结果

        Args:
            context: 钩子上下文，包含消息数据

        Returns:
            HookResult: 处理结果
        """
        # 获取原始消息
        message = context.get("message", "")

        # 检查是否启用时间戳
        if self.get_config_value("add_timestamp", True):
            # 添加时间戳前缀
            timestamp_format = self.get_config_value("timestamp_format", "[%H:%M:%S]")
            timestamp = datetime.now().strftime(timestamp_format)

            # 修改消息（这会影响实际发送的内容）
            context.set("message", f"{timestamp} {message}")

            logger.debug(f"[{self.name}] 添加时间戳: {timestamp}")

        # 更新统计
        self._message_count["sent"] += 1

        # 可选：记录消息日志
        if self.get_config_value("log_messages", False):
            logger.info(f"[{self.name}] 发送消息: {message[:50]}...")

        # 返回 MODIFIED 表示数据已被修改
        return HookResult.MODIFIED

    async def _on_post_message_receive(self, context: HookContext) -> HookResult:
        """
        消息接收后的钩子处理

        Args:
            context: 钩子上下文

        Returns:
            HookResult: 处理结果
        """
        # 更新统计
        self._message_count["received"] += 1

        # 获取消息内容
        message = context.get("message", "")
        msg_type = context.get("msg_type", "text")

        # 可选：记录消息日志
        if self.get_config_value("log_messages", False):
            logger.info(
                f"[{self.name}] 收到消息 (类型={msg_type}): "
                f"{message[:50] if isinstance(message, str) else '<非文本>'}..."
            )

        # 继续执行后续钩子
        return HookResult.CONTINUE

    async def _on_post_screenshot(self, context: HookContext) -> HookResult:
        """
        截图完成后的钩子处理

        Args:
            context: 钩子上下文

        Returns:
            HookResult: 处理结果
        """
        # 更新统计
        self._screenshot_count += 1

        # 获取截图信息
        image_path = context.get("image_path", "")
        success = context.get("success", False)
        mode = context.get("mode", "unknown")

        if success:
            logger.info(
                f"[{self.name}] 截图完成 (第 {self._screenshot_count} 次): "
                f"模式={mode}, 路径={image_path}"
            )
        else:
            logger.warning(f"[{self.name}] 截图失败: 模式={mode}")

        return HookResult.CONTINUE

    # ==================== 使用 @hook 装饰器的示例 ====================

    # 注意：使用装饰器注册的钩子会在 on_load 时自动注册
    # 下面是装饰器的使用示例（已注释，避免重复注册）

    # @hook(HookType.ON_CONNECT, HookPriority.NORMAL)
    # async def on_connect(self, context: HookContext) -> HookResult:
    #     """连接建立时的处理"""
    #     server_url = context.get("server_url", "")
    #     connected_at = context.get("connected_at", "")
    #
    #     self._connection_events.append({
    #         "type": "connect",
    #         "server": server_url,
    #         "time": connected_at,
    #     })
    #
    #     logger.info(f"[{self.name}] 已连接到服务器: {server_url}")
    #     return HookResult.CONTINUE

    # @hook(HookType.ON_DISCONNECT, HookPriority.NORMAL)
    # async def on_disconnect(self, context: HookContext) -> HookResult:
    #     """连接断开时的处理"""
    #     reason = context.get("reason", "unknown")
    #
    #     self._connection_events.append({
    #         "type": "disconnect",
    #         "reason": reason,
    #         "time": datetime.now().isoformat(),
    #     })
    #
    #     logger.info(f"[{self.name}] 连接已断开: {reason}")
    #     return HookResult.CONTINUE

    # ==================== 公共方法 ====================

    def get_statistics(self) -> Dict[str, Any]:
        """
        获取插件统计信息

        这是一个公共方法，可以被其他组件调用。

        Returns:
            Dict[str, Any]: 统计信息字典
        """
        return {
            "messages": self._message_count.copy(),
            "screenshots": self._screenshot_count,
            "connection_events": len(self._connection_events),
        }

    def reset_statistics(self) -> None:
        """重置统计信息"""
        self._message_count = {"sent": 0, "received": 0}
        self._screenshot_count = 0
        self._connection_events.clear()
        logger.info(f"[{self.name}] 统计信息已重置")


# ==================== 插件工厂函数（可选） ====================


def create_plugin() -> IPlugin:
    """
    插件工厂函数

    这是一个可选的工厂函数，可以用于创建插件实例。
    插件管理器会优先查找 IPlugin 的子类，如果找不到则查找此函数。

    Returns:
        IPlugin: 插件实例
    """
    return ExamplePlugin()


# ==================== 开发说明 ====================

"""
插件开发指南:

1. 创建插件文件
   - 在 plugins/installed/ 目录下创建 .py 文件
   - 或创建目录，包含 __init__.py

2. 定义插件类
   - 继承 IPlugin 基类
   - 实现 metadata 属性（必需）
   - 实现生命周期方法（可选）

3. 注册钩子
   方式一：在 on_load 中手动注册
   ```python
   def on_load(self) -> bool:
       self.register_hook(HookType.PRE_MESSAGE_SEND, self._handler)
       return True
   ```
   
   方式二：使用 @hook 装饰器
   ```python
   @hook(HookType.PRE_MESSAGE_SEND, HookPriority.HIGH)
   async def _handler(self, context: HookContext) -> HookResult:
       return HookResult.CONTINUE
   ```

4. 处理配置
   ```python
   # 加载配置
   self.load_config()
   
   # 读取配置值
   value = self.get_config_value("key", default_value)
   
   # 设置配置值
   self.set_config_value("key", new_value)
   
   # 保存配置
   self.save_config()
   ```

5. 钩子返回值
   - HookResult.CONTINUE: 继续执行后续钩子和原始操作
   - HookResult.ABORT: 中止后续钩子和原始操作
   - HookResult.SKIP: 跳过后续钩子，继续原始操作
   - HookResult.MODIFIED: 表示数据已修改，继续执行

6. 可用钩子类型
   - PRE_MESSAGE_SEND / POST_MESSAGE_SEND
   - PRE_MESSAGE_RECEIVE / POST_MESSAGE_RECEIVE
   - PRE_SCREENSHOT / POST_SCREENSHOT / ON_SCREENSHOT_ANALYSIS
   - ON_CONNECT / ON_DISCONNECT / ON_RECONNECT
   - ON_PROACTIVE_TRIGGER / ON_PROACTIVE_MESSAGE
   - ON_THEME_CHANGE / ON_WINDOW_STATE_CHANGE
   - ON_APP_START / ON_APP_SHUTDOWN
   - CUSTOM

7. 最佳实践
   - 始终在 on_unload 中清理资源
   - 使用 logger 记录日志而非 print
   - 钩子回调应尽量轻量，避免阻塞
   - 配置应有合理的默认值
   - 处理所有可能的异常
"""
