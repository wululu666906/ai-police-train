<template>
  <div class="history-page">
    <div class="page-header">
      <div>
        <h1 class="page-title">训练历史</h1>
        <p class="page-desc">查看你的训练记录、会话完成情况和评估结果。</p>
      </div>
      <div class="history-tools">
        <span class="tool-label">显示空会话</span>
        <van-switch v-model="showEmptySessions" size="22px" @change="handleToggleEmpty" />
      </div>
    </div>

    <div v-if="!loading" class="summary-bar">
      <div class="summary-item">
        <span class="summary-num">{{ total }}</span>
        <span class="summary-label">{{ showEmptySessions ? '当前筛选结果' : '当前可见记录' }}</span>
      </div>
      <div class="summary-item">
        <span class="summary-num">{{ activeCount }}</span>
        <span class="summary-label">进行中训练</span>
      </div>
      <div class="summary-item">
        <span class="summary-num">{{ finishedCount }}</span>
        <span class="summary-label">已完成训练</span>
      </div>
      <div v-if="hiddenEmptyCount > 0 && !showEmptySessions" class="summary-item">
        <span class="summary-num summary-warn">{{ hiddenEmptyCount }}</span>
        <span class="summary-label">已隐藏空会话</span>
      </div>
      <div v-if="showEmptySessions" class="summary-tip">空会话指尚未产生有效对话内容的训练记录。</div>
    </div>

    <div v-if="!loading" class="status-filter-row">
      <button
        v-for="item in statusOptions"
        :key="item.value"
        type="button"
        class="status-chip"
        :class="{ active: statusFilter === item.value }"
        @click="changeStatusFilter(item.value)"
      >
        {{ item.label }}
      </button>
    </div>

    <div v-if="loading" class="loading-state">
      <van-loading color="#165DFF">加载中...</van-loading>
    </div>

    <div v-else-if="loadError" class="error-state">
      <van-icon name="warning-o" size="48" color="#f59e0b" />
      <p>{{ loadError }}</p>
      <span>你可以稍后重试，或先返回训练大厅继续训练。</span>
      <div class="error-actions">
        <van-button plain size="small" @click="fetchHistory">重新加载</van-button>
        <van-button type="primary" size="small" class="go-btn" @click="router.push('/student/hall')">
          前往训练大厅
        </van-button>
      </div>
    </div>

    <div v-else-if="records.length === 0" class="empty-state">
      <van-icon name="records-o" size="48" color="#C9CDD4" />
      <p>{{ emptyTitle }}</p>
      <span v-if="hiddenEmptyCount > 0">当前有 {{ hiddenEmptyCount }} 条空会话被自动隐藏。</span>
      <span v-else>{{ emptyDescription }}</span>
      <van-button type="primary" size="small" class="go-btn" @click="router.push('/student/hall')">
        前往训练大厅
      </van-button>
    </div>

    <div v-else>
      <div class="history-list">
        <article v-for="record in records" :key="record.id" class="history-card">
          <div class="card-top">
            <div>
              <div class="record-id">会话 #{{ record.id }}</div>
              <h3 class="record-title">{{ record.case_title }}</h3>
              <div v-if="record.status !== 'finished'" class="record-substatus" :class="{ empty: record.is_empty_session }">
                {{ record.is_empty_session ? '仅创建未开聊' : '已有进行中对话' }}
              </div>
            </div>
            <van-tag :type="record.status === 'finished' ? 'success' : 'warning'" size="medium">
              {{ record.status === 'finished' ? '已完成' : '进行中' }}
            </van-tag>
          </div>

          <div class="record-grid">
            <div class="record-item">
              <span class="item-label">案件类型</span>
              <span class="item-value">{{ record.case_type }}</span>
            </div>
            <div class="record-item">
              <span class="item-label">训练场景</span>
              <span class="item-value">{{ record.scene_name }}</span>
            </div>
            <div class="record-item">
              <span class="item-label">难度</span>
              <span class="item-value">{{ record.difficulty }}</span>
            </div>
            <div class="record-item">
              <span class="item-label">时间</span>
              <span class="item-value">{{ formatTime(record.created_at) }}</span>
            </div>
          </div>

          <div class="metric-row">
            <div class="metric-card">
              <span class="metric-label">对话轮次</span>
              <strong class="metric-value">{{ record.turn_count ?? 0 }}</strong>
              <span v-if="record.is_empty_session" class="metric-tip">尚未开始有效对话</span>
            </div>
            <div class="metric-card">
              <span class="metric-label">最终情绪</span>
              <strong class="metric-value" :style="{ color: getEmotionColor(record.final_emotion) }">
                {{ record.final_emotion }}
              </strong>
            </div>
            <div class="metric-card">
              <span class="metric-label">最终配合</span>
              <strong class="metric-value trust">{{ record.final_cooperation ?? record.final_trust ?? 30 }}</strong>
            </div>
            <div class="metric-card">
              <span class="metric-label">失控风险</span>
              <strong class="metric-value risk">{{ record.final_risk ?? 50 }}</strong>
            </div>
            <div class="metric-card">
              <span class="metric-label">表达清晰</span>
              <strong class="metric-value clarity">{{ record.final_clarity ?? 50 }}</strong>
            </div>
            <div class="metric-card">
              <span class="metric-label">已获信息</span>
              <strong class="metric-value">{{ record.revealed_info_count ?? 0 }}</strong>
            </div>
          </div>

          <div v-if="record.status === 'finished'" class="result-strip">
            <div class="result-strip-item">
              <span class="result-strip-label">综合评分</span>
              <strong class="result-strip-score">{{ record.total_score ?? '--' }}</strong>
            </div>
            <div v-if="record.stage_gap_missing?.length" class="result-strip-item grow">
              <span class="result-strip-label">待复盘缺口</span>
              <div class="gap-chip-row">
                <span v-for="item in record.stage_gap_missing" :key="item" class="gap-chip">{{ item }}</span>
              </div>
            </div>
            <div v-else class="result-strip-item grow">
              <span class="result-strip-label">阶段回顾</span>
              <span class="gap-complete">关键项覆盖较完整</span>
            </div>
          </div>

          <div class="action-cell">
            <van-button
              v-if="record.status === 'finished'"
              size="small"
              type="primary"
              plain
              @click="router.push(`/student/evaluation?session_id=${record.id}`)"
            >
              查看报告
            </van-button>
            <van-button
              v-if="record.status === 'finished'"
              size="small"
              plain
              :loading="reEvaluatingId === record.id"
              :disabled="reEvaluatingId !== null"
              @click="reEvaluate(record.id)"
            >
              重新评估
            </van-button>
            <van-button
              v-if="record.status !== 'finished'"
              size="small"
              type="success"
              plain
              @click="continueTraining(record.id)"
            >
              继续训练
            </van-button>
            <van-button
              size="small"
              type="danger"
              plain
              :loading="deletingId === record.id"
              :disabled="deletingId !== null || reEvaluatingId !== null"
              @click="deleteSession(record.id)"
            >
              删除记录
            </van-button>
          </div>
        </article>
      </div>

      <div v-if="total > pageSize" class="pager">
        <van-button size="small" plain :disabled="page <= 1" @click="changePage(page - 1)">上一页</van-button>
        <span class="pager-text">第 {{ page }} / {{ totalPages }} 页，共 {{ total }} 条</span>
        <van-button size="small" plain :disabled="page >= totalPages" @click="changePage(page + 1)">下一页</van-button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { showConfirmDialog, showToast } from 'vant'
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
  } catch {
    records.value = []
    total.value = 0
    hiddenEmptyCount.value = 0
    activeCount.value = 0
    finishedCount.value = 0
    totalPages.value = 1
    loadError.value = '训练历史加载失败'
    showToast('获取历史记录失败')
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

const formatTime = (iso: string) => {
  if (!iso) return '-'
  const d = new Date(iso)
  return `${d.getMonth() + 1}/${d.getDate()} ${d.getHours().toString().padStart(2, '0')}:${d.getMinutes().toString().padStart(2, '0')}`
}

onMounted(fetchHistory)
</script>

<style scoped>
.history-page {
  padding: 24px 24px 36px;
  max-width: 1160px;
  margin: 0 auto;
  font-family: 'PingFang SC', 'Microsoft YaHei', 'Segoe UI', sans-serif;
}

.page-header {
  margin-bottom: 20px;
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
}

.page-title {
  font-size: 28px;
  font-weight: 800;
  color: #1d2129;
  margin: 0;
}

.page-desc {
  font-size: 14px;
  color: #86909c;
  margin: 8px 0 0;
}

.history-tools {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 12px;
  background: #fff;
  border: 1px solid #e5e6eb;
  border-radius: 12px;
}

.tool-label {
  font-size: 13px;
  color: #4e5969;
}

.summary-bar {
  display: flex;
  align-items: center;
  gap: 16px;
  margin-bottom: 20px;
  padding: 14px 16px;
  background: #f7f8fa;
  border-radius: 14px;
  flex-wrap: wrap;
}

.summary-item {
  display: flex;
  align-items: baseline;
  gap: 8px;
}

.status-filter-row {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  margin-bottom: 18px;
}

.status-chip {
  border: 1px solid #d9e1ec;
  background: #fff;
  color: #4e5969;
  border-radius: 999px;
  padding: 8px 14px;
  font-size: 13px;
  font-weight: 700;
  transition: all 0.2s ease;
}

.status-chip.active {
  border-color: #165dff;
  background: #165dff;
  color: #fff;
}

.summary-num {
  font-size: 22px;
  font-weight: 700;
  color: #165dff;
}

.summary-warn {
  color: #ff7d00;
}

.summary-label,
.summary-tip {
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

.history-list {
  display: grid;
  gap: 16px;
}

.history-card {
  background: rgba(255, 255, 255, 0.96);
  border-radius: 18px;
  border: 1px solid #e5e6eb;
  box-shadow: 0 8px 24px rgba(15, 23, 42, 0.04);
  padding: 18px;
}

.card-top {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 12px;
}

.record-id {
  font-size: 12px;
  color: #6b7c93;
  font-weight: 700;
}

.record-title {
  margin: 6px 0 0;
  color: #1d2129;
  font-size: 18px;
}

.record-substatus {
  display: inline-flex;
  margin-top: 8px;
  padding: 4px 10px;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 700;
  color: #165dff;
  background: #eaf2ff;
}

.record-substatus.empty {
  color: #c2410c;
  background: #fff7ed;
}

.record-grid {
  margin-top: 16px;
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
}

.record-item {
  padding: 12px 14px;
  background: #f8fbff;
  border-radius: 14px;
}

.item-label {
  display: block;
  font-size: 12px;
  color: #7b8794;
}

.item-value {
  display: block;
  margin-top: 6px;
  font-size: 14px;
  color: #1d2129;
  font-weight: 600;
}

.metric-row {
  margin-top: 14px;
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;
}

.metric-card {
  padding: 14px;
  border-radius: 14px;
  background: #fff;
  border: 1px solid #eef2f6;
}

.metric-label {
  display: block;
  color: #7b8794;
  font-size: 12px;
}

.metric-value {
  display: block;
  margin-top: 8px;
  color: #1d2129;
  font-size: 24px;
  font-weight: 800;
}

.metric-value.trust {
  color: #165dff;
}

.metric-value.risk {
  color: #d97706;
}

.metric-value.clarity {
  color: #0f9f56;
}

.metric-tip {
  display: block;
  margin-top: 6px;
  color: #86909c;
  font-size: 12px;
}

.action-cell {
  margin-top: 16px;
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.result-strip {
  margin-top: 14px;
  padding: 14px;
  border-radius: 14px;
  background: linear-gradient(180deg, #f8fbff 0%, #f5f9ff 100%);
  border: 1px solid #dbe8ff;
  display: flex;
  gap: 16px;
  flex-wrap: wrap;
}

.result-strip-item {
  min-width: 120px;
}

.result-strip-item.grow {
  flex: 1;
}

.result-strip-label {
  display: block;
  font-size: 12px;
  color: #6b7c93;
}

.result-strip-score {
  display: block;
  margin-top: 8px;
  font-size: 24px;
  font-weight: 800;
  color: #165dff;
}

.gap-chip-row {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 8px;
}

.gap-chip {
  display: inline-flex;
  align-items: center;
  padding: 5px 10px;
  border-radius: 999px;
  background: #fff7ed;
  color: #c2410c;
  font-size: 12px;
  font-weight: 700;
}

.gap-complete {
  display: inline-block;
  margin-top: 8px;
  color: #15803d;
  font-size: 13px;
  font-weight: 700;
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
  .record-grid,
  .metric-row {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 640px) {
  .history-page {
    padding: 16px 14px 28px;
  }

  .page-header,
  .card-top,
  .pager {
    flex-direction: column;
    align-items: stretch;
  }

  .record-grid,
  .metric-row {
    grid-template-columns: 1fr;
  }
}
</style>
