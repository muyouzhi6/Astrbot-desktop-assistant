"""
媒体处理器

负责处理媒体文件相关逻辑：
- 图片下载和显示
- 语音下载和播放
- 视频下载和播放
"""

import asyncio
import os
import logging
from typing import TYPE_CHECKING, Optional, Any, Dict

from PySide6.QtCore import QObject, Signal

if TYPE_CHECKING:
    from ..config import ClientConfig
    from ..bridge import MessageBridge

logger = logging.getLogger(__name__)


class MediaHandler(QObject):
    """媒体处理器 - 处理媒体文件下载和播放"""

    # 信号定义
    download_completed = Signal(str, str)  # 下载完成，参数为(文件路径, 类型)
    download_failed = Signal(str, str)  # 下载失败，参数为(文件名, 错误信息)

    def __init__(
        self,
        config: "ClientConfig",
        bridge: Optional["MessageBridge"] = None,
        floating_ball: Optional[Any] = None,
        chat_history_manager: Optional[Any] = None,
        message_handler: Optional[Any] = None,
        parent: Optional[QObject] = None,
    ):
        """
        初始化媒体处理器

        Args:
            config: 客户端配置
            bridge: 消息桥接实例
            floating_ball: 悬浮球窗口实例
            chat_history_manager: 聊天记录管理器
            message_handler: 消息处理器（用于获取主动对话状态）
            parent: 父对象
        """
        super().__init__(parent)
        self._config = config
        self._bridge = bridge
        self._floating_ball = floating_ball
        self._chat_history_manager = chat_history_manager
        self._message_handler = message_handler

        # 存储目录
        self._storage_dirs: Dict[str, str] = {}

        # 音频播放器
        self._audio_player = None
        self._audio_output = None

    def set_bridge(self, bridge: "MessageBridge") -> None:
        """设置消息桥接"""
        self._bridge = bridge

    def set_floating_ball(self, floating_ball: Any) -> None:
        """设置悬浮球实例"""
        self._floating_ball = floating_ball

    def set_chat_history_manager(self, manager: Any) -> None:
        """设置聊天记录管理器"""
        self._chat_history_manager = manager

    def set_message_handler(self, handler: Any) -> None:
        """设置消息处理器"""
        self._message_handler = handler

    def set_storage_dirs(self, storage_dirs: Dict[str, str]) -> None:
        """设置存储目录"""
        self._storage_dirs = storage_dirs

    def ensure_storage_dirs(self, base_dir: Optional[str] = None) -> Dict[str, str]:
        """
        确保存储目录结构存在

        Args:
            base_dir: 基础目录，如果为 None 则使用配置

        Returns:
            存储目录字典
        """
        if not base_dir:
            base_dir = self._config.storage.image_save_path
            if not base_dir:
                from ..config import ClientConfig

                base_dir = os.path.join(str(ClientConfig.get_config_dir()), "downloads")

        self._storage_dirs = {
            "image": os.path.join(base_dir, "images"),
            "voice": os.path.join(base_dir, "voices"),
            "video": os.path.join(base_dir, "videos"),
            "file": os.path.join(base_dir, "files"),
        }

        for dir_path in self._storage_dirs.values():
            os.makedirs(dir_path, exist_ok=True)

        return self._storage_dirs

    def get_save_path(self, filename: str, msg_type: str) -> str:
        """
        获取文件保存路径

        Args:
            filename: 文件名
            msg_type: 消息类型

        Returns:
            完整的保存路径
        """
        dir_path = self._storage_dirs.get(msg_type, self._storage_dirs.get("file", ""))
        return os.path.join(dir_path, filename)

    def handle_image_response(
        self, filename: str, metadata: dict, should_silent: bool = False
    ) -> None:
        """处理 AI 返回的图片"""
        asyncio.ensure_future(self._download_media(filename, "image", should_silent))

    def handle_voice_response(
        self, filename: str, metadata: dict, should_silent: bool = False
    ) -> None:
        """处理 AI 返回的语音"""
        asyncio.ensure_future(self._download_media(filename, "voice", should_silent))

    def handle_video_response(
        self, filename: str, metadata: dict, should_silent: bool = False
    ) -> None:
        """处理 AI 返回的视频"""
        asyncio.ensure_future(self._download_media(filename, "video", should_silent))

    async def _download_media(
        self, filename: str, msg_type: str, should_silent: bool = False
    ) -> None:
        """
        下载媒体文件并显示

        Args:
            filename: 文件名
            msg_type: 消息类型
            should_silent: 是否静默处理
        """
        save_path = self.get_save_path(filename, msg_type)

        # 检查是否是主动对话的响应
        is_proactive_response = (
            self._message_handler and self._message_handler.is_proactive_pending()
        )

        # 检查免打扰模式
        do_not_disturb = self._config.interaction.do_not_disturb

        # 检查是否正在等待响应（用户主动发起的对话）
        (
            self._floating_ball and self._floating_ball.is_waiting_response()
        )

        # 判断是否需要静默处理 (优先使用传入参数，否则使用免打扰配置)
        should_silent = should_silent or do_not_disturb

        # 下载文件
        if not self._bridge:
            logger.error("MessageBridge 未设置")
            return

        success = await self._bridge.api_client.download_file(filename, save_path)

        if success and os.path.exists(save_path):
            content = save_path

            if msg_type == "voice":
                # 构建消息内容：path|duration
                content = f"{save_path}|0"

                # 主动对话或静默模式的语音响应
                if is_proactive_response or should_silent:
                    # 静默添加到历史记录
                    if self._chat_history_manager:
                        self._chat_history_manager.add_message(
                            role="assistant",
                            content=content,
                            msg_type="voice",
                            file_path=save_path,
                        )
                    # 免打扰模式下语音消息始终后台自动播放
                    self.play_audio(save_path)
                    # 设置未读消息标记
                    if self._floating_ball:
                        self._floating_ball.set_unread_message(True)

                    # 发射信号
                    self.download_completed.emit(save_path, msg_type)
                    return

            elif msg_type == "video":
                # 构建消息内容：path|thumbnail|duration
                content = f"{save_path}||0"

            if is_proactive_response or should_silent:
                # 静默模式：添加到历史记录，不弹窗
                if self._chat_history_manager:
                    self._chat_history_manager.add_message(
                        role="assistant",
                        content=content,
                        msg_type=msg_type,
                        file_path=save_path,
                    )
                # 设置未读消息标记
                if self._floating_ball:
                    self._floating_ball.set_unread_message(True)
            else:
                # 正常模式：在窗口中显示并弹出
                if self._floating_ball:
                    # 通过 compact_window 添加消息
                    self._floating_ball._compact_window.add_ai_message(
                        content, msg_type
                    )
                    self._floating_ball.show_input()

            # 发射信号
            self.download_completed.emit(save_path, msg_type)
        else:
            error_msg = f"下载失败: {filename}"
            logger.error(error_msg)
            if self._floating_ball and not should_silent:
                self._floating_ball.show_bubble(f"❌ {error_msg}")
            elif self._floating_ball and should_silent:
                self._floating_ball.set_unread_message(True)
            self.download_failed.emit(filename, error_msg)

    def play_audio(self, audio_path: str) -> None:
        """
        播放音频文件

        Args:
            audio_path: 音频文件路径
        """
        try:
            from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput
            from PySide6.QtCore import QUrl

            if not self._audio_player:
                self._audio_player = QMediaPlayer()
                self._audio_output = QAudioOutput()
                self._audio_player.setAudioOutput(self._audio_output)

            self._audio_player.setSource(QUrl.fromLocalFile(audio_path))
            self._audio_output.setVolume(1.0)  # type: ignore
            self._audio_player.play()
        except ImportError:
            logger.warning("QMediaPlayer 不可用，无法播放语音")
            logger.warning("QMediaPlayer 不可用，无法播放语音")
        except Exception as e:
            logger.error(f"播放语音失败: {e}")
            logger.error(f"播放语音失败: {e}")
