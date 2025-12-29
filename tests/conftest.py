"""
pytest 配置和共享 fixtures

提供测试所需的共享配置、Mock 对象和工具函数。
"""

import asyncio
import sys
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# 将 desktop_client 添加到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from desktop_client.config import (
    ClientConfig,
)
from desktop_client.api_client import (
    AstrBotApiClient,
    ConnectionState,
    SSEEvent,
)
from desktop_client.platforms.base import (
    IPlatformAdapter,
    Result,
    WindowInfo,
    AppInfo,
)


# ============ 配置相关 fixtures ============


@pytest.fixture
def temp_config_dir(tmp_path: Path) -> Path:
    """创建临时配置目录"""
    config_dir = tmp_path / "config"
    config_dir.mkdir(parents=True, exist_ok=True)
    return config_dir


@pytest.fixture
def temp_config_file(temp_config_dir: Path) -> Path:
    """创建临时配置文件路径"""
    return temp_config_dir / "config.json"


@pytest.fixture
def default_config() -> ClientConfig:
    """创建默认配置实例"""
    return ClientConfig()


@pytest.fixture
def sample_config() -> ClientConfig:
    """创建示例配置实例（带自定义值）"""
    config = ClientConfig()
    config.server.url = "http://test-server:8080"
    config.server.username = "test_user"
    config.server.password = "test_password"
    config.server.token = "test_token_12345"
    config.appearance.ball_size = 80
    config.appearance.theme = "dark"
    config.chat_window.font_size = 16
    config.session_id = "test_session_001"
    return config


@pytest.fixture
def sample_config_dict() -> dict:
    """创建示例配置字典"""
    return {
        "server": {
            "url": "http://test-server:8080",
            "username": "test_user",
            "password": "test_password",
            "token": "test_token_12345",
            "auto_reconnect": True,
            "reconnect_interval": 5,
            "startup_delay": 3,
            "max_reconnect_attempts": 0,
            "request_timeout": 30,
            "enable_streaming": True,
        },
        "appearance": {
            "ball_size": 80,
            "ball_opacity": 0.9,
            "avatar_path": "",
            "user_avatar_path": "",
            "bot_avatar_path": "",
            "theme": "dark",
            "always_on_top": False,
            "breathing_enabled": True,
            "auto_start": False,
            "custom_theme": {
                "enabled": False,
                "primary": "",
                "primary_light": "",
                "primary_dark": "",
                "bg_primary": "",
                "bg_secondary": "",
                "text_primary": "",
                "text_secondary": "",
                "ball_bg": "",
                "ball_glow": "",
                "ball_border": "",
                "bubble_user_bg": "",
                "bubble_user_text": "",
                "bubble_ai_bg": "",
                "bubble_ai_text": "",
            },
        },
        "chat_window": {
            "window_width": 400,
            "window_height": 600,
            "font_size": 16,
            "show_timestamp": True,
        },
        "voice": {
            "enable_tts": True,
            "auto_play_voice": False,
        },
        "hotkeys": {
            "toggle_chat": "Ctrl+Shift+A",
            "region_screenshot": "Ctrl+Shift+S",
            "full_screenshot": "Ctrl+Shift+F",
            "toggle_ball": "Ctrl+Shift+B",
            "quick_ask": "Ctrl+Shift+Q",
            "cycle_theme": "Ctrl+Shift+T",
            "global_enabled": False,
        },
        "interaction": {
            "default_mode": "window",
            "single_click": "bubble",
            "double_click": "window",
            "bubble_duration": 5,
            "bubble_auto_hide": True,
            "do_not_disturb": False,
        },
        "proactive": {
            "enabled": False,
            "check_interval": 600,
            "trigger_probability": 0.2,
            "require_user_active": True,
            "idle_threshold": 60,
            "time_range_enabled": False,
            "time_range_start": "09:00",
            "time_range_end": "22:00",
            "screenshot_width": 800,
            "screenshot_height": 600,
            "max_response_tokens": 50,
            "prompt_template": "你是用户的桌面助手。",
        },
        "storage": {
            "image_save_path": "",
            "chat_history_path": "",
        },
        "session_id": "test_session_001",
    }


# ============ API 客户端相关 fixtures ============


@pytest.fixture
def mock_api_client() -> MagicMock:
    """创建 Mock API 客户端"""
    client = MagicMock(spec=AstrBotApiClient)
    client.state = ConnectionState.DISCONNECTED
    client.is_connected = False
    client.token = None
    client.server_url = "http://localhost:6185"
    client.username = "test_user"
    client.password = "test_password"

    # Mock 异步方法
    client.login = AsyncMock(return_value=(True, "登录成功"))
    client.check_connection = AsyncMock(return_value=True)
    client.create_session = AsyncMock(return_value=(True, "session_123"))
    client.get_sessions = AsyncMock(return_value=(True, []))
    client.close = AsyncMock()
    client.start_health_check = AsyncMock()
    client.stop_health_check = AsyncMock()

    return client


@pytest.fixture
def sample_sse_events() -> list[SSEEvent]:
    """创建示例 SSE 事件列表"""
    return [
        SSEEvent(
            event_type="plain",
            data="Hello",
            streaming=True,
            chain_type="normal",
        ),
        SSEEvent(
            event_type="plain",
            data=" World",
            streaming=True,
            chain_type="normal",
        ),
        SSEEvent(
            event_type="plain",
            data="!",
            streaming=False,
            chain_type="normal",
        ),
        SSEEvent(
            event_type="end",
            data="",
            streaming=False,
        ),
    ]


# ============ 平台适配器相关 fixtures ============


class MockPlatformAdapter(IPlatformAdapter):
    """Mock 平台适配器实现"""

    def __init__(self):
        self._autostart_enabled = False
        self._active_window = WindowInfo(
            title="Test Window",
            process="test.exe",
            pid=1234,
        )
        self._running_apps = [
            AppInfo(pid=1234, name="test.exe"),
            AppInfo(pid=5678, name="browser.exe"),
        ]

    @property
    def platform_name(self) -> str:
        return "mock"

    def get_active_window(self) -> WindowInfo:
        return self._active_window

    def get_running_apps(self, max_count: int = 50) -> list[AppInfo]:
        return self._running_apps[:max_count]

    def enable_autostart(self) -> Result:
        self._autostart_enabled = True
        return Result.success("已启用开机自启")

    def disable_autostart(self) -> Result:
        self._autostart_enabled = False
        return Result.success("已禁用开机自启")

    def is_autostart_enabled(self) -> bool:
        return self._autostart_enabled


@pytest.fixture
def mock_platform_adapter() -> MockPlatformAdapter:
    """创建 Mock 平台适配器"""
    return MockPlatformAdapter()


# ============ 异步测试支持 ============


@pytest.fixture
def event_loop():
    """创建事件循环"""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


# ============ 临时文件和目录 fixtures ============


@pytest.fixture
def temp_image_file(tmp_path: Path) -> Path:
    """创建临时图片文件"""
    image_file = tmp_path / "test_image.png"
    # 创建一个最小的有效 PNG 文件（1x1 透明像素）
    png_data = bytes(
        [
            0x89,
            0x50,
            0x4E,
            0x47,
            0x0D,
            0x0A,
            0x1A,
            0x0A,  # PNG signature
            0x00,
            0x00,
            0x00,
            0x0D,
            0x49,
            0x48,
            0x44,
            0x52,  # IHDR chunk
            0x00,
            0x00,
            0x00,
            0x01,
            0x00,
            0x00,
            0x00,
            0x01,  # 1x1
            0x08,
            0x06,
            0x00,
            0x00,
            0x00,
            0x1F,
            0x15,
            0xC4,
            0x89,
            0x00,
            0x00,
            0x00,
            0x0A,
            0x49,
            0x44,
            0x41,  # IDAT chunk
            0x54,
            0x78,
            0x9C,
            0x63,
            0x00,
            0x01,
            0x00,
            0x00,
            0x05,
            0x00,
            0x01,
            0x0D,
            0x0A,
            0x2D,
            0xB4,
            0x00,
            0x00,
            0x00,
            0x00,
            0x49,
            0x45,
            0x4E,
            0x44,
            0xAE,  # IEND chunk
            0x42,
            0x60,
            0x82,
        ]
    )
    image_file.write_bytes(png_data)
    return image_file


@pytest.fixture
def temp_audio_file(tmp_path: Path) -> Path:
    """创建临时音频文件"""
    audio_file = tmp_path / "test_audio.wav"
    # 创建一个最小的有效 WAV 文件
    wav_data = bytes(
        [
            0x52,
            0x49,
            0x46,
            0x46,  # "RIFF"
            0x24,
            0x00,
            0x00,
            0x00,  # File size - 8
            0x57,
            0x41,
            0x56,
            0x45,  # "WAVE"
            0x66,
            0x6D,
            0x74,
            0x20,  # "fmt "
            0x10,
            0x00,
            0x00,
            0x00,  # Chunk size
            0x01,
            0x00,  # Audio format (PCM)
            0x01,
            0x00,  # Num channels
            0x44,
            0xAC,
            0x00,
            0x00,  # Sample rate (44100)
            0x88,
            0x58,
            0x01,
            0x00,  # Byte rate
            0x02,
            0x00,  # Block align
            0x10,
            0x00,  # Bits per sample
            0x64,
            0x61,
            0x74,
            0x61,  # "data"
            0x00,
            0x00,
            0x00,
            0x00,  # Data size
        ]
    )
    audio_file.write_bytes(wav_data)
    return audio_file


# ============ 环境变量 Mock ============


@pytest.fixture
def mock_env_vars(monkeypatch):
    """Mock 环境变量"""
    monkeypatch.setenv("APPDATA", str(Path(tempfile.gettempdir()) / "appdata"))
    monkeypatch.setenv("HOME", str(Path(tempfile.gettempdir()) / "home"))


# ============ Qt Mock（避免 GUI 依赖）============


@pytest.fixture
def mock_qt_app():
    """Mock Qt Application（用于无 GUI 测试）"""
    with patch("PySide6.QtWidgets.QApplication") as mock_app:
        mock_instance = MagicMock()
        mock_app.return_value = mock_instance
        mock_app.instance.return_value = mock_instance
        yield mock_app
