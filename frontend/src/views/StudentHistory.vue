<template>
  <div class="student-page history-page">
    <template v-if="!loading">
      <el-row :gutter="16" class="summary-row">
        <el-col :xs="12" :sm="6">
          <StudentStatCard
            :label="showEmptySessions ? '当前筛选结果' : '当前可见记录'"
            :value="total"
            tone="primary"
          />
        </el-col>
        <el-col :xs="12" :sm="6">
          <StudentStatCard label="进行中训练" :value="activeCount" tone="primary" />
        </el-col>
        <el-col :xs="12" :sm="6">
          <StudentStatCard label="已完成训练" :value="finishedCount" tone="success" />
        </el-col>
        <el-col v-if="hiddenEmptyCount > 0 && !showEmptySessions" :xs="12" :sm="6">
          <StudentStatCard label="已隐藏空会话" :value="hiddenEmptyCount" tone="warning" />
        </el-col>
      </el-row>

      <section class="card card--compact toolbar-card">
        <div class="toolbar-card__main">
          <SelectFilter
            :data="statusFilterData"
            :default-values="statusFilterValues"
            @change="onStatusFilterChange"
          />
          <p v-if="showEmptySessions" class="summary-tip">空会话指尚未产生有效对话内容的训练记录。</p>
        </div>
        <div class="summary-tools">
          <span class="tool-label">显示空会话</span>
          <el-switch v-model="showEmptySessions" @change="handleToggleEmpty" />
        </div>
      </section>
    </template>

    <div v-if="loading" class="card loading-state">
      <el-skeleton :rows="8" animated />
    </div>

    <div v-else-if="loadError" class="card error-state">
      <el-empty :description="loadError">
        <div class="error-actions">
          <el-button @click="fetchHistory">重新加载</el-button>
          <el-button type="primary" @click="router.push('/student/hall')">前往训练大厅</el-button>
        </div>
      </el-empty>
    </div>

    <div v-else-if="records.length === 0" class="card empty-state">
      <el-empty :description="emptyTitle">
        <template #description>
          <p>{{ emptyTitle }}</p>
          <span v-if="hiddenEmptyCount > 0">当前有 {{ hiddenEmptyCount }} 条空会话被自动隐藏。</span>
          <span v-else>{{ emptyDescription }}</span>
        </template>
        <el-button type="primary" @click="router.push('/student/hall')">前往训练大厅</el-button>
      </el-empty>
    </div>

    <div v-else class="history-list-wrapper">
      <div class="history-list">
        <article
          v-for="record in records"
          :key="record.id"
          class="card history-card"
          :class="record.status === 'finished' ? 'history-card--finished' : 'history-card--active'"
        >
          <!-- 头部：核心识别信息 -->
          <header class="card-header">
            <div class="card-header-main">
              <div class="card-title-row">
                <span class="status-badge" :class="record.status === 'finished' ? 'status-badge--done' : 'status-badge--live'">
                  {{ record.status === 'finished' ? '已完成' : '进行中' }}
                </span>
                <h3 class="record-title">{{ record.case_title || '未命名案件' }}</h3>
              </div>
              <p class="record-scene">{{ record.scene_name || '未指定场景' }}</p>
              <div class="record-meta">
                <span class="meta-chip">{{ record.case_type || '未分类' }}</span>
                <span class="meta-dot">·</span>
                <span class="meta-text">难度 {{ record.difficulty || '中等' }}</span>
                <span class="meta-dot">·</span>
                <span class="meta-text">{{ formatTime(record.created_at) }}</span>
              </div>
            </div>

            <div v-if="record.status === 'finished'" class="score-highlight">
              <span class="score-label">综合评分</span>
              <strong class="score-value" :class="getScoreClass(record.total_score)">
                {{ record.total_score ?? '--' }}
              </strong>
            </div>
            <div v-else class="progress-highlight">
              <span class="score-label">对话轮次</span>
              <strong class="score-value score-value--primary">{{ record.turn_count ?? 0 }}</strong>
            </div>
          </header>

          <!-- 训练数据：主次分明 -->
          <section class="card-body">
            <div class="stat-group stat-group--primary">
              <div class="stat-block">
                <span class="stat-label">对话轮次</span>
                <strong class="stat-value">{{ record.turn_count ?? 0 }}</strong>
              </div>
              <div class="stat-block">
                <span class="stat-label">已获信息</span>
                <strong class="stat-value stat-value--primary">{{ record.revealed_info_count ?? 0 }}</strong>
              </div>
            </div>

            <div class="stat-divider" aria-hidden="true"></div>

            <div class="stat-group stat-group--secondary">
              <div class="stat-pill">
                <span class="stat-pill-label">情绪</span>
                <strong class="stat-pill-value" :style="{ color: getEmotionColor(record.final_emotion) }">
                  {{ record.final_emotion ?? '--' }}
                </strong>
              </div>
              <div class="stat-pill">
                <span class="stat-pill-label">配合</span>
                <strong class="stat-pill-value stat-pill-value--blue">
                  {{ record.final_cooperation ?? record.final_trust ?? 30 }}
                </strong>
              </div>
              <div class="stat-pill">
                <span class="stat-pill-label">风险</span>
                <strong class="stat-pill-value stat-pill-value--amber">{{ record.final_risk ?? 50 }}</strong>
              </div>
              <div class="stat-pill">
                <span class="stat-pill-label">清晰</span>
                <strong class="stat-pill-value stat-pill-value--green">{{ record.final_clarity ?? 50 }}</strong>
              </div>
            </div>
          </section>

          <!-- 已完成：复盘摘要 -->
          <section v-if="record.status === 'finished'" class="card-review">
            <span class="review-label">阶段复盘</span>
            <div v-if="record.stage_gap_missing?.length" class="review-gaps">
              <span v-for="item in record.stage_gap_missing" :key="item" class="gap-chip">{{ item }}</span>
            </div>
            <span v-else class="review-ok">关键项覆盖较完整</span>
          </section>

          <!-- 操作区 -->
          <footer class="card-footer">
            <el-button
              v-if="record.status === 'finished'"
              size="small"
              type="primary"
              @click="router.push(`/student/evaluation?session_id=${record.id}`)"
            >
              查看报告
            </el-button>
            <el-button
              v-if="record.status === 'finished'"
              size="small"
              plain
              :loading="reEvaluatingId === record.id"
              :disabled="reEvaluatingId !== null"
              @click="reEvaluate(record.id)"
            >
              重新评估
            </el-button>
            <el-button
              v-if="record.status !== 'finished'"
              size="small"
              type="primary"
              @click="continueTraining(record.id)"
            >
              继续训练
            </el-button>
            <el-button
              size="small"
              plain
              type="danger"
              :loading="deletingId === record.id"
              :disabled="deletingId !== null || reEvaluatingId !== null"
              @click="deleteSession(record.id)"
            >
              删除记录
            </el-button>
          </footer>
        </article>
      </div>

      <div v-if="total > pageSize" class="pager card card--compact">
        <el-button size="small" :disabled="page <= 1" @click="changePage(page - 1)">上一页</el-button>
        <span class="pager-text">第 {{ page }} / {{ totalPages }} 页，共 {{ total }} 条</span>
        <el-button size="small" :disabled="page >= totalPages" @click="changePage(page + 1)">下一页</el-button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { showConfirmDialog, showToast } from 'vant'
import SelectFilter from '../geeker-adapt/components/SelectFilter/index.vue'
import StudentStatCard from '../geeker-adapt/components/StudentStatCard.vue'
import request from '../utils/request'

const router = useRouter()
const records = ref<any[]>([])
const loading = ref(true)
const page = ref(1)
const pageSize = 10
const total = ref(0)
const totalPages = ref(1)
const showEmptySessions = ref(false)
const hiddenEmptyCount = ref(0)
const reEvaluatingId = ref<number | null>(null)
const deletingId = ref<number | null>(null)
const loadError = ref('')
const statusFilter = ref<'all' | 'active' | 'finished'>('all')
const activeCount = ref(0)
const finishedCount = ref(0)

const statusOptions = [
  { label: '全部', value: 'all' as const },
  { label: '进行中', value: 'active' as const },
  { label: '已完成', value: 'finished' as const },
]

const statusFilterValues = computed(() => ({ status: statusFilter.value }))

const statusFilterData = computed(() => [
  {
    title: '记录状态',
    key: 'status',
    options: statusOptions.map((item) => ({ label: item.label, value: item.value })),
  },
])

const onStatusFilterChange = async (values: Record<string, unknown>) => {
  const next = values.status as 'all' | 'active' | 'finished'
  await changeStatusFilter(next)
}

const emptyTitle = computed(() => {
  if (statusFilter.value === 'active') return showEmptySessions.value ? '暂无进行中的训练记录' : '暂无有效进行中训练'
  if (statusFilter.value === 'finished') return '暂无已完成训练记录'
  return showEmptySessions.value ? '暂无训练记录' : '暂无有效训练记录'
})

const emptyDescription = computed(() => {
  if (statusFilter.value === 'active') return '开始一场训练后，未结束的会话会显示在这里。'
  if (statusFilter.value === 'finished') return '完成一次训练并生成评估后，记录会显示在这里。'
  return '完成一次训练后，记录会显示在这里。'
})

const fetchHistory = async () => {
  loading.value = true
  loadError.value = ''
  try {
    const res: any = await request.get('/student/history', {
      params: {
        page: page.value,
        page_size: pageSize,
        include_empty: showEmptySessions.value,
        status: statusFilter.value === 'all' ? undefined : statusFilter.value,
      },
      _skipErrorToast: true,
    } as any)
    records.value = res.items || []
    total.value = res.total || 0
    activeCount.value = Number(res.active_count || 0)
    finishedCount.value = Number(res.finished_count || 0)
    hiddenEmptyCount.value = res.hidden_empty_count || 0
    totalPages.value = Math.max(1, Math.ceil(total.value / pageSize))
  } catch (error: any) {
    records.value = []
    total.value = 0
    hiddenEmptyCount.value = 0
    activeCount.value = 0
    finishedCount.value = 0
    totalPages.value = 1
    const isBackendUnavailable = !error?.response
    loadError.value = isBackendUnavailable
      ? '后端服务未启动，请先运行 backend\\start.ps1'
      : error?.response?.data?.detail || '训练历史加载失败'
    showToast(isBackendUnavailable ? '无法连接后端服务' : '获取历史记录失败')
  } finally {
    loading.value = false
  }
}

const reEvaluate = async (sessionId: number) => {
  if (!sessionId || reEvaluatingId.value !== null) return
  reEvaluatingId.value = sessionId
  try {
    await request.post(`/training/re-evaluate/${sessionId}`, null, { _skipErrorToast: true } as any)
    showToast({ type: 'success', message: '评估报告已重新生成' })
    router.push(`/student/evaluation?session_id=${sessionId}&refresh=1`)
  } catch (error: any) {
    const errorMsg = error?.response?.data?.detail || '重新评估失败'
    showToast(errorMsg)
  } finally {
    reEvaluatingId.value = null
  }
}

const continueTraining = (sessionId: number) => {
  router.push(`/student/training/${sessionId}`)
}

const deleteSession = async (sessionId: number) => {
  if (!sessionId || deletingId.value !== null || reEvaluatingId.value !== null) return

  try {
    await showConfirmDialog({
      title: '删除训练记录',
      message: '删除后，这条训练会话、对话内容和评估结果将无法恢复。是否继续？',
      confirmButtonColor: '#dc2626',
    })
  } catch {
    return
  }

  deletingId.value = sessionId
  try {
    await request.delete(`/training/session/${sessionId}`, { _skipErrorToast: true } as any)
    showToast({ type: 'success', message: '训练记录已删除' })

    if (records.value.length === 1 && page.value > 1) {
      page.value -= 1
    }
    await fetchHistory()
  } catch (error: any) {
    const errorMsg = error?.response?.data?.detail || '删除训练记录失败'
    showToast(errorMsg)
  } finally {
    deletingId.value = null
  }
}

const changePage = async (nextPage: number) => {
  if (nextPage === page.value || nextPage < 1 || nextPage > totalPages.value) return
  page.value = nextPage
  await fetchHistory()
}

const changeStatusFilter = async (nextStatus: 'all' | 'active' | 'finished') => {
  if (nextStatus === statusFilter.value) return
  statusFilter.value = nextStatus
  page.value = 1
  await fetchHistory()
}

const handleToggleEmpty = async () => {
  page.value = 1
  await fetchHistory()
}

const getEmotionColor = (value: number) => {
  if (value >= 70) return '#F53F3F'
  if (value >= 40) return '#FF7D00'
  return '#00B42A'
}

const getScoreClass = (score: number | null | undefined) => {
  const value = Number(score)
  if (!Number.isFinite(value)) return ''
  if (value >= 85) return 'score-value--excellent'
  if (value >= 70) return 'score-value--good'
  if (value >= 60) return 'score-value--pass'
  return 'score-value--weak'
}

const formatTime = (iso: string) => {
  if (!iso) return '-'
  const d = new Date(iso)
  return `${d.getMonth() + 1}/${d.getDate()} ${d.getHours().toString().padStart(2, '0')}:${d.getMinutes().toString().padStart(2, '0')}`
}

onMounted(fetchHistory)
</script>

<style scoped>
.history-page {
  padding-top: 16px;
  height: 100%;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.summary-row {
  margin-bottom: 16px;
}

.toolbar-card {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 16px;
  flex-wrap: wrap;
}

.toolbar-card__main {
  flex: 1;
  min-width: 0;
}

.summary-tools {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-left: auto;
  padding-left: 12px;
}

.tool-label {
  font-size: 13px;
  color: #64748b;
  white-space: nowrap;
}

.summary-item {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 150px;
  padding-right: 14px;
  border-right: 1px solid #e2e8f0;
}

.summary-item:last-of-type {
  border-right: none;
}

.summary-tip {
  margin: 8px 0 0;
  font-size: 13px;
  color: #4e5969;
}

.loading-state,
.empty-state,
.error-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 80px 0;
  gap: 8px;
  color: #86909c;
  text-align: center;
}

.empty-state p {
  font-size: 15px;
  color: #4e5969;
  font-weight: 500;
  margin: 16px 0 4px;
}

.go-btn {
  margin-top: 16px;
  background: #165dff !important;
  border: none !important;
  border-radius: 8px !important;
}

.error-actions {
  display: flex;
  flex-wrap: wrap;
  justify-content: center;
  gap: 12px;
  margin-top: 16px;
}

.history-list-wrapper {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.history-list {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  display: grid;
  gap: 10px;
  align-content: start;
  padding-right: 4px;
}

.history-card {
  background: #fff;
  border-radius: 10px;
  border: 1px solid #e5e7eb;
  overflow: hidden;
  height: 240px;
  display: flex;
  flex-direction: column;
  flex-shrink: 0;
}

.history-card--finished {
  border-left: 4px solid #10b981;
}

.history-card--active {
  border-left: 4px solid #165dff;
}

.card-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  padding: 6px 14px 4px;
  border-bottom: 1px solid #f1f5f9;
  flex-shrink: 0;
  height: 60px;
}

.card-header-main {
  min-width: 0;
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 1px;
}

.card-title-row {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: nowrap;
  flex-shrink: 0;
}

.status-badge {
  display: inline-flex;
  align-items: center;
  padding: 2px 8px;
  border-radius: 999px;
  font-size: 11px;
  font-weight: 700;
  white-space: nowrap;
}

.status-badge--done {
  color: #047857;
  background: #ecfdf5;
}

.status-badge--live {
  color: #165dff;
  background: #eff6ff;
}

.record-title {
  margin: 0;
  color: #0f172a;
  font-size: 15px;
  font-weight: 800;
  line-height: 1.3;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.record-scene {
  color: #334155;
  font-size: 12px;
  font-weight: 600;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  flex-shrink: 0;
}

.record-meta {
  display: flex;
  flex-wrap: nowrap;
  align-items: center;
  gap: 10px;
  font-size: 12px;
  color: #111827;
  flex-shrink: 0;
  overflow: hidden;
}

.meta-chip {
  display: inline-flex;
  align-items: center;
  padding: 1px 7px;
  border-radius: 3px;
  background: #f8fafc;
  color: #111827;
  font-size: 12px;
  font-weight: 600;
  flex-shrink: 0;
}

.meta-dot {
  color: #cbd5e1;
  flex-shrink: 0;
}

.meta-text {
  color: #111827;
  font-weight: 600;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  flex-shrink: 1;
}

.score-highlight,
.progress-highlight {
  flex-shrink: 0;
  min-width: 80px;
  text-align: right;
}

.score-label {
  display: block;
  font-size: 11px;
  color: #94a3b8;
  font-weight: 600;
}

.score-value {
  display: block;
  margin-top: 2px;
  font-size: 30px;
  font-weight: 900;
  line-height: 1;
  color: #165dff;
}

.score-value--primary {
  color: #165dff;
}

.score-value--excellent {
  color: #059669;
}

.score-value--good {
  color: #165dff;
}

.score-value--pass {
  color: #d97706;
}

.score-value--weak {
  color: #dc2626;
}

.card-body {
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 6px 14px;
  background: #fafbfc;
  flex: 1;
  min-height: 0;
  overflow: hidden;
}

.stat-group {
  display: flex;
  align-items: center;
  gap: 10px;
}

.stat-group--primary {
  flex-shrink: 0;
}

.stat-group--secondary {
  flex: 1;
  flex-wrap: wrap;
  justify-content: flex-end;
}

.stat-divider {
  width: 1px;
  height: 32px;
  background: #e5e7eb;
  flex-shrink: 0;
}

.stat-block {
  min-width: 0;
  padding: 6px 12px;
  border-radius: 8px;
  background: #fff;
  border: 1px solid #e5e7eb;
  display: flex;
  align-items: center;
  gap: 8px;
}

.stat-label {
  font-size: 12px;
  color: #64748b;
  font-weight: 700;
  letter-spacing: 0.02em;
}

.stat-value {
  font-size: 18px;
  font-weight: 800;
  color: #0f172a;
  line-height: 1;
}

.stat-value--primary {
  color: #165dff;
}

.stat-pill {
  display: flex;
  align-items: center;
  gap: 5px;
  padding: 5px 10px;
  border-radius: 8px;
  background: #fff;
  border: 1px solid #e5e7eb;
}

.stat-pill-label {
  font-size: 12px;
  color: #64748b;
  font-weight: 600;
}

.stat-pill-value {
  font-size: 16px;
  font-weight: 800;
  color: #334155;
  line-height: 1;
}

.stat-pill-value--blue {
  color: #165dff;
}

.stat-pill-value--amber {
  color: #d97706;
}

.stat-pill-value--green {
  color: #059669;
}

.card-review {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 4px 14px;
  border-top: 1px solid #f1f5f9;
  background: #fff;
  height: 30px;
  flex-shrink: 0;
  overflow: hidden;
}

.review-label {
  flex-shrink: 0;
  font-size: 12px;
  font-weight: 700;
  color: #64748b;
}

.review-gaps {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  flex: 1;
}

.gap-chip {
  display: inline-flex;
  align-items: center;
  padding: 2px 8px;
  border-radius: 4px;
  background: #fff7ed;
  color: #c2410c;
  font-size: 12px;
  font-weight: 600;
}

.review-ok {
  color: #059669;
  font-size: 12px;
  font-weight: 600;
}

.card-footer {
  display: flex;
  flex-wrap: wrap;
  justify-content: flex-end;
  align-items: center;
  gap: 8px;
  padding: 4px 14px;
  border-top: 1px solid #f1f5f9;
  background: #fff;
  height: 44px;
  flex-shrink: 0;
  overflow: hidden;
}

.card-footer :deep(.el-button) {
  font-size: 13px !important;
  padding: 7px 16px !important;
  height: 34px !important;
}

.pager {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 12px;
  padding: 20px 4px 0;
}

.pager-text {
  font-size: 13px;
  color: #86909c;
}

@media (max-width: 900px) {
  .card-header {
    flex-direction: column;
    gap: 8px;
  }

  .score-highlight,
  .progress-highlight {
    display: flex;
    align-items: baseline;
    gap: 8px;
    text-align: left;
  }

  .score-value {
    font-size: 20px;
  }

  .card-body {
    flex-direction: column;
    gap: 8px;
    align-items: stretch;
  }

  .stat-divider {
    width: 100%;
    height: 1px;
  }

  .stat-group--secondary {
    justify-content: flex-start;
  }
}

@media (max-width: 640px) {
  .history-page {
    padding: 12px 14px 24px;
  }

  .summary-bar {
    flex-direction: column;
    align-items: stretch;
  }

  .summary-tools {
    margin-left: 0;
    padding-left: 0;
    padding-top: 8px;
    border-top: 1px solid #f1f5f9;
    justify-content: flex-end;
  }

  .card-footer,
  .pager {
    flex-direction: column;
    align-items: stretch;
  }

  .card-footer :deep(.van-button) {
    width: 100%;
  }

  .stat-group--primary,
  .stat-group--secondary {
    width: 100%;
  }

  .stat-pill {
    flex: 1;
    min-width: calc(50% - 6px);
  }
}
</style>
