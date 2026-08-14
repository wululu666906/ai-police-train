from __future__ import annotations

import ast
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REQUIRED = [
    "CLAUDE.md",
    "docs/architecture.md",
    "docs/contracts.md",
    "docs/260812平台大更新开发计划.md",
    "memory/session-state.md",
    "ai_workflow_service/main.py",
    "backend/services/agent_workflow_client.py",
]
FORBIDDEN_LEGACY = [
    "backend/services/ai_service.py",
    "backend/services/evaluation_service.py",
    "backend/services/persona_engine.py",
    "backend/services/multi_role_actor.py",
    "backend/services/multi_role_director.py",
    "backend/services/state_influence_engine.py",
    "ai_workflow_service/skills/case_parse_skill.py",
    "ai_workflow_service/skills/persona_build_skill.py",
    "ai_workflow_service/skills/scene_build_skill.py",
]


def python_files(root: Path):
    for path in root.rglob("*.py"):
        if any(part in {"venv", "node_modules", "__pycache__"} for part in path.parts):
            continue
        yield path


def imported_roots(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            roots.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            roots.add(node.module.split(".")[0])
    return roots


def main() -> int:
    errors: list[str] = []
    warnings: list[str] = []
    for relative in REQUIRED:
        if not (ROOT / relative).exists():
            errors.append(f"缺少 Harness 文件: {relative}")
    for relative in FORBIDDEN_LEGACY:
        if (ROOT / relative).exists():
            errors.append(f"旧链路仍存在: {relative}")
    for path in python_files(ROOT / "ai_workflow_service"):
        try:
            roots = imported_roots(path)
        except (SyntaxError, UnicodeDecodeError) as exc:
            errors.append(f"无法解析 {path.relative_to(ROOT)}: {exc}")
            continue
        forbidden = roots & {"backend", "models", "database"}
        if forbidden:
            errors.append(f"Agent 越界导入 {path.relative_to(ROOT)}: {sorted(forbidden)}")
        if path.name != "tinytroupe_adapter.py" and "tinytroupe" in roots:
            errors.append(f"TinyTroupe 绕过 Adapter: {path.relative_to(ROOT)}")
    for path in python_files(ROOT / "backend"):
        try:
            roots = imported_roots(path)
        except (SyntaxError, UnicodeDecodeError):
            continue
        if "tinytroupe" in roots:
            errors.append(f"平台直接导入 TinyTroupe: {path.relative_to(ROOT)}")
    contracts = (ROOT / "docs/contracts.md").read_text(encoding="utf-8")
    for endpoint in ("/healthz", "/v1/workflows/execute", "/v1/case-imports/execute", "/v1/workflows/{workflow_id}"):
        if endpoint not in contracts:
            errors.append(f"契约未登记接口: {endpoint}")
    contract_source = (ROOT / "ai_workflow_service/contracts.py").read_text(encoding="utf-8")
    for legacy_skill in ("case_parse", "persona_build", "scene_build"):
        if f'{legacy_skill} = "{legacy_skill}"' in contract_source:
            errors.append(f"旧 Skill 契约仍存在: {legacy_skill}")
    if (ROOT / "frontend/pnpm-lock.yaml").exists() or (ROOT / "frontend/pnpm-workspace.yaml").exists():
        warnings.append("前端仍存在 pnpm 配置，但构建链使用 npm ci")
    for message in warnings:
        print(f"WARN: {message}")
    for message in errors:
        print(f"ERROR: {message}")
    if errors:
        return 1
    print("Harness audit passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
