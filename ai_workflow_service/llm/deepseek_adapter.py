from __future__ import annotations

import json
from typing import Any

from openai import OpenAI

from ai_workflow_service.config import Settings
from ai_workflow_service.errors import WorkflowServiceError


class DeepSeekAdapter:
    def __init__(self, settings: Settings):
        self.settings = settings
        self._client = OpenAI(
            api_key=settings.deepseek_api_key or "missing-api-key",
            base_url=settings.deepseek_base_url,
            timeout=settings.deepseek_timeout_seconds,
        )

    @property
    def configured(self) -> bool:
        return bool(self.settings.deepseek_api_key)

    def complete_json(
        self,
        *,
        system: str,
        user: str,
        temperature: float = 0.3,
        max_tokens: int = 4000,
    ) -> dict[str, Any]:
        if not self.configured:
            raise WorkflowServiceError("MODEL_NOT_CONFIGURED", "DeepSeek API Key 未配置")
        last_error: Exception | None = None
        for _ in range(2):
            try:
                response = self._client.chat.completions.create(
                    model=self.settings.deepseek_model,
                    messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
                    response_format={"type": "json_object"},
                    temperature=temperature,
                    max_tokens=max_tokens,
                )
                content = response.choices[0].message.content or "{}"
                result = json.loads(content)
                if not isinstance(result, dict):
                    raise ValueError("模型返回值不是 JSON 对象")
                return result
            except Exception as exc:
                last_error = exc
        raise WorkflowServiceError("MODEL_REQUEST_FAILED", f"DeepSeek 请求失败: {last_error}", retryable=True)
