"""
配置模块单元测试

测试 ClientConfig 及其子配置类的功能：
- 默认值
- 序列化/反序列化
- 配置文件读写
- 数据校验
"""

import json
import os
import sys
from pathlib import Path

import pytest

# 确保可以导入 desktop_client
sys.path.insert(0, str(Path(__file__).parent.parent))

from desktop_client.config import (
    ClientConfig,
    ServerConfig,
    AppearanceConfig,
    ChatWindowConfig,
    HotkeyConfigData,
    InteractionConfig,
    PetRuntimeConfig,
    VoiceConfig,
    StorageConfig,
    ProactiveDialogConfig,
    DEFAULT_PROACTIVE_PROMPT_TEMPLATE,
    LEGACY_PROACTIVE_PROMPT_TEMPLATE,
    CustomThemeConfig,
    load_config,
    save_config,
)


class TestServerConfig:
    """ServerConfig 测试"""

    @pytest.mark.unit
    def test_default_values(self):
        """测试默认值"""
        config = ServerConfig()

        assert config.url == "http://localhost:6185"
        assert config.username == "astrbot"
        assert config.password == ""
        assert config.api_key == ""
        assert config.auth_mode == "openapi"
        assert config.token is None
        assert config.auto_reconnect is True
        assert config.reconnect_interval == 5
        assert config.startup_delay == 5
        assert config.max_reconnect_attempts == 0
        assert config.request_timeout == 30
        assert config.enable_streaming is True
        assert config.enable_remote_control is False

    @pytest.mark.unit
    def test_custom_values(self):
        """测试自定义值"""
        config = ServerConfig(
            url="http://custom:8080",
            username="custom_user",
            password="custom_pass",
            api_key="abk_custom",
            auth_mode="legacy",
            token="token123",
            auto_reconnect=False,
            reconnect_interval=10,
        )

        assert config.url == "http://custom:8080"
        assert config.username == "custom_user"
        assert config.password == "custom_pass"
        assert config.api_key == "abk_custom"
        assert config.auth_mode == "legacy"
        assert config.token == "token123"
        assert config.auto_reconnect is False
        assert config.reconnect_interval == 10


class TestAppearanceConfig:
    """AppearanceConfig 测试"""

    @pytest.mark.unit
    def test_default_values(self):
        """测试默认值"""
        config = AppearanceConfig()

        assert config.ball_size == 64
        assert config.ball_opacity == 0.9
        assert config.avatar_path == ""
        assert config.user_avatar_path == ""
        assert config.bot_avatar_path == ""
        assert config.theme == "tiktok"
        assert config.always_on_top is False
        assert config.breathing_enabled is True
        assert config.auto_start is False
        assert isinstance(config.custom_theme, CustomThemeConfig)

    @pytest.mark.unit
    def test_custom_theme_defaults(self):
        """测试自定义主题默认值"""
        config = AppearanceConfig()

        assert config.custom_theme.enabled is False
        assert config.custom_theme.primary == ""
        assert config.custom_theme.bg_primary == ""
        assert config.custom_theme.ball_bg == ""


class TestChatWindowConfig:
    """ChatWindowConfig 测试"""

    @pytest.mark.unit
    def test_default_values(self):
        """测试默认值"""
        config = ChatWindowConfig()

        assert config.window_width == 400
        assert config.window_height == 600
        assert config.font_size == 14
        assert config.show_timestamp is True
        assert config.history_display_limit == 10


class TestStorageConfig:
    """StorageConfig 测试"""

    @pytest.mark.unit
    def test_default_values(self):
        """测试默认值"""
        config = StorageConfig()

        assert config.image_save_path == ""
        assert config.chat_history_path == ""

    @pytest.mark.unit
    def test_resolved_image_save_path_default(self, tmp_path: Path, monkeypatch):
        """测试默认图片保存路径解析"""
        # 切换到临时目录
        monkeypatch.chdir(tmp_path)

        config = StorageConfig()
        resolved = config.resolved_image_save_path

        assert resolved.exists()
        assert "images" in str(resolved)

    @pytest.mark.unit
    def test_resolved_image_save_path_custom(self, tmp_path: Path):
        """测试自定义图片保存路径解析"""
        custom_path = tmp_path / "custom_images"
        config = StorageConfig(image_save_path=str(custom_path))

        resolved = config.resolved_image_save_path

        assert resolved == custom_path
        assert resolved.exists()


class TestProactiveDialogConfig:
    """ProactiveDialogConfig 测试"""

    @pytest.mark.unit
    def test_default_values(self):
        """测试默认值"""
        config = ProactiveDialogConfig()

        assert config.enabled is False
        assert config.check_interval == 600
        assert config.trigger_probability == 0.2
        assert config.require_user_active is True
        assert config.idle_threshold == 60
        assert config.time_range_enabled is False
        assert config.time_range_start == "09:00"
        assert config.time_range_end == "22:00"
        assert config.screenshot_width == 800
        assert config.screenshot_height == 600
        assert config.max_response_tokens == 50
        assert config.prompt_template == DEFAULT_PROACTIVE_PROMPT_TEMPLATE
        assert "你是用户的桌面助手" not in config.prompt_template
        assert "原有的人设" in config.prompt_template

    @pytest.mark.unit
    def test_legacy_default_prompt_migrates_without_overwriting_custom(self, tmp_path):
        """旧版默认提示词自动迁移为保人设模板，自定义模板保持不变"""
        legacy_path = tmp_path / "legacy_config.json"
        legacy_path.write_text(
            json.dumps(
                {"proactive": {"prompt_template": LEGACY_PROACTIVE_PROMPT_TEMPLATE}},
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        loaded_legacy = ClientConfig.load(str(legacy_path))
        assert loaded_legacy.proactive.prompt_template == DEFAULT_PROACTIVE_PROMPT_TEMPLATE

        custom_prompt = "按猫娘口吻简短评论当前屏幕"
        custom_path = tmp_path / "custom_config.json"
        custom_path.write_text(
            json.dumps(
                {"proactive": {"prompt_template": custom_prompt}},
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        loaded_custom = ClientConfig.load(str(custom_path))
        assert loaded_custom.proactive.prompt_template == custom_prompt


class TestPetRuntimeConfig:
    """PetRuntimeConfig 测试"""

    @pytest.mark.unit
    def test_default_values(self):
        config = PetRuntimeConfig()

        assert config.enabled is True
        assert config.display_mode == "pet"
        assert config.listen_host == "127.0.0.1"
        assert config.listen_port == 17321
        assert config.current_pet_id == "taotao"
        assert config.pet_packages_dir == ""
        assert config.window_scale == 1.0
        assert config.always_on_top is True
        assert config.bubble_ttl_ms == 4000
        assert config.api_enabled is True


class TestClientConfig:
    """ClientConfig 完整测试"""

    @pytest.mark.unit
    def test_default_initialization(self, default_config: ClientConfig):
        """测试默认初始化"""
        assert isinstance(default_config.server, ServerConfig)
        assert isinstance(default_config.appearance, AppearanceConfig)
        assert isinstance(default_config.chat_window, ChatWindowConfig)
        assert isinstance(default_config.voice, VoiceConfig)
        assert isinstance(default_config.hotkeys, HotkeyConfigData)
        assert isinstance(default_config.interaction, InteractionConfig)
        assert isinstance(default_config.pet_runtime, PetRuntimeConfig)
        assert isinstance(default_config.proactive, ProactiveDialogConfig)
        assert isinstance(default_config.storage, StorageConfig)
        assert default_config.session_id is None

    @pytest.mark.unit
    def test_save_and_load(self, sample_config: ClientConfig, temp_config_file: Path):
        """测试保存和加载配置"""
        # 保存配置
        result = sample_config.save(str(temp_config_file))
        assert result is True
        assert temp_config_file.exists()

        # 加载配置
        loaded = ClientConfig.load(str(temp_config_file))

        # 验证加载的值
        assert loaded.server.url == sample_config.server.url
        assert loaded.server.username == sample_config.server.username
        assert loaded.server.token == sample_config.server.token
        assert loaded.appearance.ball_size == sample_config.appearance.ball_size
        assert loaded.appearance.theme == sample_config.appearance.theme
        assert loaded.chat_window.font_size == sample_config.chat_window.font_size
        assert (
            loaded.chat_window.history_display_limit
            == sample_config.chat_window.history_display_limit
        )
        assert loaded.pet_runtime.current_pet_id == sample_config.pet_runtime.current_pet_id
        assert loaded.pet_runtime.display_mode == sample_config.pet_runtime.display_mode
        assert loaded.session_id == sample_config.session_id

    @pytest.mark.unit
    def test_load_nonexistent_file(self, tmp_path: Path):
        """测试加载不存在的文件（应返回默认配置）"""
        nonexistent = tmp_path / "nonexistent.json"

        config = ClientConfig.load(str(nonexistent))

        # 应该返回默认配置
        assert config.server.url == "http://localhost:6185"
        assert config.server.username == "astrbot"

    @pytest.mark.unit
    def test_load_from_dict(self, sample_config_dict: dict, temp_config_file: Path):
        """测试从字典加载配置"""
        # 写入配置文件
        with open(temp_config_file, "w", encoding="utf-8") as f:
            json.dump(sample_config_dict, f)

        # 加载
        config = ClientConfig.load(str(temp_config_file))

        assert config.server.url == sample_config_dict["server"]["url"]
        assert config.server.username == sample_config_dict["server"]["username"]
        assert (
            config.appearance.ball_size == sample_config_dict["appearance"]["ball_size"]
        )
        assert config.session_id == sample_config_dict["session_id"]

    @pytest.mark.unit
    def test_load_partial_config(self, temp_config_file: Path):
        """测试加载部分配置（缺失字段应使用默认值）"""
        partial_config = {
            "server": {
                "url": "http://partial:8080",
            },
            "appearance": {
                "theme": "dark",
            },
        }

        with open(temp_config_file, "w", encoding="utf-8") as f:
            json.dump(partial_config, f)

        config = ClientConfig.load(str(temp_config_file))

        # 指定的值
        assert config.server.url == "http://partial:8080"
        assert config.appearance.theme == "dark"

        # 默认值
        assert config.server.username == "astrbot"  # 默认值
        assert config.appearance.ball_size == 64  # 默认值
        assert config.session_id is None  # 默认值

    @pytest.mark.unit
    def test_to_legacy_dict(self, sample_config: ClientConfig):
        """测试转换为旧版字典格式"""
        legacy = sample_config.to_legacy_dict()

        assert legacy["server_url"] == sample_config.server.url
        assert legacy["username"] == sample_config.server.username
        assert legacy["ball_size"] == sample_config.appearance.ball_size
        assert legacy["theme"] == sample_config.appearance.theme
        assert legacy["font_size"] == sample_config.chat_window.font_size

    @pytest.mark.unit
    def test_update_from_legacy_dict(self, default_config: ClientConfig):
        """测试从旧版字典更新配置"""
        legacy = {
            "server_url": "http://legacy:9999",
            "username": "legacy_user",
            "password": "legacy_pass",
            "ball_size": 100,
            "theme": "light",
            "font_size": 18,
        }

        default_config.update_from_legacy_dict(legacy)

        assert default_config.server.url == "http://legacy:9999"
        assert default_config.server.username == "legacy_user"
        assert default_config.server.password == "legacy_pass"
        assert default_config.appearance.ball_size == 100
        assert default_config.appearance.theme == "light"
        assert default_config.chat_window.font_size == 18

    @pytest.mark.unit
    def test_custom_theme_serialization(self, temp_config_file: Path):
        """测试自定义主题序列化"""
        config = ClientConfig()
        config.appearance.custom_theme.enabled = True
        config.appearance.custom_theme.primary = "#FF5722"
        config.appearance.custom_theme.bg_primary = "#1E1E1E"

        # 保存
        config.save(str(temp_config_file))

        # 加载
        loaded = ClientConfig.load(str(temp_config_file))

        assert loaded.appearance.custom_theme.enabled is True
        assert loaded.appearance.custom_theme.primary == "#FF5722"
        assert loaded.appearance.custom_theme.bg_primary == "#1E1E1E"

    @pytest.mark.unit
    def test_thread_safety(self, sample_config: ClientConfig, temp_config_file: Path):
        """测试线程安全（锁的存在性）"""
        # 确保配置有锁
        assert hasattr(sample_config, "_lock")

        # 保存应该成功（不会死锁）
        result = sample_config.save(str(temp_config_file))
        assert result is True

    @pytest.mark.unit
    def test_config_dir_creation(self, tmp_path: Path, monkeypatch):
        """测试配置目录创建"""
        # Mock 环境变量
        if os.name == "nt":
            monkeypatch.setenv("APPDATA", str(tmp_path))
        else:
            monkeypatch.setenv("HOME", str(tmp_path))

        config_dir = ClientConfig.get_config_dir()

        assert config_dir.exists()
        assert config_dir.is_dir()


class TestConfigHelperFunctions:
    """配置辅助函数测试"""

    @pytest.mark.unit
    def test_load_config_function(
        self, temp_config_file: Path, sample_config_dict: dict
    ):
        """测试 load_config 函数"""
        with open(temp_config_file, "w", encoding="utf-8") as f:
            json.dump(sample_config_dict, f)

        config = load_config(str(temp_config_file))

        assert isinstance(config, ClientConfig)
        assert config.server.url == sample_config_dict["server"]["url"]

    @pytest.mark.unit
    def test_save_config_function(
        self, sample_config: ClientConfig, temp_config_file: Path
    ):
        """测试 save_config 函数"""
        result = save_config(sample_config, str(temp_config_file))

        assert result is True
        assert temp_config_file.exists()

        # 验证内容
        with open(temp_config_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        assert data["server"]["url"] == sample_config.server.url


class TestConfigEdgeCases:
    """配置边界情况测试"""

    @pytest.mark.unit
    def test_load_corrupted_json(self, temp_config_file: Path):
        """测试加载损坏的 JSON 文件"""
        with open(temp_config_file, "w", encoding="utf-8") as f:
            f.write("{ invalid json }")

        # 应该返回默认配置而不是崩溃
        config = ClientConfig.load(str(temp_config_file))

        assert config.server.url == "http://localhost:6185"

    @pytest.mark.unit
    def test_load_empty_file(self, temp_config_file: Path):
        """测试加载空文件"""
        temp_config_file.touch()

        config = ClientConfig.load(str(temp_config_file))

        assert config.server.url == "http://localhost:6185"

    @pytest.mark.unit
    def test_save_to_readonly_location(self, tmp_path: Path):
        """测试保存到只读位置（应该失败但不崩溃）"""
        # 创建只读目录在 Windows 上比较复杂，这里简化测试
        # 测试保存到不存在的深层目录
        config = ClientConfig()

        # 这个路径可能无法写入（取决于权限）
        # 但函数应该返回 False 而不是抛出异常
        result = config.save("/nonexistent/deep/path/config.json")

        # 在大多数系统上这应该失败
        # 但重要的是不崩溃
        assert isinstance(result, bool)

    @pytest.mark.unit
    def test_unicode_in_config(self, temp_config_file: Path):
        """测试配置中的 Unicode 字符"""
        config = ClientConfig()
        config.proactive.prompt_template = "你好，这是中文测试 🎉"

        config.save(str(temp_config_file))
        loaded = ClientConfig.load(str(temp_config_file))

        assert loaded.proactive.prompt_template == "你好，这是中文测试 🎉"

    @pytest.mark.unit
    def test_special_characters_in_password(self, temp_config_file: Path):
        """测试密码中的特殊字符"""
        config = ClientConfig()
        config.server.password = 'p@$$w0rd!#%^&*(){}[]|\\:";<>,.?/'

        config.save(str(temp_config_file))
        loaded = ClientConfig.load(str(temp_config_file))

        assert loaded.server.password == config.server.password

    @pytest.mark.unit
    def test_api_key_is_obfuscated_on_disk(self, temp_config_file: Path):
        config = ClientConfig()
        config.server.api_key = "abk_secret"

        config.save(str(temp_config_file))

        raw = temp_config_file.read_text(encoding="utf-8")
        assert "abk_secret" not in raw

        loaded = ClientConfig.load(str(temp_config_file))
        assert loaded.server.api_key == "abk_secret"
