"""
AstrBot HTTP API 客户端

负责与远程 AstrBot 服务器通信，包括：
- 登录认证
- 会话管理
- 消息发送/接收（SSE 流式）
- 文件上传/下载
"""

import asyncio
import hashlib
import json
import os
import time
import warnings
from dataclasses import dataclass
from enum import Enum
from typing import Optional, Callable, AsyncGenerator, Any

import httpx
import websockets

# 忽略 httpcore 的异步生成器清理警告（这是 httpcore 的已知问题）
warnings.filterwarnings("ignore", message="async generator ignored GeneratorExit")
# 忽略 cancel scope 相关的警告
warnings.filterwarnings("ignore", message="Attempted to exit cancel scope")


class ConnectionState(Enum):
    """连接状态"""

    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    RECONNECTING = "reconnecting"
    ERROR = "error"


@dataclass
class SSEEvent:
    """SSE 事件"""

    event_type: str  # plain, image, record, file, end, complete, break, message_saved
    data: str
    streaming: bool = False
    chain_type: str = "normal"  # normal, reasoning
    raw: Optional[dict] = None


class WebSocketClient:
    """WebSocket 客户端，用于实时双向通信

    稳定性增强（参考 Satori 适配器的成功模式）：
    - 心跳间隔从 25 秒降到 10 秒
    - 自动响应服务端 server_ping
    - 支持忙碌状态报告，长操作时延长超时
    """

    # 心跳配置常量 - 优化稳定性：PING_TIMEOUT 必须大于 PING_INTERVAL
    PING_INTERVAL = 20  # WebSocket 底层心跳间隔（秒）
    PING_TIMEOUT = 40  # WebSocket 底层心跳超时（秒）- 必须大于 PING_INTERVAL 的 2 倍
    HEARTBEAT_INTERVAL = 15  # 应用层心跳间隔（秒）- 比 PING_INTERVAL 稍小
    # 服务端 CLIENT_INACTIVE_TIMEOUT = 60 秒，BUSY_STATE_TIMEOUT_EXTENSION = 120 秒
    # 忙碌状态下总超时 = 60 + 120 = 180 秒，这里设置为稍小的值以适配忙碌状态
    HEARTBEAT_ACK_TIMEOUT = 90  # 心跳响应超时阈值（秒）- 增加到 90 秒以匹配忙碌状态

    # 连接质量监控阈值
    HIGH_LATENCY_THRESHOLD = 5.0  # 高延迟阈值（秒）
    MAX_HIGH_LATENCY_COUNT = 3  # 连续高延迟次数阈值，超过则重连

    # 重连配置
    BASE_RECONNECT_DELAY = 1  # 基础重连延迟（秒）
    MAX_RECONNECT_DELAY = 60  # 最大重连延迟（秒）
    RECONNECT_JITTER = 0.5  # 重连抖动因子（避免同时重连）

    def __init__(
        self,
        server_url: str,
        token: str,
        session_id: str,
        on_message: Optional[Callable[[dict], None]] = None,
        on_command: Optional[Callable[[str, str, dict], Any]] = None,
        on_connection_state: Optional[Callable[[str], None]] = None,
        on_reconnect: Optional[Callable[[], None]] = None,
        ws_port: Optional[int] = None,
    ):
        """
        初始化 WebSocket 客户端

        Args:
            ws_port: WebSocket 服务端口。
                     - 如果指定了端口（如 6190），将连接到该独立端口
                     - 如果为 None，将复用 API 端口（统一端口模式）
            on_connection_state: 连接状态变化回调，参数为状态字符串
            on_reconnect: 重连成功回调，用于通知上层重置状态
        """
        # 解析服务器 URL，提取 host 和 port
        from urllib.parse import urlparse

        parsed = urlparse(server_url)
        host = parsed.hostname or "localhost"
        scheme = "wss" if parsed.scheme == "https" else "ws"

        # 获取 API 端口
        api_port = parsed.port
        if not api_port:
            api_port = 443 if parsed.scheme == "https" else 80

        # 端口选择逻辑：
        # - 如果显式指定了 ws_port，使用指定的端口（独立端口模式）
        # - 否则复用 API 端口（统一端口模式）
        if ws_port is not None:
            port = ws_port
            print(f"[WebSocket] 使用独立端口模式: {port}")
        else:
            port = api_port
            print(f"[WebSocket] 使用统一端口模式 (复用 API 端口): {port}")

        # 构建 WebSocket URL
        self.url = (
            f"{scheme}://{host}:{port}/ws/client?token={token}&session_id={session_id}"
        )
        self.session_id = session_id

        # 详细日志：帮助调试连接问题
        print("[WebSocket] 初始化:")
        print(f"  - 源 server_url: {server_url}")
        print(f"  - 解析 host: {host}")
        print(f"  - 目标端口: {port}")
        print(f"  - 最终 URL: {self.url}")

        self.on_message = on_message
        self.on_command = (
            on_command  # 命令处理回调: (command, request_id, params) -> result
        )
        self.on_connection_state = on_connection_state  # 连接状态回调
        self.on_reconnect = on_reconnect  # 重连成功回调
        self.ws = None

        self._running = False
        self._reconnect_task: Optional[asyncio.Task] = None
        self._heartbeat_task: Optional[asyncio.Task] = None
        self._pong_monitor_task: Optional[asyncio.Task] = None

        # 心跳状态跟踪
        self._last_heartbeat_ack: float = 0  # 上次收到心跳响应的时间
        self._last_heartbeat_sent: float = 0  # 上次发送心跳的时间
        self._heartbeat_failures: int = 0  # 连续心跳失败次数
        self._max_heartbeat_failures: int = 3  # 最大允许连续失败次数

        # websockets 库底层 pong 监控
        self._last_pong_time: float = 0  # 上次收到底层 pong 的时间

        # 连接质量监控
        self._connection_state: str = (
            "disconnected"  # disconnected, connecting, connected, reconnecting
        )
        self._last_message_time: float = 0  # 上次收到消息的时间
        self._total_reconnects: int = 0  # 总重连次数
        self._successful_pings: int = 0  # 成功的心跳次数
        self._failed_pings: int = 0  # 失败的心跳次数

        # 延迟监控
        self._recent_latencies: list[float] = []  # 最近的心跳延迟记录
        self._max_latency_history = 10  # 保留最近 10 次延迟记录
        self._high_latency_count: int = 0  # 连续高延迟次数

        # 服务端配置（连接后从服务端获取）
        self._server_timeout_config: Optional[dict] = None

        # 忙碌状态追踪
        self._is_busy: bool = False
        self._busy_operation: str = ""

    async def start(self):
        """启动 WebSocket 客户端"""
        if self._running:
            return

        self._running = True
        self._set_connection_state("connecting")
        self._reconnect_task = asyncio.create_task(self._connect_loop())

    def _set_connection_state(self, state: str):
        """设置连接状态并触发回调"""
        if self._connection_state != state:
            old_state = self._connection_state
            self._connection_state = state
            print(f"[WebSocket] 连接状态: {old_state} -> {state}")
            if self.on_connection_state:
                try:
                    self.on_connection_state(state)
                except Exception as e:
                    print(f"[WebSocket] 状态回调异常: {e}")

    async def stop(self):
        """停止 WebSocket 客户端"""
        self._running = False
        self._set_connection_state("disconnected")

        # 先取消心跳任务
        if self._heartbeat_task:
            self._heartbeat_task.cancel()
            try:
                await self._heartbeat_task
            except asyncio.CancelledError:
                pass
            self._heartbeat_task = None

        # 取消 pong 监控任务
        if self._pong_monitor_task:
            self._pong_monitor_task.cancel()
            try:
                await self._pong_monitor_task
            except asyncio.CancelledError:
                pass
            self._pong_monitor_task = None

        # 关闭 WebSocket 连接
        if self.ws:
            try:
                await self.ws.close(1000, "Client stopping")
            except Exception as e:
                print(f"[WebSocket] 关闭连接时出错: {e}")
            self.ws = None

        # 取消重连任务
        if self._reconnect_task:
            self._reconnect_task.cancel()
            try:
                await self._reconnect_task
            except asyncio.CancelledError:
                pass
            self._reconnect_task = None

    async def _connect_loop(self):
        """连接维护循环（自动重连，指数退避 + 抖动）"""
        import random

        reconnect_attempts = 0

        while self._running:
            try:
                if reconnect_attempts > 0:
                    self._set_connection_state("reconnecting")
                else:
                    self._set_connection_state("connecting")

                print(f"[WebSocket] 正在连接: {self.url}")

                async with websockets.connect(
                    self.url,
                    ping_interval=self.PING_INTERVAL,  # 30秒发送ping（与服务端一致）
                    ping_timeout=self.PING_TIMEOUT,  # 20秒超时（增加容错）
                    close_timeout=10,  # 关闭超时10秒
                    max_size=10 * 1024 * 1024,  # 最大消息大小 10MB
                    compression=None,  # 禁用压缩以减少 CPU 开销
                ) as ws:
                    self.ws = ws
                    current_time = time.time()

                    # 判断是否为重连
                    is_reconnect = reconnect_attempts > 0 or self._total_reconnects > 0

                    # 重置所有状态计数
                    reconnect_attempts = 0  # 重置重连计数
                    self._heartbeat_failures = 0  # 重置心跳失败计数
                    self._high_latency_count = 0  # 重置高延迟计数
                    self._recent_latencies.clear()  # 清空延迟历史

                    # 初始化时间戳
                    self._last_heartbeat_ack = current_time
                    self._last_heartbeat_sent = current_time
                    self._last_pong_time = current_time
                    self._last_message_time = current_time

                    self._set_connection_state("connected")

                    if is_reconnect:
                        self._total_reconnects += 1
                        print(
                            f"[WebSocket] ✅ 重连成功（第 {self._total_reconnects} 次重连）"
                        )
                        # 触发重连成功回调
                        if self.on_reconnect:
                            try:
                                if asyncio.iscoroutinefunction(self.on_reconnect):
                                    await self.on_reconnect()
                                else:
                                    self.on_reconnect()
                            except Exception as e:
                                print(f"[WebSocket] 重连回调异常: {e}")
                    else:
                        print("[WebSocket] ✅ 连接成功")

                    # 尝试获取服务端超时配置
                    await self._request_server_config()

                    # 启动应用层心跳
                    self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())

                    # 启动底层 pong 监控
                    self._pong_monitor_task = asyncio.create_task(self._monitor_pong())

                    # 消息接收循环
                    async for message in ws:
                        if not self._running:
                            break

                        # 更新最后消息时间
                        self._last_message_time = time.time()

                        try:
                            data = json.loads(message)

                            # 处理心跳响应 - 更新心跳状态
                            if data.get("type") == "heartbeat_ack":
                                current_time = time.time()
                                latency = current_time - self._last_heartbeat_sent
                                self._last_heartbeat_ack = current_time
                                self._heartbeat_failures = 0  # 收到响应，重置失败计数
                                self._successful_pings += 1

                                # 记录延迟
                                self._record_latency(latency)

                                # 检查延迟是否过高
                                if latency > self.HIGH_LATENCY_THRESHOLD:
                                    self._high_latency_count += 1
                                    print(
                                        f"[WebSocket] ⚠️ 心跳延迟过高: {latency:.2f}s ({self._high_latency_count}/{self.MAX_HIGH_LATENCY_COUNT})"
                                    )
                                else:
                                    self._high_latency_count = 0
                                continue

                            # 处理服务端配置响应
                            if data.get("type") == "server_config":
                                self._server_timeout_config = data.get("config", {})
                                print(
                                    f"[WebSocket] 收到服务端配置: {self._server_timeout_config}"
                                )
                                continue

                            # 处理连接状态广播（包含服务端配置）
                            if data.get("type") == "connection_status":
                                status = data.get("status")
                                config = data.get("config", {})
                                print(f"[WebSocket] 服务端确认连接状态: {status}")
                                if config:
                                    self._server_timeout_config = config
                                    print(f"[WebSocket] 服务端配置: {config}")
                                continue

                            # 处理服务端主动探测（server_ping）- 立即响应
                            if data.get("type") == "server_ping":
                                server_timestamp = data.get("timestamp", 0)
                                # 发送 server_pong 响应
                                pong_msg = {
                                    "type": "server_pong",
                                    "client_timestamp": server_timestamp,
                                    "response_time": time.time(),
                                    "session_id": self.session_id,
                                }
                                await self.ws.send(json.dumps(pong_msg))
                                # 更新活跃时间
                                self._last_message_time = time.time()
                                continue

                            # 处理忙碌状态确认
                            if data.get("type") == "busy_state_ack":
                                is_busy = data.get("is_busy", False)
                                operation = data.get("operation", "")
                                print(
                                    f"[WebSocket] 忙碌状态确认: is_busy={is_busy}, operation={operation}"
                                )
                                continue

                            # 处理服务端下发的命令
                            if data.get("type") == "command":
                                await self._handle_command(data)
                                continue

                            if self.on_message:
                                # 在主线程/事件循环中调用回调
                                if asyncio.iscoroutinefunction(self.on_message):
                                    await self.on_message(data)
                                else:
                                    self.on_message(data)
                        except json.JSONDecodeError:
                            print(f"[WebSocket] 收到无效 JSON 消息: {message[:100]}...")
                        except Exception as e:
                            print(f"[WebSocket] 处理消息出错: {e}")
                            import traceback

                            traceback.print_exc()

            except websockets.ConnectionClosed as e:
                # 区分正常关闭和异常关闭
                if e.code == 1000:
                    print("[WebSocket] 连接正常关闭")
                elif e.code == 1001:
                    print("[WebSocket] 服务端正在关闭")
                elif e.code == 1006:
                    print("[WebSocket] ❌ 连接异常断开（网络问题）")
                else:
                    print(f"[WebSocket] 连接关闭: code={e.code}, reason={e.reason}")

            except ConnectionRefusedError as e:
                print(f"[WebSocket] ❌ 连接被拒绝: {e}")
                print(f"  - 请检查服务端是否运行在 {self.url}")
            except asyncio.TimeoutError:
                print("[WebSocket] ❌ 连接超时")
            except OSError as e:
                # 网络不可达等系统级错误
                print(f"[WebSocket] ❌ 网络错误: {e}")
            except Exception as e:
                print(f"[WebSocket] ❌ 异常: {type(e).__name__}: {e}")
                import traceback

                traceback.print_exc()
            finally:
                self.ws = None
                # 取消心跳任务
                if self._heartbeat_task:
                    self._heartbeat_task.cancel()
                    try:
                        await self._heartbeat_task
                    except asyncio.CancelledError:
                        pass
                    self._heartbeat_task = None

                # 取消 pong 监控任务
                if self._pong_monitor_task:
                    self._pong_monitor_task.cancel()
                    try:
                        await self._pong_monitor_task
                    except asyncio.CancelledError:
                        pass
                    self._pong_monitor_task = None

            # 指数退避重连（带抖动）
            if self._running:
                self._set_connection_state("reconnecting")

                # 计算延迟：基础延迟 * 2^attempts + 随机抖动
                base_delay = self.BASE_RECONNECT_DELAY * (
                    2 ** min(reconnect_attempts, 6)
                )  # 限制指数增长
                jitter = random.uniform(0, self.RECONNECT_JITTER * base_delay)
                delay = min(base_delay + jitter, self.MAX_RECONNECT_DELAY)

                reconnect_attempts += 1
                print(
                    f"[WebSocket] 将在 {delay:.1f} 秒后重连 (第 {reconnect_attempts} 次尝试，历史重连 {self._total_reconnects} 次)"
                )
                await asyncio.sleep(delay)

    async def _heartbeat_loop(self):
        """应用层心跳循环 - 确保连接活跃，并监控连接质量"""
        consecutive_send_failures = 0

        while self._running and self.ws:
            try:
                current_time = time.time()

                # 发送心跳（带时间戳和序列号）
                heartbeat_msg = {
                    "type": "heartbeat",
                    "timestamp": current_time,
                    "session_id": self.session_id,
                    "ping_count": self._successful_pings + self._failed_pings,
                    "stats": {
                        "avg_latency": self._get_average_latency(),
                        "high_latency_count": self._high_latency_count,
                    },
                }
                self._last_heartbeat_sent = current_time
                await self.ws.send(json.dumps(heartbeat_msg))
                consecutive_send_failures = 0  # 发送成功，重置计数

                # 等待心跳间隔
                await asyncio.sleep(self.HEARTBEAT_INTERVAL)

                current_time = time.time()

                # 检查心跳响应是否超时
                time_since_last_ack = current_time - self._last_heartbeat_ack
                if time_since_last_ack > self.HEARTBEAT_ACK_TIMEOUT:
                    self._heartbeat_failures += 1
                    self._failed_pings += 1
                    print(
                        f"[WebSocket] ⚠️ 心跳响应超时 ({self._heartbeat_failures}/{self._max_heartbeat_failures})，距上次响应 {time_since_last_ack:.1f}s"
                    )

                    # 连续失败达到阈值才断开
                    if self._heartbeat_failures >= self._max_heartbeat_failures:
                        print("[WebSocket] ❌ 心跳失败次数过多，主动断开连接以触发重连")
                        await self._force_reconnect("heartbeat_timeout")
                        break

                # 检查连续高延迟
                if self._high_latency_count >= self.MAX_HIGH_LATENCY_COUNT:
                    print(
                        f"[WebSocket] ⚠️ 连续 {self._high_latency_count} 次高延迟，连接质量差，主动重连"
                    )
                    await self._force_reconnect("high_latency")
                    break

                # 检查底层 pong 状态
                time_since_pong = current_time - self._last_pong_time
                if time_since_pong > self.PING_INTERVAL * 2:
                    print(
                        f"[WebSocket] ⚠️ 底层 pong 超时: {time_since_pong:.1f}s，可能存在网络问题"
                    )

            except asyncio.CancelledError:
                break
            except websockets.ConnectionClosed:
                print("[WebSocket] 心跳时连接已关闭")
                break
            except Exception as e:
                consecutive_send_failures += 1
                print(
                    f"[WebSocket] ⚠️ 心跳发送失败 ({consecutive_send_failures}/3): {e}"
                )

                # 连续发送失败 3 次，认为连接已断开
                if consecutive_send_failures >= 3:
                    print("[WebSocket] ❌ 心跳发送连续失败，断开连接")
                    break

                # 短暂等待后重试
                await asyncio.sleep(2)

    async def _monitor_pong(self):
        """监控 websockets 库底层的 pong 响应"""
        while self._running and self.ws:
            try:
                # 检查 websockets 连接的 latency 属性（如果可用）
                if hasattr(self.ws, "latency") and self.ws.latency is not None:
                    # websockets 库会自动计算 ping-pong 延迟
                    self._last_pong_time = time.time()

                await asyncio.sleep(5)  # 每 5 秒检查一次
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"[WebSocket] pong 监控异常: {e}")
                await asyncio.sleep(5)

    async def _request_server_config(self):
        """请求服务端配置"""
        try:
            if self.ws:
                config_request = {
                    "type": "get_config",
                    "timestamp": time.time(),
                }
                await self.ws.send(json.dumps(config_request))
                print("[WebSocket] 已请求服务端配置")
        except Exception as e:
            print(f"[WebSocket] 请求服务端配置失败: {e}")

    async def _force_reconnect(self, reason: str):
        """强制重连"""
        print(f"[WebSocket] 强制重连，原因: {reason}")
        if self.ws:
            try:
                await self.ws.close(1000, f"Force reconnect: {reason}")
            except Exception:
                pass

    def _record_latency(self, latency: float):
        """记录心跳延迟"""
        self._recent_latencies.append(latency)
        if len(self._recent_latencies) > self._max_latency_history:
            self._recent_latencies.pop(0)

    def _get_average_latency(self) -> float:
        """获取平均心跳延迟"""
        if not self._recent_latencies:
            return 0.0
        return sum(self._recent_latencies) / len(self._recent_latencies)

    async def _handle_command(self, data: dict):
        """
        处理服务端下发的命令

        命令格式：
        {
            "type": "command",
            "command": "screenshot",
            "request_id": "xxx",
            "params": {...}
        }
        """
        command: str = data.get("command", "")
        request_id: str = data.get("request_id", "")
        params: dict = data.get("params", {})

        if not command:
            print("[WebSocket] 收到无效命令: 缺少 command 字段")
            return

        print(f"[WebSocket] 收到命令: {command}, request_id={request_id}")

        if self.on_command:
            try:
                # 调用命令处理回调
                if asyncio.iscoroutinefunction(self.on_command):
                    result = await self.on_command(command, request_id, params)
                else:
                    result = self.on_command(command, request_id, params)

                # 如果回调返回了结果，自动发送响应
                if result is not None:
                    await self.send_command_result(command, request_id, result)

            except Exception as e:
                print(f"[WebSocket] 命令处理异常: {e}")
                # 发送错误响应
                await self.send_command_result(
                    command, request_id, {"success": False, "error_message": str(e)}
                )
        else:
            print(f"[WebSocket] 未设置命令处理器，忽略命令: {command}")

    async def send_command_result(self, command: str, request_id: str, result: dict):
        """
        发送命令执行结果

        Args:
            command: 命令名称
            request_id: 请求 ID
            result: 执行结果
        """
        message = {
            "type": "command_result",
            "command": command,
            "data": {"request_id": request_id, **result},
        }
        await self.send(message)
        print(f"[WebSocket] 已发送命令结果: {command}, request_id={request_id}")

    async def send(self, data: dict):
        """发送消息"""
        if self.ws:
            await self.ws.send(json.dumps(data))
        else:
            print("[WebSocket] ⚠️ 未连接，无法发送消息")

    async def send_desktop_state(self, state_data: dict):
        """
        发送桌面状态上报

        Args:
            state_data: 桌面状态数据（DesktopState.to_dict() 的结果）
        """
        message = {
            "type": "desktop_state",
            "data": state_data,
        }
        await self.send(message)

    async def set_busy_state(
        self, is_busy: bool, operation: str = "", duration: int = 30
    ):
        """
        设置忙碌状态

        在执行长时间操作（如截图、文件传输）前调用，通知服务端延长超时时间。

        Args:
            is_busy: 是否进入忙碌状态
            operation: 操作名称（如 "screenshot", "file_upload"）
            duration: 预计操作持续时间（秒），最大 120 秒
        """
        self._is_busy = is_busy
        self._busy_operation = operation if is_busy else ""

        message = {
            "type": "busy_state",
            "is_busy": is_busy,
            "operation": operation,
            "duration": min(duration, 120),  # 最大 120 秒
            "timestamp": time.time(),
        }
        await self.send(message)

        if is_busy:
            print(f"[WebSocket] 进入忙碌状态: {operation}，预计 {duration}s")
        else:
            print(f"[WebSocket] 退出忙碌状态: {operation}")

    async def with_busy_state(self, operation: str, duration: int = 30):
        """
        忙碌状态上下文管理器

        使用方法:
            async with client.with_busy_state("screenshot", 60):
                # 执行截图操作
                result = await take_screenshot()

        Args:
            operation: 操作名称
            duration: 预计操作持续时间（秒）

        Returns:
            异步上下文管理器
        """
        return BusyStateContext(self, operation, duration)

    @property
    def is_connected(self) -> bool:
        """检查 WebSocket 是否已连接"""
        return (
            self.ws is not None
            and self._running
            and self._connection_state == "connected"
        )

    @property
    def connection_state(self) -> str:
        """获取当前连接状态"""
        return self._connection_state

    def get_connection_stats(self) -> dict:
        """获取连接统计信息"""
        current_time = time.time()
        return {
            "state": self._connection_state,
            "total_reconnects": self._total_reconnects,
            "successful_pings": self._successful_pings,
            "failed_pings": self._failed_pings,
            "heartbeat_failures": self._heartbeat_failures,
            "high_latency_count": self._high_latency_count,
            "average_latency": self._get_average_latency(),
            "recent_latencies": self._recent_latencies.copy(),
            "last_message_age": current_time - self._last_message_time
            if self._last_message_time
            else None,
            "last_heartbeat_age": current_time - self._last_heartbeat_ack
            if self._last_heartbeat_ack
            else None,
            "last_pong_age": current_time - self._last_pong_time
            if self._last_pong_time
            else None,
            "server_config": self._server_timeout_config,
            "is_busy": self._is_busy,
            "busy_operation": self._busy_operation,
        }


class BusyStateContext:
    """忙碌状态上下文管理器"""

    def __init__(self, client: WebSocketClient, operation: str, duration: int):
        self.client = client
        self.operation = operation
        self.duration = duration

    async def __aenter__(self):
        await self.client.set_busy_state(True, self.operation, self.duration)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.client.set_busy_state(False, self.operation)
        return False


class AstrBotApiClient:
    """AstrBot HTTP API 客户端"""

    def __init__(
        self,
        server_url: str,
        username: str = "",
        password: str = "",
        token: Optional[str] = None,
        timeout: int = 30,
        on_state_change: Optional[Callable[[ConnectionState], None]] = None,
    ):
        self.server_url = server_url.rstrip("/")
        self.username = username
        self.password = password
        self.token = token
        self.timeout = timeout
        self.on_state_change = on_state_change

        self._state = ConnectionState.DISCONNECTED
        self._client: Optional[httpx.AsyncClient] = None
        self._sse_client: Optional[httpx.AsyncClient] = None
        self.ws_client: Optional[WebSocketClient] = None

        # WebSocket 连接状态（独立于 HTTP API 状态）
        self._ws_connection_state: str = "disconnected"

        # 连接健康检测配置优化：
        # - 检查间隔增加到 30 秒，减少不必要的网络请求
        # - 连续失败计数器，避免单次超时就触发断联
        # - 考虑 WebSocket 连接状态，避免误判
        self._health_check_task: Optional[asyncio.Task] = None
        self._last_successful_request: float = 0
        self._health_check_interval: int = 30  # 30秒检测一次（从10秒增加）
        self._health_check_failures: int = 0  # 连续失败计数
        self._max_health_check_failures: int = 3  # 连续失败多少次才触发断联

    @property
    def state(self) -> ConnectionState:
        return self._state

    @state.setter
    def state(self, value: ConnectionState):
        if self._state != value:
            self._state = value
            if self.on_state_change:
                self.on_state_change(value)

    @property
    def is_connected(self) -> bool:
        """
        综合判断连接状态

        考虑 HTTP API 状态和 WebSocket 状态：
        - HTTP 连接正常 -> 已连接
        - HTTP 断开但 WebSocket 正常 -> 仍视为已连接（可发送消息）
        - 两者都断开 -> 未连接
        """
        # HTTP 状态正常
        if self._state == ConnectionState.CONNECTED:
            return True
        # HTTP 异常但 WebSocket 正常
        if self._ws_connection_state == "connected":
            return True
        return False

    @property
    def is_fully_connected(self) -> bool:
        """检查是否完全连接（HTTP 和 WebSocket 都正常）"""
        return (
            self._state == ConnectionState.CONNECTED
            and self._ws_connection_state == "connected"
        )

    @property
    def connection_summary(self) -> dict:
        """获取连接状态摘要"""
        return {
            "http_connected": self._state == ConnectionState.CONNECTED,
            "ws_connected": self._ws_connection_state == "connected",
            "is_connected": self.is_connected,
            "is_fully_connected": self.is_fully_connected,
            "http_state": self._state.value,
            "ws_state": self._ws_connection_state,
        }

    @property
    def api_base(self) -> str:
        return f"{self.server_url}/api"

    def _get_headers(self) -> dict:
        """获取请求头"""
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return headers

    async def _ensure_client(self) -> httpx.AsyncClient:
        """确保 HTTP 客户端已创建（单例复用）"""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(self.timeout, connect=10.0),
                follow_redirects=True,
                http2=True,  # 尝试启用 HTTP/2 以提升普通 API 请求性能
            )
        return self._client

    async def _ensure_sse_client(self) -> httpx.AsyncClient:
        """确保 SSE 客户端已创建（单例复用，更长超时）"""
        if self._sse_client is None or self._sse_client.is_closed:
            # SSE 流式请求需要更长的读取超时
            self._sse_client = httpx.AsyncClient(
                timeout=httpx.Timeout(
                    connect=10.0,
                    read=300.0,  # 5 分钟读取超时
                    write=30.0,
                    pool=10.0,
                ),
                follow_redirects=True,
                http2=False,  # SSE 保持禁用 HTTP/2，避免流控制问题
                limits=httpx.Limits(max_keepalive_connections=5, max_connections=10),
            )
        return self._sse_client

    async def close(self):
        """关闭所有客户端连接"""
        # 停止健康检测
        await self.stop_health_check()

        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None

        if self._sse_client and not self._sse_client.is_closed:
            await self._sse_client.aclose()
            self._sse_client = None

        if self.ws_client:
            await self.ws_client.stop()
            self.ws_client = None

        self.state = ConnectionState.DISCONNECTED

    async def start_health_check(self):
        """启动连接健康检测"""
        if self._health_check_task is not None:
            return
        self._health_check_task = asyncio.create_task(self._health_check_loop())
        print("[API Client] 连接健康检测已启动")

    async def stop_health_check(self):
        """停止连接健康检测"""
        if self._health_check_task:
            self._health_check_task.cancel()
            try:
                await self._health_check_task
            except asyncio.CancelledError:
                pass
            self._health_check_task = None
            print("[API Client] 连接健康检测已停止")

    async def _health_check_loop(self):
        """连接健康检测循环"""
        while True:
            try:
                await asyncio.sleep(self._health_check_interval)

                # 只在连接状态下检测
                if self._state != ConnectionState.CONNECTED:
                    # 重置失败计数（非连接状态不计入失败）
                    self._health_check_failures = 0
                    continue

                # 检测 HTTP API 连接是否健康
                is_http_healthy = await self._check_http_connection()

                if not is_http_healthy:
                    self._health_check_failures += 1
                    print(
                        f"[API Client] ⚠️ HTTP 健康检测失败 ({self._health_check_failures}/{self._max_health_check_failures})"
                    )

                    # 检查 WebSocket 是否仍然连接
                    # 如果 WebSocket 仍然正常工作，不立即断开
                    ws_connected = self._ws_connection_state == "connected"

                    if ws_connected:
                        print(
                            "[API Client] HTTP 检测失败但 WebSocket 仍连接，暂不断开"
                        )
                        # WebSocket 正常时，使用更宽松的失败阈值
                        effective_max_failures = self._max_health_check_failures * 2
                    else:
                        effective_max_failures = self._max_health_check_failures

                    # 只有连续失败达到阈值才触发断联
                    if self._health_check_failures >= effective_max_failures:
                        ws_connected = self._ws_connection_state == "connected"
                        if ws_connected:
                            # WebSocket 仍然正常，只记录警告，不断开连接
                            print(
                                "[API Client] ⚠️ HTTP 健康检测失败但 WebSocket 正常，保持连接"
                            )
                            self._health_check_failures = 0  # 重置计数，继续监控
                        else:
                            print("[API Client] ❌ HTTP 和 WebSocket 都异常，触发重连")
                            self._health_check_failures = 0
                            self.state = ConnectionState.DISCONNECTED
                else:
                    # 检测成功，重置失败计数
                    self._health_check_failures = 0
                    self._last_successful_request = time.time()

            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"[API Client] 健康检测异常: {e}")

    async def _check_http_connection(self) -> bool:
        """
        检查 HTTP API 连接是否健康（内部方法，不改变状态）

        Returns:
            bool: HTTP 连接是否健康
        """
        if not self.token:
            return False

        try:
            client = await self._ensure_client()
            response = await client.get(
                f"{self.api_base}/chat/sessions",
                headers=self._get_headers(),
                timeout=10.0,
            )

            if response.status_code == 200:
                data = response.json()
                if data.get("status") == "ok":
                    return True

            # 401 表示 token 过期
            if response.status_code == 401:
                print("[API Client] ⚠️ Token 已过期，需要重新登录")
                self.token = None

            return False

        except httpx.TimeoutException:
            print("[API Client] ⚠️ HTTP 连接检测超时")
            return False
        except Exception as e:
            print(f"[API Client] ⚠️ HTTP 连接检测异常: {e}")
            return False

    def _on_ws_connection_state_change(self, state: str):
        """
        WebSocket 连接状态变化回调

        Args:
            state: WebSocket 连接状态 (disconnected, connecting, connected, reconnecting)
        """
        old_state = self._ws_connection_state
        self._ws_connection_state = state
        print(f"[API Client] WebSocket 状态变化: {old_state} -> {state}")

        # 如果 WebSocket 连接成功，确保 API 状态也是连接状态
        if state == "connected" and self._state != ConnectionState.CONNECTED:
            # 只有在 token 有效的情况下才更新状态
            if self.token:
                self.state = ConnectionState.CONNECTED
                self._health_check_failures = 0  # 重置失败计数

        # 如果 WebSocket 断开且 HTTP 也失败，才标记为断开
        elif state == "disconnected":
            # 不立即断开，让健康检测来处理
            pass

    def _on_ws_reconnect(self):
        """
        WebSocket 重连成功回调

        当 WebSocket 重连成功时，重置 HTTP 健康检测失败计数
        """
        print("[API Client] WebSocket 重连成功，重置 HTTP 失败计数")
        self._health_check_failures = 0
        self._last_successful_request = time.time()

    # ========== 认证相关 ==========

    def _hash_password(self, password: str) -> str:
        """对密码进行 MD5 哈希处理（AstrBot 服务器端存储的是 MD5 哈希）"""
        return hashlib.md5(password.encode("utf-8")).hexdigest()

    async def login(
        self, username: Optional[str] = None, password: Optional[str] = None
    ) -> tuple[bool, str]:
        """
        登录获取 token

        Returns:
            (success, message_or_token)
        """
        self.state = ConnectionState.CONNECTING

        username = username or self.username
        password = password or self.password

        if not username or not password:
            self.state = ConnectionState.ERROR
            return False, "用户名或密码为空"

        # AstrBot 服务器存储的是 MD5 哈希密码，需要对明文密码进行哈希
        password_hash = self._hash_password(password)

        try:
            client = await self._ensure_client()

            response = await client.post(
                f"{self.api_base}/auth/login",
                json={"username": username, "password": password_hash},
                headers={"Content-Type": "application/json"},
            )

            if response.status_code != 200:
                self.state = ConnectionState.ERROR
                return False, f"HTTP {response.status_code}"

            data = response.json()

            if data.get("status") == "ok":
                self.token = data["data"]["token"]
                self.username = username
                self.password = password
                self.state = ConnectionState.CONNECTED
                self._last_successful_request = time.time()

                # 登录成功后启动健康检测
                await self.start_health_check()

                change_pwd_hint = data["data"].get("change_pwd_hint", False)
                msg = "登录成功"
                if change_pwd_hint:
                    msg += "（建议修改默认密码）"

                return True, msg
            else:
                self.state = ConnectionState.ERROR
                return False, data.get("message", "登录失败")

        except httpx.ConnectError as e:
            self.state = ConnectionState.ERROR
            return False, f"连接失败: {e}"
        except httpx.TimeoutException:
            self.state = ConnectionState.ERROR
            return False, "连接超时"
        except Exception as e:
            self.state = ConnectionState.ERROR
            return False, f"登录异常: {e}"

    async def check_connection(self) -> bool:
        """检查连接状态"""
        if not self.token:
            return False

        try:
            client = await self._ensure_client()
            # 尝试获取会话列表来验证 token 是否有效
            response = await client.get(
                f"{self.api_base}/chat/sessions",
                headers=self._get_headers(),
                timeout=10.0,  # 健康检测使用较短超时
            )

            if response.status_code == 200:
                data = response.json()
                if data.get("status") == "ok":
                    if self._state != ConnectionState.CONNECTED:
                        self.state = ConnectionState.CONNECTED
                    self._last_successful_request = time.time()
                    return True

            # 401 表示 token 过期，需要重新登录
            if response.status_code == 401:
                print("[API Client] ⚠️ Token 已过期，需要重新登录")
                self.token = None

            self.state = ConnectionState.DISCONNECTED
            return False

        except httpx.TimeoutException:
            print("[API Client] ⚠️ 连接检测超时")
            self.state = ConnectionState.DISCONNECTED
            return False
        except Exception as e:
            print(f"[API Client] ⚠️ 连接检测异常: {e}")
            self.state = ConnectionState.DISCONNECTED
            return False

    async def start_websocket(
        self,
        session_id: str,
        on_message: Optional[Callable[[dict], None]] = None,
        on_command: Optional[Callable[[str, str, dict], Any]] = None,
        ws_port: Optional[int] = None,
    ):
        """
        启动 WebSocket 连接

        Args:
            session_id: 会话 ID
            on_message: 消息处理回调，接收 dict 类型消息
            on_command: 命令处理回调，接收 (command, request_id, params)，返回执行结果
            ws_port: WebSocket 服务端口。
                     - 如果指定（如 6190），将连接到该独立端口
                     - 如果为 None，将复用 API 端口
        """
        if not self.token:
            print("[API Client] 启动 WebSocket 失败: 未登录")
            return

        if self.ws_client:
            await self.ws_client.stop()

        self.ws_client = WebSocketClient(
            server_url=self.server_url,
            token=self.token,
            session_id=session_id,
            on_message=on_message,
            on_command=on_command,
            on_connection_state=self._on_ws_connection_state_change,
            on_reconnect=self._on_ws_reconnect,  # 添加重连回调
            ws_port=ws_port,
        )
        await self.ws_client.start()

    @property
    def ws_connection_state(self) -> str:
        """获取 WebSocket 连接状态"""
        return self._ws_connection_state

    @property
    def is_ws_connected(self) -> bool:
        """检查 WebSocket 是否已连接"""
        return self._ws_connection_state == "connected"

    # ========== 会话管理 ==========

    async def create_session(
        self, platform_id: str = "webchat"
    ) -> tuple[bool, Optional[str]]:
        """
        创建新会话

        Returns:
            (success, session_id or error_message)
        """
        try:
            client = await self._ensure_client()

            response = await client.get(
                f"{self.api_base}/chat/new_session",
                params={"platform_id": platform_id},
                headers=self._get_headers(),
            )

            if response.status_code != 200:
                return False, f"HTTP {response.status_code}"

            data = response.json()

            if data.get("status") == "ok":
                session_id = data["data"]["session_id"]
                return True, session_id
            else:
                return False, data.get("message", "创建会话失败")

        except Exception as e:
            return False, str(e)

    async def get_sessions(
        self, platform_id: Optional[str] = "webchat"
    ) -> tuple[bool, Any]:
        """
        获取会话列表

        Returns:
            (success, sessions_list or error_message)
        """
        try:
            client = await self._ensure_client()

            params = {}
            if platform_id:
                params["platform_id"] = platform_id

            response = await client.get(
                f"{self.api_base}/chat/sessions",
                params=params,
                headers=self._get_headers(),
            )

            if response.status_code != 200:
                return False, f"HTTP {response.status_code}"

            data = response.json()

            if data.get("status") == "ok":
                return True, data.get("data", [])
            else:
                return False, data.get("message", "获取会话列表失败")

        except Exception as e:
            return False, str(e)

    async def get_session_history(self, session_id: str) -> tuple[bool, Any]:
        """
        获取会话历史

        Returns:
            (success, history_data or error_message)
        """
        try:
            client = await self._ensure_client()

            response = await client.get(
                f"{self.api_base}/chat/get_session",
                params={"session_id": session_id},
                headers=self._get_headers(),
            )

            if response.status_code != 200:
                return False, f"HTTP {response.status_code}"

            data = response.json()

            if data.get("status") == "ok":
                return True, data.get("data", {})
            else:
                return False, data.get("message", "获取会话历史失败")

        except Exception as e:
            return False, str(e)

    async def delete_session(self, session_id: str) -> tuple[bool, str]:
        """删除会话"""
        try:
            client = await self._ensure_client()

            response = await client.get(
                f"{self.api_base}/chat/delete_session",
                params={"session_id": session_id},
                headers=self._get_headers(),
            )

            if response.status_code != 200:
                return False, f"HTTP {response.status_code}"

            data = response.json()

            if data.get("status") == "ok":
                return True, "删除成功"
            else:
                return False, data.get("message", "删除会话失败")

        except Exception as e:
            return False, str(e)

    # ========== 文件操作 ==========

    async def upload_file(self, file_path: str) -> tuple[bool, Optional[dict]]:
        """
        上传文件

        Returns:
            (success, {"attachment_id": str, "filename": str, "type": str} or None)
        """
        try:
            if not os.path.exists(file_path):
                return False, None

            client = await self._ensure_client()

            filename = os.path.basename(file_path)

            # 读取文件
            with open(file_path, "rb") as f:
                file_content = f.read()

            # 根据扩展名确定 MIME 类型
            ext = os.path.splitext(filename)[1].lower()
            mime_types = {
                ".png": "image/png",
                ".jpg": "image/jpeg",
                ".jpeg": "image/jpeg",
                ".gif": "image/gif",
                ".webp": "image/webp",
                ".bmp": "image/bmp",
                ".wav": "audio/wav",
                ".mp3": "audio/mpeg",
                ".ogg": "audio/ogg",
            }
            content_type = mime_types.get(ext, "application/octet-stream")

            # 构建 multipart 表单
            files = {"file": (filename, file_content, content_type)}

            # 不使用 JSON 头，使用 multipart
            headers = {}
            if self.token:
                headers["Authorization"] = f"Bearer {self.token}"

            response = await client.post(
                f"{self.api_base}/chat/post_file",
                files=files,
                headers=headers,
            )

            if response.status_code != 200:
                return False, None

            data = response.json()

            if data.get("status") == "ok":
                return True, data.get("data")
            else:
                return False, None

        except httpx.ConnectError:
            self.state = ConnectionState.DISCONNECTED
            return False, None
        except Exception as e:
            print(f"[API Client] 上传文件失败: {e}")
            return False, None

    async def download_file(self, filename: str, save_path: str) -> bool:
        """下载文件"""
        try:
            client = await self._ensure_client()

            response = await client.get(
                f"{self.api_base}/chat/get_file",
                params={"filename": filename},
                headers=self._get_headers(),
            )

            if response.status_code != 200:
                return False

            with open(save_path, "wb") as f:
                f.write(response.content)

            return True

        except httpx.ConnectError:
            self.state = ConnectionState.DISCONNECTED
            return False
        except Exception as e:
            print(f"[API Client] 下载文件失败: {e}")
            return False

    async def get_attachment(self, attachment_id: str, save_path: str) -> bool:
        """下载附件"""
        try:
            client = await self._ensure_client()

            response = await client.get(
                f"{self.api_base}/chat/get_attachment",
                params={"attachment_id": attachment_id},
                headers=self._get_headers(),
            )

            if response.status_code != 200:
                return False

            with open(save_path, "wb") as f:
                f.write(response.content)

            return True

        except Exception as e:
            print(f"[API Client] 下载附件失败: {e}")
            return False

    # ========== 消息发送 ==========

    async def send_message(
        self,
        session_id: str,
        message: str | list,
        selected_provider: Optional[str] = None,
        selected_model: Optional[str] = None,
        enable_streaming: bool = True,
    ) -> AsyncGenerator[SSEEvent, None]:
        """
        发送消息并接收 SSE 流式响应

        Args:
            session_id: 会话 ID
            message: 消息内容，可以是字符串或消息段列表
            selected_provider: 选择的 LLM 提供者
            selected_model: 选择的模型
            enable_streaming: 是否启用流式响应

        Yields:
            SSEEvent 对象
        """
        # 构建请求体
        body = {
            "session_id": session_id,
            "message": message,
            "enable_streaming": enable_streaming,
        }

        if selected_provider:
            body["selected_provider"] = selected_provider
        if selected_model:
            body["selected_model"] = selected_model

        # 使用复用的 SSE 客户端
        client = await self._ensure_sse_client()

        try:
            headers = self._get_headers()
            # SSE 特定头
            headers["Accept"] = "text/event-stream"
            headers["Cache-Control"] = "no-cache"
            # 移除 Connection: close 以允许 Keep-Alive

            async with client.stream(
                "POST",
                f"{self.api_base}/chat/send",
                json=body,
                headers=headers,
            ) as response:
                if response.status_code != 200:
                    yield SSEEvent(
                        event_type="error",
                        data=f"HTTP {response.status_code}",
                    )
                    return

                # 手动处理 SSE 流
                async for line in response.aiter_lines():
                    if not line:
                        continue

                    # 移除可能的 BOM
                    if line.startswith("\ufeff"):
                        line = line[1:]

                    # 只处理 data: 开头的行
                    if line.startswith("data: "):
                        data_str = line[6:]  # 去掉 'data: ' 前缀

                        try:
                            event_data = json.loads(data_str)
                            event_type = event_data.get("type", "plain")

                            event = SSEEvent(
                                event_type=event_type,
                                data=event_data.get("data", ""),
                                streaming=event_data.get("streaming", False),
                                chain_type=event_data.get("chain_type", "normal"),
                                raw=event_data,
                            )
                            yield event

                            # 让出控制权 - 关键！
                            await asyncio.sleep(0)

                            if event.event_type == "end":
                                return
                        except json.JSONDecodeError:
                            continue

        except httpx.ConnectError as e:
            self.state = ConnectionState.DISCONNECTED
            yield SSEEvent(event_type="error", data=f"连接失败: {e}")
        except httpx.TimeoutException as e:
            # 如果是连接超时，也标记为断开
            if isinstance(e, (httpx.ConnectTimeout, httpx.PoolTimeout)):
                self.state = ConnectionState.DISCONNECTED
                yield SSEEvent(event_type="error", data=f"连接超时: {e}")
            else:
                yield SSEEvent(
                    event_type="error", data=f"请求超时（服务器响应时间过长）: {e}"
                )
        except GeneratorExit:
            pass
        except Exception as e:
            yield SSEEvent(event_type="error", data=f"发送消息异常: {e}")

    async def send_text_message(
        self,
        session_id: str,
        text: str,
        **kwargs,
    ) -> AsyncGenerator[SSEEvent, None]:
        """发送纯文本消息"""
        async for event in self.send_message(session_id, text, **kwargs):
            yield event

    async def send_image_message(
        self,
        session_id: str,
        image_path: str,
        text: str = "",
        **kwargs,
    ) -> AsyncGenerator[SSEEvent, None]:
        """发送图片消息"""
        # 先上传图片
        success, result = await self.upload_file(image_path)

        if not success or not result:
            yield SSEEvent(event_type="error", data="图片上传失败")
            return

        # 构建消息段
        message_parts = []

        if text:
            message_parts.append({"type": "plain", "text": text})

        message_parts.append(
            {
                "type": "image",
                "attachment_id": result["attachment_id"],
            }
        )

        async for event in self.send_message(session_id, message_parts, **kwargs):
            yield event

    async def send_voice_message(
        self,
        session_id: str,
        audio_path: str,
        **kwargs,
    ) -> AsyncGenerator[SSEEvent, None]:
        """发送语音消息"""
        # 先上传音频
        success, result = await self.upload_file(audio_path)

        if not success or not result:
            yield SSEEvent(event_type="error", data="音频上传失败")
            return

        # 构建消息段
        message_parts = [
            {
                "type": "record",
                "attachment_id": result["attachment_id"],
            }
        ]

        async for event in self.send_message(session_id, message_parts, **kwargs):
            yield event

    async def send_file_message(
        self,
        session_id: str,
        file_path: str,
        text: str = "",
        **kwargs,
    ) -> AsyncGenerator[SSEEvent, None]:
        """发送文件消息"""
        # 先上传文件
        success, result = await self.upload_file(file_path)

        if not success or not result:
            yield SSEEvent(event_type="error", data="文件上传失败")
            return

        # 构建消息段
        message_parts = []

        if text:
            message_parts.append({"type": "plain", "text": text})

        message_parts.append(
            {
                "type": "file",
                "attachment_id": result["attachment_id"],
            }
        )

        async for event in self.send_message(session_id, message_parts, **kwargs):
            yield event
