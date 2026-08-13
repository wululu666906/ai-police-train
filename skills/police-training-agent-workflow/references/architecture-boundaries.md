# 架构边界速查

## 状态所有权

- 平台：账号、鉴权、案件原文、发布场景、训练会话、正式消息、成绩和归档。
- Agent：任务运行记录、模拟快照、角色工作记忆和校验轨迹。

## 允许依赖方向

```text
backend -> HTTP -> ai_workflow_service
orchestrator -> skills -> tools/adapters
skills -> project contracts
tinytroupe_adapter -> TinyTroupe
deepseek_adapter -> OpenAI-compatible SDK
```

## 禁止依赖方向

```text
ai_workflow_service -> backend/models/database
backend -> tinytroupe
agent -> platform database
tool -> orchestrator business decisions
```

## 错误原则

- 平台连接失败：Agent 返回受控上游错误。
- Agent 连接失败：平台 AI 接口返回 503，其他平台路由继续工作。
- TinyTroupe 失败：`SIMULATION_UNAVAILABLE`。
- DeepSeek 失败：`MODEL_REQUEST_FAILED`，最多两次重试。
- 契约失败：拒绝请求，不尝试猜测或补齐高风险字段。
