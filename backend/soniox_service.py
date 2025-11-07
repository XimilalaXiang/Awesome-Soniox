import asyncio
import json
import logging
import websockets
from typing import Callable, Optional
from models import SonioxConfig, TranscriptionToken

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class SonioxWebSocketService:
    """Soniox WebSocket 服务，用于实时语音转录"""

    SONIOX_WS_URL = "wss://stt-rt.soniox.com/transcribe-websocket"

    def __init__(self, config: SonioxConfig):
        self.config = config
        self.ws_connection: Optional[websockets.WebSocketClientProtocol] = None
        self.is_connected = False
        self.session_id: Optional[str] = None
        self._last_audio_ts: float = 0.0
        self._keepalive_task: Optional[asyncio.Task] = None

    async def connect(self, on_message: Callable):
        """连接到 Soniox WebSocket API"""
        try:
            logger.info(f"Connecting to Soniox WebSocket: {self.SONIOX_WS_URL}")

            # 连接到 WebSocket
            self.ws_connection = await websockets.connect(
                self.SONIOX_WS_URL,
                ping_interval=20,
                ping_timeout=10,
                max_size=10 * 1024 * 1024  # 10MB
            )

            # 发送初始配置
            config_message = {
                "api_key": self.config.api_key,
                "model": self.config.model,
                "audio_format": "auto",  # 自动检测音频格式
                "enable_speaker_diarization": self.config.enable_speaker_diarization,
                "enable_language_identification": self.config.enable_language_identification,
                "enable_endpoint_detection": getattr(self.config, "enable_endpoint_detection", True),
            }

            if self.config.language_hints:
                config_message["language_hints"] = self.config.language_hints

            await self.ws_connection.send(json.dumps(config_message))
            logger.info("Sent configuration to Soniox")

            self.is_connected = True

            # 启动消息接收循环
            asyncio.create_task(self._receive_messages(on_message))

            # 启动 keepalive 任务（在无音频分片时维持会话与上下文）
            self._keepalive_task = asyncio.create_task(self._keepalive_loop())

            return True

        except Exception as e:
            logger.error(f"Error connecting to Soniox: {str(e)}")
            self.is_connected = False
            return False

    async def _receive_messages(self, on_message: Callable):
        """接收来自 Soniox 的消息"""
        try:
            async for message in self.ws_connection:
                if isinstance(message, str):
                    data = json.loads(message)

                    # 处理转录结果
                    if "tokens" in data:
                        tokens = []
                        for token_data in data["tokens"]:
                            token = TranscriptionToken(
                                text=token_data.get("text", ""),
                                start_ms=token_data.get("start_ms", 0.0),
                                end_ms=token_data.get("end_ms", 0.0),
                                confidence=token_data.get("confidence", 1.0),
                                is_final=token_data.get("is_final", False),
                                speaker=token_data.get("speaker"),
                                language=token_data.get("language")
                            )
                            tokens.append(token)

                        # 调用回调函数
                        await on_message({
                            "type": "transcription",
                            "tokens": [token.model_dump() for token in tokens],
                            "audio_final_proc_ms": data.get("audio_final_proc_ms", 0.0),
                            "audio_total_proc_ms": data.get("audio_total_proc_ms", 0.0)
                        })

                    # 处理其他消息类型
                    elif "message_type" in data:
                        logger.info(f"Received message: {data.get('message_type')}")
                        if data.get("message_type") == "session_started":
                            self.session_id = data.get("session_id")
                            await on_message({
                                "type": "session_started",
                                "session_id": self.session_id
                            })

        except websockets.exceptions.ConnectionClosed:
            logger.info("Soniox WebSocket connection closed")
            self.is_connected = False
        except Exception as e:
            logger.error(f"Error receiving messages from Soniox: {str(e)}")
            self.is_connected = False

    async def _keepalive_loop(self):
        """在长时间静默时发送 keepalive 控制消息，避免会话因无音频而被关闭"""
        try:
            import time
            while self.is_connected and self.ws_connection:
                now = time.time()
                # 若 15 秒未发送音频，则发送 keepalive
                if now - self._last_audio_ts > 15:
                    try:
                        await self.ws_connection.send(json.dumps({"type": "keepalive"}))
                        logger.debug("Sent keepalive to Soniox")
                        # 避免高频发送
                        self._last_audio_ts = now
                    except Exception as e:
                        logger.warning(f"Keepalive failed: {e}")
                await asyncio.sleep(5)
        except Exception as e:
            logger.warning(f"Keepalive loop error: {e}")

    async def send_audio(self, audio_data: bytes):
        """发送音频数据到 Soniox"""
        if not self.is_connected or not self.ws_connection:
            logger.error("Not connected to Soniox")
            return False

        try:
            await self.ws_connection.send(audio_data)
            # 记录最近发送音频时间戳
            try:
                import time
                self._last_audio_ts = time.time()
            except Exception:
                pass
            return True
        except Exception as e:
            logger.error(f"Error sending audio to Soniox: {str(e)}")
            return False

    async def finalize(self):
        """强制完成当前的转录（使 pending tokens 变为 final）"""
        if not self.is_connected or not self.ws_connection:
            return False

        try:
            finalize_message = {"type": "finalize"}
            await self.ws_connection.send(json.dumps(finalize_message))
            return True
        except Exception as e:
            logger.error(f"Error sending finalize message: {str(e)}")
            return False

    async def close(self):
        """关闭 WebSocket 连接"""
        if self.ws_connection:
            try:
                # 发送空帧来优雅地关闭
                await self.ws_connection.send(b"")
                await self.ws_connection.close()
                logger.info("Soniox WebSocket connection closed gracefully")
            except Exception as e:
                logger.error(f"Error closing Soniox connection: {str(e)}")
            finally:
                self.is_connected = False
                self.ws_connection = None
                # 结束 keepalive 任务
                if self._keepalive_task and not self._keepalive_task.done():
                    self._keepalive_task.cancel()
                    self._keepalive_task = None
