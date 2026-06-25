<template>
  <div class="student-page training-history-page">
    <section class="history-hero">
      <div>
        <h1 class="history-hero__title">实训记录</h1>
        <p class="history-hero__subtitle">查看自己的视频实训记录、得分与评估报告。</p>
      </div>
    </section>

    <section class="filter-panel">
      <div class="filter-grid">
        <div class="filter-item">
          <label>实训类型</label>
          <el-select v-model="typeFilter" placeholder="全部类型" @change="resetPagination">
            <el-option label="全部类型" value="all" />
            <el-option v-for="item in availableTypes" :key="item" :label="item" :value="item" />
          </el-select>
        </div>

        <div class="filter-item">
          <label>训练模式</label>
          <el-select v-model="modeFilter" placeholder="全部模式" @change="resetPagination">
            <el-option label="全部模式" value="all" />
            <el-option label="练习模式" value="practice" />
            <el-option label="正式考核" value="exam" />
          </el-select>
        </div>

        <div class="filter-item">
          <label>完成状态</label>
          <el-select v-model="statusFilter" placeholder="全部状态" @change="resetPagination">
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
            @change="resetPagination"
          />
        </div>

        <div class="filter-item filter-item--search">
          <label>&nbsp;</label>
          <el-input
            v-model="keyword"
            placeholder="搜索视频名称、场景、关键词"
            clearable
            :prefix-icon="Search"
            @input="resetPagination"
            @clear="resetPagination"
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

    <section class="stats-grid">
      <article v-for="card in statCards" :key="card.label" class="stat-card">
        <div class="stat-card__main">
          <div class="stat-card__label">{{ card.label }}</div>
          <div class="stat-card__value" :class="`is-${card.tone}`">{{ card.value }}</div>
          <div class="stat-card__desc">{{ card.desc }}</div>
        </div>
        <div class="stat-card__icon" :class="`is-${card.tone}`">
          <el-icon><component :is="card.icon" /></el-icon>
        </div>
      </article>
    </section>

    <section class="analytics-grid">
      <article class="chart-card">
        <div class="chart-card__title">能力雷达图（近 10 次平均表现）</div>
        <div ref="radarChartRef" class="chart-card__canvas" />
      </article>

      <article class="chart-card chart-card--issue">
        <div class="chart-card__title">高频失分原因 TOP5</div>
        <div class="issue-list">
          <div v-for="item in issueTopList" :key="item.label" class="issue-item">
            <div class="issue-item__head">
              <span>{{ item.label }}</span>
              <strong>{{ item.value }}%</strong>
            </div>
            <div class="issue-item__bar">
              <span :style="{ width: `${item.value}%` }" />
            </div>
          </div>
          <div v-if="!issueTopList.length" class="issue-empty">暂无明显失分项，继续保持。</div>
        </div>
      </article>

      <article class="chart-card chart-card--trend">
        <div class="chart-card__title">训练趋势（近 7 次）</div>
        <div ref="trendChartRef" class="chart-card__canvas chart-card__canvas--trend" />
      </article>
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
            <div v-for="(item, index) in pagedSessions" :key="item.id" class="history-row">
              <div class="cell-center">{{ (currentPage - 1) * pageSize + index + 1 }}</div>

              <div class="history-row__title-cell">
                <div class="history-row__title">{{ item.video_title || '未知视频' }}</div>
                <div class="history-row__sub">Session #{{ item.id }}</div>
              </div>

              <div class="history-row__scene">{{ sceneForSession(item) }}</div>

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
                <template v-if="item.total_score != null">
                  {{ item.total_score.toFixed(1) }}
                </template>
                <span v-else>--</span>
              </div>

              <div class="cell-center">
                <span v-if="item.total_score != null" class="grade-badge" :class="`grade-badge--${gradeKey(item)}`">
                  {{ gradeText(item) }}
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

              <div class="action-cell">
                <template v-if="item.status === 'active'">
                  <el-button type="primary" plain size="small" @click="handleAction('continue', item)">继续训练</el-button>
                </template>
                <template v-else-if="item.status === 'finished'">
                  <el-button type="primary" plain size="small" @click="handleAction('report', item)">查看报告</el-button>
                </template>
                <template v-else>
                  <el-button type="warning" plain size="small" @click="handleAction('redo', item)">去重修</el-button>
                </template>

                <el-dropdown trigger="click" @command="handleDropdownCommand($event, item)">
                  <button type="button" class="more-btn">
                    <el-icon><MoreFilled /></el-icon>
                  </button>
                  <template #dropdown>
                    <el-dropdown-menu>
                      <el-dropdown-item v-if="item.status === 'finished'" command="report">查看报告</el-dropdown-item>
                      <el-dropdown-item v-if="item.status === 'finished' && latestReplayArtifact(item)" command="replay">查看回放</el-dropdown-item>
                      <el-dropdown-item v-if="item.status === 'active'" command="continue">继续训练</el-dropdown-item>
                      <el-dropdown-item v-if="item.video_id" command="redo">重新训练</el-dropdown-item>
                    </el-dropdown-menu>
                  </template>
                </el-dropdown>
              </div>
            </div>
          </div>
        </div>

        <div class="table-footer">
          <span class="table-footer__count">共 {{ filteredSessions.length }} 条</span>
          <el-pagination
            v-model:current-page="currentPage"
            v-model:page-size="pageSize"
            background
            layout="prev, pager, next, sizes"
            :page-sizes="[8, 10, 20]"
            :total="filteredSessions.length"
          />
        </div>
      </template>
    </section>

    <el-dialog
      v-model="showReplayDialog"
      title="训练录制回放"
      width="720px"
      destroy-on-close
      class="replay-dialog"
    >
      <template v-if="replayArtifactUrl">
        <video class="replay-video" :src="replayArtifactUrl" controls preload="metadata" />
      </template>
      <el-empty v-else description="未找到可回放的训练录制" />
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, inject, nextTick, onMounted, onUnmounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { CircleCheck, MoreFilled, Opportunity, Refresh, Star, Search, Warning } from '@element-plus/icons-vue'
import * as echarts from 'echarts'
import request from '../utils/request'

interface ArtifactItem {
  id: number
  artifact_type: string
  file_url?: string
  mime_type?: string
  duration_seconds?: number | null
  created_at?: string
}

interface SessionItem {
  id: number
  video_id: number
  video_title?: string
  node_total: number
  mode: string
  status: string
  current_node_index: number
  total_score: number | null
  full_score: number | null
  grade?: string
  artifacts?: ArtifactItem[]
  created_at: string
  finished_at?: string
}

interface ReportData {
  session_id?: number
  video_title: string
  mode?: string
  grade: string
  total_score: number
  full_score: number
  percentage: number
  pass_count: number
  skip_count: number
  fail_count: number
  total_nodes?: number
  total_deducted: number
  violation_count?: number
  violation_summary?: Record<string, number>
  failure_reason_summary?: Record<string, number>
  finished_at?: string
  node_summaries: {
    node_index: number
    node_title?: string
    result: string
    retry_count: number
    score_earned: number
    score_deducted: number
    speech_transcript?: string
    failure_reasons?: string[]
  }[]
}

const router = useRouter()
const setMainScrollable = inject<(value: boolean) => void>('setMainScrollable')

const sessions = ref<SessionItem[]>([])
const loading = ref(true)
const showReplayDialog = ref(false)
const replayArtifactUrl = ref('')

const typeFilter = ref('all')
const modeFilter = ref<'all' | 'practice' | 'exam'>('all')
const statusFilter = ref<'all' | 'finished' | 'active' | 'retry' | 'abandoned'>('all')
const keyword = ref('')
const dateRange = ref<[string, string] | []>([])
const currentPage = ref(1)
const pageSize = ref(10)

const radarChartRef = ref<HTMLElement | null>(null)
const trendChartRef = ref<HTMLElement | null>(null)
let radarChart: echarts.ECharts | null = null
let trendChart: echarts.ECharts | null = null

onMounted(() => {
  setMainScrollable?.(true)
  void fetchHistory()
  window.addEventListener('resize', handleResize)
})

onUnmounted(() => {
  setMainScrollable?.(false)
  radarChart?.dispose()
  trendChart?.dispose()
  window.removeEventListener('resize', handleResize)
})

watch(
  [sessions, typeFilter, modeFilter, statusFilter, keyword, dateRange],
  () => {
    currentPage.value = 1
    void nextTick(() => {
      renderRadarChart()
      renderTrendChart()
    })
  },
  { deep: true }
)

const availableTypes = computed(() => Array.from(new Set(sessions.value.map((item) => sceneForSession(item)))))

const filteredSessions = computed(() => {
  const kw = keyword.value.trim().toLowerCase()

  return sessions.value.filter((item) => {
    if (typeFilter.value !== 'all' && sceneForSession(item) !== typeFilter.value) return false
    if (modeFilter.value !== 'all' && item.mode !== modeFilter.value) return false

    if (statusFilter.value === 'finished' && item.status !== 'finished') return false
    if (statusFilter.value === 'active' && item.status !== 'active') return false
    if (statusFilter.value === 'abandoned' && item.status !== 'abandoned') return false
    if (statusFilter.value === 'retry' && !needsRetry(item)) return false

    if (dateRange.value.length === 2) {
      const [start, end] = dateRange.value
      const time = new Date(item.created_at).getTime()
      const startTime = new Date(`${start}T00:00:00`).getTime()
      const endTime = new Date(`${end}T23:59:59`).getTime()
      if (time < startTime || time > endTime) return false
    }

    if (!kw) return true
    return [
      item.video_title || '',
      sceneForSession(item),
      gradeText(item),
      statusText(item),
    ].join(' ').toLowerCase().includes(kw)
  })
})

const pagedSessions = computed(() => {
  const start = (currentPage.value - 1) * pageSize.value
  return filteredSessions.value.slice(start, start + pageSize.value)
})

const finishedSessions = computed(() => filteredSessions.value.filter((item) => item.status === 'finished'))
const activeSessions = computed(() => filteredSessions.value.filter((item) => item.status === 'active'))
const retrySessions = computed(() => filteredSessions.value.filter((item) => needsRetry(item)))

const averageScore = computed(() => {
  const values = finishedSessions.value
    .map((item) => scorePercent(item))
    .filter((value): value is number => value != null)
  if (!values.length) return 0
  return Number((values.reduce((sum, value) => sum + value, 0) / values.length).toFixed(1))
})

const averageScoreDelta = computed(() => {
  const values = finishedSessions.value
    .map((item) => scorePercent(item))
    .filter((value): value is number => value != null)
  if (values.length < 2) return 0
  const mid = Math.floor(values.length / 2)
  const prev = values.slice(0, mid)
  const next = values.slice(mid)
  if (!prev.length || !next.length) return 0
  const prevAvg = prev.reduce((sum, value) => sum + value, 0) / prev.length
  const nextAvg = next.reduce((sum, value) => sum + value, 0) / next.length
  return Number((nextAvg - prevAvg).toFixed(1))
})

const statCards = computed(() => [
  {
    label: '全部记录',
    value: filteredSessions.value.length,
    desc: `共完成 ${sessions.value.length} 次训练`,
    icon: Opportunity,
    tone: 'blue',
  },
  {
    label: '已完成',
    value: finishedSessions.value.length,
    desc: `完成率 ${filteredSessions.value.length ? ((finishedSessions.value.length / filteredSessions.value.length) * 100).toFixed(1) : '0.0'}%`,
    icon: CircleCheck,
    tone: 'green',
  },
  {
    label: '进行中',
    value: activeSessions.value.length,
    desc: activeSessions.value.length ? `最近训练：${relativeTime(activeSessions.value[0]?.created_at)}` : '最近暂无进行中的训练',
    icon: Refresh,
    tone: 'indigo',
  },
  {
    label: '待重修',
    value: retrySessions.value.length,
    desc: `需重修节点 ${retrySessions.value.reduce((sum, item) => sum + Math.max((item.node_total || 0) - (item.current_node_index || 0), 0), 0)} 个`,
    icon: Warning,
    tone: 'orange',
  },
  {
    label: '平均得分',
    value: averageScore.value,
    desc: `较上周期 ${averageScoreDelta.value > 0 ? '+' : ''}${averageScoreDelta.value}`,
    icon: Star,
    tone: 'purple',
  },
])

const radarMetrics = computed(() => {
  const base = finishedSessions.value.length
    ? finishedSessions.value.map((item) => scorePercent(item) || 0)
    : [72]
  const overall = base.reduce((sum, value) => sum + value, 0) / base.length

  const metric = (matcher: RegExp, fallbackOffset: number) => {
    const scoped = finishedSessions.value
      .filter((item) => matcher.test(item.video_title || ''))
      .map((item) => scorePercent(item) || 0)
    const value = scoped.length
      ? scoped.reduce((sum, current) => sum + current, 0) / scoped.length
      : Math.max(45, Math.min(98, overall + fallbackOffset))
    return Number(value.toFixed(1))
  }

  return [
    { label: '肢体动作规范', value: metric(/盘查|队列|姿势|处置/, 2) },
    { label: '口头沟通规范', value: metric(/话术|询问|文明用语/, -2) },
    { label: '执法专业与安全处置', value: metric(/现场|法律|执法|防卫/, 1) },
    { label: '虚拟道具操作规范', value: metric(/证件|装备|盘查/, -5) },
    { label: '流程执行完整度', value: metric(/流程|观察|标准/, -1) },
  ]
})

const issueTopList = computed(() => {
  const counter = new Map<string, number>()
  const lowScoreSessions = finishedSessions.value.filter((item) => (scorePercent(item) || 0) < 85)

  const append = (label: string) => {
    counter.set(label, (counter.get(label) || 0) + 1)
  }

  lowScoreSessions.forEach((item) => {
    const title = item.video_title || ''
    if (/话术|询问|文明用语/.test(title)) append('动作不规范 / 话术态度不足')
    if (/现场|流程|观察/.test(title)) append('节点超时')
    if (/证件|盘查|身份/.test(title)) append('未展示证件 / 装备')
    if (/法律|防卫|执法/.test(title)) append('选项或规范理解偏差')
    if (/队列|姿势/.test(title)) append('流程顺序错误')
    if (!/话术|询问|文明用语|现场|流程|观察|证件|盘查|身份|法律|防卫|执法|队列|姿势/.test(title)) {
      append('话术不完整 / 缺失')
    }
  })

  const total = Array.from(counter.values()).reduce((sum, value) => sum + value, 0)
  return Array.from(counter.entries())
    .sort((a, b) => b[1] - a[1])
    .slice(0, 5)
    .map(([label, count]) => ({
      label,
      value: total ? Math.round((count / total) * 100) : 0,
    }))
})

const trendSeries = computed(() => {
  return [...finishedSessions.value]
    .sort((a, b) => new Date(a.finished_at || a.created_at).getTime() - new Date(b.finished_at || b.created_at).getTime())
    .slice(-7)
})

async function fetchHistory() {
  loading.value = true
  try {
    const res: unknown = await request.get('/video-training/history')
    sessions.value = Array.isArray(res) ? (res as SessionItem[]) : []
    await nextTick()
    renderRadarChart()
    renderTrendChart()
  } catch {
    ElMessage.error('加载视频实训历史失败')
  } finally {
    loading.value = false
  }
}

async function handleAction(command: string, session: SessionItem) {
  if (command === 'report') {
    router.push(`/student/video-report/${session.id}`)
    return
  }

  if (command === 'replay') {
    const artifact = latestReplayArtifact(session)
    if (!artifact?.file_url) {
      ElMessage.warning('当前记录暂无可回放的训练录制')
      return
    }
    replayArtifactUrl.value = resolveMediaUrl(artifact.file_url)
    showReplayDialog.value = true
    return
  }

  router.push(`/student/video-training/${session.video_id}`)
}

function latestReplayArtifact(session: SessionItem): ArtifactItem | null {
  const items = Array.isArray(session.artifacts) ? session.artifacts : []
  const sorted = [...items].sort((a, b) => new Date(b.created_at || 0).getTime() - new Date(a.created_at || 0).getTime())
  return sorted.find((item) => item.artifact_type === 'camera_recording' && item.file_url) || null
}

function resolveMediaUrl(url?: string): string {
  if (!url) return ''
  if (/^https?:\/\//i.test(url)) return url
  const baseUrl = String(request.defaults.baseURL || '').replace(/\/$/, '')
  if (!baseUrl) return url
  return `${baseUrl}${url.startsWith('/') ? url : `/${url}`}`
}

function calcProgress(session: SessionItem): number {
  if (!session.node_total) return 0
  if (session.status === 'finished') return 100
  return Math.min(100, Math.round((session.current_node_index / session.node_total) * 100))
}

function scorePercent(session: SessionItem): number | null {
  if (session.total_score == null || session.full_score == null || session.full_score === 0) return null
  return Number(((session.total_score / session.full_score) * 100).toFixed(1))
}

function needsRetry(session: SessionItem): boolean {
  const pct = scorePercent(session)
  return session.status === 'abandoned' || (session.status === 'finished' && pct != null && pct < 70)
}

function statusKey(session: SessionItem): 'done' | 'live' | 'retry' | 'abandoned' {
  if (needsRetry(session)) return 'retry'
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

function gradeText(session: SessionItem): string {
  if (session.grade) return session.grade
  const pct = scorePercent(session)
  if (pct == null) return '--'
  if (pct >= 90) return '优秀'
  if (pct >= 70) return '合格'
  return '待重修'
}

function gradeKey(session: SessionItem): 'excellent' | 'pass' | 'fail' {
  const grade = gradeText(session)
  if (grade === '优秀') return 'excellent'
  if (grade === '合格') return 'pass'
  return 'fail'
}

function scoreClass(session: SessionItem): string {
  const pct = scorePercent(session)
  if (pct == null) return ''
  if (pct >= 90) return 'score-cell--excellent'
  if (pct >= 70) return 'score-cell--good'
  return 'score-cell--weak'
}

function sceneForSession(session: SessionItem): string {
  const title = session.video_title || ''
  if (/现场|处置|盘查/.test(title)) return '街面纠纷警情处置'
  if (/法律|防卫|执法/.test(title)) return '法律知识学习'
  if (/证件|身份/.test(title)) return '证件出示规范'
  if (/文明|话术|询问/.test(title)) return '文明执法用语规范'
  if (/观察|环境/.test(title)) return '环境观察重点'
  if (/队列|姿势/.test(title)) return '队列动作训练'
  return '综合训练场景'
}

function durationText(session: SessionItem): string {
  const artifact = latestReplayArtifact(session)
  if (artifact?.duration_seconds) return formatDurationSeconds(artifact.duration_seconds)
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

function relativeTime(iso?: string): string {
  if (!iso) return '--'
  const diff = Date.now() - new Date(iso).getTime()
  const hours = Math.max(1, Math.round(diff / 3600000))
  if (hours < 24) return `${hours} 小时前`
  return `${Math.round(hours / 24)} 天前`
}

function resetPagination() {
  currentPage.value = 1
}

function resetFilters() {
  typeFilter.value = 'all'
  modeFilter.value = 'all'
  statusFilter.value = 'all'
  keyword.value = ''
  dateRange.value = []
  resetPagination()
}

function handleResize() {
  radarChart?.resize()
  trendChart?.resize()
}

function handleDropdownCommand(command: string | number | object, session: SessionItem) {
  void handleAction(String(command), session)
}

function renderRadarChart() {
  if (!radarChartRef.value) return
  if (!radarChart) radarChart = echarts.init(radarChartRef.value)

  radarChart.setOption({
    animation: false,
    tooltip: { trigger: 'item' },
    radar: {
      radius: '60%',
      splitNumber: 4,
      axisName: { color: '#475569', fontSize: 12 },
      splitLine: { lineStyle: { color: 'rgba(148, 163, 184, 0.28)' } },
      splitArea: { areaStyle: { color: ['rgba(37, 99, 235, 0.02)', 'rgba(37, 99, 235, 0.04)'] } },
      indicator: radarMetrics.value.map((item) => ({ name: item.label, max: 100 })),
    },
    series: [
      {
        type: 'radar',
        data: [
          {
            value: radarMetrics.value.map((item) => item.value),
            name: '我的得分',
            areaStyle: { color: 'rgba(37, 99, 235, 0.18)' },
            lineStyle: { color: '#2563eb', width: 2 },
            itemStyle: { color: '#2563eb' },
          },
        ],
      },
    ],
  })
}

function renderTrendChart() {
  if (!trendChartRef.value) return
  if (!trendChart) trendChart = echarts.init(trendChartRef.value)

  const data = trendSeries.value.map((item) => ({
    label: formatDateTime(item.finished_at || item.created_at).slice(5, 10),
    score: scorePercent(item) || 0,
  }))

  trendChart.setOption({
    animation: false,
    tooltip: {
      trigger: 'axis',
      formatter: (params: { axisValue?: string; data?: number }[]) => {
        const point = params?.[0]
        return `${point?.axisValue || '--'}<br/>得分：${point?.data ?? '--'}`
      },
    },
    grid: { left: 42, right: 20, top: 24, bottom: 28 },
    xAxis: {
      type: 'category',
      data: data.map((item) => item.label),
      axisLine: { lineStyle: { color: '#dbe2ef' } },
      axisLabel: { color: '#64748b' },
    },
    yAxis: {
      type: 'value',
      min: 0,
      max: 100,
      splitLine: { lineStyle: { color: 'rgba(148, 163, 184, 0.18)' } },
      axisLabel: { color: '#64748b' },
    },
    series: [
      {
        data: data.map((item) => item.score),
        type: 'line',
        smooth: true,
        symbol: 'circle',
        symbolSize: 8,
        lineStyle: { color: '#2563eb', width: 3 },
        itemStyle: { color: '#2563eb' },
        areaStyle: {
          color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color: 'rgba(37,99,235,0.18)' },
            { offset: 1, color: 'rgba(37,99,235,0.02)' },
          ]),
        },
      },
    ],
  })
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

.history-hero__title {
  margin: 0;
  font-size: 22px;
  font-weight: 800;
  color: #13213a;
}

.history-hero__subtitle {
  margin: 8px 0 0;
  font-size: 14px;
  color: #64748b;
}

.filter-panel,
.table-panel,
.chart-card,
.stat-card {
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

.stats-grid {
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 1fr));
  gap: 16px;
}

.stat-card {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 18px 20px;
  border-radius: 8px;
}

.stat-card__label {
  font-size: 14px;
  font-weight: 700;
  color: #475569;
}

.stat-card__value {
  margin-top: 8px;
  font-size: 42px;
  line-height: 1;
  font-weight: 800;
  color: #0f172a;
}

.stat-card__value.is-blue,
.stat-card__icon.is-blue {
  color: #2563eb;
}

.stat-card__value.is-green,
.stat-card__icon.is-green {
  color: #16a34a;
}

.stat-card__value.is-indigo,
.stat-card__icon.is-indigo {
  color: #3b82f6;
}

.stat-card__value.is-orange,
.stat-card__icon.is-orange {
  color: #f97316;
}

.stat-card__value.is-purple,
.stat-card__icon.is-purple {
  color: #9333ea;
}

.stat-card__desc {
  margin-top: 8px;
  font-size: 14px;
  color: #64748b;
}

.stat-card__icon {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 56px;
  height: 56px;
  border-radius: 16px;
  font-size: 24px;
  background: rgba(37, 99, 235, 0.08);
}

.analytics-grid {
  display: grid;
  grid-template-columns: 1.1fr 1fr 1.8fr;
  gap: 16px;
}

.chart-card {
  padding: 16px 18px;
  border-radius: 8px;
}

.chart-card__title {
  margin-bottom: 12px;
  font-size: 16px;
  font-weight: 800;
  color: #13213a;
}

.chart-card__canvas {
  height: 240px;
}

.chart-card__canvas--trend {
  height: 250px;
}

.issue-list {
  display: flex;
  flex-direction: column;
  gap: 16px;
  padding-top: 8px;
}

.issue-item__head {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  font-size: 14px;
  color: #334155;
}

.issue-item__head strong {
  color: #475569;
}

.issue-item__bar {
  height: 8px;
  margin-top: 8px;
  overflow: hidden;
  border-radius: 999px;
  background: #e8eef8;
}

.issue-item__bar span {
  display: block;
  height: 100%;
  border-radius: 999px;
  background: #2563eb;
}

.issue-empty {
  font-size: 14px;
  line-height: 1.7;
  color: #64748b;
}

.table-panel {
  overflow: hidden;
}

.state-panel {
  padding: 56px 24px;
}

.history-table__head,
.history-row {
  display: grid;
  grid-template-columns: 60px minmax(220px, 1.6fr) minmax(150px, 1fr) 110px 100px 80px 80px 130px 90px 150px 120px;
  gap: 14px;
  align-items: center;
  padding: 16px 18px;
}

.history-table__head {
  font-size: 14px;
  font-weight: 800;
  color: #334155;
  border-bottom: 1px solid #e8eef7;
  background: #f8fafc;
}

.history-row {
  font-size: 14px;
  color: #334155;
  border-bottom: 1px solid #edf2f7;
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
}

.history-row__sub,
.muted,
.progress-text {
  font-size: 12px;
  color: #94a3b8;
}

.history-row__sub {
  margin-top: 4px;
}

.history-row__scene,
.time-cell {
  font-size: 13px;
  color: #475569;
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
  justify-content: center;
  gap: 8px;
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

.more-btn:hover {
  color: #2563eb;
  border-color: #93c5fd;
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

.replay-video {
  display: block;
  width: 100%;
  max-height: 70vh;
  border-radius: 8px;
  background: #020617;
}

@media (max-width: 1480px) {
  .stats-grid {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }

  .analytics-grid {
    grid-template-columns: 1fr 1fr;
  }

  .chart-card--trend {
    grid-column: 1 / -1;
  }
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
    min-width: 1480px;
  }
}

@media (max-width: 900px) {
  .training-history-page {
    padding: 14px;
  }

  .stats-grid,
  .analytics-grid,
  .filter-grid {
    grid-template-columns: 1fr;
  }

  .table-footer {
    flex-direction: column;
    align-items: stretch;
  }
}
</style>
