"""
更新服务模块

实现应用程序更新功能，包括：
- 检查 GitHub 是否有新版本（支持 Release 稳定版和 Git 最新版两种模式）
- 执行更新脚本（update.bat/update.sh）
- 定时检查更新任务
"""

import os
import sys
import subprocess
import logging
import asyncio
import platform
import re
from datetime import datetime
from typing import Optional, Tuple, Dict, Any
from pathlib import Path

try:
    from PySide6.QtCore import QObject, Signal, QTimer

    HAS_PYSIDE6 = True
except ImportError:
    try:
        from PyQt6.QtCore import QObject, pyqtSignal as Signal, QTimer

        HAS_PYSIDE6 = False
    except ImportError:
        HAS_PYSIDE6 = None

try:
    import aiohttp

    HAS_AIOHTTP = True
except ImportError:
    HAS_AIOHTTP = False

from ..config import UpdateConfig


# 配置日志
logger = logging.getLogger(__name__)


class UpdateService(QObject):
    """
    更新服务

    管理应用程序更新功能，包括：
    - 检查 GitHub 是否有新版本
    - 执行更新脚本
    - 定时检查任务
    """

    # 信号定义
    update_available = Signal(str, str)  # (当前版本, 最新版本)
    update_completed = Signal(bool, str)  # (是否成功, 消息)
    update_failed = Signal(str)  # 错误消息
    check_started = Signal()  # 开始检查更新
    check_finished = Signal(bool, str)  # (是否有更新, 最新版本或错误消息)

    def __init__(
        self,
        config: Optional[UpdateConfig] = None,
        project_dir: Optional[str] = None,
        parent: Optional[QObject] = None,
    ):
        """
        初始化更新服务

        Args:
            config: 更新配置，不指定则使用默认配置
            project_dir: 项目目录，不指定则自动检测
            parent: 父对象
        """
        super().__init__(parent)

        self._config = config or UpdateConfig()
        self._project_dir = project_dir or self._detect_project_dir()
        self._is_checking = False
        self._latest_version: Optional[str] = None
        self._current_version: Optional[str] = None

        # 创建定时检查计时器
        self._schedule_timer = QTimer(self)
        self._schedule_timer.timeout.connect(self._on_schedule_check)
        self._schedule_timer.setInterval(60 * 1000)  # 每分钟检查一次是否到达计划时间

        # 启动时获取当前版本
        self._current_version = self._get_current_version()

        logger.info(f"UpdateService 初始化完成，项目目录: {self._project_dir}")
        logger.info(f"当前版本: {self._current_version}")

    @property
    def is_checking(self) -> bool:
        """是否正在检查更新"""
        return self._is_checking

    @property
    def config(self) -> UpdateConfig:
        """获取当前配置"""
        return self._config

    @property
    def current_version(self) -> str:
        """获取当前版本"""
        return self._current_version or "unknown"

    @property
    def latest_version(self) -> Optional[str]:
        """获取最新版本（上次检查结果）"""
        return self._latest_version

    @property
    def last_check_time(self) -> str:
        """获取上次检查时间"""
        return self._config.last_check_time

    def _detect_project_dir(self) -> str:
        """
        自动检测项目目录

        Returns:
            项目目录路径
        """
        # 尝试从模块路径推断
        try:
            if getattr(sys, "frozen", False):
                # 打包后的可执行文件
                return str(Path(sys.executable).parent)
            else:
                # 开发模式
                # __file__ 位于 desktop_client/services/update_service.py
                return str(Path(__file__).parent.parent.parent)
        except Exception as e:
            logger.error(f"检测项目目录失败: {e}")
            return os.getcwd()

    def _get_current_version(self) -> Optional[str]:
        """
        获取当前版本

        根据更新模式返回不同格式的版本：
        - release 模式: 尝试获取 git tag，如 "v1.0.0"
        - git 模式: 返回 commit hash

        Returns:
            版本号或 None
        """
        try:
            if self._config.update_mode == "release":
                # 尝试获取当前 tag
                result = subprocess.run(
                    ["git", "describe", "--tags", "--abbrev=0"],
                    cwd=self._project_dir,
                    capture_output=True,
                    text=True,
                    timeout=10,
                )
                if result.returncode == 0 and result.stdout.strip():
                    return result.stdout.strip()
                # 如果没有 tag，返回 commit hash

            # 默认返回 commit hash
            result = subprocess.run(
                ["git", "log", "-1", "--format=%h"],
                cwd=self._project_dir,
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode == 0:
                return result.stdout.strip()
        except Exception as e:
            logger.error(f"获取当前版本失败: {e}")
        return None

    def _get_current_commit_date(self) -> Optional[str]:
        """
        获取当前 commit 的日期

        Returns:
            日期字符串
        """
        try:
            result = subprocess.run(
                ["git", "log", "-1", "--format=%ci"],
                cwd=self._project_dir,
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode == 0:
                return result.stdout.strip()
        except Exception as e:
            logger.error(f"获取 commit 日期失败: {e}")
        return None

    async def check_for_update(self) -> Tuple[bool, str, str]:
        """
        检查 GitHub 是否有新版本

        根据 update_mode 配置选择检查方式：
        - "release": 检查 GitHub Releases 的最新稳定版
        - "git": 检查 Git 仓库的最新代码

        Returns:
            (是否有更新, 当前版本, 最新版本或错误消息)
        """
        if self._is_checking:
            return False, self.current_version, "正在检查中..."

        self._is_checking = True
        self.check_started.emit()

        try:
            # 获取当前版本
            current = self._get_current_version()
            if not current:
                self._is_checking = False
                self.check_finished.emit(False, "无法获取当前版本")
                return False, "unknown", "无法获取当前版本"

            self._current_version = current

            # 根据更新模式选择检查方式
            if self._config.update_mode == "release":
                return await self._check_release_update(current)
            else:
                return await self._check_git_update(current)

        except Exception as e:
            logger.error(f"检查更新失败: {e}")
            self._is_checking = False
            self.check_finished.emit(False, str(e))
            return False, self.current_version, str(e)

    async def _check_release_update(self, current: str) -> Tuple[bool, str, str]:
        """
        检查 GitHub Release 更新（稳定版模式）

        Args:
            current: 当前版本号

        Returns:
            (是否有更新, 当前版本, 最新版本或错误消息)
        """
        try:
            release_info = await self._get_latest_release()

            if release_info is None:
                self._is_checking = False
                self.check_finished.emit(False, "无法获取 Release 信息")
                return False, current, "无法获取 Release 信息（可能还没有发布 Release）"

            latest_version = release_info.get("tag_name", "")
            download_url = release_info.get("html_url", "")

            # 保存 Release 信息
            self._config.latest_release_version = latest_version
            self._config.latest_release_url = download_url

            self._latest_version = latest_version
            self._update_last_check_time()

            # 比较版本
            has_update = self._compare_versions(current, latest_version)

            if has_update:
                self.update_available.emit(current, latest_version)

            self.check_finished.emit(has_update, latest_version)
            self._is_checking = False

            return has_update, current, latest_version

        except Exception as e:
            logger.error(f"检查 Release 更新失败: {e}")
            self._is_checking = False
            self.check_finished.emit(False, str(e))
            return False, current, str(e)

    async def _check_git_update(self, current: str) -> Tuple[bool, str, str]:
        """
        检查 Git 最新代码更新（开发版模式）

        Args:
            current: 当前版本号

        Returns:
            (是否有更新, 当前版本, 最新版本或错误消息)
        """
        # 使用 git fetch 获取远程最新信息
        fetch_result = await self._run_git_command(
            ["git", "fetch", "origin", "--depth", "1"]
        )
        if not fetch_result[0]:
            # 尝试使用 API
            has_update, latest = await self._check_via_api()
            self._is_checking = False

            if has_update is None:
                self.check_finished.emit(False, latest)
                return False, current, latest

            self._latest_version = latest
            self._update_last_check_time()

            if has_update:
                self.update_available.emit(current, latest)

            self.check_finished.emit(has_update, latest)
            return has_update, current, latest

        # 获取远程最新 commit
        result = await self._run_git_command(
            ["git", "rev-parse", "--short", "origin/main"]
        )
        if not result[0]:
            # 尝试 master 分支
            result = await self._run_git_command(
                ["git", "rev-parse", "--short", "origin/master"]
            )

        if not result[0]:
            self._is_checking = False
            self.check_finished.emit(False, "无法获取远程版本")
            return False, current, "无法获取远程版本"

        latest = result[1].strip()
        self._latest_version = latest
        self._update_last_check_time()

        has_update = current != latest

        if has_update:
            self.update_available.emit(current, latest)

        self.check_finished.emit(has_update, latest)
        self._is_checking = False

        return has_update, current, latest

    async def _get_latest_release(self) -> Optional[Dict[str, Any]]:
        """
        从 GitHub API 获取最新 Release 信息

        Returns:
            Release 信息字典或 None
        """
        if not HAS_AIOHTTP:
            logger.warning("aiohttp 库未安装，无法通过 API 检查 Release")
            return None

        try:
            # 解析仓库 URL
            repo_url = self._config.repo_url
            parts = repo_url.rstrip("/").split("/")
            owner = parts[-2]
            repo = parts[-1]

            api_url = f"https://api.github.com/repos/{owner}/{repo}/releases/latest"

            async with aiohttp.ClientSession() as session:
                headers = {
                    "Accept": "application/vnd.github.v3+json",
                    "User-Agent": "AstrBot-Desktop-Assistant",
                }
                async with session.get(
                    api_url, headers=headers, timeout=aiohttp.ClientTimeout(total=30)
                ) as response:
                    if response.status == 200:
                        return await response.json()
                    elif response.status == 404:
                        logger.info("仓库暂无 Release 发布")
                        return None
                    else:
                        logger.error(f"GitHub API 请求失败: {response.status}")
                        return None

        except Exception as e:
            logger.error(f"获取 Release 信息失败: {e}")
            return None

    def _compare_versions(self, current: str, latest: str) -> bool:
        """
        比较版本号，判断是否需要更新

        支持的版本格式:
        - 语义化版本: v1.0.0, 1.0.0, v1.2.3-beta
        - Commit hash: abc1234

        Args:
            current: 当前版本
            latest: 最新版本

        Returns:
            True 如果需要更新
        """
        if not current or not latest:
            return False

        # 如果完全相同，不需要更新
        if current == latest:
            return False

        # 尝试解析语义化版本
        current_ver = self._parse_version(current)
        latest_ver = self._parse_version(latest)

        if current_ver and latest_ver:
            # 比较语义化版本
            return latest_ver > current_ver

        # 如果无法解析为语义化版本，简单比较字符串
        # 对于 commit hash，只要不同就认为有更新
        return current != latest

    def _parse_version(self, version: str) -> Optional[Tuple[int, int, int]]:
        """
        解析语义化版本号

        Args:
            version: 版本字符串，如 "v1.2.3" 或 "1.2.3"

        Returns:
            (major, minor, patch) 元组或 None
        """
        # 移除 'v' 前缀
        version = version.lstrip("v")

        # 移除预发布后缀 (如 -beta, -rc.1)
        version = version.split("-")[0]

        # 尝试解析
        match = re.match(r"^(\d+)\.(\d+)\.(\d+)", version)
        if match:
            return (int(match.group(1)), int(match.group(2)), int(match.group(3)))

        return None

    async def _check_via_api(self) -> Tuple[Optional[bool], str]:
        """
        通过 GitHub API 检查更新

        Returns:
            (是否有更新, 最新版本或错误消息)
            如果检查失败，has_update 为 None
        """
        if not HAS_AIOHTTP:
            return None, "aiohttp 库未安装，无法通过 API 检查更新"

        try:
            # 解析仓库 URL
            repo_url = self._config.repo_url
            # 从 URL 提取 owner/repo
            parts = repo_url.rstrip("/").split("/")
            owner = parts[-2]
            repo = parts[-1]

            api_url = f"https://api.github.com/repos/{owner}/{repo}/commits/main"

            async with aiohttp.ClientSession() as session:
                async with session.get(
                    api_url, timeout=aiohttp.ClientTimeout(total=30)
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        latest_sha = data.get("sha", "")[:7]

                        has_update = latest_sha != self._current_version
                        return has_update, latest_sha
                    else:
                        # 尝试 master 分支
                        api_url = f"https://api.github.com/repos/{owner}/{repo}/commits/master"
                        async with session.get(
                            api_url, timeout=aiohttp.ClientTimeout(total=30)
                        ) as response2:
                            if response2.status == 200:
                                data = await response2.json()
                                latest_sha = data.get("sha", "")[:7]

                                has_update = latest_sha != self._current_version
                                return has_update, latest_sha
                            else:
                                return None, f"API 请求失败: {response2.status}"

        except Exception as e:
            logger.error(f"API 检查更新失败: {e}")
            return None, str(e)

    async def _run_git_command(self, cmd: list) -> Tuple[bool, str]:
        """
        异步运行 Git 命令

        Args:
            cmd: 命令列表

        Returns:
            (是否成功, 输出或错误消息)
        """
        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                cwd=self._project_dir,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=30)

            if process.returncode == 0:
                return True, stdout.decode("utf-8", errors="replace")
            else:
                return False, stderr.decode("utf-8", errors="replace")

        except asyncio.TimeoutError:
            return False, "命令执行超时"
        except Exception as e:
            return False, str(e)

    def _update_last_check_time(self):
        """更新上次检查时间"""
        self._config.last_check_time = datetime.now().isoformat()

    def perform_update(self) -> bool:
        """
        执行更新操作

        根据更新模式选择不同的更新方式：
        - release 模式: 调用更新脚本，更新到指定 tag
        - git 模式: 调用更新脚本，拉取最新代码

        Returns:
            是否成功启动更新
        """
        try:
            system = platform.system().lower()

            # 确定更新脚本参数
            update_mode = self._config.update_mode
            target_version = ""

            if update_mode == "release" and self._config.latest_release_version:
                target_version = self._config.latest_release_version

            if system == "windows":
                script_path = os.path.join(self._project_dir, "update.bat")
                if not os.path.exists(script_path):
                    self.update_failed.emit("找不到 update.bat 更新脚本")
                    return False

                # 构建命令，传递更新模式和目标版本
                cmd = ["cmd", "/c", "start", "cmd", "/k", script_path]
                if update_mode == "release" and target_version:
                    cmd = [
                        "cmd",
                        "/c",
                        "start",
                        "cmd",
                        "/k",
                        script_path,
                        "release",
                        target_version,
                    ]

                # 使用 start 命令在新窗口中运行
                subprocess.Popen(cmd, cwd=self._project_dir, shell=False)

            elif system in ("linux", "darwin"):
                script_path = os.path.join(self._project_dir, "update.sh")
                if not os.path.exists(script_path):
                    self.update_failed.emit("找不到 update.sh 更新脚本")
                    return False

                # 确保脚本有执行权限
                os.chmod(script_path, 0o755)

                # 构建命令
                script_args = [script_path]
                if update_mode == "release" and target_version:
                    script_args = [script_path, "release", target_version]

                # 在新终端中运行
                if system == "darwin":
                    # macOS
                    subprocess.Popen(
                        ["open", "-a", "Terminal"] + script_args, cwd=self._project_dir
                    )
                else:
                    # Linux - 尝试多种终端
                    terminals = [
                        ["gnome-terminal", "--"] + ["bash"] + script_args,
                        ["xterm", "-e", f"bash {' '.join(script_args)}"],
                        ["konsole", "-e", f"bash {' '.join(script_args)}"],
                    ]

                    for terminal_cmd in terminals:
                        try:
                            subprocess.Popen(terminal_cmd, cwd=self._project_dir)
                            break
                        except FileNotFoundError:
                            continue
                    else:
                        # 如果没有找到终端，直接在后台运行
                        subprocess.Popen(["bash"] + script_args, cwd=self._project_dir)
            else:
                self.update_failed.emit(f"不支持的操作系统: {system}")
                return False

            mode_text = "稳定版" if update_mode == "release" else "最新版"
            logger.info(f"更新脚本已启动 (模式: {mode_text})")
            self.update_completed.emit(
                True, f"更新脚本已启动 (模式: {mode_text})，请查看更新窗口"
            )

            # 如果配置了自动重启，退出当前程序
            if self._config.auto_restart:
                logger.info("配置了自动重启，将在 3 秒后退出...")
                QTimer.singleShot(3000, self._exit_for_restart)

            return True

        except Exception as e:
            error_msg = f"启动更新失败: {e}"
            logger.error(error_msg)
            self.update_failed.emit(error_msg)
            return False

    def _exit_for_restart(self):
        """退出程序以便重启"""
        logger.info("程序退出以便更新后重启")
        sys.exit(0)

    def start_scheduled_checks(self) -> bool:
        """
        启动定时检查任务

        Returns:
            是否成功启动
        """
        if not self._config.enabled:
            logger.info("自动更新未启用，不启动定时检查")
            return False

        if not self._config.scheduled_times:
            logger.info("未配置定时检查时间")
            return False

        self._schedule_timer.start()
        logger.info(f"定时检查任务已启动，计划时间: {self._config.scheduled_times}")
        return True

    def stop_scheduled_checks(self):
        """停止定时检查任务"""
        self._schedule_timer.stop()
        logger.info("定时检查任务已停止")

    def _on_schedule_check(self):
        """定时检查回调"""
        if not self._config.enabled:
            return

        now = datetime.now()
        current_time = now.strftime("%H:%M")

        # 检查是否匹配任何计划时间
        for scheduled_time in self._config.scheduled_times:
            if current_time == scheduled_time:
                # 避免在同一分钟内重复检查
                last_check = self._config.last_check_time
                if last_check:
                    try:
                        last_dt = datetime.fromisoformat(last_check)
                        if (now - last_dt).total_seconds() < 120:  # 2分钟内不重复检查
                            return
                    except Exception:
                        pass

                logger.info(f"到达计划检查时间 {scheduled_time}，开始检查更新")
                # 异步执行检查
                asyncio.create_task(self.check_for_update())
                break

    def update_config(self, config: UpdateConfig):
        """
        更新配置（运行时）

        Args:
            config: 新的配置
        """
        was_running = self._schedule_timer.isActive()

        if was_running:
            self.stop_scheduled_checks()

        self._config = config
        logger.info("更新配置已更新")

        if was_running and config.enabled:
            self.start_scheduled_checks()

    def get_status(self) -> dict:
        """
        获取服务状态

        Returns:
            状态信息字典
        """
        has_update = False
        if self._latest_version and self._current_version:
            if self._config.update_mode == "release":
                has_update = self._compare_versions(
                    self._current_version, self._latest_version
                )
            else:
                has_update = self._current_version != self._latest_version

        return {
            "enabled": self._config.enabled,
            "is_checking": self._is_checking,
            "current_version": self._current_version,
            "latest_version": self._latest_version,
            "last_check_time": self._config.last_check_time,
            "check_on_startup": self._config.check_on_startup,
            "scheduled_times": self._config.scheduled_times,
            "auto_restart": self._config.auto_restart,
            "has_update": has_update,
            "project_dir": self._project_dir,
            "update_mode": self._config.update_mode,
            "latest_release_version": self._config.latest_release_version,
            "latest_release_url": self._config.latest_release_url,
        }
