"""
开机自启管理模块

提供跨平台开机自启功能的管理。
使用平台适配器实现跨平台支持。
"""

from typing import Tuple

from ..platforms import get_platform_adapter


def is_autostart_enabled() -> bool:
    """
    检查是否已启用开机自启

    Returns:
        bool: 是否已启用
    """
    adapter = get_platform_adapter()
    return adapter.is_autostart_enabled()


def enable_autostart() -> Tuple[bool, str]:
    """
    启用开机自启

    Returns:
        Tuple[bool, str]: (是否成功, 消息)
    """
    adapter = get_platform_adapter()
    result = adapter.enable_autostart()
    return result.is_success, result.message


def disable_autostart() -> Tuple[bool, str]:
    """
    禁用开机自启

    Returns:
        Tuple[bool, str]: (是否成功, 消息)
    """
    adapter = get_platform_adapter()
    result = adapter.disable_autostart()
    return result.is_success, result.message


def set_autostart(enabled: bool) -> Tuple[bool, str]:
    """
    设置开机自启状态

    Args:
        enabled: 是否启用

    Returns:
        Tuple[bool, str]: (是否成功, 消息)
    """
    if enabled:
        return enable_autostart()
    else:
        return disable_autostart()


# 导出平台适配器的 Result 类型，供需要更详细结果的调用者使用
__all__ = [
    "is_autostart_enabled",
    "enable_autostart",
    "disable_autostart",
    "set_autostart",
]
