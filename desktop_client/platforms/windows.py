"""
Windows 平台适配器

实现 Windows 系统的平台功能：
- 活动窗口检测
- 运行应用获取
- 开机自启管理
"""

import os
import sys
import logging
from pathlib import Path
from typing import List, Optional

from .base import IPlatformAdapter, WindowInfo, AppInfo, Result

# 配置日志
logger = logging.getLogger(__name__)


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
    
    def _get_project_root(self) -> Path:
        """获取项目根目录
        
        通过多种方式检测项目根目录，确保在不同安装场景下都能正确找到。
        
        Returns:
            Path: 项目根目录路径
        """
        # 方式1：如果是打包后的可执行文件，使用可执行文件所在目录
        if getattr(sys, 'frozen', False):
            return Path(sys.executable).parent
        
        # 方式2：通过当前模块路径推断
        # 当前文件: desktop_client/platforms/windows.py
        # 项目根目录: desktop_client 的父目录
        current_file = Path(__file__).resolve()
        # platforms -> desktop_client -> project_root
        project_root = current_file.parent.parent.parent
        
        # 验证：检查是否存在 desktop_client 目录
        if (project_root / "desktop_client").is_dir():
            return project_root
        
        # 方式3：通过环境变量（如果设置了）
        env_root = os.environ.get('ASTRBOT_PROJECT_ROOT')
        if env_root:
            env_path = Path(env_root)
            if env_path.is_dir() and (env_path / "desktop_client").is_dir():
                return env_path
        
        # 方式4：使用当前工作目录
        cwd = Path.cwd()
        if (cwd / "desktop_client").is_dir():
            return cwd
        
        # 回退到推断的路径
        logger.warning(f"[Windows] 无法确定项目根目录，使用推断路径: {project_root}")
        return project_root
    
    def _find_pythonw(self) -> Optional[Path]:
        """查找 pythonw.exe 路径
        
        按优先级查找：
        1. 当前 Python 解释器同目录下的 pythonw.exe
        2. 虚拟环境中的 pythonw.exe
        3. 系统 PATH 中的 pythonw.exe
        
        Returns:
            Optional[Path]: pythonw.exe 路径，未找到返回 None
        """
        python_path = Path(sys.executable)
        
        # 方式1：同目录下的 pythonw.exe
        pythonw_path = python_path.parent / "pythonw.exe"
        if pythonw_path.exists():
            logger.info(f"[Windows] 找到 pythonw.exe: {pythonw_path}")
            return pythonw_path
        
        # 方式2：检查 Scripts 目录（虚拟环境）
        scripts_pythonw = python_path.parent / "Scripts" / "pythonw.exe"
        if scripts_pythonw.exists():
            logger.info(f"[Windows] 找到虚拟环境 pythonw.exe: {scripts_pythonw}")
            return scripts_pythonw
        
        # 方式3：检查父目录（某些虚拟环境结构）
        parent_pythonw = python_path.parent.parent / "pythonw.exe"
        if parent_pythonw.exists():
            logger.info(f"[Windows] 找到父目录 pythonw.exe: {parent_pythonw}")
            return parent_pythonw
        
        # 方式4：通过 where 命令查找
        try:
            import subprocess
            result = subprocess.run(
                ["where", "pythonw.exe"],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0 and result.stdout.strip():
                found_path = Path(result.stdout.strip().split('\n')[0])
                if found_path.exists():
                    logger.info(f"[Windows] 通过 where 命令找到 pythonw.exe: {found_path}")
                    return found_path
        except Exception as e:
            logger.debug(f"[Windows] where 命令查找失败: {e}")
        
        logger.warning("[Windows] 未找到 pythonw.exe，将使用 python.exe（可能显示控制台窗口）")
        return None
    
    def _get_app_path(self) -> str:
        """获取应用程序路径"""
        if getattr(sys, 'frozen', False):
            # PyInstaller 打包后的可执行文件
            return sys.executable
        else:
            # 开发模式下，优先使用 pythonw.exe 避免控制台窗口
            pythonw = self._find_pythonw()
            if pythonw:
                return str(pythonw)
            return sys.executable
    
    def _get_startup_command(self) -> str:
        """获取启动命令（包含工作目录）"""
        if getattr(sys, 'frozen', False):
            return f'"{sys.executable}"'
        else:
            project_root = self._get_project_root()
            
            # 创建一个启动脚本来隐藏控制台窗口
            vbs_path = self._create_silent_launcher(project_root)
            return f'wscript.exe "{vbs_path}"'
    
    def _create_silent_launcher(self, project_root: Path) -> str:
        """创建静默启动器脚本（VBS），避免显示黑框
        
        Args:
            project_root: 项目根目录
            
        Returns:
            str: VBS 脚本文件路径
        """
        # 获取 Python 解释器路径
        python_path = self._get_app_path()
        
        # 规范化路径，使用双反斜杠
        project_root_str = str(project_root).replace('\\', '\\\\')
        python_path_str = python_path.replace('\\', '\\\\')
        
        # VBS 脚本内容
        # 添加 --autostart 参数，让应用知道这是开机自启，可以使用更长的启动延迟
        # 添加错误处理和日志记录
        vbs_content = f'''
' AstrBot Desktop Assistant 开机自启脚本
' 自动生成，请勿手动修改

On Error Resume Next

Set WshShell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")

' 设置工作目录
projectRoot = "{project_root_str}"
pythonPath = "{python_path_str}"

' 检查目录是否存在
If Not fso.FolderExists(projectRoot) Then
    ' 尝试使用脚本所在目录
    scriptPath = WScript.ScriptFullName
    scriptDir = fso.GetParentFolderName(scriptPath)
    ' 配置目录的父目录可能是项目根目录
    parentDir = fso.GetParentFolderName(scriptDir)
    If fso.FolderExists(parentDir & "\\desktop_client") Then
        projectRoot = parentDir
    End If
End If

' 切换到项目目录
WshShell.CurrentDirectory = projectRoot

' 延迟启动（等待网络和其他服务就绪）
WScript.Sleep 5000

' 启动应用程序
cmd = """" & pythonPath & """ -m desktop_client --autostart"
WshShell.Run cmd, 0, False

If Err.Number <> 0 Then
    ' 记录错误日志
    Set logFile = fso.OpenTextFile(scriptDir & "\\autostart_error.log", 8, True)
    logFile.WriteLine Now() & " - 启动失败: " & Err.Description
    logFile.Close
End If
'''
        
        # 保存到用户配置目录
        from ..config import ClientConfig
        config_dir = ClientConfig.get_config_dir()
        vbs_path = config_dir / "autostart_launcher.vbs"
        
        try:
            with open(vbs_path, 'w', encoding='utf-8') as f:
                f.write(vbs_content.strip())
            
            logger.info(f"[Windows] 创建静默启动器: {vbs_path}")
            print(f"[Windows] 创建静默启动器: {vbs_path}")
            
            # 同时保存项目根目录信息，便于调试
            info_path = config_dir / "autostart_info.txt"
            with open(info_path, 'w', encoding='utf-8') as f:
                f.write(f"项目根目录: {project_root}\n")
                f.write(f"Python路径: {python_path}\n")
                f.write(f"VBS脚本: {vbs_path}\n")
                f.write(f"创建时间: {__import__('datetime').datetime.now()}\n")
            
        except Exception as e:
            logger.error(f"[Windows] 创建启动器失败: {e}")
            print(f"[Windows] 创建启动器失败: {e}")
        
        return str(vbs_path)
    
    def enable_autostart(self) -> Result:
        """启用开机自启"""
        try:
            import winreg
            key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_SET_VALUE)
            
            startup_cmd = self._get_startup_command()
            winreg.SetValueEx(key, "AstrBotDesktopClient", 0, winreg.REG_SZ, startup_cmd)
            winreg.CloseKey(key)
            
            logger.info(f"[Windows] 已启用开机自启: {startup_cmd}")
            print(f"[Windows] 已启用开机自启: {startup_cmd}")
            
            # 验证注册表写入是否成功
            if self.is_autostart_enabled():
                return Result.success("开机自启已启用")
            else:
                return Result.failed("注册表写入后验证失败")
                
        except PermissionError:
            logger.error("[Windows] 没有足够的权限修改注册表")
            return Result.failed("没有足够的权限修改注册表")
        except Exception as e:
            logger.error(f"[Windows] 启用开机自启失败: {e}")
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
                logger.info("[Windows] 已禁用开机自启")
                print("[Windows] 已禁用开机自启")
            except FileNotFoundError:
                # 值不存在，无需删除
                logger.debug("[Windows] 开机自启项不存在，无需删除")
            
            winreg.CloseKey(key)
            
            # 清理 VBS 启动器文件
            self._cleanup_autostart_files()
            
            return Result.success("开机自启已禁用")
        except PermissionError:
            logger.error("[Windows] 没有足够的权限修改注册表")
            return Result.failed("没有足够的权限修改注册表")
        except Exception as e:
            logger.error(f"[Windows] 禁用开机自启失败: {e}")
            print(f"[Windows] 禁用开机自启失败: {e}")
            return Result.failed(f"禁用失败: {str(e)}")
    
    def _cleanup_autostart_files(self):
        """清理开机自启相关文件"""
        try:
            from ..config import ClientConfig
            config_dir = ClientConfig.get_config_dir()
            
            # 删除 VBS 启动器
            vbs_path = config_dir / "autostart_launcher.vbs"
            if vbs_path.exists():
                vbs_path.unlink()
                logger.info(f"[Windows] 已删除启动器: {vbs_path}")
            
            # 删除信息文件
            info_path = config_dir / "autostart_info.txt"
            if info_path.exists():
                info_path.unlink()
            
            # 删除错误日志
            error_log = config_dir / "autostart_error.log"
            if error_log.exists():
                error_log.unlink()
                
        except Exception as e:
            logger.warning(f"[Windows] 清理启动器文件失败: {e}")
    
    def is_autostart_enabled(self) -> bool:
        """检查是否已启用开机自启"""
        try:
            import winreg
            key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_READ)
            try:
                value, _ = winreg.QueryValueEx(key, "AstrBotDesktopClient")
                # 验证注册的命令是否仍然有效
                if value:
                    # 提取 VBS 路径进行验证
                    if 'wscript.exe' in value.lower():
                        # 提取引号中的路径
                        import re
                        match = re.search(r'"([^"]+\.vbs)"', value)
                        if match:
                            vbs_path = Path(match.group(1))
                            if not vbs_path.exists():
                                logger.warning(f"[Windows] VBS 启动器不存在: {vbs_path}")
                                # 注册表项存在但文件不存在，需要重新创建
                                return True  # 仍然返回 True，让用户知道需要重新启用
                    return True
                return False
            except FileNotFoundError:
                return False
            finally:
                winreg.CloseKey(key)
        except Exception as e:
            logger.error(f"[Windows] 检查开机自启状态失败: {e}")
            print(f"[Windows] 检查开机自启状态失败: {e}")
            return False
    
    def get_autostart_info(self) -> dict:
        """获取开机自启详细信息（用于调试）"""
        info = {
            'enabled': False,
            'command': '',
            'vbs_exists': False,
            'vbs_path': '',
            'project_root': str(self._get_project_root()),
            'python_path': self._get_app_path(),
        }
        
        try:
            import winreg
            key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_READ)
            try:
                value, _ = winreg.QueryValueEx(key, "AstrBotDesktopClient")
                info['enabled'] = True
                info['command'] = value
                
                # 检查 VBS 文件是否存在
                import re
                match = re.search(r'"([^"]+\.vbs)"', value)
                if match:
                    vbs_path = Path(match.group(1))
                    info['vbs_path'] = str(vbs_path)
                    info['vbs_exists'] = vbs_path.exists()
                    
            except FileNotFoundError:
                pass
            finally:
                winreg.CloseKey(key)
        except Exception as e:
            info['error'] = str(e)
        
        return info