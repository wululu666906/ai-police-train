<template>
  <div class="space-y-6 pb-20">
    <div class="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
      <div>
        <h1 class="text-2xl font-bold text-gray-800">学员账号管理</h1>
        <p class="text-sm text-gray-500 mt-1">支持按学号模板批量开通、名单导入开户、号段删除，以及导出本次账号清单。</p>
      </div>
      <div class="rounded-2xl border border-blue-100 bg-blue-50 px-4 py-3 text-sm text-blue-700">
        模板示例：`251040702xx`，起始号 `1`，结束号 `50`
      </div>
    </div>

    <div class="grid grid-cols-1 xl:grid-cols-[1.05fr_0.95fr] gap-6">
      <section class="bg-white rounded-[28px] shadow-sm border border-gray-100 p-7">
        <div class="flex items-center justify-between gap-4">
          <div>
            <h2 class="text-lg font-bold text-gray-800">模板批量开通</h2>
            <p class="text-sm text-gray-500 mt-1">系统会把模板末尾的 `x / X` 当作流水号占位符。</p>
          </div>
          <van-button plain size="small" class="!border-gray-200 !text-gray-600" @click="fillExample">
            填入示例
          </van-button>
        </div>

        <div class="grid grid-cols-1 md:grid-cols-2 gap-5 mt-6">
          <div class="field-block md:col-span-2">
            <label class="field-label">学号模板</label>
            <input v-model.trim="form.template" type="text" class="field-input" placeholder="例如 251040702xx" />
          </div>
          <div class="field-block">
            <label class="field-label">起始编号</label>
            <input v-model.number="form.startNo" type="number" min="1" class="field-input" placeholder="1" />
          </div>
          <div class="field-block">
            <label class="field-label">结束编号</label>
            <input v-model.number="form.endNo" type="number" min="1" class="field-input" placeholder="50" />
          </div>
          <div class="field-block md:col-span-2">
            <label class="field-label">初始密码</label>
            <input v-model.trim="form.password" type="text" class="field-input" placeholder="请输入统一初始密码" />
          </div>
        </div>

        <div class="mt-6 rounded-2xl bg-slate-50 border border-slate-100 p-5">
          <div class="text-sm font-bold text-slate-700">模板生成预览</div>
          <div class="mt-3 text-sm text-slate-500 leading-7">
            <template v-if="previewError">{{ previewError }}</template>
            <template v-else-if="previewList.length">
              <div>将生成 {{ previewList.length }} 个账号：</div>
              <div class="mt-3 flex flex-wrap gap-2">
                <span v-for="item in previewVisibleList" :key="item" class="preview-chip">{{ item }}</span>
              </div>
              <div v-if="previewHiddenCount > 0" class="mt-3 text-xs text-slate-400">
                其余 {{ previewHiddenCount }} 个账号会在执行时一并生成，避免预览区域过长。
              </div>
            </template>
            <template v-else>请输入模板、编号范围与初始密码后查看预览。</template>
          </div>
        </div>

        <div class="mt-6 flex flex-wrap gap-3">
          <van-button type="primary" class="!bg-[#16324F] !border-none !rounded-full !px-8" :loading="creating" @click="createStudents">
            批量开通账号
          </van-button>
          <van-button plain class="!rounded-full !px-8 !border-red-200 !text-red-600" :loading="deleting" @click="deleteStudents">
            批量删除该号段
          </van-button>
          <van-button plain class="!rounded-full !px-8 !border-gray-200 !text-gray-600" :loading="loading" @click="fetchStudents">
            刷新列表
          </van-button>
        </div>
      </section>

      <section class="bg-white rounded-[28px] shadow-sm border border-gray-100 p-7">
        <div class="flex items-center justify-between gap-4">
          <div>
            <h2 class="text-lg font-bold text-gray-800">名单导入开户</h2>
            <p class="text-sm text-gray-500 mt-1">支持 `xlsx / csv`，自动识别 `学号` 或 `username` 列。</p>
          </div>
          <div class="flex items-center gap-2">
            <input ref="fileInputRef" type="file" accept=".xlsx,.csv" class="hidden" @change="handleFileChange" />
            <van-button plain size="small" class="!border-gray-200 !text-gray-600" @click="downloadImportTemplate">
              下载模板
            </van-button>
            <van-button plain size="small" class="!border-gray-200 !text-gray-600" @click="chooseFile">
              选择文件
            </van-button>
          </div>
        </div>

        <div class="mt-6 rounded-2xl border border-slate-100 bg-slate-50 p-5">
          <div class="text-sm font-bold text-slate-700">导入说明</div>
          <div class="mt-2 text-sm leading-7 text-slate-500">
            第一行可写表头，优先读取 `学号`、`username`、`账号`、`account` 列；若没有表头，则默认读取第一列。
          </div>
          <div class="mt-3 text-xs text-slate-400">当前文件：{{ importFileName || '未选择文件' }}</div>
        </div>

        <div class="mt-5 field-block">
          <label class="field-label">导入初始密码</label>
          <input v-model.trim="importForm.password" type="text" class="field-input" placeholder="请输入导入账号统一初始密码" />
        </div>

        <div class="mt-5 rounded-2xl bg-slate-50 border border-slate-100 p-5">
          <div class="flex items-center justify-between gap-3">
            <div class="text-sm font-bold text-slate-700">名单预览</div>
            <div v-if="importPreviewList.length" class="text-xs text-slate-400">
              有效 {{ importSummary.validCount }} 条，去重 {{ importSummary.duplicateCount }} 条
            </div>
          </div>
          <div class="mt-3 text-sm text-slate-500 leading-7">
            <template v-if="importError">{{ importError }}</template>
            <template v-else-if="importPreviewList.length">
              <div>识别到 {{ importPreviewList.length }} 个账号：</div>
              <div class="mt-3 flex flex-wrap gap-2">
                <span v-for="item in importPreviewVisibleList" :key="item" class="preview-chip">{{ item }}</span>
              </div>
              <div v-if="importPreviewHiddenCount > 0" class="mt-3 text-xs text-slate-400">
                还有 {{ importPreviewHiddenCount }} 个账号已识别成功，可直接导入创建。
              </div>
            </template>
            <template v-else>请选择名单文件后查看预览。</template>
          </div>
        </div>

        <div v-if="lastImportSummary.totalRows > 0" class="mt-5 rounded-2xl border border-slate-100 bg-slate-50 p-4 text-sm text-slate-600">
          上次导入结果：原始 {{ lastImportSummary.totalRows }} 行，识别 {{ lastImportSummary.validCount }} 个学号，去重 {{ lastImportSummary.duplicateCount }} 个，成功创建 {{ lastCreateResult.created_count }} 个，跳过已有 {{ lastCreateResult.skipped_count }} 个。
        </div>

        <div class="mt-6 flex flex-wrap gap-3">
          <van-button type="primary" class="!bg-[#1D3557] !border-none !rounded-full !px-8" :loading="importing" @click="importStudents">
            导入并开通账号
          </van-button>
          <van-button plain class="!rounded-full !px-8 !border-gray-200 !text-gray-600" @click="clearImportFile">
            清空导入
          </van-button>
        </div>
      </section>
    </div>

    <section class="bg-white rounded-[28px] shadow-sm border border-gray-100 p-7">
      <div class="flex items-center justify-between gap-4">
        <div>
          <h2 class="text-lg font-bold text-gray-800">本次结果</h2>
          <p class="text-sm text-gray-500 mt-1">新建成功后可直接导出学号与初始密码清单。</p>
        </div>
        <div class="text-xs text-gray-400">当前学员总数 {{ students.length }}</div>
      </div>

      <div class="grid grid-cols-2 gap-4 mt-6">
        <div class="result-stat bg-emerald-50 border-emerald-100">
          <div class="result-stat__label text-emerald-600">本次创建</div>
          <div class="result-stat__value text-emerald-700">{{ lastCreateResult.created_count }}</div>
        </div>
        <div class="result-stat bg-amber-50 border-amber-100">
          <div class="result-stat__label text-amber-600">跳过重复</div>
          <div class="result-stat__value text-amber-700">{{ lastCreateResult.skipped_count }}</div>
        </div>
      </div>

      <div class="mt-5 space-y-4">
        <div class="rounded-2xl border border-slate-100 bg-slate-50 p-4">
          <div class="flex items-center justify-between gap-3">
            <div class="text-sm font-bold text-slate-700">新建账号</div>
            <van-button plain size="small" class="!border-gray-200 !text-gray-600" :disabled="!lastCreateResult.created_usernames.length" @click="exportCreatedAccounts">
              导出本次清单
            </van-button>
          </div>
          <div class="mt-2 text-sm leading-7 text-slate-500 break-all">
            {{ lastCreateResult.created_usernames.length ? lastCreateResult.created_usernames.join('、') : '暂无本次新增账号' }}
          </div>
          <div v-if="lastCreatePassword" class="mt-3 text-xs text-slate-400">本次导出将使用初始密码：{{ lastCreatePassword }}</div>
        </div>

        <div class="rounded-2xl border border-slate-100 bg-slate-50 p-4">
          <div class="text-sm font-bold text-slate-700">重复跳过</div>
          <div class="mt-2 text-sm leading-7 text-slate-500 break-all">
            {{ lastCreateResult.skipped_usernames.length ? lastCreateResult.skipped_usernames.join('、') : '暂无重复账号' }}
          </div>
        </div>

        <div class="rounded-2xl border border-slate-100 bg-slate-50 p-4">
          <div class="text-sm font-bold text-slate-700">本次删除</div>
          <div class="mt-2 text-sm leading-7 text-slate-500 break-all">
            {{ lastDeleteResult.deleted_usernames.length ? lastDeleteResult.deleted_usernames.join('、') : '暂无本次删除账号' }}
          </div>
        </div>
      </div>
    </section>

    <section class="bg-white rounded-[28px] shadow-sm border border-gray-100 p-7">
      <div class="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
        <div>
          <h2 class="text-lg font-bold text-gray-800">已开通学员账号</h2>
          <p class="text-sm text-gray-500 mt-1">这里只展示学生账号，训练记录仍然各自独立。</p>
        </div>
        <div class="flex flex-col gap-3 md:items-end">
          <input v-model.trim="searchText" type="text" class="search-input" placeholder="搜索学号" />
          <select v-model="sortMode" class="search-input">
            <option value="risk">按风险优先排序</option>
            <option value="score_asc">按均分从低到高</option>
            <option value="sessions_desc">按训练次数从高到低</option>
            <option value="latest">按创建时间从新到旧</option>
          </select>
          <label class="flex items-center gap-2 text-xs font-medium text-slate-500">
            <input v-model="onlyLowScore" type="checkbox" class="h-4 w-4 rounded border-slate-300 text-[#1D3557]" />
            仅看均分低于 60 的学员
          </label>
        </div>
      </div>

      <div v-if="gapFilterOptions.length" class="mt-5">
        <div class="text-xs font-bold text-slate-500">按高频薄弱项筛选</div>
        <div class="mt-3 flex flex-wrap gap-2">
          <button
            type="button"
            class="rounded-full px-3 py-1.5 text-xs font-bold transition-colors"
            :class="selectedGap === '' ? 'bg-[#1D3557] text-white' : 'bg-slate-100 text-slate-600 hover:bg-slate-200'"
            @click="selectedGap = ''"
          >
            全部
          </button>
          <button
            v-for="item in gapFilterOptions"
            :key="item"
            type="button"
            class="rounded-full px-3 py-1.5 text-xs font-bold transition-colors"
            :class="selectedGap === item ? 'bg-amber-500 text-white' : 'bg-amber-50 text-amber-700 hover:bg-amber-100'"
            @click="selectedGap = item"
          >
            {{ item }}
          </button>
        </div>
      </div>

      <div class="mt-5 flex flex-wrap gap-2 text-xs">
        <span class="summary-pill">当前筛选 {{ filteredStudents.length }} 人</span>
        <span class="summary-pill">低分预警 {{ lowScoreCount }} 人</span>
        <span class="summary-pill">存在高频缺口 {{ gapStudentCount }} 人</span>
      </div>

      <div v-if="loading" class="mt-6 rounded-2xl border border-slate-100 py-16 text-center text-slate-400">
        <van-loading color="#1D3557">正在加载学员账号...</van-loading>
      </div>
      <div v-else-if="pageError" class="mt-6 rounded-2xl border border-amber-200 bg-amber-50 px-6 py-12 text-center">
        <van-icon name="warning-o" size="30" class="text-amber-500" />
        <p class="mt-4 text-sm font-bold text-amber-800">{{ pageError }}</p>
        <van-button plain type="primary" class="mt-5" @click="fetchStudents">重新加载</van-button>
      </div>
      <div v-else-if="filteredStudents.length" class="mt-6 grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
        <div v-for="student in filteredStudents" :key="student.id" class="rounded-2xl border border-slate-100 bg-slate-50 px-5 py-4">
          <div class="flex items-center justify-between gap-3">
            <div class="font-bold text-slate-800">{{ student.username }}</div>
            <van-tag type="primary" plain>学员</van-tag>
          </div>
          <div class="mt-2 text-xs text-slate-400">创建时间 {{ formatTime(student.created_at) }}</div>
          <div class="mt-4 grid grid-cols-3 gap-2">
            <div class="rounded-xl bg-white border border-slate-100 px-3 py-3">
              <div class="text-[11px] text-slate-400">训练次数</div>
              <div class="mt-1 text-base font-bold text-slate-800">{{ student.total_sessions ?? 0 }}</div>
            </div>
            <div class="rounded-xl bg-white border border-slate-100 px-3 py-3">
              <div class="text-[11px] text-slate-400">已完成</div>
              <div class="mt-1 text-base font-bold text-[#165dff]">{{ student.finished_sessions ?? 0 }}</div>
            </div>
            <div class="rounded-xl bg-white border border-slate-100 px-3 py-3">
              <div class="text-[11px] text-slate-400">均分</div>
              <div class="mt-1 text-base font-bold" :class="getScoreTextClass(student.avg_score)">
                {{ formatAvgScore(student.avg_score) }}
              </div>
            </div>
          </div>
          <div class="mt-4">
            <div class="text-[11px] font-bold text-slate-500">高频薄弱项</div>
            <div v-if="student.top_gap_missing?.length" class="mt-2 flex flex-wrap gap-2">
              <span v-for="item in student.top_gap_missing" :key="item" class="inline-flex items-center rounded-full bg-amber-50 px-3 py-1 text-xs font-bold text-amber-700">
                {{ item }}
              </span>
            </div>
            <div v-else class="mt-2 text-xs text-emerald-600">当前暂无明显重复缺口</div>
          </div>
        </div>
      </div>
      <div v-else class="mt-6 rounded-2xl border border-dashed border-slate-200 py-16 text-center text-slate-400">
        暂无符合条件的学员账号
      </div>
    </section>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { useRoute } from 'vue-router'
import * as XLSX from 'xlsx'
import { showConfirmDialog, showToast } from 'vant'
import request from '../utils/request'

const route = useRoute()
const loading = ref(false)
const creating = ref(false)
const deleting = ref(false)
const importing = ref(false)
const searchText = ref('')
const selectedGap = ref('')
const onlyLowScore = ref(false)
const sortMode = ref<'risk' | 'score_asc' | 'sessions_desc' | 'latest'>('risk')
const students = ref<any[]>([])
const lastCreatePassword = ref('')
const fileInputRef = ref<HTMLInputElement | null>(null)
const importFileName = ref('')
const importedUsernames = ref<string[]>([])
const importError = ref('')
const pageError = ref('')
const previewLimit = 12

const form = reactive({
  template: '',
  startNo: 1,
  endNo: 50,
  password: '123456',
})

const importForm = reactive({
  password: '123456',
})

const lastCreateResult = reactive({
  created_count: 0,
  skipped_count: 0,
  created_usernames: [] as string[],
  skipped_usernames: [] as string[],
})

const lastDeleteResult = reactive({
  deleted_count: 0,
  skipped_count: 0,
  deleted_usernames: [] as string[],
  skipped_usernames: [] as string[],
})

const importSummary = reactive({
  totalRows: 0,
  validCount: 0,
  duplicateCount: 0,
})

const lastImportSummary = reactive({
  totalRows: 0,
  validCount: 0,
  duplicateCount: 0,
})

const buildUsername = (template: string, seqNo: number) => {
  const rawTemplate = String(template || '').trim()
  const match = rawTemplate.match(/(x|X)+$/)
  if (!match) {
    throw new Error('模板必须以 x 或 X 结尾，例如 251040702xx')
  }
  const suffix = match[0]
  const seqText = String(seqNo)
  if (seqText.length > suffix.length) {
    throw new Error(`编号 ${seqNo} 超出模板可容纳位数`)
  }
  return `${rawTemplate.slice(0, -suffix.length)}${seqText.padStart(suffix.length, '0')}`
}

const previewError = computed(() => {
  const template = form.template.trim()
  if (!template) return '请先输入学号模板。'
  if (!form.startNo || !form.endNo) return '请补充起始编号和结束编号。'
  if (form.startNo <= 0 || form.endNo <= 0) return '编号必须大于 0。'
  if (form.startNo > form.endNo) return '起始编号不能大于结束编号。'
  try {
    buildUsername(template, form.endNo)
    return ''
  } catch (error: any) {
    return error?.message || '模板格式不正确。'
  }
})

const previewList = computed(() => {
  if (previewError.value) return []
  const list: string[] = []
  for (let seqNo = form.startNo; seqNo <= form.endNo; seqNo += 1) {
    list.push(buildUsername(form.template, seqNo))
  }
  return list
})

const importPreviewList = computed(() => importedUsernames.value)
const previewVisibleList = computed(() => previewList.value.slice(0, previewLimit))
const previewHiddenCount = computed(() => Math.max(previewList.value.length - previewVisibleList.value.length, 0))
const importPreviewVisibleList = computed(() => importPreviewList.value.slice(0, previewLimit))
const importPreviewHiddenCount = computed(() => Math.max(importPreviewList.value.length - importPreviewVisibleList.value.length, 0))

const gapFilterOptions = computed(() => {
  const set = new Set<string>()
  for (const student of students.value) {
    const gaps = Array.isArray(student?.top_gap_missing) ? student.top_gap_missing : []
    for (const gap of gaps) {
      const label = String(gap || '').trim()
      if (label) set.add(label)
    }
  }
  return Array.from(set)
})

const studentRiskScore = (item: any) => {
  const avgScore = Number(item?.avg_score)
  const normalizedScoreRisk = Number.isFinite(avgScore) ? Math.max(0, 100 - avgScore) : 35
  const unfinishedRisk = Math.max(0, Number(item?.total_sessions || 0) - Number(item?.finished_sessions || 0)) * 6
  const gapRisk = (Array.isArray(item?.top_gap_missing) ? item.top_gap_missing.length : 0) * 18
  return normalizedScoreRisk + unfinishedRisk + gapRisk
}

const filteredStudents = computed(() => {
  const keyword = searchText.value.trim()
  return [...students.value]
    .filter((item) => {
      if (keyword && !String(item.username || '').includes(keyword)) return false
      if (selectedGap.value) {
        const gaps = Array.isArray(item?.top_gap_missing) ? item.top_gap_missing : []
        if (!gaps.includes(selectedGap.value)) return false
      }
      if (onlyLowScore.value) {
        const score = Number(item?.avg_score)
        if (!Number.isFinite(score) || score >= 60) return false
      }
      return true
    })
    .sort((left, right) => {
      if (sortMode.value === 'score_asc') {
        const leftScore = Number.isFinite(Number(left?.avg_score)) ? Number(left.avg_score) : Number.POSITIVE_INFINITY
        const rightScore = Number.isFinite(Number(right?.avg_score)) ? Number(right.avg_score) : Number.POSITIVE_INFINITY
        return leftScore - rightScore
      }
      if (sortMode.value === 'sessions_desc') {
        return Number(right?.total_sessions || 0) - Number(left?.total_sessions || 0)
      }
      if (sortMode.value === 'latest') {
        return new Date(right?.created_at || 0).getTime() - new Date(left?.created_at || 0).getTime()
      }
      return studentRiskScore(right) - studentRiskScore(left)
    })
})

const lowScoreCount = computed(() =>
  students.value.filter((item) => {
    const score = Number(item?.avg_score)
    return Number.isFinite(score) && score < 60
  }).length
)

const gapStudentCount = computed(() =>
  students.value.filter((item) => Array.isArray(item?.top_gap_missing) && item.top_gap_missing.length > 0).length
)

const applyRouteFilters = () => {
  const gap = String(route.query.gap || '').trim()
  const search = String(route.query.search || '').trim()
  const sort = String(route.query.sort || '').trim()
  selectedGap.value = gap
  searchText.value = search
  onlyLowScore.value = route.query.low_score === '1'
  if (sort === 'score_asc' || sort === 'sessions_desc' || sort === 'latest' || sort === 'risk') {
    sortMode.value = sort
  }
}

const formatAvgScore = (value: number | null | undefined) => {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return '--'
  return Number(value).toFixed(1)
}

const getScoreTextClass = (value: number | null | undefined) => {
  const num = Number(value)
  if (!Number.isFinite(num)) return 'text-slate-500'
  if (num >= 85) return 'text-emerald-600'
  if (num >= 60) return 'text-amber-600'
  return 'text-red-500'
}

const fillExample = () => {
  form.template = '251040702xx'
  form.startNo = 1
  form.endNo = 50
  form.password = '123456'
}

const fetchStudents = async () => {
  loading.value = true
  pageError.value = ''
  try {
    const res: any = await request.get('/auth/students')
    students.value = Array.isArray(res) ? res : []
  } catch {
    students.value = []
    pageError.value = '学员账号列表加载失败，请稍后重试。'
    showToast('学员账号列表加载失败')
  } finally {
    loading.value = false
  }
}

const applyCreateResult = async (res: any, password: string) => {
  lastCreateResult.created_count = Number(res?.created_count || 0)
  lastCreateResult.skipped_count = Number(res?.skipped_count || 0)
  lastCreateResult.created_usernames = Array.isArray(res?.created_usernames) ? res.created_usernames : []
  lastCreateResult.skipped_usernames = Array.isArray(res?.skipped_usernames) ? res.skipped_usernames : []
  lastCreatePassword.value = password
  await fetchStudents()
}

const createStudents = async () => {
  if (previewError.value) {
    showToast(previewError.value)
    return
  }
  if (!form.password.trim()) {
    showToast('请输入初始密码')
    return
  }

  creating.value = true
  try {
    const res: any = await request.post('/auth/students/batch', {
      template: form.template.trim(),
      start_no: Number(form.startNo),
      end_no: Number(form.endNo),
      password: form.password.trim(),
    })
    await applyCreateResult(res, form.password.trim())
    const message = lastCreateResult.created_count
      ? `已创建 ${lastCreateResult.created_count} 个账号${lastCreateResult.skipped_count ? `，跳过 ${lastCreateResult.skipped_count} 个已存在账号` : ''}`
      : `没有新建账号，${lastCreateResult.skipped_count} 个账号已存在`
    showToast({ type: lastCreateResult.created_count ? 'success' : 'fail', message })
  } catch {
    showToast('批量开通失败')
  } finally {
    creating.value = false
  }
}

const deleteStudents = async () => {
  if (previewError.value) {
    showToast(previewError.value)
    return
  }

  try {
    await showConfirmDialog({
      title: '确认批量删除',
      message: `将删除 ${previewList.value.length} 个目标学员账号，并清理这些账号下的训练会话和聊天记录，是否继续？`,
      confirmButtonColor: '#dc2626',
    })
  } catch {
    return
  }

  deleting.value = true
  try {
    const res: any = await request.delete('/auth/students/batch', {
      data: {
        template: form.template.trim(),
        start_no: Number(form.startNo),
        end_no: Number(form.endNo),
      },
    })
    lastDeleteResult.deleted_count = Number(res?.deleted_count || 0)
    lastDeleteResult.skipped_count = Number(res?.skipped_count || 0)
    lastDeleteResult.deleted_usernames = Array.isArray(res?.deleted_usernames) ? res.deleted_usernames : []
    lastDeleteResult.skipped_usernames = Array.isArray(res?.skipped_usernames) ? res.skipped_usernames : []
    await fetchStudents()
    const message = lastDeleteResult.deleted_count
      ? `已删除 ${lastDeleteResult.deleted_count} 个账号${lastDeleteResult.skipped_count ? `，${lastDeleteResult.skipped_count} 个目标账号未找到` : ''}`
      : '当前号段没有可删除的账号'
    showToast({ type: lastDeleteResult.deleted_count ? 'success' : 'fail', message })
  } catch {
    showToast('批量删除失败')
  } finally {
    deleting.value = false
  }
}

const chooseFile = () => {
  fileInputRef.value?.click()
}

const downloadImportTemplate = () => {
  const rows = [
    ['学号'],
    ['25104080101'],
    ['25104080102'],
  ]
  const csv = rows.map((row) => row.map((cell) => `"${String(cell).replace(/"/g, '""')}"`).join(',')).join('\n')
  const blob = new Blob(['\ufeff' + csv], { type: 'text/csv;charset=utf-8;' })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = 'student-import-template.csv'
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
  URL.revokeObjectURL(url)
}

const normalizeImportedUsernames = (rows: any[][]) => {
  if (!rows.length) {
    importSummary.totalRows = 0
    importSummary.validCount = 0
    importSummary.duplicateCount = 0
    return []
  }

  const firstRow = rows[0].map((cell) => String(cell ?? '').trim())
  const normalizedHeaderRow = firstRow.map((item) => item.toLowerCase())
  const headerIndex = normalizedHeaderRow.findIndex((item) => ['学号', 'username', '账号', 'account'].includes(item))
  const dataRows = headerIndex >= 0 ? rows.slice(1) : rows
  const targetIndex = headerIndex >= 0 ? headerIndex : 0

  const usernames = dataRows.map((row) => String(row?.[targetIndex] ?? '').trim()).filter(Boolean)
  const uniqueUsernames = Array.from(new Set(usernames))

  importSummary.totalRows = dataRows.length
  importSummary.validCount = usernames.length
  importSummary.duplicateCount = usernames.length - uniqueUsernames.length

  return uniqueUsernames
}

const handleFileChange = async (event: Event) => {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  if (!file) return

  importFileName.value = file.name
  importError.value = ''

  try {
    const buffer = await file.arrayBuffer()
    const workbook = XLSX.read(buffer, { type: 'array' })
    const firstSheetName = workbook.SheetNames[0]
    const firstSheet = workbook.Sheets[firstSheetName]
    const rows = XLSX.utils.sheet_to_json(firstSheet, { header: 1, raw: false }) as any[][]
    const uniqueUsernames = normalizeImportedUsernames(rows)

    if (!uniqueUsernames.length) {
      importError.value = '未从文件中识别到有效学号，请检查表头或第一列内容。'
      importedUsernames.value = []
      return
    }

    importedUsernames.value = uniqueUsernames
  } catch {
    importError.value = '文件解析失败，请使用 xlsx 或 csv 格式，并检查文件内容。'
    importedUsernames.value = []
    importSummary.totalRows = 0
    importSummary.validCount = 0
    importSummary.duplicateCount = 0
  } finally {
    input.value = ''
  }
}

const clearImportFile = () => {
  importFileName.value = ''
  importedUsernames.value = []
  importError.value = ''
  importSummary.totalRows = 0
  importSummary.validCount = 0
  importSummary.duplicateCount = 0
}

const importStudents = async () => {
  if (!importedUsernames.value.length) {
    showToast('请先选择并解析名单文件')
    return
  }
  if (!importForm.password.trim()) {
    showToast('请输入导入初始密码')
    return
  }

  importing.value = true
  try {
    const res: any = await request.post('/auth/students/import', {
      usernames: importedUsernames.value,
      password: importForm.password.trim(),
    })
    await applyCreateResult(res, importForm.password.trim())
    lastImportSummary.totalRows = importSummary.totalRows
    lastImportSummary.validCount = importSummary.validCount
    lastImportSummary.duplicateCount = importSummary.duplicateCount
    const message = lastCreateResult.created_count
      ? `已导入创建 ${lastCreateResult.created_count} 个账号${lastCreateResult.skipped_count ? `，跳过 ${lastCreateResult.skipped_count} 个已有账号` : ''}`
      : `名单中账号均已存在，本次没有新建`
    showToast({ type: lastCreateResult.created_count ? 'success' : 'fail', message })
  } catch {
    showToast('名单导入失败')
  } finally {
    importing.value = false
  }
}

const exportCreatedAccounts = () => {
  if (!lastCreateResult.created_usernames.length) {
    showToast('当前没有可导出的新增账号')
    return
  }

  const rows = [
    ['username', 'password'],
    ...lastCreateResult.created_usernames.map((username) => [username, lastCreatePassword.value || '']),
  ]
  const csv = rows.map((row) => row.map((cell) => `"${String(cell).replace(/"/g, '""')}"`).join(',')).join('\n')
  const blob = new Blob(['\ufeff' + csv], { type: 'text/csv;charset=utf-8;' })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  const timestamp = new Date().toISOString().slice(0, 19).replace(/[:T]/g, '-')
  link.href = url
  link.download = `student-accounts-${timestamp}.csv`
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
  URL.revokeObjectURL(url)
}

const formatTime = (iso: string) => {
  if (!iso) return '-'
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return '-'
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
}

onMounted(() => {
  applyRouteFilters()
  fetchStudents()
})
</script>

<style scoped>
.field-block {
  display: grid;
  gap: 10px;
}

.field-label {
  font-size: 13px;
  font-weight: 700;
  color: #334155;
}

.field-input,
.search-input {
  width: 100%;
  min-height: 46px;
  border-radius: 16px;
  border: 1px solid #dbe3ee;
  background: #fff;
  padding: 0 16px;
  font-size: 14px;
  color: #0f172a;
  outline: none;
  transition: border-color 0.2s ease, box-shadow 0.2s ease;
}

.field-input:focus,
.search-input:focus {
  border-color: #93b4d6;
  box-shadow: 0 0 0 4px rgba(69, 123, 157, 0.12);
}

.preview-chip {
  display: inline-flex;
  align-items: center;
  padding: 6px 10px;
  border-radius: 999px;
  background: #fff;
  border: 1px solid #e2e8f0;
  color: #334155;
  font-size: 12px;
  font-weight: 700;
}

.summary-pill {
  display: inline-flex;
  align-items: center;
  padding: 6px 10px;
  border-radius: 999px;
  background: #f8fafc;
  color: #475569;
  font-weight: 700;
}

.result-stat {
  border-width: 1px;
  border-style: solid;
  border-radius: 20px;
  padding: 18px 20px;
}

.result-stat__label {
  font-size: 12px;
  font-weight: 700;
}

.result-stat__value {
  margin-top: 10px;
  font-size: 28px;
  font-weight: 800;
}
</style>
