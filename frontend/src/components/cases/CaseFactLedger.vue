<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{ caseData: Record<string, any> | null | undefined }>()

const structured = computed(() => {
  const source = props.caseData || {}
  if (source.structured_data && typeof source.structured_data === 'string') {
    try { return { ...source, ...JSON.parse(source.structured_data) } } catch { return source }
  }
  return source.structured_data && typeof source.structured_data === 'object'
    ? { ...source, ...source.structured_data }
    : source
})

const facts = computed(() => {
  const source = structured.value
  const world = source.story_world && typeof source.story_world === 'object' ? source.story_world : {}
  const rows = world.fact_cards || world.facts || source.facts || source.fact_cards || []
  return Array.isArray(rows) ? rows : []
})

const factId = (fact: any, index: number) => fact?.id || fact?.fact_id || fact?.claim_id || `F${String(index + 1).padStart(3, '0')}`
const sourceLabel = (fact: any) => {
  const refs = Array.isArray(fact?.source_refs) ? fact.source_refs : []
  const first = refs[0] || {}
  if (fact?.source) return fact.source
  if (Number.isFinite(first.start) && Number.isFinite(first.end)) return `完整剧情 ${first.start}-${first.end}`
  return refs.length ? '案件原文' : '待核对'
}
</script>

<template>
  <section class="fact-ledger">
    <header class="fact-ledger__head">
      <div>
        <div class="fact-ledger__eyebrow">事实抽取</div>
        <h3>案件事实账本</h3>
      </div>
      <span>{{ facts.length }} 条</span>
    </header>
    <div v-if="facts.length" class="fact-ledger__list">
      <article v-for="(fact, index) in facts" :key="factId(fact, index)" class="fact-ledger__row">
        <div class="fact-ledger__id">{{ factId(fact, index) }}</div>
        <div class="fact-ledger__body">
          <div class="fact-ledger__meta">
            <span>{{ fact.fact_type || '事实' }}</span>
            <span>{{ fact.status || '已抽取' }}</span>
            <span>{{ sourceLabel(fact) }}</span>
          </div>
          <p>{{ fact.content || fact.statement || fact.fact }}</p>
          <div v-if="(fact.known_by || []).length" class="fact-ledger__known">知情角色：{{ fact.known_by.join('、') }}</div>
        </div>
      </article>
    </div>
    <div v-else class="fact-ledger__empty">当前没有可用事实，案件不能进入场景发布。</div>
  </section>
</template>

<style scoped>
.fact-ledger { padding: 18px 0; border-top: 1px solid #e2e8f0; border-bottom: 1px solid #e2e8f0; }
.fact-ledger__head { display: flex; align-items: center; justify-content: space-between; gap: 16px; margin-bottom: 12px; }
.fact-ledger__head h3 { margin: 3px 0 0; color: #0f172a; font-size: 17px; letter-spacing: 0; }
.fact-ledger__head > span { color: #475569; font-size: 13px; }
.fact-ledger__eyebrow { color: #2563eb; font-size: 12px; font-weight: 700; }
.fact-ledger__list { display: grid; gap: 0; border-top: 1px solid #e2e8f0; }
.fact-ledger__row { display: grid; grid-template-columns: 64px minmax(0, 1fr); gap: 12px; padding: 13px 0; border-bottom: 1px solid #e2e8f0; }
.fact-ledger__id { color: #1d4ed8; font-size: 13px; font-weight: 800; }
.fact-ledger__body p { margin: 6px 0; color: #1e293b; font-size: 14px; line-height: 1.65; overflow-wrap: anywhere; }
.fact-ledger__meta { display: flex; flex-wrap: wrap; gap: 10px; color: #64748b; font-size: 12px; }
.fact-ledger__known { color: #64748b; font-size: 12px; }
.fact-ledger__empty { padding: 18px 0; color: #b45309; font-size: 14px; }
@media (max-width: 640px) { .fact-ledger__row { grid-template-columns: 48px minmax(0, 1fr); } }
</style>
