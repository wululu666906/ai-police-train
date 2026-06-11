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

const updateListField = (
  key: 'trigger_points' | 'calming_points' | 'cannot_answer' | 'boundary_primary' | 'boundary_secondary' | 'relationship_pressure',
  text: string,
  limit = 0
) => {
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
  <div class="rcf-sheet">

    <!-- 基础信息组 -->
    <section class="rcf-card">
      <div class="rcf-card__header">
        <span class="rcf-card__title">角色设定</span>
        <span class="rcf-card__desc">{{ archetypeSummary || '选择行为原型后会自动填入人设描述' }}</span>
      </div>

      <div class="rcf-grid rcf-grid--four">
        <div class="rcf-field">
          <label class="rcf-label">角色姓名 <span class="rcf-required">*</span></label>
          <input
            :value="compact.name"
            type="text"
            class="rcf-input"
            placeholder="如：李娜"
            @input="updateField('name', ($event.target as HTMLInputElement).value)"
          />
        </div>
        <div class="rcf-field">
          <label class="rcf-label">行为类型</label>
          <select
            :value="compact.role_type"
            class="rcf-input"
            @change="updateField('role_type', ($event.target as HTMLSelectElement).value)"
          >
            <option v-for="option in roleTypeOptions" :key="option" :value="option">{{ option }}</option>
          </select>
        </div>
        <div class="rcf-field">
          <label class="rcf-label">激活配合型</label>
          <select
            :value="compact.status"
            class="rcf-input"
            @change="updateField('status', ($event.target as HTMLSelectElement).value)"
          >
            <option v-for="option in statusOptions" :key="option" :value="option">{{ option }}</option>
          </select>
        </div>
        <div class="rcf-field">
          <label class="rcf-label">人物身份</label>
          <select
            :value="compact.behavior_archetype"
            class="rcf-input"
            @change="updateField('behavior_archetype', ($event.target as HTMLSelectElement).value)"
          >
            <option v-for="option in behaviorArchetypeOptions" :key="option.value" :value="option.value">{{ option.value }}</option>
          </select>
        </div>
      </div>

      <div class="rcf-grid rcf-grid--three rcf-mt">
        <div class="rcf-field">
          <label class="rcf-label">角色类型</label>
          <select
            :value="compact.role_type"
            class="rcf-input"
            @change="updateField('role_type', ($event.target as HTMLSelectElement).value)"
          >
            <option v-for="option in roleTypeOptions" :key="option" :value="option">{{ option }}</option>
          </select>
        </div>
        <div class="rcf-field">
          <label class="rcf-label">当前状态</label>
          <select
            :value="compact.status"
            class="rcf-input"
            @change="updateField('status', ($event.target as HTMLSelectElement).value)"
          >
            <option v-for="option in statusOptions" :key="option" :value="option">{{ option }}</option>
          </select>
        </div>
        <div class="rcf-field">
          <label class="rcf-label">开场状态</label>
          <select
            :value="compact.opening_preset"
            class="rcf-input"
            @change="updateField('opening_preset', ($event.target as HTMLSelectElement).value)"
          >
            <option v-for="option in openingPresetOptions" :key="option.value" :value="option.value">{{ option.label }}</option>
          </select>
        </div>
      </div>
      <div v-if="presetSummary" class="rcf-hint-row">{{ presetSummary }}</div>
    </section>

    <!-- 诉求与顾虑 -->
    <section class="rcf-card">
      <div class="rcf-card__header">
        <span class="rcf-card__title">诉求与顾虑</span>
      </div>
      <div class="rcf-grid rcf-grid--two">
        <div class="rcf-field">
          <label class="rcf-label">当前诉求</label>
          <textarea
            :value="compact.current_goal"
            rows="3"
            class="rcf-textarea"
            placeholder="例如：先把人稳下来，不想把事情继续闹大"
            @input="updateField('current_goal', ($event.target as HTMLTextAreaElement).value)"
          />
        </div>
        <div class="rcf-field">
          <label class="rcf-label">最怕后果</label>
          <textarea
            :value="compact.core_concern"
            rows="3"
            class="rcf-textarea"
            placeholder="例如：最怕被认定先动手"
            @input="updateField('core_concern', ($event.target as HTMLTextAreaElement).value)"
          />
        </div>
        <div class="rcf-field">
          <label class="rcf-label">表面姿态</label>
          <textarea
            :value="compact.surface_stance"
            rows="3"
            class="rcf-textarea"
            placeholder="例如：嘴上愿意配合，但会反复强调自己没错"
            @input="updateField('surface_stance', ($event.target as HTMLTextAreaElement).value)"
          />
        </div>
        <div class="rcf-field">
          <label class="rcf-label">承压反应</label>
          <textarea
            :value="compact.pressure_response"
            rows="3"
            class="rcf-textarea"
            placeholder="例如：被追问细节时会先辩解，再试探性改口"
            @input="updateField('pressure_response', ($event.target as HTMLTextAreaElement).value)"
          />
        </div>
      </div>
    </section>

    <!-- 触发与安抚 -->
    <section class="rcf-card">
      <div class="rcf-card__header">
        <span class="rcf-card__title">触发与安抚</span>
      </div>
      <div class="rcf-grid rcf-grid--three">
        <div class="rcf-field">
          <div class="rcf-label-row">
            <label class="rcf-label">触发点</label>
            <span class="rcf-hint">最多 3 条</span>
          </div>
          <textarea
            :value="listToTextarea(compact.trigger_points)"
            rows="4"
            class="rcf-textarea"
            placeholder="每行一条"
            @input="updateListField('trigger_points', ($event.target as HTMLTextAreaElement).value, 3)"
          />
        </div>
        <div class="rcf-field">
          <div class="rcf-label-row">
            <label class="rcf-label">安抚点</label>
            <span class="rcf-hint">最多 3 条</span>
          </div>
          <textarea
            :value="listToTextarea(compact.calming_points)"
            rows="4"
            class="rcf-textarea"
            placeholder="每行一条"
            @input="updateListField('calming_points', ($event.target as HTMLTextAreaElement).value, 3)"
          />
        </div>
        <div class="rcf-field">
          <div class="rcf-label-row">
            <label class="rcf-label">关系压力</label>
            <span class="rcf-hint">最多 3 条</span>
          </div>
          <textarea
            :value="listToTextarea(compact.relationship_pressure)"
            rows="4"
            class="rcf-textarea"
            placeholder="每行一条"
            @input="updateListField('relationship_pressure', ($event.target as HTMLTextAreaElement).value, 3)"
          />
        </div>
      </div>
    </section>

    <!-- 信息边界 -->
    <section class="rcf-card">
      <div class="rcf-card__header">
        <span class="rcf-card__title">信息边界</span>
        <span class="rcf-card__desc">随场景训练范式「{{ sceneBehaviorMode }}」自动切换边界字段</span>
      </div>
      <div class="rcf-grid rcf-grid--three">
        <div class="rcf-subcard">
          <div class="rcf-field">
            <label class="rcf-label">{{ boundaryPrimaryLabel }}</label>
            <textarea
              :value="listToTextarea(compact.boundary_primary)"
              rows="5"
              class="rcf-textarea"
              placeholder="每行一条"
              @input="updateListField('boundary_primary', ($event.target as HTMLTextAreaElement).value, 6)"
            />
          </div>
        </div>
        <div class="rcf-subcard">
          <div class="rcf-field">
            <label class="rcf-label">{{ boundarySecondaryLabel }}</label>
            <textarea
              :value="listToTextarea(compact.boundary_secondary)"
              rows="5"
              class="rcf-textarea"
              placeholder="每行一条"
              @input="updateListField('boundary_secondary', ($event.target as HTMLTextAreaElement).value, 6)"
            />
          </div>
        </div>
        <div class="rcf-subcard">
          <div class="rcf-field">
            <label class="rcf-label">确实无法回答</label>
            <textarea
              :value="listToTextarea(compact.cannot_answer)"
              rows="5"
              class="rcf-textarea"
              :placeholder="compact.cannot_answer?.length ? '每行一条' : '暂无明确限制时，可先留空'"
              @input="updateListField('cannot_answer', ($event.target as HTMLTextAreaElement).value, 6)"
            />
          </div>
        </div>
      </div>

      <div v-if="sceneBehaviorMode === '管控型'" class="rcf-field rcf-mt">
        <label class="rcf-label">酒精 / 药物 / 精神状态</label>
        <textarea
          :value="compact.impairment_state"
          rows="3"
          class="rcf-textarea"
          placeholder="例如：饮酒明显，语无伦次"
          @input="updateField('impairment_state', ($event.target as HTMLTextAreaElement).value)"
        />
      </div>
    </section>

  </div>
</template>

<style scoped>
/* ── 整体容器 ──────────────────────────────────────────── */
.rcf-sheet {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

/* ── 卡片 ──────────────────────────────────────────────── */
.rcf-card {
  border: 1px solid #e2e8f0;
  border-radius: 12px;
  background: #fff;
  overflow: hidden;
}

.rcf-card__header {
  display: flex;
  align-items: baseline;
  gap: 10px;
  padding: 11px 16px 10px;
  border-bottom: 1px solid #f1f5f9;
  background: #f8fafc;
}

.rcf-card__title {
  font-size: 13px;
  font-weight: 700;
  color: #1e293b;
  white-space: nowrap;
}

.rcf-card__desc {
  font-size: 12px;
  color: #94a3b8;
  line-height: 1.5;
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.rcf-subcard {
  border: 1px solid #f1f5f9;
  border-radius: 10px;
  background: #fafcff;
  padding: 12px;
}

/* ── 网格 ──────────────────────────────────────────────── */
.rcf-grid {
  display: grid;
  gap: 12px;
  padding: 14px 16px;
  grid-template-columns: 1fr;
}

.rcf-mt {
  padding-top: 0;
}

/* ── 字段 ──────────────────────────────────────────────── */
.rcf-field {
  display: flex;
  flex-direction: column;
  gap: 5px;
}

.rcf-label-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.rcf-label {
  font-size: 12px;
  font-weight: 700;
  color: #64748b;
  line-height: 1;
}

.rcf-required {
  color: #ef4444;
  font-size: 12px;
}

.rcf-hint {
  font-size: 11px;
  color: #94a3b8;
}

.rcf-hint-row {
  padding: 0 16px 12px;
  font-size: 12px;
  color: #94a3b8;
  line-height: 1.6;
}

/* ── 输入控件 ──────────────────────────────────────────── */
.rcf-input,
.rcf-textarea {
  width: 100%;
  box-sizing: border-box;
  padding: 7px 10px;
  border: 1.5px solid #e2e8f0;
  border-radius: 8px;
  background: #fff;
  font-size: 13px;
  font-weight: 500;
  color: #0f172a;
  outline: none;
  transition: border-color 0.15s ease, box-shadow 0.15s ease;
  font-family: inherit;
}

.rcf-input:focus,
.rcf-textarea:focus {
  border-color: #1d3557;
  box-shadow: 0 0 0 3px rgba(29, 53, 87, 0.08);
}

.rcf-input::placeholder,
.rcf-textarea::placeholder {
  color: #cbd5e1;
  font-weight: 400;
}

.rcf-textarea {
  resize: vertical;
  min-height: 80px;
  line-height: 1.6;
}

/* ── 响应式 ────────────────────────────────────────────── */
@media (min-width: 700px) {
  .rcf-grid--two {
    grid-template-columns: repeat(2, 1fr);
  }
}

@media (min-width: 900px) {
  .rcf-grid--three {
    grid-template-columns: repeat(3, 1fr);
  }
  .rcf-grid--four {
    grid-template-columns: repeat(4, 1fr);
  }
}
</style>
