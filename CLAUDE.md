# AI虚拟警情处置模拟训练平台 AI 地图

## 项目定位

面向公安教学与训练的虚拟警情处置平台。传统平台负责账号、案件、场景、训练会话、成绩和数据持久化；独立 AI 工作流服务负责案件智能处理、人物模拟、场景推演和评估生成。

## 技术栈锁定

- 平台后端：Python 3.11、FastAPI、SQLAlchemy。
- 平台前端：Vue 3、TypeScript、Vite、Element Plus。
- Agent 服务：Python 3.11、FastAPI、Pydantic、HTTPX、TinyTroupe 适配层。
- 模型：DeepSeek OpenAI-compatible API。
- 数据库：由平台独占；Agent 服务不得直接连接。

## 架构边界

1. `backend/` 是传统平台进程，只负责确定性业务、鉴权和持久化。
2. `ai_workflow_service/` 是独立进程，禁止导入 `backend`、`models`、`database`。
3. 跨服务调用只能通过 `backend/services/agent_workflow_client.py` 和已登记 HTTP 契约。
4. Agent 只提出状态迁移建议；平台验证后才执行数据库变更。
5. TinyTroupe 只能由 `simulation/tinytroupe_adapter.py` 导入。
6. DeepSeek 只能由 `llm/deepseek_adapter.py` 调用。
7. 旧 AI 对话、旧多人导演、旧 Persona 和旧状态机链路不得恢复或作为降级路径。
8. Agent 服务异常不得阻塞登录、查询、班级、视频和其他平台功能。

## 核心约束

- 所有跨边界输入使用 Pydantic 白名单模型验证。
- Agent 服务不得获得平台数据库凭据。
- 文件删除、账号权限、成绩入库和最终状态提交仅由平台执行。
- 每个工作流请求必须携带 `trace_id` 和 `idempotency_key`。
- 状态写入 `ai_workflow_service/data/`，上下文窗口不是状态存储。
- 日志不得记录 API Key、完整身份证号或未经脱敏的敏感材料。
- TinyTroupe 或 DeepSeek 失败时返回受控错误，不调用已删除旧链路。
- 新接口必须先登记到 `docs/contracts.md`。

## 目录约定

- `docs/`：架构、契约、ADR 和开发计划。
- `memory/`：跨会话开发状态。
- `scripts/audit_harness.py`：机械化边界和文档同步检查。
- `ai_workflow_service/agents`：唯一主控 Agent。
- `ai_workflow_service/skills`：业务能力，不直接访问平台。
- `ai_workflow_service/tools`：无业务判断的执行工具。
- `ai_workflow_service/simulation`：TinyTroupe 隔离层。
- `skills/`：项目内 Codex 维护 Skill，不安装到用户全局目录。

## 开发流程

1. 读取本文件和 `memory/session-state.md`。
2. 先更新契约或 ADR，再修改跨边界实现。
3. 实现后运行 `python scripts/audit_harness.py`。
4. 运行 Python 编译、导入检查及前端 `vue-tsc`。
5. 更新开发计划与会话状态。

## 已知限制

- TinyTroupe 为实验性依赖，必须固定提交版本并通过适配层使用。
- 当前平台历史模型较集中，数据库重构不属于本轮范围。
- 当前工作区包含用户未提交改动，禁止复原或覆盖。

## 更新触发条件

技术栈、跨服务契约、目录边界、状态所有权或安全约束变化时更新本文件。
