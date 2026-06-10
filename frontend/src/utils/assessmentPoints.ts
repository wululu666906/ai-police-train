export const MAX_ASSESSMENT_POINTS_PER_SCENE = 6

export const canAddAssessmentPoint = (scene: any) => {
  const count = Array.isArray(scene?.assessmentPointsModel) ? scene.assessmentPointsModel.length : 0
  return count < MAX_ASSESSMENT_POINTS_PER_SCENE
}

export const assessmentPointCountLabel = (scene: any) => {
  const count = Array.isArray(scene?.assessmentPointsModel) ? scene.assessmentPointsModel.length : 0
  return `${count} / ${MAX_ASSESSMENT_POINTS_PER_SCENE}`
}

const normalizeLabel = (value: string) => String(value || '').replace(/\s+/g, '').trim().toLowerCase()

export const dedupeAssessmentPointsByLabel = (points: any[]) => {
  const seen = new Set<string>()
  const output: any[] = []
  for (const point of points || []) {
    const key = normalizeLabel(point?.label) || normalizeLabel(point?.content)
    if (!key || seen.has(key)) continue
    seen.add(key)
    output.push(point)
  }
  return output
}

export const capAssessmentPoints = (points: any[], limit = MAX_ASSESSMENT_POINTS_PER_SCENE) => {
  return (points || []).slice(0, limit)
}

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
  stage_goal: scene?.description || '',
  case_type: caseItem?.case_type,
})
