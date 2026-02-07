"""
统一日志系统

提供彩色日志输出，支持不同级别的日志显示
- DEBUG: 灰色
- INFO: 蓝色
- WARNING: 黄色
- ERROR: 红色
- CRITICAL: 红色加粗

日志格式: [时间] [级别] [模块名:行号] 消息内容
"""

import logging
import sys
from typing import Optional
from logging.handlers import RotatingFileHandler


class ColorCodes:
    """ANSI 颜色代码"""

    # 重置
    RESET = "\033[0m"

    # 前景色
    BLACK = "\033[30m"
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN = "\033[36m"
    WHITE = "\033[37m"
    GRAY = "\033[90m"

    # 高亮前景色
    BRIGHT_RED = "\033[91m"
    BRIGHT_GREEN = "\033[92m"
    BRIGHT_YELLOW = "\033[93m"
    BRIGHT_BLUE = "\033[94m"
    BRIGHT_MAGENTA = "\033[95m"
    BRIGHT_CYAN = "\033[96m"
    BRIGHT_WHITE = "\033[97m"

    # 样式
    BOLD = "\033[1m"
    DIM = "\033[2m"
    UNDERLINE = "\033[4m"


class ColoredFormatter(logging.Formatter):
    """彩色日志格式化器"""

    # 日志级别对应的颜色
    LEVEL_COLORS = {
        logging.DEBUG: ColorCodes.GRAY,
        logging.INFO: ColorCodes.BRIGHT_BLUE,
        logging.WARNING: ColorCodes.BRIGHT_YELLOW,
        logging.ERROR: ColorCodes.BRIGHT_RED,
        logging.CRITICAL: ColorCodes.BOLD + ColorCodes.BRIGHT_RED,
    }

    def __init__(
        self,
        fmt: Optional[str] = None,
        datefmt: Optional[str] = None,
        use_colors: bool = True,
    ):
        """
        初始化彩色格式化器

        Args:
            fmt: 日志格式字符串
            datefmt: 日期格式字符串
            use_colors: 是否使用颜色
        """
        if fmt is None:
            fmt = "[%(asctime)s] [%(levelname)s] [%(name)s:%(lineno)d] %(message)s"
        if datefmt is None:
            datefmt = "%Y-%m-%d %H:%M:%S"

        super().__init__(fmt, datefmt)
        self.use_colors = use_colors and self._supports_color()

    @staticmethod
    def _supports_color() -> bool:
        """检测终端是否支持颜色"""
        # Windows 10+ 支持 ANSI 颜色
        if sys.platform == "win32":
            try:
                import ctypes

                kernel32 = ctypes.windll.kernel32
                # 启用虚拟终端处理
                kernel32.SetConsoleMode(kernel32.GetStdHandle(-11), 7)
                return True
            except Exception:
                return False
        # Unix/Linux/macOS 通常支持颜色
        return hasattr(sys.stderr, "isatty") and sys.stderr.isatty()

    def format(self, record: logging.LogRecord) -> str:
        """格式化日志记录"""
        # 保存原始格式
        original_levelname = record.levelname
        original_msg = record.msg

        # 添加颜色
        if self.use_colors:
            color = self.LEVEL_COLORS.get(record.levelno, ColorCodes.RESET)
            record.levelname = f"{color}{record.levelname}{ColorCodes.RESET}"

            # 时间戳使用灰色
            asctime_colored = f"{ColorCodes.GRAY}%(asctime)s{ColorCodes.RESET}"
            # 模块名使用青色
            name_colored = f"{ColorCodes.CYAN}%(name)s{ColorCodes.RESET}"

            # 临时修改格式
            original_format = self._style._fmt
            self._style._fmt = (
                f"[{asctime_colored}] "
                f"[{color}%(levelname)s{ColorCodes.RESET}] "
                f"[{name_colored}:%(lineno)d] "
                f"{color}%(message)s{ColorCodes.RESET}"
            )

        # 格式化
        result = super().format(record)

        # 恢复原始值
        record.levelname = original_levelname
        record.msg = original_msg
        if self.use_colors:
            self._style._fmt = original_format

        return result


class ContextFilter(logging.Filter):
    """上下文过滤器 - 添加额外的上下文信息"""

    def filter(self, record: logging.LogRecord) -> bool:
        """添加自定义字段到日志记录"""
        # 添加进程 ID 和线程 ID（可选）
        import os
        import threading

        record.process_id = os.getpid()
        record.thread_name = threading.current_thread().name

        return True


def setup_logger(
    name: Optional[str] = None,
    level: int = logging.INFO,
    use_colors: bool = True,
    log_file: Optional[str] = None,
    file_level: int = logging.DEBUG,
    max_bytes: int = 10 * 1024 * 1024,  # 默认 10MB
    backup_count: int = 5,  # 默认保留 5 个备份
) -> logging.Logger:
    """
    设置并返回配置好的日志器

    Args:
        name: 日志器名称，None 表示根日志器
        level: 控制台日志级别
        use_colors: 是否使用彩色输出
        log_file: 日志文件路径（可选）
        file_level: 文件日志级别
        max_bytes: 单个日志文件最大字节数，超过则轮转（默认 10MB）
        backup_count: 保留的旧日志文件数量（默认 5 个）

    Returns:
        配置好的 Logger 实例

    示例:
        >>> logger = setup_logger(__name__)
        >>> logger.debug("调试信息")
        >>> logger.info("一般信息")
        >>> logger.warning("警告信息")
        >>> logger.error("错误信息")
    """
    logger = logging.getLogger(name)

    # 避免重复配置
    if logger.handlers:
        return logger

    logger.setLevel(logging.DEBUG)  # 日志器级别设为最低，由 handler 控制
    logger.propagate = False  # 不传播到父日志器

    # 控制台处理器
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)
    console_formatter = ColoredFormatter(use_colors=use_colors)
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)

    # 文件处理器（可选，使用日志轮转）
    if log_file:
        try:
            # 确保日志目录存在
            import os

            log_dir = os.path.dirname(log_file)
            if log_dir and not os.path.exists(log_dir):
                os.makedirs(log_dir, exist_ok=True)

            # 使用 RotatingFileHandler 实现日志轮转
            file_handler = RotatingFileHandler(
                log_file, maxBytes=max_bytes, backupCount=backup_count, encoding="utf-8"
            )
            file_handler.setLevel(file_level)
            # 文件日志不使用颜色
            file_formatter = ColoredFormatter(use_colors=False)
            file_handler.setFormatter(file_formatter)
            logger.addHandler(file_handler)
        except Exception as e:
            logger.warning(f"无法创建日志文件 {log_file}: {e}")

    return logger


def get_logger(name: str) -> logging.Logger:
    """
    获取已配置的日志器（便捷函数）

    Args:
        name: 日志器名称，通常使用 __name__

    Returns:
        Logger 实例

    示例:
        >>> from desktop_client.logger import get_logger
        >>> logger = get_logger(__name__)
        >>> logger.info("这是一条日志")
    """
    return logging.getLogger(name)


def configure_root_logger(
    level: int = logging.INFO,
    use_colors: bool = True,
    log_file: Optional[str] = None,
    max_bytes: int = 10 * 1024 * 1024,  # 默认 10MB
    backup_count: int = 5,  # 默认保留 5 个备份
) -> None:
    """
    配置根日志器（影响所有模块的日志）

    Args:
        level: 日志级别
        use_colors: 是否使用彩色输出
        log_file: 日志文件路径
        max_bytes: 单个日志文件最大字节数（默认 10MB）
        backup_count: 保留的旧日志文件数量（默认 5 个）

    示例:
        在 main.py 或 app.py 开头调用:
        >>> from desktop_client.logger import configure_root_logger
        >>> configure_root_logger(level=logging.DEBUG, log_file='logs/app.log')
    """
    # 移除默认的处理器
    root_logger = logging.getLogger()
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    # 重新配置
    setup_logger(
        name=None,  # 根日志器
        level=level,
        use_colors=use_colors,
        log_file=log_file,
        max_bytes=max_bytes,
        backup_count=backup_count,
    )


# 默认导出
__all__ = [
    "setup_logger",
    "get_logger",
    "configure_root_logger",
    "ColoredFormatter",
    "ColorCodes",
]
