"""
截图处理器

负责处理各类截图操作：
- 区域截图
- 全屏截图
- 主动对话截图
"""

import logging
from typing import TYPE_CHECKING, Optional, Any

from PySide6.QtCore import QObject, QTimer, Signal, QPoint
from PySide6.QtWidgets import QApplication

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
        
        # 保存窗口原始位置
        self._ball_pos: Optional[QPoint] = None
        self._chat_pos: Optional[QPoint] = None

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
            self._hide_windows()
            # 使用 QTimer 确保窗口隐藏后再截图，增加延迟以确保动画完成和DWM刷新
            QTimer.singleShot(500, self._start_region_capture)
        except ImportError as e:
            logger.error(f"区域截图不可用: {e}")
            self._restore_windows()

    def _start_region_capture(self) -> None:
        """开始区域截图"""
        try:
            from ..gui.screenshot_selector import RegionScreenshotCapture

            self._capture = RegionScreenshotCapture()
            self._capture.capture_async(self._on_screenshot_complete)
        except Exception as e:
            logger.error(f"启动截图失败: {e}")
            self._restore_windows()

    def do_full_screenshot(self) -> None:
        """全屏截图"""
        try:
            self._hide_windows()
            QTimer.singleShot(500, self._execute_full_screenshot)
        except ImportError as e:
            logger.error(f"截图服务不可用: {e}")
            self._restore_windows()

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
            self._restore_windows()

    def do_proactive_screenshot(self) -> None:
        """执行主动对话专用截图"""
        try:
            self._hide_windows()
            # 延迟执行以确保窗口完全隐藏
            QTimer.singleShot(500, self._execute_proactive_screenshot)
        except ImportError as e:
            logger.error(f"截图服务不可用: {e}")
            self._restore_windows()

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
            self._restore_windows()

    def _on_proactive_screenshot_complete(self, screenshot_path: str) -> None:
        """主动对话截图完成"""
        logger.debug(f"主动对话截图完成: {screenshot_path}")

        # 发射信号
        self.proactive_screenshot_completed.emit(screenshot_path)

    def _on_screenshot_complete(self, screenshot_path: Optional[str]) -> None:
        """截图完成回调"""
        self._restore_windows()

        if screenshot_path:
            self._handle_screenshot_result(screenshot_path)

    def _hide_windows(self) -> None:
        """隐藏窗口并记录状态"""
        if self._floating_ball:
            # 记录聊天窗口状态
            self._chat_window_was_visible = self._floating_ball._compact_window.isVisible()
            
            # 记录当前位置
            self._ball_pos = self._floating_ball.pos()
            self._chat_pos = self._floating_ball._compact_window.pos()

            # 多重保险机制：
            # 1. 设置透明度为0
            # 2. 移动到屏幕可视区域外
            # 3. 调用 hide()
            
            self._floating_ball.setWindowOpacity(0)
            self._floating_ball._compact_window.setWindowOpacity(0)
            
            # 移出屏幕 (足够远的位置)
            self._floating_ball.move(-10000, -10000)
            # 由于 FloatingBallWindow 实现了 moveEvent，上面的移动会自动触发 compact_window 的移动
            # 但为了保险起见，我们还是显式移动一次 (如果是隐藏状态 moveEvent 可能不触发)
            self._floating_ball._compact_window.move(-10000, -10000)
            
            # 强制刷新UI事件循环，确保窗口移动被系统处理
            QApplication.processEvents()
            
            # 最后再隐藏 (防止闪烁)
            self._floating_ball._compact_window.hide()
            self._floating_ball.hide()
            
            # 再次刷新
            QApplication.processEvents()

    def _restore_windows(self) -> None:
        """恢复窗口显示"""
        if self._floating_ball:
            # 恢复位置
            if self._ball_pos:
                self._floating_ball.move(self._ball_pos)
            if self._chat_pos:
                self._floating_ball._compact_window.move(self._chat_pos)
                
            # 恢复透明度
            self._floating_ball.setWindowOpacity(1)
            self._floating_ball._compact_window.setWindowOpacity(1)
            
            self._floating_ball.show()
            # 恢复聊天窗口显示状态
            if getattr(self, '_chat_window_was_visible', False):
                self._floating_ball._compact_window.show()

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
