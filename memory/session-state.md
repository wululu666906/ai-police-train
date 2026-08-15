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
- [x] TinyWorld 只装载在场角色，只有意图仲裁通过的角色行动；合法沉默不再作为 AI 错误。
- [x] 删除旧追问提示词、`role_brains` 和预生成多人回复运行时结构，新增 ADR-003 固化边界。

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
- 扩展既有测试批次另有 3 项旧 `story_world` 键缺失失败，与本轮新 Agent 链路无关；1 项因当前 Python 环境缺少 `openpyxl` 未能启动。

## 下次入口

先读 `CLAUDE.md`、本文件和 `docs/260812平台大更新开发计划.md`。
