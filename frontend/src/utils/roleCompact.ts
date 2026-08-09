import {
  behaviorArchetypeOptions,
  dedupeStringList,
  getSceneBoundaryFields,
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

const normalizeKnowledgeLedger = (person: any) => {
  const explicit = Array.isArray(person?.knowledge_ledger) ? person.knowledge_ledger : []
  const rows = explicit
    .filter((item: any) => item && typeof item === 'object' && String(item.content || '').trim())
    .map((item: any, index: number) => ({
      knowledge_id: String(item.knowledge_id || `K${index + 1}`).trim(),
      claim_id: String(item.claim_id || '').trim(),
      knowledge_mode: String(item.knowledge_mode || 'source_mention').trim(),
      content: String(item.content || '').trim(),
      certainty: String(item.certainty || 'source_supported').trim(),
      disclosure_policy: String(item.disclosure_policy || 'answer_when_asked').trim(),
      verbalization: String(item.verbalization || item.content || '').trim(),
      source_refs: Array.isArray(item.source_refs) ? item.source_refs : [],
    }))
  if (rows.length) return rows

  const legacyRows: any[] = []
  const append = (values: any, knowledge_mode: string, disclosure_policy: string) => {
    for (const content of dedupeStringList(values)) {
      legacyRows.push({
        knowledge_id: `K${legacyRows.length + 1}`,
        claim_id: '',
        knowledge_mode,
        content,
        certainty: 'legacy_config',
        disclosure_policy,
        verbalization: content,
        source_refs: [],
      })
    }
  }
  append(person?.known_key_points || person?.knows_facts, 'known', 'answer_when_asked')
  append(person?.withheld_key_points || person?.hidden_truths, 'withheld', 'withhold_until_triggered')
  append(person?.cannot_answer || person?.does_not_know, 'unknown', 'must_not_assert')
  return legacyRows
}

const normalizeRoleMemories = (person: any) => {
  const explicit = Array.isArray(person?.role_memories) ? person.role_memories : []
  if (explicit.length) {
    return explicit
      .filter((item: any) => item && String(item.statement || item.content || '').trim())
      .map((item: any, index: number) => ({
        memory_id: String(item.memory_id || `M${index + 1}`),
        memory_type: String(item.memory_type || item.knowledge_mode || 'direct_statement'),
        statement: String(item.statement || item.content || '').trim(),
        quote: String(item.quote || '').trim(),
        time_hint: String(item.time_hint || '').trim(),
        place_hint: String(item.place_hint || '').trim(),
        actors: Array.isArray(item.actors) ? item.actors : [],
        certainty: String(item.certainty || 'source_supported'),
        source_refs: Array.isArray(item.source_refs) ? item.source_refs : [],
        event_id: String(item.event_id || ''),
        is_scoring_fact: item.is_scoring_fact !== false,
        disclosure_policy: String(item.disclosure_policy || 'answer_when_asked'),
      }))
  }
  return normalizeKnowledgeLedger(person).map((item: any, index: number) => ({
    memory_id: String(item.knowledge_id || `M${index + 1}`),
    memory_type: String(item.knowledge_mode || 'source_mention'),
    statement: String(item.content || '').trim(),
    quote: String(item.verbalization || item.content || '').trim(),
    time_hint: '', place_hint: '', actors: [], certainty: String(item.certainty || 'legacy_config'),
    source_refs: Array.isArray(item.source_refs) ? item.source_refs : [], event_id: String(item.claim_id || ''),
  }))
}

export const personToRoleCompact = (person: any, sceneBehaviorMode = '核查取证型') => ({
  name: String(person?.name || '').trim(),
  role_type: String(person?.role_type || person?.role || '相关人员').trim() || '相关人员',
  status: String(person?.status || '正常').trim() || '正常',
  init_emotion: person?.init_emotion,
  init_trust: person?.init_trust,
  init_risk: person?.init_risk,
  init_expression_clarity: person?.init_expression_clarity,
  source_verification: String(person?.source_verification || '').trim(),
  source_refs: Array.isArray(person?.source_refs) ? person.source_refs : [],
  role_memories: normalizeRoleMemories(person),
  knowledge_ledger: normalizeKnowledgeLedger(person),
  unresolved_claims: Array.isArray(person?.unresolved_claims) ? person.unresolved_claims : [],
  response_constraints: dedupeStringList(person?.response_constraints),
  scene_behavior_mode: String(person?.scene_behavior_mode || sceneBehaviorMode || '核查取证型').trim(),
  persona_autofill: false,
})

export const expandRoleCompactToPerson = (compact: any, sceneBehaviorMode = '核查取证型'): Record<string, any> => {
  const roleMemories = normalizeRoleMemories(compact)
  const ledger = roleMemories.length
    ? roleMemories.map((memory: any, index: number) => ({
        knowledge_id: String(memory.memory_id || `K${index + 1}`), claim_id: String(memory.event_id || ''),
        knowledge_mode: String(memory.memory_type || 'source_mention'), content: String(memory.statement || '').trim(),
        certainty: String(memory.certainty || 'source_supported'), disclosure_policy: 'answer_when_asked',
        verbalization: String(memory.statement || '').trim(), source_refs: Array.isArray(memory.source_refs) ? memory.source_refs : [],
      }))
    : normalizeKnowledgeLedger(compact)
  const contents = (modes: string[]) => ledger
    .filter((item: any) => modes.includes(item.knowledge_mode))
    .map((item: any) => item.content)
    .filter(Boolean)
  const known = dedupeStringList(contents(['known', 'direct_observation', 'personal_experience', 'personal_statement', 'hearsay', 'later_learned', 'source_mention']))
  const withheld = dedupeStringList(contents(['withheld']))
  const unknown = dedupeStringList(contents(['unknown', 'unresolved']))
  return {
    ...compact,
    name: String(compact?.name || '').trim(),
    role_type: String(compact?.role_type || '相关人员').trim() || '相关人员',
    status: String(compact?.status || '正常').trim() || '正常',
    source_verification: String(compact?.source_verification || '').trim(),
    source_refs: Array.isArray(compact?.source_refs) ? compact.source_refs : [],
    role_memories: roleMemories,
    knowledge_ledger: ledger,
    unresolved_claims: Array.isArray(compact?.unresolved_claims) ? compact.unresolved_claims : [],
    response_constraints: dedupeStringList(compact?.response_constraints),
    knows_facts: known,
    known_key_points: known,
    hidden_truths: withheld,
    withheld_key_points: withheld,
    does_not_know: unknown,
    cannot_answer: unknown,
    scene_behavior_mode: String(compact?.scene_behavior_mode || sceneBehaviorMode || '核查取证型').trim(),
    persona_autofill: false,
    persona_source: String(compact?.persona_source || 'source_grounded_role_memory'),
    persona_contract_version: String(compact?.persona_contract_version || 'role_memory_v2'),
    soul_profile: compact?.soul_profile && typeof compact.soul_profile === 'object' ? compact.soul_profile : undefined,
    persona_generation: compact?.persona_generation && typeof compact.persona_generation === 'object' ? compact.persona_generation : undefined,
    current_goal: String(compact?.current_goal || compact?.soul_profile?.primary_need || '').trim(),
    init_emotion: compact?.init_emotion,
    init_trust: compact?.init_trust,
    init_risk: compact?.init_risk,
    init_expression_clarity: compact?.init_expression_clarity,
  }
}

export const buildRoleCompactSummary = (compact: any) => {
  const ledger = normalizeKnowledgeLedger(compact)
  const known = ledger.filter((item: any) => !['unknown', 'unresolved'].includes(item.knowledge_mode)).length
  const unknown = ledger.filter((item: any) => ['unknown', 'unresolved'].includes(item.knowledge_mode)).length
  return [`认知条目 ${ledger.length}`, `可回答 ${known}`, `未知/未决 ${unknown}`]
}

export const normalizeSceneOpeningConfig = (value: any) => {
  let source = value
  if (typeof source === 'string') {
    try { source = JSON.parse(source) } catch { source = {} }
  }
  source = source && typeof source === 'object' ? source : {}
  return {
    enabled: source.enabled !== false,
    mode: source.mode === 'preset' ? 'preset' : 'dynamic',
    speaker_role_ids: Array.isArray(source.speaker_role_ids) ? source.speaker_role_ids.slice(0, 3) : [],
    director_note: String(source.director_note || ''),
    preset_turns: Array.isArray(source.preset_turns) ? source.preset_turns : [],
  }
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
