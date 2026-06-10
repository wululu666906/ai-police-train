<template>
  <div class="space-y-6">
    <div class="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
      <div>
        <h1 class="text-2xl font-bold text-gray-800">数据质检</h1>
        <p class="mt-1 text-sm text-gray-500">扫描案件、场景和角色配置问题，避免错误数据直接进入学员训练。</p>
      </div>
      <div class="flex flex-wrap gap-3">
        <van-button plain type="primary" :loading="loading" @click="fetchReport">
          重新扫描
        </van-button>
        <van-button
          v-if="hasAliasConflicts"
          type="warning"
          :loading="repairing"
          @click="repairAliasDrift"
        >
          修复别名漂移
        </van-button>
        <van-button type="primary" class="!bg-[#1D3557] !border-none" @click="router.push('/admin/cases')">
          前往案件库
        </van-button>
      </div>
    </div>

    <div class="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-4">
      <div class="stat-card">
        <div class="stat-label">案件总数</div>
        <div class="stat-value">{{ summary.case_count }}</div>
      </div>
      <div class="stat-card warn">
        <div class="stat-label">有问题案件</div>
        <div class="stat-value">{{ summary.issue_case_count }}</div>
      </div>
      <div class="stat-card danger">
        <div class="stat-label">高风险问题</div>
        <div class="stat-value">{{ summary.high_count }}</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">问题总数</div>
        <div class="stat-value">{{ summary.total_issue_count }}</div>
      </div>
    </div>

    <div class="rounded-[2rem] border border-gray-100 bg-white p-6 shadow-sm">
      <div class="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
        <div class="flex flex-wrap gap-3">
          <span
            v-for="item in severityFilters"
            :key="item.value"
            class="filter-chip"
            :class="{ active: selectedSeverity === item.value }"
            @click="selectedSeverity = item.value"
          >
            {{ item.label }}
          </span>
        </div>
        <div class="text-sm text-gray-400">
          场景问题 {{ summary.issue_scene_count }} 项，角色问题 {{ summary.issue_role_count }} 项
        </div>
      </div>
    </div>

    <div v-if="loading" class="rounded-[2rem] border border-gray-100 bg-white p-12 shadow-sm">
      <div class="flex justify-center">
        <van-loading color="#1D3557" vertical>正在扫描数据质量...</van-loading>
      </div>
    </div>

    <div v-else-if="filteredIssues.length === 0" class="rounded-[2rem] border border-gray-100 bg-white p-12 text-center shadow-sm">
      <van-icon name="passed" size="48" color="#00B42A" />
      <h3 class="mt-4 text-lg font-bold text-gray-800">当前未发现匹配问题</h3>
      <p class="mt-2 text-sm text-gray-400">如果刚修改过案件配置，可以点击“重新扫描”同步最新结果。</p>
    </div>

    <div v-else class="space-y-4">
      <div
        v-for="(issue, index) in filteredIssues"
        :key="`${issue.type}-${issue.case_id}-${issue.scene_id}-${issue.role_id}-${index}`"
        class="rounded-[1.5rem] border border-gray-100 bg-white p-6 shadow-sm"
      >
        <div class="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
          <div class="space-y-3">
            <div class="flex flex-wrap items-center gap-3">
              <van-tag :color="getSeverityColor(issue.severity)" plain size="medium">{{ getSeverityLabel(issue.severity) }}</van-tag>
              <span class="text-xs font-black uppercase tracking-widest text-gray-400">{{ issue.type }}</span>
            </div>
            <div class="text-lg font-bold text-gray-800">{{ issue.message }}</div>
            <div class="text-sm text-gray-500">建议处理：{{ issue.recommendation }}</div>
            <div class="flex flex-wrap gap-4 text-sm text-gray-500">
              <span v-if="issue.case_title">案件：{{ issue.case_title }}</span>
              <span v-if="issue.scene_name">场景：{{ issue.scene_name }}</span>
              <span v-if="issue.role_name">角色：{{ issue.role_name }}</span>
            </div>
          </div>
          <van-button plain size="small" @click="goToCase(issue)">
            去案件处理
          </van-button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import request from '../utils/request'
import { showToast } from 'vant'

const router = useRouter()
const loading = ref(false)
const repairing = ref(false)
const selectedSeverity = ref('all')
const issues = ref<any[]>([])
const summary = reactive({
  case_count: 0,
  issue_case_count: 0,
  issue_scene_count: 0,
  issue_role_count: 0,
  total_issue_count: 0,
  high_count: 0,
  medium_count: 0,
  low_count: 0,
  alias_conflict_count: 0,
})

const hasAliasConflicts = computed(
  () =>
    Number(summary.alias_conflict_count) > 0 ||
    issues.value.some((item: any) => item.type === 'person_alias_conflict')
)

const severityFilters = [
  { value: 'all', label: '全部问题' },
  { value: 'high', label: '高风险' },
  { value: 'medium', label: '中风险' },
  { value: 'low', label: '低风险' },
]

const filteredIssues = computed(() => {
  if (selectedSeverity.value === 'all') return issues.value
  return issues.value.filter((item: any) => item.severity === selectedSeverity.value)
})

const applyReport = (res: any) => {
  issues.value = res?.issues || res?.report?.issues || []
  Object.assign(summary, res?.summary || res?.report?.summary || {})
}

const fetchReport = async () => {
  loading.value = true
  try {
    const res: any = await request.get('/cases/data-quality-report', { _skipErrorToast: true } as any)
    applyReport(res)
  } catch {
    showToast('数据质检扫描失败')
  } finally {
    loading.value = false
  }
}

const repairAliasDrift = async () => {
  repairing.value = true
  try {
    const res: any = await request.post('/cases/data-quality-repair', {}, { _skipErrorToast: true } as any)
    applyReport(res)
    const personCount = Number(res?.repaired_person_count ?? 0)
    const caseCount = Number(res?.repaired_case_count ?? 0)
    showToast({
      type: 'success',
      message: `已修复 ${personCount} 个人物字段（${caseCount} 个案件）`,
    })
  } catch {
    showToast('别名漂移修复失败')
  } finally {
    repairing.value = false
  }
}

const goToCase = (issue: any) => {
  if (issue?.case_id) {
    router.push(`/admin/cases?case_id=${issue.case_id}`)
    return
  }
  router.push('/admin/cases')
}

const getSeverityColor = (severity: string) => {
  if (severity === 'high') return '#F53F3F'
  if (severity === 'medium') return '#FF7D00'
  return '#86909C'
}

const getSeverityLabel = (severity: string) => {
  if (severity === 'high') return '高风险'
  if (severity === 'medium') return '中风险'
  return '低风险'
}

onMounted(fetchReport)
</script>

<style scoped>
.stat-card {
  background: white;
  border: 1px solid #f2f3f5;
  border-radius: 1.5rem;
  padding: 20px 22px;
  box-shadow: 0 2px 10px rgba(15, 23, 42, 0.04);
}

.stat-card.warn {
  background: #fffaf0;
  border-color: #ffe7ba;
}

.stat-card.danger {
  background: #fff2f0;
  border-color: #ffccc7;
}

.stat-label {
  font-size: 11px;
  color: #94a3b8;
  text-transform: uppercase;
  letter-spacing: 0.18em;
  font-weight: 900;
}

.stat-value {
  margin-top: 12px;
  font-size: 30px;
  line-height: 1;
  font-weight: 900;
  color: #1f2937;
}

.filter-chip {
  padding: 8px 14px;
  border-radius: 999px;
  background: #f8fafc;
  color: #475569;
  font-size: 13px;
  font-weight: 700;
  cursor: pointer;
  border: 1px solid transparent;
  transition: all 0.2s ease;
}

.filter-chip.active {
  background: #e0ecff;
  color: #165dff;
  border-color: #165dff;
}
</style>
