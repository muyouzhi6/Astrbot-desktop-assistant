"""
美化版设置窗口

提供完整的设置界面，支持：
- 服务器配置
- 外观设置（主题、悬浮球头像）
- 快捷键配置
- 交互模式设置
"""

import os
from typing import Optional, Callable

from PySide6.QtGui import QFont, QPixmap
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QLineEdit, QPushButton, QFrame, QScrollArea,
    QComboBox, QCheckBox, QGroupBox, QFormLayout,
    QFileDialog, QTabWidget, QKeySequenceEdit,
    QSpinBox, QDoubleSpinBox, QSlider, QMessageBox,
    QTimeEdit
)
from PySide6.QtCore import Qt, Signal, QTime
from qasync import asyncSlot

from ..api_client import AstrBotApiClient
from ..utils.autostart import is_autostart_enabled, set_autostart
from ..services import get_chat_history_manager
from ..config import save_config, ClientConfig
from .themes import theme_manager, Theme
from .hotkeys import HotkeyConfig, hotkey_manager


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
        self.setWindowFlags(
            Qt.WindowType.Window |
            Qt.WindowType.WindowCloseButtonHint
        )
        
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
        
        # 服务器设置
        self._tabs.addTab(self._create_server_tab(), "🌐 服务器")
        
        # 外观设置
        self._tabs.addTab(self._create_appearance_tab(), "🎨 外观")
        
        # 快捷键设置
        self._tabs.addTab(self._create_hotkeys_tab(), "⌨️ 快捷键")
        
        # 交互设置
        self._tabs.addTab(self._create_interaction_tab(), "💬 交互")
        
        # 主动对话设置
        self._tabs.addTab(self._create_proactive_tab(), "🤖 主动对话")
        
        # 存储设置
        self._tabs.addTab(self._create_storage_tab(), "💾 存储")
        
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
        
        icon = QLabel("⚙️")
        icon.setObjectName("titleIcon")
        
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
        self._user_avatar_preview.setText("👤")
        
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
        self._bot_avatar_preview.setText("🤖")
        
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
        self._avatar_preview.setText("🤖")
        
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
        self._auto_start.setToolTip("开启后，系统启动时自动运行桌面助手（仅支持 Windows）")
        # 检查当前状态
        if os.name == 'nt':
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
        layout = QVBoxLayout(tab)
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
        layout.addStretch()
        
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
        self._chat_history_path.setPlaceholderText("默认路径 (配置目录/chat_history.json)")
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
        
        self._clear_chat_btn = QPushButton("🗑️ 清空聊天记录")
        self._clear_chat_btn.setObjectName("dangerBtn")
        self._clear_chat_btn.clicked.connect(self._on_clear_chat_history)
        
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

    def _on_browse_storage_path(self):
        """浏览存储路径"""
        path = QFileDialog.getExistingDirectory(
            self,
            "选择保存目录",
            self._image_save_path.text() or os.getcwd()
        )
        if path:
            self._image_save_path.setText(path)
    
    def _on_browse_chat_history_path(self):
        """浏览聊天记录保存路径"""
        path, _ = QFileDialog.getSaveFileName(
            self,
            "选择聊天记录保存位置",
            self._chat_history_path.text() or "chat_history.json",
            "JSON 文件 (*.json)"
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
            QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            chat_manager.clear_history()
            self._chat_count_label.setText("当前共 0 条消息")
            QMessageBox.information(self, "成功", "聊天记录已清空。")

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
        self._proactive_trigger_probability.setToolTip("每次检测时触发主动对话的概率（0.01-1.0）")
        basic_section.add_row("触发概率", self._proactive_trigger_probability)
        
        layout.addWidget(basic_section)
        
        # 活跃检测设置
        active_section = SettingsSection("活跃检测")
        
        self._proactive_require_user_active = QCheckBox("仅在用户活跃时触发")
        self._proactive_require_user_active.setToolTip("开启后，只有当用户最近有键盘或鼠标活动时才会触发主动对话")
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
        self._proactive_time_range_enabled.setToolTip("开启后，只在指定时间段内触发主动对话")
        self._proactive_time_range_enabled.stateChanged.connect(self._on_time_range_toggle)
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
        c = t.colors
        
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
                padding: 10px 20px;
                border: none;
                border-bottom: 2px solid transparent;
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
            }}
            
            QLineEdit, QComboBox, QSpinBox, QKeySequenceEdit {{
                background-color: {c.bg_primary};
                border: 1px solid {c.border_light};
                border-radius: {t.border_radius}px;
                padding: 8px 12px;
                color: {c.text_primary};
            }}
            QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QKeySequenceEdit:focus {{
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
                padding: 8px 16px;
                color: {c.text_primary};
            }}
            QPushButton:hover {{
                background-color: {c.bg_hover};
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
        """)
        
    def _load_settings(self):
        """加载设置"""
        # 服务器设置
        if hasattr(self.config, 'server'):  # ClientConfig object
            self._server_url.setText(self.config.server.url or "")
            self._username.setText(self.config.server.username or "")
            self._password.setText(self.config.server.password or "")
            self._enable_streaming.setChecked(self.config.server.enable_streaming)
        elif hasattr(self.config, 'server_url'):  # Legacy object
            self._server_url.setText(self.config.server_url or "")
            if hasattr(self.config, 'username'):
                self._username.setText(self.config.username or "")
            if hasattr(self.config, 'password'):
                self._password.setText(self.config.password or "")
        elif isinstance(self.config, dict):  # Dict
            self._server_url.setText(self.config.get('server_url', ''))
            self._username.setText(self.config.get('username', ''))
            self._password.setText(self.config.get('password', ''))
            
        # 外观设置
        if hasattr(self.config, 'appearance'):
            self._ball_size.setValue(self.config.appearance.ball_size)
            self._breathing_enabled.setChecked(self.config.appearance.breathing_enabled)
            
            # 悬浮球头像
            if self.config.appearance.avatar_path:
                self._avatar_path = self.config.appearance.avatar_path
                pixmap = QPixmap(self._avatar_path)
                if not pixmap.isNull():
                    pixmap = pixmap.scaled(64, 64, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                    self._avatar_preview.setPixmap(pixmap)
            
            # 用户头像
            if hasattr(self.config.appearance, 'user_avatar_path') and self.config.appearance.user_avatar_path:
                self._user_avatar_path = self.config.appearance.user_avatar_path
                pixmap = QPixmap(self._user_avatar_path)
                if not pixmap.isNull():
                    pixmap = pixmap.scaled(48, 48, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                    self._user_avatar_preview.setPixmap(pixmap)
            else:
                self._user_avatar_path = ""
            
            # Bot头像
            if hasattr(self.config.appearance, 'bot_avatar_path') and self.config.appearance.bot_avatar_path:
                self._bot_avatar_path = self.config.appearance.bot_avatar_path
                pixmap = QPixmap(self._bot_avatar_path)
                if not pixmap.isNull():
                    pixmap = pixmap.scaled(48, 48, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                    self._bot_avatar_preview.setPixmap(pixmap)
            else:
                self._bot_avatar_path = ""
            
            # 开机自启 - 优先从注册表读取实际状态
            if os.name == 'nt':
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
        if hasattr(self.config, 'hotkeys'):
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
        if hasattr(self.config, 'interaction'):
            # 默认模式
            for i in range(self._default_mode.count()):
                if self._default_mode.itemData(i) == self.config.interaction.default_mode:
                    self._default_mode.setCurrentIndex(i)
                    break
            # 单击动作
            for i in range(self._single_click_action.count()):
                if self._single_click_action.itemData(i) == self.config.interaction.single_click:
                    self._single_click_action.setCurrentIndex(i)
                    break
            # 双击动作
            for i in range(self._double_click_action.count()):
                if self._double_click_action.itemData(i) == self.config.interaction.double_click:
                    self._double_click_action.setCurrentIndex(i)
                    break
            # 气泡设置
            self._bubble_duration.setValue(self.config.interaction.bubble_duration)
            self._bubble_auto_hide.setChecked(self.config.interaction.bubble_auto_hide)
        
        # 语音设置
        if hasattr(self.config, 'voice'):
            self._auto_play_voice.setChecked(self.config.voice.auto_play_voice)

        # 主动对话设置
        if hasattr(self.config, 'proactive'):
            self._proactive_enabled.setChecked(self.config.proactive.enabled)
            self._proactive_check_interval.setValue(self.config.proactive.check_interval)
            self._proactive_trigger_probability.setValue(self.config.proactive.trigger_probability)
            self._proactive_require_user_active.setChecked(self.config.proactive.require_user_active)
            self._proactive_idle_threshold.setValue(self.config.proactive.idle_threshold)
            self._proactive_time_range_enabled.setChecked(self.config.proactive.time_range_enabled)
            
            # 解析时间字符串
            start_time = QTime.fromString(self.config.proactive.time_range_start, "HH:mm")
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
            self._proactive_time_range_start.setEnabled(self.config.proactive.time_range_enabled)
            self._proactive_time_range_end.setEnabled(self.config.proactive.time_range_enabled)
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
        if hasattr(self.config, 'storage'):
            self._image_save_path.setText(self.config.storage.image_save_path or "")
            self._chat_history_path.setText(self.config.storage.chat_history_path or "")
            
            # 确保图片保存路径显示正确
            self._image_save_path.setText(self.config.storage.image_save_path or "")
            
            # 更新聊天记录数量
        chat_manager = get_chat_history_manager()
        msg_count = chat_manager.get_message_count()
        self._chat_count_label.setText(f"当前共 {msg_count} 条消息")
                
    def _on_theme_selected(self, index: int):
        """主题选择变化"""
        theme_name = self._theme_combo.itemData(index)
        if theme_name:
            theme_manager.set_theme(theme_name)
            
    def _on_upload_avatar(self):
        """上传悬浮球头像"""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "选择头像图片",
            "",
            "图片文件 (*.png *.jpg *.jpeg *.gif *.bmp *.webp)"
        )
        if file_path:
            pixmap = QPixmap(file_path)
            if not pixmap.isNull():
                # 缩放预览
                pixmap = pixmap.scaled(
                    64, 64,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation
                )
                self._avatar_preview.setPixmap(pixmap)
                self._avatar_path = file_path
            
    def _on_reset_avatar(self):
        """重置悬浮球头像"""
        self._avatar_preview.clear()
        self._avatar_preview.setText("🤖")
        self._avatar_path = ""
        
    def _on_upload_user_avatar(self):
        """上传用户头像"""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "选择用户头像图片",
            "",
            "图片文件 (*.png *.jpg *.jpeg *.gif *.bmp *.webp)"
        )
        if file_path:
            pixmap = QPixmap(file_path)
            if not pixmap.isNull():
                # 缩放预览为圆形
                pixmap = pixmap.scaled(
                    48, 48,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation
                )
                self._user_avatar_preview.setPixmap(pixmap)
                self._user_avatar_path = file_path
            
    def _on_reset_user_avatar(self):
        """重置用户头像"""
        self._user_avatar_preview.clear()
        self._user_avatar_preview.setText("👤")
        self._user_avatar_path = ""
        
    def _on_upload_bot_avatar(self):
        """上传Bot头像"""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "选择Bot头像图片",
            "",
            "图片文件 (*.png *.jpg *.jpeg *.gif *.bmp *.webp)"
        )
        if file_path:
            pixmap = QPixmap(file_path)
            if not pixmap.isNull():
                # 缩放预览
                pixmap = pixmap.scaled(
                    48, 48,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation
                )
                self._bot_avatar_preview.setPixmap(pixmap)
                self._bot_avatar_path = file_path
            
    def _on_reset_bot_avatar(self):
        """重置Bot头像"""
        self._bot_avatar_preview.clear()
        self._bot_avatar_preview.setText("🤖")
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
            client = AstrBotApiClient(server_url=url, username=username, password=password, timeout=5)
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
            'server': {
                'url': self._server_url.text(),
                'username': self._username.text(),
                'password': self._password.text(),
                'enable_streaming': self._enable_streaming.isChecked(),
            },
            'appearance': {
                'theme': self._theme_combo.currentData(),
                'avatar_path': getattr(self, '_avatar_path', ''),
                'user_avatar_path': getattr(self, '_user_avatar_path', ''),
                'bot_avatar_path': getattr(self, '_bot_avatar_path', ''),
                'ball_size': self._ball_size.value(),
                'breathing_enabled': self._breathing_enabled.isChecked(),
                'auto_start': self._auto_start.isChecked(),
            },
            'hotkeys': {
                'global_enabled': self._global_hotkeys.isChecked(),
                **{key: edit.keySequence().toString() 
                   for key, edit in self._hotkey_inputs.items()},
            },
            'interaction': {
                'default_mode': self._default_mode.currentData(),
                'single_click': self._single_click_action.currentData(),
                'double_click': self._double_click_action.currentData(),
                'bubble_duration': self._bubble_duration.value(),
                'bubble_auto_hide': self._bubble_auto_hide.isChecked(),
            },
            'voice': {
                'auto_play_voice': self._auto_play_voice.isChecked(),
            },
            'proactive': {
                'enabled': self._proactive_enabled.isChecked(),
                'check_interval': self._proactive_check_interval.value(),
                'trigger_probability': self._proactive_trigger_probability.value(),
                'require_user_active': self._proactive_require_user_active.isChecked(),
                'idle_threshold': self._proactive_idle_threshold.value(),
                'time_range_enabled': self._proactive_time_range_enabled.isChecked(),
                'time_range_start': self._proactive_time_range_start.time().toString("HH:mm"),
                'time_range_end': self._proactive_time_range_end.time().toString("HH:mm"),
            },
            'storage': {
                'image_save_path': self._image_save_path.text().strip(),
                'chat_history_path': self._chat_history_path.text().strip(),
            },
        }
        
        # 更新配置对象
        if hasattr(self.config, 'server'):  # ClientConfig object
            # 服务器
            self.config.server.url = settings['server']['url']
            self.config.server.username = settings['server']['username']
            self.config.server.password = settings['server']['password']
            self.config.server.enable_streaming = settings['server']['enable_streaming']
            
            # 外观
            self.config.appearance.theme = settings['appearance']['theme']
            self.config.appearance.avatar_path = settings['appearance']['avatar_path']
            self.config.appearance.user_avatar_path = settings['appearance']['user_avatar_path']
            self.config.appearance.bot_avatar_path = settings['appearance']['bot_avatar_path']
            self.config.appearance.ball_size = settings['appearance']['ball_size']
            self.config.appearance.breathing_enabled = settings['appearance']['breathing_enabled']
            self.config.appearance.auto_start = settings['appearance']['auto_start']
            
            # 快捷键
            self.config.hotkeys.global_enabled = settings['hotkeys']['global_enabled']
            for key, value in settings['hotkeys'].items():
                if key != 'global_enabled' and hasattr(self.config.hotkeys, key):
                    setattr(self.config.hotkeys, key, value)
            
            # 交互
            self.config.interaction.default_mode = settings['interaction']['default_mode']
            self.config.interaction.single_click = settings['interaction']['single_click']
            self.config.interaction.double_click = settings['interaction']['double_click']
            self.config.interaction.bubble_duration = settings['interaction']['bubble_duration']
            self.config.interaction.bubble_auto_hide = settings['interaction']['bubble_auto_hide']
            
            # 语音
            self.config.voice.auto_play_voice = settings['voice']['auto_play_voice']

            # 主动对话
            self.config.proactive.enabled = settings['proactive']['enabled']
            self.config.proactive.check_interval = settings['proactive']['check_interval']
            self.config.proactive.trigger_probability = settings['proactive']['trigger_probability']
            self.config.proactive.require_user_active = settings['proactive']['require_user_active']
            self.config.proactive.idle_threshold = settings['proactive']['idle_threshold']
            self.config.proactive.time_range_enabled = settings['proactive']['time_range_enabled']
            self.config.proactive.time_range_start = settings['proactive']['time_range_start']
            self.config.proactive.time_range_end = settings['proactive']['time_range_end']
            
            # 存储
            self.config.storage.image_save_path = settings['storage']['image_save_path']
            self.config.storage.chat_history_path = settings['storage']['chat_history_path']
            
            # 保存到磁盘
            if hasattr(self.config, 'save'):
                self.config.save()
            else:
                save_config(self.config)
        
        # 应用快捷键配置
        hotkey_config = HotkeyConfig.from_dict(settings['hotkeys'])
        hotkey_manager.set_config(hotkey_config)
        
        if settings['hotkeys']['global_enabled']:
            hotkey_manager.enable_global_hotkeys(True)
        
        # 应用开机自启设置
        if os.name == 'nt':
            auto_start_enabled = settings['appearance'].get('auto_start', False)
            success, msg = set_autostart(auto_start_enabled)
            if not success:
                QMessageBox.warning(self, "开机自启", f"设置开机自启失败: {msg}")
        
        self.settings_changed.emit(settings)
        self.close()
        
    def closeEvent(self, event):
        """关闭事件"""
        self.closed.emit()
        event.accept()