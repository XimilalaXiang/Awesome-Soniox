from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime


class TranscriptionToken(BaseModel):
    """单个转录 token"""
    text: str
    start_ms: float
    end_ms: float
    confidence: float
    is_final: bool
    speaker: Optional[str] = None
    language: Optional[str] = None


class TranscriptionSegment(BaseModel):
    """转录片段（按发言人分组）"""
    speaker: str
    text: str
    start_time: float
    end_time: float
    tokens: List[TranscriptionToken]


class TranscriptionSession(BaseModel):
    """转录会话"""
    session_id: str
    title: str
    created_at: datetime
    segments: List[TranscriptionSegment] = []
    full_transcript: str = ""
    status: str = "active"  # active, stopped, completed


class SonioxConfig(BaseModel):
    """Soniox API 配置"""
    api_key: str
    model: str = "stt-rt-v3"
    enable_speaker_diarization: bool = True
    enable_language_identification: bool = False
    language_hints: List[str] = []


class OpenAIConfig(BaseModel):
    """OpenAI 兼容 API 配置"""
    api_url: str = Field(default="https://api.openai.com/v1")
    api_key: str
    model: str = Field(default="gpt-4o-mini")


class SummarizeRequest(BaseModel):
    """总结请求"""
    session_id: str
    prompt: Optional[str] = "请总结以下会议内容的要点："
    openai_config: OpenAIConfig


class QuestionRequest(BaseModel):
    """提问请求"""
    session_id: str
    question: str
    openai_config: OpenAIConfig
