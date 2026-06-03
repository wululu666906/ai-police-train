<template>
  <div class="evaluation-page">
    <div v-if="loading" class="loading-state">
      <van-loading color="#165DFF" vertical>正在加载评估报告...</van-loading>
    </div>

    <article v-else-if="report" class="formal-report">
      <header class="report-header">
        <div class="header-main">
          <h1>训练评估报告</h1>
          <p v-if="reportSubtitle" class="report-subtitle">{{ reportSubtitle }}</p>
        </div>
        <div class="header-score">
          <div class="total-score">
            <span class="total-value">{{ report.total_score ?? 0 }}</span>
            <span class="total-suffix">/ 100</span>
          </div>
          <span class="grade-text">{{ reportHeader.gradeLevel }}</span>
        </div>
        <van-button plain size="small" :loading="refreshing" @click="refreshEvaluation">重新评估</van-button>
      </header>

      <section class="report-section">
        <h2>维度得分</h2>
        <table class="report-table">
          <thead>
            <tr>
              <th>维度</th>
              <th class="col-num">得分</th>
              <th class="col-num">满分</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="item in scoreItems" :key="item.dimension">
              <td>{{ item.dimension }}</td>
              <td class="col-num">{{ item.score }}</td>
              <td class="col-num">{{ item.full_score }}</td>
            </tr>
          </tbody>
        </table>
      </section>

      <section v-if="assessmentPointResults.length" class="report-section">
        <h2>考察点得分</h2>
        <table class="report-table">
          <thead>
            <tr>
              <th>考察点</th>
              <th class="col-num">得分</th>
              <th class="col-status">状态</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="item in assessmentPointResults" :key="`${item.stage_name}-${item.id}`">
              <td>{{ item.label }}</td>
              <td class="col-num">{{ item.score ?? 0 }}</td>
              <td class="col-status">{{ statusLabel(item.status) }}</td>
            </tr>
          </tbody>
        </table>
      </section>

      <section v-if="report.suggestions" class="report-section">
        <h2>综合点评</h2>
        <p class="report-text">{{ report.suggestions }}</p>
      </section>

      <section v-if="improvementItems.length" class="report-section">
        <h2>改进建议</h2>
        <ul class="report-list">
          <li v-for="item in improvementItems" :key="item">{{ item }}</li>
        </ul>
      </section>

      <footer class="report-footer">
        <van-button size="large" plain @click="router.push('/student/hall')">返回训练大厅</van-button>
        <van-button type="primary" size="large" @click="router.push('/student/history')">训练历史</van-button>
      </footer>
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
const canResumeTraining = computed(() => sessionDetail.value?.status === 'active' && Number(sessionDetail.value?.id) > 0)

const reportHeader = computed(() => {
  const meta = report.value?.evaluation_meta?.report_header || {}
  const total = Number(report.value?.total_score ?? meta.total_score ?? 0)
  return {
    gradeLevel: report.value?.grade_level || meta.grade_level || getLevel(total),
  }
})

const reportSubtitle = computed(() => {
  const meta = report.value?.evaluation_meta?.report_header || {}
  const caseTitle = meta.case_title || sessionDetail.value?.case_title
  const sceneName = meta.scene_name || sessionDetail.value?.scene_name
  const parts = [caseTitle, sceneName].filter(Boolean)
  return parts.length ? parts.join(' · ') : ''
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
  min-height: calc(100vh - 56px);
  padding: 20px 16px 32px;
  background: #f5f5f5;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'PingFang SC', 'Microsoft YaHei', sans-serif;
  font-size: 15px;
  line-height: 1.6;
  color: #1a1a1a;
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

.formal-report {
  max-width: 720px;
  margin: 0 auto;
  background: #fff;
  border: 1px solid #ddd;
}

.report-header {
  display: grid;
  grid-template-columns: 1fr auto auto;
  align-items: center;
  gap: 16px 20px;
  padding: 24px 28px;
  border-bottom: 1px solid #ddd;
}

.header-main {
  min-width: 0;
}

.report-header h1 {
  margin: 0;
  font-size: 20px;
  font-weight: 600;
  line-height: 1.3;
}

.report-subtitle {
  margin: 6px 0 0;
  font-size: 14px;
  color: #666;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.header-score {
  text-align: right;
}

.total-score {
  display: flex;
  align-items: baseline;
  justify-content: flex-end;
  gap: 4px;
}

.total-value {
  font-size: 32px;
  font-weight: 600;
  font-variant-numeric: tabular-nums;
  line-height: 1;
}

.total-suffix {
  font-size: 14px;
  color: #666;
}

.grade-text {
  display: block;
  margin-top: 4px;
  font-size: 14px;
  text-align: right;
}

.report-section {
  padding: 20px 28px;
  border-bottom: 1px solid #eee;
}

.report-section:last-of-type {
  border-bottom: none;
}

.report-section h2 {
  margin: 0 0 12px;
  font-size: 15px;
  font-weight: 600;
  line-height: 1.4;
}

.report-table {
  width: 100%;
  border-collapse: collapse;
  table-layout: fixed;
  font-size: 14px;
}

.report-table th,
.report-table td {
  padding: 10px 0;
  border-bottom: 1px solid #eee;
  text-align: left;
  vertical-align: middle;
}

.report-table th {
  font-weight: 600;
  border-bottom: 1px solid #ddd;
}

.report-table tbody tr:last-child td {
  border-bottom: none;
}

.col-num {
  width: 72px;
  text-align: right;
  font-variant-numeric: tabular-nums;
}

.col-status {
  width: 88px;
  text-align: right;
}

.report-text {
  margin: 0;
  font-size: 15px;
  line-height: 1.7;
}

.report-list {
  margin: 0;
  padding-left: 1.25em;
}

.report-list li + li {
  margin-top: 8px;
}

.report-footer {
  padding: 20px 28px 24px;
  display: flex;
  gap: 12px;
  justify-content: center;
}

.empty-actions {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  justify-content: center;
}

@media (max-width: 640px) {
  .report-header {
    grid-template-columns: 1fr;
    grid-template-rows: auto auto auto;
  }

  .header-score {
    display: flex;
    align-items: baseline;
    justify-content: space-between;
    text-align: left;
  }

  .total-score {
    justify-content: flex-start;
  }

  .grade-text {
    margin-top: 0;
    text-align: left;
  }

  .report-header .van-button {
    justify-self: start;
  }
}

@media print {
  .evaluation-page {
    padding: 0;
    background: #fff;
  }

  .formal-report {
    border: none;
    max-width: none;
  }

  .report-footer {
    display: none;
  }
}
</style>
