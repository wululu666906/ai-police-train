<template>
  <div class="student-page training-history-page">
    <section class="filter-panel">
      <div class="filter-grid">
        <div class="filter-item">
          <label>实训类型</label>
          <el-select v-model="typeFilter" placeholder="全部类型" :teleported="false">
            <el-option label="全部类型" value="all" />
            <el-option v-for="item in availableTypes" :key="item" :label="item" :value="item" />
          </el-select>
        </div>

        <div class="filter-item">
          <label>训练模式</label>
          <el-select v-model="modeFilter" placeholder="全部模式" :teleported="false">
            <el-option label="全部模式" value="all" />
            <el-option label="练习模式" value="practice" />
            <el-option label="正式考核" value="exam" />
          </el-select>
        </div>

        <div class="filter-item">
          <label>完成状态</label>
          <el-select v-model="statusFilter" placeholder="全部状态" :teleported="false">
            <el-option label="全部状态" value="all" />
            <el-option label="已完成" value="finished" />
            <el-option label="进行中" value="active" />
            <el-option label="待重修" value="retry" />
            <el-option label="已放弃" value="abandoned" />
          </el-select>
        </div>

        <div class="filter-item filter-item--range">
          <label>开始时间</label>
          <el-date-picker
            v-model="dateRange"
            type="daterange"
            start-placeholder="开始日期"
            end-placeholder="结束日期"
            range-separator="-"
            value-format="YYYY-MM-DD"
          />
        </div>

        <div class="filter-item filter-item--search">
          <label>&nbsp;</label>
          <el-input
            v-model="keyword"
            placeholder="搜索视频名称、场景、关键词"
            clearable
            :prefix-icon="Search"
          />
        </div>

        <div class="filter-item filter-item--action">
          <label>&nbsp;</label>
          <el-button plain class="reset-btn" @click="resetFilters">
            <el-icon><Refresh /></el-icon>
            重置
          </el-button>
        </div>
      </div>
    </section>

    <section class="table-panel">
      <div v-if="loading" class="state-panel">
        <el-skeleton :rows="8" animated />
      </div>

      <div v-else-if="!pagedSessions.length" class="state-panel">
        <el-empty description="暂无符合条件的实训记录">
          <el-button type="primary" @click="router.push('/student/videos')">前往视频实训中心</el-button>
        </el-empty>
      </div>

      <template v-else>
        <div class="history-table">
          <div class="history-table__head">
            <div>序号</div>
            <div>视频名称</div>
            <div>场景/案例</div>
            <div>训练模式</div>
            <div>完成状态</div>
            <div>得分</div>
            <div>评级</div>
            <div>节点完成度</div>
            <div>用时</div>
            <div>完成时间</div>
            <div>操作</div>
          </div>

          <div class="history-table__body">
            <div
              v-for="(item, index) in pagedSessions"
              :key="item.id"
              class="history-row"
              :class="{ 'history-row--clickable': canViewReport(item), 'history-row--menu-open': openActionMenuId === item.id }"
              @click="handleRowClick(item)"
            >
              <div class="cell-center">{{ (currentPage - 1) * pageSize + index + 1 }}</div>

              <div class="history-row__title-cell">
                <div class="history-row__title">{{ item.video_title || '未知视频' }}</div>
                <div class="history-row__sub">Session #{{ item.id }}</div>
              </div>

              <div class="history-row__scene">{{ item.category || '综合训练' }}</div>

              <div class="cell-center">
                <span class="mode-badge" :class="item.mode === 'exam' ? 'mode-badge--exam' : 'mode-badge--practice'">
                  {{ item.mode === 'exam' ? '正式考核' : '练习模式' }}
                </span>
              </div>

              <div class="cell-center">
                <span class="status-badge" :class="`status-badge--${statusKey(item)}`">
                  {{ statusText(item) }}
                </span>
              </div>

              <div class="cell-center score-cell" :class="scoreClass(item)">
                <template v-if="item.score_percentage != null">
                  {{ item.score_percentage.toFixed(1) }}
                </template>
                <span v-else>--</span>
              </div>

              <div class="cell-center grade-cell">
                <span v-if="item.grade" class="grade-badge" :class="`grade-badge--${gradeKey(item)}`">
                  {{ item.grade }}
                </span>
                <span v-else class="muted">--</span>
              </div>

              <div class="progress-cell">
                <div class="mini-progress">
                  <span :style="{ width: `${calcProgress(item)}%` }" />
                </div>
                <div class="progress-text">{{ item.current_node_index }}/{{ item.node_total || 0 }}</div>
              </div>

              <div class="cell-center">{{ durationText(item) }}</div>

              <div class="time-cell">
                <div>{{ formatDateTime(item.finished_at || item.created_at) }}</div>
                <div class="muted">{{ item.finished_at ? '已结束' : '最近更新' }}</div>
              </div>

              <div class="action-cell action-cell--sticky" @click.stop>
                <template v-if="item.status === 'active'">
                  <el-button type="primary" plain size="small" @click="handleAction('continue', item)">继续训练</el-button>
                </template>
                <template v-else-if="canViewReport(item)">
                  <el-button type="primary" size="small" @click="handleAction('report', item)">查看报告</el-button>
                </template>
                <template v-else>
                  <el-button type="warning" plain size="small" @click="handleAction('redo', item)">去重修</el-button>
                </template>

                <div class="more-menu">
                  <button
                    type="button"
                    class="more-btn"
                    :class="{ 'more-btn--open': openActionMenuId === item.id }"
                    :aria-expanded="openActionMenuId === item.id"
                    aria-haspopup="menu"
                    @click.stop="toggleActionMenu(item.id, $event)"
                  >
                    <el-icon><MoreFilled /></el-icon>
                  </button>
                  <div
                    v-if="openActionMenuId === item.id"
                    class="more-menu__panel"
                    :class="`more-menu__panel--${actionMenuPlacement}`"
                    role="menu"
                    @click.stop
                  >
                    <button v-if="canViewReport(item)" type="button" class="more-menu__item" role="menuitem" @click="handleMenuAction('report', item)">查看报告</button>
                    <button v-if="item.status === 'active'" type="button" class="more-menu__item" role="menuitem" @click="handleMenuAction('continue', item)">继续训练</button>
                    <button v-if="item.video_id" type="button" class="more-menu__item" role="menuitem" @click="handleMenuAction('redo', item)">重新训练</button>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>

        <div class="table-footer">
          <span class="table-footer__count">共 {{ totalCount }} 条</span>
          <div class="pager-controls">
            <el-pagination
              v-model:current-page="currentPage"
              background
              layout="prev, pager, next"
              :page-size="pageSize"
              :total="totalCount"
              @current-change="fetchHistory"
            />
            <div class="page-size-menu" @click.stop>
              <button
                type="button"
                class="page-size-menu__trigger"
                :aria-expanded="showPageSizeMenu"
                aria-haspopup="listbox"
                @click="togglePageSizeMenu"
              >
                <span>{{ pageSize }}条/页</span>
                <el-icon><ArrowUp /></el-icon>
              </button>
              <div v-if="showPageSizeMenu" class="page-size-menu__panel" role="listbox">
                <button
                  v-for="size in pageSizeOptions"
                  :key="size"
                  type="button"
                  class="page-size-menu__item"
                  :class="{ 'page-size-menu__item--active': pageSize === size }"
                  role="option"
                  :aria-selected="pageSize === size"
                  @click="selectPageSize(size)"
                >
                  {{ size }}条/页
                </button>
              </div>
            </div>
          </div>
        </div>
      </template>
    </section>
  </div>
</template>

<script setup lang="ts">
import { computed, inject, onMounted, onUnmounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { ArrowUp, MoreFilled, Refresh, Search } from '@element-plus/icons-vue'
import request from '../utils/request'

interface SessionItem {
  id: number
  video_id: number
  video_title?: string
  category?: string
  difficulty?: string
  node_total: number
  mode: string
  status: string
  current_node_index: number
  total_score: number | null
  full_score: number | null
  score_percentage: number | null
  grade?: string | null
  needs_retry?: boolean
  duration_seconds?: number | null
  report_ready?: boolean
  evaluation_status?: string
  failure_reasons?: Record<string, number>
  created_at: string
  finished_at?: string
}

interface HistoryResponse {
  items: SessionItem[]
  total: number
  page: number
  page_size: number
  has_more: boolean
  available_categories: string[]
}

const route = useRoute()
const router = useRouter()
const setMainScrollable = inject<(value: boolean) => void>('setMainScrollable')

const sessions = ref<SessionItem[]>([])
const totalCount = ref(0)
const availableCategories = ref<string[]>([])
const loading = ref(true)
const openActionMenuId = ref<number | null>(null)
const showPageSizeMenu = ref(false)
const pageSizeOptions = [8, 10, 20]
const actionMenuPlacement = ref<'up' | 'down'>('down')

// 从 URL query 恢复筛选状态
const typeFilter = ref(String(route.query.category || 'all'))
const modeFilter = ref<'all' | 'practice' | 'exam'>((route.query.mode as 'all' | 'practice' | 'exam') || 'all')
const statusFilter = ref<'all' | 'finished' | 'active' | 'retry' | 'abandoned'>((route.query.status as 'all' | 'finished' | 'active' | 'retry' | 'abandoned') || 'all')
const keyword = ref(String(route.query.keyword || ''))
const dateRange = ref<[string, string] | []>(
  route.query.date_start && route.query.date_end
    ? [String(route.query.date_start), String(route.query.date_end)]
    : []
)
const currentPage = ref(Number(route.query.page) || 1)
const pageSize = ref(Number(route.query.page_size) || 10)

// debounce 工具
let debounceTimer: ReturnType<typeof setTimeout> | null = null
function debounce(fn: () => void, ms = 300) {
  if (debounceTimer) clearTimeout(debounceTimer)
  debounceTimer = setTimeout(fn, ms)
}

onMounted(() => {
  setMainScrollable?.(false)
  void fetchHistory()
  document.addEventListener('click', closeFloatingMenus)
  window.addEventListener('resize', closeFloatingMenus)
  document.querySelector('.student-main')?.addEventListener('scroll', closeFloatingMenus, { passive: true })
})

onUnmounted(() => {
  setMainScrollable?.(false)
  document.removeEventListener('click', closeFloatingMenus)
  window.removeEventListener('resize', closeFloatingMenus)
  document.querySelector('.student-main')?.removeEventListener('scroll', closeFloatingMenus)
  if (debounceTimer) clearTimeout(debounceTimer)
})

// 监听筛选变化 - 服务端分页（使用 flush: 'post' 合并同步修改）
watch(
  [typeFilter, modeFilter, statusFilter, dateRange],
  () => {
    currentPage.value = 1
    syncQueryParams()
    void fetchHistory()
  },
  { flush: 'post' },
)

watch(keyword, () => {
  debounce(() => {
    currentPage.value = 1
    syncQueryParams()
    void fetchHistory()
  })
})

// 同步筛选状态到 URL
function syncQueryParams() {
  const query: Record<string, string> = {}
  if (typeFilter.value !== 'all') query.category = typeFilter.value
  if (modeFilter.value !== 'all') query.mode = modeFilter.value
  if (statusFilter.value !== 'all') query.status = statusFilter.value
  if (keyword.value) query.keyword = keyword.value
  if (dateRange.value.length === 2) {
    query.date_start = dateRange.value[0]
    query.date_end = dateRange.value[1]
  }
  if (currentPage.value > 1) query.page = String(currentPage.value)
  if (pageSize.value !== 10) query.page_size = String(pageSize.value)
  router.replace({ query })
}

const availableTypes = computed(() => availableCategories.value)

// 前端仅做 keyword 本地过滤（其他筛选已由后端处理）
const filteredSessions = computed(() => {
  const kw = keyword.value.trim().toLowerCase()
  if (!kw) return sessions.value
  return sessions.value.filter((item) =>
    [item.video_title || '', item.category || '', item.grade || '', statusText(item)]
      .join(' ')
      .toLowerCase()
      .includes(kw)
  )
})

// 服务端分页，pagedSessions 就是当前页数据
const pagedSessions = computed(() => filteredSessions.value)

async function fetchHistory() {
  loading.value = true
  try {
    const params: Record<string, string | number> = {
      page: currentPage.value,
      page_size: pageSize.value,
    }
    if (statusFilter.value !== 'all' && statusFilter.value !== 'retry') {
      params.status = statusFilter.value
    }
    if (modeFilter.value !== 'all') {
      params.mode = modeFilter.value
    }
    if (typeFilter.value !== 'all') {
      params.category = typeFilter.value
    }
    if (keyword.value.trim()) {
      params.keyword = keyword.value.trim()
    }
    if (dateRange.value.length === 2) {
      params.date_start = dateRange.value[0]
      params.date_end = dateRange.value[1]
    }

    const res = await request.get('/video-training/history', { params }) as any
    // 兼容旧格式（数组）和新格式（对象）
    if (Array.isArray(res)) {
      sessions.value = res
      totalCount.value = res.length
    } else {
      sessions.value = Array.isArray(res.items) ? res.items : []
      totalCount.value = res.total || 0
      if (res.available_categories?.length) {
        availableCategories.value = res.available_categories
      }
    }
  } catch {
    ElMessage.error('加载视频实训历史失败')
  } finally {
    loading.value = false
  }
}

function canViewReport(session: SessionItem): boolean {
  return session.status === 'finished' || Boolean(session.finished_at)
}

function handleRowClick(session: SessionItem) {
  if (!canViewReport(session)) return
  void handleAction('report', session)
}

async function handleAction(command: string, session: SessionItem) {
  closeFloatingMenus()
  if (command === 'report') {
    router.push(`/student/evaluation?session_id=${session.id}&type=video`)
    return
  }

  router.push(`/student/video-training/${session.video_id}`)
}

function toggleActionMenu(sessionId: number, event: MouseEvent) {
  showPageSizeMenu.value = false
  if (openActionMenuId.value === sessionId) {
    closeFloatingMenus()
    return
  }
  const rect = (event.currentTarget as HTMLElement).getBoundingClientRect()
  actionMenuPlacement.value = window.innerHeight - rect.bottom < 140 && rect.top > 140 ? 'up' : 'down'
  openActionMenuId.value = sessionId
}

function handleMenuAction(command: string, session: SessionItem) {
  void handleAction(command, session)
}

function togglePageSizeMenu() {
  openActionMenuId.value = null
  showPageSizeMenu.value = !showPageSizeMenu.value
}

function selectPageSize(size: number) {
  if (pageSize.value !== size) {
    pageSize.value = size
    currentPage.value = 1
    syncQueryParams()
    void fetchHistory()
  }
  showPageSizeMenu.value = false
}

function closeFloatingMenus() {
  openActionMenuId.value = null
  showPageSizeMenu.value = false
}

function calcProgress(session: SessionItem): number {
  if (!session.node_total) return 0
  if (session.status === 'finished') return 100
  return Math.min(100, Math.round((session.current_node_index / session.node_total) * 100))
}

function statusKey(session: SessionItem): 'done' | 'live' | 'retry' | 'abandoned' {
  if (session.needs_retry) return 'retry'
  if (session.status === 'finished') return 'done'
  if (session.status === 'abandoned') return 'abandoned'
  return 'live'
}

function statusText(session: SessionItem): string {
  const key = statusKey(session)
  if (key === 'done') return '已完成'
  if (key === 'retry') return '待重修'
  if (key === 'abandoned') return '已放弃'
  return '进行中'
}

function gradeKey(session: SessionItem): 'excellent' | 'pass' | 'fail' {
  const grade = session.grade
  if (grade === '优秀') return 'excellent'
  if (grade === '合格') return 'pass'
  return 'fail'
}

function scoreClass(session: SessionItem): string {
  const pct = session.score_percentage
  if (pct == null) return ''
  if (pct >= 90) return 'score-cell--excellent'
  if (pct >= 70) return 'score-cell--good'
  return 'score-cell--weak'
}

function durationText(session: SessionItem): string {
  if (session.duration_seconds) return formatDurationSeconds(session.duration_seconds)
  return '--'
}

function formatDurationSeconds(totalSeconds: number): string {
  const minutes = Math.floor(totalSeconds / 60)
  const seconds = totalSeconds % 60
  return `${String(minutes).padStart(2, '0')}'${String(seconds).padStart(2, '0')}"`
}

function formatDateTime(iso?: string): string {
  if (!iso) return '--'
  const d = new Date(iso)
  const date = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
  const time = `${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`
  return `${date} ${time}`
}

function resetPagination() {
  currentPage.value = 1
  syncQueryParams()
  void fetchHistory()
}

function resetFilters() {
  typeFilter.value = 'all'
  modeFilter.value = 'all'
  statusFilter.value = 'all'
  keyword.value = ''
  dateRange.value = []
  currentPage.value = 1
  syncQueryParams()
  // watch 会触发 fetchHistory，这里不重复调用
}

</script>

<style scoped lang="scss">
.training-history-page {
  display: flex;
  flex-direction: column;
  gap: 18px;
  padding: 18px 22px 24px;
  min-height: 100%;
  background: #f3f6fb;
}

.filter-panel,
.table-panel {
  background: rgba(255, 255, 255, 0.92);
  border: 1px solid rgba(214, 223, 237, 0.95);
  box-shadow: 0 18px 44px rgba(15, 23, 42, 0.06);
}

.filter-panel,
.table-panel {
  border-radius: 8px;
}

.filter-panel {
  padding: 16px 18px;
}

.filter-grid {
  display: grid;
  grid-template-columns: 170px 170px 170px minmax(280px, 1fr) minmax(260px, 320px) 100px;
  gap: 14px;
  align-items: end;
}

.filter-item {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.filter-item label {
  font-size: 14px;
  font-weight: 700;
  color: #334155;
}

.filter-item--action .reset-btn {
  height: 40px;
  border-radius: 10px;
}

.table-panel {
  overflow-x: auto;
  overflow-y: visible;
}

.history-table {
  min-width: 100%;
}

.history-table__head,
.history-row {
  display: grid;
  grid-template-columns: 52px minmax(180px, 1.4fr) minmax(120px, 1fr) 96px 88px 72px 96px 110px 80px 130px 132px;
  gap: 12px;
  align-items: center;
  justify-items: center;
  padding: 16px 18px;
  min-width: 1180px;
  overflow: visible;
}

.history-table__head {
  font-size: 14px;
  font-weight: 800;
  color: #334155;
  border-bottom: 1px solid #e8eef7;
  background: #f8fafc;
  text-align: center;
}

.history-row {
  position: relative;
  font-size: 14px;
  color: #334155;
  border-bottom: 1px solid #edf2f7;
  text-align: center;
}

.history-row--clickable {
  cursor: pointer;
}

.history-row--clickable:hover {
  background: #f8fbff;
}

.history-row--menu-open {
  z-index: 20;
}

.history-row:last-child {
  border-bottom: none;
}

.cell-center {
  text-align: center;
}

.history-row__title {
  font-size: 15px;
  font-weight: 700;
  color: #0f172a;
  text-align: center;
}

.history-row__sub,
.muted,
.progress-text {
  font-size: 12px;
  color: #94a3b8;
}

.history-row__sub {
  margin-top: 4px;
  text-align: center;
}

.history-row__scene,
.time-cell {
  font-size: 13px;
  color: #475569;
  text-align: center;
}

.mode-badge,
.status-badge,
.grade-badge {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 72px;
  padding: 4px 12px;
  font-size: 12px;
  font-weight: 700;
  border-radius: 999px;
}

.mode-badge--practice {
  color: #2563eb;
  background: #eff6ff;
}

.mode-badge--exam {
  color: #1d4ed8;
  background: #dbeafe;
}

.status-badge--done {
  color: #16a34a;
  background: #f0fdf4;
}

.status-badge--live {
  color: #2563eb;
  background: #eff6ff;
}

.status-badge--retry {
  color: #f97316;
  background: #fff7ed;
}

.status-badge--abandoned {
  color: #dc2626;
  background: #fff1f2;
}

.grade-badge--excellent {
  color: #16a34a;
  background: #ecfdf3;
}

.grade-badge--pass {
  color: #ea580c;
  background: #fff7ed;
}

.grade-badge--fail {
  color: #ef4444;
  background: #fff1f2;
}

.score-cell {
  font-size: 18px;
  font-weight: 800;
}

.score-cell--excellent {
  color: #16a34a;
}

.score-cell--good {
  color: #2563eb;
}

.score-cell--weak {
  color: #ef4444;
}

.progress-cell {
  text-align: center;
}

.mini-progress {
  width: 84px;
  height: 8px;
  margin: 0 auto 6px;
  overflow: hidden;
  border-radius: 999px;
  background: #e8eef8;
}

.mini-progress span {
  display: block;
  height: 100%;
  border-radius: 999px;
  background: #2563eb;
}

.action-cell {
  display: flex;
  align-items: center;
  justify-content: flex-start;
  gap: 8px;
  overflow: visible;
}

.action-cell--sticky {
  position: sticky;
  right: 0;
  z-index: 2;
  background: linear-gradient(90deg, rgba(255, 255, 255, 0) 0%, #fff 18%);
  padding-left: 12px;
}

.history-row--menu-open .action-cell--sticky {
  z-index: 30;
}

.history-table__head .action-cell--sticky {
  background: #f8fafc;
}

.grade-cell {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6px;
}

.report-link {
  border: none;
  background: none;
  padding: 0;
  color: #2f6df6;
  font-size: 13px;
  font-weight: 700;
  cursor: pointer;
  text-decoration: underline;
  text-underline-offset: 3px;
}

.report-link:hover {
  color: #1d4ed8;
}

.state-panel {
  padding: 56px 24px;
}

.more-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 34px;
  height: 34px;
  color: #334155;
  cursor: pointer;
  background: #fff;
  border: 1px solid #dbe4f0;
  border-radius: 10px;
}

.more-btn:hover,
.more-btn--open {
  color: #2563eb;
  border-color: #93c5fd;
  background: #eff6ff;
}

.more-menu {
  position: relative;
  display: inline-flex;
  justify-content: center;
}

.more-menu__panel {
  position: absolute;
  right: 0;
  z-index: 80;
  box-sizing: border-box;
  width: 118px;
  padding: 8px;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  background: #fff;
  box-shadow: 0 18px 42px rgba(15, 23, 42, 0.16);
}

.more-menu__panel--down {
  top: calc(100% + 8px);
}

.more-menu__panel--up {
  bottom: calc(100% + 8px);
}

.more-menu__panel--down::before,
.more-menu__panel--up::after {
  content: '';
  position: absolute;
  right: 12px;
  width: 9px;
  height: 9px;
  background: #fff;
}

.more-menu__panel--down::before {
  top: -5px;
  border-top: 1px solid #e5e7eb;
  border-left: 1px solid #e5e7eb;
  transform: rotate(45deg);
}

.more-menu__panel--up::after {
  bottom: -5px;
  border-right: 1px solid #e5e7eb;
  border-bottom: 1px solid #e5e7eb;
  transform: rotate(45deg);
}

.more-menu__item {
  display: flex;
  width: 100%;
  min-height: 34px;
  align-items: center;
  justify-content: flex-start;
  padding: 7px 10px;
  border: 0;
  border-radius: 6px;
  background: transparent;
  color: #334155;
  font-size: 14px;
  font-weight: 700;
  line-height: 1.3;
  cursor: pointer;
  white-space: nowrap;
}

.more-menu__item:hover {
  background: #eff6ff;
  color: #1d4ed8;
}

.table-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 18px;
  border-top: 1px solid #edf2f7;
}

.table-footer__count {
  font-size: 14px;
  color: #64748b;
}

.pager-controls {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 12px;
  min-width: 0;
}

.page-size-menu {
  position: relative;
  display: inline-flex;
  justify-content: center;
}

.page-size-menu__trigger {
  display: inline-flex;
  width: 128px;
  height: 40px;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  padding: 0 14px;
  border: 1px solid #1d4ed8;
  border-radius: 6px;
  background: #fff;
  color: #64748b;
  font-size: 15px;
  cursor: pointer;
}

.page-size-menu__trigger[aria-expanded='true'] {
  color: #1d4ed8;
  box-shadow: 0 0 0 2px rgba(29, 78, 216, 0.08);
}

.page-size-menu__panel {
  position: absolute;
  z-index: 60;
  bottom: calc(100% + 8px);
  left: 50%;
  width: 118px;
  padding: 8px 0;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  background: #fff;
  box-shadow: 0 18px 42px rgba(15, 23, 42, 0.16);
  transform: translateX(-50%);
}

.page-size-menu__panel::after {
  content: '';
  position: absolute;
  bottom: -5px;
  left: calc(50% - 5px);
  width: 10px;
  height: 10px;
  border-right: 1px solid #e5e7eb;
  border-bottom: 1px solid #e5e7eb;
  background: #fff;
  transform: rotate(45deg);
}

.page-size-menu__item {
  display: flex;
  width: 100%;
  height: 36px;
  align-items: center;
  justify-content: center;
  border: 0;
  background: transparent;
  color: #64748b;
  font-size: 15px;
  cursor: pointer;
}

.page-size-menu__item:hover,
.page-size-menu__item--active {
  background: #eff6ff;
  color: #2563eb;
}

@media (max-width: 1280px) {
  .filter-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .history-table {
    overflow-x: auto;
  }

  .history-table__head,
  .history-row {
    min-width: 1180px;
  }
}

@media (max-width: 900px) {
  .training-history-page {
    padding: 14px;
  }

  .filter-grid {
    grid-template-columns: 1fr;
  }

  .table-footer {
    flex-direction: column;
    align-items: center;
  }

  .pager-controls {
    flex-wrap: wrap;
  }
}
</style>
