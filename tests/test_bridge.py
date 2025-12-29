"""
消息桥接器单元测试

测试 MessageBridge 的功能：
- 消息数据类
- SSE 事件处理
- 连接状态管理
- 函数结果提取
"""

import json
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# 确保可以导入 desktop_client
sys.path.insert(0, str(Path(__file__).parent.parent))

from desktop_client.bridge import (
    InputMessage,
    OutputMessage,
    MessageBridge,
)
from desktop_client.api_client import (
    ConnectionState,
    SSEEvent,
)
from desktop_client.config import ClientConfig


class TestInputMessage:
    """InputMessage 测试"""

    @pytest.mark.unit
    def test_creation(self):
        """测试创建输入消息"""
        msg = InputMessage(
            msg_type="text",
            content="Hello, world!",
            session_id="session_123",
        )

        assert msg.msg_type == "text"
        assert msg.content == "Hello, world!"
        assert msg.session_id == "session_123"
        assert msg.timestamp > 0
        assert isinstance(msg.metadata, dict)

    @pytest.mark.unit
    def test_creation_with_metadata(self):
        """测试创建带元数据的输入消息"""
        msg = InputMessage(
            msg_type="image",
            content="/path/to/image.png",
            session_id="session_456",
            metadata={"text": "这是一张图片"},
        )

        assert msg.msg_type == "image"
        assert msg.metadata["text"] == "这是一张图片"

    @pytest.mark.unit
    def test_screenshot_type(self):
        """测试截图类型消息"""
        msg = InputMessage(
            msg_type="screenshot",
            content="/tmp/screenshot.png",
            session_id="session_789",
            metadata={"text": "请分析这个截图"},
        )

        assert msg.msg_type == "screenshot"
        assert "screenshot" in msg.content

    @pytest.mark.unit
    def test_voice_type(self):
        """测试语音类型消息"""
        msg = InputMessage(
            msg_type="voice",
            content="/tmp/audio.wav",
            session_id="session_voice",
        )

        assert msg.msg_type == "voice"


class TestOutputMessage:
    """OutputMessage 测试"""

    @pytest.mark.unit
    def test_creation(self):
        """测试创建输出消息"""
        msg = OutputMessage(
            msg_type="text",
            content="AI 回复内容",
            session_id="session_123",
        )

        assert msg.msg_type == "text"
        assert msg.content == "AI 回复内容"
        assert msg.session_id == "session_123"
        assert msg.streaming is False
        assert msg.is_complete is False
        assert isinstance(msg.metadata, dict)

    @pytest.mark.unit
    def test_streaming_message(self):
        """测试流式消息"""
        msg = OutputMessage(
            msg_type="text",
            content="流式",
            session_id="session_123",
            streaming=True,
        )

        assert msg.streaming is True
        assert msg.is_complete is False

    @pytest.mark.unit
    def test_complete_message(self):
        """测试完成消息"""
        msg = OutputMessage(
            msg_type="end",
            content="",
            session_id="session_123",
            is_complete=True,
        )

        assert msg.msg_type == "end"
        assert msg.is_complete is True

    @pytest.mark.unit
    def test_error_message(self):
        """测试错误消息"""
        msg = OutputMessage(
            msg_type="error",
            content="连接失败",
            session_id="session_123",
        )

        assert msg.msg_type == "error"
        assert msg.content == "连接失败"

    @pytest.mark.unit
    def test_image_message(self):
        """测试图片消息"""
        msg = OutputMessage(
            msg_type="image",
            content="image_123.png",
            session_id="session_123",
            metadata={"filename": "image_123.png"},
        )

        assert msg.msg_type == "image"
        assert msg.metadata["filename"] == "image_123.png"

    @pytest.mark.unit
    def test_status_message(self):
        """测试状态消息"""
        msg = OutputMessage(
            msg_type="status",
            content="connected",
            session_id="",
            metadata={"state": "connected"},
        )

        assert msg.msg_type == "status"
        assert msg.metadata["state"] == "connected"


class TestMessageBridgeInit:
    """MessageBridge 初始化测试"""

    @pytest.mark.unit
    def test_initialization(self, mock_qt_app, sample_config: ClientConfig):
        """测试初始化"""
        with patch("desktop_client.bridge.AstrBotApiClient"):
            bridge = MessageBridge(sample_config)

            assert bridge.config == sample_config
            assert bridge.api_client is not None

    @pytest.mark.unit
    def test_connection_state_property(self, mock_qt_app, sample_config: ClientConfig):
        """测试连接状态属性"""
        with patch("desktop_client.bridge.AstrBotApiClient") as mock_client_cls:
            mock_client = MagicMock()
            mock_client.state = ConnectionState.DISCONNECTED
            mock_client_cls.return_value = mock_client

            bridge = MessageBridge(sample_config)

            assert bridge.connection_state == ConnectionState.DISCONNECTED

    @pytest.mark.unit
    def test_is_connected_property(self, mock_qt_app, sample_config: ClientConfig):
        """测试是否已连接属性"""
        with patch("desktop_client.bridge.AstrBotApiClient") as mock_client_cls:
            mock_client = MagicMock()
            mock_client.is_connected = False
            mock_client_cls.return_value = mock_client

            bridge = MessageBridge(sample_config)

            assert bridge.is_connected is False

            mock_client.is_connected = True
            assert bridge.is_connected is True


class TestMessageBridgeFunctionResultExtraction:
    """消息桥接器函数结果提取测试"""

    @pytest.mark.unit
    def test_extract_function_result_normal_text(
        self, mock_qt_app, sample_config: ClientConfig
    ):
        """测试提取普通文本（不是函数结果）"""
        with patch("desktop_client.bridge.AstrBotApiClient"):
            bridge = MessageBridge(sample_config)

            result = bridge._extract_function_result("普通文本消息")

            assert result == "普通文本消息"

    @pytest.mark.unit
    def test_extract_function_result_json_with_result(
        self, mock_qt_app, sample_config: ClientConfig
    ):
        """测试提取 JSON 函数调用结果"""
        with patch("desktop_client.bridge.AstrBotApiClient"):
            bridge = MessageBridge(sample_config)

            json_content = json.dumps(
                {"id": "call_123", "ts": 1234567890, "result": "这是函数调用的结果"}
            )

            result = bridge._extract_function_result(json_content)

            assert result == "这是函数调用的结果"

    @pytest.mark.unit
    def test_extract_function_result_json_without_result(
        self, mock_qt_app, sample_config: ClientConfig
    ):
        """测试提取没有 result 字段的 JSON"""
        with patch("desktop_client.bridge.AstrBotApiClient"):
            bridge = MessageBridge(sample_config)

            json_content = json.dumps({"type": "message", "data": "some data"})

            result = bridge._extract_function_result(json_content)

            # 应该返回原始 JSON 字符串
            assert result == json_content

    @pytest.mark.unit
    def test_extract_function_result_invalid_json(
        self, mock_qt_app, sample_config: ClientConfig
    ):
        """测试提取无效 JSON"""
        with patch("desktop_client.bridge.AstrBotApiClient"):
            bridge = MessageBridge(sample_config)

            invalid_json = "{ invalid json }"

            result = bridge._extract_function_result(invalid_json)

            # 应该返回原始内容
            assert result == invalid_json

    @pytest.mark.unit
    def test_extract_function_result_empty(
        self, mock_qt_app, sample_config: ClientConfig
    ):
        """测试提取空内容"""
        with patch("desktop_client.bridge.AstrBotApiClient"):
            bridge = MessageBridge(sample_config)

            result = bridge._extract_function_result("")

            assert result == ""

    @pytest.mark.unit
    def test_extract_function_result_none(
        self, mock_qt_app, sample_config: ClientConfig
    ):
        """测试提取 None（边界情况，实际代码会处理）"""
        with patch("desktop_client.bridge.AstrBotApiClient"):
            bridge = MessageBridge(sample_config)

            # 实际代码中 content 参数类型是 str，这里测试空字符串作为替代
            result = bridge._extract_function_result("")

            assert result == ""

    @pytest.mark.unit
    def test_extract_function_result_whitespace(
        self, mock_qt_app, sample_config: ClientConfig
    ):
        """测试提取带空白的 JSON"""
        with patch("desktop_client.bridge.AstrBotApiClient"):
            bridge = MessageBridge(sample_config)

            json_content = """
            {
                "id": "call_456",
                "result": "带空白的结果"
            }
            """

            result = bridge._extract_function_result(json_content)

            assert result == "带空白的结果"


class TestMessageBridgeSSEEventHandling:
    """消息桥接器 SSE 事件处理测试"""

    @pytest.mark.unit
    def test_handle_plain_text_event(self, mock_qt_app, sample_config: ClientConfig):
        """测试处理纯文本事件"""
        with patch("desktop_client.bridge.AstrBotApiClient"):
            bridge = MessageBridge(sample_config)

            # 收集发射的信号
            received_messages = []
            bridge.message_received.connect(lambda msg: received_messages.append(msg))

            event = SSEEvent(
                event_type="plain",
                data="Hello",
                streaming=False,
                chain_type="normal",
            )

            bridge._handle_sse_event(event, "session_123")

            assert len(received_messages) == 1
            assert received_messages[0].msg_type == "text"
            assert received_messages[0].content == "Hello"

    @pytest.mark.unit
    def test_handle_streaming_event(self, mock_qt_app, sample_config: ClientConfig):
        """测试处理流式事件"""
        with patch("desktop_client.bridge.AstrBotApiClient"):
            bridge = MessageBridge(sample_config)

            received_messages = []
            bridge.message_received.connect(lambda msg: received_messages.append(msg))

            event = SSEEvent(
                event_type="plain",
                data="流式",
                streaming=True,
            )

            bridge._handle_sse_event(event, "session_123")

            assert len(received_messages) == 1
            assert received_messages[0].streaming is True

    @pytest.mark.unit
    def test_handle_reasoning_event_skipped(
        self, mock_qt_app, sample_config: ClientConfig
    ):
        """测试跳过思维链事件"""
        with patch("desktop_client.bridge.AstrBotApiClient"):
            bridge = MessageBridge(sample_config)

            received_messages = []
            bridge.message_received.connect(lambda msg: received_messages.append(msg))

            event = SSEEvent(
                event_type="plain",
                data="这是思维链内容",
                streaming=False,
                chain_type="reasoning",  # 思维链类型
            )

            bridge._handle_sse_event(event, "session_123")

            # 思维链事件应该被跳过
            assert len(received_messages) == 0

    @pytest.mark.unit
    def test_handle_empty_non_streaming_skipped(
        self, mock_qt_app, sample_config: ClientConfig
    ):
        """测试跳过空的非流式消息"""
        with patch("desktop_client.bridge.AstrBotApiClient"):
            bridge = MessageBridge(sample_config)

            received_messages = []
            bridge.message_received.connect(lambda msg: received_messages.append(msg))

            event = SSEEvent(
                event_type="plain",
                data="",  # 空内容
                streaming=False,
            )

            bridge._handle_sse_event(event, "session_123")

            # 空消息应该被跳过
            assert len(received_messages) == 0

    @pytest.mark.unit
    def test_handle_image_event(self, mock_qt_app, sample_config: ClientConfig):
        """测试处理图片事件"""
        with patch("desktop_client.bridge.AstrBotApiClient"):
            bridge = MessageBridge(sample_config)

            received_messages = []
            bridge.message_received.connect(lambda msg: received_messages.append(msg))

            event = SSEEvent(
                event_type="image",
                data="[IMAGE]image_123.png",
            )

            bridge._handle_sse_event(event, "session_123")

            assert len(received_messages) == 1
            assert received_messages[0].msg_type == "image"
            assert received_messages[0].content == "image_123.png"

    @pytest.mark.unit
    def test_handle_record_event(self, mock_qt_app, sample_config: ClientConfig):
        """测试处理语音事件"""
        with patch("desktop_client.bridge.AstrBotApiClient"):
            bridge = MessageBridge(sample_config)

            received_messages = []
            bridge.message_received.connect(lambda msg: received_messages.append(msg))

            event = SSEEvent(
                event_type="record",
                data="[RECORD]audio_123.wav",
            )

            bridge._handle_sse_event(event, "session_123")

            assert len(received_messages) == 1
            assert received_messages[0].msg_type == "voice"
            assert received_messages[0].content == "audio_123.wav"

    @pytest.mark.unit
    def test_handle_file_event(self, mock_qt_app, sample_config: ClientConfig):
        """测试处理文件事件"""
        with patch("desktop_client.bridge.AstrBotApiClient"):
            bridge = MessageBridge(sample_config)

            received_messages = []
            bridge.message_received.connect(lambda msg: received_messages.append(msg))

            event = SSEEvent(
                event_type="file",
                data="[FILE]document.pdf",
            )

            bridge._handle_sse_event(event, "session_123")

            assert len(received_messages) == 1
            assert received_messages[0].msg_type == "file"
            assert received_messages[0].content == "document.pdf"

    @pytest.mark.unit
    def test_handle_end_event(self, mock_qt_app, sample_config: ClientConfig):
        """测试处理结束事件"""
        with patch("desktop_client.bridge.AstrBotApiClient"):
            bridge = MessageBridge(sample_config)

            received_messages = []
            bridge.message_received.connect(lambda msg: received_messages.append(msg))

            event = SSEEvent(
                event_type="end",
                data="",
            )

            bridge._handle_sse_event(event, "session_123")

            assert len(received_messages) == 1
            assert received_messages[0].msg_type == "end"
            assert received_messages[0].is_complete is True

    @pytest.mark.unit
    def test_handle_break_event(self, mock_qt_app, sample_config: ClientConfig):
        """测试处理中断事件"""
        with patch("desktop_client.bridge.AstrBotApiClient"):
            bridge = MessageBridge(sample_config)

            received_messages = []
            bridge.message_received.connect(lambda msg: received_messages.append(msg))

            event = SSEEvent(
                event_type="break",
                data="",
            )

            bridge._handle_sse_event(event, "session_123")

            assert len(received_messages) == 1
            assert received_messages[0].msg_type == "end"
            assert received_messages[0].is_complete is False
            assert received_messages[0].metadata.get("break") is True

    @pytest.mark.unit
    def test_handle_error_event(self, mock_qt_app, sample_config: ClientConfig):
        """测试处理错误事件"""
        with patch("desktop_client.bridge.AstrBotApiClient"):
            bridge = MessageBridge(sample_config)

            received_messages = []
            bridge.message_received.connect(lambda msg: received_messages.append(msg))

            event = SSEEvent(
                event_type="error",
                data="服务器错误",
            )

            bridge._handle_sse_event(event, "session_123")

            assert len(received_messages) == 1
            assert received_messages[0].msg_type == "error"
            assert received_messages[0].content == "服务器错误"

    @pytest.mark.unit
    def test_handle_message_saved_event(self, mock_qt_app, sample_config: ClientConfig):
        """测试处理消息保存事件"""
        with patch("desktop_client.bridge.AstrBotApiClient"):
            bridge = MessageBridge(sample_config)

            received_messages = []
            bridge.message_received.connect(lambda msg: received_messages.append(msg))

            event = SSEEvent(
                event_type="message_saved",
                data="",
                raw={
                    "data": {
                        "id": "msg_123",
                        "created_at": "2024-01-01T00:00:00Z",
                    }
                },
            )

            bridge._handle_sse_event(event, "session_123")

            assert len(received_messages) == 1
            assert received_messages[0].msg_type == "saved"
            assert received_messages[0].metadata["message_id"] == "msg_123"


class TestMessageBridgeServerConfig:
    """消息桥接器服务器配置测试"""

    @pytest.mark.unit
    def test_update_server_config(self, mock_qt_app, sample_config: ClientConfig):
        """测试更新服务器配置"""
        with patch("desktop_client.bridge.AstrBotApiClient") as mock_client_cls:
            mock_client = MagicMock()
            mock_client.state = ConnectionState.DISCONNECTED
            mock_client_cls.return_value = mock_client

            bridge = MessageBridge(sample_config)

            bridge.update_server_config(
                url="http://new-server:9999",
                username="new_user",
                password="new_pass",
            )

            assert bridge.config.server.url == "http://new-server:9999"
            assert bridge.config.server.username == "new_user"
            assert bridge.config.server.password == "new_pass"
            assert bridge.config.server.token is None  # Token 应该被清除
            assert mock_client.token is None

    @pytest.mark.unit
    def test_update_server_config_partial(
        self, mock_qt_app, sample_config: ClientConfig
    ):
        """测试部分更新服务器配置"""
        with patch("desktop_client.bridge.AstrBotApiClient") as mock_client_cls:
            mock_client = MagicMock()
            mock_client_cls.return_value = mock_client

            bridge = MessageBridge(sample_config)
            original_username = bridge.config.server.username

            bridge.update_server_config(url="http://only-url:8080")

            assert bridge.config.server.url == "http://only-url:8080"
            # 其他字段不变
            assert bridge.config.server.username == original_username


class TestMessageBridgeAsync:
    """消息桥接器异步方法测试"""

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_connect_server_with_token(
        self, mock_qt_app, sample_config: ClientConfig
    ):
        """测试使用 Token 连接服务器"""
        with patch("desktop_client.bridge.AstrBotApiClient") as mock_client_cls:
            mock_client = MagicMock()
            mock_client.token = "valid_token"
            mock_client.check_connection = AsyncMock(return_value=True)
            mock_client.create_session = AsyncMock(return_value=(True, "session_new"))
            mock_client.start_health_check = AsyncMock()
            mock_client_cls.return_value = mock_client

            # 清除现有 session_id 以测试创建新会话
            sample_config.session_id = None

            bridge = MessageBridge(sample_config)
            success, message = await bridge.connect_server()

            assert success is True
            assert "Token" in message
            mock_client.check_connection.assert_called_once()

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_connect_server_login(self, mock_qt_app, sample_config: ClientConfig):
        """测试登录连接服务器"""
        with patch("desktop_client.bridge.AstrBotApiClient") as mock_client_cls:
            mock_client = MagicMock()
            mock_client.token = None
            mock_client.login = AsyncMock(return_value=(True, "登录成功"))
            mock_client.create_session = AsyncMock(return_value=(True, "session_new"))
            mock_client_cls.return_value = mock_client

            sample_config.session_id = None

            bridge = MessageBridge(sample_config)

            # 模拟登录后设置 token
            async def mock_login():
                mock_client.token = "new_token"
                return (True, "登录成功")

            mock_client.login = mock_login

            success, message = await bridge.connect_server()

            assert success is True

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_disconnect_server(self, mock_qt_app, sample_config: ClientConfig):
        """测试断开服务器连接"""
        with patch("desktop_client.bridge.AstrBotApiClient") as mock_client_cls:
            mock_client = MagicMock()
            mock_client.close = AsyncMock()
            mock_client_cls.return_value = mock_client

            bridge = MessageBridge(sample_config)
            await bridge.disconnect_server()

            mock_client.close.assert_called_once()

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_send_input_not_connected(
        self, mock_qt_app, sample_config: ClientConfig
    ):
        """测试未连接时发送消息"""
        with patch("desktop_client.bridge.AstrBotApiClient") as mock_client_cls:
            mock_client = MagicMock()
            mock_client.is_connected = False
            mock_client_cls.return_value = mock_client

            bridge = MessageBridge(sample_config)

            received_messages = []
            bridge.message_received.connect(lambda msg: received_messages.append(msg))

            msg = InputMessage(
                msg_type="text",
                content="test",
                session_id="session_123",
            )

            await bridge.send_input(msg)

            assert len(received_messages) == 1
            assert received_messages[0].msg_type == "error"
            assert "未连接" in received_messages[0].content


class TestSSEEvent:
    """SSEEvent 数据类测试"""

    @pytest.mark.unit
    def test_default_values(self):
        """测试默认值"""
        event = SSEEvent(event_type="plain", data="test")

        assert event.event_type == "plain"
        assert event.data == "test"
        assert event.streaming is False
        assert event.chain_type == "normal"
        assert event.raw is None

    @pytest.mark.unit
    def test_with_raw_data(self):
        """测试带原始数据"""
        raw = {"type": "plain", "data": "test", "extra": "info"}
        event = SSEEvent(event_type="plain", data="test", raw=raw)

        assert event.raw == raw
        assert event.raw is not None
        assert event.raw["extra"] == "info"


class TestConnectionState:
    """ConnectionState 枚举测试"""

    @pytest.mark.unit
    def test_state_values(self):
        """测试状态值"""
        assert ConnectionState.DISCONNECTED.value == "disconnected"
        assert ConnectionState.CONNECTING.value == "connecting"
        assert ConnectionState.CONNECTED.value == "connected"
        assert ConnectionState.RECONNECTING.value == "reconnecting"
        assert ConnectionState.ERROR.value == "error"
