"""
消息桥接器 (QAsync 重构版)

负责 GUI 和远程服务器之间的消息传递。
使用 qasync 使得 asyncio 和 Qt 事件循环共存，因此不再需要线程安全队列。
"""

import asyncio
import json
import time
from dataclasses import dataclass, field
from typing import Optional, Any, Callable

from PySide6.QtCore import QObject, Signal

from .api_client import AstrBotApiClient, SSEEvent, ConnectionState
from .config import ClientConfig


@dataclass
class InputMessage:
    """输入消息（GUI -> 服务器）"""
    msg_type: str  # text, image, voice, file, screenshot
    content: Any
    session_id: str
    timestamp: float = field(default_factory=time.time)
    metadata: dict = field(default_factory=dict)


@dataclass  
class OutputMessage:
    """输出消息（服务器 -> GUI）"""
    msg_type: str  # text, image, voice, file, error, end, status
    content: Any
    session_id: str
    streaming: bool = False
    is_complete: bool = False
    metadata: dict = field(default_factory=dict)


class MessageBridge(QObject):
    """
    消息桥接器
    
    负责：
    1. 管理与 AstrBot 服务器的连接
    2. 处理消息传递（直接通过 asyncio 和 Signal）
    """
    
    # 信号
    message_received = Signal(object)  # 发送 OutputMessage
    connection_state_changed = Signal(object) # 发送 ConnectionState
    
    def __init__(self, config: ClientConfig):
        super().__init__()
        self.config = config
        
        # API 客户端
        self.api_client = AstrBotApiClient(
            server_url=config.server.url,
            username=config.server.username,
            password=config.server.password,
            token=config.server.token,
            timeout=config.server.request_timeout,
            on_state_change=self._on_api_state_change,
        )
        
    def _on_api_state_change(self, state: ConnectionState):
        """API 客户端状态变化回调"""
        self.connection_state_changed.emit(state)
        
        # 发送状态消息到 GUI
        self.message_received.emit(OutputMessage(
            msg_type="status",
            content=state.value,
            session_id="",
            metadata={"state": state.value}
        ))
    
    @property
    def connection_state(self) -> ConnectionState:
        return self.api_client.state
    
    @property
    def is_connected(self) -> bool:
        return self.api_client.is_connected
    
    async def connect_server(self) -> tuple[bool, str]:
        """连接到服务器（登录）"""
        # 1. 尝试使用现有 Token 验证
        if self.api_client.token:
            is_valid = await self.api_client.check_connection()
            if is_valid:
                # 确保有会话
                if not self.config.session_id:
                    session_ok, session_result = await self.api_client.create_session()
                    if session_ok:
                        self.config.session_id = session_result
                        self.config.save()
                # Token 验证成功后也启动健康检测
                await self.api_client.start_health_check()
                return True, "连接成功 (Token)"
        
        # 2. Token 无效或不存在，尝试使用用户名密码登录
        success, message = await self.api_client.login()
        
        if success:
            # 保存 token 到配置
            self.config.server.token = self.api_client.token
            self.config.save()
            
            # 确保有会话
            if not self.config.session_id:
                session_ok, session_result = await self.api_client.create_session()
                if session_ok:
                    self.config.session_id = session_result
                    self.config.save()
                else:
                    return False, f"创建会话失败: {session_result}"
            
            # login() 内部已经启动健康检测，无需重复
        
        return success, message
    
    async def disconnect_server(self):
        """断开连接"""
        await self.api_client.close()
    
    async def send_input(self, msg: InputMessage):
        """发送输入消息"""
        if not self.is_connected:
            self.message_received.emit(OutputMessage(
                msg_type="error",
                content="未连接到服务器",
                session_id=msg.session_id,
            ))
            return

        try:
            session_id = msg.session_id or self.config.session_id
            
            if not session_id:
                self.message_received.emit(OutputMessage(
                    msg_type="error",
                    content="没有有效的会话",
                    session_id="",
                ))
                return
            
            # 根据消息类型发送
            streaming = self.config.server.enable_streaming
            
            if msg.msg_type == "text":
                async for event in self.api_client.send_text_message(
                    session_id=session_id,
                    text=msg.content,
                    enable_streaming=streaming,
                ):
                    self._handle_sse_event(event, session_id)
                    await asyncio.sleep(0)
                    
            elif msg.msg_type in ("image", "screenshot"):
                async for event in self.api_client.send_image_message(
                    session_id=session_id,
                    image_path=msg.content,
                    text=msg.metadata.get("text", ""),
                    enable_streaming=streaming,
                ):
                    self._handle_sse_event(event, session_id)
                    await asyncio.sleep(0)
                    
            elif msg.msg_type == "voice":
                async for event in self.api_client.send_voice_message(
                    session_id=session_id,
                    audio_path=msg.content,
                    enable_streaming=streaming,
                ):
                    self._handle_sse_event(event, session_id)
                    await asyncio.sleep(0)
                    
            elif msg.msg_type == "file":
                async for event in self.api_client.send_file_message(
                    session_id=session_id,
                    file_path=msg.content,
                    text=msg.metadata.get("text", ""),
                    enable_streaming=streaming,
                ):
                    self._handle_sse_event(event, session_id)
                    await asyncio.sleep(0)
            
        except Exception as e:
            print(f"处理输入消息失败: {e}")
            self.message_received.emit(OutputMessage(
                msg_type="error",
                content=f"发送失败: {e}",
                session_id=msg.session_id,
            ))

    def _handle_sse_event(self, event: SSEEvent, session_id: str):
        """处理 SSE 事件并发射信号"""
        if event.event_type == "plain":
            # 检查内容是否为空，避免发送空消息
            if not event.data and not event.streaming:
                return  # 跳过空的非流式消息
            
            # Bug 3 修复：跳过 reasoning 类型的思维链内容
            if event.chain_type == "reasoning":
                return  # 不显示思维链内容
            
            # Bug 2 修复：检测并处理 JSON 格式的函数调用结果
            content = event.data
            if content and not event.streaming:
                content = self._extract_function_result(content)
            
            self.message_received.emit(OutputMessage(
                msg_type="text",
                content=content,
                session_id=session_id,
                streaming=event.streaming,
                metadata={"chain_type": event.chain_type}
            ))
            
        elif event.event_type == "image":
            filename = event.data.replace("[IMAGE]", "")
            self.message_received.emit(OutputMessage(
                msg_type="image",
                content=filename,
                session_id=session_id,
                metadata={"filename": filename}
            ))
            
        elif event.event_type == "record":
            filename = event.data.replace("[RECORD]", "")
            self.message_received.emit(OutputMessage(
                msg_type="voice",
                content=filename,
                session_id=session_id,
                metadata={"filename": filename}
            ))
            
        elif event.event_type == "file":
            filename = event.data.replace("[FILE]", "")
            self.message_received.emit(OutputMessage(
                msg_type="file",
                content=filename,
                session_id=session_id,
                metadata={"filename": filename}
            ))
            
        elif event.event_type in ("end", "complete"):
            self.message_received.emit(OutputMessage(
                msg_type="end",
                content="",
                session_id=session_id,
                is_complete=True,
            ))
            
        elif event.event_type == "break":
            self.message_received.emit(OutputMessage(
                msg_type="end",
                content="",
                session_id=session_id,
                is_complete=False,
                metadata={"break": True}
            ))
            
        elif event.event_type == "message_saved":
            raw = event.raw or {}
            data = raw.get("data", {})
            self.message_received.emit(OutputMessage(
                msg_type="saved",
                content="",
                session_id=session_id,
                metadata={
                    "message_id": data.get("id"),
                    "created_at": data.get("created_at"),
                }
            ))
            
        elif event.event_type == "error":
            self.message_received.emit(OutputMessage(
                msg_type="error",
                content=event.data,
                session_id=session_id,
            ))

    def _extract_function_result(self, content: str) -> str:
        """
        提取函数调用结果中的 result 字段
        
        如果内容是 JSON 格式的函数调用结果（如 {"id": "...", "ts": ..., "result": "..."}），
        则只返回 result 字段的内容，否则返回原始内容。
        """
        if not content:
            return content
            
        content = content.strip()
        
        # 快速检查是否可能是 JSON
        if not (content.startswith("{") and content.endswith("}")):
            return content
            
        try:
            data = json.loads(content)
            # 检查是否是函数调用结果的 JSON 格式
            if isinstance(data, dict) and "id" in data and "result" in data:
                result = data.get("result", "")
                # 如果 result 存在且有内容，返回 result
                if result:
                    return str(result)
        except (json.JSONDecodeError, TypeError, ValueError):
            # 不是有效的 JSON，返回原始内容
            pass
            
        return content

    def update_server_config(
        self,
        url: Optional[str] = None,
        username: Optional[str] = None,
        password: Optional[str] = None,
    ):
        """更新服务器配置"""
        if url:
            self.config.server.url = url
            self.api_client.server_url = url
        if username:
            self.config.server.username = username
            self.api_client.username = username
        if password:
            self.config.server.password = password
            self.api_client.password = password
        
        # 清除旧 token 并重置状态
        self.config.server.token = None
        self.api_client.token = None
        self.api_client.state = ConnectionState.DISCONNECTED