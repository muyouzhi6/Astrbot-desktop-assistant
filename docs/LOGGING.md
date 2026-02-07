# 日志系统使用指南

## 概述

项目使用统一的彩色日志系统，支持：
- 不同级别的彩色输出（DEBUG、INFO、WARNING、ERROR、CRITICAL）
- 详细的日志格式（时间、级别、模块名、行号）
- 同时输出到控制台和文件
- 跨平台颜色支持（Windows 10+、macOS、Linux）

## 日志级别和颜色

| 级别 | 颜色 | 使用场景 |
|------|------|----------|
| DEBUG | 灰色 | 调试信息，详细的执行流程 |
| INFO | 亮蓝色 | 一般信息，正常的操作流程 |
| WARNING | 亮黄色 | 警告信息，可能的问题 |
| ERROR | 亮红色 | 错误信息，需要处理的异常 |
| CRITICAL | 加粗红色 | 严重错误，系统无法继续运行 |

## 快速开始

### 1. 在模块中使用日志器

```python
# 方式1：推荐用于新模块
from desktop_client.logger import get_logger

logger = get_logger(__name__)

def some_function():
    logger.debug("这是调试信息")
    logger.info("这是一般信息")
    logger.warning("这是警告信息")
    logger.error("这是错误信息")
    logger.critical("这是严重错误")
```

```python
# 方式2：使用标准 logging（自动使用配置的格式化器）
import logging

logger = logging.getLogger(__name__)

def another_function():
    logger.info("标准 logging 也可以工作")
```

### 2. 配置根日志器（在应用启动时）

在 `main.py` 或应用入口处配置：

```python
import logging
from desktop_client.logger import configure_root_logger
from desktop_client.config import ClientConfig

# 获取日志文件路径
config_dir = ClientConfig.get_config_dir()
log_file = os.path.join(config_dir, "logs", "desktop_client.log")

# 配置根日志器（带日志轮转）
configure_root_logger(
    level=logging.DEBUG,    # 控制台显示级别
    use_colors=True,        # 启用彩色输出
    log_file=log_file,      # 日志文件路径
    max_bytes=10*1024*1024, # 单个文件最大 10MB（可选，默认 10MB）
    backup_count=5          # 保留 5 个备份文件（可选，默认 5 个）
)
```

**日志轮转说明**：
- `max_bytes`: 单个日志文件的最大字节数，超过后会自动轮转（默认 10MB）
- `backup_count`: 保留的旧日志文件数量（默认 5 个）
- 轮转后的日志文件名格式：`desktop_client.log.1`, `desktop_client.log.2`, ...
- 最新的日志始终在 `desktop_client.log` 中

### 3. 为单个模块设置独立的日志器

```python
from desktop_client.logger import setup_logger
import logging

# 创建独立配置的日志器
logger = setup_logger(
    name="my_module",
    level=logging.INFO,
    use_colors=True,
    log_file="logs/my_module.log"
)

logger.info("这个模块有独立的日志配置")
```

## 日志格式说明

### 控制台输出格式
```
[2025-12-29 10:30:45] [INFO] [desktop_client.app:52] 启用 QSS 主题系统
```

格式分解：
- `[2025-12-29 10:30:45]` - 时间戳（灰色）
- `[INFO]` - 日志级别（根据级别显示不同颜色）
- `[desktop_client.app:52]` - 模块名和行号（青色）
- `启用 QSS 主题系统` - 日志消息（根据级别显示不同颜色）

### 文件输出格式
文件中的日志不包含颜色代码，便于文本处理：
```
[2025-12-29 10:30:45] [INFO] [desktop_client.app:52] 启用 QSS 主题系统
```

## 最佳实践

### 1. 选择合适的日志级别

```python
# ❌ 不好的做法
logger.info("变量 x 的值为 123")  # 过于详细的调试信息
logger.error("用户点击了按钮")    # 普通操作不应该用 ERROR

# ✅ 好的做法
logger.debug("变量 x 的值为 123")     # 调试信息用 DEBUG
logger.info("用户点击了按钮")         # 正常操作用 INFO
logger.warning("配置文件不存在，使用默认配置")  # 警告用 WARNING
logger.error("无法连接到服务器")       # 错误用 ERROR
```

### 2. 记录有价值的上下文信息

```python
# ❌ 不好的做法
logger.error("发生错误")

# ✅ 好的做法
logger.error(f"连接服务器失败: {server_url}, 错误: {str(e)}")
```

### 3. 使用异常记录

```python
try:
    risky_operation()
except Exception as e:
    # 使用 exc_info=True 记录完整的堆栈信息
    logger.error("操作失败", exc_info=True)

    # 或者使用 logger.exception（自动包含堆栈）
    logger.exception("操作失败")
```

### 4. 敏感信息脱敏

```python
# ❌ 不好的做法
logger.info(f"用户登录: {username}, 密码: {password}")

# ✅ 好的做法
logger.info(f"用户登录: {username}, 密码: ****")
```

## 性能考虑

### 延迟格式化

对于复杂的日志消息，使用延迟格式化避免不必要的字符串操作：

```python
# ❌ 不好的做法（总是会执行格式化）
logger.debug("复杂计算结果: " + expensive_calculation())

# ✅ 好的做法（只在日志级别满足时才格式化）
logger.debug("复杂计算结果: %s", expensive_calculation())
```

## 迁移指南

### 从 print() 迁移到 logger

```python
# 旧代码
print("[DEBUG] 创建实例...")
print(f"[INFO] 配置加载成功: {config}")
print(f"[ERROR] 连接失败: {error}")

# 新代码
logger.debug("创建实例")
logger.info(f"配置加载成功: {config}")
logger.error(f"连接失败: {error}")
```

## 自定义配置

### 禁用颜色

```python
from desktop_client.logger import configure_root_logger
import logging

# 禁用颜色（适用于不支持的终端）
configure_root_logger(
    level=logging.INFO,
    use_colors=False
)
```

### 只输出到文件

```python
# 创建只写入文件的日志器
import logging
from desktop_client.logger import setup_logger

logger = setup_logger(
    name="file_only",
    level=logging.CRITICAL,  # 控制台设置为 CRITICAL，几乎不输出
    log_file="logs/app.log",
    file_level=logging.DEBUG  # 文件记录所有 DEBUG 及以上
)
```

## 日志文件管理

### 日志文件位置

默认日志文件保存在：
```
~/.astrbot-desktop/logs/desktop_client.log
```

### 日志轮转

**默认配置**：
- 日志系统已内置日志轮转功能（使用 `RotatingFileHandler`）
- 单个日志文件默认最大 10MB
- 默认保留 5 个备份文件
- 轮转文件命名：`desktop_client.log.1`, `desktop_client.log.2`, ..., `desktop_client.log.5`

**自定义轮转配置**：

```python
import logging
from desktop_client.logger import configure_root_logger

# 自定义日志轮转参数
configure_root_logger(
    level=logging.INFO,
    log_file="logs/app.log",
    max_bytes=50*1024*1024,  # 50MB
    backup_count=10           # 保留 10 个备份
)
```

**按时间轮转**（如需实现）：

如需按时间轮转（如每天轮转），可以使用 `TimedRotatingFileHandler`：

```python
import logging
from logging.handlers import TimedRotatingFileHandler
from desktop_client.logger import ColoredFormatter

# 创建按时间轮转的处理器（每天午夜轮转）
handler = TimedRotatingFileHandler(
    "logs/app.log",
    when="midnight",         # 每天午夜轮转
    interval=1,              # 每 1 天
    backupCount=30,          # 保留 30 天
    encoding='utf-8'
)
handler.setLevel(logging.DEBUG)
handler.setFormatter(ColoredFormatter(use_colors=False))

logger = logging.getLogger(__name__)
logger.addHandler(handler)
```

## 故障排查

### 日志没有显示颜色

1. 检查终端是否支持 ANSI 颜色
2. Windows 用户确保使用 Windows 10 或更高版本
3. 尝试禁用颜色：`configure_root_logger(use_colors=False)`

### 日志文件无法创建

1. 检查日志目录是否有写权限
2. 检查磁盘空间是否充足
3. 查看是否有其他进程占用日志文件

### 日志输出重复

确保不要多次调用 `configure_root_logger()` 或 `setup_logger()`。日志器在配置后会保持状态。

## 示例代码

完整示例见 `desktop_client/app.py` 中的使用。

```python
from desktop_client.logger import get_logger

logger = get_logger(__name__)

class MyService:
    def __init__(self):
        logger.info("初始化服务")

    def process(self, data):
        logger.debug(f"处理数据: {len(data)} 项")
        try:
            result = self._do_process(data)
            logger.info("处理完成")
            return result
        except ValueError as e:
            logger.warning(f"数据验证失败: {e}")
            return None
        except Exception as e:
            logger.error("处理失败", exc_info=True)
            raise
```

## 参考资料

- Python logging 官方文档: https://docs.python.org/3/library/logging.html
- ANSI 颜色代码参考: https://en.wikipedia.org/wiki/ANSI_escape_code
