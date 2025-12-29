"""
macOS 平台适配器

实现 macOS 系统的平台功能：
- 活动窗口检测
- 运行应用获取
- 开机自启管理
"""

import os
import sys
from pathlib import Path
from typing import List

from .base import IPlatformAdapter, WindowInfo, AppInfo, Result


# macOS 专用依赖
try:
    from AppKit import NSWorkspace

    HAS_APPKIT = True
except ImportError:
    HAS_APPKIT = False

try:
    import psutil

    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False


class MacOSPlatformAdapter(IPlatformAdapter):
    """macOS 平台适配器"""

    # LaunchAgent plist 名称
    LAUNCH_AGENT_NAME = "com.astrbot.desktop-client"

    @property
    def platform_name(self) -> str:
        """获取平台名称"""
        return "macOS"

    def get_active_window(self) -> WindowInfo:
        """获取当前活动窗口信息"""
        info = WindowInfo()

        if not HAS_APPKIT:
            print("[macOS] AppKit 未安装，无法获取窗口信息")
            return info

        try:
            workspace = NSWorkspace.sharedWorkspace()
            active_app = workspace.frontmostApplication()

            if active_app:
                info.process = active_app.localizedName()
                info.pid = active_app.processIdentifier()
                # macOS 获取窗口标题需要额外的 Accessibility API
                # 简化处理：使用应用名称作为标题
                info.title = info.process
        except Exception as e:
            print(f"[macOS] 获取窗口信息失败: {e}")

        return info

    def get_running_apps(self, max_count: int = 50) -> List[AppInfo]:
        """获取运行中的应用列表"""
        apps: List[AppInfo] = []

        if not HAS_PSUTIL:
            print("[macOS] psutil 未安装，无法获取应用列表")
            return apps

        try:
            seen = set()
            for proc in psutil.process_iter(["pid", "name"]):
                try:
                    pinfo = proc.info
                    name = pinfo.get("name")
                    # 过滤系统进程和重复项
                    if name and not name.startswith("_") and name not in seen:
                        apps.append(
                            AppInfo(
                                pid=pinfo["pid"],
                                name=name,
                            )
                        )
                        seen.add(name)
                        if len(apps) >= max_count:
                            break
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
        except Exception as e:
            print(f"[macOS] 获取运行应用列表失败: {e}")

        return apps

    def _get_launch_agents_dir(self) -> Path:
        """获取 LaunchAgents 目录"""
        return Path.home() / "Library" / "LaunchAgents"

    def _get_plist_path(self) -> Path:
        """获取 plist 文件路径"""
        return self._get_launch_agents_dir() / f"{self.LAUNCH_AGENT_NAME}.plist"

    def _get_app_path(self) -> str:
        """获取应用程序路径"""
        if getattr(sys, "frozen", False):
            return sys.executable
        else:
            return sys.executable

    def _get_startup_command(self) -> List[str]:
        """获取启动命令列表"""
        if getattr(sys, "frozen", False):
            return [sys.executable]
        else:
            return [sys.executable, "-m", "desktop_client"]

    def _get_working_directory(self) -> str:
        """获取工作目录"""
        if getattr(sys, "frozen", False):
            return os.path.dirname(sys.executable)
        else:
            # 获取项目根目录（desktop_client 的父目录）
            module_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            return os.path.dirname(module_path)

    def _generate_plist_content(self) -> str:
        """生成 plist 文件内容"""
        command = self._get_startup_command()
        working_dir = self._get_working_directory()

        # 构建 ProgramArguments
        program_args = "\n".join(f"        <string>{arg}</string>" for arg in command)

        return f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>{self.LAUNCH_AGENT_NAME}</string>
    <key>ProgramArguments</key>
    <array>
{program_args}
    </array>
    <key>WorkingDirectory</key>
    <string>{working_dir}</string>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <false/>
</dict>
</plist>
"""

    def enable_autostart(self) -> Result:
        """启用开机自启"""
        try:
            # 确保 LaunchAgents 目录存在
            launch_agents_dir = self._get_launch_agents_dir()
            launch_agents_dir.mkdir(parents=True, exist_ok=True)

            # 写入 plist 文件
            plist_path = self._get_plist_path()
            plist_content = self._generate_plist_content()
            plist_path.write_text(plist_content, encoding="utf-8")

            # 加载 LaunchAgent
            os.system(f'launchctl load "{plist_path}"')

            print(f"[macOS] 已启用开机自启: {plist_path}")
            return Result.success("开机自启已启用")
        except PermissionError:
            return Result.failed("没有足够的权限写入 LaunchAgents 目录")
        except Exception as e:
            print(f"[macOS] 启用开机自启失败: {e}")
            return Result.failed(f"启用失败: {str(e)}")

    def disable_autostart(self) -> Result:
        """禁用开机自启"""
        try:
            plist_path = self._get_plist_path()

            if plist_path.exists():
                # 卸载 LaunchAgent
                os.system(f'launchctl unload "{plist_path}"')
                # 删除 plist 文件
                plist_path.unlink()
                print("[macOS] 已禁用开机自启")

            return Result.success("开机自启已禁用")
        except PermissionError:
            return Result.failed("没有足够的权限删除 plist 文件")
        except Exception as e:
            print(f"[macOS] 禁用开机自启失败: {e}")
            return Result.failed(f"禁用失败: {str(e)}")

    def is_autostart_enabled(self) -> bool:
        """检查是否已启用开机自启"""
        try:
            plist_path = self._get_plist_path()
            return plist_path.exists()
        except Exception as e:
            print(f"[macOS] 检查开机自启状态失败: {e}")
            return False
