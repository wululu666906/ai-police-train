import {
  behaviorArchetypeOptions,
  buildLegacyInfoBoundary,
  dedupeStringList,
  getBehaviorArchetypeMeta,
  getSceneBoundaryFields,
  normalizeBehaviorTemplate,
  parseTextList,
  stringifyTextList,
} from './personaTemplate'

export const openingPresetOptions = [
  { value: 'calm_cooperative', label: '冷静配合', summary: '开场较稳，愿意配合核实。' },
  { value: 'cautious_guarded', label: '谨慎观望', summary: '先试探警方掌握多少，再决定说多少。' },
  { value: 'emotional_venting', label: '情绪宣泄', summary: '情绪先于事实，需要先被听见。' },
  { value: 'defensive_evasive', label: '防御回避', summary: '先自保、切责任，回避关键点。' },
  { value: 'confrontational', label: '对抗顶撞', summary: '嘴硬反问，不愿被压着走。' },
  { value: 'intoxicated_chaotic', label: '醉酒失控', summary: '表达破碎，现场管控优先。' },
  { value: 'withdrawn', label: '封闭拒答', summary: '意愿低、表达少，需先稳关系。' },
] as const

export type OpeningPresetValue = (typeof openingPresetOptions)[number]['value']

export const openingPresetScores: Record<OpeningPresetValue, { init_emotion: number; init_trust: number; init_risk: number; init_expression_clarity: number }> = {
  calm_cooperative: { init_emotion: 42, init_trust: 58, init_risk: 24, init_expression_clarity: 78 },
  cautious_guarded: { init_emotion: 54, init_trust: 28, init_risk: 34, init_expression_clarity: 74 },
  emotional_venting: { init_emotion: 76, init_trust: 38, init_risk: 56, init_expression_clarity: 54 },
  defensive_evasive: { init_emotion: 62, init_trust: 20, init_risk: 44, init_expression_clarity: 70 },
  confrontational: { init_emotion: 78, init_trust: 14, init_risk: 72, init_expression_clarity: 68 },
  intoxicated_chaotic: { init_emotion: 86, init_trust: 10, init_risk: 88, init_expression_clarity: 22 },
  withdrawn: { init_emotion: 80, init_trust: 18, init_risk: 82, init_expression_clarity: 28 },
}

const archetypeDefaultPreset: Record<string, OpeningPresetValue> = {
  求助配合型: 'calm_cooperative',
  委屈宣泄型: 'emotional_venting',
  谨慎回避型: 'cautious_guarded',
  防御切责型: 'defensive_evasive',
  强硬对抗型: 'confrontational',
  醉酒失控型: 'intoxicated_chaotic',
  绝望封闭型: 'withdrawn',
  围观起哄型: 'confrontational',
  创伤受害型: 'emotional_venting',
  精神危机型: 'intoxicated_chaotic',
  利益算计型: 'defensive_evasive',
  权威敏感型: 'confrontational',
  沉默恐惧型: 'withdrawn',
  过度依赖型: 'emotional_venting',
}

export const trainingFocusOptions = [
  { value: 'intake', label: '接警研判', behavior_mode: '核查取证型' },
  { value: 'onsite', label: '现场处置', behavior_mode: '核查取证型' },
  { value: 'interview', label: '重点问询', behavior_mode: '核查取证型' },
  { value: 'mediation', label: '调解稳控', behavior_mode: '调解型' },
  { value: 'crisis', label: '危机干预', behavior_mode: '危机干预型' },
  { value: 'control', label: '现场管控', behavior_mode: '管控型' },
] as const

export type TrainingFocusValue = (typeof trainingFocusOptions)[number]['value']

export const boundaryFieldKeysByMode: Record<string, [string, string]> = {
  核查取证型: ['known_key_points', 'withheld_key_points'],
  调解型: ['conflict_core', 'acceptable_outcomes'],
  危机干预型: ['trigger_sources', 'concerned_targets'],
  管控型: ['escalation_actions', 'deescalation_conditions'],
}

export const boundaryFieldLabelsByMode: Record<string, [string, string]> = {
  核查取证型: ['可核实事实', '暂不主动说'],
  调解型: ['矛盾焦点', '可接受结果'],
  危机干预型: ['刺激源', '牵挂对象'],
  管控型: ['升级动作', '降刺激条件'],
}

export const inferOpeningPreset = (source: any): OpeningPresetValue => {
  const explicit = String(source?.opening_preset || '').trim() as OpeningPresetValue
  if (openingPresetScores[explicit]) return explicit
  const archetype = String(source?.behavior_archetype || '').trim()
  if (archetypeDefaultPreset[archetype]) return archetypeDefaultPreset[archetype]
  return 'calm_cooperative'
}

export const trainingFocusToBehaviorMode = (focus: string) =>
  trainingFocusOptions.find((item) => item.value === focus)?.behavior_mode || '核查取证型'

export const inferTrainingFocus = (sceneName = '', behaviorMode = '') => {
  const name = String(sceneName || '')
  if (/接警|110|报警/.test(name)) return 'intake'
  if (/调解|协商|纠纷/.test(name)) return 'mediation'
  if (/轻生|危机|干预|跳楼/.test(name)) return 'crisis'
  if (/醉酒|管控|围观|控制/.test(name)) return 'control'
  if (/问询|询问|笔录|讯问/.test(name)) return 'interview'
  if (/现场|处置|处警/.test(name)) return 'onsite'
  if (behaviorMode === '调解型') return 'mediation'
  if (behaviorMode === '危机干预型') return 'crisis'
  if (behaviorMode === '管控型') return 'control'
  return 'interview'
}

export const personToRoleCompact = (person: any, sceneBehaviorMode = '核查取证型') => {
  const normalized = normalizeBehaviorTemplate({ ...person, scene_behavior_mode: sceneBehaviorMode })
  const mode = normalized.scene_behavior_mode || sceneBehaviorMode
  const [primaryKey, secondaryKey] = boundaryFieldKeysByMode[mode] || boundaryFieldKeysByMode['核查取证型']
  const [primaryLabel, secondaryLabel] = boundaryFieldLabelsByMode[mode] || boundaryFieldLabelsByMode['核查取证型']

  return {
    name: String(person?.name || '').trim(),
    role_type: String(person?.role_type || person?.role || '相关人员').trim() || '相关人员',
    status: String(person?.status || '正常').trim() || '正常',
    behavior_archetype: normalized.behavior_archetype,
    opening_preset: inferOpeningPreset(person),
    current_goal: normalized.current_goal,
    core_concern: normalized.core_concern,
    trigger_points: normalized.trigger_points.slice(0, 3),
    calming_points: normalized.calming_points.slice(0, 3),
    cannot_answer: dedupeStringList(person?.cannot_answer || person?.does_not_know).slice(0, 6),
    boundary_primary: dedupeStringList(normalized[primaryKey as keyof typeof normalized]).slice(0, 6),
    boundary_secondary: dedupeStringList(normalized[secondaryKey as keyof typeof normalized]).slice(0, 6),
    impairment_state: normalized.impairment_state,
    relationship_pressure: normalized.relationship_pressure.slice(0, 2),
    surface_stance: normalized.surface_stance,
    pressure_response: normalized.pressure_response,
    _boundary_primary_key: primaryKey,
    _boundary_secondary_key: secondaryKey,
    _boundary_primary_label: primaryLabel,
    _boundary_secondary_label: secondaryLabel,
  }
}

export const expandRoleCompactToPerson = (compact: any, sceneBehaviorMode = '核查取证型'): Record<string, any> => {
  const mode = sceneBehaviorMode || '核查取证型'
  const [primaryKey, secondaryKey] = boundaryFieldKeysByMode[mode] || boundaryFieldKeysByMode['核查取证型']
  const archetypeMeta = getBehaviorArchetypeMeta(compact?.behavior_archetype)
  const preset = inferOpeningPreset(compact)
  const scores = openingPresetScores[preset]

  const payload: Record<string, any> = {
    name: String(compact?.name || '').trim(),
    role_type: String(compact?.role_type || '相关人员').trim() || '相关人员',
    status: String(compact?.status || '正常').trim() || '正常',
    behavior_archetype: String(compact?.behavior_archetype || archetypeMeta.value).trim() || archetypeMeta.value,
    opening_preset: preset,
    current_goal: String(compact?.current_goal || '').trim(),
    core_concern: String(compact?.core_concern || '').trim(),
    trigger_points: dedupeStringList(compact?.trigger_points).slice(0, 3),
    calming_points: dedupeStringList(compact?.calming_points).slice(0, 3),
    cannot_answer: dedupeStringList(compact?.cannot_answer).slice(0, 6),
    does_not_know: dedupeStringList(compact?.cannot_answer).slice(0, 6),
    scene_behavior_mode: mode,
    impairment_state: String(compact?.impairment_state || '').trim(),
    relationship_pressure: dedupeStringList(compact?.relationship_pressure).slice(0, 2),
    surface_stance: String(compact?.surface_stance || archetypeMeta.surface_stance || '').trim(),
    pressure_response: String(compact?.pressure_response || archetypeMeta.pressure_response || '').trim(),
    interaction_style: archetypeMeta.interaction_style,
    police_attitude: archetypeMeta.police_attitude,
    personality: archetypeMeta.personality,
    speaking_style: archetypeMeta.speaking_style,
    init_emotion: scores.init_emotion,
    init_trust: scores.init_trust,
    init_risk: scores.init_risk,
    init_expression_clarity: scores.init_expression_clarity,
    compact_v1: true,
  }

  payload[primaryKey] = dedupeStringList(compact?.boundary_primary)
  payload[secondaryKey] = dedupeStringList(compact?.boundary_secondary)

  const legacy = buildLegacyInfoBoundary(payload)
  payload.knows_facts = legacy.knows_facts
  payload.hidden_truths = legacy.hidden_truths
  payload.does_not_know = dedupeStringList(compact?.cannot_answer).slice(0, 6)

  const normalized = normalizeBehaviorTemplate(payload)
  return {
    ...normalized,
    name: payload.name,
    role_type: payload.role_type,
    status: payload.status,
    opening_preset: payload.opening_preset,
    does_not_know: payload.does_not_know,
    cannot_answer: payload.cannot_answer,
    compact_v1: true,
  } as Record<string, any>
}

export const buildRoleCompactSummary = (compact: any) => {
  const parts = [
    compact?.behavior_archetype ? `原型 ${compact.behavior_archetype}` : '',
    compact?.current_goal ? `诉求 ${compact.current_goal}` : '',
    compact?.core_concern ? `顾虑 ${compact.core_concern}` : '',
  ].filter(Boolean)
  return parts.slice(0, 3)
}

export const listToTextarea = (value: any) => stringifyTextList(value)
export const textareaToList = (value: string, limit = 0) => {
  const items = parseTextList(value)
  return limit ? items.slice(0, limit) : items
}

export const sceneToCompactView = (scene: any) => {
  // Admin-visible scene fields only; training_focus / behavior_mode are inferred internally.
  const stages = Array.isArray(scene?.stages) ? scene.stages : Array.isArray(scene?.stagesModel) ? scene.stagesModel : []
  const stageMeta = stages[0]?.meta || {}
  const behaviorMode =
    String(scene?.behavior_mode || stageMeta?.behavior_mode || '').trim() ||
    trainingFocusToBehaviorMode(String(scene?.training_focus || stageMeta?.training_focus || inferTrainingFocus(scene?.name || scene?.scene_name || '', scene?.behavior_mode || '')))

  const cards: any[] = []
  if (Array.isArray(scene?.assessmentPointsModel)) {
    cards.push(...scene.assessmentPointsModel.map((point: any) => ({ id: point.id, label: point.label, content: point.content })))
  } else {
    for (const stage of stages) {
      for (const point of stage?.assessment_points || []) {
        if (point?.label) cards.push({ id: point.id, label: point.label, content: point.content || '' })
      }
    }
  }

  return {
    name: String(scene?.name || scene?.scene_name || '').trim(),
    training_focus: String(scene?.training_focus || stageMeta?.training_focus || inferTrainingFocus(scene?.name || '', behaviorMode)),
    behavior_mode: behaviorMode,
    difficulty: String(scene?.difficulty || '中等').trim() || '中等',
    description: String(scene?.description || scene?.scene_description || '').trim(),
    dispatch_brief: String(scene?.dispatch_brief || '').trim(),
    first_impression: String(scene?.first_impression || '').trim(),
    role_names: scene?.role_names || [],
    primary_role_name: String(scene?.primary_role_name || '').trim(),
    assessment_points: cards,
  }
}

export { behaviorArchetypeOptions, getSceneBoundaryFields }
