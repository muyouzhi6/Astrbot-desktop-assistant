"""
消息桥接器 (QAsync 重构版)

负责 GUI 和远程服务器之间的消息传递。
使用 qasync 使得 asyncio 和 Qt 事件循环共存，因此不再需要线程安全队列。
"""

import asyncio
import json
import logging
import time
import uuid
from dataclasses import dataclass, field
from typing import Optional, Any

from PySide6.QtCore import QObject, Signal

from .api_client import AstrBotApiClient, SSEEvent, ConnectionState
from .config import ClientConfig

logger = logging.getLogger(__name__)


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
    3. 请求-响应匹配（通过 request_id）
    """

    # 信号
    message_received = Signal(object)  # 发送 OutputMessage
    connection_state_changed = Signal(object)  # 发送 ConnectionState

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

        # 请求追踪：当前活跃的请求ID
        self._current_request_id: Optional[str] = None
        # 请求锁：确保同一时间只有一个请求在处理
        self._request_lock = asyncio.Lock()

    def _on_api_state_change(self, state: ConnectionState):
        """API 客户端状态变化回调"""
        self.connection_state_changed.emit(state)

        # 发送状态消息到 GUI
        self.message_received.emit(
            OutputMessage(
                msg_type="status",
                content=state.value,
                session_id="",
                metadata={"state": state.value},
            )
        )

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

    def _generate_request_id(self) -> str:
        """生成唯一的请求ID"""
        return f"req_{int(time.time() * 1000)}_{uuid.uuid4().hex[:8]}"

    async def send_input(self, msg: InputMessage):
        """发送输入消息（使用请求锁确保顺序处理）"""
        if not self.is_connected:
            self.message_received.emit(
                OutputMessage(
                    msg_type="error",
                    content="未连接到服务器",
                    session_id=msg.session_id,
                )
            )
            return

        # 使用锁确保同一时间只有一个请求在处理
        # 这样可以避免多个并发请求导致的响应混淆
        async with self._request_lock:
            await self._send_input_internal(msg)

    async def _send_input_internal(self, msg: InputMessage):
        """内部发送消息实现"""
        try:
            session_id = msg.session_id or self.config.session_id

            if not session_id:
                self.message_received.emit(
                    OutputMessage(
                        msg_type="error",
                        content="没有有效的会话",
                        session_id="",
                    )
                )
                return

            # 生成唯一请求ID
            request_id = self._generate_request_id()
            self._current_request_id = request_id
            logger.debug(f"发送请求: {request_id}, 类型: {msg.msg_type}")

            # 根据消息类型发送
            streaming = self.config.server.enable_streaming

            if msg.msg_type == "text":
                async for event in self.api_client.send_text_message(
                    session_id=session_id,
                    text=msg.content,
                    enable_streaming=streaming,
                ):
                    self._handle_sse_event(event, session_id, request_id)
                    await asyncio.sleep(0)

            elif msg.msg_type in ("image", "screenshot"):
                async for event in self.api_client.send_image_message(
                    session_id=session_id,
                    image_path=msg.content,
                    text=msg.metadata.get("text", ""),
                    enable_streaming=streaming,
                ):
                    self._handle_sse_event(event, session_id, request_id)
                    await asyncio.sleep(0)

            elif msg.msg_type == "voice":
                async for event in self.api_client.send_voice_message(
                    session_id=session_id,
                    audio_path=msg.content,
                    enable_streaming=streaming,
                ):
                    self._handle_sse_event(event, session_id, request_id)
                    await asyncio.sleep(0)

            elif msg.msg_type == "file":
                async for event in self.api_client.send_file_message(
                    session_id=session_id,
                    file_path=msg.content,
                    text=msg.metadata.get("text", ""),
                    enable_streaming=streaming,
                ):
                    self._handle_sse_event(event, session_id, request_id)
                    await asyncio.sleep(0)

            logger.debug(f"请求完成: {request_id}")

        except Exception as e:
            logger.error(f"处理输入消息失败: {e}")
            self.message_received.emit(
                OutputMessage(
                    msg_type="error",
                    content=f"发送失败: {e}",
                    session_id=msg.session_id,
                )
            )
        finally:
            # 清除当前请求ID
            self._current_request_id = None

    def _handle_sse_event(
        self, event: SSEEvent, session_id: str, request_id: Optional[str] = None
    ):
        """处理 SSE 事件并发射信号"""
        # 将请求ID添加到元数据中，用于追踪
        base_metadata = {"request_id": request_id} if request_id else {}

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

            metadata = {**base_metadata, "chain_type": event.chain_type}
            self.message_received.emit(
                OutputMessage(
                    msg_type="text",
                    content=content,
                    session_id=session_id,
                    streaming=event.streaming,
                    metadata=metadata,
                )
            )

        elif event.event_type == "image":
            filename = event.data.replace("[IMAGE]", "")
            metadata = {**base_metadata, "filename": filename}
            self.message_received.emit(
                OutputMessage(
                    msg_type="image",
                    content=filename,
                    session_id=session_id,
                    metadata=metadata,
                )
            )

        elif event.event_type == "record":
            filename = event.data.replace("[RECORD]", "")
            metadata = {**base_metadata, "filename": filename}
            self.message_received.emit(
                OutputMessage(
                    msg_type="voice",
                    content=filename,
                    session_id=session_id,
                    metadata=metadata,
                )
            )

        elif event.event_type == "file":
            filename = event.data.replace("[FILE]", "")
            metadata = {**base_metadata, "filename": filename}
            self.message_received.emit(
                OutputMessage(
                    msg_type="file",
                    content=filename,
                    session_id=session_id,
                    metadata=metadata,
                )
            )

        elif event.event_type in ("end", "complete"):
            self.message_received.emit(
                OutputMessage(
                    msg_type="end",
                    content="",
                    session_id=session_id,
                    is_complete=True,
                    metadata=base_metadata,
                )
            )

        elif event.event_type == "break":
            metadata = {**base_metadata, "break": True}
            self.message_received.emit(
                OutputMessage(
                    msg_type="end",
                    content="",
                    session_id=session_id,
                    is_complete=False,
                    metadata=metadata,
                )
            )

        elif event.event_type == "message_saved":
            raw = event.raw or {}
            data = raw.get("data", {})
            metadata = {
                **base_metadata,
                "message_id": data.get("id"),
                "created_at": data.get("created_at"),
            }
            self.message_received.emit(
                OutputMessage(
                    msg_type="saved",
                    content="",
                    session_id=session_id,
                    metadata=metadata,
                )
            )

        elif event.event_type == "error":
            self.message_received.emit(
                OutputMessage(
                    msg_type="error",
                    content=event.data,
                    session_id=session_id,
                    metadata=base_metadata,
                )
            )

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
