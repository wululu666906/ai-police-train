---
name: police-training-agent-workflow
description: Maintain and extend this repository's isolated police-training Agent + Skill + Tool workflow, TinyTroupe persona simulation, DeepSeek adapter, platform HTTP boundary, workflow contracts, and Harness documentation. Use when changing ai_workflow_service, adding a runtime Skill or Tool, modifying cross-service workflow APIs, diagnosing Agent isolation, or cleaning obsolete AI pipeline code in this project.
---

# 维护警情 Agent 工作流

## 开始前

1. 读取仓库根目录 `CLAUDE.md`。
2. 读取 `memory/session-state.md` 恢复进度。
3. 涉及跨服务数据时读取 `docs/contracts.md`。
4. 涉及架构选择时读取 `docs/decisions/` 中相关 ADR。

## 边界

- 保持 `backend/` 与 `ai_workflow_service/` 为独立进程。
- 禁止 Agent 服务导入 `backend`、`models` 或 `database`。
- 禁止平台直接导入 TinyTroupe；TinyTroupe 只存在于其 Adapter。
- 禁止 Skill 直接修改平台数据库、权限、成绩或正式训练状态。
- 禁止恢复已删除的旧对话、多人导演、Persona、状态影响和评估链路。
- 跨服务能力必须经 `backend/services/agent_workflow_client.py` 调用。

## 修改流程

1. 先在 `docs/contracts.md` 登记或更新接口。
2. 为重大边界变化新增或更新 ADR。
3. 将业务判断放入 Skill，将纯执行放入 Tool。
4. 将第三方 TinyTroupe API 变化封装在 Adapter 内。
5. 用 Pydantic `extra="forbid"` 校验边界输入。
6. 将长期状态写入 Agent 自有状态存储。
7. 更新 `docs/260812平台大更新开发计划.md` 和 `memory/session-state.md`。
8. 运行 `python scripts/audit_harness.py` 以及项目类型检查。

## 新增运行时 Skill

1. 在 `ai_workflow_service/contracts.py` 登记 Skill 名称和输入模型。
2. 在 `ai_workflow_service/skills/` 实现单一业务能力。
3. 在 Orchestrator 的显式状态图中登记允许入口。
4. 不在 Skill 中直接调用数据库、文件删除或平台内部模块。
5. 更新接口契约和开发计划。

详细目录和错误规则见 [architecture-boundaries.md](references/architecture-boundaries.md)。
