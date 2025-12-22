"""
AstrBot HTTP API 客户端

负责与远程 AstrBot 服务器通信，包括：
- 登录认证
- 会话管理
- 消息发送/接收（SSE 流式）
- 文件上传/下载
"""

import asyncio
import hashlib
import json
import os
import time
import warnings
from dataclasses import dataclass
from enum import Enum
from typing import Optional, Callable, AsyncGenerator, Any
from pathlib import Path

import httpx

# 忽略 httpcore 的异步生成器清理警告（这是 httpcore 的已知问题）
warnings.filterwarnings("ignore", message="async generator ignored GeneratorExit")
# 忽略 cancel scope 相关的警告
warnings.filterwarnings("ignore", message="Attempted to exit cancel scope")


class ConnectionState(Enum):
    """连接状态"""
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    RECONNECTING = "reconnecting"
    ERROR = "error"


@dataclass
class SSEEvent:
    """SSE 事件"""
    event_type: str  # plain, image, record, file, end, complete, break, message_saved
    data: str
    streaming: bool = False
    chain_type: str = "normal"  # normal, reasoning
    raw: Optional[dict] = None


class AstrBotApiClient:
    """AstrBot HTTP API 客户端"""
    
    def __init__(
        self,
        server_url: str,
        username: str = "",
        password: str = "",
        token: Optional[str] = None,
        timeout: int = 30,
        on_state_change: Optional[Callable[[ConnectionState], None]] = None,
    ):
        self.server_url = server_url.rstrip('/')
        self.username = username
        self.password = password
        self.token = token
        self.timeout = timeout
        self.on_state_change = on_state_change
        
        self._state = ConnectionState.DISCONNECTED
        self._client: Optional[httpx.AsyncClient] = None
        
    @property
    def state(self) -> ConnectionState:
        return self._state
    
    @state.setter
    def state(self, value: ConnectionState):
        if self._state != value:
            self._state = value
            if self.on_state_change:
                self.on_state_change(value)
    
    @property
    def is_connected(self) -> bool:
        return self._state == ConnectionState.CONNECTED
    
    @property
    def api_base(self) -> str:
        return f"{self.server_url}/api"
    
    def _get_headers(self) -> dict:
        """获取请求头"""
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return headers
    
    async def _ensure_client(self) -> httpx.AsyncClient:
        """确保 HTTP 客户端已创建"""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(self.timeout, connect=10),
                follow_redirects=True,
            )
        return self._client
    
    async def _get_sse_client(self) -> httpx.AsyncClient:
        """获取用于 SSE 请求的客户端（更长超时）"""
        # SSE 流式请求需要更长的读取超时，因为 AI 可能需要较长时间思考
        # 禁用 HTTP/2 以避免流控制导致的延迟问题
        return httpx.AsyncClient(
            timeout=httpx.Timeout(
                connect=10.0,
                read=300.0,  # 5 分钟读取超时
                write=30.0,
                pool=10.0,
            ),
            follow_redirects=True,
            http2=False,  # 禁用 HTTP/2，避免流控制问题导致消息延迟
        )
    
    async def close(self):
        """关闭客户端"""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None
        self.state = ConnectionState.DISCONNECTED
    
    # ========== 认证相关 ==========
    
    def _hash_password(self, password: str) -> str:
        """对密码进行 MD5 哈希处理（AstrBot 服务器端存储的是 MD5 哈希）"""
        return hashlib.md5(password.encode('utf-8')).hexdigest()
    
    async def login(self, username: Optional[str] = None, password: Optional[str] = None) -> tuple[bool, str]:
        """
        登录获取 token
        
        Returns:
            (success, message_or_token)
        """
        self.state = ConnectionState.CONNECTING
        
        username = username or self.username
        password = password or self.password
        
        if not username or not password:
            self.state = ConnectionState.ERROR
            return False, "用户名或密码为空"
        
        # AstrBot 服务器存储的是 MD5 哈希密码，需要对明文密码进行哈希
        password_hash = self._hash_password(password)
        
        try:
            client = await self._ensure_client()
            
            response = await client.post(
                f"{self.api_base}/auth/login",
                json={"username": username, "password": password_hash},
                headers={"Content-Type": "application/json"},
            )
            
            if response.status_code != 200:
                self.state = ConnectionState.ERROR
                return False, f"HTTP {response.status_code}"
            
            data = response.json()
            
            if data.get("status") == "ok":
                self.token = data["data"]["token"]
                self.username = username
                self.password = password
                self.state = ConnectionState.CONNECTED
                
                change_pwd_hint = data["data"].get("change_pwd_hint", False)
                msg = "登录成功"
                if change_pwd_hint:
                    msg += "（建议修改默认密码）"
                
                return True, msg
            else:
                self.state = ConnectionState.ERROR
                return False, data.get("message", "登录失败")
                
        except httpx.ConnectError as e:
            self.state = ConnectionState.ERROR
            return False, f"连接失败: {e}"
        except httpx.TimeoutException:
            self.state = ConnectionState.ERROR
            return False, "连接超时"
        except Exception as e:
            self.state = ConnectionState.ERROR
            return False, f"登录异常: {e}"
    
    async def check_connection(self) -> bool:
        """检查连接状态"""
        if not self.token:
            return False
        
        try:
            client = await self._ensure_client()
            # 尝试获取会话列表来验证 token 是否有效
            response = await client.get(
                f"{self.api_base}/chat/sessions",
                headers=self._get_headers(),
            )
            
            if response.status_code == 200:
                data = response.json()
                if data.get("status") == "ok":
                    self.state = ConnectionState.CONNECTED
                    return True
            
            self.state = ConnectionState.DISCONNECTED
            return False
            
        except Exception:
            self.state = ConnectionState.DISCONNECTED
            return False
    
    # ========== 会话管理 ==========
    
    async def create_session(self, platform_id: str = "webchat") -> tuple[bool, Optional[str]]:
        """
        创建新会话
        
        Returns:
            (success, session_id or error_message)
        """
        try:
            client = await self._ensure_client()
            
            response = await client.get(
                f"{self.api_base}/chat/new_session",
                params={"platform_id": platform_id},
                headers=self._get_headers(),
            )
            
            if response.status_code != 200:
                return False, f"HTTP {response.status_code}"
            
            data = response.json()
            
            if data.get("status") == "ok":
                session_id = data["data"]["session_id"]
                return True, session_id
            else:
                return False, data.get("message", "创建会话失败")
                
        except Exception as e:
            return False, str(e)
    
    async def get_sessions(self, platform_id: Optional[str] = "webchat") -> tuple[bool, Any]:
        """
        获取会话列表
        
        Returns:
            (success, sessions_list or error_message)
        """
        try:
            client = await self._ensure_client()
            
            params = {}
            if platform_id:
                params["platform_id"] = platform_id
            
            response = await client.get(
                f"{self.api_base}/chat/sessions",
                params=params,
                headers=self._get_headers(),
            )
            
            if response.status_code != 200:
                return False, f"HTTP {response.status_code}"
            
            data = response.json()
            
            if data.get("status") == "ok":
                return True, data.get("data", [])
            else:
                return False, data.get("message", "获取会话列表失败")
                
        except Exception as e:
            return False, str(e)
    
    async def get_session_history(self, session_id: str) -> tuple[bool, Any]:
        """
        获取会话历史
        
        Returns:
            (success, history_data or error_message)
        """
        try:
            client = await self._ensure_client()
            
            response = await client.get(
                f"{self.api_base}/chat/get_session",
                params={"session_id": session_id},
                headers=self._get_headers(),
            )
            
            if response.status_code != 200:
                return False, f"HTTP {response.status_code}"
            
            data = response.json()
            
            if data.get("status") == "ok":
                return True, data.get("data", {})
            else:
                return False, data.get("message", "获取会话历史失败")
                
        except Exception as e:
            return False, str(e)
    
    async def delete_session(self, session_id: str) -> tuple[bool, str]:
        """删除会话"""
        try:
            client = await self._ensure_client()
            
            response = await client.get(
                f"{self.api_base}/chat/delete_session",
                params={"session_id": session_id},
                headers=self._get_headers(),
            )
            
            if response.status_code != 200:
                return False, f"HTTP {response.status_code}"
            
            data = response.json()
            
            if data.get("status") == "ok":
                return True, "删除成功"
            else:
                return False, data.get("message", "删除会话失败")
                
        except Exception as e:
            return False, str(e)
    
    # ========== 文件操作 ==========
    
    async def upload_file(self, file_path: str) -> tuple[bool, Optional[dict]]:
        """
        上传文件
        
        Returns:
            (success, {"attachment_id": str, "filename": str, "type": str} or None)
        """
        try:
            if not os.path.exists(file_path):
                return False, None
            
            client = await self._ensure_client()
            
            filename = os.path.basename(file_path)
            
            # 读取文件
            with open(file_path, 'rb') as f:
                file_content = f.read()
            
            # 根据扩展名确定 MIME 类型
            ext = os.path.splitext(filename)[1].lower()
            mime_types = {
                '.png': 'image/png',
                '.jpg': 'image/jpeg',
                '.jpeg': 'image/jpeg',
                '.gif': 'image/gif',
                '.webp': 'image/webp',
                '.bmp': 'image/bmp',
                '.wav': 'audio/wav',
                '.mp3': 'audio/mpeg',
                '.ogg': 'audio/ogg',
            }
            content_type = mime_types.get(ext, 'application/octet-stream')
            
            # 构建 multipart 表单
            files = {
                'file': (filename, file_content, content_type)
            }
            
            # 不使用 JSON 头，使用 multipart
            headers = {}
            if self.token:
                headers["Authorization"] = f"Bearer {self.token}"
            
            response = await client.post(
                f"{self.api_base}/chat/post_file",
                files=files,
                headers=headers,
            )
            
            if response.status_code != 200:
                return False, None
            
            data = response.json()
            
            if data.get("status") == "ok":
                return True, data.get("data")
            else:
                return False, None
                
        except Exception as e:
            print(f"上传文件失败: {e}")
            return False, None
    
    async def download_file(self, filename: str, save_path: str) -> bool:
        """下载文件"""
        try:
            client = await self._ensure_client()
            
            response = await client.get(
                f"{self.api_base}/chat/get_file",
                params={"filename": filename},
                headers=self._get_headers(),
            )
            
            if response.status_code != 200:
                return False
            
            with open(save_path, 'wb') as f:
                f.write(response.content)
            
            return True
            
        except Exception as e:
            print(f"下载文件失败: {e}")
            return False
    
    async def get_attachment(self, attachment_id: str, save_path: str) -> bool:
        """下载附件"""
        try:
            client = await self._ensure_client()
            
            response = await client.get(
                f"{self.api_base}/chat/get_attachment",
                params={"attachment_id": attachment_id},
                headers=self._get_headers(),
            )
            
            if response.status_code != 200:
                return False
            
            with open(save_path, 'wb') as f:
                f.write(response.content)
            
            return True
            
        except Exception as e:
            print(f"下载附件失败: {e}")
            return False
    
    # ========== 消息发送 ==========
    
    async def send_message(
        self,
        session_id: str,
        message: str | list,
        selected_provider: Optional[str] = None,
        selected_model: Optional[str] = None,
        enable_streaming: bool = True,
    ) -> AsyncGenerator[SSEEvent, None]:
        """
        发送消息并接收 SSE 流式响应
        
        Args:
            session_id: 会话 ID
            message: 消息内容，可以是字符串或消息段列表
            selected_provider: 选择的 LLM 提供者
            selected_model: 选择的模型
            enable_streaming: 是否启用流式响应
            
        Yields:
            SSEEvent 对象
        """
        # 构建请求体
        body = {
            "session_id": session_id,
            "message": message,
            "enable_streaming": enable_streaming,
        }
        
        if selected_provider:
            body["selected_provider"] = selected_provider
        if selected_model:
            body["selected_model"] = selected_model
        
        # 强制使用新的客户端实例，不复用连接，避免 qasync 环境下的缓冲/唤醒问题
        # 这是为了解决 GUI 界面中消息延迟显示（需要下一次请求触发）的顽固 Bug
        
        # 创建全新的一次性客户端
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(connect=10.0, read=300.0, write=30.0, pool=10.0),
            follow_redirects=True,
            http2=False, # 禁用 HTTP2
        ) as client:
            try:
                headers = self._get_headers()
                headers["Accept-Encoding"] = "identity"
                headers["Cache-Control"] = "no-cache"
                headers["Connection"] = "close" # 明确告知服务器关闭连接
                
                async with client.stream(
                    "POST",
                    f"{self.api_base}/chat/send",
                    json=body,
                    headers=headers,
                ) as response:
                    if response.status_code != 200:
                        yield SSEEvent(
                            event_type="error",
                            data=f"HTTP {response.status_code}",
                        )
                        return
                    
                    # 手动处理 SSE 流
                    async for line in response.aiter_lines():
                        if not line:
                            continue
                            
                        # 移除可能的 BOM
                        if line.startswith('\ufeff'):
                            line = line[1:]
                            
                        # 只处理 data: 开头的行
                        if line.startswith('data: '):
                            data_str = line[6:]  # 去掉 'data: ' 前缀
                            
                            try:
                                event_data = json.loads(data_str)
                                event_type = event_data.get("type", "plain")
                                
                                event = SSEEvent(
                                    event_type=event_type,
                                    data=event_data.get("data", ""),
                                    streaming=event_data.get("streaming", False),
                                    chain_type=event_data.get("chain_type", "normal"),
                                    raw=event_data,
                                )
                                yield event
                                
                                # 让出控制权 - 关键！
                                await asyncio.sleep(0)
                                
                                if event.event_type == "end":
                                    return
                            except json.JSONDecodeError:
                                continue
                        
            except httpx.ConnectError as e:
                yield SSEEvent(event_type="error", data=f"连接失败: {e}")
            except httpx.TimeoutException as e:
                yield SSEEvent(event_type="error", data=f"请求超时（服务器响应时间过长）: {e}")
            except GeneratorExit:
                pass
            except Exception as e:
                yield SSEEvent(event_type="error", data=f"发送消息异常: {e}")
    
    async def send_text_message(
        self,
        session_id: str,
        text: str,
        **kwargs,
    ) -> AsyncGenerator[SSEEvent, None]:
        """发送纯文本消息"""
        async for event in self.send_message(session_id, text, **kwargs):
            yield event
    
    async def send_image_message(
        self,
        session_id: str,
        image_path: str,
        text: str = "",
        **kwargs,
    ) -> AsyncGenerator[SSEEvent, None]:
        """发送图片消息"""
        # 先上传图片
        success, result = await self.upload_file(image_path)
        
        if not success or not result:
            yield SSEEvent(event_type="error", data="图片上传失败")
            return
        
        # 构建消息段
        message_parts = []
        
        if text:
            message_parts.append({"type": "plain", "text": text})
        
        message_parts.append({
            "type": "image",
            "attachment_id": result["attachment_id"],
        })
        
        async for event in self.send_message(session_id, message_parts, **kwargs):
            yield event
    
    async def send_voice_message(
        self,
        session_id: str,
        audio_path: str,
        **kwargs,
    ) -> AsyncGenerator[SSEEvent, None]:
        """发送语音消息"""
        # 先上传音频
        success, result = await self.upload_file(audio_path)
        
        if not success or not result:
            yield SSEEvent(event_type="error", data="音频上传失败")
            return
        
        # 构建消息段
        message_parts = [{
            "type": "record",
            "attachment_id": result["attachment_id"],
        }]
        
        async for event in self.send_message(session_id, message_parts, **kwargs):
            yield event
    
    async def send_file_message(
        self,
        session_id: str,
        file_path: str,
        text: str = "",
        **kwargs,
    ) -> AsyncGenerator[SSEEvent, None]:
        """发送文件消息"""
        # 先上传文件
        success, result = await self.upload_file(file_path)
        
        if not success or not result:
            yield SSEEvent(event_type="error", data="文件上传失败")
            return
        
        # 构建消息段
        message_parts = []
        
        if text:
            message_parts.append({"type": "plain", "text": text})
        
        message_parts.append({
            "type": "file",
            "attachment_id": result["attachment_id"],
        })
        
        async for event in self.send_message(session_id, message_parts, **kwargs):
            yield event