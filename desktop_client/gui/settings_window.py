"""
美化版设置窗口

提供完整的设置界面，支持：
- 服务器配置
- 外观设置（主题、悬浮球头像）
- 快捷键配置
- 交互模式设置
"""

import os
from typing import Optional, Dict

from PySide6.QtGui import QPixmap, QColor
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QFrame,
    QScrollArea,
    QComboBox,
    QCheckBox,
    QFileDialog,
    QTabWidget,
    QKeySequenceEdit,
    QSpinBox,
    QDoubleSpinBox,
    QMessageBox,
    QTimeEdit,
    QColorDialog,
)
from PySide6.QtCore import Qt, Signal, QTime, QSize
from qasync import asyncSlot

from ..api_client import AstrBotApiClient
from ..utils.autostart import is_autostart_enabled, set_autostart
from ..services import get_chat_history_manager
from ..config import save_config, ClientConfig, CustomThemeConfig
from .themes import theme_manager, Theme
from .icons import icon_manager
from .hotkeys import HotkeyConfig, hotkey_manager


class ColorPickerButton(QPushButton):
    """颜色选择器按钮

    显示当前颜色预览，点击弹出 QColorDialog 选择颜色。
    """

    color_changed = Signal(str)  # 颜色变化信号，传递十六进制颜色值

    def __init__(self, color: str = "", parent=None):
        super().__init__(parent)
        self._color = color
        self.setFixedSize(30, 30)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.clicked.connect(self._on_click)
        self._update_style()

    @property
    def color(self) -> str:
        """获取当前颜色值"""
        return self._color

    @color.setter
    def color(self, value: str):
        """设置颜色值"""
        self._color = value
        self._update_style()

    def _update_style(self):
        """更新按钮样式以显示当前颜色"""
        # 获取当前主题颜色
        from .themes import theme_manager

        c = theme_manager.get_current_colors()

        if self._color:
            # 有颜色时显示颜色
            self.setStyleSheet(f"""
                QPushButton {{
                    background-color: {self._color};
                    border: 2px solid {c.border_base};
                    border-radius: 4px;
                    min-height: 30px;
                }}
                QPushButton:hover {{
                    border-color: {c.primary};
                }}
            """)
            self.setText("")
        else:
            # 无颜色时显示占位符
            self.setStyleSheet(f"""
                QPushButton {{
                    background-color: {c.bg_secondary};
                    border: 2px dashed {c.border_base};
                    border-radius: 4px;
                    color: {c.text_secondary};
                    font-size: 14px;
                    min-height: 30px;
                }}
                QPushButton:hover {{
                    border-color: {c.primary};
                }}
            """)
            self.setText("...")

    def _on_click(self):
        """点击按钮时弹出颜色选择对话框"""
        initial_color = QColor(self._color) if self._color else QColor("#FFFFFF")
        color = QColorDialog.getColor(
            initial_color,
            self,
            "选择颜色",
            QColorDialog.ColorDialogOption.ShowAlphaChannel,
        )
        if color.isValid():
            # 如果有透明度，使用 rgba 格式
            if color.alpha() < 255:
                self._color = f"rgba({color.red()}, {color.green()}, {color.blue()}, {color.alpha() / 255:.2f})"
            else:
                self._color = color.name()  # 十六进制格式
            self._update_style()
            self.color_changed.emit(self._color)

    def clear_color(self):
        """清除颜色"""
        self._color = ""
        self._update_style()
        self.color_changed.emit("")


class SettingsSection(QFrame):
    """设置分区组件"""

    def __init__(self, title: str, parent=None):
        super().__init__(parent)
        self.setObjectName("settingsSection")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 16)
        layout.setSpacing(12)

        # 标题
        self._title = QLabel(title)
        self._title.setObjectName("sectionTitle")
        layout.addWidget(self._title)

        # 内容区域
        self._content = QFrame()
        self._content.setObjectName("sectionContent")
        self._content_layout = QVBoxLayout(self._content)
        self._content_layout.setContentsMargins(16, 12, 16, 12)
        self._content_layout.setSpacing(12)
        layout.addWidget(self._content)

    def add_row(self, label: str, widget: QWidget, orientation: str = "horizontal"):
        """添加一行设置项"""
        row = QFrame()

        if orientation == "vertical":
            row_layout = QVBoxLayout(row)
            row_layout.setContentsMargins(0, 0, 0, 0)
            row_layout.setSpacing(4)

            lbl = QLabel(label)
            lbl.setObjectName("settingLabel")
            row_layout.addWidget(lbl)
            row_layout.addWidget(widget)
        else:
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(0, 0, 0, 0)

            lbl = QLabel(label)
            lbl.setObjectName("settingLabel")
            lbl.setMinimumWidth(120)

            row_layout.addWidget(lbl)
            row_layout.addWidget(widget, 1)

        self._content_layout.addWidget(row)
        return row

    def add_widget(self, widget: QWidget):
        """添加自定义组件"""
        self._content_layout.addWidget(widget)


class SettingsWindow(QWidget):
    """美化版设置窗口"""

    settings_changed = Signal(dict)
    closed = Signal()

    def __init__(self, config: Optional[ClientConfig] = None, parent=None):
        super().__init__(parent)
        self.config = config if config is not None else ClientConfig()

        self.setWindowTitle("设置")
        self.setMinimumSize(500, 600)
        self.resize(550, 700)
        self.setWindowFlags(Qt.WindowType.Window | Qt.WindowType.WindowCloseButtonHint)

        self._init_ui()
        self._apply_theme()
        self._load_settings()

        theme_manager.register_callback(self._on_theme_changed)

    def _init_ui(self):
        """初始化 UI"""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # 标题栏
        title_bar = self._create_title_bar()
        main_layout.addWidget(title_bar)

        # 标签页
        self._tabs = QTabWidget()
        self._tabs.setObjectName("settingsTabs")
        self._tabs.setUsesScrollButtons(False)  # 禁用标签栏滚动箭头

        # 服务器设置
        self._tabs.addTab(self._create_server_tab(), "服务器")

        # 外观设置
        self._tabs.addTab(self._create_appearance_tab(), "外观")

        # 快捷键设置
        self._tabs.addTab(self._create_hotkeys_tab(), "快捷键")

        # 交互设置
        self._tabs.addTab(self._create_interaction_tab(), "交互")

        # 主动对话设置
        self._tabs.addTab(self._create_proactive_tab(), "主动对话")

        # 存储设置
        self._tabs.addTab(self._create_storage_tab(), "存储")

        # 自定义颜色设置
        self._tabs.addTab(self._create_custom_colors_tab(), "配色")

        # 更新设置
        self._tabs.addTab(self._create_update_tab(), "更新")

        main_layout.addWidget(self._tabs, 1)

        # 底部按钮
        bottom_bar = self._create_bottom_bar()
        main_layout.addWidget(bottom_bar)

    def _create_title_bar(self) -> QFrame:
        """创建标题栏"""
        title_bar = QFrame()
        title_bar.setObjectName("titleBar")
        title_bar.setFixedHeight(50)

        layout = QHBoxLayout(title_bar)
        layout.setContentsMargins(16, 0, 16, 0)

        icon = QLabel()
        icon.setObjectName("titleIcon")
        # 使用 SVG 图标
        c = theme_manager.get_current_colors()
        icon.setPixmap(icon_manager.get_pixmap("settings", c.primary, 20))

        title = QLabel("设置")
        title.setObjectName("titleText")

        layout.addWidget(icon)
        layout.addWidget(title)
        layout.addStretch()

        return title_bar

    def _create_server_tab(self) -> QWidget:
        """创建服务器设置标签页"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(16, 16, 16, 16)

        # 服务器地址
        section = SettingsSection("服务器配置")

        self._server_url = QLineEdit()
        self._server_url.setPlaceholderText("http://localhost:6185")
        section.add_row("服务器地址", self._server_url)

        self._username = QLineEdit()
        self._username.setPlaceholderText("用户名")
        section.add_row("用户名", self._username)

        self._password = QLineEdit()
        self._password.setPlaceholderText("密码")
        self._password.setEchoMode(QLineEdit.EchoMode.Password)
        section.add_row("密码", self._password)

        self._enable_streaming = QCheckBox("启用流式输出 (打字机效果)")
        section.add_widget(self._enable_streaming)

        # 测试连接按钮
        self._test_btn = QPushButton("测试连接")
        self._test_btn.setObjectName("testBtn")
        self._test_btn.clicked.connect(self._on_test_connection)
        section.add_widget(self._test_btn)

        layout.addWidget(section)
        layout.addStretch()

        return tab

    def _create_appearance_tab(self) -> QWidget:
        """创建外观设置标签页"""
        tab = QWidget()
        tab_layout = QVBoxLayout(tab)
        tab_layout.setContentsMargins(0, 0, 0, 0)

        # 创建滚动区域
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll_area.setFrameShape(QFrame.Shape.NoFrame)

        # 滚动内容容器
        scroll_content = QWidget()
        layout = QVBoxLayout(scroll_content)
        layout.setContentsMargins(16, 16, 16, 16)

        # 主题设置
        theme_section = SettingsSection("主题设置")

        self._theme_combo = QComboBox()
        for name, display in theme_manager.get_theme_names():
            self._theme_combo.addItem(display, name)
        self._theme_combo.currentIndexChanged.connect(self._on_theme_selected)
        theme_section.add_row("主题", self._theme_combo)

        layout.addWidget(theme_section)

        # 头像设置
        avatar_section = SettingsSection("头像设置")

        # 用户头像
        user_avatar_row = QFrame()
        user_avatar_layout = QHBoxLayout(user_avatar_row)
        user_avatar_layout.setContentsMargins(0, 0, 0, 0)

        user_avatar_label = QLabel("用户头像")
        user_avatar_label.setObjectName("settingLabel")
        user_avatar_label.setMinimumWidth(80)

        self._user_avatar_preview = QLabel()
        self._user_avatar_preview.setFixedSize(48, 48)
        self._user_avatar_preview.setObjectName("avatarPreview")
        self._user_avatar_preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        # 使用 SVG 图标作为默认用户头像
        c = theme_manager.get_current_colors()
        self._user_avatar_preview.setPixmap(
            icon_manager.get_pixmap("user", c.text_primary, 32)
        )

        user_avatar_btns = QFrame()
        user_btns_layout = QHBoxLayout(user_avatar_btns)
        user_btns_layout.setContentsMargins(0, 0, 0, 0)
        user_btns_layout.setSpacing(8)

        self._upload_user_avatar_btn = QPushButton("选择图片")
        self._upload_user_avatar_btn.clicked.connect(self._on_upload_user_avatar)

        self._reset_user_avatar_btn = QPushButton("恢复默认")
        self._reset_user_avatar_btn.clicked.connect(self._on_reset_user_avatar)

        user_btns_layout.addWidget(self._upload_user_avatar_btn)
        user_btns_layout.addWidget(self._reset_user_avatar_btn)

        user_avatar_layout.addWidget(user_avatar_label)
        user_avatar_layout.addWidget(self._user_avatar_preview)
        user_avatar_layout.addWidget(user_avatar_btns)
        user_avatar_layout.addStretch()

        avatar_section.add_widget(user_avatar_row)

        # Bot头像
        bot_avatar_row = QFrame()
        bot_avatar_layout = QHBoxLayout(bot_avatar_row)
        bot_avatar_layout.setContentsMargins(0, 0, 0, 0)

        bot_avatar_label = QLabel("Bot头像")
        bot_avatar_label.setObjectName("settingLabel")
        bot_avatar_label.setMinimumWidth(80)

        self._bot_avatar_preview = QLabel()
        self._bot_avatar_preview.setFixedSize(48, 48)
        self._bot_avatar_preview.setObjectName("avatarPreview")
        self._bot_avatar_preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        # 使用 SVG 图标作为默认机器人头像
        self._bot_avatar_preview.setPixmap(
            icon_manager.get_pixmap("bot", c.text_primary, 32)
        )

        bot_avatar_btns = QFrame()
        bot_btns_layout = QHBoxLayout(bot_avatar_btns)
        bot_btns_layout.setContentsMargins(0, 0, 0, 0)
        bot_btns_layout.setSpacing(8)

        self._upload_bot_avatar_btn = QPushButton("选择图片")
        self._upload_bot_avatar_btn.clicked.connect(self._on_upload_bot_avatar)

        self._reset_bot_avatar_btn = QPushButton("恢复默认")
        self._reset_bot_avatar_btn.clicked.connect(self._on_reset_bot_avatar)

        bot_btns_layout.addWidget(self._upload_bot_avatar_btn)
        bot_btns_layout.addWidget(self._reset_bot_avatar_btn)

        bot_avatar_layout.addWidget(bot_avatar_label)
        bot_avatar_layout.addWidget(self._bot_avatar_preview)
        bot_avatar_layout.addWidget(bot_avatar_btns)
        bot_avatar_layout.addStretch()

        avatar_section.add_widget(bot_avatar_row)

        layout.addWidget(avatar_section)

        # 悬浮球设置
        ball_section = SettingsSection("悬浮球设置")

        # 悬浮球头像预览（使用Bot头像）
        avatar_row = QFrame()
        avatar_layout = QHBoxLayout(avatar_row)
        avatar_layout.setContentsMargins(0, 0, 0, 0)

        self._avatar_preview = QLabel()
        self._avatar_preview.setFixedSize(64, 64)
        self._avatar_preview.setObjectName("avatarPreview")
        self._avatar_preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        # 使用 SVG 图标作为默认头像
        self._avatar_preview.setPixmap(
            icon_manager.get_pixmap("bot", c.text_primary, 40)
        )

        avatar_btns = QFrame()
        btns_layout = QVBoxLayout(avatar_btns)
        btns_layout.setContentsMargins(0, 0, 0, 0)
        btns_layout.setSpacing(8)

        self._upload_avatar_btn = QPushButton("选择图片")
        self._upload_avatar_btn.clicked.connect(self._on_upload_avatar)

        self._reset_avatar_btn = QPushButton("恢复默认")
        self._reset_avatar_btn.clicked.connect(self._on_reset_avatar)

        btns_layout.addWidget(self._upload_avatar_btn)
        btns_layout.addWidget(self._reset_avatar_btn)

        avatar_layout.addWidget(self._avatar_preview)
        avatar_layout.addWidget(avatar_btns)
        avatar_layout.addStretch()

        ball_section.add_widget(avatar_row)

        # 悬浮球大小
        self._ball_size = QSpinBox()
        self._ball_size.setRange(48, 128)
        self._ball_size.setValue(64)
        self._ball_size.setSuffix(" px")
        ball_section.add_row("悬浮球大小", self._ball_size)

        # 呼吸灯效果
        self._breathing_enabled = QCheckBox("启用呼吸灯效果")
        self._breathing_enabled.setChecked(True)
        ball_section.add_widget(self._breathing_enabled)

        layout.addWidget(ball_section)

        # 系统设置
        system_section = SettingsSection("系统设置")

        # 开机自启
        self._auto_start = QCheckBox("开机自动启动")
        self._auto_start.setToolTip(
            "开启后，系统启动时自动运行桌面助手（仅支持 Windows）"
        )
        # 检查当前状态
        if os.name == "nt":
            self._auto_start.setChecked(is_autostart_enabled())
        else:
            self._auto_start.setEnabled(False)
            self._auto_start.setToolTip("开机自启仅支持 Windows 系统")
        system_section.add_widget(self._auto_start)

        layout.addWidget(system_section)
        layout.addStretch()

        # 设置滚动内容
        scroll_area.setWidget(scroll_content)
        tab_layout.addWidget(scroll_area)

        return tab

    def _create_hotkeys_tab(self) -> QWidget:
        """创建快捷键设置标签页"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(16, 16, 16, 16)

        section = SettingsSection("快捷键配置")

        # 启用全局快捷键
        self._global_hotkeys = QCheckBox("启用全局快捷键（需要 pynput 库）")
        section.add_widget(self._global_hotkeys)

        # 快捷键配置
        self._hotkey_inputs = {}

        hotkey_items = [
            ("toggle_chat", "显示/隐藏对话", "Ctrl+Shift+A"),
            ("region_screenshot", "区域截图", "Ctrl+Shift+S"),
            ("full_screenshot", "全屏截图", "Ctrl+Shift+F"),
            ("toggle_ball", "显示/隐藏悬浮球", "Ctrl+Shift+B"),
            ("quick_ask", "快速提问", "Ctrl+Shift+Q"),
            ("cycle_theme", "切换主题", "Ctrl+Shift+T"),
        ]

        for key, label, default in hotkey_items:
            edit = QKeySequenceEdit()
            edit.setKeySequence(default)
            section.add_row(label, edit)
            self._hotkey_inputs[key] = edit

        layout.addWidget(section)
        layout.addStretch()

        return tab

    def _create_interaction_tab(self) -> QWidget:
        """创建交互设置标签页"""
        tab = QWidget()
        tab_layout = QVBoxLayout(tab)
        tab_layout.setContentsMargins(0, 0, 0, 0)

        # 创建滚动区域
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll_area.setFrameShape(QFrame.Shape.NoFrame)

        # 滚动内容容器
        scroll_content = QWidget()
        layout = QVBoxLayout(scroll_content)
        layout.setContentsMargins(16, 16, 16, 16)

        # 交互模式
        mode_section = SettingsSection("交互模式")

        self._default_mode = QComboBox()
        self._default_mode.addItem("气泡对话", "bubble")
        self._default_mode.addItem("对话窗口", "window")
        mode_section.add_row("默认模式", self._default_mode)

        self._single_click_action = QComboBox()
        self._single_click_action.addItem("显示气泡", "bubble")
        self._single_click_action.addItem("打开窗口", "window")
        self._single_click_action.addItem("无操作", "none")
        mode_section.add_row("单击悬浮球", self._single_click_action)

        self._double_click_action = QComboBox()
        self._double_click_action.addItem("打开窗口", "window")
        self._double_click_action.addItem("显示气泡", "bubble")
        self._double_click_action.addItem("无操作", "none")
        mode_section.add_row("双击悬浮球", self._double_click_action)

        layout.addWidget(mode_section)

        # 气泡设置
        bubble_section = SettingsSection("气泡设置")

        self._bubble_duration = QSpinBox()
        self._bubble_duration.setRange(1, 30)
        self._bubble_duration.setValue(5)
        self._bubble_duration.setSuffix(" 秒")
        bubble_section.add_row("自动隐藏时间", self._bubble_duration)

        self._bubble_auto_hide = QCheckBox("自动隐藏气泡")
        self._bubble_auto_hide.setChecked(True)
        bubble_section.add_widget(self._bubble_auto_hide)

        layout.addWidget(bubble_section)

        # 语音设置
        voice_section = SettingsSection("语音设置")

        self._auto_play_voice = QCheckBox("收到语音消息时自动播放")
        voice_section.add_widget(self._auto_play_voice)

        layout.addWidget(voice_section)

        # 免打扰模式
        dnd_section = SettingsSection("免打扰模式")

        self._do_not_disturb = QCheckBox("启用免打扰模式")
        self._do_not_disturb.setToolTip(
            "启用后，收到消息时不会弹出对话窗口，只会显示悬浮球动画效果。\n"
            "语音消息会在后台自动播放（需启用自动播放语音）。\n"
            "适合游戏或全屏工作时使用。"
        )
        dnd_section.add_widget(self._do_not_disturb)

        dnd_info = QLabel(
            "提示：启用免打扰模式后，收到消息时悬浮球会显示脉冲动画提示，\n"
            "点击悬浮球可查看消息。语音消息会自动在后台播放。"
        )
        dnd_info.setWordWrap(True)
        dnd_info.setObjectName("infoLabel")
        dnd_section.add_widget(dnd_info)

        layout.addWidget(dnd_section)
        layout.addStretch()

        # 设置滚动内容
        scroll_area.setWidget(scroll_content)
        tab_layout.addWidget(scroll_area)

        return tab

    def _create_storage_tab(self) -> QWidget:
        """创建存储设置标签页"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(16, 16, 16, 16)

        section = SettingsSection("本地存储")

        # 图片保存路径
        path_row = QFrame()
        path_layout = QHBoxLayout(path_row)
        path_layout.setContentsMargins(0, 0, 0, 0)

        self._image_save_path = QLineEdit()
        self._image_save_path.setPlaceholderText("默认路径 (./temp/images)")
        self._image_save_path.setReadOnly(False)

        browse_btn = QPushButton("浏览...")
        browse_btn.setFixedWidth(80)
        browse_btn.clicked.connect(self._on_browse_storage_path)

        path_layout.addWidget(self._image_save_path)
        path_layout.addWidget(browse_btn)

        section.add_row("图片/截图保存路径", path_row, orientation="vertical")

        layout.addWidget(section)

        # 聊天记录存储
        chat_section = SettingsSection("聊天记录")

        # 聊天记录保存路径
        chat_path_row = QFrame()
        chat_path_layout = QHBoxLayout(chat_path_row)
        chat_path_layout.setContentsMargins(0, 0, 0, 0)

        self._chat_history_path = QLineEdit()
        self._chat_history_path.setPlaceholderText(
            "默认路径 (配置目录/chat_history.json)"
        )
        self._chat_history_path.setReadOnly(False)

        chat_browse_btn = QPushButton("浏览...")
        chat_browse_btn.setFixedWidth(80)
        chat_browse_btn.clicked.connect(self._on_browse_chat_history_path)

        chat_path_layout.addWidget(self._chat_history_path)
        chat_path_layout.addWidget(chat_browse_btn)

        chat_section.add_row("聊天记录保存路径", chat_path_row, orientation="vertical")

        # 清空聊天记录按钮
        clear_btn_row = QFrame()
        clear_btn_layout = QHBoxLayout(clear_btn_row)
        clear_btn_layout.setContentsMargins(0, 0, 0, 0)

        self._clear_chat_btn = QPushButton("清空聊天记录")
        self._clear_chat_btn.setObjectName("dangerBtn")
        self._clear_chat_btn.clicked.connect(self._on_clear_chat_history)
        # 设置删除图标
        clear_icon = icon_manager.get_icon("trash", "#FF3B30", 16)
        self._clear_chat_btn.setIcon(clear_icon)
        self._clear_chat_btn.setIconSize(QSize(16, 16))

        # 获取当前聊天记录数量
        chat_manager = get_chat_history_manager()
        msg_count = chat_manager.get_message_count()
        self._chat_count_label = QLabel(f"当前共 {msg_count} 条消息")
        self._chat_count_label.setObjectName("infoLabel")

        clear_btn_layout.addWidget(self._clear_chat_btn)
        clear_btn_layout.addWidget(self._chat_count_label)
        clear_btn_layout.addStretch()

        chat_section.add_widget(clear_btn_row)

        layout.addWidget(chat_section)

        # 说明
        info_section = SettingsSection("说明")
        info_label = QLabel(
            "• 图片/截图保存路径：设置截图和 AI 生成图片的本地保存位置，留空则使用默认路径。\n"
            "• 聊天记录保存路径：设置聊天记录的保存位置，留空则使用默认路径。\n"
            "• 清空聊天记录将删除所有历史消息，此操作不可恢复。"
        )
        info_label.setWordWrap(True)
        info_label.setObjectName("infoLabel")
        info_section.add_widget(info_label)

        layout.addWidget(info_section)
        layout.addStretch()

        return tab

    def _create_custom_colors_tab(self) -> QWidget:
        """创建自定义颜色设置标签页"""
        tab = QWidget()
        tab_layout = QVBoxLayout(tab)
        tab_layout.setContentsMargins(0, 0, 0, 0)

        # 创建滚动区域
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll_area.setFrameShape(QFrame.Shape.NoFrame)

        # 滚动内容容器
        scroll_content = QWidget()
        layout = QVBoxLayout(scroll_content)
        layout.setContentsMargins(16, 16, 16, 16)

        # 启用自定义颜色
        enable_section = SettingsSection("启用设置")
        self._custom_colors_enabled = QCheckBox("启用自定义颜色")
        self._custom_colors_enabled.setToolTip(
            "开启后，将使用下方自定义的颜色覆盖当前主题的对应颜色"
        )
        self._custom_colors_enabled.stateChanged.connect(self._on_custom_colors_toggle)
        enable_section.add_widget(self._custom_colors_enabled)
        layout.addWidget(enable_section)

        # 存储颜色选择器按钮的字典
        self._color_pickers: Dict[str, ColorPickerButton] = {}

        # 主题色组
        primary_section = SettingsSection("主题色 - 控制整体视觉风格")
        primary_colors = [
            (
                "primary",
                "主色调",
                "【保存按钮、链接、选中状态】按钮背景、选中项高亮、标签页底部线条的颜色",
            ),
            ("primary_light", "主色调（浅）", "【悬停效果】鼠标悬停时的浅色高亮效果"),
            ("primary_dark", "主色调（深）", "【按下效果】按钮按下时的深色效果"),
        ]
        self._add_color_group(primary_section, primary_colors)
        layout.addWidget(primary_section)

        # 背景色组
        bg_section = SettingsSection("背景色 - 控制窗口和区域背景")
        bg_colors = [
            (
                "bg_primary",
                "主背景色",
                "【主窗口背景】聊天窗口、设置窗口的整体背景颜色",
            ),
            (
                "bg_secondary",
                "次背景色",
                "【面板/卡片背景】设置分区、输入框区域、标签栏的背景颜色",
            ),
        ]
        self._add_color_group(bg_section, bg_colors)
        layout.addWidget(bg_section)

        # 文字色组
        text_section = SettingsSection("文字颜色 - 控制文字显示")
        text_colors = [
            (
                "text_primary",
                "主文字色",
                "【标题、正文】窗口标题、消息内容、按钮文字的颜色",
            ),
            (
                "text_secondary",
                "次文字色",
                "【描述、提示】标签说明、占位符文字、次要信息的颜色",
            ),
            (
                "system_notice_text",
                "系统通知色",
                "【系统通知】连接状态、系统提示信息的文字颜色",
            ),
        ]
        self._add_color_group(text_section, text_colors)
        layout.addWidget(text_section)

        # 悬浮球颜色组
        ball_section = SettingsSection("悬浮球颜色 - 控制桌面悬浮球外观")
        ball_colors = [
            ("ball_bg", "悬浮球背景", "【悬浮球圆形背景】桌面右下角悬浮球的填充颜色"),
            ("ball_glow", "悬浮球光晕", "【呼吸灯效果】悬浮球周围闪烁的光晕颜色"),
            ("ball_border", "悬浮球边框", "【悬浮球边框】悬浮球外圈的边框颜色"),
        ]
        self._add_color_group(ball_section, ball_colors)
        layout.addWidget(ball_section)

        # 聊天气泡颜色组
        bubble_section = SettingsSection("聊天气泡颜色 - 控制消息气泡外观")
        bubble_colors = [
            (
                "bubble_user_bg",
                "用户气泡背景",
                "【您发送的消息】用户消息气泡的背景颜色（右侧气泡）",
            ),
            (
                "bubble_user_text",
                "用户气泡文字",
                "【您发送的消息文字】用户消息中文字的颜色",
            ),
            (
                "bubble_ai_bg",
                "AI气泡背景",
                "【AI回复的消息】AI 消息气泡的背景颜色（左侧气泡）",
            ),
            ("bubble_ai_text", "AI气泡文字", "【AI回复的消息文字】AI 消息中文字的颜色"),
        ]
        self._add_color_group(bubble_section, bubble_colors)
        layout.addWidget(bubble_section)

        # 恢复默认按钮
        reset_section = SettingsSection("操作")
        reset_btn_row = QFrame()
        reset_btn_layout = QHBoxLayout(reset_btn_row)
        reset_btn_layout.setContentsMargins(0, 0, 0, 0)

        self._reset_custom_colors_btn = QPushButton("恢复默认颜色")
        self._reset_custom_colors_btn.setToolTip(
            "清除所有自定义颜色，恢复为当前主题的默认颜色"
        )
        self._reset_custom_colors_btn.clicked.connect(self._on_reset_custom_colors)
        # 设置重置图标
        reset_icon = icon_manager.get_icon("refresh-cw", "#409EFF", 16)
        self._reset_custom_colors_btn.setIcon(reset_icon)
        self._reset_custom_colors_btn.setIconSize(QSize(16, 16))

        self._preview_colors_btn = QPushButton("预览效果")
        self._preview_colors_btn.setToolTip("立即应用当前颜色设置进行预览（不保存）")
        self._preview_colors_btn.clicked.connect(self._on_preview_custom_colors)
        # 设置预览图标
        preview_icon = icon_manager.get_icon("eye", "#409EFF", 16)
        self._preview_colors_btn.setIcon(preview_icon)
        self._preview_colors_btn.setIconSize(QSize(16, 16))

        reset_btn_layout.addWidget(self._reset_custom_colors_btn)
        reset_btn_layout.addWidget(self._preview_colors_btn)
        reset_btn_layout.addStretch()

        reset_section.add_widget(reset_btn_row)
        layout.addWidget(reset_section)

        # 说明信息
        info_section = SettingsSection("使用说明")
        info_label = QLabel(
            "• 启用自定义颜色后，您设置的颜色将覆盖当前主题的对应颜色。\n"
            "• 留空的颜色项将使用当前主题的默认颜色。\n"
            "• 点击颜色预览框可打开颜色选择器，支持 RGBA 透明色。\n"
            "• 更换主题后，自定义颜色仍然有效。\n"
            "• 【即时生效】保存后颜色立即应用到所有界面。\n"
            "\n"
            "颜色对应关系示例：\n"
            "  - 主色调 → 保存按钮、选中的标签页\n"
            "  - 主背景色 → 聊天窗口整体背景\n"
            "  - 次背景色 → 输入框区域、设置面板\n"
            "  - 用户气泡背景 → 您发送的消息（右侧）\n"
            "  - AI气泡背景 → AI回复的消息（左侧）"
        )
        info_label.setWordWrap(True)
        info_label.setObjectName("infoLabel")
        info_section.add_widget(info_label)

        layout.addWidget(info_section)
        layout.addStretch()

        # 设置滚动内容
        scroll_area.setWidget(scroll_content)
        tab_layout.addWidget(scroll_area)

        return tab

    def _add_color_group(self, section: SettingsSection, colors: list):
        """添加一组颜色选择器到设置分区

        Args:
            section: 设置分区
            colors: 颜色配置列表，每项为 (key, label, tooltip)
        """
        for key, label, tooltip in colors:
            row = QFrame()
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(0, 0, 0, 0)
            row_layout.setSpacing(12)

            # 标签
            lbl = QLabel(label)
            lbl.setObjectName("settingLabel")
            lbl.setMinimumWidth(100)
            lbl.setToolTip(tooltip)

            # 颜色预览按钮
            color_btn = ColorPickerButton()
            color_btn.setToolTip(f"点击选择{label}")
            color_btn.color_changed.connect(
                lambda c, k=key: self._on_color_changed(k, c)
            )
            self._color_pickers[key] = color_btn

            # 清除按钮
            clear_btn = QPushButton()
            clear_btn.setObjectName("clearColorBtn")
            clear_btn.setFixedSize(24, 24)
            clear_btn.setToolTip("清除此颜色")
            clear_btn.clicked.connect(lambda checked, k=key: self._on_clear_color(k))
            # 设置关闭图标
            close_icon = icon_manager.get_icon("close", "#909399", 14)
            clear_btn.setIcon(close_icon)
            clear_btn.setIconSize(QSize(14, 14))

            row_layout.addWidget(lbl)
            row_layout.addWidget(color_btn)
            row_layout.addWidget(clear_btn)
            row_layout.addStretch()

            section.add_widget(row)

    def _on_custom_colors_toggle(self, state):
        """自定义颜色开关变化"""
        enabled = state == Qt.CheckState.Checked.value
        # 更新所有颜色选择器的可用状态
        for picker in self._color_pickers.values():
            picker.setEnabled(enabled)

    def _on_color_changed(self, key: str, color: str):
        """颜色变化回调"""
        # 颜色变化时可以选择立即预览
        pass

    def _on_clear_color(self, key: str):
        """清除指定颜色"""
        if key in self._color_pickers:
            self._color_pickers[key].clear_color()

    def _on_reset_custom_colors(self):
        """恢复默认颜色"""
        reply = QMessageBox.question(
            self,
            "确认恢复",
            "确定要清除所有自定义颜色吗？\n这将恢复为当前主题的默认颜色。",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )

        if reply == QMessageBox.StandardButton.Yes:
            # 清除所有颜色选择器
            for picker in self._color_pickers.values():
                picker.clear_color()
            # 禁用自定义颜色
            self._custom_colors_enabled.setChecked(False)
            # 重置主题管理器的自定义颜色
            theme_manager.reset_custom_colors()
            QMessageBox.information(self, "成功", "已恢复默认颜色。")

    def _on_preview_custom_colors(self):
        """预览自定义颜色效果"""
        if not self._custom_colors_enabled.isChecked():
            QMessageBox.information(self, "提示", "请先启用自定义颜色。")
            return

        # 构建临时配置并应用
        custom_config = self._build_custom_theme_config()
        theme_manager.apply_custom_colors(custom_config)
        QMessageBox.information(
            self,
            "预览",
            "自定义颜色已应用预览。\n点击「保存」永久保存，或点击「重置」取消。",
        )

    def _build_custom_theme_config(self) -> CustomThemeConfig:
        """从 UI 构建 CustomThemeConfig 对象"""
        config = CustomThemeConfig()
        config.enabled = self._custom_colors_enabled.isChecked()

        # 遍历所有颜色选择器
        for key, picker in self._color_pickers.items():
            if hasattr(config, key):
                setattr(config, key, picker.color)

        return config

    def _on_browse_storage_path(self):
        """浏览存储路径"""
        path = QFileDialog.getExistingDirectory(
            self, "选择保存目录", self._image_save_path.text() or os.getcwd()
        )
        if path:
            self._image_save_path.setText(path)

    def _on_browse_chat_history_path(self):
        """浏览聊天记录保存路径"""
        path, _ = QFileDialog.getSaveFileName(
            self,
            "选择聊天记录保存位置",
            self._chat_history_path.text() or "chat_history.json",
            "JSON 文件 (*.json)",
        )
        if path:
            self._chat_history_path.setText(path)

    def _on_clear_chat_history(self):
        """清空聊天记录"""
        chat_manager = get_chat_history_manager()
        msg_count = chat_manager.get_message_count()

        if msg_count == 0:
            QMessageBox.information(self, "提示", "聊天记录已经是空的。")
            return

        reply = QMessageBox.question(
            self,
            "确认清空",
            f"确定要清空所有 {msg_count} 条聊天记录吗？\n此操作不可恢复！",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )

        if reply == QMessageBox.StandardButton.Yes:
            chat_manager.clear_history()
            self._chat_count_label.setText("当前共 0 条消息")
            QMessageBox.information(self, "成功", "聊天记录已清空。")

    def _create_update_tab(self) -> QWidget:
        """创建更新设置标签页"""
        tab = QWidget()
        tab_layout = QVBoxLayout(tab)
        tab_layout.setContentsMargins(0, 0, 0, 0)

        # 创建滚动区域
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll_area.setFrameShape(QFrame.Shape.NoFrame)

        # 滚动内容容器
        scroll_content = QWidget()
        layout = QVBoxLayout(scroll_content)
        layout.setContentsMargins(16, 16, 16, 16)

        # 更新模式设置
        mode_section = SettingsSection("更新模式")

        self._update_mode = QComboBox()
        self._update_mode.addItem("📦 稳定版 (Release)", "release")
        self._update_mode.addItem("🔥 最新版 (Git)", "git")
        self._update_mode.setToolTip(
            "稳定版：从 GitHub Releases 获取经过测试的稳定版本\n"
            "最新版：直接拉取 Git 仓库的最新代码（可能包含未测试的功能）"
        )
        mode_section.add_row("更新通道", self._update_mode)

        mode_info = QLabel(
            "• 稳定版：推荐普通用户使用，版本经过测试更加稳定\n"
            "• 最新版：适合开发者或想体验新功能的用户"
        )
        mode_info.setWordWrap(True)
        mode_info.setObjectName("infoLabel")
        mode_section.add_widget(mode_info)

        layout.addWidget(mode_section)

        # 基础设置
        basic_section = SettingsSection("自动更新")

        self._update_enabled = QCheckBox("启用自动更新")
        self._update_enabled.setToolTip("开启后，程序将自动检查并提示更新")
        self._update_enabled.stateChanged.connect(self._on_update_enabled_toggle)
        basic_section.add_widget(self._update_enabled)

        self._update_check_on_startup = QCheckBox("启动时检查更新")
        self._update_check_on_startup.setToolTip("每次启动程序时自动检查是否有新版本")
        basic_section.add_widget(self._update_check_on_startup)

        self._update_auto_restart = QCheckBox("更新后自动重启")
        self._update_auto_restart.setToolTip("更新完成后自动重启程序以应用更新")
        basic_section.add_widget(self._update_auto_restart)

        layout.addWidget(basic_section)

        # 定时更新设置
        schedule_section = SettingsSection("定时检查")

        schedule_info = QLabel("设置每天自动检查更新的时间点（HH:MM 格式）：")
        schedule_info.setWordWrap(True)
        schedule_info.setObjectName("infoLabel")
        schedule_section.add_widget(schedule_info)

        # 时间点列表容器
        self._schedule_times_container = QFrame()
        self._schedule_times_layout = QVBoxLayout(self._schedule_times_container)
        self._schedule_times_layout.setContentsMargins(0, 0, 0, 0)
        self._schedule_times_layout.setSpacing(8)
        schedule_section.add_widget(self._schedule_times_container)

        # 存储时间编辑器列表
        self._schedule_time_editors = []

        # 添加时间按钮
        add_time_btn_row = QFrame()
        add_time_btn_layout = QHBoxLayout(add_time_btn_row)
        add_time_btn_layout.setContentsMargins(0, 0, 0, 0)

        self._add_schedule_time_btn = QPushButton("添加时间点")
        self._add_schedule_time_btn.setToolTip("添加一个新的定时检查时间点")
        self._add_schedule_time_btn.clicked.connect(self._on_add_schedule_time)
        # 设置添加图标
        add_icon = icon_manager.get_icon("plus", "#409EFF", 16)
        self._add_schedule_time_btn.setIcon(add_icon)
        self._add_schedule_time_btn.setIconSize(QSize(16, 16))

        add_time_btn_layout.addWidget(self._add_schedule_time_btn)
        add_time_btn_layout.addStretch()

        schedule_section.add_widget(add_time_btn_row)

        layout.addWidget(schedule_section)

        # 版本信息
        version_section = SettingsSection("版本信息")

        # 当前版本
        self._current_version_label = QLabel("当前版本：获取中...")
        self._current_version_label.setObjectName("settingLabel")
        version_section.add_widget(self._current_version_label)

        # 最新版本（Release）
        self._latest_release_label = QLabel("最新稳定版：未检查")
        self._latest_release_label.setObjectName("infoLabel")
        version_section.add_widget(self._latest_release_label)

        # 上次检查时间
        self._last_check_label = QLabel("上次检查：从未检查")
        self._last_check_label.setObjectName("infoLabel")
        version_section.add_widget(self._last_check_label)

        layout.addWidget(version_section)

        # 手动操作
        action_section = SettingsSection("手动操作")

        action_btn_row = QFrame()
        action_btn_layout = QHBoxLayout(action_btn_row)
        action_btn_layout.setContentsMargins(0, 0, 0, 0)
        action_btn_layout.setSpacing(12)

        self._check_update_btn = QPushButton("立即检查更新")
        self._check_update_btn.setToolTip("检查是否有新版本可用")
        self._check_update_btn.clicked.connect(self._on_check_update)
        # 设置检查图标
        check_icon = icon_manager.get_icon("refresh-cw", "#409EFF", 16)
        self._check_update_btn.setIcon(check_icon)
        self._check_update_btn.setIconSize(QSize(16, 16))

        self._perform_update_btn = QPushButton("立即更新")
        self._perform_update_btn.setObjectName("saveBtn")
        self._perform_update_btn.setToolTip("执行更新操作（将打开更新脚本）")
        self._perform_update_btn.clicked.connect(self._on_perform_update)
        # 设置更新图标
        update_icon = icon_manager.get_icon("download", "#FFFFFF", 16)
        self._perform_update_btn.setIcon(update_icon)
        self._perform_update_btn.setIconSize(QSize(16, 16))

        action_btn_layout.addWidget(self._check_update_btn)
        action_btn_layout.addWidget(self._perform_update_btn)
        action_btn_layout.addStretch()

        action_section.add_widget(action_btn_row)

        # 更新状态显示
        self._update_status_label = QLabel("")
        self._update_status_label.setWordWrap(True)
        self._update_status_label.setObjectName("infoLabel")
        action_section.add_widget(self._update_status_label)

        layout.addWidget(action_section)

        # 说明信息
        info_section = SettingsSection("功能说明")
        info_label = QLabel(
            "• 稳定版模式：从 GitHub Releases 获取版本，更新到指定的 Release 标签。\n"
            "• 最新版模式：直接拉取 Git 仓库的最新代码，获得最新功能。\n"
            "• 启用自动更新后，程序将在定时时间点自动检查是否有新版本。\n"
            "• 检测到更新时，会弹出提示通知您。\n"
            "• 点击「立即更新」将运行 update.bat/update.sh 脚本执行更新。\n"
            "• 更新过程中请勿关闭更新窗口，更新完成后程序将自动重启（如已启用）。"
        )
        info_label.setWordWrap(True)
        info_label.setObjectName("infoLabel")
        info_section.add_widget(info_label)

        layout.addWidget(info_section)
        layout.addStretch()

        # 设置滚动内容
        scroll_area.setWidget(scroll_content)
        tab_layout.addWidget(scroll_area)

        return tab

    def _on_update_enabled_toggle(self, state):
        """自动更新开关变化"""
        enabled = state == Qt.CheckState.Checked.value
        self._update_check_on_startup.setEnabled(enabled)
        self._update_auto_restart.setEnabled(enabled)
        self._add_schedule_time_btn.setEnabled(enabled)
        # 更新所有时间编辑器的状态
        for time_row in self._schedule_time_editors:
            time_row["editor"].setEnabled(enabled)
            time_row["remove_btn"].setEnabled(enabled)

    def _on_add_schedule_time(self):
        """添加定时检查时间点"""
        self._add_schedule_time_row(QTime(12, 0))

    def _add_schedule_time_row(self, time: QTime):
        """添加一个时间点行"""
        row = QFrame()
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(8)

        time_edit = QTimeEdit()
        time_edit.setDisplayFormat("HH:mm")
        time_edit.setTime(time)
        time_edit.setEnabled(self._update_enabled.isChecked())

        remove_btn = QPushButton()
        remove_btn.setFixedSize(24, 24)
        remove_btn.setToolTip("删除此时间点")
        remove_btn.setEnabled(self._update_enabled.isChecked())
        # 设置删除图标
        close_icon = icon_manager.get_icon("close", "#FF3B30", 14)
        remove_btn.setIcon(close_icon)
        remove_btn.setIconSize(QSize(14, 14))

        row_layout.addWidget(time_edit)
        row_layout.addWidget(remove_btn)
        row_layout.addStretch()

        # 记录信息
        time_row_info = {"row": row, "editor": time_edit, "remove_btn": remove_btn}
        self._schedule_time_editors.append(time_row_info)

        # 连接删除按钮
        remove_btn.clicked.connect(lambda: self._on_remove_schedule_time(time_row_info))

        self._schedule_times_layout.addWidget(row)

    def _on_remove_schedule_time(self, time_row_info: dict):
        """删除时间点"""
        if time_row_info in self._schedule_time_editors:
            self._schedule_time_editors.remove(time_row_info)
            time_row_info["row"].deleteLater()

    def _on_check_update(self):
        """立即检查更新"""
        self._check_update_btn.setEnabled(False)
        self._check_update_btn.setText("检查中...")
        self._update_status_label.setText("正在检查更新...")

        # 发射信号或调用服务
        # 这里通过信号通知主应用进行检查
        if hasattr(self, "_update_check_callback") and self._update_check_callback:
            self._update_check_callback()
        else:
            # 没有回调时，显示提示
            from PySide6.QtCore import QTimer

            QTimer.singleShot(1000, self._on_check_update_done)

    def _on_check_update_done(self, has_update: bool = False, message: str = ""):
        """检查更新完成回调"""
        self._check_update_btn.setEnabled(True)
        self._check_update_btn.setText("立即检查更新")

        if message:
            self._update_status_label.setText(message)
        elif has_update:
            self._update_status_label.setText(
                "发现新版本可用！点击「立即更新」进行更新。"
            )
        else:
            self._update_status_label.setText("当前已是最新版本。")

        # 更新上次检查时间
        from datetime import datetime

        self._last_check_label.setText(
            f"上次检查：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        )

    def _on_perform_update(self):
        """立即执行更新"""
        reply = QMessageBox.question(
            self,
            "确认更新",
            "确定要执行更新吗？\n\n更新过程将：\n1. 打开更新脚本窗口\n2. 从 GitHub 拉取最新代码\n3. 更新依赖项\n\n如果启用了「更新后自动重启」，程序将在更新完成后自动重启。",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )

        if reply == QMessageBox.StandardButton.Yes:
            self._update_status_label.setText("正在启动更新...")
            if (
                hasattr(self, "_update_perform_callback")
                and self._update_perform_callback
            ):
                self._update_perform_callback()
            else:
                QMessageBox.information(
                    self, "提示", "更新服务未初始化，请保存设置后重启程序。"
                )

    def set_update_callbacks(self, check_callback, perform_callback):
        """设置更新回调函数"""
        self._update_check_callback = check_callback
        self._update_perform_callback = perform_callback

    def update_version_info(self, current_version: str, last_check_time: str = ""):
        """更新版本信息显示"""
        self._current_version_label.setText(f"当前版本：{current_version or '未知'}")
        if last_check_time:
            self._last_check_label.setText(f"上次检查：{last_check_time}")

    def _create_proactive_tab(self) -> QWidget:
        """创建主动对话设置标签页"""
        tab = QWidget()
        tab_layout = QVBoxLayout(tab)
        tab_layout.setContentsMargins(0, 0, 0, 0)

        # 创建滚动区域
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll_area.setFrameShape(QFrame.Shape.NoFrame)

        # 滚动内容容器
        scroll_content = QWidget()
        layout = QVBoxLayout(scroll_content)
        layout.setContentsMargins(16, 16, 16, 16)

        # 基础设置
        basic_section = SettingsSection("基础设置")

        self._proactive_enabled = QCheckBox("启用主动对话")
        self._proactive_enabled.setToolTip("开启后，助手会根据屏幕内容主动发起对话")
        basic_section.add_widget(self._proactive_enabled)

        self._proactive_check_interval = QSpinBox()
        self._proactive_check_interval.setRange(30, 3600)
        self._proactive_check_interval.setSingleStep(30)
        self._proactive_check_interval.setSuffix(" 秒")
        self._proactive_check_interval.setToolTip("每隔多少秒检测一次是否触发主动对话")
        basic_section.add_row("检测间隔", self._proactive_check_interval)

        self._proactive_trigger_probability = QDoubleSpinBox()
        self._proactive_trigger_probability.setRange(0.01, 1.0)
        self._proactive_trigger_probability.setSingleStep(0.01)
        self._proactive_trigger_probability.setDecimals(2)
        self._proactive_trigger_probability.setToolTip(
            "每次检测时触发主动对话的概率（0.01-1.0）"
        )
        basic_section.add_row("触发概率", self._proactive_trigger_probability)

        layout.addWidget(basic_section)

        # 活跃检测设置
        active_section = SettingsSection("活跃检测")

        self._proactive_require_user_active = QCheckBox("仅在用户活跃时触发")
        self._proactive_require_user_active.setToolTip(
            "开启后，只有当用户最近有键盘或鼠标活动时才会触发主动对话"
        )
        active_section.add_widget(self._proactive_require_user_active)

        self._proactive_idle_threshold = QSpinBox()
        self._proactive_idle_threshold.setRange(5, 300)
        self._proactive_idle_threshold.setSingleStep(5)
        self._proactive_idle_threshold.setSuffix(" 秒")
        self._proactive_idle_threshold.setToolTip("用户无操作超过此时间后，视为不活跃")
        active_section.add_row("空闲阈值", self._proactive_idle_threshold)

        layout.addWidget(active_section)

        # 时间段限制
        time_section = SettingsSection("时间段限制")

        self._proactive_time_range_enabled = QCheckBox("启用时间段限制")
        self._proactive_time_range_enabled.setToolTip(
            "开启后，只在指定时间段内触发主动对话"
        )
        self._proactive_time_range_enabled.stateChanged.connect(
            self._on_time_range_toggle
        )
        time_section.add_widget(self._proactive_time_range_enabled)

        # 时间范围选择
        time_range_row = QFrame()
        time_range_layout = QHBoxLayout(time_range_row)
        time_range_layout.setContentsMargins(0, 0, 0, 0)

        start_label = QLabel("开始时间")
        start_label.setObjectName("settingLabel")
        self._proactive_time_range_start = QTimeEdit()
        self._proactive_time_range_start.setDisplayFormat("HH:mm")
        self._proactive_time_range_start.setToolTip("主动对话开始时间")

        end_label = QLabel("结束时间")
        end_label.setObjectName("settingLabel")
        self._proactive_time_range_end = QTimeEdit()
        self._proactive_time_range_end.setDisplayFormat("HH:mm")
        self._proactive_time_range_end.setToolTip("主动对话结束时间")

        time_range_layout.addWidget(start_label)
        time_range_layout.addWidget(self._proactive_time_range_start)
        time_range_layout.addSpacing(20)
        time_range_layout.addWidget(end_label)
        time_range_layout.addWidget(self._proactive_time_range_end)
        time_range_layout.addStretch()

        time_section.add_widget(time_range_row)

        layout.addWidget(time_section)

        # 说明信息
        info_section = SettingsSection("功能说明")
        info_label = QLabel(
            "主动对话功能允许助手定期截取屏幕内容，并根据当前屏幕上的信息主动发起对话。\n"
            "这可以帮助您获得更加智能的陪伴体验，但可能会消耗更多的API调用次数。"
        )
        info_label.setWordWrap(True)
        info_label.setObjectName("infoLabel")
        info_section.add_widget(info_label)

        layout.addWidget(info_section)
        layout.addStretch()

        # 设置滚动内容
        scroll_area.setWidget(scroll_content)
        tab_layout.addWidget(scroll_area)

        return tab

    def _on_time_range_toggle(self, state):
        """时间段限制开关变化"""
        enabled = state == Qt.CheckState.Checked.value
        self._proactive_time_range_start.setEnabled(enabled)
        self._proactive_time_range_end.setEnabled(enabled)

    def _create_bottom_bar(self) -> QFrame:
        """创建底部按钮栏"""
        bar = QFrame()
        bar.setObjectName("bottomBar")
        bar.setFixedHeight(60)

        layout = QHBoxLayout(bar)
        layout.setContentsMargins(16, 0, 16, 0)

        layout.addStretch()

        self._reset_btn = QPushButton("重置")
        self._reset_btn.setObjectName("resetBtn")
        self._reset_btn.clicked.connect(self._on_reset)

        self._save_btn = QPushButton("保存")
        self._save_btn.setObjectName("saveBtn")
        self._save_btn.clicked.connect(self._on_save)

        layout.addWidget(self._reset_btn)
        layout.addWidget(self._save_btn)

        return bar

    def _on_theme_changed(self, theme: Theme):
        """主题变化回调"""
        self._apply_theme()

    def _apply_theme(self):
        """应用主题样式"""
        t = theme_manager.current_theme
        c = (
            theme_manager.get_current_colors()
        )  # 使用 get_current_colors() 获取应用了自定义颜色的最终配置

        self.setStyleSheet(f"""
            QWidget {{
                background-color: {c.bg_primary};
                font-family: {t.font_family};
                color: {c.text_primary};
            }}
            
            QFrame#titleBar {{
                background-color: {c.bg_secondary};
                border-bottom: 1px solid {c.border_light};
            }}
            
            QLabel#titleIcon {{
                font-size: 24px;
                background: transparent;
            }}
            
            QLabel#titleText {{
                font-size: {t.font_size_large}px;
                font-weight: bold;
                background: transparent;
                line-height: 50px;
            }}

            QTabWidget#settingsTabs {{
                background-color: {c.bg_primary};
            }}
            QTabWidget#settingsTabs::pane {{
                border: none;
                background-color: {c.bg_primary};
            }}
            QTabBar::tab {{
                background-color: {c.bg_secondary};
                color: {c.text_secondary};
                padding: 12px 20px;
                border: none;
                border-bottom: 2px solid transparent;
                min-height: 40px;
            }}
            QTabBar::tab:selected {{
                color: {c.primary};
                border-bottom-color: {c.primary};
            }}
            QTabBar::tab:hover {{
                background-color: {c.bg_hover};
            }}
            
            QLabel#sectionTitle {{
                font-size: {t.font_size_base + 2}px;
                font-weight: bold;
                color: {c.text_primary};
                background: transparent;
            }}
            
            QFrame#sectionContent {{
                background-color: {c.bg_secondary};
                border: 1px solid {c.border_light};
                border-radius: {t.border_radius}px;
            }}
            
            QLabel#settingLabel {{
                color: {c.text_secondary};
                background: transparent;
                min-height: 24px;
                line-height: 24px;
            }}

            QLabel#infoLabel {{
                color: {c.text_secondary};
                background: transparent;
                line-height: 1.6;
            }}

            QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox, QKeySequenceEdit, QTimeEdit {{
                background-color: {c.bg_primary};
                border: 1px solid {c.border_light};
                border-radius: {t.border_radius}px;
                padding: 6px 10px;
                color: {c.text_primary};
                min-height: 28px;
            }}
            QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus, QKeySequenceEdit:focus, QTimeEdit:focus {{
                border-color: {c.primary};
            }}
            
            QComboBox::drop-down {{
                border: none;
                width: 30px;
            }}
            QComboBox::down-arrow {{
                image: none;
                border-left: 5px solid transparent;
                border-right: 5px solid transparent;
                border-top: 5px solid {c.text_secondary};
                margin-right: 10px;
            }}

            /* 下拉框列表样式 */
            QComboBox QAbstractItemView {{
                background-color: {c.bg_primary};
                border: 1px solid {c.border_light};
                border-radius: {t.border_radius}px;
                selection-background-color: {c.bg_hover};
                selection-color: {c.text_primary};
                outline: none;
            }}
            QComboBox QAbstractItemView::item {{
                min-height: 28px;
                padding: 6px 10px;
                color: {c.text_primary};
            }}
            QComboBox QAbstractItemView::item:hover {{
                background-color: {c.bg_hover};
            }}
            QComboBox QAbstractItemView::item:selected {{
                background-color: {c.primary_light};
                color: white;
            }}

            /* 隐藏数值输入框的增减按钮 */
            QSpinBox::up-button, QDoubleSpinBox::up-button {{
                width: 0px;
                border: none;
            }}
            QSpinBox::down-button, QDoubleSpinBox::down-button {{
                width: 0px;
                border: none;
            }}

            QCheckBox {{
                color: {c.text_primary};
                spacing: 8px;
            }}
            QCheckBox::indicator {{
                width: 18px;
                height: 18px;
                border-radius: 4px;
                border: 1px solid {c.border_base};
            }}
            QCheckBox::indicator:checked {{
                background-color: {c.primary};
                border-color: {c.primary};
            }}
            
            QLabel#avatarPreview {{
                background-color: {c.bg_tertiary};
                border-radius: 32px;
                font-size: 32px;
            }}
            
            QPushButton {{
                background-color: {c.bg_secondary};
                border: 1px solid {c.border_light};
                border-radius: {t.border_radius}px;
                padding: 6px 14px;
                color: {c.text_primary};
                min-height: 28px;
            }}
            QPushButton:hover {{
                background-color: {c.bg_hover};
            }}

            /* 清除颜色按钮样式 */
            QPushButton#clearColorBtn {{
                background-color: transparent;
                border: 1px solid {c.border_light};
                border-radius: 4px;
                padding: 0px;
                min-height: 24px;
            }}
            QPushButton#clearColorBtn:hover {{
                background-color: {c.bg_hover};
                border-color: {c.danger};
            }}
            QPushButton#clearColorBtn:pressed {{
                background-color: {c.danger};
            }}
            
            QPushButton#saveBtn {{
                background-color: {c.primary};
                color: white;
                border: none;
                font-weight: bold;
                min-width: 80px;
            }}
            QPushButton#saveBtn:hover {{
                background-color: {c.primary_dark};
            }}
            
            QPushButton#testBtn {{
                background-color: {c.success};
                color: white;
                border: none;
            }}
            QPushButton#testBtn:hover {{
                background-color: #218838;
            }}
            
            QPushButton#dangerBtn {{
                background-color: #dc3545;
                color: white;
                border: none;
            }}
            QPushButton#dangerBtn:hover {{
                background-color: #c82333;
            }}
            
            QFrame#bottomBar {{
                background-color: {c.bg_secondary};
                border-top: 1px solid {c.border_light};
            }}

            /* 滚动条样式 */
            QScrollBar:vertical {{
                background-color: {c.bg_secondary};
                width: 12px;
                border-radius: 6px;
                margin: 0px;
            }}
            QScrollBar::handle:vertical {{
                background-color: {c.border_base};
                border-radius: 6px;
                min-height: 30px;
            }}
            QScrollBar::handle:vertical:hover {{
                background-color: {c.text_secondary};
            }}
            QScrollBar::handle:vertical:pressed {{
                background-color: {c.primary};
            }}
            QScrollBar::add-line:vertical,
            QScrollBar::sub-line:vertical {{
                height: 0px;
            }}
            QScrollBar::add-page:vertical,
            QScrollBar::sub-page:vertical {{
                background: none;
            }}

            QScrollBar:horizontal {{
                background-color: {c.bg_secondary};
                height: 12px;
                border-radius: 6px;
                margin: 0px;
            }}
            QScrollBar::handle:horizontal {{
                background-color: {c.border_base};
                border-radius: 6px;
                min-width: 30px;
            }}
            QScrollBar::handle:horizontal:hover {{
                background-color: {c.text_secondary};
            }}
            QScrollBar::handle:horizontal:pressed {{
                background-color: {c.primary};
            }}
            QScrollBar::add-line:horizontal,
            QScrollBar::sub-line:horizontal {{
                width: 0px;
            }}
            QScrollBar::add-page:horizontal,
            QScrollBar::sub-page:horizontal {{
                background: none;
            }}
        """)

    def _load_settings(self):
        """加载设置"""
        # 服务器设置
        if hasattr(self.config, "server"):  # ClientConfig object
            self._server_url.setText(self.config.server.url or "")
            self._username.setText(self.config.server.username or "")
            self._password.setText(self.config.server.password or "")
            self._enable_streaming.setChecked(self.config.server.enable_streaming)
        elif isinstance(self.config, dict):  # Dict
            self._server_url.setText(self.config.get("server_url", ""))
            self._username.setText(self.config.get("username", ""))
            self._password.setText(self.config.get("password", ""))

        # 外观设置
        if hasattr(self.config, "appearance"):
            self._ball_size.setValue(self.config.appearance.ball_size)
            self._breathing_enabled.setChecked(self.config.appearance.breathing_enabled)

            # 悬浮球头像
            if self.config.appearance.avatar_path:
                self._avatar_path = self.config.appearance.avatar_path
                pixmap = QPixmap(self._avatar_path)
                if not pixmap.isNull():
                    pixmap = pixmap.scaled(
                        64,
                        64,
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation,
                    )
                    self._avatar_preview.setPixmap(pixmap)

            # 用户头像
            if (
                hasattr(self.config.appearance, "user_avatar_path")
                and self.config.appearance.user_avatar_path
            ):
                self._user_avatar_path = self.config.appearance.user_avatar_path
                pixmap = QPixmap(self._user_avatar_path)
                if not pixmap.isNull():
                    pixmap = pixmap.scaled(
                        48,
                        48,
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation,
                    )
                    self._user_avatar_preview.setPixmap(pixmap)
            else:
                self._user_avatar_path = ""

            # Bot头像
            if (
                hasattr(self.config.appearance, "bot_avatar_path")
                and self.config.appearance.bot_avatar_path
            ):
                self._bot_avatar_path = self.config.appearance.bot_avatar_path
                pixmap = QPixmap(self._bot_avatar_path)
                if not pixmap.isNull():
                    pixmap = pixmap.scaled(
                        48,
                        48,
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation,
                    )
                    self._bot_avatar_preview.setPixmap(pixmap)
            else:
                self._bot_avatar_path = ""

            # 开机自启 - 优先从注册表读取实际状态
            if os.name == "nt":
                self._auto_start.setChecked(is_autostart_enabled())
        else:
            self._user_avatar_path = ""
            self._bot_avatar_path = ""

        # 主题设置
        current_theme = theme_manager.current_theme.name
        for i in range(self._theme_combo.count()):
            if self._theme_combo.itemData(i) == current_theme:
                self._theme_combo.setCurrentIndex(i)
                break

        # 快捷键设置
        if hasattr(self.config, "hotkeys"):
            # 从保存的配置加载
            self._global_hotkeys.setChecked(self.config.hotkeys.global_enabled)
            for key, edit in self._hotkey_inputs.items():
                if hasattr(self.config.hotkeys, key):
                    edit.setKeySequence(getattr(self.config.hotkeys, key))
        else:
            # 从 hotkey_manager 加载
            hotkey_config = hotkey_manager.get_config()
            config_dict = hotkey_config.to_dict()
            for key, edit in self._hotkey_inputs.items():
                if key in config_dict:
                    edit.setKeySequence(config_dict[key])

        # 交互设置
        if hasattr(self.config, "interaction"):
            # 默认模式
            for i in range(self._default_mode.count()):
                if (
                    self._default_mode.itemData(i)
                    == self.config.interaction.default_mode
                ):
                    self._default_mode.setCurrentIndex(i)
                    break
            # 单击动作
            for i in range(self._single_click_action.count()):
                if (
                    self._single_click_action.itemData(i)
                    == self.config.interaction.single_click
                ):
                    self._single_click_action.setCurrentIndex(i)
                    break
            # 双击动作
            for i in range(self._double_click_action.count()):
                if (
                    self._double_click_action.itemData(i)
                    == self.config.interaction.double_click
                ):
                    self._double_click_action.setCurrentIndex(i)
                    break
            # 气泡设置
            self._bubble_duration.setValue(self.config.interaction.bubble_duration)
            self._bubble_auto_hide.setChecked(self.config.interaction.bubble_auto_hide)

        # 语音设置
        if hasattr(self.config, "voice"):
            self._auto_play_voice.setChecked(self.config.voice.auto_play_voice)

        # 免打扰模式
        if hasattr(self.config, "interaction") and hasattr(
            self.config.interaction, "do_not_disturb"
        ):
            self._do_not_disturb.setChecked(self.config.interaction.do_not_disturb)
        else:
            self._do_not_disturb.setChecked(False)

        # 主动对话设置
        if hasattr(self.config, "proactive"):
            self._proactive_enabled.setChecked(self.config.proactive.enabled)
            self._proactive_check_interval.setValue(
                self.config.proactive.check_interval
            )
            self._proactive_trigger_probability.setValue(
                self.config.proactive.trigger_probability
            )
            self._proactive_require_user_active.setChecked(
                self.config.proactive.require_user_active
            )
            self._proactive_idle_threshold.setValue(
                self.config.proactive.idle_threshold
            )
            self._proactive_time_range_enabled.setChecked(
                self.config.proactive.time_range_enabled
            )

            # 解析时间字符串
            start_time = QTime.fromString(
                self.config.proactive.time_range_start, "HH:mm"
            )
            if start_time.isValid():
                self._proactive_time_range_start.setTime(start_time)
            else:
                self._proactive_time_range_start.setTime(QTime(9, 0))

            end_time = QTime.fromString(self.config.proactive.time_range_end, "HH:mm")
            if end_time.isValid():
                self._proactive_time_range_end.setTime(end_time)
            else:
                self._proactive_time_range_end.setTime(QTime(22, 0))

            # 根据启用状态设置时间控件的可用性
            self._proactive_time_range_start.setEnabled(
                self.config.proactive.time_range_enabled
            )
            self._proactive_time_range_end.setEnabled(
                self.config.proactive.time_range_enabled
            )
        else:
            # 使用默认值
            self._proactive_enabled.setChecked(False)
            self._proactive_check_interval.setValue(600)
            self._proactive_trigger_probability.setValue(0.2)
            self._proactive_require_user_active.setChecked(True)
            self._proactive_idle_threshold.setValue(60)
            self._proactive_time_range_enabled.setChecked(False)
            self._proactive_time_range_start.setTime(QTime(9, 0))
            self._proactive_time_range_end.setTime(QTime(22, 0))
            self._proactive_time_range_start.setEnabled(False)
            self._proactive_time_range_end.setEnabled(False)

        # 存储设置
        if hasattr(self.config, "storage"):
            self._image_save_path.setText(self.config.storage.image_save_path or "")
            self._chat_history_path.setText(self.config.storage.chat_history_path or "")

            # 确保图片保存路径显示正确
            self._image_save_path.setText(self.config.storage.image_save_path or "")

            # 更新聊天记录数量
        chat_manager = get_chat_history_manager()
        msg_count = chat_manager.get_message_count()
        self._chat_count_label.setText(f"当前共 {msg_count} 条消息")

        # 自定义颜色设置
        if hasattr(self.config, "appearance") and hasattr(
            self.config.appearance, "custom_theme"
        ):
            custom_theme = self.config.appearance.custom_theme
            self._custom_colors_enabled.setChecked(custom_theme.enabled)

            # 加载各个颜色值到选择器
            color_fields = [
                "primary",
                "primary_light",
                "primary_dark",
                "bg_primary",
                "bg_secondary",
                "text_primary",
                "text_secondary",
                "system_notice_text",
                "ball_bg",
                "ball_glow",
                "ball_border",
                "bubble_user_bg",
                "bubble_user_text",
                "bubble_ai_bg",
                "bubble_ai_text",
            ]
            for field in color_fields:
                if field in self._color_pickers:
                    color_value = getattr(custom_theme, field, "")
                    self._color_pickers[field].color = color_value

            # 根据启用状态设置颜色选择器的可用性
            for picker in self._color_pickers.values():
                picker.setEnabled(custom_theme.enabled)
        else:
            # 默认禁用
            self._custom_colors_enabled.setChecked(False)
            for picker in self._color_pickers.values():
                picker.setEnabled(False)

        # 更新设置
        if hasattr(self.config, "update"):
            self._update_enabled.setChecked(self.config.update.enabled)
            self._update_check_on_startup.setChecked(
                self.config.update.check_on_startup
            )
            self._update_auto_restart.setChecked(self.config.update.auto_restart)

            # 更新模式
            update_mode = getattr(self.config.update, "update_mode", "release")
            for i in range(self._update_mode.count()):
                if self._update_mode.itemData(i) == update_mode:
                    self._update_mode.setCurrentIndex(i)
                    break

            # 加载定时时间列表
            for time_str in self.config.update.scheduled_times:
                time = QTime.fromString(time_str, "HH:mm")
                if time.isValid():
                    self._add_schedule_time_row(time)

            # 如果没有配置时间，添加默认时间
            if not self.config.update.scheduled_times:
                self._add_schedule_time_row(QTime(12, 0))
                self._add_schedule_time_row(QTime(18, 0))

            # 更新版本信息
            if self.config.update.current_version:
                self._current_version_label.setText(
                    f"当前版本：{self.config.update.current_version}"
                )
            if self.config.update.last_check_time:
                self._last_check_label.setText(
                    f"上次检查：{self.config.update.last_check_time}"
                )

            # 最新 Release 版本
            latest_release = getattr(self.config.update, "latest_release_version", "")
            if latest_release:
                self._latest_release_label.setText(f"最新稳定版：{latest_release}")

            # 根据启用状态设置控件可用性
            enabled = self.config.update.enabled
            self._update_check_on_startup.setEnabled(enabled)
            self._update_auto_restart.setEnabled(enabled)
            self._add_schedule_time_btn.setEnabled(enabled)
        else:
            # 默认值
            self._update_enabled.setChecked(False)
            self._update_check_on_startup.setChecked(True)
            self._update_auto_restart.setChecked(False)
            self._update_mode.setCurrentIndex(0)  # 默认稳定版
            self._add_schedule_time_row(QTime(12, 0))
            self._add_schedule_time_row(QTime(18, 0))
            # 禁用相关控件
            self._update_check_on_startup.setEnabled(False)
            self._update_auto_restart.setEnabled(False)
            self._add_schedule_time_btn.setEnabled(False)

    def _on_theme_selected(self, index: int):
        """主题选择变化"""
        theme_name = self._theme_combo.itemData(index)
        if theme_name:
            theme_manager.set_theme(theme_name)

    def _on_upload_avatar(self):
        """上传悬浮球头像"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "选择头像图片", "", "图片文件 (*.png *.jpg *.jpeg *.gif *.bmp *.webp)"
        )
        if file_path:
            pixmap = QPixmap(file_path)
            if not pixmap.isNull():
                # 缩放预览
                pixmap = pixmap.scaled(
                    64,
                    64,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
                self._avatar_preview.setPixmap(pixmap)
                self._avatar_path = file_path

    def _on_reset_avatar(self):
        """重置悬浮球头像"""
        self._avatar_preview.clear()
        c = theme_manager.get_current_colors()
        self._avatar_preview.setPixmap(
            icon_manager.get_pixmap("bot", c.text_primary, 40)
        )
        self._avatar_path = ""

    def _on_upload_user_avatar(self):
        """上传用户头像"""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "选择用户头像图片",
            "",
            "图片文件 (*.png *.jpg *.jpeg *.gif *.bmp *.webp)",
        )
        if file_path:
            pixmap = QPixmap(file_path)
            if not pixmap.isNull():
                # 缩放预览为圆形
                pixmap = pixmap.scaled(
                    48,
                    48,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
                self._user_avatar_preview.setPixmap(pixmap)
                self._user_avatar_path = file_path

    def _on_reset_user_avatar(self):
        """重置用户头像"""
        self._user_avatar_preview.clear()
        c = theme_manager.get_current_colors()
        self._user_avatar_preview.setPixmap(
            icon_manager.get_pixmap("user", c.text_primary, 32)
        )
        self._user_avatar_path = ""

    def _on_upload_bot_avatar(self):
        """上传Bot头像"""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "选择Bot头像图片",
            "",
            "图片文件 (*.png *.jpg *.jpeg *.gif *.bmp *.webp)",
        )
        if file_path:
            pixmap = QPixmap(file_path)
            if not pixmap.isNull():
                # 缩放预览
                pixmap = pixmap.scaled(
                    48,
                    48,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
                self._bot_avatar_preview.setPixmap(pixmap)
                self._bot_avatar_path = file_path

    def _on_reset_bot_avatar(self):
        """重置Bot头像"""
        self._bot_avatar_preview.clear()
        c = theme_manager.get_current_colors()
        self._bot_avatar_preview.setPixmap(
            icon_manager.get_pixmap("bot", c.text_primary, 32)
        )
        self._bot_avatar_path = ""

    @asyncSlot()
    async def _on_test_connection(self):
        """测试连接"""
        url = self._server_url.text().strip()
        username = self._username.text().strip()
        password = self._password.text().strip()

        if not url:
            QMessageBox.warning(self, "错误", "请输入服务器地址")
            return

        if not username or not password:
            QMessageBox.warning(self, "错误", "请输入用户名和密码")
            return

        self._test_btn.setEnabled(False)
        self._test_btn.setText("正在连接...")

        try:
            # 使用临时客户端测试
            client = AstrBotApiClient(
                server_url=url, username=username, password=password, timeout=5
            )
            success, msg = await client.login()
            await client.close()

            if success:
                QMessageBox.information(self, "成功", f"连接成功！\n{msg}")
            else:
                QMessageBox.warning(self, "失败", f"连接失败: {msg}")

        except Exception as e:
            QMessageBox.critical(self, "错误", f"发生错误: {str(e)}")
        finally:
            self._test_btn.setEnabled(True)
            self._test_btn.setText("测试连接")

    def _on_reset(self):
        """重置设置"""
        self._load_settings()

    def _on_save(self):
        """保存设置"""
        settings = {
            "server": {
                "url": self._server_url.text(),
                "username": self._username.text(),
                "password": self._password.text(),
                "enable_streaming": self._enable_streaming.isChecked(),
            },
            "appearance": {
                "theme": self._theme_combo.currentData(),
                "avatar_path": getattr(self, "_avatar_path", ""),
                "user_avatar_path": getattr(self, "_user_avatar_path", ""),
                "bot_avatar_path": getattr(self, "_bot_avatar_path", ""),
                "ball_size": self._ball_size.value(),
                "breathing_enabled": self._breathing_enabled.isChecked(),
                "auto_start": self._auto_start.isChecked(),
            },
            "hotkeys": {
                "global_enabled": self._global_hotkeys.isChecked(),
                **{
                    key: edit.keySequence().toString()
                    for key, edit in self._hotkey_inputs.items()
                },
            },
            "interaction": {
                "default_mode": self._default_mode.currentData(),
                "single_click": self._single_click_action.currentData(),
                "double_click": self._double_click_action.currentData(),
                "bubble_duration": self._bubble_duration.value(),
                "bubble_auto_hide": self._bubble_auto_hide.isChecked(),
                "do_not_disturb": self._do_not_disturb.isChecked(),
            },
            "voice": {
                "auto_play_voice": self._auto_play_voice.isChecked(),
            },
            "proactive": {
                "enabled": self._proactive_enabled.isChecked(),
                "check_interval": self._proactive_check_interval.value(),
                "trigger_probability": self._proactive_trigger_probability.value(),
                "require_user_active": self._proactive_require_user_active.isChecked(),
                "idle_threshold": self._proactive_idle_threshold.value(),
                "time_range_enabled": self._proactive_time_range_enabled.isChecked(),
                "time_range_start": self._proactive_time_range_start.time().toString(
                    "HH:mm"
                ),
                "time_range_end": self._proactive_time_range_end.time().toString(
                    "HH:mm"
                ),
            },
            "storage": {
                "image_save_path": self._image_save_path.text().strip(),
                "chat_history_path": self._chat_history_path.text().strip(),
            },
            "custom_theme": self._build_custom_theme_config(),
            "update": {
                "enabled": self._update_enabled.isChecked(),
                "check_on_startup": self._update_check_on_startup.isChecked(),
                "auto_restart": self._update_auto_restart.isChecked(),
                "update_mode": self._update_mode.currentData(),
                "scheduled_times": [
                    row["editor"].time().toString("HH:mm")
                    for row in self._schedule_time_editors
                ],
            },
        }

        # 更新配置对象
        if hasattr(self.config, "server"):  # ClientConfig object
            # 服务器
            self.config.server.url = settings["server"]["url"]
            self.config.server.username = settings["server"]["username"]
            self.config.server.password = settings["server"]["password"]
            self.config.server.enable_streaming = settings["server"]["enable_streaming"]

            # 外观
            self.config.appearance.theme = settings["appearance"]["theme"]
            self.config.appearance.avatar_path = settings["appearance"]["avatar_path"]
            self.config.appearance.user_avatar_path = settings["appearance"][
                "user_avatar_path"
            ]
            self.config.appearance.bot_avatar_path = settings["appearance"][
                "bot_avatar_path"
            ]
            self.config.appearance.ball_size = settings["appearance"]["ball_size"]
            self.config.appearance.breathing_enabled = settings["appearance"][
                "breathing_enabled"
            ]
            self.config.appearance.auto_start = settings["appearance"]["auto_start"]

            # 快捷键
            self.config.hotkeys.global_enabled = settings["hotkeys"]["global_enabled"]
            for key, value in settings["hotkeys"].items():
                if key != "global_enabled" and hasattr(self.config.hotkeys, key):
                    setattr(self.config.hotkeys, key, value)

            # 交互
            self.config.interaction.default_mode = settings["interaction"][
                "default_mode"
            ]
            self.config.interaction.single_click = settings["interaction"][
                "single_click"
            ]
            self.config.interaction.double_click = settings["interaction"][
                "double_click"
            ]
            self.config.interaction.bubble_duration = settings["interaction"][
                "bubble_duration"
            ]
            self.config.interaction.bubble_auto_hide = settings["interaction"][
                "bubble_auto_hide"
            ]
            self.config.interaction.do_not_disturb = settings["interaction"][
                "do_not_disturb"
            ]

            # 语音
            self.config.voice.auto_play_voice = settings["voice"]["auto_play_voice"]

            # 主动对话
            self.config.proactive.enabled = settings["proactive"]["enabled"]
            self.config.proactive.check_interval = settings["proactive"][
                "check_interval"
            ]
            self.config.proactive.trigger_probability = settings["proactive"][
                "trigger_probability"
            ]
            self.config.proactive.require_user_active = settings["proactive"][
                "require_user_active"
            ]
            self.config.proactive.idle_threshold = settings["proactive"][
                "idle_threshold"
            ]
            self.config.proactive.time_range_enabled = settings["proactive"][
                "time_range_enabled"
            ]
            self.config.proactive.time_range_start = settings["proactive"][
                "time_range_start"
            ]
            self.config.proactive.time_range_end = settings["proactive"][
                "time_range_end"
            ]

            # 存储
            self.config.storage.image_save_path = settings["storage"]["image_save_path"]
            self.config.storage.chat_history_path = settings["storage"][
                "chat_history_path"
            ]

            # 更新设置
            if "update" in settings:
                self.config.update.enabled = settings["update"]["enabled"]
                self.config.update.check_on_startup = settings["update"][
                    "check_on_startup"
                ]
                self.config.update.auto_restart = settings["update"]["auto_restart"]
                self.config.update.update_mode = settings["update"]["update_mode"]
                self.config.update.scheduled_times = settings["update"][
                    "scheduled_times"
                ]

            # 自定义颜色
            custom_theme_config = settings["custom_theme"]
            self.config.appearance.custom_theme.enabled = custom_theme_config.enabled
            self.config.appearance.custom_theme.primary = custom_theme_config.primary
            self.config.appearance.custom_theme.primary_light = (
                custom_theme_config.primary_light
            )
            self.config.appearance.custom_theme.primary_dark = (
                custom_theme_config.primary_dark
            )
            self.config.appearance.custom_theme.bg_primary = (
                custom_theme_config.bg_primary
            )
            self.config.appearance.custom_theme.bg_secondary = (
                custom_theme_config.bg_secondary
            )
            self.config.appearance.custom_theme.text_primary = (
                custom_theme_config.text_primary
            )
            self.config.appearance.custom_theme.text_secondary = (
                custom_theme_config.text_secondary
            )
            self.config.appearance.custom_theme.system_notice_text = (
                custom_theme_config.system_notice_text
            )
            self.config.appearance.custom_theme.ball_bg = custom_theme_config.ball_bg
            self.config.appearance.custom_theme.ball_glow = (
                custom_theme_config.ball_glow
            )
            self.config.appearance.custom_theme.ball_border = (
                custom_theme_config.ball_border
            )
            self.config.appearance.custom_theme.bubble_user_bg = (
                custom_theme_config.bubble_user_bg
            )
            self.config.appearance.custom_theme.bubble_user_text = (
                custom_theme_config.bubble_user_text
            )
            self.config.appearance.custom_theme.bubble_ai_bg = (
                custom_theme_config.bubble_ai_bg
            )
            self.config.appearance.custom_theme.bubble_ai_text = (
                custom_theme_config.bubble_ai_text
            )

            # 应用自定义颜色
            if custom_theme_config.enabled:
                theme_manager.apply_custom_colors(custom_theme_config)
            else:
                theme_manager.reset_custom_colors()

            # 保存到磁盘
            if hasattr(self.config, "save"):
                self.config.save()
            else:
                save_config(self.config)

        # 应用快捷键配置
        hotkey_config = HotkeyConfig.from_dict(settings["hotkeys"])
        hotkey_manager.set_config(hotkey_config)

        if settings["hotkeys"]["global_enabled"]:
            hotkey_manager.enable_global_hotkeys(True)

        # 应用开机自启设置
        if os.name == "nt":
            auto_start_enabled = settings["appearance"].get("auto_start", False)
            success, msg = set_autostart(auto_start_enabled)
            if not success:
                QMessageBox.warning(self, "开机自启", f"设置开机自启失败: {msg}")

        self.settings_changed.emit(settings)
        self.close()

    def closeEvent(self, event):
        """关闭事件"""
        self.closed.emit()
        event.accept()
