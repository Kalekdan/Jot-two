from __future__ import annotations

import asyncio
import json
import os
from typing import Any
from urllib import error, request

from src.core.messages import Message


# Set to True to return the full raw API response body for debugging.
DEBUG_RAW_API_RESPONSE = False


class Agent:
    """Single-turn agent that generates replies from an OpenAI-compatible chat API."""

    def __init__(self) -> None:
        self.api_key = os.environ.get("OPENAI_API_KEY", "").strip()
        self.base_url = os.environ.get("OPENAI_BASE_URL", "https://api.openai.com").strip()
        self.chat_endpoint = os.environ.get("OPENAI_CHAT_ENDPOINT", "/v1/chat/completions").strip()
        self.model = os.environ.get("OPENAI_MODEL", "gpt-5-nano").strip()
        self.system_prompt = os.environ.get(
            "OPENAI_SYSTEM_PROMPT",
            "You are Jot-two, a concise and helpful assistant.",
        ).strip()
        self.timeout_seconds = float(os.environ.get("OPENAI_TIMEOUT_SECONDS", "60"))

    def _build_url(self) -> str:
        return f"{self.base_url.rstrip('/')}/{self.chat_endpoint.lstrip('/')}"

    def _call_llm(self, user_text: str) -> str:
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": user_text},
            ],
        }

        req = request.Request(
            self._build_url(),
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}",
            },
            method="POST",
        )

        with request.urlopen(req, timeout=self.timeout_seconds) as response:
            raw_body = response.read().decode("utf-8", errors="replace")

        if DEBUG_RAW_API_RESPONSE:
            return raw_body

        body = json.loads(raw_body)

        choices = body.get("choices", [])
        if not choices:
            return "I received an empty response from the model endpoint."

        message = choices[0].get("message", {})
        content = message.get("content", "")
        if isinstance(content, str):
            return content.strip()

        if isinstance(content, list):
            parts: list[str] = []
            for item in content:
                if not isinstance(item, dict):
                    continue
                text = item.get("text")
                if isinstance(text, str) and text.strip():
                    parts.append(text.strip())
            if parts:
                return "\n".join(parts)

        return "I could not parse the model response content."

    async def process(self, message: Message) -> Message:
        user_text = str(message.payload.get("text", "")).strip()

        if not user_text:
            output_text = "I did not receive any text to process."
        elif not self.api_key:
            output_text = "OPENAI_API_KEY is not configured."
        else:
            try:
                output_text = await asyncio.to_thread(self._call_llm, user_text)
            except error.HTTPError as exc:
                error_body = exc.read().decode("utf-8", errors="replace")
                if DEBUG_RAW_API_RESPONSE:
                    output_text = error_body or f"HTTP {exc.code} with empty response body."
                else:
                    output_text = (
                        f"Model request failed with HTTP {exc.code}. "
                        f"Response: {error_body}"
                    )
            except (error.URLError, TimeoutError, json.JSONDecodeError, ValueError) as exc:
                output_text = f"Model request failed: {exc}"

        response = Message(
            request_id=message.request_id,
            source=message.source,
            user_id=message.user_id,
            reply_channel=message.reply_channel,
            timestamp=message.timestamp,
            payload={"text": output_text},
        )

        await asyncio.sleep(0)
        return response
