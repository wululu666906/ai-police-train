<template>
  <div class="evaluation-page">
    <div v-if="loading" class="loading-state">
      <van-loading color="#165DFF" vertical>正在加载评估报告...</van-loading>
    </div>

    <article v-else-if="report" class="evaluation-shell">
      <header class="page-heading">
        <div>
          <h1>训练评估报告</h1>
          <div class="meta-strip">
            <div class="meta-item">
              <span>案件名称</span>
              <strong>{{ reportMeta.caseTitle }}</strong>
            </div>
            <div class="meta-item">
              <span>训练场景</span>
              <strong>{{ reportMeta.sceneName }}</strong>
            </div>
            <div class="meta-item">
              <span>训练时长</span>
              <strong>{{ reportMeta.duration }}</strong>
            </div>
            <div class="meta-item">
              <span>完成时间</span>
              <strong>{{ reportMeta.finishedAt }}</strong>
            </div>
            <div class="meta-item">
              <span>评估人</span>
              <strong>系统评估</strong>
            </div>
          </div>
        </div>
        <div class="page-actions">
          <van-button plain size="small" icon="down" @click="printReport">导出报告</van-button>
          <van-button plain size="small" icon="printer" @click="printReport">打印报告</van-button>
          <van-button type="primary" size="small" icon="cross" @click="router.push('/student/hall')">返回训练大厅</van-button>
        </div>
      </header>

      <div class="report-layout">
        <aside class="summary-panel">
          <section class="summary-card score-card">
            <h2>综合评分</h2>
            <div class="score-line">
              <strong>{{ report.total_score ?? 0 }}</strong>
              <span>/100</span>
            </div>
            <div class="grade-badge" :class="`grade-${reportHeader.gradeClass}`">{{ reportHeader.gradeLevel }}</div>
            <p>{{ scoreSummary }}</p>
          </section>

          <section class="summary-card">
            <h2>能力短板 TOP3</h2>
            <div v-for="item in weakestScoreItems" :key="item.dimension" class="weakness-row">
              <span>{{ item.dimension }}</span>
              <strong>{{ item.score }}/{{ item.full_score }}</strong>
            </div>
          </section>

          <section class="summary-card">
            <h2>训练收尾</h2>
            <div class="closure-row">
              <span>会话结果</span>
              <strong>{{ reportMeta.passLabel }}</strong>
            </div>
            <div class="closure-row">
              <span>考察点完成度</span>
              <strong>{{ reportMeta.assessmentRate }}</strong>
            </div>
            <div class="closure-row">
              <span>阶段完成</span>
              <strong>{{ reportMeta.stageProgress }}</strong>
            </div>
            <van-button block plain :loading="refreshing" @click="refreshEvaluation">重新评估</van-button>
          </section>
        </aside>

        <main class="formal-report">
          <header class="document-header">
            <h2>训练评估报告</h2>
            <span>报告编号：{{ reportMeta.reportNo }}</span>
          </header>

          <section class="report-section">
            <h3>一、训练概述</h3>
            <div class="overview-table">
              <div><span>案件名称：</span><strong>{{ reportMeta.caseTitle }}</strong></div>
              <div><span>完成时间：</span><strong>{{ reportMeta.finishedAt }}</strong></div>
              <div><span>训练场景：</span><strong>{{ reportMeta.sceneName }}</strong></div>
              <div><span>评估方式：</span><strong>系统自动评估</strong></div>
              <div><span>训练时长：</span><strong>{{ reportMeta.duration }}</strong></div>
              <div><span>评估人：</span><strong>系统评估</strong></div>
            </div>
          </section>

          <section class="report-section">
            <h3>二、总体评价</h3>
            <p class="report-text">{{ overallComment }}</p>
          </section>

          <section class="report-section">
            <h3>三、评分结果</h3>
            <p class="report-text">
              综合得分 {{ report.total_score ?? 0 }} 分（满分 100 分），评定等级为 {{ reportHeader.gradeLevel }}。
              {{ scoreSummary }}
            </p>
          </section>

          <section class="report-section">
            <h3>四、各维度评估</h3>
            <table class="report-table">
              <tbody>
                <tr v-for="(item, index) in scoreItems" :key="item.dimension">
                  <td class="col-index">{{ Number(index) + 1 }}.</td>
                  <td>{{ item.dimension }}</td>
                  <td>{{ item.reason || '该维度已纳入系统综合评估。' }}</td>
                  <td class="col-score">{{ item.score }}/{{ item.full_score }} 分</td>
                </tr>
              </tbody>
            </table>
          </section>

          <section v-if="assessmentPointResults.length" class="report-section">
            <h3>五、考察点完成情况</h3>
            <div class="assessment-summary">
              <div>
                <span>已命中</span>
                <strong>{{ assessmentStats.hit }}</strong>
              </div>
              <div>
                <span>部分命中</span>
                <strong>{{ assessmentStats.partial }}</strong>
              </div>
              <div>
                <span>未命中</span>
                <strong>{{ assessmentStats.missed }}</strong>
              </div>
              <div>
                <span>完成度</span>
                <strong>{{ reportMeta.assessmentRate }}</strong>
              </div>
            </div>
            <p class="report-text assessment-note">
              系统已对 {{ assessmentStats.total }} 项考察点完成情况进行归并统计。为保持报告简洁，正文仅列出需要重点关注的未完成或部分完成事项。
            </p>
            <table v-if="keyAssessmentItems.length" class="report-table compact-table">
              <tbody>
                <tr v-for="item in keyAssessmentItems" :key="`${item.stage_name}-${item.id}-${item.label}`">
                  <td>{{ item.label }}</td>
                  <td>{{ item.stage_name || '综合阶段' }}</td>
                  <td class="col-score">{{ statusLabel(item.status) }}</td>
                </tr>
              </tbody>
            </table>
            <p v-else class="all-clear-text">本次训练关键考察点均已达到要求。</p>
            <details v-if="dedupedAssessmentPointResults.length > keyAssessmentItems.length" class="detail-collapse">
              <summary>查看全部考察点明细（{{ dedupedAssessmentPointResults.length }} 项）</summary>
              <table class="report-table compact-table">
                <tbody>
                  <tr v-for="item in dedupedAssessmentPointResults" :key="`all-${item.stage_name}-${item.id}-${item.label}`">
                    <td>{{ item.label }}</td>
                    <td>{{ item.stage_name || '综合阶段' }}</td>
                    <td class="col-score">{{ statusLabel(item.status) }}</td>
                  </tr>
                </tbody>
              </table>
            </details>
          </section>

          <section class="report-section">
            <h3>{{ assessmentPointResults.length ? '六' : '五' }}、改进建议</h3>
            <ul class="report-list">
              <li v-for="item in finalImprovementItems" :key="item">{{ item }}</li>
            </ul>
          </section>

          <section class="report-section">
            <h3>{{ assessmentPointResults.length ? '七' : '六' }}、综合点评</h3>
            <p class="report-text">{{ report.suggestions || overallComment }}</p>
          </section>
        </main>
      </div>
    </article>

    <div v-else class="empty-state">
      <p>{{ emptyState.title }}</p>
      <span>{{ emptyState.description }}</span>
      <div class="empty-actions">
        <van-button v-if="canResumeTraining" plain size="small" @click="resumeTraining">继续训练</van-button>
        <van-button plain size="small" @click="router.push('/student/history')">训练历史</van-button>
        <van-button type="primary" size="small" @click="router.push('/student/hall')">训练大厅</van-button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { showToast } from 'vant'
import request from '../utils/request'

const router = useRouter()
const route = useRoute()
const report = ref<any>(null)
const loading = ref(true)
const refreshing = ref(false)
const sessionDetail = ref<any>(null)
const emptyState = ref({
  title: '暂无评估数据',
  description: '当前会话可能还未完成评估，或评估结果暂未写入。',
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

const scoreItems = computed(() => (Array.isArray(report.value?.scores) ? report.value.scores : []))
const improvementItems = computed(() => (Array.isArray(report.value?.improvements) ? report.value.improvements : []))
const assessmentPointResults = computed(() =>
  Array.isArray(report.value?.assessment_point_results) ? report.value.assessment_point_results : [],
)
const dedupedAssessmentPointResults = computed(() => {
  const rank: Record<string, number> = { miss: 0, partial: 1, hit: 2 }
  const map = new Map<string, any>()
  for (const item of assessmentPointResults.value) {
    const label = String(item?.label || '').replace(/（.*?）|\(.*?\)/g, '').trim()
    const stageName = String(item?.stage_name || '综合阶段').trim()
    const key = `${label}__${stageName}`
    const current = map.get(key)
    if (!current || (rank[item?.status] ?? 0) < (rank[current?.status] ?? 0)) {
      map.set(key, { ...item, label: label || item?.label || '未命名考察点', stage_name: stageName })
    }
  }
  return Array.from(map.values())
})
const assessmentStats = computed(() => {
  const items = dedupedAssessmentPointResults.value
  const hit = items.filter((item: any) => item.status === 'hit').length
  const partial = items.filter((item: any) => item.status === 'partial').length
  const missed = items.filter((item: any) => item.status !== 'hit' && item.status !== 'partial').length
  return { total: items.length, hit, partial, missed }
})
const keyAssessmentItems = computed(() => {
  const statusOrder: Record<string, number> = { miss: 0, partial: 1, hit: 2 }
  return dedupedAssessmentPointResults.value
    .filter((item: any) => item.status !== 'hit')
    .sort((a: any, b: any) => (statusOrder[a.status] ?? 0) - (statusOrder[b.status] ?? 0))
    .slice(0, 6)
})
const canResumeTraining = computed(() => sessionDetail.value?.status === 'active' && Number(sessionDetail.value?.id) > 0)

const reportHeader = computed(() => {
  const meta = report.value?.evaluation_meta?.report_header || {}
  const total = Number(report.value?.total_score ?? meta.total_score ?? 0)
  return {
    gradeLevel: report.value?.grade_level || meta.grade_level || getLevel(total),
    gradeClass: getGradeClass(total),
  }
})

const reportMeta = computed(() => {
  const meta = report.value?.evaluation_meta?.report_header || {}
  const caseTitle = meta.case_title || sessionDetail.value?.case_title
  const sceneName = meta.scene_name || sessionDetail.value?.scene_name
  const createdAt = sessionDetail.value?.created_at || meta.created_at
  const finishedAt = meta.finished_at || report.value?.evaluated_at || sessionDetail.value?.updated_at || createdAt
  const hitCount = assessmentStats.value.hit
  const partialCount = assessmentStats.value.partial
  const totalCount = assessmentStats.value.total
  const score = Number(report.value?.total_score || 0)
  return {
    caseTitle: caseTitle || '未知案件',
    sceneName: sceneName || '训练场景',
    duration: formatDuration(meta.duration_seconds || sessionDetail.value?.duration_seconds),
    finishedAt: formatDateTime(finishedAt),
    reportNo: `PES-${formatReportNo(finishedAt)}-${String(sessionDetail.value?.id || getSessionId() || 0).padStart(4, '0')}`,
    passLabel: score >= 60 ? '满足' : '未满足',
    assessmentRate: totalCount ? `${Math.round(((hitCount + partialCount * 0.5) / totalCount) * 100)}%` : '暂无数据',
    stageProgress: totalCount ? `${hitCount + partialCount}/${totalCount}` : '暂无数据',
  }
})

const weakestScoreItems = computed(() =>
  [...scoreItems.value]
    .sort((a: any, b: any) => Number(a.score || 0) / Math.max(Number(a.full_score || 1), 1) - Number(b.score || 0) / Math.max(Number(b.full_score || 1), 1))
    .slice(0, 3),
)

const scoreSummary = computed(() => {
  const score = Number(report.value?.total_score || 0)
  if (score >= 90) return '训练表现稳定，流程完整，能够较好完成关键事实查明和现场处置要求。'
  if (score >= 75) return '训练基本达标，但在细节追问、证据固定或法律依据表达方面仍需继续巩固。'
  if (score >= 60) return '训练达到基础要求，但关键环节存在遗漏，需要强化规范语言和闭环处置。'
  return '训练未达到预期标准，需重点补强事实核查、证据意识、程序规范和风险控制能力。'
})

const overallComment = computed(() => {
  const strengths = Array.isArray(report.value?.strengths) ? report.value.strengths : []
  const improvements = finalImprovementItems.value
  if (strengths.length || improvements.length) {
    return `学员在本次训练中${strengths.length ? `表现出${strengths.join('、')}等优点` : '能够完成部分基础处置动作'}，但在${improvements.slice(0, 3).join('、')}等方面仍需加强。建议后续围绕接警核实、现场稳控、证据固定和依法告知开展针对性训练。`
  }
  return scoreSummary.value
})

const finalImprovementItems = computed(() => {
  if (improvementItems.value.length) return improvementItems.value
  return weakestScoreItems.value.map((item: any) => `加强${item.dimension}训练，提升该环节处置质量。`)
})

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

const fetchEvaluation = async () => {
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
      showToast('当前训练尚未生成评估报告')
      if (res.status === 'active') {
        setEmptyState('尚未完成评估', '训练进行中，完成后再查看报告。')
      } else {
        setEmptyState('报告暂未生成', '可在训练历史中重新评估。')
      }
      return
    }
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
  await fetchEvaluation()
  if (route.query.refresh === '1') {
    await refreshEvaluation()
    const nextQuery = { ...route.query }
    delete nextQuery.refresh
    router.replace({ query: nextQuery })
  }
})
</script>

<style scoped>
.evaluation-page {
  min-height: calc(100vh - 52px);
  padding: 18px 24px 36px;
  background: #f3f6fb;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'PingFang SC', 'Microsoft YaHei', sans-serif;
  font-size: 14px;
  line-height: 1.6;
  color: #111827;
}

.loading-state,
.empty-state {
  min-height: calc(100vh - 120px);
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  text-align: center;
  gap: 8px;
}

.empty-state span {
  font-size: 14px;
  color: #666;
}

.evaluation-shell {
  max-width: 1360px;
  margin: 0 auto;
}

.page-heading {
  display: flex;
  justify-content: space-between;
  gap: 22px;
  align-items: flex-start;
  margin-bottom: 16px;
}

.page-heading h1 {
  margin: 0 0 12px;
  font-size: 24px;
  color: #111827;
  font-weight: 900;
}

.meta-strip {
  display: grid;
  grid-template-columns: repeat(5, minmax(120px, auto));
  gap: 18px 36px;
}

.meta-item {
  display: grid;
  gap: 2px;
}

.meta-item span {
  color: #64748b;
  font-size: 12px;
}

.meta-item strong {
  color: #111827;
  font-size: 14px;
}

.page-actions {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
  justify-content: flex-end;
}

.report-layout {
  display: grid;
  grid-template-columns: 340px minmax(0, 1fr);
  gap: 20px;
  align-items: start;
}

.summary-panel {
  display: grid;
  gap: 14px;
}

.summary-card {
  padding: 22px 24px;
  background: #fff;
  border: 1px solid #e6edf5;
  border-radius: 8px;
  box-shadow: 0 10px 28px rgba(15, 23, 42, 0.05);
}

.summary-card h2 {
  margin: 0 0 16px;
  color: #111827;
  font-size: 16px;
  font-weight: 900;
}

.score-line {
  display: flex;
  align-items: baseline;
  gap: 6px;
  margin: 8px 0 12px;
}

.score-line strong {
  color: #f04423;
  font-size: 56px;
  line-height: 1;
  font-weight: 900;
  font-variant-numeric: tabular-nums;
}

.score-line span {
  color: #94a3b8;
  font-size: 20px;
  font-weight: 700;
}

.grade-badge {
  display: inline-flex;
  min-width: 68px;
  justify-content: center;
  border-radius: 999px;
  padding: 5px 12px;
  font-size: 13px;
  font-weight: 800;
  background: #fee2e2;
  color: #dc2626;
}

.grade-pass {
  background: #dcfce7;
  color: #047857;
}

.grade-ok {
  background: #fef3c7;
  color: #b45309;
}

.score-card p {
  margin: 14px 0 0;
  color: #64748b;
  font-size: 13px;
}

.weakness-row,
.closure-row {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  align-items: center;
  padding: 10px 0;
  border-bottom: 1px solid #eef2f7;
}

.weakness-row:last-child,
.closure-row:last-of-type {
  border-bottom: none;
}

.weakness-row span,
.closure-row span {
  color: #334155;
  font-weight: 700;
}

.weakness-row strong,
.closure-row strong {
  color: #ef4444;
  font-variant-numeric: tabular-nums;
}

.summary-card .van-button {
  margin-top: 16px;
}

.formal-report {
  min-height: 720px;
  padding: 34px 44px 42px;
  background: #fff;
  border: 1px solid #e6edf5;
  border-radius: 8px;
  box-shadow: 0 10px 28px rgba(15, 23, 42, 0.05);
}

.document-header {
  display: flex;
  justify-content: center;
  position: relative;
  padding-bottom: 22px;
  border-bottom: 2px solid #cbd5e1;
}

.document-header h2 {
  margin: 0;
  color: #111827;
  font-size: 26px;
  font-weight: 900;
  letter-spacing: 0;
}

.document-header span {
  position: absolute;
  right: 0;
  bottom: 12px;
  color: #64748b;
  font-size: 13px;
}

.report-section {
  padding: 18px 0;
  border-bottom: 1px solid #cbd5e1;
}

.report-section:last-child {
  border-bottom: none;
}

.report-section h3 {
  margin: 0 0 12px;
  color: #111827;
  font-size: 17px;
  font-weight: 900;
}

.report-table {
  width: 100%;
  border-collapse: collapse;
  table-layout: fixed;
  font-size: 14px;
}

.report-table td {
  padding: 8px 10px;
  border-bottom: 1px solid #eef2f7;
  text-align: left;
  vertical-align: middle;
}

.report-table tbody tr:last-child td {
  border-bottom: none;
}

.col-index {
  width: 34px;
  color: #111827;
}

.col-score {
  width: 118px;
  text-align: right;
  color: #111827;
  font-weight: 800;
  font-variant-numeric: tabular-nums;
  white-space: nowrap;
}

.report-text {
  margin: 0;
  color: #111827;
  font-size: 14px;
  line-height: 1.9;
  text-indent: 2em;
}

.overview-table {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px 60px;
  padding: 0 18px;
}

.overview-table div {
  display: flex;
  gap: 8px;
  min-width: 0;
}

.overview-table span {
  color: #334155;
  white-space: nowrap;
}

.overview-table strong {
  color: #111827;
  font-weight: 700;
}

.report-list {
  margin: 0;
  padding-left: 22px;
  color: #111827;
  line-height: 1.9;
}

.assessment-summary {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 10px;
  margin-bottom: 12px;
}

.assessment-summary div {
  display: grid;
  gap: 4px;
  padding: 10px 12px;
  border: 1px solid #e5e7eb;
  border-radius: 6px;
  background: #fafafa;
}

.assessment-summary span {
  color: #64748b;
  font-size: 12px;
}

.assessment-summary strong {
  color: #111827;
  font-size: 18px;
  font-variant-numeric: tabular-nums;
}

.assessment-note {
  margin-bottom: 10px;
  color: #334155;
}

.compact-table td {
  padding-top: 7px;
  padding-bottom: 7px;
}

.all-clear-text {
  margin: 0;
  color: #047857;
  font-weight: 700;
}

.detail-collapse {
  margin-top: 12px;
  border-top: 1px dashed #cbd5e1;
  padding-top: 10px;
}

.detail-collapse summary {
  width: fit-content;
  color: #334155;
  cursor: pointer;
  font-weight: 700;
}

.detail-collapse .report-table {
  margin-top: 10px;
}

.empty-actions {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  justify-content: center;
}

@media (max-width: 1100px) {
  .page-heading,
  .report-layout {
    grid-template-columns: 1fr;
    display: grid;
  }

  .page-actions {
    justify-content: flex-start;
  }

  .meta-strip {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 640px) {
  .evaluation-page {
    padding: 16px 12px 28px;
  }

  .formal-report {
    padding: 24px 18px;
  }

  .document-header {
    justify-content: flex-start;
  }

  .document-header span {
    position: static;
    display: block;
    margin-top: 8px;
  }

  .overview-table,
  .meta-strip,
  .assessment-summary {
    grid-template-columns: 1fr;
  }
}

@media print {
  .evaluation-page {
    padding: 0;
    background: #fff;
  }

  .page-heading,
  .summary-panel {
    display: none;
  }

  .report-layout {
    display: block;
  }

  .formal-report {
    border: none;
    box-shadow: none;
    border-radius: 0;
    max-width: none;
  }
}
</style>
