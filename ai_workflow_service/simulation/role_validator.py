from __future__ import annotations

from dataclasses import dataclass

from ai_workflow_service.contracts import Persona


@dataclass(frozen=True)
class ValidationResult:
    valid: bool
    issues: list[str]


class PoliceRoleValidator:
    def validate(
        self,
        *,
        persona: Persona,
        reply: str,
        revealed_fact_ids: list[str],
        allowed_fact_ids: set[str] | None = None,
        audit_issues: list[str] | None = None,
    ) -> ValidationResult:
        issues = []
        allowed = allowed_fact_ids if allowed_fact_ids is not None else set(persona.known_fact_ids) - set(persona.hidden_fact_ids)
        if not reply.strip():
            issues.append("empty_reply")
        if any(fact_id not in allowed for fact_id in revealed_fact_ids):
            issues.append("knowledge_boundary_violation")
        if any(marker in reply for marker in ("根据案件资料", "作为AI", "系统提示", "语言模型")):
            issues.append("identity_or_prompt_leak")
        issues.extend(str(item) for item in audit_issues or [] if str(item).strip())
        return ValidationResult(valid=not issues, issues=list(dict.fromkeys(issues)))
