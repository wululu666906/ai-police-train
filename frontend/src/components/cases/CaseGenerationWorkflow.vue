<template>
  <section class="case-workflow">
    <header class="case-workflow__header">
      <div>
        <div class="case-workflow__eyebrow">标准化生成链路</div>
        <h3 class="case-workflow__title">场景生成完整工作流</h3>
      </div>
      <span class="case-workflow__badge">现场第一印象由剧本生成节点负责</span>
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
    key: 'parse',
    name: '文档解析',
    owner: '责任：案件解析节点',
    output: '产物：结构化案件与事实摘要',
    description: '从原文中提取标题、类型、案情背景、事实线索和复核提醒，只保留可追溯信息。',
  },
  {
    key: 'world',
    name: '案件故事世界',
    owner: '责任：故事世界节点',
    output: '产物：事实卡、人物卡、时间线',
    description: '按原文证据组织完整剧情、事实卡和人物关系，作为后续场景生成的唯一事实边界。',
  },
  {
    key: 'roles',
    name: '人物来源记忆',
    owner: '责任：角色核对节点',
    output: '产物：人物线与回答边界',
    description: '把人物可说、不可说、待核实的信息分开，防止角色串台或越权透露全案事实。',
  },
  {
    key: 'blueprint',
    name: '场景蓝图',
    owner: '责任：蓝图规划节点',
    output: '产物：场景目标、角色、事实引用',
    description: '按训练价值拆分场景，确定可交流角色、场景事实范围和可观察完成条件。',
  },
  {
    key: 'script',
    name: '场景剧本',
    owner: '责任：剧本生成节点',
    output: '产物：接警简报、现场第一印象、阶段脚本',
    description: '生成场景文案。其中现场第一印象只写入场第一眼可观察内容，不承担任务说明或剧情摘要。',
  },
  {
    key: 'validate',
    name: '角色与事实校验',
    owner: '责任：后端校验节点',
    output: '产物：可发布场景草案',
    description: '校验角色是否属于蓝图、事实引用是否越界、现场第一印象是否混入冗余信息。',
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
  gap: 16px;
  margin-bottom: 14px;
}

.case-workflow__eyebrow {
  color: #2563eb;
  font-size: 11px;
  font-weight: 900;
  letter-spacing: 0.12em;
}

.case-workflow__title {
  margin: 4px 0 0;
  color: #0f172a;
  font-size: 16px;
  font-weight: 900;
  line-height: 1.35;
}

.case-workflow__badge {
  flex-shrink: 0;
  border: 1px solid #bfdbfe;
  border-radius: 999px;
  background: #eff6ff;
  color: #1d4ed8;
  padding: 6px 10px;
  font-size: 12px;
  font-weight: 800;
}

.case-workflow__rail {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 10px;
}

.case-workflow__step {
  display: flex;
  gap: 10px;
  min-width: 0;
  border: 1px solid #e0edff;
  border-radius: 14px;
  background: #fff;
  padding: 12px;
}

.case-workflow__index {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  border-radius: 999px;
  background: #1d3557;
  color: #fff;
  font-size: 12px;
  font-weight: 900;
  flex-shrink: 0;
}

.case-workflow__content {
  min-width: 0;
}

.case-workflow__name {
  color: #172033;
  font-size: 13px;
  font-weight: 900;
}

.case-workflow__desc {
  margin: 6px 0 0;
  color: #475569;
  font-size: 12px;
  line-height: 1.65;
}

.case-workflow__meta {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-top: 8px;
}

.case-workflow__meta span {
  border-radius: 999px;
  background: #f1f5f9;
  color: #64748b;
  padding: 3px 7px;
  font-size: 11px;
  font-weight: 700;
}

@media (max-width: 1180px) {
  .case-workflow__rail {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 760px) {
  .case-workflow__header {
    flex-direction: column;
  }

  .case-workflow__badge {
    border-radius: 10px;
  }

  .case-workflow__rail {
    grid-template-columns: 1fr;
  }
}
</style>
