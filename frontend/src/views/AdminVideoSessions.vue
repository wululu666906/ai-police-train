<template>
  <div class="space-y-5">
    <section class="admin-filter-panel">
      <div class="admin-filter-bar">
        <label class="admin-filter-item">
          <span>实训视频</span>
          <el-select v-model="filterVideoId" clearable placeholder="全部视频" style="width:180px" @change="fetchSessions">
            <el-option v-for="v in videoOptions" :key="v.id" :label="v.title" :value="v.id" />
          </el-select>
        </label>
        <label class="admin-filter-item">
          <span>完成状态</span>
          <el-select v-model="filterStatus" clearable placeholder="全部状态" style="width:130px" @change="fetchSessions">
            <el-option label="进行中" value="active" />
            <el-option label="已完成" value="finished" />
            <el-option label="已放弃" value="abandoned" />
          </el-select>
        </label>
        <label class="admin-filter-item">
          <span>学员账号</span>
          <el-input v-model="filterUsername" placeholder="输入账号搜索" clearable style="width:160px" @change="onFilterChange" />
        </label>
        <label class="admin-filter-item">
          <span>复核状态</span>
          <el-select v-model="filterReviewMode" placeholder="全部记录" style="width:150px" @change="onFilterChange">
            <el-option label="全部记录" value="" />
            <el-option label="仅已复核" value="reviewed" />
            <el-option label="仅改判节点" value="overridden" />
          </el-select>
        </label>
        <label class="admin-filter-item">
          <span>异常类型</span>
          <el-select v-model="filterViolationType" clearable placeholder="全部异常" style="width:160px" @change="onFilterChange">
            <el-option
              v-for="item in violationFilterOptions"
              :key="item.value"
              :label="item.label"
              :value="item.value"
            />
          </el-select>
        </label>
      </div>
    </section>

    <section v-if="analytics" class="analytics-grid">
      <div class="analytics-card">
        <div class="analytics-card__label">实训场次</div>
        <div class="analytics-card__num">{{ analytics.session_count }}</div>
        <div class="analytics-card__sub">进行中 {{ analytics.active_count }}，已完成 {{ analytics.finished_count }}</div>
      </div>
      <div class="analytics-card">
        <div class="analytics-card__label">平均得分</div>
        <div class="analytics-card__num">{{ analytics.avg_score }}</div>
        <div class="analytics-card__sub">用于快速判断整体训练质量</div>
      </div>
      <div class="analytics-card">
        <div class="analytics-card__label">违规总数</div>
        <div class="analytics-card__num analytics-card__num--warn">{{ analytics.total_violation_count }}</div>
        <div class="analytics-card__sub">切屏、离页、设备中断都会计入</div>
      </div>
      <div class="analytics-card">
        <div class="analytics-card__label">人工复核</div>
        <div class="analytics-card__num">{{ analytics.reviewed_count }}</div>
        <div class="analytics-card__sub">其中改判 {{ analytics.overridden_count }} 条</div>
      </div>
    </section>

    <section v-if="analytics && (analytics.failure_reason_summary.length || analytics.violation_summary.length)" class="analytics-panels">
      <div class="analytics-panel">
        <div class="analytics-panel__title">高频失分原因</div>
        <div v-if="analytics.failure_reason_summary.length" class="analytics-chip-list">
          <span v-for="item in analytics.failure_reason_summary.slice(0, 6)" :key="item.reason" class="analytics-chip analytics-chip--danger">
            {{ formatFailureReason(item.reason) }} x{{ item.count }}
          </span>
        </div>
        <div v-else class="analytics-empty">暂无失分原因数据</div>
      </div>
      <div class="analytics-panel">
        <div class="analytics-panel__title">违规类型</div>
        <div v-if="analytics.violation_summary.length" class="analytics-chip-list">
          <span v-for="item in analytics.violation_summary.slice(0, 6)" :key="item.type" class="analytics-chip analytics-chip--warn">
            {{ formatViolationType(item.type) }} x{{ item.count }}
          </span>
        </div>
        <div v-else class="analytics-empty">暂无违规记录</div>
      </div>
      <div class="analytics-panel">
        <div class="analytics-panel__title">高风险节点</div>
        <div v-if="analytics.node_failure_summary.length" class="analytics-list">
          <div v-for="item in analytics.node_failure_summary.slice(0, 5)" :key="item.node_id" class="analytics-list__row">
            <span>{{ item.node_title }}</span>
            <span class="analytics-list__count">失败 {{ item.fail_count }} 次</span>
          </div>
        </div>
        <div v-else class="analytics-empty">暂无节点失败统计</div>
      </div>
    </section>

    <section v-if="reviewItems.length" class="analytics-panel">
      <div class="analytics-panel__title">复核记录列表</div>
      <div class="analytics-list">
        <div v-for="item in reviewItems" :key="item.node_result_id" class="analytics-list__row analytics-list__row--review">
          <div>
            <strong>{{ item.username }}</strong>
            <span style="margin-left:8px;color:#64748b">{{ item.video_title }}</span>
            <div style="margin-top:4px;font-size:12px;color:#64748b">
              第 {{ item.node_index + 1 }} 节点 · {{ item.node_title }}
              <span v-if="item.review_note"> · {{ item.review_note }}</span>
            </div>
          </div>
          <div class="analytics-list__review-meta">
            <span class="analytics-chip" :class="item.overridden ? 'analytics-chip--danger' : 'analytics-chip--warn'">
              {{ item.overridden ? '已改判' : '已复核' }}
            </span>
            <span>{{ resultLabel(item.original_result) }} → {{ resultLabel(item.current_result) }}</span>
          </div>
        </div>
      </div>
    </section>

    <section v-if="loading" class="rounded-[8px] bg-white border border-slate-100 py-16 text-center">
      <el-skeleton :rows="5" animated />
    </section>

    <section v-else-if="!sessions.length" class="rounded-[8px] border border-dashed border-slate-200 bg-white py-20 text-center">
      <van-icon name="orders-o" size="32" class="text-slate-300" />
      <h3 class="mt-4 text-lg font-bold text-slate-500">暂无实训记录</h3>
    </section>

    <section v-else class="case-table-wrap">
      <table class="case-table">
        <thead>
          <tr>
            <th>学员</th>
            <th>训练视频</th>
            <th>模式</th>
            <th>状态</th>
            <th>得分</th>
            <th>评级</th>
            <th>违规</th>
            <th>节点进度</th>
            <th>开始时间</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="s in sessions" :key="s.id">
            <td class="case-title-cell">
              <div class="case-row-title">{{ s.username }}</div>
              <div class="case-row-id">ID {{ s.user_id }}</div>
            </td>
            <td class="case-summary-cell">{{ s.video_title }}</td>
            <td>
              <van-tag :type="s.mode === 'exam' ? 'danger' : 'primary'" plain>
                {{ s.mode === 'exam' ? '考核' : '练习' }}
              </van-tag>
            </td>
            <td>
              <span :class="statusClass(s.status)">{{ statusLabel(s.status) }}</span>
            </td>
            <td class="case-metric-cell">
              <span v-if="s.total_score != null">{{ s.total_score }} / {{ s.full_score }}</span>
              <span v-else class="text-slate-400">--</span>
            </td>
            <td>
              <van-tag v-if="s.status === 'finished'" :type="gradeType(s.grade)" plain>
                {{ s.grade || '--' }}
              </van-tag>
              <span v-else class="text-slate-400">--</span>
            </td>
            <td class="case-metric-cell">
              <div class="violation-cell">
                <span>{{ s.violation_count || 0 }}</span>
                <div v-if="sessionViolationTypes(s).length" class="violation-chip-list">
                  <span
                    v-for="type in sessionViolationTypes(s)"
                    :key="`${s.id}-${type}`"
                    class="analytics-chip analytics-chip--warn"
                  >
                    {{ formatViolationType(type) }}
                  </span>
                </div>
              </div>
            </td>
            <td class="case-metric-cell">
              <el-progress
                :percentage="nodeProgress(s)"
                :stroke-width="5"
                style="width:80px"
                :show-text="false"
                :color="s.status === 'finished' ? '#52c41a' : '#0066ff'"
              />
              <span style="font-size:11px;color:#6b7280;margin-left:4px">{{ s.current_node_index }}/{{ nodeTotal(s) }}</span>
            </td>
            <td style="font-size:12px;color:#6b7280">{{ formatDate(s.created_at) }}</td>
            <td class="case-action-cell">
              <div v-if="s.status === 'finished'" class="case-action-group">
                <van-button
                  size="small"
                  type="primary"
                  class="!bg-[#1D3557] !border-none !rounded-[6px]"
                  @click="viewReport(s)"
                >
                  查看报告
                </van-button>
                <van-button
                  v-if="latestReplayArtifact(s)"
                  size="small"
                  plain
                  type="primary"
                  class="!rounded-[6px]"
                  @click="playSessionReplay(s)"
                >
                  查看录制
                </van-button>
              </div>
              <span v-else class="text-slate-400 text-xs">训练中</span>
            </td>
          </tr>
        </tbody>
      </table>
    </section>

    <div v-if="total > pageSize" class="flex justify-center py-2">
      <el-pagination
        v-model:current-page="page"
        :page-size="pageSize"
        :total="total"
        layout="prev, pager, next, total"
        @current-change="fetchSessions"
      />
    </div>

    <el-dialog v-model="showReviewDialog" title="人工复核 / 改判" width="520px">
      <el-form :model="reviewForm" label-width="96px">
        <el-form-item label="节点">
          <div class="text-slate-700">{{ reviewTargetLabel }}</div>
        </el-form-item>
        <el-form-item label="复核结果">
          <el-select v-model="reviewForm.result" style="width: 180px">
            <el-option label="通过" value="pass" />
            <el-option label="未通过" value="fail" />
            <el-option label="跳过" value="skip" />
            <el-option label="超时" value="timeout" />
          </el-select>
        </el-form-item>
        <el-form-item label="得分">
          <el-input-number v-model="reviewForm.score_earned" :min="0" :max="reviewScoreMax" />
        </el-form-item>
        <el-form-item label="失分原因">
          <el-input
            v-model="reviewForm.failureReasonText"
            type="textarea"
            :rows="2"
            placeholder="多个原因用逗号分隔；复核通过时可留空"
          />
        </el-form-item>
        <el-form-item label="复核说明">
          <el-input
            v-model="reviewForm.review_note"
            type="textarea"
            :rows="3"
            placeholder="记录人工复核依据，便于后续追溯"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showReviewDialog = false">取消</el-button>
        <el-button type="primary" :loading="reviewSaving" @click="submitReview">提交复核</el-button>
      </template>
    </el-dialog>

    <el-dialog
      v-model="showReplayDialog"
      title="学员训练录制"
      width="760px"
      destroy-on-close
    >
      <video v-if="replayUrl" class="session-replay-video" :src="replayUrl" controls preload="metadata" />
      <el-empty v-else description="当前场次暂无可查看的训练录制" />
    </el-dialog>
  </div>
</template>
<script setup lang="ts">
import { computed, reactive, ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import request from '../utils/request'

interface SessionItem {
  id: number
  user_id: number
  username: string
  video_id: number
  video_title: string
  node_total: number
  mode: string
  status: string
  current_node_index: number
  total_score: number | null
  full_score: number | null
  violation_count: number
  violation_log?: { type?: string; detail?: string; ts?: string }[]
  artifacts?: ArtifactItem[]
  grade?: string
  created_at: string
  finished_at?: string
}

interface ArtifactItem {
  id: number
  artifact_type: string
  file_url?: string
  mime_type?: string
  duration_seconds?: number | null
  created_at?: string
}

interface ReportData {
  session_id: number
  video_title: string
  mode?: string
  grade: string
  total_score: number
  full_score: number
  percentage: number
  pass_count: number
  skip_count: number
  fail_count?: number
  total_nodes: number
  total_deducted: number
  violation_count?: number
  violation_summary?: Record<string, number>
  failure_reason_summary?: Record<string, number>
  artifacts?: ArtifactItem[]
  finished_at?: string
  node_summaries: {
    node_result_id?: number
    node_index: number
    node_title?: string
    result: string
    retry_count: number
    score_earned: number
    score_deducted: number
    speech_transcript?: string
    failure_reasons?: string[]
    manual_review?: {
      reviewer_username?: string
      reviewed_at?: string
      review_note?: string
    } | null
  }[]
}

interface AnalyticsData {
  session_count: number
  finished_count: number
  active_count: number
  reviewed_count: number
  overridden_count: number
  avg_score: number
  total_violation_count: number
  failure_reason_summary: { reason: string; count: number }[]
  violation_summary: { type: string; count: number }[]
  node_failure_summary: { node_id: number; node_title: string; fail_count: number }[]
}

interface ReviewItem {
  node_result_id: number
  session_id: number
  video_title: string
  username: string
  node_index: number
  node_title: string
  current_result: string
  original_result: string
  review_note?: string
  reviewer_username?: string
  reviewed_at?: string
  overridden: boolean
}

const sessions = ref<SessionItem[]>([])
const router = useRouter()
const videoOptions = ref<{ id: number; title: string }[]>([])
const loading = ref(false)
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)

const filterVideoId = ref<number | null>(null)
const filterStatus = ref('')
const filterUsername = ref('')
const filterReviewMode = ref('')
const filterViolationType = ref('')

const violationFilterOptions = [
  { label: '切换标签页', value: 'tab_switch' },
  { label: '关闭或刷新页面', value: 'page_leave' },
  { label: '页面切入后台', value: 'page_hide' },
  { label: '设备中断', value: 'device_lost' },
  { label: '身份校验中断', value: 'identity_lost' },
]

const showReport = ref(false)
const reportData = ref<ReportData | null>(null)
const analytics = ref<AnalyticsData | null>(null)
const reviewItems = ref<ReviewItem[]>([])
const activeReportSessionId = ref<number | null>(null)
const showReviewDialog = ref(false)
const reviewSaving = ref(false)
const showReplayDialog = ref(false)
const replayUrl = ref('')
const reviewTarget = ref<ReportData['node_summaries'][number] | null>(null)
const reviewForm = reactive({
  result: 'pass',
  score_earned: 0,
  review_note: '',
  failureReasonText: '',
})
const failureReasonList = computed(() =>
  Object.entries(reportData.value?.failure_reason_summary || {}).map(([key, count]) => ({
    key,
    count,
    label: formatFailureReason(key),
  })),
)
const violationList = computed(() =>
  Object.entries(reportData.value?.violation_summary || {}).map(([key, count]) => ({
    key,
    count,
    label: formatViolationType(key),
  })),
)
const reviewScoreMax = computed(() => {
  if (!reviewTarget.value) return 100
  return Math.max(reviewTarget.value.score_earned + reviewTarget.value.score_deducted, reviewTarget.value.score_earned, 0)
})
const reviewTargetLabel = computed(() => {
  if (!reviewTarget.value) return '--'
  return `第 ${reviewTarget.value.node_index + 1} 节点：${reviewTarget.value.node_title}`
})

onMounted(() => {
  fetchVideoOptions()
  fetchSessions()
})

async function fetchVideoOptions() {
  try {
    const res: any = await request.get('/videos/admin/list', { params: { video_type: 'interactive', page_size: 100, page: 1 } })
    videoOptions.value = (res.items || []).map((v: any) => ({ id: v.id, title: v.title }))
  } catch {}
}

async function fetchSessions() {
  loading.value = true
  try {
    const params: Record<string, any> = { page: page.value, page_size: pageSize.value }
    if (filterVideoId.value) params.video_id = filterVideoId.value
    if (filterStatus.value) params.status = filterStatus.value
    if (filterUsername.value.trim()) params.username = filterUsername.value.trim()
    if (filterReviewMode.value === 'reviewed') params.reviewed_only = true
    if (filterReviewMode.value === 'overridden') params.override_only = true
    if (filterViolationType.value) params.violation_type = filterViolationType.value
    const res: any = await request.get('/video-training/admin/sessions', { params })
    sessions.value = res.items || []
    total.value = res.total || 0
  } catch {
    ElMessage.error('加载实训记录失败')
  } finally {
    loading.value = false
  }
  await Promise.all([fetchAnalytics(), fetchReviews()])
}

async function fetchAnalytics() {
  try {
    const params: Record<string, any> = {}
    if (filterVideoId.value) params.video_id = filterVideoId.value
    if (filterStatus.value) params.status = filterStatus.value
    if (filterUsername.value.trim()) params.username = filterUsername.value.trim()
    if (filterReviewMode.value === 'reviewed') params.reviewed_only = true
    if (filterReviewMode.value === 'overridden') params.override_only = true
    if (filterViolationType.value) params.violation_type = filterViolationType.value
    analytics.value = await request.get('/video-training/admin/analytics', { params })
  } catch {
    analytics.value = null
  }
}

async function fetchReviews() {
  try {
    const params: Record<string, any> = { page: 1, page_size: 8 }
    if (filterVideoId.value) params.video_id = filterVideoId.value
    if (filterStatus.value) params.status = filterStatus.value
    if (filterUsername.value.trim()) params.username = filterUsername.value.trim()
    if (filterReviewMode.value === 'overridden') params.override_only = true
    const res: any = await request.get('/video-training/admin/reviews', { params })
    reviewItems.value = res.items || []
  } catch {
    reviewItems.value = []
  }
}

function onFilterChange() {
  page.value = 1
  fetchSessions()
}

async function viewReport(s: SessionItem) {
  router.push(`/admin/video-sessions/${s.id}/report`)
}

function latestReplayArtifact(session: SessionItem): ArtifactItem | null {
  const items = Array.isArray(session.artifacts) ? session.artifacts : []
  const sorted = [...items].sort((a, b) => {
    const aTime = new Date(a.created_at || 0).getTime()
    const bTime = new Date(b.created_at || 0).getTime()
    return bTime - aTime
  })
  return sorted.find((item) => item.artifact_type === 'camera_recording' && item.file_url) || null
}

function resolveMediaUrl(url?: string): string {
  if (!url) return ''
  if (/^https?:\/\//i.test(url)) return url
  const baseUrl = String(request.defaults.baseURL || '').replace(/\/$/, '')
  if (!baseUrl) return url
  return `${baseUrl}${url.startsWith('/') ? url : `/${url}`}`
}

function playSessionReplay(session: SessionItem) {
  const artifact = latestReplayArtifact(session)
  if (!artifact?.file_url) {
    ElMessage.warning('当前场次暂无可查看的训练录制')
    return
  }
  replayUrl.value = resolveMediaUrl(artifact.file_url)
  showReplayDialog.value = true
}

function openReviewDialog(item: ReportData['node_summaries'][number]) {
  reviewTarget.value = item
  reviewForm.result = item.result || 'pass'
  reviewForm.score_earned = item.score_earned || 0
  reviewForm.review_note = item.manual_review?.review_note || ''
  reviewForm.failureReasonText = (item.failure_reasons || []).join(', ')
  showReviewDialog.value = true
}

async function refreshActiveReport() {
  if (!activeReportSessionId.value) return
  const res: any = await request.get(`/video-training/admin/sessions/${activeReportSessionId.value}/report`)
  reportData.value = { ...res, grade: gradeFromScore(res.percentage) }
}

async function submitReview() {
  if (!reviewTarget.value?.node_result_id) {
    ElMessage.error('当前节点缺少复核目标')
    return
  }
  reviewSaving.value = true
  try {
    const failure_reasons = reviewForm.failureReasonText
      .split(/[，,]/)
      .map(item => item.trim())
      .filter(Boolean)
    await request.post(`/video-training/admin/node-results/${reviewTarget.value.node_result_id}/review`, {
      result: reviewForm.result,
      score_earned: reviewForm.score_earned,
      failure_reasons,
      review_note: reviewForm.review_note.trim(),
    })
    showReviewDialog.value = false
    await refreshActiveReport()
    await fetchSessions()
    ElMessage.success('复核结果已更新')
  } catch {
    ElMessage.error('提交复核失败')
  } finally {
    reviewSaving.value = false
  }
}

function gradeFromScore(pct: number): string {
  if (pct >= 90) return '优秀'
  if (pct >= 70) return '合格'
  return '待重修'
}

function nodeProgress(s: SessionItem): number {
  const total = nodeTotal(s)
  if (!total) return 0
  return Math.min(100, Math.round((s.current_node_index / total) * 100))
}

function nodeTotal(s: SessionItem): number {
  return s.node_total || 0
}

function statusLabel(status: string): string {
  return { active: '进行中', finished: '已完成', abandoned: '已放弃' }[status] || status
}

function statusClass(status: string): string {
  if (status === 'finished') return 'case-ok'
  if (status === 'active') return 'text-blue-600 font-semibold'
  return 'text-slate-400'
}

function gradeType(grade?: string): 'success' | 'primary' | 'warning' | 'danger' {
  if (grade === '优秀') return 'success'
  if (grade === '合格') return 'primary'
  if (grade === '待重修') return 'danger'
  return 'warning'
}

function resultLabel(r: string): string {
  return { pass: '通过', skip: '跳过', timeout: '超时跳过', fail: '未完成' }[r] || r
}

function resultColor(r: string): string {
  if (r === 'pass') return 'text-emerald-600 font-semibold'
  if (r === 'skip' || r === 'timeout') return 'text-amber-600 font-semibold'
  return 'text-red-600 font-semibold'
}

function formatFailureReason(reason: string): string {
  return ({
    gesture_mismatch: '动作未达标',
    keyword_mismatch: '话术未匹配',
    judge_incorrect: '判断题错误',
    choice_incorrect: '选择题错误',
    prop_missed: '道具动作遗漏',
    manual_review_failed: '人工复核判定未通过',
  } as Record<string, string>)[reason] || reason
}

function formatViolationType(type: string): string {
  return ({
    tab_switch: '切换标签页',
    page_leave: '关闭或刷新页面',
    page_hide: '页面切入后台',
    device_lost: '设备中断',
    identity_lost: '身份校验中断',
  } as Record<string, string>)[type] || type
}

function sessionViolationTypes(session: SessionItem): string[] {
  const list = (session.violation_log || [])
    .map(item => item?.type || '')
    .filter(Boolean)
  return Array.from(new Set(list)).slice(0, 3)
}

function formatDate(iso?: string): string {
  if (!iso) return '--'
  return new Date(iso).toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' })
}
</script>

<style scoped lang="scss">
.admin-filter-panel,
.case-table-wrap {
  background: #fff;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
}

.admin-filter-panel {
  padding: 16px 20px;
}

.admin-filter-bar {
  display: flex;
  flex-wrap: wrap;
  gap: 14px 16px;
  align-items: flex-end;
}

.admin-filter-item {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 13px;
  color: #334155;
}

.admin-filter-item > span {
  white-space: nowrap;
  font-weight: 700;
  color: #0f172a;
}

.analytics-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 14px;
}

.analytics-card,
.analytics-panel {
  background: #fff;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  padding: 16px 18px;
}

.analytics-card__label,
.analytics-panel__title {
  font-size: 12px;
  font-weight: 700;
  color: #64748b;
  margin-bottom: 8px;
}

.analytics-card__num {
  font-size: 28px;
  line-height: 1;
  font-weight: 800;
  color: #0f172a;
}

.analytics-card__num--warn {
  color: #dc2626;
}

.analytics-card__sub {
  margin-top: 8px;
  font-size: 12px;
  color: #94a3b8;
}

.analytics-panels {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 14px;
}

.analytics-chip-list {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.analytics-chip {
  display: inline-flex;
  align-items: center;
  padding: 4px 10px;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 600;
}

.analytics-chip--danger {
  background: #fff1f2;
  color: #e11d48;
}

.analytics-chip--warn {
  background: #fff7ed;
  color: #ea580c;
}

.analytics-list {
  display: grid;
  gap: 8px;
}

.analytics-list__row {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  font-size: 13px;
  color: #334155;
}

.analytics-list__row--review {
  align-items: flex-start;
  padding: 10px 0;
  border-bottom: 1px solid #f1f5f9;
}

.case-action-group {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.session-replay-video {
  display: block;
  width: 100%;
  max-height: 72vh;
  border-radius: 8px;
  background: #020617;
}

.analytics-list__row--review:last-child {
  border-bottom: 0;
  padding-bottom: 0;
}

.analytics-list__count {
  color: #dc2626;
  font-weight: 700;
}

.analytics-list__review-meta {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 6px;
  font-size: 12px;
  color: #64748b;
}

.analytics-empty {
  color: #94a3b8;
  font-size: 12px;
}

.case-table-wrap {
  overflow: hidden;
}

.case-table {
  width: 100%;
  border-collapse: collapse;
  table-layout: fixed;
}

.case-table thead th {
  padding: 14px 12px;
  background: #f8fafc;
  color: #475569;
  font-size: 12px;
  font-weight: 700;
  text-align: left;
  border-bottom: 1px solid #e2e8f0;
}

.case-table tbody td {
  padding: 16px 12px;
  border-bottom: 1px solid #f1f5f9;
  vertical-align: middle;
  color: #0f172a;
  font-size: 13px;
}

.case-table tbody tr:hover {
  background: #f8fbff;
}

.case-title-cell,
.case-summary-cell {
  min-width: 0;
}

.case-row-title {
  font-size: 16px;
  font-weight: 800;
  color: #0f172a;
  line-height: 1.2;
}

.case-row-id {
  margin-top: 6px;
  font-size: 12px;
  color: #94a3b8;
}

.case-summary-cell {
  color: #334155;
  line-height: 1.6;
  word-break: break-all;
}

.case-metric-cell {
  color: #334155;
}

.violation-cell {
  display: grid;
  gap: 6px;
}

.violation-chip-list {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.case-action-cell {
  white-space: nowrap;
}

.case-ok {
  color: #16a34a;
  font-weight: 700;
}

@media (max-width: 960px) {
  .analytics-grid,
  .analytics-panels {
    grid-template-columns: 1fr;
  }

  .admin-filter-item {
    width: 100%;
    justify-content: space-between;
  }

  .case-table-wrap {
    overflow-x: auto;
  }

  .case-table {
    min-width: 1080px;
  }
}
</style>

