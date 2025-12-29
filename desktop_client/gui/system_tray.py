"""
系统托盘

提供系统托盘图标和菜单。
"""

from typing import Optional
from PySide6.QtWidgets import (
    QSystemTrayIcon,
    QMenu,
    QApplication,
)
from PySide6.QtCore import Signal, QObject
from PySide6.QtGui import QIcon, QPixmap, QPainter, QColor, QBrush

from ..api_client import ConnectionState


class SystemTrayIcon(QObject):
    """系统托盘"""

    # 信号
    show_chat_requested = Signal()
    show_settings_requested = Signal()
    quit_requested = Signal()

    def __init__(self, app: QApplication, parent: Optional[QObject] = None):
        super().__init__(parent)
        self.app = app
        self._current_state = ConnectionState.DISCONNECTED

        self._setup_tray()

    def _setup_tray(self):
        """设置托盘"""
        self._tray = QSystemTrayIcon(self.app)

        # 创建默认图标
        self._update_icon(ConnectionState.DISCONNECTED)

        # 创建菜单
        menu = QMenu()

        # 显示对话
        show_action = menu.addAction("显示对话窗口")
        show_action.triggered.connect(self.show_chat_requested.emit)

        menu.addSeparator()

        # 设置
        settings_action = menu.addAction("设置")
        settings_action.triggered.connect(self.show_settings_requested.emit)

        menu.addSeparator()

        # 退出
        quit_action = menu.addAction("退出")
        quit_action.triggered.connect(self.quit_requested.emit)

        self._tray.setContextMenu(menu)

        # 双击显示
        self._tray.activated.connect(self._on_activated)

        # 显示托盘图标
        self._tray.show()

    def _on_activated(self, reason: QSystemTrayIcon.ActivationReason):
        """托盘激活"""
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            self.show_chat_requested.emit()
        elif reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self.show_chat_requested.emit()

    def _create_icon(self, color: str) -> QIcon:
        """创建带颜色指示的图标"""
        # 创建 32x32 图标
        size = 32
        pixmap = QPixmap(size, size)
        pixmap.fill(QColor(0, 0, 0, 0))  # 透明背景

        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # 绘制主圆形（蓝色）
        painter.setBrush(QBrush(QColor("#0084ff")))
        painter.setPen(QColor("#0084ff"))
        painter.drawEllipse(2, 2, size - 4, size - 4)

        # 绘制 "A" 字母
        painter.setPen(QColor("white"))
        font = painter.font()
        font.setPixelSize(18)
        font.setBold(True)
        painter.setFont(font)
        painter.drawText(pixmap.rect(), 0x84, "A")  # AlignCenter

        # 绘制状态指示点
        status_color = QColor(color)
        painter.setBrush(QBrush(status_color))
        painter.setPen(status_color)
        painter.drawEllipse(size - 10, size - 10, 8, 8)

        painter.end()

        return QIcon(pixmap)

    def _update_icon(self, state: ConnectionState):
        """更新图标"""
        color_map = {
            ConnectionState.DISCONNECTED: "gray",
            ConnectionState.CONNECTING: "orange",
            ConnectionState.CONNECTED: "green",
            ConnectionState.RECONNECTING: "orange",
            ConnectionState.ERROR: "red",
        }

        color = color_map.get(state, "gray")
        icon = self._create_icon(color)
        self._tray.setIcon(icon)

        # 更新提示
        status_text = {
            ConnectionState.DISCONNECTED: "未连接",
            ConnectionState.CONNECTING: "连接中...",
            ConnectionState.CONNECTED: "已连接",
            ConnectionState.RECONNECTING: "重连中...",
            ConnectionState.ERROR: "连接错误",
        }
        self._tray.setToolTip(f"AstrBot 桌面助手 - {status_text.get(state, '未知')}")

    def update_connection_state(self, state: ConnectionState):
        """更新连接状态"""
        self._current_state = state
        self._update_icon(state)

    def show_message(
        self,
        title: str,
        message: str,
        icon: QSystemTrayIcon.MessageIcon = QSystemTrayIcon.MessageIcon.Information,
        duration: int = 3000,
    ):
        """显示通知消息"""
        self._tray.showMessage(title, message, icon, duration)

    def hide(self):
        """隐藏托盘图标"""
        self._tray.hide()

    def show(self):
        """显示托盘图标"""
        self._tray.show()
