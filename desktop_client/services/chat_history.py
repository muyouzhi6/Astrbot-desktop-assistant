"""
聊天记录管理器

提供统一的消息管理，支持：
- 单例模式确保全局唯一
- 消息持久化到本地文件
- Qt 信号机制实现跨窗口同步
"""

import asyncio
import json
import os
import uuid
import time
from dataclasses import dataclass, field, asdict
from typing import List, Optional, Dict, Any
from pathlib import Path

from PySide6.QtCore import QObject, Signal


@dataclass
class ChatMessage:
    """聊天消息数据结构"""
    id: str = ""                    # UUID
    role: str = "user"              # "user" / "assistant"
    content: str = ""               # 消息内容
    msg_type: str = "text"          # "text" / "image" / "voice" / "video" / "file"
    timestamp: float = 0.0          # 时间戳
    file_path: str = ""             # 媒体文件路径（可选）
    metadata: Dict[str, Any] = field(default_factory=dict)  # 其他元数据
    
    def __post_init__(self):
        if not self.id:
            self.id = str(uuid.uuid4())
        if self.timestamp == 0.0:
            self.timestamp = time.time()
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ChatMessage':
        """从字典创建"""
        return cls(
            id=data.get('id', ''),
            role=data.get('role', 'user'),
            content=data.get('content', ''),
            msg_type=data.get('msg_type', 'text'),
            timestamp=data.get('timestamp', 0.0),
            file_path=data.get('file_path', ''),
            metadata=data.get('metadata', {})
        )


class ChatHistoryManager(QObject):
    """
    聊天记录管理器（单例模式）
    
    提供统一的消息管理接口，支持：
    - 添加、获取、清除消息
    - 持久化到本地 JSON 文件
    - Qt 信号机制实现跨窗口同步
    """
    
    # 信号定义
    message_added = Signal(object)      # 新消息添加时发射，参数为 ChatMessage
    message_updated = Signal(str, str)  # 消息更新时发射，参数为 (message_id, new_content)
    messages_cleared = Signal()         # 消息清除时发射
    history_loaded = Signal()           # 历史记录加载完成时发射
    
    # 单例实例
    _instance: Optional['ChatHistoryManager'] = None
    _initialized: bool = False
    
    def __new__(cls, *args, **kwargs):
        """单例模式实现"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self, history_path: str = ""):
        """
        初始化聊天记录管理器
        
        Args:
            history_path: 聊天记录保存路径，为空则使用默认路径
        """
        # 避免重复初始化
        if ChatHistoryManager._initialized:
            # 如果已初始化但传入了新路径，更新路径
            if history_path and history_path != self._history_path:
                self._history_path = history_path
            return
            
        super().__init__()
        
        self._messages: List[ChatMessage] = []
        self._history_path = history_path or self._get_default_history_path()
        self._max_messages = 1000  # 最大保存消息数
        self._auto_save = True     # 自动保存开关
        self._dirty = False        # 是否有未保存的更改
        
        # 加载历史记录
        self.load_from_file()
        
        ChatHistoryManager._initialized = True
    
    @staticmethod
    def _get_default_history_path() -> str:
        """获取默认的聊天记录保存路径"""
        # Windows: %APPDATA%/AstrBotDesktopClient/chat_history.json
        # Linux/Mac: ~/.config/astrbot-desktop-client/chat_history.json
        if os.name == 'nt':
            base = os.environ.get('APPDATA', os.path.expanduser('~'))
            config_dir = Path(base) / 'AstrBotDesktopClient'
        else:
            config_dir = Path.home() / '.config' / 'astrbot-desktop-client'
        
        config_dir.mkdir(parents=True, exist_ok=True)
        return str(config_dir / 'chat_history.json')
    
    @classmethod
    def get_instance(cls, history_path: str = "") -> 'ChatHistoryManager':
        """
        获取单例实例
        
        Args:
            history_path: 聊天记录保存路径
            
        Returns:
            ChatHistoryManager 实例
        """
        if cls._instance is None:
            cls._instance = cls(history_path)
        return cls._instance
    
    @classmethod
    def reset_instance(cls):
        """重置单例实例（主要用于测试）"""
        cls._instance = None
        cls._initialized = False
    
    def set_history_path(self, path: str):
        """
        设置聊天记录保存路径
        
        Args:
            path: 新的保存路径
        """
        if path != self._history_path:
            # 先保存当前数据到旧路径
            if self._dirty:
                self.save_to_file()
            
            self._history_path = path
            # 从新路径加载数据
            self.load_from_file()
    
    def get_history_path(self) -> str:
        """获取当前聊天记录保存路径"""
        return self._history_path
    
    def add_message(
        self,
        role: str,
        content: str,
        msg_type: str = "text",
        file_path: str = "",
        metadata: Optional[Dict[str, Any]] = None
    ) -> ChatMessage:
        """
        添加新消息
        
        Args:
            role: 消息角色 ("user" / "assistant")
            content: 消息内容
            msg_type: 消息类型 ("text" / "image" / "voice" / "video" / "file")
            file_path: 媒体文件路径
            metadata: 其他元数据
            
        Returns:
            创建的 ChatMessage 对象
        """
        message = ChatMessage(
            role=role,
            content=content,
            msg_type=msg_type,
            file_path=file_path,
            metadata=metadata or {}
        )
        
        self._messages.append(message)
        self._dirty = True
        
        # 限制消息数量
        if len(self._messages) > self._max_messages:
            self._messages = self._messages[-self._max_messages:]
        
        # 自动保存 (异步)
        if self._auto_save:
            self._schedule_save()
        
        # 发射信号
        self.message_added.emit(message)
        
        return message
    
    def update_message(self, message_id: str, content: str) -> bool:
        """
        更新消息内容（用于流式响应）
        
        Args:
            message_id: 消息 ID
            content: 新的消息内容
            
        Returns:
            是否更新成功
        """
        for msg in self._messages:
            if msg.id == message_id:
                msg.content = content
                self._dirty = True
                
                # 发射更新信号
                self.message_updated.emit(message_id, content)
                return True
        
        return False
    
    def get_last_message(self) -> Optional[ChatMessage]:
        """获取最后一条消息"""
        if self._messages:
            return self._messages[-1]
        return None
    
    def get_messages(self, limit: int = 0) -> List[ChatMessage]:
        """
        获取所有消息
        
        Args:
            limit: 返回的最大消息数，0 表示返回全部
            
        Returns:
            消息列表
        """
        if limit > 0:
            return self._messages[-limit:]
        return self._messages.copy()
    
    def get_message_by_id(self, message_id: str) -> Optional[ChatMessage]:
        """
        根据 ID 获取消息
        
        Args:
            message_id: 消息 ID
            
        Returns:
            ChatMessage 对象，未找到返回 None
        """
        for msg in self._messages:
            if msg.id == message_id:
                return msg
        return None
    
    def clear_history(self):
        """清空所有聊天记录"""
        self._messages.clear()
        self._dirty = True
        
        if self._auto_save:
            self._schedule_save()
        
        # 发射信号
        self.messages_cleared.emit()
    
    def _schedule_save(self):
        """调度异步保存任务"""
        try:
            # 获取当前事件循环
            loop = asyncio.get_running_loop()
            if loop.is_running():
                loop.create_task(self.save_to_file_async())
            else:
                # 如果没有运行中的循环，回退到同步保存
                self.save_to_file_sync()
        except RuntimeError:
            # 如果没有事件循环，回退到同步保存
            self.save_to_file_sync()

    async def save_to_file_async(self, path: str = "") -> bool:
        """
        异步保存聊天记录到文件
        
        Args:
            path: 保存路径，为空则使用默认路径
            
        Returns:
            是否保存成功
        """
        save_path = path or self._history_path
        
        try:
            # 1. 在主线程中准备数据（避免多线程竞争）
            # 深拷贝或转换为 dict，确保传递给线程的数据是独立的
            data_to_save = {
                'version': 1,
                'messages': [msg.to_dict() for msg in self._messages]
            }
            
            # 2. 在线程池中执行文件写入操作
            def _write_file():
                # 确保目录存在
                Path(save_path).parent.mkdir(parents=True, exist_ok=True)
                with open(save_path, 'w', encoding='utf-8') as f:
                    json.dump(data_to_save, f, ensure_ascii=False, indent=2)
            
            await asyncio.to_thread(_write_file)
            
            self._dirty = False
            # print(f"[ChatHistory] 聊天记录已异步保存到: {save_path}")
            return True
            
        except Exception as e:
            print(f"[ChatHistory] 异步保存聊天记录失败: {e}")
            return False

    def save_to_file_sync(self, path: str = "") -> bool:
        """
        同步保存聊天记录到文件（保留用于向后兼容或无事件循环的情况）
        
        Args:
            path: 保存路径，为空则使用默认路径
            
        Returns:
            是否保存成功
        """
        save_path = path or self._history_path
        
        try:
            # 确保目录存在
            Path(save_path).parent.mkdir(parents=True, exist_ok=True)
            
            data = {
                'version': 1,
                'messages': [msg.to_dict() for msg in self._messages]
            }
            
            with open(save_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            
            self._dirty = False
            print(f"[ChatHistory] 聊天记录已保存到: {save_path}")
            return True
            
        except Exception as e:
            print(f"[ChatHistory] 保存聊天记录失败: {e}")
            return False
            
    def save_to_file(self, path: str = "") -> bool:
        """
        保存聊天记录到文件 (兼容旧接口，优先使用异步)
        
        Args:
            path: 保存路径
            
        Returns:
            True (注意：异步保存时无法立即知道结果，这里总是返回 True 或调度结果)
        """
        if path:
             # 如果指定了路径，通常是导出操作，使用同步保存以确保完成
            return self.save_to_file_sync(path)
        
        self._schedule_save()
        return True
    
    def load_from_file(self, path: str = "") -> bool:
        """
        从文件加载聊天记录
        
        Args:
            path: 加载路径，为空则使用默认路径
            
        Returns:
            是否加载成功
        """
        load_path = path or self._history_path
        
        if not os.path.exists(load_path):
            print(f"[ChatHistory] 聊天记录文件不存在: {load_path}，将使用空历史记录")
            self._messages = []
            self._dirty = False
            # 即使文件不存在，也发射信号通知UI可以开始显示（空列表）
            self.history_loaded.emit()
            return True  # 不视为错误，只是没有历史记录
        
        try:
            with open(load_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # 检查文件是否为空
            if not content.strip():
                print(f"[ChatHistory] 聊天记录文件为空: {load_path}")
                self._messages = []
                self._dirty = False
                self.history_loaded.emit()
                return True
            
            data = json.loads(content)
            
            # 版本检查
            version = data.get('version', 1)
            if version != 1:
                print(f"[ChatHistory] 警告: 聊天记录版本 {version} 可能不兼容")
            
            # 加载消息
            messages_data = data.get('messages', [])
            loaded_messages = []
            
            for i, m in enumerate(messages_data):
                try:
                    msg = ChatMessage.from_dict(m)
                    loaded_messages.append(msg)
                except Exception as e:
                    print(f"[ChatHistory] 跳过无效消息 {i}: {e}")
                    continue
            
            self._messages = loaded_messages
            self._dirty = False
            print(f"[ChatHistory] 成功加载 {len(self._messages)} 条聊天记录 (来自 {load_path})")
            
            # 发射信号
            self.history_loaded.emit()
            
            return True
            
        except json.JSONDecodeError as e:
            print(f"[ChatHistory] 聊天记录文件格式错误: {e}")
            # 文件损坏，备份后重置
            self._backup_corrupted_file(load_path)
            self._messages = []
            self._dirty = False
            self.history_loaded.emit()
            return False
            
        except Exception as e:
            print(f"[ChatHistory] 加载聊天记录失败: {e}")
            import traceback
            traceback.print_exc()
            # 出错时也发射信号，让UI可以正常初始化
            self._messages = []
            self._dirty = False
            self.history_loaded.emit()
            return False
    
    def _backup_corrupted_file(self, path: str):
        """备份损坏的聊天记录文件"""
        try:
            if os.path.exists(path):
                backup_path = path + f".corrupted.{int(time.time())}"
                os.rename(path, backup_path)
                print(f"[ChatHistory] 已备份损坏的文件到: {backup_path}")
        except Exception as e:
            print(f"[ChatHistory] 备份损坏文件失败: {e}")
    
    def set_auto_save(self, enabled: bool):
        """设置自动保存开关"""
        self._auto_save = enabled
    
    def set_max_messages(self, max_count: int):
        """设置最大消息数"""
        self._max_messages = max(100, max_count)  # 最少保留 100 条
    
    def get_message_count(self) -> int:
        """获取消息数量"""
        return len(self._messages)
    
    def has_unsaved_changes(self) -> bool:
        """检查是否有未保存的更改"""
        return self._dirty
    
    def export_to_file(self, path: str, format: str = "json") -> bool:
        """
        导出聊天记录到指定文件
        
        Args:
            path: 导出路径
            format: 导出格式 ("json" / "txt")
            
        Returns:
            是否导出成功
        """
        try:
            if format == "txt":
                with open(path, 'w', encoding='utf-8') as f:
                    for msg in self._messages:
                        role = "用户" if msg.role == "user" else "助手"
                        time_str = time.strftime('%Y-%m-%d %H:%M:%S', 
                                                  time.localtime(msg.timestamp))
                        f.write(f"[{time_str}] {role}:\n{msg.content}\n\n")
            else:
                return self.save_to_file(path)
            
            print(f"[ChatHistory] 聊天记录已导出到: {path}")
            return True
            
        except Exception as e:
            print(f"[ChatHistory] 导出聊天记录失败: {e}")
            return False


# 便捷函数
def get_chat_history_manager(history_path: str = "") -> ChatHistoryManager:
    """获取聊天记录管理器实例"""
    return ChatHistoryManager.get_instance(history_path)