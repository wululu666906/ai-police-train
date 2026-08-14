<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{ scene: Record<string, any>; caseData?: Record<string, any> | null }>()

const factMap = computed(() => {
  const source = props.caseData || {}
  let structured: any = source
  if (typeof source.structured_data === 'string') {
    try { structured = { ...source, ...JSON.parse(source.structured_data) } } catch { structured = source }
  } else if (source.structured_data && typeof source.structured_data === 'object') {
    structured = { ...source, ...source.structured_data }
  }
  const world = structured.story_world || {}
  const facts = world.fact_cards || world.facts || structured.facts || structured.fact_cards || []
  return new Map((Array.isArray(facts) ? facts : []).map((fact: any) => [String(fact.id || fact.fact_id || fact.claim_id), fact]))
})

const outcomes = computed(() => Array.isArray(props.scene.expected_outcomes) ? props.scene.expected_outcomes.filter(Boolean) : [])
const factIds = computed(() => Array.isArray(props.scene.fact_ids) ? props.scene.fact_ids.filter(Boolean) : [])
const stages = computed(() => Array.isArray(props.scene.stages) ? props.scene.stages.filter((item: any) => item && typeof item === 'object') : [])
const factLabel = (id: string) => String((factMap.value.get(String(id)) as any)?.content || id)
</script>

<template>
  <section class="training-contract">
    <div class="training-contract__block">
      <div class="training-contract__label">训练目标</div>
      <p>{{ scene.training_goal || '待补充民警可执行的训练目标' }}</p>
    </div>
    <div class="training-contract__block">
      <div class="training-contract__label">预期达到效果</div>
      <ol v-if="outcomes.length">
        <li v-for="item in outcomes" :key="item">{{ item }}</li>
      </ol>
      <p v-else class="training-contract__missing">待补充可观察、可判断的训练效果</p>
    </div>
    <div class="training-contract__block">
      <div class="training-contract__label">绑定事实</div>
      <div v-if="factIds.length" class="training-contract__facts">
        <span v-for="id in factIds" :key="id" :title="factLabel(id)">{{ id }}</span>
      </div>
      <p v-else class="training-contract__missing">未绑定案件事实</p>
    </div>
    <div v-if="stages.length" class="training-contract__block">
      <div class="training-contract__label">训练阶段</div>
      <div class="training-contract__stages">
        <div v-for="(stage, index) in stages" :key="`${stage.stage_name}-${index}`">
          <strong>{{ stage.stage_name || `阶段 ${index + 1}` }}</strong>
          <span>{{ stage.stage_goal || '待补充阶段目标' }}</span>
        </div>
      </div>
    </div>
  </section>
</template>

<style scoped>
.training-contract { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 16px 24px; margin-top: 16px; padding-top: 16px; border-top: 1px solid #e2e8f0; }
.training-contract__block { min-width: 0; }
.training-contract__label { margin-bottom: 6px; color: #475569; font-size: 12px; font-weight: 800; }
.training-contract p, .training-contract ol { margin: 0; color: #1e293b; font-size: 13px; line-height: 1.65; }
.training-contract ol { padding-left: 20px; }
.training-contract__facts { display: flex; flex-wrap: wrap; gap: 6px; }
.training-contract__facts span { padding: 3px 7px; border: 1px solid #bfdbfe; color: #1d4ed8; background: #eff6ff; border-radius: 4px; font-size: 12px; font-weight: 700; }
.training-contract .training-contract__missing { color: #b45309; }
.training-contract__stages { display: grid; gap: 7px; }
.training-contract__stages div { display: grid; grid-template-columns: minmax(80px, auto) minmax(0, 1fr); gap: 8px; font-size: 12px; }
.training-contract__stages strong { color: #334155; }
.training-contract__stages span { color: #64748b; overflow-wrap: anywhere; }
@media (max-width: 720px) { .training-contract { grid-template-columns: 1fr; } }
</style>
