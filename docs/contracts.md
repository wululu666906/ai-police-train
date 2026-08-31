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
| 案件导入主流程 | 平台 -> Agent | SYNC | `POST /v1/case-imports/execute` | 写 Agent 状态与节点审计 | 受限 |
| 查询工作流 | 平台 -> Agent | SYNC | `GET /v1/workflows/{workflow_id}` | 无 | 受限 |

## POST /v1/workflows/execute

请求字段：

- `workflow_id: string`，平台生成的稳定标识。
- `stage: enum`，仅允许已声明的工作流状态。
- `skill: enum|null`，为空时由 Orchestrator 选择。
- `case_id: string|null`、`training_id: string|null`。
- `payload: object`，由目标 Skill 的白名单模型再次校验。

`role_simulation` 的 `payload` 必须包含全部场景 `personas`、逐角色状态与隔离记忆、`scene_world`、`case_world`、完整公开历史和可选的 `target_role_name`。`scene_world` 必须提供本场景 `fact_ids` 和逐角色 `role_participation`。单个旧 `persona` 仅保留服务端兼容解析，不再由平台发送。开场生成可把 `input_kind` 设为 `opening`，此时 TinyTroupe 按剧情主动开口，不得把系统开场提示当作学员台词入库。场景在场角色人数默认上限为 24（配置项 `TINY_TROUPE_MAX_ACTORS`，硬顶 32），不再截断为 6 人。TinyTroupe 必须对每个行动角色**单独**调用大模型生成，禁止把多人对话打包成一次 DeepSeek 请求；同轮已发言台词需注入后续角色并做防复述过滤。

返回字段：

- `workflow_id`、`trace_id`、`stage`、`next_stage`、`skill`。
- `status: succeeded|failed`。
- `result: object`。
- `transition_proposal: object|null`，仅为建议，不直接修改平台数据。
- `error: object|null`。

`role_simulation` 的 `result` 额外返回：

- `reply_turns`：逐角色的 `person_id`、平台角色 ID、姓名、公开台词和披露事实。
- `role_state_results`：逐角色的新四维状态、变化量和状态标签。
- `role_intents`：TinyTroupe 本轮实际结果回写，发言为 `answer`，未开口为 `silent`，仅供服务审计。
- `active_speakers`：本轮产出公开 `TALK` 的角色；可能为空。
- `simulation_meta`：世界 ID、轮次、观察者/行动者/发言者数量、调用数、重试数、重建标记，以及 `per_actor_isolated=true`。

合法沉默轮次返回成功状态、空 `reply_turns`、`routing_summary` 和可选 `addressing_warning`，平台不得将其转换为 AI 执行错误。四维状态只轻微影响角色台词风格，不得参与发言、事实披露、阶段推进或动作结果判断。

## POST /v1/case-imports/execute

流程图定义的主业务入口。请求使用 `workflow_id`、`case_id`、`source_text`；返回清洗结果、完整剧情、事实/人物、角色记忆、案件故事世界、训练剧本 `training_scripts`、场景蓝图和训练读取源。角色节点同时生成四维初始值。每个节点均写入 Agent 审计日志，平台只负责持久化与质量门禁。

事实账本生成必须基于完整剧情：按 `##` 章节（无章节则按自然段）分块，对每块抽取 1-N 条原子事实，再去重合并为总账本；另用剧情抽样生成全案 `summary`。不得再先把全文压成约 1/5 浓缩稿；不得把整段完整剧情当作单条事实。分块抽取失败时允许对本块做确定性句子回退。

`training_scripts` 为场景生成真源，平台必须按脚本决定场景数量（1-4）并透传以下字段到对应场景：

- `scene_pack`：`dispatch_brief`、`first_impression`、`training_entry_phase`、`student_role`
- `training_goal`、`expected_outcomes`、`plot_arc`
- `opening_lines[]`：开场预设发言，每项含 `speaker_name`、`content`；平台写入场景 `opening_config.preset_turns`，训练进场优先使用
- `stages[]`：`stage_name`、`stage_goal`、`learner_actions`、`role_pressure_points`、`expected_stage_effects`、`fact_ids`、`recommended_prompts`
- `role_training_functions[]`、`completion_criteria[]`、`failure_patterns[]`

场景考察配置的**唯一数据源**为剧本 `expected_outcomes`（本场景考察点，1-6 条可观察短句）。平台编辑与 AI 追加/刷新只读写该字段；粘贴导入、文件导入与分场景桶分派入口已下线。AI 调度：未满 6 条时追加并去重，已满时仅刷新替换内容、不再新增。评估与训练进度优先按 `expected_outcomes` 做关键词/语义命中；仅当旧案件无该字段时才回退到历史 `assessment_points`。

开场无可用 `opening_lines` / `preset_turns` 时，平台可调用 `role_simulation`（TinyTroupe）按剧情组织开场发言，不得回退固定句式。开场响应须返回 `recommended_questions` / `recommended_question_items` 供学员端进场展示。

训练回合建议提问由独立 `RecommendedQuestionsSkill` 按**当前剧本节点节奏**每轮新生成一批，不得原样复用上一批或已点选/已说过的问句。每项须含 `kind`：`hint`（快速发言提示）或 `plot_advance`（推进剧情）；单批建议 4 条（两类各约 2 条）。生成须消费 `plot_arc`、`current_stage_script`、`expected_outcomes`、阶段压力点与已用题历史。会话只读回放可展示最近一批，禁止在中后期回退到首阶段静态模板冒充新题。

`scene_blueprints` / `necessary_scenes` 由上述剧本字段派生，不再作为独立生成真源。剧本已生成但准入过滤过严时，允许以 `script_first_direct` / `script-first-direct` 模式直接使用剧本派生场景，避免空场景。

场景节点禁止使用默认场景、默认阶段、默认考核点或默认角色名单补齐结果。若连剧本也无法形成有效训练场景，允许返回空 `scene_blueprints`，并在 `case_import_quality.scene_admission` 中返回 `no_suitable_scene=true` 和拒绝原因。准入以 `expected_outcomes` 为考察可观察性主依据，不再强制要求 stages 内 `assessment_points`。

场景蓝图的 `first_impression` 必须为 80-160 字单段文本，只能包含民警进入场景时可直接观察的环境、人员位置、当前动作、伤情或危险物、声音和即时风险。不得包含接警/报警转述、人员清单、任务说明、人物内心、隐藏事实、案件结论或裁判结果。平台发布门禁对少于 80 字的内容只生成可确认警告，不直接阻断发布；超过 160 字或违反内容边界时阻断发布，并返回具体原因代码。

## 边界规则

- Agent 不接受 SQL、文件删除路径、账号权限或成绩写入指令。
- 平台不得向 Agent 发送数据库 URL、API Key 或认证凭据。
- `payload` 最大 2MB；角色对话只传当前必要事实和有限历史。
- 平台必须验证 `transition_proposal` 是否符合自身状态机。
