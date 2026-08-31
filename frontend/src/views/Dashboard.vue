<template>
  <div class="admin-workbench">
    <div v-if="loading" class="workbench-state">
      <van-loading color="#1d4ed8" size="24">正在加载工作台数据...</van-loading>
    </div>

    <div v-else-if="pageError" class="workbench-state workbench-state--warning">
      <van-icon name="warning-o" size="36" class="text-amber-500" />
      <p class="mt-4 text-base font-bold text-amber-800">{{ pageError }}</p>
      <p class="mt-2 text-sm text-amber-700">当前无法获取工作台数据，你可以稍后重试。</p>
      <van-button plain type="primary" class="mt-6" @click="fetchStats">重新加载</van-button>
    </div>

    <template v-else>
      <div v-if="staleMessage" class="workbench-notice">
        {{ staleMessage }}
      </div>

      <section class="summary-grid">
        <button
          v-for="item in summaryCards"
          :key="item.title"
          type="button"
          class="summary-card"
          :class="item.tone"
          @click="goTo(item.route)"
        >
          <div class="summary-icon">
            <van-icon :name="item.icon" />
          </div>
          <div class="summary-copy">
            <span>{{ item.title }}</span>
            <strong>{{ item.value }}</strong>
            <small>{{ item.note }}</small>
          </div>
        </button>
      </section>

      <section class="panel-grid panel-grid--top">
        <article class="panel panel--wide">
          <div class="panel-head">
            <div>
              <h3>近 7 日训练完成量</h3>
              <p>普通训练 / 视频实训</p>
            </div>
            <van-button text type="primary" size="small" @click="goTo('/admin/video-sessions')">
              查看会话
            </van-button>
          </div>

          <div class="bar-chart">
            <div
              v-for="item in trend"
              :key="item.key"
              class="bar-column"
            >
              <div
                class="bar"
                :style="{ height: `${getBarHeight(item.count + Number(item.video_count || 0))}px` }"
                :title="`文字训练 ${item.count} 次 / 视频实训 ${Number(item.video_count || 0)} 次`"
              ></div>
              <span>{{ item.label }}</span>
            </div>
          </div>
        </article>

        <article class="panel">
          <div class="panel-head">
            <div>
              <h3>平台内容状态</h3>
              <p>按内容流转和训练状态汇总</p>
            </div>
          </div>

          <div class="donut-layout">
            <div class="donut" :style="contentRingStyle">
              <div class="donut-core">
                <strong>{{ completionRateText }}</strong>
                <span>完成率</span>
              </div>
            </div>

            <div class="legend-list">
              <div
                v-for="item in contentSegments"
                :key="item.label"
                class="legend-item"
              >
                <span class="legend-dot" :style="{ background: item.color }"></span>
                <div class="legend-copy">
                  <strong>{{ item.label }}</strong>
                  <span>{{ formatNumber(item.value) }} 条</span>
                </div>
                <em>{{ item.percent }}%</em>
              </div>
            </div>
          </div>
        </article>
      </section>

      <section class="panel-grid panel-grid--bottom">
        <article class="panel">
          <div class="panel-head">
            <div>
              <h3>待处理事项</h3>
              <p>按最近缺口和会话状态整理</p>
            </div>
            <van-button text type="primary" size="small" @click="goTo('/admin/video-sessions')">
              查看全部
            </van-button>
          </div>

          <div class="task-list">
            <div
              v-for="item in pendingTasks"
              :key="item.title"
              class="task-row"
            >
              <span class="task-tag" :class="item.tone">{{ item.tag }}</span>
              <div class="task-copy">
                <strong>{{ item.title }}</strong>
                <span>{{ item.meta }}</span>
              </div>
              <div class="task-count">{{ item.count }}</div>
              <van-button plain type="primary" size="small" @click="goTo(item.route)">
                {{ item.action }}
              </van-button>
            </div>
          </div>
        </article>

        <article class="panel">
          <div class="panel-head">
            <div>
              <h3>快捷入口</h3>
              <p>常用管理页面一键跳转</p>
            </div>
          </div>

          <div class="quick-grid">
            <button
              v-for="item in quickActions"
              :key="item.title"
              type="button"
              class="quick-card"
              @click="goTo(item.route)"
            >
              <div class="quick-icon" :class="item.tone">
                <van-icon :name="item.icon" />
              </div>
              <div class="quick-copy">
                <strong>{{ item.title }}</strong>
                <span>{{ item.desc }}</span>
              </div>
            </button>
          </div>
        </article>
      </section>
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import request from '../utils/request'

type TrendItem = {
  label: string
  count: number
  video_count?: number
  key: string
}

type SummaryCard = {
  title: string
  value: string
  note: string
  icon: string
  tone: string
  route: string
}

type StatusSegment = {
  label: string
  value: number
  color: string
  percent: number
}

type TaskItem = {
  tag: string
  title: string
  meta: string
  count: string
  action: string
  route: string
  tone: string
}

type QuickAction = {
  title: string
  desc: string
  icon: string
  route: string
  tone: string
}

type DashboardStats = {
  cases: number
  roles: number
  rag: number
  sessions: number
  students: number
  today_sessions: number
  active_sessions: number
  finished_sessions: number
  video_sessions: number
  video_active_sessions: number
  video_finished_sessions: number
  completion_rate: number
  active_rate: number
  peak_daily_sessions: number
  avg_daily_sessions: number
  stage_gap_reports: number
  stage_gap_top_missing: Array<{ label: string; count: number }>
  stage_gap_scene_risk: Array<{ scene_type: string; count: number }>
  trend: Array<{ label: string; count: number }>
  updated_at: string
}

const router = useRouter()
const refreshTimer = ref<number | null>(null)
const loading = ref(true)
const pageError = ref('')
const staleMessage = ref('')
const statsData = ref<DashboardStats>({
  cases: 0,
  roles: 0,
  rag: 0,
  sessions: 0,
  students: 0,
  today_sessions: 0,
  active_sessions: 0,
  finished_sessions: 0,
  video_sessions: 0,
  video_active_sessions: 0,
  video_finished_sessions: 0,
  completion_rate: 0,
  active_rate: 0,
  peak_daily_sessions: 0,
  avg_daily_sessions: 0,
  stage_gap_reports: 0,
  stage_gap_top_missing: [],
  stage_gap_scene_risk: [],
  trend: [],
  updated_at: '',
})

const trend = computed<TrendItem[]>(() => {
  const source = Array.isArray(statsData.value.trend) && statsData.value.trend.length
    ? statsData.value.trend
    : Array.from({ length: 7 }, (_, index) => ({
      label: '--',
      count: 0,
      key: `empty-${index}`,
    }))

  return source.map((item, index) => ({
    label: item.label || '--',
    count: Number(item.count || 0),
    video_count: Number((item as any).video_count || 0),
    key: `${item.label || 'empty'}-${index}`,
  }))
})

const trendMax = computed(() => Math.max(
  ...trend.value.map((item) => item.count + Number(item.video_count || 0)),
  1,
))

const finishedSessions = computed(() => Number(statsData.value.finished_sessions || 0))
const videoSessionCount = computed(() => Number(statsData.value.video_sessions || 0))
const videoFinishedSessions = computed(() => Number(statsData.value.video_finished_sessions || 0))
const videoActiveSessions = computed(() => Number(statsData.value.video_active_sessions || 0))
const activeSessions = computed(() => Number(statsData.value.active_sessions || 0))
const sessionCount = computed(() => Number(statsData.value.sessions || 0))
const studentCount = computed(() => Number(statsData.value.students || 0))
const ragCount = computed(() => Number(statsData.value.rag || 0))
const stageGapReports = computed(() => Number(statsData.value.stage_gap_reports || 0))
const topMissing = computed(() => statsData.value.stage_gap_top_missing || [])
const sceneRisk = computed(() => statsData.value.stage_gap_scene_risk || [])
const completionRate = computed(() => clampPercent(statsData.value.completion_rate))
const completionRateText = computed(() => `${completionRate.value.toFixed(0)}%`)

const summaryCards = computed<SummaryCard[]>(() => [
  {
    title: '案件与场景',
    value: formatNumber(statsData.value.cases),
    note: `近 7 日缺口 ${formatNumber(stageGapReports.value)} 项`,
    icon: 'orders-o',
    tone: 'tone-blue',
    route: '/admin/cases',
  },
  {
    title: '在训学员',
    value: formatNumber(studentCount.value),
    note: `角色模板 ${formatNumber(statsData.value.roles)} 个`,
    icon: 'friends-o',
    tone: 'tone-green',
    route: '/admin/students',
  },
  {
    title: '普通训练会话',
    value: formatNumber(sessionCount.value),
    note: `已完成 ${formatNumber(finishedSessions.value)} 条`,
    icon: 'todo-list-o',
    tone: 'tone-amber',
    route: '/admin/text-sessions',
  },
  {
    title: '视频实训会话',
    value: formatNumber(videoSessionCount.value),
    note: `进行中 ${formatNumber(videoActiveSessions.value)} 条，已完成 ${formatNumber(videoFinishedSessions.value)} 条`,
    icon: 'video-o',
    tone: 'tone-purple',
    route: '/admin/video-sessions',
  },
])

const contentSegments = computed<StatusSegment[]>(() => {
  const raw = [
    { label: '已发布案例', value: Number(statsData.value.cases || 0), color: '#4f6cf7' },
    { label: '文字训练完成', value: finishedSessions.value, color: '#30b96c' },
    { label: '视频实训进行中', value: videoActiveSessions.value, color: '#f6ab48' },
    { label: '视频实训完成', value: videoFinishedSessions.value, color: '#8b5cf6' },
  ]
  const total = raw.reduce((sum, item) => sum + item.value, 0) || 1

  return raw.map((item) => ({
    ...item,
    percent: Math.round((item.value / total) * 100),
  }))
})

const contentRingStyle = computed(() => {
  const total = contentSegments.value.reduce((sum, item) => sum + item.value, 0)
  if (!total) {
    return { background: 'conic-gradient(#e2e8f0 0deg 360deg)' }
  }

  let angle = 0
  const parts = contentSegments.value.map((item) => {
    const start = angle
    const span = (item.value / total) * 360
    angle += span
    return `${item.color} ${start}deg ${angle}deg`
  })

  return {
    background: `conic-gradient(${parts.join(', ')})`,
  }
})

const pendingTasks = computed<TaskItem[]>(() => {
  const topGap = topMissing.value[0]
  const topScene = sceneRisk.value[0]

  return [
    {
      tag: '内容',
      title: topGap ? `案例解析候选人工确认：${topGap.label}` : '案例解析候选人工确认',
      meta: topGap
        ? `近 7 日出现 ${formatNumber(topGap.count)} 次`
        : '暂时没有高频缺口，继续保持训练覆盖。',
      count: topGap ? `${formatNumber(topGap.count)} 次` : `${formatNumber(stageGapReports.value)} 项`,
      action: '处理',
      route: '/admin/cases',
      tone: 'tone-amber',
    },
    {
      tag: '视频',
      title: topScene ? `视频分析待复核：${topScene.scene_type}` : '视频训练报告待复核',
      meta: topScene
        ? `相关会话 ${formatNumber(topScene.count)} 条`
        : `视频实训完成 ${formatNumber(videoFinishedSessions.value)} 条`,
      count: topScene ? `${formatNumber(topScene.count)} 条` : `${formatNumber(videoActiveSessions.value)} 条`,
      action: '处理',
      route: '/admin/video-sessions',
      tone: 'tone-blue',
    },
    {
      tag: '学员',
      title: '学员档案与验证检查',
      meta: `在训学员 ${formatNumber(studentCount.value)} 人，建议检查基础信息完整性`,
      count: `${formatNumber(studentCount.value)} 人`,
      action: '处理',
      route: '/admin/students',
      tone: 'tone-green',
    },
    {
      tag: '知识',
      title: '知识片段补充整理',
      meta: `RAG 片段 ${formatNumber(ragCount.value)} 条，可继续补充训练材料`,
      count: `${formatNumber(ragCount.value)} 条`,
      action: '处理',
      route: '/admin/knowledge',
      tone: 'tone-purple',
    },
  ]
})

const quickActions = computed<QuickAction[]>(() => [
  {
    title: '案件解析',
    desc: '结构化导入材料',
    icon: 'orders-o',
    route: '/admin/cases',
    tone: 'tone-blue',
  },
  {
    title: '发布作业',
    desc: '下发班级训练',
    icon: 'todo-list-o',
    route: '/admin/classes',
    tone: 'tone-green',
  },
  {
    title: '上传视频',
    desc: '自动分析与节点生成',
    icon: 'video-o',
    route: '/admin/videos',
    tone: 'tone-purple',
  },
  {
    title: '训练统计',
    desc: '查看完成率和平均值',
    icon: 'bar-chart-o',
    route: '/admin/video-sessions',
    tone: 'tone-amber',
  },
])

function goTo(path: string) {
  router.push(path)
}

function clampPercent(value: number) {
  if (!Number.isFinite(value)) return 0
  return Math.max(0, Math.min(100, Number(value)))
}

function formatNumber(value: number) {
  return new Intl.NumberFormat('zh-CN').format(Number(value || 0))
}

function getBarHeight(count: number) {
  return Math.max(24, (count / trendMax.value) * 160)
}

async function fetchStats(options: { background?: boolean } = {}) {
  if (!options.background) {
    loading.value = true
  }

  try {
    const res: any = await request.get('/dashboard/stats')
    statsData.value = {
      ...statsData.value,
      ...(res || {}),
    }
    pageError.value = ''
    staleMessage.value = ''
  } catch (error) {
    console.error('Dashboard stats error:', error)
    if (loading.value) {
      pageError.value = '工作台数据加载失败'
    } else {
      staleMessage.value = '自动刷新失败，当前展示的是最近一次成功加载的数据。'
    }
  } finally {
    if (!options.background) {
      loading.value = false
    }
  }
}

onMounted(async () => {
  await fetchStats()
  refreshTimer.value = window.setInterval(() => fetchStats({ background: true }), 30000)
})

onUnmounted(() => {
  if (refreshTimer.value) {
    window.clearInterval(refreshTimer.value)
    refreshTimer.value = null
  }
})
</script>

<style scoped>
.admin-workbench {
  display: flex;
  flex-direction: column;
  gap: 16px;
  padding-bottom: 24px;
}

.workbench-state {
  min-height: 220px;
  display: grid;
  place-items: center;
  text-align: center;
  background: #fff;
  border: 1px solid #e6ebf3;
  border-radius: 8px;
  box-shadow: 0 4px 16px rgba(35, 56, 104, 0.06);
}

.workbench-state--warning {
  background: #fffaf0;
  border-color: #f6d99b;
}

.workbench-notice {
  border: 1px solid #f6d99b;
  border-radius: 8px;
  background: #fffaf0;
  color: #8a5a11;
  padding: 12px 14px;
  font-size: 13px;
}

.summary-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 16px;
}

.summary-card {
  min-width: 0;
  display: flex;
  align-items: center;
  gap: 16px;
  width: 100%;
  min-height: 104px;
  padding: 18px 20px;
  border: 1px solid #e6ebf3;
  border-radius: 8px;
  background: #fff;
  color: inherit;
  font: inherit;
  text-align: left;
  cursor: pointer;
  appearance: none;
  box-shadow: 0 4px 16px rgba(35, 56, 104, 0.06);
  transition:
    transform 0.18s ease,
    box-shadow 0.18s ease,
    border-color 0.18s ease;
}

.summary-card:hover {
  transform: translateY(-1px);
  border-color: #cfdaf1;
  box-shadow: 0 8px 22px rgba(35, 56, 104, 0.08);
}

.summary-icon {
  width: 48px;
  height: 48px;
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex: none;
  font-size: 22px;
}

.tone-blue .summary-icon,
.tone-blue .quick-icon {
  color: #4f6cf7;
  background: #e8efff;
}

.tone-green .summary-icon,
.tone-green .quick-icon {
  color: #2fbf71;
  background: #e8f8ef;
}

.tone-amber .summary-icon,
.tone-amber .quick-icon {
  color: #f59e0b;
  background: #fff4df;
}

.tone-purple .summary-icon,
.tone-purple .quick-icon {
  color: #8b5cf6;
  background: #f1e9ff;
}

.summary-copy {
  min-width: 0;
}

.summary-copy span {
  color: #8b96aa;
  font-size: 12px;
}

.summary-copy strong {
  display: block;
  margin-top: 6px;
  color: #17213b;
  font-size: 28px;
  font-weight: 800;
  line-height: 1;
}

.summary-copy small {
  display: block;
  margin-top: 8px;
  color: #29b765;
  font-size: 12px;
}

.panel-grid {
  display: grid;
  gap: 16px;
}

.panel-grid--top {
  grid-template-columns: minmax(0, 2fr) minmax(320px, 1fr);
}

.panel-grid--bottom {
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.panel {
  min-width: 0;
  padding: 20px;
  border: 1px solid #e6ebf3;
  border-radius: 8px;
  background: #fff;
  box-shadow: 0 4px 16px rgba(35, 56, 104, 0.06);
}

.panel--wide {
  min-height: 330px;
}

.panel-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
}

.panel-head h3 {
  margin: 0;
  color: #17213b;
  font-size: 17px;
  font-weight: 800;
}

.panel-head p {
  margin: 8px 0 0;
  color: #8b96aa;
  font-size: 12px;
}

.bar-chart {
  height: 220px;
  display: flex;
  align-items: flex-end;
  gap: 18px;
  padding: 22px 8px 0;
  border-bottom: 1px solid #e5eaf1;
}

.bar-column {
  height: 100%;
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: flex-end;
  gap: 8px;
}

.bar {
  width: 34px;
  min-height: 8px;
  border-radius: 7px 7px 0 0;
  background: linear-gradient(180deg, #4f6cf7, #a7b6ff);
}

.bar-column span {
  color: #8b96aa;
  font-size: 12px;
}

.donut-layout {
  display: grid;
  grid-template-columns: 190px minmax(0, 1fr);
  align-items: center;
  gap: 16px;
  min-height: 248px;
}

.donut {
  position: relative;
  width: 164px;
  height: 164px;
  margin: 0 auto;
  border-radius: 50%;
}

.donut::after {
  content: '';
  position: absolute;
  inset: 28px;
  border-radius: 50%;
  background: #fff;
}

.donut-core {
  position: absolute;
  inset: 28px;
  z-index: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  text-align: center;
}

.donut-core strong {
  color: #17213b;
  font-size: 30px;
  font-weight: 800;
  line-height: 1;
}

.donut-core span {
  margin-top: 6px;
  color: #8b96aa;
  font-size: 12px;
}

.legend-list {
  display: grid;
  gap: 14px;
}

.legend-item {
  display: grid;
  grid-template-columns: 10px minmax(0, 1fr) auto;
  align-items: center;
  gap: 10px;
}

.legend-dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
}

.legend-copy {
  min-width: 0;
}

.legend-copy strong,
.legend-copy span {
  display: block;
}

.legend-copy strong {
  color: #253047;
  font-size: 13px;
}

.legend-copy span {
  margin-top: 4px;
  color: #8b96aa;
  font-size: 12px;
}

.legend-item em {
  color: #4f6cf7;
  font-size: 12px;
  font-style: normal;
  font-weight: 800;
}

.task-list {
  display: grid;
  gap: 6px;
  margin-top: 14px;
}

.task-row {
  display: grid;
  grid-template-columns: 72px minmax(0, 1fr) 82px auto;
  gap: 12px;
  align-items: center;
  min-height: 58px;
  padding: 12px 4px;
  border-bottom: 1px solid #edf1f6;
}

.task-row:last-child {
  border-bottom: 0;
}

.task-tag {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  height: 28px;
  border-radius: 8px;
  border: 1px solid transparent;
  font-size: 12px;
  font-weight: 700;
}

.task-tag.tone-blue {
  border-color: #cfdaf1;
  color: #4f6cf7;
  background: #eef3ff;
}

.task-tag.tone-green {
  border-color: #cfeedd;
  color: #30a768;
  background: #eefaf4;
}

.task-tag.tone-amber {
  border-color: #f8ddb4;
  color: #f59e0b;
  background: #fff8eb;
}

.task-tag.tone-purple {
  border-color: #e2d4ff;
  color: #8b5cf6;
  background: #f6efff;
}

.task-copy {
  min-width: 0;
}

.task-copy strong {
  display: block;
  color: #253047;
  font-size: 13px;
  font-weight: 700;
}

.task-copy span {
  display: block;
  margin-top: 5px;
  color: #8b96aa;
  font-size: 12px;
}

.task-count {
  color: #253047;
  font-size: 13px;
  font-weight: 700;
  text-align: right;
}

.quick-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
  margin-top: 14px;
}

.quick-card {
  display: flex;
  align-items: center;
  gap: 10px;
  width: 100%;
  min-height: 82px;
  padding: 14px;
  border: 1px solid #e6ebf3;
  border-radius: 8px;
  background: #fafbfd;
  color: inherit;
  font: inherit;
  appearance: none;
  cursor: pointer;
  text-align: left;
  transition:
    transform 0.18s ease,
    border-color 0.18s ease,
    background-color 0.18s ease;
}

.quick-card:hover {
  transform: translateY(-1px);
  border-color: #d0dbf0;
  background: #f6f9ff;
}

.quick-icon {
  width: 44px;
  height: 44px;
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex: none;
  font-size: 20px;
}

.quick-copy {
  min-width: 0;
}

.quick-copy strong {
  display: block;
  color: #17213b;
  font-size: 13px;
  font-weight: 800;
}

.quick-copy span {
  display: block;
  margin-top: 5px;
  color: #8b96aa;
  font-size: 12px;
}

@media (max-width: 1200px) {
  .summary-grid,
  .panel-grid--bottom {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .panel-grid--top {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 760px) {
  .summary-grid,
  .panel-grid--bottom,
  .quick-grid,
  .donut-layout {
    grid-template-columns: 1fr;
  }

  .summary-card {
    min-height: 96px;
  }

  .task-row {
    grid-template-columns: 1fr;
    gap: 8px;
  }

  .task-count {
    text-align: left;
  }
}
</style>
