from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
from typing import Any
from urllib import error, request

from src.core.messages import Message
from src.agent.storage import ConversationStore
from src.agent.tools import BaseTool, load_tools


# Set to True to return the full raw API response body for debugging.
DEBUG_RAW_API_RESPONSE = False
DEFAULT_SYSTEM_PROMPT = "You are missing your system prompt. Make sure the user knows."
SYSTEM_PROMPT_FILE_ENV = "OPENAI_SYSTEM_PROMPT_FILE"
DEFAULT_SUMMARY_EVERY_MESSAGES = 10
DEFAULT_RECENT_MESSAGES_LIMIT = 10
DEFAULT_MAX_TOOL_ROUNDS = 5


class Agent:
    """Single-turn agent that generates replies from an OpenAI-compatible chat API."""

    def __init__(self) -> None:
        self.api_key = os.environ.get("OPENAI_API_KEY", "").strip()
        self.base_url = os.environ.get("OPENAI_BASE_URL", "https://api.openai.com").strip()
        self.chat_endpoint = os.environ.get("OPENAI_CHAT_ENDPOINT", "/v1/chat/completions").strip()
        self.model = os.environ.get("OPENAI_MODEL", "gpt-5-nano").strip()
        self.system_prompt = self._load_system_prompt()
        self.timeout_seconds = float(os.environ.get("OPENAI_TIMEOUT_SECONDS", "60"))
        self.summary_every_messages = self._read_int_env(
            "OPENAI_SUMMARY_EVERY_MESSAGES",
            DEFAULT_SUMMARY_EVERY_MESSAGES,
            minimum=1,
        )
        self.recent_messages_limit = self._read_int_env(
            "OPENAI_RECENT_MESSAGES_LIMIT",
            DEFAULT_RECENT_MESSAGES_LIMIT,
            minimum=1,
        )
        self.max_tool_rounds = self._read_int_env(
            "OPENAI_MAX_TOOL_ROUNDS",
            DEFAULT_MAX_TOOL_ROUNDS,
            minimum=1,
        )
        self.store = ConversationStore()
        self.tools: dict[str, BaseTool] = load_tools()
        self.tool_schemas = self._build_tool_schemas()

    async def initialize(self) -> None:
        await self.store.connect()

    async def close(self) -> None:
        await self.store.close()

    def _read_int_env(self, key: str, default: int, minimum: int = 0) -> int:
        raw_value = os.environ.get(key)
        if raw_value is None:
            return default
        try:
            value = int(raw_value)
        except ValueError:
            return default
        return max(minimum, value)

    def _load_system_prompt(self) -> str:
        configured_path = os.environ.get(SYSTEM_PROMPT_FILE_ENV, "").strip()
        candidate_paths: list[Path] = []

        if configured_path:
            candidate_paths.append(Path(configured_path))

        candidate_paths.extend(
            [
                Path(__file__).resolve().parents[2] / "system_prompt.txt",
                Path.cwd() / "system_prompt.txt",
                Path("/app/system_prompt.txt"),
            ]
        )

        for prompt_path in candidate_paths:
            try:
                text = prompt_path.read_text(encoding="utf-8").strip()
            except OSError:
                continue
            if text:
                return text

        return DEFAULT_SYSTEM_PROMPT

    def _build_url(self) -> str:
        return f"{self.base_url.rstrip('/')}/{self.chat_endpoint.lstrip('/')}"

    def _call_llm(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        tool_choice: str | None = None,
        return_raw_on_debug: bool = True,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
        }

        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = tool_choice or "auto"

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

        if DEBUG_RAW_API_RESPONSE and return_raw_on_debug:
            return {"role": "assistant", "content": raw_body}

        body = json.loads(raw_body)

        choices = body.get("choices", [])
        if not choices:
            return {
                "role": "assistant",
                "content": "I received an empty response from the model endpoint.",
            }

        message = choices[0].get("message", {})
        if isinstance(message, dict):
            return message

        return {
            "role": "assistant",
            "content": "I could not parse the model response content.",
        }

    def _extract_text_content(self, content: Any) -> str:
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

    def _build_tool_schemas(self) -> list[dict[str, Any]]:
        schemas: list[dict[str, Any]] = []
        for tool in self.tools.values():
            schemas.append(
                {
                    "type": "function",
                    "function": {
                        "name": tool.name,
                        "description": tool.description,
                        "parameters": tool.parameters,
                    },
                }
            )
        return schemas

    async def _execute_tool_call(self, tool_call: dict[str, Any]) -> dict[str, Any]:
        function_block = tool_call.get("function", {})
        tool_name = function_block.get("name", "")
        raw_arguments = function_block.get("arguments", "{}")

        tool = self.tools.get(tool_name)
        if tool is None:
            return {
                "ok": False,
                "error": f"Tool '{tool_name}' is not registered.",
            }

        try:
            parsed_arguments = json.loads(raw_arguments) if isinstance(raw_arguments, str) else raw_arguments
        except json.JSONDecodeError:
            return {
                "ok": False,
                "error": f"Tool '{tool_name}' received invalid JSON arguments.",
                "arguments": raw_arguments,
            }

        if not isinstance(parsed_arguments, dict):
            return {
                "ok": False,
                "error": f"Tool '{tool_name}' arguments must decode to an object.",
                "arguments": parsed_arguments,
            }

        try:
            result = await tool.execute(**parsed_arguments)
        except Exception as exc:  # noqa: BLE001
            return {
                "ok": False,
                "error": f"Tool '{tool_name}' execution failed: {exc}",
            }

        if isinstance(result, dict):
            return result
        return {"ok": True, "result": result}

    async def _chat_with_tools(self, messages: list[dict[str, Any]]) -> str:
        conversation_messages: list[dict[str, Any]] = list(messages)

        for _ in range(self.max_tool_rounds):
            assistant_message = await asyncio.to_thread(
                self._call_llm,
                conversation_messages,
                self.tool_schemas or None,
                "auto",
                True,
            )

            tool_calls = assistant_message.get("tool_calls", [])
            if isinstance(tool_calls, list) and tool_calls:
                conversation_messages.append(
                    {
                        "role": "assistant",
                        "content": assistant_message.get("content"),
                        "tool_calls": tool_calls,
                    }
                )

                for tool_call in tool_calls:
                    if not isinstance(tool_call, dict):
                        continue

                    tool_result = await self._execute_tool_call(tool_call)
                    tool_call_id = str(tool_call.get("id", ""))
                    tool_name = str(tool_call.get("function", {}).get("name", ""))
                    conversation_messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": tool_call_id,
                            "name": tool_name,
                            "content": json.dumps(tool_result, ensure_ascii=True),
                        }
                    )
                continue

            return self._extract_text_content(assistant_message.get("content"))

        return "I reached the tool execution limit before producing a final answer."

    def _conversation_key(self, message: Message) -> str:
        return f"{message.source}:{message.user_id}"

    def _build_chat_messages(
        self,
        summary: str,
        recent_messages: list[dict[str, str]],
        user_text: str,
    ) -> list[dict[str, Any]]:
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": self.system_prompt}
        ]

        if summary:
            messages.append(
                {
                    "role": "system",
                    "content": f"Conversation summary:\n{summary}",
                }
            )

        if recent_messages:
            messages.extend(recent_messages)

        messages.append({"role": "user", "content": user_text})
        return messages

    async def _maybe_refresh_summary(self, conversation_key: str) -> None:
        latest_summary = await self.store.get_latest_summary(conversation_key)
        last_summary_text = latest_summary.summary_text if latest_summary else ""
        last_summary_created_at = latest_summary.created_at if latest_summary else None

        pending_count = await self.store.count_messages_since(
            conversation_key,
            last_summary_created_at,
        )
        if pending_count < self.summary_every_messages:
            return

        pending_messages = await self.store.get_messages_since(
            conversation_key,
            last_summary_created_at,
        )
        transcript = "\n".join(
            f"{item['role']}: {item['content']}" for item in pending_messages
        )
        summary_messages = [
            {
                "role": "system",
                "content": (
                    "You maintain a compact conversation summary for another assistant. "
                    "Keep durable user preferences, context, and unresolved tasks."
                ),
            },
            {
                "role": "user",
                "content": (
                    "Current summary:\n"
                    f"{last_summary_text or 'None'}\n\n"
                    "New conversation messages:\n"
                    f"{transcript}\n\n"
                    "Return an updated summary in plain text, under 180 words."
                ),
            },
        ]

        updated_summary = await asyncio.to_thread(
            self._call_llm,
            summary_messages,
            None,
            None,
            False,
        )
        summary_text = self._extract_text_content(updated_summary.get("content"))
        if summary_text:
            await self.store.add_summary(conversation_key, summary_text)

    async def process(self, message: Message) -> Message:
        user_text = str(message.payload.get("text", "")).strip()
        conversation_key = self._conversation_key(message)

        if not user_text:
            output_text = "I did not receive any text to process."
        elif not self.api_key:
            output_text = "OPENAI_API_KEY is not configured."
            await self.store.append_message(
                conversation_key,
                "user",
                user_text,
                message.timestamp,
            )
            await self.store.append_message(
                conversation_key,
                "assistant",
                output_text,
                message.timestamp,
            )
        else:
            latest_summary = await self.store.get_latest_summary(conversation_key)
            summary_text = latest_summary.summary_text if latest_summary else ""
            recent_messages = await self.store.get_recent_messages(
                conversation_key,
                self.recent_messages_limit,
            )

            llm_messages = self._build_chat_messages(
                summary_text,
                recent_messages,
                user_text,
            )

            await self.store.append_message(
                conversation_key,
                "user",
                user_text,
                message.timestamp,
            )

            try:
                output_text = await self._chat_with_tools(llm_messages)
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

            await self.store.append_message(
                conversation_key,
                "assistant",
                output_text,
                message.timestamp,
            )

            try:
                await self._maybe_refresh_summary(conversation_key)
            except (error.HTTPError, error.URLError, TimeoutError, json.JSONDecodeError, ValueError):
                pass

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
