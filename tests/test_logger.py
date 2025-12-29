"""
日志系统测试脚本

用于测试彩色日志系统的各个级别和功能
"""

import sys
import os

# 添加父目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logging
from desktop_client.logger import configure_root_logger, get_logger


def test_basic_logging():
    """测试基本的日志功能"""
    print("=" * 60)
    print("测试基本日志功能")
    print("=" * 60)

    logger = get_logger(__name__)

    logger.debug("这是一条 DEBUG 级别的日志 - 用于调试信息")
    logger.info("这是一条 INFO 级别的日志 - 用于一般信息")
    logger.warning("这是一条 WARNING 级别的日志 - 用于警告信息")
    logger.error("这是一条 ERROR 级别的日志 - 用于错误信息")
    logger.critical("这是一条 CRITICAL 级别的日志 - 用于严重错误")


def test_formatted_logging():
    """测试格式化日志"""
    print("\n" + "=" * 60)
    print("测试格式化日志")
    print("=" * 60)

    logger = get_logger("test.module")

    server_url = "http://localhost:6185"
    port = 6190
    session_id = "desktop_12345678"

    logger.info(f"服务器配置 - URL: {server_url}, 端口: {port}")
    logger.debug(f"使用 Session ID: {session_id}")


def test_exception_logging():
    """测试异常日志"""
    print("\n" + "=" * 60)
    print("测试异常日志")
    print("=" * 60)

    logger = get_logger("test.exceptions")

    try:
        result = 10 / 0
        logger.info(f"计算结果: {result}")
    except ZeroDivisionError as e:
        logger.error(f"计算错误: {str(e)}")
        logger.exception("捕获异常（包含堆栈信息）:")


def test_different_modules():
    """测试不同模块的日志"""
    print("\n" + "=" * 60)
    print("测试不同模块的日志")
    print("=" * 60)

    logger1 = get_logger("desktop_client.app")
    logger2 = get_logger("desktop_client.bridge")
    logger3 = get_logger("desktop_client.handlers.message")

    logger1.info("来自 app 模块的日志")
    logger2.info("来自 bridge 模块的日志")
    logger3.info("来自 message handler 模块的日志")


def test_realworld_scenario():
    """模拟真实场景的日志"""
    print("\n" + "=" * 60)
    print("模拟真实应用场景")
    print("=" * 60)

    logger = get_logger("desktop_client.app")

    logger.info("应用启动 - run() 开始")
    logger.debug("设置 qasync 事件循环")
    logger.info("启用 QSS 主题系统")
    logger.info("已启用 macOS 主题，QSS 长度：1234")

    logger.debug("尝试连接服务器")
    logger.info("服务器连接成功: http://localhost:6185")

    logger.warning("配置文件版本较旧，已自动升级")

    logger.info(
        "启动 WebSocket 连接 - 服务器: http://localhost:6185, WS端口: 6190, Session: desktop_abc123"
    )
    logger.info("WebSocket 连接启动成功，可接收远程命令")

    logger.debug("主动对话服务已启动")
    logger.info("进入事件循环")

    # 模拟一个错误
    logger.error("服务器连接失败: Connection refused")
    logger.warning("启动 WebSocket 连接失败: [Errno 111] Connection refused")


if __name__ == "__main__":
    # 配置根日志器
    configure_root_logger(
        level=logging.DEBUG,
        use_colors=True,
        log_file=None,  # 不写文件，只输出到控制台
    )

    print("彩色日志系统测试\n")

    test_basic_logging()
    test_formatted_logging()
    test_exception_logging()
    test_different_modules()
    test_realworld_scenario()

    print("\n" + "=" * 60)
    print("测试完成！")
    print("=" * 60)
