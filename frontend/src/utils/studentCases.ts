import request from './request'

export type StudentSceneItem = {
  id: number
  name: string
  difficulty?: string
  description?: string
  has_active_session?: boolean
  active_session_id?: number | null
  active_session_is_empty?: boolean
  finished_session_id?: number | null
  final_score?: number | null
  training_status?: 'not_started' | 'in_progress' | 'evaluating' | 'completed'
  status_label?: string
}

export type StudentCaseItem = {
  id: number
  title: string
  case_type: string
  background: string
  created_at?: string
  train_count?: number
  empty_session_count?: number
  scenes: StudentSceneItem[]
}

const validTrainingStatuses = new Set(['not_started', 'in_progress', 'evaluating', 'completed'])

function nullableNumber(value: unknown) {
  const numberValue = Number(value)
  return Number.isFinite(numberValue) && numberValue > 0 ? numberValue : null
}

function normalizeTrainingStatus(scene: any): StudentSceneItem['training_status'] {
  const rawStatus = String(scene?.training_status || '').trim()
  if (validTrainingStatuses.has(rawStatus)) return rawStatus as StudentSceneItem['training_status']
  if (scene?.finished_session_id) return 'completed'
  if (scene?.has_active_session || scene?.active_session_id) return 'in_progress'
  return 'not_started'
}

function normalizeScene(scene: any): StudentSceneItem | null {
  const id = Number(scene?.id)
  if (!Number.isFinite(id)) return null

  return {
    id,
    name: String(scene?.name || scene?.scene_name || '未命名场景'),
    difficulty: scene?.difficulty || undefined,
    description: scene?.description || undefined,
    training_status: normalizeTrainingStatus(scene),
    status_label: scene?.status_label || undefined,
    has_active_session: Boolean(scene?.has_active_session || scene?.active_session_id),
    active_session_id: nullableNumber(scene?.active_session_id),
    active_session_is_empty: Boolean(scene?.active_session_is_empty),
    finished_session_id: nullableNumber(scene?.finished_session_id),
    final_score: typeof scene?.final_score === 'number' ? scene.final_score : null,
  }
}

export function normalizeStudentCases(payload: unknown): StudentCaseItem[] {
  if (!Array.isArray(payload)) return []

  return payload
    .map((item: any) => {
      const id = Number(item?.id)
      if (!Number.isFinite(id)) return null

      const scenes = Array.isArray(item?.scenes)
        ? item.scenes.map(normalizeScene).filter((scene): scene is StudentSceneItem => Boolean(scene))
        : []

      if (!scenes.length) return null

      return {
        id,
        title: String(item?.title || item?.case_title || '未命名案件'),
        case_type: String(item?.case_type || '文字训练'),
        background: String(item?.background || item?.description || ''),
        created_at: item?.created_at || undefined,
        train_count: Number(item?.train_count || 0),
        empty_session_count: Number(item?.empty_session_count || 0),
        scenes,
      }
    })
    .filter((item): item is StudentCaseItem => Boolean(item))
}

async function requestCaseList(url: string) {
  const response = await request.get(url, { _skipErrorToast: true } as any)
  return normalizeStudentCases(response)
}

export async function fetchStudentCases() {
  const studentCases = await requestCaseList('/student/cases').catch(() => [])
  if (studentCases.length) return studentCases

  if (import.meta.env.DEV) {
    const devApiCases = await requestCaseList('/api/student/cases').catch(() => [])
    if (devApiCases.length) return devApiCases
  }

  return requestCaseList('/cases/').catch(() => [])
}

export async function fetchStudentCaseTypes(cases: StudentCaseItem[] = []) {
  const remoteTypes = await request
    .get('/student/case-types', { _skipErrorToast: true } as any)
    .catch(() => [])
  if (Array.isArray(remoteTypes) && remoteTypes.length) return remoteTypes.filter(Boolean).map(String)

  return Array.from(new Set(cases.map((item) => item.case_type).filter(Boolean)))
}
