<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { expandRoleCompactToPerson, listToTextarea, personToRoleCompact, textareaToList } from '../utils/roleCompact'

const props = withDefaults(defineProps<{ modelValue: Record<string, any>; sceneBehaviorMode?: string }>(), {
  sceneBehaviorMode: '核查取证型',
})
const emit = defineEmits<{ 'update:modelValue': [value: Record<string, any>] }>()

const roleTypeOptions = ['相关人员', '证人', '嫌疑人', '被害人', '报警人', '民警']
const statusOptions = ['正常', '受伤可交流', '死亡', '重伤', '昏迷', '无法接受询问']
const memoryTypeOptions = [
  { value: 'direct_statement', label: '直接陈述' },
  { value: 'personal_experience', label: '亲历' },
  { value: 'direct_observation', label: '亲眼所见' },
  { value: 'hearsay', label: '听他人说' },
  { value: 'later_learned', label: '事后得知' },
  { value: 'source_mention', label: '原文提及' },
]
const legacyRoleFields = [
  'behavior_archetype', 'opening_preset', 'current_goal', 'current_need', 'core_concern', 'weakness',
  'relationship_pressure', 'surface_stance', 'pressure_response', 'trigger_points', 'calming_points',
  'police_attitude', 'interaction_style', 'personality', 'speaking_style', 'authority_attitude',
  'stress_response', 'public_mask', 'private_drive', 'self_image', 'boundary_primary', 'boundary_secondary',
  'known_key_points', 'withheld_key_points', 'hidden_truths', 'does_not_know', 'cannot_answer',
]

const compact = ref(personToRoleCompact(props.modelValue, props.sceneBehaviorMode))
watch(() => [props.modelValue, props.sceneBehaviorMode], () => {
  compact.value = personToRoleCompact(props.modelValue, props.sceneBehaviorMode)
}, { deep: true })

const memoryRows = computed(() => Array.isArray(compact.value.role_memories) ? compact.value.role_memories : [])

const syncOut = () => {
  const next = { ...props.modelValue, ...expandRoleCompactToPerson(compact.value, props.sceneBehaviorMode) }
  for (const field of legacyRoleFields) delete next[field]
  next.role_template_version = 'source_memory_v2'
  emit('update:modelValue', next)
}
const updateField = (key: string, value: any) => {
  compact.value = { ...compact.value, [key]: value }
  syncOut()
}
const updateList = (key: string, text: string) => updateField(key, textareaToList(text, 12))
const updateMemory = (index: number, key: string, value: string) => {
  const rows = memoryRows.value.map((item: any) => ({ ...item }))
  rows[index] = { ...rows[index], [key]: value }
  updateField('role_memories', rows)
}
const addMemory = () => updateField('role_memories', [
  ...memoryRows.value,
  { memory_id: `M${memoryRows.value.length + 1}`, memory_type: 'direct_statement', statement: '', time_hint: '', place_hint: '', actors: [], source_refs: [] },
])
const removeMemory = (index: number) => updateField('role_memories', memoryRows.value.filter((_: any, i: number) => i !== index))
</script>

<template>
  <div class="role-memory-form">
    <section class="form-section">
      <header><strong>角色身份</strong><span>只保存原文可回溯信息，不再使用旧版人格参数。</span></header>
      <div class="grid grid-3">
        <label>角色姓名<input :value="compact.name" @input="updateField('name', ($event.target as HTMLInputElement).value)" /></label>
        <label>角色类型<select :value="compact.role_type" @change="updateField('role_type', ($event.target as HTMLSelectElement).value)"><option v-for="item in roleTypeOptions" :key="item" :value="item">{{ item }}</option></select></label>
        <label>人物状态<select :value="compact.status" @change="updateField('status', ($event.target as HTMLSelectElement).value)"><option v-for="item in statusOptions" :key="item" :value="item">{{ item }}</option></select></label>
      </div>
    </section>

    <section v-if="false" class="form-section">
      <header><strong>人物线与角色证言</strong><span>按角色经历顺序整理，尽量保留原文，仅做轻微润色。</span></header>
      <div v-if="!memoryRows.length" class="empty">暂未提取到该角色的陈述、证言或亲历内容</div>
      <article v-for="(memory, index) in memoryRows" :key="memory.memory_id || index" class="memory-row">
        <div class="grid grid-3">
          <label>记忆来源<select :value="memory.memory_type" @change="updateMemory(index, 'memory_type', ($event.target as HTMLSelectElement).value)"><option v-for="item in memoryTypeOptions" :key="item.value" :value="item.value">{{ item.label }}</option></select></label>
          <label>时间线索<input :value="memory.time_hint" placeholder="如：7月19日上午、冲突后" @input="updateMemory(index, 'time_hint', ($event.target as HTMLInputElement).value)" /></label>
          <label>空间线索<input :value="memory.place_hint" placeholder="如：山脚、公路边" @input="updateMemory(index, 'place_hint', ($event.target as HTMLInputElement).value)" /></label>
        </div>
        <label>证言 / 陈述 / 亲历记忆<textarea :value="memory.statement" rows="4" placeholder="该角色自己说了什么、经历了什么、看见或听见了什么" @input="updateMemory(index, 'statement', ($event.target as HTMLTextAreaElement).value)" /></label>
        <p v-if="memory.quote" class="source-quote">原文回溯：{{ memory.quote }}</p>
        <button type="button" class="danger" @click="removeMemory(index)">删除该条</button>
      </article>
      <button type="button" @click="addMemory">添加角色证言</button>
    </section>

    <section v-if="false" class="form-section">
      <header><strong>事实边界</strong><span>约束角色只能依据本人人物线回答。</span></header>
      <div class="grid grid-2">
        <label>回答约束<textarea :value="listToTextarea(compact.response_constraints)" rows="5" placeholder="每行一条" @input="updateList('response_constraints', ($event.target as HTMLTextAreaElement).value)" /></label>
        <label>待核实 / 无法确认<textarea :value="listToTextarea(compact.unresolved_claims)" rows="5" placeholder="每行一条" @input="updateList('unresolved_claims', ($event.target as HTMLTextAreaElement).value)" /></label>
      </div>
    </section>
  </div>
</template>

<style scoped>
.role-memory-form { display: flex; flex-direction: column; gap: 14px; }
.form-section { border: 1px solid #e2e8f0; border-radius: 8px; background: #fff; overflow: hidden; }
header { display: flex; align-items: baseline; gap: 10px; padding: 12px 16px; background: #f8fafc; border-bottom: 1px solid #eef2f7; }
header strong { color: #172033; font-size: 14px; }
header span { color: #8290a6; font-size: 12px; }
.grid { display: grid; gap: 14px; padding: 16px; }
.grid-3 { grid-template-columns: repeat(3, minmax(0, 1fr)); }
.grid-2 { grid-template-columns: repeat(2, minmax(0, 1fr)); }
label { display: flex; flex-direction: column; gap: 7px; color: #52627a; font-size: 13px; font-weight: 600; }
input, select, textarea { width: 100%; border: 1px solid #d7e0ec; border-radius: 6px; padding: 9px 11px; color: #1e293b; background: #fff; font: inherit; font-weight: 400; box-sizing: border-box; }
textarea { resize: vertical; line-height: 1.6; }
.memory-row { margin: 14px 16px; padding: 14px; border: 1px solid #e5eaf1; border-radius: 8px; background: #fbfcfe; }
.memory-row .grid { padding: 0 0 12px; }
button { margin: 0 16px 16px; border: 1px solid #bfdbfe; border-radius: 6px; padding: 7px 12px; background: #eff6ff; color: #1d4ed8; cursor: pointer; }
.memory-row button { margin: 10px 0 0; }
.source-quote { margin: 0; padding: 8px 10px; border-left: 3px solid #93c5fd; color: #64748b; background: #f8fafc; font-size: 12px; line-height: 1.6; }
button.danger { border-color: #fecaca; background: #fff1f2; color: #b91c1c; }
.empty { margin: 16px; padding: 18px; border: 1px dashed #cbd5e1; color: #94a3b8; text-align: center; }
@media (max-width: 900px) { .grid-3, .grid-2 { grid-template-columns: 1fr; } header { align-items: flex-start; flex-direction: column; } }
</style>
