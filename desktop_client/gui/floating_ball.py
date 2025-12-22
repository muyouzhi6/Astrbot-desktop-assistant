"""
美化版悬浮球窗口

提供可拖拽的圆形悬浮窗口，支持：
- 自定义头像图片
- 主题配色
- 呼吸灯动画效果
- 单击显示气泡对话
- 双击打开对话窗口
- 右键菜单
"""

from typing import Callable, Optional
import os
import math
from enum import Enum

from PySide6.QtCore import (
    Qt, QPoint, QTimer, Signal, QPropertyAnimation,
    QEasingCurve, Property, QSize, QRectF
)
from PySide6.QtGui import (
    QPixmap, QPainter, QBrush, QColor, QMouseEvent,
    QFont, QPen, QLinearGradient, QRadialGradient,
    QPainterPath
)
from PySide6.QtWidgets import QWidget, QLabel, QVBoxLayout, QHBoxLayout, QPushButton, QMenu, QApplication, QFrame

from .themes import theme_manager, Theme
from .simple_chat_window import PasteAwareTextEdit
from .markdown_utils import MarkdownLabel


class FloatingBallState(Enum):
    """悬浮球状态"""
    NORMAL = "normal"           # 正常
    BUSY = "busy"               # 忙碌 (如正在思考)
    PROCESSING = "processing"   # 处理中 (如语音识别中)
    DISCONNECTED = "disconnected" # 断开连接
    UNREAD_MESSAGE = "unread_message"  # 有未读消息


from PySide6.QtWidgets import QWidget, QLabel, QVBoxLayout, QMenu, QApplication, QTextEdit, QScrollArea, QDialog, QGraphicsView, QGraphicsScene, QGraphicsPixmapItem
from PySide6.QtGui import QClipboard

class ClickableImageLabel(QLabel):
    """可点击的图片标签，支持点击放大和右键复制"""
    
    clicked = Signal()
    
    def __init__(self, image_path: str = "", parent=None):
        super().__init__(parent)
        self._image_path = image_path
        self._original_pixmap: Optional[QPixmap] = None
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_context_menu)
        # 连接点击信号到预览方法
        self.clicked.connect(self._show_preview)
        
        if image_path:
            self.load_image(image_path)
            
    def load_image(self, image_path: str, max_size: int = 200):
        """加载并缩放图片"""
        self._image_path = image_path
        if os.path.exists(image_path):
            pixmap = QPixmap(image_path)
            if not pixmap.isNull():
                self._original_pixmap = pixmap
                # 缩放为缩略图
                scaled = pixmap.scaled(
                    max_size, 150,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation
                )
                self.setPixmap(scaled)
                
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)
        
    def _show_context_menu(self, pos):
        """显示右键菜单"""
        menu = QMenu(self)
        
        # 应用主题样式
        t = theme_manager.current_theme
        c = t.colors
        menu.setStyleSheet(f"""
            QMenu {{
                background-color: {c.bg_primary};
                border: 1px solid {c.border_light};
                border-radius: 8px;
                padding: 4px;
            }}
            QMenu::item {{
                padding: 6px 16px;
                border-radius: 4px;
                color: {c.text_primary};
            }}
            QMenu::item:selected {{
                background-color: {c.bg_hover};
            }}
        """)
        
        copy_action = menu.addAction("📋 复制图片")
        copy_action.triggered.connect(self._copy_to_clipboard)
        
        view_action = menu.addAction("🔍 查看大图")
        view_action.triggered.connect(self._show_preview)
        
        menu.exec(self.mapToGlobal(pos))
        
    def _copy_to_clipboard(self):
        """复制图片到剪贴板"""
        if self._original_pixmap and not self._original_pixmap.isNull():
            clipboard = QApplication.clipboard()
            clipboard.setPixmap(self._original_pixmap)
            
    def _show_preview(self):
        """显示大图预览"""
        if self._original_pixmap and not self._original_pixmap.isNull():
            dialog = ImagePreviewDialog(self._original_pixmap, self._image_path, self.window())
            dialog.exec()


class ImagePreviewDialog(QDialog):
    """图片预览对话框"""
    
    def __init__(self, pixmap: QPixmap, image_path: str = "", parent=None):
        super().__init__(parent)
        self._pixmap = pixmap
        self._image_path = image_path
        
        self.setWindowTitle("图片预览")
        self.setModal(True)
        self.setMinimumSize(400, 300)
        
        # 设置窗口标志，确保对话框在最前面显示
        self.setWindowFlags(
            Qt.WindowType.Dialog |
            Qt.WindowType.WindowCloseButtonHint |
            Qt.WindowType.WindowTitleHint
        )
        
        # 计算合适的窗口大小和位置
        dialog_width = 800
        dialog_height = 600
        
        screen = QApplication.primaryScreen()
        if screen:
            screen_rect = screen.availableGeometry()
            # 窗口最大为屏幕的 80%
            max_w = int(screen_rect.width() * 0.8)
            max_h = int(screen_rect.height() * 0.8)
            
            img_w = pixmap.width()
            img_h = pixmap.height()
            
            # 如果图片比最大尺寸小，使用图片原尺寸加一点边距
            if img_w < max_w and img_h < max_h:
                dialog_width = min(img_w + 40, max_w)
                dialog_height = min(img_h + 80, max_h)
            else:
                dialog_width = max_w
                dialog_height = max_h
                
            self.resize(dialog_width, dialog_height)
            
            # 居中显示 - 使用 availableGeometry 确保在可见区域内
            center_x = screen_rect.x() + (screen_rect.width() - dialog_width) // 2
            center_y = screen_rect.y() + (screen_rect.height() - dialog_height) // 2
            self.move(center_x, center_y)
        else:
            self.resize(dialog_width, dialog_height)
        
        # 主布局
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # 使用 QGraphicsView 显示图片，支持缩放
        self._scene = QGraphicsScene()
        self._view = QGraphicsView(self._scene)
        self._view.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self._view.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        self._view.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self._view.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        
        # 添加图片到场景
        self._pixmap_item = QGraphicsPixmapItem(pixmap)
        self._scene.addItem(self._pixmap_item)
        
        layout.addWidget(self._view, 1)
        
        # 底部按钮区
        btn_frame = QFrame()
        btn_layout = QHBoxLayout(btn_frame)
        btn_layout.setContentsMargins(12, 8, 12, 8)
        
        # 复制按钮
        copy_btn = QPushButton("📋 复制到剪贴板")
        copy_btn.clicked.connect(self._copy_to_clipboard)
        
        # 下载按钮
        download_btn = QPushButton("💾 下载图片")
        download_btn.clicked.connect(self._download_image)
        
        # 适应窗口按钮
        fit_btn = QPushButton("📐 适应窗口")
        fit_btn.clicked.connect(self._fit_to_window)
        
        # 原始大小按钮
        original_btn = QPushButton("1:1 原始大小")
        original_btn.clicked.connect(self._show_original_size)
        
        # 关闭按钮
        close_btn = QPushButton("关闭")
        close_btn.clicked.connect(self.close)
        
        btn_layout.addWidget(copy_btn)
        btn_layout.addWidget(download_btn)
        btn_layout.addWidget(fit_btn)
        btn_layout.addWidget(original_btn)
        btn_layout.addStretch()
        btn_layout.addWidget(close_btn)
        
        layout.addWidget(btn_frame)
        
        # 应用主题
        self._apply_theme()
        
        # 默认适应窗口显示
        QTimer.singleShot(50, self._fit_to_window)
        
    def _apply_theme(self):
        """应用主题样式"""
        t = theme_manager.current_theme
        c = t.colors
        
        self.setStyleSheet(f"""
            QDialog {{
                background-color: {c.bg_primary};
            }}
            QGraphicsView {{
                background-color: {c.bg_secondary};
                border: none;
            }}
            QPushButton {{
                background-color: {c.bg_secondary};
                color: {c.text_primary};
                border: 1px solid {c.border_light};
                border-radius: 6px;
                padding: 8px 16px;
                font-size: {t.font_size_base}px;
            }}
            QPushButton:hover {{
                background-color: {c.bg_hover};
            }}
        """)
        
    def _copy_to_clipboard(self):
        """复制图片到剪贴板"""
        clipboard = QApplication.clipboard()
        clipboard.setPixmap(self._pixmap)
        
    def _download_image(self):
        """下载图片到本地"""
        from PySide6.QtWidgets import QFileDialog
        
        # 确定默认文件名
        default_name = "image.png"
        if self._image_path and os.path.exists(self._image_path):
            default_name = os.path.basename(self._image_path)
        
        # 打开保存对话框
        file_path, selected_filter = QFileDialog.getSaveFileName(
            self,
            "保存图片",
            default_name,
            "PNG 图片 (*.png);;JPEG 图片 (*.jpg *.jpeg);;所有文件 (*.*)"
        )
        
        if file_path:
            # 根据扩展名确定格式
            ext = os.path.splitext(file_path)[1].lower()
            if ext in ['.jpg', '.jpeg']:
                self._pixmap.save(file_path, "JPEG", 95)
            else:
                self._pixmap.save(file_path, "PNG")
        
    def _fit_to_window(self):
        """适应窗口显示"""
        self._view.fitInView(self._pixmap_item, Qt.AspectRatioMode.KeepAspectRatio)
        
    def _show_original_size(self):
        """显示原始大小"""
        self._view.resetTransform()
        
    def wheelEvent(self, event):
        """鼠标滚轮缩放"""
        factor = 1.15
        if event.angleDelta().y() > 0:
            self._view.scale(factor, factor)
        else:
            self._view.scale(1 / factor, 1 / factor)


class CompactChatWindow(QWidget):
    """精简版对话窗口 - 替代原有的气泡和输入框，提供统一体验"""
    
    message_sent = Signal(str)
    image_sent = Signal(str, str) # path, text
    closed = Signal()
    
    def __init__(self, parent=None, max_history: int = 50):
        super().__init__(parent)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        
        self._max_history = max_history
        self._message_history = [] # [(msg_type, content, is_user), ...]
        self._attachment_path = None
        self._is_waiting = False
        self._current_ai_message = ""
        self._current_ai_label = None # 当前 AI 回复的 MarkdownLabel
        
        # 主容器
        self._container = QFrame()
        self._container.setObjectName("compactContainer")
        
        # 主布局
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(self._container)
        
        # 容器内布局
        container_layout = QVBoxLayout(self._container)
        container_layout.setContentsMargins(12, 12, 12, 12)
        container_layout.setSpacing(8)
        
        # 1. 顶部栏 (标题 + 关闭)
        top_bar = QHBoxLayout()
        top_bar.setContentsMargins(0, 0, 0, 0)
        
        self._title_label = QLabel("AstrBot")
        self._title_label.setObjectName("compactTitle")
        top_bar.addWidget(self._title_label)
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
        self._scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        
        # 自适应尺寸，不再设置固定最小/最大大小
        self.setMinimumWidth(320)
        self.setMaximumWidth(400)
        
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
        self._remove_attachment_btn.setStyleSheet("background: rgba(255,0,0,0.7); color: white; border-radius: 9px; border: none;")
        
        preview_layout.addWidget(self._preview_label)
        preview_layout.addWidget(self._remove_attachment_btn)
        preview_layout.addStretch()
        container_layout.addWidget(self._preview_frame)
        
        # 4. 输入框 + 发送按钮
        input_layout = QHBoxLayout()
        input_layout.setSpacing(8)
        
        self._input = PasteAwareTextEdit()
        self._input.setPlaceholderText("输入消息...")
        self._input.setFixedHeight(40)
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
        
        # 应用主题
        self._apply_theme()
        theme_manager.register_callback(self._on_theme_changed)
        
    def _on_theme_changed(self, theme: Theme):
        self._apply_theme()
        
    def _apply_theme(self):
        t = theme_manager.current_theme
        c = t.colors
        
        # 容器
        self._container.setStyleSheet(f"""
            QFrame#compactContainer {{
                background-color: {c.bg_primary};
                border: 1px solid {c.border_light};
                border-radius: {t.border_radius + 4}px;
            }}
        """)
        
        # 标题
        self._title_label.setStyleSheet(f"""
            QLabel#compactTitle {{
                color: {c.text_secondary};
                font-weight: bold;
                font-size: {t.font_size_small}px;
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
        
        # 刷新所有历史消息的样式 (主要是 MarkdownLabel)
        for i in range(self._history_layout.count()):
            item = self._history_layout.itemAt(i)
            if item and item.widget():
                widget = item.widget()
                if isinstance(widget, MarkdownLabel):
                    widget.update_theme()
                elif isinstance(widget, QLabel):
                    # 更新用户消息颜色
                    widget.setStyleSheet(f"""
                        QLabel {{
                            color: {c.text_primary};
                            background-color: {c.bg_secondary};
                            border-radius: 8px;
                            padding: 8px;
                        }}
                    """)

    def _on_close(self):
        self.hide()
        self.closed.emit()
        
    def set_attachment(self, path: str):
        if not path or not os.path.exists(path):
            return
        self._attachment_path = path
        pixmap = QPixmap(path)
        if not pixmap.isNull():
            self._preview_label.setPixmap(pixmap.scaled(
                100, 40, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation
            ))
            self._preview_frame.setVisible(True)
            
    def clear_attachment(self):
        self._attachment_path = None
        self._preview_frame.setVisible(False)
        
    def _send(self):
        text = self._input.toPlainText().strip()
        if not text and not self._attachment_path:
            return
            
        if self._attachment_path:
            self.add_user_message(text or "[图片]", image_path=self._attachment_path)
            self.image_sent.emit(self._attachment_path, text)
            self.clear_attachment()
        else:
            self.add_user_message(text)
            self.message_sent.emit(text)
            
        self._input.clear()
        self._start_waiting()
        
    def _start_waiting(self):
        self._is_waiting = True
        self._send_btn.setEnabled(False)
        self._input.setEnabled(False)
        
        # 添加一个空的 AI 消息占位
        self._current_ai_message = "..."
        self._current_ai_label = self.add_ai_message("...")
        
    def add_user_message(self, text: str, image_path: Optional[str] = None):
        """添加用户消息"""
        container = QWidget()
        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addStretch() # 右对齐
        
        if image_path:
            lbl = ClickableImageLabel(image_path)
        else:
            lbl = QLabel(text)
            lbl.setWordWrap(True)
            t = theme_manager.current_theme
            c = t.colors
            lbl.setStyleSheet(f"""
                QLabel {{
                    color: {c.text_primary};
                    background-color: {c.bg_secondary};
                    border-radius: 8px;
                    padding: 8px;
                    max-width: 260px;
                }}
            """)
            
        layout.addWidget(lbl)
        self._add_to_history(container)
        
    def add_ai_message(self, text: str):
        """添加 AI 消息 (Markdown)"""
        container = QWidget()
        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # 机器人头像
        avatar = QLabel("🤖")
        avatar.setFixedSize(24, 24)
        avatar.setStyleSheet("font-size: 16px;")
        layout.addWidget(avatar, alignment=Qt.AlignmentFlag.AlignTop)
        
        # Markdown 内容
        md_label = MarkdownLabel(text, parent=container)
        md_label.setMaximumWidth(280) # 限制宽度
        layout.addWidget(md_label)
        layout.addStretch()
        
        self._add_to_history(container)
        return md_label
        
    def _add_to_history(self, widget: QWidget):
        # 插入到 stretch 之前
        count = self._history_layout.count()
        self._history_layout.insertWidget(count - 1, widget)
        
        # 限制历史数量
        while self._history_layout.count() > self._max_history + 1: # +1 for stretch
            item = self._history_layout.itemAt(0)
            if item and item.widget():
                w = item.widget()
                self._history_layout.removeWidget(w)
                w.deleteLater()
                
        self._update_geometry()
        QTimer.singleShot(50, self._scroll_to_bottom)
    
    def _update_geometry(self):
        """根据内容自适应调整窗口高度"""
        # 计算内容高度
        content_height = self._history_widget.sizeHint().height()
        
        # 基础高度（标题栏 + 输入框等）
        base_height = 100
        if self._preview_frame.isVisible():
            base_height += 50
            
        target_height = content_height + base_height
        
        # 限制高度范围
        min_height = 200
        max_height = 600
        
        final_height = max(min(target_height, max_height), min_height)
        
        self.resize(self.width(), final_height)

    def _scroll_to_bottom(self):
        scrollbar = self._scroll_area.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def update_streaming_response(self, content: str):
        """更新流式响应"""
        if self._current_ai_label:
            self._current_ai_message = content
            self._current_ai_label.set_markdown(content)
            self._scroll_to_bottom()
            
    def finish_response(self):
        """响应结束"""
        self._is_waiting = False
        self._send_btn.setEnabled(True)
        self._input.setEnabled(True)
        self._input.setFocus()
        self._current_ai_label = None

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self.hide()
            event.accept()
        else:
            super().keyPressEvent(event)
            
    def showEvent(self, event):
        super().showEvent(event)
        self._input.setFocus()
        QTimer.singleShot(100, self._scroll_to_bottom)


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

    def __init__(
        self,
        config=None,
        parent=None
    ):
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
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedSize(self.ball_size + 40, self.ball_size + 40)  # 增加预留边距以支持缩放
        
        # 缩放动画
        self._scale_animation = QPropertyAnimation(self, b"scale_factor_prop", self)
        self._scale_animation.setDuration(150)
        self._scale_animation.setEasingCurve(QEasingCurve.OutBack)
        
        # 拖拽状态
        self._dragging = False
        self._drag_start_pos = QPoint()
        self._click_timer = QTimer()
        self._click_timer.setSingleShot(True)
        self._click_timer.timeout.connect(self._on_single_click)
        self._pending_click = False
        self._drag_threshold = 5 # 拖拽阈值
        self._double_click_interval = 300  # 双击检测间隔（毫秒）
        self._last_release_time = 0  # 上次释放时间（用于双击检测）
        
        # 自定义头像
        self._custom_avatar: Optional[QPixmap] = None
        self._avatar_path = ""
        
        # 加载头像
        if hasattr(self.config, 'appearance'):
            appearance = getattr(self.config, 'appearance')
            if hasattr(appearance, 'avatar_path'):
                self._load_avatar(appearance.avatar_path)
            elif isinstance(appearance, dict) and 'avatar_path' in appearance:
                 self._load_avatar(appearance['avatar_path'])
        
        # 精简版对话窗口
        self._compact_window = CompactChatWindow()
        self._compact_window.message_sent.connect(self.message_sent)
        self._compact_window.image_sent.connect(self.image_sent)
        
        # 呼吸灯动画
        self._breath_timer = QTimer(self)
        self._breath_timer.timeout.connect(self._update_breathing)
        self._breath_phase = 0.0
        self._breath_timer.start(50)  # 20 FPS
        
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
                    self.ball_size, self.ball_size,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation
                )
        else:
            self._custom_avatar = None
        self.update()
        
    def set_avatar(self, avatar_path: str):
        """设置头像"""
        self._load_avatar(avatar_path)
        
    def _update_breathing(self):
        """更新呼吸灯效果"""
        if self._breathing:
            self._breath_phase += 0.08
            if self._breath_phase > 2 * math.pi:
                self._breath_phase -= 2 * math.pi
            self._glow_intensity = (math.sin(self._breath_phase) + 1) / 2 * 0.4 + 0.3
        
        # 未读消息脉冲动画（更快的频率）
        if self._has_unread:
            self._pulse_phase += 0.15  # 更快的脉冲
            if self._pulse_phase > 2 * math.pi:
                self._pulse_phase -= 2 * math.pi
        
        self.update()
        
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
        
        theme = theme_manager.current_theme
        colors = theme.colors
        
        # 计算缩放后的尺寸
        current_size = self.ball_size * self._scale_factor
        
        center_x = self.width() // 2
        center_y = self.height() // 2
        radius = current_size // 2
        
        # 根据状态确定基础颜色
        if self._state == FloatingBallState.DISCONNECTED:
            base_color = QColor(colors.text_secondary)
            glow_color = QColor(colors.text_secondary)
        elif self._state == FloatingBallState.BUSY:
            base_color = QColor(colors.warning)
            glow_color = QColor(colors.warning)
        elif self._state == FloatingBallState.PROCESSING:
            base_color = QColor(colors.primary)
            glow_color = QColor(colors.primary)
        else: # NORMAL
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
                center_x - radius - i,
                center_y - radius - i,
                (radius + i) * 2,
                (radius + i) * 2
            )
        
        # 2. 绘制主圆形背景（带渐变）
        gradient = QRadialGradient(center_x - radius * 0.3, center_y - radius * 0.3, radius * 1.5)
        
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
            center_x - radius,
            center_y - radius,
            radius * 2,
            radius * 2
        )
        
        # 3. 绘制内部高光
        highlight = QRadialGradient(center_x - radius * 0.2, center_y - radius * 0.3, radius * 0.6)
        highlight.setColorAt(0, QColor(255, 255, 255, 80))
        highlight.setColorAt(1, Qt.GlobalColor.transparent)
        
        painter.setBrush(QBrush(highlight))
        painter.drawEllipse(
            center_x - radius,
            center_y - radius,
            radius * 2,
            radius * 2
        )
        
        # 4. 绘制头像或图标
        if self._custom_avatar and not self._custom_avatar.isNull():
            # 创建圆形裁剪路径
            path = QPainterPath()
            path.addEllipse(
                center_x - radius + 4,
                center_y - radius + 4,
                (radius - 4) * 2,
                (radius - 4) * 2
            )
            painter.setClipPath(path)
            
            # 绘制头像
            avatar_size = (radius - 4) * 2
            painter.drawPixmap(
                int(center_x - radius + 4),
                int(center_y - radius + 4),
                int(avatar_size),
                int(avatar_size),
                self._custom_avatar
            )
            painter.setClipping(False)
            
            # 如果是断开连接，添加灰色遮罩
            if self._state == FloatingBallState.DISCONNECTED:
                painter.setBrush(QColor(0, 0, 0, 100))
                painter.drawEllipse(
                    center_x - radius + 4,
                    center_y - radius + 4,
                    (radius - 4) * 2,
                    (radius - 4) * 2
                )
        else:
            # 绘制默认图标
            painter.setPen(QColor(255, 255, 255))
            font = QFont("Segoe UI Emoji", int(radius))
            painter.setFont(font)
            
            icon_text = "🤖"
            if self._state == FloatingBallState.DISCONNECTED:
                icon_text = "🔌"
            elif self._state == FloatingBallState.BUSY:
                icon_text = "💭"
            elif self._state == FloatingBallState.PROCESSING:
                icon_text = "✨"
                
            painter.drawText(
                QRectF(center_x - radius, center_y - radius, radius * 2, radius * 2),
                Qt.AlignmentFlag.AlignCenter,
                icon_text
            )
            
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
                 painter.drawEllipse(QPoint(int(status_x), int(status_y)), status_radius, status_radius)
        
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
                painter.drawEllipse(QPoint(int(dot_x), int(dot_y)), dot_radius + i * 2, dot_radius + i * 2)
            
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
                center_x - radius + 1,
                center_y - radius + 1,
                (radius - 1) * 2,
                (radius - 1) * 2
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
                distance = (current_global_pos - self._press_global_pos).manhattanLength()
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
            if not getattr(self, '_has_moved_significantly', False):
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
        t = theme_manager.current_theme
        c = t.colors
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
        
        open_action = menu.addAction("💬 打开对话")
        open_action.triggered.connect(self.double_clicked.emit)
        
        menu.addSeparator()

        # 截图功能
        region_screenshot_action = menu.addAction("✂️ 区域截图")
        region_screenshot_action.triggered.connect(self._on_region_screenshot)
        
        full_screenshot_action = menu.addAction("🖥️ 全屏截图")
        full_screenshot_action.triggered.connect(self._on_full_screenshot)
        
        menu.addSeparator()
        
        # 主题子菜单
        theme_menu = menu.addMenu("🎨 切换主题")
        theme_menu.setStyleSheet(menu.styleSheet())
        
        for theme_name, display_name in theme_manager.get_theme_names():
            action = theme_menu.addAction(display_name)
            action.triggered.connect(lambda checked, n=theme_name: theme_manager.set_theme(n))
        
        menu.addSeparator()
        
        restart_action = menu.addAction("🔄 重启")
        restart_action.triggered.connect(self.restart_requested.emit)
        
        settings_action = menu.addAction("⚙️ 设置")
        settings_action.triggered.connect(self.settings_requested.emit)
        
        quit_action = menu.addAction("❌ 退出")
        quit_action.triggered.connect(self.quit_requested.emit)
        
        menu.exec(pos)

    def _on_region_screenshot(self):
        """区域截图"""
        try:
            from .screenshot_selector import RegionScreenshotCapture
            
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
            from ..services.screen_capture import ScreenCaptureService
            
            self.hide()
            QTimer.singleShot(100, self._do_full_screenshot)
        except ImportError as e:
            print(f"截图功能不可用: {e}")
            
    def _do_full_screenshot(self):
        """执行全屏截图"""
        try:
            from ..services.screen_capture import ScreenCaptureService
            
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