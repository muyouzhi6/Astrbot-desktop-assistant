"""
主题系统

提供多种精美主题配色方案，支持：
- 浅色/深色主题
- 自定义配色
- 主题切换
"""

from dataclasses import dataclass
from typing import Dict, Optional, TYPE_CHECKING
from enum import Enum
import copy
import logging

logger = logging.getLogger(__name__)


if TYPE_CHECKING:
    from ..config import CustomThemeConfig


class ThemeType(Enum):
    """主题类型"""

    LIGHT = "light"
    DARK = "dark"
    CUSTOM = "custom"


@dataclass
class ThemeColors:
    """主题颜色配置"""

    # 主色调
    primary: str = "#409EFF"
    primary_light: str = "#66B1FF"
    primary_dark: str = "#337ECC"

    # 辅助色
    success: str = "#67C23A"
    warning: str = "#E6A23C"
    danger: str = "#F56C6C"
    info: str = "#909399"

    # 背景色
    bg_primary: str = "#FFFFFF"
    bg_secondary: str = "#F5F7FA"
    bg_tertiary: str = "#EBEEF5"
    bg_hover: str = "#F5F7FA"

    # 文字色
    text_primary: str = "#303133"
    text_regular: str = "#606266"
    text_secondary: str = "#909399"
    text_placeholder: str = "#C0C4CC"
    text_inverse: str = "#FFFFFF"

    # 系统通知颜色
    system_notice_text: str = "#666666"

    # 边框色
    border_base: str = "#DCDFE6"
    border_light: str = "#E4E7ED"
    border_lighter: str = "#EBEEF5"
    border_extra_light: str = "#F2F6FC"

    # 阴影
    shadow_base: str = "rgba(0, 0, 0, 0.1)"
    shadow_light: str = "rgba(0, 0, 0, 0.05)"

    # 悬浮球专用
    ball_bg: str = "#409EFF"
    ball_border: str = "#337ECC"
    ball_glow: str = "rgba(64, 158, 255, 0.4)"

    # 气泡专用
    bubble_user_bg: str = "#409EFF"
    bubble_user_text: str = "#FFFFFF"
    bubble_ai_bg: str = "#FFFFFF"
    bubble_ai_text: str = "#303133"
    bubble_ai_border: str = "#E4E7ED"


@dataclass
class Theme:
    """完整主题"""

    name: str
    display_name: str
    type: ThemeType
    colors: ThemeColors

    # 样式配置
    border_radius: int = 12
    border_radius_small: int = 6
    border_radius_large: int = 16

    # 字体
    font_family: str = '"Microsoft YaHei", "Segoe UI", "PingFang SC", sans-serif'
    font_size_base: int = 16
    font_size_small: int = 13
    font_size_large: int = 18

    # 动画
    transition_duration: str = "0.3s"


# ============ 预设主题 ============

THEME_LIGHT_BLUE = Theme(
    name="light_blue",
    display_name="清新蓝",
    type=ThemeType.LIGHT,
    colors=ThemeColors(
        primary="#409EFF",
        primary_light="#66B1FF",
        primary_dark="#337ECC",
        ball_bg="#409EFF",
        ball_glow="rgba(64, 158, 255, 0.4)",
        bubble_user_bg="#409EFF",
    ),
)

THEME_LIGHT_GREEN = Theme(
    name="light_green",
    display_name="清新绿",
    type=ThemeType.LIGHT,
    colors=ThemeColors(
        primary="#67C23A",
        primary_light="#85CE61",
        primary_dark="#529B2E",
        ball_bg="#67C23A",
        ball_glow="rgba(103, 194, 58, 0.4)",
        bubble_user_bg="#67C23A",
    ),
)

THEME_LIGHT_PURPLE = Theme(
    name="light_purple",
    display_name="优雅紫",
    type=ThemeType.LIGHT,
    colors=ThemeColors(
        primary="#9B59B6",
        primary_light="#B07CC6",
        primary_dark="#7D3C98",
        ball_bg="#9B59B6",
        ball_glow="rgba(155, 89, 182, 0.4)",
        bubble_user_bg="#9B59B6",
    ),
)

THEME_LIGHT_PINK = Theme(
    name="light_pink",
    display_name="甜美粉",
    type=ThemeType.LIGHT,
    colors=ThemeColors(
        primary="#E91E63",
        primary_light="#EC407A",
        primary_dark="#C2185B",
        ball_bg="#E91E63",
        ball_glow="rgba(233, 30, 99, 0.4)",
        bubble_user_bg="#E91E63",
    ),
)

THEME_LIGHT_ORANGE = Theme(
    name="light_orange",
    display_name="活力橙",
    type=ThemeType.LIGHT,
    colors=ThemeColors(
        primary="#FF9800",
        primary_light="#FFB74D",
        primary_dark="#F57C00",
        ball_bg="#FF9800",
        ball_glow="rgba(255, 152, 0, 0.4)",
        bubble_user_bg="#FF9800",
    ),
)

THEME_DARK = Theme(
    name="dark",
    display_name="深色模式",
    type=ThemeType.DARK,
    colors=ThemeColors(
        primary="#409EFF",
        primary_light="#66B1FF",
        primary_dark="#337ECC",
        bg_primary="#1E1E1E",
        bg_secondary="#252526",
        bg_tertiary="#2D2D2D",
        bg_hover="#3C3C3C",
        text_primary="#FFFFFF",  # 纯白，确保最高对比度
        text_regular="#E0E0E0",
        text_secondary="#A0A0A0",
        text_placeholder="#707070",
        text_inverse="#1E1E1E",
        border_base="#404040",
        border_light="#505050",
        border_lighter="#606060",
        border_extra_light="#707070",
        shadow_base="rgba(0, 0, 0, 0.4)",
        shadow_light="rgba(0, 0, 0, 0.3)",
        ball_bg="#409EFF",
        ball_glow="rgba(64, 158, 255, 0.5)",
        bubble_user_bg="#409EFF",
        bubble_user_text="#FFFFFF",
        bubble_ai_bg="#2D2D2D",
        bubble_ai_text="#FFFFFF",  # 确保 AI 气泡文字清晰
        bubble_ai_border="#404040",
    ),
)

THEME_DARK_GREEN = Theme(
    name="dark_green",
    display_name="暗夜绿",
    type=ThemeType.DARK,
    colors=ThemeColors(
        primary="#4CAF50",
        primary_light="#66BB6A",
        primary_dark="#388E3C",
        bg_primary="#1A1F1A",
        bg_secondary="#222722",
        bg_tertiary="#2A302A",
        bg_hover="#3A403A",
        text_primary="#D0E0D0",
        text_regular="#A0B0A0",
        text_secondary="#708070",
        text_placeholder="#506050",
        text_inverse="#1A1F1A",
        border_base="#3A4A3A",
        border_light="#4A5A4A",
        border_lighter="#5A6A5A",
        border_extra_light="#6A7A6A",
        ball_bg="#4CAF50",
        ball_glow="rgba(76, 175, 80, 0.5)",
        bubble_user_bg="#4CAF50",
        bubble_ai_bg="#2A302A",
        bubble_ai_text="#D0E0D0",
        bubble_ai_border="#3A4A3A",
    ),
)

THEME_SAKURA = Theme(
    name="sakura",
    display_name="樱花粉",
    type=ThemeType.LIGHT,
    colors=ThemeColors(
        primary="#FFB7C5",
        primary_light="#FFC8D4",
        primary_dark="#FF9AAD",
        bg_primary="#FFF5F7",
        bg_secondary="#FFECEF",
        bg_tertiary="#FFE4E8",
        bg_hover="#FFD8DE",
        text_primary="#5C3D42",
        text_regular="#7A5459",
        text_secondary="#9E7A7F",
        text_placeholder="#C4A0A5",
        border_base="#FFD1D9",
        border_light="#FFE0E6",
        border_lighter="#FFEAEF",
        ball_bg="linear-gradient(135deg, #FFB7C5, #FF9AAD)",
        ball_glow="rgba(255, 183, 197, 0.5)",
        bubble_user_bg="#FFB7C5",
        bubble_user_text="#5C3D42",
        bubble_ai_bg="#FFFFFF",
        bubble_ai_text="#5C3D42",
        bubble_ai_border="#FFD1D9",
    ),
)

THEME_OCEAN = Theme(
    name="ocean",
    display_name="深海蓝",
    type=ThemeType.DARK,
    colors=ThemeColors(
        primary="#00BCD4",
        primary_light="#26C6DA",
        primary_dark="#00ACC1",
        bg_primary="#0A1929",
        bg_secondary="#0D2137",
        bg_tertiary="#132F4C",
        bg_hover="#1E3A5F",
        text_primary="#E0E6ED",  # 显著提高亮度
        text_regular="#B0B8C3",  # 显著提高亮度
        text_secondary="#7A8B9C",
        text_placeholder="#4F5D6B",
        text_inverse="#0A1929",
        border_base="#1E3A5F",
        border_light="#2A4A70",
        border_lighter="#3A5A80",
        shadow_base="rgba(0, 188, 212, 0.2)",
        ball_bg="#00BCD4",
        ball_glow="rgba(0, 188, 212, 0.5)",
        bubble_user_bg="#00BCD4",
        bubble_ai_bg="#132F4C",
        bubble_ai_text="#E0E6ED",  # 与 text_primary 保持一致
        bubble_ai_border="#2A4A70",  # 稍微加亮边框
    ),
)

THEME_MACOS_LIGHT = Theme(
    name="macos_light",
    display_name="macOS 风格（浅色）",
    type=ThemeType.LIGHT,
    colors=ThemeColors(
        primary="#007AFF",  # macOS 系统蓝
        primary_light="#3395FF",
        primary_dark="#0051D5",
        success="#34C759",  # macOS 绿色
        warning="#FF9500",  # macOS 橙色
        danger="#FF3B30",  # macOS 红色
        bg_primary="#FFFFFF",
        bg_secondary="#F5F5F7",  # macOS 浅灰
        bg_tertiary="#E8E8ED",
        bg_hover="#E5E5EA",
        text_primary="#1D1D1F",  # macOS 主文字色
        text_regular="#1D1D1F",
        text_secondary="#6E6E73",
        text_placeholder="#A1A1A6",
        text_inverse="#FFFFFF",
        border_base="#D1D1D6",
        border_light="#D1D1D6",
        border_lighter="#E5E5EA",
        border_extra_light="#F5F5F7",
        shadow_base="rgba(0, 0, 0, 0.08)",
        shadow_light="rgba(0, 0, 0, 0.05)",
        ball_bg="#007AFF",
        ball_glow="rgba(0, 122, 255, 0.4)",
        ball_border="#0051D5",
        bubble_user_bg="#007AFF",
        bubble_user_text="#FFFFFF",
        bubble_ai_bg="#FFFFFF",
        bubble_ai_text="#1D1D1F",
        bubble_ai_border="#E5E5EA",
        system_notice_text="#6E6E73",
    ),
    border_radius=10,
    border_radius_small=6,
    border_radius_large=14,
    font_family='-apple-system, "SF Pro Display", "PingFang SC", "Microsoft YaHei", sans-serif',
    font_size_base=13,
    font_size_small=11,
    font_size_large=15,
)


# 所有预设主题
PRESET_THEMES: Dict[str, Theme] = {
    "light_blue": THEME_LIGHT_BLUE,
    "light_green": THEME_LIGHT_GREEN,
    "light_purple": THEME_LIGHT_PURPLE,
    "light_pink": THEME_LIGHT_PINK,
    "light_orange": THEME_LIGHT_ORANGE,
    "dark": THEME_DARK,
    "dark_green": THEME_DARK_GREEN,
    "sakura": THEME_SAKURA,
    "ocean": THEME_OCEAN,
    "macos_light": THEME_MACOS_LIGHT,  # macOS 风格
}


class ThemeManager:
    """主题管理器"""

    _instance: Optional["ThemeManager"] = None
    _callbacks: list
    _current_theme: Theme
    _custom_config: Optional["CustomThemeConfig"]
    _effective_colors: Optional[ThemeColors]

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._current_theme = THEME_LIGHT_BLUE
            cls._instance._callbacks = []
            cls._instance._custom_config = None
            cls._instance._effective_colors = None
            # QSS 支持
            cls._instance._qss_enabled = False
            cls._instance._qss_loader = None
            cls._instance._global_qss = ""
        return cls._instance

    @property
    def current_theme(self) -> Theme:
        return self._current_theme

    def get_current_colors(self) -> ThemeColors:
        """获取当前生效的颜色配置（应用了自定义颜色后的最终颜色）"""
        if self._effective_colors is not None:
            return self._effective_colors
        return self._current_theme.colors

    def apply_custom_colors(self, custom_config: "CustomThemeConfig") -> None:
        """应用自定义颜色配置

        Args:
            custom_config: 自定义主题颜色配置对象
        """

        self._custom_config = custom_config
        self._update_effective_colors()
        self._notify_callbacks()

    def reset_custom_colors(self) -> None:
        """清除自定义颜色并恢复主题默认"""
        self._custom_config = None
        self._effective_colors = None
        self._notify_callbacks()

    def _update_effective_colors(self) -> None:
        """更新生效的颜色配置"""
        if self._custom_config is None or not self._custom_config.enabled:
            self._effective_colors = None
            return

        # 深拷贝当前主题的颜色作为基础
        base_colors = copy.deepcopy(self._current_theme.colors)

        # 自定义颜色字段映射（CustomThemeConfig 字段名 -> ThemeColors 字段名）
        color_mappings = {
            "primary": "primary",
            "primary_light": "primary_light",
            "primary_dark": "primary_dark",
            "bg_primary": "bg_primary",
            "bg_secondary": "bg_secondary",
            "text_primary": "text_primary",
            "text_secondary": "text_secondary",
            "system_notice_text": "system_notice_text",
            "ball_bg": "ball_bg",
            "ball_glow": "ball_glow",
            "ball_border": "ball_border",
            "bubble_user_bg": "bubble_user_bg",
            "bubble_user_text": "bubble_user_text",
            "bubble_ai_bg": "bubble_ai_bg",
            "bubble_ai_text": "bubble_ai_text",
        }

        # 只覆盖非空字段
        for custom_field, theme_field in color_mappings.items():
            custom_value = getattr(self._custom_config, custom_field, "")
            if custom_value:  # 非空字符串
                setattr(base_colors, theme_field, custom_value)

        self._effective_colors = base_colors

    def set_theme(self, theme_name: str) -> bool:
        """设置主题"""
        if theme_name in PRESET_THEMES:
            self._current_theme = PRESET_THEMES[theme_name]
            # 主题切换后重新计算生效的颜色
            self._update_effective_colors()

            # QSS 模式下重新加载并应用样式
            if self._qss_enabled:
                self._load_global_qss()
                from PySide6.QtWidgets import QApplication

                app = QApplication.instance()
                if app:
                    self.apply_global_stylesheet(app)

            self._notify_callbacks()
            return True
        return False

    def cycle_theme(self):
        """循环切换到下一个主题"""
        theme_names = list(PRESET_THEMES.keys())
        current_name = self._current_theme.name

        try:
            current_index = theme_names.index(current_name)
            next_index = (current_index + 1) % len(theme_names)
        except ValueError:
            next_index = 0

        next_theme_name = theme_names[next_index]
        self.set_theme(next_theme_name)

    def get_theme_names(self) -> list:
        """获取所有主题名称"""
        return [(name, theme.display_name) for name, theme in PRESET_THEMES.items()]

    def register_callback(self, callback):
        """注册主题变化回调"""
        self._callbacks.append(callback)

    def unregister_callback(self, callback):
        """取消注册回调"""
        if callback in self._callbacks:
            self._callbacks.remove(callback)

    def _notify_callbacks(self):
        """通知所有回调"""
        for callback in self._callbacks:
            try:
                callback(self._current_theme)
            except Exception as e:
                logger.error(f"Theme callback error: {e}")

    # ============ QSS 支持方法 ============

    def enable_qss_mode(self, enabled: bool = True):
        """启用/禁用 QSS 模式

        Args:
            enabled: True=使用 QSS, False=使用 Python 样式（默认）
        """
        self._qss_enabled = enabled
        if enabled and self._qss_loader is None:
            from .theme_qss.loader import QSSThemeLoader

            self._qss_loader = QSSThemeLoader()
            self._load_global_qss()

    def is_qss_enabled(self) -> bool:
        """检查是否启用了 QSS 模式"""
        return self._qss_enabled

    def _load_global_qss(self):
        """加载全局 QSS 样式表"""
        if not self._qss_enabled or self._qss_loader is None:
            return

        # 将当前主题颜色转换为 QSS 变量
        color_vars = self._colors_to_qss_variables()

        # 加载主题（base.qss + 主题特定.qss）
        self._global_qss = self._qss_loader.load_theme(
            self._current_theme.name, color_vars
        )

    def _colors_to_qss_variables(self) -> dict:
        """将当前主题颜色转换为 QSS 变量字典

        Returns:
            颜色变量字典，key 使用连字符命名（如 'primary-light'）
        """
        c = self.get_current_colors()
        t = self._current_theme

        return {
            # 主色调
            "primary": c.primary,
            "primary-light": c.primary_light,
            "primary-dark": c.primary_dark,
            # 辅助色
            "success": c.success,
            "warning": c.warning,
            "danger": c.danger,
            "info": c.info,
            # 背景色
            "bg-primary": c.bg_primary,
            "bg-secondary": c.bg_secondary,
            "bg-tertiary": c.bg_tertiary,
            "bg-hover": c.bg_hover,
            # 文字色
            "text-primary": c.text_primary,
            "text-regular": c.text_regular,
            "text-secondary": c.text_secondary,
            "text-tertiary": c.text_secondary,  # 使用 text_secondary
            "text-placeholder": c.text_placeholder,
            "text-inverse": c.text_inverse,
            # 边框色
            "border-base": c.border_base,
            "border-light": c.border_light,
            "border-lighter": c.border_lighter,
            "border-extra-light": c.border_extra_light,
            # 阴影
            "shadow-base": c.shadow_base,
            "shadow-light": c.shadow_light,
            "shadow-medium": c.shadow_base,  # 使用 shadow_base
            # 圆角
            "border-radius": f"{t.border_radius}px",
            "border-radius-small": f"{t.border_radius_small}px",
            "border-radius-large": f"{t.border_radius_large}px",
        }

    def apply_global_stylesheet(self, app):
        """应用全局样式表到 QApplication

        Args:
            app: QApplication 实例
        """
        if self._qss_enabled and self._global_qss:
            app.setStyleSheet(self._global_qss)
            logger.info(f"已应用 QSS 样式表：{len(self._global_qss)} 字符")
        else:
            logger.info("QSS 模式未启用，跳过全局样式应用")

    def get_global_qss(self) -> str:
        """获取当前全局 QSS 样式表内容（用于调试）"""
        return self._global_qss

    # ============ 样式生成方法 ============

    def get_floating_ball_style(self) -> str:
        """获取悬浮球样式"""
        self.get_current_colors()
        return """
            FloatingBallWindow {
                background: transparent;
            }
        """

    def get_bubble_user_style(self) -> str:
        """获取用户消息气泡样式"""
        t = self._current_theme
        c = self.get_current_colors()
        return f"""
            MessageBubble {{
                background-color: {c.bubble_user_bg};
                border-radius: {t.border_radius_large}px;
                border-bottom-right-radius: 4px;
            }}
            QTextEdit {{
                background-color: transparent;
                color: {c.bubble_user_text};
                font-family: {t.font_family};
                font-size: {t.font_size_base}px;
                border: none;
                padding: 0;
            }}
        """

    def get_bubble_ai_style(self) -> str:
        """获取 AI 消息气泡样式"""
        t = self._current_theme
        c = self.get_current_colors()
        return f"""
            MessageBubble {{
                background-color: {c.bubble_ai_bg};
                border-radius: {t.border_radius_large}px;
                border-bottom-left-radius: 4px;
                border: 1px solid {c.bubble_ai_border};
            }}
            QTextEdit {{
                background-color: transparent;
                color: {c.bubble_ai_text};
                font-family: {t.font_family};
                font-size: {t.font_size_base}px;
                border: none;
                padding: 0;
            }}
        """

    def get_chat_window_style(self) -> str:
        """获取对话窗口样式"""
        c = self.get_current_colors()
        return f"""
            QMainWindow {{
                background-color: {c.bg_secondary};
            }}
            QScrollArea {{
                background-color: {c.bg_secondary};
                border: none;
            }}
            QScrollBar:vertical {{
                background-color: transparent;
                width: 6px;
                border-radius: 3px;
                margin: 2px;
            }}
            QScrollBar::handle:vertical {{
                background-color: rgba(0, 0, 0, 0.15);
                border-radius: 3px;
                min-height: 30px;
                margin: 1px;
            }}
            QScrollBar::handle:vertical:hover {{
                background-color: rgba(0, 0, 0, 0.3);
            }}
            QScrollBar::handle:vertical:pressed {{
                background-color: rgba(0, 0, 0, 0.4);
            }}
            QScrollBar::add-line:vertical,
            QScrollBar::sub-line:vertical,
            QScrollBar::add-page:vertical,
            QScrollBar::sub-page:vertical {{
                height: 0px;
                background: none;
            }}
        """

    def get_input_area_style(self) -> str:
        """获取输入区域样式"""
        t = self._current_theme
        c = self.get_current_colors()
        return f"""
            QFrame {{
                background-color: {c.bg_primary};
                border-top: 1px solid {c.border_light};
            }}
            QLineEdit {{
                padding: 10px 16px;
                border: 1px solid {c.border_base};
                border-radius: {t.border_radius_large}px;
                background-color: {c.bg_secondary};
                font-size: {t.font_size_base}px;
                color: {c.text_primary};
            }}
            QLineEdit:focus {{
                border: 2px solid {c.primary};
                background-color: {c.bg_primary};
            }}
            QLineEdit::placeholder {{
                color: {c.text_placeholder};
            }}
        """

    def get_send_button_style(self) -> str:
        """获取发送按钮样式"""
        t = self._current_theme
        c = self.get_current_colors()
        return f"""
            QPushButton {{
                background-color: {c.primary};
                color: {c.text_inverse};
                border: none;
                border-radius: {t.border_radius_large}px;
                font-size: {t.font_size_base}px;
                font-weight: bold;
                padding: 10px 20px;
            }}
            QPushButton:hover {{
                background-color: {c.primary_light};
            }}
            QPushButton:pressed {{
                background-color: {c.primary_dark};
            }}
            QPushButton:disabled {{
                background-color: {c.bg_tertiary};
                color: {c.text_placeholder};
            }}
        """

    def get_header_style(self) -> str:
        """获取标题栏样式"""
        t = self._current_theme
        c = self.get_current_colors()
        return f"""
            QFrame {{
                background-color: {c.bg_primary};
                border-bottom: 1px solid {c.border_light};
            }}
            QLabel {{
                color: {c.text_primary};
                font-family: {t.font_family};
            }}
        """

    def get_settings_window_style(self) -> str:
        """获取设置窗口样式"""
        t = self._current_theme
        c = self.get_current_colors()
        return f"""
            QDialog {{
                background-color: {c.bg_primary};
            }}
            QLabel {{
                color: {c.text_primary};
                font-family: {t.font_family};
            }}
            QLineEdit {{
                padding: 8px 12px;
                border: 1px solid {c.border_base};
                border-radius: {t.border_radius_small}px;
                background-color: {c.bg_secondary};
                color: {c.text_primary};
            }}
            QLineEdit:focus {{
                border: 2px solid {c.primary};
            }}
            QPushButton {{
                padding: 8px 16px;
                border: 1px solid {c.border_base};
                border-radius: {t.border_radius_small}px;
                background-color: {c.bg_primary};
                color: {c.text_primary};
            }}
            QPushButton:hover {{
                background-color: {c.bg_hover};
                border-color: {c.primary};
            }}
            QPushButton#primaryButton {{
                background-color: {c.primary};
                color: {c.text_inverse};
                border: none;
            }}
            QPushButton#primaryButton:hover {{
                background-color: {c.primary_light};
            }}
            QComboBox {{
                padding: 8px 12px;
                border: 1px solid {c.border_base};
                border-radius: {t.border_radius_small}px;
                background-color: {c.bg_secondary};
                color: {c.text_primary};
            }}
            QGroupBox {{
                font-weight: bold;
                border: 1px solid {c.border_light};
                border-radius: {t.border_radius}px;
                margin-top: 12px;
                padding-top: 12px;
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                left: 12px;
                padding: 0 6px;
                color: {c.text_primary};
            }}
        """


# 全局主题管理器实例
theme_manager = ThemeManager()

# 导出主题列表
THEMES = PRESET_THEMES
