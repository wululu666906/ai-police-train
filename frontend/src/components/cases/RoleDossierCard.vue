<script setup lang="ts">
import { computed } from 'vue'

const props = withDefaults(defineProps<{ person: any; index?: number; expanded?: boolean }>(), {
  index: 0,
  expanded: false,
})
defineEmits<{ remove: []; toggle: [] }>()

const memories = computed(() => Array.isArray(props.person?.role_memories) ? props.person.role_memories : [])
const soul = computed(() => props.person?.soul_profile && typeof props.person.soul_profile === 'object' ? props.person.soul_profile : {})
const list = (value: unknown) => Array.isArray(value) ? value.filter(Boolean) : value ? [value] : []
</script>

<template>
  <article class="role-card" :class="{ 'role-card--expanded': expanded }">
    <header class="role-card__header">
      <button type="button" class="role-card__toggle" :aria-expanded="expanded" @click="$emit('toggle')">
        <span class="role-card__number">人物 {{ Number(index) + 1 }}</span>
        <span class="role-card__identity">
          <strong>{{ person?.name || '未命名角色' }}</strong>
          <small>{{ person?.role_type || person?.role || '相关人员' }}</small>
        </span>
        <span class="role-card__count">{{ memories.length }} 条记忆</span>
        <van-icon :name="expanded ? 'arrow-up' : 'arrow-down'" aria-hidden="true" />
      </button>
    </header>

    <div class="role-card__summary">
      <span>{{ person?.status || '正常' }}</span>
      <span>{{ person?.current_goal || soul.primary_need || '画像未生成' }}</span>
      <span>{{ soul.coping_style || person?.interaction_style || '画像未生成' }}</span>
    </div>

    <div v-if="expanded" class="role-card__body">
      <section>
        <h3>身份与当前诉求</h3>
        <p>{{ person?.identity || person?.role_basis || person?.role || '原文未提供更多身份信息。' }}</p>
        <p v-if="person?.current_goal || soul.primary_need"><strong>当前诉求：</strong>{{ person?.current_goal || soul.primary_need }}</p>
      </section>

      <section>
        <h3>本人记忆时间线</h3>
        <ol v-if="memories.length" class="role-card__timeline">
          <li v-for="(memory, memoryIndex) in memories" :key="memory.memory_id || memoryIndex">
            <span>{{ memory.time_hint || `记忆 ${Number(memoryIndex) + 1}` }}</span>
            <p>{{ memory.statement || memory.content }}</p>
            <small v-if="memory.place_hint">地点：{{ memory.place_hint }}</small>
          </li>
        </ol>
        <p v-else class="role-card__muted">未从案件来源中提取到该人物的有效陈述或亲历信息。</p>
      </section>

      <section>
        <h3>回答边界</h3>
        <p v-for="item in list(person?.response_constraints)" :key="String(item)">• {{ item }}</p>
        <p v-for="item in list(person?.unresolved_claims)" :key="String(item)" class="role-card__muted">
          待核实：{{ typeof item === 'string' ? item : item?.question }}
        </p>
      </section>

      <section>
        <h3>人物心理与行为画像</h3>
        <div class="role-card__metrics">
          <span>警方信任 {{ soul.authority_trust ?? person?.init_trust ?? '-' }}</span>
          <span>配合基线 {{ soul.cooperation_baseline ?? '-' }}</span>
          <span>情绪基线 {{ soul.arousal_baseline ?? person?.init_emotion ?? '-' }}</span>
          <span>自我控制 {{ soul.self_control ?? '-' }}</span>
        </div>
        <p>{{ soul.coping_style || person?.interaction_style || '人物画像尚未生成。' }}</p>
        <p v-if="soul.speech_tendency"><strong>表达倾向：</strong>{{ soul.speech_tendency }}</p>
      </section>

      <details class="role-card__editor">
        <summary>编辑人物档案</summary>
        <slot />
      </details>

      <button type="button" class="role-card__remove" @click="$emit('remove')">删除人物</button>
    </div>
  </article>
</template>

<style scoped>
.role-card { min-width: 0; border: 1px solid #d1d1d6; border-radius: 8px; background: #fff; color: #1c1c1e; overflow: hidden; }
.role-card__header { border-bottom: 1px solid transparent; }
.role-card--expanded .role-card__header { border-bottom-color: #e5e5ea; }
.role-card__toggle { display: grid; grid-template-columns: auto minmax(0, 1fr) auto 20px; align-items: center; gap: 12px; width: 100%; min-height: 72px; padding: 12px 16px; border: 0; background: transparent; color: inherit; text-align: left; cursor: pointer; }
.role-card__number { color: #8e8e93; font-size: 12px; }
.role-card__identity { display: grid; min-width: 0; gap: 3px; }
.role-card__identity strong { overflow-wrap: anywhere; font-size: 17px; letter-spacing: 0; }
.role-card__identity small, .role-card__count { color: #636366; font-size: 12px; }
.role-card__count { white-space: nowrap; }
.role-card__summary { display: flex; flex-wrap: wrap; gap: 8px 16px; padding: 0 16px 14px; color: #636366; font-size: 13px; }
.role-card__summary span { min-width: 0; overflow-wrap: anywhere; }
.role-card__body { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); column-gap: 28px; padding: 0 16px 18px; }
.role-card__body section { padding: 18px 0 0; border-top: 1px solid #e5e5ea; }
.role-card__body section:nth-child(-n + 2) { border-top: 0; }
.role-card h3 { margin: 0 0 8px; font-size: 15px; letter-spacing: 0; }
.role-card p { margin: 6px 0; line-height: 1.75; overflow-wrap: anywhere; }
.role-card__timeline { margin: 0; padding-left: 22px; }
.role-card__timeline li { padding: 0 0 12px 6px; }
.role-card__timeline span, .role-card__timeline small, .role-card__muted { color: #8e8e93; font-size: 12px; }
.role-card__metrics { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 8px 12px; color: #636366; font-size: 13px; }
.role-card__editor { grid-column: 1 / -1; margin-top: 18px; border-top: 1px solid #e5e5ea; padding-top: 14px; }
.role-card__editor summary { min-height: 44px; color: #007aff; cursor: pointer; }
.role-card__remove { grid-column: 1 / -1; min-height: 44px; margin-top: 12px; padding: 0; border: 0; background: transparent; color: #ff3b30; cursor: pointer; }
@media (max-width: 720px) { .role-card__toggle { grid-template-columns: auto minmax(0, 1fr) 20px; } .role-card__count { display: none; } .role-card__body { grid-template-columns: minmax(0, 1fr); } .role-card__body section:nth-child(2) { border-top: 1px solid #e5e5ea; } }
</style>
