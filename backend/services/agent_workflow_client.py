from __future__ import annotations

import os
import time
import uuid
from typing import Any

import httpx


class AgentWorkflowUnavailable(RuntimeError):
    pass


class AgentWorkflowClient:
    contract_version = "2026-08-15"

    def __init__(self) -> None:
        self._health_checked_at = 0.0
        self._health_base_url = ""

    def _headers(self, idempotency_key: str | None = None) -> dict[str, str]:
        headers = {"X-Trace-Id": uuid.uuid4().hex, "Idempotency-Key": idempotency_key or uuid.uuid4().hex}
        internal_token = os.getenv("AI_WORKFLOW_INTERNAL_TOKEN", "")
        if internal_token:
            headers["X-Internal-Token"] = internal_token
        return headers

    def _ensure_compatible(self, base_url: str, timeout: float) -> None:
        now = time.monotonic()
        if self._health_base_url == base_url and now - self._health_checked_at < 30:
            return
        try:
            response = httpx.get(f"{base_url}/healthz", timeout=min(timeout, 5.0))
            response.raise_for_status()
            payload = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise AgentWorkflowUnavailable(f"AI 工作流健康检查失败: {exc}") from exc
        actual = str(payload.get("contract_version") or "")
        if actual != self.contract_version:
            raise AgentWorkflowUnavailable(
                f"AI 工作流契约版本不一致（后端={self.contract_version}，工作流={actual or '旧版本'}），请完整重启两项服务"
            )
        components = payload.get("components") or {}
        if int(components.get("tinytroupe_max_actors") or 0) != 1:
            raise AgentWorkflowUnavailable("AI 工作流仍在使用旧的多角色激活配置，请完整重启两项服务")
        self._health_base_url = base_url
        self._health_checked_at = now

    def execute_case_import(self, *, workflow_id: str, case_id: str, source_text: str, idempotency_key: str) -> dict[str, Any]:
        base_url = os.getenv("AI_WORKFLOW_URL", "http://127.0.0.1:8020").rstrip("/")
        timeout = float(os.getenv("CASE_IMPORT_TIMEOUT_SECONDS", "180"))
        self._ensure_compatible(base_url, timeout)
        try:
            response = httpx.post(
                f"{base_url}/v1/case-imports/execute",
                json={"workflow_id": workflow_id, "case_id": case_id, "source_text": source_text},
                headers=self._headers(idempotency_key),
                timeout=timeout,
            )
            response.raise_for_status()
            result = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise AgentWorkflowUnavailable(f"AI workflow service unavailable: {exc}") from exc
        if result.get("status") != "succeeded":
            error = result.get("error") or {}
            raise AgentWorkflowUnavailable(error.get("message") or "Case import workflow failed")
        return result

    def execute(
        self,
        *,
        workflow_id: str,
        stage: str,
        skill: str,
        payload: dict[str, Any],
        case_id: str | None = None,
        training_id: str | None = None,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        headers = self._headers(idempotency_key)
        base_url = os.getenv("AI_WORKFLOW_URL", "http://127.0.0.1:8020").rstrip("/")
        timeout = float(os.getenv("AI_WORKFLOW_TIMEOUT_SECONDS", "120"))
        self._ensure_compatible(base_url, timeout)
        try:
            response = httpx.post(
                f"{base_url}/v1/workflows/execute",
                json={
                    "workflow_id": workflow_id,
                    "stage": stage,
                    "skill": skill,
                    "case_id": case_id,
                    "training_id": training_id,
                    "payload": payload,
                },
                headers=headers,
                timeout=timeout,
            )
            response.raise_for_status()
            result = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise AgentWorkflowUnavailable(f"AI 工作流服务不可用: {exc}") from exc
        if result.get("status") != "succeeded":
            error = result.get("error") or {}
            raise AgentWorkflowUnavailable(error.get("message") or "AI 工作流执行失败")
        return result


agent_workflow_client = AgentWorkflowClient()
