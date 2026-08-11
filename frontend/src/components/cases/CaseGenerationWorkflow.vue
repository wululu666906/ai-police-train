<template>
  <section class="case-workflow">
    <header class="case-workflow__header">
      <div>
        <div class="case-workflow__eyebrow">标准化生成链路</div>
        <h3 class="case-workflow__title">案件导入到训练回复</h3>
      </div>
      <span class="case-workflow__badge">按新流程图编排</span>
    </header>

    <div class="case-workflow__rail">
      <article v-for="(step, index) in workflowSteps" :key="step.key" class="case-workflow__step">
        <span class="case-workflow__index">{{ String(index + 1).padStart(2, '0') }}</span>
        <div class="case-workflow__content">
          <div class="case-workflow__name">{{ step.name }}</div>
          <p class="case-workflow__desc">{{ step.description }}</p>
          <div class="case-workflow__meta">
            <span>{{ step.owner }}</span>
            <span>{{ step.output }}</span>
          </div>
        </div>
      </article>
    </div>
  </section>
</template>

<script setup lang="ts">
const workflowSteps = [
  {
    key: 'import',
    name: '导入案件原文',
    owner: '责任：管理员上传',
    output: '产物：原始材料',
    description: '上传 Word/PDF/文本等材料，作为全流程唯一输入源。',
  },
  {
    key: 'clean',
    name: '文本清洗',
    owner: '责任：文本清洗节点',
    output: '产物：可训练正文',
    description: '去除非案件信息、文书噪声与识别标记，保留可追溯正文。',
  },
  {
    key: 'story',
    name: '完整案件剧情',
    owner: '责任：剧情生成节点',
    output: '产物：完整剧情 + 基础元数据',
    description: '生成可阅读的完整案件剧情，并附带案件名称、类型与背景摘要。',
  },
  {
    key: 'facts',
    name: '事实与角色记忆',
    owner: '责任：事实解析节点',
    output: '产物：事实卡、人物、角色记忆',
    description: '从完整剧情提取事实、识别人物并生成每人可说/不可说的来源记忆。',
  },
  {
    key: 'world',
    name: '案件故事世界',
    owner: '责任：故事世界节点',
    output: '产物：剧情 + 事实 + 角色汇总',
    description: '把完整剧情、事实与角色记忆汇总为训练后台的统一世界载体。',
  },
  {
    key: 'blueprint',
    name: '场景蓝图',
    owner: '责任：蓝图规划节点',
    output: '产物：训练目标、角色、简报、第一印象',
    description: '按每个场景的训练目标、角色、接警简报与现场第一印象生成蓝图。',
  },
  {
    key: 'reply',
    name: '角色回复',
    owner: '责任：训练对话角色',
    output: '产物：开场与对话台词',
    description: '角色读取记忆、角色信息、事实与上下文后，由训练对话 AI 生成回复。',
  },
]
</script>

<style scoped>
.case-workflow {
  border: 1px solid #dbeafe;
  border-radius: 18px;
  background: #f8fbff;
  padding: 16px;
}

.case-workflow__header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 14px;
}

.case-workflow__eyebrow {
  font-size: 12px;
  color: #2563eb;
  font-weight: 600;
}

.case-workflow__title {
  margin: 4px 0 0;
  font-size: 18px;
  color: #0f172a;
}

.case-workflow__badge {
  font-size: 12px;
  color: #475569;
  background: #e2e8f0;
  border-radius: 999px;
  padding: 4px 10px;
  white-space: nowrap;
}

.case-workflow__rail {
  display: grid;
  gap: 10px;
}

.case-workflow__step {
  display: grid;
  grid-template-columns: 40px 1fr;
  gap: 10px;
  padding: 12px;
  border-radius: 14px;
  background: #fff;
  border: 1px solid #e2e8f0;
}

.case-workflow__index {
  width: 32px;
  height: 32px;
  border-radius: 10px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  background: #dbeafe;
  color: #1d4ed8;
  font-size: 12px;
  font-weight: 700;
}

.case-workflow__name {
  font-size: 15px;
  font-weight: 600;
  color: #0f172a;
}

.case-workflow__desc {
  margin: 6px 0 8px;
  font-size: 13px;
  line-height: 1.5;
  color: #475569;
}

.case-workflow__meta {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  font-size: 12px;
  color: #64748b;
}

.case-workflow__meta span {
  background: #f1f5f9;
  border-radius: 999px;
  padding: 2px 8px;
}
</style>
