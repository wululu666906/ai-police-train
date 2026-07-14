<template>
  <div class="student-page evaluation-page">
    <div v-if="loading" class="loading-state">
      <el-skeleton :rows="10" animated />
    </div>

    <article v-else-if="report" class="evaluation-document">
      <header class="report-topbar no-print">
        <div class="report-brand">
          <span class="brand-mark">评</span>
          <strong>训练评估报告</strong>
        </div>
        <div class="report-crumb">{{ evaluationBreadcrumb }} / 详情</div>
        <div class="page-actions">
          <el-button plain size="small" :icon="Printer" @click="printReport">打印报告</el-button>
          <el-button type="primary" size="small" :icon="Download" @click="printReport">下载报告</el-button>
          <el-button plain size="small" :icon="ArrowLeft" @click="router.push(evaluationReturnPath)">返回列表</el-button>
        </div>
      </header>

      <section v-if="isLegacyReport" class="legacy-state">
        <h2>旧版评估报告</h2>
        <p>当前记录仍是旧版固定维度报告。系统现在只使用 Adaptive V1 评估制度，请重新评估后查看新版报告。</p>
        <el-button type="primary" :loading="refreshing" @click="refreshEvaluation">重新评估</el-button>
      </section>

      <main v-else class="report-paper">
        <header class="paper-hero">
          <div>
            <h2>训练评估报告</h2>
            <p>报告编号：{{ reportMeta.reportNo }}<span>评估日期：{{ reportMeta.finishedAt }}</span></p>
          </div>
        </header>

        <section class="report-section report-section--summary">
          <div class="section-title"><i></i><span>本次结论</span></div>
          <div class="summary-layout">
            <div class="summary-copy">
              <h3>{{ trainingVerdict.title }}</h3>
              <p>{{ trainingVerdict.description }}</p>
            </div>
            <div class="summary-metrics">
              <article v-for="item in topMetricCards" :key="item.label">
                <span>{{ item.label }}</span>
                <strong>{{ item.value }}</strong>
                <p>{{ item.note }}</p>
              </article>
            </div>
          </div>
          <div class="insight-grid">
            <article>
              <span>优势亮点</span>
              <strong>{{ advantagePoint.title }}</strong>
              <p>{{ advantagePoint.note }}</p>
            </article>
            <article>
              <span>提升建议</span>
              <strong>{{ promotionSuggestion.title }}</strong>
              <p>{{ promotionSuggestion.note }}</p>
            </article>
          </div>
        </section>

        <section class="report-section">
          <div class="section-title"><i></i><span>训练概况</span></div>
          <div class="overview-table">
            <div><span>案件名称</span><strong>{{ reportMeta.caseTitle }}</strong></div>
            <div><span>训练类型</span><strong>{{ reportMeta.sceneName }}</strong></div>
            <div><span>训练时长</span><strong>{{ reportMeta.duration }}</strong></div>
            <div><span>评估人</span><strong>系统评估</strong></div>
            <div><span>评估方式</span><strong>系统自动评估</strong></div>
            <div><span>完成时间</span><strong>{{ reportMeta.finishedAt }}</strong></div>
          </div>
        </section>

        <section class="report-section">
          <div class="section-title"><i></i><span>能力指标结果</span></div>
          <div class="score-grid">
            <article v-for="item in commonScoreItems" :key="item.dimension" class="score-item">
              <div class="score-item__head">
                <strong>{{ item.dimension }}</strong>
                <span>{{ item.score }}/{{ item.full_score }} 分</span>
              </div>
              <div class="score-bar"><i :style="{ width: scoreWidth(item) }"></i></div>
              <p>{{ item.reason || '该项已纳入通用能力评估。' }}</p>
            </article>
          </div>
        </section>

        <section class="report-section">
          <div class="section-title"><i></i><span>场景考察点</span></div>
          <div class="assessment-summary">
            <div><span>已命中</span><strong>{{ assessmentStats.hit }}</strong><em>项</em></div>
            <div><span>部分命中</span><strong>{{ assessmentStats.partial }}</strong><em>项</em></div>
            <div><span>未命中</span><strong>{{ assessmentStats.missed }}</strong><em>项</em></div>
            <div><span>完成度</span><strong>{{ reportMeta.assessmentRate }}</strong></div>
          </div>
          <table class="report-table assessment-table">
            <thead>
              <tr>
                <th>考察点</th>
                <th>相关聊天记录</th>
                <th>状态</th>
                <th>权重</th>
                <th>得分</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="item in assessmentPointDisplayItems" :key="item.displayKey">
                <td class="assessment-point-cell">
                  <strong>{{ item.shortLabel }}</strong>
                  <p>{{ item.summary }}</p>
                </td>
                <td class="assessment-chat-cell">
                  <div v-if="item.chatRecords.length" class="chat-records">
                    <article
                      v-for="record in item.chatRecords"
                      :key="record.key"
                      class="chat-evidence-message"
                      :class="`chat-evidence-message--${record.role}`"
                    >
                      <div v-if="record.role === 'assistant'" class="chat-evidence-avatar">
                        {{ record.avatarText }}
                      </div>
                      <div class="chat-evidence-body">
                        <div class="chat-evidence-speaker">{{ record.speakerName }}</div>
                        <div class="chat-evidence-bubble">{{ record.text }}</div>
                      </div>
                      <div v-if="record.role === 'user'" class="chat-evidence-avatar chat-evidence-avatar--user">学</div>
                    </article>
                  </div>
                  <div v-else class="chat-records-empty">未截取到足够明确的聊天凭证</div>
                </td>
                <td class="assessment-state-cell">
                  <span class="assessment-item__state" :data-state="item.status">{{ statusLabel(item.status) }}</span>
                </td>
                <td class="assessment-number-cell">{{ percent(item.score_share) }}</td>
                <td class="assessment-number-cell">{{ item.weighted_score ?? item.score }}/{{ item.full_score ?? '-' }}</td>
              </tr>
            </tbody>
          </table>
        </section>

        <section class="report-section report-section--score">
          <div class="section-title"><i></i><span>综合得分</span></div>
          <div class="score-layout">
            <div class="score-narrative">
              <div class="score-summary-line">
                <strong>{{ totalScore }}</strong><span>/100</span><em :class="`grade-${reportHeader.gradeClass}`">{{ reportHeader.gradeLevel }}</em>
              </div>
              <p class="report-text">{{ studentScoreIntro }}</p>
              <div class="calibration-strip">
                <div><span>通用得分</span><strong>{{ percent(weighting.common_share) }}</strong></div>
                <div><span>沟通得分</span><strong>{{ percent(weighting.assessment_share) }}</strong></div>
                <div><span>必考命中率</span><strong>{{ requiredHitRateLabel }}</strong></div>
                <div><span>总分上限</span><strong>{{ scoreCapLabel }}</strong></div>
                <div><span>红线提示</span><strong>{{ redFlags.length ? `${redFlags.length} 项` : '无' }}</strong></div>
              </div>
            </div>
            <div class="score-gauge">
              <ECharts :option="gaugeOption" :height="210" />
            </div>
          </div>
          <div v-if="studentNoticeItems.length" class="notice-list"><p v-for="item in studentNoticeItems" :key="item">{{ item }}</p></div>
        </section>

        <section v-if="reportArtifacts.length" class="report-section">
          <div class="section-title"><i></i><span>凭证留痕</span></div>
          <div class="artifact-grid">
            <article v-for="item in reportArtifacts" :key="item.id" class="artifact-item">
              <div>
                <strong>{{ artifactLabel(item.artifact_type) }}</strong>
                <p>{{ item.mime_type || '附件' }}</p>
              </div>
              <a :href="resolveMediaUrl(item.file_url)" target="_blank" rel="noreferrer">打开凭证</a>
            </article>
          </div>
        </section>

        <section class="report-section"><div class="section-title"><i></i><span>综合点评</span></div><p class="report-text">{{ enhancedOverallComment }}</p></section>
        <section class="report-section"><div class="section-title"><i></i><span>反馈建议</span></div><ol class="report-list advice-list"><li v-for="item in actionableAdviceItems" :key="item">{{ item }}</li></ol></section>

        <section class="report-section">
          <div class="section-title"><i></i><span>对话分析</span></div>
          <div v-if="deductionDialogueItems.length" class="dialogue-list">
            <article v-for="item in deductionDialogueItems" :key="item.key" class="dialogue-item">
              <div class="dialogue-item__head">
                <strong>{{ item.utterance }}</strong>
                <span>{{ item.reason }}</span>
              </div>
              <div class="dialogue-item__columns">
                <div>
                  <label>问题类型</label>
                  <ul>
                    <li v-for="line in item.reasonItems" :key="line">{{ line }}</li>
                  </ul>
                </div>
                <div>
                  <label>改善建议</label>
                  <ul>
                    <li v-for="line in item.adviceItems" :key="line">{{ line }}</li>
                  </ul>
                </div>
              </div>
            </article>
          </div>
          <p v-else class="all-clear-text">本次报告未识别到需要单独展开的扣分发言，可重点查看能力指标结果。</p>
        </section>
      </main>
    </article>

    <div v-else class="empty-state">
      <el-empty :description="emptyState.title">
        <template #description><p>{{ emptyState.title }}</p><span>{{ emptyState.description }}</span></template>
        <div class="empty-actions"><el-button v-if="canResumeTraining" plain size="small" @click="resumeTraining">继续训练</el-button><el-button plain size="small" @click="router.push('/student/history')">训练历史</el-button><el-button type="primary" size="small" @click="router.push(evaluationReturnPath)">{{ evaluationReturnLabel }}</el-button></div>
      </el-empty>
    </div>
  </div>
</template>


<script setup lang="ts">
import { computed, inject, onMounted, onUnmounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ArrowLeft, Download, Printer } from '@element-plus/icons-vue'
import { showToast } from 'vant'
import request from '../utils/request'
import ECharts from '../geeker-adapt/components/ECharts/index.vue'

const router = useRouter()
const route = useRoute()
const setMainScrollable = inject<(value: boolean) => void>('setMainScrollable')
const report = ref<any>(null)
const loading = ref(true)
const refreshing = ref(false)
const pollingReport = ref(false)
const sessionDetail = ref<any>(null)
const emptyState = ref({
  title: '暂无评估数据',
  description: '当前会话可能还未完成评估，或评估结果暂未写入。',
})
let evaluationPollTimer: number | null = null
const assignmentContext = computed(() => sessionDetail.value?.assignment_context || null)
const isAssignmentReport = computed(() => Boolean(assignmentContext.value || route.query.source === 'assignment'))
const evaluationReturnPath = computed(() => isAssignmentReport.value ? '/student/classes' : '/student/hall')
const evaluationReturnLabel = computed(() => isAssignmentReport.value ? '班级作业' : '训练大厅')
const evaluationBreadcrumb = computed(() => isAssignmentReport.value ? '班级作业 / 训练评估报告' : '训练历史 / 训练评估报告')
const routeAssignmentId = computed(() => {
  const raw = Array.isArray(route.query.assignment_id) ? route.query.assignment_id[0] : route.query.assignment_id
  const id = Number(raw)
  return Number.isFinite(id) && id > 0 ? id : null
})

const safeParse = <T>(value: any, fallback: T): T => {
  if (value === null || value === undefined || value === '') return fallback
  if (typeof value !== 'string') return value as T
  try {
    return JSON.parse(value) as T
  } catch {
    return fallback
  }
}

const isAdaptiveReport = computed(() => report.value?.evaluation_meta?.scoring_version === 'adaptive_v1')
const isLegacyReport = computed(() => {
  if (!report.value) return false
  if (isAdaptiveReport.value) return false
  return Array.isArray(report.value?.scores) && report.value.scores.length > 0
})
const scoreItems = computed(() => (Array.isArray(report.value?.scores) ? report.value.scores : []))
const commonScoreItems = computed(() => scoreItems.value.filter((item: any) => item?.group === 'common'))
const improvementItems = computed(() => (Array.isArray(report.value?.improvements) ? report.value.improvements : []))
const assessmentPointResults = computed(() =>
  Array.isArray(report.value?.assessment_point_results) ? report.value.assessment_point_results : [],
)
const normalizeAssessmentPointText = (value: any) =>
  String(value || '')
    .trim()
    .toLowerCase()
    .replace(/（.*?）|\(.*?\)/g, '')
    .split(/怎样算完成|具体要求|回放时|回放训练/)[0]
    .replace(/[\s，。！？、；：“”‘’（）()《》【】[\]{}<>.,!?;:'"`~@#$%^&*\-_=+|\\/]+/g, '')

const assessmentPointKey = (item: any) => {
  const semantic = `${normalizeAssessmentPointText(item?.label)}__${normalizeAssessmentPointText(assessmentPointContent(item))}`
  return `semantic:${semantic}`
}

const assessmentTextSimilarity = (left: string, right: string) => {
  if (!left && !right) return 1
  if (!left || !right) return 0
  const leftSet = new Set(left.split(''))
  const rightSet = new Set(right.split(''))
  const intersection = [...leftSet].filter((char) => rightSet.has(char)).length
  const union = new Set([...leftSet, ...rightSet]).size || 1
  return intersection / union
}

const isSameAssessmentPoint = (left: any, right: any) => {
  const leftId = String(left?.id || '').trim()
  const rightId = String(right?.id || '').trim()
  if (leftId && rightId && leftId === rightId) return true

  const leftLabel = normalizeAssessmentPointText(left?.label)
  const rightLabel = normalizeAssessmentPointText(right?.label)
  if (!leftLabel || leftLabel !== rightLabel) return false

  const leftContent = normalizeAssessmentPointText(assessmentPointContent(left))
  const rightContent = normalizeAssessmentPointText(assessmentPointContent(right))
  if (!leftContent || !rightContent) return true
  if (leftContent.includes(rightContent) || rightContent.includes(leftContent)) return true
  return assessmentTextSimilarity(leftContent, rightContent) >= 0.72
}

const assessmentPointQuality = (item: any) => {
  let score = 0
  if (normalizeAssessmentPointText(assessmentPointContent(item))) score += 4
  if (Array.isArray(item?.keywords) && item.keywords.length) score += 2
  if (String(item?.id || '').trim()) score += 1
  if (item?.weight !== undefined && item?.weight !== null) score += 1
  if (item?.required !== undefined && item?.required !== null) score += 1
  return score
}

const mergeAssessmentPointForDisplay = (current: any, incoming: any, rank: Record<string, number>) => {
  const preferred = assessmentPointQuality(incoming) > assessmentPointQuality(current) ? incoming : current
  const other = preferred === incoming ? current : incoming
  const bestStatusItem = (rank[incoming?.status] ?? 0) > (rank[current?.status] ?? 0) ? incoming : current
  return {
    ...other,
    ...preferred,
    status: bestStatusItem?.status,
    score: bestStatusItem?.score ?? preferred?.score,
    weighted_score: bestStatusItem?.weighted_score ?? preferred?.weighted_score,
    evidence: Array.from(new Set([...(current?.evidence || []), ...(incoming?.evidence || [])])),
  }
}

const dedupedAssessmentPointResults = computed(() => {
  const rank: Record<string, number> = { miss: 0, missed: 0, partial: 1, hit: 2 }
  const items: any[] = []
  for (const item of assessmentPointResults.value) {
    const label = String(item?.label || '').replace(/（.*?）|\(.*?\)/g, '').trim()
    const normalizedItem = { ...item, label: label || item?.label || '未命名考察点' }
    const index = items.findIndex((current) => isSameAssessmentPoint(current, normalizedItem))
    if (index < 0) {
      items.push(normalizedItem)
    } else {
      items[index] = mergeAssessmentPointForDisplay(items[index], normalizedItem, rank)
    }
  }
  return items
})
const assessmentStats = computed(() => {
  const items = dedupedAssessmentPointResults.value
  const hit = items.filter((item: any) => item.status === 'hit').length
  const partial = items.filter((item: any) => item.status === 'partial').length
  const missed = items.filter((item: any) => item.status !== 'hit' && item.status !== 'partial').length
  return { total: items.length, hit, partial, missed }
})
const canResumeTraining = computed(() => sessionDetail.value?.status === 'active' && Number(sessionDetail.value?.id) > 0)
const weighting = computed(() => report.value?.evaluation_meta?.weighting || {})
const assessmentCompletion = computed(() => report.value?.evaluation_meta?.assessment_completion || {})
const scoreCaps = computed(() => Array.isArray(report.value?.evaluation_meta?.score_caps?.caps) ? report.value.evaluation_meta.score_caps.caps : [])
const redFlags = computed(() => Array.isArray(report.value?.evaluation_meta?.red_flags) ? report.value.evaluation_meta.red_flags : [])
const scoreCapLabel = computed(() => {
  const cap = Number(report.value?.evaluation_meta?.score_caps?.final_cap)
  return Number.isFinite(cap) && cap < 100 ? `${cap} 分` : '无'
})

const pickFirstFinite = (...values: any[]) => {
  for (const value of values) {
    if (value === null || value === undefined || value === '') continue
    const normalized = Number(value)
    if (Number.isFinite(normalized)) return normalized
  }
  return null
}

const reportHeader = computed(() => {
  const meta = report.value?.evaluation_meta?.report_header || {}
  const total = Number(report.value?.total_score ?? meta.total_score ?? 0)
  return {
    gradeLevel: report.value?.grade_level || meta.grade_level || getLevel(total),
    gradeClass: getGradeClass(total),
  }
})

const totalScore = computed(() => Math.round(Number(report.value?.total_score || 0)))
const requiredHitRateLabel = computed(() => percent(assessmentCompletion.value?.required_rate))

const topMetricCards = computed(() => [
  { label: '综合得分', value: `${totalScore.value}/100`, note: reportHeader.value.gradeLevel },
  { label: '必考命中率', value: requiredHitRateLabel.value, note: `命中 ${assessmentStats.value.hit}/${assessmentStats.value.total} 项` },
  { label: '完成度', value: reportMeta.value.assessmentRate, note: reportMeta.value.stageProgress },
])

const advantagePoint = computed(() => {
  const strengths = Array.isArray(report.value?.strengths) ? report.value.strengths.filter(Boolean) : []
  const bestScore = [...commonScoreItems.value].sort((a: any, b: any) => scoreRatio(b) - scoreRatio(a))[0]
  return {
    title: strengths[0] || bestScore?.dimension || '基础处置较稳定',
    note: strengths[1] || bestScore?.reason || '本次训练中能够完成部分基础问询和处置推进。',
  }
})

const promotionSuggestion = computed(() => {
  const weakPoint = weakAssessmentItems.value[0]
  const weakScore = weakCommonScoreItems.value[0]
  return {
    title: weakScore?.dimension || weakPoint?.label || '继续巩固处置闭环',
    note: weakPoint?.feedback || weakPoint?.content || weakScore?.reason || '建议围绕未命中考察点进行复盘，并在下一轮训练中主动补齐关键问询。',
  }
})

const gaugeOption = computed<any>(() => ({
  series: [
    {
      type: 'gauge' as const,
      startAngle: 200,
      endAngle: -20,
      min: 0,
      max: 100,
      splitNumber: 5,
      radius: '100%',
      center: ['50%', '66%'],
      progress: {
        show: true,
        roundCap: true,
        width: 18,
        itemStyle: { color: '#2f6df6' },
      },
      axisLine: {
        roundCap: true,
        lineStyle: {
          width: 18,
          color: [[1, '#e6ebf7']],
        },
      },
      axisTick: { show: false },
      splitLine: { show: false },
      axisLabel: { show: false },
      pointer: { show: false },
      anchor: { show: false },
      title: {
        show: true,
        offsetCenter: [0, '34%'],
        color: '#2f6df6',
        fontSize: 14,
        fontWeight: 700,
      },
      detail: {
        valueAnimation: true,
        offsetCenter: [0, '8%'],
        formatter: `{value|${totalScore.value}}{unit|/100}`,
        rich: {
          value: { color: '#18213d', fontSize: 36, fontWeight: 800 },
          unit: { color: '#9aa6bd', fontSize: 14, fontWeight: 700 },
        },
      },
      data: [{ value: totalScore.value, name: reportHeader.value.gradeLevel }],
    },
  ],
}))

const diffSeconds = (start: any, end: any) => {
  if (!start || !end) return null
  const startDate = new Date(start)
  const endDate = new Date(end)
  if (Number.isNaN(startDate.getTime()) || Number.isNaN(endDate.getTime())) return null
  const seconds = Math.floor((endDate.getTime() - startDate.getTime()) / 1000)
  return seconds >= 0 ? seconds : null
}

const formatTrainingDuration = (seconds: any) => {
  if (seconds === null || seconds === undefined || seconds === '') return '未记录'
  const total = Number(seconds)
  if (!Number.isFinite(total) || total < 0) return '未记录'
  const minutes = Math.floor(total / 60)
  const remainSeconds = Math.floor(total % 60)
  return `${minutes}分${remainSeconds}秒`
}

const reportMeta = computed(() => {
  const meta = report.value?.evaluation_meta?.report_header || {}
  const caseTitle = meta.case_title || sessionDetail.value?.case_title
  const sceneName = meta.scene_name || sessionDetail.value?.scene_name
  const createdAt = meta.training_started_at || sessionDetail.value?.training_started_at || meta.created_at || sessionDetail.value?.created_at
  const finishedAt = meta.training_finished_at || meta.finished_at || sessionDetail.value?.training_finished_at || report.value?.evaluated_at || sessionDetail.value?.updated_at || createdAt
  const durationSeconds = pickFirstFinite(
    meta.duration_seconds,
    sessionDetail.value?.duration_seconds,
    diffSeconds(createdAt, finishedAt),
  )
  const score = Number(report.value?.total_score || 0)
  return {
    caseTitle: caseTitle || '未知案件',
    sceneName: sceneName || '训练场景',
    duration: formatTrainingDuration(durationSeconds),
    finishedAt: formatDateTime(finishedAt),
    reportNo: `PES-${formatReportNo(finishedAt)}-${String(sessionDetail.value?.id || getSessionId() || 0).padStart(4, '0')}`,
    passLabel: score >= 60 ? '满足' : '未满足',
    assessmentRate: percent(assessmentCompletion.value.weight_rate),
    stageProgress: assessmentStats.value.total ? `${assessmentStats.value.hit + assessmentStats.value.partial}/${assessmentStats.value.total}` : '暂无数据',
  }
})

const weakestScoreItems = computed(() =>
  [...scoreItems.value]
    .sort((a: any, b: any) => Number(a.score || 0) / Math.max(Number(a.full_score || 1), 1) - Number(b.score || 0) / Math.max(Number(b.full_score || 1), 1))
    .slice(0, 3),
)

const negativeReasonTerms = ['不足', '未能', '未及时', '未充分', '未有效', '缺少', '缺乏', '缺失', '没有', '不够', '忽略', '欠缺', '遗漏', '薄弱', '短板', '问题', '风险', '扣分', '仍需', '需要加强', '追问不足', '识别不及时', '未完成', '部分完成']
const positiveReasonTerms = ['礼貌', '克制', '清晰', '较好', '能够', '已', '充分', '到位', '有效', '完整', '稳定', '未出现压迫', '未出现激化', '未出现明显']
const weakLevelLabels = ['需改进', '不合格', '较弱', '薄弱', 'weak', 'poor', 'bad']

const scoreRatio = (item: any) => Number(item?.score || 0) / Math.max(Number(item?.full_score || 1), 1)

const removePositiveNegativePhrases = (value: string) =>
  value
    .replace(/未出现[^，。；、]*(压迫|激化|违规|明显问题|明显失误|对抗|抵触)/g, '')
    .replace(/没有出现[^，。；、]*(压迫|激化|违规|明显问题|明显失误|对抗|抵触)/g, '')

const hasNegativeReason = (value: any) => {
  const text = removePositiveNegativePhrases(String(value || ''))
  return negativeReasonTerms.some((term) => text.includes(term))
}

const isMostlyPositiveReason = (value: any) => {
  const text = String(value || '')
  if (!text) return false
  return positiveReasonTerms.some((term) => text.includes(term)) && !hasNegativeReason(text)
}

const isIssueScoreItem = (item: any) => {
  const ratio = scoreRatio(item)
  const reason = String(item?.reason || '')
  const level = String(item?.level || item?.grade || item?.status || '').toLowerCase()
  if (Number(item?.score || 0) >= Number(item?.full_score || 0)) return false
  if (isMostlyPositiveReason(reason)) return false
  if (hasNegativeReason(reason)) return true
  if (weakLevelLabels.some((label) => level.includes(label.toLowerCase()))) return true
  return ratio <= 0.75
}

const weakCommonScoreItems = computed(() =>
  commonScoreItems.value
    .filter(isIssueScoreItem)
    .sort((a: any, b: any) => scoreRatio(a) - scoreRatio(b)),
)

const weakAssessmentItems = computed(() =>
  assessmentPointResults.value.filter((item: any) => item.status !== 'hit').slice(0, 5),
)

const studentMessages = computed(() =>
  (Array.isArray(sessionDetail.value?.messages) ? sessionDetail.value.messages : [])
    .filter((message: any) => message?.role === 'user' && String(message?.content || '').trim())
    .map((message: any) => String(message.content || '').trim()),
)

const scoreSummary = computed(() => {
  const score = Number(report.value?.total_score || 0)
  if (score >= 90) return '通用能力稳定，场景考察点覆盖充分，可进入更高难度训练。'
  if (score >= 75) return '训练基本达标，仍需针对未命中考察点和薄弱通用能力继续巩固。'
  if (score >= 60) return '训练达到基础要求，但关键考察点或闭环表达仍存在明显缺口。'
  return '训练未达到预期标准，需先补齐必考点，再强化主动追问和处置收尾。'
})

const studentScoreIntro = computed(() => {
  const score = Number(report.value?.total_score || 0)
  const grade = reportHeader.value.gradeLevel
  const result = score >= 60 ? '已达到本次训练的基础要求' : '暂未达到本次训练的预期要求'
  const action = score >= 75
    ? '建议继续巩固薄弱环节，提升处置完整度。'
    : score >= 60
      ? '建议重点复盘关键事实核查、主动追问和收尾表达。'
      : '建议先补齐关键处置点，再强化主动追问和处置收尾。'
  return `综合得分 ${score} 分（满分 100 分），评定等级为 ${grade}。本次训练${result}，${action}`
})

const trainingVerdict = computed(() => {
  const score = Number(report.value?.total_score || 0)
  const missedRequired = Number(assessmentCompletion.value?.required_missed || 0)
  const hasRedFlags = redFlags.value.length > 0
  if (score >= 80 && !missedRequired && !hasRedFlags) {
    return {
      title: '可以进入巩固提升',
      description: '本次训练整体稳定，建议继续挑战同类更复杂警情，保持处置链条完整度。',
    }
  }
  if (score >= 60 && !hasRedFlags) {
    return {
      title: '建议针对薄弱点复训',
      description: '本次已达到基础要求，但仍有关键问询、现场动作或收尾表达需要补齐。',
    }
  }
  return {
    title: '建议先完成补练',
    description: '本次训练未达到预期标准，请优先复盘未命中考察点和扣分发言，再重新训练。',
  }
})

const formatStudentNotice = (value: any, type = '重点提醒') => {
  const raw = String(value || '').trim()
  if (!raw) return ''
  const text = raw
    .replace(/必考点\s*hit\s*率低于\s*\d+%?/gi, '必考处置点完成不足')
    .replace(/hit\s*率/gi, '完成情况')
    .replace(/总分上限\s*\d+\s*分/g, '')
    .replace(/上限|校准|红线/g, '')
    .replace(/[，,。；;：:]\s*$/g, '')
  if (text.includes('人身风险') || text.includes('伤情') || text.includes('紧急')) {
    return `${type}：${text}，后续应优先确认人员安全、伤情情况和危险是否仍在持续。`
  }
  if (text.includes('必考') || text.includes('完成不足')) {
    return `${type}：${text}，后续需优先补齐关键问询和必要处置动作。`
  }
  return `${type}：${text}。`
}

const studentNoticeItems = computed(() => {
  const items = [
    ...scoreCaps.value.map((item: any) => formatStudentNotice(item?.reason, '重点提醒')),
    ...redFlags.value.map((item: any) => formatStudentNotice(item?.label, '风险提醒')),
  ].filter(Boolean)
  return Array.from(new Set(items)).slice(0, 4)
})

const overallComment = computed(() => {
  const strengths = Array.isArray(report.value?.strengths) ? report.value.strengths : []
  const improvements = finalImprovementItems.value
  if (strengths.length || improvements.length) {
    return `学员在本次训练中${strengths.length ? `表现出${strengths.join('、')}等优点` : '能够完成部分基础处置动作'}，但在${improvements.slice(0, 3).join('、')}等方面仍需加强。建议后续按通用能力和本场景考察点逐项复训。`
  }
  return scoreSummary.value
})

const enhancedOverallComment = computed(() => {
  const score = Number(report.value?.total_score || 0)
  const strengths = Array.isArray(report.value?.strengths) ? report.value.strengths.filter(Boolean).slice(0, 3) : []
  const weakDimensions = weakCommonScoreItems.value.map((item: any) => item.dimension).slice(0, 3)
  const weakPoints = weakAssessmentItems.value.map((item: any) => item.label).filter(Boolean).slice(0, 3)
  const findings = Array.isArray(report.value?.evaluation_meta?.rule_findings) ? report.value.evaluation_meta.rule_findings : []
  const findingText = findings.map((item: any) => item?.message).filter(Boolean).slice(0, 2)

  const performance = score >= 85
    ? '本次训练整体表现较稳，能够较好完成场景推进和关键要求。'
    : score >= 70
      ? '本次训练整体达到基本要求，但处置链条中仍有若干关键环节不够充分。'
      : score >= 60
        ? '本次训练达到基础通过线，但关键事实核查、表达组织或闭环处置仍存在明显短板。'
        : '本次训练未达到预期标准，学员需要先补齐场景必考点，再提升问询推进和处置收束质量。'

  const strengthText = strengths.length
    ? `主要优点是${strengths.join('；')}。`
    : '本次训练可作为基础复盘样本，后续应重点提升稳定性和完整性。'
  const lossText = [
    weakDimensions.length ? `主要失分集中在${weakDimensions.join('、')}` : '',
    weakPoints.length ? `场景考察点中${weakPoints.join('、')}完成不足` : '',
    findingText.length ? findingText.join('；') : '',
  ].filter(Boolean).join('；')
  const direction = actionableAdviceItems.value.slice(0, 2).join('；')

  return `${performance}${strengthText}${lossText ? `失分原因主要包括：${lossText}。` : ''}${direction ? `后续改进方向：${direction}` : '后续建议围绕薄弱能力项开展针对性复训。'}`
})

const finalImprovementItems = computed(() => {
  if (improvementItems.value.length) return improvementItems.value
  return weakestScoreItems.value.map((item: any) => `加强${item.dimension}训练，提升该环节处置质量。`)
})

const makeActionableAdvice = (text: string) => {
  const value = String(text || '').trim()
  if (!value) return ''
  if (value.includes('情绪') || value.includes('安抚') || value.includes('抵触')) {
    return '面对情绪激动或抵触对象时，应先表达理解并降低对抗感，再进入事实询问，例如先说明“我理解您现在着急，我们先确认安全和经过”。'
  }
  if (value.includes('地点') || value.includes('时间') || value.includes('身份') || value.includes('人物') || value.includes('关系')) {
    return `围绕“${value.replace(/^必考点未完成：/, '')}”建立固定追问顺序，优先核实时间、地点、身份关系和事件经过，避免只停留在笼统问询。`
  }
  if (value.includes('风险') || value.includes('伤情') || value.includes('安全')) {
    return '出现纠纷升级、伤情或安全隐患时，应先确认是否有人受伤、危险是否持续、是否需要增援或急救，再继续了解经过。'
  }
  if (value.includes('证据') || value.includes('现场') || value.includes('动作')) {
    return '现场类训练中应同步体现证据意识，及时提示保护现场、固定客观材料，并说明下一步核查或处置动作。'
  }
  if (value.includes('闭环') || value.includes('收尾') || value.includes('总结')) {
    return '结束前应复述已核实事实、确认双方诉求，并明确下一步处置安排，形成完整处置闭环。'
  }
  if (value.includes('追问') || value.includes('主动') || value.includes('逻辑')) {
    return '每轮提问后应根据回答继续追问细节，按“事实确认-矛盾核实-风险判断-处置告知”的顺序推进。'
  }
  return value.length < 14 ? `针对“${value}”，请在下一轮训练中给出具体问法、处置动作和收尾确认。` : value
}

const actionableAdviceItems = computed(() => {
  const rawItems = [
    ...finalImprovementItems.value,
    ...weakCommonScoreItems.value.map((item: any) => item.reason),
    ...weakAssessmentItems.value.map((item: any) => item.feedback || item.content || item.label),
  ]
  const mapped = rawItems.map(makeActionableAdvice).filter(Boolean)
  return Array.from(new Set(mapped)).slice(0, 6)
})

const stripSpeakerPrefix = (value: string) =>
  String(value || '').replace(/^(学员|民警|用户|user)[:：]\s*/i, '').trim()

const normalizeDialogueText = (value: string) =>
  stripSpeakerPrefix(value)
    .replace(/\s+/g, '')
    .replace(/[，。！？、；：“”"'.…,.!?;:]/g, '')
    .toLowerCase()

const findUtteranceFromEvidence = (evidence: any[]) => {
  const candidates = (Array.isArray(evidence) ? evidence : [])
    .map((item) => stripSpeakerPrefix(String(item || '')))
    .filter(Boolean)
  for (const candidate of candidates) {
    const matched = studentMessages.value.find((message: string) => message.includes(candidate) || candidate.includes(message))
    if (matched) return matched
    if (!candidate.startsWith('AI角色') && !candidate.startsWith('动作')) return candidate
  }
  return studentMessages.value[studentMessages.value.length - 1] || '未定位到具体学员发言'
}

const adviceForReason = (reason: string) => makeActionableAdvice(reason) || '建议将该问题改写为更具体、可执行的问法，并在下一轮训练中主动补齐。'

const assessmentPointContent = (item: any) =>
  String(
    item?.content ||
    item?.requirement ||
    item?.description ||
    item?.target ||
    item?.assessment_target ||
    item?.goal ||
    '暂无考核目标',
  ).trim()

const splitBulletLines = (value: any, limit = 3) => {
  const text = String(value || '').trim()
  if (!text) return []
  const parts = text
    .split(/[。！？；;\n]+/)
    .map((item) => item.trim().replace(/^[：:、\-\s]+|[：:、\-\s]+$/g, ''))
    .filter(Boolean)
  const result: string[] = []
  const seen = new Set<string>()
  for (const part of (parts.length ? parts : [text])) {
    if (seen.has(part)) continue
    seen.add(part)
    result.push(part)
    if (result.length >= limit) break
  }
  return result
}

const shortAssessmentText = (value: any, limit = 48) => {
  const text = String(value || '').replace(/^(学员应|应当|需要|需|具体要求|怎样算完成|完成标准|考察点)[:：\s]*/g, '')
  const compact = text.split(/[。！？；;\n]+/)[0].replace(/\s+/g, '').trim()
  if (!compact) return ''
  return compact.length > limit ? `${compact.slice(0, Math.max(1, limit - 1))}…` : compact
}

const normalizeEvidenceItems = (value: any) => {
  const items = Array.isArray(value) ? value : []
  return items
    .map((item) => {
      if (item && typeof item === 'object') {
        return {
          kind: String(item.kind || 'text'),
          text: String(item.text || item.label || item.content || '').trim(),
          label: String(item.label || item.text || item.content || '').trim(),
        }
      }
      const text = String(item || '').trim()
      return { kind: 'text', text, label: text }
    })
    .filter((item) => item.text)
}

const dialogueMessages = computed(() =>
  (Array.isArray(sessionDetail.value?.messages) ? sessionDetail.value.messages : [])
    .filter((message: any) => ['user', 'assistant'].includes(String(message?.role || '')) && String(message?.content || '').trim())
    .map((message: any, index: number) => ({
      index,
      role: String(message.role || ''),
      text: String(message.content || '').trim(),
      speakerName: String(message.speaker_name || '').trim() || (message.role === 'user' ? '执法民警' : sessionDetail.value?.role_name || 'AI角色'),
    })),
)

const chatRecordText = (value: any) =>
  stripSpeakerPrefix(String(value || ''))
    .replace(/^(AI角色|AI|助手|assistant)[:：]\s*/i, '')
    .replace(/^动作[:：]\s*/i, '')
    .trim()

const evidenceRole = (value: string) => {
  const text = String(value || '').trim()
  if (/^(AI角色|AI|助手|assistant)[:：]/i.test(text)) return 'assistant'
  if (/^(学员|民警|用户|user)[:：]/i.test(text)) return 'user'
  if (/^动作[:：]/i.test(text)) return 'action'
  return 'text'
}

const roleLabel = (role: string) => {
  if (role === 'user') return '学员'
  if (role === 'assistant') return 'AI角色'
  if (role === 'action') return '动作'
  return '凭证'
}

const speakerNameForRole = (role: string, fallback = '') => {
  if (role === 'user') return '执法民警'
  if (role === 'assistant') return fallback || sessionDetail.value?.role_name || 'AI角色'
  if (role === 'action') return '动作日志'
  return '凭证'
}

const avatarTextForRole = (role: string, speakerName = '') => {
  if (role === 'user') return '学'
  if (role === 'assistant') return String(speakerName || 'AI').slice(0, 1)
  if (role === 'action') return '动'
  return '证'
}

const findDialogueIndex = (needle: string, preferredRole?: string) => {
  const normalizedNeedle = normalizeDialogueText(chatRecordText(needle))
  if (!normalizedNeedle) return -1
  return dialogueMessages.value.findIndex((message: { role: string; text: string }) => {
    if (preferredRole && preferredRole !== 'text' && preferredRole !== 'action' && message.role !== preferredRole) return false
    const normalizedMessage = normalizeDialogueText(message.text)
    return normalizedMessage.includes(normalizedNeedle) || normalizedNeedle.includes(normalizedMessage)
  })
}

const pushChatRecord = (
  output: Array<{ key: string; role: string; roleLabel: string; speakerName: string; avatarText: string; text: string }>,
  role: string,
  text: string,
  key: string,
  speakerName = '',
) => {
  const clean = chatRecordText(text)
  if (!clean) return
  const dedupeKey = `${role}:${normalizeDialogueText(clean)}`
  if (output.some((item) => `${item.role}:${normalizeDialogueText(item.text)}` === dedupeKey)) return
  const resolvedSpeaker = speakerNameForRole(role, speakerName)
  output.push({ key, role, roleLabel: roleLabel(role), speakerName: resolvedSpeaker, avatarText: avatarTextForRole(role, resolvedSpeaker), text: clean })
}

const buildAssessmentChatRecords = (item: any, evidenceItems: Array<{ kind: string; text: string }>) => {
  const records: Array<{ key: string; role: string; roleLabel: string; speakerName: string; avatarText: string; text: string }> = []
  for (const evidence of evidenceItems) {
    const rawText = String(evidence.text || '').trim()
    const role = evidence.kind === 'student_utterance'
      ? 'user'
      : evidence.kind === 'assistant_reply' || evidence.kind === 'context'
        ? 'assistant'
        : evidenceRole(rawText)
    const messageIndex = findDialogueIndex(rawText, role === 'action' ? undefined : role)
    if (messageIndex >= 0) {
      const message = dialogueMessages.value[messageIndex]
      if (message.role === 'user') {
        pushChatRecord(records, message.role, message.text, `${item.id || item.label}-msg-${message.index}`, message.speakerName)
        const nextAssistant = dialogueMessages.value.slice(messageIndex + 1).find((next: { role: string }) => next.role === 'assistant')
        if (nextAssistant) {
          pushChatRecord(records, 'assistant', nextAssistant.text, `${item.id || item.label}-reply-${nextAssistant.index}`, nextAssistant.speakerName)
        }
      } else if (message.role === 'assistant') {
        const previousUser = [...dialogueMessages.value.slice(0, messageIndex)].reverse().find((prev: { role: string }) => prev.role === 'user')
        if (previousUser) {
          pushChatRecord(records, 'user', previousUser.text, `${item.id || item.label}-prev-${previousUser.index}`, previousUser.speakerName)
        }
        pushChatRecord(records, message.role, message.text, `${item.id || item.label}-msg-${message.index}`, message.speakerName)
      }
    } else {
      pushChatRecord(records, role, rawText, `${item.id || item.label}-ev-${records.length}`)
    }
    if (records.length >= 4) break
  }
  return records.slice(0, 4)
}

const assessmentPointDisplayItems = computed(() =>
  dedupedAssessmentPointResults.value.map((item: any) => {
    const shortLabel = String(item.short_label || item.label || '场景考察点').trim()
    const summary = String(item.summary || shortAssessmentText(item.feedback || assessmentPointContent(item)) || shortLabel).trim()
    const fullText = String(item.full_text || assessmentPointContent(item)).trim()
    const evidenceItems = normalizeEvidenceItems(item.evidence_items || item.evidence)
    const contextEvidenceItems = normalizeEvidenceItems(item.context_evidence_items || item.context_evidence)
    const allEvidenceItems = [...evidenceItems, ...contextEvidenceItems]
    const mediaRefs = Array.isArray(item.media_refs) ? item.media_refs : []
    const feedbackItems = Array.isArray(item.feedback_items) ? item.feedback_items : splitBulletLines(item.feedback, 3)
    return {
      ...item,
      shortLabel,
      summary,
      fullText,
      evidenceItems,
      contextEvidenceItems,
      chatRecords: buildAssessmentChatRecords(item, allEvidenceItems),
      mediaRefs,
      feedbackItems,
      displayKey: assessmentPointKey(item),
    }
  }),
)

const deductionDialogueItems = computed(() => {
  const items: Array<{ key: string; utterance: string; reason: string; advice: string; reasonItems: string[]; adviceItems: string[] }> = []
  for (const score of weakCommonScoreItems.value) {
    const reason = String(score.reason || `${score.dimension}存在不足。`)
    if (!hasNegativeReason(reason) && scoreRatio(score) > 0.75) continue
    items.push({
      key: `score-${score.dimension}`,
      utterance: findUtteranceFromEvidence(score.evidence || []),
      reason,
      advice: adviceForReason(reason),
      reasonItems: splitBulletLines(reason, 3),
      adviceItems: splitBulletLines(adviceForReason(reason), 3),
    })
  }

  for (const point of weakAssessmentItems.value) {
    const label = String(point.label || '场景考察点')
    const reason = point.status === 'partial'
      ? `${label}仅部分完成：${point.feedback || point.content || '关键要素仍未补齐。'}`
      : `${label}未有效完成：${point.feedback || point.content || '对话中未出现满足要求的问询或处置。'}`
    items.push({
      key: `point-${point.id || label}`,
      utterance: findUtteranceFromEvidence(point.evidence || []),
      reason,
      advice: adviceForReason(`${label} ${reason}`),
      reasonItems: splitBulletLines(reason, 3),
      adviceItems: splitBulletLines(adviceForReason(`${label} ${reason}`), 3),
    })
  }

  const seenUtterances = new Set<string>()
  const seenReasons = new Set<string>()
  return items.filter((item) => {
    const utteranceKey = normalizeDialogueText(item.utterance)
    const reasonKey = normalizeDialogueText(item.reason).slice(0, 48)
    if (!utteranceKey || utteranceKey === normalizeDialogueText('未定位到具体学员发言')) return false
    if (seenUtterances.has(utteranceKey) || seenReasons.has(reasonKey)) return false
    seenUtterances.add(utteranceKey)
    seenReasons.add(reasonKey)
    return true
  }).slice(0, 6)
})

const resolveMediaUrl = (value: string) => {
  if (!value) return ''
  if (/^https?:\/\//i.test(value) || value.startsWith('blob:') || value.startsWith('data:')) return value
  return value.startsWith('/') ? value : `/${value}`
}

const artifactLabel = (type: string) => {
  const mapping: Record<string, string> = {
    screenshot: '截图凭证',
    screen_capture: '截图凭证',
    camera_recording: '视频留痕',
    microphone_recording: '语音留痕',
    audio_recording: '语音留痕',
  }
  return mapping[String(type || '').toLowerCase()] || '会话凭证'
}

const reportArtifacts = computed(() => {
  const items = Array.isArray(sessionDetail.value?.artifacts) ? sessionDetail.value.artifacts : []
  return items.filter((item: any) => item?.file_url)
})

const percent = (value: any) => {
  const number = Number(value)
  if (!Number.isFinite(number)) return '暂无数据'
  return `${Math.round(number * 100)}%`
}

const scoreWidth = (item: any) => {
  const score = Number(item?.score || 0)
  const fullScore = Math.max(Number(item?.full_score || 0), 1)
  return `${Math.max(0, Math.min(100, Math.round((score / fullScore) * 100)))}%`
}

const difficultyFromWeight = (weight: any) => {
  const value = Number(weight || 10)
  if (value <= 10) return '低'
  if (value >= 14) return '高'
  return '中等'
}

const setEmptyState = (title: string, description: string) => {
  emptyState.value = { title, description }
}

const resumeTraining = () => {
  if (!canResumeTraining.value) return
  router.push(`/student/training/${sessionDetail.value.id}`)
}

const getSessionId = () => {
  const rawSessionId = route.query.session_id
  const sessionId = Number(rawSessionId)
  if (!rawSessionId || Number.isNaN(sessionId) || sessionId <= 0) return null
  return sessionId
}

const normalizeReportPayload = (payload: any) => {
  if (!payload) return null
  if (payload.evaluation_result !== undefined) {
    return safeParse(payload.evaluation_result, null)
  }
  return safeParse(payload, null)
}

const clearEvaluationPoll = () => {
  if (evaluationPollTimer != null) {
    window.clearTimeout(evaluationPollTimer)
    evaluationPollTimer = null
  }
  pollingReport.value = false
}

const fetchEvaluation = async (options: { silent?: boolean; attempt?: number } = {}) => {
  const sessionId = getSessionId()
  if (!sessionId) {
    showToast('无法加载评估报告')
    setEmptyState('无法定位评估报告', '请从训练历史重新打开报告。')
    loading.value = false
    return
  }

  try {
    const res: any = await request.get(`/training/session/${sessionId}`, {
      params: {
        for_report: 1,
        assignment_id: routeAssignmentId.value || undefined,
      },
      _skipErrorToast: true,
    } as any)
    sessionDetail.value = res || null
    if (!res.evaluation_result) {
      if (res.status === 'evaluating' && (options.attempt || 0) < 12) {
        pollingReport.value = true
        setEmptyState('评估报告生成中', '系统正在生成评估报告，请稍候。')
        loading.value = false
        clearEvaluationPoll()
        pollingReport.value = true
        evaluationPollTimer = window.setTimeout(() => {
          void fetchEvaluation({ silent: true, attempt: (options.attempt || 0) + 1 })
        }, 1200)
        return
      }
      pollingReport.value = false
      if (!options.silent) showToast('当前训练尚未生成评估报告')
      if (res.status === 'active') {
        setEmptyState('尚未完成评估', '训练进行中，完成后再查看报告。')
      } else {
        setEmptyState('报告暂未生成', '系统可能仍在生成报告，请稍后刷新；也可在训练历史中重新评估。')
      }
      return
    }
    clearEvaluationPoll()
    report.value = normalizeReportPayload(res)
    if (!report.value) {
      showToast('评估报告解析失败')
      setEmptyState('报告解析失败', '可在训练历史中重新评估。')
    }
  } catch (error: any) {
    clearEvaluationPoll()
    const status = Number(error?.response?.status || 0)
    if (status === 401) {
      setEmptyState('登录状态已失效', '请重新登录后再查看评估报告。')
    } else if (status === 403 || status === 404) {
      showToast('当前账号无权访问该评估报告')
      setEmptyState('无法查看该评估报告', '该训练记录不存在，或不属于当前登录账号。请从训练历史或班级作业入口重新打开。')
    } else {
      showToast('获取评估报告失败')
      setEmptyState('加载失败', '请稍后重试。')
    }
  } finally {
    loading.value = false
  }
}

const refreshEvaluation = async () => {
  const sessionId = getSessionId()
  if (!sessionId || refreshing.value) return
  refreshing.value = true
  try {
    const res: any = await request.post(`/training/re-evaluate/${sessionId}`, null, { _skipErrorToast: true } as any)
    const nextReport = normalizeReportPayload(res)
    if (nextReport) {
      clearEvaluationPoll()
      report.value = nextReport
      showToast({ type: 'success', message: '评估报告已更新' })
    } else {
      showToast('评估报告更新成功，但结果格式异常')
    }
  } catch (error: any) {
    const errorMsg = error?.response?.data?.detail || '重新评估失败'
    showToast(errorMsg)
  } finally {
    refreshing.value = false
  }
}

const statusLabel = (status: string) => {
  if (status === 'hit') return '已命中'
  if (status === 'partial') return '部分命中'
  return '未命中'
}

const getLevel = (score: number) => {
  if (score >= 90) return '卓越'
  if (score >= 80) return '优秀'
  if (score >= 70) return '良好'
  if (score >= 60) return '合格'
  return '需改进'
}

const getGradeClass = (score: number) => {
  if (score >= 80) return 'pass'
  if (score >= 60) return 'ok'
  return 'fail'
}

const formatDateTime = (value: any) => {
  if (!value) return '未记录'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return String(value)
  const pad = (num: number) => String(num).padStart(2, '0')
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())} ${pad(date.getHours())}:${pad(date.getMinutes())}`
}

const formatReportNo = (value: any) => {
  const date = value ? new Date(value) : new Date()
  const safeDate = Number.isNaN(date.getTime()) ? new Date() : date
  const pad = (num: number) => String(num).padStart(2, '0')
  return `${safeDate.getFullYear()}${pad(safeDate.getMonth() + 1)}${pad(safeDate.getDate())}${pad(safeDate.getHours())}${pad(safeDate.getMinutes())}`
}

const formatDuration = (seconds: any) => {
  const total = Number(seconds || 0)
  if (!Number.isFinite(total) || total <= 0) return '未记录'
  const minutes = Math.floor(total / 60)
  const remainSeconds = Math.floor(total % 60)
  if (minutes <= 0) return `${remainSeconds}秒`
  return `${minutes}分${remainSeconds}秒`
}

const printReport = () => {
  window.print()
}

onMounted(async () => {
  setMainScrollable?.(true)
  if (route.query.refresh === '1') {
    await refreshEvaluation()
    const nextQuery = { ...route.query }
    delete nextQuery.refresh
    router.replace({ query: nextQuery })
  } else {
    await fetchEvaluation()
  }
})

onUnmounted(() => {
  clearEvaluationPoll()
  setMainScrollable?.(false)
})
</script>

<style scoped>
.evaluation-page { min-height: 100%; padding: 0 0 36px; background: #f5f8fc; color: #15213b; font-size: 14px; line-height: 1.7; }
.evaluation-document { width: 100%; margin: 0 auto; }
.report-topbar { height: 74px; display: grid; grid-template-columns: 220px 1fr auto; align-items: center; gap: 24px; padding: 0 56px; background: rgba(255, 255, 255, 0.92); border-bottom: 1px solid #e8edf6; }
.report-brand { display: flex; align-items: center; gap: 12px; color: #10203f; font-size: 18px; font-weight: 900; }
.brand-mark { width: 28px; height: 28px; display: inline-grid; place-items: center; border-radius: 6px; background: #2f6df6; color: #fff; font-size: 14px; }
.report-crumb { color: #8a96ad; font-size: 13px; }
.page-actions, .empty-actions { display: flex; flex-wrap: wrap; gap: 10px; justify-content: flex-end; }
.report-paper, .legacy-state, .loading-state, .empty-state { background: #fff; }
.report-paper { width: min(1160px, calc(100% - 72px)); margin: 36px auto 0; padding: 0 0 34px; min-height: 760px; box-shadow: 0 18px 48px rgba(33, 58, 99, 0.08); }
.paper-hero { padding: 40px 52px 28px; border-bottom: 1px solid #e6ebf3; }
.paper-hero h2 { margin: 0 0 12px; color: #101a33; font-size: 30px; line-height: 1.2; font-weight: 900; letter-spacing: 0; }
.paper-hero p { margin: 0; color: #647089; font-size: 13px; }
.paper-hero span { margin-left: 28px; }
.report-section { padding: 28px 52px; border-bottom: 1px solid #e6ebf3; }
.report-section:last-child { border-bottom: 0; }
.section-title { display: flex; align-items: center; gap: 12px; margin-bottom: 18px; color: #18213d; font-size: 16px; font-weight: 900; }
.section-title i { width: 5px; height: 14px; border-radius: 3px; background: #8eb1ff; }
.summary-layout { display: grid; grid-template-columns: minmax(0, 1fr) minmax(420px, 1.15fr); gap: 34px; align-items: center; }
.summary-copy { padding-left: 24px; }
.summary-copy h3 { margin: 0 0 10px; color: #101a33; font-size: 22px; line-height: 1.3; font-weight: 900; }
.summary-copy p, .insight-grid p, .score-item p, .report-text, .report-table td p { margin: 0; color: #657189; }
.summary-metrics { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); border-left: 1px solid #e1e7f2; }
.summary-metrics article { min-height: 92px; padding: 4px 26px; border-right: 1px solid #e1e7f2; }
.summary-metrics span, .insight-grid span { color: #66748e; font-size: 13px; font-weight: 700; }
.summary-metrics strong { display: block; margin: 9px 0 3px; color: #2f6df6; font-size: 31px; line-height: 1; font-weight: 900; }
.summary-metrics p { margin: 0; color: #7c879d; font-size: 13px; }
.insight-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 38px; margin-top: 26px; padding-top: 24px; border-top: 1px solid #e6ebf3; }
.insight-grid article { min-width: 0; }
.insight-grid strong { display: block; margin: 8px 0; color: #2f6df6; font-size: 17px; font-weight: 900; overflow-wrap: anywhere; }
.overview-table { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); row-gap: 13px; column-gap: 72px; }
.overview-table div { min-width: 0; display: grid; grid-template-columns: 92px minmax(0, 1fr); align-items: baseline; gap: 12px; }
.overview-table span { color: #7b879c; }
.overview-table strong { color: #15213b; font-weight: 900; overflow-wrap: anywhere; }
.score-grid { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); border-top: 1px solid #e2e8f2; border-left: 1px solid #e2e8f2; }
.score-item { min-height: 126px; padding: 18px 22px; border-right: 1px solid #e2e8f2; border-bottom: 1px solid #e2e8f2; background: #fff; }
.score-item__head { display: flex; justify-content: space-between; gap: 12px; align-items: center; }
.score-item__head strong { color: #121d39; font-size: 15px; font-weight: 900; }
.score-item__head span { color: #2f6df6; font-weight: 900; white-space: nowrap; }
.score-bar { height: 6px; margin: 14px 0 13px; border-radius: 999px; background: #e7edf7; overflow: hidden; }
.score-bar i { display: block; height: 100%; border-radius: inherit; background: #2f6df6; }
.assessment-summary, .calibration-strip { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); margin-bottom: 20px; }
.assessment-summary div { min-height: 54px; display: flex; align-items: baseline; justify-content: center; gap: 7px; }
.assessment-summary span { color: #6d7890; }
.assessment-summary strong { color: #15213b; font-size: 26px; line-height: 1; font-weight: 900; }
.assessment-summary em { color: #6d7890; font-style: normal; }
.assessment-table th:nth-child(1), .assessment-table td:nth-child(1) { width: 26%; text-align: left; }
.assessment-table th:nth-child(2), .assessment-table td:nth-child(2) { width: 42%; text-align: left; }
.assessment-table th:nth-child(n + 3), .assessment-table td:nth-child(n + 3) { text-align: center; vertical-align: middle; }
.assessment-point-cell strong { display: block; color: #15213b; font-weight: 900; }
.assessment-point-cell p { margin: 6px 0 0; color: #667085; line-height: 1.55; overflow-wrap: anywhere; }
.assessment-state-cell { white-space: nowrap; }
.assessment-number-cell { color: #15213b; font-weight: 900; white-space: nowrap; }
.assessment-item__state { display: inline-flex; align-items: center; justify-content: center; min-width: 64px; padding: 3px 9px; border-radius: 999px; font-style: normal; font-size: 12px; font-weight: 900; white-space: nowrap; }
.assessment-item__state[data-state="hit"] { background: #ecfdf3; color: #067647; }
.assessment-item__state[data-state="partial"] { background: #fff6e8; color: #9a5b13; }
.assessment-item__state[data-state="missed"] { background: #fef3f2; color: #b42318; }
.chat-records { display: grid; gap: 10px; padding: 2px 0; }
.chat-evidence-message { display: flex; align-items: flex-start; gap: 8px; }
.chat-evidence-message--user { justify-content: flex-end; }
.chat-evidence-message--action { justify-content: center; }
.chat-evidence-avatar { width: 28px; height: 28px; flex: 0 0 28px; display: inline-flex; align-items: center; justify-content: center; border-radius: 50%; background: #0f766e; color: #fff; font-size: 12px; font-weight: 900; box-shadow: 0 1px 2px rgba(15, 23, 42, 0.12); }
.chat-evidence-avatar--user { background: #123b76; }
.chat-evidence-body { max-width: min(360px, 78%); display: flex; flex-direction: column; gap: 3px; }
.chat-evidence-message--user .chat-evidence-body { align-items: flex-end; }
.chat-evidence-message--action .chat-evidence-body { max-width: 90%; align-items: center; }
.chat-evidence-speaker { max-width: 160px; color: #64748b; font-size: 12px; font-weight: 700; line-height: 1.2; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.chat-evidence-message--user .chat-evidence-speaker { text-align: right; }
.chat-evidence-bubble { padding: 7px 10px; border-radius: 8px; background: #f8fafc; color: #0f172a; border: 1px solid #e2e8f0; font-size: 13px; line-height: 1.55; white-space: pre-wrap; word-break: break-word; text-align: left; }
.chat-evidence-message--user .chat-evidence-bubble { background: #d9f7be; color: #102a18; border-color: #b7eb8f; }
.chat-evidence-message--action .chat-evidence-bubble { background: #fff7ed; color: #9a3412; border-color: #fed7aa; }
.chat-records-empty { color: #98a2b3; font-size: 13px; }
.artifact-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 12px; }
.artifact-item { display: flex; justify-content: space-between; gap: 16px; align-items: center; padding: 14px 16px; border: 1px solid #e2e8f2; border-radius: 8px; background: #fff; }
.artifact-item strong { color: #15213b; font-size: 14px; font-weight: 900; }
.artifact-item p { margin: 4px 0 0; color: #667085; font-size: 12px; }
.artifact-item a { color: #2f6df6; font-weight: 700; text-decoration: none; white-space: nowrap; }
.dialogue-list { display: grid; gap: 14px; }
.dialogue-item { padding: 16px 18px; border: 1px solid #e2e8f2; border-radius: 8px; background: #fff; }
.dialogue-item__head strong { display: block; color: #15213b; font-weight: 900; overflow-wrap: anywhere; }
.dialogue-item__head span { display: block; margin-top: 6px; color: #667085; line-height: 1.6; overflow-wrap: anywhere; }
.dialogue-item__columns { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 18px; margin-top: 12px; }
.dialogue-item__columns label { display: block; margin-bottom: 6px; color: #2f6df6; font-size: 12px; font-weight: 900; }
.dialogue-item__columns li { margin-bottom: 4px; color: #344054; line-height: 1.65; overflow-wrap: anywhere; }
.report-table { width: 100%; border-collapse: collapse; table-layout: fixed; border: 1px solid #e2e8f2; }
.report-table th, .report-table td { border-bottom: 1px solid #e2e8f2; border-right: 1px solid #e2e8f2; padding: 13px 18px; vertical-align: top; }
.report-table th:last-child, .report-table td:last-child { border-right: 0; }
.report-table tr:last-child td { border-bottom: 0; }
.report-table th { color: #5d6980; font-size: 13px; font-weight: 900; background: #f7f9fd; text-align: left; }
.assessment-table td:first-child strong { display: block; color: #15213b; font-weight: 900; }
.assessment-table td p { margin-top: 4px; line-height: 1.55; }
.col-score { color: #d3382b; font-weight: 900; white-space: nowrap; }
.score-layout { display: grid; grid-template-columns: minmax(0, 1fr) 280px; gap: 44px; align-items: center; }
.score-summary-line { display: flex; align-items: baseline; gap: 8px; margin-bottom: 12px; }
.score-summary-line strong { color: #2f6df6; font-size: 50px; line-height: 1; font-weight: 900; }
.score-summary-line span { color: #8c98ad; font-size: 20px; font-weight: 800; }
.score-summary-line em { margin-left: 10px; padding: 3px 18px; border-radius: 5px; background: #e9f0ff; color: #2f6df6; font-style: normal; font-size: 13px; font-weight: 900; }
.grade-pass { color: #067647; } .grade-ok { color: #2f6df6; } .grade-fail { color: #d92d20; }
.report-text { line-height: 2; }
.calibration-strip { grid-template-columns: repeat(5, minmax(0, 1fr)); margin: 26px 0 0; border-top: 1px solid #e6ebf3; }
.calibration-strip div { min-width: 0; display: grid; place-items: center; gap: 4px; min-height: 58px; border-right: 1px solid #e6ebf3; }
.calibration-strip div:last-child { border-right: 0; }
.calibration-strip span { color: #6d7890; font-size: 13px; }
.calibration-strip strong { color: #15213b; font-weight: 900; overflow-wrap: anywhere; }
.score-gauge { min-width: 0; height: 210px; }
.notice-list { display: grid; gap: 8px; margin-top: 18px; }
.notice-list p { margin: 0; padding: 10px 14px; color: #8a4b12; background: #fff6eb; border-left: 3px solid #f2a13b; }
.report-list { margin: 0; padding-left: 22px; color: #344054; line-height: 2; }
.advice-list li + li { margin-top: 4px; }
.dialogue-table th:first-child, .dialogue-table td:first-child { width: 38%; }
.dialogue-table td { color: #344054; line-height: 1.75; }
.all-clear-text { margin: 0; color: #067647; font-weight: 800; }
.loading-state, .empty-state, .legacy-state { min-height: 420px; width: min(1160px, calc(100% - 72px)); margin: 36px auto 0; display: flex; flex-direction: column; justify-content: center; align-items: center; text-align: center; padding: 32px; border: 1px solid #e2e8f2; }
.empty-state span { color: #667085; }
:deep(.el-button) { border-radius: 4px; font-weight: 700; }
:deep(.el-button--primary) { background: #2f6df6; border-color: #2f6df6; }
@media (max-width: 1100px) {
  .report-topbar { grid-template-columns: 1fr; height: auto; padding: 18px 24px; gap: 10px; }
  .page-actions { justify-content: flex-start; }
  .summary-layout, .score-layout { grid-template-columns: 1fr; }
  .summary-metrics, .score-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .summary-metrics { border-left: 0; }
  .summary-metrics article { border-left: 1px solid #e1e7f2; }
  .overview-table, .insight-grid, .assessment-summary, .calibration-strip, .artifact-grid, .dialogue-item__columns { grid-template-columns: 1fr; }
  .calibration-strip div { border-right: 0; border-bottom: 1px solid #e6ebf3; }
  .artifact-item { flex-direction: column; align-items: flex-start; }
}
@media (max-width: 720px) {
  .evaluation-page { padding-bottom: 18px; }
  .report-paper, .loading-state, .empty-state, .legacy-state { width: calc(100% - 28px); margin-top: 14px; }
  .paper-hero, .report-section { padding: 24px 18px; }
  .paper-hero span { display: block; margin: 4px 0 0; }
  .summary-copy { padding-left: 0; }
  .summary-metrics, .score-grid { grid-template-columns: 1fr; }
  .overview-table div { grid-template-columns: 82px minmax(0, 1fr); }
  .page-actions, .page-actions .el-button { width: 100%; }
  .chat-evidence-body { max-width: 82%; }
  .dialogue-item__columns { display: grid; }
  .report-section { overflow-x: hidden; }
}
@media print {
  .evaluation-page { padding: 0; background: #fff; }
  .no-print { display: none !important; }
  .report-paper { width: 100%; margin: 0; box-shadow: none; }
}
</style>
