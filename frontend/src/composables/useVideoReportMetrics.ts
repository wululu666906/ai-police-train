export interface VideoReportNode {
  node_result_id?: number
  node_index: number
  node_title?: string
  result: string
  retry_count: number
  score_earned: number
  score_deducted: number
  speech_transcript?: string
  failure_reasons?: string[]
  manual_review?: {
    reviewer_username?: string
    reviewed_at?: string
    review_note?: string
  } | null
}

export interface VideoAssessmentCheck {
  id?: string
  label?: string
  content?: string
  stage_name?: string
  dimension?: string
  status?: 'hit' | 'partial' | 'missed' | string
  score?: number
  full_score?: number
  weighted_score?: number
  weight?: number
  score_share?: number
  evidence?: string[]
  reason?: string
}

export interface VideoReportData {
  session_id?: number
  video_id?: number
  video_title?: string
  mode?: string
  total_score?: number
  full_score?: number
  percentage?: number
  grade?: string
  grade_level?: string
  summary?: string
  pass_count?: number
  skip_count?: number
  fail_count?: number
  total_nodes?: number
  total_deducted?: number
  violation_count?: number
  violation_summary?: Record<string, number>
  failure_reason_summary?: Record<string, number>
  dimension_scores?: {
    key: string
    label: string
    score: number
    full_score: number
    percentage: number
  }[]
  weakness_summary?: string[]
  assessment_check_results?: VideoAssessmentCheck[]
  assessment_point_results?: VideoAssessmentCheck[]
  ability_profile?: {
    enabled?: boolean
    semantic_average?: number
    standard_point_coverage?: number
    strengths?: string[]
    risks?: string[]
    next_training?: string[]
  }
  node_summaries?: VideoReportNode[]
  finished_at?: string
  evaluation_status?: string
  report_ready?: boolean
}

export function resultLabel(result: string) {
  return ({ pass: '通过', skip: '跳过', timeout: '超时', fail: '未通过' } as Record<string, string>)[result] || result
}

export function formatFailureReason(reason: string) {
  return ({
    gesture_mismatch: '动作未达标',
    keyword_mismatch: '话术未匹配',
    judge_incorrect: '判断题错误',
    choice_incorrect: '选择题错误',
    prop_missed: '道具动作遗漏',
    manual_review_failed: '人工复核判定未通过',
  } as Record<string, string>)[reason] || reason
}

export function formatViolationType(type: string) {
  return ({
    tab_switch: '切换标签页',
    page_leave: '关闭或刷新页面',
    page_hide: '页面切入后台',
    device_lost: '设备中断',
    identity_lost: '身份校验中断',
  } as Record<string, string>)[type] || type
}

<<<<<<< HEAD
export function artifactLabel(type: string) {
  return ({
    camera_recording: '训练录屏',
    microphone_recording: '语音留痕',
  } as Record<string, string>)[type] || type
}

export function assessmentStatusLabel(status?: string) {
  return ({
    hit: '完成',
    partial: '部分完成',
    missed: '未完成',
  } as Record<string, string>)[String(status || '')] || String(status || '未判定')
}

export function resolveMediaUrl(url?: string) {
  if (!url) return ''
  if (/^https?:\/\//i.test(url)) return url
  if (!url.startsWith('/')) return url

  const apiBase = String(import.meta.env.VITE_API_URL || '').trim()
  if (apiBase && /^https?:\/\//i.test(apiBase)) {
    return `${apiBase.replace(/\/$/, '')}${url}`
  }
  return `${window.location.origin}${url}`
}

=======
>>>>>>> c75d28e11697d318d584360255fb4e860ec8271e
export function formatDateTime(value?: string) {
  if (!value) return ''
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return ''
  return date.toLocaleString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  })
}

export function useVideoReportMetrics(report: VideoReportData | null) {
  const reportTitle = report?.video_title || '视频实训报告'
  const reportModeLabel = report?.mode === 'exam' ? '考核模式' : '练习模式'
  const reportPercentage = Number(report?.percentage || 0)
  const reportFinishedAt = formatDateTime(report?.finished_at)
  const reportScore = Number(report?.total_score || 0)
  const reportFullScore = Number(report?.full_score || 0)
  const reportGrade = report?.grade || '待评定'
  const reportPassCount = Number(report?.pass_count || 0)
  const reportSkipCount = Number(report?.skip_count || 0)
  const reportFailCount = Number(report?.fail_count || 0)
  const reportViolationCount = Number(report?.violation_count || 0)
  const reportTotalDeducted = Number(report?.total_deducted || 0)
  const reportTotalNodes = Number(report?.total_nodes || report?.node_summaries?.length || 0)
  const reportNodes = report?.node_summaries || []
  const dimensionScores = report?.dimension_scores || []
  const weaknessSummary = report?.weakness_summary || []
  const reportSummary = String(report?.summary || '').trim()
  const assessmentChecks = report?.assessment_check_results || report?.assessment_point_results || []
  const abilityProfile = report?.ability_profile

  const scoreHint = reportPercentage >= 90
    ? '训练表现稳定，动作、话术和流程控制较完整。'
    : reportPercentage >= 70
      ? '整体完成度良好，建议重点复盘失分节点。'
      : '当前仍有明显薄弱项，建议按失分节点针对性重练。'

  const failureReasonList = Object.entries(report?.failure_reason_summary || {}).map(([key, count]) => ({
    key,
    count,
    label: formatFailureReason(key),
  }))

  const violationList = Object.entries(report?.violation_summary || {}).map(([key, count]) => ({
    key,
    count,
    label: formatViolationType(key),
  }))

  const strengthTitle = abilityProfile?.strengths?.[0] || dimensionScores[0]?.label || '节点完成较稳定'
  const strengthNote = abilityProfile?.strengths?.slice(1).join('、') || scoreHint
  const weaknessTitle = weaknessSummary[0] || abilityProfile?.risks?.[0] || '重点复盘失分节点'
  const weaknessNote = weaknessSummary[1] || abilityProfile?.next_training?.[0] || '建议结合节点明细查看具体失分原因。'

  return {
    reportTitle,
    reportModeLabel,
    reportPercentage,
    reportFinishedAt,
    reportScore,
    reportFullScore,
    reportGrade,
    reportPassCount,
    reportSkipCount,
    reportFailCount,
    reportViolationCount,
    reportTotalDeducted,
    reportTotalNodes,
    reportNodes,
    dimensionScores,
    weaknessSummary,
    reportSummary,
    assessmentChecks,
    abilityProfile,
    scoreHint,
    failureReasonList,
    violationList,
    strengthTitle,
    strengthNote,
    weaknessTitle,
    weaknessNote,
  }
}

export function isVideoReportReady(payload: VideoReportData | null | undefined) {
  return Boolean(payload?.report_ready || (payload?.evaluation_status === 'completed' && payload?.node_summaries))
}
