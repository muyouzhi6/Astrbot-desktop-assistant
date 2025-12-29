"""
屏幕捕获服务

提供全屏截图、区域截图、窗口截图等功能。
"""

import os
import time
from typing import Optional, Tuple, Callable
from io import BytesIO

try:
    import mss
    import mss.tools

    HAS_MSS = True
except ImportError:
    HAS_MSS = False

try:
    from PIL import Image

    HAS_PIL = True
except ImportError:
    HAS_PIL = False


class ScreenCaptureService:
    """屏幕捕获服务"""

    def __init__(self, save_dir: str = "./temp/screenshots"):
        """
        初始化屏幕捕获服务

        Args:
            save_dir: 截图保存目录
        """
        self.save_dir = save_dir
        os.makedirs(save_dir, exist_ok=True)

        if not HAS_MSS:
            print("警告: mss 库未安装，截图功能不可用")
        if not HAS_PIL:
            print("警告: Pillow 库未安装，截图功能不可用")

    def capture_full_screen(self) -> Optional[Image.Image]:
        """
        捕获全屏

        Returns:
            PIL Image 对象，失败返回 None
        """
        if not HAS_MSS or not HAS_PIL:
            return None

        try:
            with mss.mss() as sct:
                # 获取所有显示器的组合
                monitor = sct.monitors[0]  # 0 是所有显示器的组合
                screenshot = sct.grab(monitor)
                return Image.frombytes(
                    "RGB", screenshot.size, screenshot.bgra, "raw", "BGRX"
                )
        except Exception as e:
            print(f"全屏截图失败: {e}")
            return None

    def capture_monitor(self, monitor_index: int = 1) -> Optional[Image.Image]:
        """
        捕获指定显示器

        Args:
            monitor_index: 显示器索引，从 1 开始

        Returns:
            PIL Image 对象，失败返回 None
        """
        if not HAS_MSS or not HAS_PIL:
            return None

        try:
            with mss.mss() as sct:
                if monitor_index < 1 or monitor_index >= len(sct.monitors):
                    print(f"显示器索引 {monitor_index} 无效")
                    return None
                monitor = sct.monitors[monitor_index]
                screenshot = sct.grab(monitor)
                return Image.frombytes(
                    "RGB", screenshot.size, screenshot.bgra, "raw", "BGRX"
                )
        except Exception as e:
            print(f"显示器截图失败: {e}")
            return None

    def capture_region(
        self, left: int, top: int, width: int, height: int
    ) -> Optional[Image.Image]:
        """
        捕获指定区域

        Args:
            left: 左边界
            top: 上边界
            width: 宽度
            height: 高度

        Returns:
            PIL Image 对象，失败返回 None
        """
        if not HAS_MSS or not HAS_PIL:
            return None

        try:
            with mss.mss() as sct:
                region = {"left": left, "top": top, "width": width, "height": height}
                screenshot = sct.grab(region)
                return Image.frombytes(
                    "RGB", screenshot.size, screenshot.bgra, "raw", "BGRX"
                )
        except Exception as e:
            print(f"区域截图失败: {e}")
            return None

    def capture_full_screen_to_file(
        self, filename: Optional[str] = None
    ) -> Optional[str]:
        """
        捕获全屏并保存到文件

        Args:
            filename: 文件名，不指定则自动生成

        Returns:
            保存的文件路径，失败返回 None
        """
        image = self.capture_full_screen()
        if image is None:
            return None

        if filename is None:
            filename = f"screenshot_{int(time.time() * 1000)}.png"

        filepath = os.path.join(self.save_dir, filename)

        try:
            image.save(filepath, "PNG")
            return filepath
        except Exception as e:
            print(f"保存截图失败: {e}")
            return None

    def capture_to_bytes(self, image: Optional[Image.Image] = None) -> Optional[bytes]:
        """
        将截图转换为字节数据

        Args:
            image: PIL Image 对象，不指定则捕获全屏

        Returns:
            PNG 格式的字节数据，失败返回 None
        """
        if image is None:
            image = self.capture_full_screen()
        if image is None:
            return None

        try:
            buffer = BytesIO()
            image.save(buffer, format="PNG")
            return buffer.getvalue()
        except Exception as e:
            print(f"转换截图失败: {e}")
            return None

    def get_screen_size(self) -> Tuple[int, int]:
        """
        获取主屏幕大小

        Returns:
            (宽度, 高度) 元组
        """
        if not HAS_MSS:
            return (1920, 1080)

        try:
            with mss.mss() as sct:
                monitor = sct.monitors[1]  # 主显示器
                return (monitor["width"], monitor["height"])
        except Exception:
            return (1920, 1080)  # 默认值

    def get_monitors_info(self) -> list:
        """
        获取所有显示器信息

        Returns:
            显示器信息列表
        """
        if not HAS_MSS:
            return []

        try:
            with mss.mss() as sct:
                return [
                    {
                        "index": i,
                        "left": m["left"],
                        "top": m["top"],
                        "width": m["width"],
                        "height": m["height"],
                    }
                    for i, m in enumerate(sct.monitors)
                ]
        except Exception as e:
            print(f"获取显示器信息失败: {e}")
            return []

    def capture_region_to_file(
        self,
        left: int,
        top: int,
        width: int,
        height: int,
        filename: Optional[str] = None,
    ) -> Optional[str]:
        """
        捕获指定区域并保存到文件

        Args:
            left: 左边界
            top: 上边界
            width: 宽度
            height: 高度
            filename: 文件名，不指定则自动生成

        Returns:
            保存的文件路径，失败返回 None
        """
        image = self.capture_region(left, top, width, height)
        if image is None:
            return None

        if filename is None:
            filename = f"region_{int(time.time() * 1000)}.png"

        filepath = os.path.join(self.save_dir, filename)

        try:
            image.save(filepath, "PNG")
            return filepath
        except Exception as e:
            print(f"保存区域截图失败: {e}")
            return None

    def start_region_capture(
        self,
        on_complete: Optional[Callable[[Optional[str]], None]] = None,
        on_cancel: Optional[Callable[[], None]] = None,
    ):
        """
        启动交互式区域截图选择

        需要在 Qt 事件循环中调用此方法。

        Args:
            on_complete: 完成回调，参数为截图文件路径
            on_cancel: 取消回调，无参数
        """
        try:
            from ..gui.screenshot_selector import RegionScreenshotCapture

            capture = RegionScreenshotCapture(self.save_dir)
            capture.capture_async(
                on_complete=lambda path: on_complete(path) if on_complete else None
            )
        except ImportError as e:
            print(f"无法启动区域截图: {e}")
            if on_cancel:
                on_cancel()
