"""
截图处理器

负责处理各类截图操作：
- 区域截图
- 全屏截图
- 主动对话截图
"""

import logging
from typing import TYPE_CHECKING, Optional, Any

from PySide6.QtCore import QObject, QTimer, Signal

if TYPE_CHECKING:
    from ..config import ClientConfig

logger = logging.getLogger(__name__)


class ScreenshotHandler(QObject):
    """截图处理器 - 处理截图相关逻辑"""

    # 信号定义
    screenshot_completed = Signal(str)  # 截图完成，参数为截图路径
    proactive_screenshot_completed = Signal(str)  # 主动对话截图完成

    def __init__(
        self,
        config: "ClientConfig",
        floating_ball: Optional[Any] = None,
        parent: Optional[QObject] = None,
    ):
        """
        初始化截图处理器

        Args:
            config: 客户端配置
            floating_ball: 悬浮球窗口实例
            parent: 父对象
        """
        super().__init__(parent)
        self._config = config
        self._floating_ball = floating_ball
        self._capture = None  # 区域截图捕获对象

    def set_floating_ball(self, floating_ball: Any) -> None:
        """设置悬浮球实例"""
        self._floating_ball = floating_ball

    def on_screenshot(self, screenshot_type: str) -> None:
        """
        处理截图请求

        Args:
            screenshot_type: 截图类型 ("region" 或 "full")
        """
        if screenshot_type == "region":
            self.do_region_screenshot()
        else:
            self.do_full_screenshot()

    def do_region_screenshot(self) -> None:
        """区域截图"""
        try:

            # 隐藏窗口
            if self._floating_ball:
                self._floating_ball.hide()

            # 使用 QTimer 确保窗口隐藏后再截图
            QTimer.singleShot(100, self._start_region_capture)
        except ImportError as e:
            logger.error(f"区域截图不可用: {e}")
            logger.error(f"区域截图不可用: {e}")

    def _start_region_capture(self) -> None:
        """开始区域截图"""
        try:
            from ..gui.screenshot_selector import RegionScreenshotCapture

            self._capture = RegionScreenshotCapture()
            self._capture.capture_async(self._on_screenshot_complete)
        except Exception as e:
            logger.error(f"启动截图失败: {e}")
            logger.error(f"启动截图失败: {e}")
            self._restore_windows()

    def do_full_screenshot(self) -> None:
        """全屏截图"""
        try:

            # 隐藏窗口
            if self._floating_ball:
                self._floating_ball.hide()

            QTimer.singleShot(100, self._execute_full_screenshot)
        except ImportError as e:
            logger.error(f"截图服务不可用: {e}")
            logger.error(f"截图服务不可用: {e}")

    def _execute_full_screenshot(self) -> None:
        """执行全屏截图"""
        try:
            from ..services.screen_capture import ScreenCaptureService

            # 使用配置的存储路径
            save_dir = self._config.storage.image_save_path or "./temp/screenshots"
            service = ScreenCaptureService(save_dir=save_dir)
            screenshot_path = service.capture_full_screen_to_file()

            self._restore_windows()

            if screenshot_path:
                self._handle_screenshot_result(screenshot_path)
        except Exception as e:
            logger.error(f"截图失败: {e}")
            logger.error(f"截图失败: {e}")
            self._restore_windows()

    def do_proactive_screenshot(self) -> None:
        """执行主动对话专用截图"""
        try:

            # 隐藏窗口
            if self._floating_ball:
                self._floating_ball.hide()

            # 延迟执行以确保窗口完全隐藏
            QTimer.singleShot(100, self._execute_proactive_screenshot)
        except ImportError as e:
            logger.error(f"截图服务不可用: {e}")
            logger.error(f"截图服务不可用: {e}")

    def _execute_proactive_screenshot(self) -> None:
        """执行主动对话截图"""
        try:
            from ..services.screen_capture import ScreenCaptureService

            # 使用配置的存储路径
            save_dir = self._config.storage.image_save_path or "./temp/screenshots"
            service = ScreenCaptureService(save_dir=save_dir)
            screenshot_path = service.capture_full_screen_to_file()

            self._restore_windows()

            if screenshot_path:
                self._on_proactive_screenshot_complete(screenshot_path)
        except Exception as e:
            logger.error(f"主动对话截图失败: {e}")
            logger.error(f"主动对话截图失败: {e}")
            self._restore_windows()

    def _on_proactive_screenshot_complete(self, screenshot_path: str) -> None:
        """主动对话截图完成"""
        logger.debug(f"主动对话截图完成: {screenshot_path}")
        logger.debug(f"主动对话截图完成: {screenshot_path}")

        # 发射信号
        self.proactive_screenshot_completed.emit(screenshot_path)

    def _on_screenshot_complete(self, screenshot_path: Optional[str]) -> None:
        """截图完成回调"""
        self._restore_windows()

        if screenshot_path:
            self._handle_screenshot_result(screenshot_path)

    def _restore_windows(self) -> None:
        """恢复窗口显示"""
        if self._floating_ball:
            self._floating_ball.show()

    def _handle_screenshot_result(self, screenshot_path: str) -> None:
        """处理截图结果"""
        # 粘贴到气泡输入框
        if self._floating_ball:
            self._floating_ball.set_attachment(screenshot_path)
            self._floating_ball.show_input()

        # 发射信号
        self.screenshot_completed.emit(screenshot_path)

    def add_screenshot_to_chat(self, screenshot_path: str) -> None:
        """添加截图到对话（旧方法保留兼容）"""
        self._handle_screenshot_result(screenshot_path)
