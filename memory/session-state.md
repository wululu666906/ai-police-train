# 开发会话状态

## 当前目标

执行“260812平台大更新”：清理旧 AI 链路，修复失配接口，搭建独立 Agent + Skill + Tool + TinyTroupe 服务，并保持平台隔离。

## 已确认决策

- 旧链路完全删除，不复用、不回退。
- 当前未提交精简改动作为基线，修复因删除造成的接口断裂。
- 清理缓存、日志、临时产物和明确冗余源码；保留业务数据、视频、人脸资料、模型。
- 2026-08-13 已按用户确认执行 A+B 清理；随后核实并删除 C 档三项：`tools/ffmpeg`（改用本机 PATH ffmpeg）、`vendor/face_antispoof_onnx_src`（运行用 `data/face_models`）、根目录设计 docx。`.env` 中 `FFMPEG_BINARY=` 已清空。
- 只创建项目内 Skill，不安装到用户全局目录。
- 禁止提交代码、启动开发服务器和新增测试代码文件。

## 当前进度

- [x] 2026-08-28 视频实训本地卡顿：根因是 `FFMPEG_BINARY=` 空串导致 HLS `-c copy` 切段 WinError 87，前端回退整片 ~85MB/1440p；已修复空值回退 PATH，并重切库内 116 条均为 ready（不转码）。
- [x] 2026-08-28 开场气泡头像：SSE 带 avatar、发言名模糊匹配、sceneRoles 回填；建议提问改为民警可说出口语，过滤教练句（请立即确认…），兜底不再生成旁白指令。
- [x] 2026-08-28 恢复训练角色资源库头像：`serialize_scene_roles` 回填 `avatar_id`/`avatar_url`；启动幂等 `seed_avatars`；本地已种子化 20 条。
- [x] 2026-08-28 现网 `82.156.126.212:5175` 增量部署完成：平台 `15176` healthy；AI 工作流 `8020` 已起（`ai-police-workflow:runtime` 轻量 TinyTroupe+llama-index-openai，跳过 torch）；`AI_WORKFLOW_URL=http://ai_police_workflow:8020`；远端磁盘清理后可用约 8.4GB。
- [x] 2026-08-28 现网角色无法回复：轻量安装缺 `ipython`；`action_generator`→`experimentation`→`InPlaceExperimentRunner` 导入链触发；已 `pip install ipython` 并 commit runtime；对话 E2E 验证 2 角色正常回复。
- [x] 2026-08-28 人脸达上限自动结束评估失败：根因是 `_finalize_face_termination` 提前置 `evaluating` 且 `evaluate_session` 异常无兜底；已改为 pending 标记 + finish 统一收口（含 fallback/修复卡住会话）。
- [x] 2026-08-27 建议提问按剧本节奏每轮新生成：`kind=hint|plot_advance`；硬去重已用/已展示题；阶段推进切新剧本；禁止首阶段模板冒充中后期新题；前端分区「快速发言/推进剧情」。
- [x] 2026-08-27 修复训练进场人脸验证：忽略会话历史 verified 自动放行；挂载自动 `runVerify`；去掉可跳过退出；`StudentTraining` 按 session 重置并强制重建 Guard。
- [x] 2026-08-27 修复考察点评估全零：短关键词抽取、规则命中放宽；`EvaluationSkill` 增加 LLM `point_reviews` 语义补判并与规则取较高完成度合并。旧会话需强制重评后分数才更新。
- [x] 事实/角色账本默认收起；账本过滤法院审理/辩护片段；角色构建正向补齐四维与档案；训练线索回传原文。
- [x] 完成现状分析与技术决策。
- [x] 建立 Harness 地图、架构、契约与 ADR。
- [x] 完成旧链路清理和接口修复。
- [x] 完成独立 Agent 服务。
- [x] 完成平台接入。
- [x] 加固 Agent 阶段/Skill 白名单和状态迁移校验，补齐场景角色映射与评估考核点传递。
- [x] 启动 Docker Agent 服务并在本地虚拟环境安装 TinyTroupe 0.7.0。
- [x] 修复 Agent 的 DeepSeek 环境继承、空 Base URL 回退、案件字段归一化和 Skill 异常隔离。
- [x] 完成项目内 Skill。
- [x] 完成静态检查、Skill 校验和适用既有测试验证。
- [x] 按流程图启用 Case Import Harness 主业务通道并完成 Docker HTTP 实测。
- [x] 删除旧 `case_parse`、`persona_build`、`scene_build` Skill、调度与公开入口。
- [x] 接通训练读取源、场景蓝图直用和角色回复底线校验上下文。
- [x] 将 `ai_workflow_service` 默认模型切换为 `deepseek-v4-flash`，并加载服务本地 `.env` 中的 DeepSeek 密钥。
- [x] 将场景第一印象上下游契约统一为 80-160 字可观察单段文本，上游增加安全规范化，发布门禁将字数不足调整为可确认警告并分类返回其他违规原因。
- [x] 完成角色记忆隔离、角色初始四维、无模板场景准入、逐角色发言意图、累计训练进度和独立建议追问链路。
- [x] TinyWorld 只装载在场角色；在场角色在世界内自行行动，合法沉默不再作为 AI 错误。
- [x] 对话训练发言导演交由 TinyTroupe：最多 6 人行动，台词只取 `TALK`，契约版本 `2026-08-24`。
- [x] 删除旧追问提示词、`role_brains` 和预生成多人回复运行时结构，新增 ADR-003 固化边界。
- [x] 2026-08-26 酒馆式重建：ScenePack/RoleCard/Lorebook 契约与 ADR-004；CanonCompile 时点门禁；回合装配器；训练 payload 按场景切卡；超时时点审计；`POST /v1/case-canons/recompile` 与平台 `/{case_id}/recompile-canon`；契约版本 `2026-08-26`。
- [x] 2026-08-26 撤销酒馆式新增，契约回退 `2026-08-24`；修复 NO_PRESENT_PERSONAS；场景构建增加训练剧本（剧情走向/引导提问）；训练记忆仅取场景剧本；前端暂时隐藏事实账本与全案人物线。
- [x] 2026-08-26 修复对话 Unicode 乱码（`UXXXX`）；放宽角色名保存，避免导入角色静默丢弃；发布门禁默认不再校验场景关联事实数量，场景合同改为展示剧情走向。
- [x] 2026-08-26 剧本前置驱动场景：标准化开端/发展/收尾剧情链路；开场发言按剧本 opening_lines；引导提问按剧情节点动态生成并在开场展示。
- [x] 2026-08-26 修复剧本前置 `to_scene_candidates` 把 `FourDimensionalState` 原对象写入 `scene_roles`，导致案件导入修复阶段 `json.dumps` 失败（仅序列化为 dict，未改训练/对话逻辑）。
- [x] 2026-08-26 场景搭建失败：剧本 assessment_points 为字符串被准入丢弃；规范化为可观察 dict，并在无蓝图时从 training_scripts 重建场景。
- [x] 2026-08-26 **已回退**剧情/剧本体系完善相关改动至 HEAD（`64c08a7`）：删除 `scene_script_skill`，恢复 harness 场景蓝图直出、追问/开场/训练记忆/场景合同/前端解析页到完善前；保留 Unicode 文本修复与场景角色 `present=True` 兜底。当前对话/解析失败另含 DeepSeek API **402 余额不足**，需充值后才能恢复 LLM。
- [x] 2026-08-27 修复角色脏名入库、事实账本通读全文分点、开场白按剧本/TinyTroupe 组织、进场展示建议提问；契约登记 `opening_lines` 与开场 `input_kind=opening`。
- [x] 2026-08-27 修复解析角色截断（首某远→首某）、剧本阶段字段被 normalize_stage 剥空、二次编辑未回填 training_scripts、PUT 保存未走质量确认门禁导致 422。
- [x] 2026-08-27 修复案件解析反复失败：FactAnalysis 的 relationships/timeline 对 LLM 字符串列表做规范化，避免 CaseWorld 校验崩溃。
- [x] 2026-08-27 放开场景角色人数上限（默认 24/硬顶 32）；TinyTroupe 逐角色单独调模型并防复述；事实账本改为先浓缩约 1/5 再分点。
- [x] 2026-08-27 考察点模块改为「本场景预期业务效果」：剧本 `expected_outcomes` 单一真源；AI 追加/刷新+去重；下线粘贴/上传/分派；评估优先命中 expected_outcomes；仅新整理案件生效。
- [x] 2026-08-27 完整剧情防空降级：DeepSeek 超时默认 900s；剧情生成流式累计，超时尽量返回已生成正文；空结果也进修补；有章节草稿可 `partial_draft_kept`，避免直接贴 OCR 原文。
- [x] 2026-08-27 界面「效果」统一改称「考察点」（字段仍为 `expected_outcomes`）。
- [x] 2026-08-27 事实账本改为按完整剧情 `##`/段落分块抽取原子事实并去重合并；取消整篇 1/5 浓缩；契约已同步。

## 验证备注

- AI 工作流服务端口已统一为 `127.0.0.1:8020`，TinyTroupe 与 DeepSeek 配置由开发脚本或 Compose 加载。
- DeepSeek 完整链路请求成功；端到端耗时 53.39 秒，事实、人物、角色记忆、场景蓝图和四类训练读取源断言全部通过。
- 平台案件解析和场景生成主入口实调通过，统一标记为 `agent-workflow-v2-flowchart`。
- 旧案件 AI Skill 请求实测返回 HTTP 422，不存在旧链路回退入口。
- 节点审计覆盖导入、清洗、剧情、事实、人物、记忆、故事世界和场景蓝图，可按 Workflow ID 定位。
- 前端 `vue-tsc --noEmit` 已通过；当前 Node.js 版本为 22.22.0。
- 宿主机 `127.0.0.1:8010` 被其他项目占用；本地 AgentWorkflowClient 改为访问 `http://127.0.0.1:8020`。
- `.pytest_cache`、`.pytest-run-tmp`、`.pytest-tmp` 仍受 Windows ACL 限制无法删除（空目录）。
- 视频实训 ffmpeg 已切到本机 WinGet PATH；人脸模型仍在 `data/face_models`。
- 第一印象真实任务数据复验通过：两条短文本仅生成 `FIRST_IMPRESSION_TOO_SHORT` 警告，无阻断项且 `publishable=true`；上游安全文本均落在 80-160 字。
- 2026-08-15 验证：129 个业务 Python 文件静态编译通过，Harness 审计通过，前端 `vue-tsc --noEmit` 通过，角色/场景/记忆相关既有测试 13 项通过，新增能力使用命令行领域冒烟断言通过。
- 2026-08-27 验证：改动文件 `py_compile` 通过，`scripts/audit_harness.py` 通过，前端 `vue-tsc --noEmit` 通过。脏名样例「未明确/证言及辨认/报警人」保存门禁拒绝，「首某/彭某乙」保留。本地 5556/8000/8020/6670 均在监听。旧案件需重新整理才会刷新人物与事实。
- 2026-08-27 人数/隔离/事实浓缩：`py_compile` + `audit_harness` 通过；需重启 `ai_workflow_service` 使配置与 skill 生效。旧案件仍需重新整理才刷新事实账本。
- 2026-08-27 预期业务效果改造：`py_compile` + `audit_harness` + `vue-tsc` 通过。旧案件不自动迁移考察点；需重新整理后才有剧本 `expected_outcomes`。
- 2026-08-27 超时/流式部分返回：`py_compile` + `audit_harness` 通过；8020 已起，日志 `timeout=900`；`CASE_IMPORT`/`AI_WORKFLOW`/`DEEPSEEK` 默认与 example/compose 均为 900。长 OCR 案需重新整理验证。
- 2026-08-27 事实分块抽取：分块单测通过（`##` 分章保留、超 12 块均摊合并）；`py_compile` + `audit_harness` 通过。旧案件需重新整理才刷新账本。

## 下次入口

先读 `CLAUDE.md`、本文件和 `docs/260812平台大更新开发计划.md`。
