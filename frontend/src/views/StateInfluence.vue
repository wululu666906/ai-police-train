<template>
  <div class="space-y-6">
    <div class="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
      <div>
        <h1 class="text-2xl font-bold text-gray-800">四轴触发表</h1>
        <p class="mt-1 text-sm text-gray-500">
          模拟分值→契约、回归一致率、覆盖项编辑（P2 可运营）。
        </p>
        <p v-if="meta.overrides_path" class="mt-2 text-xs text-gray-400">文件：{{ meta.overrides_path }}</p>
      </div>
      <div class="flex flex-wrap gap-3">
        <van-button plain type="primary" :loading="loading" @click="loadAll">重新加载</van-button>
        <van-button
          v-if="activeTab === 'overrides'"
          type="primary"
          class="!bg-[#1D3557] !border-none"
          :loading="saving"
          @click="saveOverrides"
        >
          保存覆盖项
        </van-button>
      </div>
    </div>

    <div class="flex flex-wrap gap-2">
      <span
        v-for="tab in tabs"
        :key="tab.id"
        class="tab-chip"
        :class="{ active: activeTab === tab.id }"
        @click="activeTab = tab.id"
      >
        {{ tab.label }}
      </span>
    </div>

    <!-- 模拟器 -->
    <div v-if="activeTab === 'simulate'" class="rounded-[2rem] border border-gray-100 bg-white p-6 shadow-sm space-y-5">
      <div class="grid grid-cols-1 gap-4 md:grid-cols-2">
        <div v-for="axis in axisDefs" :key="axis.key">
          <label class="mb-2 block text-sm font-semibold text-gray-700">{{ axis.label }}（{{ simulateScores[axis.key] }}）</label>
          <van-slider v-model="simulateScores[axis.key]" :min="0" :max="100" :step="1" @change="runSimulate" />
        </div>
      </div>
      <van-field v-model="simulateMessage" label="模拟问法" placeholder="例如：你先别急，慢慢说…" @blur="runSimulate" />
      <van-button type="primary" size="small" class="!bg-[#1D3557] !border-none" :loading="simulating" @click="runSimulate">
        生成契约
      </van-button>

      <div v-if="simulateResult" class="rounded-2xl bg-slate-50 p-4 text-sm text-slate-700 space-y-2">
        <div class="flex flex-wrap gap-2">
          <van-tag type="primary" plain>{{ simulateResult.affect_label || '—' }}</van-tag>
          <van-tag plain>主情绪 {{ simulateResult.contract?.primary_affect }}</van-tag>
          <van-tag plain>delivery {{ simulateResult.contract?.delivery }}</van-tag>
        </div>
        <pre class="max-h-64 overflow-auto text-xs whitespace-pre-wrap">{{ simulateResult.contract_block }}</pre>
      </div>
    </div>

    <!-- 回归指标 -->
    <div v-else-if="activeTab === 'regression'" class="space-y-4">
      <div class="grid grid-cols-1 gap-4 md:grid-cols-3">
        <div class="stat-card">
          <div class="stat-label">回归通过数</div>
          <div class="stat-value">{{ regression?.passed ?? '—' }}/{{ regression?.total ?? '—' }}</div>
        </div>
        <div class="stat-card" :class="regression?.meets_target ? '' : 'warn'">
          <div class="stat-label">一致率</div>
          <div class="stat-value">{{ regression ? Math.round(regression.pass_rate * 100) : '—' }}%</div>
        </div>
        <div class="stat-card">
          <div class="stat-label">目标</div>
          <div class="stat-value">≥ {{ regression ? Math.round(regression.target_pass_rate * 100) : 85 }}%</div>
        </div>
      </div>

      <div
        v-for="item in regression?.results || []"
        :key="item.id"
        class="rounded-[1.25rem] border border-gray-100 bg-white p-4 shadow-sm"
      >
        <div class="flex flex-wrap items-center gap-2">
          <van-tag :type="item.passed ? 'success' : 'danger'" plain>{{ item.passed ? '通过' : '失败' }}</van-tag>
          <span class="text-sm font-semibold text-gray-800">{{ item.label }}</span>
        </div>
        <p class="mt-2 text-xs text-gray-500">
          期望 {{ item.expected_affect }} → 实际 {{ item.actual_affect }}
          <span v-if="item.affect_label">（{{ item.affect_label }}）</span>
        </p>
      </div>
    </div>

    <!-- 覆盖项 -->
    <div v-else class="rounded-[2rem] border border-gray-100 bg-white p-6 shadow-sm">
      <div class="mb-3 flex flex-wrap items-center gap-3 text-sm text-gray-500">
        <van-tag v-if="meta.has_overrides" type="success" plain>已存在覆盖</van-tag>
        <van-tag v-else plain>仅使用内置表</van-tag>
        <span>单轮变化上限：{{ tables.MAX_DELTA_PER_TURN ?? '—' }}</span>
      </div>
      <label class="mb-2 block text-sm font-semibold text-gray-700">覆盖项 JSON（overrides）</label>
      <textarea v-model="overridesText" class="state-influence-editor" spellcheck="false" />
      <p v-if="parseError" class="mt-2 text-sm text-red-500">{{ parseError }}</p>
      <details class="mt-4">
        <summary class="cursor-pointer text-sm font-semibold text-gray-700">合并后完整表（只读）</summary>
        <pre class="mt-4 max-h-[360px] overflow-auto rounded-xl bg-slate-50 p-4 text-xs">{{ mergedPreview }}</pre>
      </details>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { showToast } from 'vant'
import request from '../utils/request'

const tabs = [
  { id: 'simulate', label: '契约模拟' },
  { id: 'regression', label: '回归指标' },
  { id: 'overrides', label: '覆盖编辑' },
] as const

type TabId = (typeof tabs)[number]['id']

const activeTab = ref<TabId>('simulate')
const loading = ref(false)
const saving = ref(false)
const simulating = ref(false)
const overridesText = ref('{}')
const parseError = ref('')
const tables = reactive<Record<string, unknown>>({})
const meta = reactive({ overrides_path: '', has_overrides: false })
const regression = ref<{
  total: number
  passed: number
  pass_rate: number
  target_pass_rate: number
  meets_target: boolean
  results: Array<{
    id: string
    label: string
    expected_affect: string
    actual_affect: string
    affect_label?: string
    passed: boolean
  }>
} | null>(null)

const axisDefs = [
  { key: 'emotion' as const, label: '情绪' },
  { key: 'cooperation' as const, label: '配合度' },
  { key: 'risk' as const, label: '风险' },
  { key: 'clarity' as const, label: '清晰度' },
]

const simulateScores = reactive({ emotion: 85, cooperation: 35, risk: 82, clarity: 18 })
const simulateMessage = ref('你先别急，慢慢说')
const simulateResult = ref<{
  affect_label?: string
  contract?: Record<string, unknown>
  contract_block?: string
} | null>(null)

const mergedPreview = computed(() => JSON.stringify(tables, null, 2))

const loadTables = async () => {
  const data = (await request.get('/api/admin/state-influence/tables')) as {
    tables?: Record<string, unknown>
    overrides?: Record<string, unknown>
    overrides_path?: string
    has_overrides?: boolean
  }
  Object.assign(tables, data.tables || {})
  meta.overrides_path = data.overrides_path || ''
  meta.has_overrides = Boolean(data.has_overrides)
  overridesText.value = JSON.stringify(data.overrides || {}, null, 2)
}

const loadRegression = async () => {
  regression.value = (await request.get('/api/admin/state-influence/metrics/regression')) as typeof regression.value
}

const runSimulate = async () => {
  simulating.value = true
  try {
    simulateResult.value = (await request.post('/api/admin/state-influence/simulate', {
      scores: { ...simulateScores },
      user_message: simulateMessage.value,
    })) as typeof simulateResult.value
  } catch {
    showToast({ type: 'fail', message: '模拟失败' })
  } finally {
    simulating.value = false
  }
}

const loadAll = async () => {
  loading.value = true
  parseError.value = ''
  try {
    await Promise.all([loadTables(), loadRegression()])
    if (activeTab.value === 'simulate' && !simulateResult.value) {
      await runSimulate()
    }
  } catch {
    showToast({ type: 'fail', message: '加载失败' })
  } finally {
    loading.value = false
  }
}

const saveOverrides = async () => {
  parseError.value = ''
  let overrides: Record<string, unknown>
  try {
    overrides = JSON.parse(overridesText.value || '{}')
    if (typeof overrides !== 'object' || overrides === null || Array.isArray(overrides)) {
      throw new Error('覆盖项必须是 JSON 对象')
    }
  } catch (error) {
    parseError.value = error instanceof Error ? error.message : 'JSON 格式无效'
    return
  }
  saving.value = true
  try {
    const data = (await request.put('/api/admin/state-influence/tables', { overrides })) as {
      tables?: Record<string, unknown>
      message?: string
    }
    if (data.tables) Object.assign(tables, data.tables)
    meta.has_overrides = Object.keys(overrides).length > 0
    showToast({ type: 'success', message: data.message || '已保存' })
    await loadRegression()
  } catch {
    showToast({ type: 'fail', message: '保存失败' })
  } finally {
    saving.value = false
  }
}

onMounted(() => {
  loadAll()
})
</script>

<style scoped>
.tab-chip {
  cursor: pointer;
  border-radius: 999px;
  border: 1px solid #e5e7eb;
  padding: 0.4rem 1rem;
  font-size: 13px;
  color: #64748b;
  background: #fff;
}
.tab-chip.active {
  border-color: #1d3557;
  color: #1d3557;
  background: #eef4ff;
  font-weight: 600;
}
.stat-card {
  border-radius: 1.5rem;
  border: 1px solid #f1f5f9;
  background: #fff;
  padding: 1.25rem 1.5rem;
  box-shadow: 0 1px 2px rgba(15, 23, 42, 0.04);
}
.stat-card.warn {
  border-color: #fde68a;
  background: #fffbeb;
}
.stat-label {
  font-size: 12px;
  color: #94a3b8;
}
.stat-value {
  margin-top: 0.35rem;
  font-size: 1.75rem;
  font-weight: 700;
  color: #0f172a;
}
.state-influence-editor {
  width: 100%;
  min-height: 280px;
  border-radius: 1rem;
  border: 1px solid #e5e7eb;
  padding: 1rem;
  font-family: ui-monospace, Menlo, Monaco, Consolas, monospace;
  font-size: 12px;
  line-height: 1.5;
  resize: vertical;
}
</style>
