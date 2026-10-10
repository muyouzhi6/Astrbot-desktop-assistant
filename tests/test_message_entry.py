"""Exercise the Qt send action, app slot, bridge and HTTP transport (#20/#21)."""

import asyncio
import json
from types import SimpleNamespace

import httpx
import pytest
from PySide6.QtWidgets import QApplication
from qasync import QEventLoop

from desktop_client.app import DesktopClientApp
from desktop_client.config import ClientConfig
from desktop_client.gui.floating_ball import CompactChatWindow
from desktop_client.services.chat_history import ChatHistoryManager


@pytest.fixture(scope="module")
def qt_app():
    return QApplication.instance() or QApplication([])


@pytest.mark.parametrize("auth_mode", ["openapi", "legacy"])
@pytest.mark.parametrize("message, outcome", [
    ("你好", "stream"),
    ("🙂中文\n" * 2500, "stream"),
    ("", "ignored"),
    (" \n\t ", "ignored"),
    ("hello", "401"),
    ("hello", "500"),
    ("hello", "timeout"),
    ("hello", "disconnected"),
], ids=["normal", "long-unicode", "empty", "whitespace", "unauthorized", "server-error", "timeout", "disconnected"])
def test_user_send_action(qt_app, monkeypatch, auth_mode, message, outcome):
    config = ClientConfig()
    config.server.url = "http://test.invalid"
    config.server.auth_mode = auth_mode
    config.server.api_key = "test-fixture" if auth_mode == "openapi" else ""
    config.server.username = "test-user"
    config.server.password = "test-fixture"
    config.session_id = ""
    monkeypatch.setattr("desktop_client.app.load_config", lambda: config)
    ChatHistoryManager.reset_instance()
    history = ChatHistoryManager.get_instance()
    app = DesktopClientApp()
    window = CompactChatWindow(config=config)
    facade = SimpleNamespace(
        update_streaming_response=window.update_streaming_response,
        finish_response=window.finish_response,
        has_active_response=lambda: bool(window._current_ai_message_id),
        is_chat_window_visible=lambda: True,
        set_unread_message=lambda value: None,
        show_bubble=lambda text, **kwargs: window._display_ai_text(text),
        show_system_message=lambda text: None,
    )
    app._floating_ball = facade
    app._message_handler.set_floating_ball(facade)
    app._message_handler.set_chat_history_manager(history)
    api = app._bridge.api_client
    requests = []
    outputs = []
    widths = []
    app._bridge.message_received.connect(outputs.append)
    window.message_sent.connect(app._on_message_sent)
    reply = "Hi, " + "中文流式回复，随着文本增长应自动换行。" * 30

    class ReplyStream(httpx.AsyncByteStream):
        async def __aiter__(self):
            for chunk in [reply[:4], reply[4:]]:
                event = {"type": "plain", "data": chunk, "streaming": True}
                yield ("data: " + json.dumps(event) + "\n\n").encode()
                await asyncio.sleep(0.06)
                label = window._message_labels.get(window._current_ai_message_id)
                if label:
                    widths.append(label.width())
            yield b'data: {"type":"end","data":""}\n\n'

    def respond(request):
        path = request.url.path
        if path == "/api/auth/login":
            return httpx.Response(200, json={"status": "ok", "data": {"token": "test-fixture"}})
        if path.endswith("/chat/sessions"):
            return httpx.Response(200, json={"status": "ok", "data": []})
        if path == "/api/chat/new_session":
            return httpx.Response(200, json={"status": "ok", "data": {"session_id": "test-session"}})
        assert path == ("/api/v1/chat" if auth_mode == "openapi" else "/api/chat/send")
        assert request.method == "POST"
        body = json.loads(request.content)
        requests.append(body)
        if outcome == "timeout":
            raise httpx.ReadTimeout("test response timeout")
        if outcome in {"401", "500"}:
            return httpx.Response(int(outcome))
        return httpx.Response(200, headers={"Content-Type": "text/event-stream"}, stream=ReplyStream())

    transport = httpx.MockTransport(respond)
    api._client = httpx.AsyncClient(transport=transport)
    monkeypatch.setattr(api, "_create_sse_client", lambda: httpx.AsyncClient(transport=transport))

    async def exercise():
        success, _ = await app._bridge.connect_server()
        assert success and app._bridge.is_connected and config.session_id
        if outcome == "disconnected":
            await app._bridge.disconnect_server()
        window.show()
        window._input.setPlainText(message)
        window._send_btn.click()
        for _ in range(100):
            if outcome == "ignored" or any(m.msg_type in {"end", "error"} for m in outputs):
                break
            await asyncio.sleep(0.02)
        await asyncio.sleep(0.08)
        print(f"mode={auth_mode}, input_length={len(message)}, outcome={outcome}, "
              f"chat_requests={len(requests)}, events={[m.msg_type for m in outputs]}")
        if outcome in {"ignored", "disconnected"}:
            assert not requests
        else:
            assert len(requests) == 1
            assert requests[0]["message"] == message.strip()
            assert requests[0]["session_id"] == config.session_id
        if outcome == "stream":
            assert [m.content for m in history.get_messages() if m.role == "assistant"] == [reply]
            assert any(m.msg_type == "end" for m in outputs)
            assert not any(m.msg_type == "error" for m in outputs)
            assert window._current_ai_message_id == ""
            assert not window._stream_flush_timer.isActive()
            assert len(widths) == 2 and widths[1] > widths[0]
            label = next(iter(window._message_labels.values()))
            assert label.document().size().width() <= label.viewport().width() + 1
            assert label.document().size().height() <= label.viewport().height()
            assert label.parentWidget().width() >= label.width() + 24
            saved = json.loads(config.get_config_dir().joinpath("chat_history.json").read_text())
            assert saved["messages"][-1]["content"] == reply
        elif outcome != "ignored":
            assert any(m.msg_type == "error" for m in outputs)
            assert not window._current_ai_message_id
        assert not app._bridge._request_lock.locked()
        assert app._bridge._current_request_id is None
        if outcome != "ignored":
            assert window._input.toPlainText() == ""

    async def run():
        try:
            await exercise()
        finally:
            await app._bridge.disconnect_server()
            window._stream_flush_timer.stop()
            window._auto_hide_timer.stop()
            window.close()
            window.deleteLater()
            await asyncio.sleep(0)
            ChatHistoryManager.reset_instance()

    with QEventLoop(qt_app) as loop:
        asyncio.set_event_loop(loop)
        loop.run_until_complete(run())
