"""
远程命令处理器

处理服务端通过 WebSocket 下发的命令，如截图等。
"""

import asyncio
import base64
import logging
import time
from typing import TYPE_CHECKING, Optional, Dict, Any, Callable

from PySide6.QtCore import QObject, Signal

if TYPE_CHECKING:
    from ..config import ClientConfig
    from ..bridge import MessageBridge

logger = logging.getLogger(__name__)


class RemoteCommandHandler(QObject):
    """
    远程命令处理器

    处理服务端下发的命令，如：
    - screenshot: 截图并返回 base64 编码的图片
    """

    # 信号定义
    command_received = Signal(str, str, dict)  # command, request_id, params
    command_completed = Signal(
        str, str, bool, str
    )  # command, request_id, success, message

    def __init__(
        self,
        config: "ClientConfig",
        bridge: Optional["MessageBridge"] = None,
        parent: Optional[QObject] = None,
    ):
        """
        初始化远程命令处理器

        Args:
            config: 客户端配置
            bridge: 消息桥接器（用于访问 WebSocket 客户端）
            parent: 父对象
        """
        super().__init__(parent)
        self._config = config
        self._bridge = bridge
        self._floating_ball = None

        # 命令处理器映射
        self._command_handlers: Dict[str, Callable] = {
            "screenshot": self._handle_screenshot_command,
        }

    def set_floating_ball(self, floating_ball: Any) -> None:
        """设置悬浮球实例（用于隐藏/显示窗口）"""
        self._floating_ball = floating_ball

    def set_bridge(self, bridge: "MessageBridge") -> None:
        """设置消息桥接器（用于访问 WebSocket 客户端）"""
        self._bridge = bridge

    async def _set_busy_state(
        self, is_busy: bool, operation: str = "", duration: int = 60
    ) -> None:
        """
        设置忙碌状态，通知服务端延长超时时间

        Args:
            is_busy: 是否进入忙碌状态
            operation: 操作名称
            duration: 预计操作持续时间（秒）
        """
        try:
            if self._bridge and self._bridge.api_client.ws_client:
                ws_client = self._bridge.api_client.ws_client
                if ws_client.is_connected:
                    await ws_client.set_busy_state(is_busy, operation, duration)
                else:
                    logger.warning("WebSocket 未连接，无法报告忙碌状态")
            else:
                logger.warning("Bridge 或 WebSocket 客户端未设置，无法报告忙碌状态")
        except Exception as e:
            logger.error(f"设置忙碌状态失败: {e}")

    async def handle_command(
        self, command: str, request_id: str, params: dict
    ) -> Dict[str, Any]:
        """
        处理远程命令

        Args:
            command: 命令名称
            request_id: 请求 ID
            params: 命令参数

        Returns:
            命令执行结果字典
        """
        logger.info(f"处理远程命令: {command}, request_id={request_id}")
        self.command_received.emit(command, request_id, params)

        handler = self._command_handlers.get(command)

        if handler is None:
            error_msg = f"未知命令: {command}"
            logger.warning(error_msg)
            self.command_completed.emit(command, request_id, False, error_msg)
            return {"success": False, "error_message": error_msg}

        try:
            result = await handler(request_id, params)
            success = result.get("success", False)
            message = result.get("error_message", "") if not success else "成功"
            self.command_completed.emit(command, request_id, success, message)
            return result
        except Exception as e:
            error_msg = f"命令执行异常: {str(e)}"
            logger.error(error_msg, exc_info=True)
            self.command_completed.emit(command, request_id, False, error_msg)
            return {"success": False, "error_message": error_msg}

    async def _handle_screenshot_command(
        self, request_id: str, params: dict
    ) -> Dict[str, Any]:
        """
        处理截图命令

        Args:
            request_id: 请求 ID
            params: 命令参数
                - type: 截图类型 ("full" 或 "region")

        Returns:
            包含截图结果的字典
        """
        screenshot_type = params.get("type", "full")

        logger.info(f"执行远程截图: type={screenshot_type}, request_id={request_id}")

        # 报告忙碌状态，通知服务端延长超时（截图+编码+传输预计需要30-60秒）
        await self._set_busy_state(True, "screenshot", 60)

        try:
            # 导入截图服务
            from ..services.screen_capture import ScreenCaptureService

            # 隐藏悬浮球窗口（避免截到自己）
            if self._floating_ball:
                self._floating_ball.hide()

            # 等待窗口隐藏
            await asyncio.sleep(0.15)

            # 执行截图
            save_dir = self._config.storage.image_save_path or "./temp/screenshots"
            service = ScreenCaptureService(save_dir=save_dir)

            if screenshot_type == "full":
                image = service.capture_full_screen()
            else:
                # 区域截图暂不支持远程触发（需要用户交互）
                image = service.capture_full_screen()

            # 恢复窗口
            if self._floating_ball:
                self._floating_ball.show()

            if image is None:
                return {"success": False, "error_message": "截图失败：无法捕获屏幕"}

            # 将图片转换为 base64
            image_bytes = service.capture_to_bytes(image)

            if image_bytes is None:
                return {"success": False, "error_message": "截图失败：无法编码图片"}

            image_base64 = base64.b64encode(image_bytes).decode("utf-8")

            logger.info(
                f"远程截图成功: size={len(image_bytes)} bytes, "
                f"resolution={image.width}x{image.height}"
            )

            return {
                "success": True,
                "image_base64": image_base64,
                "width": image.width,
                "height": image.height,
                "timestamp": time.time(),
            }

        except ImportError as e:
            error_msg = f"截图服务不可用: {str(e)}"
            logger.error(error_msg)
            return {"success": False, "error_message": error_msg}
        except Exception as e:
            error_msg = f"截图异常: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return {"success": False, "error_message": error_msg}
        finally:
            # 确保窗口恢复
            if self._floating_ball:
                self._floating_ball.show()

            # 退出忙碌状态
            await self._set_busy_state(False, "screenshot")

    def register_command(self, command: str, handler: Callable) -> None:
        """
        注册自定义命令处理器

        Args:
            command: 命令名称
            handler: 处理函数，签名: async (request_id, params) -> dict
        """
        self._command_handlers[command] = handler
        logger.info(f"已注册远程命令处理器: {command}")

    def unregister_command(self, command: str) -> None:
        """
        注销命令处理器

        Args:
            command: 命令名称
        """
        if command in self._command_handlers:
            del self._command_handlers[command]
            logger.info(f"已注销远程命令处理器: {command}")

    @property
    def supported_commands(self) -> list:
        """获取支持的命令列表"""
        return list(self._command_handlers.keys())
