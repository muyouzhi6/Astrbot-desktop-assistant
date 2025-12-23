"""
Shared Chat Widgets for AstrBot Desktop Client
"""

import os
import math
import base64
from typing import Optional

from PySide6.QtCore import Qt, Signal, QTimer, QSize, QUrl
from PySide6.QtGui import (
    QPixmap, QPainter, QBrush, QColor, QMouseEvent,
    QFont, QPen, QLinearGradient, QRadialGradient,
    QPainterPath, QCursor, QDesktopServices
)
from PySide6.QtWidgets import (
    QWidget, QLabel, QVBoxLayout, QHBoxLayout, QPushButton, QMenu,
    QApplication, QFrame, QSizePolicy, QTextEdit, QScrollArea,
    QDialog, QGraphicsView, QGraphicsScene, QGraphicsPixmapItem, QFileDialog,
    QSlider
)
from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput

from .themes import theme_manager, Theme

def format_file_size(size_bytes: int) -> str:
    """格式化文件大小"""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    elif size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.1f} MB"
    else:
        return f"{size_bytes / (1024 * 1024 * 1024):.1f} GB"


def format_duration(seconds: float) -> str:
    """格式化时长"""
    minutes = int(seconds // 60)
    secs = int(seconds % 60)
    return f"{minutes}:{secs:02d}"


class VoiceMessageWidget(QFrame):
    """语音消息组件 - 内置音频播放器"""
    
    play_requested = Signal(str)  # 发送音频路径（保留兼容性）
    
    def __init__(self, audio_path: str, duration: float = 0, parent=None):
        super().__init__(parent)
        self._audio_path = audio_path
        self._duration = duration  # 预设时长（秒）
        self._is_playing = False
        self._is_seeking = False  # 是否正在拖动进度条
        
        self.setObjectName("voiceMessage")
        
        # 初始化媒体播放器
        self._player = QMediaPlayer(self)
        self._audio_output = QAudioOutput(self)
        self._player.setAudioOutput(self._audio_output)
        self._audio_output.setVolume(1.0)
        
        # 连接播放器信号
        self._player.playbackStateChanged.connect(self._on_playback_state_changed)
        self._player.positionChanged.connect(self._on_position_changed)
        self._player.durationChanged.connect(self._on_duration_changed)
        self._player.errorOccurred.connect(self._on_error)
        
        # 加载音频文件
        if audio_path and os.path.exists(audio_path):
            self._player.setSource(QUrl.fromLocalFile(audio_path))
        
        # 布局
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(10)
        
        # 播放/暂停按钮
        self._play_btn = QPushButton("▶")
        self._play_btn.setObjectName("voicePlayBtn")
        self._play_btn.setFixedSize(36, 36)
        self._play_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._play_btn.clicked.connect(self._toggle_play)
        layout.addWidget(self._play_btn)
        
        # 进度条
        self._slider = QSlider(Qt.Orientation.Horizontal)
        self._slider.setObjectName("voiceSlider")
        self._slider.setMinimum(0)
        self._slider.setMaximum(1000)  # 使用1000作为精度
        self._slider.setValue(0)
        self._slider.setCursor(Qt.CursorShape.PointingHandCursor)
        self._slider.sliderPressed.connect(self._on_slider_pressed)
        self._slider.sliderReleased.connect(self._on_slider_released)
        self._slider.sliderMoved.connect(self._on_slider_moved)
        layout.addWidget(self._slider, 1)
        
        # 时间显示标签
        self._time_label = QLabel("0:00 / 0:00")
        self._time_label.setObjectName("voiceTimeLabel")
        self._time_label.setMinimumWidth(80)
        layout.addWidget(self._time_label)
        
        # 如果有预设时长，显示它
        if duration > 0:
            self._update_time_display(0, int(duration * 1000))
        
        self._apply_theme()
        theme_manager.register_callback(self._on_theme_changed)
        
    def _on_theme_changed(self, theme: Theme):
        self._apply_theme()
        
    def _apply_theme(self):
        t = theme_manager.current_theme
        c = theme_manager.get_current_colors()  # 使用 get_current_colors() 获取应用了自定义颜色的最终配置
        
        self.setStyleSheet(f"""
            QFrame#voiceMessage {{
                background-color: {c.bg_secondary};
                border: 1px solid {c.border_light};
                border-radius: 12px;
                min-width: 220px;
            }}
            QFrame#voiceMessage:hover {{
                background-color: {c.bg_hover};
            }}
            QPushButton#voicePlayBtn {{
                background-color: {c.primary};
                color: white;
                border: none;
                border-radius: 18px;
                font-size: 14px;
                font-weight: bold;
            }}
            QPushButton#voicePlayBtn:hover {{
                background-color: {c.primary_dark};
            }}
            QPushButton#voicePlayBtn:pressed {{
                background-color: {c.primary_dark};
            }}
            QSlider#voiceSlider {{
                height: 20px;
            }}
            QSlider#voiceSlider::groove:horizontal {{
                border: none;
                height: 4px;
                background: {c.border_light};
                border-radius: 2px;
            }}
            QSlider#voiceSlider::handle:horizontal {{
                background: {c.primary};
                border: none;
                width: 12px;
                height: 12px;
                margin: -4px 0;
                border-radius: 6px;
            }}
            QSlider#voiceSlider::handle:horizontal:hover {{
                background: {c.primary_dark};
                width: 14px;
                height: 14px;
                margin: -5px 0;
                border-radius: 7px;
            }}
            QSlider#voiceSlider::sub-page:horizontal {{
                background: {c.primary};
                border-radius: 2px;
            }}
            QLabel#voiceTimeLabel {{
                color: {c.text_secondary};
                font-size: {t.font_size_small}px;
                background: transparent;
            }}
        """)
    
    def _toggle_play(self):
        """切换播放/暂停状态"""
        if self._player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self._player.pause()
        else:
            self._player.play()
            self.play_requested.emit(self._audio_path)
    
    def _on_playback_state_changed(self, state):
        """播放状态变化"""
        if state == QMediaPlayer.PlaybackState.PlayingState:
            self._is_playing = True
            self._play_btn.setText("⏸")
        elif state == QMediaPlayer.PlaybackState.PausedState:
            self._is_playing = False
            self._play_btn.setText("▶")
        elif state == QMediaPlayer.PlaybackState.StoppedState:
            self._is_playing = False
            self._play_btn.setText("▶")
            # 播放完成后重置进度
            self._slider.setValue(0)
            self._update_time_display(0, self._player.duration())
    
    def _on_position_changed(self, position: int):
        """播放位置变化"""
        if not self._is_seeking:
            duration = self._player.duration()
            if duration > 0:
                slider_value = int((position / duration) * 1000)
                self._slider.setValue(slider_value)
            self._update_time_display(position, duration)
    
    def _on_duration_changed(self, duration: int):
        """音频时长变化"""
        self._update_time_display(self._player.position(), duration)
    
    def _on_error(self, error, error_string):
        """播放错误"""
        print(f"音频播放错误: {error_string}")
    
    def _on_slider_pressed(self):
        """滑块按下"""
        self._is_seeking = True
    
    def _on_slider_released(self):
        """滑块释放"""
        self._is_seeking = False
        duration = self._player.duration()
        if duration > 0:
            position = int((self._slider.value() / 1000) * duration)
            self._player.setPosition(position)
    
    def _on_slider_moved(self, value: int):
        """滑块移动"""
        duration = self._player.duration()
        if duration > 0:
            position = int((value / 1000) * duration)
            self._update_time_display(position, duration)
    
    def _update_time_display(self, position: int, duration: int):
        """更新时间显示"""
        pos_str = format_duration(position / 1000) if position >= 0 else "0:00"
        dur_str = format_duration(duration / 1000) if duration > 0 else "0:00"
        self._time_label.setText(f"{pos_str} / {dur_str}")
    
    def set_playing(self, playing: bool):
        """设置播放状态"""
        if playing:
            self._player.play()
        else:
            self._player.pause()
    
    def stop(self):
        """停止播放"""
        self._player.stop()
    
    def cleanup(self):
        """清理资源"""
        self._player.stop()
        self._player.setSource(QUrl())


class VideoMessageWidget(QFrame):
    """视频消息组件"""
    
    play_requested = Signal(str)  # 发送视频路径
    
    def __init__(self, video_path: str, thumbnail_path: str = "", duration: float = 0, parent=None):
        super().__init__(parent)
        self._video_path = video_path
        self._thumbnail_path = thumbnail_path
        self._duration = duration
        
        self.setObjectName("videoMessage")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # 缩略图容器
        self._thumbnail_container = QWidget()
        self._thumbnail_container.setFixedSize(200, 150)
        thumb_layout = QVBoxLayout(self._thumbnail_container)
        thumb_layout.setContentsMargins(0, 0, 0, 0)
        
        # 缩略图
        self._thumbnail_label = QLabel()
        self._thumbnail_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._thumbnail_label.setFixedSize(200, 150)
        
        if thumbnail_path and os.path.exists(thumbnail_path):
            pixmap = QPixmap(thumbnail_path)
            if not pixmap.isNull():
                scaled = pixmap.scaled(200, 150, Qt.AspectRatioMode.KeepAspectRatio,
                                       Qt.TransformationMode.SmoothTransformation)
                self._thumbnail_label.setPixmap(scaled)
        else:
            self._thumbnail_label.setText("🎬")
            self._thumbnail_label.setStyleSheet("font-size: 48px; background: #333;")
            
        thumb_layout.addWidget(self._thumbnail_label)
        layout.addWidget(self._thumbnail_container)
        
        # 播放按钮覆盖层
        self._play_overlay = QLabel("▶")
        self._play_overlay.setObjectName("videoPlayOverlay")
        self._play_overlay.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._play_overlay.setFixedSize(50, 50)
        # 将播放按钮居中放置在缩略图上
        self._play_overlay.setParent(self._thumbnail_container)
        self._play_overlay.move(75, 50)
        
        # 时长标签
        if duration > 0:
            self._duration_label = QLabel(format_duration(duration))
            self._duration_label.setObjectName("videoDuration")
            self._duration_label.setParent(self._thumbnail_container)
            self._duration_label.move(160, 130)
            
        self._apply_theme()
        theme_manager.register_callback(self._on_theme_changed)
        
    def _on_theme_changed(self, theme: Theme):
        self._apply_theme()
        
    def _apply_theme(self):
        t = theme_manager.current_theme
        c = theme_manager.get_current_colors()  # 使用 get_current_colors() 获取应用了自定义颜色的最终配置
        
        self.setStyleSheet(f"""
            QFrame#videoMessage {{
                background-color: {c.bg_tertiary};
                border: 1px solid {c.border_light};
                border-radius: 8px;
            }}
            QLabel#videoPlayOverlay {{
                background-color: rgba(0, 0, 0, 0.6);
                color: white;
                border-radius: 25px;
                font-size: 24px;
            }}
            QLabel#videoDuration {{
                background-color: rgba(0, 0, 0, 0.7);
                color: white;
                padding: 2px 6px;
                border-radius: 4px;
                font-size: {t.font_size_small}px;
            }}
        """)
        
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.play_requested.emit(self._video_path)
            # 默认打开视频
            QDesktopServices.openUrl(QUrl.fromLocalFile(self._video_path))
        super().mousePressEvent(event)


class FileMessageWidget(QFrame):
    """文件消息组件"""
    
    open_requested = Signal(str)  # 发送文件路径
    download_requested = Signal(str)  # 发送文件路径
    
    def __init__(self, file_path: str, file_name: str = "", file_size: int = 0, parent=None):
        super().__init__(parent)
        self._file_path = file_path
        self._file_name = file_name or os.path.basename(file_path)
        self._file_size = file_size
        
        self.setObjectName("fileMessage")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(10)
        
        # 文件图标
        self._icon_label = QLabel()
        self._icon_label.setFixedSize(40, 40)
        self._icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        # 根据文件扩展名选择图标
        ext = os.path.splitext(self._file_name)[1].lower()
        if ext in ['.pdf']:
            icon_text = "📄"
        elif ext in ['.doc', '.docx']:
            icon_text = "📝"
        elif ext in ['.xls', '.xlsx']:
            icon_text = "📊"
        elif ext in ['.ppt', '.pptx']:
            icon_text = "📽️"
        elif ext in ['.zip', '.rar', '.7z', '.tar', '.gz']:
            icon_text = "🗜️"
        elif ext in ['.txt', '.md', '.json', '.xml']:
            icon_text = "📃"
        elif ext in ['.py', '.js', '.ts', '.java', '.c', '.cpp', '.h']:
            icon_text = "💻"
        else:
            icon_text = "📁"
            
        self._icon_label.setText(icon_text)
        layout.addWidget(self._icon_label)
        
        # 文件信息
        info_layout = QVBoxLayout()
        info_layout.setContentsMargins(0, 0, 0, 0)
        info_layout.setSpacing(2)
        
        self._name_label = QLabel(self._file_name)
        self._name_label.setObjectName("fileName")
        self._name_label.setWordWrap(True)
        self._name_label.setMaximumWidth(200)
        info_layout.addWidget(self._name_label)
        
        if file_size > 0:
            self._size_label = QLabel(format_file_size(file_size))
            self._size_label.setObjectName("fileSize")
            info_layout.addWidget(self._size_label)
            
        layout.addLayout(info_layout)
        layout.addStretch()
        
        # 下载/打开按钮
        self._action_btn = QPushButton("📥")
        self._action_btn.setObjectName("fileActionBtn")
        self._action_btn.setFixedSize(32, 32)
        self._action_btn.setToolTip("打开文件")
        self._action_btn.clicked.connect(self._on_action_clicked)
        layout.addWidget(self._action_btn)
        
        self._apply_theme()
        theme_manager.register_callback(self._on_theme_changed)
        
    def _on_theme_changed(self, theme: Theme):
        self._apply_theme()
        
    def _apply_theme(self):
        t = theme_manager.current_theme
        c = theme_manager.get_current_colors()  # 使用 get_current_colors() 获取应用了自定义颜色的最终配置
        
        self.setStyleSheet(f"""
            QFrame#fileMessage {{
                background-color: {c.bg_secondary};
                border: 1px solid {c.border_light};
                border-radius: 8px;
            }}
            QFrame#fileMessage:hover {{
                background-color: {c.bg_hover};
                border-color: {c.primary};
            }}
            QLabel {{
                background: transparent;
            }}
            QLabel#fileName {{
                color: {c.text_primary};
                font-size: {t.font_size_base}px;
                font-weight: bold;
            }}
            QLabel#fileSize {{
                color: {c.text_secondary};
                font-size: {t.font_size_small}px;
            }}
            QPushButton#fileActionBtn {{
                background-color: {c.primary};
                color: white;
                border: none;
                border-radius: 16px;
                font-size: 14px;
            }}
            QPushButton#fileActionBtn:hover {{
                background-color: {c.primary_dark};
            }}
        """)
        # 设置图标字体大小
        self._icon_label.setStyleSheet("font-size: 28px; background: transparent;")
        
    def _on_action_clicked(self):
        if os.path.exists(self._file_path):
            self.open_requested.emit(self._file_path)
            QDesktopServices.openUrl(QUrl.fromLocalFile(self._file_path))
        else:
            self.download_requested.emit(self._file_path)
            
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._on_action_clicked()
        super().mousePressEvent(event)


class ClickableImageLabel(QLabel):
    """可点击的图片标签，支持点击放大和右键复制"""
    
    clicked = Signal()
    
    def __init__(self, image_path: str = "", parent=None):
        super().__init__(parent)
        self._image_path = image_path
        self._original_pixmap: Optional[QPixmap] = None
        self._scaled_size = QSize(0, 0)  # 记录缩放后的尺寸
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_context_menu)
        # 连接点击信号到预览方法 (可选，也可以外部连接)
        # self.clicked.connect(self._show_preview)
        # 设置固定的尺寸策略，防止被拉伸
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        
        if image_path:
            self.load_image(image_path)
            
    def load_image(self, image_path: str, max_size: int = 200):
        """加载并缩放图片"""
        self._image_path = image_path
        if os.path.exists(image_path):
            pixmap = QPixmap(image_path)
            if not pixmap.isNull():
                self._original_pixmap = pixmap
                # 缩放为缩略图，限制最大宽高
                max_width = min(max_size, 300)
                max_height = 200
                scaled = pixmap.scaled(
                    max_width, max_height,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation
                )
                self.setPixmap(scaled)
                # 记录缩放后的尺寸
                self._scaled_size = scaled.size()
                # 设置固定尺寸，避免多余空间
                self.setFixedSize(scaled.width(), scaled.height())
                # 设置对齐方式
                self.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
    
    def sizeHint(self):
        """返回推荐尺寸"""
        if self._scaled_size.isValid() and not self._scaled_size.isEmpty():
            return self._scaled_size
        return super().sizeHint()
    
    def minimumSizeHint(self):
        """返回最小尺寸"""
        return self.sizeHint()
                
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
            self._show_preview()
        super().mousePressEvent(event)
        
    def _show_context_menu(self, pos):
        """显示右键菜单"""
        menu = QMenu(self)
        
        # 应用主题样式
        t = theme_manager.current_theme
        c = theme_manager.get_current_colors()  # 使用 get_current_colors() 获取应用了自定义颜色的最终配置
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
        c = theme_manager.get_current_colors()  # 使用 get_current_colors() 获取应用了自定义颜色的最终配置
        
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


class PasteAwareTextEdit(QTextEdit):
    """支持图片粘贴的输入框"""
    
    image_pasted = Signal(str)
    enter_pressed = Signal()
    
    def canInsertFromMimeData(self, source):
        if source.hasImage():
            return True
        return QTextEdit.canInsertFromMimeData(self, source)
        
    def insertFromMimeData(self, source):
        if source.hasImage():
            image = source.imageData()
            if image:
                import tempfile
                with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
                    image.save(f.name, "PNG")
                self.image_pasted.emit(f.name)
            return
        QTextEdit.insertFromMimeData(self, source)
        
    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Return:
            if event.modifiers() == Qt.KeyboardModifier.ShiftModifier:
                QTextEdit.keyPressEvent(self, event)
            else:
                self.enter_pressed.emit()
                event.accept()
        else:
            QTextEdit.keyPressEvent(self, event)