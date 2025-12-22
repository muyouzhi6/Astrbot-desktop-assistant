"""
AstrBot 桌面客户端主应用 (QAsync 重构版)

集成：
- 主题系统
- 快捷键系统
- 两种交互模式（气泡对话、对话窗口）
- 悬浮球
- 系统托盘
- 主动对话服务
"""

import asyncio
import logging
import os
import sys
from typing import Optional
from dataclasses import dataclass

from PySide6.QtCore import Qt, QTimer, Slot, QObject
from PySide6.QtWidgets import QApplication
from qasync import QEventLoop, asyncSlot

from .api_client import AstrBotApiClient
from .config import ClientConfig, load_config, save_config
from .bridge import MessageBridge, InputMessage, OutputMessage
from .services.proactive_dialog import ProactiveDialogService


# 配置日志
logger = logging.getLogger(__name__)


class DesktopClientApp(QObject):
    """桌面客户端应用"""
    
    def __init__(self, server_url: Optional[str] = None, username: Optional[str] = None, password: Optional[str] = None):
        super().__init__()
        
        print("[DEBUG] 创建 DesktopClientApp 实例...")
        
        # 加载配置
        self.config = load_config()
        
        # 命令行参数覆盖配置
        if server_url:
            self.config.server.url = server_url
        if username:
            self.config.server.username = username
        if password:
            self.config.server.password = password
            
        print(f"[DEBUG] 最终配置: url={self.config.server.url}")
        
        # GUI 组件
        self._app: Optional[QApplication] = None
        self._floating_ball = None
        self._chat_window = None
        self._settings_window = None
        self._system_tray = None
        
        # 消息桥接
        self._bridge = MessageBridge(self.config)
        self._bridge.message_received.connect(self._handle_output_message)
        
        # 快捷键管理器
        self._hotkey_manager = None
        
        # 主动对话服务
        self._proactive_service = None

        # 确保 API Client 同步更新（为了兼容旧代码引用）
        self.api_client = self._bridge.api_client
        
    def run(self):
        """运行应用"""
        print("[DEBUG] run() 开始")
        
        # 1. 初始化 Qt 应用
        self._app = QApplication.instance()
        if not self._app:
            self._app = QApplication(sys.argv)
        if self._app:
            self._app.setQuitOnLastWindowClosed(False)
        
        # 2. 设置 qasync 事件循环
        print("[DEBUG] 设置 qasync 事件循环...")
        loop = QEventLoop(self._app)
        asyncio.set_event_loop(loop)
        
        # 3. 初始化 GUI
        print("[DEBUG] 初始化 GUI...")
        self._init_gui()
        
        # 4. 初始化快捷键
        print("[DEBUG] 初始化快捷键...")
        self._init_hotkeys()
        
        # 5. 启动初始任务
        print("[DEBUG] 启动初始任务...")
        asyncio.ensure_future(self._startup())
        
        # 6. 运行事件循环
        print("[DEBUG] 进入事件循环...")
        with loop:
            loop.run_forever()
            
    async def _startup(self):
        """启动时异步任务"""
        # 检查自动连接
        if self.config.server.auto_reconnect:
            await self._reconnect_server()
            
            # 如果连接成功且启用了主动对话，启动主动对话服务
            if self._bridge.is_connected and self.config.proactive.enabled:
                if self._proactive_service:
                    self._proactive_service.start()
                    print("[DEBUG] 主动对话服务已启动")
        else:
            print("[DEBUG] 自动连接已禁用")

    async def _reconnect_server(self):
        """重新连接服务器"""
        print("[DEBUG] 尝试连接服务器...")
        success, msg = await self._bridge.connect_server()
        if success:
            print(f"[DEBUG] 连接成功: {msg}")
            if self._floating_ball:
                self._floating_ball.show_bubble("已连接到服务器")
            
            # 连接成功后，如果启用了主动对话，启动服务
            if self.config.proactive.enabled and self._proactive_service:
                if not self._proactive_service.is_running:
                    self._proactive_service.start()
                    print("[DEBUG] 主动对话服务已启动")
        else:
            print(f"[DEBUG] 连接失败: {msg}")
            if self._floating_ball:
                self._floating_ball.show_bubble(f"连接失败: {msg}")
            
            # 连接失败，停止主动对话服务
            if self._proactive_service and self._proactive_service.is_running:
                self._proactive_service.stop()
                print("[DEBUG] 主动对话服务已停止（连接失败）")

    def _init_gui(self):
        """初始化 GUI 组件"""
        print("[DEBUG] _init_gui 开始")
        
        # 导入主题管理器
        from .gui.themes import theme_manager
        
        # 加载保存的主题
        if hasattr(self.config, 'appearance') and self.config.appearance.theme:
            theme_manager.set_theme(self.config.appearance.theme)
        
        # 创建悬浮球
        print("[DEBUG] 创建悬浮球...")
        from .gui.floating_ball import FloatingBallWindow
        self._floating_ball = FloatingBallWindow(config=self.config)
        self._floating_ball.clicked.connect(self._on_ball_clicked)
        self._floating_ball.double_clicked.connect(self._on_ball_double_clicked)
        self._floating_ball.settings_requested.connect(self._show_settings)
        self._floating_ball.restart_requested.connect(self._restart)
        self._floating_ball.quit_requested.connect(self._quit)
        self._floating_ball.screenshot_requested.connect(self._on_screenshot)
        self._floating_ball.message_sent.connect(self._on_message_sent)
        self._floating_ball.image_sent.connect(self._on_image_sent)
        self._floating_ball.show()
        print("[DEBUG] 悬浮球创建完成并显示")
        
        # 创建对话窗口
        print("[DEBUG] 创建对话窗口...")
        from .gui.simple_chat_window import SimpleChatWindow
        self._chat_window = SimpleChatWindow(api_client=self._bridge.api_client)
        self._chat_window.message_sent.connect(self._on_message_sent)
        self._chat_window.image_sent.connect(self._on_image_sent)
        self._chat_window.screenshot_requested.connect(self._on_screenshot)
        print("[DEBUG] 对话窗口创建完成")
        
        # 创建系统托盘
        print("[DEBUG] 创建系统托盘...")
        from .gui.system_tray import SystemTrayIcon
        self._system_tray = SystemTrayIcon(self._app)
        self._system_tray.show_chat_requested.connect(self._show_chat_window)
        self._system_tray.show_settings_requested.connect(self._show_settings)
        self._system_tray.quit_requested.connect(self._quit)
        self._system_tray.show()
        print("[DEBUG] 系统托盘创建完成")
        
        # 创建设置窗口
        print("[DEBUG] 创建设置窗口...")
        from .gui.settings_window import SettingsWindow
        self._settings_window = SettingsWindow(config=self.config)
        self._settings_window.settings_changed.connect(self._on_settings_changed)
        print("[DEBUG] 设置窗口创建完成")
        
        # 创建主动对话服务
        print("[DEBUG] 创建主动对话服务...")
        
        # 使用配置的存储路径，如果未设置则使用默认路径
        if self.config.storage.image_save_path:
            screenshot_dir = self.config.storage.image_save_path
        else:
            screenshot_dir = os.path.join(str(ClientConfig.get_config_dir()), "screenshots")
            
        self._proactive_service = ProactiveDialogService(
            config=self.config.proactive,
            screenshot_dir=screenshot_dir,
            parent=self
        )
        self._proactive_service.dialog_triggered.connect(self._on_proactive_dialog_triggered)
        print("[DEBUG] 主动对话服务创建完成")
        
        print("[DEBUG] _init_gui 完成")
        
    def _init_hotkeys(self):
        """初始化快捷键"""
        from .gui.hotkeys import hotkey_manager
        
        self._hotkey_manager = hotkey_manager
        
        # 设置父窗口以启用 Qt 快捷键
        if self._floating_ball:
            self._hotkey_manager.set_parent_widget(self._floating_ball)
        
        # 连接信号
        self._hotkey_manager.toggle_chat_triggered.connect(self._toggle_chat_window)
        self._hotkey_manager.region_screenshot_triggered.connect(lambda: self._on_screenshot("region"))
        self._hotkey_manager.full_screenshot_triggered.connect(lambda: self._on_screenshot("full"))
        self._hotkey_manager.toggle_ball_triggered.connect(self._toggle_floating_ball)
        self._hotkey_manager.quick_ask_triggered.connect(self._show_quick_ask)
        self._hotkey_manager.cycle_theme_triggered.connect(self._cycle_theme)
        
    @asyncSlot(str)
    async def _on_proactive_dialog_triggered(self, screenshot_path: str):
        """
        处理主动对话触发
        
        当主动对话服务检测到触发条件满足时调用此方法。
        
        Args:
            screenshot_path: 截图文件路径
        """
        logger.info(f"主动对话触发: {screenshot_path}")
        print(f"[DEBUG] 主动对话触发: {screenshot_path}")
        
        # 检查是否已连接
        if not self._bridge.is_connected:
            logger.warning("未连接到服务器，跳过主动对话")
            print("[DEBUG] 未连接到服务器，跳过主动对话")
            return
        
        # 检查是否有有效会话
        if not self.config.session_id:
            logger.warning("没有有效会话，跳过主动对话")
            print("[DEBUG] 没有有效会话，跳过主动对话")
            return
        
        try:
            # 使用配置的提示词模板
            prompt = self.config.proactive.prompt_template
            
            logger.debug(f"发送主动对话截图: {screenshot_path}")
            print(f"[DEBUG] 发送主动对话截图: {screenshot_path}")
            
            # 标记这是主动对话的消息，用于后续处理响应
            self._proactive_dialog_pending = True
            
            # 发送图片消息到 AI
            await self._bridge.send_input(InputMessage(
                msg_type="image",
                content=screenshot_path,
                session_id=self.config.session_id,
                metadata={
                    "text": prompt,
                    "proactive": True,  # 标记为主动对话
                }
            ))
            
        except Exception as e:
            logger.error(f"主动对话发送失败: {e}")
            print(f"[ERROR] 主动对话发送失败: {e}")
            self._proactive_dialog_pending = False
    
    @Slot(object)
    def _handle_output_message(self, message: OutputMessage):
        """处理接收到的消息 (Slot)"""
        msg_type = message.msg_type
        content = message.content
        
        # 检查是否是主动对话的响应
        is_proactive_response = getattr(self, '_proactive_dialog_pending', False)
        
        if msg_type == "text":
            # 忽略空消息
            if not content:
                return
            
            # 主动对话响应：只在气泡中显示，不添加到对话窗口历史
            if is_proactive_response:
                if message.streaming:
                    # 流式响应时累积内容
                    if not hasattr(self, '_proactive_response_buffer'):
                        self._proactive_response_buffer = ""
                    self._proactive_response_buffer += content
                else:
                    # 非流式完整响应
                    if self._floating_ball:
                        self._floating_ball.show_bubble(content)
                        # 触发未读消息动态效果
                        self._floating_ball.set_unread_message(True)
                    self._proactive_dialog_pending = False
                return
                
            if message.streaming:
                # 流式响应
                if self._chat_window:
                    if not self._chat_window._current_ai_bubble:
                        self._chat_window.start_ai_response()
                    self._chat_window.update_ai_response(content)
                    
                # 同时更新气泡输入框的响应显示（如果正在等待响应）
                if self._floating_ball and self._floating_ball.is_waiting_response():
                    self._floating_ball.update_streaming_response(content)
            else:
                # 完整响应（非流式）
                if self._chat_window:
                    self._chat_window.add_ai_message(content)
                
                # 同时更新气泡输入框的响应显示
                if self._floating_ball:
                    if self._floating_ball.is_waiting_response():
                        self._floating_ball.update_streaming_response(content)
                        self._floating_ball.finish_response()
                    else:
                        # 在气泡中显示摘要
                        summary = content[:100] + "..." if len(content) > 100 else content
                        self._floating_ball.show_bubble(summary)
                    
        elif msg_type == "image":
            # AI 返回的图片
            self._handle_image_response(content, message.metadata)
                    
        elif msg_type == "voice":
            # AI 返回的语音
            self._handle_voice_response(content, message.metadata)
                    
        elif msg_type == "end":
            # 主动对话响应结束
            if is_proactive_response:
                # 显示累积的响应内容
                buffer = getattr(self, '_proactive_response_buffer', '')
                if buffer and self._floating_ball:
                    self._floating_ball.show_bubble(buffer)
                    # 触发未读消息动态效果
                    self._floating_ball.set_unread_message(True)
                # 清理状态
                self._proactive_dialog_pending = False
                self._proactive_response_buffer = ""
                return
            
            # 对话窗口完成响应
            if self._chat_window:
                self._chat_window.finish_ai_response()
                
            # 气泡输入框完成响应
            if self._floating_ball and self._floating_ball.is_waiting_response():
                self._floating_ball.finish_response()
                
        elif msg_type == "error":
            # 主动对话错误
            if is_proactive_response:
                logger.error(f"主动对话响应错误: {content}")
                self._proactive_dialog_pending = False
                self._proactive_response_buffer = ""
                return
            
            if self._chat_window:
                self._chat_window.add_error_message(content)
            if self._floating_ball:
                # 如果气泡输入框在等待，也需要结束等待并显示错误
                if self._floating_ball.is_waiting_response():
                    self._floating_ball.update_streaming_response(f"❌ {content}")
                    self._floating_ball.finish_response()
                else:
                    self._floating_ball.show_bubble(f"❌ {content}")
            
    def _on_ball_clicked(self):
        """悬浮球单击"""
        # 清除未读消息状态
        if self._floating_ball and self._floating_ball.has_unread_message():
            self._floating_ball.clear_unread_message()
        
        action = self.config.interaction.single_click
        if action == "bubble":
            self._show_bubble_input()
        elif action == "window":
            self._show_chat_window()
            
    def _on_ball_double_clicked(self):
        """悬浮球双击"""
        # 清除未读消息状态
        if self._floating_ball and self._floating_ball.has_unread_message():
            self._floating_ball.clear_unread_message()
        
        action = self.config.interaction.double_click
        if action == "bubble":
            self._show_bubble_input()
        elif action == "window":
            self._show_chat_window()
            
    def _show_bubble_input(self):
        """显示气泡输入"""
        if self._floating_ball:
            self._floating_ball.show_input()
            
    def _show_chat_window(self):
        """显示对话窗口"""
        if self._chat_window:
            self._chat_window.show_and_focus()
            
    def _toggle_chat_window(self):
        """切换对话窗口显示"""
        if self._chat_window:
            if self._chat_window.isVisible():
                self._chat_window.hide()
            else:
                self._chat_window.show_and_focus()
                
    def _toggle_floating_ball(self):
        """切换悬浮球显示"""
        if self._floating_ball:
            if self._floating_ball.isVisible():
                self._floating_ball.hide()
            else:
                self._floating_ball.show()
                
    def _show_quick_ask(self):
        """显示快速提问"""
        # 打开对话窗口并聚焦输入框
        self._show_chat_window()
        
    def _cycle_theme(self):
        """循环切换主题"""
        from .gui.themes import theme_manager
        theme_manager.cycle_theme()
        
    def _on_screenshot(self, screenshot_type: str):
        """处理截图"""
        if screenshot_type == "region":
            self._do_region_screenshot()
        else:
            self._do_full_screenshot()
            
    def _do_region_screenshot(self):
        """区域截图"""
        try:
            from .gui.screenshot_selector import RegionScreenshotCapture
            
            # 记录当前对话窗口状态
            self._chat_was_visible_before_screenshot = (
                self._chat_window is not None and self._chat_window.isVisible()
            )
            
            # 隐藏窗口
            if self._floating_ball:
                self._floating_ball.hide()
            if self._chat_window and self._chat_window.isVisible():
                self._chat_window.hide()
            
            # 使用 QTimer 确保窗口隐藏后再截图
            QTimer.singleShot(100, self._start_region_capture)
        except ImportError as e:
            print(f"区域截图不可用: {e}")
            
    def _start_region_capture(self):
        """开始区域截图"""
        try:
            from .gui.screenshot_selector import RegionScreenshotCapture
            
            self._capture = RegionScreenshotCapture()
            self._capture.capture_async(self._on_screenshot_complete)
        except Exception as e:
            print(f"启动截图失败: {e}")
            self._restore_windows()
            
    def _do_full_screenshot(self):
        """全屏截图"""
        try:
            from .services.screen_capture import ScreenCaptureService
            
            # 记录当前对话窗口状态
            self._chat_was_visible_before_screenshot = (
                self._chat_window is not None and self._chat_window.isVisible()
            )
            
            # 隐藏窗口
            if self._floating_ball:
                self._floating_ball.hide()
            if self._chat_window and self._chat_window.isVisible():
                self._chat_window.hide()
                
            QTimer.singleShot(100, self._execute_full_screenshot)
        except ImportError as e:
            print(f"截图服务不可用: {e}")
            
    def _execute_full_screenshot(self):
        """执行全屏截图"""
        try:
            from .services.screen_capture import ScreenCaptureService
            
            # 使用配置的存储路径
            save_dir = self.config.storage.image_save_path or "./temp/screenshots"
            service = ScreenCaptureService(save_dir=save_dir)
            screenshot_path = service.capture_full_screen_to_file()
            
            self._restore_windows()
            
            if screenshot_path:
                self._handle_screenshot_result(screenshot_path)
        except Exception as e:
            print(f"截图失败: {e}")
            self._restore_windows()
            
    def _on_screenshot_complete(self, screenshot_path: Optional[str]):
        """截图完成回调"""
        self._restore_windows()
        
        if screenshot_path:
            self._handle_screenshot_result(screenshot_path)
            
    def _restore_windows(self):
        """恢复窗口显示"""
        if self._floating_ball:
            self._floating_ball.show()
            
    def _handle_screenshot_result(self, screenshot_path: str):
        """处理截图结果 - 根据对话窗口状态决定粘贴位置"""
        # 记录截图前对话窗口是否可见
        chat_was_visible = getattr(self, '_chat_was_visible_before_screenshot', False)
        
        if chat_was_visible and self._chat_window:
            # 对话窗口打开：粘贴到对话窗口输入框
            self._chat_window.set_attachment(screenshot_path)
            self._chat_window.show_and_focus()
        else:
            # 对话窗口关闭：粘贴到气泡输入框
            if self._floating_ball:
                self._floating_ball.set_attachment(screenshot_path)
                self._floating_ball.show_input()
            
    def _add_screenshot_to_chat(self, screenshot_path: str):
        """添加截图到对话（旧方法保留兼容）"""
        self._handle_screenshot_result(screenshot_path)
            
    @asyncSlot(str)
    async def _on_message_sent(self, message: str):
        """处理发送的消息 (Async Slot)"""
        # 判断消息来源：如果对话窗口不可见，则消息来自气泡输入框
        from_bubble = self._chat_window is None or not self._chat_window.isVisible()
        
        if from_bubble and self._chat_window:
            # 从气泡发送的消息，需要添加用户消息到对话窗口
            self._chat_window.add_user_message(message)
            
        # 发送消息到服务器
        await self._bridge.send_input(InputMessage(
            msg_type="text",
            content=message,
            session_id=self.config.session_id or ""
        ))
        
    @asyncSlot(str, str)
    async def _on_image_sent(self, image_path: str, text: str = ""):
        """处理发送的图片消息 (Async Slot)"""
        await self._send_image_message(image_path, text)

    async def _send_image_message(self, image_path: str, text: str = ""):
        """发送图片消息"""
        await self._bridge.send_input(InputMessage(
            msg_type="image",
            content=image_path,
            session_id=self.config.session_id or "",
            metadata={"text": text}
        ))
        
    def _handle_image_response(self, filename: str, metadata: dict):
        """处理 AI 返回的图片"""
        import asyncio
        asyncio.ensure_future(self._download_and_show_image(filename))
        
    async def _download_and_show_image(self, filename: str):
        """下载并显示图片"""
        import tempfile
        import os
        
        # 确定保存目录
        if self.config.storage.image_save_path:
            save_dir = self.config.storage.image_save_path
            os.makedirs(save_dir, exist_ok=True)
            save_path = os.path.join(save_dir, f"{filename}")
        else:
            # 创建临时文件保存图片
            temp_dir = tempfile.gettempdir()
            save_path = os.path.join(temp_dir, f"astrbot_img_{filename}")
        
        success = await self._bridge.api_client.download_file(filename, save_path)
        
        if success and os.path.exists(save_path):
            if self._chat_window:
                self._chat_window.add_ai_message(save_path, "image")
            # 在气泡中显示实际图片缩略图
            if self._floating_ball:
                # 使用 Markdown 显示图片
                image_md = f"![image]({save_path})"
                self._floating_ball.show_bubble(image_md)
        else:
            if self._chat_window:
                self._chat_window.add_error_message(f"图片下载失败: {filename}")
                
    def _handle_voice_response(self, filename: str, metadata: dict):
        """处理 AI 返回的语音"""
        import asyncio
        asyncio.ensure_future(self._download_and_play_voice(filename))
        
    async def _download_and_play_voice(self, filename: str):
        """下载并播放语音"""
        import tempfile
        import os
        
        # 创建临时文件保存语音
        temp_dir = tempfile.gettempdir()
        save_path = os.path.join(temp_dir, f"astrbot_voice_{filename}")
        
        success = await self._bridge.api_client.download_file(filename, save_path)
        
        if success and os.path.exists(save_path):
            if self._chat_window:
                self._chat_window.add_ai_message(save_path, "voice")
            if self._floating_ball:
                self._floating_ball.show_bubble("🔊 [收到语音]")
            
            # 自动播放语音（如果启用）
            if self.config.voice.auto_play_voice:
                self._play_audio(save_path)
        else:
            if self._chat_window:
                self._chat_window.add_error_message(f"语音下载失败: {filename}")
                
    def _play_audio(self, audio_path: str):
        """播放音频文件"""
        try:
            from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput
            from PySide6.QtCore import QUrl
            
            if not hasattr(self, '_audio_player'):
                self._audio_player = QMediaPlayer()
                self._audio_output = QAudioOutput()
                self._audio_player.setAudioOutput(self._audio_output)
                
            self._audio_player.setSource(QUrl.fromLocalFile(audio_path))
            self._audio_output.setVolume(1.0)
            self._audio_player.play()
        except ImportError:
            print("[WARNING] QMediaPlayer 不可用，无法播放语音")
        except Exception as e:
            print(f"[ERROR] 播放语音失败: {e}")
            
    def _show_settings(self):
        """显示设置窗口"""
        if self._settings_window:
            self._settings_window.show()
            self._settings_window.raise_()
            self._settings_window.activateWindow()
            
    def _on_settings_changed(self, settings: dict):
        """处理设置变化"""
        # 更新服务器配置
        server = settings.get('server', {})
        need_reconnect = False
        
        # 使用 'in' 检查键是否存在，而不是检查值是否为真
        # 这样即使是空字符串也会被正确保存
        if 'url' in server or 'username' in server or 'password' in server:
            self._bridge.update_server_config(
                url=server.get('url'),
                username=server.get('username'),
                password=server.get('password')
            )
            if 'url' in server:
                self.config.server.url = server['url']
            if 'username' in server:
                self.config.server.username = server['username']
            if 'password' in server:
                self.config.server.password = server['password']
            if 'enable_streaming' in server:
                self.config.server.enable_streaming = server['enable_streaming']
            need_reconnect = True
            
        # 如果需要重连，立即尝试连接
        if need_reconnect:
            print("[DEBUG] 配置已更新，正在重新连接...")
            asyncio.ensure_future(self._reconnect_server())

        # 更新外观配置
        appearance = settings.get('appearance', {})
        if 'theme' in appearance:
            self.config.appearance.theme = appearance['theme']
        if 'avatar_path' in appearance:
            self.config.appearance.avatar_path = appearance['avatar_path']
            if self._floating_ball:
                self._floating_ball.set_avatar(appearance['avatar_path'])
        if 'ball_size' in appearance:
            self.config.appearance.ball_size = appearance['ball_size']
        if 'breathing_enabled' in appearance:
            self.config.appearance.breathing_enabled = appearance['breathing_enabled']
            if self._floating_ball:
                self._floating_ball.set_breathing(appearance['breathing_enabled'])
                
        # 更新快捷键配置
        hotkeys = settings.get('hotkeys', {})
        if 'global_enabled' in hotkeys:
            self.config.hotkeys.global_enabled = hotkeys['global_enabled']
        for key in ['toggle_chat', 'region_screenshot', 'full_screenshot', 'toggle_ball', 'quick_ask', 'cycle_theme']:
            if key in hotkeys:
                setattr(self.config.hotkeys, key, hotkeys[key])
                
        # 更新交互配置
        interaction = settings.get('interaction', {})
        if 'default_mode' in interaction:
            self.config.interaction.default_mode = interaction['default_mode']
        if 'single_click' in interaction:
            self.config.interaction.single_click = interaction['single_click']
        if 'double_click' in interaction:
            self.config.interaction.double_click = interaction['double_click']
        if 'bubble_duration' in interaction:
            self.config.interaction.bubble_duration = interaction['bubble_duration']
        if 'bubble_auto_hide' in interaction:
            self.config.interaction.bubble_auto_hide = interaction['bubble_auto_hide']
        
        # 更新主动对话配置
        proactive = settings.get('proactive', {})
        if proactive:
            for key, value in proactive.items():
                if hasattr(self.config.proactive, key):
                    setattr(self.config.proactive, key, value)
            
            # 更新主动对话服务配置
            if self._proactive_service:
                self._proactive_service.update_config(self.config.proactive)
                print("[DEBUG] 主动对话服务配置已更新")
        
        # 更新存储配置
        storage = settings.get('storage', {})
        if 'image_save_path' in storage:
            self.config.storage.image_save_path = storage['image_save_path']
            print(f"[DEBUG] 图片保存路径已更新: {storage['image_save_path']}")
            
            # 同步更新主动对话服务的截图目录
            if self._proactive_service and storage['image_save_path']:
                self._proactive_service._screenshot_dir = storage['image_save_path']
                print(f"[DEBUG] 主动对话服务截图目录已更新")
            
        # 保存配置到文件
        print("[DEBUG] 保存配置...")
        if save_config(self.config):
            print(f"[DEBUG] 配置已保存到: {ClientConfig.get_config_path()}")
        else:
            print("[DEBUG] 配置保存失败")
        
    def _restart(self):
        """重启应用"""
        import subprocess
        
        print("[DEBUG] 正在重启应用...")
        
        # 保存配置
        if save_config(self.config):
            print(f"[DEBUG] 配置已保存")
        
        # 清理快捷键
        if self._hotkey_manager:
            self._hotkey_manager.cleanup()
            
        # 停止主动对话服务
        if self._proactive_service:
            self._proactive_service.stop()
            
        # 获取当前 Python 解释器
        python = sys.executable
        
        # 获取项目根目录（desktop_client 的父目录）
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        
        # 使用 -m 模块方式启动，避免相对导入问题
        # 在 Windows 上 os.execv 不能正确工作，使用 subprocess.Popen
        try:
            # 创建新进程，使用 python -m desktop_client 方式启动
            if os.name == 'nt':
                # Windows 特有：创建新的进程组，避免被父进程关闭影响
                subprocess.Popen(
                    [python, "-m", "desktop_client"],
                    cwd=project_root,
                    creationflags=subprocess.CREATE_NEW_PROCESS_GROUP
                )
            else:
                # Unix/Linux/macOS
                subprocess.Popen(
                    [python, "-m", "desktop_client"],
                    cwd=project_root
                )
            print("[DEBUG] 新进程已启动")
        except Exception as e:
            print(f"[ERROR] 重启失败: {e}")
            return
        
        # 退出当前 Qt 应用
        if self._app:
            self._app.quit()
            
    def _quit(self):
        """退出应用"""
        # 停止主动对话服务
        if self._proactive_service:
            self._proactive_service.stop()
            print("[DEBUG] 主动对话服务已停止")
        
        # 清理快捷键
        if self._hotkey_manager:
            self._hotkey_manager.cleanup()
            
        # 断开连接
        asyncio.ensure_future(self._bridge.disconnect_server())
            
        # 退出应用
        if self._app:
            self._app.quit()


def main():
    """入口函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description="AstrBot Desktop Client")
    parser.add_argument("-s", "--server", help="Server URL")
    parser.add_argument("-u", "--username", help="Username")
    parser.add_argument("-p", "--password", help="Password")
    
    args = parser.parse_args()
    
    app = DesktopClientApp(
        server_url=args.server,
        username=args.username,
        password=args.password
    )
    
    # 捕获 Ctrl+C
    import signal
    signal.signal(signal.SIGINT, lambda *args: app._quit())
    
    app.run()


if __name__ == "__main__":
    main()