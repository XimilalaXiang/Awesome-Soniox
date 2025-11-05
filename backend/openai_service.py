import logging
from typing import AsyncGenerator
import aiohttp
from models import OpenAIConfig

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class OpenAIService:
    """OpenAI 兼容 API 服务"""

    def __init__(self, config: OpenAIConfig):
        self.config = config
        self.api_url = config.api_url.rstrip("/") + "/chat/completions"

    async def summarize(self, transcript: str, prompt: str) -> AsyncGenerator[str, None]:
        """
        使用 OpenAI 兼容 API 总结转录内容（流式）

        Args:
            transcript: 转录文本
            prompt: 总结提示词

        Yields:
            总结内容的流式文本块
        """
        try:
            headers = {
                "Authorization": f"Bearer {self.config.api_key}",
                "Content-Type": "application/json"
            }

            payload = {
                "model": self.config.model,
                "messages": [
                    {
                        "role": "system",
                        "content": "你是一个专业的会议助手，擅长总结和分析会议内容。"
                    },
                    {
                        "role": "user",
                        "content": f"{prompt}\n\n转录内容：\n{transcript}"
                    }
                ],
                "stream": True,
                "temperature": 0.7
            }

            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.api_url,
                    headers=headers,
                    json=payload
                ) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        logger.error(f"OpenAI API error: {error_text}")
                        yield f"错误: {error_text}"
                        return

                    # 处理流式响应
                    async for line in response.content:
                        line = line.decode("utf-8").strip()
                        if line.startswith("data: "):
                            data_str = line[6:]  # 移除 "data: " 前缀

                            if data_str == "[DONE]":
                                break

                            try:
                                import json
                                data = json.loads(data_str)
                                if "choices" in data and len(data["choices"]) > 0:
                                    delta = data["choices"][0].get("delta", {})
                                    content = delta.get("content", "")
                                    if content:
                                        yield content
                            except json.JSONDecodeError:
                                continue

        except Exception as e:
            logger.error(f"Error in OpenAI service: {str(e)}")
            yield f"错误: {str(e)}"

    async def answer_question(
        self, transcript: str, question: str
    ) -> AsyncGenerator[str, None]:
        """
        使用 OpenAI 兼容 API 回答关于转录内容的问题（流式）

        Args:
            transcript: 转录文本
            question: 用户问题

        Yields:
            回答内容的流式文本块
        """
        try:
            headers = {
                "Authorization": f"Bearer {self.config.api_key}",
                "Content-Type": "application/json"
            }

            payload = {
                "model": self.config.model,
                "messages": [
                    {
                        "role": "system",
                        "content": "你是一个专业的会议助手。请根据提供的会议转录内容回答用户的问题。"
                    },
                    {
                        "role": "user",
                        "content": f"会议转录内容：\n{transcript}\n\n问题：{question}"
                    }
                ],
                "stream": True,
                "temperature": 0.7
            }

            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.api_url,
                    headers=headers,
                    json=payload
                ) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        logger.error(f"OpenAI API error: {error_text}")
                        yield f"错误: {error_text}"
                        return

                    # 处理流式响应
                    async for line in response.content:
                        line = line.decode("utf-8").strip()
                        if line.startswith("data: "):
                            data_str = line[6:]

                            if data_str == "[DONE]":
                                break

                            try:
                                import json
                                data = json.loads(data_str)
                                if "choices" in data and len(data["choices"]) > 0:
                                    delta = data["choices"][0].get("delta", {})
                                    content = delta.get("content", "")
                                    if content:
                                        yield content
                            except json.JSONDecodeError:
                                continue

        except Exception as e:
            logger.error(f"Error in OpenAI service: {str(e)}")
            yield f"错误: {str(e)}"
