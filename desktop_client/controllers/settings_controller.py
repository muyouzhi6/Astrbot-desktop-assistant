"""
设置控制器

负责处理设置变化逻辑：
- 服务器配置更新
- 外观配置更新
- 快捷键配置更新
- 交互配置更新
- 主动对话配置更新
- 存储配置更新
- 更新配置更新
"""

import logging
from typing import TYPE_CHECKING, Optional, Any, Dict

from PySide6.QtCore import QObject, Signal

if TYPE_CHECKING:
    from ..config import ClientConfig
    from ..bridge import MessageBridge

logger = logging.getLogger(__name__)


class SettingsController(QObject):
    """设置控制器 - 处理设置变化逻辑"""

    # 信号定义
    reconnect_requested = Signal()  # 请求重连服务器
    config_saved = Signal(bool)  # 配置保存完成，参数为是否成功

    def __init__(
        self,
        config: "ClientConfig",
        bridge: Optional["MessageBridge"] = None,
        floating_ball: Optional[Any] = None,
        proactive_service: Optional[Any] = None,
        chat_history_manager: Optional[Any] = None,
        update_service: Optional[Any] = None,
        parent: Optional[QObject] = None,
    ):
        """
        初始化设置控制器

        Args:
            config: 客户端配置
            bridge: 消息桥接实例
            floating_ball: 悬浮球窗口实例
            proactive_service: 主动对话服务实例
            chat_history_manager: 聊天记录管理器
            update_service: 更新服务实例
            parent: 父对象
        """
        super().__init__(parent)
        self._config = config
        self._bridge = bridge
        self._floating_ball = floating_ball
        self._proactive_service = proactive_service
        self._chat_history_manager = chat_history_manager
        self._update_service = update_service

    def set_bridge(self, bridge: "MessageBridge") -> None:
        """设置消息桥接"""
        self._bridge = bridge

    def set_floating_ball(self, floating_ball: Any) -> None:
        """设置悬浮球实例"""
        self._floating_ball = floating_ball

    def set_proactive_service(self, service: Any) -> None:
        """设置主动对话服务"""
        self._proactive_service = service

    def set_chat_history_manager(self, manager: Any) -> None:
        """设置聊天记录管理器"""
        self._chat_history_manager = manager

    def set_update_service(self, service: Any) -> None:
        """设置更新服务"""
        self._update_service = service

    def on_settings_changed(self, settings: Dict[str, Any]) -> None:
        """
        处理设置变化

        Args:
            settings: 设置字典
        """
        need_reconnect = False

        # 更新服务器配置
        need_reconnect = self._update_server_settings(settings.get("server", {}))

        # 更新外观配置
        self._update_appearance_settings(settings.get("appearance", {}))

        # 更新快捷键配置
        self._update_hotkey_settings(settings.get("hotkeys", {}))

        # 更新交互配置
        self._update_interaction_settings(settings.get("interaction", {}))

        # 更新主动对话配置
        self._update_proactive_settings(settings.get("proactive", {}))

        # 更新存储配置
        self._update_storage_settings(settings.get("storage", {}))

        # 更新更新配置
        self._update_update_settings(settings.get("update", {}))

        # 保存配置到文件
        self._save_config()

        # 如果需要重连，发射信号
        if need_reconnect:
            logger.debug("配置已更新，请求重新连接...")
            self.reconnect_requested.emit()

    def _update_server_settings(self, server: Dict[str, Any]) -> bool:
        """
        更新服务器配置

        Args:
            server: 服务器设置字典

        Returns:
            是否需要重连
        """
        need_reconnect = False

        if "url" in server or "username" in server or "password" in server:
            if self._bridge:
                self._bridge.update_server_config(
                    url=server.get("url"),
                    username=server.get("username"),
                    password=server.get("password"),
                )
            if "url" in server:
                self._config.server.url = server["url"]
            if "username" in server:
                self._config.server.username = server["username"]
            if "password" in server:
                self._config.server.password = server["password"]
            if "enable_streaming" in server:
                self._config.server.enable_streaming = server["enable_streaming"]
            need_reconnect = True

        return need_reconnect

    def _update_appearance_settings(self, appearance: Dict[str, Any]) -> None:
        """
        更新外观配置

        Args:
            appearance: 外观设置字典
        """
        if "theme" in appearance:
            self._config.appearance.theme = appearance["theme"]

        if "avatar_path" in appearance:
            self._config.appearance.avatar_path = appearance["avatar_path"]
            if self._floating_ball:
                self._floating_ball.set_avatar(appearance["avatar_path"])

        if "user_avatar_path" in appearance:
            self._config.appearance.user_avatar_path = appearance["user_avatar_path"]
            if self._floating_ball:
                self._floating_ball.set_user_avatar(appearance["user_avatar_path"])

        if "bot_avatar_path" in appearance:
            self._config.appearance.bot_avatar_path = appearance["bot_avatar_path"]
            if self._floating_ball:
                self._floating_ball.set_bot_avatar(appearance["bot_avatar_path"])

        if "ball_size" in appearance:
            self._config.appearance.ball_size = appearance["ball_size"]

        if "breathing_enabled" in appearance:
            self._config.appearance.breathing_enabled = appearance["breathing_enabled"]
            if self._floating_ball:
                self._floating_ball.set_breathing(appearance["breathing_enabled"])

    def _update_hotkey_settings(self, hotkeys: Dict[str, Any]) -> None:
        """
        更新快捷键配置

        Args:
            hotkeys: 快捷键设置字典
        """
        if "global_enabled" in hotkeys:
            self._config.hotkeys.global_enabled = hotkeys["global_enabled"]

        for key in [
            "toggle_chat",
            "region_screenshot",
            "full_screenshot",
            "toggle_ball",
            "quick_ask",
            "cycle_theme",
        ]:
            if key in hotkeys:
                setattr(self._config.hotkeys, key, hotkeys[key])

    def _update_interaction_settings(self, interaction: Dict[str, Any]) -> None:
        """
        更新交互配置

        Args:
            interaction: 交互设置字典
        """
        if "default_mode" in interaction:
            self._config.interaction.default_mode = interaction["default_mode"]
        if "single_click" in interaction:
            self._config.interaction.single_click = interaction["single_click"]
        if "double_click" in interaction:
            self._config.interaction.double_click = interaction["double_click"]
        if "bubble_duration" in interaction:
            self._config.interaction.bubble_duration = interaction["bubble_duration"]
        if "bubble_auto_hide" in interaction:
            self._config.interaction.bubble_auto_hide = interaction["bubble_auto_hide"]
        if "do_not_disturb" in interaction:
            self._config.interaction.do_not_disturb = interaction["do_not_disturb"]

    def _update_proactive_settings(self, proactive: Dict[str, Any]) -> None:
        """
        更新主动对话配置

        Args:
            proactive: 主动对话设置字典
        """
        if not proactive:
            return

        for key, value in proactive.items():
            if hasattr(self._config.proactive, key):
                setattr(self._config.proactive, key, value)

        # 更新主动对话服务配置
        if self._proactive_service:
            self._proactive_service.update_config(self._config.proactive)
            logger.debug("主动对话服务配置已更新")

    def _update_storage_settings(self, storage: Dict[str, Any]) -> None:
        """
        更新存储配置

        Args:
            storage: 存储设置字典
        """
        if "image_save_path" in storage:
            self._config.storage.image_save_path = storage["image_save_path"]
            logger.debug(f"图片保存路径已更新: {storage['image_save_path']}")

            # 同步更新主动对话服务的截图目录
            if self._proactive_service and storage["image_save_path"]:
                self._proactive_service._screenshot_dir = storage["image_save_path"]
                logger.debug("主动对话服务截图目录已更新")

        if "chat_history_path" in storage:
            new_path = storage["chat_history_path"]
            self._config.storage.chat_history_path = new_path
            logger.debug(f"聊天记录保存路径已更新: {new_path}")

            # 通知 ChatHistoryManager 更新路径
            if self._chat_history_manager:
                try:
                    self._chat_history_manager.set_history_path(new_path)
                    logger.debug("ChatHistoryManager 路径已同步更新")
                except Exception as e:
                    logger.error(f"ChatHistoryManager 路径更新失败: {e}")
                    logger.error(f"ChatHistoryManager 路径更新失败: {e}")

    def _update_update_settings(self, update: Dict[str, Any]) -> None:
        """
        更新更新配置

        Args:
            update: 更新设置字典
        """
        if not update:
            return

        # 更新配置对象
        if "enabled" in update:
            self._config.update.enabled = update["enabled"]
        if "check_on_startup" in update:
            self._config.update.check_on_startup = update["check_on_startup"]
        if "auto_restart" in update:
            self._config.update.auto_restart = update["auto_restart"]
        if "scheduled_times" in update:
            self._config.update.scheduled_times = update["scheduled_times"]

        # 更新更新服务配置
        if self._update_service:
            self._update_service.update_config(self._config.update)

            # 根据配置启动或停止定时检查
            if self._config.update.enabled:
                self._update_service.start_scheduled_checks()
                logger.debug("更新定时检查已启动")
            else:
                self._update_service.stop_scheduled_checks()
                logger.debug("更新定时检查已停止")

        logger.debug(
            f"更新配置已更新: enabled={self._config.update.enabled}, "
            f"scheduled_times={self._config.update.scheduled_times}"
        )

    def _save_config(self) -> None:
        """保存配置到文件"""
        from ..config import save_config, ClientConfig

        logger.debug("保存配置...")
        success = save_config(self._config)
        if success:
            logger.debug(f"配置已保存到: {ClientConfig.get_config_path()}")
        else:
            logger.debug("配置保存失败")

        self.config_saved.emit(success)
