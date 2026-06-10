<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import {
  behaviorArchetypeOptions,
  expandRoleCompactToPerson,
  listToTextarea,
  openingPresetOptions,
  personToRoleCompact,
  textareaToList,
} from '../utils/roleCompact'

const props = withDefaults(
  defineProps<{
    modelValue: Record<string, any>
    sceneBehaviorMode?: string
  }>(),
  {
    sceneBehaviorMode: '核查取证型',
  }
)

const emit = defineEmits<{
  'update:modelValue': [value: Record<string, any>]
}>()

const roleTypeOptions = ['相关人员', '证人', '嫌疑人', '被害人', '民警']
const statusOptions = ['正常', '受伤可交流', '死亡', '重伤', '昏迷', '无法接受询问']

const compact = ref(personToRoleCompact(props.modelValue, props.sceneBehaviorMode))

watch(
  () => [props.modelValue, props.sceneBehaviorMode],
  () => {
    compact.value = personToRoleCompact(props.modelValue, props.sceneBehaviorMode)
  },
  { deep: true }
)

const boundaryPrimaryLabel = computed(() => compact.value._boundary_primary_label || '可核实事实')
const boundarySecondaryLabel = computed(() => compact.value._boundary_secondary_label || '暂不主动说')

const syncOut = () => {
  const expanded = expandRoleCompactToPerson(compact.value, props.sceneBehaviorMode)
  emit('update:modelValue', { ...props.modelValue, ...expanded })
}

const updateField = (key: string, value: any) => {
  compact.value = { ...compact.value, [key]: value }
  syncOut()
}

const updateListField = (key: 'trigger_points' | 'calming_points' | 'cannot_answer' | 'boundary_primary' | 'boundary_secondary', text: string, limit = 0) => {
  updateField(key, textareaToList(text, limit))
}

const archetypeSummary = computed(() => {
  const item = behaviorArchetypeOptions.find((option) => option.value === compact.value.behavior_archetype)
  return item?.summary || ''
})

const presetSummary = computed(() => {
  const item = openingPresetOptions.find((option) => option.value === compact.value.opening_preset)
  return item?.summary || ''
})
</script>

<template>
  <div class="role-compact-form">
    <div class="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-4">
      <div>
        <label class="form-label form-label--muted">角色姓名</label>
        <input :value="compact.name" type="text" class="form-input" @input="updateField('name', ($event.target as HTMLInputElement).value)" />
      </div>
      <div>
        <label class="form-label form-label--muted">角色类型</label>
        <select :value="compact.role_type" class="form-input" @change="updateField('role_type', ($event.target as HTMLSelectElement).value)">
          <option v-for="option in roleTypeOptions" :key="option" :value="option">{{ option }}</option>
        </select>
      </div>
      <div>
        <label class="form-label form-label--muted">当前状态</label>
        <select :value="compact.status" class="form-input" @change="updateField('status', ($event.target as HTMLSelectElement).value)">
          <option v-for="option in statusOptions" :key="option" :value="option">{{ option }}</option>
        </select>
      </div>
      <div>
        <label class="form-label form-label--muted">行为原型</label>
        <select :value="compact.behavior_archetype" class="form-input" @change="updateField('behavior_archetype', ($event.target as HTMLSelectElement).value)">
          <option v-for="option in behaviorArchetypeOptions" :key="option.value" :value="option.value">{{ option.value }}</option>
        </select>
      </div>
    </div>

    <div class="mt-3 rounded-2xl border border-slate-100 bg-slate-50 px-3 py-2 text-xs leading-5 text-slate-500">
      {{ archetypeSummary }}
    </div>

    <div class="persona-compact-grid mt-4">
      <section class="persona-compact-panel">
        <div class="persona-compact-panel__title">诉求与顾虑</div>
        <div class="mt-3 space-y-3">
          <div>
            <label class="form-label form-label--muted">当前诉求</label>
            <textarea
              :value="compact.current_goal"
              rows="2"
              class="form-textarea form-textarea--compact"
              placeholder="例如：先把人稳下来，不想把事情继续闹大"
              @input="updateField('current_goal', ($event.target as HTMLTextAreaElement).value)"
            />
          </div>
          <div>
            <label class="form-label form-label--muted">最怕后果</label>
            <textarea
              :value="compact.core_concern"
              rows="2"
              class="form-textarea form-textarea--compact"
              placeholder="例如：最怕被认定先动手"
              @input="updateField('core_concern', ($event.target as HTMLTextAreaElement).value)"
            />
          </div>
        </div>
      </section>

      <section class="persona-compact-panel">
        <div class="persona-compact-panel__title">触发与安抚</div>
        <div class="mt-3 space-y-3">
          <div>
            <label class="form-label form-label--muted">触发点（最多 3 条）</label>
            <textarea
              :value="listToTextarea(compact.trigger_points)"
              rows="2"
              class="form-textarea form-textarea--compact"
              placeholder="每行一条"
              @input="updateListField('trigger_points', ($event.target as HTMLTextAreaElement).value, 3)"
            />
          </div>
          <div>
            <label class="form-label form-label--muted">安抚点（最多 3 条）</label>
            <textarea
              :value="listToTextarea(compact.calming_points)"
              rows="2"
              class="form-textarea form-textarea--compact"
              placeholder="每行一条"
              @input="updateListField('calming_points', ($event.target as HTMLTextAreaElement).value, 3)"
            />
          </div>
        </div>
      </section>

      <section class="persona-compact-panel">
        <div class="persona-compact-panel__title">开场状态</div>
        <div class="mt-3 space-y-2">
          <select :value="compact.opening_preset" class="form-input" @change="updateField('opening_preset', ($event.target as HTMLSelectElement).value)">
            <option v-for="option in openingPresetOptions" :key="option.value" :value="option.value">{{ option.label }}</option>
          </select>
          <p class="text-xs leading-5 text-slate-500">{{ presetSummary }}</p>
        </div>
      </section>

      <section class="persona-compact-panel">
        <div class="persona-compact-panel__title">信息边界</div>
        <div class="mt-3 space-y-3">
          <div class="rounded-2xl border border-slate-100 bg-slate-50 px-3 py-2 text-xs leading-5 text-slate-500">
            随场景训练范式「{{ sceneBehaviorMode }}」自动切换边界字段。
          </div>
          <div>
            <label class="form-label form-label--muted">{{ boundaryPrimaryLabel }}</label>
            <textarea
              :value="listToTextarea(compact.boundary_primary)"
              rows="2"
              class="form-textarea form-textarea--compact"
              placeholder="每行一条"
              @input="updateListField('boundary_primary', ($event.target as HTMLTextAreaElement).value, 6)"
            />
          </div>
          <div>
            <label class="form-label form-label--muted">{{ boundarySecondaryLabel }}</label>
            <textarea
              :value="listToTextarea(compact.boundary_secondary)"
              rows="2"
              class="form-textarea form-textarea--compact"
              placeholder="每行一条"
              @input="updateListField('boundary_secondary', ($event.target as HTMLTextAreaElement).value, 6)"
            />
          </div>
          <div>
            <label class="form-label form-label--muted">确实无法回答</label>
            <textarea
              :value="listToTextarea(compact.cannot_answer)"
              rows="2"
              class="form-textarea form-textarea--compact"
              placeholder="每行一条"
              @input="updateListField('cannot_answer', ($event.target as HTMLTextAreaElement).value, 6)"
            />
          </div>
          <div v-if="sceneBehaviorMode === '管控型'">
            <label class="form-label form-label--muted">酒精 / 药物 / 精神状态</label>
            <textarea
              :value="compact.impairment_state"
              rows="2"
              class="form-textarea form-textarea--compact"
              placeholder="例如：饮酒明显，语无伦次"
              @input="updateField('impairment_state', ($event.target as HTMLTextAreaElement).value)"
            />
          </div>
        </div>
      </section>
    </div>
  </div>
</template>

<style scoped>
.role-compact-form :deep(.persona-compact-grid) {
  display: grid;
  grid-template-columns: repeat(1, minmax(0, 1fr));
  gap: 1rem;
}

@media (min-width: 1280px) {
  .role-compact-form :deep(.persona-compact-grid) {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

.role-compact-form :deep(.persona-compact-panel) {
  border: 1px solid rgb(241 245 249);
  border-radius: 1rem;
  background: #fff;
  padding: 1rem;
}

.role-compact-form :deep(.persona-compact-panel__title) {
  font-size: 0.875rem;
  font-weight: 700;
  color: rgb(51 65 85);
}
</style>
