// TODO: replace with API — mock data for hall right panel and card enrichments

export type SubStepStatus = 'active' | 'completed' | 'idle'

export interface MockSubStep {
  name: string
  status: SubStepStatus
}

export interface MockAnnouncement {
  id: number
  title: string
  date: string
  isNew: boolean
}

export interface MockTodayOverview {
  date: string
  trainingCount: number
  trainingDelta: number
  completedCount: number
  completedDelta: number
  avgScore: number
  avgScoreDelta: number
}

export interface MockStatusSlice {
  name: string
  value: number
  color: string
}

const SUB_STEP_NAMES = [
  '现场处置与初步调查',
  '询问笔录与证据固定',
  '调解沟通与后续跟进',
  '案件移交与归档总结',
]

/** Stable pseudo-random in [0, 1) from numeric seed */
function seededRatio(seed: number): number {
  const x = Math.sin(seed * 12.9898 + 78.233) * 43758.5453
  return x - Math.floor(x)
}

export function getMockProgress(caseId: number, sessionId?: number | null): number {
  const seed = Number(caseId) * 17 + Number(sessionId || 0) * 31
  const ratio = seededRatio(seed)
  if (sessionId) return Math.min(95, Math.max(15, Math.round(ratio * 70 + 20)))
  return Math.min(90, Math.max(5, Math.round(ratio * 85 + 5)))
}

export function getMockLastTrainAt(sessionId: number): string {
  const ratio = seededRatio(sessionId * 7 + 3)
  const hoursAgo = Math.floor(ratio * 72) + 1
  const date = new Date(Date.now() - hoursAgo * 3600 * 1000)
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())} ${pad(date.getHours())}:${pad(date.getMinutes())}`
}

export function getMockParticipantCount(caseId: number): number {
  return Math.floor(seededRatio(caseId * 13 + 5) * 35) + 12
}

export function getMockFinalScore(caseId: number): number {
  return Math.floor(seededRatio(caseId * 23 + 11) * 25) + 72
}

export function getMockSubSteps(caseId: number, status: 'active' | 'completed' | 'idle'): MockSubStep[] {
  const count = 3
  const progress = status === 'completed' ? count : status === 'active' ? Math.floor(seededRatio(caseId) * 2) + 1 : 0

  return SUB_STEP_NAMES.slice(0, count).map((name, index) => {
    let stepStatus: SubStepStatus = 'idle'
    if (status === 'completed') stepStatus = 'completed'
    else if (status === 'active') {
      if (index < progress - 1) stepStatus = 'completed'
      else if (index === progress - 1) stepStatus = 'active'
    }
    return { name, status: stepStatus }
  })
}

// TODO: replace with GET /student/stats/today
export const MOCK_TODAY_OVERVIEW: MockTodayOverview = {
  date: new Date().toISOString().slice(0, 10),
  trainingCount: 8,
  trainingDelta: 2,
  completedCount: 5,
  completedDelta: 1,
  avgScore: 82.5,
  avgScoreDelta: 5.3,
}

// TODO: replace with aggregated status stats API
export const MOCK_STATUS_DISTRIBUTION: MockStatusSlice[] = [
  { name: '进行中', value: 40, color: '#0066FF' },
  { name: '已完成', value: 50, color: '#52c41a' },
  { name: '未开始', value: 10, color: '#fa8c16' },
]

// TODO: replace with GET /student/announcements
export const MOCK_ANNOUNCEMENTS: MockAnnouncement[] = [
  { id: 1, title: '系统维护通知：本周六凌晨 2:00-4:00 暂停服务', date: '05-29', isNew: true },
  { id: 2, title: '训练规则更新：新增情绪识别评分维度说明', date: '05-28', isNew: true },
  { id: 3, title: '新案件上线：邻里纠纷、酒驾醉驾场景已开放', date: '05-27', isNew: false },
]

export const MOCK_NOTIFICATION_COUNT = 12
