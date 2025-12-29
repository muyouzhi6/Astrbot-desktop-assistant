"""
Desktop Client Services
"""

from .screen_capture import ScreenCaptureService
from .proactive_dialog import ProactiveDialogService
from .chat_history import ChatHistoryManager, ChatMessage, get_chat_history_manager
from .desktop_monitor import DesktopMonitorService, DesktopState
from .update_service import UpdateService

__all__ = [
    "ScreenCaptureService",
    "ProactiveDialogService",
    "ChatHistoryManager",
    "ChatMessage",
    "get_chat_history_manager",
    "DesktopMonitorService",
    "DesktopState",
    "UpdateService",
]
