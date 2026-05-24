<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { showConfirmDialog, showToast } from 'vant'
import {
  behaviorArchetypeOptions,
  buildLegacyInfoBoundary,
  buildSceneBoundaryGroups,
  buildBehaviorSummary,
  clarityScoreFromLevel,
  cooperationScoreFromLevel,
  dedupeStringList,
  emotionScoreFromLevel,
  getSceneBoundaryFields,
  normalizeBehaviorTemplate,
  policeAttitudeOptions,
  riskScoreFromLevel,
  sceneBehaviorModeOptions,
  stateLevelOptions,
  stringifyTextList,
  parseTextList,
} from '../utils/personaTemplate'
import request from '../utils/request'

const roles = ref<any[]>([])
const loading = ref(false)
const saving = ref(false)
const deleting = ref(false)
const showDetail = ref(false)
const roleOptions = ref<any[]>([])
const pageError = ref('')
const syncingCaseSelection = ref(false)
const form = reactive({
  id: null as number | null,
  scope: 'public' as 'public' | 'case',
  case_id: null as number | null,
  scene_ids: [] as number[],
  primary_scene_id: null as number | null,
  name: '',
  role_type: '相关人员',
  behavior_archetype: '求助配合型',
  police_attitude: '主动求助',
  interaction_style: '配合型',
  personality: '',
  speaking_style: '常规',
  status: '正常',
  scene_behavior_mode: '核查取证型',
  current_goal: '',
  core_concern: '',
  calming_points_text: '',
  relationship_pressure_text: '',
  surface_stance: '',
  pressure_response: '',
  trigger_points_text: '',
  emotion_level: '中',
  cooperation_level: '中',
  risk_level: '中',
  clarity_level: '中',
  init_emotion: 50,
  init_trust: 30,
  init_risk: 50,
  init_expression_clarity: 52,
  impairment_state: '',
  iq_level: '中等',
  eq_level: '中等',
  lying_ability: '一般',
  knows_facts_text: '',
  does_not_know_text: '',
  hidden_truths_text: '',
  known_key_points_text: '',
  withheld_key_points_text: '',
  conflict_core_text: '',
  acceptable_outcomes_text: '',
  no_go_topics_text: '',
  trigger_sources_text: '',
  concerned_targets_text: '',
  taboo_actions_text: '',
  escalation_actions_text: '',
  deescalation_conditions_text: '',
})

const roleIdentityOptions = ['相关人员', '证人', '嫌疑人', '被害人', '民警']
const statusOptions = ['正常', '死亡', '重伤', '昏迷', '无法接受询问']
const levelOptions = ['低', '中等', '高']
const lieOptions = ['弱', '一般', '强']
const previewList = (value: string) => parseTextList(value).slice(0, 4)

const boundaryFieldTextMap = {
  known_key_points: 'known_key_points_text',
  withheld_key_points: 'withheld_key_points_text',
  conflict_core: 'conflict_core_text',
  acceptable_outcomes: 'acceptable_outcomes_text',
  no_go_topics: 'no_go_topics_text',
  trigger_sources: 'trigger_sources_text',
  concerned_targets: 'concerned_targets_text',
  taboo_actions: 'taboo_actions_text',
  escalation_actions: 'escalation_actions_text',
  deescalation_conditions: 'deescalation_conditions_text',
} as const

const buildBoundaryListsFromForm = () =>
  Object.fromEntries(
    Object.entries(boundaryFieldTextMap).map(([fieldKey, textKey]) => [fieldKey, dedupeStringList(parseTextList(form[textKey as keyof typeof form] as string))])
  )

const groupedRoles = computed(() => {
  const groups: Record<string, any[]> = {}
  roles.value.forEach((role) => {
    const title = role.case_title || '公共角色模板'
    if (!groups[title]) groups[title] = []
    groups[title].push(role)
  })
  return groups
})

const currentCaseScenes = computed(() => {
  const currentCase = roleOptions.value.find((item) => item.id === form.case_id)
  return currentCase?.scenes || []
})

const currentBoundaryFields = computed(() =>
  getSceneBoundaryFields(form.scene_behavior_mode).map((field) => ({
    ...field,
    modelKey: boundaryFieldTextMap[field.key],
  }))
)

const currentPrimaryScene = computed(() => {
  const preferredId = form.primary_scene_id || form.scene_ids[0]
  return currentCaseScenes.value.find((item: any) => item.id === preferredId) || null
})

const roleCountSummary = computed(() => ({
  total: roles.value.length,
  publicCount: roles.value.filter((item) => item.is_public).length,
  caseCount: roles.value.filter((item) => !item.is_public).length,
}))

watch(
  () => form.case_id,
  () => {
    if (syncingCaseSelection.value) return
    form.scene_ids = []
    form.primary_scene_id = null
  },
  { flush: 'sync' }
)

watch(
  () => [form.scope, form.primary_scene_id, ...form.scene_ids],
  () => {
    if (form.scope !== 'case') return
    const nextMode = currentPrimaryScene.value?.behavior_mode
    if (nextMode) {
      form.scene_behavior_mode = nextMode
    }
  },
  { flush: 'sync' }
)

const roleDraftProfile = computed(() => {
  const normalized = normalizeBehaviorTemplate({
    ...form,
    calming_points: parseTextList(form.calming_points_text),
    relationship_pressure: parseTextList(form.relationship_pressure_text),
    trigger_points: parseTextList(form.trigger_points_text),
    scene_behavior_mode: form.scene_behavior_mode,
    risk_level: form.risk_level,
    clarity_level: form.clarity_level,
    impairment_state: form.impairment_state,
    ...buildBoundaryListsFromForm(),
  })
  const relationshipPressure = previewList(form.relationship_pressure_text)
  const triggerPoints = normalized.trigger_points.slice(0, 4)
  const calmingPoints = normalized.calming_points.slice(0, 4)
  const legacyBoundary = buildLegacyInfoBoundary({
    ...normalized,
    does_not_know: dedupeStringList(parseTextList(form.does_not_know_text)),
  })
  const hiddenTruths = legacyBoundary.hidden_truths.slice(0, 4)
  const knownFacts = legacyBoundary.knows_facts.slice(0, 4)
  const boundaryGroups = buildSceneBoundaryGroups(normalized).map((field) => {
    const textKey = boundaryFieldTextMap[field.key]
    const manualItems = textKey ? previewList(form[textKey]) : []
    return {
      ...field,
      items: manualItems.length ? manualItems : field.items.slice(0, 4),
    }
  })

  const contradictions: string[] = []
  if (normalized.current_goal.trim() && normalized.core_concern.trim()) {
    contradictions.push(`一旦${normalized.core_concern.trim()}被碰到，角色会更本能地围绕“${normalized.current_goal.trim()}”防守或求助。`)
  }
  if (normalized.core_concern.trim() && triggerPoints.length) {
    contradictions.push('一旦碰到最担心的后果或敏感点，回答质量会明显波动。')
  }
  if (relationshipPressure.length && normalized.pressure_response.trim()) {
    contradictions.push('既受关系压力牵引，又有固定防御动作，容易先护人或先切责任。')
  }

  const summaryParts = [
    normalized.behavior_archetype ? `行为原型偏向${normalized.behavior_archetype}` : '',
    normalized.police_attitude ? `面对警方时更像“${normalized.police_attitude}”` : '',
    normalized.current_goal.trim() ? `当前最想保住的是${normalized.current_goal.trim()}` : '',
    normalized.core_concern.trim() ? `最担心的是${normalized.core_concern.trim()}` : '',
    relationshipPressure.length ? `现实和关系压力主要来自${relationshipPressure.join('、')}` : '',
    normalized.pressure_response.trim() ? `承压后常见反应是${normalized.pressure_response.trim()}` : '',
    triggerPoints.length ? `提到${triggerPoints.join('、')}时更容易情绪起伏或改口` : '',
    calmingPoints.length ? `更容易被${calmingPoints.join('、')}稳住` : '',
  ].filter(Boolean)

  return {
    normalized,
    relationshipPressure,
    triggerPoints,
    calmingPoints,
    hiddenTruths,
    knownFacts,
    boundaryGroups,
    contradictions,
    summaryText: summaryParts.join('；') || '当前还缺少足够信息，建议先补行为原型、诉求、顾虑和触发点。',
  }
})

const previewStateLabel = computed(() => {
  if (form.risk_level === '高') return '需要优先稳控'
  if (form.clarity_level === '低') return '表达混乱不稳'
  if (form.cooperation_level === '高') return '开场较易配合'
  if (form.emotion_level === '高') return '开场情绪高压'
  return '初始谨慎试探'
})

const previewBreakthroughs = computed(() => {
  const result: string[] = []
  if (roleDraftProfile.value.normalized.core_concern.trim()) {
    result.push(`先围绕“${roleDraftProfile.value.normalized.core_concern.trim()}”追问最现实的后果压力`)
  }
  if (roleDraftProfile.value.relationshipPressure.length) {
    result.push(`从“${roleDraftProfile.value.relationshipPressure[0]}”切入其关系负担和顾虑`)
  }
  if (roleDraftProfile.value.triggerPoints.length) {
    result.push(`提到“${roleDraftProfile.value.triggerPoints[0]}”时更可能出现情绪波动或改口`)
  }
  if (roleDraftProfile.value.calmingPoints.length) {
    result.push(`优先使用“${roleDraftProfile.value.calmingPoints[0]}”这一类安抚动作，更容易让其继续交流`)
  }
  if (roleDraftProfile.value.hiddenTruths.length) {
    result.push(`可核对其刻意没主动提的“${roleDraftProfile.value.hiddenTruths[0]}”`)
  }
  return result.slice(0, 4)
})

const buildRoleOverview = (role: any) => {
  const compact = normalizeBehaviorTemplate(role)
  const parts = [
    compact.behavior_archetype ? `原型：${compact.behavior_archetype}` : '',
    compact.current_goal ? `诉求：${compact.current_goal}` : '',
    compact.core_concern ? `顾虑：${compact.core_concern}` : '',
    compact.police_attitude ? `态度：${compact.police_attitude}` : '',
  ].filter(Boolean)
  return parts.join('；') || '还没有补充核心角色驱动。'
}

const getRoleSummaryChips = (role: any) => {
  const compact = normalizeBehaviorTemplate(role)
  return [
    compact.behavior_archetype ? `原型 ${compact.behavior_archetype}` : '',
    compact.current_goal ? `诉求 ${compact.current_goal}` : '',
    compact.core_concern ? `顾虑 ${compact.core_concern}` : '',
    compact.trigger_points[0] ? `触发点 ${compact.trigger_points[0]}` : '',
  ].filter(Boolean).slice(0, 3)
}

const generatePersonaSummary = () => {
  form.personality = roleDraftProfile.value.summaryText
  showToast({ type: 'success', message: '已根据结构化字段写入性格摘要' })
}

const getInteractionStyleClass = (type: string) => {
  if (type === '委屈宣泄型' || type === '醉酒失控型') return 'bg-orange-100 text-orange-700'
  if (type === '强硬对抗型' || type === '围观起哄型') return 'bg-red-100 text-red-700'
  if (type === '求助配合型') return 'bg-green-100 text-green-700'
  return 'bg-blue-100 text-blue-700'
}

const fetchRoles = async () => {
  loading.value = true
  pageError.value = ''
  try {
    const res: any = await request.get('/cases/all/roles', { _skipErrorToast: true } as any)
    roles.value = Array.isArray(res) ? res : []
  } catch (error) {
    console.error('Fetch roles error:', error)
    pageError.value = '角色列表加载失败，请稍后重试。'
  } finally {
    loading.value = false
  }
}

const fetchRoleOptions = async () => {
  try {
    const res: any = await request.get('/cases/role-case-options', { _skipErrorToast: true } as any)
    roleOptions.value = Array.isArray(res) ? res : []
  } catch (error) {
    console.error('Fetch role options error:', error)
    pageError.value = pageError.value || '案件选项加载失败，请稍后重试。'
  }
}

const refreshPage = async () => {
  await Promise.all([fetchRoles(), fetchRoleOptions()])
}

const resetForm = () => {
  form.id = null
  form.scope = 'public'
  form.case_id = null
  form.scene_ids = []
  form.primary_scene_id = null
  form.name = ''
  form.role_type = '相关人员'
  form.behavior_archetype = '求助配合型'
  form.police_attitude = '主动求助'
  form.interaction_style = '配合型'
  form.personality = ''
  form.speaking_style = '常规'
  form.status = '正常'
  form.scene_behavior_mode = '核查取证型'
  form.current_goal = ''
  form.core_concern = ''
  form.calming_points_text = ''
  form.relationship_pressure_text = ''
  form.surface_stance = ''
  form.pressure_response = ''
  form.trigger_points_text = ''
  form.emotion_level = '中'
  form.cooperation_level = '中'
  form.risk_level = '中'
  form.clarity_level = '中'
  form.init_emotion = 50
  form.init_trust = 30
  form.init_risk = 50
  form.init_expression_clarity = 52
  form.impairment_state = ''
  form.iq_level = '中等'
  form.eq_level = '中等'
  form.lying_ability = '一般'
  form.knows_facts_text = ''
  form.does_not_know_text = ''
  form.hidden_truths_text = ''
  form.known_key_points_text = ''
  form.withheld_key_points_text = ''
  form.conflict_core_text = ''
  form.acceptable_outcomes_text = ''
  form.no_go_topics_text = ''
  form.trigger_sources_text = ''
  form.concerned_targets_text = ''
  form.taboo_actions_text = ''
  form.escalation_actions_text = ''
  form.deescalation_conditions_text = ''
}

const closeDetail = () => {
  showDetail.value = false
}

const openCreate = () => {
  resetForm()
  showDetail.value = true
}

const openDetail = (role: any) => {
  const compact = normalizeBehaviorTemplate(role)
  syncingCaseSelection.value = true
  form.id = role.id
  form.scope = role.is_public ? 'public' : 'case'
  form.case_id = role.case_id ?? null
  form.scene_ids = Array.isArray(role.scene_ids) ? [...role.scene_ids] : []
  form.primary_scene_id = role.primary_scene_id ?? null
  form.name = role.name || ''
  form.role_type = role.role_type || '相关人员'
  form.behavior_archetype = compact.behavior_archetype
  form.police_attitude = compact.police_attitude
  form.interaction_style = compact.interaction_style || role.interaction_style || '配合型'
  form.personality = role.personality || ''
  form.speaking_style = role.speaking_style || '常规'
  form.status = role.status || '正常'
  form.scene_behavior_mode = compact.scene_behavior_mode || currentPrimaryScene.value?.behavior_mode || '核查取证型'
  form.current_goal = compact.current_goal
  form.core_concern = compact.core_concern
  form.calming_points_text = stringifyTextList(compact.calming_points)
  form.relationship_pressure_text = stringifyTextList(compact.relationship_pressure)
  form.surface_stance = compact.surface_stance
  form.pressure_response = compact.pressure_response
  form.trigger_points_text = stringifyTextList(compact.trigger_points)
  form.emotion_level = compact.emotion_level
  form.cooperation_level = compact.cooperation_level
  form.risk_level = compact.risk_level || '中'
  form.clarity_level = compact.clarity_level || '中'
  form.init_emotion = Number(role.init_emotion ?? 50)
  form.init_trust = Number(role.init_trust ?? 30)
  form.init_risk = Number(compact.init_risk ?? 50)
  form.init_expression_clarity = Number(compact.init_expression_clarity ?? 52)
  form.impairment_state = String(compact.impairment_state || '').trim()
  form.iq_level = role.iq_level || '中等'
  form.eq_level = role.eq_level || '中等'
  form.lying_ability = role.lying_ability || '一般'
  form.knows_facts_text = stringifyTextList(role.knows_facts)
  form.does_not_know_text = stringifyTextList(role.does_not_know)
  form.hidden_truths_text = stringifyTextList(role.hidden_truths)
  form.known_key_points_text = stringifyTextList(compact.known_key_points)
  form.withheld_key_points_text = stringifyTextList(compact.withheld_key_points)
  form.conflict_core_text = stringifyTextList(compact.conflict_core)
  form.acceptable_outcomes_text = stringifyTextList(compact.acceptable_outcomes)
  form.no_go_topics_text = stringifyTextList(compact.no_go_topics)
  form.trigger_sources_text = stringifyTextList(compact.trigger_sources)
  form.concerned_targets_text = stringifyTextList(compact.concerned_targets)
  form.taboo_actions_text = stringifyTextList(compact.taboo_actions)
  form.escalation_actions_text = stringifyTextList(compact.escalation_actions)
  form.deescalation_conditions_text = stringifyTextList(compact.deescalation_conditions)
  syncingCaseSelection.value = false
  showDetail.value = true
}

const buildPayload = () => {
  const boundaryLists = buildBoundaryListsFromForm()
  const normalized = normalizeBehaviorTemplate({
    ...form,
    calming_points: dedupeStringList(parseTextList(form.calming_points_text)),
    relationship_pressure: dedupeStringList(parseTextList(form.relationship_pressure_text)),
    trigger_points: dedupeStringList(parseTextList(form.trigger_points_text)),
    scene_behavior_mode: form.scene_behavior_mode,
    risk_level: form.risk_level,
    clarity_level: form.clarity_level,
    impairment_state: form.impairment_state,
    ...boundaryLists,
    init_emotion: emotionScoreFromLevel(form.emotion_level, form.init_emotion),
    init_trust: cooperationScoreFromLevel(form.cooperation_level, form.init_trust),
    init_risk: riskScoreFromLevel(form.risk_level, form.init_risk),
    init_expression_clarity: clarityScoreFromLevel(form.clarity_level, form.init_expression_clarity),
  })
  const legacyBoundary = buildLegacyInfoBoundary({
    ...normalized,
    does_not_know: dedupeStringList(parseTextList(form.does_not_know_text)),
  })
  const relationshipPressure = dedupeStringList(parseTextList(form.relationship_pressure_text))
  const triggerPoints = normalized.trigger_points
  const calmingPoints = normalized.calming_points
  return {
    name: form.name.trim(),
    role_type: form.role_type,
    behavior_archetype: normalized.behavior_archetype,
    police_attitude: normalized.police_attitude,
    interaction_style: normalized.interaction_style,
    personality: form.personality.trim(),
    speaking_style: form.speaking_style.trim(),
    status: form.status,
    current_goal: normalized.current_goal.trim(),
    core_concern: normalized.core_concern.trim(),
    calming_points: calmingPoints,
    relationship_pressure: relationshipPressure,
    surface_stance: normalized.surface_stance.trim(),
    pressure_response: normalized.pressure_response.trim(),
    trigger_points: triggerPoints,
    scene_behavior_mode: normalized.scene_behavior_mode,
    emotion_level: normalized.emotion_level,
    cooperation_level: normalized.cooperation_level,
    risk_level: normalized.risk_level,
    clarity_level: normalized.clarity_level,
    init_emotion: normalized.init_emotion,
    init_trust: normalized.init_trust,
    init_risk: normalized.init_risk,
    init_expression_clarity: normalized.init_expression_clarity,
    impairment_state: normalized.impairment_state,
    iq_level: form.iq_level,
    eq_level: form.eq_level,
    lying_ability: form.lying_ability,
    knows_facts: legacyBoundary.knows_facts,
    does_not_know: dedupeStringList(parseTextList(form.does_not_know_text)),
    hidden_truths: legacyBoundary.hidden_truths,
    known_key_points: normalized.known_key_points,
    withheld_key_points: normalized.withheld_key_points,
    conflict_core: normalized.conflict_core,
    acceptable_outcomes: normalized.acceptable_outcomes,
    no_go_topics: normalized.no_go_topics,
    trigger_sources: normalized.trigger_sources,
    concerned_targets: normalized.concerned_targets,
    taboo_actions: normalized.taboo_actions,
    escalation_actions: normalized.escalation_actions,
    deescalation_conditions: normalized.deescalation_conditions,
    weakness: normalized.core_concern.trim(),
    current_need: normalized.current_goal.trim(),
    public_mask: normalized.surface_stance.trim(),
    authority_attitude: normalized.police_attitude.trim(),
    stress_response: normalized.pressure_response.trim(),
    private_drive: normalized.current_goal.trim(),
    trigger_topics: triggerPoints,
    case_id: form.scope === 'case' ? form.case_id : null,
    scene_ids: form.scope === 'case' ? form.scene_ids : [],
    primary_scene_id: form.scope === 'case' ? form.primary_scene_id : null,
  }
}

const saveRole = async () => {
  if (!form.name.trim()) {
    showToast('请输入角色名称')
    return
  }
  if (form.scope === 'case' && !form.case_id) {
    showToast('案件人物必须先选择所属案件')
    return
  }
  if (form.scope === 'case' && !form.scene_ids.length) {
    showToast('案件人物至少分配一个场景')
    return
  }
  if (form.scope === 'case' && form.primary_scene_id && !form.scene_ids.includes(form.primary_scene_id)) {
    showToast('主对话场景必须包含在已分配场景中')
    return
  }

  saving.value = true
  try {
    const payload = buildPayload()
    if (form.id) {
      await request.put(`/cases/roles/${form.id}`, payload, { _skipErrorToast: true } as any)
      showToast({ type: 'success', message: '角色已更新' })
    } else {
      await request.post('/cases/roles', payload, { _skipErrorToast: true } as any)
      showToast({ type: 'success', message: '角色已创建' })
    }
    closeDetail()
    await fetchRoles()
  } catch (error) {
    console.error('Save role error:', error)
    showToast('角色保存失败')
  } finally {
    saving.value = false
  }
}

const deleteRole = async () => {
  if (!form.id || deleting.value) return
  try {
    await showConfirmDialog({
      title: '确认删除',
      message:
        form.scope === 'case'
          ? '删除案件人物后，学员端将不再在对应场景中看到该人物。确定继续吗？'
          : '删除公共角色模板后，不会影响已存在案件，但模板本身将被移除。确定继续吗？',
    })
    deleting.value = true
    await request.delete(`/cases/roles/${form.id}`, { _skipErrorToast: true } as any)
    showToast({ type: 'success', message: '角色已删除' })
    closeDetail()
    await fetchRoles()
  } catch (error) {
    if (error) {
      console.error('Delete role error:', error)
      showToast('角色删除失败')
    }
  } finally {
    deleting.value = false
  }
}

onMounted(refreshPage)
</script>

<template>
  <div class="space-y-8 pb-20">
    <div class="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
      <div>
        <h2 class="text-xl font-bold text-slate-900">AI 训练角色库</h2>
        <p class="mt-2 max-w-3xl text-sm leading-7 text-slate-500">
          公共模板用于沉淀可复用人物；案件人物会同步进入案件并按你分配的场景出现在学员端。现在两类角色统一使用“行为原型 + 对警方态度 + 诉求 + 顾虑 + 触发点 + 安抚点”的轻量模板。
        </p>
      </div>
      <van-button type="primary" round icon="plus" class="!bg-[#1D3557] !border-none px-6" @click="openCreate">
        新增角色
      </van-button>
    </div>

    <div class="hero-note">
      <div class="hero-note__label">录入建议</div>
      <p class="hero-note__text">
        先判断“这个人一开口像哪种现场人物”，再补他眼下最怕什么、最想保住什么、什么会把他点燃、什么能把他稳住。
      </p>
    </div>

    <div class="grid grid-cols-1 gap-4 md:grid-cols-3">
      <div class="stat-card">
        <div class="stat-card__label">总角色数</div>
        <div class="stat-card__value">{{ roleCountSummary.total }}</div>
      </div>
      <div class="stat-card stat-card--sky">
        <div class="stat-card__label">公共模板</div>
        <div class="stat-card__value">{{ roleCountSummary.publicCount }}</div>
      </div>
      <div class="stat-card stat-card--emerald">
        <div class="stat-card__label">案件人物</div>
        <div class="stat-card__value">{{ roleCountSummary.caseCount }}</div>
      </div>
    </div>

    <div v-if="loading" class="flex justify-center py-20">
      <van-loading type="spinner" color="#1D3557" />
    </div>

    <div v-else-if="pageError" class="rounded-3xl border border-amber-200 bg-amber-50 px-6 py-12 text-center">
      <van-icon name="warning-o" size="32" class="text-amber-500" />
      <p class="mt-4 text-base font-bold text-amber-700">{{ pageError }}</p>
      <van-button plain type="primary" class="mt-5" @click="refreshPage">重新加载</van-button>
    </div>

    <div v-else-if="roles.length === 0" class="rounded-3xl border border-dashed border-slate-200 bg-white py-20 text-center">
      <van-icon name="friends-o" size="60" class="mb-4 text-slate-200" />
      <p class="text-base font-bold text-slate-500">暂无角色数据</p>
      <p class="mt-2 text-sm text-slate-400">先创建公共模板或案件人物，后续才能参与学员端训练。</p>
      <van-button type="primary" round class="!bg-[#1D3557] !border-none mt-6" @click="openCreate">
        新增第一个角色
      </van-button>
    </div>

    <div v-else class="space-y-10">
      <div v-for="(group, caseTitle) in groupedRoles" :key="caseTitle" class="space-y-5">
        <div class="flex items-center gap-4">
          <div class="h-px flex-1 bg-slate-100"></div>
          <h3 class="rounded-full border border-slate-100 bg-slate-50 px-4 py-1 text-xs font-black uppercase tracking-[0.2em] text-slate-400">
            {{ caseTitle }}
          </h3>
          <div class="h-px flex-1 bg-slate-100"></div>
        </div>

        <div class="grid grid-cols-1 gap-5 xl:grid-cols-3 md:grid-cols-2">
          <div
            v-for="role in group"
            :key="role.id"
            class="role-card group"
            @click="openDetail(role)"
          >
            <div class="flex items-start justify-between gap-3">
              <div class="flex items-center gap-3">
                <div class="role-card__avatar">
                  <van-icon name="user-o" size="22" class="text-slate-400" />
                </div>
                <div>
                  <h3 class="text-base font-bold text-slate-900">{{ role.name }}</h3>
                  <div class="mt-2 flex flex-wrap gap-2">
                    <span class="role-pill role-pill--slate">{{ role.role_type || '相关人员' }}</span>
                    <span :class="['role-pill', getInteractionStyleClass(role.behavior_archetype)]">
                      {{ role.behavior_archetype || '求助配合型' }}
                    </span>
                    <span class="role-pill role-pill--sky">
                      {{ role.police_attitude || role.authority_attitude || '试探观望' }}
                    </span>
                    <span class="role-pill" :class="role.is_public ? 'role-pill--sky' : 'role-pill--emerald'">
                      {{ role.is_public ? '公共模板' : '案件人物' }}
                    </span>
                  </div>
                </div>
              </div>
              <van-icon name="setting-o" class="text-slate-300 transition-colors group-hover:text-[#1D3557]" />
            </div>

            <div class="role-card__summary">
              <div class="role-card__eyebrow">人物驱动摘要</div>
              <p class="role-card__summary-text line-clamp-3">{{ buildRoleOverview(role) }}</p>
            </div>

            <div class="role-chip-list">
              <span v-for="chip in getRoleSummaryChips(role)" :key="chip" class="role-chip">{{ chip }}</span>
              <span v-if="!getRoleSummaryChips(role).length" class="role-chip role-chip--muted">待补充核心画像</span>
            </div>

            <div class="grid grid-cols-2 gap-4">
              <div class="space-y-1">
                <div class="flex items-center justify-between text-[10px] font-bold uppercase tracking-wider text-slate-400">
                  <span>情绪强度</span>
                  <span class="text-orange-500">{{ role.init_emotion }}%</span>
                </div>
                <div class="h-1 overflow-hidden rounded-full bg-slate-100">
                  <div class="h-full bg-orange-400" :style="{ width: `${role.init_emotion}%` }"></div>
                </div>
              </div>
              <div class="space-y-1">
                <div class="flex items-center justify-between text-[10px] font-bold uppercase tracking-wider text-slate-400">
                  <span>配合程度</span>
                  <span class="text-blue-500">{{ role.init_trust }}%</span>
                </div>
                <div class="h-1 overflow-hidden rounded-full bg-slate-100">
                  <div class="h-full bg-blue-500" :style="{ width: `${role.init_trust}%` }"></div>
                </div>
              </div>
            </div>

            <div class="role-card__footer">
              <span>{{ role.status || '正常' }}</span>
              <span v-if="!role.is_public">已分配 {{ role.scene_ids?.length || 0 }} 个场景</span>
            </div>
          </div>
        </div>
      </div>
    </div>

    <van-popup v-model:show="showDetail" position="right" :style="{ width: 'min(640px, 100vw)', height: '100%' }" class="p-8">
      <div class="flex h-full flex-col">
        <div class="mb-2 flex items-center justify-between">
          <h3 class="text-xl font-black text-[#1D3557]">{{ form.id ? '编辑角色' : '新增角色' }}</h3>
          <van-icon name="cross" class="cursor-pointer text-slate-300" @click="closeDetail" />
        </div>
        <p class="mb-6 text-xs leading-6 text-slate-400">
          案件人物会同步到案件人物清单，并按分配场景进入学员端；公共模板则保留为可复用角色模板。
        </p>

        <div class="flex-1 space-y-6 overflow-y-auto pr-2">
          <section class="section-card">
            <div class="section-card__header">
              <div>
                <div class="section-card__eyebrow">Scope</div>
                <h4 class="section-card__title">角色范围</h4>
              </div>
              <p class="section-card__hint">公共模板只做沉淀，案件人物才会进入具体训练场景。</p>
            </div>
            <div class="grid grid-cols-2 gap-3">
              <button
                type="button"
                class="scope-card"
                :class="{ active: form.scope === 'public', disabled: Boolean(form.id) }"
                :disabled="Boolean(form.id)"
                @click="form.scope = 'public'"
              >
                <span class="scope-card__title">公共模板</span>
                <span class="scope-card__desc">不会直接进入学员端，适合沉淀典型人物。</span>
              </button>
              <button
                type="button"
                class="scope-card"
                :class="{ active: form.scope === 'case', disabled: Boolean(form.id) }"
                :disabled="Boolean(form.id)"
                @click="form.scope = 'case'"
              >
                <span class="scope-card__title">案件人物</span>
                <span class="scope-card__desc">绑定案件并按场景进入学员端训练。</span>
              </button>
            </div>
            <p v-if="form.id" class="section-card__tip">编辑已有角色时，范围保持不变；如需迁移范围，建议新建后删除旧角色。</p>
          </section>

          <section v-if="form.scope === 'case'" class="section-card section-card--sky">
            <div class="section-card__header">
              <div>
                <div class="section-card__eyebrow">Scenes</div>
                <h4 class="section-card__title">案件与场景绑定</h4>
              </div>
              <p class="section-card__hint">只有被分配到场景的人物，学员端对话里才会真正出现。</p>
            </div>
            <div class="space-y-4">
              <div>
                <label class="field-label">所属案件</label>
                <select v-model="form.case_id" class="form-input">
                  <option :value="null">请选择所属案件</option>
                  <option v-for="item in roleOptions" :key="item.id" :value="item.id">{{ item.title }}</option>
                </select>
              </div>
              <div v-if="currentCaseScenes.length">
                <label class="field-label">出现场景</label>
                <div class="scene-grid">
                  <label v-for="scene in currentCaseScenes" :key="scene.id" class="scene-option">
                    <input v-model="form.scene_ids" type="checkbox" :value="scene.id" />
                    <span>{{ scene.name }}</span>
                  </label>
                </div>
              </div>
              <div v-else-if="form.case_id" class="empty-inline-note">该案件下还没有可分配场景，请先回案件页生成或维护场景。</div>
              <div v-if="form.scene_ids.length">
                <label class="field-label">主对话场景</label>
                <select v-model="form.primary_scene_id" class="form-input">
                  <option :value="null">不指定，由系统自动决策</option>
                  <option v-for="scene in currentCaseScenes.filter((item: any) => form.scene_ids.includes(item.id))" :key="scene.id" :value="scene.id">
                    {{ scene.name }}
                  </option>
                </select>
              </div>
            </div>
          </section>

          <section class="section-card">
            <div class="section-card__header">
              <div>
                <div class="section-card__eyebrow">Basics</div>
                <h4 class="section-card__title">基础信息</h4>
              </div>
              <p class="section-card__hint">先定身份、状态和开场原型，再去补他眼下的真实顾虑。</p>
            </div>
            <div class="space-y-4">
              <div>
                <label class="field-label">角色名称</label>
                <input v-model="form.name" type="text" class="form-input" placeholder="请输入角色名称" />
              </div>
              <div class="grid grid-cols-1 gap-4 md:grid-cols-3">
                <div>
                  <label class="field-label">身份类别</label>
                  <select v-model="form.role_type" class="form-input">
                    <option v-for="item in roleIdentityOptions" :key="item" :value="item">{{ item }}</option>
                  </select>
                </div>
                <div>
                  <label class="field-label">行为原型</label>
                  <select v-model="form.behavior_archetype" class="form-input">
                    <option v-for="item in behaviorArchetypeOptions" :key="item.value" :value="item.value">{{ item.value }}</option>
                  </select>
                </div>
                <div>
                  <label class="field-label">状态</label>
                  <select v-model="form.status" class="form-input">
                    <option v-for="item in statusOptions" :key="item" :value="item">{{ item }}</option>
                  </select>
                </div>
              </div>
              <div>
                <label class="field-label">对警方态度</label>
                <select v-model="form.police_attitude" class="form-input">
                  <option v-for="item in policeAttitudeOptions" :key="item.value" :value="item.value">{{ item.value }}</option>
                </select>
              </div>
              <div>
                <label class="field-label">场景行为模式</label>
                <select v-model="form.scene_behavior_mode" class="form-input">
                  <option v-for="item in sceneBehaviorModeOptions" :key="item.value" :value="item.value">{{ item.value }}</option>
                </select>
              </div>
              <div>
                <label class="field-label">开场原型提示</label>
                <div class="rounded-2xl border border-slate-100 bg-slate-50 px-4 py-3 text-sm leading-6 text-slate-600">
                  {{ roleDraftProfile.normalized.behavior_archetype }}：{{ buildBehaviorSummary(roleDraftProfile.normalized).join('；') || '先补充关键模板字段' }}
                </div>
              </div>
            </div>
          </section>

          <section class="section-card section-card--indigo">
            <div class="section-card__header">
              <div>
                <div class="section-card__eyebrow">Persona</div>
                <h4 class="section-card__title">简化角色模板</h4>
              </div>
              <p class="section-card__hint">这些字段直接决定 AI 的开场状态、情绪触发点和松口条件。</p>
            </div>
            <div class="grid grid-cols-1 gap-4">
              <div>
                <label class="field-label">当前诉求</label>
                <textarea v-model="form.current_goal" rows="3" class="form-textarea" placeholder="例如：先别把责任全落自己头上，不要影响孩子和赔偿"></textarea>
              </div>
              <div>
                <label class="field-label">最担心什么后果</label>
                <textarea v-model="form.core_concern" rows="3" class="form-textarea" placeholder="例如：最怕被认定先动手，最怕单位和家里都知道"></textarea>
              </div>
              <div>
                <label class="field-label">敏感触发点</label>
                <textarea v-model="form.trigger_points_text" rows="4" class="form-textarea" placeholder="每行一个，例如：孩子会不会被牵连&#10;赔偿金额&#10;谁先动手"></textarea>
              </div>
              <div>
                <label class="field-label">安抚点</label>
                <textarea v-model="form.calming_points_text" rows="4" class="form-textarea" placeholder="每行一个，例如：先把经过说完&#10;给明确处理步骤&#10;降低围观刺激"></textarea>
              </div>
            </div>
          </section>

          <section class="section-card section-card--amber">
            <div class="section-card__header">
              <div>
                <div class="section-card__eyebrow">State</div>
                <h4 class="section-card__title">开场状态与高级补充</h4>
              </div>
              <p class="section-card__hint">四轴状态会直接影响学生端反馈；信息边界则跟随当前场景行为模式动态切换。</p>
            </div>
            <div class="rounded-2xl border border-amber-200 bg-white/80 px-4 py-3 text-xs leading-6 text-amber-800">
              {{ sceneBehaviorModeOptions.find((item) => item.value === form.scene_behavior_mode)?.summary || '先选择当前场景的行为模式，信息边界会自动切换。' }}
            </div>
            <div class="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-4">
              <div>
                <label class="field-label">情绪强度</label>
                <select v-model="form.emotion_level" class="form-input">
                  <option v-for="item in stateLevelOptions" :key="item.value" :value="item.value">{{ item.label }}</option>
                </select>
              </div>
              <div>
                <label class="field-label">配合程度</label>
                <select v-model="form.cooperation_level" class="form-input">
                  <option v-for="item in stateLevelOptions" :key="item.value" :value="item.value">{{ item.label }}</option>
                </select>
              </div>
              <div>
                <label class="field-label">失控风险</label>
                <select v-model="form.risk_level" class="form-input">
                  <option v-for="item in stateLevelOptions" :key="item.value" :value="item.value">{{ item.label }}</option>
                </select>
              </div>
              <div>
                <label class="field-label">表达清晰度</label>
                <select v-model="form.clarity_level" class="form-input">
                  <option v-for="item in stateLevelOptions" :key="item.value" :value="item.value">{{ item.label }}</option>
                </select>
              </div>
            </div>
            <div class="rounded-2xl border border-amber-200 bg-white/80 px-4 py-3 text-xs leading-6 text-amber-800">
              高情绪 + 高风险会更容易抢话、冲动或升级；高清晰度则更容易在学生问到位时给出可用信息。
            </div>
            <details class="rounded-2xl border border-amber-200 bg-white/80 px-4 py-3">
              <summary class="cursor-pointer text-sm font-bold text-amber-900">高级补充字段</summary>
              <div class="mt-4 grid grid-cols-1 gap-4 md:grid-cols-2">
                <div>
                  <label class="field-label">语言风格</label>
                  <input v-model="form.speaking_style" type="text" class="form-input" placeholder="例如：嘴硬、碎嘴、急促、阴阳怪气、表面冷静" />
                </div>
                <div>
                  <label class="field-label">性格底色</label>
                  <textarea v-model="form.personality" rows="3" class="form-textarea" placeholder="不填则按行为原型自动生成"></textarea>
                </div>
                <div>
                  <label class="field-label">关系 / 现实压力</label>
                  <textarea v-model="form.relationship_pressure_text" rows="4" class="form-textarea" placeholder="每行一个，例如：护着儿子&#10;怕邻里继续报复&#10;担心赔钱后日子过不下去"></textarea>
                </div>
                <div>
                  <label class="field-label">自定义承压反应</label>
                  <textarea v-model="form.pressure_response" rows="4" class="form-textarea" placeholder="留空则按行为原型自动生成"></textarea>
                </div>
                <div v-if="form.scene_behavior_mode === '管控型'" class="md:col-span-2">
                  <label class="field-label">酒精 / 药物 / 精神状态说明</label>
                  <textarea v-model="form.impairment_state" rows="3" class="form-textarea" placeholder="例如：饮酒明显，说话重复，步态不稳；或疑似受药物影响，判断力下降。"></textarea>
                </div>
                <div>
                  <label class="field-label">IQ 等级</label>
                  <select v-model="form.iq_level" class="form-input">
                    <option v-for="item in levelOptions" :key="item" :value="item">{{ item }}</option>
                  </select>
                </div>
                <div>
                  <label class="field-label">EQ 等级</label>
                  <select v-model="form.eq_level" class="form-input">
                    <option v-for="item in levelOptions" :key="item" :value="item">{{ item }}</option>
                  </select>
                </div>
                <div>
                  <label class="field-label">撒谎能力</label>
                  <select v-model="form.lying_ability" class="form-input">
                    <option v-for="item in lieOptions" :key="item" :value="item">{{ item }}</option>
                  </select>
                </div>
              </div>
            </details>
          </section>

          <section class="section-card section-card--emerald">
            <div class="flex items-center justify-between gap-3">
              <div>
                <div class="section-card__eyebrow">Preview</div>
                <h4 class="section-card__title">实时预览</h4>
              </div>
              <van-button plain size="small" class="!border-[#1D3557] !text-[#1D3557]" @click="generatePersonaSummary">
                一键写入摘要
              </van-button>
            </div>

            <div class="preview-panel">
              <div class="preview-panel__header">
                <div>
                  <div class="preview-panel__name">{{ form.name || '未命名角色' }}</div>
                  <div class="preview-panel__meta">
                    <span>{{ form.role_type || '相关人员' }}</span>
                    <span>{{ roleDraftProfile.normalized.behavior_archetype || '求助配合型' }}</span>
                    <span>{{ roleDraftProfile.normalized.police_attitude || '试探观望' }}</span>
                    <span>{{ roleDraftProfile.normalized.scene_behavior_mode || '核查取证型' }}</span>
                    <span>{{ previewStateLabel }}</span>
                    <span>情绪 {{ roleDraftProfile.normalized.emotion_level }}</span>
                    <span>配合 {{ roleDraftProfile.normalized.cooperation_level }}</span>
                    <span>风险 {{ roleDraftProfile.normalized.risk_level }}</span>
                    <span>清晰 {{ roleDraftProfile.normalized.clarity_level }}</span>
                  </div>
                </div>
              </div>

              <div class="preview-block">
                <div class="preview-block__label">AI 会把这个人理解为</div>
                <p class="preview-block__text">{{ roleDraftProfile.summaryText }}</p>
              </div>

              <div class="preview-grid">
                <div class="preview-card">
                  <div class="preview-card__title">诉求与顾虑</div>
                  <p class="preview-quote">当前诉求：{{ roleDraftProfile.normalized.current_goal || '暂未填写' }}</p>
                  <p class="preview-quote preview-quote--muted">核心顾虑：{{ roleDraftProfile.normalized.core_concern || '暂未填写' }}</p>
                  <p class="preview-quote preview-quote--muted">开场口径：{{ roleDraftProfile.normalized.surface_stance || '系统会按行为原型自动生成' }}</p>
                </div>
                <div class="preview-card">
                  <div class="preview-card__title">承压与触发</div>
                  <p class="preview-quote">{{ roleDraftProfile.normalized.pressure_response || '系统会按行为原型自动生成承压反应' }}</p>
                  <div class="preview-tags mt-3">
                    <span v-for="item in roleDraftProfile.triggerPoints" :key="item" class="preview-tag preview-tag--amber">{{ item }}</span>
                    <span v-if="!roleDraftProfile.triggerPoints.length" class="preview-empty">还没填敏感触发点</span>
                  </div>
                </div>
              </div>

              <div class="preview-card">
                <div class="preview-card__title">安抚与关系压力</div>
                <div class="preview-tags">
                  <span v-for="item in roleDraftProfile.calmingPoints" :key="item" class="preview-tag preview-tag--emerald">{{ item }}</span>
                  <span v-for="item in roleDraftProfile.relationshipPressure" :key="item" class="preview-tag preview-tag--blue">{{ item }}</span>
                  <span v-if="!roleDraftProfile.calmingPoints.length && !roleDraftProfile.relationshipPressure.length" class="preview-empty">还没填安抚点或关系压力</span>
                </div>
              </div>

              <div class="preview-grid">
                <div v-for="field in roleDraftProfile.boundaryGroups" :key="field.key" class="preview-card">
                  <div class="preview-card__title">{{ field.label }}</div>
                  <ul class="preview-list">
                    <li v-for="item in field.items" :key="item">{{ item }}</li>
                    <li v-if="!field.items.length">当前还没有补充这一组场景边界。</li>
                  </ul>
                </div>
              </div>

              <div class="preview-block">
                <div class="preview-block__label">预计突破口</div>
                <ul class="preview-list">
                  <li v-for="item in previewBreakthroughs" :key="item">{{ item }}</li>
                  <li v-if="!previewBreakthroughs.length">建议先补“最担心的后果”“安抚点”或“敏感触发点”。</li>
                </ul>
              </div>

              <div v-if="roleDraftProfile.contradictions.length" class="preview-block">
                <div class="preview-block__label">人物矛盾感</div>
                <ul class="preview-list">
                  <li v-for="item in roleDraftProfile.contradictions" :key="item">{{ item }}</li>
                </ul>
              </div>
            </div>
          </section>

          <section class="section-card">
            <div class="section-card__header">
              <div>
                <div class="section-card__eyebrow">Facts</div>
                <h4 class="section-card__title">信息边界</h4>
              </div>
              <p class="section-card__hint">不再固定成三种框，而是跟着当前场景模式走。管理员只补学生真正需要碰到的边界即可。</p>
            </div>
            <div class="space-y-4">
              <div v-for="field in currentBoundaryFields" :key="field.key">
                <label class="field-label">{{ field.label }}</label>
                <textarea
                  v-model="form[field.modelKey]"
                  rows="4"
                  class="form-textarea"
                  :placeholder="field.placeholder"
                ></textarea>
              </div>
              <div>
                <label class="field-label">当前确实不知道的点</label>
                <textarea v-model="form.does_not_know_text" rows="4" class="form-textarea" placeholder="每行一条，例如：我不知道屋里后来到底是谁先拿了东西。这个字段作为辅助补充，不参与场景模式切换。"></textarea>
              </div>
            </div>
          </section>
        </div>

        <div class="flex gap-3 border-t border-slate-100 pt-6">
          <van-button plain block class="!border-slate-200 !text-slate-500 h-11" @click="closeDetail">取消</van-button>
          <van-button v-if="form.id" plain block type="danger" class="h-11" :loading="deleting" @click="deleteRole">
            删除
          </van-button>
          <van-button block type="primary" class="!bg-[#1D3557] !border-none h-11" :loading="saving" @click="saveRole">
            保存
          </van-button>
        </div>
      </div>
    </van-popup>
  </div>
</template>

<style scoped>
.line-clamp-3 {
  display: -webkit-box;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.hero-note {
  border: 1px solid #dbeafe;
  border-radius: 28px;
  background:
    radial-gradient(circle at top right, rgba(191, 219, 254, 0.42), transparent 35%),
    linear-gradient(135deg, #ffffff 0%, #eff6ff 52%, #f8fafc 100%);
  padding: 18px 20px;
}

.hero-note__label {
  font-size: 11px;
  font-weight: 900;
  letter-spacing: 0.16em;
  text-transform: uppercase;
  color: #2563eb;
}

.hero-note__text {
  margin-top: 8px;
  max-width: 920px;
  font-size: 14px;
  line-height: 1.8;
  color: #475569;
}

.stat-card {
  border: 1px solid #e2e8f0;
  border-radius: 24px;
  background: linear-gradient(180deg, #ffffff 0%, #f8fafc 100%);
  padding: 18px;
}

.stat-card--sky {
  background: linear-gradient(180deg, #f8fbff 0%, #eff6ff 100%);
  border-color: #dbeafe;
}

.stat-card--emerald {
  background: linear-gradient(180deg, #f0fdf4 0%, #ecfdf5 100%);
  border-color: #bbf7d0;
}

.stat-card__label {
  font-size: 11px;
  font-weight: 900;
  letter-spacing: 0.16em;
  text-transform: uppercase;
  color: #94a3b8;
}

.stat-card__value {
  margin-top: 10px;
  font-size: 30px;
  line-height: 1;
  font-weight: 900;
  color: #0f172a;
}

.role-card {
  display: flex;
  flex-direction: column;
  gap: 16px;
  cursor: pointer;
  border: 1px solid #e2e8f0;
  border-radius: 28px;
  background: linear-gradient(180deg, #ffffff 0%, #f8fafc 100%);
  padding: 22px;
  box-shadow: 0 16px 40px rgba(15, 23, 42, 0.04);
  transition: transform 0.2s ease, box-shadow 0.2s ease, border-color 0.2s ease;
}

.role-card:hover {
  transform: translateY(-2px);
  border-color: #cbd5e1;
  box-shadow: 0 22px 48px rgba(15, 23, 42, 0.08);
}

.role-card__avatar {
  display: flex;
  width: 48px;
  height: 48px;
  align-items: center;
  justify-content: center;
  border-radius: 18px;
  border: 1px solid #e2e8f0;
  background: #f8fafc;
}

.role-pill {
  display: inline-flex;
  align-items: center;
  border-radius: 999px;
  padding: 4px 10px;
  font-size: 11px;
  font-weight: 800;
}

.role-pill--slate {
  background: #e2e8f0;
  color: #334155;
}

.role-pill--sky {
  background: #dbeafe;
  color: #1d4ed8;
}

.role-pill--emerald {
  background: #d1fae5;
  color: #047857;
}

.role-card__summary {
  border-radius: 20px;
  border: 1px solid #e2e8f0;
  background: rgba(255, 255, 255, 0.88);
  padding: 14px;
}

.role-card__eyebrow {
  font-size: 10px;
  font-weight: 900;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  color: #94a3b8;
}

.role-card__summary-text {
  margin-top: 8px;
  font-size: 13px;
  line-height: 1.8;
  color: #334155;
}

.role-chip-list {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.role-chip {
  display: inline-flex;
  align-items: center;
  border-radius: 999px;
  background: #eff6ff;
  color: #1d4ed8;
  padding: 6px 10px;
  font-size: 11px;
  font-weight: 700;
}

.role-chip--muted {
  background: #f1f5f9;
  color: #64748b;
}

.role-card__footer {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  border-radius: 16px;
  background: #f8fafc;
  padding: 12px 14px;
  font-size: 12px;
  font-weight: 700;
  color: #64748b;
}

.section-card {
  border: 1px solid #e2e8f0;
  border-radius: 26px;
  background: linear-gradient(180deg, #ffffff 0%, #f8fafc 100%);
  padding: 18px;
}

.section-card--sky {
  background: linear-gradient(180deg, #f8fbff 0%, #eff6ff 100%);
  border-color: #dbeafe;
}

.section-card--indigo {
  background: linear-gradient(180deg, #eef2ff 0%, #f8fafc 100%);
  border-color: #c7d2fe;
}

.section-card--amber {
  background: linear-gradient(180deg, #fffaf0 0%, #fffbeb 100%);
  border-color: #fde68a;
}

.section-card--emerald {
  background: linear-gradient(180deg, #f0fdf4 0%, #f8fafc 100%);
  border-color: #bbf7d0;
}

.section-card__header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 16px;
}

.section-card__eyebrow {
  font-size: 11px;
  font-weight: 900;
  letter-spacing: 0.16em;
  text-transform: uppercase;
  color: #64748b;
}

.section-card__title {
  margin-top: 4px;
  font-size: 20px;
  line-height: 1.25;
  font-weight: 900;
  color: #0f172a;
}

.section-card__hint {
  max-width: 260px;
  border-radius: 18px;
  background: rgba(255, 255, 255, 0.78);
  padding: 10px 12px;
  font-size: 12px;
  line-height: 1.6;
  color: #64748b;
}

.section-card__tip {
  margin-top: 12px;
  font-size: 12px;
  line-height: 1.7;
  color: #64748b;
}

.scope-card {
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding: 16px;
  border-radius: 18px;
  border: 1px solid #e2e8f0;
  background: rgba(255, 255, 255, 0.84);
  text-align: left;
  transition: all 0.2s ease;
}

.scope-card.active {
  border-color: #1d3557;
  background: #f4f8fd;
  box-shadow: 0 12px 30px rgba(29, 53, 87, 0.08);
}

.scope-card.disabled {
  cursor: not-allowed;
  opacity: 0.7;
}

.scope-card__title {
  font-size: 14px;
  font-weight: 800;
  color: #1f2937;
}

.scope-card__desc {
  font-size: 12px;
  line-height: 1.7;
  color: #64748b;
}

.field-label {
  display: block;
  margin-bottom: 8px;
  font-size: 13px;
  font-weight: 800;
  color: #334155;
}

.form-input,
.form-textarea {
  width: 100%;
  border: 1px solid #dbe3ee;
  border-radius: 16px;
  padding: 12px 14px;
  font-size: 14px;
  color: #0f172a;
  outline: none;
  background: #fff;
  transition: border-color 0.2s ease, box-shadow 0.2s ease;
}

.form-input:focus,
.form-textarea:focus {
  border-color: #93b4d6;
  box-shadow: 0 0 0 4px rgba(69, 123, 157, 0.12);
}

.form-textarea {
  resize: vertical;
  min-height: 88px;
}

.scene-grid {
  display: grid;
  gap: 10px;
}

.scene-option {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 12px;
  border-radius: 14px;
  background: rgba(255, 255, 255, 0.86);
  border: 1px solid #dbeafe;
  font-size: 13px;
  color: #475569;
}

.empty-inline-note {
  border: 1px dashed #bfdbfe;
  border-radius: 18px;
  background: rgba(255, 255, 255, 0.74);
  padding: 14px;
  font-size: 12px;
  line-height: 1.7;
  color: #475569;
}

.slider-head {
  display: flex;
  justify-content: space-between;
  margin-bottom: 10px;
  font-size: 13px;
  font-weight: 700;
  color: #475569;
}

.preview-panel {
  display: flex;
  flex-direction: column;
  gap: 14px;
  padding: 16px;
  border-radius: 22px;
  border: 1px solid #bbf7d0;
  background:
    radial-gradient(circle at top right, rgba(34, 197, 94, 0.12), transparent 30%),
    linear-gradient(180deg, #ffffff 0%, #f6fef8 100%);
}

.preview-panel__header {
  display: flex;
  justify-content: space-between;
  gap: 12px;
}

.preview-panel__name {
  font-size: 18px;
  font-weight: 900;
  color: #0f172a;
}

.preview-panel__meta {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 8px;
  font-size: 11px;
  font-weight: 700;
  color: #365d4a;
}

.preview-panel__meta span {
  padding: 4px 8px;
  border-radius: 999px;
  background: rgba(15, 118, 110, 0.08);
}

.preview-grid {
  display: grid;
  gap: 12px;
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.preview-card,
.preview-block {
  border-radius: 18px;
  border: 1px solid #dbe5dd;
  background: rgba(255, 255, 255, 0.92);
  padding: 14px;
}

.preview-card__title,
.preview-block__label {
  margin-bottom: 10px;
  font-size: 11px;
  font-weight: 900;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: #64748b;
}

.preview-block__text {
  font-size: 14px;
  line-height: 1.8;
  color: #0f172a;
}

.preview-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.preview-tag {
  display: inline-flex;
  align-items: center;
  padding: 6px 10px;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 700;
}

.preview-tag--blue {
  background: #e0f2fe;
  color: #0369a1;
}

.preview-tag--amber {
  background: #fef3c7;
  color: #b45309;
}

.preview-tag--emerald {
  background: #dcfce7;
  color: #047857;
}

.preview-empty {
  font-size: 12px;
  color: #94a3b8;
}

.preview-quote {
  font-size: 13px;
  line-height: 1.8;
  color: #0f172a;
}

.preview-quote--muted {
  margin-top: 6px;
  color: #475569;
}

.preview-list {
  display: grid;
  gap: 8px;
  padding-left: 18px;
  font-size: 13px;
  line-height: 1.7;
  color: #334155;
}

@media (max-width: 960px) {
  .section-card__header {
    flex-direction: column;
  }

  .section-card__hint {
    max-width: none;
  }

  .preview-grid {
    grid-template-columns: 1fr;
  }
}
</style>
