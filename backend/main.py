import asyncio
import logging
import uuid
import json
from datetime import datetime, timedelta
import os, hmac, hashlib, base64
from typing import Dict, Optional
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Depends, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, Response
from sqlalchemy.ext.asyncio import AsyncSession
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
from database import get_db, init_db, TranscriptionSessionDB, SettingDB, async_session_maker
import crud

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Soniox Transcription Platform")
# ============== 简单密码登录（Cookie） ==============
SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret")
ACCESS_PASSWORD = os.getenv("ACCESS_PASSWORD", "")
COOKIE_NAME = "auth_token"
TOKEN_TTL_SECONDS = 60 * 60 * 12  # 12h


def _sign(payload: str) -> str:
    mac = hmac.new(SECRET_KEY.encode(), payload.encode(), hashlib.sha256).hexdigest()
    return f"{base64.urlsafe_b64encode(payload.encode()).decode()}.{mac}"


def _verify(token: str) -> bool:
    try:
        data_b64, mac = token.split(".", 1)
        payload = base64.urlsafe_b64decode(data_b64.encode()).decode()
        if hmac.new(SECRET_KEY.encode(), payload.encode(), hashlib.sha256).hexdigest() != mac:
            return False
        parts = payload.split("|")
        exp = 0
        for p in parts:
            if p.startswith("exp:"):
                exp = int(p.split(":", 1)[1])
        return int(datetime.utcnow().timestamp()) < exp
    except Exception:
        return False


def _set_auth_cookie(response, ttl=TOKEN_TTL_SECONDS):
    exp = int((datetime.utcnow() + timedelta(seconds=ttl)).timestamp())
    payload = f"auth|exp:{exp}"
    token = _sign(payload)
    response.set_cookie(
        COOKIE_NAME,
        token,
        httponly=True,
        secure=True,
        samesite="Lax",
        max_age=ttl,
        path="/",
    )


def _clear_auth_cookie(response):
    response.delete_cookie(COOKIE_NAME, path="/")

def _random_salt() -> str:
    return base64.urlsafe_b64encode(os.urandom(16)).decode()

def _hash_password(password: str, salt: str) -> str:
    digest = hashlib.sha256((salt + password).encode()).hexdigest()
    return f"v1${salt}${digest}"

def _verify_password(stored: str, password: str) -> bool:
    try:
        ver, salt, digest = stored.split("$", 2)
        if ver != "v1":
            return False
        return hashlib.sha256((salt + password).encode()).hexdigest() == digest
    except Exception:
        return False

async def _get_setting(key: str) -> Optional[str]:
    async with async_session_maker() as session:
        row = await session.get(SettingDB, key)
        return row.value if row else None

async def _set_setting(key: str, value: str) -> None:
    async with async_session_maker() as session:
        row = await session.get(SettingDB, key)
        if row:
            row.value = value
        else:
            row = SettingDB(key=key, value=value)
            session.add(row)
        await session.commit()

async def _is_initialized() -> bool:
    if ACCESS_PASSWORD:
        return True
    v = await _get_setting("password_hash")
    return bool(v)


@app.post("/auth/login")
async def auth_login(body: dict):
    from fastapi import Response, HTTPException
    pwd = (body or {}).get("password", "")
    # 若设置了环境变量密码，则优先使用（企业部署固定密码）
    if ACCESS_PASSWORD:
        if pwd != ACCESS_PASSWORD:
            raise HTTPException(status_code=401, detail="Invalid password")
    else:
        stored = await _get_setting("password_hash")
        if not stored or not _verify_password(stored, pwd):
            raise HTTPException(status_code=401, detail="Invalid password")
    resp = Response(content=json.dumps({"ok": True}), media_type="application/json")
    _set_auth_cookie(resp)
    return resp


from fastapi import Request
@app.get("/auth/status")
async def auth_status(request: Request):
    token = request.cookies.get(COOKIE_NAME)
    setup_needed = not await _is_initialized()
    return {"ok": bool(token) and _verify(token), "setup": setup_needed}


@app.post("/auth/logout")
async def auth_logout():
    from fastapi import Response
    resp = Response(content=json.dumps({"ok": True}), media_type="application/json")
    _clear_auth_cookie(resp)
    return resp

@app.post("/auth/setup")
async def auth_setup(body: dict):
    from fastapi import Response, HTTPException
    if ACCESS_PASSWORD:
        raise HTTPException(status_code=400, detail="Setup disabled (configured by env)")
    if await _is_initialized():
        raise HTTPException(status_code=400, detail="Already initialized")
    pwd = (body or {}).get("password", "")
    if not pwd or len(pwd) < 4:
        raise HTTPException(status_code=400, detail="Password too short")
    salt = _random_salt()
    stored = _hash_password(pwd, salt)
    await _set_setting("password_hash", stored)
    resp = Response(content=json.dumps({"ok": True}), media_type="application/json")
    _set_auth_cookie(resp)
    return resp

def _require_auth(request: Request):
    if not ACCESS_PASSWORD and asyncio.get_event_loop().is_running():
        # 若未开启密码模式，但已初始化设置，则也要求登录
        pass
    token = request.cookies.get(COOKIE_NAME)
    if ACCESS_PASSWORD and (not token or not _verify(token)):
        raise HTTPException(status_code=401, detail="Unauthorized")

# 全局云端配置存取
@app.get("/config")
async def get_config(request: Request):
    _require_auth(request)
    soniox_cfg_raw = await _get_setting("soniox_config") or "{}"
    openai_cfg_raw = await _get_setting("openai_config") or "{}"
    soniox_key = await _get_setting("soniox_api_key")
    openai_key = await _get_setting("openai_api_key")
    try:
        soniox_cfg = json.loads(soniox_cfg_raw) if soniox_cfg_raw else {}
        openai_cfg = json.loads(openai_cfg_raw) if openai_cfg_raw else {}
    except Exception:
        soniox_cfg, openai_cfg = {}, {}
    # 掩码返回：不回显密钥，仅返回 has_api_key 标记
    soniox_cfg.pop("api_key", None)
    openai_cfg.pop("api_key", None)
    soniox_cfg["has_api_key"] = bool(soniox_key)
    openai_cfg["has_api_key"] = bool(openai_key)
    return {"soniox_config": soniox_cfg, "openai_config": openai_cfg}

@app.put("/config")
async def put_config(request: Request):
    _require_auth(request)
    body = await request.json()
    soniox = body.get("soniox_config") or {}
    openai = body.get("openai_config") or {}
    # 验证（允许缺少 api_key）
    try:
        if soniox:
            temp = dict(soniox)
            if "api_key" not in temp or not temp.get("api_key"):
                temp["api_key"] = "placeholder"
            SonioxConfig(**temp)
        if openai:
            temp = dict(openai)
            if "api_key" not in temp or not temp.get("api_key"):
                temp["api_key"] = "placeholder"
            OpenAIConfig(**temp)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    # 保存（密钥分开存储；留空不更新；clear_* 为 true 时清空）
    if soniox:
        key = soniox.get("api_key")
        if key:
            await _set_setting("soniox_api_key", key)
        if soniox.get("clear_api_key") is True:
            await _set_setting("soniox_api_key", "")
        soniox_slim = {k: v for k, v in soniox.items() if k not in ("api_key", "clear_api_key")}
        await _set_setting("soniox_config", json.dumps(soniox_slim))
    if openai:
        key = openai.get("api_key")
        if key:
            await _set_setting("openai_api_key", key)
        if openai.get("clear_api_key") is True:
            await _set_setting("openai_api_key", "")
        openai_slim = {k: v for k, v in openai.items() if k not in ("api_key", "clear_api_key")}
        await _set_setting("openai_config", json.dumps(openai_slim))
    return {"ok": True}

# 启动事件：初始化数据库
@app.on_event("startup")
async def startup_event():
    """应用启动时初始化数据库"""
    logger.info("Initializing database...")
    await init_db()
    logger.info("Database initialized successfully")

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
    # 认证校验（基于 Cookie）
    token = websocket.cookies.get(COOKIE_NAME)
    if ACCESS_PASSWORD and (not token or not _verify(token)):
        await websocket.close(code=4401)
        return
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
        incoming_cfg = dict(config_data["config"])
        if not incoming_cfg.get("api_key"):
            # 若前端未回显/未发送密钥，则从服务器保存中补全
            stored_key = await _get_setting("soniox_api_key")
            if not stored_key:
                await websocket.send_json({"type": "error", "error_message": "Missing Soniox API key"})
                await websocket.close()
                return
            incoming_cfg["api_key"] = stored_key
        soniox_config = SonioxConfig(**incoming_cfg)

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
                            start_time=token.get("start_ms", 0.0),
                            end_time=token.get("end_ms", 0.0),
                            tokens=[],
                        )

                    # 仅当 token 为最终（is_final=True）时，纳入持久化/全文
                    if token.get("is_final"):
                        current_segment.tokens.append(token)
                        current_segment.text += token.get("text", "")
                        current_segment.end_time = token.get("end_ms", current_segment.end_time)
                        session.full_transcript += token.get("text", "")

                        # 若检测到句末标记（endpoint 或 finalize），落段并重置
                        if token.get("text") in ("<end>", "<fin>"):
                            if current_segment:
                                session.segments.append(current_segment)
                            current_segment = None
                            current_speaker = None

                # 发送给客户端
                await websocket.send_json(message)

            elif message["type"] == "session_started":
                await websocket.send_json(
                    {"type": "session_started", "session_id": session_id}
                )
            elif message["type"] == "error":
                # 将 Soniox 错误原样转发给前端，便于客户端显示与排查
                await websocket.send_json(message)

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
                elif data.get("command") == "set_format":
                    fmt = data.get("audio_format")
                    sr = data.get("sample_rate")
                    ch = data.get("num_channels")
                    ok = await soniox_service.reconfigure(fmt, sr, ch)
                    await websocket.send_json(
                        {
                            "type": "reconfigured",
                            "ok": ok,
                            "audio_format": fmt,
                            "sample_rate": sr,
                            "num_channels": ch,
                        }
                    )

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

        # 保存到数据库
        try:
            async for db in get_db():
                await crud.create_session(db, session)
                logger.info(f"Session {session_id} saved to database")
                break
        except Exception as e:
            logger.error(f"Error saving session to database: {str(e)}")

        logger.info(f"Transcription session ended: {session_id}")


@app.get("/sessions")
async def get_sessions(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=100),
    search: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db)
):
    """获取所有转录会话（从数据库）"""
    sessions = await crud.get_sessions(db, skip=skip, limit=limit, search=search)
    total = await crud.get_session_count(db, search=search)

    return {
        "total": total,
        "skip": skip,
        "limit": limit,
        "sessions": [
            {
                "session_id": session.session_id,
                "title": session.title,
                "created_at": session.created_at.isoformat(),
                "updated_at": session.updated_at.isoformat(),
                "status": session.status,
                "duration_seconds": session.duration_seconds,
                "speaker_count": session.speaker_count,
                "word_count": session.word_count,
            }
            for session in sessions
        ]
    }


@app.get("/sessions/{session_id}")
async def get_session(session_id: str, db: AsyncSession = Depends(get_db)):
    """获取特定会话的详细信息"""
    # 优先从活跃会话中获取
    if session_id in active_sessions:
        session = active_sessions[session_id]
        return session.model_dump()

    # 从数据库获取
    db_session = await crud.get_session(db, session_id)
    if not db_session:
        raise HTTPException(status_code=404, detail="Session not found")

    # 解析 segments
    segments = json.loads(db_session.segments_json)

    return {
        "session_id": db_session.session_id,
        "title": db_session.title,
        "created_at": db_session.created_at.isoformat(),
        "segments": segments,
        "full_transcript": db_session.full_transcript,
        "status": db_session.status,
        "duration_seconds": db_session.duration_seconds,
        "speaker_count": db_session.speaker_count,
        "word_count": db_session.word_count,
        "ai_summary": db_session.ai_summary,
        "ai_action_items": db_session.ai_action_items,
    }


@app.post("/summarize")
async def summarize_session(request: SummarizeRequest, db: AsyncSession = Depends(get_db)):
    """总结会话内容（流式响应）"""
    # 从活跃会话或数据库获取
    transcript = None
    if request.session_id in active_sessions:
        session = active_sessions[request.session_id]
        transcript = session.full_transcript
    else:
        db_session = await crud.get_session(db, request.session_id)
        if not db_session:
            raise HTTPException(status_code=404, detail="Session not found")
        transcript = db_session.full_transcript

    if not transcript:
        raise HTTPException(status_code=400, detail="No transcript available")

    # 创建 OpenAI 服务（若未传 api_key 则使用服务器保存）
    openai_cfg = request.openai_config
    if not openai_cfg.api_key:
        stored_key = await _get_setting("openai_api_key")
        if stored_key:
            # 尝试加载服务器保存的非密钥字段
            raw = await _get_setting("openai_config") or "{}"
            try:
                base = json.loads(raw)
            except Exception:
                base = {}
            openai_cfg = OpenAIConfig(
                api_url=base.get("api_url", openai_cfg.api_url),
                api_key=stored_key,
                model=base.get("model", openai_cfg.model),
            )
    openai_service = OpenAIService(openai_cfg)

    # 流式返回总结
    async def generate():
        summary = ""
        async for chunk in openai_service.summarize(transcript, request.prompt):
            summary += chunk
            yield chunk

        # 保存总结到数据库
        try:
            await crud.update_ai_summary(db, request.session_id, summary)
        except Exception as e:
            logger.error(f"Error saving summary: {str(e)}")

    return StreamingResponse(generate(), media_type="text/plain")


@app.post("/question")
async def answer_question(request: QuestionRequest, db: AsyncSession = Depends(get_db)):
    """回答关于会话内容的问题（流式响应）"""
    # 从活跃会话或数据库获取
    transcript = None
    if request.session_id in active_sessions:
        session = active_sessions[request.session_id]
        transcript = session.full_transcript
    else:
        db_session = await crud.get_session(db, request.session_id)
        if not db_session:
            raise HTTPException(status_code=404, detail="Session not found")
        transcript = db_session.full_transcript

    if not transcript:
        raise HTTPException(status_code=400, detail="No transcript available")

    # 创建 OpenAI 服务（若未传 api_key 则使用服务器保存）
    openai_cfg = request.openai_config
    if not openai_cfg.api_key:
        stored_key = await _get_setting("openai_api_key")
        if stored_key:
            raw = await _get_setting("openai_config") or "{}"
            try:
                base = json.loads(raw)
            except Exception:
                base = {}
            openai_cfg = OpenAIConfig(
                api_url=base.get("api_url", openai_cfg.api_url),
                api_key=stored_key,
                model=base.get("model", openai_cfg.model),
            )
    openai_service = OpenAIService(openai_cfg)

    # 流式返回回答
    async def generate():
        async for chunk in openai_service.answer_question(transcript, request.question):
            yield chunk

    return StreamingResponse(generate(), media_type="text/plain")


@app.delete("/sessions/{session_id}")
async def delete_session(session_id: str, db: AsyncSession = Depends(get_db)):
    """删除会话"""
    # 如果会话还在活跃，先关闭连接
    if session_id in active_soniox_connections:
        soniox_service = active_soniox_connections[session_id]
        await soniox_service.close()
        del active_soniox_connections[session_id]

    if session_id in active_sessions:
        del active_sessions[session_id]

    # 从数据库删除
    deleted = await crud.delete_session(db, session_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Session not found")

    return {"message": "Session deleted"}


@app.get("/sessions/{session_id}/export")
async def export_session(
    session_id: str,
    format: str = Query("txt", regex="^(txt|json|markdown)$"),
    db: AsyncSession = Depends(get_db)
):
    """导出会话内容"""
    # 获取会话
    db_session = await crud.get_session(db, session_id)
    if not db_session:
        raise HTTPException(status_code=404, detail="Session not found")

    # 解析 segments
    segments = json.loads(db_session.segments_json)

    if format == "txt":
        # 纯文本格式
        content = f"Title: {db_session.title}\n"
        content += f"Date: {db_session.created_at.strftime('%Y-%m-%d %H:%M:%S')}\n"
        content += f"Duration: {db_session.duration_seconds:.1f}s\n"
        content += f"Speakers: {db_session.speaker_count}\n"
        content += "\n" + "=" * 50 + "\n\n"

        for seg in segments:
            content += f"[{seg['speaker']}]\n"
            content += f"{seg['text']}\n\n"

        return Response(
            content=content,
            media_type="text/plain",
            headers={"Content-Disposition": f"attachment; filename={session_id}.txt"}
        )

    elif format == "json":
        # JSON 格式
        data = {
            "session_id": db_session.session_id,
            "title": db_session.title,
            "created_at": db_session.created_at.isoformat(),
            "duration_seconds": db_session.duration_seconds,
            "speaker_count": db_session.speaker_count,
            "word_count": db_session.word_count,
            "segments": segments,
            "full_transcript": db_session.full_transcript,
            "ai_summary": db_session.ai_summary,
            "ai_action_items": db_session.ai_action_items,
        }

        return Response(
            content=json.dumps(data, indent=2, ensure_ascii=False),
            media_type="application/json",
            headers={"Content-Disposition": f"attachment; filename={session_id}.json"}
        )

    elif format == "markdown":
        # Markdown 格式
        content = f"# {db_session.title}\n\n"
        content += f"**Date:** {db_session.created_at.strftime('%Y-%m-%d %H:%M:%S')}\n"
        content += f"**Duration:** {db_session.duration_seconds:.1f}s\n"
        content += f"**Speakers:** {db_session.speaker_count}\n"
        content += f"**Words:** {db_session.word_count}\n\n"

        if db_session.ai_summary:
            content += "## AI Summary\n\n"
            content += f"{db_session.ai_summary}\n\n"

        if db_session.ai_action_items:
            content += "## Action Items\n\n"
            content += f"{db_session.ai_action_items}\n\n"

        content += "## Transcript\n\n"

        for seg in segments:
            content += f"### {seg['speaker']}\n\n"
            content += f"{seg['text']}\n\n"

        return Response(
            content=content,
            media_type="text/markdown",
            headers={"Content-Disposition": f"attachment; filename={session_id}.md"}
        )


@app.put("/sessions/{session_id}/title")
async def update_session_title(
    session_id: str,
    title: str,
    db: AsyncSession = Depends(get_db)
):
    """更新会话标题"""
    from sqlalchemy import update

    result = await db.execute(
        update(TranscriptionSessionDB)
        .where(TranscriptionSessionDB.session_id == session_id)
        .values(title=title, updated_at=datetime.utcnow())
    )

    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="Session not found")

    await db.commit()
    return {"message": "Title updated"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
