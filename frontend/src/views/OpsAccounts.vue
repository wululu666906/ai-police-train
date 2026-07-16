<template>
  <div class="ops-accounts">
    <section class="ops-toolbar">
      <div class="ops-filters">
        <label>
          <span>角色</span>
          <select v-model="roleFilter" @change="fetchAccounts">
            <option value="">全部账号</option>
            <option value="admin">管理端账号</option>
            <option value="student">学员端账号</option>
            <option value="maintainer">维护账号</option>
          </select>
        </label>
        <label class="ops-search">
          <OpsIcon name="search" />
          <input v-model.trim="keyword" placeholder="搜索账号" @keyup.enter="fetchAccounts" />
        </label>
      </div>

      <div class="ops-actions">
        <label class="ops-group-move" title="将已选账号迁移到指定分类">
          <span>迁移到</span>
          <input v-model.trim="moveTargetGroup" list="ops-account-groups" placeholder="分类名" />
        </label>
        <button type="button" class="ops-action-btn" :disabled="!selectedDeletableAccountCount || movingGroup" @click="moveSelectedAccounts">
          <OpsIcon name="refresh" />
          <span>迁移分组</span>
        </button>
        <button type="button" class="ops-action-btn" :disabled="loading" @click="fetchAccounts">
          <OpsIcon name="refresh" />
          <span>刷新</span>
        </button>
        <button type="button" class="ops-action-btn" @click="showBatchDialog = true">
          <OpsIcon name="batch" />
          <span>批量学员</span>
        </button>
        <button type="button" class="ops-action-btn" @click="openImportDialog">
          <OpsIcon name="bookmark-plus" />
          <span>文件导入</span>
        </button>
        <button type="button" class="ops-action-btn" :disabled="!selectedDeletableAccountCount || deletingBatch" @click="batchDeleteSelected">
          <OpsIcon name="trash" />
          <span>批量删除{{ selectedDeletableAccountCount ? `（${selectedDeletableAccountCount}）` : '' }}</span>
        </button>
        <button type="button" class="ops-action-btn ops-action-btn--primary" @click="openCreateDialog">
          <OpsIcon name="add" />
          <span>创建账号</span>
        </button>
      </div>
    </section>

    <section class="ops-summary">
      <div v-for="item in summaryCards" :key="item.role">
        <span>{{ item.label }}</span>
        <strong>{{ item.count }}</strong>
      </div>
    </section>

    <section class="ops-group-nav">
      <button type="button" :class="{ active: !groupFilter }" @click="setGroupFilter('')">
        全部账号
        <strong>{{ accountsTotalCount }}</strong>
      </button>
      <button type="button" :class="{ active: groupFilter === '__ungrouped__' }" @click="setGroupFilter('__ungrouped__')">
        未分类
        <strong>{{ ungroupedCount }}</strong>
      </button>
      <button v-for="group in accountGroups" :key="group.name" type="button" :class="{ active: groupFilter === group.name }" @click="setGroupFilter(group.name)">
        {{ group.name }}
        <strong>{{ group.count }}</strong>
      </button>
    </section>

    <datalist id="ops-account-groups">
      <option v-for="group in accountGroups" :key="group.name" :value="group.name" />
    </datalist>

    <section class="ops-table-wrap">
      <table class="ops-table">
        <thead>
          <tr>
            <th class="ops-check-col">
              <input type="checkbox" :checked="allSelectableSelected" :indeterminate="someSelectableSelected && !allSelectableSelected" @change="toggleSelectAll" />
            </th>
            <th>账号</th>
            <th>角色</th>
            <th>单位/部门</th>
            <th>分类</th>
            <th>联系方式</th>
            <th>最后登录</th>
            <th>创建时间</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-if="loading">
            <td colspan="9" class="ops-empty">正在加载账号...</td>
          </tr>
          <tr v-else-if="!accounts.length">
            <td colspan="9" class="ops-empty">暂无账号</td>
          </tr>
          <tr v-for="accountItem in accounts" v-else :key="accountItem.id">
            <td class="ops-check-col">
              <input
                type="checkbox"
                :checked="selectedAccountIds.includes(accountItem.id)"
                :disabled="accountItem.role === 'maintainer' || accountItem.id === selfAccountId"
                @change="toggleSelectedAccount(accountItem.id)"
              />
            </td>
            <td>
              <button type="button" class="ops-account-name" @click="openEditDialog(accountItem)">
                {{ accountItem.username }}
              </button>
              <div class="ops-muted">{{ accountItem.display_name || accountItem.real_name || '-' }}</div>
            </td>
            <td>
              <span class="ops-role" :class="`ops-role--${accountItem.role}`">{{ roleLabel(accountItem.role) }}</span>
            </td>
            <td>{{ joinText(accountItem.unit, accountItem.department) }}</td>
            <td><span class="ops-group-chip">{{ accountItem.account_group || '未分类' }}</span></td>
            <td>{{ joinText(accountItem.phone, accountItem.email) }}</td>
            <td>{{ formatTime(accountItem.last_login_at) }}</td>
            <td>{{ formatDate(accountItem.created_at) }}</td>
            <td>
              <div class="ops-row-actions">
                <button type="button" @click="openEditDialog(accountItem)"><OpsIcon name="edit" :size="16" />编辑</button>
                <button type="button" @click="openResetDialog(accountItem)"><OpsIcon name="key" :size="16" />重置密码</button>
                <button type="button" class="danger" :disabled="accountItem.role === 'maintainer'" @click="deleteAccount(accountItem)"><OpsIcon name="trash" :size="16" />删除</button>
              </div>
            </td>
          </tr>
        </tbody>
      </table>
    </section>

    <input ref="importFileInput" class="ops-file-input" type="file" accept=".xlsx,.xls,.csv,.tsv,.json,.docx,.ods,.pdf,.txt" @change="handleImportFileChange" />

    <van-popup v-model:show="showAccountDialog" teleport="body" :style="{ width: 'min(620px, 96vw)', borderRadius: '8px', overflow: 'hidden' }">
      <div class="ops-dialog">
        <header>
          <h3>{{ editingAccount ? '编辑账号' : '创建账号' }}</h3>
          <van-icon name="cross" @click="showAccountDialog = false" />
        </header>
        <div class="ops-dialog__body">
          <label>
            <span>账号</span>
            <input v-model.trim="accountForm.username" />
          </label>
          <label>
            <span>角色</span>
            <select v-model="accountForm.role" :disabled="editingAccount?.role === 'maintainer'">
              <option value="admin">管理端账号</option>
              <option value="student">学员端账号</option>
            </select>
          </label>
          <label v-if="!editingAccount">
            <span>初始密码</span>
            <input v-model.trim="accountForm.password" type="text" />
          </label>
          <label>
            <span>账号分类</span>
            <input v-model.trim="accountForm.account_group" list="ops-account-groups" placeholder="例如：七月新开通 / 一班 / 维护测试" />
          </label>
          <label>
            <span>显示名</span>
            <input v-model.trim="accountForm.display_name" />
          </label>
          <label>
            <span>姓名</span>
            <input v-model.trim="accountForm.real_name" />
          </label>
          <label>
            <span>电话</span>
            <input v-model.trim="accountForm.phone" />
          </label>
          <label>
            <span>邮箱</span>
            <input v-model.trim="accountForm.email" />
          </label>
          <label>
            <span>单位</span>
            <input v-model.trim="accountForm.unit" />
          </label>
          <label>
            <span>部门</span>
            <input v-model.trim="accountForm.department" />
          </label>
          <label class="ops-dialog__wide">
            <span>备注</span>
            <textarea v-model.trim="accountForm.bio" rows="3"></textarea>
          </label>
        </div>
        <footer>
          <van-button plain @click="showAccountDialog = false">取消</van-button>
          <van-button type="primary" :loading="savingAccount" @click="saveAccount">保存</van-button>
        </footer>
      </div>
    </van-popup>

    <van-popup v-model:show="showBatchDialog" teleport="body" :style="{ width: 'min(560px, 96vw)', borderRadius: '8px', overflow: 'hidden' }">
      <div class="ops-dialog">
        <header>
          <h3>批量开通学员账号</h3>
          <van-icon name="cross" @click="showBatchDialog = false" />
        </header>
        <div class="ops-dialog__body">
          <label>
            <span>学号模板</span>
            <input v-model.trim="batchForm.template" placeholder="例如 251040702xx" />
          </label>
          <label>
            <span>起始编号</span>
            <input v-model.number="batchForm.start_no" type="number" min="1" />
          </label>
          <label>
            <span>结束编号</span>
            <input v-model.number="batchForm.end_no" type="number" min="1" />
          </label>
          <label>
            <span>初始密码</span>
            <input v-model.trim="batchForm.password" type="text" />
          </label>
          <label>
            <span>账号分类</span>
            <input v-model.trim="batchForm.account_group" list="ops-account-groups" placeholder="本次批量开通的分类名" />
          </label>
          <div class="ops-dialog__wide ops-preview">{{ batchPreviewText }}</div>
        </div>
        <footer>
          <van-button plain @click="showBatchDialog = false">取消</van-button>
          <van-button type="primary" :loading="savingBatch" @click="createBatch">批量开通</van-button>
        </footer>
      </div>
    </van-popup>

    <van-popup v-model:show="showResetDialog" teleport="body" :style="{ width: 'min(420px, 94vw)', borderRadius: '8px', overflow: 'hidden' }">
      <div class="ops-dialog">
        <header>
          <h3>重置密码</h3>
          <van-icon name="cross" @click="showResetDialog = false" />
        </header>
        <div class="ops-dialog__body ops-dialog__body--single">
          <div class="ops-reset-target">{{ resetTarget?.username }}</div>
          <label>
            <span>新密码</span>
            <input v-model.trim="newPassword" type="text" />
          </label>
        </div>
        <footer>
          <van-button plain @click="showResetDialog = false">取消</van-button>
          <van-button type="primary" :loading="savingPassword" @click="resetPassword">确认重置</van-button>
        </footer>
      </div>
    </van-popup>

    <van-popup v-model:show="showImportDialog" teleport="body" :style="{ width: 'min(920px, 96vw)', maxHeight: '92vh', borderRadius: '8px', overflow: 'hidden' }">
      <div class="ops-dialog ops-dialog--import">
        <header>
          <h3>文件导入账号</h3>
          <van-icon name="cross" @click="closeImportDialog" />
        </header>
        <div class="ops-import-panel">
          <div class="ops-import-controls">
            <label>
              <span>导入文件</span>
              <div class="ops-import-file-row">
                <input :value="importFileName || '未选择文件'" disabled />
                <van-button type="primary" plain :loading="importLoading" @click="triggerImportFile">选择文件</van-button>
              </div>
            </label>
            <label>
              <span>本次导入分类</span>
              <input v-model.trim="importAccountGroup" list="ops-account-groups" placeholder="填写后会应用到本次导入账号" @change="applyImportGroup" />
            </label>
          </div>
          <div class="ops-import-meta">
            <div><span>文件</span><strong>{{ importFileName || '未选择' }}</strong></div>
            <div><span>总数</span><strong>{{ importTotalCount }}</strong></div>
            <div><span>可导入</span><strong>{{ importReadyCount }}</strong></div>
            <div><span>已选</span><strong>{{ selectedImportCount }}</strong></div>
            <div><span>错误</span><strong>{{ importErrorCount }}</strong></div>
          </div>
          <p class="ops-import-tip">支持 xlsx、csv、tsv、json、docx、ods、pdf、txt；可在表头统一切换角色，也可逐行调整。选中后可批量移除不需要导入的账号。</p>
          <div class="ops-import-tip">表头角色按钮会优先作用于已勾选账号；若未勾选，则作用于全部可导入账号。</div>
          <div v-if="importLoading" class="ops-import-state">正在解析文件...</div>
          <div v-else-if="importError" class="ops-import-state ops-import-state--error">{{ importError }}</div>
          <div v-else class="ops-import-table-wrap">
            <table class="ops-import-table">
              <thead>
                <tr>
                  <th class="ops-import-check-cell">
                    <input
                      type="checkbox"
                      :checked="allImportRowsSelected"
                      :indeterminate="someImportRowsSelected && !allImportRowsSelected"
                      :disabled="!importPreviewItems.length"
                      @change="toggleSelectAllImportRows"
                    />
                  </th>
                  <th>行号</th>
                  <th>账号</th>
                  <th>
                    <div class="ops-import-role-head">
                      <span>角色</span>
                      <div class="ops-import-role-actions">
                        <button type="button" :class="['ops-import-role-action', importTargetRole === 'student' ? 'is-active' : '']" :disabled="!importPreviewItems.length || importLoading || importCommitting" @click="applyImportRole('student')">学员端</button>
                        <button type="button" :class="['ops-import-role-action', importTargetRole === 'admin' ? 'is-active' : '']" :disabled="!importPreviewItems.length || importLoading || importCommitting" @click="applyImportRole('admin')">管理端</button>
                      </div>
                    </div>
                  </th>
                  <th>初始密码</th>
                  <th>显示名</th>
                  <th>分类</th>
                  <th>状态</th>
                  <th>问题</th>
                </tr>
              </thead>
              <tbody>
                <tr v-if="!importPreviewItems.length">
                  <td colspan="9" class="ops-empty">暂无导入内容</td>
                </tr>
                <tr v-for="item in importPreviewItems" :key="`${item.row_number}-${item.username}`">
                  <td class="ops-import-check-cell">
                    <input
                      type="checkbox"
                      :checked="item.selected"
                      @change="toggleImportRow(item)"
                    />
                  </td>
                  <td>{{ item.row_number }}</td>
                  <td>{{ item.username }}</td>
                  <td>
                    <select v-model="item.role" :disabled="item.status !== 'ready'" @change="syncImportTargetRole(item.role)">
                      <option value="student">学员端账号</option>
                      <option value="admin">管理端账号</option>
                    </select>
                  </td>
                  <td>{{ item.password || '123456' }}</td>
                  <td>{{ item.display_name || item.real_name || '-' }}</td>
                  <td>
                    <input class="ops-import-group-input" v-model.trim="item.account_group" list="ops-account-groups" placeholder="未分类" />
                  </td>
                  <td>
                    <span :class="['ops-import-status', item.status === 'ready' ? 'ops-import-status--ready' : 'ops-import-status--error']">
                      {{ item.status === 'ready' ? '可导入' : '有问题' }}
                    </span>
                  </td>
                  <td class="ops-import-errors">
                    <span v-if="item.errors?.length">{{ item.errors.join('；') }}</span>
                    <span v-else>-</span>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
        <footer>
          <van-button plain @click="closeImportDialog">取消</van-button>
          <van-button plain :disabled="!importPreviewItems.length" @click="downloadImportTemplate">下载模板</van-button>
          <van-button plain :disabled="!selectedImportCount || importCommitting" @click="removeSelectedImportRows">批量删除（{{ selectedImportCount }}）</van-button>
          <van-button type="primary" :loading="importCommitting" :disabled="!selectedReadyImportCount" @click="commitImport">确认导入（{{ selectedReadyImportCount }}）</van-button>
        </footer>
      </div>
    </van-popup>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { showConfirmDialog, showToast } from 'vant'
import request from '../utils/request'
import OpsIcon from '../components/OpsIcon.vue'

type Account = {
  id: number
  username: string
  role: 'admin' | 'student' | 'maintainer'
  display_name?: string
  real_name?: string
  phone?: string
  email?: string
  unit?: string
  department?: string
  account_group?: string
  bio?: string
  created_at?: string
  updated_at?: string
  last_login_at?: string
}

type ImportItem = {
  row_number: number
  username: string
  password?: string
  role: 'admin' | 'student' | 'maintainer' | string
  display_name?: string
  real_name?: string
  phone?: string
  email?: string
  unit?: string
  department?: string
  account_group?: string
  bio?: string
  status?: string
  errors?: string[]
  selected?: boolean
}

type ImportPreview = {
  filename: string
  total_count: number
  ready_count: number
  error_count: number
  items: ImportItem[]
}

const loading = ref(false)
const savingAccount = ref(false)
const savingBatch = ref(false)
const savingPassword = ref(false)
const deletingBatch = ref(false)
const movingGroup = ref(false)
const accounts = ref<Account[]>([])
const accountGroups = ref<Array<{ name: string; count: number }>>([])
const ungroupedCount = ref(0)
const selectedAccountIds = ref<number[]>([])
const keyword = ref('')
const roleFilter = ref('')
const groupFilter = ref('')
const moveTargetGroup = ref('')
const showAccountDialog = ref(false)
const showBatchDialog = ref(false)
const showResetDialog = ref(false)
const showImportDialog = ref(false)
const editingAccount = ref<Account | null>(null)
const resetTarget = ref<Account | null>(null)
const newPassword = ref('123456')
const importFileInput = ref<HTMLInputElement | null>(null)
const importFileName = ref('')
const importTargetRole = ref<'student' | 'admin'>('student')
const importAccountGroup = ref('')
const importSelectedFile = ref<File | null>(null)
const importPreview = ref<ImportPreview | null>(null)
const importLoading = ref(false)
const importError = ref('')
const importCommitting = ref(false)

const accountForm = reactive({
  username: '',
  password: '123456',
  role: 'student',
  display_name: '',
  real_name: '',
  phone: '',
  email: '',
  unit: '',
  department: '',
  account_group: '',
  bio: '',
})

const batchForm = reactive({
  template: '251040702xx',
  start_no: 1,
  end_no: 10,
  password: '123456',
  account_group: '',
})

const importPreviewItems = computed(() => importPreview.value?.items || [])
const importSelectableItems = computed(() => importPreviewItems.value.filter((item) => item.status === 'ready'))
const selectedImportItems = computed(() => importPreviewItems.value.filter((item) => item.selected))
const selectedReadyImportItems = computed(() => selectedImportItems.value.filter((item) => item.status === 'ready'))
const selectedImportCount = computed(() => selectedImportItems.value.length)
const selectedReadyImportCount = computed(() => selectedReadyImportItems.value.length)
const importTotalCount = computed(() => importPreviewItems.value.length)
const importReadyCount = computed(() => importSelectableItems.value.length)
const importErrorCount = computed(() => importPreviewItems.value.filter((item) => item.status !== 'ready').length)
const allImportRowsSelected = computed(() => Boolean(importPreviewItems.value.length) && importPreviewItems.value.every((item) => item.selected))
const someImportRowsSelected = computed(() => importPreviewItems.value.some((item) => item.selected))
const selfAccountId = computed(() => Number(localStorage.getItem('user_id') || 0))
const selectableAccounts = computed(() => accounts.value.filter((item) => item.role !== 'maintainer' && item.id !== selfAccountId.value))
const selectedDeletableAccounts = computed(() => accounts.value.filter((item) => selectedAccountIds.value.includes(item.id) && item.role !== 'maintainer' && item.id !== selfAccountId.value))
const selectedDeletableAccountCount = computed(() => selectedDeletableAccounts.value.length)
const allSelectableSelected = computed(() => Boolean(selectableAccounts.value.length) && selectableAccounts.value.every((item) => selectedAccountIds.value.includes(item.id)))
const someSelectableSelected = computed(() => selectableAccounts.value.some((item) => selectedAccountIds.value.includes(item.id)))

const summaryCards = computed(() => {
  const counts = accounts.value.reduce<Record<string, number>>((acc, item) => {
    acc[item.role] = (acc[item.role] || 0) + 1
    return acc
  }, {})
  return [
    { role: 'admin', label: '管理端账号', count: counts.admin || 0 },
    { role: 'student', label: '学员端账号', count: counts.student || 0 },
    { role: 'maintainer', label: '维护账号', count: counts.maintainer || 0 },
  ]
})

const accountsTotalCount = computed(() => accountGroups.value.reduce((total, item) => total + item.count, ungroupedCount.value))

const batchPreviewText = computed(() => {
  const count = Math.max(0, Number(batchForm.end_no || 0) - Number(batchForm.start_no || 0) + 1)
  if (!batchForm.template.trim()) return '请输入学号模板。'
  if (count <= 0) return '请检查起始编号和结束编号。'
  return `将尝试创建 ${count} 个学员账号，已存在账号会自动跳过。`
})

const roleLabel = (role: string) => {
  if (role === 'maintainer') return '维护账号'
  if (role === 'admin') return '管理端账号'
  if (role === 'student') return '学员端账号'
  return role || '-'
}

const normalizeImportRole = (role: string) => (role === 'admin' ? 'admin' : 'student')

const joinText = (...values: Array<string | undefined>) => {
  const clean = values.map((item) => String(item || '').trim()).filter(Boolean)
  return clean.length ? clean.join(' / ') : '-'
}

const formatDate = (value?: string) => {
  if (!value) return '-'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return '-'
  return date.toLocaleDateString('zh-CN')
}

const formatTime = (value?: string) => {
  if (!value) return '-'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return '-'
  return date.toLocaleString('zh-CN', { hour12: false })
}

const fetchAccounts = async () => {
  loading.value = true
  try {
    const params: any = {}
    if (roleFilter.value) params.role = roleFilter.value
    if (groupFilter.value && groupFilter.value !== '__ungrouped__') params.group = groupFilter.value
    if (keyword.value) params.keyword = keyword.value
    const res: any = await request.get('/ops/accounts', { params })
    const rows = Array.isArray(res) ? res : []
    accounts.value = groupFilter.value === '__ungrouped__'
      ? rows.filter((item: Account) => !String(item.account_group || '').trim())
      : rows
    selectedAccountIds.value = selectedAccountIds.value.filter((id) => accounts.value.some((item) => item.id === id && item.role !== 'maintainer'))
  } finally {
    loading.value = false
  }
}

const fetchAccountGroups = async () => {
  const res: any = await request.get('/ops/account-groups')
  accountGroups.value = Array.isArray(res?.groups) ? res.groups : []
  ungroupedCount.value = Number(res?.ungrouped_count || 0)
}

const refreshAccountsAndGroups = async () => {
  await Promise.all([fetchAccounts(), fetchAccountGroups()])
}

const setGroupFilter = async (group: string) => {
  groupFilter.value = group
  selectedAccountIds.value = []
  await fetchAccounts()
}

const openImportDialog = () => {
  importTargetRole.value = 'student'
  importAccountGroup.value = groupFilter.value && groupFilter.value !== '__ungrouped__' ? groupFilter.value : ''
  importSelectedFile.value = null
  importFileName.value = ''
  importPreview.value = null
  importError.value = ''
  showImportDialog.value = true
}

const triggerImportFile = () => {
  importFileInput.value?.click()
}

const closeImportDialog = () => {
  showImportDialog.value = false
  importFileName.value = ''
  importSelectedFile.value = null
  importPreview.value = null
  importError.value = ''
  importLoading.value = false
  importCommitting.value = false
  importAccountGroup.value = ''
  if (importFileInput.value) importFileInput.value.value = ''
}

const buildImportTemplate = () => {
  const roleText = importTargetRole.value === 'admin' ? '管理端账号' : '学员端账号'
  const account = importTargetRole.value === 'admin' ? 'admin001' : 'student001'
  const csv = `账号,初始密码,角色,显示名,姓名,电话,邮箱,单位,部门,备注\n${account},123456,${roleText},示例账号,张三,13800000000,zs@example.com,示例单位,示例部门,备注`
  const blob = new Blob([csv], { type: 'text/csv;charset=utf-8' })
  const link = document.createElement('a')
  link.href = URL.createObjectURL(blob)
  link.download = '账号导入模板.csv'
  link.click()
  URL.revokeObjectURL(link.href)
}

const downloadImportTemplate = () => buildImportTemplate()

const previewImportFile = async (file: File) => {
  importLoading.value = true
  importError.value = ''
  try {
    const formData = new FormData()
    formData.append('file', file)
    formData.append('target_role', importTargetRole.value)
    const res: any = await request.post('/ops/accounts/import/preview', formData)
    const items = Array.isArray(res?.items)
      ? res.items.map((item: ImportItem) => ({
        ...item,
        role: normalizeImportRole(item.role),
        account_group: importAccountGroup.value || item.account_group || '',
        selected: item.status === 'ready',
      }))
      : []
    importPreview.value = { ...res, items }
    importFileName.value = res?.filename || file.name
    showImportDialog.value = true
  } catch (error: any) {
    importError.value = String(error?.response?.data?.detail || error?.message || '解析失败')
    showImportDialog.value = true
  } finally {
    importLoading.value = false
  }
}

const handleImportFileChange = async (event: Event) => {
  const target = event.target as HTMLInputElement
  const file = target.files?.[0]
  if (!file) return
  importSelectedFile.value = file
  await previewImportFile(file)
}

const repreviewImportFile = async () => {
  if (!importSelectedFile.value) {
    importPreview.value = null
    return
  }
  await previewImportFile(importSelectedFile.value)
}

const syncImportTargetRole = (role: string) => {
  importTargetRole.value = normalizeImportRole(role) as 'student' | 'admin'
}

const applyImportRole = (role: 'student' | 'admin') => {
  importTargetRole.value = role
  const targets = selectedReadyImportItems.value.length ? selectedReadyImportItems.value : importSelectableItems.value
  targets.forEach((item) => {
    item.role = role
  })
}

const applyImportGroup = () => {
  const targets = selectedImportItems.value.length ? selectedImportItems.value : importPreviewItems.value
  targets.forEach((item) => {
    item.account_group = importAccountGroup.value
  })
}

const toggleImportRow = (item: ImportItem) => {
  item.selected = !item.selected
}

const toggleSelectAllImportRows = () => {
  const nextState = !allImportRowsSelected.value
  importPreviewItems.value.forEach((item) => {
    item.selected = nextState
  })
}

const removeSelectedImportRows = async () => {
  if (!importPreview.value) return
  if (!selectedImportItems.value.length) {
    showToast('请先勾选要移除的账号')
    return
  }
  try {
    await showConfirmDialog({
      title: '确认批量删除',
      message: `将从本次导入预览中移除 ${selectedImportItems.value.length} 个账号，已选账号不会被导入，是否继续？`,
      confirmButtonColor: '#dc2626',
    })
  } catch {
    return
  }
  const selectedKeys = new Set(selectedImportItems.value.map((item) => `${item.row_number}-${item.username}`))
  importPreview.value = {
    ...importPreview.value,
    items: importPreviewItems.value.filter((item) => !selectedKeys.has(`${item.row_number}-${item.username}`)),
  }
}

const commitImport = async () => {
  const readyItems = selectedReadyImportItems.value.map((item) => ({
    row_number: item.row_number,
    username: item.username,
    password: item.password,
    role: normalizeImportRole(item.role),
    display_name: item.display_name,
    real_name: item.real_name,
    phone: item.phone,
    email: item.email,
    unit: item.unit,
    department: item.department,
    account_group: item.account_group,
    bio: item.bio,
  }))
  if (!readyItems.length) {
    showToast('请先选择可导入的账号')
    return
  }
  importCommitting.value = true
  try {
    const res: any = await request.post('/ops/accounts/import/commit', { accounts: readyItems })
    showToast({ type: 'success', message: `已创建 ${res.created_count || 0} 个，跳过 ${res.skipped_count || 0} 个` })
    closeImportDialog()
    await refreshAccountsAndGroups()
  } finally {
    importCommitting.value = false
  }
}

const resetAccountForm = () => {
  accountForm.username = ''
  accountForm.password = '123456'
  accountForm.role = 'student'
  accountForm.display_name = ''
  accountForm.real_name = ''
  accountForm.phone = ''
  accountForm.email = ''
  accountForm.unit = ''
  accountForm.department = ''
  accountForm.account_group = groupFilter.value && groupFilter.value !== '__ungrouped__' ? groupFilter.value : ''
  accountForm.bio = ''
}

const toggleSelectedAccount = (id: number) => {
  const account = accounts.value.find((item) => item.id === id)
  if (!account || account.role === 'maintainer' || account.id === selfAccountId.value) return
  if (selectedAccountIds.value.includes(id)) {
    selectedAccountIds.value = selectedAccountIds.value.filter((item) => item !== id)
  } else {
    selectedAccountIds.value = [...selectedAccountIds.value, id]
  }
}

const toggleSelectAll = () => {
  if (allSelectableSelected.value) {
    selectedAccountIds.value = []
  } else {
    selectedAccountIds.value = selectableAccounts.value.map((item) => item.id)
  }
}

const openCreateDialog = () => {
  editingAccount.value = null
  resetAccountForm()
  showAccountDialog.value = true
}

const openEditDialog = (item: Account) => {
  editingAccount.value = item
  accountForm.username = item.username || ''
  accountForm.password = ''
  accountForm.role = item.role === 'maintainer' ? 'admin' : item.role
  accountForm.display_name = item.display_name || ''
  accountForm.real_name = item.real_name || ''
  accountForm.phone = item.phone || ''
  accountForm.email = item.email || ''
  accountForm.unit = item.unit || ''
  accountForm.department = item.department || ''
  accountForm.account_group = item.account_group || ''
  accountForm.bio = item.bio || ''
  showAccountDialog.value = true
}

const saveAccount = async () => {
  if (!accountForm.username.trim()) {
    showToast('请输入账号')
    return
  }
  if (!editingAccount.value && accountForm.password.trim().length < 6) {
    showToast('初始密码至少 6 位')
    return
  }
  savingAccount.value = true
  try {
    const payload = {
      username: accountForm.username.trim(),
      role: accountForm.role,
      display_name: accountForm.display_name.trim(),
      real_name: accountForm.real_name.trim(),
      phone: accountForm.phone.trim(),
      email: accountForm.email.trim(),
      unit: accountForm.unit.trim(),
      department: accountForm.department.trim(),
      account_group: accountForm.account_group.trim(),
      bio: accountForm.bio.trim(),
    }
    if (editingAccount.value) {
      await request.patch(`/ops/accounts/${editingAccount.value.id}`, payload)
      showToast({ type: 'success', message: '账号已更新' })
    } else {
      await request.post('/ops/accounts', { ...payload, password: accountForm.password.trim() })
      showToast({ type: 'success', message: '账号已创建' })
    }
    showAccountDialog.value = false
    await refreshAccountsAndGroups()
  } finally {
    savingAccount.value = false
  }
}

const createBatch = async () => {
  if (!batchForm.template.trim() || !batchForm.password.trim()) {
    showToast('请补全模板和初始密码')
    return
  }
  savingBatch.value = true
  try {
    const res: any = await request.post('/ops/accounts/batch', {
      template: batchForm.template.trim(),
      start_no: Number(batchForm.start_no),
      end_no: Number(batchForm.end_no),
      password: batchForm.password.trim(),
      account_group: batchForm.account_group.trim(),
    })
    showToast({ type: 'success', message: `新增 ${res.created_count || 0} 个，跳过 ${res.skipped_count || 0} 个` })
    showBatchDialog.value = false
    await refreshAccountsAndGroups()
  } finally {
    savingBatch.value = false
  }
}

const openResetDialog = (item: Account) => {
  resetTarget.value = item
  newPassword.value = '123456'
  showResetDialog.value = true
}

const resetPassword = async () => {
  if (!resetTarget.value) return
  if (newPassword.value.trim().length < 6) {
    showToast('新密码至少 6 位')
    return
  }
  savingPassword.value = true
  try {
    await request.post(`/ops/accounts/${resetTarget.value.id}/reset-password`, { new_password: newPassword.value.trim() })
    showToast({ type: 'success', message: '密码已重置' })
    showResetDialog.value = false
  } finally {
    savingPassword.value = false
  }
}

const deleteAccount = async (item: Account) => {
  if (item.role === 'maintainer') return
  try {
    await showConfirmDialog({
      title: '确认删除账号',
      message: item.role === 'student'
        ? `将删除学员 ${item.username} 及其训练记录，是否继续？`
        : `将删除管理端账号 ${item.username}，是否继续？`,
      confirmButtonColor: '#dc2626',
    })
  } catch {
    return
  }
  await request.delete(`/ops/accounts/${item.id}`)
  showToast({ type: 'success', message: '账号已删除' })
  await refreshAccountsAndGroups()
}

const moveSelectedAccounts = async () => {
  const selected = selectedDeletableAccounts.value
  if (!selected.length) {
    showToast('请先选择要迁移的账号')
    return
  }
  const targetGroup = moveTargetGroup.value.trim()
  movingGroup.value = true
  try {
    await Promise.all(selected.map((item) => request.patch(`/ops/accounts/${item.id}`, { account_group: targetGroup })))
    showToast({ type: 'success', message: targetGroup ? `已迁移到 ${targetGroup}` : '已迁移到未分类' })
    selectedAccountIds.value = []
    await refreshAccountsAndGroups()
  } finally {
    movingGroup.value = false
  }
}

const batchDeleteSelected = async () => {
  const selected = selectedDeletableAccounts.value
  if (!selected.length) {
    showToast('请先选择可删除账号')
    return
  }
  const studentCount = selected.filter((item) => item.role === 'student').length
  const adminCount = selected.filter((item) => item.role === 'admin').length
  try {
    await showConfirmDialog({
      title: '确认批量删除账号',
      message: `将删除 ${selected.length} 个账号，其中管理端账号 ${adminCount} 个、学员端账号 ${studentCount} 个；删除学员会同步清理其训练记录，是否继续？`,
      confirmButtonColor: '#dc2626',
    })
  } catch {
    return
  }
  deletingBatch.value = true
  try {
    const res: any = await request.post('/ops/accounts/batch-delete', { account_ids: selected.map((item) => item.id) })
    showToast({ type: 'success', message: `已删除 ${res.deleted_count || 0} 个，跳过 ${res.skipped_count || 0} 个` })
    selectedAccountIds.value = []
    await refreshAccountsAndGroups()
  } finally {
    deletingBatch.value = false
  }
}

onMounted(refreshAccountsAndGroups)
</script>

<style scoped>
.ops-accounts {
  display: grid;
  gap: 16px;
}

.ops-toolbar,
.ops-summary,
.ops-table-wrap {
  border: 1px solid #dbe3ee;
  border-radius: 8px;
  background: #fff;
}

.ops-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 14px;
}

.ops-filters,
.ops-actions {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.ops-group-move {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  color: #475569;
  font-size: 13px;
  font-weight: 900;
}

.ops-group-move input {
  width: 150px;
  height: 36px;
  border: 1px solid #cbd5e1;
  border-radius: 6px;
  padding: 0 10px;
  outline: none;
}

.ops-filters label {
  display: flex;
  align-items: center;
  gap: 8px;
  color: #475569;
  font-size: 13px;
  font-weight: 800;
}

.ops-filters select,
.ops-search {
  height: 36px;
  border: 1px solid #cbd5e1;
  border-radius: 6px;
  background: #fff;
}

.ops-filters select {
  min-width: 140px;
  padding: 0 10px;
}

.ops-search {
  padding: 0 10px;
  color: #64748b;
}

.ops-search input {
  border: 0;
  outline: none;
}

.ops-action-btn {
  height: 36px;
  display: inline-flex;
  align-items: center;
  gap: 7px;
  border: 1px solid #cbd5e1;
  border-radius: 6px;
  background: #fff;
  color: #334155;
  padding: 0 12px;
  font-size: 13px;
  font-weight: 900;
  transition: background 0.15s ease, border-color 0.15s ease, color 0.15s ease, transform 0.15s ease;
}

.ops-action-btn:hover:not(:disabled) {
  border-color: #93c5fd;
  background: #eff6ff;
  color: #1d4ed8;
  transform: translateY(-1px);
}

.ops-action-btn:disabled {
  cursor: not-allowed;
  opacity: 0.56;
}

.ops-action-btn--primary {
  border-color: #2563eb;
  background: #2563eb;
  color: #fff;
}

.ops-action-btn--primary:hover:not(:disabled) {
  border-color: #1d4ed8;
  background: #1d4ed8;
  color: #fff;
}

.ops-summary {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
}

.ops-group-nav {
  display: flex;
  gap: 8px;
  overflow-x: auto;
  padding: 10px;
  border: 1px solid #dbe3ee;
  border-radius: 8px;
  background: #fff;
}

.ops-group-nav button {
  flex: none;
  display: inline-flex;
  align-items: center;
  gap: 8px;
  height: 34px;
  border: 1px solid #dbe3ee;
  border-radius: 999px;
  background: #f8fafc;
  color: #334155;
  padding: 0 12px;
  font-size: 13px;
  font-weight: 900;
}

.ops-group-nav button.active {
  border-color: #1d4ed8;
  background: #eff6ff;
  color: #1d4ed8;
}

.ops-group-nav strong {
  color: inherit;
  font-size: 12px;
}

.ops-summary div {
  padding: 14px 18px;
  border-right: 1px solid #eef2f7;
}

.ops-summary div:last-child {
  border-right: 0;
}

.ops-summary span {
  display: block;
  color: #64748b;
  font-size: 12px;
  font-weight: 800;
}

.ops-summary strong {
  display: block;
  margin-top: 4px;
  color: #0f172a;
  font-size: 24px;
}

.ops-table-wrap {
  overflow-x: auto;
}

.ops-table {
  width: 100%;
  min-width: 1120px;
  border-collapse: collapse;
}

.ops-table th,
.ops-table td {
  border-bottom: 1px solid #eef2f7;
  padding: 12px 14px;
  text-align: left;
  font-size: 13px;
}

.ops-check-col {
  width: 44px;
  text-align: center !important;
}

.ops-table th {
  background: #f8fafc;
  color: #475569;
  font-weight: 900;
}

.ops-account-name {
  border: 0;
  background: transparent;
  padding: 0;
  color: #1d4ed8;
  font-weight: 900;
}

.ops-muted {
  margin-top: 4px;
  color: #94a3b8;
  font-size: 12px;
}

.ops-role {
  display: inline-flex;
  border-radius: 999px;
  padding: 4px 9px;
  font-size: 12px;
  font-weight: 900;
}

.ops-role--maintainer {
  background: #eff6ff;
  color: #1d4ed8;
}

.ops-role--admin {
  background: #f0fdf4;
  color: #15803d;
}

.ops-role--student {
  background: #fff7ed;
  color: #c2410c;
}

.ops-group-chip {
  display: inline-flex;
  max-width: 150px;
  border-radius: 999px;
  background: #f1f5f9;
  color: #475569;
  padding: 4px 9px;
  font-size: 12px;
  font-weight: 900;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.ops-row-actions {
  display: flex;
  align-items: center;
  gap: 8px;
  white-space: nowrap;
}

.ops-row-actions button {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  border: 0;
  background: transparent;
  color: #2563eb;
  font-weight: 800;
}

.ops-row-actions .danger {
  color: #dc2626;
}

.ops-row-actions button:disabled {
  cursor: not-allowed;
  color: #cbd5e1;
}

.ops-file-input {
  display: none;
}

.ops-empty {
  height: 120px;
  text-align: center !important;
  color: #94a3b8;
}

.ops-dialog header,
.ops-dialog footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 16px;
  border-bottom: 1px solid #eef2f7;
}

.ops-dialog footer {
  justify-content: flex-end;
  gap: 10px;
  border-top: 1px solid #eef2f7;
  border-bottom: 0;
}

.ops-dialog h3 {
  margin: 0;
  font-size: 16px;
}

.ops-dialog--import {
  max-height: 92vh;
  display: flex;
  flex-direction: column;
}

.ops-dialog--import header,
.ops-dialog--import footer {
  flex: none;
}

.ops-dialog__body {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 14px;
  padding: 16px;
}

.ops-dialog__body--single {
  grid-template-columns: 1fr;
}

.ops-dialog label {
  display: grid;
  gap: 6px;
  color: #334155;
  font-size: 13px;
  font-weight: 800;
}

.ops-dialog input,
.ops-dialog select,
.ops-dialog textarea {
  width: 100%;
  border: 1px solid #cbd5e1;
  border-radius: 6px;
  padding: 8px 10px;
  outline: none;
}

.ops-dialog__wide {
  grid-column: 1 / -1;
}

.ops-preview,
.ops-reset-target {
  border: 1px solid #bfdbfe;
  border-radius: 6px;
  background: #eff6ff;
  padding: 10px;
  color: #1d4ed8;
  font-size: 13px;
  font-weight: 800;
}

.ops-import-panel {
  flex: 1;
  min-height: 0;
  display: grid;
  grid-template-rows: auto auto auto minmax(0, 1fr);
  gap: 12px;
  padding: 16px;
  overflow: hidden;
}

.ops-import-controls {
  display: grid;
  grid-template-columns: minmax(0, 1fr);
  gap: 10px;
}

.ops-import-file-row {
  display: flex;
  gap: 8px;
}

.ops-import-file-row input {
  flex: 1;
}

.ops-import-meta {
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 1fr));
  gap: 10px;
}

.ops-import-meta div {
  border: 1px solid #dbe3ee;
  border-radius: 6px;
  padding: 10px 12px;
  background: #f8fafc;
}

.ops-import-meta span {
  display: block;
  color: #64748b;
  font-size: 12px;
  font-weight: 800;
}

.ops-import-meta strong {
  display: block;
  margin-top: 4px;
  color: #0f172a;
  font-size: 18px;
}

.ops-import-tip {
  margin: 0;
  color: #64748b;
  font-size: 12px;
  line-height: 1.6;
}

.ops-import-state {
  padding: 18px;
  border-radius: 6px;
  background: #f8fafc;
  color: #475569;
  font-weight: 800;
}

.ops-import-state--error {
  background: #fef2f2;
  color: #b91c1c;
}

.ops-import-table-wrap {
  min-height: 240px;
  max-height: calc(92vh - 260px);
  overflow: auto;
  border: 1px solid #e2e8f0;
  border-radius: 6px;
}

.ops-import-table {
  width: 100%;
  min-width: 1100px;
  border-collapse: collapse;
}

.ops-import-table th,
.ops-import-table td {
  border-bottom: 1px solid #eef2f7;
  padding: 10px 12px;
  text-align: left;
  font-size: 12px;
  vertical-align: top;
}

.ops-import-table th {
  background: #f8fafc;
  color: #475569;
  font-weight: 900;
}

.ops-import-check-cell {
  width: 44px;
  text-align: center !important;
  vertical-align: middle !important;
}

.ops-import-check-cell input {
  width: 16px;
  height: 16px;
  accent-color: #2563eb;
}

.ops-import-role-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  min-width: 190px;
}

.ops-import-role-actions {
  display: inline-flex;
  gap: 4px;
  padding: 2px;
  border: 1px solid #dbe3ee;
  border-radius: 6px;
  background: #fff;
}

.ops-import-role-action {
  height: 26px;
  border: 0;
  border-radius: 4px;
  background: transparent;
  color: #64748b;
  padding: 0 8px;
  font-size: 12px;
  font-weight: 900;
}

.ops-import-role-action.is-active {
  background: #0f3f9c;
  color: #fff;
}

.ops-import-role-action:disabled {
  cursor: not-allowed;
  opacity: 0.5;
}

.ops-import-table td select {
  width: 118px;
  height: 30px;
  border: 1px solid #cbd5e1;
  border-radius: 6px;
  background: #fff;
  color: #0f172a;
  padding: 0 8px;
  font-size: 12px;
  font-weight: 800;
}

.ops-import-group-input {
  width: 130px;
  height: 30px;
  border: 1px solid #cbd5e1;
  border-radius: 6px;
  padding: 0 8px;
  font-size: 12px;
  font-weight: 800;
}

.ops-import-status {
  display: inline-flex;
  padding: 4px 8px;
  border-radius: 999px;
  font-weight: 900;
}

.ops-import-status--ready {
  background: #ecfdf5;
  color: #15803d;
}

.ops-import-status--error {
  background: #fef2f2;
  color: #dc2626;
}

.ops-import-errors {
  color: #b45309;
}

@media (max-width: 760px) {
  .ops-toolbar,
  .ops-summary {
    display: grid;
  }

  .ops-summary {
    grid-template-columns: 1fr;
  }

  .ops-dialog__body {
    grid-template-columns: 1fr;
  }

  .ops-import-meta {
    grid-template-columns: 1fr 1fr;
  }

  .ops-group-move input {
    width: 120px;
  }
}
</style>
