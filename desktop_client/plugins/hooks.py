"""
钩子系统定义

提供插件扩展点的核心机制：
- HookType: 钩子类型枚举，定义所有可用的扩展点
- HookPriority: 钩子优先级，控制执行顺序
- HookContext: 钩子上下文，传递数据给回调函数
- HookResult: 钩子执行结果，控制后续处理流程
"""

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Dict, Optional


class HookType(Enum):
    """
    钩子类型枚举

    定义插件系统中所有可用的扩展点。
    插件可以注册这些钩子来扩展或修改应用行为。
    """

    # ==================== 消息相关钩子 ====================

    PRE_MESSAGE_SEND = auto()
    """
    消息发送前
    
    在用户消息发送到服务器前触发。
    可用于：消息过滤、内容修改、发送拦截。
    
    Context data:
        - message: str - 原始消息内容
        - session_id: str - 会话ID
        - metadata: dict - 消息元数据
    
    修改 context.data["message"] 可改变发送内容。
    返回 HookResult.ABORT 可阻止消息发送。
    """

    POST_MESSAGE_SEND = auto()
    """
    消息发送后
    
    在用户消息成功发送到服务器后触发。
    可用于：消息日志、统计、触发附加操作。
    
    Context data:
        - message: str - 发送的消息内容
        - session_id: str - 会话ID
        - success: bool - 发送是否成功
    """

    PRE_MESSAGE_RECEIVE = auto()
    """
    消息接收前（预处理）
    
    在服务器响应消息被处理前触发。
    可用于：响应过滤、内容预处理。
    
    Context data:
        - message: str - 原始响应内容
        - msg_type: str - 消息类型
        - metadata: dict - 消息元数据
    
    修改 context.data["message"] 可改变显示内容。
    返回 HookResult.ABORT 可阻止消息显示。
    """

    POST_MESSAGE_RECEIVE = auto()
    """
    消息接收后（后处理）
    
    在服务器响应消息被显示后触发。
    可用于：消息日志、触发后续操作、自动回复。
    
    Context data:
        - message: str - 响应内容
        - msg_type: str - 消息类型
        - displayed: bool - 是否已显示
    """

    # ==================== 截图相关钩子 ====================

    PRE_SCREENSHOT = auto()
    """
    截图前
    
    在截图操作执行前触发。
    可用于：准备截图环境、隐藏敏感内容。
    
    Context data:
        - mode: str - 截图模式 ("full" | "region")
        - source: str - 触发来源 ("hotkey" | "button" | "proactive")
    
    返回 HookResult.ABORT 可阻止截图。
    """

    POST_SCREENSHOT = auto()
    """
    截图后
    
    在截图操作完成后触发。
    可用于：图片处理、自动分析、保存到其他位置。
    
    Context data:
        - image_path: str - 截图保存路径
        - mode: str - 截图模式
        - success: bool - 截图是否成功
        - image_data: bytes - 图片二进制数据（可选）
    """

    ON_SCREENSHOT_ANALYSIS = auto()
    """
    截图分析时
    
    在截图被发送进行 AI 分析时触发。
    可用于：添加额外上下文、修改分析请求。
    
    Context data:
        - image_path: str - 截图路径
        - prompt: str - 分析提示词
        - context: dict - 桌面上下文信息
    
    修改 context.data["prompt"] 可改变分析请求。
    """

    # ==================== 连接相关钩子 ====================

    ON_CONNECT = auto()
    """
    连接建立时
    
    在与服务器建立连接后触发。
    可用于：初始化同步、发送问候消息。
    
    Context data:
        - server_url: str - 服务器地址
        - connected_at: str - 连接时间 (ISO 8601)
    """

    ON_DISCONNECT = auto()
    """
    连接断开时
    
    在与服务器断开连接后触发。
    可用于：清理资源、保存状态、显示通知。
    
    Context data:
        - reason: str - 断开原因
        - was_clean: bool - 是否正常断开
        - reconnecting: bool - 是否将自动重连
    """

    ON_RECONNECT = auto()
    """
    重新连接时
    
    在自动重连尝试时触发。
    可用于：记录重连、修改重连策略。
    
    Context data:
        - attempt: int - 重连尝试次数
        - max_attempts: int - 最大重连次数
        - interval: float - 重连间隔（秒）
    """

    # ==================== 主动对话钩子 ====================

    ON_PROACTIVE_TRIGGER = auto()
    """
    主动对话触发时
    
    在主动对话条件满足时触发。
    可用于：自定义触发条件、修改触发行为。
    
    Context data:
        - trigger_type: str - 触发类型
        - idle_time: float - 空闲时间（秒）
        - last_activity: str - 最后活动时间
    
    返回 HookResult.ABORT 可阻止此次主动对话。
    """

    ON_PROACTIVE_MESSAGE = auto()
    """
    主动对话消息生成时
    
    在主动对话消息生成后、发送前触发。
    可用于：修改消息内容、添加上下文。
    
    Context data:
        - message: str - 生成的消息
        - context: dict - 桌面上下文
        - screenshot_path: str - 截图路径（如有）
    
    修改 context.data["message"] 可改变发送内容。
    """

    # ==================== UI 相关钩子 ====================

    ON_THEME_CHANGE = auto()
    """
    主题切换时
    
    在应用主题切换时触发。
    可用于：同步插件 UI、保存主题偏好。
    
    Context data:
        - old_theme: str - 旧主题名称
        - new_theme: str - 新主题名称
        - colors: dict - 主题颜色配置
    """

    ON_WINDOW_STATE_CHANGE = auto()
    """
    窗口状态变化时
    
    在主要窗口状态变化时触发。
    可用于：响应窗口显示/隐藏、调整行为。
    
    Context data:
        - window: str - 窗口名称 ("floating_ball" | "chat" | "settings")
        - state: str - 窗口状态 ("show" | "hide" | "minimize" | "maximize")
    """

    # ==================== 生命周期钩子 ====================

    ON_APP_START = auto()
    """
    应用启动时
    
    在应用完成初始化后触发。
    可用于：执行启动任务、显示欢迎消息。
    
    Context data:
        - version: str - 应用版本
        - config: dict - 应用配置摘要
    """

    ON_APP_SHUTDOWN = auto()
    """
    应用关闭时
    
    在应用开始关闭流程时触发。
    可用于：保存数据、清理资源。
    
    Context data:
        - reason: str - 关闭原因 ("user" | "error" | "restart")
    """

    # ==================== 自定义钩子 ====================

    CUSTOM = auto()
    """
    自定义钩子
    
    用于插件之间的通信或自定义扩展点。
    
    Context data:
        - event_name: str - 自定义事件名称
        - data: Any - 自定义数据
    """


class HookPriority(Enum):
    """
    钩子优先级

    控制同一钩子类型下多个回调的执行顺序。
    数值越小，优先级越高，越先执行。
    """

    HIGHEST = 0
    """最高优先级 - 系统级处理"""

    HIGH = 25
    """高优先级 - 优先执行"""

    NORMAL = 50
    """正常优先级 - 默认值"""

    LOW = 75
    """低优先级 - 后执行"""

    LOWEST = 100
    """最低优先级 - 最后执行"""

    MONITOR = 999
    """监控优先级 - 仅用于记录，不应修改数据"""


class HookResult(Enum):
    """
    钩子执行结果

    控制钩子链的执行流程。
    """

    CONTINUE = auto()
    """
    继续执行
    
    继续执行后续钩子和原始操作。
    这是默认返回值。
    """

    ABORT = auto()
    """
    中止执行
    
    中止后续钩子和原始操作。
    用于阻止某个操作发生。
    """

    SKIP = auto()
    """
    跳过后续钩子
    
    跳过后续钩子但继续原始操作。
    用于短路钩子链。
    """

    MODIFIED = auto()
    """
    数据已修改
    
    表示钩子修改了上下文数据。
    继续执行后续钩子和原始操作。
    """


@dataclass
class HookContext:
    """
    钩子上下文

    在钩子回调之间传递数据。
    钩子可以读取和修改 data 字典中的内容。

    Attributes:
        hook_type: 当前钩子类型
        data: 钩子数据字典，包含与钩子相关的所有信息
        source_plugin: 触发此钩子的插件名称（如适用）
        cancelled: 钩子链是否已被取消
        results: 各插件的执行结果

    Example:
        ```python
        async def on_pre_message(context: HookContext) -> HookResult:
            # 读取数据
            message = context.data.get("message", "")

            # 修改数据
            context.data["message"] = message.upper()

            # 添加自定义数据
            context.set("my_plugin_processed", True)

            return HookResult.MODIFIED
        ```
    """

    hook_type: HookType = field(metadata={"description": "钩子类型"})
    data: Dict[str, Any] = field(
        default_factory=dict, metadata={"description": "钩子数据"}
    )
    source_plugin: Optional[str] = field(
        default=None, metadata={"description": "触发源插件"}
    )
    cancelled: bool = field(default=False, metadata={"description": "是否已取消"})
    results: Dict[str, HookResult] = field(
        default_factory=dict, metadata={"description": "各插件执行结果"}
    )

    def get(self, key: str, default: Any = None) -> Any:
        """
        获取数据值

        Args:
            key: 数据键
            default: 默认值

        Returns:
            Any: 数据值
        """
        return self.data.get(key, default)

    def set(self, key: str, value: Any) -> None:
        """
        设置数据值

        Args:
            key: 数据键
            value: 数据值
        """
        self.data[key] = value

    def cancel(self) -> None:
        """取消钩子链执行"""
        self.cancelled = True

    def is_cancelled(self) -> bool:
        """检查是否已取消"""
        return self.cancelled

    def add_result(self, plugin_name: str, result: HookResult) -> None:
        """
        添加插件执行结果

        Args:
            plugin_name: 插件名称
            result: 执行结果
        """
        self.results[plugin_name] = result

    def has_modifications(self) -> bool:
        """检查是否有数据被修改"""
        return HookResult.MODIFIED in self.results.values()

    def was_aborted(self) -> bool:
        """检查是否被中止"""
        return HookResult.ABORT in self.results.values() or self.cancelled

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "hook_type": self.hook_type.name,
            "data": self.data,
            "source_plugin": self.source_plugin,
            "cancelled": self.cancelled,
            "results": {k: v.name for k, v in self.results.items()},
        }

    def __repr__(self) -> str:
        return f"<HookContext({self.hook_type.name}) cancelled={self.cancelled}>"


# ==================== 钩子装饰器 ====================


def hook(hook_type: HookType, priority: HookPriority = HookPriority.NORMAL):
    """
    钩子装饰器

    用于标记方法为钩子处理函数，便于自动注册。

    Args:
        hook_type: 钩子类型
        priority: 钩子优先级

    Example:
        ```python
        class MyPlugin(IPlugin):
            @hook(HookType.PRE_MESSAGE_SEND, HookPriority.HIGH)
            async def on_pre_message(self, context: HookContext) -> HookResult:
                # 处理逻辑
                return HookResult.CONTINUE
        ```
    """

    def decorator(func):
        func._hook_type = hook_type
        func._hook_priority = priority
        return func

    return decorator


# ==================== 钩子工具函数 ====================


def create_context(hook_type: HookType, **data) -> HookContext:
    """
    创建钩子上下文

    便捷函数，用于创建预填充数据的上下文。

    Args:
        hook_type: 钩子类型
        **data: 上下文数据

    Returns:
        HookContext: 钩子上下文对象

    Example:
        ```python
        context = create_context(
            HookType.PRE_MESSAGE_SEND,
            message="Hello",
            session_id="123"
        )
        ```
    """
    return HookContext(hook_type=hook_type, data=data)


def get_hook_description(hook_type: HookType) -> str:
    """
    获取钩子类型描述

    Args:
        hook_type: 钩子类型

    Returns:
        str: 钩子描述
    """
    descriptions = {
        HookType.PRE_MESSAGE_SEND: "消息发送前",
        HookType.POST_MESSAGE_SEND: "消息发送后",
        HookType.PRE_MESSAGE_RECEIVE: "消息接收前",
        HookType.POST_MESSAGE_RECEIVE: "消息接收后",
        HookType.PRE_SCREENSHOT: "截图前",
        HookType.POST_SCREENSHOT: "截图后",
        HookType.ON_SCREENSHOT_ANALYSIS: "截图分析时",
        HookType.ON_CONNECT: "连接建立时",
        HookType.ON_DISCONNECT: "连接断开时",
        HookType.ON_RECONNECT: "重新连接时",
        HookType.ON_PROACTIVE_TRIGGER: "主动对话触发时",
        HookType.ON_PROACTIVE_MESSAGE: "主动对话消息生成时",
        HookType.ON_THEME_CHANGE: "主题切换时",
        HookType.ON_WINDOW_STATE_CHANGE: "窗口状态变化时",
        HookType.ON_APP_START: "应用启动时",
        HookType.ON_APP_SHUTDOWN: "应用关闭时",
        HookType.CUSTOM: "自定义事件",
    }
    return descriptions.get(hook_type, hook_type.name)
