<template>
  <div class="ops-overview">
    <section class="ops-overview-toolbar">
      <div>
        <strong>数据更新时间</strong>
        <span>{{ lastUpdatedText }}</span>
      </div>
      <button type="button" :disabled="loading" @click="fetchUsage">
        <OpsIcon name="refresh" />
        <span>刷新数据</span>
      </button>
    </section>

    <section class="ops-metric-grid">
      <div v-for="item in metricCards" :key="item.key" class="ops-metric-card">
        <span>{{ item.label }}</span>
        <strong>{{ item.value }}</strong>
        <p>{{ item.hint }}</p>
      </div>
    </section>

    <section class="ops-overview-grid">
      <div class="ops-panel">
        <header>
          <h3>账号结构</h3>
          <button type="button" @click="router.push('/ops/accounts')">管理账号</button>
        </header>
        <div class="ops-role-bars">
          <div v-for="item in roleCards" :key="item.role" class="ops-role-row">
            <div>
              <span>{{ item.label }}</span>
              <strong>{{ item.count }}</strong>
            </div>
            <div class="ops-role-bar">
              <i :style="{ width: `${item.percent}%` }"></i>
            </div>
          </div>
        </div>
      </div>

      <div class="ops-panel">
        <header>
          <h3>使用数据</h3>
          <button type="button" @click="router.push('/ops/usage')">查看监管</button>
        </header>
        <div class="ops-signal-list">
          <div v-for="item in usageSignals" :key="item.label">
            <span>{{ item.label }}</span>
            <strong>{{ item.value }}</strong>
            <p>{{ item.hint }}</p>
          </div>
        </div>
      </div>
    </section>

    <section class="ops-overview-grid">
      <div class="ops-panel">
        <header>
          <h3>需要跟进</h3>
          <button type="button" @click="setStudentUsage">筛选学员</button>
        </header>
        <div class="ops-risk-list">
          <button v-for="item in riskAccounts" :key="item.id" type="button" @click="openUsage(item)">
            <div>
              <strong>{{ item.username }}</strong>
              <span>{{ item.display_name || item.real_name || roleLabel(item.role) }}</span>
            </div>
            <em>{{ riskText(item) }}</em>
          </button>
          <div v-if="!riskAccounts.length" class="ops-empty">暂无明显风险项</div>
        </div>
      </div>

      <div class="ops-panel">
        <header>
          <h3>最近活跃账号</h3>
          <button type="button" @click="router.push('/ops/usage')">全部行为</button>
        </header>
        <div class="ops-active-list">
          <button v-for="item in activeAccounts" :key="item.id" type="button" @click="openUsage(item)">
            <div>
              <strong>{{ item.username }}</strong>
              <span>{{ roleLabel(item.role) }}</span>
            </div>
            <time>{{ formatTime(item.usage_changed_at || item.last_login_at) }}</time>
          </button>
          <div v-if="!activeAccounts.length" class="ops-empty">暂无活跃记录</div>
        </div>
      </div>
    </section>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import request from '../utils/request'
import OpsIcon from '../components/OpsIcon.vue'

type UsageStats = {
  normal_training_count: number
  video_training_count: number
  assignment_submission_count: number
  admin_class_count: number
  admin_assignment_count: number
  admin_video_count: number
  face_event_count: number
  speech_usage_count: number
  speech_failed_count: number
}

type UsageAccount = {
  id: number
  username: string
  role: string
  display_name?: string
  real_name?: string
  last_login_at?: string
  total_action_count: number
  usage_changed_at?: string
  stats: UsageStats
  profile?: {
    face?: {
      registered?: boolean
    }
  }
}

const router = useRouter()
const loading = ref(false)
const accounts = ref<UsageAccount[]>([])
const lastUpdated = ref<Date | null>(null)

const totals = computed(() => accounts.value.reduce((acc, item) => {
  acc.accounts += 1
  acc[item.role] = (acc[item.role] || 0) + 1
  acc.training += Number(item.stats?.normal_training_count || 0)
  acc.video += Number(item.stats?.video_training_count || 0)
  acc.assignment += Number(item.stats?.assignment_submission_count || 0)
  acc.face += Number(item.stats?.face_event_count || 0)
  acc.speech += Number(item.stats?.speech_usage_count || 0)
  acc.speechFailed += Number(item.stats?.speech_failed_count || 0)
  acc.adminOps += Number(item.stats?.admin_class_count || 0)
    + Number(item.stats?.admin_assignment_count || 0)
    + Number(item.stats?.admin_video_count || 0)
  if (item.last_login_at) acc.loggedIn += 1
  if (item.role === 'student' && item.profile?.face?.registered) acc.faceProfiles += 1
  return acc
}, {
  accounts: 0,
  admin: 0,
  student: 0,
  maintainer: 0,
  training: 0,
  video: 0,
  assignment: 0,
  face: 0,
  speech: 0,
  speechFailed: 0,
  adminOps: 0,
  loggedIn: 0,
  faceProfiles: 0,
} as Record<string, number>))

const metricCards = computed(() => [
  { key: 'accounts', label: '账号总数', value: totals.value.accounts, hint: `已登录 ${totals.value.loggedIn} 个` },
  { key: 'students', label: '学员账号', value: totals.value.student, hint: `人脸档案 ${totals.value.faceProfiles} 个` },
  { key: 'training', label: '训练使用', value: totals.value.training + totals.value.video, hint: `普通 ${totals.value.training} / 视频 ${totals.value.video}` },
  { key: 'speech', label: '语音调用', value: totals.value.speech, hint: `失败 ${totals.value.speechFailed} 次` },
])

const roleCards = computed(() => [
  { role: 'admin', label: '管理端账号', count: totals.value.admin },
  { role: 'student', label: '学员端账号', count: totals.value.student },
  { role: 'maintainer', label: '维护账号', count: totals.value.maintainer },
].map((item) => ({
  ...item,
  percent: totals.value.accounts ? Math.max(6, Math.round((item.count / totals.value.accounts) * 100)) : 0,
})))

const usageSignals = computed(() => [
  { label: '普通训练', value: totals.value.training, hint: '学员进入案件场景的累计次数' },
  { label: '视频训练', value: totals.value.video, hint: '视频训练会话累计次数' },
  { label: '作业提交', value: totals.value.assignment, hint: '学员端提交训练作业次数' },
  { label: '人脸行为', value: totals.value.face, hint: '按维护端有效口径统计' },
  { label: '管理维护动作', value: totals.value.adminOps, hint: '班级、作业和视频资源维护' },
])

const riskAccounts = computed(() => accounts.value
  .filter((item) => {
    if (item.role === 'student' && !item.last_login_at) return true
    if (item.role === 'student' && !item.profile?.face?.registered) return true
    if (Number(item.stats?.speech_failed_count || 0) > 0) return true
    return false
  })
  .sort((a, b) => Number(b.stats?.speech_failed_count || 0) - Number(a.stats?.speech_failed_count || 0))
  .slice(0, 8))

const activeAccounts = computed(() => [...accounts.value]
  .filter((item) => item.usage_changed_at || item.last_login_at)
  .sort((a, b) => new Date(b.usage_changed_at || b.last_login_at || 0).getTime() - new Date(a.usage_changed_at || a.last_login_at || 0).getTime())
  .slice(0, 8))

const lastUpdatedText = computed(() => lastUpdated.value ? lastUpdated.value.toLocaleString('zh-CN', { hour12: false }) : '-')

const roleLabel = (role: string) => {
  if (role === 'admin') return '管理端账号'
  if (role === 'student') return '学员端账号'
  if (role === 'maintainer') return '维护账号'
  return role || '-'
}

const formatTime = (value?: string) => {
  if (!value) return '-'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return '-'
  return date.toLocaleString('zh-CN', { hour12: false })
}

const riskText = (item: UsageAccount) => {
  if (Number(item.stats?.speech_failed_count || 0) > 0) return `语音失败 ${item.stats.speech_failed_count} 次`
  if (item.role === 'student' && !item.profile?.face?.registered) return '未建人脸档案'
  if (item.role === 'student' && !item.last_login_at) return '尚未登录'
  return '需要复核'
}

const fetchUsage = async () => {
  loading.value = true
  try {
    const res: any = await request.get('/ops/accounts/usage')
    accounts.value = Array.isArray(res) ? res : []
    lastUpdated.value = new Date()
  } finally {
    loading.value = false
  }
}

const openUsage = (item: UsageAccount) => {
  router.push(`/ops/usage?account=${encodeURIComponent(String(item.id))}`)
}

const setStudentUsage = () => {
  router.push('/ops/usage?role=student')
}

onMounted(fetchUsage)
</script>

<style scoped>
.ops-overview {
  display: grid;
  gap: 16px;
}

.ops-overview-toolbar,
.ops-metric-card,
.ops-panel {
  border: 1px solid #dbe3ee;
  border-radius: 8px;
  background: #fff;
}

.ops-overview-toolbar {
  min-height: 52px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 10px 14px;
}

.ops-overview-toolbar strong,
.ops-overview-toolbar span {
  display: block;
}

.ops-overview-toolbar strong {
  color: #0f172a;
  font-size: 13px;
}

.ops-overview-toolbar span {
  margin-top: 3px;
  color: #64748b;
  font-size: 12px;
}

.ops-overview-toolbar button,
.ops-panel header button {
  height: 34px;
  display: inline-flex;
  align-items: center;
  gap: 6px;
  border: 1px solid #cbd5e1;
  border-radius: 6px;
  background: #fff;
  color: #334155;
  padding: 0 12px;
  font-size: 12px;
  font-weight: 900;
}

.ops-overview-toolbar button:hover,
.ops-panel header button:hover {
  border-color: #2563eb;
  color: #1d4ed8;
  background: #eff6ff;
}

.ops-metric-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
}

.ops-metric-card {
  padding: 16px;
}

.ops-metric-card span,
.ops-role-row span,
.ops-signal-list span {
  color: #64748b;
  font-size: 12px;
  font-weight: 900;
}

.ops-metric-card strong {
  display: block;
  margin-top: 8px;
  color: #0f172a;
  font-size: 28px;
  line-height: 1;
}

.ops-metric-card p,
.ops-signal-list p {
  margin: 8px 0 0;
  color: #64748b;
  font-size: 12px;
}

.ops-overview-grid {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);
  gap: 16px;
}

.ops-panel {
  min-width: 0;
}

.ops-panel header {
  min-height: 54px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  border-bottom: 1px solid #eef2f7;
  padding: 0 16px;
}

.ops-panel h3 {
  margin: 0;
  color: #0f172a;
  font-size: 15px;
}

.ops-role-bars,
.ops-signal-list,
.ops-risk-list,
.ops-active-list {
  display: grid;
  gap: 10px;
  padding: 14px;
}

.ops-role-row {
  display: grid;
  gap: 8px;
}

.ops-role-row > div:first-child {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.ops-role-row strong,
.ops-signal-list strong {
  color: #0f172a;
}

.ops-role-bar {
  height: 8px;
  overflow: hidden;
  border-radius: 999px;
  background: #e2e8f0;
}

.ops-role-bar i {
  display: block;
  height: 100%;
  border-radius: inherit;
  background: #2563eb;
}

.ops-signal-list {
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.ops-signal-list div {
  border: 1px solid #eef2f7;
  border-radius: 6px;
  padding: 12px;
}

.ops-signal-list strong {
  display: block;
  margin-top: 6px;
  font-size: 20px;
}

.ops-risk-list button,
.ops-active-list button {
  min-height: 48px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  border: 1px solid #eef2f7;
  border-radius: 6px;
  background: #fff;
  padding: 10px 12px;
  text-align: left;
}

.ops-risk-list button:hover,
.ops-active-list button:hover {
  border-color: #2563eb;
  background: #f8fbff;
}

.ops-risk-list strong,
.ops-active-list strong {
  display: block;
  color: #0f172a;
  font-size: 13px;
}

.ops-risk-list span,
.ops-active-list span,
.ops-active-list time {
  display: block;
  margin-top: 3px;
  color: #64748b;
  font-size: 12px;
}

.ops-risk-list em {
  flex: none;
  border-radius: 999px;
  background: #fff7ed;
  color: #c2410c;
  padding: 4px 8px;
  font-size: 12px;
  font-style: normal;
  font-weight: 900;
}

.ops-empty {
  padding: 28px;
  text-align: center;
  color: #94a3b8;
  font-weight: 800;
}

@media (max-width: 1080px) {
  .ops-metric-grid,
  .ops-overview-grid {
    grid-template-columns: 1fr 1fr;
  }
}

@media (max-width: 760px) {
  .ops-metric-grid,
  .ops-overview-grid,
  .ops-signal-list {
    grid-template-columns: 1fr;
  }
}
</style>
