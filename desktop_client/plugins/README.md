# 🔌 AstrBot Desktop 插件开发指南

本文档详细介绍如何为 AstrBot Desktop 桌面客户端开发插件。

## 📋 目录

- [快速开始](#-快速开始)
- [插件结构](#-插件结构)
- [核心概念](#-核心概念)
- [钩子系统](#-钩子系统)
- [配置管理](#-配置管理)
- [最佳实践](#-最佳实践)
- [API 参考](#-api-参考)
- [示例插件](#-示例插件)

---

## 🚀 快速开始

### 1. 创建插件文件

在 `plugins/installed/` 目录下创建你的插件：

**单文件插件：**
```
plugins/installed/my_plugin.py
```

**目录插件：**
```
plugins/installed/my_plugin/
├── __init__.py      # 插件入口
├── handlers.py      # 钩子处理器
└── utils.py         # 工具函数
```

### 2. 编写插件代码

```python
from desktop_client.plugins import IPlugin, PluginMetadata
from desktop_client.plugins.hooks import HookType, HookContext, HookResult

class MyPlugin(IPlugin):
    """我的第一个插件"""
    
    @property
    def metadata(self) -> PluginMetadata:
        return PluginMetadata(
            name="my_plugin",
            version="1.0.0",
            author="你的名字",
            description="插件功能描述",
        )
    
    def on_load(self) -> bool:
        # 注册钩子
        self.register_hook(
            HookType.PRE_MESSAGE_SEND,
            self._on_message
        )
        return True
    
    async def _on_message(self, context: HookContext) -> HookResult:
        message = context.get("message", "")
        print(f"即将发送消息: {message}")
        return HookResult.CONTINUE
```

### 3. 启用插件

- 重启应用，插件会自动被发现
- 或使用插件管理器热加载

---

## 📁 插件结构

### 必需元素

| 元素 | 说明 |
|------|------|
| `IPlugin` 子类 | 插件主类，包含核心逻辑 |
| `metadata` 属性 | 返回 `PluginMetadata` 对象 |

### 可选元素

| 元素 | 说明 |
|------|------|
| `on_load()` | 插件加载时调用 |
| `on_unload()` | 插件卸载时调用 |
| `on_enable()` | 插件启用时调用 |
| `on_disable()` | 插件禁用时调用 |

### 生命周期

```
创建实例 → on_load() → on_enable() → [运行中] → on_disable() → on_unload()
```

---

## 🎯 核心概念

### PluginMetadata（插件元数据）

```python
PluginMetadata(
    name="unique_plugin_id",      # 唯一标识符（必需）
    version="1.0.0",              # 版本号
    author="作者名",               # 作者
    description="功能描述",        # 描述
    homepage="https://...",       # 主页
    dependencies=["other_plugin"], # 依赖插件
    tags=["工具", "消息"],         # 分类标签
)
```

### PluginState（插件状态）

| 状态 | 说明 |
|------|------|
| `UNLOADED` | 未加载 |
| `LOADED` | 已加载但未启用 |
| `ENABLED` | 已启用，正在运行 |
| `DISABLED` | 已禁用 |
| `ERROR` | 错误状态 |

---

## 🪝 钩子系统

钩子允许插件在应用的关键时刻插入自定义逻辑。

### 可用钩子

#### 消息相关

| 钩子 | 触发时机 | 可修改数据 |
|------|----------|------------|
| `PRE_MESSAGE_SEND` | 消息发送前 | `message`, `metadata` |
| `POST_MESSAGE_SEND` | 消息发送后 | - |
| `PRE_MESSAGE_RECEIVE` | 消息接收前 | `message` |
| `POST_MESSAGE_RECEIVE` | 消息接收后 | - |

#### 截图相关

| 钩子 | 触发时机 | 可修改数据 |
|------|----------|------------|
| `PRE_SCREENSHOT` | 截图前 | - |
| `POST_SCREENSHOT` | 截图后 | - |
| `ON_SCREENSHOT_ANALYSIS` | 截图分析时 | `prompt` |

#### 连接相关

| 钩子 | 触发时机 |
|------|----------|
| `ON_CONNECT` | 连接建立时 |
| `ON_DISCONNECT` | 连接断开时 |
| `ON_RECONNECT` | 重新连接时 |

#### 主动对话

| 钩子 | 触发时机 | 可修改数据 |
|------|----------|------------|
| `ON_PROACTIVE_TRIGGER` | 主动对话触发时 | - |
| `ON_PROACTIVE_MESSAGE` | 主动对话消息生成时 | `message` |

#### UI 相关

| 钩子 | 触发时机 |
|------|----------|
| `ON_THEME_CHANGE` | 主题切换时 |
| `ON_WINDOW_STATE_CHANGE` | 窗口状态变化时 |

#### 生命周期

| 钩子 | 触发时机 |
|------|----------|
| `ON_APP_START` | 应用启动时 |
| `ON_APP_SHUTDOWN` | 应用关闭时 |

### 注册钩子

**方式一：手动注册**

```python
def on_load(self) -> bool:
    self.register_hook(
        HookType.PRE_MESSAGE_SEND,
        self._handler,
        HookPriority.NORMAL
    )
    return True

async def _handler(self, context: HookContext) -> HookResult:
    # 处理逻辑
    return HookResult.CONTINUE
```

**方式二：装饰器注册**

```python
from desktop_client.plugins.hooks import hook

@hook(HookType.PRE_MESSAGE_SEND, HookPriority.HIGH)
async def on_pre_message(self, context: HookContext) -> HookResult:
    # 处理逻辑
    return HookResult.CONTINUE
```

### HookContext（钩子上下文）

```python
async def handler(self, context: HookContext) -> HookResult:
    # 读取数据
    message = context.get("message", "")
    
    # 修改数据
    context.set("message", f"[前缀] {message}")
    
    # 检查状态
    if context.is_cancelled():
        return HookResult.CONTINUE
    
    return HookResult.MODIFIED
```

### HookResult（返回值）

| 返回值 | 效果 |
|--------|------|
| `CONTINUE` | 继续执行后续钩子和原始操作 |
| `ABORT` | 中止所有后续操作 |
| `SKIP` | 跳过后续钩子，继续原始操作 |
| `MODIFIED` | 数据已修改，继续执行 |

### HookPriority（优先级）

| 优先级 | 值 | 说明 |
|--------|-----|------|
| `HIGHEST` | 0 | 最先执行 |
| `HIGH` | 25 | 优先执行 |
| `NORMAL` | 50 | 默认优先级 |
| `LOW` | 75 | 后执行 |
| `LOWEST` | 100 | 最后执行 |
| `MONITOR` | 999 | 仅监控，不应修改数据 |

---

## ⚙️ 配置管理

插件配置自动持久化到 `plugins/configs/{plugin_name}.json`。

### 使用配置

```python
def on_load(self) -> bool:
    # 加载配置
    self.load_config()
    
    # 设置默认值
    if "setting_name" not in self.config:
        self.set_config_value("setting_name", "default_value")
    
    return True

def on_unload(self) -> None:
    # 保存配置
    self.save_config()
    super().on_unload()

def some_method(self):
    # 读取配置
    value = self.get_config_value("setting_name", "fallback")
    
    # 修改配置
    self.set_config_value("setting_name", "new_value")
```

---

## ✨ 最佳实践

### 1. 错误处理

```python
async def handler(self, context: HookContext) -> HookResult:
    try:
        # 可能出错的代码
        result = await some_operation()
    except Exception as e:
        logger.error(f"[{self.name}] 操作失败: {e}")
        return HookResult.CONTINUE  # 不中断其他插件
    
    return HookResult.CONTINUE
```

### 2. 使用日志

```python
import logging
logger = logging.getLogger(__name__)

class MyPlugin(IPlugin):
    def on_load(self) -> bool:
        logger.info(f"[{self.name}] 插件加载")
        logger.debug(f"[{self.name}] 调试信息")
        logger.warning(f"[{self.name}] 警告信息")
        logger.error(f"[{self.name}] 错误信息")
        return True
```

### 3. 资源清理

```python
def on_unload(self) -> None:
    # 关闭文件、连接等
    if self._file:
        self._file.close()
    
    # 取消定时器
    if self._timer:
        self._timer.cancel()
    
    # 调用父类（自动注销钩子）
    super().on_unload()
```

### 4. 异步操作

```python
async def handler(self, context: HookContext) -> HookResult:
    # 正确：使用 await
    result = await self._async_operation()
    
    # 避免：长时间阻塞
    # time.sleep(10)  # ❌
    await asyncio.sleep(0.1)  # ✅
    
    return HookResult.CONTINUE
```

### 5. 插件依赖

```python
@property
def metadata(self) -> PluginMetadata:
    return PluginMetadata(
        name="my_plugin",
        dependencies=["base_plugin"],  # 声明依赖
    )

def on_load(self) -> bool:
    # 管理器会确保依赖已加载
    return True
```

---

## 📚 API 参考

### IPlugin 基类

```python
class IPlugin(ABC):
    # 属性
    @property
    def metadata(self) -> PluginMetadata: ...  # 必须实现
    @property
    def name(self) -> str: ...
    @property
    def version(self) -> str: ...
    @property
    def state(self) -> PluginState: ...
    @property
    def is_enabled(self) -> bool: ...
    @property
    def config(self) -> Dict[str, Any]: ...
    
    # 生命周期
    def on_load(self) -> bool: ...
    def on_unload(self) -> None: ...
    def on_enable(self) -> bool: ...
    def on_disable(self) -> None: ...
    
    # 钩子管理
    def register_hook(
        self,
        hook_type: HookType,
        callback: Callable,
        priority: HookPriority = None
    ) -> bool: ...
    
    def unregister_hook(
        self,
        hook_type: HookType,
        callback: Callable
    ) -> bool: ...
    
    # 配置管理
    def load_config(self) -> Dict[str, Any]: ...
    def save_config(self) -> bool: ...
    def get_config_value(self, key: str, default: Any = None) -> Any: ...
    def set_config_value(self, key: str, value: Any) -> None: ...
```

### PluginManager 管理器

```python
# 获取全局管理器
from desktop_client.plugins import get_plugin_manager
manager = get_plugin_manager()

# 插件操作
await manager.discover_plugins()           # 发现插件
await manager.load_plugin(PluginClass)     # 加载插件
await manager.unload_plugin("plugin_name") # 卸载插件
await manager.enable_plugin("plugin_name") # 启用插件
await manager.disable_plugin("plugin_name")# 禁用插件
await manager.reload_plugin("plugin_name") # 重载插件

# 钩子调度
context = HookContext(hook_type=HookType.CUSTOM, data={})
await manager.dispatch_hook(context)

# 插件查询
plugin = manager.get_plugin("plugin_name")
plugins = manager.list_plugins()
```

---

## 📝 示例插件

查看 [`example_plugin.py`](./example_plugin.py) 获取完整的示例代码，包括：

- ✅ 元数据定义
- ✅ 生命周期方法
- ✅ 钩子注册与处理
- ✅ 配置管理
- ✅ 统计功能
- ✅ 日志记录

---

## 🤝 贡献指南

1. Fork 本仓库
2. 创建功能分支
3. 编写插件代码
4. 添加测试和文档
5. 提交 Pull Request

---

## 📄 许可证

插件遵循项目主许可证。

---

## 🔗 相关链接

- [AstrBot 主项目](https://github.com/Soulter/AstrBot)
- [桌面客户端文档](../README.md)
- [架构设计文档](../../docs/ARCHITECTURE.md)