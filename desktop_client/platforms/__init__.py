"""
平台适配器模块

提供跨平台功能的统一接口和工厂函数。
"""

import platform
from typing import Optional

from .base import (
    IPlatformAdapter,
    WindowInfo,
    AppInfo,
    Result,
    ResultStatus,
)


# 缓存的适配器实例
_platform_adapter: Optional[IPlatformAdapter] = None


def get_platform_adapter() -> IPlatformAdapter:
    """
    获取当前平台的适配器实例

    使用工厂模式根据当前操作系统返回对应的平台适配器。
    适配器实例会被缓存，多次调用返回同一实例。

    Returns:
        IPlatformAdapter: 平台适配器实例

    Raises:
        RuntimeError: 不支持的平台
    """
    global _platform_adapter

    if _platform_adapter is not None:
        return _platform_adapter

    system = platform.system()

    if system == "Windows":
        from .windows import WindowsPlatformAdapter

        _platform_adapter = WindowsPlatformAdapter()
    elif system == "Darwin":
        from .macos import MacOSPlatformAdapter

        _platform_adapter = MacOSPlatformAdapter()
    elif system == "Linux":
        from .linux import LinuxPlatformAdapter

        _platform_adapter = LinuxPlatformAdapter()
    else:
        raise RuntimeError(f"不支持的平台: {system}")

    return _platform_adapter


def get_platform_name() -> str:
    """
    获取当前平台名称

    Returns:
        str: 平台名称 (Windows/macOS/Linux)
    """
    return get_platform_adapter().platform_name


# 导出公共接口
__all__ = [
    # 抽象基类和数据类型
    "IPlatformAdapter",
    "WindowInfo",
    "AppInfo",
    "Result",
    "ResultStatus",
    # 工厂函数
    "get_platform_adapter",
    "get_platform_name",
]
