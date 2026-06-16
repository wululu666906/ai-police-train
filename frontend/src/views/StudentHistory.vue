<template>
  <div class="student-page student-page--hall history-page">
    <div class="hall-layout hall-layout--list">
      <template v-if="!loading">
        <div class="list-toolbar history-toolbar">
          <div>
            <h1 class="history-title">训练历史</h1>
            <p class="list-subtitle">统一查看进行中、已完成和已隐藏的训练记录</p>
          </div>
        </div>

        <section class="summary-grid">
          <article v-for="item in summaryCards" :key="item.key" class="card summary-card">
            <div class="summary-card__content">
              <span class="summary-card__label">{{ item.label }}</span>
              <strong class="summary-card__value" :class="`summary-card__value--${item.tone}`">
                {{ item.value }}
              </strong>
            </div>
          </article>
        </section>

        <section class="card filter-panel">
          <div class="filter-panel__left">
            <span class="filter-panel__label">状态筛选：</span>
            <button
              v-for="item in statusTabs"
              :key="item.value"
              type="button"
              class="filter-chip"
              :class="{ 'filter-chip--active': item.active }"
              @click="item.onClick"
            >
              {{ item.label }}
            </button>
          </div>

          <div class="filter-panel__right">
            <div class="filter-input">
              <input
                v-model.trim="searchKeyword"
                type="text"
                class="filter-input__field"
                placeholder="搜索案件名称或训练类型"
              />
            </div>

            <div class="date-filter">
              <el-date-picker
                v-model="dateRange"
                type="daterange"
                range-separator="-"
                start-placeholder="开始日期"
                end-placeholder="结束日期"
                value-format="YYYY-MM-DD"
                :teleported="false"
              />
            </div>
          </div>
        </section>
      </template>

      <section class="card history-table-card">
        <div v-if="loading" class="state-panel loading-state">
          <el-skeleton :rows="8" animated />
        </div>

        <div v-else-if="loadError" class="state-panel error-state">
          <el-empty :description="loadError">
            <div class="error-actions">
              <el-button @click="fetchHistory">重新加载</el-button>
              <el-button type="primary" @click="router.push('/student/hall')">前往训练大厅</el-button>
            </div>
          </el-empty>
        </div>

        <div v-else-if="filteredRecords.length === 0" class="state-panel empty-state">
          <el-empty :description="emptyTitle">
            <template #description>
              <p>{{ emptyTitle }}</p>
              <span v-if="searchKeyword || hasDateRange">可以清空筛选条件后再查看。</span>
              <span v-else>{{ emptyDescription }}</span>
            </template>
            <el-button type="primary" @click="router.push('/student/hall')">前往训练大厅</el-button>
          </el-empty>
        </div>

        <template v-else>
          <div class="history-table__head">
            <div>案件信息</div>
            <div>训练状态</div>
            <div>时间</div>
            <div>能力指标</div>
            <div>综合评分</div>
            <div>操作</div>
          </div>

          <div class="history-table__body">
            <article v-for="record in filteredRecords" :key="record.id" class="history-row">
              <div class="history-row__case">
                <div class="history-row__case-text">
                  <h3 class="history-row__title">{{ record.case_title || '未命名案件' }}</h3>
                  <p class="history-row__scene">{{ record.scene_name || '未指定场景' }}</p>
                  <div class="history-row__meta">
                    <span>{{ record.case_type || '未分类' }}</span>
                    <span>难度 {{ record.difficulty || '中等' }}</span>
                  </div>
                </div>
              </div>

              <div class="history-row__status">
                <span class="status-badge" :class="record.status === 'finished' ? 'status-badge--done' : 'status-badge--live'">
                  {{ record.status === 'finished' ? '已完成' : '进行中' }}
                </span>
              </div>

              <div class="history-row__time">
                <div class="history-row__time-main">{{ formatTime(record.created_at) }}</div>
                <div class="history-row__time-sub">对话 {{ record.turn_count ?? 0 }} 轮次</div>
              </div>

              <div class="history-row__metrics">
                <span class="metric-chip metric-chip--blue">配合 {{ record.final_cooperation ?? record.final_trust ?? 30 }}</span>
                <span class="metric-chip metric-chip--orange">风险 {{ record.final_risk ?? 50 }}</span>
                <span class="metric-chip metric-chip--green">清晰 {{ record.final_clarity ?? 50 }}</span>
                <span class="metric-chip metric-chip--red">情绪 {{ record.final_emotion ?? '--' }}</span>
              </div>

              <div class="history-row__score" :class="getScoreClass(record.total_score)">
                {{ getDisplayScore(record) }}
              </div>

              <div class="history-row__actions">
                <el-dropdown
                  trigger="click"
                  popper-class="history-action-dropdown"
                  :disabled="isActionLocked(record.id)"
                  @command="(command: string | number | object) => handleRecordAction(command, record)"
                >
                  <button
                    type="button"
                    class="action-menu-trigger"
                    :class="{ 'action-menu-trigger--loading': isActionLocked(record.id) }"
                    :disabled="isActionLocked(record.id)"
                  >
                    <span>操作</span>
                    <span v-if="isActionLocked(record.id)" class="action-loading-dot" aria-hidden="true"></span>
                    <el-icon v-else><ArrowDown /></el-icon>
                  </button>
                  <template #dropdown>
                    <el-dropdown-menu>
                      <el-dropdown-item command="dialogue">
                        <el-icon><ChatLineRound /></el-icon>
                        <span>查看对话</span>
                      </el-dropdown-item>
                      <el-dropdown-item v-if="record.status === 'finished'" command="report">
                        <el-icon><Document /></el-icon>
                        <span>查看报告</span>
                      </el-dropdown-item>
                      <el-dropdown-item v-if="record.status === 'finished'" command="reevaluate" :disabled="reEvaluatingId !== null">
                        <el-icon><Refresh /></el-icon>
                        <span>重新评估</span>
                      </el-dropdown-item>
                      <el-dropdown-item v-if="record.status !== 'finished'" command="continue">
                        <el-icon><VideoPlay /></el-icon>
                        <span>继续训练</span>
                      </el-dropdown-item>
                      <el-dropdown-item command="delete" divided :disabled="deletingId !== null || reEvaluatingId !== null" class="history-action-dropdown__danger">
                        <el-icon><Delete /></el-icon>
                        <span>删除记录</span>
                      </el-dropdown-item>
                    </el-dropdown-menu>
                  </template>
                </el-dropdown>
              </div>
            </article>
          </div>

          <div class="history-table__footer">
            <span class="history-table__count">共 {{ filteredRecords.length }} 条记录</span>

            <div v-if="total > pageSize" class="pager">
              <el-button size="small" :disabled="page <= 1" @click="changePage(page - 1)">上一页</el-button>
              <span class="pager-number">{{ page }}</span>
              <el-button size="small" :disabled="page >= totalPages" @click="changePage(page + 1)">下一页</el-button>
              <span class="pager-size">{{ pageSize }} 条/页</span>
            </div>
          </div>
        </template>
      </section>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, inject, onMounted, onUnmounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { showConfirmDialog, showToast } from 'vant'
import { ArrowDown, ChatLineRound, Delete, Document, Refresh, VideoPlay } from '@element-plus/icons-vue'
import request from '../utils/request'
import '../geeker-adapt/styles/student-hall.scss'

const router = useRouter()
const setMainScrollable = inject<(value: boolean) => void>('setMainScrollable')

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
const searchKeyword = ref('')
const dateRange = ref<[string, string] | []>([])

const hasDateRange = computed(() => Array.isArray(dateRange.value) && dateRange.value.length === 2)

const summaryCards = computed(() => [
  { key: 'total', label: '全部记录', value: total.value, tone: 'blue' },
  { key: 'active', label: '进行中', value: activeCount.value, tone: 'indigo' },
  { key: 'finished', label: '已完成', value: finishedCount.value, tone: 'green' },
  { key: 'hidden', label: '已隐藏会话', value: hiddenEmptyCount.value, tone: 'orange' },
])

const statusTabs = computed(() => [
  {
    label: '全部',
    value: 'all',
    active: statusFilter.value === 'all' && !showEmptySessions.value,
    onClick: () => changeStatusFilter('all'),
  },
  {
    label: '进行中',
    value: 'active',
    active: statusFilter.value === 'active',
    onClick: () => changeStatusFilter('active'),
  },
  {
    label: '已完成',
    value: 'finished',
    active: statusFilter.value === 'finished',
    onClick: () => changeStatusFilter('finished'),
  },
  {
    label: '已隐藏',
    value: 'hidden',
    active: showEmptySessions.value,
    onClick: () => handleToggleEmpty(),
  },
])

const filteredRecords = computed(() => {
  const keyword = searchKeyword.value.trim().toLowerCase()
  const start = hasDateRange.value ? String(dateRange.value[0] ?? '') : ''
  const end = hasDateRange.value ? String(dateRange.value[1] ?? '') : ''

  return records.value.filter((record) => {
    const title = String(record.case_title || '').toLowerCase()
    const type = String(record.case_type || '').toLowerCase()
    const scene = String(record.scene_name || '').toLowerCase()
    const created = String(record.created_at || '')
    const day = created ? created.slice(0, 10) : ''

    const matchKeyword = !keyword || title.includes(keyword) || type.includes(keyword) || scene.includes(keyword)
    const matchDate = !hasDateRange.value || (day >= start && day <= end)
    return matchKeyword && matchDate
  })
})

const emptyTitle = computed(() => {
  if (searchKeyword.value || hasDateRange.value) return '当前筛选条件下暂无训练记录'
  if (statusFilter.value === 'active') return '暂无进行中的训练记录'
  if (statusFilter.value === 'finished') return '暂无已完成训练记录'
  if (showEmptySessions.value) return '暂无隐藏会话记录'
  return '暂无训练记录'
})

const emptyDescription = computed(() => {
  if (statusFilter.value === 'active') return '开始一场训练后，未结束的会话会显示在这里。'
  if (statusFilter.value === 'finished') return '完成一次训练并生成评估后，记录会显示在这里。'
  if (showEmptySessions.value) return '这里会显示被隐藏的空会话记录。'
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
    hiddenEmptyCount.value = Number(res.hidden_empty_count || 0)
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
    showToast(error?.response?.data?.detail || '重新评估失败')
  } finally {
    reEvaluatingId.value = null
  }
}

const continueTraining = (sessionId: number) => {
  router.push(`/student/training/${sessionId}`)
}

const openDialogue = (sessionId: number) => {
  if (!sessionId) return
  router.push(`/student/history/${sessionId}/dialogue`)
}

const isActionLocked = (sessionId: number) => deletingId.value === sessionId || reEvaluatingId.value === sessionId

const handleRecordAction = async (rawCommand: string | number | object, record: any) => {
  if (!record?.id || isActionLocked(record.id)) return
  const command = String(rawCommand)

  if (command === 'dialogue') {
    openDialogue(record.id)
    return
  }

  if (command === 'report') {
    router.push(`/student/evaluation?session_id=${record.id}`)
    return
  }

  if (command === 'continue') {
    continueTraining(record.id)
    return
  }

  if (command === 'reevaluate') {
    await reEvaluate(record.id)
    return
  }

  if (command === 'delete') {
    await deleteSession(record.id)
  }
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
    showToast(error?.response?.data?.detail || '删除训练记录失败')
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
  showEmptySessions.value = false
  if (nextStatus === statusFilter.value) return
  statusFilter.value = nextStatus
  page.value = 1
  await fetchHistory()
}

const handleToggleEmpty = async () => {
  showEmptySessions.value = !showEmptySessions.value
  if (showEmptySessions.value) {
    statusFilter.value = 'all'
  }
  page.value = 1
  await fetchHistory()
}

const getDisplayScore = (record: any) => {
  if (record.status === 'finished') return record.total_score ?? '--'
  return record.final_emotion ?? '--'
}

const getScoreClass = (score: number | null | undefined) => {
  const value = Number(score)
  if (!Number.isFinite(value)) return 'history-row__score--warning'
  if (value >= 85) return 'history-row__score--excellent'
  if (value >= 70) return 'history-row__score--good'
  if (value >= 60) return 'history-row__score--warning'
  return 'history-row__score--weak'
}

const formatTime = (iso: string) => {
  if (!iso) return '-'
  const date = new Date(iso)
  return `${date.getMonth() + 1}/${date.getDate()} ${date.getHours().toString().padStart(2, '0')}:${date.getMinutes().toString().padStart(2, '0')}`
}

onMounted(() => {
  setMainScrollable?.(true)
  fetchHistory()
})

onUnmounted(() => {
  setMainScrollable?.(false)
})
</script>

<style scoped>
.history-page {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.history-toolbar {
  align-items: flex-start;
}

.history-title {
  margin: 0;
  color: #111827;
  font-size: 14px;
  font-weight: 800;
}

.list-subtitle {
  margin: 4px 0 0;
  color: #6b7280;
  font-size: 12px;
}

.summary-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
}

.summary-card {
  padding: 14px 16px;
  border-radius: 6px;
}

.summary-card__content {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.summary-card__label {
  color: #64748b;
  font-size: 12px;
  font-weight: 600;
}

.summary-card__value {
  font-size: 26px;
  font-weight: 800;
  line-height: 1.1;
}

.summary-card__value--blue,
.summary-card__value--indigo {
  color: #0f2d6b;
}

.summary-card__value--green {
  color: #18a058;
}

.summary-card__value--orange {
  color: #f97316;
}

.filter-panel {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 12px 16px;
  border-radius: 6px;
}

.filter-panel__left,
.filter-panel__right {
  display: flex;
  align-items: center;
  gap: 10px;
}

.filter-panel__left {
  flex-wrap: wrap;
}

.filter-panel__right {
  margin-left: auto;
}

.filter-panel__label {
  color: #111827;
  font-size: 13px;
  font-weight: 700;
}

.filter-chip {
  border: 1px solid #e5e7eb;
  border-radius: var(--police-radius-lg);
  background: #fff;
  padding: 7px 16px;
  color: #6b7280;
  font-size: 13px;
  font-weight: 700;
  cursor: pointer;
}

.filter-chip--active {
  border-color: var(--student-accent, #0066ff);
  background: var(--student-accent, #0066ff);
  color: #fff;
}

.filter-input,
.date-filter {
  min-width: 280px;
  border: 1px solid #e5e7eb;
  border-radius: var(--police-radius-lg);
  background: #fff;
  padding: 0 12px;
}

.filter-input__field {
  width: 100%;
  height: 38px;
  border: none;
  outline: none;
  background: transparent;
  color: #111827;
  font-size: 13px;
}

.date-filter :deep(.el-input__wrapper) {
  box-shadow: none !important;
  padding: 0;
}

.date-filter :deep(.el-range-input) {
  font-size: 13px;
  color: #111827;
}

.date-filter :deep(.el-range-separator),
.date-filter :deep(.el-input__icon) {
  color: #9ca3af;
}

.history-table-card {
  --history-table-columns: minmax(320px, 2.2fr) minmax(118px, 0.85fr) minmax(150px, 1fr) minmax(360px, 1.7fr) minmax(118px, 0.72fr) minmax(96px, 0.6fr);
  --history-table-gap: 16px;
  --history-table-x: 24px;

  overflow: visible;
  padding: 0;
  border-radius: 6px;
}

.history-table__head,
.history-row {
  display: grid;
  grid-template-columns: var(--history-table-columns);
  gap: var(--history-table-gap);
  box-sizing: border-box;
}

.history-table__head {
  position: sticky;
  top: 0;
  z-index: 20;
  border-bottom: 1px solid #f3f4f6;
  background: #fff;
  padding: 18px var(--history-table-x) 16px;
  color: #111827;
  font-size: 13px;
  font-weight: 700;
}

.history-table__head > div {
  min-width: 0;
}

.history-table__head > div:not(:first-child) {
  text-align: center;
}

.history-table__head::after {
  content: '';
  position: absolute;
  right: 0;
  bottom: -8px;
  left: 0;
  height: 8px;
  pointer-events: none;
  box-shadow: 0 8px 16px rgba(15, 23, 42, 0.08);
}

.history-table__body {
  padding: 0;
}

.history-row {
  align-items: center;
  border-bottom: 1px solid #f3f4f6;
  padding: 18px var(--history-table-x);
  min-height: 140px;
}

.history-row > div {
  min-width: 0;
}

.history-row__case-text {
  min-width: 0;
}

.history-row__title {
  margin: 0;
  color: #111827;
  font-size: 15px;
  font-weight: 800;
  line-height: 22px;
}

.history-row__scene {
  margin: 4px 0 0;
  color: #374151;
  font-size: 12px;
  font-weight: 600;
}

.history-row__meta {
  display: flex;
  gap: 16px;
  margin-top: 8px;
  color: #111827;
  font-size: 12px;
  font-weight: 700;
}

.history-row__status,
.history-row__time,
.history-row__score,
.history-row__actions {
  display: flex;
  align-items: center;
  align-self: stretch;
}

.history-row__time,
.history-row__actions {
  flex-direction: column;
  justify-content: center;
  gap: 10px;
}

.history-row__status,
.history-row__score {
  justify-content: center;
}

.history-row__time-main {
  color: #111827;
  font-size: 12px;
  font-weight: 700;
}

.history-row__time-sub {
  color: #6b7280;
  font-size: 12px;
}

.status-badge {
  display: inline-flex;
  align-items: center;
  border-radius: var(--police-radius);
  padding: 6px 12px;
  font-size: 12px;
  font-weight: 700;
}

.status-badge--done {
  border: 1px solid #d1fae5;
  background: #ecfdf5;
  color: #047857;
}

.status-badge--live {
  border: 1px solid #dbeafe;
  background: #eff6ff;
  color: #165dff;
}

.history-row__metrics {
  display: grid;
  grid-template-columns: repeat(2, minmax(72px, 1fr));
  gap: 6px 8px;
  align-content: center;
  align-self: stretch;
}

.metric-chip {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: 6px;
  padding: 4px 10px;
  font-size: 12px;
  font-weight: 700;
  min-height: 28px;
  box-sizing: border-box;
  white-space: nowrap;
}

.metric-chip--blue {
  border: 1px solid #dbeafe;
  background: #eff6ff;
  color: #165dff;
}

.metric-chip--orange {
  border: 1px solid #fed7aa;
  background: #fff7ed;
  color: #ea580c;
}

.metric-chip--green {
  border: 1px solid #d1fae5;
  background: #ecfdf5;
  color: #059669;
}

.metric-chip--red {
  border: 1px solid #fecaca;
  background: #fff1f2;
  color: #ef4444;
}

.history-row__score {
  font-size: 20px;
  font-weight: 900;
  min-width: 72px;
}

.history-row__score--excellent,
.history-row__score--good {
  color: #ef4444;
}

.history-row__score--warning {
  color: #f97316;
}

.history-row__score--weak {
  color: #dc2626;
}

.history-row__actions {
  min-width: 96px;
  align-items: center;
  justify-content: center;
}

.action-menu-trigger {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  width: 84px;
  height: 38px;
  border: 1px solid #e5e7eb;
  border-radius: 6px;
  background: #fff;
  color: #111827;
  box-shadow: 0 4px 12px rgba(15, 23, 42, 0.04);
  font-size: 13px;
  font-weight: 800;
  cursor: pointer;
  transition:
    border-color 0.18s ease,
    box-shadow 0.18s ease,
    color 0.18s ease;
}

.action-menu-trigger:hover:not(:disabled),
.action-menu-trigger:focus-visible {
  border-color: #bfdbfe;
  color: #165dff;
  box-shadow: 0 8px 18px rgba(22, 93, 255, 0.12);
  outline: none;
}

.action-menu-trigger:disabled {
  cursor: not-allowed;
  opacity: 0.62;
}

.action-loading-dot {
  width: 12px;
  height: 12px;
  border: 2px solid #bfdbfe;
  border-top-color: #165dff;
  border-radius: 50%;
  animation: action-spin 0.8s linear infinite;
}

.history-table__footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 24px;
}

.history-table__count {
  color: #111827;
  font-size: 13px;
  font-weight: 700;
}

.pager {
  display: flex;
  align-items: center;
  gap: 14px;
}

.pager-number {
  display: inline-flex;
  height: 34px;
  min-width: 34px;
  align-items: center;
  justify-content: center;
  border-radius: var(--police-radius);
  background: var(--student-accent, #0066ff);
  padding: 0 12px;
  color: #fff;
  font-size: 13px;
  font-weight: 800;
}

.pager-size {
  border: 1px solid #e5e7eb;
  border-radius: var(--police-radius-lg);
  padding: 8px 14px;
  color: #6b7280;
  font-size: 13px;
  font-weight: 700;
}

.loading-state,
.empty-state,
.error-state {
  display: flex;
  min-height: 360px;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  text-align: center;
}

.error-actions {
  display: flex;
  flex-wrap: wrap;
  justify-content: center;
  gap: 12px;
  margin-top: 16px;
}

@media (max-width: 1480px) {
  .summary-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .filter-panel {
    flex-direction: column;
    align-items: stretch;
  }

  .filter-panel__right {
    margin-left: 0;
    flex-wrap: wrap;
  }

  .history-table-card {
    --history-table-columns: minmax(260px, 2fr) minmax(106px, 0.82fr) minmax(132px, 0.94fr) minmax(300px, 1.55fr) minmax(96px, 0.66fr) minmax(88px, 0.55fr);
    --history-table-gap: 14px;
    --history-table-x: 20px;
  }
}

@media (max-width: 1200px) {
  .history-table__head {
    display: none;
  }

  .history-row {
    grid-template-columns: 1fr;
    gap: 14px;
    padding: 18px 16px;
  }

  .history-row__score {
    justify-content: flex-start;
  }

  .history-row__metrics {
    grid-template-columns: repeat(2, minmax(0, 120px));
  }

  .history-row__actions {
    align-items: stretch;
    min-width: 0;
  }

  .action-menu-trigger {
    width: 100%;
  }
}

@media (max-width: 768px) {
  .summary-grid {
    grid-template-columns: 1fr;
  }

  .filter-input,
  .date-filter {
    min-width: 0;
    width: 100%;
  }

  .history-table__footer {
    flex-direction: column;
    align-items: stretch;
    gap: 12px;
  }

  .history-row__metrics {
    grid-template-columns: 1fr 1fr;
  }

  .pager {
    justify-content: space-between;
  }
}

:global(.history-action-dropdown) {
  min-width: 132px !important;
  border: 1px solid #e5e7eb !important;
  border-radius: 6px !important;
  box-shadow: 0 18px 42px rgba(15, 23, 42, 0.13) !important;
}

:global(.history-action-dropdown .el-dropdown-menu) {
  padding: 8px !important;
}

:global(.history-action-dropdown .el-dropdown-menu__item) {
  display: flex !important;
  align-items: center !important;
  gap: 8px !important;
  min-height: 38px !important;
  border-radius: 5px !important;
  padding: 0 10px !important;
  color: #111827 !important;
  font-size: 13px !important;
  font-weight: 800 !important;
}

:global(.history-action-dropdown .el-dropdown-menu__item:hover) {
  background: #f8fafc !important;
  color: #165dff !important;
}

:global(.history-action-dropdown .el-dropdown-menu__item .el-icon) {
  margin-right: 0 !important;
  font-size: 15px !important;
}

:global(.history-action-dropdown__danger),
:global(.history-action-dropdown__danger .el-icon) {
  color: #ef4444 !important;
}

:global(.history-action-dropdown__danger:hover) {
  background: #fff1f2 !important;
  color: #dc2626 !important;
}

@keyframes action-spin {
  to {
    transform: rotate(360deg);
  }
}
</style>
