from __future__ import annotations

import json
from typing import Any

from openai import OpenAI

from ai_workflow_service.config import Settings
from ai_workflow_service.errors import WorkflowServiceError


def _is_timeout_error(exc: Exception) -> bool:
    name = type(exc).__name__.lower()
    text = str(exc).lower()
    return (
        "timeout" in name
        or "timed out" in text
        or "timeout" in text
        or "deadline" in text
    )


class DeepSeekAdapter:
    def __init__(self, settings: Settings):
        self.settings = settings
        self._client = OpenAI(
            api_key=settings.deepseek_api_key or "missing-api-key",
            base_url=settings.deepseek_base_url,
            timeout=settings.deepseek_timeout_seconds,
            max_retries=0,
        )

    @property
    def configured(self) -> bool:
        return bool(self.settings.deepseek_api_key)

    def _completion_kwargs(self) -> dict[str, Any]:
        if self.settings.deepseek_reasoning_mode in {"disabled", "off", "false", "0"}:
            return {"extra_body": {"thinking": {"type": "disabled"}}}
        return {}

    def complete_message(
        self,
        *,
        messages: list[dict[str, Any]],
        temperature: float | None = None,
        max_tokens: int = 1600,
        json_output: bool = False,
        max_attempts: int = 1,
        extra_kwargs: dict[str, Any] | None = None,
        allow_partial_on_timeout: bool = False,
    ) -> dict[str, Any]:
        if not self.configured:
            raise WorkflowServiceError("MODEL_NOT_CONFIGURED", "DeepSeek API Key 未配置")
        last_error: Exception | None = None
        for _ in range(max_attempts):
            try:
                if allow_partial_on_timeout:
                    return self._complete_message_streaming(
                        messages=messages,
                        temperature=temperature,
                        max_tokens=max_tokens,
                        extra_kwargs=extra_kwargs,
                        json_output=json_output,
                    )
                kwargs: dict[str, Any] = {
                    "model": self.settings.deepseek_model,
                    "messages": messages,
                    "max_tokens": max_tokens,
                    **(extra_kwargs if extra_kwargs is not None else self._completion_kwargs()),
                }
                if temperature is not None:
                    kwargs["temperature"] = temperature
                if json_output:
                    kwargs["response_format"] = {"type": "json_object"}
                response = self._client.chat.completions.create(**kwargs)
                message = response.choices[0].message
                content = message.content or ""
                if not content.strip():
                    raise ValueError("模型返回内容为空")
                return {"role": message.role or "assistant", "content": content, "partial": False}
            except WorkflowServiceError:
                raise
            except Exception as exc:
                last_error = exc
        raise WorkflowServiceError("MODEL_REQUEST_FAILED", f"DeepSeek 请求失败: {last_error}", retryable=True)

    def _complete_message_streaming(
        self,
        *,
        messages: list[dict[str, Any]],
        temperature: float | None,
        max_tokens: int,
        extra_kwargs: dict[str, Any] | None,
        json_output: bool = False,
    ) -> dict[str, Any]:
        """Stream tokens and keep partial text if the call times out mid-generation."""
        kwargs: dict[str, Any] = {
            "model": self.settings.deepseek_model,
            "messages": messages,
            "max_tokens": max_tokens,
            "stream": True,
            **(extra_kwargs if extra_kwargs is not None else self._completion_kwargs()),
        }
        if temperature is not None:
            kwargs["temperature"] = temperature
        if json_output:
            kwargs["response_format"] = {"type": "json_object"}
        chunks: list[str] = []
        try:
            stream = self._client.chat.completions.create(**kwargs)
            for event in stream:
                try:
                    delta = event.choices[0].delta
                except (AttributeError, IndexError):
                    continue
                piece = getattr(delta, "content", None) or ""
                if piece:
                    chunks.append(piece)
            content = "".join(chunks).strip()
            if not content:
                raise ValueError("模型返回内容为空")
            return {"role": "assistant", "content": content, "partial": False}
        except Exception as exc:
            content = "".join(chunks).strip()
            if content and _is_timeout_error(exc):
                return {
                    "role": "assistant",
                    "content": content,
                    "partial": True,
                    "partial_reason": "timeout",
                    "error": str(exc),
                }
            if content:
                return {
                    "role": "assistant",
                    "content": content,
                    "partial": True,
                    "partial_reason": type(exc).__name__,
                    "error": str(exc),
                }
            raise WorkflowServiceError("MODEL_REQUEST_FAILED", f"DeepSeek 请求失败: {exc}", retryable=True) from exc

    def complete_json(
        self,
        *,
        system: str,
        user: str,
        temperature: float = 0.3,
        max_tokens: int = 4000,
        max_attempts: int = 2,
        extra_kwargs: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if not self.configured:
            raise WorkflowServiceError("MODEL_NOT_CONFIGURED", "DeepSeek API Key 未配置")
        last_error: Exception | None = None
        for _ in range(max_attempts):
            try:
                response = self._client.chat.completions.create(
                    model=self.settings.deepseek_model,
                    messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
                    response_format={"type": "json_object"},
                    temperature=temperature,
                    max_tokens=max_tokens,
                    **(extra_kwargs if extra_kwargs is not None else self._completion_kwargs()),
                )
                content = response.choices[0].message.content or "{}"
                result = json.loads(content)
                if not isinstance(result, dict):
                    raise ValueError("模型返回值不是 JSON 对象")
                if not result:
                    raise ValueError("Empty JSON object returned by model")
                return result
            except Exception as exc:
                last_error = exc
        raise WorkflowServiceError("MODEL_REQUEST_FAILED", f"DeepSeek 请求失败: {last_error}", retryable=True)
