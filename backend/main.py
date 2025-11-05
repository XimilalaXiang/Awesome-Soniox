import asyncio
import logging
import uuid
from datetime import datetime
from typing import Dict
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from models import (
    SonioxConfig,
    OpenAIConfig,
    TranscriptionSession,
    TranscriptionSegment,
    SummarizeRequest,
    QuestionRequest,
)
from soniox_service import SonioxWebSocketService
from openai_service import OpenAIService

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Soniox Transcription Platform")

# 配置 CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 存储活跃的转录会话
active_sessions: Dict[str, TranscriptionSession] = {}
# 存储活跃的 Soniox 连接
active_soniox_connections: Dict[str, SonioxWebSocketService] = {}


@app.get("/")
async def root():
    """健康检查"""
    return {"status": "ok", "service": "Soniox Transcription Platform"}


@app.websocket("/ws/transcribe")
async def transcribe_websocket(websocket: WebSocket):
    """
    WebSocket 端点用于实时转录
    客户端首先发送 Soniox 配置，然后流式发送音频数据
    """
    await websocket.accept()
    session_id = str(uuid.uuid4())
    soniox_service: SonioxWebSocketService = None
    current_segment: TranscriptionSegment = None
    current_speaker: str = None

    logger.info(f"New transcription session started: {session_id}")

    # 创建新的转录会话
    session = TranscriptionSession(
        session_id=session_id,
        title=f"Session {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        created_at=datetime.now(),
    )
    active_sessions[session_id] = session

    try:
        # 第一条消息应该是配置
        config_data = await websocket.receive_json()

        if "config" not in config_data:
            await websocket.send_json({"error": "First message must contain 'config'"})
            await websocket.close()
            return

        # 解析 Soniox 配置
        soniox_config = SonioxConfig(**config_data["config"])

        # 定义消息处理回调
        async def on_soniox_message(message):
            """处理来自 Soniox 的消息并转发给客户端"""
            nonlocal current_segment, current_speaker

            if message["type"] == "transcription":
                tokens = message["tokens"]

                # 按发言人分组 tokens
                for token in tokens:
                    speaker = token.get("speaker") or "Speaker 0"

                    # 如果发言人改变，创建新的 segment
                    if speaker != current_speaker:
                        if current_segment:
                            session.segments.append(current_segment)

                        current_speaker = speaker
                        current_segment = TranscriptionSegment(
                            speaker=speaker,
                            text="",
                            start_time=token["start_ms"],
                            end_time=token["end_ms"],
                            tokens=[],
                        )

                    # 添加 token 到当前 segment
                    current_segment.tokens.append(token)
                    current_segment.text += token["text"]
                    current_segment.end_time = token["end_ms"]

                    # 如果是 final token，更新完整转录
                    if token["is_final"]:
                        session.full_transcript += token["text"]

                # 发送给客户端
                await websocket.send_json(message)

            elif message["type"] == "session_started":
                await websocket.send_json(
                    {"type": "session_started", "session_id": session_id}
                )

        # 连接到 Soniox
        soniox_service = SonioxWebSocketService(soniox_config)
        active_soniox_connections[session_id] = soniox_service

        connected = await soniox_service.connect(on_soniox_message)

        if not connected:
            await websocket.send_json({"error": "Failed to connect to Soniox"})
            await websocket.close()
            return

        await websocket.send_json(
            {"type": "connected", "session_id": session_id, "message": "Ready to receive audio"}
        )

        # 接收并转发音频数据
        while True:
            message = await websocket.receive()

            if "bytes" in message:
                # 音频数据 - 转发到 Soniox
                audio_data = message["bytes"]
                await soniox_service.send_audio(audio_data)

            elif "text" in message:
                # 文本消息 - 处理命令
                import json

                data = json.loads(message["text"])

                if data.get("command") == "finalize":
                    await soniox_service.finalize()

                elif data.get("command") == "stop":
                    # 保存当前 segment
                    if current_segment:
                        session.segments.append(current_segment)
                    session.status = "completed"
                    await websocket.send_json(
                        {"type": "session_completed", "session_id": session_id}
                    )
                    break

    except WebSocketDisconnect:
        logger.info(f"Client disconnected: {session_id}")
    except Exception as e:
        logger.error(f"Error in transcription session {session_id}: {str(e)}")
        await websocket.send_json({"error": str(e)})
    finally:
        # 清理
        if soniox_service:
            await soniox_service.close()
        if session_id in active_soniox_connections:
            del active_soniox_connections[session_id]

        # 保存最后的 segment
        if current_segment:
            session.segments.append(current_segment)
            session.status = "stopped"

        logger.info(f"Transcription session ended: {session_id}")


@app.get("/sessions")
async def get_sessions():
    """获取所有转录会话"""
    return {
        "sessions": [
            {
                "session_id": session.session_id,
                "title": session.title,
                "created_at": session.created_at.isoformat(),
                "status": session.status,
                "segments_count": len(session.segments),
            }
            for session in active_sessions.values()
        ]
    }


@app.get("/sessions/{session_id}")
async def get_session(session_id: str):
    """获取特定会话的详细信息"""
    if session_id not in active_sessions:
        raise HTTPException(status_code=404, detail="Session not found")

    session = active_sessions[session_id]
    return session.model_dump()


@app.post("/summarize")
async def summarize_session(request: SummarizeRequest):
    """总结会话内容（流式响应）"""
    if request.session_id not in active_sessions:
        raise HTTPException(status_code=404, detail="Session not found")

    session = active_sessions[request.session_id]

    if not session.full_transcript:
        raise HTTPException(status_code=400, detail="No transcript available")

    # 创建 OpenAI 服务
    openai_service = OpenAIService(request.openai_config)

    # 流式返回总结
    async def generate():
        async for chunk in openai_service.summarize(
            session.full_transcript, request.prompt
        ):
            yield chunk

    return StreamingResponse(generate(), media_type="text/plain")


@app.post("/question")
async def answer_question(request: QuestionRequest):
    """回答关于会话内容的问题（流式响应）"""
    if request.session_id not in active_sessions:
        raise HTTPException(status_code=404, detail="Session not found")

    session = active_sessions[request.session_id]

    if not session.full_transcript:
        raise HTTPException(status_code=400, detail="No transcript available")

    # 创建 OpenAI 服务
    openai_service = OpenAIService(request.openai_config)

    # 流式返回回答
    async def generate():
        async for chunk in openai_service.answer_question(
            session.full_transcript, request.question
        ):
            yield chunk

    return StreamingResponse(generate(), media_type="text/plain")


@app.delete("/sessions/{session_id}")
async def delete_session(session_id: str):
    """删除会话"""
    if session_id not in active_sessions:
        raise HTTPException(status_code=404, detail="Session not found")

    # 如果会话还在活跃，先关闭连接
    if session_id in active_soniox_connections:
        soniox_service = active_soniox_connections[session_id]
        await soniox_service.close()
        del active_soniox_connections[session_id]

    del active_sessions[session_id]
    return {"message": "Session deleted"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
