# ADR-002：TinyTroupe 只能通过适配层使用

- 状态：已接受
- 日期：2026-08-13

## 背景

TinyTroupe 为实验性项目，版本升级可能包含破坏性 API 变化。

## 决策

固定 Git 提交依赖，只有 `simulation/tinytroupe_adapter.py` 可以导入 TinyTroupe。业务 Skill 依赖项目自有协议与模型，不依赖第三方具体类型。

## 后果

- 升级影响集中在单一文件。
- TinyTroupe 未安装或初始化失败时，服务仍可启动并通过健康接口报告降级状态。
- 角色推演请求明确失败，不回退已删除的旧链路。
