<template>
  <div class="space-y-8 pb-20">
    <div v-if="loading" class="rounded-3xl border border-slate-200 bg-white py-24 text-center">
      <van-loading color="#1D3557" size="24">正在加载总览数据...</van-loading>
    </div>

    <div v-else-if="pageError" class="rounded-3xl border border-amber-200 bg-amber-50 px-6 py-16 text-center">
      <van-icon name="warning-o" size="36" class="text-amber-500" />
      <p class="mt-4 text-base font-bold text-amber-800">{{ pageError }}</p>
      <p class="mt-2 text-sm text-amber-700">当前无法获取管理端总览数据，你可以立即重试。</p>
      <van-button plain type="primary" class="mt-6" @click="fetchStats">重新加载</van-button>
    </div>

    <template v-else>
      <div
        v-if="staleMessage"
        class="rounded-2xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800"
      >
        {{ staleMessage }}
      </div>

    <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
      <div
        v-for="item in stats"
        :key="item.key"
        class="bg-white p-6 rounded-2xl shadow-sm border border-gray-100 flex items-center space-x-4"
      >
        <div class="w-12 h-12 flex items-center justify-center rounded-xl text-2xl" :class="item.badgeClass">
          <van-icon :name="item.icon" />
        </div>
        <div class="min-w-0">
          <div class="text-gray-400 text-[10px] font-black uppercase tracking-widest">{{ item.title }}</div>
          <div class="text-2xl font-black text-gray-800">{{ item.val }}</div>
          <div class="text-xs text-gray-400 mt-1">{{ item.note }}</div>
        </div>
      </div>
    </div>

    <div class="grid grid-cols-1 lg:grid-cols-3 gap-8">
      <div class="lg:col-span-2 bg-white rounded-3xl shadow-sm border border-gray-100 p-8">
        <div class="flex items-center justify-between mb-8">
          <div>
            <h3 class="font-bold text-gray-800 text-lg flex items-center">
              <span class="w-1.5 h-6 bg-[#1D3557] rounded-full mr-3"></span>
              近 7 日训练活跃度
            </h3>
            <p class="text-xs text-gray-400 mt-2">按训练会话创建时间实时统计，每 30 秒自动刷新一次</p>
          </div>
          <div class="text-right">
            <div class="text-[10px] uppercase font-black tracking-[0.2em] text-gray-400">Updated</div>
            <div class="text-sm font-bold text-[#1D3557]">{{ updatedAtText }}</div>
          </div>
        </div>

        <div class="h-56 flex items-end justify-between px-4 space-x-4">
          <div
            v-for="item in trend"
            :key="item.label"
            class="flex-1 flex flex-col items-center group"
          >
            <div
              class="w-full rounded-t-lg transition-all cursor-default relative bg-[#457B9D]/20 group-hover:bg-[#1D3557]"
              :style="{ height: `${getBarHeight(item.count)}px` }"
            >
              <div class="opacity-0 group-hover:opacity-100 absolute -top-8 left-1/2 -translate-x-1/2 bg-gray-800 text-white text-[10px] py-1 px-2 rounded whitespace-nowrap z-10 transition-opacity">
                {{ item.count }} 次
              </div>
            </div>
            <span class="text-[10px] text-gray-400 mt-3 font-medium">{{ item.label }}</span>
          </div>
        </div>
      </div>

      <div class="bg-white rounded-3xl shadow-sm border border-gray-100 p-8 flex flex-col">
        <h3 class="font-bold text-gray-800 text-lg mb-6">训练运行状态</h3>
        <div class="flex-1 flex flex-col justify-center space-y-8">
          <div class="space-y-2">
            <div class="flex justify-between text-xs font-bold">
              <span class="text-gray-400">会话完成率</span>
              <span class="text-[#1D3557]">{{ completionRateText }}</span>
            </div>
            <van-progress :percentage="completionRate" stroke-width="4" color="#1D3557" track-color="#f2f3f5" :show-pivot="false" />
          </div>
          <div class="space-y-2">
            <div class="flex justify-between text-xs font-bold">
              <span class="text-gray-400">进行中占比</span>
              <span class="text-green-500">{{ activeRateText }}</span>
            </div>
            <van-progress :percentage="activeRate" stroke-width="4" color="#10b981" track-color="#f2f3f5" :show-pivot="false" />
          </div>
          <div class="space-y-2">
            <div class="flex justify-between text-xs font-bold">
              <span class="text-gray-400">今日训练量 / 近 7 日峰值</span>
              <span class="text-orange-500">{{ todaySessions }}/{{ peakDailySessions }}</span>
            </div>
            <van-progress :percentage="todayVsPeakRate" stroke-width="4" color="#f59e0b" track-color="#f2f3f5" :show-pivot="false" />
          </div>
        </div>
      </div>
    </div>

    <div class="grid grid-cols-1 md:grid-cols-2 gap-8">
      <div class="bg-[#1D3557] rounded-3xl shadow-xl p-8 text-white relative overflow-hidden group cursor-pointer" @click="router.push('/admin/knowledge')">
        <div class="absolute right-[-20px] bottom-[-20px] opacity-10 group-hover:scale-110 transition-transform">
          <van-icon name="cluster" size="180" />
        </div>
        <div class="relative z-10 space-y-4">
          <h3 class="text-xl font-bold flex items-center">
            <van-icon name="points" class="mr-3" /> 知识库实时概览
          </h3>
          <p class="text-sm text-blue-200/80 leading-loose max-w-[80%]">
            当前已入库 {{ ragCount }} 条知识片段，可直接支撑案件训练、对话问询与评估辅助分析。
          </p>
          <div class="pt-4 flex items-center text-xs font-black uppercase tracking-widest text-blue-300">
            前往管理 <van-icon name="arrow" class="ml-2" />
          </div>
        </div>
      </div>

      <div class="bg-white rounded-3xl shadow-sm p-8 border border-gray-100 flex flex-col justify-between group cursor-pointer hover:shadow-md transition-all">
        <div>
          <div class="w-14 h-14 bg-indigo-50 border border-indigo-100 rounded-2xl flex items-center justify-center mb-6">
            <van-icon name="friends-o" class="text-2xl text-indigo-600" />
          </div>
          <h3 class="font-bold text-gray-800 text-lg mb-2">学员训练动态</h3>
          <p class="text-sm text-gray-400 leading-relaxed">
            当前学员总数 {{ studentCount }} 人，进行中会话 {{ activeSessions }} 个，近 7 日日均训练 {{ avgDailySessions }} 次。
          </p>
        </div>
        <div class="pt-6 flex justify-end">
          <van-button
            plain
            round
            size="small"
            class="!border-gray-200 !text-gray-600 px-6 hover:!bg-gray-50 transition-colors"
            @click="router.push('/admin/students')"
          >
            查看学员表现
          </van-button>
        </div>
      </div>
    </div>

    <div class="grid grid-cols-1 xl:grid-cols-2 gap-8">
      <div class="bg-white rounded-3xl shadow-sm border border-gray-100 p-8">
        <div class="flex items-center justify-between mb-6">
          <div>
            <h3 class="font-bold text-gray-800 text-lg">班级高频缺口</h3>
            <p class="text-xs text-gray-400 mt-2">基于已完成训练报告里的阶段缺口摘要聚合</p>
          </div>
          <div class="text-right">
            <div class="text-[10px] uppercase font-black tracking-[0.2em] text-gray-400">Reports</div>
            <div class="text-sm font-bold text-[#1D3557]">{{ stageGapReports }}</div>
          </div>
        </div>

        <div v-if="topMissing.length" class="space-y-4">
          <button
            v-for="item in topMissing"
            :key="item.label"
            type="button"
            class="block w-full space-y-2 rounded-2xl px-3 py-3 text-left transition-colors hover:bg-orange-50"
            @click="router.push({ path: '/admin/students', query: { gap: item.label, sort: 'risk' } })"
          >
            <div class="flex items-center justify-between text-sm">
              <span class="font-semibold text-gray-700">{{ item.label }}</span>
              <span class="text-[#c2410c] font-bold">{{ item.count }} 次</span>
            </div>
            <van-progress
              :percentage="getGapPercent(item.count, topMissing[0]?.count || 1)"
              stroke-width="6"
              color="#f97316"
              track-color="#f5f5f5"
              :show-pivot="false"
            />
          </button>
        </div>
        <div v-else class="text-sm text-gray-400">当前完成训练较少，暂未形成稳定缺口统计。</div>
      </div>

      <div class="bg-white rounded-3xl shadow-sm border border-gray-100 p-8">
        <h3 class="font-bold text-gray-800 text-lg mb-2">高风险场景类型</h3>
        <p class="text-xs text-gray-400 mb-6">出现阶段缺口次数最多的训练场景类型</p>
        <div v-if="sceneRisk.length" class="grid gap-4">
          <div
            v-for="item in sceneRisk"
            :key="item.scene_type"
            class="rounded-2xl border border-gray-100 bg-[#f8fbff] px-4 py-4 flex items-center justify-between"
          >
            <div>
              <div class="text-sm font-bold text-gray-800">{{ item.scene_type }}</div>
              <div class="text-xs text-gray-400 mt-1">更容易出现阶段关键项遗漏</div>
            </div>
            <div class="text-right">
              <div class="text-2xl font-black text-[#1D3557]">{{ item.count }}</div>
              <div class="text-[10px] uppercase tracking-widest text-gray-400 font-black">Gap Cases</div>
            </div>
          </div>
        </div>
        <div v-else class="text-sm text-gray-400">当前暂无场景缺口聚合数据。</div>
      </div>
    </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import request from '../utils/request'

const router = useRouter()
const refreshTimer = ref<number | null>(null)
const loading = ref(true)
const pageError = ref('')
const staleMessage = ref('')
const statsData = ref<any>({
  cases: 0,
  roles: 0,
  rag: 0,
  sessions: 0,
  students: 0,
  today_sessions: 0,
  active_sessions: 0,
  finished_sessions: 0,
  completion_rate: 0,
  active_rate: 0,
  peak_daily_sessions: 0,
  avg_daily_sessions: 0,
  trend: [],
  updated_at: '',
})

const stats = computed(() => [
  {
    title: '案件剧本',
    key: 'cases',
    val: statsData.value.cases,
    note: '案件剧本总数',
    icon: 'orders-o',
    badgeClass: 'bg-[#1D3557]/10 text-[#1D3557]',
  },
  {
    title: '角色',
    key: 'roles',
    val: statsData.value.roles,
    note: 'AI 角色总数',
    icon: 'friends-o',
    badgeClass: 'bg-emerald-50 text-emerald-600',
  },
  {
    title: 'RAG',
    key: 'rag',
    val: statsData.value.rag,
    note: '知识片段数量',
    icon: 'cluster-o',
    badgeClass: 'bg-amber-50 text-amber-600',
  },
  {
    title: '会话',
    key: 'sessions',
    val: statsData.value.sessions,
    note: '训练会话总数',
    icon: 'bar-chart-o',
    badgeClass: 'bg-slate-100 text-slate-600',
  },
])

const trend = computed(() => {
  const fallback = Array.from({ length: 7 }, (_, index) => ({ label: '--', count: 0, id: index }))
  const source = Array.isArray(statsData.value.trend) && statsData.value.trend.length ? statsData.value.trend : fallback
  return source.map((item: any, index: number) => ({
    label: item.label || '--',
    count: Number(item.count || 0),
    id: `${item.label || 'empty'}-${index}`,
  }))
})

const peakDailySessions = computed(() => Number(statsData.value.peak_daily_sessions || 0))
const todaySessions = computed(() => Number(statsData.value.today_sessions || 0))
const activeSessions = computed(() => Number(statsData.value.active_sessions || 0))
const ragCount = computed(() => Number(statsData.value.rag || 0))
const studentCount = computed(() => Number(statsData.value.students || 0))
const avgDailySessions = computed(() => Number(statsData.value.avg_daily_sessions || 0))
const stageGapReports = computed(() => Number(statsData.value.stage_gap_reports || 0))
const topMissing = computed(() => (Array.isArray(statsData.value.stage_gap_top_missing) ? statsData.value.stage_gap_top_missing : []))
const sceneRisk = computed(() => (Array.isArray(statsData.value.stage_gap_scene_risk) ? statsData.value.stage_gap_scene_risk : []))

const completionRate = computed(() => clampPercent(statsData.value.completion_rate))
const activeRate = computed(() => clampPercent(statsData.value.active_rate))
const todayVsPeakRate = computed(() => {
  if (!peakDailySessions.value) return todaySessions.value > 0 ? 100 : 0
  return clampPercent((todaySessions.value / peakDailySessions.value) * 100)
})

const completionRateText = computed(() => `${completionRate.value.toFixed(1)}%`)
const activeRateText = computed(() => `${activeRate.value.toFixed(1)}%`)
const updatedAtText = computed(() => {
  const raw = statsData.value.updated_at
  if (!raw) return '--:--:--'
  const date = new Date(raw)
  return Number.isNaN(date.getTime()) ? '--:--:--' : date.toLocaleTimeString('zh-CN', { hour12: false })
})

function clampPercent(value: any) {
  const num = Number(value || 0)
  if (!Number.isFinite(num)) return 0
  return Math.max(0, Math.min(100, num))
}

function getBarHeight(count: number) {
  const maxCount = Math.max(...trend.value.map((item: { count: number }) => item.count), 1)
  return Math.max(24, (count / maxCount) * 160)
}

function getGapPercent(count: number, maxCount: number) {
  if (!maxCount) return 0
  return clampPercent((count / maxCount) * 100)
}

async function fetchStats(options: { background?: boolean } = {}) {
  if (!options.background) {
    loading.value = true
  }
  try {
    const res: any = await request.get('/dashboard/stats')
    statsData.value = {
      ...statsData.value,
      ...res,
    }
    pageError.value = ''
    staleMessage.value = ''
  } catch (error) {
    console.error('Dashboard stats error:', error)
    if (loading.value) {
      pageError.value = '管理端总览加载失败'
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
