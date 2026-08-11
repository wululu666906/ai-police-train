<template>
  <div class="student-page practice-history-page">
    <section class="history-panel">
      <div class="history-toolbar">
        <div class="history-tabs" role="tablist" aria-label="记录类型">
          <button
            v-for="tab in historyTabs"
            :key="tab.value"
            type="button"
            role="tab"
            :aria-selected="activeTab === tab.value"
            :class="{ 'history-tab--active': activeTab === tab.value }"
            class="history-tab"
            @click="activeTab = tab.value"
          >
            {{ tab.label }}
            <span>{{ tab.count }}</span>
          </button>
        </div>
        <div class="history-filters">
          <el-input v-model="keyword" clearable placeholder="搜索训练名称、场景" :prefix-icon="Search" />
          <el-date-picker
            v-model="dateRange"
            type="daterange"
            value-format="YYYY-MM-DD"
            range-separator="-"
            start-placeholder="开始日期"
            end-placeholder="结束日期"
          />
          <el-button text @click="resetFilters">
            <el-icon><Refresh /></el-icon>
            重置
          </el-button>
        </div>
      </div>

      <div v-if="loading" class="state-panel">
        <el-skeleton :rows="8" animated />
      </div>
      <div v-else-if="filteredRecords.length === 0" class="state-panel">
        <el-empty description="暂无符合条件的练习记录">
          <el-button type="primary" @click="router.push('/student/home')">去开始训练</el-button>
        </el-empty>
      </div>
      <div v-else class="history-table-wrap">
        <div class="history-table">
          <div class="history-table__head">
            <span>训练内容</span>
            <span>类型</span>
            <span>状态</span>
            <span>进度</span>
            <span>成绩</span>
            <span>时间</span>
            <span class="col-actions">操作</span>
          </div>
          <article
            v-for="record in filteredRecords"
            :key="record.key"
            class="history-row"
            :class="{ 'history-row--menu-open': openMenuKey === record.key }"
          >
            <div class="record-title">
              <strong>{{ record.title }}</strong>
              <small>{{ record.category }} · {{ record.subtitle }}</small>
            </div>
            <div>
              <span class="type-tag" :class="`type-tag--${record.kind}`">{{ record.kind === 'text' ? '文字训练' : '视频实训' }}</span>
            </div>
            <div>
              <span class="status-tag" :class="`status-tag--${record.status}`">{{ record.statusLabel }}</span>
            </div>
            <div class="record-progress">
              <el-progress :percentage="record.progress" :show-text="false" :stroke-width="6" />
              <small>{{ record.progressLabel }}</small>
            </div>
            <div class="record-score" :class="scoreClass(record.score)">
              {{ record.score == null ? '--' : record.score }}
            </div>
            <div class="record-time">
              <strong>{{ formatTime(record.time) }}</strong>
              <small>{{ record.kind === 'text' ? '对话训练' : '节点训练' }}</small>
            </div>
            <div class="record-actions" @click.stop>
              <el-button v-if="record.status === 'active'" type="primary" size="small" @click="continueRecord(record)">继续</el-button>
              <el-button v-else-if="record.status === 'finished'" type="primary" plain size="small" @click="viewReport(record)">查看报告</el-button>
              <el-button v-else type="warning" plain size="small" @click="continueRecord(record)">重新训练</el-button>
              <div class="more-menu">
                <button
                  type="button"
                  class="more-btn"
                  :class="{ 'more-btn--open': openMenuKey === record.key }"
                  title="更多操作"
                  :aria-expanded="openMenuKey === record.key"
                  aria-haspopup="menu"
                  @click="toggleMoreMenu(record, $event)"
                >
                  <el-icon><MoreFilled /></el-icon>
                </button>
                <div
                  v-if="openMenuKey === record.key"
                  class="more-menu__panel"
                  :class="`more-menu__panel--${menuPlacement}`"
                  role="menu"
                  @click.stop
                >
                  <button
                    v-if="record.kind === 'text'"
                    type="button"
                    class="more-menu__item"
                    role="menuitem"
                    @click="handleCommand('dialogue', record)"
                  >
                    查看对话
                  </button>
                  <button
                    v-if="record.status === 'finished'"
                    type="button"
                    class="more-menu__item"
                    role="menuitem"
                    @click="handleCommand('report', record)"
                  >
                    查看报告
                  </button>
                  <button
                    type="button"
                    class="more-menu__item"
                    role="menuitem"
                    @click="handleCommand('continue', record)"
                  >
                    {{ record.status === 'active' ? '继续训练' : '重新训练' }}
                  </button>
                  <button
                    v-if="record.kind === 'text'"
                    type="button"
                    class="more-menu__item more-menu__item--danger"
                    role="menuitem"
                    @click="handleCommand('delete', record)"
                  >
                    删除记录
                  </button>
                </div>
              </div>
            </div>
          </article>
        </div>
      </div>

      <div v-if="filteredRecords.length" class="history-footer">
        <span>共 {{ filteredTotal }} 条记录</span>
        <el-pagination
          v-model:current-page="currentPage"
          v-model:page-size="pageSize"
          background
          layout="prev, pager, next"
          :page-sizes="[10, 20, 50]"
          :total="filteredTotal"
        />
      </div>
    </section>
  </div>
</template>

<script setup lang="ts">
import { computed, inject, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { showConfirmDialog, showToast } from 'vant'
import { MoreFilled, Refresh, Search } from '@element-plus/icons-vue'
import request from '../utils/request'

interface UnifiedRecord {
  key: string
  id: number
  kind: 'text' | 'video'
  title: string
  category: string
  subtitle: string
  status: 'active' | 'finished' | 'retry' | 'abandoned'
  statusLabel: string
  progress: number
  progressLabel: string
  score: number | null
  time?: string
  raw: any
}

const router = useRouter()
const route = useRoute()
const setMainScrollable = inject<(value: boolean) => void>('setMainScrollable')

const loading = ref(true)
const records = ref<UnifiedRecord[]>([])
const keyword = ref('')
const dateRange = ref<[string, string] | []>([])
const currentPage = ref(1)
const pageSize = ref(10)
const openMenuKey = ref<string | null>(null)
const menuPlacement = ref<'down' | 'up'>('down')
const activeTab = ref<'all' | 'text' | 'video' | 'abandoned'>(
  route.query.tab === 'video' ? 'video' : route.query.tab === 'abandoned' ? 'abandoned' : 'all',
)

const historyTabs = computed(() => [
  { value: 'all' as const, label: '全部记录', count: records.value.length },
  { value: 'text' as const, label: '普通训练', count: records.value.filter((item) => item.kind === 'text').length },
  { value: 'video' as const, label: '视频实训', count: records.value.filter((item) => item.kind === 'video').length },
  { value: 'abandoned' as const, label: '已放弃', count: records.value.filter((item) => item.status === 'abandoned').length },
])

const filteredRecords = computed(() => {
  const text = keyword.value.trim().toLowerCase()
  const start = dateRange.value[0] || ''
  const end = dateRange.value[1] || ''
  const result = records.value.filter((record) => {
    const matchesTab =
      activeTab.value === 'all' ||
      (activeTab.value === 'text' && record.kind === 'text') ||
      (activeTab.value === 'video' && record.kind === 'video') ||
      (activeTab.value === 'abandoned' && record.status === 'abandoned')
    const matchesKeyword = !text || [record.title, record.category, record.subtitle, record.statusLabel].join(' ').toLowerCase().includes(text)
    const day = String(record.time || '').slice(0, 10)
    const matchesDate = !start || !end || (day >= start && day <= end)
    return matchesTab && matchesKeyword && matchesDate
  })
  const startIndex = (currentPage.value - 1) * pageSize.value
  return result.slice(startIndex, startIndex + pageSize.value)
})

const filteredTotal = computed(() => {
  const current = activeTab.value
  return records.value.filter((record) => {
    if (current === 'text') return record.kind === 'text'
    if (current === 'video') return record.kind === 'video'
    if (current === 'abandoned') return record.status === 'abandoned'
    return true
  }).filter((record) => {
    const text = keyword.value.trim().toLowerCase()
    const day = String(record.time || '').slice(0, 10)
    return (!text || [record.title, record.category, record.subtitle, record.statusLabel].join(' ').toLowerCase().includes(text))
      && (!dateRange.value[0] || !dateRange.value[1] || (day >= dateRange.value[0] && day <= dateRange.value[1]))
  }).length
})

watch([activeTab, keyword, dateRange], () => {
  currentPage.value = 1
  closeMoreMenu()
})

watch(currentPage, () => {
  closeMoreMenu()
})

function closeMoreMenu() {
  openMenuKey.value = null
}

function resolveMenuPlacement(trigger: HTMLElement) {
  const rect = trigger.getBoundingClientRect()
  const spaceBelow = window.innerHeight - rect.bottom
  menuPlacement.value = spaceBelow < 180 && rect.top > 180 ? 'up' : 'down'
}

function toggleMoreMenu(record: UnifiedRecord, event: MouseEvent) {
  if (openMenuKey.value === record.key) {
    closeMoreMenu()
    return
  }
  resolveMenuPlacement(event.currentTarget as HTMLElement)
  openMenuKey.value = record.key
}

function onDocumentPointerDown(event: MouseEvent) {
  const target = event.target as HTMLElement | null
  if (!target) return
  if (target.closest('.more-menu')) return
  closeMoreMenu()
}

function onViewportChange() {
  if (!openMenuKey.value) return
  closeMoreMenu()
}

async function fetchHistory() {
  loading.value = true
  try {
    const [textRes, videoRes] = await Promise.all([
      request.get('/student/history', { params: { page: 1, page_size: 200, include_empty: false }, _skipErrorToast: true } as any),
      request.get('/video-training/history', { params: { page: 1, page_size: 200 }, _skipErrorToast: true } as any),
    ])
    const textData: any = textRes
    const videoData: any = videoRes
    const textItems = Array.isArray(textData?.items) ? textData.items : Array.isArray(textData) ? textData : []
    const videoItems = Array.isArray(videoData?.items) ? videoData.items : Array.isArray(videoData) ? videoData : []
    records.value = [
      ...textItems.map(normalizeTextRecord),
      ...videoItems.map(normalizeVideoRecord),
    ].sort((a, b) => String(b.time || '').localeCompare(String(a.time || '')))
  } catch {
    records.value = []
    ElMessage.error('练习记录加载失败，请稍后重试')
  } finally {
    loading.value = false
  }
}

function normalizeTextRecord(item: any): UnifiedRecord {
  const status = item.status === 'finished' ? 'finished' : item.status === 'abandoned' ? 'abandoned' : 'active'
  return {
    key: `text-${item.id}`,
    id: Number(item.id),
    kind: 'text',
    title: item.case_title || '未命名案件',
    category: item.case_type || '普通训练',
    subtitle: item.scene_name || '综合场景',
    status,
    statusLabel: status === 'finished' ? '已完成' : status === 'abandoned' ? '已放弃' : '进行中',
    progress: status === 'finished' ? 100 : item.turn_count ? Math.min(95, Number(item.turn_count) * 5) : 0,
    progressLabel: item.turn_count ? `${item.turn_count} 轮对话` : '尚未开始',
    score: item.total_score == null ? null : Number(item.total_score),
    time: item.created_at,
    raw: item,
  }
}

function normalizeVideoRecord(item: any): UnifiedRecord {
  const status = item.needs_retry ? 'retry' : item.status === 'finished' ? 'finished' : item.status === 'abandoned' ? 'abandoned' : 'active'
  const current = Number(item.current_node_index || 0)
  const total = Number(item.node_total || 0)
  return {
    key: `video-${item.id}`,
    id: Number(item.id),
    kind: 'video',
    title: item.video_title || '未命名视频',
    category: item.category || '视频实训',
    subtitle: item.mode === 'exam' ? '正式考核' : '练习模式',
    status,
    statusLabel: status === 'finished' ? '已完成' : status === 'retry' ? '待重修' : status === 'abandoned' ? '已放弃' : '进行中',
    progress: status === 'finished' ? 100 : total ? Math.min(100, Math.round((current / total) * 100)) : 0,
    progressLabel: `${current}/${total} 节点`,
    score: item.score_percentage == null ? null : Number(Number(item.score_percentage).toFixed(1)),
    time: item.finished_at || item.created_at,
    raw: item,
  }
}

function continueRecord(record: UnifiedRecord) {
  if (record.kind === 'video') router.push(`/student/video-training/${record.raw.video_id}`)
  else router.push(`/student/training/${record.id}`)
}

function viewReport(record: UnifiedRecord) {
  router.push(`/student/evaluation?session_id=${record.id}${record.kind === 'video' ? '&type=video' : ''}`)
}

async function handleCommand(command: string, record: UnifiedRecord) {
  closeMoreMenu()
  if (command === 'report') {
    viewReport(record)
    return
  }
  if (command === 'continue') {
    continueRecord(record)
    return
  }
  if (command === 'dialogue') {
    router.push(`/student/history/${record.id}/dialogue`)
    return
  }
  if (command === 'delete') {
    try {
      await showConfirmDialog({
        title: '删除练习记录',
        message: '删除后将无法恢复这条训练会话和评估结果，是否继续？',
        confirmButtonColor: '#dc2626',
      })
      await request.delete(`/training/session/${record.id}`, { _skipErrorToast: true } as any)
      showToast({ type: 'success', message: '记录已删除' })
      await fetchHistory()
    } catch {
      // 用户取消或删除失败时保持当前列表
    }
  }
}

function scoreClass(score: number | null) {
  if (score == null) return ''
  if (score >= 85) return 'record-score--excellent'
  if (score >= 70) return 'record-score--good'
  return 'record-score--weak'
}

function formatTime(value?: string) {
  if (!value) return '--'
  const date = new Date(value)
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')} ${String(date.getHours()).padStart(2, '0')}:${String(date.getMinutes()).padStart(2, '0')}`
}

function resetFilters() {
  keyword.value = ''
  dateRange.value = []
  activeTab.value = 'all'
}

onMounted(() => {
  setMainScrollable?.(true)
  fetchHistory()
  document.addEventListener('pointerdown', onDocumentPointerDown)
  window.addEventListener('resize', onViewportChange)
  document.querySelector('.student-main')?.addEventListener('scroll', onViewportChange, { passive: true })
})

onBeforeUnmount(() => {
  document.removeEventListener('pointerdown', onDocumentPointerDown)
  window.removeEventListener('resize', onViewportChange)
  document.querySelector('.student-main')?.removeEventListener('scroll', onViewportChange)
  closeMoreMenu()
})
</script>

<style scoped lang="scss">
.practice-history-page {
  min-height: 100%;
  padding: 22px;
  color: #17213b;
  background: #f3f6fa;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.history-panel {
  overflow: visible;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  background: #fff;
  box-shadow: 0 4px 16px rgba(35, 56, 104, 0.06);
}

.history-toolbar {
  flex-wrap: wrap;
  padding: 13px 16px 0;
  border-bottom: 1px solid #edf1f6;
}

.history-tabs {
  gap: 3px;
}

.history-tab {
  min-height: 42px;
  padding: 0 12px;
  border: 0;
  border-bottom: 2px solid transparent;
  background: transparent;
  color: #7c8798;
  font-size: 13px;
  font-weight: 700;
  cursor: pointer;
}

.history-tab span {
  margin-left: 4px;
  color: #a0aaba;
  font-size: 11px;
  font-weight: 500;
}

.history-tab--active {
  border-bottom-color: #3566f6;
  color: #3566f6;
}

.history-filters {
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: 8px;
  padding-bottom: 10px;
}

.history-filters :deep(.el-input) {
  width: 210px;
}

.history-filters :deep(.el-date-editor) {
  width: 250px;
}

.history-table-wrap {
  overflow: visible;
}

.history-table {
  width: 100%;
  min-width: 0;
}

.history-table__head,
.history-row {
  display: grid;
  grid-template-columns: minmax(180px, 1.45fr) 96px 88px 140px 72px 148px minmax(168px, 188px);
  align-items: center;
  gap: 12px;
  padding: 14px 16px;
}

.history-table__head {
  color: #657187;
  background: #fafbfd;
  border-bottom: 1px solid #e8edf4;
  font-size: 12px;
  font-weight: 800;
}

.col-actions,
.record-actions {
  justify-self: start;
  text-align: left;
}

.history-row {
  position: relative;
  min-height: 78px;
  color: #334155;
  border-bottom: 1px solid #edf1f6;
  font-size: 12px;
  overflow: visible;
}

.history-row:last-child {
  border-bottom: 0;
}

.history-row:hover {
  background: #fbfcff;
}

.history-row--menu-open {
  z-index: 20;
  background: #fbfcff;
}

.record-title,
.record-time {
  display: flex;
  flex-direction: column;
  gap: 5px;
  min-width: 0;
}

.record-title strong {
  overflow: hidden;
  color: #253047;
  font-size: 13px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.record-title small,
.record-time small,
.record-progress small {
  color: #9aa5b6;
  font-size: 11px;
}

.type-tag,
.status-tag {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 66px;
  padding: 4px 7px;
  border-radius: 4px;
  font-size: 11px;
}

.type-tag--text {
  background: #eef3ff;
  color: #3566f6;
}

.type-tag--video {
  background: #eaf8f0;
  color: #16a36a;
}

.status-tag--active {
  background: #fff3e4;
  color: #d97816;
}

.status-tag--finished {
  background: #eaf8f0;
  color: #16a36a;
}

.status-tag--retry {
  background: #fff7e8;
  color: #c87916;
}

.status-tag--abandoned {
  background: #fff0f0;
  color: #d64c4c;
}

.record-progress {
  width: 130px;
}

.record-progress :deep(.el-progress) {
  margin-bottom: 5px;
}

.record-score {
  font-size: 18px;
  font-weight: 800;
}

.record-score--excellent { color: #16a36a; }
.record-score--good { color: #3566f6; }
.record-score--weak { color: #d64c4c; }

.record-time strong {
  color: #475569;
  font-size: 12px;
  font-weight: 600;
}

.record-actions {
  display: inline-flex;
  align-items: center;
  justify-content: flex-start;
  gap: 8px;
  width: auto;
  max-width: 100%;
}

.more-menu {
  position: relative;
  flex: 0 0 auto;
  z-index: 1;
}

.more-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  padding: 0;
  border: 1px solid #dbe4f0;
  border-radius: 999px;
  background: #fff;
  color: #64748b;
  cursor: pointer;
  transition: border-color 0.15s ease, color 0.15s ease, background 0.15s ease;
}

.more-btn:hover,
.more-btn--open {
  color: #2563eb;
  border-color: #93c5fd;
  background: #eff6ff;
}

.more-menu__panel {
  position: absolute;
  right: 0;
  z-index: 30;
  box-sizing: border-box;
  width: 132px;
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
  right: 10px;
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
  font-size: 13px;
  font-weight: 700;
  line-height: 1.3;
  cursor: pointer;
  white-space: nowrap;
}

.more-menu__item:hover {
  background: #eff6ff;
  color: #2563eb;
}

.more-menu__item--danger {
  margin-top: 4px;
  border-top: 1px solid #e5e7eb;
  border-radius: 0 0 6px 6px;
  color: #dc2626;
}

.more-menu__item--danger:hover {
  background: #fff1f2;
  color: #b91c1c;
}

.history-footer {
  padding: 14px 16px;
  color: #8b96aa;
  font-size: 12px;
}

.state-panel {
  padding: 54px 24px;
}

@media (max-width: 1100px) {
  .history-table-wrap {
    overflow-x: auto;
  }

  .history-table {
    min-width: 980px;
  }
}

@media (max-width: 960px) {
  .practice-history-page {
    padding: 14px;
  }
}

@media (max-width: 620px) {
  .history-toolbar {
    align-items: stretch;
    flex-direction: column;
  }

  .history-tabs {
    overflow-x: auto;
  }

  .history-filters {
    justify-content: flex-start;
  }

  .history-filters :deep(.el-input),
  .history-filters :deep(.el-date-editor) {
    width: 100%;
  }

  .history-footer {
    align-items: flex-start;
    flex-direction: column;
  }
}
</style>
