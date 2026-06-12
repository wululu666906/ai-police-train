<template>
  <div class="students-page space-y-5 pb-20">

    <!-- 页头 -->
    <div class="admin-list-header">
      <div>
        <h1>学员账号</h1>
        <p>支持按学号模板批量开通、名单导入开户，以及导出账号清单。</p>
      </div>
      <div class="flex items-center gap-3">
        <van-button plain class="!rounded-[6px] !border-slate-200 !text-slate-600" :loading="loading" @click="fetchStudents">
          刷新列表
        </van-button>
        <van-button plain class="!rounded-[6px] !border-[#1D3557] !text-[#1D3557]" icon="description" @click="showImportPopup = true">
          名单导入
        </van-button>
        <van-button type="primary" icon="plus" class="!bg-[#1D3557] !border-none !rounded-[6px]" @click="showBatchPopup = true">
          批量开通
        </van-button>
      </div>
    </div>

    <!-- 上次操作结果条 -->
    <div v-if="lastCreateResult.created_count > 0 || lastDeleteResult.deleted_count > 0" class="result-bar">
      <div class="result-bar__inner">
        <template v-if="lastCreateResult.created_count > 0">
          <span class="result-bar__item text-emerald-700">
            <van-icon name="success" />
            本次新建 {{ lastCreateResult.created_count }} 个
          </span>
          <span v-if="lastCreateResult.skipped_count > 0" class="result-bar__item text-amber-600">
            跳过重复 {{ lastCreateResult.skipped_count }} 个
          </span>
          <van-button plain size="mini" class="!border-slate-200 !text-slate-500 !rounded-full" :disabled="!lastCreateResult.created_usernames.length" @click="exportCreatedAccounts">
            导出本次清单
          </van-button>
        </template>
        <template v-if="lastDeleteResult.deleted_count > 0">
          <span class="result-bar__item text-red-600">
            <van-icon name="delete-o" />
            本次删除 {{ lastDeleteResult.deleted_count }} 个
          </span>
        </template>
      </div>
      <van-icon name="cross" class="cursor-pointer text-slate-300 hover:text-slate-500" @click="clearLastResult" />
    </div>

    <!-- 筛选栏 -->
    <section class="admin-filter-panel">
      <div class="admin-filter-bar">
        <label class="admin-filter-item">
          <span>排序</span>
          <select v-model="sortMode" class="admin-filter-select">
            <option value="risk">风险优先</option>
            <option value="score_asc">均分从低到高</option>
            <option value="sessions_desc">训练次数从高到低</option>
            <option value="latest">创建时间从新到旧</option>
          </select>
        </label>
        <label class="student-checkbox-filter">
          <input v-model="onlyLowScore" type="checkbox" class="h-4 w-4 rounded border-slate-300" />
          仅看均分低于 60
        </label>
      </div>
      <label class="admin-search-box">
        <van-icon name="search" />
        <input v-model.trim="searchText" type="text" placeholder="搜索学号" />
      </label>
      <div class="admin-filter-summary">
        筛选 {{ filteredStudents.length }} / {{ students.length }} 人 &nbsp;·&nbsp; 低分预警 {{ lowScoreCount }} 人
      </div>
    </section>

    <!-- 高频薄弱项标签筛选 -->
    <div v-if="gapFilterOptions.length" class="gap-filter-bar">
      <span class="gap-filter-label">薄弱项</span>
      <button
        type="button"
        class="gap-chip"
        :class="selectedGap === '' ? 'gap-chip--active' : ''"
        @click="selectedGap = ''"
      >全部</button>
      <button
        v-for="item in gapFilterOptions"
        :key="item"
        type="button"
        class="gap-chip"
        :class="selectedGap === item ? 'gap-chip--warn' : ''"
        @click="selectedGap = item"
      >{{ item }}</button>
    </div>

    <!-- 学员列表 -->
    <div v-if="loading" class="rounded-2xl border border-slate-100 bg-white py-24 text-center">
      <van-loading color="#1D3557" vertical>正在加载学员账号...</van-loading>
    </div>
    <div v-else-if="pageError" class="rounded-2xl border border-amber-200 bg-amber-50 px-6 py-12 text-center">
      <van-icon name="warning-o" size="30" class="text-amber-500" />
      <p class="mt-4 text-sm font-bold text-amber-800">{{ pageError }}</p>
      <van-button plain type="primary" class="mt-5" @click="fetchStudents">重新加载</van-button>
    </div>
    <div v-else-if="filteredStudents.length" class="student-table-wrap">
      <table class="student-table">
        <thead>
          <tr>
            <th>学员账号</th>
            <th>创建时间</th>
            <th>训练次数</th>
            <th>已完成</th>
            <th>均分</th>
            <th>高频薄弱项</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="student in filteredStudents" :key="student.id">
            <td>
              <button type="button" class="student-name student-link" @click="openStudentProfile(student.id)">
                {{ student.username }}
              </button>
              <van-tag type="primary" plain>学员</van-tag>
            </td>
            <td>{{ formatTime(student.created_at) }}</td>
            <td class="metric-cell">{{ student.total_sessions ?? 0 }}</td>
            <td class="metric-cell text-[#165dff]">{{ student.finished_sessions ?? 0 }}</td>
            <td class="metric-cell" :class="getScoreTextClass(student.avg_score)">
              {{ formatAvgScore(student.avg_score) }}
            </td>
            <td>
              <div v-if="student.top_gap_missing?.length" class="student-gap-list">
                <span v-for="item in student.top_gap_missing" :key="item" class="student-gap-chip">{{ item }}</span>
              </div>
              <span v-else class="student-ok">暂无明显重复缺口</span>
            </td>
            <td>
              <button type="button" class="profile-action-btn" @click="openStudentProfile(student.id)">
                查看画像
              </button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
    <div v-else class="rounded-2xl border border-dashed border-slate-200 bg-white py-20 text-center text-slate-400">
      暂无符合条件的学员账号
    </div>

    <!-- 弹窗：批量开通 -->
    <van-popup
      v-model:show="showBatchPopup"
      teleport="body"
      :style="{ width: 'min(560px, 96vw)', borderRadius: '16px', overflow: 'hidden' }"
      class="flex flex-col"
    >
      <div class="flex h-14 items-center justify-between border-b border-slate-100 px-5">
        <h3 class="font-bold text-slate-800">批量开通账号</h3>
        <van-icon name="cross" class="cursor-pointer text-slate-400" @click="showBatchPopup = false" />
      </div>
      <div class="overflow-y-auto p-5 space-y-4" style="max-height: 80vh">
        <div class="rounded-xl bg-blue-50 border border-blue-100 px-4 py-3 text-sm text-blue-700">
          系统将模板末尾的 <code>x / X</code> 作为流水号占位符，例如 <code>251040702xx</code> → 01 ~ 50
        </div>
        <div class="grid grid-cols-1 gap-4">
          <div class="field-block">
            <label class="field-label">学号模板</label>
            <div class="flex gap-2">
              <input v-model.trim="form.template" type="text" class="field-input" placeholder="例如 251040702xx" />
              <van-button plain size="small" class="!border-slate-200 !text-slate-500 shrink-0" @click="fillExample">示例</van-button>
            </div>
          </div>
          <div class="grid grid-cols-2 gap-4">
            <div class="field-block">
              <label class="field-label">起始编号</label>
              <input v-model.number="form.startNo" type="number" min="1" class="field-input" placeholder="1" />
            </div>
            <div class="field-block">
              <label class="field-label">结束编号</label>
              <input v-model.number="form.endNo" type="number" min="1" class="field-input" placeholder="50" />
            </div>
          </div>
          <div class="field-block">
            <label class="field-label">初始密码</label>
            <input v-model.trim="form.password" type="text" class="field-input" placeholder="请输入统一初始密码" />
          </div>
        </div>

        <div class="rounded-xl bg-slate-50 border border-slate-100 p-4">
          <div class="text-sm font-bold text-slate-700">生成预览</div>
          <div class="mt-2 text-sm text-slate-500 leading-7">
            <template v-if="previewError">{{ previewError }}</template>
            <template v-else-if="previewList.length">
              <div>将生成 {{ previewList.length }} 个账号：</div>
              <div class="mt-2 flex flex-wrap gap-2">
                <span v-for="item in previewVisibleList" :key="item" class="preview-chip">{{ item }}</span>
              </div>
              <div v-if="previewHiddenCount > 0" class="mt-2 text-xs text-slate-400">
                其余 {{ previewHiddenCount }} 个账号执行时一并生成。
              </div>
            </template>
            <template v-else>请输入模板、编号范围后查看预览。</template>
          </div>
        </div>

        <div class="flex gap-3 pt-1">
          <van-button type="primary" class="!bg-[#1D3557] !border-none !rounded-[6px] flex-1" :loading="creating" @click="createStudents">
            批量开通账号
          </van-button>
          <van-button plain class="!rounded-[6px] !border-red-200 !text-red-600" :loading="deleting" @click="deleteStudents">
            删除该号段
          </van-button>
        </div>
      </div>
    </van-popup>

    <!-- 弹窗：名单导入 -->
    <van-popup
      v-model:show="showImportPopup"
      teleport="body"
      :style="{ width: 'min(520px, 96vw)', borderRadius: '16px', overflow: 'hidden' }"
      class="flex flex-col"
    >
      <div class="flex h-14 items-center justify-between border-b border-slate-100 px-5">
        <h3 class="font-bold text-slate-800">名单导入开户</h3>
        <van-icon name="cross" class="cursor-pointer text-slate-400" @click="showImportPopup = false" />
      </div>
      <div class="overflow-y-auto p-5 space-y-4" style="max-height: 80vh">
        <div class="rounded-xl bg-slate-50 border border-slate-100 p-4 text-sm text-slate-500 leading-7">
          支持 <code>xlsx / csv</code>，优先识别 <code>学号</code>、<code>username</code>、<code>账号</code>、<code>account</code> 列；若无表头则读取第一列。
        </div>

        <div class="flex items-center gap-3">
          <input ref="fileInputRef" type="file" accept=".xlsx,.csv" class="hidden" @change="handleFileChange" />
          <van-button plain class="!rounded-[6px] !border-slate-200 !text-slate-600 flex-1" icon="description" @click="chooseFile">
            {{ importFileName || '选择名单文件' }}
          </van-button>
          <van-button plain size="small" class="!rounded-[6px] !border-slate-200 !text-slate-500 shrink-0" @click="downloadImportTemplate">
            下载模板
          </van-button>
          <van-button v-if="importFileName" plain size="small" class="!rounded-[6px] !border-slate-200 !text-slate-400 shrink-0" @click="clearImportFile">
            清空
          </van-button>
        </div>

        <div class="field-block">
          <label class="field-label">导入初始密码</label>
          <input v-model.trim="importForm.password" type="text" class="field-input" placeholder="请输入导入账号统一初始密码" />
        </div>

        <div class="rounded-xl bg-slate-50 border border-slate-100 p-4">
          <div class="flex items-center justify-between gap-3">
            <div class="text-sm font-bold text-slate-700">名单预览</div>
            <div v-if="importPreviewList.length" class="text-xs text-slate-400">
              有效 {{ importSummary.validCount }} 条，去重 {{ importSummary.duplicateCount }} 条
            </div>
          </div>
          <div class="mt-2 text-sm text-slate-500 leading-7">
            <template v-if="importError">{{ importError }}</template>
            <template v-else-if="importPreviewList.length">
              <div>识别到 {{ importPreviewList.length }} 个账号：</div>
              <div class="mt-2 flex flex-wrap gap-2">
                <span v-for="item in importPreviewVisibleList" :key="item" class="preview-chip">{{ item }}</span>
              </div>
              <div v-if="importPreviewHiddenCount > 0" class="mt-2 text-xs text-slate-400">
                还有 {{ importPreviewHiddenCount }} 个已识别，可直接导入。
              </div>
            </template>
            <template v-else>请选择名单文件后查看预览。</template>
          </div>
        </div>

        <div v-if="lastImportSummary.totalRows > 0" class="rounded-xl border border-slate-100 bg-slate-50 p-3 text-xs text-slate-500">
          上次导入：原始 {{ lastImportSummary.totalRows }} 行，识别 {{ lastImportSummary.validCount }} 个，去重 {{ lastImportSummary.duplicateCount }} 个，创建 {{ lastCreateResult.created_count }} 个，跳过 {{ lastCreateResult.skipped_count }} 个。
        </div>

        <van-button type="primary" class="!bg-[#1D3557] !border-none !rounded-[6px] w-full" :loading="importing" @click="importStudents">
          导入并开通账号
        </van-button>
      </div>
    </van-popup>

  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import * as XLSX from 'xlsx'
import { showConfirmDialog, showToast } from 'vant'
import request from '../utils/request'

const route = useRoute()
const router = useRouter()
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
const showBatchPopup = ref(false)
const showImportPopup = ref(false)

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

const openStudentProfile = (studentId: number) => {
  router.push(`/admin/students/${studentId}`)
}

const clearLastResult = () => {
  lastCreateResult.created_count = 0
  lastCreateResult.skipped_count = 0
  lastCreateResult.created_usernames = []
  lastCreateResult.skipped_usernames = []
  lastDeleteResult.deleted_count = 0
  lastDeleteResult.skipped_count = 0
  lastDeleteResult.deleted_usernames = []
  lastDeleteResult.skipped_usernames = []
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
    if (lastCreateResult.created_count > 0) showBatchPopup.value = false
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
    if (lastCreateResult.created_count > 0) showImportPopup.value = false
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
.admin-list-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 18px 20px;
  border: 1px solid var(--police-border);
  border-radius: var(--police-radius-lg);
  background: #fff;
}

.admin-list-header h1 {
  margin: 0;
  color: var(--police-text-primary);
  font-size: 22px;
  font-weight: 800;
}

.admin-list-header p {
  margin: 4px 0 0;
  color: var(--police-text-muted);
  font-size: 13px;
}

/* 操作结果条 */
.result-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 10px 16px;
  border: 1px solid #d1fae5;
  border-radius: var(--police-radius-lg);
  background: #f0fdf4;
}

.result-bar__inner {
  display: flex;
  align-items: center;
  gap: 14px;
  flex-wrap: wrap;
}

.result-bar__item {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  font-size: 13px;
  font-weight: 700;
}

/* 筛选栏 */
.admin-filter-panel {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 14px;
  padding: 12px 16px;
  border: 1px solid var(--police-border);
  border-radius: var(--police-radius-lg);
  background: #fff;
}

.admin-filter-bar {
  display: flex;
  align-items: center;
  gap: 12px;
}

.admin-filter-item {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  color: var(--police-text-secondary);
  font-size: 13px;
}

.admin-filter-select {
  height: 34px;
  min-width: 160px;
  border: 1px solid var(--police-border);
  border-radius: var(--police-radius);
  background: #fff;
  padding: 0 10px;
  color: var(--police-text-primary);
  font-size: 13px;
}

.admin-search-box {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  width: min(220px, 100%);
  height: 34px;
  border: 1px solid var(--police-border);
  border-radius: var(--police-radius);
  background: #fff;
  padding: 0 12px;
  color: var(--police-text-muted);
}

.admin-search-box input {
  min-width: 0;
  flex: 1;
  border: none;
  background: transparent;
  color: var(--police-text-primary);
  font-size: 13px;
  outline: none;
}

.admin-filter-summary {
  color: var(--police-text-muted);
  font-size: 13px;
  white-space: nowrap;
}

.student-checkbox-filter {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  color: var(--police-text-secondary);
  font-size: 12px;
  font-weight: 600;
  white-space: nowrap;
}

/* 薄弱项筛选 */
.gap-filter-bar {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
  padding: 10px 16px;
  border: 1px solid var(--police-border);
  border-radius: var(--police-radius-lg);
  background: #fff;
}

.gap-filter-label {
  font-size: 12px;
  font-weight: 700;
  color: var(--police-text-muted);
  margin-right: 4px;
}

.gap-chip {
  display: inline-flex;
  align-items: center;
  padding: 4px 12px;
  border-radius: 999px;
  background: #f1f5f9;
  color: #475569;
  font-size: 12px;
  font-weight: 700;
  border: none;
  cursor: pointer;
  transition: background 0.15s, color 0.15s;
}

.gap-chip:hover {
  background: #e2e8f0;
}

.gap-chip--active {
  background: #1D3557;
  color: #fff;
}

.gap-chip--warn {
  background: #f59e0b;
  color: #fff;
}

/* 弹窗内字段 */
.field-block {
  display: grid;
  gap: 8px;
}

.field-label {
  font-size: 13px;
  font-weight: 700;
  color: #334155;
}

.field-input {
  width: 100%;
  min-height: 36px;
  border-radius: var(--police-radius);
  border: 1px solid #dbe3ee;
  background: #fff;
  padding: 0 12px;
  font-size: 13px;
  color: #0f172a;
  outline: none;
  transition: border-color 0.2s ease, box-shadow 0.2s ease;
}

.field-input:focus {
  border-color: #93b4d6;
  box-shadow: 0 0 0 3px rgba(69, 123, 157, 0.1);
}

.preview-chip {
  display: inline-flex;
  align-items: center;
  padding: 4px 10px;
  border-radius: 999px;
  background: #fff;
  border: 1px solid #e2e8f0;
  color: #334155;
  font-size: 12px;
  font-weight: 700;
}

/* 学员表格 */
.student-table-wrap {
  overflow-x: auto;
  border: 1px solid var(--police-border);
  border-radius: var(--police-radius-lg);
  background: #fff;
}

.student-table {
  width: 100%;
  min-width: 860px;
  border-collapse: collapse;
}

.student-table th {
  background: #f8fafc;
  border-bottom: 1px solid var(--police-border);
  padding: 12px 14px;
  text-align: left;
  font-size: 13px;
  font-weight: 700;
  color: var(--police-text-secondary);
  white-space: nowrap;
}

.student-table td {
  border-bottom: 1px solid var(--police-border-light);
  padding: 13px 14px;
  vertical-align: middle;
  font-size: 13px;
  color: var(--police-text-primary);
}

.student-table tr:last-child td {
  border-bottom: none;
}

.student-table tbody tr:hover td {
  background: #f8fafc;
}

.student-name {
  margin-bottom: 5px;
  font-weight: 700;
  color: #1e293b;
}

.student-link {
  display: inline-flex;
  align-items: center;
  border: none;
  background: transparent;
  padding: 0;
  cursor: pointer;
}

.student-link:hover {
  color: #1d4ed8;
}

.profile-action-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 88px;
  height: 34px;
  border-radius: 999px;
  border: 1px solid #cbd5e1;
  background: #ffffff;
  color: #1d3557;
  font-size: 13px;
  font-weight: 700;
  transition: all 0.2s ease;
}

.profile-action-btn:hover {
  border-color: #1d3557;
  background: #eff6ff;
}

.metric-cell {
  font-size: 16px;
  font-weight: 800;
  font-variant-numeric: tabular-nums;
}

.student-gap-list {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.student-gap-chip {
  display: inline-flex;
  align-items: center;
  border-radius: 20px;
  background: #fff7ed;
  color: #c2410c;
  padding: 3px 9px;
  font-size: 12px;
  font-weight: 700;
}

.student-ok {
  color: var(--police-success);
  font-size: 12px;
  font-weight: 700;
}
</style>
