"""
美化版悬浮球窗口

提供可拖拽的圆形悬浮窗口，支持：
- 自定义头像图片
- 主题配色
- 呼吸灯动画效果
- 单击显示气泡对话
- 双击打开对话窗口
- 右键菜单
- 聊天记录持久化和跨窗口同步
"""

from typing import Optional, Set
import os
import sys
import math
from enum import Enum

from PySide6.QtCore import (
    Qt,
    QPoint,
    QTimer,
    Signal,
    QPropertyAnimation,
    QEasingCurve,
    Property,
    QSize,
)
from PySide6.QtGui import (
    QPixmap,
    QPainter,
    QBrush,
    QColor,
    QMouseEvent,
    QPen,
    QRadialGradient,
    QPainterPath,
)
from PySide6.QtWidgets import (
    QWidget,
    QLabel,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QMenu,
    QApplication,
    QFrame,
    QSizePolicy,
    QScrollArea,
    QFileDialog,
)
from ..services.screen_capture import ScreenCaptureService
from .themes import theme_manager, Theme
from .icons import icon_manager
from .chat_widgets import (
    PasteAwareTextEdit,
    VoiceMessageWidget,
    VideoMessageWidget,
    FileMessageWidget,
    ClickableImageLabel,
)
from .markdown_utils import MarkdownLabel
from ..services import get_chat_history_manager, ChatMessage


# macOS 窗口置顶支持
# 使用 PyObjC 设置 NSWindow.level 实现真正的置顶效果
_HAS_PYOBJC = False
_NSFloatingWindowLevel = 3  # NSFloatingWindowLevel 常量值

if sys.platform == "darwin":
    try:
        from AppKit import (
            NSFloatingWindowLevel as _NSFloatingWindowLevel,
        )

        _HAS_PYOBJC = True
    except ImportError:
        # PyObjC 未安装，回退到 Qt 默认行为
        print(
            "[macOS] PyObjC 未安装，窗口置顶功能可能受限。建议安装: pip install pyobjc-framework-Cocoa"
        )
        _HAS_PYOBJC = False


def _set_macos_window_level(widget: QWidget, level: Optional[int] = None):
    """
    在 macOS 上设置窗口层级以实现真正的置顶效果

    Args:
        widget: Qt 窗口组件
        level: NSWindow 层级，默认为 NSFloatingWindowLevel (3)
    """
    if sys.platform != "darwin" or not _HAS_PYOBJC:
        return

    actual_level = level if level is not None else _NSFloatingWindowLevel

    try:
        # 获取窗口的 native window handle (NSWindow)
        window_id = widget.winId()
        if window_id:
            # 通过 NSApp 获取所有窗口，找到匹配的窗口
            from AppKit import NSApp

            for ns_window in NSApp.windows():
                # 检查窗口编号是否匹配
                if ns_window.windowNumber() == int(window_id):
                    ns_window.setLevel_(actual_level)
                    # 设置窗口收集行为，确保在所有桌面空间可见
                    ns_window.setCollectionBehavior_(
                        ns_window.collectionBehavior()
                        | (1 << 0)  # NSWindowCollectionBehaviorCanJoinAllSpaces
                        | (1 << 4)  # NSWindowCollectionBehaviorFullScreenAuxiliary
                    )
                    print(f"[macOS] 已设置窗口层级为 {actual_level}")
                    return

            # 如果上述方法失败，尝试使用 Objective-C runtime
            try:
                import objc

                # 将 window_id 转换为 NSWindow 对象
                # PySide6 的 winId() 返回的是 NSView 的指针
                ns_view = objc.objc_object(c_void_p=int(window_id))
                if hasattr(ns_view, "window") and ns_view.window():
                    ns_window = ns_view.window()
                    ns_window.setLevel_(actual_level)
                    ns_window.setCollectionBehavior_(
                        ns_window.collectionBehavior()
                        | (1 << 0)  # NSWindowCollectionBehaviorCanJoinAllSpaces
                        | (1 << 4)  # NSWindowCollectionBehaviorFullScreenAuxiliary
                    )
                    print(f"[macOS] 已通过 NSView 设置窗口层级为 {actual_level}")
            except Exception as e2:
                print(f"[macOS] 备用方法设置窗口层级失败: {e2}")

    except Exception as e:
        print(f"[macOS] 设置窗口层级失败: {e}")


class FloatingBallState(Enum):
    """悬浮球状态"""

    NORMAL = "normal"  # 正常
    BUSY = "busy"  # 忙碌 (如正在思考)
    PROCESSING = "processing"  # 处理中 (如语音识别中)
    DISCONNECTED = "disconnected"  # 断开连接
    UNREAD_MESSAGE = "unread_message"  # 有未读消息


class CompactChatWindow(QWidget):
    """精简版对话窗口 - 替代原有的气泡和输入框，提供统一体验"""

    message_sent = Signal(str)
    image_sent = Signal(str, str)  # path, text
    closed = Signal()

    def __init__(self, parent=None, max_history: int = 50, config=None):
        super().__init__(parent)
        self._config = config
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        self._max_history = max_history
        self._message_history = []  # [(msg_type, content, is_user), ...]
        self._attachment_path = None
        self._is_waiting = False

        # 自动隐藏定时器
        self._auto_hide_timer = QTimer(self)
        self._auto_hide_timer.setSingleShot(True)
        self._auto_hide_timer.timeout.connect(self._on_auto_hide_timeout)
        self._auto_hide_enabled = False
        self._auto_hide_duration = 5000  # 默认5秒
        self._current_ai_message = ""
        self._current_ai_label = None  # 当前 AI 回复的 MarkdownLabel
        self._current_ai_message_id: str = ""  # 当前流式响应的消息ID

        # 已显示消息ID集合，用于避免重复显示
        self._displayed_message_ids: Set[str] = set()

        # 消息ID与MarkdownLabel的映射，用于更新消息
        self._message_labels: dict = {}  # {message_id: MarkdownLabel}

        # 历史记录加载状态标志
        self._history_loaded = False
        self._history_loading = False

        # 聊天记录管理器
        self._chat_history = get_chat_history_manager()

        # 自定义头像路径
        self._user_avatar_path = ""
        self._bot_avatar_path = ""
        self._user_avatar_pixmap: Optional[QPixmap] = None
        self._bot_avatar_pixmap: Optional[QPixmap] = None

        # 调整大小相关状态
        self._resizing = False
        self._resize_edge = None  # 'left', 'right', 'top', 'bottom', 'top-left', etc.
        self._resize_margin = 6
        self._last_pos = QPoint()

        # 主容器
        self._container = QFrame()
        self._container.setObjectName("compactContainer")

        # 主布局
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(self._container)

        # 容器内布局
        container_layout = QVBoxLayout(self._container)
        # 增加边距以便更容易拖动（虽然这里是内部布局，外部调整大小靠鼠标事件）
        container_layout.setContentsMargins(12, 12, 12, 12)
        container_layout.setSpacing(8)

        # 1. 顶部栏 (关闭按钮)
        top_bar = QHBoxLayout()
        top_bar.setContentsMargins(0, 0, 0, 0)

        top_bar.addStretch()

        self._close_btn = QPushButton("×")
        self._close_btn.setObjectName("compactCloseBtn")
        self._close_btn.setFixedSize(24, 24)
        self._close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._close_btn.clicked.connect(self._on_close)
        top_bar.addWidget(self._close_btn)

        container_layout.addLayout(top_bar)

        # 2. 消息历史区域
        self._scroll_area = QScrollArea()
        self._scroll_area.setObjectName("compactScroll")
        self._scroll_area.setWidgetResizable(True)
        # 禁用横向滚动条，确保不会出现不必要的滚动条
        self._scroll_area.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self._scroll_area.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded
        )

        # 设置初始大小和最小大小，允许调整
        self.setMinimumWidth(300)
        self.setMinimumHeight(200)
        self.resize(360, 480)  # 默认大小

        self._history_widget = QWidget()
        self._history_layout = QVBoxLayout(self._history_widget)
        self._history_layout.setContentsMargins(0, 0, 0, 0)
        self._history_layout.setSpacing(8)
        self._history_layout.addStretch()

        self._scroll_area.setWidget(self._history_widget)
        container_layout.addWidget(self._scroll_area)

        # 3. 附件预览区 (隐藏)
        self._preview_frame = QFrame()
        self._preview_frame.setVisible(False)
        preview_layout = QHBoxLayout(self._preview_frame)
        preview_layout.setContentsMargins(0, 0, 0, 0)

        self._preview_label = QLabel()
        self._preview_label.setFixedHeight(40)
        self._preview_label.setStyleSheet("border-radius: 4px;")

        self._remove_attachment_btn = QPushButton("×")
        self._remove_attachment_btn.setFixedSize(18, 18)
        self._remove_attachment_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._remove_attachment_btn.clicked.connect(self.clear_attachment)
        self._remove_attachment_btn.setStyleSheet(
            "background: rgba(255,0,0,0.7); color: white; border-radius: 9px; border: none;"
        )

        preview_layout.addWidget(self._preview_label)
        preview_layout.addWidget(self._remove_attachment_btn)
        preview_layout.addStretch()
        container_layout.addWidget(self._preview_frame)

        # 4. 输入框 + 发送按钮
        input_layout = QHBoxLayout()
        input_layout.setSpacing(8)

        # 附件按钮
        self._attach_btn = QPushButton()
        self._attach_btn.setObjectName("compactAttachBtn")
        self._attach_btn.setFixedSize(32, 40)
        self._attach_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._attach_btn.setToolTip("发送图片/附件")
        self._attach_btn.clicked.connect(self._on_attach_clicked)
        input_layout.addWidget(self._attach_btn)

        self._input = PasteAwareTextEdit()
        self._input.setPlaceholderText("输入消息...")
        self._input.setFixedHeight(40)
        self._input.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )
        self._input.image_pasted.connect(self.set_attachment)
        self._input.enter_pressed.connect(self._send)
        input_layout.addWidget(self._input)

        self._send_btn = QPushButton("发送")
        self._send_btn.setObjectName("compactSendBtn")
        self._send_btn.setFixedSize(60, 40)
        self._send_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._send_btn.clicked.connect(self._send)
        input_layout.addWidget(self._send_btn)

        container_layout.addLayout(input_layout)

        # 启用鼠标追踪以支持边缘检测
        self.setMouseTracking(True)
        self._container.setMouseTracking(True)

        # 应用主题
        self._apply_theme()
        theme_manager.register_callback(self._on_theme_changed)

        # 连接聊天记录管理器的信号
        self._chat_history.message_added.connect(self._on_history_message_added)
        self._chat_history.message_updated.connect(self._on_history_message_updated)
        self._chat_history.messages_cleared.connect(self._on_history_cleared)
        self._chat_history.history_loaded.connect(self._on_history_loaded)

        # 历史记录将由 FloatingBallWindow 在头像设置完成后统一加载
        # 移除这里的延迟加载，避免与 FloatingBallWindow 中的 reload_history_display 产生竞态条件
        # 见 FloatingBallWindow.__init__ 中的 QTimer.singleShot(150, self._compact_window.reload_history_display)

    def _on_theme_changed(self, theme: Theme):
        """主题切换时只更新样式，不重新加载历史"""
        # 保存当前滚动位置
        scrollbar = self._scroll_area.verticalScrollBar()
        scroll_pos = scrollbar.value()

        self._apply_theme()

        # 恢复滚动位置
        QTimer.singleShot(50, lambda: scrollbar.setValue(scroll_pos))

    def _apply_theme(self):
        t = theme_manager.current_theme
        c = (
            theme_manager.get_current_colors()
        )  # 使用 get_current_colors() 获取应用了自定义颜色的最终配置

        # 容器
        self._container.setStyleSheet(f"""
            QFrame#compactContainer {{
                background-color: {c.bg_primary};
                border: 1px solid {c.border_light};
                border-radius: {t.border_radius + 4}px;
            }}
        """)

        # 关闭按钮
        self._close_btn.setStyleSheet(f"""
            QPushButton#compactCloseBtn {{
                background: transparent;
                color: {c.text_secondary};
                border: none;
                border-radius: 12px;
                font-size: 16px;
                font-weight: bold;
                padding-bottom: 2px;
            }}
            QPushButton#compactCloseBtn:hover {{
                background-color: #ff4d4f;
                color: white;
            }}
        """)

        # 滚动区
        self._scroll_area.setStyleSheet(f"""
            QScrollArea#compactScroll {{
                background: transparent;
                border: none;
            }}
            QScrollArea#compactScroll QScrollBar:vertical {{
                background: {c.bg_secondary};
                width: 6px;
                border-radius: 3px;
            }}
            QScrollArea#compactScroll QScrollBar::handle:vertical {{
                background: {c.text_secondary};
                border-radius: 3px;
                min-height: 20px;
            }}
            QScrollArea#compactScroll QScrollBar::add-line:vertical,
            QScrollArea#compactScroll QScrollBar::sub-line:vertical {{
                height: 0px;
            }}
        """)

        self._history_widget.setStyleSheet("background: transparent;")

        # 输入框
        self._input.setStyleSheet(f"""
            QTextEdit {{
                background-color: {c.bg_secondary};
                border: 1px solid {c.border_light};
                border-radius: {t.border_radius}px;
                padding: 8px;
                font-family: {t.font_family};
                font-size: {t.font_size_base}px;
                color: {c.text_primary};
            }}
            QTextEdit:focus {{
                border: 1px solid {c.primary};
            }}
        """)

        # 发送按钮
        self._send_btn.setStyleSheet(f"""
            QPushButton#compactSendBtn {{
                background-color: {c.primary};
                color: white;
                border: none;
                border-radius: {t.border_radius}px;
                font-weight: bold;
            }}
            QPushButton#compactSendBtn:hover {{
                background-color: {c.primary_dark};
            }}
            QPushButton#compactSendBtn:disabled {{
                background-color: {c.text_secondary};
            }}
        """)

        # 附件按钮
        self._attach_btn.setStyleSheet(f"""
            QPushButton#compactAttachBtn {{
                background-color: {c.bg_secondary};
                color: {c.text_primary};
                border: 1px solid {c.border_light};
                border-radius: {t.border_radius}px;
            }}
            QPushButton#compactAttachBtn:hover {{
                background-color: {c.bg_hover};
            }}
        """)
        # 设置附件图标
        attach_icon = icon_manager.get_icon("attach", c.text_primary, 18)
        self._attach_btn.setIcon(attach_icon)
        self._attach_btn.setIconSize(QSize(18, 18))

        # 刷新所有历史消息的样式 (主要是 MarkdownLabel 和用户消息气泡)
        for i in range(self._history_layout.count()):
            item = self._history_layout.itemAt(i)
            if item and item.widget():
                container = item.widget()
                # 遍历容器中的所有子组件
                self._update_widget_theme(container, c, t)

    def _update_widget_theme(self, widget, c, t):
        """递归更新组件及其子组件的主题"""
        if isinstance(widget, MarkdownLabel):
            widget.update_theme()
        elif isinstance(widget, QLabel):
            # 检查是否是用户消息气泡（通过检查样式表中是否包含 bubble 相关颜色）
            current_style = widget.styleSheet()
            if "bubble" in current_style.lower() or "background-color" in current_style:
                # 判断是用户消息还是头像标签
                # 用户消息气泡有 border-radius: 12px 和 padding: 10px
                if (
                    "border-radius: 12px" in current_style
                    and "padding: 10px" in current_style
                ):
                    widget.setStyleSheet(f"""
                        QLabel {{
                            color: {c.bubble_user_text};
                            background-color: {c.bubble_user_bg};
                            border-radius: 12px;
                            padding: 10px;
                            font-family: {t.font_family};
                            font-size: {t.font_size_base}px;
                        }}
                    """)

        # 递归处理子组件
        if hasattr(widget, "children"):
            for child in widget.children():
                if isinstance(child, QWidget):
                    self._update_widget_theme(child, c, t)

    def set_user_avatar(self, avatar_path: str):
        """设置用户头像路径"""
        self._user_avatar_path = avatar_path
        if avatar_path and os.path.exists(avatar_path):
            pixmap = QPixmap(avatar_path)
            if not pixmap.isNull():
                # 缩放为圆形头像
                self._user_avatar_pixmap = pixmap.scaled(
                    24,
                    24,
                    Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                    Qt.TransformationMode.SmoothTransformation,
                )
        else:
            self._user_avatar_pixmap = None

    def set_bot_avatar(self, avatar_path: str):
        """设置Bot头像路径"""
        self._bot_avatar_path = avatar_path
        if avatar_path and os.path.exists(avatar_path):
            pixmap = QPixmap(avatar_path)
            if not pixmap.isNull():
                # 缩放为圆形头像
                self._bot_avatar_pixmap = pixmap.scaled(
                    24,
                    24,
                    Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                    Qt.TransformationMode.SmoothTransformation,
                )
        else:
            self._bot_avatar_pixmap = None

    def reload_history_display(self):
        """重新加载历史记录显示（在头像设置后调用）

        此方法会清空当前显示并重新加载所有历史记录。
        使用 _history_loading 标志防止并发加载。
        """
        # 防止并发加载
        if self._history_loading:
            print("[CompactChatWindow] 历史记录正在加载中，跳过重复加载")
            return

        self._history_loading = True

        try:
            # 清空当前显示
            while self._history_layout.count() > 1:
                item = self._history_layout.itemAt(0)
                if item and item.widget():
                    w = item.widget()
                    if w is not None:
                        self._history_layout.removeWidget(w)
                        w.deleteLater()

            self._displayed_message_ids.clear()
            self._message_labels.clear()

            # 重新加载显示
            messages = self._chat_history.get_messages()
            print(f"[CompactChatWindow] 加载 {len(messages)} 条历史记录")

            for msg in messages:
                self._display_message_from_history(msg)

            self._history_loaded = True
            self._scroll_to_bottom()

        finally:
            self._history_loading = False

    def _load_history(self):
        """加载聊天历史记录

        此方法只在历史未加载时执行，防止重复加载。
        """
        # 如果已经加载过或正在加载，跳过
        if self._history_loaded or self._history_loading:
            print("[CompactChatWindow] 历史记录已加载或正在加载，跳过")
            return

        self._history_loading = True

        try:
            # 显示已有的消息
            messages = self._chat_history.get_messages()
            print(f"[CompactChatWindow] _load_history: 加载 {len(messages)} 条消息")

            for msg in messages:
                self._display_message_from_history(msg)

            self._history_loaded = True
            self._scroll_to_bottom()

        finally:
            self._history_loading = False

    def _display_message_from_history(self, msg: ChatMessage):
        """从历史记录中显示消息（不会再次添加到历史记录）"""
        if msg.id in self._displayed_message_ids:
            return  # 已经显示过了

        self._displayed_message_ids.add(msg.id)

        if msg.role == "user":
            # 用户消息
            if msg.msg_type == "image" and msg.file_path:
                self._display_user_image(msg.file_path)
            else:
                self._display_user_text(msg.content)
        else:
            # AI消息
            if msg.msg_type == "voice":
                self._display_ai_voice(msg.content, msg.id)
            elif msg.msg_type == "video":
                self._display_ai_video(msg.content, msg.id)
            elif msg.msg_type == "image":
                # 优先使用 file_path，如果没有则尝试从 content 解析
                image_path = msg.file_path or msg.content
                self._display_ai_image(image_path, msg.id)
            elif msg.msg_type == "file":
                self._display_ai_file(msg.content, msg.id)
            else:
                label = self._display_ai_text(msg.content, msg.id)
                if label:
                    self._message_labels[msg.id] = label

    def _display_user_text(self, text: str):
        """显示用户文本消息（仅UI，不添加到历史）"""
        container = QWidget()
        container.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum
        )
        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        # 弹性空间，将内容推到右边
        layout.addStretch()

        # 文本气泡
        lbl = QLabel(text)
        lbl.setWordWrap(True)
        lbl.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Minimum)
        t = theme_manager.current_theme
        c = (
            theme_manager.get_current_colors()
        )  # 使用 get_current_colors() 获取应用了自定义颜色的最终配置
        lbl.setStyleSheet(f"""
            QLabel {{
                color: {c.bubble_user_text};
                background-color: {c.bubble_user_bg};
                border-radius: 12px;
                padding: 10px;
                font-family: {t.font_family};
                font-size: {t.font_size_base}px;
            }}
        """)
        # 最大宽度为窗口宽度的 70% 左右
        lbl.setMaximumWidth(int(self.width() * 0.7))
        layout.addWidget(lbl)

        # 用户头像
        avatar = QLabel()
        avatar.setFixedSize(32, 32)
        avatar.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)

        if self._user_avatar_pixmap and not self._user_avatar_pixmap.isNull():
            circular_avatar = self._create_circular_avatar(self._user_avatar_pixmap, 32)
            avatar.setPixmap(circular_avatar)
            avatar.setStyleSheet("background: transparent;")
        else:
            # 使用 SVG 图标作为默认头像
            icon_pixmap = icon_manager.get_pixmap("user", c.text_inverse, 20)
            avatar.setPixmap(icon_pixmap)
            avatar.setStyleSheet(
                f"font-size: 20px; background-color: {c.primary}; border-radius: 16px; color: white;"
            )
            avatar.setAlignment(Qt.AlignmentFlag.AlignCenter)

        layout.addWidget(avatar, alignment=Qt.AlignmentFlag.AlignTop)

        container.adjustSize()
        self._add_to_history(container, is_image=False)

    def _display_user_image(self, image_path: str):
        """显示用户图片消息（仅UI，不添加到历史）"""
        container = QWidget()
        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        # 弹性空间
        layout.addStretch()

        lbl = ClickableImageLabel(image_path)
        container.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        layout.addWidget(lbl)

        # 用户头像
        avatar = QLabel()
        avatar.setFixedSize(32, 32)
        avatar.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)

        c = (
            theme_manager.get_current_colors()
        )  # 使用 get_current_colors() 获取应用了自定义颜色的最终配置

        if self._user_avatar_pixmap and not self._user_avatar_pixmap.isNull():
            circular_avatar = self._create_circular_avatar(self._user_avatar_pixmap, 32)
            avatar.setPixmap(circular_avatar)
            avatar.setStyleSheet("background: transparent;")
        else:
            # 使用 SVG 图标作为默认头像
            icon_pixmap = icon_manager.get_pixmap("user", c.text_inverse, 20)
            avatar.setPixmap(icon_pixmap)
            avatar.setStyleSheet(
                f"font-size: 20px; background-color: {c.primary}; border-radius: 16px; color: white;"
            )
            avatar.setAlignment(Qt.AlignmentFlag.AlignCenter)

        layout.addWidget(avatar, alignment=Qt.AlignmentFlag.AlignTop)

        container.adjustSize()
        # container.setFixedHeight(lbl.height()) # 移除固定高度，让布局自动适应

        self._add_to_history(container, is_image=True)

    def _display_ai_text(
        self, text: str, message_id: str = ""
    ) -> Optional[MarkdownLabel]:
        """显示AI文本消息（仅UI，不添加到历史）"""
        container = QWidget()
        container.setSizePolicy(
            QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Minimum
        )
        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        # 机器人头像
        avatar = QLabel()
        avatar.setFixedSize(32, 32)
        avatar.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)

        c = (
            theme_manager.get_current_colors()
        )  # 使用 get_current_colors() 获取应用了自定义颜色的最终配置

        if self._bot_avatar_pixmap and not self._bot_avatar_pixmap.isNull():
            circular_avatar = self._create_circular_avatar(self._bot_avatar_pixmap, 32)
            avatar.setPixmap(circular_avatar)
            avatar.setStyleSheet("background: transparent;")
        else:
            # 使用 SVG 图标作为默认头像
            icon_pixmap = icon_manager.get_pixmap("bot", c.text_primary, 20)
            avatar.setPixmap(icon_pixmap)
            avatar.setStyleSheet(
                f"font-size: 20px; background-color: {c.bg_tertiary}; border-radius: 16px;"
            )
            avatar.setAlignment(Qt.AlignmentFlag.AlignCenter)

        layout.addWidget(avatar, alignment=Qt.AlignmentFlag.AlignTop)

        md_label = MarkdownLabel(text, parent=container)
        # 最大宽度为窗口宽度的 75%
        md_label.setMaximumWidth(int(self.width() * 0.75))
        md_label.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Minimum)
        layout.addWidget(md_label)

        layout.addStretch()
        container.adjustSize()

        self._add_to_history(container)

        return md_label

    def _display_ai_image(self, image_path: str, message_id: str = ""):
        """显示AI图片消息"""
        container = QWidget()
        container.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        # 机器人头像
        avatar = QLabel()
        avatar.setFixedSize(32, 32)
        avatar.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)

        c = (
            theme_manager.get_current_colors()
        )  # 使用 get_current_colors() 获取应用了自定义颜色的最终配置

        if self._bot_avatar_pixmap and not self._bot_avatar_pixmap.isNull():
            circular_avatar = self._create_circular_avatar(self._bot_avatar_pixmap, 32)
            avatar.setPixmap(circular_avatar)
            avatar.setStyleSheet("background: transparent;")
        else:
            # 使用 SVG 图标作为默认头像
            icon_pixmap = icon_manager.get_pixmap("bot", c.text_primary, 20)
            avatar.setPixmap(icon_pixmap)
            avatar.setStyleSheet(
                f"font-size: 20px; background-color: {c.bg_tertiary}; border-radius: 16px;"
            )
            avatar.setAlignment(Qt.AlignmentFlag.AlignCenter)

        layout.addWidget(avatar, alignment=Qt.AlignmentFlag.AlignTop)

        lbl = ClickableImageLabel(image_path)
        layout.addWidget(lbl)
        layout.addStretch()

        self._add_to_history(container, is_image=True)

    def _display_ai_file(self, content: str, message_id: str = ""):
        """显示AI文件消息"""
        # content format: path|name|size
        parts = content.split("|")
        file_path = parts[0]
        file_name = parts[1] if len(parts) > 1 else ""
        file_size = int(parts[2]) if len(parts) > 2 else 0

        container = QWidget()
        container.setSizePolicy(
            QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Minimum
        )
        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        # 机器人头像
        avatar = QLabel()
        avatar.setFixedSize(32, 32)
        avatar.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)

        c = (
            theme_manager.get_current_colors()
        )  # 使用 get_current_colors() 获取应用了自定义颜色的最终配置

        if self._bot_avatar_pixmap and not self._bot_avatar_pixmap.isNull():
            circular_avatar = self._create_circular_avatar(self._bot_avatar_pixmap, 32)
            avatar.setPixmap(circular_avatar)
            avatar.setStyleSheet("background: transparent;")
        else:
            # 使用 SVG 图标作为默认头像
            icon_pixmap = icon_manager.get_pixmap("bot", c.text_primary, 20)
            avatar.setPixmap(icon_pixmap)
            avatar.setStyleSheet(
                f"font-size: 20px; background-color: {c.bg_tertiary}; border-radius: 16px;"
            )
            avatar.setAlignment(Qt.AlignmentFlag.AlignCenter)

        layout.addWidget(avatar, alignment=Qt.AlignmentFlag.AlignTop)

        file_widget = FileMessageWidget(file_path, file_name, file_size)
        file_widget.setMaximumWidth(260)
        layout.addWidget(file_widget)
        layout.addStretch()

        self._add_to_history(container)

    def _display_ai_video(self, content: str, message_id: str = ""):
        """显示AI视频消息（仅UI，不添加到历史）"""
        # 解析内容: path|thumbnail|duration
        parts = content.split("|")
        video_path = parts[0].strip()
        thumbnail = parts[1] if len(parts) > 1 else ""
        duration = float(parts[2]) if len(parts) > 2 else 0

        container = QWidget()
        container.setSizePolicy(
            QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Minimum
        )
        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        # 机器人头像
        avatar = QLabel()
        avatar.setFixedSize(32, 32)
        avatar.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)

        c = (
            theme_manager.get_current_colors()
        )  # 使用 get_current_colors() 获取应用了自定义颜色的最终配置

        if self._bot_avatar_pixmap and not self._bot_avatar_pixmap.isNull():
            circular_avatar = self._create_circular_avatar(self._bot_avatar_pixmap, 32)
            avatar.setPixmap(circular_avatar)
            avatar.setStyleSheet("background: transparent;")
        else:
            # 使用 SVG 图标作为默认头像
            icon_pixmap = icon_manager.get_pixmap("bot", c.text_primary, 20)
            avatar.setPixmap(icon_pixmap)
            avatar.setStyleSheet(
                f"font-size: 20px; background-color: {c.bg_tertiary}; border-radius: 16px;"
            )
            avatar.setAlignment(Qt.AlignmentFlag.AlignCenter)

        layout.addWidget(avatar, alignment=Qt.AlignmentFlag.AlignTop)

        video_widget = VideoMessageWidget(
            video_path, thumbnail, duration, parent=container
        )
        video_widget.setMaximumWidth(260)
        layout.addWidget(video_widget)

        layout.addStretch()
        container.adjustSize()

        self._add_to_history(container)

    def _display_ai_voice(self, content: str, message_id: str = ""):
        """显示AI语音消息（仅UI，不添加到历史）

        Args:
            content: 格式为 "audio_path|duration" 或仅 "audio_path"
            message_id: 消息ID
        """
        # 解析内容获取音频路径和时长
        parts = content.split("|")
        audio_path = parts[0].strip()
        duration = float(parts[1]) if len(parts) > 1 else 0

        # 验证音频路径存在
        if not audio_path or not os.path.exists(audio_path):
            # 如果路径无效，显示为文本消息
            self._display_ai_text(f"🔊 [语音消息: {audio_path}]", message_id)
            return

        container = QWidget()
        container.setSizePolicy(
            QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Minimum
        )
        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        # 机器人头像
        avatar = QLabel()
        avatar.setFixedSize(32, 32)
        avatar.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)

        c = (
            theme_manager.get_current_colors()
        )  # 使用 get_current_colors() 获取应用了自定义颜色的最终配置

        if self._bot_avatar_pixmap and not self._bot_avatar_pixmap.isNull():
            circular_avatar = self._create_circular_avatar(self._bot_avatar_pixmap, 32)
            avatar.setPixmap(circular_avatar)
            avatar.setStyleSheet("background: transparent;")
        else:
            # 使用 SVG 图标作为默认头像
            icon_pixmap = icon_manager.get_pixmap("bot", c.text_primary, 20)
            avatar.setPixmap(icon_pixmap)
            avatar.setStyleSheet(
                f"font-size: 20px; background-color: {c.bg_tertiary}; border-radius: 16px;"
            )
            avatar.setAlignment(Qt.AlignmentFlag.AlignCenter)

        layout.addWidget(avatar, alignment=Qt.AlignmentFlag.AlignTop)

        voice_widget = VoiceMessageWidget(audio_path, duration, parent=container)
        voice_widget.setMaximumWidth(260)
        layout.addWidget(voice_widget)

        layout.addStretch()
        container.adjustSize()

        self._add_to_history(container)

    def _on_history_message_added(self, msg: ChatMessage):
        """处理历史记录管理器发出的消息添加信号"""
        if msg.id in self._displayed_message_ids:
            return

        self._display_message_from_history(msg)
        self._scroll_to_bottom()

        # 自动播放语音逻辑
        if msg.role == "assistant" and msg.msg_type == "voice":
            should_play = False
            if self._config:
                if hasattr(self._config, "voice") and hasattr(
                    self._config.voice, "auto_play_voice"
                ):
                    should_play = self._config.voice.auto_play_voice
                elif isinstance(self._config, dict):
                    if "voice" in self._config:
                        should_play = self._config["voice"].get(
                            "auto_play_voice", False
                        )
                    else:
                        should_play = self._config.get("auto_play_voice", False)

            if should_play:
                # 查找最后添加的 widget (它是 container，包含 voice_widget)
                if self._history_layout.count() > 1:
                    container_item = self._history_layout.itemAt(
                        self._history_layout.count() - 2
                    )
                    if container_item:
                        container = container_item.widget()
                        if container:
                            voice_widget = container.findChild(VoiceMessageWidget)
                            if voice_widget:
                                voice_widget.set_playing(True)

    def _on_history_message_updated(self, message_id: str, new_content: str):
        """处理历史记录管理器发出的消息更新信号"""
        # 如果是当前正在流式响应的消息，更新MarkdownLabel
        if message_id in self._message_labels:
            label = self._message_labels[message_id]
            if label and isinstance(label, MarkdownLabel):
                label.set_markdown(new_content)
                self._scroll_to_bottom()

    def _on_history_cleared(self):
        """处理历史记录清除信号"""
        # 清空所有显示的消息
        while self._history_layout.count() > 1:  # 保留 stretch
            item = self._history_layout.itemAt(0)
            if item:
                w = item.widget()
                if w is not None:
                    self._history_layout.removeWidget(w)
                    w.deleteLater()

        self._displayed_message_ids.clear()
        self._message_labels.clear()
        self._current_ai_label = None
        self._current_ai_message_id = ""
        self._update_geometry()

    def _on_history_loaded(self):
        """处理历史记录加载完成信号

        当 ChatHistoryManager 完成文件加载时调用此方法。
        注意：此方法只在初始化时或显式调用 load_from_file 后触发，
        主题切换不会触发此方法。
        """
        # 如果已经加载过且当前有显示内容，跳过重复加载
        # 这可以防止某些意外情况下的重复加载
        if self._history_loaded and self._displayed_message_ids:
            print("[CompactChatWindow] 历史已加载且有显示内容，跳过重复加载")
            return

        print("[CompactChatWindow] 收到 history_loaded 信号，重新加载显示")

        # 重置加载状态以允许重新加载
        self._history_loaded = False

        # 调用 reload_history_display 来重新加载
        self.reload_history_display()

    def _on_close(self):
        self.hide()
        self.closed.emit()

    def set_attachment(self, path: str):
        if not path or not os.path.exists(path):
            return
        self._attachment_path = path
        pixmap = QPixmap(path)
        if not pixmap.isNull():
            self._preview_label.setPixmap(
                pixmap.scaled(
                    100,
                    40,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
            )
            self._preview_frame.setVisible(True)

    def clear_attachment(self):
        self._attachment_path = None
        self._preview_frame.setVisible(False)

    def _send(self):
        text = self._input.toPlainText().strip()
        if not text and not self._attachment_path:
            return

        if self._attachment_path:
            # 添加图片消息到历史记录 - 信号会处理显示，无需手动显示
            self._chat_history.add_message(
                role="user",
                content=text or "[图片]",
                msg_type="image",
                file_path=self._attachment_path,
            )

            if text:
                # 如果有文字，也添加文字消息
                self._chat_history.add_message(
                    role="user", content=text, msg_type="text"
                )

            self.image_sent.emit(self._attachment_path, text)
            self.clear_attachment()
        else:
            # 添加文本消息到历史记录 - 信号会处理显示
            self._chat_history.add_message(role="user", content=text, msg_type="text")

            self.message_sent.emit(text)

        self._input.clear()
        # 不再调用 _start_waiting()，允许连续发送消息

    def _start_waiting(self):
        """开始等待响应状态

        注意：不再禁用输入控件，允许用户在等待响应时继续发送消息
        """
        self._is_waiting = True
        # 移除禁用控件的代码，允许并发发送消息
        # self._send_btn.setEnabled(False)
        # self._input.setEnabled(False)

        # 不创建占位消息
        self._current_ai_message_id = ""
        self._current_ai_message = ""
        self._current_ai_label = None

    def add_system_message(self, text: str):
        """添加系统通知消息（仅UI，不保存到历史）"""
        container = QWidget()
        container.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 8, 0, 8)
        layout.setSpacing(0)

        # 居中布局
        layout.addStretch()

        lbl = QLabel(text)

        # 获取样式配置
        t = theme_manager.current_theme
        c = theme_manager.get_current_colors()

        # 字体大小比基准小 2px
        font_size = max(10, t.font_size_base - 2)

        lbl.setStyleSheet(f"""
            QLabel {{
                color: {c.system_notice_text};
                font-family: {t.font_family};
                font-size: {font_size}px;
                padding: 2px 8px;
                border-radius: 4px;
            }}
        """)
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)

        layout.addWidget(lbl)
        layout.addStretch()

        self._add_to_history(container)

    def add_user_message(self, text: str, image_path: Optional[str] = None):
        """添加用户消息（通过历史记录管理器）"""
        if image_path:
            # 添加图片消息
            msg = self._chat_history.add_message(
                role="user", content=text, msg_type="image", file_path=image_path
            )
            if msg.id not in self._displayed_message_ids:
                self._displayed_message_ids.add(msg.id)
                self._display_user_image(image_path)
        else:
            # 添加文本消息
            msg = self._chat_history.add_message(
                role="user", content=text, msg_type="text"
            )
            if msg.id not in self._displayed_message_ids:
                self._displayed_message_ids.add(msg.id)
                self._display_user_text(text)

    def _create_circular_avatar(self, pixmap: QPixmap, size: int = 24) -> QPixmap:
        """创建圆形头像"""
        rounded_pixmap = QPixmap(size, size)
        rounded_pixmap.fill(Qt.GlobalColor.transparent)

        painter = QPainter(rounded_pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # 绘制圆形裁剪路径
        path = QPainterPath()
        path.addEllipse(0, 0, size, size)
        painter.setClipPath(path)

        # 绘制头像
        painter.drawPixmap(0, 0, size, size, pixmap)
        painter.end()

        return rounded_pixmap

    def add_ai_message(self, text: str, msg_type: str = "text"):
        """添加 AI 消息（通过历史记录管理器）

        Args:
            text: 消息内容。对于语音消息，格式为 "path|duration"
            msg_type: 消息类型，"text" 或 "voice"
        """
        # 如果有等待中的消息（占位消息 "..."），需要替换它而不是创建新消息
        if self._current_ai_message_id and self._is_waiting:
            # 更新占位消息的内容和类型
            if msg_type == "voice":
                # 语音消息需要特殊处理：删除占位消息的MarkdownLabel，显示语音组件
                self._replace_waiting_with_voice(text)
            else:
                # 文本消息：直接更新占位消息的内容
                self._chat_history.update_message(self._current_ai_message_id, text)
                if self._current_ai_label:
                    self._current_ai_label.set_markdown(text)

            self.finish_response()
            return self._current_ai_label

        # 没有等待中的消息，正常添加新消息
        # 解析语音消息的文件路径
        file_path = ""
        if msg_type == "voice":
            parts = text.split("|")
            file_path = parts[0] if parts else ""

        # 添加到历史记录
        msg = self._chat_history.add_message(
            role="assistant", content=text, msg_type=msg_type, file_path=file_path
        )

        # 显示消息
        if msg.id not in self._displayed_message_ids:
            self._displayed_message_ids.add(msg.id)
            if msg_type == "voice":
                self._display_ai_voice(text, msg.id)
                return None
            else:
                label = self._display_ai_text(text, msg.id)
                if label:
                    self._message_labels[msg.id] = label
                return label

        return None

    def _replace_waiting_with_voice(self, content: str):
        """将等待中的占位消息替换为语音消息组件

        Args:
            content: 格式为 "audio_path|duration" 或仅 "audio_path"
        """
        if not self._current_ai_message_id:
            return

        # 更新历史记录中的消息类型和内容
        # 由于 ChatHistoryManager.update_message 只更新内容，我们需要删除旧消息并添加新消息
        # 但为了简化，我们先更新内容，然后在UI层做替换

        # 解析音频路径
        parts = content.split("|")
        parts[0].strip()

        # 更新历史记录
        self._chat_history.update_message(self._current_ai_message_id, content)

        # 找到并删除占位消息的UI组件
        if self._current_ai_label:
            # 找到包含这个label的container widget
            parent_obj = self._current_ai_label.parent()
            if parent_obj and isinstance(parent_obj, QWidget):
                parent_widget = parent_obj
                # 从历史layout中移除
                for i in range(self._history_layout.count()):
                    item = self._history_layout.itemAt(i)
                    if item and item.widget() == parent_widget:
                        self._history_layout.removeWidget(parent_widget)
                        parent_widget.deleteLater()
                        break

            # 从映射中删除
            if self._current_ai_message_id in self._message_labels:
                del self._message_labels[self._current_ai_message_id]

            self._current_ai_label = None

        # 显示语音消息组件
        self._display_ai_voice(content, self._current_ai_message_id)

    def add_voice_message(
        self, audio_path: str, duration: float = 0, is_user: bool = False
    ):
        """添加语音消息

        Args:
            audio_path: 音频文件路径
            duration: 音频时长（秒）
            is_user: 是否是用户消息
        """
        container = QWidget()
        container.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum
        )
        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        if is_user:
            # 用户消息：右对齐
            layout.addStretch()
            voice_widget = VoiceMessageWidget(audio_path, duration, parent=container)
            voice_widget.setMaximumWidth(240)
            layout.addWidget(voice_widget)
        else:
            # AI 消息：左对齐，带头像
            avatar = QLabel()
            avatar.setFixedSize(24, 24)
            avatar.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)

            c = (
                theme_manager.get_current_colors()
            )  # 使用 get_current_colors() 获取应用了自定义颜色的最终配置

            if self._bot_avatar_pixmap and not self._bot_avatar_pixmap.isNull():
                circular_avatar = self._create_circular_avatar(
                    self._bot_avatar_pixmap, 24
                )
                avatar.setPixmap(circular_avatar)
                avatar.setStyleSheet("background: transparent;")
            else:
                # 使用 SVG 图标作为默认头像
                icon_pixmap = icon_manager.get_pixmap("bot", c.text_primary, 16)
                avatar.setPixmap(icon_pixmap)
                avatar.setStyleSheet(
                    f"font-size: 16px; background-color: {c.bg_tertiary}; border-radius: 12px;"
                )

            layout.addWidget(avatar, alignment=Qt.AlignmentFlag.AlignTop)

            voice_widget = VoiceMessageWidget(audio_path, duration, parent=container)
            voice_widget.setMaximumWidth(260)
            layout.addWidget(voice_widget)
            layout.addStretch()

        container.adjustSize()
        self._add_to_history(container)

    def _add_to_history(self, widget: QWidget, is_image: bool = False):
        # 设置widget的大小策略（图片消息保持 Fixed 高度）
        if not is_image:
            widget.setSizePolicy(
                QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum
            )
        # 如果是图片消息，保留其 Fixed 高度策略
        # widget.setMaximumWidth(340)  # 限制最大宽度，避免横向滚动条

        # 插入到 stretch 之前
        count = self._history_layout.count()
        self._history_layout.insertWidget(count - 1, widget)

        # 限制历史数量
        while self._history_layout.count() > self._max_history + 1:  # +1 for stretch
            item = self._history_layout.itemAt(0)
            if item:
                w = item.widget()
                if w:
                    self._history_layout.removeWidget(w)
                    w.deleteLater()

        # 延迟更新布局，确保widget已完成布局
        QTimer.singleShot(10, self._update_geometry)
        QTimer.singleShot(50, self._scroll_to_bottom)

    def _update_geometry(self):
        """根据内容自适应调整窗口高度（仅在未手动调整大小时）"""
        # 如果用户已经在调整大小，或者是初始显示，我们可能不需要强制调整
        # 这里改为：如果内容很少，适应内容高度；如果内容很多，保持当前高度或最大高度
        pass
        # 移除强制 setFixedSize，允许用户调整

    def _scroll_to_bottom(self):
        scrollbar = self._scroll_area.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def update_streaming_response(self, content: str):
        """更新流式响应"""
        self._current_ai_message = content

        # 如果还没有创建AI消息，先创建一个
        if not self._current_ai_message_id:
            msg = self._chat_history.add_message(
                role="assistant", content=content, msg_type="text"
            )
            self._current_ai_message_id = msg.id

            # 显示消息
            if msg.id not in self._displayed_message_ids:
                self._displayed_message_ids.add(msg.id)
                label = self._display_ai_text(content, msg.id)
                if label:
                    self._current_ai_label = label
                    self._message_labels[msg.id] = label
        else:
            # 更新历史记录中的消息
            self._chat_history.update_message(self._current_ai_message_id, content)
            # 直接更新当前label
            if self._current_ai_label:
                self._current_ai_label.set_markdown(content)

        self._scroll_to_bottom()

    def _on_attach_clicked(self):
        """点击附件按钮"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "选择图片", "", "图片文件 (*.png *.jpg *.jpeg *.gif *.bmp *.webp)"
        )
        if file_path:
            self.set_attachment(file_path)

    # === 窗口调整大小逻辑 ===

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._resize_edge = self._check_edge(event.pos())
            if self._resize_edge:
                self._resizing = True
                self._last_pos = event.globalPosition().toPoint()
                event.accept()
            else:
                super().mousePressEvent(event)
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._resizing:
            delta = event.globalPosition().toPoint() - self._last_pos
            self._last_pos = event.globalPosition().toPoint()

            geo = self.geometry()
            new_geo = geo

            if self._resize_edge:
                if "left" in self._resize_edge:
                    new_geo.setLeft(geo.left() + delta.x())
                if "right" in self._resize_edge:
                    new_geo.setRight(geo.right() + delta.x())
                if "top" in self._resize_edge:
                    new_geo.setTop(geo.top() + delta.y())
                if "bottom" in self._resize_edge:
                    new_geo.setBottom(geo.bottom() + delta.y())

            # 检查最小尺寸
            if (
                new_geo.width() >= self.minimumWidth()
                and new_geo.height() >= self.minimumHeight()
            ):
                self.setGeometry(new_geo)

            event.accept()
        else:
            edge = self._check_edge(event.pos())
            if edge:
                if edge in ["left", "right"]:
                    self.setCursor(Qt.CursorShape.SizeHorCursor)
                elif edge in ["top", "bottom"]:
                    self.setCursor(Qt.CursorShape.SizeVerCursor)
                elif edge in ["top-left", "bottom-right"]:
                    self.setCursor(Qt.CursorShape.SizeFDiagCursor)
                elif edge in ["top-right", "bottom-left"]:
                    self.setCursor(Qt.CursorShape.SizeBDiagCursor)
            else:
                self.setCursor(Qt.CursorShape.ArrowCursor)
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._resizing = False
            self._resize_edge = None
        super().mouseReleaseEvent(event)

    def _check_edge(self, pos):
        """检查鼠标是否在边缘"""
        x = pos.x()
        y = pos.y()
        w = self.width()
        h = self.height()
        m = self._resize_margin

        edge = ""
        if y < m:
            edge += "top"
        elif y > h - m:
            edge += "bottom"

        if x < m:
            edge += ("-" if edge else "") + "left"
        elif x > w - m:
            edge += ("-" if edge else "") + "right"

        return edge if edge else None

    def finish_response(self):
        """响应结束"""
        self._is_waiting = False
        # 移除重新启用控件的代码，因为控件始终保持可用状态
        # self._send_btn.setEnabled(True)
        # self._input.setEnabled(True)
        # self._input.setFocus()

        # 保存最终内容
        if self._current_ai_message_id and self._current_ai_message:
            self._chat_history.update_message(
                self._current_ai_message_id, self._current_ai_message
            )

        self._current_ai_label = None
        self._current_ai_message_id = ""

        # 确保保存
        self._chat_history.save_to_file()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self.hide()
            event.accept()
        else:
            super().keyPressEvent(event)

    def set_auto_hide(self, enabled: bool, duration: int = 5000):
        """设置自动隐藏功能
        Args:
            enabled: 是否启用自动隐藏
            duration: 隐藏延迟时间（毫秒）
        """
        self._auto_hide_enabled = enabled
        self._auto_hide_duration = duration

    def _on_auto_hide_timeout(self):
        """自动隐藏超时回调"""
        if self._auto_hide_enabled and not self._is_waiting:
            self.hide()

    def enterEvent(self, event):
        """鼠标进入时停止自动隐藏"""
        self._auto_hide_timer.stop()
        super().enterEvent(event)

    def leaveEvent(self, event):
        """鼠标离开时重启自动隐藏"""
        if self._auto_hide_enabled and self.isVisible():
            self._auto_hide_timer.start(self._auto_hide_duration)
        super().leaveEvent(event)

    def showEvent(self, event):
        super().showEvent(event)
        self._input.setFocus()
        QTimer.singleShot(100, self._scroll_to_bottom)

        # macOS: 设置窗口置顶层级
        if sys.platform == "darwin":
            QTimer.singleShot(50, lambda: _set_macos_window_level(self))

        # 启动自动隐藏定时器
        if self._auto_hide_enabled:
            self._auto_hide_timer.start(self._auto_hide_duration)


class FloatingBallWindow(QWidget):
    """美化版悬浮球窗口"""

    # 信号
    clicked = Signal()
    double_clicked = Signal()
    settings_requested = Signal()
    restart_requested = Signal()
    quit_requested = Signal()
    screenshot_requested = Signal(str)
    message_sent = Signal(str)
    image_sent = Signal(str, str)

    def __init__(self, config=None, parent=None):
        super().__init__(parent)
        self.config = config or {}

        # 状态
        self._state = FloatingBallState.NORMAL

        # 未读消息状态
        self._has_unread = False
        self._pulse_phase = 0.0

        # 配置参数
        self.ball_size = 64
        self._glow_intensity = 0.0
        self._breathing = True
        self._scale_factor = 1.0

        # 窗口属性
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedSize(
            self.ball_size + 40, self.ball_size + 40
        )  # 增加预留边距以支持缩放

        # 缩放动画
        self._scale_animation = QPropertyAnimation(self, b"scale_factor_prop", self)
        self._scale_animation.setDuration(150)
        self._scale_animation.setEasingCurve(QEasingCurve.Type.OutBack)

        # 拖拽状态
        self._dragging = False
        self._drag_start_pos = QPoint()
        self._click_timer = QTimer()
        self._click_timer.setSingleShot(True)
        self._click_timer.timeout.connect(self._on_single_click)
        self._pending_click = False
        self._drag_threshold = 5  # 拖拽阈值
        self._double_click_interval = 300  # 双击检测间隔（毫秒）
        self._last_release_time = 0  # 上次释放时间（用于双击检测）

        # 自定义头像
        self._custom_avatar: Optional[QPixmap] = None
        self._avatar_path = ""

        # 加载头像
        if hasattr(self.config, "appearance"):
            appearance = getattr(self.config, "appearance")
            if hasattr(appearance, "avatar_path"):
                self._load_avatar(appearance.avatar_path)
            elif isinstance(appearance, dict) and "avatar_path" in appearance:
                self._load_avatar(appearance["avatar_path"])

        # 精简版对话窗口
        self._compact_window = CompactChatWindow(config=self.config)
        self._compact_window.message_sent.connect(self.message_sent)
        self._compact_window.image_sent.connect(self.image_sent)

        # 从配置加载用户和Bot头像并传递给精简窗口
        user_avatar_loaded = False
        bot_avatar_loaded = False

        if hasattr(self.config, "appearance"):
            appearance = getattr(self.config, "appearance")
            # 加载用户头像
            user_avatar = ""
            if hasattr(appearance, "user_avatar_path"):
                user_avatar = appearance.user_avatar_path or ""
            elif isinstance(appearance, dict) and "user_avatar_path" in appearance:
                user_avatar = appearance.get("user_avatar_path", "") or ""
            if user_avatar:
                self._compact_window.set_user_avatar(user_avatar)
                user_avatar_loaded = True

            # 加载Bot头像
            bot_avatar = ""
            if hasattr(appearance, "bot_avatar_path"):
                bot_avatar = getattr(appearance, "bot_avatar_path", "") or ""
            elif isinstance(appearance, dict) and "bot_avatar_path" in appearance:
                bot_avatar = appearance.get("bot_avatar_path", "") or ""
            # 如果没有bot_avatar_path，尝试使用旧的avatar_path
            if not bot_avatar:
                if hasattr(appearance, "avatar_path"):
                    bot_avatar = getattr(appearance, "avatar_path", "") or ""
                elif isinstance(appearance, dict) and "avatar_path" in appearance:
                    bot_avatar = appearance.get("avatar_path", "") or ""
            if bot_avatar:
                self._compact_window.set_bot_avatar(bot_avatar)
                bot_avatar_loaded = True

        # 如果头像已加载，立即刷新历史显示以确保头像正确显示
        if user_avatar_loaded or bot_avatar_loaded:
            # 使用更长的延迟确保头像已完全加载
            QTimer.singleShot(150, self._compact_window.reload_history_display)

        # 从配置加载自动隐藏设置
        if hasattr(self.config, "interaction"):
            interaction = getattr(self.config, "interaction")
            auto_hide = getattr(interaction, "bubble_auto_hide", False)
            duration = getattr(interaction, "bubble_duration", 5) * 1000  # 秒转毫秒
            self._compact_window.set_auto_hide(auto_hide, duration)

        # 呼吸灯动画
        self._breath_timer = QTimer(self)
        self._breath_timer.timeout.connect(self._update_breathing)
        self._breath_phase = 0.0
        self._breath_timer.start(30)  # ~33 FPS

        # 优化刷新：记录上次需要刷新的状态，避免无意义的 update
        self._needs_update = True

        # 悬停状态
        self._hovered = False

        # 初始位置
        self._move_to_default_position()

        # 注册主题回调
        theme_manager.register_callback(self._on_theme_changed)

    def get_scale_factor(self):
        return self._scale_factor

    def set_scale_factor(self, value):
        self._scale_factor = value
        self.update()

    scale_factor_prop = Property(float, get_scale_factor, set_scale_factor)

    def set_state(self, state: FloatingBallState):
        """设置状态"""
        if self._state != state:
            self._state = state
            self._needs_update = True
            self.update()

    def _on_theme_changed(self, theme: Theme):
        """主题变化"""
        self.update()

    def _load_avatar(self, avatar_path: str = ""):
        """加载自定义头像图片"""
        self._avatar_path = avatar_path
        if avatar_path and os.path.exists(avatar_path):
            pixmap = QPixmap(avatar_path)
            if not pixmap.isNull():
                # 缩放并裁剪为正方形
                size = min(pixmap.width(), pixmap.height())
                rect = pixmap.rect()
                if rect.width() > rect.height():
                    x = (rect.width() - size) // 2
                    pixmap = pixmap.copy(x, 0, size, size)
                elif rect.height() > rect.width():
                    y = (rect.height() - size) // 2
                    pixmap = pixmap.copy(0, y, size, size)

                self._custom_avatar = pixmap.scaled(
                    self.ball_size,
                    self.ball_size,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
        else:
            self._custom_avatar = None
        self.update()

    def set_avatar(self, avatar_path: str):
        """设置悬浮球头像"""
        self._load_avatar(avatar_path)

    def set_user_avatar(self, avatar_path: str):
        """设置用户头像（传递给精简窗口）"""
        self._compact_window.set_user_avatar(avatar_path)

    def set_bot_avatar(self, avatar_path: str):
        """设置Bot头像（传递给精简窗口）"""
        self._compact_window.set_bot_avatar(avatar_path)

    def add_user_message(self, text: str, image_path: Optional[str] = None):
        """添加用户消息（传递给精简窗口）"""
        self._compact_window.add_user_message(text, image_path)

    def _update_breathing(self):
        """更新呼吸灯效果"""
        should_update = False

        if self._breathing:
            self._breath_phase += 0.02
            if self._breath_phase > 2 * math.pi:
                self._breath_phase -= 2 * math.pi
            self._glow_intensity = (math.sin(self._breath_phase) + 1) / 2 * 0.4 + 0.3
            should_update = True

        # 未读消息脉冲动画（更快的频率）
        if self._has_unread:
            self._pulse_phase += 0.10  # 更快的脉冲
            if self._pulse_phase > 2 * math.pi:
                self._pulse_phase -= 2 * math.pi
            should_update = True

        # 如果状态不是 NORMAL，也需要刷新（可能有其他动画效果）
        if (
            self._state != FloatingBallState.NORMAL
            and self._state != FloatingBallState.DISCONNECTED
        ):
            should_update = True

        # 只有在需要时才调用 update，减少 CPU 占用和潜在的闪烁
        if should_update or self._needs_update:
            self.update()
            self._needs_update = False

    def _move_to_default_position(self):
        """移动到默认位置"""
        screen = QApplication.primaryScreen()
        if screen:
            geometry = screen.availableGeometry()
            x = geometry.right() - self.width() - 30
            y = geometry.center().y() - self.height() // 2
            self.move(x, y)

    def paintEvent(self, event):
        """绘制悬浮球"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        colors = (
            theme_manager.get_current_colors()
        )  # 使用 get_current_colors() 获取应用了自定义颜色的最终配置

        # 计算缩放后的尺寸
        current_size = self.ball_size * self._scale_factor

        center_x = self.width() // 2
        center_y = self.height() // 2
        radius = current_size // 2

        # 根据状态确定基础颜色
        if self._state == FloatingBallState.DISCONNECTED:
            base_color = QColor(colors.text_secondary)
            glow_color = QColor(colors.text_secondary)
            # 在断开连接状态下强制刷新以确保灰色显示
            if not self._breathing:
                self._needs_update = True
        elif self._state == FloatingBallState.BUSY:
            base_color = QColor(colors.warning)
            glow_color = QColor(colors.warning)
        elif self._state == FloatingBallState.PROCESSING:
            base_color = QColor(colors.primary)
            glow_color = QColor(colors.primary)
        else:  # NORMAL
            base_color = QColor(colors.primary)
            glow_color = QColor(colors.primary)

        # 1. 绘制外发光
        glow_intensity = self._glow_intensity
        if self._state == FloatingBallState.PROCESSING:
            # 处理中状态呼吸更快更明显
            glow_intensity = self._glow_intensity * 1.5

        glow_color.setAlphaF(min(1.0, glow_intensity * (0.8 if self._hovered else 0.5)))

        for i in range(10, 0, -2):
            glow = QRadialGradient(center_x, center_y, radius + i)
            glow_c = QColor(glow_color)
            glow_c.setAlphaF(glow_color.alphaF() * (1 - i / 12))
            glow.setColorAt(0.7, glow_c)
            glow.setColorAt(1.0, Qt.GlobalColor.transparent)

            painter.setBrush(QBrush(glow))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawEllipse(
                int(center_x - radius - i),
                int(center_y - radius - i),
                int((radius + i) * 2),
                int((radius + i) * 2),
            )

        # 2. 绘制主圆形背景（带渐变）
        gradient = QRadialGradient(
            center_x - radius * 0.3, center_y - radius * 0.3, radius * 1.5
        )

        if self._state == FloatingBallState.DISCONNECTED:
            gradient.setColorAt(0, base_color.lighter(120))
            gradient.setColorAt(1, base_color.darker(120))
        else:
            gradient.setColorAt(0, base_color.lighter(110))
            gradient.setColorAt(0.5, base_color)
            gradient.setColorAt(1, base_color.darker(110))

        painter.setBrush(QBrush(gradient))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(
            int(center_x - radius),
            int(center_y - radius),
            int(radius * 2),
            int(radius * 2),
        )

        # 3. 绘制内部高光
        highlight = QRadialGradient(
            center_x - radius * 0.2, center_y - radius * 0.3, radius * 0.6
        )
        highlight.setColorAt(0, QColor(255, 255, 255, 80))
        highlight.setColorAt(1, Qt.GlobalColor.transparent)

        painter.setBrush(QBrush(highlight))
        painter.drawEllipse(
            int(center_x - radius),
            int(center_y - radius),
            int(radius * 2),
            int(radius * 2),
        )

        # 4. 绘制头像或图标
        if self._custom_avatar and not self._custom_avatar.isNull():
            # 创建圆形裁剪路径
            path = QPainterPath()
            path.addEllipse(
                float(center_x - radius + 4),
                float(center_y - radius + 4),
                float((radius - 4) * 2),
                float((radius - 4) * 2),
            )
            painter.setClipPath(path)

            # 绘制头像
            avatar_size = (radius - 4) * 2
            painter.drawPixmap(
                int(center_x - radius + 4),
                int(center_y - radius + 4),
                int(avatar_size),
                int(avatar_size),
                self._custom_avatar,
            )
            painter.setClipping(False)

            # 如果是断开连接，添加灰色遮罩
            if self._state == FloatingBallState.DISCONNECTED:
                painter.setBrush(QColor(0, 0, 0, 100))
                painter.drawEllipse(
                    int(center_x - radius + 4),
                    int(center_y - radius + 4),
                    int((radius - 4) * 2),
                    int((radius - 4) * 2),
                )
        else:
            # 绘制默认SVG图标
            # 根据状态选择图标
            icon_name = "bot"
            if self._state == FloatingBallState.DISCONNECTED:
                icon_name = "zap-off"
            elif self._state == FloatingBallState.BUSY:
                icon_name = "message-square"
            elif self._state == FloatingBallState.PROCESSING:
                icon_name = "refresh-cw"

            # 获取白色图标（确保在彩色背景上清晰可见）
            icon_size = int(radius * 1.2)  # 图标大小约为半径的1.2倍
            icon_pixmap = icon_manager.get_pixmap(icon_name, "#FFFFFF", icon_size)

            # 居中绘制图标
            icon_x = center_x - icon_size // 2
            icon_y = center_y - icon_size // 2
            painter.drawPixmap(int(icon_x), int(icon_y), icon_pixmap)

            # 绘制状态小红点 (如果不是正常状态且有自定义头像时)
            if self._state != FloatingBallState.NORMAL and self._custom_avatar:
                status_radius = 6
                status_color = Qt.GlobalColor.red
                if self._state == FloatingBallState.BUSY:
                    status_color = colors.warning
                elif self._state == FloatingBallState.PROCESSING:
                    status_color = colors.primary
                elif self._state == FloatingBallState.DISCONNECTED:
                    status_color = colors.text_secondary

                painter.setBrush(status_color)
                painter.setPen(Qt.PenStyle.NoPen)
                # 右下角
                status_x = center_x + radius * 0.7
                status_y = center_y + radius * 0.7
                painter.drawEllipse(
                    QPoint(int(status_x), int(status_y)), status_radius, status_radius
                )

        # 6. 绘制未读消息指示器（红点 + 脉冲效果）
        if self._has_unread:
            # 脉冲缩放效果
            pulse_scale = 1.0 + 0.3 * math.sin(self._pulse_phase)
            dot_radius = int(8 * pulse_scale)

            # 红点位置：右上角
            dot_x = center_x + radius * 0.6
            dot_y = center_y - radius * 0.6

            # 绘制外发光
            pulse_alpha = int(100 + 80 * math.sin(self._pulse_phase))
            glow_color = QColor(255, 80, 80, pulse_alpha)
            for i in range(4, 0, -1):
                painter.setBrush(QColor(255, 80, 80, int(pulse_alpha * (1 - i / 5))))
                painter.setPen(Qt.PenStyle.NoPen)
                painter.drawEllipse(
                    QPoint(int(dot_x), int(dot_y)),
                    dot_radius + i * 2,
                    dot_radius + i * 2,
                )

            # 绘制红点主体
            painter.setBrush(QColor(255, 80, 80))
            painter.setPen(QPen(QColor(255, 255, 255, 200), 2))
            painter.drawEllipse(QPoint(int(dot_x), int(dot_y)), dot_radius, dot_radius)

        # 5. 绘制边框
        if self._hovered:
            border_pen = QPen(QColor(255, 255, 255, 150))
            border_pen.setWidth(2)
            painter.setPen(border_pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawEllipse(
                int(center_x - radius + 1),
                int(center_y - radius + 1),
                int((radius - 1) * 2),
                int((radius - 1) * 2),
            )

    def enterEvent(self, event):
        """鼠标进入"""
        self._hovered = True
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        # 缩放动画
        self._scale_animation.stop()
        self._scale_animation.setStartValue(self._scale_factor)
        self._scale_animation.setEndValue(1.1)
        self._scale_animation.start()

    def leaveEvent(self, event):
        """鼠标离开"""
        self._hovered = False
        self.setCursor(Qt.CursorShape.ArrowCursor)

        # 恢复大小
        self._scale_animation.stop()
        self._scale_animation.setStartValue(self._scale_factor)
        self._scale_animation.setEndValue(1.0)
        self._scale_animation.start()

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton:
            self._dragging = True
            self._drag_start_pos = event.globalPosition().toPoint() - self.pos()
            self._press_global_pos = event.globalPosition().toPoint()
            self._has_moved_significantly = False
            event.accept()
        elif event.button() == Qt.MouseButton.RightButton:
            self._show_context_menu(event.globalPosition().toPoint())
            event.accept()

    def mouseMoveEvent(self, event: QMouseEvent):
        if self._dragging:
            current_global_pos = event.globalPosition().toPoint()

            # 检查是否移动超过阈值
            if not self._has_moved_significantly:
                distance = (
                    current_global_pos - self._press_global_pos
                ).manhattanLength()
                if distance > self._drag_threshold:
                    self._has_moved_significantly = True

            # 移动窗口
            new_pos = current_global_pos - self._drag_start_pos
            self.move(new_pos)

            # 移动窗口跟随
            if not self._compact_window.isHidden():
                self._update_compact_window_position()
            event.accept()

    def mouseReleaseEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton:
            self._dragging = False

            # 判断是否是点击（没有显著移动）
            if not getattr(self, "_has_moved_significantly", False):
                from PySide6.QtCore import QDateTime

                current_time = QDateTime.currentMSecsSinceEpoch()

                # 检查是否是双击的第二次释放
                time_since_last = current_time - self._last_release_time

                if time_since_last < self._double_click_interval:
                    # 这是双击的第二次释放，双击已在 mouseDoubleClickEvent 中处理
                    # 停止可能存在的单击定时器
                    self._click_timer.stop()
                    self._pending_click = False
                else:
                    # 这是单击，或双击的第一次释放
                    # 启动定时器等待可能的第二次点击
                    self._pending_click = True
                    self._click_timer.start(self._double_click_interval)

                self._last_release_time = current_time

            event.accept()

    def mouseDoubleClickEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton:
            # 停止单击定时器，防止单击也被触发
            self._click_timer.stop()
            self._pending_click = False

            # 发射双击信号
            self.double_clicked.emit()
            event.accept()

    def _on_single_click(self):
        if self._pending_click:
            self._pending_click = False
            self.clicked.emit()

    def _show_context_menu(self, pos: QPoint):
        """右键菜单"""
        menu = QMenu(self)

        # 应用主题样式
        c = (
            theme_manager.get_current_colors()
        )  # 使用 get_current_colors() 获取应用了自定义颜色的最终配置
        menu.setStyleSheet(f"""
            QMenu {{
                background-color: {c.bg_primary};
                border: 1px solid {c.border_light};
                border-radius: 8px;
                padding: 6px;
            }}
            QMenu::item {{
                padding: 8px 20px 8px 12px;
                border-radius: 4px;
                color: {c.text_primary};
            }}
            QMenu::item:selected {{
                background-color: {c.bg_hover};
            }}
            QMenu::separator {{
                height: 1px;
                background-color: {c.border_light};
                margin: 4px 8px;
            }}
        """)

        # 截图功能
        region_screenshot_action = menu.addAction("区域截图")
        region_screenshot_action.setIcon(
            icon_manager.get_icon("screenshot", c.text_primary, 16)
        )
        region_screenshot_action.triggered.connect(self._on_region_screenshot)

        full_screenshot_action = menu.addAction("全屏截图")
        full_screenshot_action.setIcon(
            icon_manager.get_icon("screenshot", c.text_primary, 16)
        )
        full_screenshot_action.triggered.connect(self._on_full_screenshot)

        menu.addSeparator()

        # 主题子菜单
        theme_menu = menu.addMenu("切换主题")
        theme_menu.setIcon(icon_manager.get_icon("theme", c.text_primary, 16))
        theme_menu.setStyleSheet(menu.styleSheet())

        for theme_name, display_name in theme_manager.get_theme_names():
            action = theme_menu.addAction(display_name)
            action.triggered.connect(
                lambda checked, n=theme_name: theme_manager.set_theme(n)
            )

        menu.addSeparator()

        restart_action = menu.addAction("重启")
        restart_action.setIcon(icon_manager.get_icon("restart", c.text_primary, 16))
        restart_action.triggered.connect(self.restart_requested.emit)

        settings_action = menu.addAction("设置")
        settings_action.setIcon(icon_manager.get_icon("settings", c.text_primary, 16))
        settings_action.triggered.connect(self.settings_requested.emit)

        quit_action = menu.addAction("退出")
        quit_action.setIcon(icon_manager.get_icon("exit", c.danger, 16))
        quit_action.triggered.connect(self.quit_requested.emit)

        menu.exec(pos)

    def _on_region_screenshot(self):
        """区域截图"""
        try:
            self.hide()
            QTimer.singleShot(100, self._start_region_capture)
        except ImportError as e:
            print(f"区域截图功能不可用: {e}")

    def _start_region_capture(self):
        """开始区域截图"""
        try:
            from .screenshot_selector import RegionScreenshotCapture

            self._capture = RegionScreenshotCapture()
            self._capture.capture_async(self._on_screenshot_complete)
        except Exception as e:
            print(f"启动区域截图失败: {e}")
            self.show()

    def _on_full_screenshot(self):
        """全屏截图"""
        try:
            self.hide()
            QTimer.singleShot(100, self._do_full_screenshot)
        except ImportError as e:
            print(f"截图功能不可用: {e}")

    def _do_full_screenshot(self):
        """执行全屏截图"""
        try:
            service = ScreenCaptureService()
            screenshot_path = service.capture_full_screen_to_file()

            self.show()

            if screenshot_path:
                self.screenshot_requested.emit(screenshot_path)
        except Exception as e:
            print(f"全屏截图失败: {e}")
            self.show()

    def _on_screenshot_complete(self, screenshot_path):
        """截图完成回调"""
        self.show()

        if screenshot_path:
            self.screenshot_requested.emit(screenshot_path)

    def show_bubble(self, text: str, duration: int = 0):
        """显示气泡 (实际显示在精简窗口中)"""
        self._update_compact_window_position()
        self._compact_window.add_ai_message(text)
        self._compact_window.show()

    def show_system_message(self, text: str):
        """显示系统消息 (显示在精简窗口中，不强制弹窗)"""
        self._compact_window.add_system_message(text)

    def toggle_input(self):
        """切换输入框显示/隐藏"""
        if self._compact_window.isVisible():
            self._compact_window.hide()
        else:
            self.show_input()

    def show_input(self):
        """显示输入框 (显示精简窗口)"""
        self._update_compact_window_position()
        self._compact_window.show()
        self._compact_window.activateWindow()

    def _update_compact_window_position(self):
        """更新精简窗口位置"""
        w = self._compact_window.width()
        h = self._compact_window.height()

        # 默认显示在左侧
        x = self.x() - w - 10
        y = self.y() + (self.height() - h) // 2

        # 如果左侧空间不足，显示在右侧
        if x < 0:
            x = self.x() + self.width() + 10

        self._compact_window.move(x, y)

    # === 代理方法供外部调用 ===

    def is_waiting_response(self) -> bool:
        return self._compact_window._is_waiting

    def update_streaming_response(self, content: str):
        self._compact_window.update_streaming_response(content)

    def finish_response(self):
        self._compact_window.finish_response()

    def set_attachment(self, path: str):
        self._compact_window.set_attachment(path)

    def set_breathing(self, enabled: bool):
        """设置呼吸灯效果"""
        self._breathing = enabled
        if not enabled:
            self._glow_intensity = 0.3
            self.update()

    def set_unread_message(self, has_unread: bool = True):
        """设置未读消息状态"""
        if self._has_unread != has_unread:
            self._has_unread = has_unread
            if has_unread:
                self._pulse_phase = 0.0  # 重置脉冲相位
            self.update()

    def clear_unread_message(self):
        """清除未读消息状态"""
        self.set_unread_message(False)

    def has_unread_message(self) -> bool:
        """检查是否有未读消息"""
        return self._has_unread

    def showEvent(self, event):
        """窗口显示事件"""
        super().showEvent(event)

        # macOS: 设置窗口置顶层级
        if sys.platform == "darwin":
            QTimer.singleShot(50, lambda: _set_macos_window_level(self))
