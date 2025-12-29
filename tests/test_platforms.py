"""
平台适配器单元测试

测试平台适配器的功能：
- 基类接口定义
- Result 类
- WindowInfo 和 AppInfo 数据类
- Mock 适配器行为
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# 确保可以导入 desktop_client
sys.path.insert(0, str(Path(__file__).parent.parent))

from desktop_client.platforms.base import (
    IPlatformAdapter,
    Result,
    ResultStatus,
    WindowInfo,
    AppInfo,
)


class TestResultStatus:
    """ResultStatus 枚举测试"""

    @pytest.mark.unit
    def test_status_values(self):
        """测试状态值"""
        assert ResultStatus.SUCCESS.value == "success"
        assert ResultStatus.FAILED.value == "failed"
        assert ResultStatus.NOT_SUPPORTED.value == "not_supported"


class TestResult:
    """Result 类测试"""

    @pytest.mark.unit
    def test_success_result(self):
        """测试成功结果"""
        result = Result.success("操作成功")

        assert result.status == ResultStatus.SUCCESS
        assert result.message == "操作成功"
        assert result.is_success is True

    @pytest.mark.unit
    def test_success_result_no_message(self):
        """测试无消息的成功结果"""
        result = Result.success()

        assert result.status == ResultStatus.SUCCESS
        assert result.message == ""
        assert result.is_success is True

    @pytest.mark.unit
    def test_failed_result(self):
        """测试失败结果"""
        result = Result.failed("操作失败：权限不足")

        assert result.status == ResultStatus.FAILED
        assert result.message == "操作失败：权限不足"
        assert result.is_success is False

    @pytest.mark.unit
    def test_not_supported_result(self):
        """测试不支持结果"""
        result = Result.not_supported("此功能在 Windows 上不支持")

        assert result.status == ResultStatus.NOT_SUPPORTED
        assert result.message == "此功能在 Windows 上不支持"
        assert result.is_success is False

    @pytest.mark.unit
    def test_not_supported_default_message(self):
        """测试不支持结果的默认消息"""
        result = Result.not_supported()

        assert result.status == ResultStatus.NOT_SUPPORTED
        assert "不支持" in result.message
        assert result.is_success is False

    @pytest.mark.unit
    def test_result_direct_creation(self):
        """测试直接创建结果"""
        result = Result(status=ResultStatus.SUCCESS, message="直接创建")

        assert result.status == ResultStatus.SUCCESS
        assert result.message == "直接创建"


class TestWindowInfo:
    """WindowInfo 类测试"""

    @pytest.mark.unit
    def test_default_values(self):
        """测试默认值"""
        info = WindowInfo()

        assert info.title is None
        assert info.process is None
        assert info.pid is None

    @pytest.mark.unit
    def test_custom_values(self):
        """测试自定义值"""
        info = WindowInfo(
            title="Visual Studio Code",
            process="code.exe",
            pid=12345,
        )

        assert info.title == "Visual Studio Code"
        assert info.process == "code.exe"
        assert info.pid == 12345

    @pytest.mark.unit
    def test_to_dict(self):
        """测试转换为字典"""
        info = WindowInfo(
            title="Test Window",
            process="test.exe",
            pid=9999,
        )

        result = info.to_dict()

        assert isinstance(result, dict)
        assert result["title"] == "Test Window"
        assert result["process"] == "test.exe"
        assert result["pid"] == 9999

    @pytest.mark.unit
    def test_to_dict_with_none(self):
        """测试包含 None 值时转换为字典"""
        info = WindowInfo(title="Partial Info")

        result = info.to_dict()

        assert result["title"] == "Partial Info"
        assert result["process"] is None
        assert result["pid"] is None


class TestAppInfo:
    """AppInfo 类测试"""

    @pytest.mark.unit
    def test_creation(self):
        """测试创建"""
        info = AppInfo(pid=1234, name="python.exe")

        assert info.pid == 1234
        assert info.name == "python.exe"

    @pytest.mark.unit
    def test_to_dict(self):
        """测试转换为字典"""
        info = AppInfo(pid=5678, name="chrome.exe")

        result = info.to_dict()

        assert isinstance(result, dict)
        assert result["pid"] == 5678
        assert result["name"] == "chrome.exe"


class TestMockPlatformAdapter:
    """Mock 平台适配器测试（使用 conftest 中的 fixture）"""

    @pytest.mark.unit
    def test_platform_name(self, mock_platform_adapter):
        """测试平台名称"""
        assert mock_platform_adapter.platform_name == "mock"

    @pytest.mark.unit
    def test_get_active_window(self, mock_platform_adapter):
        """测试获取活动窗口"""
        window = mock_platform_adapter.get_active_window()

        assert isinstance(window, WindowInfo)
        assert window.title == "Test Window"
        assert window.process == "test.exe"
        assert window.pid == 1234

    @pytest.mark.unit
    def test_get_running_apps(self, mock_platform_adapter):
        """测试获取运行中的应用"""
        apps = mock_platform_adapter.get_running_apps()

        assert isinstance(apps, list)
        assert len(apps) == 2
        assert all(isinstance(app, AppInfo) for app in apps)
        assert apps[0].name == "test.exe"
        assert apps[1].name == "browser.exe"

    @pytest.mark.unit
    def test_get_running_apps_with_limit(self, mock_platform_adapter):
        """测试获取运行中的应用（带数量限制）"""
        apps = mock_platform_adapter.get_running_apps(max_count=1)

        assert len(apps) == 1
        assert apps[0].name == "test.exe"

    @pytest.mark.unit
    def test_enable_autostart(self, mock_platform_adapter):
        """测试启用开机自启"""
        assert mock_platform_adapter.is_autostart_enabled() is False

        result = mock_platform_adapter.enable_autostart()

        assert result.is_success is True
        assert mock_platform_adapter.is_autostart_enabled() is True

    @pytest.mark.unit
    def test_disable_autostart(self, mock_platform_adapter):
        """测试禁用开机自启"""
        # 先启用
        mock_platform_adapter.enable_autostart()
        assert mock_platform_adapter.is_autostart_enabled() is True

        # 再禁用
        result = mock_platform_adapter.disable_autostart()

        assert result.is_success is True
        assert mock_platform_adapter.is_autostart_enabled() is False

    @pytest.mark.unit
    def test_set_autostart_enable(self, mock_platform_adapter):
        """测试 set_autostart 启用"""
        result = mock_platform_adapter.set_autostart(True)

        assert result.is_success is True
        assert mock_platform_adapter.is_autostart_enabled() is True

    @pytest.mark.unit
    def test_set_autostart_disable(self, mock_platform_adapter):
        """测试 set_autostart 禁用"""
        mock_platform_adapter.enable_autostart()

        result = mock_platform_adapter.set_autostart(False)

        assert result.is_success is True
        assert mock_platform_adapter.is_autostart_enabled() is False


class TestIPlatformAdapterInterface:
    """IPlatformAdapter 接口测试"""

    @pytest.mark.unit
    def test_cannot_instantiate_abstract_class(self):
        """测试不能实例化抽象类"""
        with pytest.raises(TypeError):
            IPlatformAdapter()

    @pytest.mark.unit
    def test_abstract_methods(self):
        """测试抽象方法列表"""
        abstract_methods = IPlatformAdapter.__abstractmethods__

        assert "platform_name" in abstract_methods
        assert "get_active_window" in abstract_methods
        assert "get_running_apps" in abstract_methods
        assert "enable_autostart" in abstract_methods
        assert "disable_autostart" in abstract_methods
        assert "is_autostart_enabled" in abstract_methods


class TestPlatformAdapterFactory:
    """平台适配器工厂测试"""

    @pytest.mark.unit
    def test_get_platform_adapter_windows(self):
        """测试 Windows 平台适配器获取"""
        # 由于 get_platform_adapter 使用延迟导入和全局缓存，
        # 我们测试工厂函数的基本行为
        import desktop_client.platforms as platforms_module

        # 重置缓存以便测试
        original_adapter = platforms_module._platform_adapter
        platforms_module._platform_adapter = None

        try:
            with patch("platform.system", return_value="Windows"):
                with patch(
                    "desktop_client.platforms.windows.WindowsPlatformAdapter"
                ) as mock_cls:
                    mock_adapter = MagicMock()
                    mock_adapter.platform_name = "Windows"
                    mock_cls.return_value = mock_adapter

                    adapter = platforms_module.get_platform_adapter()

                    assert adapter is not None
                    mock_cls.assert_called_once()
        finally:
            # 恢复原始缓存
            platforms_module._platform_adapter = original_adapter

    @pytest.mark.unit
    def test_get_platform_adapter_macos(self):
        """测试 macOS 平台适配器获取"""
        import desktop_client.platforms as platforms_module

        original_adapter = platforms_module._platform_adapter
        platforms_module._platform_adapter = None

        try:
            with patch("platform.system", return_value="Darwin"):
                with patch(
                    "desktop_client.platforms.macos.MacOSPlatformAdapter"
                ) as mock_cls:
                    mock_adapter = MagicMock()
                    mock_adapter.platform_name = "macOS"
                    mock_cls.return_value = mock_adapter

                    adapter = platforms_module.get_platform_adapter()

                    assert adapter is not None
                    mock_cls.assert_called_once()
        finally:
            platforms_module._platform_adapter = original_adapter

    @pytest.mark.unit
    def test_get_platform_adapter_linux(self):
        """测试 Linux 平台适配器获取"""
        import desktop_client.platforms as platforms_module

        original_adapter = platforms_module._platform_adapter
        platforms_module._platform_adapter = None

        try:
            with patch("platform.system", return_value="Linux"):
                with patch(
                    "desktop_client.platforms.linux.LinuxPlatformAdapter"
                ) as mock_cls:
                    mock_adapter = MagicMock()
                    mock_adapter.platform_name = "Linux"
                    mock_cls.return_value = mock_adapter

                    adapter = platforms_module.get_platform_adapter()

                    assert adapter is not None
                    mock_cls.assert_called_once()
        finally:
            platforms_module._platform_adapter = original_adapter


class TestPlatformAdapterEdgeCases:
    """平台适配器边界情况测试"""

    @pytest.mark.unit
    def test_window_info_unicode_title(self):
        """测试窗口标题包含 Unicode 字符"""
        info = WindowInfo(
            title="文档 - 记事本 🎉",
            process="notepad.exe",
            pid=1111,
        )

        result = info.to_dict()

        assert result["title"] == "文档 - 记事本 🎉"

    @pytest.mark.unit
    def test_app_info_long_name(self):
        """测试应用名称很长的情况"""
        long_name = "a" * 500 + ".exe"
        info = AppInfo(pid=9999, name=long_name)

        result = info.to_dict()

        assert result["name"] == long_name
        assert len(result["name"]) == 504

    @pytest.mark.unit
    def test_result_unicode_message(self):
        """测试结果消息包含 Unicode 字符"""
        result = Result.failed("失败：文件「配置.json」不存在")

        assert "配置.json" in result.message
        assert result.is_success is False

    @pytest.mark.unit
    def test_empty_running_apps(self, mock_platform_adapter):
        """测试没有运行中应用的情况"""
        mock_platform_adapter._running_apps = []

        apps = mock_platform_adapter.get_running_apps()

        assert isinstance(apps, list)
        assert len(apps) == 0

    @pytest.mark.unit
    def test_autostart_toggle_multiple_times(self, mock_platform_adapter):
        """测试多次切换自启状态"""
        # 初始状态
        assert mock_platform_adapter.is_autostart_enabled() is False

        # 启用 -> 禁用 -> 启用 -> 禁用
        mock_platform_adapter.enable_autostart()
        assert mock_platform_adapter.is_autostart_enabled() is True

        mock_platform_adapter.disable_autostart()
        assert mock_platform_adapter.is_autostart_enabled() is False

        mock_platform_adapter.enable_autostart()
        assert mock_platform_adapter.is_autostart_enabled() is True

        mock_platform_adapter.disable_autostart()
        assert mock_platform_adapter.is_autostart_enabled() is False


class TestWindowInfoComparison:
    """WindowInfo 比较测试"""

    @pytest.mark.unit
    def test_window_info_equality(self):
        """测试窗口信息相等性（dataclass 自动生成）"""
        info1 = WindowInfo(title="Test", process="test.exe", pid=123)
        info2 = WindowInfo(title="Test", process="test.exe", pid=123)

        assert info1 == info2

    @pytest.mark.unit
    def test_window_info_inequality(self):
        """测试窗口信息不相等"""
        info1 = WindowInfo(title="Test1", process="test.exe", pid=123)
        info2 = WindowInfo(title="Test2", process="test.exe", pid=123)

        assert info1 != info2


class TestAppInfoComparison:
    """AppInfo 比较测试"""

    @pytest.mark.unit
    def test_app_info_equality(self):
        """测试应用信息相等性"""
        info1 = AppInfo(pid=123, name="test.exe")
        info2 = AppInfo(pid=123, name="test.exe")

        assert info1 == info2

    @pytest.mark.unit
    def test_app_info_inequality(self):
        """测试应用信息不相等"""
        info1 = AppInfo(pid=123, name="test1.exe")
        info2 = AppInfo(pid=123, name="test2.exe")

        assert info1 != info2
