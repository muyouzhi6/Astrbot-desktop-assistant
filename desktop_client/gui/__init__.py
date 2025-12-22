"""
AstrBot Desktop Client GUI 模块

包含所有 GUI 组件：
- FloatingBallWindow: 悬浮球窗口
- SimpleChatWindow: 对话窗口
- SettingsWindow: 设置窗口
- SystemTrayIcon: 系统托盘
- ThemeManager: 主题管理器
- HotkeyManager: 快捷键管理器
"""

from .floating_ball import FloatingBallWindow, CompactChatWindow
from .simple_chat_window import SimpleChatWindow, MessageBubble, ChatInputWidget
from .settings_window import SettingsWindow
from .system_tray import SystemTrayIcon
from .themes import (
    Theme, ThemeColors, 
    theme_manager, ThemeManager,
    THEMES
)
from .hotkeys import (
    HotkeyConfig, HotkeyManager,
    hotkey_manager, get_hotkey_manager
)

__all__ = [
    # 悬浮球
    "FloatingBallWindow",
    "CompactChatWindow",
    
    # 对话窗口
    "SimpleChatWindow",
    "MessageBubble",
    "ChatInputWidget",
    
    # 设置窗口
    "SettingsWindow",
    
    # 系统托盘
    "SystemTrayIcon",
    
    # 主题系统
    "Theme",
    "ThemeColors",
    "ThemeManager",
    "theme_manager",
    "THEMES",
    
    # 快捷键系统
    "HotkeyConfig",
    "HotkeyManager",
    "hotkey_manager",
    "get_hotkey_manager",
]