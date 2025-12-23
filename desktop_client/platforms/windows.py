"""
Windows 平台适配器

实现 Windows 系统的平台功能：
- 活动窗口检测
- 运行应用获取
- 开机自启管理
"""

import os
import sys
from typing import List

from .base import IPlatformAdapter, WindowInfo, AppInfo, Result


# Windows 专用依赖
try:
    import win32gui
    import win32process
    HAS_WIN32 = True
except ImportError:
    HAS_WIN32 = False

try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False


class WindowsPlatformAdapter(IPlatformAdapter):
    """Windows 平台适配器"""
    
    @property
    def platform_name(self) -> str:
        """获取平台名称"""
        return "Windows"
    
    def get_active_window(self) -> WindowInfo:
        """获取当前活动窗口信息"""
        info = WindowInfo()
        
        if not HAS_WIN32:
            print("[Windows] win32gui 未安装，无法获取窗口信息")
            return info
        
        try:
            hwnd = win32gui.GetForegroundWindow()
            if hwnd:
                info.title = win32gui.GetWindowText(hwnd)
                
                # 获取进程 ID
                _, pid = win32process.GetWindowThreadProcessId(hwnd)
                info.pid = pid
                
                # 获取进程名
                if HAS_PSUTIL:
                    try:
                        process = psutil.Process(pid)
                        info.process = process.name()
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        pass
        except Exception as e:
            print(f"[Windows] 获取窗口信息失败: {e}")
        
        return info
    
    def get_running_apps(self, max_count: int = 50) -> List[AppInfo]:
        """获取运行中的应用列表"""
        apps: List[AppInfo] = []
        
        if not HAS_PSUTIL:
            print("[Windows] psutil 未安装，无法获取应用列表")
            return apps
        
        try:
            seen = set()
            for proc in psutil.process_iter(['pid', 'name']):
                try:
                    pinfo = proc.info
                    name = pinfo.get('name')
                    # 过滤系统进程和重复项
                    if name and not name.startswith('_') and name not in seen:
                        apps.append(AppInfo(
                            pid=pinfo['pid'],
                            name=name,
                        ))
                        seen.add(name)
                        if len(apps) >= max_count:
                            break
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
        except Exception as e:
            print(f"[Windows] 获取运行应用列表失败: {e}")
        
        return apps
    
    def _get_app_path(self) -> str:
        """获取应用程序路径"""
        if getattr(sys, 'frozen', False):
            # PyInstaller 打包后的可执行文件
            return sys.executable
        else:
            # 开发模式下，使用 pythonw.exe 运行模块
            python_path = sys.executable
            # 使用 pythonw.exe 避免控制台窗口
            pythonw_path = python_path.replace('python.exe', 'pythonw.exe')
            if os.path.exists(pythonw_path):
                python_path = pythonw_path
            return python_path
    
    def _get_startup_command(self) -> str:
        """获取启动命令（包含工作目录）"""
        if getattr(sys, 'frozen', False):
            return f'"{sys.executable}"'
        else:
            python_path = self._get_app_path()
            
            # 获取项目根目录（desktop_client 的父目录）
            module_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            project_root = os.path.dirname(module_path)
            
            # 使用 cmd /c 切换到工作目录后再启动
            return f'cmd /c "cd /d "{project_root}" && "{python_path}" -m desktop_client"'
    
    def enable_autostart(self) -> Result:
        """启用开机自启"""
        try:
            import winreg
            key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_SET_VALUE)
            
            startup_cmd = self._get_startup_command()
            winreg.SetValueEx(key, "AstrBotDesktopClient", 0, winreg.REG_SZ, startup_cmd)
            winreg.CloseKey(key)
            
            print(f"[Windows] 已启用开机自启: {startup_cmd}")
            return Result.success("开机自启已启用")
        except PermissionError:
            return Result.failed("没有足够的权限修改注册表")
        except Exception as e:
            print(f"[Windows] 启用开机自启失败: {e}")
            return Result.failed(f"启用失败: {str(e)}")
    
    def disable_autostart(self) -> Result:
        """禁用开机自启"""
        try:
            import winreg
            key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_SET_VALUE)
            
            try:
                winreg.DeleteValue(key, "AstrBotDesktopClient")
                print("[Windows] 已禁用开机自启")
            except FileNotFoundError:
                # 值不存在，无需删除
                pass
            
            winreg.CloseKey(key)
            return Result.success("开机自启已禁用")
        except PermissionError:
            return Result.failed("没有足够的权限修改注册表")
        except Exception as e:
            print(f"[Windows] 禁用开机自启失败: {e}")
            return Result.failed(f"禁用失败: {str(e)}")
    
    def is_autostart_enabled(self) -> bool:
        """检查是否已启用开机自启"""
        try:
            import winreg
            key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_READ)
            try:
                winreg.QueryValueEx(key, "AstrBotDesktopClient")
                return True
            except FileNotFoundError:
                return False
            finally:
                winreg.CloseKey(key)
        except Exception as e:
            print(f"[Windows] 检查开机自启状态失败: {e}")
            return False