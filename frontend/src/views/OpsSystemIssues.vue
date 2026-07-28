<template>
  <div class="ops-issues">
    <section class="toolbar">
      <div class="tabs">
        <button v-for="item in categories" :key="item.value" :class="{ active: category === item.value }" @click="category = item.value; refresh()">{{ item.label }}</button>
      </div>
      <select v-model="status" @change="refresh">
        <option value="">全部状态</option>
        <option value="pending">待处理</option>
        <option value="acknowledged">已确认</option>
        <option value="resolved">已解决</option>
        <option value="ignored">已忽略</option>
      </select>
      <button class="refresh" :disabled="loading" @click="refresh">刷新</button>
    </section>

    <section class="grid">
      <article class="panel">
        <header><h3>问题队列</h3><span>{{ issues.length }} 条</span></header>
        <button v-for="item in issues" :key="item.id" class="issue" :class="{ active: selected?.id === item.id }" @click="selected = item">
          <div><strong>{{ item.title }}</strong><span>{{ categoryLabel(item.category) }} · {{ formatTime(item.created_at) }}</span></div>
          <em :class="item.severity">{{ severityLabel(item.severity) }}</em>
        </button>
        <p v-if="!loading && !issues.length" class="empty">当前筛选下没有异常记录</p>
      </article>

      <article class="panel detail">
        <template v-if="selected">
          <header><div><h3>{{ selected.title }}</h3><p>{{ categoryLabel(selected.category) }} · {{ selected.source || '-' }}</p></div><select :value="selected.status" @change="onStatusChange"><option value="pending">待处理</option><option value="acknowledged">已确认</option><option value="resolved">已解决</option><option value="ignored">已忽略</option></select></header>
          <section><h4>异常说明</h4><pre>{{ selected.detail || '无额外说明' }}</pre></section>
          <section><h4>关联信息</h4><p>案件 ID：{{ selected.case_id || '-' }}　工作流记录：{{ selected.workflow_run_id || '-' }}</p><pre>{{ pretty(selected.metadata) }}</pre></section>
        </template>
        <p v-else class="empty">选择一条记录查看详情</p>
      </article>
    </section>

    <section class="panel runs">
      <header><h3>AI 调用记录</h3><button class="refresh" :disabled="loadingRuns" @click="loadRuns">刷新</button></header>
      <div v-for="run in runs" :key="run.id" class="run">
        <strong>{{ stageLabel(run.stage) }}</strong><span>{{ run.primary_provider || '-' }} → {{ run.final_provider || '-' }} / {{ run.model || '-' }}</span><span>尝试 {{ run.attempt_count }} 次</span><span>{{ run.used_rule_fallback ? '规则兜底' : run.switched_provider ? '已切换供应商' : '模型成功' }}</span><time>{{ formatTime(run.created_at) }}</time>
      </div>
      <p v-if="!loadingRuns && !runs.length" class="empty">暂无 AI 调用记录</p>
    </section>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import request from '../utils/request'

type Issue = { id: number; category: string; severity: string; status: string; source?: string; case_id?: number; workflow_run_id?: number; title: string; detail?: string; metadata?: Record<string, any>; created_at?: string }
type Run = { id: number; stage: string; primary_provider?: string; final_provider?: string; model?: string; attempt_count: number; switched_provider: boolean; used_rule_fallback: boolean; created_at?: string }

const categories = [{ value: '', label: '全部' }, { value: 'ai_exception', label: 'AI 异常' }, { value: 'rule_fallback', label: '规则兜底' }, { value: 'feature_failure', label: '功能失效' }, { value: 'external_service', label: '外部服务' }]
const category = ref('')
const status = ref('')
const loading = ref(false)
const loadingRuns = ref(false)
const issues = ref<Issue[]>([])
const runs = ref<Run[]>([])
const selected = ref<Issue | null>(null)

const refresh = async () => {
  loading.value = true
  try {
    const params: Record<string, string> = {}
    if (category.value) params.category = category.value
    if (status.value) params.status = status.value
    const result: any = await request.get('/ops/system-issues', { params })
    issues.value = Array.isArray(result) ? result : []
    selected.value = issues.value.find((item) => item.id === selected.value?.id) || issues.value[0] || null
  } finally { loading.value = false }
}

const loadRuns = async () => {
  loadingRuns.value = true
  try { const result: any = await request.get('/ops/ai-workflow-runs'); runs.value = Array.isArray(result) ? result : [] } finally { loadingRuns.value = false }
}
const setStatus = async (nextStatus: string) => {
  if (!selected.value) return
  const updated: any = await request.patch(`/ops/system-issues/${selected.value.id}`, { status: nextStatus })
  selected.value = updated
  issues.value = issues.value.map((item) => item.id === updated.id ? updated : item)
}
const onStatusChange = (event: Event) => setStatus((event.target as HTMLSelectElement).value)
const categoryLabel = (value: string) => categories.find((item) => item.value === value)?.label || value
const severityLabel = (value: string) => ({ error: '错误', warning: '警告', info: '提示' } as Record<string, string>)[value] || value
const stageLabel = (value: string) => ({ evidence_extraction: '原文证据提取', case_worldview: '案件世界观', scene_blueprint: '场景蓝图', scene_script: '场景剧本', scene_generation: '场景生成' } as Record<string, string>)[value] || value
const formatTime = (value?: string) => value ? new Date(value).toLocaleString('zh-CN', { hour12: false }) : '-'
const pretty = (value: any) => JSON.stringify(value || {}, null, 2)
onMounted(async () => { await Promise.all([refresh(), loadRuns()]) })
</script>

<style scoped>
.ops-issues{display:grid;gap:16px}.toolbar,.panel{background:#fff;border:1px solid #dbe3ee;border-radius:8px;padding:14px}.toolbar{display:flex;gap:12px;align-items:center;justify-content:space-between}.tabs{display:flex;gap:6px;flex-wrap:wrap}.tabs button,.refresh,select{border:1px solid #cbd5e1;border-radius:6px;background:#fff;padding:7px 10px;color:#334155}.tabs .active{background:#2563eb;color:#fff;border-color:#2563eb}.grid{display:grid;grid-template-columns:minmax(300px,.9fr) minmax(400px,1.4fr);gap:16px}.panel header{display:flex;justify-content:space-between;align-items:center;gap:12px}.panel h3,.panel h4{margin:0;color:#0f172a}.panel header p{margin:4px 0 0;color:#64748b;font-size:12px}.issue{width:100%;display:flex;justify-content:space-between;text-align:left;padding:12px 4px;border:0;border-bottom:1px solid #eef2f7;background:#fff}.issue.active{background:#eff6ff}.issue strong,.issue span{display:block}.issue span,.run,pre,.empty{color:#64748b;font-size:12px}.issue em{font-style:normal;font-weight:700}.issue em.error{color:#dc2626}.issue em.warning{color:#d97706}.detail section{margin-top:18px}.detail pre{white-space:pre-wrap;word-break:break-word;background:#f8fafc;padding:10px;border-radius:6px;color:#334155}.runs .run{display:grid;grid-template-columns:150px 1fr 100px 120px 170px;gap:10px;padding:10px 0;border-bottom:1px solid #eef2f7}.run strong{color:#0f172a}.empty{text-align:center;padding:28px}@media(max-width:900px){.grid{grid-template-columns:1fr}.runs .run{grid-template-columns:1fr;gap:4px}.toolbar{align-items:flex-start;flex-direction:column}}
</style>
