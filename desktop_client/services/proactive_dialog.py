"""
主动对话服务

实现智能触发机制，包括用户活跃检测、时间段限制、概率判断等。
"""

import os
import random
import ctypes
import logging
from datetime import datetime, time as dt_time
from typing import Optional

try:
    from PySide6.QtCore import QObject, Signal, QTimer

    HAS_PYSIDE6 = True
except ImportError:
    try:
        from PyQt6.QtCore import QObject, pyqtSignal as Signal, QTimer

        HAS_PYSIDE6 = False
    except ImportError:
        HAS_PYSIDE6 = None

try:
    from PIL import Image

    HAS_PIL = True
except ImportError:
    HAS_PIL = False

from .screen_capture import ScreenCaptureService
from ..config import ProactiveDialogConfig


# 配置日志
logger = logging.getLogger(__name__)


# Windows API 结构体定义
class LASTINPUTINFO(ctypes.Structure):
    """Windows LASTINPUTINFO 结构体"""

    _fields_ = [
        ("cbSize", ctypes.c_uint),
        ("dwTime", ctypes.c_uint),
    ]


class ProactiveDialogService(QObject):
    """
    主动对话服务

    管理主动对话的触发逻辑，包括：
    - 定时检测机制
    - 用户活跃检测
    - 时间段限制
    - 概率触发判断
    - 截图压缩
    """

    # 信号：触发对话，参数为截图路径
    dialog_triggered = Signal(str)

    def __init__(
        self,
        config: Optional[ProactiveDialogConfig] = None,
        screenshot_dir: str = "./temp/screenshots",
        parent: Optional[QObject] = None,
    ):
        """
        初始化主动对话服务

        Args:
            config: 主动对话配置，不指定则使用默认配置
            screenshot_dir: 截图保存目录
            parent: 父对象
        """
        super().__init__(parent)

        self._config = config or ProactiveDialogConfig()
        self._screenshot_dir = screenshot_dir
        self._is_running = False

        # 创建截图服务
        self._screen_capture = ScreenCaptureService(save_dir=screenshot_dir)

        # 创建定时器
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._on_timer_tick)

        # 确保截图目录存在
        os.makedirs(screenshot_dir, exist_ok=True)

        logger.info("ProactiveDialogService 初始化完成")

    @property
    def is_running(self) -> bool:
        """服务是否正在运行"""
        return self._is_running

    @property
    def config(self) -> ProactiveDialogConfig:
        """获取当前配置"""
        return self._config

    def start(self) -> bool:
        """
        启动服务

        Returns:
            是否成功启动
        """
        if self._is_running:
            logger.warning("服务已在运行中")
            return False

        if not self._config.enabled:
            logger.info("主动对话功能未启用")
            return False

        # 设置定时器间隔（配置中是秒，QTimer需要毫秒）
        interval_ms = self._config.check_interval * 1000
        self._timer.start(interval_ms)
        self._is_running = True

        logger.info(f"主动对话服务已启动，检测间隔: {self._config.check_interval}秒")
        return True

    def stop(self):
        """停止服务"""
        if not self._is_running:
            return

        self._timer.stop()
        self._is_running = False

        logger.info("主动对话服务已停止")

    def update_config(self, config: ProactiveDialogConfig):
        """
        更新配置（运行时）

        Args:
            config: 新的配置
        """
        was_running = self._is_running

        # 如果正在运行，先停止
        if was_running:
            self.stop()

        self._config = config
        logger.info("主动对话配置已更新")

        # 如果之前在运行且新配置启用，重新启动
        if was_running and config.enabled:
            self.start()

    def _on_timer_tick(self):
        """定时器触发回调"""
        try:
            self._check_and_trigger()
        except Exception as e:
            logger.error(f"定时检测时发生错误: {e}")

    def _check_and_trigger(self):
        """检查条件并触发对话"""
        # 检查是否启用
        if not self._config.enabled:
            logger.debug("主动对话未启用，跳过检测")
            return

        # 检查时间段限制
        if not self._check_time_range():
            logger.debug("当前时间不在允许的时间段内，跳过检测")
            return

        # 检查用户活跃状态
        if self._config.require_user_active and not self._check_user_active():
            logger.debug("用户不活跃，跳过检测")
            return

        # 检查概率触发
        if not self._check_probability():
            logger.debug("概率检测未通过，跳过触发")
            return

        # 所有条件满足，进行截图并触发对话
        logger.info("所有条件满足，准备触发主动对话")
        self._capture_and_trigger()

    def _check_time_range(self) -> bool:
        """
        检查当前时间是否在允许的时间段内

        Returns:
            是否在允许的时间段内
        """
        if not self._config.time_range_enabled:
            return True

        try:
            now = datetime.now().time()

            # 解析开始和结束时间
            start_parts = self._config.time_range_start.split(":")
            end_parts = self._config.time_range_end.split(":")

            start_time = dt_time(int(start_parts[0]), int(start_parts[1]))
            end_time = dt_time(int(end_parts[0]), int(end_parts[1]))

            # 检查是否在时间范围内
            if start_time <= end_time:
                # 正常情况：如 09:00 - 22:00
                return start_time <= now <= end_time
            else:
                # 跨夜情况：如 22:00 - 06:00
                return now >= start_time or now <= end_time

        except Exception as e:
            logger.error(f"解析时间范围失败: {e}")
            return True  # 解析失败时默认允许

    def _check_user_active(self) -> bool:
        """
        检查用户是否活跃（通过检测空闲时间）

        Returns:
            用户是否活跃
        """
        try:
            idle_seconds = self._get_idle_time()
            is_active = idle_seconds < self._config.idle_threshold

            logger.debug(
                f"用户空闲时间: {idle_seconds}秒，阈值: {self._config.idle_threshold}秒，活跃: {is_active}"
            )

            return is_active

        except Exception as e:
            logger.error(f"检测用户活跃状态失败: {e}")
            return True  # 检测失败时默认认为活跃

    def _get_idle_time(self) -> float:
        """
        获取用户空闲时间（秒）

        使用 Windows API GetLastInputInfo 获取最后一次输入时间

        Returns:
            空闲时间（秒）
        """
        try:
            # 创建 LASTINPUTINFO 结构体
            lii = LASTINPUTINFO()
            lii.cbSize = ctypes.sizeof(LASTINPUTINFO)

            # 调用 GetLastInputInfo
            if ctypes.windll.user32.GetLastInputInfo(ctypes.byref(lii)):
                # 获取当前 tick count
                current_tick = ctypes.windll.kernel32.GetTickCount()

                # 计算空闲时间（毫秒转秒）
                idle_ms = current_tick - lii.dwTime

                # 处理 tick count 溢出情况
                if idle_ms < 0:
                    idle_ms += 0xFFFFFFFF

                return idle_ms / 1000.0
            else:
                logger.warning("GetLastInputInfo 调用失败")
                return 0.0

        except Exception as e:
            logger.error(f"获取空闲时间失败: {e}")
            return 0.0

    def _check_probability(self) -> bool:
        """
        检查概率触发

        Returns:
            是否通过概率检测
        """
        probability = self._config.trigger_probability
        roll = random.random()
        passed = roll < probability

        logger.debug(f"概率检测: 随机值={roll:.4f}, 阈值={probability}, 通过={passed}")

        return passed

    def _capture_and_trigger(self):
        """截图并触发对话"""
        try:
            # 捕获全屏
            image = self._screen_capture.capture_full_screen()

            if image is None:
                logger.error("截图失败")
                return

            # 压缩图片
            compressed_image = self._compress_image(image)

            if compressed_image is None:
                logger.error("图片压缩失败")
                return

            # 保存到文件
            filename = f"proactive_{int(datetime.now().timestamp() * 1000)}.jpg"
            filepath = os.path.join(self._screenshot_dir, filename)

            # 保存为 JPEG 格式（更小的文件大小）
            compressed_image.save(filepath, "JPEG", quality=85)

            logger.info(f"主动对话截图已保存: {filepath}")

            # 发射信号
            self.dialog_triggered.emit(filepath)

        except Exception as e:
            logger.error(f"截图并触发对话失败: {e}")

    def _compress_image(self, image: "Image.Image") -> Optional["Image.Image"]:
        """
        压缩图片到配置的尺寸

        Args:
            image: 原始 PIL Image 对象

        Returns:
            压缩后的 Image 对象，失败返回 None
        """
        if not HAS_PIL:
            logger.error("Pillow 库未安装，无法压缩图片")
            return None

        try:
            target_width = self._config.screenshot_width
            target_height = self._config.screenshot_height

            # 获取原始尺寸
            orig_width, orig_height = image.size

            # 计算缩放比例（保持宽高比）
            width_ratio = target_width / orig_width
            height_ratio = target_height / orig_height
            ratio = min(width_ratio, height_ratio)

            # 如果图片已经小于目标尺寸，不需要压缩
            if ratio >= 1:
                logger.debug("图片尺寸已小于目标尺寸，无需压缩")
                return image

            # 计算新尺寸
            new_width = int(orig_width * ratio)
            new_height = int(orig_height * ratio)

            # 使用高质量缩放
            compressed = image.resize((new_width, new_height), Image.Resampling.LANCZOS)

            logger.debug(
                f"图片已压缩: {orig_width}x{orig_height} -> {new_width}x{new_height}"
            )

            return compressed

        except Exception as e:
            logger.error(f"压缩图片失败: {e}")
            return None

    def trigger_manually(self) -> bool:
        """
        手动触发一次主动对话（用于测试）

        Returns:
            是否成功触发
        """
        try:
            logger.info("手动触发主动对话")
            self._capture_and_trigger()
            return True
        except Exception as e:
            logger.error(f"手动触发失败: {e}")
            return False

    def get_status(self) -> dict:
        """
        获取服务状态

        Returns:
            状态信息字典
        """
        idle_time = 0.0
        try:
            idle_time = self._get_idle_time()
        except Exception:
            pass

        return {
            "is_running": self._is_running,
            "enabled": self._config.enabled,
            "check_interval": self._config.check_interval,
            "trigger_probability": self._config.trigger_probability,
            "require_user_active": self._config.require_user_active,
            "idle_threshold": self._config.idle_threshold,
            "current_idle_time": idle_time,
            "time_range_enabled": self._config.time_range_enabled,
            "time_range": f"{self._config.time_range_start} - {self._config.time_range_end}",
            "in_time_range": self._check_time_range(),
        }
