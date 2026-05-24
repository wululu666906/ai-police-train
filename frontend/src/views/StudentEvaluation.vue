<template>
  <div class="evaluation-page">
    <div v-if="loading" class="loading-state">
      <van-loading color="#165DFF" vertical>正在加载评估报告...</van-loading>
    </div>

    <div v-else-if="report" class="report-layout">
      <section class="hero-card">
        <div class="hero-icon">
          <van-icon name="medal-o" size="100" />
        </div>
        <div class="hero-top">
          <div>
            <p class="hero-label">综合评分</p>
            <h1>{{ report.total_score ?? 0 }}</h1>
          </div>
          <div class="hero-actions">
            <van-tag :color="getLevelColor(report.total_score ?? 0)" size="large" round>
              {{ getLevel(report.total_score ?? 0) }}
            </van-tag>
            <van-button plain size="small" :loading="refreshing" @click="refreshEvaluation">重新评估</van-button>
          </div>
        </div>
      </section>

      <section class="card">
        <div class="section-title">
          <span class="bar"></span>
          <h3>维度评分</h3>
        </div>
        <div class="score-grid">
          <div v-for="item in scoreItems" :key="item.dimension" class="score-card">
            <div class="score-head">
              <span>{{ item.dimension }}</span>
              <strong :class="getScoreClass(item.score, item.full_score)">
                {{ item.score }}<em>/{{ item.full_score }}</em>
              </strong>
            </div>
            <div class="score-track">
              <div class="score-fill" :class="getBarClass(item.score, item.full_score)" :style="{ width: `${getScorePercent(item.score, item.full_score)}%` }"></div>
            </div>
            <p>{{ item.reason || '本项暂无详细说明。' }}</p>
          </div>
        </div>
      </section>

      <section v-if="assessmentPointResults.length" class="card">
        <div class="section-title">
          <span class="bar"></span>
          <h3>关键考察点回顾</h3>
        </div>
        <div class="evidence-list">
          <article v-for="item in assessmentPointResults" :key="`${item.stage_name}-${item.id}`" class="evidence-card">
            <div class="evidence-head">
              <div>
                <span class="stage-name">{{ item.stage_name || '当前阶段' }}</span>
                <h4>{{ item.label }}</h4>
              </div>
              <span class="status-pill" :class="`status-${item.status}`">{{ statusLabel(item.status) }}</span>
            </div>
            <div class="evidence-meta">
              <span>得分 {{ item.score || 0 }}</span>
              <span>权重 {{ item.weight || 0 }}</span>
            </div>
            <p class="feedback">{{ item.feedback || '暂无反馈。' }}</p>
            <div v-if="item.evidence?.length" class="evidence-tags">
              <span v-for="e in item.evidence" :key="e" class="evidence-tag">{{ e }}</span>
            </div>
            <div v-if="item.knowledge_titles?.length" class="knowledge-line">
              关联知识：{{ item.knowledge_titles.join('、') }}
            </div>
          </article>
        </div>
      </section>

      <section v-if="actionResults.length" class="card">
        <div class="section-title">
          <span class="bar"></span>
          <h3>动作与收尾回顾</h3>
        </div>
        <div class="evidence-list">
          <article v-for="item in actionResults" :key="`${item.stage_name}-${item.id}`" class="evidence-card">
            <div class="evidence-head">
              <div>
                <span class="stage-name">{{ item.stage_name || '当前阶段' }}</span>
                <h4>{{ item.label }}</h4>
              </div>
              <span class="status-pill" :class="`status-${item.status}`">{{ statusLabel(item.status) }}</span>
            </div>
            <p class="feedback">{{ item.feedback || '暂无动作反馈。' }}</p>
            <div v-if="item.evidence?.length" class="evidence-tags">
              <span v-for="e in item.evidence" :key="e" class="evidence-tag">{{ e }}</span>
            </div>
          </article>
        </div>
      </section>

      <section v-if="closureSummary && Object.keys(closureSummary).length" class="card">
        <div class="section-title">
          <span class="bar"></span>
          <h3>训练收尾</h3>
        </div>
        <div class="closure-grid">
          <div class="closure-item">
            <span>收尾准备</span>
            <strong>{{ closureSummary.ready ? '已满足' : '未满足' }}</strong>
          </div>
          <div class="closure-item">
            <span>收尾动作命中</span>
            <strong>{{ closureSummary.closure_hit ? '已触发' : '未触发' }}</strong>
          </div>
          <div class="closure-item">
            <span>阶段</span>
            <strong>{{ closureSummary.current_stage || '未知' }}</strong>
          </div>
        </div>
        <div v-if="closureSummary.missing_point_ids?.length" class="closure-line">
          缺失考察点：{{ closureSummary.missing_point_ids.join('、') }}
        </div>
        <div v-if="closureSummary.missing_action_ids?.length" class="closure-line">
          缺失动作：{{ closureSummary.missing_action_ids.join('、') }}
        </div>
        <div v-if="closureSummary.closing_script" class="closure-script">
          {{ closureSummary.closing_script }}
        </div>
      </section>

      <section v-if="stageGapSummary" class="card">
        <div class="section-title">
          <span class="bar"></span>
          <h3>阶段完整性概览</h3>
        </div>
        <div class="pill-block">
          <div class="pill-title">重点项</div>
          <div class="pill-list">
            <span v-for="item in stageGapSummary.requirements || []" :key="item" class="pill">{{ item }}</span>
          </div>
        </div>
        <div v-if="stageGapSummary.satisfied?.length" class="pill-block">
          <div class="pill-title success">已覆盖</div>
          <div class="pill-list">
            <span v-for="item in stageGapSummary.satisfied" :key="item" class="pill success">{{ item }}</span>
          </div>
        </div>
        <div v-if="stageGapSummary.missing?.length" class="pill-block">
          <div class="pill-title warn">待加强</div>
          <div class="pill-list">
            <span v-for="item in stageGapSummary.missing" :key="item" class="pill warn">{{ item }}</span>
          </div>
        </div>
      </section>

      <div class="split-grid">
        <section class="card">
          <div class="section-title">
            <span class="bar"></span>
            <h3>表现亮点</h3>
          </div>
          <ul v-if="strengthItems.length" class="feedback-list">
            <li v-for="item in strengthItems" :key="item">{{ item }}</li>
          </ul>
          <div v-else class="inline-empty">本次训练暂未识别出明显亮点。</div>
        </section>

        <section class="card">
          <div class="section-title">
            <span class="bar"></span>
            <h3>改进建议</h3>
          </div>
          <ul v-if="improvementItems.length" class="feedback-list">
            <li v-for="item in improvementItems" :key="item">{{ item }}</li>
          </ul>
          <div v-else class="inline-empty">当前暂无额外改进建议。</div>
        </section>
      </div>

      <section v-if="report.suggestions" class="card highlight-card">
        <div class="section-title">
          <span class="bar"></span>
          <h3>综合点评</h3>
        </div>
        <p class="highlight-text">{{ report.suggestions }}</p>
      </section>

      <div class="action-bar">
        <van-button size="large" class="ghost-btn" @click="router.push('/student/hall')">返回训练大厅</van-button>
        <van-button type="primary" size="large" class="primary-btn" @click="router.push('/student/history')">查看训练历史</van-button>
      </div>
    </div>

    <div v-else class="empty-state">
      <van-icon name="info-o" size="48" color="#C9CDD4" />
      <p>{{ emptyState.title }}</p>
      <span>{{ emptyState.description }}</span>
      <div class="empty-actions">
        <van-button v-if="canResumeTraining" plain size="small" @click="resumeTraining">继续当前训练</van-button>
        <van-button plain size="small" @click="router.push('/student/history')">查看训练历史</van-button>
        <van-button type="primary" size="small" @click="router.push('/student/hall')">返回训练大厅</van-button>
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
const strengthItems = computed(() => (Array.isArray(report.value?.strengths) ? report.value.strengths : []))
const improvementItems = computed(() => (Array.isArray(report.value?.improvements) ? report.value.improvements : []))
const stageGapSummary = computed(() => report.value?.evaluation_meta?.stage_gap_summary || null)
const assessmentPointResults = computed(() => (Array.isArray(report.value?.assessment_point_results) ? report.value.assessment_point_results : []))
const actionResults = computed(() => (Array.isArray(report.value?.action_results) ? report.value.action_results : []))
const closureSummary = computed(() => report.value?.closure_summary || null)
const canResumeTraining = computed(() => sessionDetail.value?.status === 'active' && Number(sessionDetail.value?.id) > 0)

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

const fetchEvaluation = async () => {
  const sessionId = getSessionId()
  if (!sessionId) {
    showToast('缺少训练会话编号，无法加载评估报告')
    setEmptyState('无法定位评估报告', '当前页面缺少训练会话编号。你可以返回训练历史重新打开报告，或回到训练大厅重新开始。')
    loading.value = false
    return
  }

  try {
    const res: any = await request.get(`/training/session/${sessionId}`, { _skipErrorToast: true } as any)
    sessionDetail.value = res || null
    if (!res.evaluation_result) {
      showToast('当前训练尚未生成评估报告')
      if (res.status === 'active') {
        setEmptyState('当前训练尚未完成评估', '这条会话还在进行中，暂时没有评估报告。你可以回到训练现场继续完成，再回来查看报告。')
      } else {
        setEmptyState('评估报告暂未写入', '当前会话已经结束，但评估结果还没有成功写入。你可以前往训练历史重新评估，或稍后再试。')
      }
      return
    }
    report.value = safeParse(res.evaluation_result, null)
    if (!report.value) {
      showToast('评估报告解析失败')
      setEmptyState('评估报告解析失败', '当前报告内容格式异常，暂时无法正常展示。你可以在训练历史里尝试重新评估。')
    }
  } catch {
    showToast('获取评估报告失败')
    setEmptyState('获取评估报告失败', '当前无法从服务端加载这条报告。你可以返回训练历史重试，或稍后再进入。')
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
    report.value = res || report.value
    showToast({ type: 'success', message: '评估报告已更新' })
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
  if (score >= 60) return '合格'
  return '需改进'
}

const getLevelColor = (score: number) => {
  if (score >= 85) return '#00B42A'
  if (score >= 60) return '#FF7D00'
  return '#F53F3F'
}

const getScorePercent = (score: number, full: number) => {
  if (!full) return 0
  return Math.max(0, Math.min(100, (score / full) * 100))
}

const getScoreClass = (score: number, full: number) => {
  const ratio = full ? score / full : 0
  if (ratio >= 0.85) return 'green'
  if (ratio >= 0.6) return 'orange'
  return 'red'
}

const getBarClass = (score: number, full: number) => {
  const ratio = full ? score / full : 0
  if (ratio >= 0.85) return 'bar-green'
  if (ratio >= 0.6) return 'bar-orange'
  return 'bar-red'
}

onMounted(fetchEvaluation)
</script>

<style scoped>
.evaluation-page {
  min-height: calc(100vh - 56px);
  padding: 22px;
  background:
    radial-gradient(circle at top right, rgba(22, 93, 255, 0.08), transparent 32%),
    linear-gradient(180deg, #f8fafc 0%, #eef2f7 100%);
}

.loading-state,
.empty-state {
  min-height: calc(100vh - 120px);
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  text-align: center;
}

.report-layout {
  display: flex;
  flex-direction: column;
  gap: 18px;
}

.hero-card,
.card {
  position: relative;
  border-radius: 28px;
  background: rgba(255, 255, 255, 0.95);
  border: 1px solid rgba(15, 23, 42, 0.06);
  box-shadow: 0 24px 50px rgba(15, 23, 42, 0.06);
}

.hero-card {
  padding: 26px;
  overflow: hidden;
}

.hero-icon {
  position: absolute;
  right: 18px;
  top: 14px;
  color: rgba(22, 93, 255, 0.08);
}

.hero-top {
  position: relative;
  z-index: 1;
  display: flex;
  justify-content: space-between;
  gap: 18px;
}

.hero-label {
  margin: 0;
  font-size: 14px;
  color: #64748b;
}

.hero-card h1 {
  margin: 8px 0 0;
  font-size: 62px;
  line-height: 1;
  color: #0f172a;
}

.hero-actions {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 12px;
}

.card {
  padding: 22px;
}

.section-title {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 16px;
}

.section-title .bar {
  width: 6px;
  height: 22px;
  border-radius: 999px;
  background: linear-gradient(180deg, #165dff 0%, #7aa2ff 100%);
}

.section-title h3 {
  margin: 0;
  font-size: 18px;
  color: #0f172a;
}

.score-grid,
.split-grid,
.closure-grid {
  display: grid;
  gap: 14px;
}

.score-grid {
  grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
}

.split-grid {
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.closure-grid {
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
}

.score-card {
  padding: 18px;
  border-radius: 20px;
  background: #f8fafc;
}

.score-head {
  display: flex;
  justify-content: space-between;
  gap: 10px;
  margin-bottom: 10px;
  color: #0f172a;
  font-weight: 700;
}

.score-head strong {
  font-size: 22px;
}

.score-head em {
  font-style: normal;
  font-size: 13px;
}

.green {
  color: #00b42a;
}

.orange {
  color: #ff7d00;
}

.red {
  color: #f53f3f;
}

.score-track {
  height: 9px;
  border-radius: 999px;
  background: #e5e7eb;
  overflow: hidden;
}

.score-fill {
  height: 100%;
  border-radius: inherit;
}

.bar-green {
  background: linear-gradient(90deg, #23c16b 0%, #00b42a 100%);
}

.bar-orange {
  background: linear-gradient(90deg, #ffb547 0%, #ff7d00 100%);
}

.bar-red {
  background: linear-gradient(90deg, #ff8f8f 0%, #f53f3f 100%);
}

.score-card p,
.highlight-text,
.feedback,
.closure-line,
.knowledge-line {
  margin: 12px 0 0;
  line-height: 1.7;
  color: #475569;
}

.evidence-list {
  display: grid;
  gap: 12px;
}

.evidence-card {
  padding: 18px;
  border-radius: 20px;
  background: #f8fafc;
}

.evidence-head {
  display: flex;
  justify-content: space-between;
  gap: 16px;
}

.evidence-head h4 {
  margin: 6px 0 0;
  color: #0f172a;
}

.stage-name {
  display: inline-block;
  padding: 4px 10px;
  border-radius: 999px;
  background: rgba(22, 93, 255, 0.08);
  color: #165dff;
  font-size: 12px;
  font-weight: 700;
}

.status-pill {
  align-self: flex-start;
  padding: 6px 10px;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 700;
}

.status-hit {
  background: rgba(0, 180, 42, 0.12);
  color: #00b42a;
}

.status-partial {
  background: rgba(255, 125, 0, 0.12);
  color: #d97706;
}

.status-missed {
  background: rgba(245, 63, 63, 0.12);
  color: #f53f3f;
}

.evidence-meta {
  display: flex;
  gap: 14px;
  margin-top: 10px;
  font-size: 12px;
  color: #64748b;
}

.evidence-tags,
.pill-list {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 12px;
}

.evidence-tag,
.pill {
  padding: 7px 10px;
  border-radius: 999px;
  font-size: 12px;
}

.evidence-tag {
  background: #fff;
  color: #334155;
}

.closure-item {
  padding: 14px;
  border-radius: 18px;
  background: #f8fafc;
}

.closure-item span {
  display: block;
  font-size: 12px;
  color: #64748b;
}

.closure-item strong {
  display: block;
  margin-top: 6px;
  color: #0f172a;
}

.closure-script {
  margin-top: 14px;
  padding: 14px;
  border-radius: 16px;
  background: rgba(22, 93, 255, 0.08);
  color: #165dff;
  line-height: 1.7;
}

.pill-block + .pill-block {
  margin-top: 14px;
}

.pill-title {
  margin-bottom: 8px;
  font-size: 12px;
  font-weight: 700;
  color: #334155;
}

.pill-title.success {
  color: #00b42a;
}

.pill-title.warn {
  color: #d97706;
}

.pill {
  background: #eef2ff;
  color: #334155;
}

.pill.success {
  background: #ecfdf3;
  color: #00b42a;
}

.pill.warn {
  background: #fff7ed;
  color: #d97706;
}

.feedback-list {
  margin: 0;
  padding-left: 18px;
  color: #334155;
  line-height: 1.9;
}

.inline-empty {
  color: #94a3b8;
}

.highlight-card {
  background: linear-gradient(135deg, rgba(22, 93, 255, 0.04) 0%, rgba(122, 162, 255, 0.08) 100%);
}

.action-bar,
.empty-actions {
  display: flex;
  gap: 12px;
  justify-content: center;
}

.ghost-btn,
.primary-btn {
  min-width: 180px;
}

@media (max-width: 900px) {
  .split-grid {
    grid-template-columns: 1fr;
  }

  .hero-top,
  .action-bar,
  .empty-actions {
    flex-direction: column;
    align-items: stretch;
  }
}
</style>
