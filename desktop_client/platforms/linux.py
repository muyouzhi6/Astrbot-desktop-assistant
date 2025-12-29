"""
Linux 平台适配器

实现 Linux 系统的平台功能：
- 活动窗口检测（使用 xdotool）
- 运行应用获取
- 开机自启管理（使用 XDG autostart）
"""

import os
import subprocess
import sys
from pathlib import Path
from typing import List

from .base import IPlatformAdapter, WindowInfo, AppInfo, Result


try:
    import psutil

    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False


class LinuxPlatformAdapter(IPlatformAdapter):
    """Linux 平台适配器"""

    # 桌面文件名称
    DESKTOP_FILE_NAME = "astrbot-desktop-client.desktop"

    @property
    def platform_name(self) -> str:
        """获取平台名称"""
        return "Linux"

    def _check_xdotool(self) -> bool:
        """检查 xdotool 是否可用"""
        try:
            result = subprocess.run(
                ["which", "xdotool"], capture_output=True, timeout=5
            )
            return result.returncode == 0
        except Exception:
            return False

    def get_active_window(self) -> WindowInfo:
        """获取当前活动窗口信息"""
        info = WindowInfo()

        try:
            # 使用 xdotool 获取活动窗口标题
            result = subprocess.run(
                ["xdotool", "getactivewindow", "getwindowname"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0:
                info.title = result.stdout.strip()

            # 获取窗口 PID
            result = subprocess.run(
                ["xdotool", "getactivewindow", "getwindowpid"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0:
                pid = int(result.stdout.strip())
                info.pid = pid

                # 获取进程名
                if HAS_PSUTIL:
                    try:
                        process = psutil.Process(pid)
                        info.process = process.name()
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        pass
        except FileNotFoundError:
            print("[Linux] xdotool 未安装，无法获取窗口信息")
        except subprocess.TimeoutExpired:
            print("[Linux] xdotool 命令超时")
        except Exception as e:
            print(f"[Linux] 获取窗口信息失败: {e}")

        return info

    def get_running_apps(self, max_count: int = 50) -> List[AppInfo]:
        """获取运行中的应用列表"""
        apps: List[AppInfo] = []

        if not HAS_PSUTIL:
            print("[Linux] psutil 未安装，无法获取应用列表")
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
            print(f"[Linux] 获取运行应用列表失败: {e}")

        return apps

    def _get_autostart_dir(self) -> Path:
        """获取 XDG autostart 目录"""
        # 遵循 XDG 规范
        xdg_config_home = os.environ.get("XDG_CONFIG_HOME", "")
        if xdg_config_home:
            return Path(xdg_config_home) / "autostart"
        return Path.home() / ".config" / "autostart"

    def _get_desktop_file_path(self) -> Path:
        """获取 .desktop 文件路径"""
        return self._get_autostart_dir() / self.DESKTOP_FILE_NAME

    def _get_app_path(self) -> str:
        """获取应用程序路径"""
        if getattr(sys, "frozen", False):
            return sys.executable
        else:
            return sys.executable

    def _get_startup_command(self) -> str:
        """获取启动命令"""
        if getattr(sys, "frozen", False):
            return sys.executable
        else:
            return f"{sys.executable} -m desktop_client"

    def _get_working_directory(self) -> str:
        """获取工作目录"""
        if getattr(sys, "frozen", False):
            return os.path.dirname(sys.executable)
        else:
            # 获取项目根目录（desktop_client 的父目录）
            module_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            return os.path.dirname(module_path)

    def _generate_desktop_file_content(self) -> str:
        """生成 .desktop 文件内容"""
        exec_command = self._get_startup_command()
        working_dir = self._get_working_directory()

        return f"""[Desktop Entry]
Type=Application
Name=AstrBot Desktop Client
Comment=AstrBot Desktop Assistant Client
Exec={exec_command}
Path={working_dir}
Terminal=false
Hidden=false
X-GNOME-Autostart-enabled=true
"""

    def enable_autostart(self) -> Result:
        """启用开机自启"""
        try:
            # 确保 autostart 目录存在
            autostart_dir = self._get_autostart_dir()
            autostart_dir.mkdir(parents=True, exist_ok=True)

            # 写入 .desktop 文件
            desktop_file_path = self._get_desktop_file_path()
            desktop_content = self._generate_desktop_file_content()
            desktop_file_path.write_text(desktop_content, encoding="utf-8")

            # 设置可执行权限
            desktop_file_path.chmod(0o755)

            print(f"[Linux] 已启用开机自启: {desktop_file_path}")
            return Result.success("开机自启已启用")
        except PermissionError:
            return Result.failed("没有足够的权限写入 autostart 目录")
        except Exception as e:
            print(f"[Linux] 启用开机自启失败: {e}")
            return Result.failed(f"启用失败: {str(e)}")

    def disable_autostart(self) -> Result:
        """禁用开机自启"""
        try:
            desktop_file_path = self._get_desktop_file_path()

            if desktop_file_path.exists():
                desktop_file_path.unlink()
                print("[Linux] 已禁用开机自启")

            return Result.success("开机自启已禁用")
        except PermissionError:
            return Result.failed("没有足够的权限删除 .desktop 文件")
        except Exception as e:
            print(f"[Linux] 禁用开机自启失败: {e}")
            return Result.failed(f"禁用失败: {str(e)}")

    def is_autostart_enabled(self) -> bool:
        """检查是否已启用开机自启"""
        try:
            desktop_file_path = self._get_desktop_file_path()
            return desktop_file_path.exists()
        except Exception as e:
            print(f"[Linux] 检查开机自启状态失败: {e}")
            return False
