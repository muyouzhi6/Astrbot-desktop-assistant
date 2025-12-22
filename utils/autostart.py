"""
开机自启管理模块

提供 Windows 系统开机自启功能的管理。
使用注册表方式实现开机自启。
"""

import os
import sys
from typing import Tuple


def get_app_path() -> str:
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
        
        # 获取 desktop_client 模块路径
        module_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        return f'"{python_path}" -m desktop_client'


def get_startup_command() -> str:
    """获取启动命令（包含工作目录）"""
    if getattr(sys, 'frozen', False):
        return f'"{sys.executable}"'
    else:
        python_path = sys.executable
        pythonw_path = python_path.replace('python.exe', 'pythonw.exe')
        if os.path.exists(pythonw_path):
            python_path = pythonw_path
        
        # 获取项目根目录（desktop_client 的父目录）
        module_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        project_root = os.path.dirname(module_path)
        
        # 使用 cmd /c 切换到工作目录后再启动
        return f'cmd /c "cd /d "{project_root}" && "{python_path}" -m desktop_client"'


def is_autostart_enabled() -> bool:
    """检查是否已启用开机自启"""
    if os.name != 'nt':
        return False
    
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
        print(f"[AutoStart] 检查开机自启状态失败: {e}")
        return False


def enable_autostart() -> Tuple[bool, str]:
    """启用开机自启"""
    if os.name != 'nt':
        return False, "开机自启仅支持 Windows 系统"
    
    try:
        import winreg
        key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_SET_VALUE)
        
        startup_cmd = get_startup_command()
        winreg.SetValueEx(key, "AstrBotDesktopClient", 0, winreg.REG_SZ, startup_cmd)
        winreg.CloseKey(key)
        
        print(f"[AutoStart] 已启用开机自启: {startup_cmd}")
        return True, "开机自启已启用"
    except PermissionError:
        return False, "没有足够的权限修改注册表"
    except Exception as e:
        print(f"[AutoStart] 启用开机自启失败: {e}")
        return False, f"启用失败: {str(e)}"


def disable_autostart() -> Tuple[bool, str]:
    """禁用开机自启"""
    if os.name != 'nt':
        return False, "开机自启仅支持 Windows 系统"
    
    try:
        import winreg
        key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_SET_VALUE)
        
        try:
            winreg.DeleteValue(key, "AstrBotDesktopClient")
            print("[AutoStart] 已禁用开机自启")
        except FileNotFoundError:
            # 值不存在，无需删除
            pass
        
        winreg.CloseKey(key)
        return True, "开机自启已禁用"
    except PermissionError:
        return False, "没有足够的权限修改注册表"
    except Exception as e:
        print(f"[AutoStart] 禁用开机自启失败: {e}")
        return False, f"禁用失败: {str(e)}"


def set_autostart(enabled: bool) -> Tuple[bool, str]:
    """设置开机自启状态"""
    if enabled:
        return enable_autostart()
    else:
        return disable_autostart()