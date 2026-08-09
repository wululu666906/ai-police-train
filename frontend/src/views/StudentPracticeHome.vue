<template>
  <div class="student-page practice-home-page">
    <section class="home-hero">
      <div class="home-hero__content">
        <span class="home-hero__eyebrow">训练工作台</span>
        <h1>警情处置模拟训练</h1>
        <p>围绕案件脚本、现场角色和处置阶段展开 AI 对话训练，支持快速进入任务、查看班级与历史记录。</p>
        <div class="home-hero__chips">
          <span>AI 对话</span>
          <span>多角色协同</span>
          <span>处置复盘</span>
        </div>
      </div>
      <div class="home-hero__metrics">
        <div
          v-for="(metric, index) in heroMetrics"
          :key="metric.label"
          class="home-metric"
          :class="{ 'home-metric--primary': index === 0 }"
        >
          <span class="home-metric__label">{{ metric.label }}</span>
          <strong>{{ metric.value }}</strong>
        </div>
      </div>
    </section>

    <div class="home-layout">
      <section class="home-panel schedule-panel">
        <div class="panel-heading">
          <div>
            <h2>今日安排</h2>
            <p>{{ selectedDateLabel }}</p>
          </div>
          <el-button text type="primary" @click="openTrainingCenter('tasks')">
            前往训练中心
            <el-icon><ArrowRight /></el-icon>
          </el-button>
        </div>

        <div class="week-row">
          <button
            v-for="day in weekDays"
            :key="day.key"
            type="button"
            class="day-chip"
            :class="{ 'day-chip--active': day.active }"
            @click="selectScheduleDate(day.key)"
          >
            <span>{{ day.label }}</span>
            <b>{{ day.date }}</b>
          </button>
        </div>

        <div v-if="loading" class="schedule-item schedule-item--muted">
          <div class="schedule-icon"><el-icon><Clock /></el-icon></div>
          <div class="schedule-copy">
            <strong>正在加载今日安排</strong>
            <span>正在读取班级作业、文字训练和视频实训数据</span>
          </div>
        </div>

        <div v-else-if="scheduleEntries.length" class="schedule-list">
          <div
            v-for="item in scheduleEntries"
            :key="item.key"
            class="schedule-item"
            :class="`schedule-item--${item.tone}`"
          >
            <div class="schedule-icon"><el-icon><Clock /></el-icon></div>
            <div class="schedule-copy">
              <strong>{{ item.title }}</strong>
              <span>{{ item.meta }}</span>
            </div>
            <el-button type="primary" plain size="small" @click="handleScheduleAction(item)">
              {{ item.action }}
            </el-button>
          </div>
        </div>

        <div v-else class="schedule-item schedule-item--muted">
          <div class="schedule-icon"><el-icon><Clock /></el-icon></div>
          <div class="schedule-copy">
            <strong>{{ emptyScheduleTitle }}</strong>
            <span>{{ emptyScheduleDescription }}</span>
          </div>
          <el-button type="primary" plain size="small" @click="openTrainingCenter('tasks')">
            去训练中心
          </el-button>
        </div>
      </section>

      <section class="home-panel quick-panel">
        <div class="panel-heading">
          <div>
            <h2>快捷入口</h2>
          </div>
        </div>
        <div class="quick-grid">
          <button v-for="item in quickEntries" :key="item.label" type="button" class="quick-item" @click="item.action">
            <span class="quick-icon" :class="`quick-icon--${item.tone}`">
              <el-icon><component :is="item.icon" /></el-icon>
            </span>
            <span class="quick-copy">
              <strong>{{ item.label }}</strong>
              <small>{{ item.description }}</small>
            </span>
            <el-icon class="quick-arrow"><ArrowRight /></el-icon>
          </button>
        </div>
      </section>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, inject, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ArrowRight, Clock, DataAnalysis, Document, Files, VideoPlay } from '@element-plus/icons-vue'
import request from '../utils/request'
import { fetchStudentCases } from '../utils/studentCases'

interface AssignmentItem {
  id: number
  title: string
  class_name?: string
  status?: string
  due_at?: string | null
  effective_due_at?: string | null
  allow_late?: boolean
  completed_count?: number
  required_count?: number
}

interface HomeCase {
  id: number
  title?: string
  scenes?: Array<Record<string, unknown>>
}

interface ScheduleEntry {
  key: string
  title: string
  meta: string
  action: string
  target: 'classes' | 'tasks' | 'free' | 'video'
  tone: 'danger' | 'warning' | 'primary' | 'muted'
}

const router = useRouter()
const setMainScrollable = inject<(value: boolean) => void>('setMainScrollable')

const loading = ref(false)
const selectedDateKey = ref('')
const assignments = ref<AssignmentItem[]>([])
const cases = ref<HomeCase[]>([])

const now = new Date()
const todayKey = toDateKey(now)
selectedDateKey.value = todayKey

const weekDays = computed(() => {
  const weekdayLabels = ['周日', '周一', '周二', '周三', '周四', '周五', '周六']
  return Array.from({ length: 7 }, (_, index) => {
    const offset = index - 2
    const date = new Date(now)
    date.setDate(now.getDate() + offset)
    const key = toDateKey(date)
    return {
      label: offset === 0 ? '今天' : weekdayLabels[date.getDay()],
      date: `${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`,
      key,
      active: selectedDateKey.value === key,
    }
  })
})

const allScenes = computed(() => cases.value.flatMap((item) => Array.isArray(item.scenes) ? item.scenes : []))
const totalCaseCount = computed(() => cases.value.length)
const totalSceneCount = computed(() => allScenes.value.length)
const activeSceneCount = computed(() => allScenes.value.filter((scene: any) => {
  const status = String(scene?.training_status || '')
  return status === 'in_progress' || status === 'evaluating' || Boolean(scene?.has_active_session)
}).length)
const completedSceneCount = computed(() => allScenes.value.filter((scene: any) => String(scene?.training_status || '') === 'completed').length)
const heroMetrics = computed(() => [
  { label: '可训练场景', value: totalSceneCount.value },
  { label: '进行中', value: activeSceneCount.value },
  { label: '已完成', value: completedSceneCount.value },
  { label: '案件数', value: totalCaseCount.value },
])

const selectedDay = computed(() => weekDays.value.find((day) => day.key === selectedDateKey.value))
const isSelectedToday = computed(() => selectedDateKey.value === todayKey)
const selectedDateLabel = computed(() =>
  isSelectedToday.value
    ? '优先处理临近截止、待补齐和可恢复任务'
    : `显示 ${selectedDay.value?.label || '所选日期'} 的安排`
)
const emptyScheduleTitle = computed(() =>
  isSelectedToday.value ? '今日暂无待处理任务' : `${selectedDay.value?.date || '所选日期'}暂无安排`
)
const emptyScheduleDescription = computed(() =>
  isSelectedToday.value
    ? '新的班级作业、案件训练或视频实训发布后会显示在这里'
    : '当前没有该日期截止的班级任务'
)

const scheduleEntries = computed<ScheduleEntry[]>(() => {
  const entries: ScheduleEntry[] = assignments.value
    .filter((assignment) => assignmentDateKey(assignment) === selectedDateKey.value || (isSelectedToday.value && !assignmentDateKey(assignment)))
    .slice(0, 3)
    .map((assignment) => {
      const status = normalizeAssignmentStatus(assignment.status)
      const days = daysUntilDue(assignment)
      return {
        key: `assignment-${assignment.id}`,
        title: assignment.title || '未命名班级作业',
        meta: `${assignment.class_name || '我的班级'} · ${assignmentProgressText(assignment)} · ${duePressureText(assignment)}`,
        action: status === 'in_progress' ? '继续作业' : status === 'unsubmitted' ? '补交作业' : '查看作业',
        target: 'classes',
        tone: status === 'unsubmitted' ? 'danger' : days !== null && days <= 1 ? 'warning' : 'primary',
      }
    })

  if (!entries.length && isSelectedToday.value) {
    const activeCase = cases.value.find((item) => (item.scenes || []).length > 0)
    if (activeCase) {
      entries.push({
        key: `case-${activeCase.id}`,
        title: activeCase.title || '训练案件',
        meta: `案件训练 · 共 ${activeCase.scenes?.length || 0} 个场景`,
        action: '进入训练大厅',
        target: 'tasks',
        tone: 'primary',
      })
    }
  }

  return entries
})

const quickEntries = [
  { label: '训练大厅', description: '浏览案件与场景', icon: VideoPlay, tone: 'blue', action: () => openTrainingCenter('free') },
  { label: '我的班级', description: '查看公告与成员', icon: Files, tone: 'green', action: () => router.push('/student/classes') },
  { label: '练习记录', description: '查看历史与评估', icon: DataAnalysis, tone: 'orange', action: () => router.push('/student/history') },
  { label: '视频实训', description: '第一视角节点训练', icon: Document, tone: 'cyan', action: () => openTrainingCenter('video') },
]

function selectScheduleDate(key: string) {
  selectedDateKey.value = key
}

function openTrainingCenter(tab: 'tasks' | 'free' | 'video' = 'tasks') {
  router.push({ path: '/student/training-center', query: tab === 'tasks' ? {} : { tab } })
}

function handleScheduleAction(item: ScheduleEntry) {
  if (item.target === 'classes') {
    router.push('/student/classes')
    return
  }
  openTrainingCenter(item.target)
}

function normalizeAssignmentStatus(status?: string): 'pending' | 'in_progress' | 'completed' | 'unsubmitted' {
  if (status === 'completed' || status === 'late') return 'completed'
  if (status === 'in_progress' || status === 'evaluating') return 'in_progress'
  if (status === 'unsubmitted' || status === 'expired') return 'unsubmitted'
  return 'pending'
}

function assignmentDueTime(assignment: AssignmentItem) {
  const raw = assignment.effective_due_at || assignment.due_at
  if (!raw) return null
  const time = new Date(raw).getTime()
  return Number.isNaN(time) ? null : time
}

function assignmentDateKey(assignment: AssignmentItem) {
  const raw = assignment.effective_due_at || assignment.due_at
  if (!raw) return ''
  const date = new Date(raw)
  return Number.isNaN(date.getTime()) ? '' : toDateKey(date)
}

function daysUntilDue(assignment: AssignmentItem) {
  const time = assignmentDueTime(assignment)
  if (!time) return null
  return Math.ceil((time - Date.now()) / 86400000)
}

function assignmentProgressText(assignment: AssignmentItem) {
  const completed = Number(assignment.completed_count || 0)
  const required = Number(assignment.required_count || 0)
  return required ? `${completed}/${required} 已完成` : `${completed} 项已完成`
}

function duePressureText(assignment: AssignmentItem) {
  const days = daysUntilDue(assignment)
  if (days === null) return '未设置截止时间'
  if (days < 0) return assignment.allow_late ? `已逾期 ${Math.abs(days)} 天，可补交` : `已逾期 ${Math.abs(days)} 天`
  if (days === 0) return '今天截止'
  if (days === 1) return '明天截止'
  if (days <= 3) return `${days} 天后截止`
  return `剩余 ${days} 天`
}

function toDateKey(date: Date) {
  const year = date.getFullYear()
  const month = String(date.getMonth() + 1).padStart(2, '0')
  const day = String(date.getDate()).padStart(2, '0')
  return `${year}-${month}-${day}`
}

async function fetchHomeSummary() {
  loading.value = true
  try {
    const [casesRes, assignmentsRes] = await Promise.all([
      fetchStudentCases(),
      request.get('/classes/student/assignments', { _skipErrorToast: true } as any),
    ])
    cases.value = Array.isArray(casesRes) ? casesRes : []
    assignments.value = Array.isArray(assignmentsRes) ? assignmentsRes : []
  } catch {
    cases.value = []
    assignments.value = []
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  setMainScrollable?.(true)
  fetchHomeSummary()
})
</script>

<style scoped lang="scss">
.practice-home-page {
  min-height: 100%;
  padding: 18px;
  color: #17213b;
  background: transparent;
  box-sizing: border-box;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.home-hero {
  display: grid;
  grid-template-columns: minmax(0, 1.45fr) minmax(360px, 0.95fr);
  gap: 18px;
  min-height: 210px;
  overflow: hidden;
  border-radius: 8px;
  padding: 24px;
  background:
    linear-gradient(135deg, rgba(8, 31, 82, 0.97), rgba(18, 57, 138, 0.96)),
    #081f52;
  color: #fff;
  box-shadow: 0 14px 30px rgba(13, 38, 95, 0.16);
}

.home-hero__content {
  display: flex;
  flex-direction: column;
  justify-content: center;
  min-width: 0;
}

.home-hero__content h1 {
  margin: 14px 0 10px;
  font-size: 30px;
  line-height: 1.16;
  font-weight: 800;
  letter-spacing: 0;
}

.home-hero__content p {
  max-width: 640px;
  margin: 0;
  color: rgba(255, 255, 255, 0.78);
  font-size: 14px;
  line-height: 1.9;
}

.home-hero__eyebrow {
  display: inline-flex;
  align-items: center;
  width: fit-content;
  height: 28px;
  padding: 0 12px;
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.12);
  border: 1px solid rgba(255, 255, 255, 0.18);
  color: rgba(255, 255, 255, 0.86);
  font-size: 12px;
  font-weight: 700;
}

.home-hero__chips {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 22px;
}

.home-hero__chips span {
  display: inline-flex;
  align-items: center;
  height: 30px;
  padding: 0 12px;
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.1);
  border: 1px solid rgba(255, 255, 255, 0.14);
  color: rgba(255, 255, 255, 0.84);
  font-size: 12px;
  font-weight: 600;
}

.home-hero__metrics {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
  align-content: center;
}

.home-metric {
  min-height: 82px;
  border-radius: 8px;
  padding: 16px;
  background: rgba(255, 255, 255, 0.1);
  border: 1px solid rgba(255, 255, 255, 0.14);
}

.home-metric--primary {
  background: rgba(255, 255, 255, 0.16);
}

.home-metric__label {
  display: block;
  color: rgba(255, 255, 255, 0.72);
  font-size: 12px;
}

.home-metric strong {
  display: block;
  margin-top: 10px;
  font-size: 28px;
  line-height: 1;
  font-weight: 800;
}

.home-layout {
  display: grid;
  grid-template-columns: minmax(0, 1.2fr) minmax(340px, 0.8fr);
  gap: 16px;
  min-height: 0;
  flex: 1;
}

.home-panel {
  min-height: 0;
  padding: 18px;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  background: #fff;
  box-shadow: 0 4px 16px rgba(35, 56, 104, 0.06);
}

.panel-heading {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
}

.panel-heading h2 {
  margin: 0;
  color: #17213b;
  font-size: 17px;
  font-weight: 800;
}

.panel-heading p {
  margin: 5px 0 0;
  color: #8b96aa;
  font-size: 12px;
}

.week-row {
  display: grid;
  grid-template-columns: repeat(7, minmax(0, 1fr));
  gap: 8px;
  margin-top: 16px;
}

.day-chip {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 5px;
  padding: 9px 4px;
  border: 1px solid #e7edf5;
  border-radius: 7px;
  background: #fff;
  color: #8b96aa;
  cursor: pointer;
  font-size: 11px;
  font-family: inherit;
  text-align: center;
  transition: border-color 0.18s ease, background-color 0.18s ease, color 0.18s ease;
}

.day-chip:hover {
  border-color: #b9c8ff;
  background: #f7f9ff;
  color: #3566f6;
}

.day-chip b {
  color: #334155;
  font-size: 12px;
}

.day-chip--active {
  border-color: #3566f6;
  background: #eef3ff;
  color: #3566f6;
}

.day-chip--active b {
  color: #2454c4;
}

.schedule-list {
  display: grid;
  gap: 10px;
  margin-top: 16px;
}

.schedule-list .schedule-item {
  margin-top: 0;
}

.schedule-item {
  display: grid;
  grid-template-columns: 38px minmax(0, 1fr) auto;
  align-items: center;
  gap: 12px;
  margin-top: 12px;
  padding: 11px 12px;
  border: 1px solid #e8edf5;
  border-left: 3px solid #3566f6;
  border-radius: 7px;
  background: #fafcff;
}

.schedule-item--danger {
  border-left-color: #dc2626;
  background: #fffafa;
}

.schedule-item--danger .schedule-icon {
  background: #fee2e2;
  color: #dc2626;
}

.schedule-item--warning {
  border-left-color: #e08322;
  background: #fffaf4;
}

.schedule-item--warning .schedule-icon {
  background: #fff1d9;
  color: #e08322;
}

.schedule-item--muted {
  border-left-color: #cbd5e1;
  background: #f8fafc;
}

.schedule-item--muted .schedule-icon {
  background: #eef2f7;
  color: #64748b;
}

.schedule-icon,
.quick-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex: 0 0 auto;
}

.schedule-icon {
  width: 34px;
  height: 34px;
  border-radius: 8px;
  background: #e9efff;
  color: #3566f6;
}

.schedule-copy {
  display: flex;
  flex-direction: column;
  gap: 5px;
  min-width: 0;
}

.schedule-copy strong {
  overflow: hidden;
  color: #253047;
  font-size: 13px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.schedule-copy span {
  color: #8b96aa;
  font-size: 12px;
}

.quick-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 8px;
  margin-top: 14px;
}

.quick-panel {
  align-self: start;
}

.quick-item {
  display: flex;
  align-items: center;
  gap: 9px;
  min-width: 0;
  padding: 10px;
  border: 1px solid transparent;
  border-radius: 7px;
  background: #fafbfd;
  text-align: left;
  cursor: pointer;
}

.quick-item:hover {
  border-color: #dbe5ff;
  background: #f6f8ff;
}

.quick-icon {
  width: 32px;
  height: 32px;
  border-radius: 8px;
}

.quick-icon--blue { background: #eaf0ff; color: #3566f6; }
.quick-icon--green { background: #eaf8f0; color: #16a36a; }
.quick-icon--cyan { background: #e8f8fb; color: #0c9bb4; }
.quick-icon--orange { background: #fff3e7; color: #e68325; }

.quick-copy {
  display: flex;
  flex: 1;
  flex-direction: column;
  gap: 3px;
  min-width: 0;
}

.quick-copy strong,
.quick-copy small {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.quick-copy strong {
  color: #253047;
  font-size: 12px;
}

.quick-copy small {
  color: #8b96aa;
  font-size: 11px;
}

.quick-arrow {
  color: #a1acbc;
}

@media (max-width: 1180px) {
  .home-hero {
    grid-template-columns: 1fr;
  }

  .home-layout {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 760px) {
  .practice-home-page {
    padding: 14px;
  }

  .home-hero__content h1 {
    font-size: 24px;
  }

  .home-hero__metrics,
  .home-layout,
  .quick-grid {
    grid-template-columns: 1fr;
  }

  .schedule-item {
    grid-template-columns: 34px minmax(0, 1fr);
  }

  .schedule-item :deep(.el-button) {
    grid-column: 2;
    justify-self: start;
  }
}
</style>
