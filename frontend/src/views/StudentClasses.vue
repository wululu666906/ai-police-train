<template>
  <div class="student-page class-task-page">
    <header class="task-header">
      <div>
        <h1>班级作业</h1>
        <p>加入班级后，训练作业会统一下发到这里，支持开始训练、继续训练和查看报告。</p>
      </div>
      <div class="join-box">
        <input v-model.trim="inviteCode" type="text" placeholder="输入班级邀请码" />
        <el-button type="primary" :loading="joining" @click="joinClass">加入班级</el-button>
      </div>
    </header>

    <section class="class-strip">
      <button
        type="button"
        class="class-filter"
        :class="{ 'class-filter--active': selectedClassId === 0 }"
        @click="selectClass(0)"
      >
        全部班级
      </button>
      <button
        v-for="item in classes"
        :key="item.id"
        type="button"
        class="class-filter"
        :class="{ 'class-filter--active': selectedClassId === item.id }"
        @click="selectClass(item.id)"
      >
        {{ item.name }}
      </button>
    </section>

    <section v-if="announcements.length" class="notice-band">
      <article v-for="item in announcements.slice(0, 3)" :key="item.id">
        <div>
          <strong>{{ item.title }}</strong>
          <span>{{ formatDateTime(item.created_at) }}</span>
        </div>
        <p>{{ item.content || '无正文' }}</p>
      </article>
    </section>

    <section class="summary-grid">
      <div class="summary-card">
        <span>待完成</span>
        <strong>{{ statusCount.pending + statusCount.in_progress }}</strong>
      </div>
      <div class="summary-card">
        <span>已完成</span>
        <strong>{{ statusCount.completed }}</strong>
      </div>
      <div class="summary-card summary-card--warn">
        <span>逾期未交</span>
        <strong>{{ statusCount.unsubmitted }}</strong>
      </div>
    </section>

    <section class="task-panel">
      <div class="task-toolbar">
        <el-tabs v-model="activeTab" class="task-tabs">
          <el-tab-pane label="全部作业" name="all" />
          <el-tab-pane label="待完成" name="pending" />
          <el-tab-pane label="训练中" name="in_progress" />
          <el-tab-pane label="已完成" name="completed" />
          <el-tab-pane label="未提交" name="unsubmitted" />
        </el-tabs>
        <el-button plain :loading="loading" @click="fetchAll">刷新</el-button>
      </div>

      <div v-if="loading" class="state-panel">
        <el-skeleton :rows="8" animated />
      </div>
      <div v-else-if="visibleAssignments.length" class="assignment-list">
        <article v-for="assignment in visibleAssignments" :key="assignment.id" class="assignment-card">
          <header>
            <div>
              <div class="assignment-meta">
                <van-tag :type="statusType(assignment.status)" plain>{{ statusLabel(assignment.status) }}</van-tag>
                <span>{{ assignment.class_name }}</span>
              </div>
              <h2>{{ assignment.title }}</h2>
              <p>{{ assignment.instructions || '暂无训练要求说明。' }}</p>
            </div>
            <div class="assignment-progress">
              <strong>{{ assignment.completed_count }}/{{ assignment.required_count }}</strong>
              <span>案件完成</span>
            </div>
          </header>

          <div class="assignment-info">
            <span>发布时间：{{ formatDateTime(assignment.published_at) }}</span>
            <span>截止时间：{{ formatDateTime(assignment.effective_due_at || assignment.due_at) }}</span>
            <span>{{ assignment.allow_late ? '允许补交' : '按时截止' }}</span>
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
                      @click="router.push(`/student/evaluation?session_id=${scene.finished_session_id}`)"
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
    </section>
  </div>
</template>

<script setup lang="ts">
import { computed, inject, onMounted, onUnmounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { showToast } from 'vant'
import request from '../utils/request'

const router = useRouter()
const setMainScrollable = inject<(value: boolean) => void>('setMainScrollable')

const classes = ref<any[]>([])
const assignments = ref<any[]>([])
const announcements = ref<any[]>([])
const assignmentDetails = reactive<Record<number, any>>({})
const selectedClassId = ref(0)
const expandedAssignmentId = ref<number | null>(null)
const activeTab = ref<'all' | 'pending' | 'in_progress' | 'completed' | 'unsubmitted'>('all')
const inviteCode = ref('')
const loading = ref(false)
const joining = ref(false)
const startingSceneId = ref<number | null>(null)
const startingAssignmentId = ref<number | null>(null)

const visibleAssignments = computed(() => {
  let result = assignments.value
  if (activeTab.value !== 'all') {
    result = result.filter((assignment) => normalizeStatus(assignment.status) === activeTab.value)
  }
  return [...result].sort((left, right) => {
    const leftDue = new Date(left.effective_due_at || left.due_at || 8640000000000000).getTime()
    const rightDue = new Date(right.effective_due_at || right.due_at || 8640000000000000).getTime()
    return leftDue - rightDue
  })
})

const statusCount = computed(() => {
  const initial = { pending: 0, in_progress: 0, completed: 0, unsubmitted: 0 }
  for (const assignment of assignments.value) {
    const status = normalizeStatus(assignment.status)
    initial[status] += 1
  }
  return initial
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

const fetchAll = async () => {
  loading.value = true
  try {
    const classParam = selectedClassId.value ? `?class_id=${selectedClassId.value}` : ''
    const [classRes, assignmentRes, announcementRes]: any[] = await Promise.all([
      request.get('/classes/student/my'),
      request.get(`/classes/student/assignments${classParam}`),
      request.get(`/classes/student/announcements${classParam}`),
    ])
    classes.value = Array.isArray(classRes) ? classRes : []
    assignments.value = Array.isArray(assignmentRes) ? assignmentRes : []
    announcements.value = Array.isArray(announcementRes) ? announcementRes : []
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
    router.push(`/student/training/${res.id}`)
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
  setMainScrollable?.(true)
  await fetchAll()
})

onUnmounted(() => {
  setMainScrollable?.(false)
})
</script>

<style scoped>
.class-task-page {
  display: grid;
  gap: 14px;
  padding: 20px 28px 32px;
}

.task-header,
.task-toolbar,
.assignment-card header,
.assignment-card footer,
.scene-card,
.case-row,
.notice-band article div {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 14px;
}

.task-header {
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  background: #fff;
  padding: 18px 20px;
}

.task-header h1 {
  margin: 0;
  color: #111827;
  font-size: 24px;
  font-weight: 900;
}

.task-header p {
  margin: 5px 0 0;
  color: #64748b;
  font-size: 13px;
}

.join-box {
  display: grid;
  grid-template-columns: 190px auto;
  gap: 8px;
}

.join-box input {
  height: 32px;
  border: 1px solid #dbe3ee;
  border-radius: 6px;
  padding: 0 10px;
  color: #0f172a;
  outline: none;
}

.class-strip {
  display: flex;
  gap: 8px;
  overflow-x: auto;
  padding-bottom: 2px;
}

.class-filter {
  height: 32px;
  flex-shrink: 0;
  border: 1px solid #dbe3ee;
  border-radius: 999px;
  background: #fff;
  padding: 0 14px;
  color: #475569;
  font-size: 13px;
  font-weight: 800;
  cursor: pointer;
}

.class-filter--active {
  border-color: #165dff;
  background: #165dff;
  color: #fff;
}

.notice-band {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 10px;
}

.notice-band article {
  border: 1px solid #dbeafe;
  border-radius: 8px;
  background: #f8fbff;
  padding: 12px;
}

.notice-band strong {
  color: #0f172a;
  font-size: 14px;
}

.notice-band span,
.notice-band p {
  margin: 6px 0 0;
  color: #64748b;
  font-size: 12px;
  line-height: 1.6;
}

.summary-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 10px;
}

.summary-card {
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  background: #fff;
  padding: 14px 16px;
}

.summary-card span {
  color: #64748b;
  font-size: 13px;
  font-weight: 800;
}

.summary-card strong {
  display: block;
  margin-top: 8px;
  color: #165dff;
  font-size: 30px;
  line-height: 1;
  font-weight: 900;
}

.summary-card--warn strong {
  color: #dc2626;
}

.task-panel {
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  background: #fff;
  overflow: hidden;
}

.task-toolbar {
  padding: 0 14px;
  border-bottom: 1px solid #eef2f7;
}

.task-tabs :deep(.el-tabs__header) {
  margin-bottom: 0;
}

.assignment-list {
  display: grid;
  gap: 14px;
  padding: 14px;
}

.assignment-card {
  border: 1px solid #e5e7eb;
  border-radius: 10px;
  background: #fff;
  padding: 16px;
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

.assignment-card p {
  margin: 8px 0 0;
  color: #64748b;
  font-size: 13px;
  line-height: 1.7;
}

.assignment-progress {
  min-width: 112px;
  display: grid;
  justify-items: end;
}

.assignment-progress strong {
  color: #165dff;
  font-size: 28px;
  line-height: 1;
}

.assignment-progress span {
  margin-top: 6px;
  color: #64748b;
  font-size: 12px;
}

.assignment-info {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  margin-top: 14px;
  color: #475569;
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

.state-panel {
  padding: 18px;
}

@media (max-width: 960px) {
  .task-header,
  .assignment-card header,
  .assignment-card footer,
  .scene-card,
  .case-row {
    display: grid;
    grid-template-columns: 1fr;
  }

  .join-box,
  .summary-grid,
  .notice-band {
    grid-template-columns: 1fr;
  }

  .class-task-page {
    padding: 16px;
  }
}
</style>
