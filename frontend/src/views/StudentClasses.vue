<template>
  <div class="student-page class-task-page">
    <header class="task-header">
      <div class="task-header__main">
        <div>
          <span class="section-kicker">MY CLASSES</span>
          <h1>{{ pageTitle }}</h1>
          <p>先查看我的班级，再按要求完成作业训练并提交评估报告</p>
        </div>
      </div>
      <el-select
        v-model="selectedClassId"
        class="class-filter"
        placeholder="选择班级"
        :teleported="false"
        @change="selectClass(Number($event))"
      >
        <el-option label="全部班级" :value="0" />
        <el-option
          v-for="item in classes"
          :key="item.id"
          :label="item.name || '未命名班级'"
          :value="Number(item.id)"
        />
      </el-select>
      <div class="join-box">
        <input v-model.trim="inviteCode" type="text" placeholder="输入班级邀请码" />
        <el-button type="primary" :loading="joining" @click="joinClass">加入班级</el-button>
      </div>
    </header>

    <section class="task-panel">
      <div class="task-toolbar">
        <el-tabs v-model="activeTab" class="task-tabs">
          <el-tab-pane label="全部作业" name="all" />
          <el-tab-pane label="待完成" name="pending" />
          <el-tab-pane label="训练中" name="in_progress" />
          <el-tab-pane label="已完成" name="completed" />
          <el-tab-pane label="未提交" name="unsubmitted" />
        </el-tabs>
        <el-button plain :loading="loading" @click="fetchAll">
          <el-icon><Refresh /></el-icon>
          刷新
        </el-button>
      </div>

      <div ref="taskBodyRef" class="task-panel__body">
        <div v-if="loading" class="state-panel">
          <el-skeleton :rows="8" animated />
        </div>
        <div v-else-if="visibleAssignments.length" class="assignment-list">
          <article v-for="assignment in visibleAssignments" :key="assignment.id" class="assignment-card">
          <header>
            <div class="assignment-main">
              <div class="assignment-meta">
                <span class="status-pill" :class="`status-pill--${normalizeStatus(assignment.status)}`">
                  {{ statusLabel(assignment.status) }}
                </span>
                <span>{{ assignment.class_name }}</span>
              </div>
              <h2>{{ assignment.title }}</h2>
              <dl class="assignment-brief">
                <div v-for="row in assignmentBriefRows(assignment)" :key="`${row.label}-${row.text}`" class="assignment-brief__row">
                  <dt>{{ row.label }}</dt>
                  <dd>{{ row.text }}</dd>
                </div>
              </dl>
            </div>
            <div class="assignment-progress">
              <strong>{{ progressText(assignment) }}</strong>
              <span>场景完成</span>
              <button type="button" @click="toggleAssignment(assignment)">
                <el-icon><ArrowRight /></el-icon>
              </button>
            </div>
          </header>

          <div class="assignment-info">
            <span><el-icon><Calendar /></el-icon>发布时间：{{ formatDateTime(assignment.published_at) }}</span>
            <span><el-icon><Clock /></el-icon>截止时间：{{ formatDateTime(assignment.effective_due_at || assignment.due_at) }}</span>
            <span class="assignment-info__danger"><el-icon><Warning /></el-icon>{{ duePressureText(assignment) }}</span>
            <span>{{ assignment.allow_late ? '允许补交' : '按时截止' }}</span>
          </div>

          <div class="completion-standard">
            <el-icon><InfoFilled /></el-icon>
            <strong>完成标准</strong>
            <span>{{ completionStandardText(assignment) }}</span>
          </div>

          <div v-if="ruleBriefRows(assignment.scoring_rule).length" class="scoring-rule">
            <strong>达标与计分</strong>
            <dl>
              <div v-for="row in ruleBriefRows(assignment.scoring_rule)" :key="`${row.label}-${row.text}`">
                <dt>{{ row.label }}</dt>
                <dd>{{ row.text }}</dd>
              </div>
            </dl>
          </div>

          <div class="case-list">
            <div v-for="caseItem in assignment.cases" :key="caseItem.id" class="case-row">
              <div>
                <strong>{{ caseItem.title }}</strong>
                <span>{{ caseItem.case_type || '未分类' }}</span>
              </div>
              <van-tag plain :type="caseStatusType(caseStatus(assignment, caseItem.id))">
                {{ caseStatusLabel(caseStatus(assignment, caseItem.id)) }}
              </van-tag>
            </div>
          </div>

          <div v-if="expandedAssignmentId === assignment.id && assignmentDetails[assignment.id]" class="scene-list">
            <section v-for="caseItem in assignmentDetails[assignment.id].cases" :key="caseItem.id">
              <h3>{{ caseItem.title }}</h3>
              <div class="scene-grid">
                <div v-for="scene in caseItem.scenes" :key="scene.id" class="scene-card">
                  <div>
                    <strong>{{ scene.name }}</strong>
                    <span>{{ scene.difficulty || '中等' }} / {{ sceneStatusLabel(scene.training_status) }}</span>
                  </div>
                  <div class="scene-actions">
                    <el-button
                      v-if="scene.finished_session_id"
                      plain
                      size="small"
                      @click="router.push(`/student/evaluation?session_id=${scene.finished_session_id}&source=assignment&assignment_id=${assignment.id}`)"
                    >
                      查看报告
                    </el-button>
                    <el-button
                      type="primary"
                      size="small"
                      :loading="startingSceneId === scene.id"
                      :disabled="!canStartAssignment(assignment) || startingSceneId !== null"
                      @click="startScene(assignment.id, scene)"
                    >
                      {{ sceneActionLabel(scene.training_status) }}
                    </el-button>
                  </div>
                </div>
              </div>
            </section>
          </div>

          <footer>
            <el-button plain @click="toggleAssignment(assignment)">
              {{ expandedAssignmentId === assignment.id ? '收起案件' : '查看案件训练' }}
            </el-button>
            <el-button
              type="primary"
              :loading="startingAssignmentId === assignment.id"
              :disabled="!canStartAssignment(assignment) || startingSceneId !== null"
              @click="startFirstScene(assignment)"
            >
              {{ primaryActionLabel(assignment) }}
            </el-button>
          </footer>
          </article>
        </div>
        <el-empty v-else :description="emptyDescription" />
      </div>
    </section>
  </div>
</template>

<script setup lang="ts">
import { computed, inject, nextTick, onMounted, onUnmounted, reactive, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import {
  ArrowRight,
  Calendar,
  Clock,
  InfoFilled,
  Refresh,
  Warning,
} from '@element-plus/icons-vue'
import { showToast } from 'vant'
import request from '../utils/request'

const router = useRouter()
const setMainScrollable = inject<(value: boolean) => void>('setMainScrollable')

const classes = ref<any[]>([])
const assignments = ref<any[]>([])
const assignmentDetails = reactive<Record<number, any>>({})
const selectedClassId = ref(0)
const expandedAssignmentId = ref<number | null>(null)
const activeTab = ref<'all' | 'pending' | 'in_progress' | 'completed' | 'unsubmitted'>('all')
const inviteCode = ref('')
const loading = ref(false)
const joining = ref(false)
const startingSceneId = ref<number | null>(null)
const startingAssignmentId = ref<number | null>(null)
const taskBodyRef = ref<HTMLElement | null>(null)

const pageTitle = computed(() => {
  return '我的班级'
})

const visibleAssignments = computed(() => {
  let result = assignments.value
  if (activeTab.value !== 'all') {
    result = result.filter((assignment) => normalizeStatus(assignment.status) === activeTab.value)
  }
  return [...result].sort((left, right) => {
    const priorityDiff = assignmentPriority(right) - assignmentPriority(left)
    if (priorityDiff !== 0) return priorityDiff
    const leftDue = new Date(left.effective_due_at || left.due_at || 8640000000000000).getTime()
    const rightDue = new Date(right.effective_due_at || right.due_at || 8640000000000000).getTime()
    return leftDue - rightDue
  })
})

const emptyDescription = computed(() => {
  if (!classes.value.length) return '请先通过邀请码加入班级'
  if (activeTab.value === 'all') return '当前班级暂无作业'
  return '暂无符合当前状态的作业'
})

const normalizeStatus = (status: string): 'pending' | 'in_progress' | 'completed' | 'unsubmitted' => {
  if (status === 'completed' || status === 'late') return 'completed'
  if (status === 'in_progress' || status === 'evaluating') return 'in_progress'
  if (status === 'unsubmitted' || status === 'expired') return 'unsubmitted'
  return 'pending'
}

const dueTime = (assignment: any) => {
  const raw = assignment?.effective_due_at || assignment?.due_at
  if (!raw) return null
  const time = new Date(raw).getTime()
  return Number.isNaN(time) ? null : time
}

const daysUntilDue = (assignment: any) => {
  const time = dueTime(assignment)
  if (!time) return null
  return Math.ceil((time - Date.now()) / 86400000)
}

const assignmentPriority = (assignment: any) => {
  const status = normalizeStatus(assignment.status)
  const days = daysUntilDue(assignment)
  if (status === 'unsubmitted') return assignment.allow_late ? 100 : 90
  if (status === 'in_progress') return 80
  if (status === 'pending' && days !== null && days <= 1) return 70
  if (status === 'pending' && days !== null && days <= 3) return 60
  if (status === 'pending') return 40
  return 0
}

const duePressureText = (assignment: any) => {
  const days = daysUntilDue(assignment)
  if (days === null) return '未设置截止时间'
  if (days < 0) return assignment.allow_late ? `已逾期 ${Math.abs(days)} 天，可补交` : `已逾期 ${Math.abs(days)} 天`
  if (days === 0) return '今天截止'
  if (days === 1) return '明天截止'
  if (days <= 3) return `${days} 天后截止`
  return `剩余 ${days} 天`
}

const completionStandardText = (assignment: any) => {
  const required = Number(assignment.required_count || assignment.cases?.length || 0)
  const completed = Number(assignment.completed_count || 0)
  const lateText = assignment.allow_late ? '截止后仍可补交' : '截止后将不可继续提交'
  if (!required) return `${lateText}；当前作业暂无可训练场景，请等待教官补充。`
  return `需完成 ${required} 个训练场景并生成评估报告，当前已完成 ${completed} 个；${lateText}。`
}

const progressText = (assignment: any) => {
  const completed = Number(assignment?.completed_count || 0)
  const required = Number(assignment?.required_count || assignment?.cases?.length || 0)
  return `${completed}/${required || 0}`
}

const textLines = (value: any) =>
  String(value || '')
    .split(/\n+/)
    .map((line) => line.trim())
    .filter(Boolean)

const extractLabeledText = (text: string, label: string, labels: string[]) => {
  const nextLabels = labels.filter((item) => item !== label).join('|')
  const match = text.match(new RegExp(`${label}[：:]\\s*([\\s\\S]*?)(?=(?:${nextLabels})[：:]|$)`))
  return match?.[1]?.trim() || ''
}

const briefRows = (value: any, labels: string[], fallbackLabels: string[]) => {
  const text = String(value || '').trim()
  if (!text) return []
  const labeledRows = labels
    .map((label) => ({ label, text: extractLabeledText(text, label, labels) }))
    .filter((row) => row.text)
  if (labeledRows.length) return labeledRows
  return textLines(text)
    .slice(0, 3)
    .map((line, index) => ({ label: fallbackLabels[index] || '补充说明', text: line }))
}

const assignmentBriefRows = (assignment: any) => {
  const rows = briefRows(assignment?.instructions, ['训练目标', '训练重点', '提交要求'], ['训练要求', '补充说明'])
  return rows.length ? rows : [{ label: '训练要求', text: '暂无训练要求说明。' }]
}

const ruleBriefRows = (value: any) =>
  briefRows(value, ['达标规则', '计分口径', '重点关注', '扣分规则', '评分标准'], ['达标规则', '计分口径', '重点关注'])

const assignmentActionHint = (assignment: any) => {
  const status = normalizeStatus(assignment.status)
  if (status === 'unsubmitted') return assignment.allow_late ? '作业已过截止时间，但仍开放补交，建议先完成未提交案件。' : '作业已截止且暂未开放补交，请联系教官确认处理方式。'
  if (status === 'in_progress') return '已有未完成训练记录，建议继续上次进度，避免重复开始。'
  if (status === 'pending') return `${duePressureText(assignment)}，请按完成标准依次完成案件训练。`
  return '已完成，可查看报告或根据评估结果重新训练。'
}

const fetchAll = async () => {
  loading.value = true
  try {
    const classParam = selectedClassId.value ? `?class_id=${selectedClassId.value}` : ''
    const [classRes, assignmentRes]: any[] = await Promise.all([
      request.get('/classes/student/my'),
      request.get(`/classes/student/assignments${classParam}`),
    ])
    classes.value = Array.isArray(classRes) ? classRes : []
    assignments.value = Array.isArray(assignmentRes) ? assignmentRes : []
    if (!selectedClassId.value && classes.value.length === 1) selectedClassId.value = Number(classes.value[0].id)
  } finally {
    loading.value = false
  }
}

const selectClass = async (classId: number) => {
  selectedClassId.value = classId
  expandedAssignmentId.value = null
  await fetchAll()
}

const joinClass = async () => {
  if (!inviteCode.value.trim()) {
    showToast('请输入班级邀请码')
    return
  }
  joining.value = true
  try {
    const res: any = await request.post('/classes/join', { invite_code: inviteCode.value.trim() })
    showToast({ type: 'success', message: `已加入 ${res?.classroom?.name || '班级'}` })
    inviteCode.value = ''
    selectedClassId.value = Number(res?.classroom?.id || 0)
    await fetchAll()
  } finally {
    joining.value = false
  }
}

const fetchAssignmentDetail = async (assignmentId: number) => {
  const detail: any = await request.get(`/classes/student/assignments/${assignmentId}`)
  assignmentDetails[assignmentId] = detail
  return detail
}

const toggleAssignment = async (assignment: any) => {
  if (expandedAssignmentId.value === assignment.id) {
    expandedAssignmentId.value = null
    return
  }
  expandedAssignmentId.value = assignment.id
  if (!assignmentDetails[assignment.id]) {
    await fetchAssignmentDetail(assignment.id)
  }
}

const startFirstScene = async (assignment: any) => {
  startingAssignmentId.value = assignment.id
  try {
    const detail = assignmentDetails[assignment.id] || await fetchAssignmentDetail(assignment.id)
    const targetCase = (detail.cases || []).find((item: any) => !['completed', 'late'].includes(item.status)) || detail.cases?.[0]
    const targetScene = targetCase?.scenes?.find((scene: any) => scene.training_status === 'in_progress' || scene.training_status === 'evaluating')
      || targetCase?.scenes?.[0]
    if (!targetScene) {
      showToast('该作业暂无可训练场景')
      return
    }
    await startScene(assignment.id, targetScene)
  } finally {
    startingAssignmentId.value = null
  }
}

const startScene = async (assignmentId: number, scene: any) => {
  if (!scene?.id || startingSceneId.value !== null) return
  startingSceneId.value = scene.id
  try {
    const res: any = await request.post(`/training/start/${scene.id}?assignment_id=${assignmentId}`, null, { _skipErrorToast: true } as any)
    if (!res?.id) throw new Error('训练初始化失败')
    if (scene.training_status === 'in_progress') {
      showToast('已恢复上次未完成训练')
    }
    router.push(`/student/training/${res.id}?source=assignment&assignment_id=${assignmentId}`)
  } catch (error: any) {
    showToast(error?.response?.data?.detail || error?.message || '训练环境初始化失败')
  } finally {
    startingSceneId.value = null
  }
}

const canStartAssignment = (assignment: any) => {
  if (assignment.status === 'unsubmitted' && !assignment.allow_late) return false
  return true
}

const primaryActionLabel = (assignment: any) => {
  if (!canStartAssignment(assignment)) return '已截止'
  if (assignment.status === 'completed' || assignment.status === 'late') return '重新训练'
  if (assignment.status === 'in_progress') return '继续训练'
  return '开始训练'
}

const sceneActionLabel = (status: string) => {
  if (status === 'completed' || status === 'late') return '重新训练'
  if (status === 'in_progress' || status === 'evaluating') return '继续训练'
  return '开始训练'
}

const statusLabel = (status: string) => {
  const map: Record<string, string> = {
    pending: '待完成',
    in_progress: '训练中',
    completed: '已完成',
    late: '补交完成',
    unsubmitted: '未提交',
  }
  return map[status] || '待完成'
}

const statusType = (status: string) => {
  if (status === 'completed') return 'success'
  if (status === 'late' || status === 'in_progress') return 'warning'
  if (status === 'unsubmitted') return 'danger'
  return 'primary'
}

const caseStatus = (assignment: any, caseId: number) => {
  const item = (assignment.case_statuses || []).find((row: any) => row.case_id === caseId)
  return item?.status || 'pending'
}

const caseStatusLabel = (status: string) => {
  const map: Record<string, string> = {
    completed: '已完成',
    late: '补交',
    in_progress: '训练中',
    evaluating: '评估中',
    expired: '已截止',
    pending: '待训练',
  }
  return map[status] || status
}

const caseStatusType = (status: string) => {
  if (status === 'completed') return 'success'
  if (status === 'late' || status === 'in_progress' || status === 'evaluating') return 'warning'
  if (status === 'expired') return 'danger'
  return 'primary'
}

const sceneStatusLabel = (status: string) => caseStatusLabel(status === 'not_started' ? 'pending' : status)

const formatDateTime = (value: any) => {
  if (!value) return '未设置'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return String(value)
  const pad = (num: number) => String(num).padStart(2, '0')
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())} ${pad(date.getHours())}:${pad(date.getMinutes())}`
}

onMounted(async () => {
  setMainScrollable?.(false)
  await fetchAll()
})

onUnmounted(() => {
  setMainScrollable?.(false)
})

watch(activeTab, async () => {
  expandedAssignmentId.value = null
  await nextTick()
  if (taskBodyRef.value) {
    taskBodyRef.value.scrollTop = 0
  }
})
</script>

<style scoped>
.class-task-page {
  display: grid;
  grid-template-rows: auto minmax(0, 1fr);
  gap: 16px;
  height: 100%;
  min-height: 0;
  overflow: hidden;
  padding: 22px;
  background: #f3f6fa;
}

.task-header,
.task-toolbar,
.assignment-card header,
.scene-card,
.case-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 14px;
}

.task-header {
  display: grid;
  grid-template-columns: minmax(260px, 1fr) 220px auto;
  align-items: end;
  gap: 16px;
  width: min(100%, 1480px);
  justify-self: center;
  padding: 0;
}

.task-header__main {
  display: flex;
  align-items: center;
  min-width: 0;
}

.section-kicker {
  color: #3566f6;
  font-size: 10px;
  font-weight: 800;
  letter-spacing: 0.08em;
}

.task-header h1 {
  margin: 4px 0 6px;
  color: #17213b;
  font-size: 26px;
  font-weight: 800;
  letter-spacing: 0;
}

.task-header p {
  margin: 0;
  color: #8b96aa;
  font-size: 13px;
}

.class-filter {
  width: 100%;
}

.join-box {
  display: grid;
  grid-template-columns: 220px auto;
  align-items: center;
  gap: 8px;
  flex: 0 0 auto;
}

.join-box input {
  border: 1px solid #dbe3ee;
  border-radius: 6px;
  background: #fff;
  padding: 7px 12px;
  color: #0f172a;
  font-size: 13px;
  outline: none;
}

.join-box input::placeholder {
  color: #a5afbf;
}

.join-box input:focus {
  border-color: #9ab5ff;
  box-shadow: 0 0 0 3px rgba(53, 102, 246, 0.1);
}

.join-box :deep(.el-button) {
  border-radius: 6px;
  font-weight: 700;
}

.assignment-info__danger {
  color: #dc2626;
}

.task-panel {
  display: flex;
  flex-direction: column;
  min-height: 0;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  background: #fff;
  overflow: hidden;
  box-shadow: 0 1px 2px rgb(15 23 42 / 4%);
}

.task-toolbar {
  flex: 0 0 auto;
  height: 50px;
  padding: 0 14px;
  border-bottom: 1px solid #eef2f7;
}

.task-panel__body {
  flex: 1;
  min-height: 0;
  overflow-y: scroll;
  overflow-x: hidden;
  scrollbar-gutter: stable;
}

.task-tabs :deep(.el-tabs__header) {
  margin-bottom: 0;
}

.task-tabs :deep(.el-tabs__item:focus-visible),
.task-tabs :deep(.el-tabs__item.is-focus) {
  box-shadow: none !important;
  outline: none !important;
}

.assignment-list {
  display: grid;
  gap: 14px;
  padding: 14px 14px 80px;
}

.assignment-card {
  border: 1px solid #e5e7eb;
  border-radius: 10px;
  background: #fff;
  padding: 18px 20px;
}

.assignment-main {
  min-width: 0;
}

.assignment-meta {
  display: flex;
  align-items: center;
  gap: 8px;
  color: #64748b;
  font-size: 12px;
}

.assignment-card h2 {
  margin: 10px 0 0;
  color: #0f172a;
  font-size: 20px;
  font-weight: 900;
}

.assignment-progress {
  min-width: 118px;
  display: grid;
  justify-items: end;
  gap: 6px;
}

.assignment-progress strong {
  color: #165dff;
  font-size: 30px;
  line-height: 1;
}

.assignment-progress span {
  color: #64748b;
  font-size: 12px;
}

.assignment-progress button {
  display: grid;
  place-items: center;
  width: 28px;
  height: 28px;
  border: 0;
  border-radius: 50%;
  background: #f1f5f9;
  color: #475569;
  cursor: pointer;
}

.assignment-info {
  display: flex;
  flex-wrap: wrap;
  gap: 14px;
  margin-top: 14px;
  color: #475569;
  font-size: 13px;
}

.assignment-info span {
  display: inline-flex;
  align-items: center;
  gap: 5px;
}

.completion-standard,
.scoring-rule {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  margin: 14px 0 12px;
  border: 1px solid #e0f2fe;
  border-radius: 8px;
  background: #f8fbff;
  padding: 10px 12px;
}

.scoring-rule {
  margin-top: -4px;
  border-color: #e5e7eb;
  background: #fff;
}

.completion-standard strong,
.scoring-rule strong {
  flex: 0 0 auto;
  color: #0f172a;
  font-size: 13px;
  font-weight: 900;
}

.completion-standard span,
.scoring-rule span {
  color: #475569;
  font-size: 12px;
  line-height: 1.6;
}

.assignment-brief,
.scoring-rule dl {
  display: grid;
  gap: 8px;
  margin: 12px 0 0;
}

.assignment-brief__row,
.scoring-rule dl > div {
  display: grid;
  grid-template-columns: 68px minmax(0, 1fr);
  gap: 10px;
}

.assignment-brief dt,
.scoring-rule dt {
  color: #334155;
  font-size: 12px;
  font-weight: 900;
}

.assignment-brief dd,
.scoring-rule dd {
  margin: 0;
  color: #64748b;
  font-size: 13px;
  line-height: 1.6;
}

.scoring-rule dl {
  flex: 1;
  min-width: 0;
  margin-top: 0;
}

.scoring-rule dd {
  font-size: 12px;
}

.case-list,
.scene-list {
  display: grid;
  gap: 10px;
  margin-top: 14px;
}

.case-row,
.scene-card {
  border: 1px solid #eef2f7;
  border-radius: 8px;
  background: #f8fafc;
  padding: 12px;
}

.case-row strong,
.scene-card strong {
  color: #0f172a;
  font-size: 14px;
}

.case-row span,
.scene-card span {
  display: block;
  margin-top: 6px;
  color: #64748b;
  font-size: 12px;
}

.scene-grid {
  display: grid;
  gap: 10px;
  margin-top: 10px;
}

.scene-actions {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.status-pill {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-height: 24px;
  border: 1px solid #bfdbfe;
  border-radius: 999px;
  background: #eff6ff;
  padding: 3px 9px;
  color: #165dff;
  font-size: 12px;
  font-weight: 900;
  white-space: nowrap;
}

.status-pill--completed {
  border-color: #bbf7d0;
  background: #f0fdf4;
  color: #16a34a;
}

.status-pill--in_progress {
  border-color: #fde68a;
  background: #fffbeb;
  color: #b45309;
}

.status-pill--unsubmitted {
  border-color: #fecaca;
  background: #fff1f2;
  color: #dc2626;
}

.state-panel {
  padding: 18px;
}

@media (max-width: 960px) {
  .task-header,
  .assignment-card header,
  .scene-card,
  .case-row {
    display: grid;
    grid-template-columns: 1fr;
  }

  .task-header {
    grid-template-columns: 1fr;
    gap: 14px;
  }

  .join-box {
    grid-template-columns: 1fr;
    width: 100%;
  }

  .join-box :deep(.el-button) {
    width: 100%;
  }

  .class-task-page {
    padding: 14px;
  }
}
</style>
