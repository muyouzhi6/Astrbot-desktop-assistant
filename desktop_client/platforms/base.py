"""
平台适配器抽象基类

定义跨平台功能的统一接口，各平台需实现具体适配器。
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import List, Optional


class ResultStatus(Enum):
    """操作结果状态"""

    SUCCESS = "success"
    FAILED = "failed"
    NOT_SUPPORTED = "not_supported"


@dataclass
class Result:
    """操作结果"""

    status: ResultStatus
    message: str = ""

    @property
    def is_success(self) -> bool:
        """是否成功"""
        return self.status == ResultStatus.SUCCESS

    @classmethod
    def success(cls, message: str = "") -> "Result":
        """创建成功结果"""
        return cls(status=ResultStatus.SUCCESS, message=message)

    @classmethod
    def failed(cls, message: str) -> "Result":
        """创建失败结果"""
        return cls(status=ResultStatus.FAILED, message=message)

    @classmethod
    def not_supported(cls, message: str = "此功能在当前平台不支持") -> "Result":
        """创建不支持结果"""
        return cls(status=ResultStatus.NOT_SUPPORTED, message=message)


@dataclass
class WindowInfo:
    """窗口信息"""

    title: Optional[str] = None
    process: Optional[str] = None
    pid: Optional[int] = None

    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            "title": self.title,
            "process": self.process,
            "pid": self.pid,
        }


@dataclass
class AppInfo:
    """应用信息"""

    pid: int
    name: str

    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            "pid": self.pid,
            "name": self.name,
        }


class IPlatformAdapter(ABC):
    """
    平台适配器抽象基类

    定义跨平台功能的统一接口：
    - 窗口管理
    - 应用管理
    - 开机自启管理
    """

    @property
    @abstractmethod
    def platform_name(self) -> str:
        """获取平台名称"""
        pass

    @abstractmethod
    def get_active_window(self) -> WindowInfo:
        """
        获取当前活动窗口信息

        Returns:
            WindowInfo: 窗口信息对象
        """
        pass

    @abstractmethod
    def get_running_apps(self, max_count: int = 50) -> List[AppInfo]:
        """
        获取运行中的应用列表

        Args:
            max_count: 最大返回数量

        Returns:
            List[AppInfo]: 应用信息列表
        """
        pass

    @abstractmethod
    def enable_autostart(self) -> Result:
        """
        启用开机自启

        Returns:
            Result: 操作结果
        """
        pass

    @abstractmethod
    def disable_autostart(self) -> Result:
        """
        禁用开机自启

        Returns:
            Result: 操作结果
        """
        pass

    @abstractmethod
    def is_autostart_enabled(self) -> bool:
        """
        检查是否已启用开机自启

        Returns:
            bool: 是否已启用
        """
        pass

    def set_autostart(self, enabled: bool) -> Result:
        """
        设置开机自启状态

        Args:
            enabled: 是否启用

        Returns:
            Result: 操作结果
        """
        if enabled:
            return self.enable_autostart()
        else:
            return self.disable_autostart()
