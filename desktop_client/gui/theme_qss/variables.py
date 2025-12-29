"""
QSS 变量处理器

支持在 QSS 中使用类似 CSS 变量的语法
"""

import re
from typing import Dict


class QSSVariableProcessor:
    """QSS 变量处理器

    支持语法：
    - 定义变量：@primary: #007AFF;
    - 使用变量：background-color: @primary;

    Example:
        >>> processor = QSSVariableProcessor()
        >>> qss = "@primary: #007AFF; QPushButton { background: @primary; }"
        >>> result = processor.process(qss)
    """

    def __init__(self):
        self.variables: Dict[str, str] = {}

    def process(self, qss_content: str, color_overrides: Dict[str, str] = None) -> str:
        """处理 QSS 中的变量

        Args:
            qss_content: 原始 QSS 内容
            color_overrides: 颜色覆盖字典（来自配置或主题）

        Returns:
            处理后的 QSS 内容
        """
        # 1. 提取变量定义
        var_pattern = r"@([\w-]+)\s*:\s*([^;]+);"
        for match in re.finditer(var_pattern, qss_content):
            var_name, var_value = match.groups()
            self.variables[var_name] = var_value.strip()

        # 2. 应用颜色覆盖
        if color_overrides:
            self.variables.update(color_overrides)

        # 3. 替换变量引用
        def replace_var(match):
            var_name = match.group(1)
            return self.variables.get(var_name, match.group(0))

        result = re.sub(r"@([\w-]+)", replace_var, qss_content)

        # 4. 移除变量定义行
        result = re.sub(var_pattern, "", result)

        # 5. 清理多余空行
        result = re.sub(r"\n\s*\n\s*\n", "\n\n", result)

        return result.strip()

    def get_variable(self, name: str) -> str:
        """获取变量值"""
        return self.variables.get(name, "")

    def set_variable(self, name: str, value: str):
        """设置变量值"""
        self.variables[name] = value

    def clear(self):
        """清空所有变量"""
        self.variables.clear()
