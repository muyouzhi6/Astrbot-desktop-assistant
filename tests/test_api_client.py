import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest
import httpx

from desktop_client.api_client import AstrBotApiClient


class _FakeSseResponse:
    def __init__(self, status_code: int = 200, lines: list[str] | None = None):
        self.status_code = status_code
        self._lines = lines or []

    async def aiter_lines(self):
        for line in self._lines:
            yield line


class _FakeSseContext:
    def __init__(self, response: _FakeSseResponse):
        self._response = response

    async def __aenter__(self):
        return self._response

    async def __aexit__(self, exc_type, exc, tb):
        return False


class TestAstrBotApiClientOpenApiMode:
    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_legacy_login_sends_plain_password(self):
        submitted = []

        def respond(request):
            submitted.append(json.loads(request.content))
            return httpx.Response(
                200, json={"status": "ok", "data": {"token": "fixture"}}
            )

        client = AstrBotApiClient(
            "http://localhost:6185",
            username="alice",
            password="fixture-password",
            auth_mode="legacy",
        )
        client._client = httpx.AsyncClient(
            transport=httpx.MockTransport(respond)
        )
        try:
            success, _ = await client.login()
            assert success
            assert submitted == [
                {"username": "alice", "password": "fixture-password"}
            ]
        finally:
            await client.close()

    @pytest.mark.unit
    def test_openapi_headers_prefer_api_key(self):
        client = AstrBotApiClient(
            "http://localhost:6185",
            username="alice",
            api_key="abk_test",
            token="legacy_token",
        )

        headers = client._get_headers()

        assert client.uses_openapi is True
        assert headers["Authorization"] == "Bearer abk_test"

    @pytest.mark.unit
    def test_legacy_headers_use_token_when_forced(self):
        client = AstrBotApiClient(
            "http://localhost:6185",
            api_key="abk_test",
            auth_mode="legacy",
            token="legacy_token",
        )

        headers = client._get_headers()

        assert client.uses_openapi is False
        assert headers["Authorization"] == "Bearer legacy_token"

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_openapi_websocket_uses_api_key_token(self):
        client = AstrBotApiClient(
            "http://localhost:6185",
            username="alice",
            api_key="abk_test",
        )
        ws_client = MagicMock()
        ws_client.start = AsyncMock()

        import desktop_client.api_client as api_module

        original_ws_client = api_module.WebSocketClient
        ws_client_factory = MagicMock(return_value=ws_client)
        try:
            api_module.WebSocketClient = ws_client_factory
            await client.start_websocket("desktop_session")
        finally:
            api_module.WebSocketClient = original_ws_client

        ws_client_factory.assert_called_once()
        _, kwargs = ws_client_factory.call_args
        assert kwargs["token"] == "abk_test"
        ws_client.start.assert_awaited_once()

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_openapi_check_connection_uses_username(self):
        client = AstrBotApiClient(
            "http://localhost:6185",
            username="alice",
            api_key="abk_test",
        )
        response = MagicMock(status_code=200)
        response.json.return_value = {"status": "ok", "data": {"sessions": []}}
        http_client = MagicMock()
        http_client.get = AsyncMock(return_value=response)
        client._ensure_client = AsyncMock(return_value=http_client)

        ok = await client.check_connection()

        assert ok is True
        assert client.state.name == "CONNECTED"
        http_client.get.assert_awaited_once()
        _, kwargs = http_client.get.call_args
        assert kwargs["params"] == {"username": "alice", "page": 1, "page_size": 1}
        assert kwargs["headers"]["Authorization"] == "Bearer abk_test"

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_openapi_login_reports_scope_error_as_api_key_failure(self):
        client = AstrBotApiClient(
            "http://localhost:6185",
            username="alice",
            api_key="abk_test",
        )
        response = MagicMock(status_code=403)
        response.json.return_value = {"message": "Insufficient API key scope"}
        http_client = MagicMock()
        http_client.get = AsyncMock(return_value=response)
        client._ensure_client = AsyncMock(return_value=http_client)

        success, message = await client.login()

        assert success is False
        assert client.state.name == "ERROR"
        assert message == "OpenAPI API Key 验证失败: Insufficient API key scope"

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_openapi_login_reports_timeout_as_connection_check_failure(self):
        client = AstrBotApiClient(
            "http://localhost:6185",
            username="alice",
            api_key="abk_test",
        )
        http_client = MagicMock()
        http_client.get = AsyncMock(side_effect=httpx.ReadTimeout("slow"))
        client._ensure_client = AsyncMock(return_value=http_client)

        success, message = await client.login()

        assert success is False
        assert client.state.name == "ERROR"
        assert message.startswith("OpenAPI 连接检测失败:")
        assert "API Key 验证失败" not in message

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_openapi_create_session_is_local_uuid(self):
        client = AstrBotApiClient(
            "http://localhost:6185",
            username="alice",
            api_key="abk_test",
        )

        success, session_id = await client.create_session()

        assert success is True
        assert session_id.startswith("desktop_")

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_openapi_upload_file_hits_v1_endpoint(self, tmp_path: Path):
        file_path = tmp_path / "demo.png"
        file_path.write_bytes(b"fake image bytes")

        client = AstrBotApiClient(
            "http://localhost:6185",
            username="alice",
            api_key="abk_test",
        )
        response = MagicMock(status_code=200)
        response.json.return_value = {
            "status": "ok",
            "data": {"attachment_id": "att_123", "filename": "demo.png"},
        }
        http_client = MagicMock()
        http_client.post = AsyncMock(return_value=response)
        client._ensure_client = AsyncMock(return_value=http_client)

        success, payload = await client.upload_file(str(file_path))

        assert success is True
        assert payload["attachment_id"] == "att_123"
        http_client.post.assert_awaited_once()
        args, kwargs = http_client.post.call_args
        assert args[0] == "http://localhost:6185/api/v1/file"
        assert kwargs["headers"]["Authorization"] == "Bearer abk_test"
        assert kwargs["files"]["file"][0] == "demo.png"

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_openapi_upload_file_accepts_id_alias(self, tmp_path: Path):
        file_path = tmp_path / "demo.webp"
        file_path.write_bytes(b"fake image bytes")

        client = AstrBotApiClient(
            "http://localhost:6185",
            username="alice",
            api_key="abk_test",
        )
        response = MagicMock(status_code=201)
        response.json.return_value = {
            "status": "ok",
            "data": {"id": "att_alias", "filename": "demo.webp"},
        }
        http_client = MagicMock()
        http_client.post = AsyncMock(return_value=response)
        client._ensure_client = AsyncMock(return_value=http_client)

        success, payload = await client.upload_file(str(file_path))

        assert success is True
        assert payload["attachment_id"] == "att_alias"

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_send_image_message_uses_openapi_attachment_id_alias(
        self, tmp_path: Path
    ):
        file_path = tmp_path / "shot.png"
        file_path.write_bytes(b"fake image bytes")

        client = AstrBotApiClient(
            "http://localhost:6185",
            username="alice",
            api_key="abk_test",
        )
        client.upload_file = AsyncMock(
            return_value=(True, {"id": "att_alias", "attachment_id": "att_alias"})
        )
        response = _FakeSseResponse(
            200,
            ['data: {"type":"end","data":"","streaming":false}'],
        )
        http_client = MagicMock()
        http_client.stream = MagicMock(return_value=_FakeSseContext(response))
        http_client.aclose = AsyncMock()
        client._create_sse_client = MagicMock(return_value=http_client)

        events = []
        async for event in client.send_image_message("session_001", str(file_path), "看图"):
            events.append(event)

        assert [event.event_type for event in events] == ["end"]
        _, kwargs = http_client.stream.call_args
        assert kwargs["json"]["message"] == [
            {"type": "plain", "text": "看图"},
            {"type": "image", "attachment_id": "att_alias"},
        ]

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_openapi_download_file_uses_v1_attachment_endpoint(self, tmp_path: Path):
        save_path = tmp_path / "downloaded.jpg"
        client = AstrBotApiClient(
            "http://localhost:6185",
            username="alice",
            api_key="abk_test",
        )
        response = MagicMock(status_code=200)
        response.content = b"image-bytes"
        http_client = MagicMock()
        http_client.get = AsyncMock(return_value=response)
        client._ensure_client = AsyncMock(return_value=http_client)

        success = await client.download_file("attachment_123", str(save_path))

        assert success is True
        assert save_path.read_bytes() == b"image-bytes"
        http_client.get.assert_awaited_once()
        args, kwargs = http_client.get.call_args
        assert args[0] == "http://localhost:6185/api/v1/file"
        assert kwargs["params"] == {"attachment_id": "attachment_123"}

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_openapi_send_message_hits_v1_chat_and_injects_username(self):
        client = AstrBotApiClient(
            "http://localhost:6185",
            username="alice",
            api_key="abk_test",
        )
        response = _FakeSseResponse(
            200,
            [
                'data: {"type":"plain","data":{"text":"hello"},"streaming":true}',
                'data: {"type":"end","data":"","streaming":false}',
            ],
        )
        http_client = MagicMock()
        http_client.stream = MagicMock(return_value=_FakeSseContext(response))
        http_client.aclose = AsyncMock()
        client._create_sse_client = MagicMock(return_value=http_client)

        events = []
        async for event in client.send_message("session_001", "hi"):
            events.append(event)

        assert [event.event_type for event in events] == ["plain", "end"]
        assert json.loads(events[0].data) == {"text": "hello"}
        args, kwargs = http_client.stream.call_args
        assert args == ("POST", "http://localhost:6185/api/v1/chat")
        assert kwargs["headers"]["Authorization"] == "Bearer abk_test"
        assert kwargs["json"]["username"] == "alice"
        assert kwargs["json"]["session_id"] == "session_001"
        http_client.aclose.assert_awaited_once()

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_openapi_send_message_omits_blank_session_id(self):
        client = AstrBotApiClient(
            "http://localhost:6185",
            username="alice",
            api_key="abk_test",
        )
        response = _FakeSseResponse(200, ['data: {"type":"end","data":"","streaming":false}'])
        http_client = MagicMock()
        http_client.stream = MagicMock(return_value=_FakeSseContext(response))
        http_client.aclose = AsyncMock()
        client._create_sse_client = MagicMock(return_value=http_client)

        events = []
        async for event in client.send_message("", "hi"):
            events.append(event)

        assert [event.event_type for event in events] == ["end"]
        _, kwargs = http_client.stream.call_args
        assert kwargs["json"]["username"] == "alice"
        assert "session_id" not in kwargs["json"]
        http_client.aclose.assert_awaited_once()

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_send_message_reports_json_error_envelope(self):
        client = AstrBotApiClient(
            "http://localhost:6185", username="alice", api_key="fixture"
        )
        transport = httpx.MockTransport(
            lambda request: httpx.Response(
                200, json={"status": "error", "message": "Session rejected"}
            )
        )
        client._create_sse_client = lambda: httpx.AsyncClient(
            transport=transport
        )

        events = [
            event async for event in client.send_message("session_001", "hi")
        ]

        assert [(event.event_type, event.data) for event in events] == [
            ("error", "Session rejected")
        ]

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_send_message_accepts_data_without_space_and_done_marker(self):
        client = AstrBotApiClient(
            "http://localhost:6185",
            username="alice",
            api_key="abk_test",
        )
        response = _FakeSseResponse(
            200,
            [
                ": heartbeat",
                'data:{"type":"plain","data":"hello","streaming":true}',
                "data: [DONE]",
            ],
        )
        http_client = MagicMock()
        http_client.stream = MagicMock(return_value=_FakeSseContext(response))
        http_client.aclose = AsyncMock()
        client._create_sse_client = MagicMock(return_value=http_client)

        events = []
        async for event in client.send_message("session_001", "hi"):
            events.append(event)

        assert [event.event_type for event in events] == ["plain", "end"]
        assert events[0].data == "hello"

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_send_message_adds_end_when_stream_closes_without_terminal_event(self):
        client = AstrBotApiClient(
            "http://localhost:6185",
            username="alice",
            api_key="abk_test",
        )
        response = _FakeSseResponse(
            200,
            ['data: {"type":"plain","data":"hello","streaming":true}'],
        )
        http_client = MagicMock()
        http_client.stream = MagicMock(return_value=_FakeSseContext(response))
        http_client.aclose = AsyncMock()
        client._create_sse_client = MagicMock(return_value=http_client)

        events = []
        async for event in client.send_message("session_001", "hi"):
            events.append(event)

        assert [event.event_type for event in events] == ["plain", "end"]


class TestAstrBotApiClientSSEDataNormalization:
    @pytest.mark.unit
    def test_normalize_sse_data_value_keeps_structured_json(self):
        raw_data = {"id": "call_123", "name": "search", "args": {"q": "hello"}}

        normalized = AstrBotApiClient._normalize_sse_data_value(raw_data)

        assert json.loads(normalized) == raw_data

    @pytest.mark.unit
    def test_normalize_sse_data_value_handles_plain_string(self):
        normalized = AstrBotApiClient._normalize_sse_data_value("hello")

        assert normalized == "hello"
