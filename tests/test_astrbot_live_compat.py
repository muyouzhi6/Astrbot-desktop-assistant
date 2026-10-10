"""Loopback tests against three official AstrBot dashboard versions."""

import asyncio
import os
import socket
import subprocess
import sys
import time
from pathlib import Path
from types import SimpleNamespace

import pytest

VERSIONS = ("4.26.8", "4.27.3", "4.28.2")
FIXTURE_USER = "compat-user"
FIXTURE_PASSWORD = "compat-test-password"
FIXTURE_KEY = "compat-test-api-key"
_QT_APP = None


async def _serve(source, root, port):
    os.environ["ASTRBOT_ROOT"] = str(root)
    sys.path.insert(0, str(source))

    import uvicorn
    from fastapi import FastAPI
    from fastapi.responses import JSONResponse

    from astrbot import __version__
    from astrbot.core.db.sqlite import SQLiteDatabase
    from astrbot.core.platform.sources.webchat.webchat_queue_mgr import (
        webchat_queue_mgr,
    )
    from astrbot.core.platform_message_history_mgr import (
        PlatformMessageHistoryManager,
    )
    from astrbot.core.utils.auth_password import hash_md5_dashboard_password
    from astrbot.dashboard.api import auth, chat, open_api
    from astrbot.dashboard.responses import ApiError, error
    from astrbot.dashboard.services.api_key_service import ApiKeyService
    from astrbot.dashboard.services.auth_service import AuthService
    from astrbot.dashboard.services.chat_service import ChatService
    from astrbot.dashboard.services.open_api_service import OpenApiService

    assert __version__ == source.name.removeprefix("AstrBot-")

    class MemoryConfig(dict):
        def save_config(self, *args, **kwargs):
            pass

    data = root / "data"
    data.mkdir(parents=True, exist_ok=True)
    db = SQLiteDatabase(str(data / "compat.sqlite"))
    await db.initialize()
    await db.create_api_key(
        name="compat",
        key_hash=ApiKeyService.hash_key(FIXTURE_KEY),
        key_prefix="compat",
        scopes=["chat"],
        created_by=FIXTURE_USER,
    )
    config = MemoryConfig(
        dashboard={
            "username": FIXTURE_USER,
            "password": hash_md5_dashboard_password(FIXTURE_PASSWORD),
            "pbkdf2_password": "",
            "password_storage_upgraded": False,
            "password_change_required": False,
            "jwt_secret": "compat-test-jwt-secret",
            "totp": {"enable": False},
        }
    )
    lifecycle = SimpleNamespace(
        conversation_manager=SimpleNamespace(),
        platform_message_history_manager=PlatformMessageHistoryManager(db),
        umop_config_router=SimpleNamespace(),
        astrbot_config_mgr=SimpleNamespace(get_conf_list=lambda: [], confs={}),
        platform_manager=SimpleNamespace(),
    )
    app = FastAPI()
    app.state.db = db
    app.state.jwt_secret = config["dashboard"]["jwt_secret"]
    app.state.services = SimpleNamespace(
        auth=AuthService(db, config),
        chat=ChatService(db, lifecycle),
        open_api=OpenApiService(db, lifecycle),
    )
    app.include_router(auth.legacy_router)
    app.include_router(chat.legacy_router)
    app.include_router(open_api.router, prefix="/api/v1")

    @app.exception_handler(ApiError)
    async def api_error(_request, exc):
        return JSONResponse(error(exc.message), status_code=exc.status_code)

    async def answer(item):
        _, _, payload = item
        request_id = payload["message_id"]
        for event in (
            {"type": "plain", "data": "AstrBot live reply", "streaming": True},
            {"type": "end", "data": ""},
        ):
            await webchat_queue_mgr.put_back_queue(
                request_id, {**event, "message_id": request_id}
            )

    webchat_queue_mgr.set_listener(answer)
    server = uvicorn.Server(
        uvicorn.Config(app, host="127.0.0.1", port=port, log_level="error")
    )
    try:
        await server.serve()
    finally:
        await webchat_queue_mgr.clear_listener()
        await db.engine.dispose()


@pytest.fixture(scope="module", params=VERSIONS)
def live_astrbot(request, tmp_path_factory):
    runtime = os.environ.get("ASTRBOT_COMPAT_PYTHON")
    sources = os.environ.get("ASTRBOT_COMPAT_SOURCE_ROOT")
    if not runtime or not sources:
        pytest.skip("Set AstrBot runtime and official source paths")
    source = Path(sources) / f"AstrBot-{request.param}"
    assert source.is_dir(), source
    root = tmp_path_factory.mktemp(f"astrbot-{request.param}")
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()
    log_dir = Path(os.environ.get("ASTRBOT_COMPAT_LOG_DIR", root))
    with (log_dir / f"finalfix2-live-server-{request.param}.log").open(
        "w"
    ) as output:
        proc = subprocess.Popen(
            [runtime, __file__, "--serve", str(source), str(root), str(port)],
            stdout=output,
            stderr=subprocess.STDOUT,
            env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
        )
        try:
            import httpx

            url = f"http://127.0.0.1:{port}"
            for _ in range(100):
                if proc.poll() is not None:
                    pytest.fail(
                        f"AstrBot {request.param} exited during startup"
                    )
                try:
                    response = httpx.get(
                        f"{url}/api/v1/chat/sessions", timeout=0.5
                    )
                    if response.status_code == 401:
                        break
                except httpx.ConnectError:
                    time.sleep(0.1)
            else:
                pytest.fail(f"AstrBot {request.param} did not start")
            yield request.param, url
        finally:
            proc.terminate()
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait(timeout=10)


@pytest.mark.parametrize("auth_mode", ["openapi", "legacy"])
@pytest.mark.asyncio
async def test_live_login_and_send(live_astrbot, auth_mode):
    from desktop_client.api_client import AstrBotApiClient

    version, url = live_astrbot
    client = AstrBotApiClient(
        url,
        username=FIXTURE_USER,
        password=FIXTURE_PASSWORD,
        api_key=FIXTURE_KEY if auth_mode == "openapi" else "",
        auth_mode=auth_mode,
    )
    try:
        success, detail = await client.login()
        assert success, f"AstrBot {version} {auth_mode}: {detail}"
        created, session_id = await client.create_session()
        assert created, f"AstrBot {version} {auth_mode}: {session_id}"
        events = [
            event
            async for event in client.send_message(
                session_id, "hello from desktop"
            )
        ]
        kinds = [
            event.event_type
            for event in events
            if event.event_type in ("plain", "end", "error")
        ]
        assert kinds == ["plain", "end"]
        assert (
            next(event.data for event in events if event.event_type == "plain")
            == "AstrBot live reply"
        )
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_live_error_envelope_reaches_client(live_astrbot):
    from desktop_client.api_client import AstrBotApiClient

    version, url = live_astrbot
    client = AstrBotApiClient(url, username=FIXTURE_USER, api_key=FIXTURE_KEY)
    try:
        success, detail = await client.login()
        assert success, f"AstrBot {version}: {detail}"
        events = [event async for event in client.send_message("", "")]
        assert len(events) == 1
        assert events[0].event_type == "error"
        assert "empty" in events[0].data.lower()
    finally:
        await client.close()


@pytest.mark.parametrize("auth_mode", ["openapi", "legacy"])
def test_live_qt_send_action(live_astrbot, auth_mode, monkeypatch):
    global _QT_APP

    from PySide6.QtWidgets import QApplication

    from desktop_client.app import DesktopClientApp
    from desktop_client.config import ClientConfig
    from desktop_client.gui.floating_ball import CompactChatWindow
    from desktop_client.services.chat_history import ChatHistoryManager

    version, url = live_astrbot
    _QT_APP = QApplication.instance() or QApplication([])
    qt_app = _QT_APP
    config = ClientConfig()
    config.server.url = url
    config.server.auth_mode = auth_mode
    config.server.api_key = FIXTURE_KEY if auth_mode == "openapi" else ""
    config.server.username = FIXTURE_USER
    config.server.password = FIXTURE_PASSWORD
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
    outputs = []
    app._bridge.message_received.connect(outputs.append)
    window.message_sent.connect(app._on_message_sent)

    async def exercise():
        try:
            success, detail = await app._bridge.connect_server()
            assert success, f"AstrBot {version} {auth_mode}: {detail}"
            window.show()
            window._input.setPlainText("Qt live request")
            window._send_btn.click()
            for _ in range(120):
                qt_app.processEvents()
                finished = any(
                    message.msg_type in {"end", "error"} for message in outputs
                )
                if finished and app._bridge._current_request_id is None:
                    break
                await asyncio.sleep(0.025)
            await asyncio.sleep(0.1)
            assert not any(message.msg_type == "error" for message in outputs)
            assert any(message.msg_type == "end" for message in outputs)
            assert [
                message.content
                for message in history.get_messages()
                if message.role == "assistant"
            ] == ["AstrBot live reply"]
            assert window._current_ai_message_id == ""
            assert not app._bridge._request_lock.locked()
        finally:
            await app._bridge.disconnect_server()
            window._stream_flush_timer.stop()
            window._auto_hide_timer.stop()
            window.close()
            window.deleteLater()
            await asyncio.sleep(0)
            ChatHistoryManager.reset_instance()

    asyncio.run(exercise())


if __name__ == "__main__" and sys.argv[1:2] == ["--serve"]:
    asyncio.run(_serve(Path(sys.argv[2]), Path(sys.argv[3]), int(sys.argv[4])))
