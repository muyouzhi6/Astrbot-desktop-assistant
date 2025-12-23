"""
客户端配置模块

管理独立客户端的所有配置项，包括服务器连接信息和本地设置。
"""

import json
import os
import threading
from dataclasses import dataclass, field, asdict
from typing import Optional
from pathlib import Path


@dataclass
class ServerConfig:
    """服务器连接配置"""
    url: str = "http://localhost:6185"
    username: str = "astrbot"
    password: str = ""
    # 认证 token（登录后获取）
    token: Optional[str] = None
    # 自动重连
    auto_reconnect: bool = True
    reconnect_interval: int = 5  # 秒
    # 启动延迟连接（秒），用于开机自启时等待网络就绪
    startup_delay: int = 3
    # 最大重连次数，0表示无限重连
    max_reconnect_attempts: int = 0
    # 请求超时
    request_timeout: int = 30  # 秒
    # 是否启用流式输出
    enable_streaming: bool = True
    

@dataclass
class CustomThemeConfig:
    """自定义主题颜色配置
    
    所有颜色字段默认为空字符串，表示使用当前主题的默认颜色。
    颜色值格式为十六进制，如 "#FF5722" 或 "rgba(255, 87, 34, 0.8)"
    """
    # 是否启用自定义颜色
    enabled: bool = False
    # 主色调
    primary: str = ""
    primary_light: str = ""
    primary_dark: str = ""
    # 背景色
    bg_primary: str = ""
    bg_secondary: str = ""
    # 文字颜色
    text_primary: str = ""
    text_secondary: str = ""
    # 悬浮球颜色
    ball_bg: str = ""
    ball_glow: str = ""
    ball_border: str = ""
    # 用户气泡颜色
    bubble_user_bg: str = ""
    bubble_user_text: str = ""
    # AI气泡颜色
    bubble_ai_bg: str = ""
    bubble_ai_text: str = ""


@dataclass
class AppearanceConfig:
    """外观配置"""
    ball_size: int = 64
    ball_opacity: float = 0.9
    avatar_path: str = ""  # 悬浮球头像（向后兼容，同时作为bot头像）
    user_avatar_path: str = ""  # 用户头像路径
    bot_avatar_path: str = ""  # Bot头像路径
    theme: str = "auto"
    always_on_top: bool = False
    breathing_enabled: bool = True
    auto_start: bool = False  # 开机自启
    # 自定义主题颜色
    custom_theme: CustomThemeConfig = field(default_factory=CustomThemeConfig)
    

@dataclass
class ChatWindowConfig:
    """对话窗口配置"""
    window_width: int = 400
    window_height: int = 600
    font_size: int = 14
    show_timestamp: bool = True
    

@dataclass
class HotkeyConfigData:
    """快捷键配置"""
    toggle_chat: str = "Ctrl+Shift+A"
    region_screenshot: str = "Ctrl+Shift+S"
    full_screenshot: str = "Ctrl+Shift+F"
    toggle_ball: str = "Ctrl+Shift+B"
    quick_ask: str = "Ctrl+Shift+Q"
    cycle_theme: str = "Ctrl+Shift+T"
    global_enabled: bool = False


@dataclass
class InteractionConfig:
    """交互配置"""
    default_mode: str = "window"  # bubble | window
    single_click: str = "bubble"  # bubble | window | none
    double_click: str = "window"  # bubble | window | none
    bubble_duration: int = 5  # 秒
    bubble_auto_hide: bool = True
    do_not_disturb: bool = False  # 免打扰模式：收到消息不弹窗，只显示动画效果


@dataclass
class VoiceConfig:
    """语音配置"""
    enable_tts: bool = True
    auto_play_voice: bool = False


@dataclass
class StorageConfig:
    """存储配置"""
    # 图片/截图保存路径
    image_save_path: str = ""
    # 聊天记录保存路径
    chat_history_path: str = ""
    
    @property
    def resolved_image_save_path(self) -> Path:
        """获取解析后的图片保存路径"""
        if self.image_save_path:
            path = Path(self.image_save_path)
            try:
                path.mkdir(parents=True, exist_ok=True)
                return path
            except Exception as e:
                print(f"无法创建自定义存储目录: {e}")
        
        # 默认路径: ./temp/images
        default_path = Path("temp") / "images"
        default_path.mkdir(parents=True, exist_ok=True)
        return default_path
    
    @property
    def resolved_chat_history_path(self) -> Path:
        """获取解析后的聊天记录保存路径"""
        if self.chat_history_path:
            path = Path(self.chat_history_path)
            try:
                path.parent.mkdir(parents=True, exist_ok=True)
                return path
            except Exception as e:
                print(f"无法创建聊天记录目录: {e}")
        
        # 默认路径: 配置目录下的 chat_history.json
        # Windows: %APPDATA%/AstrBotDesktopClient/chat_history.json
        # Linux/Mac: ~/.config/astrbot-desktop-client/chat_history.json
        if os.name == 'nt':
            base = os.environ.get('APPDATA', os.path.expanduser('~'))
            config_dir = Path(base) / 'AstrBotDesktopClient'
        else:
            config_dir = Path.home() / '.config' / 'astrbot-desktop-client'
        
        config_dir.mkdir(parents=True, exist_ok=True)
        return config_dir / 'chat_history.json'


@dataclass
class ProactiveDialogConfig:
    """主动对话配置"""
    # 是否启用主动对话
    enabled: bool = False
    # 检测间隔（秒），默认10分钟
    check_interval: int = 600
    # 触发概率，默认20%
    trigger_probability: float = 0.2
    # 是否要求用户活跃
    require_user_active: bool = True
    # 用户空闲阈值（秒），超过则认为不活跃
    idle_threshold: int = 60
    # 是否启用时间段限制
    time_range_enabled: bool = False
    # 开始时间
    time_range_start: str = "09:00"
    # 结束时间
    time_range_end: str = "22:00"
    # 截图压缩宽度
    screenshot_width: int = 800
    # 截图压缩高度
    screenshot_height: int = 600
    # AI响应最大token数
    max_response_tokens: int = 50
    # 主动对话提示词模板
    prompt_template: str = """你是用户的桌面助手。现在请根据用户当前的屏幕内容，主动发起一段简短、自然的对话。
要求：
1. 像朋友一样自然地打招呼或发起话题
2. 可以对屏幕内容进行简短评论或提供帮助
3. 保持简洁，不超过2-3句话
4. 语气轻松友好，不要太正式"""
    

@dataclass
class ClientConfig:
    """客户端完整配置"""
    server: ServerConfig = field(default_factory=ServerConfig)
    appearance: AppearanceConfig = field(default_factory=AppearanceConfig)
    chat_window: ChatWindowConfig = field(default_factory=ChatWindowConfig)
    voice: VoiceConfig = field(default_factory=VoiceConfig)
    hotkeys: HotkeyConfigData = field(default_factory=HotkeyConfigData)
    interaction: InteractionConfig = field(default_factory=InteractionConfig)
    proactive: ProactiveDialogConfig = field(default_factory=ProactiveDialogConfig)
    storage: StorageConfig = field(default_factory=StorageConfig)
    # 会话 ID
    session_id: Optional[str] = None
    
    # 线程锁
    _lock: threading.Lock = field(default_factory=threading.Lock, init=False, repr=False)
    
    def __post_init__(self):
        # 确保反序列化后锁存在
        if not hasattr(self, '_lock'):
            object.__setattr__(self, '_lock', threading.Lock())

    @classmethod
    def get_config_dir(cls) -> Path:
        """获取配置文件目录"""
        # Windows: %APPDATA%/AstrBotDesktopClient
        # Linux/Mac: ~/.config/astrbot-desktop-client
        if os.name == 'nt':
            base = os.environ.get('APPDATA', os.path.expanduser('~'))
            config_dir = Path(base) / 'AstrBotDesktopClient'
        else:
            config_dir = Path.home() / '.config' / 'astrbot-desktop-client'
        
        config_dir.mkdir(parents=True, exist_ok=True)
        return config_dir
    
    @classmethod
    def get_config_path(cls) -> Path:
        """获取配置文件路径"""
        return cls.get_config_dir() / 'config.json'
    
    @classmethod
    def load(cls, config_path: Optional[str] = None) -> 'ClientConfig':
        """从文件加载配置"""
        if config_path:
            path = Path(config_path)
        else:
            path = cls.get_config_path()
        
        print(f"[DEBUG] 尝试加载配置文件: {path}")
        
        if not path.exists():
            print(f"[DEBUG] 配置文件不存在，使用默认配置")
            return cls()
        
        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            print(f"[DEBUG] 成功读取配置文件，内容: {json.dumps(data.get('server', {}), ensure_ascii=False)}")
            
            config = cls()
            
            # 加载服务器配置
            if 'server' in data:
                for key, value in data['server'].items():
                    if hasattr(config.server, key):
                        setattr(config.server, key, value)
            
            # 加载外观配置
            if 'appearance' in data:
                for key, value in data['appearance'].items():
                    if key == 'custom_theme' and isinstance(value, dict):
                        # 特殊处理嵌套的 custom_theme 配置
                        for ct_key, ct_value in value.items():
                            if hasattr(config.appearance.custom_theme, ct_key):
                                setattr(config.appearance.custom_theme, ct_key, ct_value)
                    elif hasattr(config.appearance, key):
                        setattr(config.appearance, key, value)
            
            # 加载对话窗口配置
            if 'chat_window' in data:
                for key, value in data['chat_window'].items():
                    if hasattr(config.chat_window, key):
                        setattr(config.chat_window, key, value)
            
            # 加载语音配置
            if 'voice' in data:
                for key, value in data['voice'].items():
                    if hasattr(config.voice, key):
                        setattr(config.voice, key, value)
            
            # 加载快捷键配置
            if 'hotkeys' in data:
                for key, value in data['hotkeys'].items():
                    if hasattr(config.hotkeys, key):
                        setattr(config.hotkeys, key, value)
            
            # 加载交互配置
            if 'interaction' in data:
                for key, value in data['interaction'].items():
                    if hasattr(config.interaction, key):
                        setattr(config.interaction, key, value)
            
            # 加载主动对话配置
            if 'proactive' in data:
                for key, value in data['proactive'].items():
                    if hasattr(config.proactive, key):
                        setattr(config.proactive, key, value)
            
            # 加载存储配置
            if 'storage' in data:
                for key, value in data['storage'].items():
                    if hasattr(config.storage, key):
                        setattr(config.storage, key, value)

            # 加载会话 ID
            config.session_id = data.get('session_id')
            
            print(f"[DEBUG] 配置加载完成: server.url={config.server.url}, server.username={config.server.username}")
            
            return config
            
        except Exception as e:
            import traceback
            print(f"加载配置失败: {e}")
            traceback.print_exc()
            return cls()
    
    def save(self, config_path: Optional[str] = None) -> bool:
        """保存配置到文件"""
        # 确保锁存在 (处理从 dict 加载的情况)
        if not hasattr(self, '_lock'):
            object.__setattr__(self, '_lock', threading.Lock())
            
        with self._lock:
            if config_path:
                path = Path(config_path)
            else:
                # 确保配置目录存在
                self.get_config_dir()  # 这会创建目录
                path = self.get_config_path()
            
            try:
                # 确保父目录存在
                path.parent.mkdir(parents=True, exist_ok=True)
                
                # 构建外观配置，包含嵌套的 custom_theme
                appearance_data = asdict(self.appearance)
                # custom_theme 已经被 asdict 正确序列化为嵌套字典
                
                data = {
                    'server': asdict(self.server),
                    'appearance': appearance_data,
                    'chat_window': asdict(self.chat_window),
                    'voice': asdict(self.voice),
                    'hotkeys': asdict(self.hotkeys),
                    'interaction': asdict(self.interaction),
                    'proactive': asdict(self.proactive),
                    'storage': asdict(self.storage),
                    'session_id': self.session_id,
                }
                
                # 不保存密码和 token 的明文（可选：加密存储）
                # 这里简单处理，不保存敏感信息
                # data['server']['password'] = ""  # 可选：不保存密码
                
                with open(path, 'w', encoding='utf-8') as f:
                    json.dump(data, f, indent=2, ensure_ascii=False)
                
                print(f"[DEBUG] 配置已成功保存到: {path}")
                return True
                
            except Exception as e:
                import traceback
                print(f"保存配置失败: {e}")
                traceback.print_exc()
                return False
    
    def to_legacy_dict(self) -> dict:
        """转换为旧版（插件模式）配置格式，用于兼容现有 GUI 组件"""
        return {
            # 服务器配置
            'server_url': self.server.url,
            'username': self.server.username,
            'auto_reconnect': self.server.auto_reconnect,
            # 外观配置
            'ball_size': self.appearance.ball_size,
            'ball_opacity': self.appearance.ball_opacity,
            'avatar_path': self.appearance.avatar_path,
            'theme': self.appearance.theme,
            # 对话窗口配置
            'window_width': self.chat_window.window_width,
            'window_height': self.chat_window.window_height,
            'font_size': self.chat_window.font_size,
            # 语音配置
            'enable_tts': self.voice.enable_tts,
            'auto_play_voice': self.voice.auto_play_voice,
        }
    
    def update_from_legacy_dict(self, legacy: dict):
        """从旧版配置格式更新"""
        # 服务器配置
        if 'server_url' in legacy:
            self.server.url = legacy['server_url']
        if 'username' in legacy:
            self.server.username = legacy['username']
        if 'password' in legacy:
            self.server.password = legacy['password']
        if 'auto_reconnect' in legacy:
            self.server.auto_reconnect = legacy['auto_reconnect']
        
        # 外观配置
        if 'ball_size' in legacy:
            self.appearance.ball_size = legacy['ball_size']
        if 'ball_opacity' in legacy:
            self.appearance.ball_opacity = legacy['ball_opacity']
        if 'avatar_path' in legacy:
            self.appearance.avatar_path = legacy['avatar_path']
        if 'theme' in legacy:
            self.appearance.theme = legacy['theme']
        
        # 对话窗口配置
        if 'window_width' in legacy:
            self.chat_window.window_width = legacy['window_width']
        if 'window_height' in legacy:
            self.chat_window.window_height = legacy['window_height']
        if 'font_size' in legacy:
            self.chat_window.font_size = legacy['font_size']
        
        # 语音配置
        if 'enable_tts' in legacy:
            self.voice.enable_tts = legacy['enable_tts']
        if 'auto_play_voice' in legacy:
            self.voice.auto_play_voice = legacy['auto_play_voice']


def load_config(config_path: Optional[str] = None) -> ClientConfig:
    """加载配置"""
    return ClientConfig.load(config_path)


def save_config(config: ClientConfig, config_path: Optional[str] = None) -> bool:
    """保存配置"""
    return config.save(config_path)