<template>
  <div class="student-page evaluation-page">
    <div v-if="loading" class="loading-state">
      <el-skeleton :rows="10" animated />
    </div>

    <article v-else-if="report" class="evaluation-document">
      <header class="document-toolbar no-print">
        <div>
          <p>训练历史 / 训练评估报告</p>
          <h1>训练评估报告</h1>
        </div>
        <div class="page-actions">
          <el-button plain size="small" @click="printReport">导出报告</el-button>
          <el-button plain size="small" @click="printReport">打印报告</el-button>
          <el-button type="primary" size="small" @click="router.push('/student/hall')">返回训练大厅</el-button>
        </div>
      </header>

      <section v-if="isLegacyReport" class="legacy-state">
        <h2>旧版评估报告</h2>
        <p>当前记录仍是旧版固定维度报告。系统现在只使用 Adaptive V1 评估制度，请重新评估后查看新版报告。</p>
        <el-button type="primary" :loading="refreshing" @click="refreshEvaluation">重新评估</el-button>
      </section>

      <main v-else class="report-paper">
        <header class="paper-header">
          <h2>训练评估报告</h2>
          <span>报告编号：{{ reportMeta.reportNo }}</span>
        </header>

        <section class="report-action-brief">
          <div class="action-verdict">
            <span>本次结论</span>
            <strong>{{ trainingVerdict.title }}</strong>
            <p>{{ trainingVerdict.description }}</p>
          </div>
          <div class="action-card-grid">
            <article v-for="item in reportActionCards" :key="item.label">
              <span>{{ item.label }}</span>
              <strong>{{ item.value }}</strong>
              <p>{{ item.note }}</p>
            </article>
          </div>
          <div class="next-step-list">
            <strong>下一轮训练建议</strong>
            <ol>
              <li v-for="item in nextTrainingSteps" :key="item">{{ item }}</li>
            </ol>
          </div>
        </section>

        <section class="report-section report-section--overview">
          <h3>一、训练概况</h3>
          <div class="overview-table">
            <div><span>案件名称：</span><strong>{{ reportMeta.caseTitle }}</strong></div>
            <div><span>训练场景：</span><strong>{{ reportMeta.sceneName }}</strong></div>
            <div><span>训练时长：</span><strong>{{ reportMeta.duration }}</strong></div>
            <div><span>完成时间：</span><strong>{{ reportMeta.finishedAt }}</strong></div>
            <div><span>评估方式：</span><strong>系统自动评估</strong></div>
            <div><span>评估人：</span><strong>系统评估</strong></div>
          </div>
        </section>

        <section class="report-section">
          <h3>二、能力指标结果</h3>
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
          <h3>三、场景考察点</h3>
          <div class="assessment-summary">
            <div><span>已命中</span><strong>{{ assessmentStats.hit }}</strong></div>
            <div><span>部分命中</span><strong>{{ assessmentStats.partial }}</strong></div>
            <div><span>未命中</span><strong>{{ assessmentStats.missed }}</strong></div>
            <div><span>完成度</span><strong>{{ reportMeta.assessmentRate }}</strong></div>
          </div>
          <p class="report-text assessment-note">
            系统已对 {{ assessmentStats.total }} 项考察点按数量、难度和必考属性动态分配分值。场景未配置的专项能力不会作为固定维度扣分。
          </p>
          <table class="report-table assessment-table">
            <thead>
              <tr><th>考察点</th><th>难度</th><th>属性</th><th>状态</th><th>权重</th><th>得分</th></tr>
            </thead>
            <tbody>
              <tr v-for="item in dedupedAssessmentPointResults" :key="assessmentPointKey(item)">
                <td><strong>{{ item.label }}</strong><p :title="assessmentPointContent(item)">{{ assessmentPointContent(item) }}</p></td>
                <td>{{ item.difficulty_level || difficultyFromWeight(item.weight) }}</td>
                <td>{{ item.required ? '必考' : '选考' }}</td>
                <td>{{ statusLabel(item.status) }}</td>
                <td>{{ percent(item.score_share) }}</td>
                <td class="col-score">{{ item.weighted_score ?? item.score }}/{{ item.full_score ?? '-' }}</td>
              </tr>
            </tbody>
          </table>
        </section>

        <section class="report-section report-section--score">
          <h3>四、综合评分</h3>
          <div class="score-summary-line">
            <strong>{{ report.total_score ?? 0 }}</strong><span>/100</span><em :class="`grade-${reportHeader.gradeClass}`">{{ reportHeader.gradeLevel }}</em>
          </div>
          <p class="report-text">{{ studentScoreIntro }}</p>
          <div class="calibration-strip">
            <div><span>通用能力</span><strong>{{ percent(weighting.common_share) }}</strong></div>
            <div><span>场景考察点</span><strong>{{ percent(weighting.assessment_share) }}</strong></div>
            <div><span>必考命中率</span><strong>{{ percent(assessmentCompletion.required_rate) }}</strong></div>
            <div><span>总分上限</span><strong>{{ scoreCapLabel }}</strong></div>
            <div><span>红线提示</span><strong>{{ redFlags.length ? `${redFlags.length} 项` : '无' }}</strong></div>
          </div>
          <div v-if="studentNoticeItems.length" class="notice-list"><p v-for="item in studentNoticeItems" :key="item">{{ item }}</p></div>
        </section>

        <section class="report-section"><h3>五、综合点评</h3><p class="report-text">{{ enhancedOverallComment }}</p></section>
        <section class="report-section"><h3>六、反馈建议</h3><ul class="report-list advice-list"><li v-for="item in actionableAdviceItems" :key="item">{{ item }}</li></ul></section>

        <section class="report-section">
          <h3>七、对话分析</h3>
          <div v-if="deductionDialogueItems.length" class="dialogue-analysis-list">
            <article v-for="item in deductionDialogueItems" :key="item.key" class="dialogue-analysis-row">
              <div><span>学员发言</span><p>{{ item.utterance }}</p></div>
              <div><span>问题说明</span><p>{{ item.reason }}</p></div>
              <div><span>改进建议</span><p>{{ item.advice }}</p></div>
            </article>
          </div>
          <p v-else class="all-clear-text">本次报告未识别到需要单独展开的扣分发言，可重点查看能力指标结果。</p>
        </section>
      </main>
    </article>

    <div v-else class="empty-state">
      <el-empty :description="emptyState.title">
        <template #description><p>{{ emptyState.title }}</p><span>{{ emptyState.description }}</span></template>
        <div class="empty-actions"><el-button v-if="canResumeTraining" plain size="small" @click="resumeTraining">继续训练</el-button><el-button plain size="small" @click="router.push('/student/history')">训练历史</el-button><el-button type="primary" size="small" @click="router.push('/student/hall')">训练大厅</el-button></div>
      </el-empty>
    </div>
  </div>
</template>


<script setup lang="ts">
import { computed, inject, onMounted, onUnmounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { showToast } from 'vant'
import request from '../utils/request'

const router = useRouter()
const route = useRoute()
const setMainScrollable = inject<(value: boolean) => void>('setMainScrollable')
const report = ref<any>(null)
const loading = ref(true)
const refreshing = ref(false)
const sessionDetail = ref<any>(null)
const emptyState = ref({
  title: '暂无评估数据',
  description: '当前会话可能还未完成评估，或评估结果暂未写入。',
})
let evaluationPollTimer: number | null = null

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

const reportActionCards = computed(() => {
  const requiredRate = percent(assessmentCompletion.value?.required_rate)
  const weakDimension = weakCommonScoreItems.value[0]?.dimension || '暂无明显短板'
  const weakPoint = weakAssessmentItems.value[0]?.label || '暂无未命中考察点'
  return [
    { label: '综合得分', value: `${Math.round(Number(report.value?.total_score || 0))}`, note: reportHeader.value.gradeLevel },
    { label: '必考命中率', value: requiredRate, note: scoreCapLabel.value === '无' ? '未触发额外上限' : `总分上限 ${scoreCapLabel.value}` },
    { label: '优先补强能力', value: weakDimension, note: weakCommonScoreItems.value[0]?.reason || '继续保持现有训练节奏' },
    { label: '优先补齐考察点', value: weakPoint, note: weakAssessmentItems.value[0]?.content || weakAssessmentItems.value[0]?.feedback || '本场景考察点完成较完整' },
  ]
})

const nextTrainingSteps = computed(() => {
  const steps = actionableAdviceItems.value.slice(0, 3)
  if (steps.length >= 3) return steps
  const fallback = [
    '重新训练前先阅读本报告中的未命中考察点，明确下一轮必须主动问到或做到的内容。',
    '训练中按“身份核实-事实经过-风险判断-处置告知-收尾确认”的顺序推进。',
    '结束前用一句话复述已核实事实，并明确下一步处置安排。',
  ]
  return Array.from(new Set([...steps, ...fallback])).slice(0, 3)
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

const deductionDialogueItems = computed(() => {
  const items: Array<{ key: string; utterance: string; reason: string; advice: string }> = []
  for (const score of weakCommonScoreItems.value) {
    const reason = String(score.reason || `${score.dimension}存在不足。`)
    if (!hasNegativeReason(reason) && scoreRatio(score) > 0.75) continue
    items.push({
      key: `score-${score.dimension}`,
      utterance: findUtteranceFromEvidence(score.evidence || []),
      reason,
      advice: adviceForReason(reason),
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
    const res: any = await request.get(`/training/session/${sessionId}`, { _skipErrorToast: true } as any)
    sessionDetail.value = res || null
    if (!res.evaluation_result) {
      if (res.status === 'evaluating' && (options.attempt || 0) < 12) {
        setEmptyState('评估报告生成中', '系统正在生成评估报告，请稍候。')
        loading.value = false
        clearEvaluationPoll()
        evaluationPollTimer = window.setTimeout(() => {
          loading.value = true
          void fetchEvaluation({ silent: true, attempt: (options.attempt || 0) + 1 })
        }, 1200)
        return
      }
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
  } catch {
    showToast('获取评估报告失败')
    setEmptyState('加载失败', '请稍后重试。')
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
  await fetchEvaluation()
  if (route.query.refresh === '1') {
    await refreshEvaluation()
    const nextQuery = { ...route.query }
    delete nextQuery.refresh
    router.replace({ query: nextQuery })
  }
})

onUnmounted(() => {
  clearEvaluationPoll()
  setMainScrollable?.(false)
})
</script>

<style scoped>
.evaluation-page { min-height: 100%; padding: 20px 28px 36px; background: #f3f5f8; color: #1f2937; font-size: 15px; line-height: 1.75; }
.evaluation-document { max-width: 1280px; margin: 0 auto; }
.document-toolbar { height: 56px; display: flex; align-items: center; justify-content: space-between; gap: 16px; margin-bottom: 14px; }
.document-toolbar p { margin: 0 0 4px; color: #667085; font-size: 13px; }
.document-toolbar h1 { margin: 0; color: #111827; font-size: 24px; font-weight: 900; }
.page-actions, .empty-actions { display: flex; flex-wrap: wrap; gap: 10px; justify-content: flex-end; }
.report-paper, .legacy-state, .loading-state, .empty-state { background: #fff; border: 1px solid #d9e0ea; }
.report-paper { padding: 38px 48px 44px; min-height: 760px; }
.paper-header { position: relative; display: flex; justify-content: center; padding-bottom: 24px; border-bottom: 2px solid #c8d1df; }
.paper-header h2 { margin: 0; color: #111827; font-size: 30px; font-weight: 900; letter-spacing: 0; }
.paper-header span { position: absolute; right: 0; bottom: 14px; color: #667085; font-size: 13px; }
.report-action-brief { display: grid; grid-template-columns: 1.15fr 2fr; gap: 14px; margin: 20px 0 2px; border: 1px solid #d8e0ea; background: #f8fbff; padding: 16px; }
.action-verdict { display: grid; align-content: start; gap: 6px; border-right: 1px solid #d8e0ea; padding-right: 14px; }
.action-verdict span, .action-card-grid span, .next-step-list strong { color: #475467; font-size: 13px; font-weight: 900; }
.action-verdict strong { color: #111827; font-size: 22px; line-height: 1.25; font-weight: 900; }
.action-verdict p, .action-card-grid p { margin: 0; color: #667085; font-size: 13px; line-height: 1.7; }
.action-card-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 10px; }
.action-card-grid article { border: 1px solid #e5e7eb; background: #fff; padding: 12px; }
.action-card-grid strong { display: block; margin: 5px 0; color: #165dff; font-size: 18px; line-height: 1.3; font-weight: 900; }
.next-step-list { grid-column: 1 / -1; border-top: 1px solid #d8e0ea; padding-top: 12px; }
.next-step-list ol { margin: 8px 0 0; padding-left: 20px; color: #344054; line-height: 1.8; }
.report-section { padding: 24px 0; border-bottom: 1px solid #d8e0ea; }
.report-section:last-child { border-bottom: 0; }
.report-section h3 { margin: 0 0 14px; color: #111827; font-size: 19px; font-weight: 900; }
.report-text { margin: 0; color: #1f2937; line-height: 2; text-indent: 2em; }
.overview-table, .score-grid, .assessment-summary, .calibration-strip, .dialogue-analysis-list { border-top: 1px solid #d8e0ea; border-left: 1px solid #d8e0ea; }
.overview-table { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); }
.overview-table div, .calibration-strip div { min-width: 0; display: flex; gap: 8px; align-items: center; }
.overview-table div { min-height: 44px; padding: 9px 14px; border-right: 1px solid #d8e0ea; border-bottom: 1px solid #d8e0ea; }
.overview-table span, .calibration-strip span { color: #475467; white-space: nowrap; }
.overview-table strong, .calibration-strip strong { color: #111827; font-weight: 800; overflow-wrap: anywhere; }
.score-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); }
.score-item { min-height: 132px; padding: 16px; border-right: 1px solid #d8e0ea; border-bottom: 1px solid #d8e0ea; background: #fff; }
.score-item__head { display: flex; justify-content: space-between; gap: 16px; align-items: center; }
.score-item__head strong { color: #111827; font-weight: 900; }
.score-item__head span { color: #165dff; font-weight: 900; white-space: nowrap; }
.score-item p { margin: 10px 0 0; color: #475467; line-height: 1.8; }
.score-bar { height: 7px; margin-top: 12px; background: #e5e7eb; overflow: hidden; }
.score-bar i { display: block; height: 100%; background: #165dff; }
.assessment-summary, .calibration-strip { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); margin-bottom: 14px; }
.assessment-summary div, .calibration-strip div { min-height: 54px; padding: 10px 14px; border-right: 1px solid #d8e0ea; border-bottom: 1px solid #d8e0ea; justify-content: center; }
.assessment-summary span { color: #667085; }
.assessment-summary strong { color: #111827; font-size: 22px; font-weight: 900; }
.assessment-note { margin-bottom: 14px; color: #475467; }
.report-table { width: 100%; border-collapse: collapse; table-layout: fixed; border: 1px solid #d8e0ea; }
.report-table th, .report-table td { border-bottom: 1px solid #d8e0ea; border-right: 1px solid #d8e0ea; padding: 10px 12px; vertical-align: middle; }
.report-table th:last-child, .report-table td:last-child { border-right: 0; }
.report-table tr:last-child td { border-bottom: 0; }
.report-table th { color: #1f2937; font-size: 13px; font-weight: 900; background: #f5f7fa; text-align: left; }
.assessment-table th:nth-child(n + 2), .assessment-table td:nth-child(n + 2) { text-align: center; }
.assessment-table th:first-child, .assessment-table td:first-child { width: 42%; }
.assessment-table td:first-child strong { display: block; color: #111827; font-weight: 900; }
.assessment-table td p { margin: 4px 0 0; color: #667085; line-height: 1.55; }
.col-score { color: #d92d20; font-weight: 900; white-space: nowrap; }
.report-section--score .report-text { margin-top: 12px; }
.score-summary-line { display: flex; align-items: baseline; gap: 8px; margin-bottom: 8px; }
.score-summary-line strong { color: #d92d20; font-size: 44px; line-height: 1; font-weight: 900; }
.score-summary-line span { color: #98a2b3; font-size: 20px; font-weight: 800; }
.score-summary-line em { margin-left: 8px; padding: 3px 10px; border: 1px solid currentColor; font-style: normal; font-size: 13px; font-weight: 900; }
.grade-pass { color: #067647; } .grade-ok { color: #b54708; } .grade-fail { color: #d92d20; }
.calibration-strip { grid-template-columns: repeat(5, minmax(0, 1fr)); margin: 14px 0 0; }
.notice-list { display: grid; gap: 8px; margin-top: 14px; }
.notice-list p { margin: 0; padding: 8px 12px; color: #7a2e0e; background: #fff7ed; border-left: 3px solid #f79009; }
.report-list { margin: 0; padding-left: 22px; color: #1f2937; line-height: 2; }
.advice-list li + li { margin-top: 6px; }
.dialogue-analysis-list { display: grid; }
.dialogue-analysis-row { display: grid; grid-template-columns: 1.1fr 1fr 1fr; border-bottom: 1px solid #d8e0ea; }
.dialogue-analysis-row > div { padding: 12px 14px; border-right: 1px solid #d8e0ea; }
.dialogue-analysis-row span { display: block; margin-bottom: 6px; color: #475467; font-size: 13px; font-weight: 900; }
.dialogue-analysis-row p, .all-clear-text { margin: 0; color: #1f2937; line-height: 1.8; }
.all-clear-text { color: #067647; font-weight: 800; }
.loading-state, .empty-state, .legacy-state { min-height: 420px; display: flex; flex-direction: column; justify-content: center; align-items: center; text-align: center; padding: 32px; }
.empty-state span { color: #667085; }
:deep(.el-button) { border-radius: 4px; font-weight: 700; }
:deep(.el-button--primary) { background: #165dff; border-color: #165dff; }
@media (max-width: 1100px) { .overview-table, .score-grid, .assessment-summary, .calibration-strip, .dialogue-analysis-row { grid-template-columns: 1fr; } .paper-header { justify-content: flex-start; display: block; } .paper-header span { position: static; display: block; margin-top: 8px; } }
@media (max-width: 720px) { .evaluation-page { padding: 14px; } .document-toolbar { height: auto; align-items: flex-start; flex-direction: column; } .page-actions, .page-actions .el-button { width: 100%; } .report-paper { padding: 24px 18px; } }
@media print { .evaluation-page { padding: 0; background: #fff; } .no-print { display: none !important; } .report-paper { border: 0; padding: 0; } }
</style>
