<template>
  <div class="admin-text-sessions">
    <section class="admin-filter-panel">
      <div class="admin-filter-bar">
        <label class="admin-filter-item">
          <span>完成状态</span>
          <el-select v-model="filterStatus" clearable placeholder="全部状态" style="width:130px" @change="onFilterChange">
            <el-option label="进行中" value="active" />
            <el-option label="评估中" value="evaluating" />
            <el-option label="已完成" value="finished" />
          </el-select>
        </label>
        <label class="admin-filter-item">
          <span>学员账号</span>
          <el-input
            v-model="filterUsername"
            placeholder="输入账号搜索"
            clearable
            style="width:160px"
            @change="onFilterChange"
          />
        </label>
        <label class="admin-filter-item">
          <span>训练内容</span>
          <el-input
            v-model="filterKeyword"
            clearable
            placeholder="搜索训练名称、场景"
            :prefix-icon="Search"
            style="width:210px"
            @change="onFilterChange"
          />
        </label>
        <label class="admin-filter-item">
          <span>时间范围</span>
          <el-date-picker
            v-model="dateRange"
            type="daterange"
            value-format="YYYY-MM-DD"
            range-separator="-"
            start-placeholder="开始日期"
            end-placeholder="结束日期"
            @change="onFilterChange"
          />
        </label>
        <el-button text @click="resetFilters">
          <el-icon><Refresh /></el-icon>
          重置
        </el-button>
      </div>
    </section>

    <section class="history-panel">
      <div v-if="loading" class="state-panel">
        <el-skeleton :rows="8" animated />
      </div>
      <div v-else-if="records.length === 0" class="state-panel">
        <el-empty description="暂无符合条件的普通训练记录" />
      </div>
      <div v-else class="history-table-wrap">
        <div class="history-table">
          <div class="history-table__head">
            <span>学员</span>
            <span>训练内容</span>
            <span>类型</span>
            <span>状态</span>
            <span>进度</span>
            <span>成绩</span>
            <span>时间</span>
            <span class="col-actions">操作</span>
          </div>
          <article
            v-for="record in records"
            :key="record.key"
            class="history-row"
            :class="{ 'history-row--menu-open': openMenuKey === record.key }"
          >
            <div class="record-student">
              <strong>{{ record.username }}</strong>
              <small>ID {{ record.userId }}</small>
            </div>
            <div class="record-title">
              <strong>{{ record.title }}</strong>
              <small>{{ record.category }} · {{ record.subtitle }}</small>
            </div>
            <div>
              <span class="type-tag type-tag--text">文字训练</span>
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
              <small>对话训练</small>
            </div>
            <div class="record-actions" @click.stop>
              <el-button
                v-if="record.status === 'finished'"
                type="primary"
                plain
                size="small"
                @click="viewReport(record)"
              >
                查看报告
              </el-button>
              <el-button
                v-else
                type="primary"
                plain
                size="small"
                @click="viewDialogue(record)"
              >
                查看对话
              </el-button>
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
                  <button type="button" class="more-menu__item" role="menuitem" @click="handleCommand('dialogue', record)">
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
                </div>
              </div>
            </div>
          </article>
        </div>
      </div>

      <div v-if="records.length" class="history-footer">
        <span>共 {{ total }} 条记录</span>
        <el-pagination
          v-model:current-page="page"
          :page-size="pageSize"
          background
          layout="prev, pager, next"
          :total="total"
          @current-change="fetchSessions"
        />
      </div>
    </section>
  </div>
</template>

<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { MoreFilled, Refresh, Search } from '@element-plus/icons-vue'
import request from '../utils/request'

interface AdminTextRecord {
  key: string
  id: number
  userId: number
  username: string
  title: string
  category: string
  subtitle: string
  status: 'active' | 'evaluating' | 'finished'
  statusLabel: string
  progress: number
  progressLabel: string
  score: number | null
  time?: string
}

const router = useRouter()
const loading = ref(false)
const records = ref<AdminTextRecord[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const filterStatus = ref('')
const filterUsername = ref('')
const filterKeyword = ref('')
const dateRange = ref<[string, string] | []>([])
const openMenuKey = ref<string | null>(null)
const menuPlacement = ref<'down' | 'up'>('down')

const statusLabelOf = (status: string) => {
  if (status === 'finished') return '已完成'
  if (status === 'evaluating') return '评估中'
  return '进行中'
}

const scoreClass = (score: number | null) => {
  if (score == null) return ''
  if (score >= 85) return 'record-score--excellent'
  if (score >= 60) return 'record-score--good'
  return 'record-score--weak'
}

const formatTime = (value?: string) => {
  if (!value) return '--'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  const y = date.getFullYear()
  const m = String(date.getMonth() + 1).padStart(2, '0')
  const d = String(date.getDate()).padStart(2, '0')
  const hh = String(date.getHours()).padStart(2, '0')
  const mm = String(date.getMinutes()).padStart(2, '0')
  return `${y}-${m}-${d} ${hh}:${mm}`
}

const normalizeRecord = (item: any): AdminTextRecord => {
  const status = item.status === 'finished' ? 'finished' : item.status === 'evaluating' ? 'evaluating' : 'active'
  const turns = Number(item.user_message_count || item.turn_count || 0)
  return {
    key: `text-${item.id}`,
    id: Number(item.id),
    userId: Number(item.user_id),
    username: item.username || '未知学员',
    title: item.case_title || '未命名案件',
    category: item.case_type || '普通训练',
    subtitle: item.scene_name || '综合场景',
    status,
    statusLabel: statusLabelOf(status),
    progress: status === 'finished' ? 100 : turns ? Math.min(95, turns * 5) : 0,
    progressLabel: turns ? `${turns} 轮对话` : '尚未开始',
    score: item.total_score == null ? null : Number(item.total_score),
    time: item.display_time || item.created_at,
  }
}

const closeMoreMenu = () => {
  openMenuKey.value = null
}

const resolveMenuPlacement = (el: HTMLElement | null) => {
  if (!el) {
    menuPlacement.value = 'down'
    return
  }
  const rect = el.getBoundingClientRect()
  const spaceBelow = window.innerHeight - rect.bottom
  menuPlacement.value = spaceBelow < 180 && rect.top > 180 ? 'up' : 'down'
}

const toggleMoreMenu = (record: AdminTextRecord, event: MouseEvent) => {
  if (openMenuKey.value === record.key) {
    closeMoreMenu()
    return
  }
  resolveMenuPlacement(event.currentTarget as HTMLElement)
  openMenuKey.value = record.key
}

const onDocumentPointerDown = (event: MouseEvent) => {
  const target = event.target as HTMLElement | null
  if (!target?.closest('.more-menu')) closeMoreMenu()
}

const onFilterChange = () => {
  page.value = 1
  fetchSessions()
}

const resetFilters = () => {
  filterStatus.value = ''
  filterUsername.value = ''
  filterKeyword.value = ''
  dateRange.value = []
  page.value = 1
  fetchSessions()
}

const fetchSessions = async () => {
  loading.value = true
  closeMoreMenu()
  try {
    const params: Record<string, string | number> = {
      page: page.value,
      page_size: pageSize.value,
    }
    if (filterStatus.value) params.status = filterStatus.value
    if (filterUsername.value.trim()) params.username = filterUsername.value.trim()
    if (filterKeyword.value.trim()) params.keyword = filterKeyword.value.trim()
    if (Array.isArray(dateRange.value) && dateRange.value.length === 2) {
      params.start_date = dateRange.value[0]
      params.end_date = dateRange.value[1]
    }

    const res: any = await request.get('/training/admin/sessions', { params })
    const items = Array.isArray(res?.items) ? res.items : []
    records.value = items.map(normalizeRecord)
    total.value = Number(res?.total || 0)
  } catch (error: any) {
    records.value = []
    total.value = 0
    ElMessage.error(error?.response?.data?.detail || '普通训练记录加载失败')
  } finally {
    loading.value = false
  }
}

const viewReport = (record: AdminTextRecord) => {
  closeMoreMenu()
  router.push(`/admin/text-sessions/${record.id}/report`)
}

const viewDialogue = (record: AdminTextRecord) => {
  closeMoreMenu()
  router.push(`/admin/text-sessions/${record.id}/dialogue`)
}

const handleCommand = (command: string, record: AdminTextRecord) => {
  if (command === 'report') viewReport(record)
  else if (command === 'dialogue') viewDialogue(record)
}

onMounted(() => {
  fetchSessions()
  document.addEventListener('pointerdown', onDocumentPointerDown)
})

onBeforeUnmount(() => {
  document.removeEventListener('pointerdown', onDocumentPointerDown)
  closeMoreMenu()
})
</script>

<style scoped lang="scss">
.admin-text-sessions {
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

.state-panel {
  padding: 48px 16px;
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
  grid-template-columns: 110px minmax(180px, 1.45fr) 96px 88px 140px 72px 148px minmax(168px, 188px);
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

.history-row:hover,
.history-row--menu-open {
  background: #fbfcff;
}

.history-row--menu-open {
  z-index: 20;
}

.record-student,
.record-title,
.record-time {
  display: flex;
  flex-direction: column;
  gap: 5px;
  min-width: 0;
}

.record-student strong,
.record-title strong {
  overflow: hidden;
  color: #253047;
  font-size: 13px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.record-student small,
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

.status-tag--active,
.status-tag--evaluating {
  background: #fff3e4;
  color: #d97816;
}

.status-tag--finished {
  background: #eaf8f0;
  color: #16a36a;
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
  top: calc(100% + 6px);
}

.more-menu__panel--up {
  bottom: calc(100% + 6px);
}

.more-menu__item {
  display: block;
  width: 100%;
  padding: 8px 10px;
  border: 0;
  border-radius: 6px;
  background: transparent;
  color: #334155;
  font-size: 12px;
  text-align: left;
  cursor: pointer;
}

.more-menu__item:hover {
  background: #eff6ff;
  color: #2563eb;
}

.history-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 12px 16px 16px;
  border-top: 1px solid #edf1f6;
  color: #64748b;
  font-size: 12px;
}

@media (max-width: 1200px) {
  .history-table__head,
  .history-row {
    grid-template-columns: 100px minmax(160px, 1.2fr) 88px 80px 120px 64px 130px minmax(150px, 170px);
  }
}
</style>
