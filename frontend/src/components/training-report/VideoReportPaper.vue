<template>
  <main class="report-paper">
    <header class="paper-hero">
      <div>
        <h2>视频实训评估报告</h2>
        <p>
          报告编号：VR-{{ report?.session_id || '0000' }}
          <span>评估日期：{{ reportFinishedAt || '未记录' }}</span>
        </p>
      </div>
    </header>

    <section class="report-section report-section--summary">
      <div class="section-title"><i></i><span>本次结论</span></div>
      <div class="summary-layout">
        <div class="summary-copy">
          <div class="verdict-card" :class="`verdict-card--${verdict.tone}`">
            <span>{{ verdict.label }}</span>
            <strong>{{ verdict.title }}</strong>
          </div>
          <h3>{{ reportGrade }}</h3>
          <p>{{ scoreHint }}</p>
        </div>
        <div class="summary-metrics">
          <article>
            <span>综合得分</span>
            <strong>{{ reportScore }}</strong>
            <p>/ {{ reportFullScore }} 分</p>
          </article>
          <article>
            <span>得分率</span>
            <strong>{{ reportPercentage }}%</strong>
            <p>{{ reportModeLabel }}</p>
          </article>
          <article>
            <span>通过节点</span>
            <strong>{{ reportPassCount }}</strong>
            <p>共 {{ reportTotalNodes }} 个节点</p>
          </article>
        </div>
      </div>
      <div class="insight-grid">
        <article>
          <span>优势亮点</span>
          <strong>{{ strengthTitle }}</strong>
          <p>{{ strengthNote }}</p>
        </article>
        <article>
          <span>提升建议</span>
          <strong>{{ weaknessTitle }}</strong>
          <p>{{ weaknessNote }}</p>
        </article>
      </div>
    </section>

    <section class="report-section">
      <div class="section-title"><i></i><span>训练概况</span></div>
      <div class="overview-table">
        <div><span>实训名称</span><strong>{{ reportTitle }}</strong></div>
        <div><span>训练模式</span><strong>{{ reportModeLabel }}</strong></div>
        <div><span>通过节点</span><strong>{{ reportPassCount }}</strong></div>
        <div><span>未通过节点</span><strong>{{ reportFailCount }}</strong></div>
        <div><span>跳过节点</span><strong>{{ reportSkipCount }}</strong></div>
        <div><span>违规次数</span><strong>{{ reportViolationCount }}</strong></div>
        <div><span>总扣分</span><strong>{{ reportTotalDeducted }}</strong></div>
        <div><span>完成时间</span><strong>{{ reportFinishedAt || '未记录' }}</strong></div>
      </div>
    </section>

    <section v-if="dimensionScores.length" class="report-section">
      <div class="section-title"><i></i><span>能力指标结果</span></div>
      <div class="score-grid">
        <article v-for="item in dimensionScores" :key="item.key" class="score-item" :class="scoreItemClass(item.percentage)">
          <div class="score-item__head">
            <strong>{{ item.label }}</strong>
            <span>{{ item.score }}/{{ item.full_score }} 分</span>
          </div>
          <div class="score-bar"><i :style="{ width: `${item.percentage}%` }"></i></div>
          <p>完成度 {{ item.percentage }}%，基于节点动作、话术与流程表现综合判定。</p>
        </article>
      </div>
    </section>

    <section v-if="assessmentChecks.length" class="report-section">
      <div class="section-title"><i></i><span>考察点核查</span></div>
      <div class="assessment-summary">
        <div><span>已完成</span><strong>{{ assessmentStats.hit }}</strong><em>项</em></div>
        <div><span>部分完成</span><strong>{{ assessmentStats.partial }}</strong><em>项</em></div>
        <div><span>未完成</span><strong>{{ assessmentStats.missed }}</strong><em>项</em></div>
        <div><span>完成度</span><strong>{{ assessmentCompletionRate }}%</strong></div>
      </div>
      <div v-if="assessmentIssueGroups.length" class="assessment-compact-list">
        <article v-for="item in assessmentIssueGroups" :key="item.label" class="assessment-compact-item">
          <div>
            <strong>{{ item.label }}</strong>
            <p>{{ item.note }}</p>
          </div>
          <span>{{ item.count }} 项</span>
        </article>
      </div>
      <p v-else class="assessment-compact-note">本次视频实训未识别到需要单独展开的考察点问题，可重点查看能力指标和节点明细。</p>
    </section>

    <section class="report-section report-section--score">
      <div class="section-title"><i></i><span>综合得分</span></div>
      <div class="score-report-layout">
        <div class="score-report-copy">
          <div class="score-report-main">
            <strong>{{ reportScore }}</strong><span>/{{ normalizedFullScore }}</span>
            <em :class="`score-report-grade--${verdict.tone}`">{{ reportGrade }}</em>
          </div>
          <p class="report-text">{{ scoreNarrative }}</p>
          <div class="score-breakdown">
            <div v-for="item in scoreBreakdownItems" :key="item.label">
              <span>{{ item.label }}</span>
              <strong>{{ item.value }}</strong>
            </div>
          </div>
        </div>
        <div class="score-donut" :style="{ '--score-angle': `${scoreAngle}deg` }">
          <div>
            <strong>{{ reportScore }}</strong>
            <span>/{{ normalizedFullScore }}</span>
            <em>{{ verdict.label }}</em>
          </div>
        </div>
      </div>
      <div v-if="scoreNoticeItems.length" class="score-notices">
        <p v-for="item in scoreNoticeItems" :key="item">{{ item }}</p>
      </div>
    </section>

    <section v-if="feedbackAdviceItems.length" class="report-section">
      <div class="section-title"><i></i><span>反馈建议</span></div>
      <ol class="report-list advice-list">
        <li v-for="item in feedbackAdviceItems" :key="item">{{ item }}</li>
      </ol>
    </section>

    <section class="report-section">
      <div class="section-title"><i></i><span>节点明细</span></div>
      <div class="node-list">
        <article
          v-for="item in problemNodes"
          :key="`problem-${item.node_index}`"
          class="node-item node-item--attention"
        >
          <div class="node-item__head">
            <strong>{{ item.node_title || `节点 ${item.node_index + 1}` }}</strong>
            <span class="node-item__result" :class="`node-item__result--${item.result}`">{{ resultLabel(item.result) }}</span>
          </div>
          <div class="node-item__meta">
            <span>序号 {{ item.node_index + 1 }}</span>
            <span>得分 {{ item.score_earned }}</span>
            <span v-if="item.score_deducted">扣分 {{ item.score_deducted }}</span>
            <span v-if="item.retry_count">重试 x{{ item.retry_count }}</span>
          </div>
          <div v-if="item.speech_transcript" class="node-item__speech">语音识别：{{ item.speech_transcript }}</div>
          <div v-if="item.failure_reasons?.length" class="node-item__issues">
            失分原因：{{ item.failure_reasons.map(formatFailureReason).join('、') }}
          </div>
          <div v-if="item.manual_review?.review_note" class="node-item__speech">
            复核说明：{{ item.manual_review.review_note }}
          </div>
          <div v-if="reviewable" class="node-item__actions">
            <el-button size="small" type="primary" plain @click="emit('review-node', item)">人工复核 / 改判</el-button>
          </div>
        </article>
        <div v-if="!problemNodes.length" class="node-clear-state">
          本次训练暂无明显异常节点，可结合能力指标继续巩固。
        </div>
      </div>

      <details v-if="passedNodes.length" class="node-group">
        <summary class="node-group__title">已通过节点（{{ passedNodes.length }}）</summary>
        <div class="node-list">
          <article v-for="item in passedNodes" :key="`pass-${item.node_index}`" class="node-item">
            <div class="node-item__head">
              <strong>{{ item.node_title || `节点 ${item.node_index + 1}` }}</strong>
              <span class="node-item__result" :class="`node-item__result--${item.result}`">{{ resultLabel(item.result) }}</span>
            </div>
            <div class="node-item__meta">
              <span>序号 {{ item.node_index + 1 }}</span>
              <span>得分 {{ item.score_earned }}</span>
              <span v-if="item.retry_count">重试 x{{ item.retry_count }}</span>
            </div>
            <div v-if="item.speech_transcript" class="node-item__speech">语音识别：{{ item.speech_transcript }}</div>
            <div v-if="item.manual_review?.review_note" class="node-item__speech">
              复核说明：{{ item.manual_review.review_note }}
            </div>
            <div v-if="reviewable" class="node-item__actions">
              <el-button size="small" plain @click="emit('review-node', item)">查看 / 复核</el-button>
            </div>
          </article>
        </div>
      </details>
    </section>
  </main>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import {
  formatDateTime,
  formatFailureReason,
  resultLabel,
  useVideoReportMetrics,
  type VideoReportData,
  type VideoReportNode,
} from '../../composables/useVideoReportMetrics'

const props = withDefaults(defineProps<{
  report: VideoReportData | null
  reviewable?: boolean
}>(), {
  reviewable: false,
})

const emit = defineEmits<{
  'review-node': [item: VideoReportNode]
}>()

const metrics = computed(() => useVideoReportMetrics(props.report))

const reportTitle = computed(() => metrics.value.reportTitle)
const reportModeLabel = computed(() => metrics.value.reportModeLabel)
const reportPercentage = computed(() => metrics.value.reportPercentage)
const reportFinishedAt = computed(() => metrics.value.reportFinishedAt)
const reportScore = computed(() => metrics.value.reportScore)
const reportFullScore = computed(() => metrics.value.reportFullScore)
const reportGrade = computed(() => metrics.value.reportGrade)
const reportPassCount = computed(() => metrics.value.reportPassCount)
const reportSkipCount = computed(() => metrics.value.reportSkipCount)
const reportFailCount = computed(() => metrics.value.reportFailCount)
const reportViolationCount = computed(() => metrics.value.reportViolationCount)
const reportTotalDeducted = computed(() => metrics.value.reportTotalDeducted)
const reportTotalNodes = computed(() => metrics.value.reportTotalNodes)
const reportNodes = computed(() => metrics.value.reportNodes)
const dimensionScores = computed(() => metrics.value.dimensionScores)
const weaknessSummary = computed(() => metrics.value.weaknessSummary)
const assessmentChecks = computed(() => metrics.value.assessmentChecks)
const scoreHint = computed(() => metrics.value.scoreHint)
const failureReasonList = computed(() => metrics.value.failureReasonList)
const violationList = computed(() => metrics.value.violationList)
const strengthTitle = computed(() => metrics.value.strengthTitle)
const strengthNote = computed(() => metrics.value.strengthNote)
const weaknessTitle = computed(() => metrics.value.weaknessTitle)
const weaknessNote = computed(() => metrics.value.weaknessNote)

const problemNodes = computed(() =>
  reportNodes.value.filter((item) =>
    item.result !== 'pass' ||
    Number(item.score_deducted || 0) > 0 ||
    Boolean(item.failure_reasons?.length) ||
    Boolean(item.manual_review?.review_note)
  )
)
const passedNodes = computed(() => reportNodes.value.filter((item) => !problemNodes.value.includes(item)))
const normalizedFullScore = computed(() => reportFullScore.value || 100)
const scoreAngle = computed(() => Math.max(0, Math.min(360, Math.round((reportPercentage.value / 100) * 360))))
const normalizedAssessmentStatus = (status?: string) => {
  if (status === 'hit' || status === 'partial') return status
  return 'missed'
}

const assessmentStats = computed(() => {
  const hit = assessmentChecks.value.filter((item) => normalizedAssessmentStatus(item.status) === 'hit').length
  const partial = assessmentChecks.value.filter((item) => normalizedAssessmentStatus(item.status) === 'partial').length
  const missed = Math.max(assessmentChecks.value.length - hit - partial, 0)
  return { hit, partial, missed }
})
const assessmentCompletionRate = computed(() => {
  if (!assessmentChecks.value.length) return 0
  const weightedHits = assessmentStats.value.hit + assessmentStats.value.partial * 0.5
  return Math.round((weightedHits / assessmentChecks.value.length) * 100)
})
const assessmentIssueGroups = computed(() => {
  const groups = new Map<string, { label: string; count: number; missed: number; partial: number; stages: Set<string> }>()
  for (const item of assessmentChecks.value) {
    const status = normalizedAssessmentStatus(item.status)
    if (status === 'hit') continue
    const label = item.label || item.content || '未命名考察点'
    const current = groups.get(label) || { label, count: 0, missed: 0, partial: 0, stages: new Set<string>() }
    current.count += 1
    if (status === 'missed') current.missed += 1
    if (status === 'partial') current.partial += 1
    if (item.stage_name) current.stages.add(item.stage_name)
    groups.set(label, current)
  }
  return [...groups.values()]
    .sort((left, right) => right.missed - left.missed || right.count - left.count)
    .slice(0, 3)
    .map((item) => {
      const stageText = [...item.stages].slice(0, 2).join('、')
      const statusText = item.missed ? `${item.missed} 项未完成` : `${item.partial} 项部分完成`
      return {
        label: item.label,
        count: item.count,
        note: `${statusText}${stageText ? `，涉及 ${stageText}${item.stages.size > 2 ? '等节点' : ''}` : ''}。`,
      }
    })
})

const verdict = computed(() => {
  if (!props.report?.report_ready && props.report?.evaluation_status && props.report.evaluation_status !== 'completed') {
    return { tone: 'pending', label: '待评定', title: '报告尚未完成评估' }
  }
  if (reportPercentage.value < 60 || reportFailCount.value > 0) {
    return { tone: 'danger', label: '需重训', title: '存在未通过节点，请优先复盘' }
  }
  if (reportPercentage.value < 80 || reportSkipCount.value > 0 || reportViolationCount.value > 0 || problemNodes.value.length > 0) {
    return { tone: 'warn', label: '建议复盘', title: '整体完成，可针对薄弱项巩固' }
  }
  return { tone: 'success', label: '通过', title: '表现稳定，可进入下一阶段' }
})

const scoreBreakdownItems = computed(() => [
  { label: '得分率', value: `${reportPercentage.value}%` },
  { label: '通过率', value: reportTotalNodes.value ? `${Math.round((reportPassCount.value / reportTotalNodes.value) * 100)}%` : '0%' },
  { label: '未通过', value: `${reportFailCount.value} 项` },
  { label: '跳过/超时', value: `${reportSkipCount.value} 项` },
  { label: '违规记录', value: reportViolationCount.value ? `${reportViolationCount.value} 次` : '无' },
])

const scoreNarrative = computed(() => {
  if (reportPercentage.value >= 90) {
    return `综合得分 ${reportScore.value} 分，整体表现稳定，动作、话术和流程控制较完整。`
  }
  if (reportPercentage.value >= 70) {
    return `综合得分 ${reportScore.value} 分，已达到基础要求，但仍建议围绕失分节点进行针对性复盘。`
  }
  return `综合得分 ${reportScore.value} 分，当前未达到稳定训练标准，建议先完成关键节点补练后再进入下一阶段。`
})

const scoreNoticeItems = computed(() => {
  const notices: string[] = []
  if (reportPercentage.value < 60) notices.push('重点提醒：综合得分低于 60%，建议优先完成未通过节点补练。')
  if (assessmentChecks.value.length && assessmentCompletionRate.value < 60) notices.push('重点提醒：考察点完成度偏低，请对照表格逐项补齐有效动作或证据。')
  if (reportViolationCount.value > 0) notices.push(`重点提醒：本次训练出现 ${reportViolationCount.value} 次违规记录，可能影响最终评级。`)
  if (!notices.length && problemNodes.value.length) notices.push('重点提醒：存在扣分或复核节点，请结合节点明细完成复盘。')
  return notices
})

const priorityActions = computed(() => {
  const actions: string[] = []
  for (const item of problemNodes.value.slice(0, 2)) {
    const title = item.node_title || `节点 ${item.node_index + 1}`
    const reasons = item.failure_reasons?.map(formatFailureReason).join('、')
    actions.push(`重练第 ${item.node_index + 1} 节点：${title}${reasons ? `，重点处理${reasons}` : ''}`)
  }
  for (const item of failureReasonList.value.slice(0, 2)) {
    actions.push(`高频失分：${item.label}出现 ${item.count} 次，训练时需单独核对。`)
  }
  for (const item of violationList.value.slice(0, 1)) {
    actions.push(`训练纪律：${item.label}出现 ${item.count} 次，避免影响最终评级。`)
  }
  for (const item of weaknessSummary.value.slice(0, 2)) {
    actions.push(item)
  }
  return Array.from(new Set(actions)).slice(0, 3)
})

const feedbackAdviceItems = computed(() => {
  const advice: string[] = []
  advice.push(...priorityActions.value)
  for (const item of dimensionScores.value.filter((score) => score.percentage < 70).slice(0, 2)) {
    advice.push(`能力补强：${item.label}完成度为 ${item.percentage}%，下一轮训练需针对该能力重复演练。`)
  }
  if (!advice.length) {
    advice.push('继续保持当前训练节奏，下一轮可提高训练难度或进入考核模式。')
  }
  return Array.from(new Set(advice)).slice(0, 4)
})

function scoreItemClass(percentage: number) {
  if (percentage >= 85) return 'score-item--good'
  if (percentage >= 70) return 'score-item--warn'
  return 'score-item--weak'
}
</script>

<style scoped src="../../styles/training-report-shell.css"></style>
