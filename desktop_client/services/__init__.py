"""
Desktop Client Services
"""

from .screen_capture import ScreenCaptureService
from .proactive_dialog import ProactiveDialogService

__all__ = [
    "ScreenCaptureService",
    "ProactiveDialogService",
]