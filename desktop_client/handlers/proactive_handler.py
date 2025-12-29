"""
主动对话处理器

负责处理主动对话相关逻辑：
- 触发主动对话
- 发送主动对话消息
- 处理主动对话响应
"""

import asyncio
import logging
from typing import TYPE_CHECKING, Optional, Any

from PySide6.QtCore import QObject, Signal
from qasync import asyncSlot

if TYPE_CHECKING:
    from ..config import ClientConfig
    from ..bridge import MessageBridge

logger = logging.getLogger(__name__)


class ProactiveHandler(QObject):
    """主动对话处理器"""

    # 信号定义
    dialog_started = Signal()  # 主动对话开始
    dialog_completed = Signal()  # 主动对话完成
    dialog_failed = Signal(str)  # 主动对话失败，参数为错误信息

    def __init__(
        self,
        config: "ClientConfig",
        bridge: Optional["MessageBridge"] = None,
        floating_ball: Optional[Any] = None,
        message_handler: Optional[Any] = None,
        parent: Optional[QObject] = None,
    ):
        """
        初始化主动对话处理器

        Args:
            config: 客户端配置
            bridge: 消息桥接实例
            floating_ball: 悬浮球窗口实例
            message_handler: 消息处理器实例
            parent: 父对象
        """
        super().__init__(parent)
        self._config = config
        self._bridge = bridge
        self._floating_ball = floating_ball
        self._message_handler = message_handler

    def set_bridge(self, bridge: "MessageBridge") -> None:
        """设置消息桥接"""
        self._bridge = bridge

    def set_floating_ball(self, floating_ball: Any) -> None:
        """设置悬浮球实例"""
        self._floating_ball = floating_ball

    def set_message_handler(self, handler: Any) -> None:
        """设置消息处理器"""
        self._message_handler = handler

    @asyncSlot(str)
    async def on_proactive_dialog_triggered(self, screenshot_path: str) -> None:
        """
        处理主动对话触发

        当主动对话服务检测到触发条件满足时调用此方法。

        Args:
            screenshot_path: 截图文件路径
        """
        logger.info(f"主动对话触发: {screenshot_path}")
        logger.debug(f"主动对话触发: {screenshot_path}")

        # 检查是否已连接
        if not self._bridge or not self._bridge.is_connected:
            logger.warning("未连接到服务器，跳过主动对话")
            logger.debug("未连接到服务器，跳过主动对话")
            self.dialog_failed.emit("未连接到服务器")
            return

        # 检查是否有有效会话
        if not self._config.session_id:
            logger.warning("没有有效会话，跳过主动对话")
            logger.debug("没有有效会话，跳过主动对话")
            self.dialog_failed.emit("没有有效会话")
            return

        try:
            # 使用配置的提示词模板
            prompt = self._config.proactive.prompt_template

            logger.debug(f"发送主动对话截图: {screenshot_path}")
            logger.debug(f"发送主动对话截图: {screenshot_path}")

            # 标记这是主动对话的消息，用于后续处理响应
            if self._message_handler:
                self._message_handler.set_proactive_pending(True)

            # 发射开始信号
            self.dialog_started.emit()

            # 导入 InputMessage
            from ..bridge import InputMessage

            # 发送图片消息到 AI
            await self._bridge.send_input(
                InputMessage(
                    msg_type="image",
                    content=screenshot_path,
                    session_id=self._config.session_id,
                    metadata={
                        "text": prompt,
                        "proactive": True,  # 标记为主动对话
                    },
                )
            )

        except Exception as e:
            logger.error(f"主动对话发送失败: {e}")
            logger.error(f"主动对话发送失败: {e}")
            if self._message_handler:
                self._message_handler.set_proactive_pending(False)
            self.dialog_failed.emit(str(e))

    def handle_proactive_screenshot_complete(self, screenshot_path: str) -> None:
        """
        处理主动对话截图完成

        Args:
            screenshot_path: 截图路径
        """
        logger.debug(f"主动对话截图完成: {screenshot_path}")

        # 将截图作为用户消息添加到历史记录中（显示在对话框里）
        if self._floating_ball:
            # 使用空文本，只有图片
            self._floating_ball.add_user_message(text="", image_path=screenshot_path)
            # 确保气泡窗口显示
            self._floating_ball.show_input()

        # 触发主动对话
        asyncio.ensure_future(self.on_proactive_dialog_triggered(screenshot_path))
