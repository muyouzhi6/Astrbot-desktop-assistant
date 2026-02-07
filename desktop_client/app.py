"""
AstrBot 桌面客户端主应用 (QAsync 重构版)

集成：
- 主题系统
- 快捷键系统
- 两种交互模式（气泡对话、对话窗口）
- 悬浮球
- 系统托盘
- 主动对话服务

重构后的职责：
- 应用初始化和运行逻辑
- 组件组装和连接
- 生命周期管理
"""

import asyncio
import os
import sys
from typing import Optional

from PySide6.QtCore import QTimer, QObject
from PySide6.QtWidgets import QApplication
from qasync import QEventLoop, asyncSlot

from .config import ClientConfig, load_config, save_config
from .bridge import MessageBridge, InputMessage
from .services.proactive_dialog import ProactiveDialogService
from .services import get_chat_history_manager, UpdateService
from .handlers import (
    MessageHandler,
    ScreenshotHandler,
    ProactiveHandler,
    MediaHandler,
    RemoteCommandHandler,
)
from .controllers import SettingsController
from .logger import get_logger


# 获取日志器
logger = get_logger(__name__)


class DesktopClientApp(QObject):
    """桌面客户端应用"""

    def __init__(
        self,
        server_url: Optional[str] = None,
        username: Optional[str] = None,
        password: Optional[str] = None,
    ):
        super().__init__()

        logger.debug("创建 DesktopClientApp 实例")

        # 加载配置
        self.config = load_config()

        # 命令行参数覆盖配置
        if server_url:
            self.config.server.url = server_url
        if username:
            self.config.server.username = username
        if password:
            self.config.server.password = password

        logger.debug(f"最终配置: url={self.config.server.url}")

        # GUI 组件
        self._app: Optional[QApplication] = None
        self._floating_ball = None
        self._settings_window = None
        self._system_tray = None

        # 消息桥接
        self._bridge = MessageBridge(self.config)

        # 快捷键管理器
        self._hotkey_manager = None

        # 主动对话服务
        self._proactive_service = None

        # 更新服务
        self._update_service = None

        # 重连计时器
        self._reconnect_timer: Optional[QTimer] = None
        self._reconnect_attempts = 0

        # 确保 API Client 同步更新（为了兼容旧代码引用）
        self.api_client = self._bridge.api_client

        # 初始化处理器和控制器
        self._init_handlers()

    def _init_handlers(self):
        """初始化处理器和控制器"""
        # 媒体处理器
        self._media_handler = MediaHandler(
            config=self.config, bridge=self._bridge, parent=self
        )

        # 消息处理器
        self._message_handler = MessageHandler(
            config=self.config,
            media_handler=self._media_handler,
            chat_history_manager=None,  # 稍后设置
            parent=self,
        )

        # 截图处理器
        self._screenshot_handler = ScreenshotHandler(config=self.config, parent=self)

        # 主动对话处理器
        self._proactive_handler = ProactiveHandler(
            config=self.config,
            bridge=self._bridge,
            message_handler=self._message_handler,
            parent=self,
        )

        # 远程命令处理器
        self._remote_command_handler = RemoteCommandHandler(
            config=self.config, bridge=self._bridge, parent=self
        )

        # 设置控制器
        self._settings_controller = SettingsController(
            config=self.config, bridge=self._bridge, parent=self
        )

        # 连接信号
        self._bridge.message_received.connect(
            self._message_handler.handle_output_message
        )
        self._bridge.connection_state_changed.connect(self._on_connection_state_changed)
        self._screenshot_handler.proactive_screenshot_completed.connect(
            self._proactive_handler.handle_proactive_screenshot_complete
        )
        self._settings_controller.reconnect_requested.connect(
            lambda: asyncio.ensure_future(self._reconnect_server())
        )

    def _is_autostart_launch(self) -> bool:
        """检测是否为开机自启启动

        通过以下方式检测：
        1. 命令行参数 --autostart
        2. 环境变量 ASTRBOT_AUTOSTART
        3. 系统启动时间判断（如果系统启动不足5分钟，可能是开机自启）
        """
        import time

        # 方式1：检查命令行参数
        if "--autostart" in sys.argv:
            return True

        # 方式2：检查环境变量
        if os.environ.get("ASTRBOT_AUTOSTART") == "1":
            return True

        # 方式3：检查系统启动时间（仅限有 psutil 的情况）
        try:
            import psutil

            boot_time = psutil.boot_time()
            uptime = time.time() - boot_time
            # 如果系统启动不足3分钟，很可能是开机自启
            if uptime < 180:
                logger.debug(f"系统启动时间 {uptime:.1f} 秒，判断为开机自启")
                return True
        except ImportError:
            pass
        except Exception as e:
            logger.debug(f"检测系统启动时间失败: {e}")

        return False

    def run(self):
        """运行应用"""
        logger.debug("应用启动 - run() 开始")

        # 1. 初始化 Qt 应用
        self._app = QApplication.instance()  # type: ignore
        if not self._app:
            self._app = QApplication(sys.argv)
        if self._app:
            self._app.setQuitOnLastWindowClosed(False)

        # 2. 启用 QSS 主题系统并从配置加载主题
        logger.info("启用 QSS 主题系统")
        from .gui.themes import theme_manager

        theme_manager.enable_qss_mode(True)
        # 从配置加载保存的主题，如果没有则使用默认主题
        saved_theme = "macos_light"  # 默认主题
        if hasattr(self.config, "appearance") and self.config.appearance.theme:
            saved_theme = self.config.appearance.theme
        theme_manager.set_theme(saved_theme)
        if self._app:
            theme_manager.apply_global_stylesheet(self._app)
        logger.info(
            f"已启用主题 '{saved_theme}'，QSS 长度：{len(theme_manager.get_global_qss())}"
        )

        # 3. 设置 qasync 事件循环
        logger.debug("设置 qasync 事件循环")
        loop = QEventLoop(self._app)
        asyncio.set_event_loop(loop)

        # 3. 初始化 GUI
        logger.debug("初始化 GUI")
        self._init_gui()

        # 4. 初始化快捷键
        logger.debug("初始化快捷键")
        self._init_hotkeys()

        # 5. 启动初始任务
        logger.debug("启动初始任务")
        asyncio.ensure_future(self._startup())

        # 6. 运行事件循环
        logger.info("进入事件循环")
        with loop:
            loop.run_forever()

    async def _startup(self):
        """启动时异步任务"""
        if self.config.server.auto_reconnect:
            # 计算总启动延迟
            startup_delay = self.config.server.startup_delay

            # 检测是否为开机自启（通过命令行参数或环境变量）
            is_autostart = self._is_autostart_launch()
            if is_autostart:
                extra_delay = getattr(self.config.server, "autostart_extra_delay", 10)
                startup_delay += extra_delay
                logger.info(f"检测到开机自启，增加额外延迟 {extra_delay} 秒")

            if startup_delay > 0:
                logger.info(f"启动延迟 {startup_delay} 秒后连接服务器")
                await asyncio.sleep(startup_delay)

            await self._reconnect_server()

            if self._bridge.is_connected and self.config.proactive.enabled:
                if self._proactive_service:
                    self._proactive_service.start()
                    logger.info("主动对话服务已启动")
        else:
            logger.warning("自动连接已禁用")

    async def _reconnect_server(self):
        """重新连接服务器"""
        logger.debug("尝试连接服务器")
        success, msg = await self._bridge.connect_server()
        if success:
            logger.info(f"服务器连接成功: {msg}")
            self._reconnect_attempts = 0
            # 注意：连接成功的系统消息由 message_handler._handle_status_message() 统一处理
            # 避免重复显示"已连接到服务器"消息

            if self.config.proactive.enabled and self._proactive_service:
                if not self._proactive_service.is_running:
                    self._proactive_service.start()
                    logger.debug("主动对话服务已启动")

            # 启动 WebSocket 连接（用于接收远程命令）
            await self._start_websocket_connection()
        else:
            logger.error(f"服务器连接失败: {msg}")
            if self._floating_ball:
                self._floating_ball.show_system_message(f"连接失败: {msg}")

            if self._proactive_service and self._proactive_service.is_running:
                self._proactive_service.stop()
                logger.debug("主动对话服务已停止（连接失败）")

            self._schedule_reconnect()

    async def _start_websocket_connection(self):
        """启动 WebSocket 连接（用于接收服务端下发的命令）"""
        # 使用配置中的 session_id，如果为空则生成一个临时的
        session_id = self.config.session_id
        if not session_id:
            import uuid

            session_id = f"desktop_{uuid.uuid4().hex[:8]}"
            logger.debug(f"未设置 session_id，使用临时 ID: {session_id}")

        try:
            # 定义远程命令处理回调
            async def on_remote_command(command: str, request_id: str, params: dict):
                """处理远程命令并返回结果"""
                return await self._remote_command_handler.handle_command(
                    command, request_id, params
                )

            # 定义连接状态回调，用于在连接成功后同步配置
            def on_connection_state(state: str):
                """连接状态变化回调"""
                logger.debug(f"WebSocket 连接状态变化: {state}")
                if state == "connected":
                    # 连接成功后，异步发送配置同步消息
                    asyncio.ensure_future(self._sync_config_to_server())

            # 启动 WebSocket 客户端，同时传入消息和命令处理回调
            # 注意：优先使用自定义 ws_url，否则使用 ws_port 连接
            ws_url = self.config.server.ws_url if self.config.server.ws_url else None
            logger.info(
                f"启动 WebSocket 连接 - 服务器: {self.config.server.url}, "
                f"自定义WS地址: {ws_url or '无'}, WS端口: {self.config.server.ws_port}, Session: {session_id}"
            )

            await self._bridge.api_client.start_websocket(
                session_id=session_id,
                on_message=self._on_websocket_message,
                on_command=on_remote_command,
                ws_port=self.config.server.ws_port,
                ws_url=ws_url,
            )

            # 设置连接状态回调
            if self._bridge.api_client.ws_client:
                self._bridge.api_client.ws_client.on_connection_state = (
                    on_connection_state
                )

            logger.info("WebSocket 连接启动成功，可接收远程命令")

        except Exception as e:
            logger.warning(f"启动 WebSocket 连接失败: {e}")
            import traceback

            traceback.print_exc()

            # 启动一个延时重试任务
            logger.debug("5秒后重试启动 WebSocket 连接")
            asyncio.get_running_loop().call_later(
                5, lambda: asyncio.ensure_future(self._start_websocket_connection())
            )

    async def _sync_config_to_server(self):
        """同步客户端配置到服务端

        在 WebSocket 连接成功后调用，将客户端保存的设置（如 TTS dual_output）
        发送给服务端，由服务端应用到 AstrBot 核心配置。
        """
        try:
            ws_client = self._bridge.api_client.ws_client
            if not ws_client or not ws_client.is_connected:
                logger.warning("无法同步配置：WebSocket 未连接")
                return

            # 构建配置同步消息
            config_sync_data = {
                "type": "config_sync",
                "data": {
                    "voice": {
                        "enable_tts": self.config.voice.enable_tts,
                        "auto_play_voice": self.config.voice.auto_play_voice,
                        "dual_output": self.config.voice.dual_output,
                    },
                    # 可以扩展其他需要同步的配置
                },
            }

            await ws_client.send(config_sync_data)
            logger.debug(
                f"配置同步消息已发送: dual_output={self.config.voice.dual_output}"
            )

        except Exception as e:
            logger.warning(f"同步配置到服务端失败: {e}")
            import traceback

            traceback.print_exc()

    def _on_websocket_message(self, data: dict):
        """处理 WebSocket 消息"""
        msg_type = data.get("type")

        if msg_type == "message":
            # 处理服务端推送的消息
            content = data.get("content", "")
            if content and self._floating_ball:
                self._floating_ball.show_bubble(content)
        elif msg_type == "notification":
            # 处理通知消息
            content = data.get("content", "")
            if content and self._floating_ball:
                self._floating_ball.show_system_message(content)

    def _on_connection_state_changed(self, state):
        """处理连接状态变化"""
        from .api_client import ConnectionState

        logger.debug(f"连接状态变化: {state}")

        if state == ConnectionState.DISCONNECTED:
            if self.config.server.auto_reconnect:
                self._schedule_reconnect()
        elif state == ConnectionState.CONNECTED:
            self._cancel_reconnect()

    def _schedule_reconnect(self):
        """调度自动重连"""
        max_attempts = self.config.server.max_reconnect_attempts
        if max_attempts > 0 and self._reconnect_attempts >= max_attempts:
            logger.debug(f"已达到最大重连次数 ({max_attempts})，停止重连")
            if self._floating_ball:
                self._floating_ball.show_system_message("连接失败，已达最大重试次数")
            return

        base_interval = self.config.server.reconnect_interval
        interval = min(base_interval * (2**self._reconnect_attempts), 60)

        logger.debug(
            f"将在 {interval} 秒后尝试重连 (第 {self._reconnect_attempts + 1} 次)"
        )

        self._cancel_reconnect()

        self._reconnect_timer = QTimer()
        self._reconnect_timer.setSingleShot(True)
        self._reconnect_timer.timeout.connect(self._do_reconnect)
        self._reconnect_timer.start(int(interval * 1000))

        self._reconnect_attempts += 1

    def _cancel_reconnect(self):
        """取消重连定时器"""
        if self._reconnect_timer:
            self._reconnect_timer.stop()
            self._reconnect_timer = None

    def _do_reconnect(self):
        """执行重连"""
        logger.debug("执行自动重连...")
        asyncio.ensure_future(self._reconnect_server())

    def _init_gui(self):
        """初始化 GUI 组件"""
        logger.debug("_init_gui 开始")

        # 导入主题管理器
        from .gui.themes import theme_manager

        # 加载保存的主题
        if hasattr(self.config, "appearance") and self.config.appearance.theme:
            theme_manager.set_theme(self.config.appearance.theme)

        # 应用自定义颜色配置
        if hasattr(self.config, "appearance") and hasattr(
            self.config.appearance, "custom_theme"
        ):
            try:
                theme_manager.apply_custom_colors(self.config.appearance.custom_theme)
                logger.debug("自定义颜色配置已应用")
            except Exception as e:
                logger.warning(f"应用自定义颜色配置失败，使用默认主题: {e}")

        # 创建悬浮球
        logger.debug("创建悬浮球...")
        from .gui.floating_ball import FloatingBallWindow

        self._floating_ball = FloatingBallWindow(config=self.config)
        self._floating_ball.clicked.connect(self._on_ball_clicked)
        self._floating_ball.double_clicked.connect(self._on_ball_double_clicked)
        self._floating_ball.settings_requested.connect(self._show_settings)
        self._floating_ball.restart_requested.connect(self._restart)
        self._floating_ball.quit_requested.connect(self._quit)
        self._floating_ball.screenshot_requested.connect(
            self._screenshot_handler.on_screenshot
        )
        self._floating_ball.message_sent.connect(self._on_message_sent)
        self._floating_ball.image_sent.connect(self._on_image_sent)
        self._floating_ball.show()
        logger.debug("悬浮球创建完成并显示")

        # 更新处理器的悬浮球引用
        self._message_handler.set_floating_ball(self._floating_ball)
        self._media_handler.set_floating_ball(self._floating_ball)
        self._screenshot_handler.set_floating_ball(self._floating_ball)
        self._proactive_handler.set_floating_ball(self._floating_ball)
        self._settings_controller.set_floating_ball(self._floating_ball)
        self._remote_command_handler.set_floating_ball(self._floating_ball)

        # 创建系统托盘
        logger.debug("创建系统托盘...")
        from .gui.system_tray import SystemTrayIcon

        if self._app is None:
            raise RuntimeError("QApplication not initialized")
        self._system_tray = SystemTrayIcon(self._app)
        self._system_tray.show_chat_requested.connect(self._show_bubble_input)
        self._system_tray.show_settings_requested.connect(self._show_settings)
        self._system_tray.quit_requested.connect(self._quit)
        self._system_tray.show()
        logger.debug("系统托盘创建完成")

        # 确保存储目录结构存在
        self._media_handler.ensure_storage_dirs()

        # 初始化聊天记录管理器
        chat_history_path = self.config.storage.chat_history_path
        chat_history_manager = get_chat_history_manager(chat_history_path)
        self._message_handler.set_chat_history_manager(chat_history_manager)
        self._media_handler.set_chat_history_manager(chat_history_manager)
        self._settings_controller.set_chat_history_manager(chat_history_manager)

        # 创建设置窗口
        logger.debug("创建设置窗口...")
        from .gui.settings_window import SettingsWindow

        self._settings_window = SettingsWindow(config=self.config)
        self._settings_window.settings_changed.connect(
            self._settings_controller.on_settings_changed
        )
        logger.debug("设置窗口创建完成")

        # 创建更新服务并绑定到设置窗口
        logger.debug("创建更新服务...")
        self._update_service = UpdateService(config=self.config.update, parent=self)
        self._settings_window.set_update_callbacks(
            check_callback=self._on_check_update,
            perform_callback=self._on_perform_update,
        )

        # 连接更新服务信号
        self._update_service.update_available.connect(self._on_update_available)
        self._update_service.check_finished.connect(self._on_update_check_finished)

        # 启动时检查更新（如果配置启用）
        if self.config.update.check_on_startup:
            logger.debug("启动时检查更新已启用，将在启动后检查更新")
            # 延迟检查，等待应用完全启动
            QTimer.singleShot(5000, self._startup_update_check)

        # 启动定时更新检查（如果配置启用）
        if self.config.update.enabled and self.config.update.scheduled_times:
            logger.debug(f"启动定时更新检查，时间点: {self.config.update.scheduled_times}")
            self._update_service.start_scheduled_checks()

        logger.debug("更新服务创建完成")

        # 创建主动对话服务
        logger.debug("创建主动对话服务...")
        if self.config.storage.image_save_path:
            screenshot_dir = self.config.storage.image_save_path
        else:
            screenshot_dir = os.path.join(
                str(ClientConfig.get_config_dir()), "screenshots"
            )

        self._proactive_service = ProactiveDialogService(
            config=self.config.proactive, screenshot_dir=screenshot_dir, parent=self
        )
        self._proactive_service.dialog_triggered.connect(
            self._proactive_handler.on_proactive_dialog_triggered
        )
        self._settings_controller.set_proactive_service(self._proactive_service)
        logger.debug("主动对话服务创建完成")

        logger.debug("_init_gui 完成")

    def _init_hotkeys(self):
        """初始化快捷键"""
        from .gui.hotkeys import hotkey_manager

        self._hotkey_manager = hotkey_manager

        if self._floating_ball:
            self._hotkey_manager.set_parent_widget(self._floating_ball)

        self._hotkey_manager.toggle_chat_triggered.connect(self._toggle_chat_window)
        self._hotkey_manager.region_screenshot_triggered.connect(
            lambda: self._screenshot_handler.on_screenshot("region")
        )
        self._hotkey_manager.full_screenshot_triggered.connect(
            lambda: self._screenshot_handler.on_screenshot("full")
        )
        self._hotkey_manager.toggle_ball_triggered.connect(self._toggle_floating_ball)
        self._hotkey_manager.quick_ask_triggered.connect(self._show_quick_ask)
        self._hotkey_manager.cycle_theme_triggered.connect(self._cycle_theme)

    # ==================== 事件处理 ====================

    def _on_ball_clicked(self):
        """悬浮球单击 - 切换气泡对话显示/隐藏"""
        if self._floating_ball and self._floating_ball.has_unread_message():
            self._floating_ball.clear_unread_message()

        if self._floating_ball:
            self._floating_ball.toggle_input()

    def _on_ball_double_clicked(self):
        """悬浮球双击：截图并触发主动对话"""
        if self._floating_ball and self._floating_ball.has_unread_message():
            self._floating_ball.clear_unread_message()

        logger.debug("悬浮球双击：触发主动对话截图...")
        self._screenshot_handler.do_proactive_screenshot()

    def _show_bubble_input(self):
        """显示气泡输入"""
        if self._floating_ball:
            self._floating_ball.show_input()

    def _show_chat_window(self):
        """显示对话窗口 (兼容旧接口)"""
        self._show_bubble_input()

    def _toggle_chat_window(self):
        """切换对话窗口显示 (兼容旧接口)"""
        self._show_bubble_input()

    def _toggle_floating_ball(self):
        """切换悬浮球显示"""
        if self._floating_ball:
            if self._floating_ball.isVisible():
                self._floating_ball.hide()
            else:
                self._floating_ball.show()

    def _show_quick_ask(self):
        """显示快速提问"""
        self._show_bubble_input()

    def _cycle_theme(self):
        """循环切换主题"""
        from .gui.themes import theme_manager

        theme_manager.cycle_theme()

    @asyncSlot(str)
    async def _on_message_sent(self, message: str):
        """处理发送的消息 (Async Slot)"""
        await self._bridge.send_input(
            InputMessage(
                msg_type="text",
                content=message,
                session_id=self.config.session_id or "",
            )
        )

    @asyncSlot(str, str)
    async def _on_image_sent(self, image_path: str, text: str = ""):
        """处理发送的图片消息 (Async Slot)"""
        await self._bridge.send_input(
            InputMessage(
                msg_type="image",
                content=image_path,
                session_id=self.config.session_id or "",
                metadata={"text": text},
            )
        )

    def _show_settings(self):
        """显示设置窗口"""
        if self._settings_window:
            self._settings_window.show()
            self._settings_window.raise_()
            self._settings_window.activateWindow()

    def _on_check_update(self):
        """检查更新回调"""
        if self._update_service:
            asyncio.ensure_future(self._do_check_update())

    def _startup_update_check(self):
        """启动时的更新检查"""
        logger.debug("执行启动时更新检查...")
        if self._update_service:
            asyncio.ensure_future(self._do_check_update(silent=True))

    def _on_update_available(self, current_version: str, latest_version: str):
        """发现新版本时的回调"""
        logger.info(f"发现新版本: {current_version} -> {latest_version}")
        if self._floating_ball:
            self._floating_ball.show_system_message(
                f"发现新版本 {latest_version}，可在设置中更新"
            )

    def _on_update_check_finished(self, has_update: bool, message: str):
        """更新检查完成回调"""
        logger.debug(f"更新检查完成: has_update={has_update}, message={message}")

    async def _do_check_update(self, silent: bool = False):
        """异步执行更新检查

        Args:
            silent: 是否静默模式（不显示"已是最新版本"提示）
        """
        if not self._update_service:
            return

        try:
            has_update, current, latest = await self._update_service.check_for_update()

            if self._settings_window:
                # 使用公共方法更新版本信息
                from datetime import datetime

                self._settings_window.update_version_info(
                    current_version=current,
                    last_check_time=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                )

                if has_update:
                    # 使用 _on_check_update_done 回调方法
                    self._settings_window._on_check_update_done(
                        has_update=True, message=f"发现新版本: {latest}"
                    )
                elif not silent:
                    # 非静默模式才显示"已是最新版本"
                    self._settings_window._on_check_update_done(
                        has_update=False, message="已是最新版本"
                    )

            # 保存更新检查时间到配置
            from datetime import datetime
            self.config.update.last_check_time = datetime.now().isoformat()
            save_config(self.config)

        except Exception as e:
            logger.error(f"检查更新失败: {e}")
            if self._settings_window and not silent:
                self._settings_window._on_check_update_done(
                    has_update=False, message=f"检查失败: {e}"
                )

    def _on_perform_update(self):
        """执行更新回调"""
        if self._update_service:
            success = self._update_service.perform_update()
            if success:
                logger.debug("更新脚本已启动")
            else:
                logger.error("启动更新脚本失败")

    def _restart(self):
        """重启应用"""
        import subprocess

        logger.debug("正在重启应用...")

        if save_config(self.config):
            logger.debug("配置已保存")

        if self._hotkey_manager:
            self._hotkey_manager.cleanup()

        if self._proactive_service:
            self._proactive_service.stop()

        python = sys.executable
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

        try:
            if os.name == "nt":
                subprocess.Popen(
                    [python, "-m", "desktop_client"],
                    cwd=project_root,
                    creationflags=subprocess.CREATE_NEW_PROCESS_GROUP,
                )
            else:
                subprocess.Popen([python, "-m", "desktop_client"], cwd=project_root)
            logger.debug("新进程已启动")
        except Exception as e:
            logger.error(f"重启失败: {e}")
            return

        if self._app:
            self._app.quit()

    def _quit(self):
        """退出应用"""
        if self._proactive_service:
            self._proactive_service.stop()
            logger.debug("主动对话服务已停止")

        self._cancel_reconnect()

        if self._hotkey_manager:
            self._hotkey_manager.cleanup()

        asyncio.ensure_future(self._bridge.disconnect_server())

        if self._app:
            self._app.quit()


def main():
    """入口函数"""
    import argparse
    import traceback

    logger.debug("main() 函数开始执行")

    try:
        parser = argparse.ArgumentParser(description="AstrBot Desktop Client")
        parser.add_argument("-s", "--server", help="Server URL")
        parser.add_argument("-u", "--username", help="Username")
        parser.add_argument("-p", "--password", help="Password")
        parser.add_argument("--autostart", action="store_true", help="开机自启模式")

        args = parser.parse_args()
        logger.debug(f"命令行参数解析完成: autostart={args.autostart}")

        # 如果是开机自启模式，额外等待一下确保系统完全就绪
        if args.autostart:
            import time
            logger.info("检测到开机自启模式，等待 5 秒确保系统环境就绪...")
            time.sleep(5)

        logger.debug("准备创建 DesktopClientApp 实例...")
        app = DesktopClientApp(
            server_url=args.server, username=args.username, password=args.password
        )
        logger.debug("DesktopClientApp 实例创建成功")

        import signal

        signal.signal(signal.SIGINT, lambda *args: app._quit())

        logger.debug("准备调用 app.run()...")
        app.run()
        logger.debug("app.run() 执行完毕")

    except Exception as e:
        logger.error(f"main() 函数发生异常: {e}")
        logger.error(f"异常详情:\n{traceback.format_exc()}")

        # 写入错误日志文件，便于调试开机自启问题
        try:
            from .config import ClientConfig
            config_dir = ClientConfig.get_config_dir()
            error_log_path = config_dir / "autostart_crash.log"
            with open(error_log_path, "a", encoding="utf-8") as f:
                import datetime
                f.write(f"\n{'='*50}\n")
                f.write(f"崩溃时间: {datetime.datetime.now()}\n")
                f.write(f"异常类型: {type(e).__name__}\n")
                f.write(f"异常消息: {e}\n")
                f.write(f"详细堆栈:\n{traceback.format_exc()}\n")
            logger.info(f"错误日志已写入: {error_log_path}")
        except Exception as log_error:
            logger.error(f"写入错误日志失败: {log_error}")

        raise


if __name__ == "__main__":
    main()
