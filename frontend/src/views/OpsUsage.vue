<template>
  <div class="ops-usage">
    <section class="ops-usage-toolbar">
      <div class="ops-tabs">
        <button type="button" :class="{ active: roleFilter === 'admin' }" @click="setRole('admin')">管理端账号</button>
        <button type="button" :class="{ active: roleFilter === 'student' }" @click="setRole('student')">学员端账号</button>
        <button type="button" :class="{ active: roleFilter === '' }" @click="setRole('')">全部</button>
      </div>
      <label class="ops-usage-search">
        <OpsIcon name="search" />
        <input v-model.trim="keyword" placeholder="搜索账号" @keyup.enter="fetchUsage" />
      </label>
      <button type="button" class="ops-refresh" :disabled="loading" @click="fetchUsage">
        <OpsIcon name="refresh" />
        <span>刷新</span>
      </button>
    </section>

    <section class="ops-usage-grid">
      <div class="ops-account-panel">
        <header>
          <h3>账号列表</h3>
          <span>{{ usageAccounts.length }} 个</span>
        </header>
        <div class="ops-account-list">
          <button
            v-for="item in usageAccounts"
            :key="item.id"
            type="button"
            class="ops-account-card"
            :class="{ active: selectedId === item.id }"
            @click="selectAccount(item)"
          >
            <div>
              <strong>{{ item.username }}</strong>
              <span>{{ item.display_name || item.real_name || '-' }}</span>
            </div>
            <i :class="`role-${item.role}`">{{ roleLabel(item.role) }}</i>
            <em>{{ item.total_action_count }} 条行为</em>
          </button>
          <div v-if="!loading && !usageAccounts.length" class="ops-empty">暂无账号</div>
        </div>
      </div>

      <div class="ops-detail-panel">
        <header>
          <div>
            <h3>{{ detail?.username || '选择账号查看监管详情' }}</h3>
            <p v-if="detail">{{ roleLabel(detail.role) }} / 最后登录：{{ formatTime(detail.last_login_at) }}</p>
          </div>
          <span class="ops-live">行为变化后自动刷新</span>
        </header>

        <template v-if="detail">
          <div class="ops-stat-grid">
            <div><span>普通训练</span><strong>{{ detail.stats.normal_training_count }}</strong></div>
            <div><span>视频训练</span><strong>{{ detail.stats.video_training_count }}</strong></div>
            <div><span>作业提交</span><strong>{{ detail.stats.assignment_submission_count }}</strong></div>
            <div><span>人脸核验</span><strong>{{ detail.stats.face_event_count }}</strong></div>
            <div><span>语音识别</span><strong>{{ detail.stats.speech_usage_count }}</strong></div>
          </div>

          <section class="ops-profile-grid">
            <div>
              <span>账号档案</span>
              <strong>{{ profileName }}</strong>
              <p>{{ joinText(detail.profile?.unit, detail.profile?.department) }}</p>
              <p>{{ joinText(detail.profile?.phone, detail.profile?.email) }}</p>
            </div>
            <div>
              <span>管理端开通账号</span>
              <strong>{{ detail.profile?.opened_accounts?.length || 0 }}</strong>
              <p>{{ openedAccountPreview }}</p>
            </div>
          </section>

          <section class="ops-face-card">
            <div class="ops-face-photo-list">
              <div v-for="(url, index) in faceImageUrls" :key="url" class="ops-face-photo">
                <img :src="url" :alt="`人脸档案照片 ${index + 1}`" loading="lazy" />
              </div>
              <div v-if="!faceImageUrls.length" class="ops-face-photo ops-face-photo--empty">
                <span>暂无照片</span>
              </div>
            </div>
            <div>
              <span>人脸档案</span>
              <strong :class="detail.profile?.face?.registered ? 'ok' : 'warn'">{{ detail.profile?.face?.registered ? '已建档' : '未建档' }}</strong>
              <p>建档时间：{{ formatTime(detail.profile?.face?.created_at) }}</p>
              <p>更新时间：{{ formatTime(detail.profile?.face?.updated_at) }}</p>
              <p>最近核验：{{ statusLabel(detail.profile?.face?.latest_status) }}</p>
              <p>相似度：{{ detail.profile?.face?.latest_similarity ?? '-' }}</p>
              <p>照片样本：{{ detail.profile?.face?.sample_count ?? 0 }} 张</p>
            </div>
          </section>

          <div class="ops-category-tabs">
            <button
              v-for="item in categoryTabs"
              :key="item.key"
              type="button"
              :class="{ active: activeCategory === item.key }"
              @click="activeCategory = item.key"
            >
              {{ item.label }} <span>{{ categoryCount(item.key) }}</span>
            </button>
          </div>

          <div class="ops-activity-list">
            <div v-for="(item, index) in visibleActivities" :key="`${item.created_at}-${index}`" class="ops-activity-item">
              <time>{{ formatTime(item.created_at) }}</time>
              <div>
                <strong>{{ activityTitle(item) }}</strong>
                <span>{{ item.module }} · {{ actionLabel(item.action) }} · {{ detailText(item.detail) }}</span>
              </div>
            </div>
            <div v-if="!visibleActivities.length" class="ops-empty">该分类暂无可追踪行为</div>
          </div>
        </template>

        <div v-else class="ops-empty ops-empty--detail">点击左侧账号后，将展示该账号在管理端和学员端的合并行为。</div>
      </div>
    </section>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import request from '../utils/request'
import { resolveMediaUrl } from '../utils/media'
import OpsIcon from '../components/OpsIcon.vue'

type UsageStats = {
  normal_training_count: number
  normal_finished_count: number
  training_message_count: number
  training_artifact_count: number
  video_training_count: number
  video_finished_count: number
  video_artifact_count: number
  assignment_submission_count: number
  class_join_count: number
  admin_class_count: number
  admin_assignment_count: number
  admin_announcement_count: number
  admin_video_count: number
  ops_action_count: number
  face_event_count: number
  speech_usage_count: number
  speech_failed_count: number
}

type UsageActivity = {
  module: string
  action: string
  title: string
  created_at?: string
  detail?: Record<string, any>
}

type UsageAccount = {
  id: number
  username: string
  role: string
  display_name?: string
  real_name?: string
  last_login_at?: string
  total_action_count: number
  stats: UsageStats
  usage_version?: string
  usage_changed_at?: string
  activities?: UsageActivity[]
  activity_categories?: Record<string, UsageActivity[]>
  profile?: {
    real_name?: string
    display_name?: string
    phone?: string
    email?: string
    unit?: string
    department?: string
    face?: {
      registered: boolean
      created_at?: string
      updated_at?: string
      image_url?: string
      sample_images?: string[]
      sample_count?: number
      latest_status?: string
      latest_similarity?: number
    }
    opened_accounts?: Array<{ username?: string; role?: string; action?: string; created_at?: string }>
  }
}

const route = useRoute()
const initialRole = route.query.role === 'student' || route.query.role === 'admin' ? route.query.role : ''
const initialAccountId = Number(route.query.account || 0) || null
const loading = ref(false)
const roleFilter = ref<'admin' | 'student' | ''>(initialRole as 'admin' | 'student' | '')
const keyword = ref('')
const usageAccounts = ref<UsageAccount[]>([])
const selectedId = ref<number | null>(null)
const detail = ref<UsageAccount | null>(null)
const activeCategory = ref('admin')
const globalVersion = ref('')
const usageVersions = ref<Record<number, string>>({})
const usageListCache = new Map<string, UsageAccount[]>()
let refreshTimer: number | undefined
let versionTimer: number | undefined
let versionPolling = false
let usageRequestId = 0
let detailRequestId = 0
let initialAccountHandled = false
const VERSION_POLL_INTERVAL_MS = 10000

const categoryTabs = [
  { key: 'admin', label: '管理端' },
  { key: 'training', label: '训练' },
  { key: 'assignment', label: '作业' },
  { key: 'video', label: '视频训练' },
  { key: 'face', label: '人脸' },
  { key: 'speech', label: '语音识别' },
  { key: 'audit', label: '账号审计' },
]

const visibleActivities = computed(() => detail.value?.activity_categories?.[activeCategory.value] || [])
const profileName = computed(() => detail.value?.profile?.display_name || detail.value?.profile?.real_name || detail.value?.username || '-')
const openedAccountPreview = computed(() => {
  const items = detail.value?.profile?.opened_accounts || []
  if (!items.length) return '暂无开通记录'
  return items.slice(0, 3).map((item) => item.username).filter(Boolean).join('、')
})
const withCacheBuster = (url: string, version?: string) => {
  if (!url || url.startsWith('data:') || url.startsWith('blob:')) return url
  const separator = url.includes('?') ? '&' : '?'
  return `${url}${separator}v=${encodeURIComponent(version || String(Date.now()))}`
}

const faceImageUrls = computed(() => {
  const face = detail.value?.profile?.face
  const version = face?.updated_at || detail.value?.usage_version
  const urls = [face?.image_url, ...(face?.sample_images || [])]
    .map((url) => withCacheBuster(resolveMediaUrl(url), version))
    .filter(Boolean)
  return Array.from(new Set(urls))
})

const roleLabel = (role: string) => {
  if (role === 'admin') return '管理端账号'
  if (role === 'student') return '学员端账号'
  if (role === 'maintainer') return '维护账号'
  return role || '-'
}

const actionLabel = (action: string) => {
  const labels: Record<string, string> = {
    login: '登录',
    create_class: '创建班级',
    create_assignment: '发布作业',
    create_announcement: '发布公告',
    upload_video: '上传视频',
    training_session: '普通训练',
    video_training_session: '视频训练',
    assignment_submission: '作业提交',
    create_account: '创建账号',
    import_create_account: '导入账号',
    batch_create_students: '批量开通',
    update_account: '更新账号',
    reset_password: '重置密码',
    delete_account: '删除账号',
    face_verification: '人脸核验',
    face_profile: '人脸档案更新',
    join_class: '加入班级',
    admin_register_account: '管理端注册',
    admin_batch_create_student: '管理端批量开通',
    admin_import_student: '管理端导入',
    speech_usage: '语音识别',
  }
  return labels[action] || action
}

const activityTitle = (item: UsageActivity) => {
  if (item.action === 'speech_usage') {
    return `${modeLabel(String(item.detail?.mode || ''))}：${statusLabel(String(item.detail?.status || ''))}`
  }
  if (item.action === 'face_verification') {
    return `人脸核验：${statusLabel(String(item.detail?.status || ''))}`
  }
  if (item.action === 'face_profile') {
    return `人脸档案：${statusLabel(String(item.detail?.status || ''))}`
  }
  if (item.module === '账号审计') {
    const prefix = item.title.includes('被操作') ? '被执行账号操作' : '执行账号操作'
    return `${prefix}：${actionLabel(item.action)}`
  }
  return item.title
}

const statusLabel = (value?: string) => {
  const labels: Record<string, string> = {
    success: '成功',
    failed: '失败',
    connected: '已连接',
    active: '进行中',
    in_progress: '进行中',
    finished: '已完成',
    abandoned: '已放弃',
    pending: '等待处理',
    submitted: '已提交',
    graded: '已批改',
    draft: '草稿',
    published: '已发布',
    archived: '已归档',
    pass: '通过',
    fail: '未通过',
    passed: '通过',
    rejected: '未通过',
    timeout: '超时',
    skip: '跳过',
    skipped: '已跳过',
    unknown: '未知',
    registered: '已建档',
  }
  return labels[String(value || '')] || value || '-'
}

const modeLabel = (value?: string) => {
  const labels: Record<string, string> = {
    transcribe: '语音文件识别',
    realtime: '实时语音识别',
    practice: '练习模式',
    exam: '正式考核',
    assessment: '考核模式',
    training: '训练模式',
  }
  return labels[String(value || '')] || value || '-'
}

const reasonLabel = (value?: string) => {
  const labels: Record<string, string> = {
    no_face: '未检测到人脸',
    multiple_faces: '检测到多人脸',
    face_mismatch: '人脸不匹配',
    low_similarity: '相似度不足',
    liveness_failed: '活体检测未通过',
    camera_error: '摄像头异常',
    timeout: '核验超时',
    user_cancelled: '用户取消',
  }
  return labels[String(value || '')] || value || '-'
}

const joinText = (...values: Array<string | undefined>) => {
  const clean = values.map((item) => String(item || '').trim()).filter(Boolean)
  return clean.length ? clean.join(' / ') : '-'
}

const categoryCount = (key: string) => detail.value?.activity_categories?.[key]?.length || 0

const detailText = (detail?: Record<string, any>) => {
  if (!detail) return ''
  const parts = []
  if (detail.status) parts.push(`状态：${statusLabel(detail.status)}`)
  if (detail.mode) parts.push(`模式：${modeLabel(detail.mode)}`)
  if (detail.score !== undefined && detail.score !== null) parts.push(`分数：${detail.score}`)
  if (detail.message_count !== undefined) parts.push(`消息：${detail.message_count}`)
  if (detail.artifact_count !== undefined) parts.push(`留痕：${detail.artifact_count}`)
  if (detail.reason) parts.push(`原因：${reasonLabel(detail.reason)}`)
  if (detail.reason_code) parts.push(`原因码：${reasonLabel(detail.reason_code)}`)
  if (detail.error_message) parts.push(`错误：${detail.error_message}`)
  if (detail.text_length !== undefined && detail.text_length !== null) parts.push(`识别字数：${detail.text_length}`)
  if (detail.duration_seconds !== undefined && detail.duration_seconds !== null) parts.push(`时长：${detail.duration_seconds} 秒`)
  if (detail.sample_count !== undefined && detail.sample_count !== null) parts.push(`照片样本：${detail.sample_count} 张`)
  if (detail.username) parts.push(`账号：${detail.username}`)
  return parts.join('，') || '-'
}

const formatTime = (value?: string) => {
  if (!value) return '-'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return '-'
  return date.toLocaleString('zh-CN', { hour12: false })
}

const computeGlobalVersion = (items: UsageAccount[]) => {
  return items.map((item) => item.usage_version || '').filter(Boolean).sort().at(-1) || ''
}

const computeVersionMap = (items: Array<{ id: number; usage_version?: string; version?: string }>) => {
  return items.reduce<Record<number, string>>((acc, item) => {
    acc[item.id] = String(item.usage_version || item.version || '')
    return acc
  }, {})
}

const usageCacheKey = (role = roleFilter.value, search = keyword.value) => `${role || 'all'}::${search.trim()}`

const applyUsageList = (items: UsageAccount[]) => {
  usageAccounts.value = items
  usageVersions.value = computeVersionMap(items)
  globalVersion.value = computeGlobalVersion(items)
}

const hasVersionChanged = (next: Record<number, string>) => {
  const current = usageVersions.value
  const currentIds = Object.keys(current)
  const nextIds = Object.keys(next)
  if (currentIds.length !== nextIds.length) return true
  return nextIds.some((id) => current[Number(id)] !== next[Number(id)])
}

const fetchUsage = async (silent = false) => {
  const requestId = ++usageRequestId
  if (!silent) loading.value = true
  try {
    const params: any = {}
    if (roleFilter.value) params.role = roleFilter.value
    if (keyword.value) params.keyword = keyword.value
    const cacheKey = usageCacheKey()
    const res: any = await request.get('/ops/accounts/usage', { params })
    if (requestId !== usageRequestId) return
    const items = Array.isArray(res) ? res : []
    usageListCache.set(cacheKey, items)
    applyUsageList(items)
    if (!selectedId.value && !initialAccountHandled && initialAccountId && usageAccounts.value.some((item) => item.id === initialAccountId)) {
      initialAccountHandled = true
      selectedId.value = initialAccountId
      await fetchDetail(initialAccountId)
    } else if (!selectedId.value && usageAccounts.value.length) {
      selectedId.value = usageAccounts.value[0].id
      await fetchDetail(usageAccounts.value[0].id)
    } else if (selectedId.value) {
      const stillVisible = usageAccounts.value.some((item) => item.id === selectedId.value)
      if (stillVisible) await fetchDetail(selectedId.value)
      else {
        selectedId.value = null
        detail.value = null
      }
    }
  } finally {
    if (!silent) loading.value = false
  }
}

const pollUsageVersions = async () => {
  if (versionPolling || loading.value || document.visibilityState === 'hidden') return
  versionPolling = true
  try {
    const params: any = {}
    if (roleFilter.value) params.role = roleFilter.value
    if (keyword.value) params.keyword = keyword.value
    const res: any = await request.get('/ops/accounts/usage-versions', { params, _skipErrorToast: true } as any)
    const nextVersion = String(res?.global_version || '')
    const nextVersions = computeVersionMap(Array.isArray(res?.accounts) ? res.accounts : [])
    if ((nextVersion && nextVersion !== globalVersion.value) || hasVersionChanged(nextVersions)) {
      await fetchUsage(true)
    }
  } finally {
    versionPolling = false
  }
}

const fetchDetail = async (id: number) => {
  const requestId = ++detailRequestId
  const res: any = await request.get(`/ops/accounts/${id}/usage`)
  if (requestId !== detailRequestId || selectedId.value !== id) return
  detail.value = res
  if (!categoryCount(activeCategory.value)) {
    const first = categoryTabs.find((item) => categoryCount(item.key) > 0)
    activeCategory.value = first?.key || 'admin'
  }
}

const selectAccount = async (item: UsageAccount) => {
  selectedId.value = item.id
  await fetchDetail(item.id)
}

const setRole = async (role: 'admin' | 'student' | '') => {
  roleFilter.value = role
  selectedId.value = null
  detail.value = null
  activeCategory.value = 'admin'
  const cached = usageListCache.get(usageCacheKey())
  if (cached) {
    applyUsageList(cached)
    if (cached.length) {
      selectedId.value = cached[0].id
      void fetchDetail(cached[0].id)
    }
    void fetchUsage(true)
    return
  }
  usageAccounts.value = []
  await fetchUsage()
}

onMounted(async () => {
  await fetchUsage()
  refreshTimer = window.setInterval(() => fetchUsage(true), 30000)
  versionTimer = window.setInterval(pollUsageVersions, VERSION_POLL_INTERVAL_MS)
})

onUnmounted(() => {
  if (refreshTimer) window.clearInterval(refreshTimer)
  if (versionTimer) window.clearInterval(versionTimer)
})
</script>

<style scoped>
.ops-usage {
  display: grid;
  gap: 16px;
}

.ops-usage-toolbar,
.ops-account-panel,
.ops-detail-panel {
  border: 1px solid #dbe3ee;
  border-radius: 8px;
  background: #fff;
}

.ops-usage-toolbar {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 14px;
  flex-wrap: wrap;
}

.ops-tabs {
  display: inline-flex;
  border: 1px solid #cbd5e1;
  border-radius: 6px;
  overflow: hidden;
}

.ops-tabs button {
  height: 36px;
  border: 0;
  border-right: 1px solid #cbd5e1;
  background: #fff;
  color: #475569;
  padding: 0 14px;
  font-weight: 900;
}

.ops-tabs button:last-child {
  border-right: 0;
}

.ops-tabs button.active {
  background: #2563eb;
  color: #fff;
}

.ops-usage-search {
  height: 36px;
  min-width: 220px;
  display: inline-flex;
  align-items: center;
  gap: 8px;
  border: 1px solid #cbd5e1;
  border-radius: 6px;
  padding: 0 10px;
  color: #64748b;
}

.ops-usage-search input {
  border: 0;
  outline: none;
}

.ops-refresh {
  height: 36px;
  display: inline-flex;
  align-items: center;
  gap: 7px;
  border: 1px solid #cbd5e1;
  border-radius: 6px;
  background: #fff;
  color: #334155;
  padding: 0 12px;
  font-weight: 900;
}

.ops-usage-grid {
  display: grid;
  grid-template-columns: 360px minmax(0, 1fr);
  gap: 16px;
  min-height: calc(100vh - 156px);
}

.ops-account-panel,
.ops-detail-panel {
  min-height: 0;
  display: flex;
  flex-direction: column;
}

.ops-account-panel header,
.ops-detail-panel header {
  flex: none;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 14px 16px;
  border-bottom: 1px solid #eef2f7;
}

.ops-account-panel h3,
.ops-detail-panel h3 {
  margin: 0;
  color: #0f172a;
  font-size: 16px;
}

.ops-detail-panel p {
  margin: 4px 0 0;
  color: #64748b;
  font-size: 12px;
}

.ops-live {
  color: #15803d;
  font-size: 12px;
  font-weight: 900;
}

.ops-account-list,
.ops-activity-list {
  min-height: 0;
  overflow: auto;
  padding: 12px;
}

.ops-account-card {
  width: 100%;
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 8px;
  border: 1px solid #e2e8f0;
  border-radius: 6px;
  background: #fff;
  padding: 12px;
  text-align: left;
  margin-bottom: 10px;
}

.ops-account-card.active {
  border-color: #2563eb;
  background: #eff6ff;
}

.ops-account-card strong,
.ops-account-card span,
.ops-account-card em {
  display: block;
}

.ops-account-card strong {
  color: #0f172a;
  font-size: 14px;
}

.ops-account-card span,
.ops-account-card em {
  color: #64748b;
  font-size: 12px;
  font-style: normal;
}

.ops-account-card i {
  align-self: start;
  border-radius: 999px;
  padding: 4px 8px;
  font-style: normal;
  font-size: 12px;
  font-weight: 900;
}

.role-admin {
  background: #f0fdf4;
  color: #15803d;
}

.role-student {
  background: #fff7ed;
  color: #c2410c;
}

.role-maintainer {
  background: #eff6ff;
  color: #1d4ed8;
}

.ops-stat-grid {
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 1fr));
  gap: 10px;
  padding: 14px 16px;
  border-bottom: 1px solid #eef2f7;
}

.ops-stat-grid div {
  border: 1px solid #dbe3ee;
  border-radius: 6px;
  background: #f8fafc;
  padding: 12px;
}

.ops-stat-grid span {
  display: block;
  color: #64748b;
  font-size: 12px;
  font-weight: 800;
}

.ops-stat-grid strong {
  display: block;
  margin-top: 4px;
  color: #0f172a;
  font-size: 22px;
}

.ops-profile-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 10px;
  padding: 0 16px 14px;
  border-bottom: 1px solid #eef2f7;
}

.ops-profile-grid div {
  border: 1px solid #dbe3ee;
  border-radius: 6px;
  background: #fff;
  padding: 12px;
}

.ops-profile-grid span,
.ops-profile-grid p {
  color: #64748b;
  font-size: 12px;
}

.ops-profile-grid span {
  display: block;
  font-weight: 900;
}

.ops-profile-grid strong {
  display: block;
  margin-top: 6px;
  color: #0f172a;
  font-size: 16px;
}

.ops-profile-grid strong.ok {
  color: #15803d;
}

.ops-profile-grid strong.warn {
  color: #c2410c;
}

.ops-profile-grid p {
  margin: 5px 0 0;
}

.ops-face-card {
  display: grid;
  grid-template-columns: minmax(160px, 240px) minmax(0, 1fr);
  gap: 14px;
  padding: 0 16px 14px;
  border-bottom: 1px solid #eef2f7;
}

.ops-face-card > div:last-child {
  border: 1px solid #dbe3ee;
  border-radius: 6px;
  padding: 12px;
}

.ops-face-card span,
.ops-face-card p {
  color: #64748b;
  font-size: 12px;
}

.ops-face-card span {
  display: block;
  font-weight: 900;
}

.ops-face-card strong {
  display: block;
  margin-top: 6px;
  color: #0f172a;
  font-size: 16px;
}

.ops-face-card strong.ok {
  color: #15803d;
}

.ops-face-card strong.warn {
  color: #c2410c;
}

.ops-face-card p {
  margin: 5px 0 0;
}

.ops-face-photo-list {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(108px, 1fr));
  align-content: start;
  gap: 8px;
}

.ops-face-photo {
  width: 100%;
  min-height: 132px;
  aspect-ratio: 4 / 5;
  display: grid;
  place-items: center;
  border: 1px solid #dbe3ee;
  border-radius: 6px;
  background: #f8fafc;
  color: #94a3b8;
  font-size: 12px;
  font-weight: 900;
}

.ops-face-photo img {
  width: 100%;
  height: 100%;
  object-fit: contain;
  background: #fff;
}

.ops-face-photo--empty {
  aspect-ratio: 1;
}

.ops-category-tabs {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  padding: 12px 16px;
  border-bottom: 1px solid #eef2f7;
}

.ops-category-tabs button {
  height: 32px;
  display: inline-flex;
  align-items: center;
  gap: 6px;
  border: 1px solid #cbd5e1;
  border-radius: 999px;
  background: #fff;
  color: #475569;
  padding: 0 12px;
  font-size: 12px;
  font-weight: 900;
}

.ops-category-tabs button.active {
  border-color: #2563eb;
  background: #eff6ff;
  color: #1d4ed8;
}

.ops-category-tabs span {
  color: inherit;
  opacity: 0.72;
}

.ops-activity-item {
  display: grid;
  grid-template-columns: 160px minmax(0, 1fr);
  gap: 12px;
  border-bottom: 1px solid #eef2f7;
  padding: 12px 4px;
}

.ops-activity-item time {
  color: #64748b;
  font-size: 12px;
}

.ops-activity-item strong {
  display: block;
  color: #0f172a;
  font-size: 13px;
}

.ops-activity-item span {
  display: block;
  margin-top: 4px;
  color: #64748b;
  font-size: 12px;
}

.ops-empty {
  padding: 32px;
  text-align: center;
  color: #94a3b8;
  font-weight: 800;
}

.ops-empty--detail {
  margin: auto;
}

@media (max-width: 920px) {
  .ops-usage-grid {
    grid-template-columns: 1fr;
  }

  .ops-stat-grid {
    grid-template-columns: 1fr 1fr;
  }

  .ops-profile-grid {
    grid-template-columns: 1fr;
  }

  .ops-face-card {
    grid-template-columns: 1fr;
  }
}
</style>
