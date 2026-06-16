<template>
  <div class="classroom-page">
    <header class="admin-list-header">
      <div>
        <h1>班级训练</h1>
        <p>以班级为边界发布训练作业、收集评估报告，并处理未交与补交流程。</p>
      </div>
      <div class="header-actions">
        <van-button plain class="!rounded-[6px] !border-slate-200 !text-slate-600" :loading="loadingClasses" @click="fetchClasses">
          刷新
        </van-button>
        <van-button type="primary" icon="plus" class="!rounded-[6px] !border-none !bg-[#1D3557]" @click="showClassPopup = true">
          创建班级
        </van-button>
      </div>
    </header>

    <section class="classroom-grid">
      <button
        v-for="item in classes"
        :key="item.id"
        type="button"
        class="class-card"
        :class="{ 'class-card--active': selectedClassId === item.id }"
        @click="selectClass(item.id)"
      >
        <div class="class-card__head">
          <strong>{{ item.name }}</strong>
          <span>邀请码 {{ item.invite_code }}</span>
        </div>
        <p>{{ item.description || '暂无班级说明' }}</p>
        <div class="class-card__stats">
          <span>{{ item.student_count || 0 }} 名学员</span>
          <span>{{ item.assignment_count || 0 }} 个作业</span>
          <span>全员禁言</span>
        </div>
      </button>
      <button v-if="!classes.length && !loadingClasses" type="button" class="class-card class-card--empty" @click="showClassPopup = true">
        <strong>创建第一个班级</strong>
        <p>班级创建后会自动生成邀请码，学员可通过邀请码加入。</p>
      </button>
    </section>

    <div v-if="loadingDetail" class="state-card">
      <el-skeleton :rows="7" animated />
    </div>

    <section v-else-if="classDetail" class="class-workspace">
      <div class="workspace-header">
        <div>
          <span class="workspace-kicker">班级空间</span>
          <h2>{{ classDetail.classroom.name }}</h2>
          <p>{{ classDetail.classroom.description || '该班级暂未填写说明。' }}</p>
        </div>
        <div class="invite-panel">
          <span>学员加入邀请码</span>
          <strong>{{ classDetail.classroom.invite_code }}</strong>
          <van-button plain size="small" class="!rounded-[6px] !border-slate-200 !text-slate-600" @click="copyInviteCode">
            复制
          </van-button>
        </div>
      </div>

      <div class="workspace-actions">
        <van-button plain icon="friends-o" class="!rounded-[6px] !border-slate-200 !text-slate-600" @click="showStudentPopup = true">
          添加学员
        </van-button>
        <van-button plain icon="volume-o" class="!rounded-[6px] !border-slate-200 !text-slate-600" @click="showAnnouncementPopup = true">
          发布通知
        </van-button>
        <van-button type="primary" icon="description" class="!rounded-[6px] !border-none !bg-[#1D3557]" @click="showAssignmentPopup = true">
          发布作业
        </van-button>
      </div>

      <el-tabs v-model="activeTab" class="workspace-tabs">
        <el-tab-pane label="学员名单" name="students" />
        <el-tab-pane label="作业任务" name="assignments" />
        <el-tab-pane label="作业评审区" name="review" />
        <el-tab-pane label="班级通知" name="announcements" />
      </el-tabs>

      <div v-if="activeTab === 'students'" class="panel-table-wrap">
        <table class="ops-table">
          <thead>
            <tr>
              <th>学员账号</th>
              <th>加入时间</th>
              <th>身份</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="student in classDetail.students" :key="student.id">
              <td><strong>{{ student.username }}</strong></td>
              <td>{{ formatDateTime(student.joined_at) }}</td>
              <td><van-tag type="primary" plain>学员</van-tag></td>
            </tr>
          </tbody>
        </table>
        <el-empty v-if="!classDetail.students.length" description="班级内暂无学员" />
      </div>

      <div v-if="activeTab === 'assignments'" class="panel-table-wrap">
        <table class="ops-table">
          <thead>
            <tr>
              <th>作业名称</th>
              <th>关联案件</th>
              <th>截止时间</th>
              <th>补交</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="assignment in classDetail.assignments" :key="assignment.id">
              <td>
                <strong>{{ assignment.title }}</strong>
                <p>{{ assignment.instructions || '暂无训练要求说明' }}</p>
              </td>
              <td>
                <div class="tag-list">
                  <span v-for="caseItem in assignment.cases" :key="caseItem.id">{{ caseItem.title }}</span>
                </div>
              </td>
              <td>{{ formatDateTime(assignment.due_at) }}</td>
              <td>
                <van-tag :type="assignment.allow_late ? 'success' : 'default'" plain>
                  {{ assignment.allow_late ? '允许补交' : '按时截止' }}
                </van-tag>
              </td>
              <td>
                <div class="row-actions">
                  <button type="button" @click="openReview(assignment)">评审</button>
                  <button type="button" @click="toggleAssignmentLate(assignment)">
                    {{ assignment.allow_late ? '关闭补交' : '允许补交' }}
                  </button>
                  <button type="button" @click="extendAssignmentDue(assignment)">延期</button>
                </div>
              </td>
            </tr>
          </tbody>
        </table>
        <el-empty v-if="!classDetail.assignments.length" description="暂无作业任务" />
      </div>

      <div v-if="activeTab === 'review'" class="review-panel">
        <div class="review-toolbar">
          <label>
            <span>评审作业</span>
            <select v-model.number="selectedReviewAssignmentId" @change="fetchReview">
              <option :value="0">请选择作业</option>
              <option v-for="assignment in classDetail.assignments" :key="assignment.id" :value="assignment.id">
                {{ assignment.title }}
              </option>
            </select>
          </label>
          <div v-if="reviewData" class="review-summary">
            <span>已交 {{ reviewData.summary.submitted_count }}</span>
            <span>进行中 {{ reviewData.summary.in_progress_count }}</span>
            <span>未提交 {{ reviewData.summary.unsubmitted_count }}</span>
          </div>
        </div>

        <div v-if="loadingReview" class="state-card state-card--flat">
          <el-skeleton :rows="6" animated />
        </div>
        <div v-else-if="reviewData" class="panel-table-wrap">
          <table class="ops-table review-table">
            <thead>
              <tr>
                <th>学员</th>
                <th>状态</th>
                <th>完成进度</th>
                <th>平均分</th>
                <th>最近提交</th>
                <th>补交策略</th>
                <th>操作</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="row in reviewData.rows" :key="row.student.id">
                <td><strong>{{ row.student.username }}</strong></td>
                <td><van-tag :type="reviewStatusType(row.status)" plain>{{ reviewStatusLabel(row.status) }}</van-tag></td>
                <td>{{ row.completed_count }}/{{ row.required_count }}</td>
                <td class="score-cell">{{ row.score_avg ?? '--' }}</td>
                <td>{{ formatDateTime(row.last_submitted_at) }}</td>
                <td>
                  <span>{{ row.allow_late ? '可补交' : '不可补交' }}</span>
                  <small>截止 {{ formatDateTime(row.effective_due_at) }}</small>
                </td>
                <td>
                  <div class="row-actions">
                    <button type="button" :disabled="!firstSubmission(row)" @click="openSubmission(row)">查看</button>
                    <button type="button" @click="setStudentLate(row, true)">允许补交</button>
                    <button type="button" @click="setStudentLate(row, false)">拒绝补交</button>
                    <button type="button" @click="extendStudentDue(row)">延期</button>
                  </div>
                </td>
              </tr>
            </tbody>
          </table>
          <el-empty v-if="!reviewData.rows.length" description="当前作业暂无可评审学员" />
        </div>
        <el-empty v-else description="请选择一个作业进入评审区" />
      </div>

      <div v-if="activeTab === 'announcements'" class="announcement-list">
        <article v-for="item in classDetail.announcements" :key="item.id" class="notice-item">
          <div>
            <strong>{{ item.title }}</strong>
            <span>{{ formatDateTime(item.created_at) }}</span>
          </div>
          <p>{{ item.content || '无正文' }}</p>
        </article>
        <el-empty v-if="!classDetail.announcements.length" description="暂无班级通知" />
      </div>
    </section>

    <van-popup v-model:show="showClassPopup" teleport="body" :style="popupStyle">
      <div class="popup-panel">
        <header>
          <h3>创建班级</h3>
          <van-icon name="cross" @click="showClassPopup = false" />
        </header>
        <label class="field-block">
          <span>班级名称</span>
          <input v-model.trim="classForm.name" type="text" placeholder="例如 2026 春季接警训练班" />
        </label>
        <label class="field-block">
          <span>班级说明</span>
          <textarea v-model.trim="classForm.description" rows="4" placeholder="说明训练对象、周期或教学安排" />
        </label>
        <van-button block type="primary" :loading="savingClass" class="!rounded-[6px] !border-none !bg-[#1D3557]" @click="createClass">
          创建
        </van-button>
      </div>
    </van-popup>

    <van-popup v-model:show="showStudentPopup" teleport="body" :style="popupStyle">
      <div class="popup-panel">
        <header>
          <h3>添加学员</h3>
          <van-icon name="cross" @click="showStudentPopup = false" />
        </header>
        <label class="field-block">
          <span>学员账号</span>
          <textarea v-model.trim="studentForm.usernames" rows="5" placeholder="每行一个学员账号，例如 student001" />
        </label>
        <van-button block type="primary" :loading="savingStudents" class="!rounded-[6px] !border-none !bg-[#1D3557]" @click="addStudents">
          添加到班级
        </van-button>
      </div>
    </van-popup>

    <van-popup v-model:show="showAnnouncementPopup" teleport="body" :style="popupStyle">
      <div class="popup-panel">
        <header>
          <h3>发布通知</h3>
          <van-icon name="cross" @click="showAnnouncementPopup = false" />
        </header>
        <label class="field-block">
          <span>标题</span>
          <input v-model.trim="announcementForm.title" type="text" placeholder="例如 第二次作业补交提醒" />
        </label>
        <label class="field-block">
          <span>内容</span>
          <textarea v-model.trim="announcementForm.content" rows="5" placeholder="通知内容仅管理员可发布，学员端只读展示。" />
        </label>
        <van-button block type="primary" :loading="savingAnnouncement" class="!rounded-[6px] !border-none !bg-[#1D3557]" @click="createAnnouncement">
          发布
        </van-button>
      </div>
    </van-popup>

    <van-popup v-model:show="showAssignmentPopup" teleport="body" :style="{ ...popupStyle, width: 'min(760px, 96vw)' }">
      <div class="popup-panel">
        <header>
          <h3>发布训练作业</h3>
          <van-icon name="cross" @click="showAssignmentPopup = false" />
        </header>
        <div class="form-grid">
          <label class="field-block">
            <span>作业名称</span>
            <input v-model.trim="assignmentForm.title" type="text" placeholder="例如 第三周接警专项训练" />
          </label>
          <label class="field-block">
            <span>截止时间</span>
            <input v-model="assignmentForm.dueAt" type="datetime-local" />
          </label>
        </div>
        <label class="checkline">
          <input v-model="assignmentForm.allowLate" type="checkbox" />
          允许截止后补交
        </label>
        <label class="field-block">
          <span>训练要求说明</span>
          <textarea v-model.trim="assignmentForm.instructions" rows="3" placeholder="写明训练重点、提交要求或复盘方向" />
        </label>
        <label class="field-block">
          <span>评分规则</span>
          <textarea v-model.trim="assignmentForm.scoringRule" rows="3" placeholder="默认使用系统 Adaptive V1 评估，也可补充自定义规则。" />
        </label>
        <div class="field-block">
          <span>关联案件</span>
          <div class="case-picker">
            <label v-for="caseItem in cases" :key="caseItem.id" class="case-option">
              <input v-model="assignmentForm.caseIds" type="checkbox" :value="caseItem.id" />
              <strong>{{ caseItem.title }}</strong>
              <small>{{ caseItem.case_type || '未分类' }}</small>
            </label>
          </div>
        </div>
        <van-button block type="primary" :loading="savingAssignment" class="!rounded-[6px] !border-none !bg-[#1D3557]" @click="createAssignment">
          发布作业
        </van-button>
      </div>
    </van-popup>

    <van-popup v-model:show="showSubmissionPopup" teleport="body" :style="{ width: 'min(920px, 96vw)', maxHeight: '92vh', borderRadius: '12px', overflow: 'hidden' }">
      <div class="submission-panel">
        <header>
          <div>
            <h3>提交详情</h3>
            <p v-if="submissionDetail">{{ submissionDetail.student.username }} · {{ submissionDetail.case.title }} · {{ submissionDetail.scene.name }}</p>
          </div>
          <van-icon name="cross" @click="showSubmissionPopup = false" />
        </header>
        <div v-if="loadingSubmission" class="state-card state-card--flat">
          <el-skeleton :rows="8" animated />
        </div>
        <div v-else-if="submissionDetail" class="submission-body">
          <aside>
            <div class="score-box">
              <span>系统评分</span>
              <strong>{{ submissionDetail.submission.score ?? '--' }}</strong>
            </div>
            <p>提交时间：{{ formatDateTime(submissionDetail.submission.submitted_at) }}</p>
            <p>状态：{{ reviewStatusLabel(submissionDetail.submission.status) }}</p>
          </aside>
          <main>
            <section>
              <h4>对话记录</h4>
              <div class="message-list">
                <div v-for="message in submissionDetail.messages" :key="message.id" class="message-item" :class="`message-item--${message.role}`">
                  <span>{{ message.speaker_name || roleLabel(message.role) }}</span>
                  <p>{{ message.content }}</p>
                </div>
              </div>
            </section>
            <section>
              <h4>AI评估报告</h4>
              <pre>{{ formatEvaluation(submissionDetail.submission.evaluation_result || submissionDetail.session.evaluation_result) }}</pre>
            </section>
          </main>
        </div>
      </div>
    </van-popup>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { showToast } from 'vant'
import request from '../utils/request'

const classes = ref<any[]>([])
const cases = ref<any[]>([])
const classDetail = ref<any>(null)
const reviewData = ref<any>(null)
const submissionDetail = ref<any>(null)
const selectedClassId = ref<number | null>(null)
const selectedReviewAssignmentId = ref(0)
const activeTab = ref<'students' | 'assignments' | 'review' | 'announcements'>('students')

const loadingClasses = ref(false)
const loadingDetail = ref(false)
const loadingReview = ref(false)
const loadingSubmission = ref(false)
const savingClass = ref(false)
const savingStudents = ref(false)
const savingAnnouncement = ref(false)
const savingAssignment = ref(false)

const showClassPopup = ref(false)
const showStudentPopup = ref(false)
const showAnnouncementPopup = ref(false)
const showAssignmentPopup = ref(false)
const showSubmissionPopup = ref(false)

const classForm = reactive({ name: '', description: '' })
const studentForm = reactive({ usernames: '' })
const announcementForm = reactive({ title: '', content: '' })
const assignmentForm = reactive({
  title: '',
  caseIds: [] as number[],
  dueAt: '',
  instructions: '',
  scoringRule: '系统默认评分；系统完成对话记录归档与 Adaptive V1 评估。',
  allowLate: false,
})

const popupStyle = {
  width: 'min(560px, 96vw)',
  borderRadius: '12px',
  overflow: 'hidden',
}

const selectedClass = computed(() => classes.value.find((item) => item.id === selectedClassId.value))

const fetchClasses = async () => {
  loadingClasses.value = true
  try {
    const res: any = await request.get('/classes')
    classes.value = Array.isArray(res) ? res : []
    if (!selectedClassId.value && classes.value.length) {
      selectedClassId.value = classes.value[0].id
      await fetchClassDetail()
    } else if (selectedClassId.value) {
      await fetchClassDetail()
    }
  } finally {
    loadingClasses.value = false
  }
}

const fetchCases = async () => {
  const res: any = await request.get('/cases/')
  cases.value = Array.isArray(res) ? res : []
}

const selectClass = async (classId: number) => {
  selectedClassId.value = classId
  reviewData.value = null
  selectedReviewAssignmentId.value = 0
  await fetchClassDetail()
}

const fetchClassDetail = async () => {
  if (!selectedClassId.value) return
  loadingDetail.value = true
  try {
    classDetail.value = await request.get(`/classes/${selectedClassId.value}`)
  } finally {
    loadingDetail.value = false
  }
}

const createClass = async () => {
  if (!classForm.name.trim()) {
    showToast('请输入班级名称')
    return
  }
  savingClass.value = true
  try {
    const res: any = await request.post('/classes', {
      name: classForm.name.trim(),
      description: classForm.description.trim(),
    })
    showToast({ type: 'success', message: '班级已创建' })
    classForm.name = ''
    classForm.description = ''
    showClassPopup.value = false
    await fetchClasses()
    selectedClassId.value = res.id
    await fetchClassDetail()
  } finally {
    savingClass.value = false
  }
}

const addStudents = async () => {
  if (!selectedClassId.value) return
  const usernames = studentForm.usernames
    .split(/\r?\n|,|，/)
    .map((item) => item.trim())
    .filter(Boolean)
  if (!usernames.length) {
    showToast('请输入学员账号')
    return
  }
  savingStudents.value = true
  try {
    const res: any = await request.post(`/classes/${selectedClassId.value}/students`, { usernames })
    showToast({ type: 'success', message: `已匹配 ${res.matched_count || 0} 名学员` })
    studentForm.usernames = ''
    showStudentPopup.value = false
    await fetchClassDetail()
  } finally {
    savingStudents.value = false
  }
}

const createAnnouncement = async () => {
  if (!selectedClassId.value) return
  if (!announcementForm.title.trim()) {
    showToast('请输入通知标题')
    return
  }
  savingAnnouncement.value = true
  try {
    await request.post(`/classes/${selectedClassId.value}/announcements`, {
      title: announcementForm.title.trim(),
      content: announcementForm.content.trim(),
      category: 'notice',
    })
    showToast({ type: 'success', message: '通知已发布' })
    announcementForm.title = ''
    announcementForm.content = ''
    showAnnouncementPopup.value = false
    await fetchClassDetail()
  } finally {
    savingAnnouncement.value = false
  }
}

const createAssignment = async () => {
  if (!selectedClassId.value) return
  if (!assignmentForm.title.trim()) {
    showToast('请输入作业名称')
    return
  }
  if (!assignmentForm.caseIds.length) {
    showToast('请选择关联案件')
    return
  }
  savingAssignment.value = true
  try {
    const res: any = await request.post(`/classes/${selectedClassId.value}/assignments`, {
      title: assignmentForm.title.trim(),
      case_ids: assignmentForm.caseIds,
      due_at: assignmentForm.dueAt || null,
      instructions: assignmentForm.instructions.trim(),
      scoring_rule: assignmentForm.scoringRule.trim(),
      allow_late: assignmentForm.allowLate,
    })
    showToast({ type: 'success', message: '作业已发布' })
    assignmentForm.title = ''
    assignmentForm.caseIds = []
    assignmentForm.dueAt = ''
    assignmentForm.instructions = ''
    assignmentForm.scoringRule = '系统默认评分；系统完成对话记录归档与 Adaptive V1 评估。'
    assignmentForm.allowLate = false
    showAssignmentPopup.value = false
    await fetchClassDetail()
    openReview(res)
  } finally {
    savingAssignment.value = false
  }
}

const openReview = async (assignment: any) => {
  activeTab.value = 'review'
  selectedReviewAssignmentId.value = Number(assignment.id)
  await fetchReview()
}

const fetchReview = async () => {
  if (!selectedClassId.value || !selectedReviewAssignmentId.value) {
    reviewData.value = null
    return
  }
  loadingReview.value = true
  try {
    reviewData.value = await request.get(`/classes/${selectedClassId.value}/assignments/${selectedReviewAssignmentId.value}/review`)
  } finally {
    loadingReview.value = false
  }
}

const updateAssignmentPolicy = async (assignment: any, payload: Record<string, unknown>) => {
  if (!selectedClassId.value) return
  await request.post(`/classes/${selectedClassId.value}/assignments/${assignment.id}/late-policy`, payload)
  showToast({ type: 'success', message: '作业策略已更新' })
  await fetchClassDetail()
  if (selectedReviewAssignmentId.value === assignment.id) await fetchReview()
}

const toggleAssignmentLate = async (assignment: any) => {
  await updateAssignmentPolicy(assignment, { allow_late: !assignment.allow_late })
}

const extendAssignmentDue = async (assignment: any) => {
  const value = window.prompt('请输入新的全班截止时间（格式：2026-06-30T18:00）', toDatetimeInput(assignment.due_at))
  if (value === null) return
  await updateAssignmentPolicy(assignment, { due_at: value || null })
}

const setStudentLate = async (row: any, allowLate: boolean) => {
  if (!selectedClassId.value || !selectedReviewAssignmentId.value) return
  await request.post(`/classes/${selectedClassId.value}/assignments/${selectedReviewAssignmentId.value}/students/${row.student.id}/override`, {
    allow_late: allowLate,
  })
  showToast({ type: 'success', message: allowLate ? '已允许该学员补交' : '已拒绝该学员补交' })
  await fetchReview()
}

const extendStudentDue = async (row: any) => {
  if (!selectedClassId.value || !selectedReviewAssignmentId.value) return
  const value = window.prompt('请输入该学员新的截止时间（格式：2026-06-30T18:00）', toDatetimeInput(row.effective_due_at))
  if (value === null) return
  await request.post(`/classes/${selectedClassId.value}/assignments/${selectedReviewAssignmentId.value}/students/${row.student.id}/override`, {
    due_at: value || null,
    allow_late: true,
  })
  showToast({ type: 'success', message: '已更新该学员截止时间' })
  await fetchReview()
}

const firstSubmission = (row: any) => {
  for (const caseRow of row?.cases || []) {
    if (caseRow?.submission?.id) return caseRow.submission
  }
  return null
}

const openSubmission = async (row: any) => {
  if (!selectedClassId.value || !selectedReviewAssignmentId.value) return
  const submission = firstSubmission(row)
  if (!submission) {
    showToast('该学员暂无可查看提交')
    return
  }
  showSubmissionPopup.value = true
  loadingSubmission.value = true
  submissionDetail.value = null
  try {
    submissionDetail.value = await request.get(
      `/classes/${selectedClassId.value}/assignments/${selectedReviewAssignmentId.value}/submissions/${submission.id}`,
    )
  } finally {
    loadingSubmission.value = false
  }
}

const copyInviteCode = async () => {
  const code = selectedClass.value?.invite_code || classDetail.value?.classroom?.invite_code
  if (!code) return
  try {
    await navigator.clipboard.writeText(code)
    showToast({ type: 'success', message: '邀请码已复制' })
  } catch {
    showToast(`邀请码：${code}`)
  }
}

const reviewStatusLabel = (status: string) => {
  const map: Record<string, string> = {
    submitted: '已提交',
    completed: '已完成',
    late: '迟交',
    in_progress: '训练中',
    evaluating: '评估中',
    pending: '待完成',
    unsubmitted: '未提交',
    missing: '未提交',
  }
  return map[status] || status || '--'
}

const reviewStatusType = (status: string) => {
  if (status === 'submitted' || status === 'completed') return 'success'
  if (status === 'late' || status === 'in_progress' || status === 'evaluating') return 'warning'
  if (status === 'unsubmitted' || status === 'missing') return 'danger'
  return 'default'
}

const roleLabel = (role: string) => {
  if (role === 'user') return '学员'
  if (role === 'assistant' || role === 'ai') return 'AI角色'
  if (role === 'action') return '训练动作'
  return role || '系统'
}

const formatEvaluation = (value: any) => {
  if (!value) return '暂无评估报告'
  return JSON.stringify(value, null, 2)
}

const toDatetimeInput = (value: any) => {
  if (!value) return ''
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return String(value)
  const pad = (num: number) => String(num).padStart(2, '0')
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}`
}

const formatDateTime = (value: any) => {
  if (!value) return '未设置'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return String(value)
  const pad = (num: number) => String(num).padStart(2, '0')
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())} ${pad(date.getHours())}:${pad(date.getMinutes())}`
}

onMounted(async () => {
  await Promise.all([fetchCases(), fetchClasses()])
})
</script>

<style scoped>
.classroom-page {
  display: grid;
  gap: 16px;
  padding-bottom: 28px;
}

.admin-list-header,
.workspace-header,
.workspace-actions,
.review-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
}

.admin-list-header {
  padding: 18px 20px;
  border: 1px solid var(--police-border);
  border-radius: var(--police-radius-lg);
  background: #fff;
}

.admin-list-header h1,
.workspace-header h2 {
  margin: 0;
  color: var(--police-text-primary);
  font-weight: 900;
}

.admin-list-header h1 {
  font-size: 22px;
}

.admin-list-header p,
.workspace-header p {
  margin: 5px 0 0;
  color: var(--police-text-muted);
  font-size: 13px;
}

.header-actions,
.workspace-actions,
.row-actions,
.review-summary {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.classroom-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(260px, 1fr));
  gap: 12px;
}

.class-card {
  min-height: 132px;
  border: 1px solid var(--police-border);
  border-radius: 8px;
  background: #fff;
  padding: 16px;
  text-align: left;
  cursor: pointer;
  transition: border-color 0.16s, box-shadow 0.16s;
}

.class-card:hover,
.class-card--active {
  border-color: #1d4ed8;
  box-shadow: 0 6px 20px rgba(29, 78, 216, 0.12);
}

.class-card__head {
  display: flex;
  justify-content: space-between;
  gap: 12px;
}

.class-card strong {
  color: #0f172a;
  font-size: 16px;
}

.class-card__head span {
  color: #1d4ed8;
  font-size: 12px;
  font-weight: 800;
  white-space: nowrap;
}

.class-card p {
  min-height: 40px;
  margin: 10px 0 12px;
  color: #64748b;
  font-size: 13px;
  line-height: 1.6;
}

.class-card__stats {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.class-card__stats span,
.tag-list span {
  display: inline-flex;
  align-items: center;
  border-radius: 999px;
  background: #f1f5f9;
  padding: 4px 9px;
  color: #475569;
  font-size: 12px;
  font-weight: 800;
}

.class-card--empty {
  border-style: dashed;
}

.class-workspace,
.state-card {
  border: 1px solid var(--police-border);
  border-radius: 8px;
  background: #fff;
  padding: 18px;
}

.workspace-header {
  align-items: flex-start;
  padding-bottom: 16px;
  border-bottom: 1px solid #eef2f7;
}

.workspace-kicker {
  color: #1d4ed8;
  font-size: 12px;
  font-weight: 900;
}

.invite-panel {
  display: grid;
  grid-template-columns: auto auto auto;
  align-items: center;
  gap: 10px;
  border: 1px solid #dbeafe;
  border-radius: 8px;
  background: #f8fbff;
  padding: 10px 12px;
}

.invite-panel span {
  color: #64748b;
  font-size: 12px;
  font-weight: 800;
}

.invite-panel strong {
  color: #1d4ed8;
  letter-spacing: 0.08em;
}

.workspace-actions {
  justify-content: flex-start;
  margin: 14px 0;
}

.workspace-tabs {
  border-top: 1px solid #eef2f7;
  padding-top: 4px;
}

.panel-table-wrap {
  overflow-x: auto;
}

.ops-table {
  width: 100%;
  min-width: 860px;
  border-collapse: collapse;
}

.ops-table th,
.ops-table td {
  border-bottom: 1px solid #eef2f7;
  padding: 12px 14px;
  text-align: left;
  vertical-align: top;
  font-size: 13px;
}

.ops-table th {
  background: #f8fafc;
  color: #475569;
  font-weight: 900;
}

.ops-table td strong {
  color: #0f172a;
}

.ops-table td p,
.ops-table td small {
  display: block;
  margin: 4px 0 0;
  color: #64748b;
  line-height: 1.6;
}

.tag-list {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.row-actions button {
  height: 28px;
  border: 1px solid #cbd5e1;
  border-radius: 6px;
  background: #fff;
  color: #1d3557;
  font-size: 12px;
  font-weight: 800;
  cursor: pointer;
}

.row-actions button:disabled {
  opacity: 0.45;
  cursor: not-allowed;
}

.review-toolbar {
  margin: 4px 0 12px;
}

.review-toolbar label {
  display: flex;
  align-items: center;
  gap: 8px;
  color: #334155;
  font-size: 13px;
  font-weight: 900;
}

.review-toolbar select {
  height: 34px;
  min-width: 260px;
  border: 1px solid #cbd5e1;
  border-radius: 6px;
  padding: 0 10px;
}

.review-summary span {
  border-radius: 999px;
  background: #f1f5f9;
  padding: 5px 10px;
  color: #475569;
  font-size: 12px;
  font-weight: 900;
}

.score-cell {
  color: #1d4ed8;
  font-weight: 900;
}

.announcement-list {
  display: grid;
  gap: 10px;
}

.notice-item {
  border: 1px solid #eef2f7;
  border-radius: 8px;
  padding: 12px 14px;
  background: #fbfdff;
}

.notice-item div {
  display: flex;
  justify-content: space-between;
  gap: 12px;
}

.notice-item strong {
  color: #0f172a;
}

.notice-item span,
.notice-item p {
  margin: 0;
  color: #64748b;
  font-size: 13px;
}

.popup-panel {
  display: grid;
  gap: 14px;
  padding: 18px;
  max-height: 88vh;
  overflow: auto;
  background: #fff;
}

.popup-panel header,
.submission-panel header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  border-bottom: 1px solid #eef2f7;
  padding-bottom: 12px;
}

.popup-panel h3,
.submission-panel h3 {
  margin: 0;
  color: #0f172a;
  font-size: 18px;
  font-weight: 900;
}

.field-block {
  display: grid;
  gap: 7px;
}

.field-block span {
  color: #334155;
  font-size: 13px;
  font-weight: 900;
}

.field-block input,
.field-block textarea,
.review-toolbar select {
  width: 100%;
  border: 1px solid #dbe3ee;
  border-radius: 6px;
  background: #fff;
  padding: 9px 10px;
  color: #0f172a;
  font-size: 13px;
  outline: none;
}

.form-grid {
  display: grid;
  grid-template-columns: 1fr 220px;
  gap: 12px;
}

.checkline {
  display: flex;
  align-items: center;
  gap: 8px;
  color: #334155;
  font-size: 13px;
  font-weight: 800;
}

.case-picker {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 8px;
}

.case-option {
  display: grid;
  grid-template-columns: 18px minmax(0, 1fr) auto;
  align-items: center;
  gap: 8px;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  padding: 10px;
  color: #334155;
}

.case-option strong {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 13px;
}

.case-option small {
  color: #64748b;
  font-size: 12px;
}

.submission-panel {
  display: grid;
  max-height: 92vh;
  background: #fff;
}

.submission-panel header {
  padding: 16px 18px;
}

.submission-panel header p {
  margin: 4px 0 0;
  color: #64748b;
  font-size: 13px;
}

.submission-body {
  display: grid;
  grid-template-columns: 220px minmax(0, 1fr);
  gap: 18px;
  overflow: auto;
  padding: 18px;
}

.submission-body aside {
  border: 1px solid #eef2f7;
  border-radius: 8px;
  padding: 14px;
  height: fit-content;
  background: #f8fafc;
}

.score-box {
  display: grid;
  gap: 6px;
  margin-bottom: 12px;
}

.score-box span,
.submission-body aside p {
  margin: 0 0 8px;
  color: #64748b;
  font-size: 13px;
}

.score-box strong {
  color: #dc2626;
  font-size: 42px;
  line-height: 1;
}

.submission-body main {
  display: grid;
  gap: 16px;
}

.submission-body h4 {
  margin: 0 0 10px;
  color: #0f172a;
  font-size: 15px;
  font-weight: 900;
}

.message-list {
  display: grid;
  gap: 8px;
}

.message-item {
  border: 1px solid #eef2f7;
  border-radius: 8px;
  padding: 10px 12px;
  background: #fff;
}

.message-item--user {
  border-color: #bfdbfe;
  background: #eff6ff;
}

.message-item span {
  color: #334155;
  font-size: 12px;
  font-weight: 900;
}

.message-item p {
  margin: 5px 0 0;
  color: #0f172a;
  font-size: 14px;
  line-height: 1.7;
}

pre {
  max-height: 360px;
  overflow: auto;
  border: 1px solid #eef2f7;
  border-radius: 8px;
  background: #0f172a;
  padding: 14px;
  color: #e5e7eb;
  font-size: 12px;
  line-height: 1.6;
  white-space: pre-wrap;
}

.state-card--flat {
  border: none;
  padding: 12px;
}

@media (max-width: 900px) {
  .admin-list-header,
  .workspace-header,
  .review-toolbar,
  .submission-body {
    grid-template-columns: 1fr;
    display: grid;
  }

  .invite-panel,
  .form-grid,
  .case-picker {
    grid-template-columns: 1fr;
  }
}
</style>
