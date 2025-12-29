"""
QSS 主题加载器

负责加载和组合 QSS 文件
"""

from pathlib import Path
import logging
from typing import Optional, Dict
from .variables import QSSVariableProcessor

logger = logging.getLogger(__name__)


class QSSThemeLoader:
    """QSS 主题加载器"""

    def __init__(self):
        self.processor = QSSVariableProcessor()
        self.themes_dir = Path(__file__).parent / "presets"
        self.base_qss_path = Path(__file__).parent / "base.qss"

    def load_theme(
        self, theme_name: str, color_overrides: Optional[Dict[str, str]] = None
    ) -> str:
        """加载主题

        Args:
            theme_name: 主题名称（如 "macos_light"）
            color_overrides: 颜色覆盖字典

        Returns:
            处理后的完整 QSS 样式
        """
        # 1. 加载基础样式
        base_qss = self._load_file(self.base_qss_path)

        # 2. 加载主题特定样式
        theme_qss_path = self.themes_dir / f"{theme_name}.qss"
        theme_qss = self._load_file(theme_qss_path)

        # 3. 合并样式（主题样式优先级更高）
        combined_qss = base_qss + "\n\n" + theme_qss

        # 4. 处理变量
        processed_qss = self.processor.process(combined_qss, color_overrides)

        return processed_qss

    def _load_file(self, file_path: Path) -> str:
        """加载 QSS 文件

        Args:
            file_path: 文件路径

        Returns:
            文件内容，如果文件不存在则返回空字符串
        """
        if not file_path.exists():
            return ""

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                return f.read()
        except Exception as e:
            logger.warning(f"加载 QSS 文件失败: {file_path}, 错误: {e}")
            return ""

    def get_available_themes(self) -> list:
        """获取可用的主题列表

        Returns:
            主题名称列表（不含 .qss 后缀）
        """
        if not self.themes_dir.exists():
            return []

        return [f.stem for f in self.themes_dir.glob("*.qss")]
