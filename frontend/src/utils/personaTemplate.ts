export const behaviorArchetypeOptions = [
  {
    value: '求助配合型',
    summary: '愿意解决问题，重点是尽快得到处理结果。',
    interaction_style: '配合型',
    personality: '愿意把问题解决掉，重视处理结果和反馈',
    speaking_style: '会先讲自己的诉求，追问时愿意补充具体情况',
    police_attitude: '主动求助',
    pressure_response: '如果迟迟得不到回应，会重复诉求并追问什么时候处理',
    surface_stance: '我主要是想把事情处理好，该配合的我会配合。',
    trigger_points: ['感觉被敷衍', '迟迟没人处理'],
    calming_points: ['有人认真听完整个经过', '明确告诉我下一步怎么处理'],
    init_emotion: 46,
    init_trust: 56,
    init_risk: 26,
    init_expression_clarity: 78,
  },
  {
    value: '委屈宣泄型',
    summary: '情绪先于事实，会反复强调自己吃亏和受委屈。',
    interaction_style: '情绪型',
    personality: '委屈敏感，希望先被理解和照顾感受',
    speaking_style: '会夹杂抱怨、重复和情绪宣泄，容易跳着讲',
    police_attitude: '主动求助',
    pressure_response: '被追急时会先抱怨、打断或反复强调自己吃亏',
    surface_stance: '我先把我受的委屈说清楚，你们得先听我讲完。',
    trigger_points: ['质疑自己夸大', '要求马上闭嘴或冷处理'],
    calming_points: ['先认可情绪和损失', '允许先把最委屈的部分说完'],
    init_emotion: 74,
    init_trust: 42,
    init_risk: 58,
    init_expression_clarity: 58,
  },
  {
    value: '谨慎回避型',
    summary: '怕被卷入麻烦，会先观察警方掌握多少再决定说多少。',
    interaction_style: '观察型',
    personality: '谨慎怕事，不愿轻易卷入冲突中心',
    speaking_style: '先试探、停顿、回避敏感点，再一点点补充',
    police_attitude: '试探观望',
    pressure_response: '会先说记不清或没看清，再根据警方态度慢慢补细节',
    surface_stance: '我可以配合，但我只说我自己确定的部分。',
    trigger_points: ['感觉会牵连自己', '被逼立刻表态'],
    calming_points: ['先讲清不会乱定性', '先从自己确定看到的部分问起'],
    init_emotion: 54,
    init_trust: 28,
    init_risk: 34,
    init_expression_clarity: 74,
  },
  {
    value: '防御切责型',
    summary: '会优先切责任、淡化主动性，避免后果都落到自己身上。',
    interaction_style: '观察型',
    personality: '自保意识强，先考虑怎么切开责任和后果',
    speaking_style: '会先绕关键点，把行为说成误会、气头上或被逼无奈',
    police_attitude: '防备排斥',
    pressure_response: '先淡化责任，再切掉关键行为，必要时慢慢改口',
    surface_stance: '我配合归配合，但很多事不是你们想的那样。',
    trigger_points: ['问谁先动手', '问证据链', '提到家属或赔偿后果'],
    calming_points: ['先按时间线核实', '给其把话讲完整的台阶'],
    init_emotion: 63,
    init_trust: 22,
    init_risk: 46,
    init_expression_clarity: 76,
  },
  {
    value: '强硬对抗型',
    summary: '先顶撞、抢话、反问，不愿轻易接受警方定性。',
    interaction_style: '对抗型',
    personality: '好面子、冲，抗拒被压着走',
    speaking_style: '说话强势，容易抢话、反问、顶嘴',
    police_attitude: '敌对抵触',
    pressure_response: '越压越顶，先争辩、后反问，逼到角落才可能松口',
    surface_stance: '你们别先给我扣帽子，我没你们想得那么严重。',
    trigger_points: ['被直接定性', '被命令式逼问', '被当众拆穿'],
    calming_points: ['先稳语气再问事实', '给台阶，不当众硬压'],
    init_emotion: 76,
    init_trust: 16,
    init_risk: 74,
    init_expression_clarity: 72,
  },
  {
    value: '醉酒失控型',
    summary: '表达破碎、容易重复、情绪波动大，现场管控优先于完整问答。',
    interaction_style: '情绪型',
    personality: '受酒精影响，冲动、纠缠、容易被一句话点燃',
    speaking_style: '表达断裂、重复、跑题，容易抓住一个点纠缠',
    police_attitude: '敌对抵触',
    pressure_response: '被硬控或硬压时容易吼叫、挣扎、反复纠缠',
    surface_stance: '我没事，你们别碰我，都是他们的问题。',
    trigger_points: ['强行命令', '身体接触', '围观起哄'],
    calming_points: ['简短明确的边界指令', '减少围观刺激，稳定语气重复沟通'],
    init_emotion: 84,
    init_trust: 12,
    init_risk: 90,
    init_expression_clarity: 24,
  },
  {
    value: '绝望封闭型',
    summary: '意愿低、表达少，不一定撒谎，但可能拒绝继续交流。',
    interaction_style: '观察型',
    personality: '无力、绝望、封闭，对说教和追问敏感',
    speaking_style: '回答短、慢、空，容易说“没必要”“别管我”',
    police_attitude: '试探观望',
    pressure_response: '被逼急时可能沉默、转身、拒答，或突然情绪失控',
    surface_stance: '我现在不想说太多，你们别逼我。',
    trigger_points: ['说教式劝导', '否定其痛苦', '追问为什么这么做'],
    calming_points: ['先稳住陪伴关系', '谈具体牵挂对象或下一分钟要做什么'],
    init_emotion: 82,
    init_trust: 20,
    init_risk: 84,
    init_expression_clarity: 30,
  },
  {
    value: '围观起哄型',
    summary: '关注场面和存在感，容易被群体气氛带着走。',
    interaction_style: '对抗型',
    personality: '爱起哄、好事、容易受现场情绪裹挟',
    speaking_style: '喜欢插话、带节奏、夸张表达、重复煽动性片段',
    police_attitude: '防备排斥',
    pressure_response: '感觉被针对时会继续起哄、反问或煽动旁人附和',
    surface_stance: '我就是在旁边看，你们别老盯着我。',
    trigger_points: ['当众点名', '围观者持续附和', '认为警方只针对自己'],
    calming_points: ['快速切断围观互动', '单独带离后明确边界'],
    init_emotion: 68,
    init_trust: 18,
    init_risk: 68,
    init_expression_clarity: 56,
  },
] as const

type BehaviorArchetypeOption = (typeof behaviorArchetypeOptions)[number]
type BehaviorArchetypeValue = BehaviorArchetypeOption['value']

const behaviorArchetypeMap = new Map<string, BehaviorArchetypeOption>(
  behaviorArchetypeOptions.map((item) => [item.value, item])
)

export const policeAttitudeOptions = [
  { value: '主动求助', summary: '把警方当成解决问题的人，愿意争取帮助。' },
  { value: '试探观望', summary: '先看警方态度和掌握程度，再决定说多少。' },
  { value: '防备排斥', summary: '担心被牵连、被误解或被定性，嘴上有保留。' },
  { value: '敌对抵触', summary: '本能抗拒警方介入，容易顶嘴、反问或升级。' },
] as const

export const stateLevelOptions = [
  { value: '低', label: '低' },
  { value: '中', label: '中' },
  { value: '高', label: '高' },
] as const

export const sceneBehaviorModeOptions = [
  {
    value: '核查取证型',
    summary: '围绕事实、时间线、证据和矛盾点展开问询取证，重点是把关键问题问准问实。',
  },
  {
    value: '调解型',
    summary: '围绕矛盾焦点、可接受结果和协商空间展开，重点是稳住双方情绪并寻找可落地的缓和路径。',
  },
  {
    value: '危机干预型',
    summary: '用于轻生、失控、绝望等高风险场景，优先稳住关系、识别刺激源并寻找牵挂对象。',
  },
  {
    value: '管控型',
    summary: '适用于醉酒、围观、现场失控等局面，重点是降低刺激、阻断升级动作并明确现场边界。',
  },
] as const

export const PERSON_CANONICAL_FIELDS = [
  'behavior_archetype',
  'police_attitude',
  'scene_behavior_mode',
  'current_goal',
  'core_concern',
  'relationship_pressure',
  'surface_stance',
  'pressure_response',
  'trigger_points',
  'calming_points',
  'emotion_level',
  'cooperation_level',
  'risk_level',
  'clarity_level',
  'known_key_points',
  'withheld_key_points',
  'conflict_core',
  'acceptable_outcomes',
  'no_go_topics',
  'trigger_sources',
  'concerned_targets',
  'taboo_actions',
  'escalation_actions',
  'deescalation_conditions',
  'impairment_state',
] as const

export const PERSON_ALIAS_TO_CANONICAL: Record<string, string> = {
  authority_attitude: 'police_attitude',
  current_need: 'current_goal',
  private_drive: 'current_goal',
  weakness: 'core_concern',
  stress_response: 'pressure_response',
  public_mask: 'surface_stance',
  trigger_topics: 'trigger_points',
  knows_facts: 'known_key_points',
  hidden_truths: 'withheld_key_points',
}

export const sceneBoundaryFieldMap = {
  核查取证型: [
    {
      key: 'known_key_points',
      label: '知道的关键点',
      placeholder: '每行一条，例如：我看见对方先动手；我听见他说要赔偿。',
    },
    {
      key: 'withheld_key_points',
      label: '不会主动说的关键点',
      placeholder: '每行一条，例如：其实案发前我们已经起过冲突；这个细节我不想先说。',
    },
  ],
  调解型: [
    {
      key: 'conflict_core',
      label: '冲突核心',
      placeholder: '每行一条，例如：谁先越界；赔偿怎么谈；双方积怨。',
    },
    {
      key: 'acceptable_outcomes',
      label: '可接受结果',
      placeholder: '每行一条，例如：先分开双方；对方道歉；先把车挪开。',
    },
    {
      key: 'no_go_topics',
      label: '不能碰的话题',
      placeholder: '每行一条，例如：别直接说我在撒谎；不要拿家里人施压；别一上来定性。',
    },
  ],
  危机干预型: [
    {
      key: 'trigger_sources',
      label: '刺激源',
      placeholder: '每行一条，例如：被否定、被贴标签、被逼问、被人围观。',
    },
    {
      key: 'concerned_targets',
      label: '牵挂对象',
      placeholder: '每行一条，例如：孩子、母亲、同住家人、现场同伴。',
    },
    {
      key: 'taboo_actions',
      label: '禁忌动作',
      placeholder: '每行一条，例如：突然上手拉拽、命令式训斥、当众说教。',
    },
  ],
  管控型: [
    {
      key: 'escalation_actions',
      label: '升级动作',
      placeholder: '每行一条，例如：持续围观、多人压上、反复刺激其敏感点。',
    },
    {
      key: 'deescalation_conditions',
      label: '缓和条件',
      placeholder: '每行一条，例如：减少围观、先让其站稳、用短句说明下一步。',
    },
  ],
} as const

export type SceneBehaviorModeValue = (typeof sceneBehaviorModeOptions)[number]['value']
export type SceneBoundaryFieldKey = (typeof sceneBoundaryFieldMap)[SceneBehaviorModeValue][number]['key']

const emotionScoreMap: Record<string, number> = {
  低: 36,
  中: 62,
  高: 84,
}

const cooperationScoreMap: Record<string, number> = {
  低: 18,
  中: 38,
  高: 66,
}

const riskScoreMap: Record<string, number> = {
  低: 22,
  中: 56,
  高: 82,
}

const clarityScoreMap: Record<string, number> = {
  低: 22,
  中: 52,
  高: 82,
}

const pickFirstText = (...values: any[]) => {
  for (const value of values) {
    const text = String(value ?? '').trim()
    if (text) return text
  }
  return ''
}

const clampScore = (value: any, fallback: number) => {
  const numeric = Number(value)
  if (!Number.isFinite(numeric)) return fallback
  return Math.max(0, Math.min(100, Math.round(numeric)))
}

const toStringList = (value: any): string[] => {
  if (Array.isArray(value)) {
    return value.map((item) => String(item ?? '').trim()).filter(Boolean)
  }
  if (typeof value === 'string') {
    const raw = value.trim()
    if (!raw) return []
    try {
      const parsed = JSON.parse(raw)
      if (Array.isArray(parsed)) {
        return parsed.map((item) => String(item ?? '').trim()).filter(Boolean)
      }
    } catch {
      // Fall back to newline parsing.
    }
    return raw
      .split(/\r?\n/)
      .map((item) => item.trim())
      .filter(Boolean)
  }
  return []
}

export const dedupeStringList = (value: any) => {
  const seen = new Set<string>()
  const result: string[] = []
  for (const item of toStringList(value)) {
    if (seen.has(item)) continue
    seen.add(item)
    result.push(item)
  }
  return result
}

export const parseTextList = (value: string) =>
  String(value || '')
    .split(/\r?\n/)
    .map((item) => item.trim())
    .filter(Boolean)

export const stringifyTextList = (value: any) => (Array.isArray(value) ? value.join('\n') : '')

export const inferEmotionLevel = (score: any) => {
  const numeric = clampScore(score, 50)
  if (numeric >= 75) return '高'
  if (numeric <= 44) return '低'
  return '中'
}

export const inferCooperationLevel = (score: any) => {
  const numeric = clampScore(score, 30)
  if (numeric >= 55) return '高'
  if (numeric <= 24) return '低'
  return '中'
}

export const inferRiskLevel = (score: any) => {
  const numeric = clampScore(score, 50)
  if (numeric >= 70) return '高'
  if (numeric <= 34) return '低'
  return '中'
}

export const inferClarityLevel = (score: any) => {
  const numeric = clampScore(score, 52)
  if (numeric >= 70) return '高'
  if (numeric <= 34) return '低'
  return '中'
}

export const emotionScoreFromLevel = (level: any, fallback = 50) =>
  emotionScoreMap[String(level || '').trim()] ?? clampScore(fallback, 50)

export const cooperationScoreFromLevel = (level: any, fallback = 30) =>
  cooperationScoreMap[String(level || '').trim()] ?? clampScore(fallback, 30)

export const riskScoreFromLevel = (level: any, fallback = 50) =>
  riskScoreMap[String(level || '').trim()] ?? clampScore(fallback, 50)

export const clarityScoreFromLevel = (level: any, fallback = 52) =>
  clarityScoreMap[String(level || '').trim()] ?? clampScore(fallback, 52)

export const getBehaviorArchetypeMeta = (value: any): BehaviorArchetypeOption =>
  behaviorArchetypeMap.get(String(value || '').trim()) || behaviorArchetypeOptions[0]

export const getSceneBehaviorModeMeta = (value: any) =>
  sceneBehaviorModeOptions.find((item) => item.value === String(value || '').trim()) || sceneBehaviorModeOptions[0]

export const getSceneBoundaryFields = (value: any) => {
  const mode = getSceneBehaviorModeMeta(value).value
  return [...sceneBoundaryFieldMap[mode]]
}

export const inferBehaviorArchetype = (source: any): BehaviorArchetypeValue => {
  const explicit = String(source?.behavior_archetype || '').trim()
  if (behaviorArchetypeMap.has(explicit)) return explicit as BehaviorArchetypeValue

  const roleType = String(source?.role_type || source?.role || '').trim()
  const status = String(source?.status || '').trim()
  const text = [
    source?.personality,
    source?.speaking_style,
    source?.interaction_style,
    source?.current_goal,
    source?.core_concern,
    source?.weakness,
    source?.pressure_response,
    source?.authority_attitude,
  ]
    .map((item) => String(item || ''))
    .join(' ')

  if (/轻生|跳楼|绝望|不想活|别管我|没意义/.test(text)) return '绝望封闭型'
  if (/醉酒|喝多|失控/.test(`${status} ${text}`)) return '醉酒失控型'
  if (/起哄|围观|带节奏|煽动/.test(text)) return '围观起哄型'
  if (roleType === '嫌疑人' || /切责|误会|不是我先|别定性|不是我的责任/.test(text)) return '防御切责型'
  if (roleType === '被害人' || roleType === '受害人' || /委屈|吃亏|受伤|情绪/.test(text)) return '委屈宣泄型'
  if (/对抗|强势|嘴硬|反问|顶嘴|不服/.test(text)) return '强硬对抗型'
  if (/观察|谨慎|怕事|紧张|试探|回避/.test(text)) return '谨慎回避型'
  return '求助配合型'
}

const buildSurfaceStance = (
  policeAttitude: string,
  archetypeMeta: ReturnType<typeof getBehaviorArchetypeMeta>,
  currentGoal: string
) => {
  if (currentGoal && policeAttitude === '主动求助') {
    return `我现在主要想${currentGoal}，你们先帮我把事情稳下来。`
  }
  if (policeAttitude === '试探观望') return '我可以配合，但我只说我自己确定的部分。'
  if (policeAttitude === '防备排斥') return '我可以说，但你们别先给我定性。'
  if (policeAttitude === '敌对抵触') return '你们别先冲着我来，我没你们想得那么严重。'
  return archetypeMeta.surface_stance
}

const deriveRelationshipPressure = (source: any) => {
  const direct = dedupeStringList(source?.relationship_pressure)
  if (direct.length) return direct

  const protectedTargets = dedupeStringList(source?.protected_targets)
  const fearedPeople = dedupeStringList(source?.feared_people)
  const conflictTargets = dedupeStringList(source?.conflict_targets)
  const fearedConsequences = dedupeStringList(source?.feared_consequences)

  return dedupeStringList([
    ...protectedTargets.map((item) => `护着${item}`),
    ...fearedPeople.map((item) => `忌惮${item}`),
    ...conflictTargets.map((item) => `和${item}有旧怨或关系压力`),
    ...fearedConsequences,
  ])
}

const deriveTriggerPoints = (source: any) =>
  dedupeStringList([
    ...dedupeStringList(source?.trigger_points),
    ...dedupeStringList(source?.trigger_topics),
  ])

const deriveCalmingPoints = (source: any) => dedupeStringList(source?.calming_points)

export const normalizeBehaviorTemplate = (source: any) => {
  const archetype = inferBehaviorArchetype(source)
  const archetypeMeta = getBehaviorArchetypeMeta(archetype)
  const sceneBehaviorMode = getSceneBehaviorModeMeta(source?.scene_behavior_mode).value
  const fearedConsequences = dedupeStringList(source?.feared_consequences)
  const currentGoal = pickFirstText(source?.current_goal, source?.current_need, source?.private_drive)
  const coreConcern = pickFirstText(source?.core_concern, source?.weakness, fearedConsequences[0])
  const policeAttitude =
    pickFirstText(source?.police_attitude, source?.authority_attitude, archetypeMeta.police_attitude) ||
    archetypeMeta.police_attitude
  const triggerPoints = deriveTriggerPoints(source)
  const calmingPoints = deriveCalmingPoints(source)
  const emotionLevel =
    String(source?.emotion_level || inferEmotionLevel(source?.init_emotion || archetypeMeta.init_emotion || 50)).trim() ||
    '中'
  const cooperationLevel =
    String(source?.cooperation_level || inferCooperationLevel(source?.init_trust || archetypeMeta.init_trust || 30)).trim() ||
    '中'
  const riskLevel =
    String(source?.risk_level || inferRiskLevel(source?.init_risk || archetypeMeta.init_risk || 50)).trim() || '中'
  const clarityLevel =
    String(
      source?.clarity_level ||
        inferClarityLevel(source?.init_expression_clarity || archetypeMeta.init_expression_clarity || 52)
    ).trim() || '中'
  const impairmentState = String(source?.impairment_state || source?.impairment_note || '').trim()

  const boundaryLists: Record<SceneBoundaryFieldKey, string[]> = {
    known_key_points: dedupeStringList(source?.known_key_points),
    withheld_key_points: dedupeStringList(source?.withheld_key_points),
    conflict_core: dedupeStringList(source?.conflict_core),
    acceptable_outcomes: dedupeStringList(source?.acceptable_outcomes),
    no_go_topics: dedupeStringList(source?.no_go_topics),
    trigger_sources: dedupeStringList(source?.trigger_sources),
    concerned_targets: dedupeStringList(source?.concerned_targets),
    taboo_actions: dedupeStringList(source?.taboo_actions),
    escalation_actions: dedupeStringList(source?.escalation_actions),
    deescalation_conditions: dedupeStringList(source?.deescalation_conditions),
  }

  if (sceneBehaviorMode === '核查取证型') {
    if (!boundaryLists.known_key_points.length) boundaryLists.known_key_points = dedupeStringList(source?.knows_facts)
    if (!boundaryLists.withheld_key_points.length) boundaryLists.withheld_key_points = dedupeStringList(source?.hidden_truths)
  } else if (sceneBehaviorMode === '调解型') {
    if (!boundaryLists.conflict_core.length) {
      boundaryLists.conflict_core = dedupeStringList([coreConcern, ...dedupeStringList(source?.knows_facts)].filter(Boolean)).slice(0, 3)
    }
    if (!boundaryLists.acceptable_outcomes.length) {
      boundaryLists.acceptable_outcomes = dedupeStringList([currentGoal, ...calmingPoints].filter(Boolean)).slice(0, 3)
    }
    if (!boundaryLists.no_go_topics.length) {
      boundaryLists.no_go_topics = dedupeStringList([...triggerPoints, ...dedupeStringList(source?.hidden_truths)]).slice(0, 4)
    }
  } else if (sceneBehaviorMode === '危机干预型') {
    if (!boundaryLists.trigger_sources.length) {
      boundaryLists.trigger_sources = dedupeStringList([...triggerPoints, coreConcern].filter(Boolean)).slice(0, 4)
    }
    if (!boundaryLists.concerned_targets.length) {
      boundaryLists.concerned_targets = dedupeStringList([
        ...dedupeStringList(source?.protected_targets),
        ...deriveRelationshipPressure(source),
      ]).slice(0, 4)
    }
    if (!boundaryLists.taboo_actions.length) {
      boundaryLists.taboo_actions = dedupeStringList([
        ...dedupeStringList(source?.hidden_truths),
        ...dedupeStringList(source?.does_not_know),
      ]).slice(0, 3)
    }
  } else if (sceneBehaviorMode === '管控型') {
    if (!boundaryLists.escalation_actions.length) {
      boundaryLists.escalation_actions = dedupeStringList([
        ...triggerPoints,
        ...dedupeStringList(source?.hidden_truths),
      ]).slice(0, 4)
    }
    if (!boundaryLists.deescalation_conditions.length) {
      boundaryLists.deescalation_conditions = dedupeStringList([...calmingPoints, currentGoal].filter(Boolean)).slice(0, 4)
    }
  }

  const surfaceStance = String(
    source?.surface_stance || source?.public_mask || buildSurfaceStance(policeAttitude, archetypeMeta, currentGoal)
  ).trim()
  const pressureResponse = String(
    source?.pressure_response || source?.stress_response || archetypeMeta.pressure_response || ''
  ).trim()
  const resolvedTriggerPoints = triggerPoints.length ? triggerPoints : [...archetypeMeta.trigger_points]

  return {
    behavior_archetype: archetype,
    scene_behavior_mode: sceneBehaviorMode,
    police_attitude: policeAttitude,
    current_goal: currentGoal,
    core_concern: coreConcern,
    trigger_points: resolvedTriggerPoints,
    calming_points: calmingPoints.length ? calmingPoints : [...archetypeMeta.calming_points],
    relationship_pressure: deriveRelationshipPressure(source),
    surface_stance: surfaceStance,
    pressure_response: pressureResponse,
    interaction_style: String(source?.interaction_style || archetypeMeta.interaction_style || '配合型').trim(),
    personality: String(source?.personality || archetypeMeta.personality || '').trim(),
    speaking_style: String(source?.speaking_style || archetypeMeta.speaking_style || '').trim(),
    authority_attitude: policeAttitude,
    stress_response: pressureResponse,
    public_mask: surfaceStance,
    weakness: coreConcern,
    trigger_topics: resolvedTriggerPoints,
    private_drive: currentGoal,
    current_need: currentGoal,
    emotion_level: emotionLevel,
    cooperation_level: cooperationLevel,
    risk_level: riskLevel,
    clarity_level: clarityLevel,
    init_emotion: emotionScoreFromLevel(emotionLevel, source?.init_emotion ?? archetypeMeta.init_emotion ?? 50),
    init_trust: cooperationScoreFromLevel(cooperationLevel, source?.init_trust ?? archetypeMeta.init_trust ?? 30),
    init_risk: riskScoreFromLevel(riskLevel, source?.init_risk ?? archetypeMeta.init_risk ?? 50),
    init_expression_clarity: clarityScoreFromLevel(
      clarityLevel,
      source?.init_expression_clarity ?? archetypeMeta.init_expression_clarity ?? 52
    ),
    impairment_state: impairmentState,
    knows_facts: boundaryLists.known_key_points,
    hidden_truths: boundaryLists.withheld_key_points,
    ...boundaryLists,
  }
}

export const buildLegacyInfoBoundary = (source: any) => {
  const normalized = normalizeBehaviorTemplate(source)
  let knowsFacts: string[] = []
  let hiddenTruths: string[] = []
  const doesNotKnow = dedupeStringList(source?.does_not_know)

  if (normalized.scene_behavior_mode === '核查取证型') {
    knowsFacts = dedupeStringList(normalized.known_key_points)
    hiddenTruths = dedupeStringList(normalized.withheld_key_points)
  } else if (normalized.scene_behavior_mode === '调解型') {
    knowsFacts = dedupeStringList(normalized.conflict_core)
    hiddenTruths = dedupeStringList(normalized.no_go_topics)
  } else if (normalized.scene_behavior_mode === '危机干预型') {
    knowsFacts = dedupeStringList([...(normalized.trigger_sources || []), ...(normalized.concerned_targets || [])])
    hiddenTruths = dedupeStringList(normalized.taboo_actions)
  } else if (normalized.scene_behavior_mode === '管控型') {
    knowsFacts = dedupeStringList([
      ...(normalized.escalation_actions || []),
      ...(normalized.deescalation_conditions || []),
    ])
    hiddenTruths = normalized.impairment_state ? [`醉酒/药物/精神状态影响：${normalized.impairment_state}`] : []
  }

  return {
    knows_facts: knowsFacts,
    does_not_know: doesNotKnow,
    hidden_truths: hiddenTruths,
  }
}

export const buildSceneBoundaryGroups = (source: any) => {
  const normalized = normalizeBehaviorTemplate(source)
  return getSceneBoundaryFields(normalized.scene_behavior_mode).map((field) => ({
    ...field,
    items: dedupeStringList(normalized[field.key as SceneBoundaryFieldKey]),
  }))
}

export const buildBehaviorSummary = (source: any) => {
  const normalized = normalizeBehaviorTemplate(source)
  const parts = [
    normalized.behavior_archetype ? `原型：${normalized.behavior_archetype}` : '',
    normalized.police_attitude ? `态度：${normalized.police_attitude}` : '',
    normalized.current_goal ? `诉求：${normalized.current_goal}` : '',
    normalized.core_concern ? `顾虑：${normalized.core_concern}` : '',
  ].filter(Boolean)
  return parts.slice(0, 3)
}
