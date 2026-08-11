<script setup lang="ts">
import { computed, ref } from 'vue'
import { purifyStoryMaterial, splitStorySections } from '../utils/caseAnalysis'

const props = defineProps<{ caseData?: any }>()
const activeVersion = ref<'narrative' | 'event_ledger'>('narrative')

const narrative = computed(() => {
  const value = props.caseData || {}
  return purifyStoryMaterial(
    value.story_documents?.narrative?.content
      || value.complete_story
      || value.story_world?.complete_story
      || value.full_narrative
      || value.narrative_document?.content
      || '',
  )
})

const eventEntries = computed<any[]>(() => {
  const value = props.caseData || {}
  const entries = value.story_documents?.event_ledger?.entries
    || value.story_world?.event_entries
    || value.case_reconstruction?.event_ledger
    || []
  return Array.isArray(entries)
    ? entries.filter(Boolean).map((event: any) => ({
        ...event,
        content: purifyStoryMaterial(event.content || event.statement || event.description || ''),
        statement: purifyStoryMaterial(event.statement || ''),
        description: purifyStoryMaterial(event.description || ''),
      }))
    : []
})

const storySections = computed(() => splitStorySections(narrative.value))

const audit = computed(() => props.caseData?.story_material_audit || null)
</script>

<template>
  <section class="case-story-viewer">
    <div v-if="audit" class="case-story-viewer__audit">
      <strong>素材规整</strong>
      <span>原文 {{ audit.original_chars || 0 }} 字 → 核心素材 {{ audit.training_chars || 0 }} 字</span>
      <span v-if="audit.large_document || audit.possible_truncation" class="case-story-viewer__audit-warn">
        原文体量较大，已剔除冗余文书套话；完整正文请用 Word 阅读页核验是否遗漏后半段事实。
      </span>
    </div>

    <div class="case-story-viewer__tabs" role="tablist" aria-label="完整剧情版本">
      <button
        type="button"
        role="tab"
        :aria-selected="activeVersion === 'narrative'"
        :class="{ 'is-active': activeVersion === 'narrative' }"
        @click="activeVersion = 'narrative'"
      >
        章节卡片
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

    <div v-if="activeVersion === 'narrative'" class="case-story-card-list">
      <details
        v-for="(section, index) in storySections"
        :key="`section-${index}-${section.title}`"
        class="case-story-card"
        :open="true"
      >
        <summary>
          <span :class="section.level === 'title' ? 'case-story-card__title' : 'case-story-card__heading'">
            {{ section.title }}
          </span>
          <small>{{ section.charCount }} 字</small>
        </summary>
        <div class="case-story-card__body">
          <p v-for="(paragraph, paragraphIndex) in section.paragraphs" :key="`p-${index}-${paragraphIndex}`">
            {{ paragraph }}
          </p>
        </div>
      </details>
      <div v-if="!storySections.length" class="case-story-empty">暂无案件剧情卡片</div>
    </div>

    <div v-else class="case-story-card-list">
      <details
        v-for="(event, index) in eventEntries"
        :key="event.id || event.fact_id || `event-${index}`"
        class="case-story-card"
        :open="true"
      >
        <summary>
          <span class="case-story-card__heading">{{ event.time || event.time_hint || `事件 ${index + 1}` }}</span>
          <small>{{ event.place || event.place_hint || '地点未明确' }}</small>
        </summary>
        <div class="case-story-card__body">
          <p>{{ event.content || event.statement || event.description || '暂无事件内容' }}</p>
          <div v-if="Array.isArray(event.present_roles) && event.present_roles.length" class="case-story-card__roles">
            在场人员：{{ event.present_roles.join('、') }}
          </div>
        </div>
      </details>
      <div v-if="!eventEntries.length" class="case-story-empty">暂无事件明细卡片</div>
    </div>
  </section>
</template>

<style scoped>
.case-story-viewer { min-width: 0; }
.case-story-viewer__audit {
  display: flex;
  flex-wrap: wrap;
  gap: 8px 14px;
  margin: 0 0 12px;
  padding: 10px 12px;
  border: 1px solid #dbe3ee;
  border-radius: 8px;
  background: #f8fafc;
  color: #64748b;
  font-size: 12px;
}
.case-story-viewer__audit strong { color: #172033; font-weight: 700; }
.case-story-viewer__audit-warn { flex: 1 1 100%; color: #b45309; }
.case-story-viewer__tabs {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 2px;
  width: min(100%, 360px);
  margin: 0 0 14px;
  padding: 3px;
  border: 1px solid #d1d1d6;
  border-radius: 8px;
  background: #f2f2f7;
}
.case-story-viewer__tabs button {
  min-height: 36px;
  padding: 0 16px;
  border: 0;
  border-radius: 6px;
  background: transparent;
  color: #636366;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
}
.case-story-viewer__tabs button.is-active {
  background: #fff;
  color: #1c1c1e;
  box-shadow: 0 1px 3px rgba(0, 0, 0, .12);
}
.case-story-card-list { display: grid; gap: 10px; }
.case-story-card {
  border: 1px solid #dbe3ee;
  border-radius: 8px;
  background: #fff;
  overflow: hidden;
}
.case-story-card summary {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  min-height: 48px;
  padding: 10px 14px;
  color: #172033;
  cursor: pointer;
  list-style: none;
}
.case-story-card summary::-webkit-details-marker { display: none; }
.case-story-card__title {
  font-size: 17px;
  font-weight: 800;
  line-height: 1.4;
}
.case-story-card__heading {
  font-size: 15px;
  font-weight: 700;
  line-height: 1.45;
}
.case-story-card summary small {
  flex: none;
  color: #8290a6;
  font-size: 12px;
  font-weight: 500;
}
.case-story-card__body {
  padding: 0 14px 14px;
  color: #334155;
  line-height: 1.9;
}
.case-story-card__body p {
  margin: 0 0 10px;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
  text-align: justify;
  text-indent: 2em;
}
.case-story-card__body p:last-child { margin-bottom: 0; }
.case-story-card__roles {
  margin-top: 8px;
  color: #64748b;
  font-size: 12px;
  text-indent: 0;
}
.case-story-empty {
  border: 1px dashed #cbd5e1;
  border-radius: 8px;
  padding: 22px;
  color: #94a3b8;
  text-align: center;
}
</style>
