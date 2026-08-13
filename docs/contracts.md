# 跨服务接口契约

本文件是平台与 AI 工作流服务之间接口的权威登记簿。未登记接口不得被平台调用。

## 通用请求头

- `X-Trace-Id`：必填，调用链标识。
- `Idempotency-Key`：写操作必填，同一任务重试保持一致。
- `X-Internal-Token`：可选的内部服务令牌；生产环境必须配置。

## 通用错误

```json
{
  "code": "AI_WORKFLOW_UNAVAILABLE",
  "message": "AI 工作流服务暂时不可用",
  "trace_id": "trace-id",
  "retryable": true
}
```

## 接口登记

| 名称 | 方向 | 模式 | 路径 | 状态副作用 | 安全级别 |
|---|---|---|---|---|---|
| Agent 健康检查 | 平台 -> Agent | SYNC | `GET /healthz` | 无 | 低 |
| 执行工作流 | 平台 -> Agent | SYNC | `POST /v1/workflows/execute` | 写 Agent 状态 | 受限 |
| 查询工作流 | 平台 -> Agent | SYNC | `GET /v1/workflows/{workflow_id}` | 无 | 受限 |

## POST /v1/workflows/execute

请求字段：

- `workflow_id: string`，平台生成的稳定标识。
- `stage: enum`，仅允许已声明的工作流状态。
- `skill: enum|null`，为空时由 Orchestrator 选择。
- `case_id: string|null`、`training_id: string|null`。
- `payload: object`，由目标 Skill 的白名单模型再次校验。

返回字段：

- `workflow_id`、`trace_id`、`stage`、`next_stage`、`skill`。
- `status: succeeded|failed`。
- `result: object`。
- `transition_proposal: object|null`，仅为建议，不直接修改平台数据。
- `error: object|null`。

## 边界规则

- Agent 不接受 SQL、文件删除路径、账号权限或成绩写入指令。
- 平台不得向 Agent 发送数据库 URL、API Key 或认证凭据。
- `payload` 最大 2MB；角色对话只传当前必要事实和有限历史。
- 平台必须验证 `transition_proposal` 是否符合自身状态机。
