# AI 工作流隔离架构

## 设计目标

平台与 AI 工作流必须能独立启动、独立失败和独立恢复。AI 服务不可用时，平台的非 AI 功能保持可用；平台不可达时，AI 服务健康检查和已外化的工作流状态仍可读取。

## 进程边界

```text
Vue 前端
   |
   v
平台 FastAPI  ---- 平台数据库/对象存储
   |
   | 受控 HTTP + trace_id + idempotency_key
   v
AI Workflow FastAPI ---- 独立工作流状态目录
   |          |
   |          +---- DeepSeekAdapter ---- DeepSeek API
   |
   +---- TrainingOrchestratorAgent
              |
              +---- Skills ---- Tools
              |
              +---- RoleSimulationSkill
                        |
                        +---- TinyTroupeAdapter ---- persistent TinyWorld/TinyPerson
                        |
                        +---- PoliceTrainingWorld ---- state/disclosure/stage rules
```

## 七层 Harness

1. 执行环境：独立容器、依赖和端口；不共享数据库凭据。
2. 工具接口：Tool 只执行，禁止自行决定状态迁移。
3. 上下文管理：CaseWorld、Persona、SceneWorld、四层记忆按需装配。
4. 生命周期编排：Orchestrator 通过显式状态图选择 Skill。
5. 可观测：统一 trace、阶段、耗时、模型和错误代码。
6. 验证：Pydantic 契约、角色事实边界、Harness 审计和类型检查。
7. 治理：ADR、接口登记、最小权限和依赖定期检查。

## 故障隔离

- 平台调用 Agent 超时后返回 `503 AI_WORKFLOW_UNAVAILABLE`，不影响其他路由。
- Agent 不可访问平台数据库，因此不能破坏账号、成绩或训练数据。
- TinyTroupe 导入或运行失败转成 `SIMULATION_UNAVAILABLE`。
- 角色台词只能来自 TinyTroupe 的 `TALK`；DeepSeek 作为 TinyTroupe 底层模型并执行只读聚合审计，不二次改写台词。
- 全部场景角色接收公开事件；TinyTroupe 世界内最多 6 名在场角色自行行动，未开口视为合法沉默。
- DeepSeek 超时、限流或无效输出转成明确错误；最多两次受控重试。
- 所有已接收任务状态写入 Agent 自有存储，进程重启后可恢复。

## 状态所有权

- 平台：用户、案件原文、发布场景、训练会话、消息、正式成绩、归档。
- Agent：工作流运行记录、模拟快照、角色工作记忆、校验轨迹。
- Agent 返回建议状态，平台根据允许迁移表决定是否持久化。
- TinyWorld 快照按训练工作流独立保存；幂等重放不重复推进世界，校验失败不提交本轮快照。
