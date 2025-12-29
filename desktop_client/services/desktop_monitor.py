"""
客户端桌面监控服务

负责收集本地桌面状态（活动窗口、截图等）并通过 WebSocket 上报给服务端。
使用平台适配器实现跨平台功能。
"""

import asyncio
import base64
from dataclasses import dataclass, asdict
from datetime import datetime
from io import BytesIO
from typing import Any, Callable, List, Optional

# 可选依赖
try:
    from PIL import Image

    HAS_PIL = True
except ImportError:
    HAS_PIL = False

# 导入平台适配器
from ..platforms import get_platform_adapter, IPlatformAdapter


@dataclass
class DesktopState:
    """桌面状态数据结构"""

    # 时间戳
    timestamp: str
    # 活动窗口标题
    active_window_title: Optional[str] = None
    # 活动窗口进程名
    active_window_process: Optional[str] = None
    # 活动窗口进程 ID
    active_window_pid: Optional[int] = None
    # 屏幕截图（Base64 编码的 PNG）
    screenshot_base64: Optional[str] = None
    # 截图宽度
    screenshot_width: Optional[int] = None
    # 截图高度
    screenshot_height: Optional[int] = None
    # 运行中的应用列表
    running_apps: Optional[List[dict]] = None
    # 窗口是否发生变化
    window_changed: bool = False
    # 上一个窗口标题
    previous_window_title: Optional[str] = None

    def to_dict(self) -> dict:
        """转换为字典"""
        return asdict(self)


class DesktopMonitorService:
    """客户端桌面监控服务"""

    def __init__(
        self,
        screen_capture_service: Optional[Any] = None,
        report_interval: int = 60,
        screenshot_enabled: bool = True,
        screenshot_width: int = 800,
        screenshot_height: int = 600,
        on_state_captured: Optional[Callable[[DesktopState], Any]] = None,
    ):
        """
        初始化桌面监控服务

        Args:
            screen_capture_service: 截图服务实例
            report_interval: 上报间隔（秒）
            screenshot_enabled: 是否启用截图
            screenshot_width: 截图压缩宽度
            screenshot_height: 截图压缩高度
            on_state_captured: 状态捕获回调
        """
        self.screen_capture = screen_capture_service
        self.report_interval = report_interval
        self.screenshot_enabled = screenshot_enabled
        self.screenshot_width = screenshot_width
        self.screenshot_height = screenshot_height
        self.on_state_captured = on_state_captured

        self._is_monitoring = False
        self._monitor_task: Optional[asyncio.Task] = None
        self._last_window_title: Optional[str] = None
        self._last_state: Optional[DesktopState] = None

        # 获取平台适配器
        self._platform: IPlatformAdapter = get_platform_adapter()

    @property
    def is_monitoring(self) -> bool:
        """是否正在监控"""
        return self._is_monitoring

    @property
    def last_state(self) -> Optional[DesktopState]:
        """获取最后捕获的状态"""
        return self._last_state

    async def start(self):
        """启动监控"""
        if self._is_monitoring:
            return

        self._is_monitoring = True
        self._monitor_task = asyncio.create_task(self._monitor_loop())
        print(f"桌面监控服务已启动 (平台: {self._platform.platform_name})")

    async def stop(self):
        """停止监控"""
        self._is_monitoring = False

        if self._monitor_task:
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass
            self._monitor_task = None

        print("桌面监控服务已停止")

    async def _monitor_loop(self):
        """监控循环"""
        while self._is_monitoring:
            try:
                # 捕获状态
                state = await self.capture_state()

                if state and self.on_state_captured:
                    # 调用回调
                    result = self.on_state_captured(state)
                    if asyncio.iscoroutine(result):
                        await result

                # 等待下一次采集
                await asyncio.sleep(self.report_interval)

            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"桌面监控错误: {e}")
                await asyncio.sleep(5)  # 错误后短暂等待

    async def capture_state(
        self, include_screenshot: bool = True
    ) -> Optional[DesktopState]:
        """
        捕获当前桌面状态

        Args:
            include_screenshot: 是否包含截图

        Returns:
            DesktopState 对象
        """
        try:
            # 使用平台适配器获取活动窗口信息
            window_info = self._platform.get_active_window()

            # 检测窗口变化
            current_title = window_info.title
            window_changed = current_title != self._last_window_title
            previous_title = self._last_window_title if window_changed else None
            self._last_window_title = current_title

            # 创建状态对象
            state = DesktopState(
                timestamp=datetime.now().isoformat(),
                active_window_title=window_info.title,
                active_window_process=window_info.process,
                active_window_pid=window_info.pid,
                window_changed=window_changed,
                previous_window_title=previous_title,
            )

            # 使用平台适配器获取运行中的应用列表
            apps = self._platform.get_running_apps()
            state.running_apps = [app.to_dict() for app in apps]

            # 捕获截图
            if include_screenshot and self.screenshot_enabled and self.screen_capture:
                screenshot_data = await self._capture_screenshot()
                if screenshot_data:
                    state.screenshot_base64 = screenshot_data["base64"]
                    state.screenshot_width = screenshot_data["width"]
                    state.screenshot_height = screenshot_data["height"]

            self._last_state = state
            return state

        except Exception as e:
            print(f"捕获桌面状态失败: {e}")
            return None

    async def _capture_screenshot(self) -> Optional[dict]:
        """捕获并压缩截图"""
        if not self.screen_capture or not HAS_PIL:
            return None

        try:
            # 使用 screen_capture 服务捕获全屏
            image = self.screen_capture.capture_full_screen()
            if image is None:
                return None

            # 压缩图片
            image = self._resize_image(
                image, self.screenshot_width, self.screenshot_height
            )

            # 转换为 Base64
            buffer = BytesIO()
            image.save(buffer, format="PNG", optimize=True)
            base64_data = base64.b64encode(buffer.getvalue()).decode("utf-8")

            return {
                "base64": base64_data,
                "width": image.width,
                "height": image.height,
            }

        except Exception as e:
            print(f"截图失败: {e}")
            return None

    def _resize_image(
        self, image: "Image.Image", max_width: int, max_height: int
    ) -> "Image.Image":
        """调整图片大小"""
        # 计算缩放比例
        ratio = min(max_width / image.width, max_height / image.height)

        if ratio < 1:
            new_width = int(image.width * ratio)
            new_height = int(image.height * ratio)
            return image.resize((new_width, new_height), Image.Resampling.LANCZOS)

        return image

    async def capture_and_report(self) -> Optional[DesktopState]:
        """立即捕获并触发上报"""
        state = await self.capture_state()

        if state and self.on_state_captured:
            result = self.on_state_captured(state)
            if asyncio.iscoroutine(result):
                await result

        return state
