"""
全局快捷键系统

提供全局热键功能，支持：
- 显示/隐藏对话窗口
- 区域截图
- 全屏截图
- 显示/隐藏悬浮球
- 自定义快捷键配置
"""

from typing import Dict, Optional
from dataclasses import dataclass

from PySide6.QtCore import QObject, Signal, Qt
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import QWidget


@dataclass
class HotkeyConfig:
    """快捷键配置"""

    # 显示/隐藏对话窗口
    toggle_chat: str = "Ctrl+Shift+A"
    # 区域截图
    region_screenshot: str = "Ctrl+Shift+S"
    # 全屏截图
    full_screenshot: str = "Ctrl+Shift+F"
    # 显示/隐藏悬浮球
    toggle_ball: str = "Ctrl+Shift+B"
    # 快速提问（弹出输入框）
    quick_ask: str = "Ctrl+Shift+Q"
    # 切换主题
    cycle_theme: str = "Ctrl+Shift+T"

    def to_dict(self) -> Dict[str, str]:
        """转换为字典"""
        return {
            "toggle_chat": self.toggle_chat,
            "region_screenshot": self.region_screenshot,
            "full_screenshot": self.full_screenshot,
            "toggle_ball": self.toggle_ball,
            "quick_ask": self.quick_ask,
            "cycle_theme": self.cycle_theme,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, str]) -> "HotkeyConfig":
        """从字典创建"""
        return cls(
            toggle_chat=data.get("toggle_chat", "Ctrl+Shift+A"),
            region_screenshot=data.get("region_screenshot", "Ctrl+Shift+S"),
            full_screenshot=data.get("full_screenshot", "Ctrl+Shift+F"),
            toggle_ball=data.get("toggle_ball", "Ctrl+Shift+B"),
            quick_ask=data.get("quick_ask", "Ctrl+Shift+Q"),
            cycle_theme=data.get("cycle_theme", "Ctrl+Shift+T"),
        )


class HotkeyManager(QObject):
    """
    快捷键管理器

    使用 Qt 的 QShortcut 实现应用级快捷键
    对于全局快捷键（应用未激活时也能触发），需要使用平台特定的实现
    """

    # 信号
    toggle_chat_triggered = Signal()
    region_screenshot_triggered = Signal()
    full_screenshot_triggered = Signal()
    toggle_ball_triggered = Signal()
    quick_ask_triggered = Signal()
    cycle_theme_triggered = Signal()

    _instance: Optional["HotkeyManager"] = None
    _initialized: bool = False

    def __new__(cls, *args, **kwargs) -> "HotkeyManager":
        if cls._instance is None:
            instance = super().__new__(cls)
            cls._instance = instance
        assert cls._instance is not None
        return cls._instance

    def __init__(self, parent: Optional[QWidget] = None):
        if self._initialized:
            return

        super().__init__(parent)
        self._initialized = True
        self._config = HotkeyConfig()
        self._shortcuts: Dict[str, QShortcut] = {}
        self._parent_widget = parent
        self._global_enabled = False

        # 尝试导入全局快捷键库
        self._global_hotkey_available = False
        self._keyboard_listener = None

        try:
            from pynput import keyboard

            self._global_hotkey_available = True
            self._keyboard = keyboard
        except ImportError:
            print("[HotkeyManager] pynput not available, using Qt shortcuts only")

    def set_parent_widget(self, widget: QWidget):
        """设置父窗口（用于 Qt 快捷键）"""
        self._parent_widget = widget
        self._setup_qt_shortcuts()

    def set_config(self, config: HotkeyConfig):
        """设置快捷键配置"""
        self._config = config
        self._setup_qt_shortcuts()
        if self._global_enabled:
            self._setup_global_hotkeys()

    def get_config(self) -> HotkeyConfig:
        """获取快捷键配置"""
        return self._config

    def _setup_qt_shortcuts(self):
        """设置 Qt 应用级快捷键"""
        if not self._parent_widget:
            return

        # 清除旧的快捷键
        for shortcut in self._shortcuts.values():
            shortcut.deleteLater()
        self._shortcuts.clear()

        # 创建新的快捷键
        shortcuts_map = {
            "toggle_chat": (self._config.toggle_chat, self.toggle_chat_triggered),
            "region_screenshot": (
                self._config.region_screenshot,
                self.region_screenshot_triggered,
            ),
            "full_screenshot": (
                self._config.full_screenshot,
                self.full_screenshot_triggered,
            ),
            "toggle_ball": (self._config.toggle_ball, self.toggle_ball_triggered),
            "quick_ask": (self._config.quick_ask, self.quick_ask_triggered),
            "cycle_theme": (self._config.cycle_theme, self.cycle_theme_triggered),
        }

        for name, (key_seq, signal) in shortcuts_map.items():
            if key_seq:
                shortcut = QShortcut(QKeySequence(key_seq), self._parent_widget)
                shortcut.setContext(Qt.ShortcutContext.ApplicationShortcut)
                shortcut.activated.connect(signal.emit)
                self._shortcuts[name] = shortcut

    def enable_global_hotkeys(self, enabled: bool = True):
        """启用/禁用全局快捷键"""
        self._global_enabled = enabled

        if enabled and self._global_hotkey_available:
            self._setup_global_hotkeys()
        else:
            self._stop_global_hotkeys()

    def _setup_global_hotkeys(self):
        """设置全局快捷键（使用 pynput）"""
        if not self._global_hotkey_available:
            return

        self._stop_global_hotkeys()

        try:
            from pynput import keyboard

            # 解析快捷键
            hotkeys = {}

            def create_handler(signal):
                def handler():
                    signal.emit()

                return handler

            key_map = {
                self._config.toggle_chat: self.toggle_chat_triggered,
                self._config.region_screenshot: self.region_screenshot_triggered,
                self._config.full_screenshot: self.full_screenshot_triggered,
                self._config.toggle_ball: self.toggle_ball_triggered,
                self._config.quick_ask: self.quick_ask_triggered,
                self._config.cycle_theme: self.cycle_theme_triggered,
            }

            for key_seq, signal in key_map.items():
                if key_seq:
                    # 转换 Qt 格式到 pynput 格式
                    pynput_key = self._convert_to_pynput_format(key_seq)
                    if pynput_key:
                        hotkeys[pynput_key] = create_handler(signal)

            if hotkeys:
                self._keyboard_listener = keyboard.GlobalHotKeys(hotkeys)
                self._keyboard_listener.start()
                print(f"[HotkeyManager] Global hotkeys enabled: {list(hotkeys.keys())}")

        except Exception as e:
            print(f"[HotkeyManager] Failed to setup global hotkeys: {e}")

    def _stop_global_hotkeys(self):
        """停止全局快捷键监听"""
        if self._keyboard_listener:
            try:
                self._keyboard_listener.stop()
            except Exception:
                pass
            self._keyboard_listener = None

    def _convert_to_pynput_format(self, qt_key: str) -> Optional[str]:
        """
        将 Qt 快捷键格式转换为 pynput 格式

        Qt: "Ctrl+Shift+A"
        pynput: "<ctrl>+<shift>+a"
        """
        if not qt_key:
            return None

        parts = qt_key.lower().split("+")
        result = []

        for part in parts:
            part = part.strip()
            if part == "ctrl":
                result.append("<ctrl>")
            elif part == "shift":
                result.append("<shift>")
            elif part == "alt":
                result.append("<alt>")
            elif part == "meta" or part == "win":
                result.append("<cmd>")
            elif len(part) == 1:
                result.append(part)
            else:
                # 特殊键
                special_keys = {
                    "space": "<space>",
                    "enter": "<enter>",
                    "return": "<enter>",
                    "tab": "<tab>",
                    "escape": "<esc>",
                    "esc": "<esc>",
                    "backspace": "<backspace>",
                    "delete": "<delete>",
                    "home": "<home>",
                    "end": "<end>",
                    "pageup": "<page_up>",
                    "pagedown": "<page_down>",
                    "up": "<up>",
                    "down": "<down>",
                    "left": "<left>",
                    "right": "<right>",
                }
                if part in special_keys:
                    result.append(special_keys[part])
                else:
                    result.append(part)

        return "+".join(result)

    def cleanup(self):
        """清理资源"""
        self._stop_global_hotkeys()
        for shortcut in self._shortcuts.values():
            shortcut.deleteLater()
        self._shortcuts.clear()


# 延迟初始化全局实例
_hotkey_manager: Optional[HotkeyManager] = None


def get_hotkey_manager() -> HotkeyManager:
    """获取快捷键管理器实例"""
    global _hotkey_manager
    if _hotkey_manager is None:
        _hotkey_manager = HotkeyManager()
    return _hotkey_manager


# 为向后兼容保留的属性访问
class _HotkeyManagerProxy:
    """代理类，用于延迟初始化"""

    def __getattr__(self, name):
        return getattr(get_hotkey_manager(), name)


hotkey_manager = _HotkeyManagerProxy()  # type: ignore
