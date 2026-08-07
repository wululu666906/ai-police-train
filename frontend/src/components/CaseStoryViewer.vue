<script setup lang="ts">
import { computed, ref } from 'vue'
import WordDocumentView from './WordDocumentView.vue'

const props = defineProps<{ caseData?: any }>()
const activeVersion = ref<'narrative' | 'event_ledger'>('narrative')

const narrative = computed(() => {
  const value = props.caseData || {}
  return value.story_documents?.narrative?.content
    || value.complete_story
    || value.story_world?.complete_story
    || value.full_narrative
    || value.narrative_document?.content
    || ''
})

const eventDocument = computed(() => {
  const value = props.caseData || {}
  const saved = value.story_documents?.event_ledger?.content || value.event_story
  if (saved) return saved
  const events = value.story_documents?.event_ledger?.entries
    || value.story_world?.event_entries
    || value.case_reconstruction?.event_ledger
    || []
  if (!Array.isArray(events) || !events.length) return ''
  const lines = events.map((event: any, index: number) => {
    const time = event.time || event.time_hint || '未明确'
    const place = event.place || event.place_hint || '未明确'
    const roles = Array.isArray(event.participants) && event.participants.length ? event.participants.join('、') : '相关人员'
    const content = event.content || event.statement || ''
    return `${index + 1}. 【${time}｜${place}｜${roles}】${content}`
  })
  return ['# 案件完整剧情事件明细', '', ...lines].join('\n\n')
})
</script>

<template>
  <section class="case-story-viewer">
    <div class="case-story-viewer__tabs" role="tablist" aria-label="完整剧情版本">
      <button
        type="button"
        role="tab"
        :aria-selected="activeVersion === 'narrative'"
        :class="{ 'is-active': activeVersion === 'narrative' }"
        @click="activeVersion = 'narrative'"
      >
        故事全文
      </button>
      <button
        type="button"
        role="tab"
        :aria-selected="activeVersion === 'event_ledger'"
        :class="{ 'is-active': activeVersion === 'event_ledger' }"
        @click="activeVersion = 'event_ledger'"
      >
        事件明细
      </button>
    </div>
    <WordDocumentView
      v-if="activeVersion === 'narrative'"
      :content="narrative"
      title="案件完整故事剧情"
      mode="narrative"
    />
    <WordDocumentView
      v-else
      :content="eventDocument"
      title="案件完整剧情事件明细"
      mode="event-ledger"
    />
  </section>
</template>

<style scoped>
.case-story-viewer { min-width: 0; }
.case-story-viewer__tabs { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 2px; width: min(100%, 360px); margin: 0 0 14px; padding: 3px; border: 1px solid #d1d1d6; border-radius: 8px; background: #f2f2f7; }
.case-story-viewer__tabs button { min-height: 36px; padding: 0 16px; border: 0; border-radius: 6px; background: transparent; color: #636366; font-size: 13px; font-weight: 600; cursor: pointer; }
.case-story-viewer__tabs button.is-active { background: #fff; color: #1c1c1e; box-shadow: 0 1px 3px rgba(0, 0, 0, .12); }
</style>
