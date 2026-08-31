export const MAX_EXPECTED_OUTCOMES_PER_SCENE = 6
/** @deprecated alias — 考察配置字段仍为 expected_outcomes，界面统一称「考察点」 */
export const MAX_ASSESSMENT_POINTS_PER_SCENE = MAX_EXPECTED_OUTCOMES_PER_SCENE

const normalizeTextKey = (value: string) =>
  String(value || '')
    .replace(/\s+/g, '')
    .replace(/[，。！？、；：,.!?;:"'“”‘’（）()【】\[\]《》<>·…—\-]/g, '')
    .trim()
    .toLowerCase()

export const dedupeExpectedOutcomes = (items: any[]) => {
  const seen = new Set<string>()
  const output: string[] = []
  for (const item of items || []) {
    const text = typeof item === 'string'
      ? item.trim()
      : String(item?.content || item?.text || item?.label || '').trim()
    const key = normalizeTextKey(text)
    if (!text || !key || seen.has(key)) continue
    seen.add(key)
    output.push(text)
  }
  return output
}

export const capExpectedOutcomes = (items: any[], limit = MAX_EXPECTED_OUTCOMES_PER_SCENE) =>
  dedupeExpectedOutcomes(items).slice(0, limit)

/** @deprecated */
export const dedupeAssessmentPointsByLabel = (points: any[]) => {
  const seen = new Set<string>()
  const output: any[] = []
  for (const point of points || []) {
    const key = normalizeTextKey(point?.label) || normalizeTextKey(point?.content)
    if (!key || seen.has(key)) continue
    seen.add(key)
    output.push(point)
  }
  return output
}

/** @deprecated */
export const capAssessmentPoints = (points: any[], limit = MAX_EXPECTED_OUTCOMES_PER_SCENE) =>
  (points || []).slice(0, limit)

export const canAddExpectedOutcome = (scene: any) => {
  const count = Array.isArray(scene?.expectedOutcomesModel)
    ? scene.expectedOutcomesModel.length
    : Array.isArray(scene?.expected_outcomes)
      ? scene.expected_outcomes.length
      : 0
  return count < MAX_EXPECTED_OUTCOMES_PER_SCENE
}

/** @deprecated */
export const canAddAssessmentPoint = canAddExpectedOutcome

export const expectedOutcomeCountLabel = (scene: any) => {
  const count = Array.isArray(scene?.expectedOutcomesModel)
    ? scene.expectedOutcomesModel.length
    : Array.isArray(scene?.expected_outcomes)
      ? scene.expected_outcomes.length
      : 0
  return `${count} / ${MAX_EXPECTED_OUTCOMES_PER_SCENE}`
}

/** @deprecated */
export const assessmentPointCountLabel = expectedOutcomeCountLabel

export const buildCaseInfoForAssessment = (caseItem: any) => {
  const narrative = String(caseItem?.original_content || caseItem?.full_narrative || caseItem?.background || '').trim()
  return {
    title: caseItem?.title,
    case_name: caseItem?.title,
    case_type: caseItem?.case_type,
    case_background: caseItem?.background || caseItem?.case_background,
    full_narrative: narrative,
    original_content: narrative,
  }
}

export const buildSceneInfoForAssessment = (scene: any, caseItem?: any) => ({
  name: scene?.name,
  scene_name: scene?.name,
  description: scene?.description,
  dispatch_brief: scene?.dispatch_brief,
  first_impression: scene?.first_impression,
  training_goal: scene?.training_goal || '',
  plot_arc: scene?.plot_arc || scene?.description || '',
  student_role: scene?.student_role || '民警',
  stages: Array.isArray(scene?.stages) ? scene.stages : (Array.isArray(scene?.stagesModel) ? scene.stagesModel : []),
  expected_outcomes: Array.isArray(scene?.expectedOutcomesModel)
    ? scene.expectedOutcomesModel.map((item: any) => String(item?.content || item?.text || item || '').trim()).filter(Boolean)
    : (Array.isArray(scene?.expected_outcomes) ? scene.expected_outcomes : []),
  stage_goal: scene?.training_goal || scene?.description || '',
  case_type: caseItem?.case_type,
})

export const serializeExpectedOutcomesForSave = (model: any[]) =>
  capExpectedOutcomes(
    (Array.isArray(model) ? model : []).map((item: any) =>
      typeof item === 'string' ? item : String(item?.content || item?.text || '').trim()
    )
  )
