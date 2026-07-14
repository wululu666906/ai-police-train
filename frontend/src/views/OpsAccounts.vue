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
        <button type="button" class="ops-action-btn" :disabled="loading" @click="fetchAccounts">
          <OpsIcon name="refresh" />
          <span>刷新</span>
        </button>
        <button type="button" class="ops-action-btn" @click="showBatchDialog = true">
          <OpsIcon name="batch" />
          <span>批量学员</span>
        </button>
        <button type="button" class="ops-action-btn" @click="triggerImportFile">
          <OpsIcon name="bookmark-plus" />
          <span>文件导入</span>
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

    <section class="ops-table-wrap">
      <table class="ops-table">
        <thead>
          <tr>
            <th>账号</th>
            <th>角色</th>
            <th>单位/部门</th>
            <th>联系方式</th>
            <th>最后登录</th>
            <th>创建时间</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-if="loading">
            <td colspan="7" class="ops-empty">正在加载账号...</td>
          </tr>
          <tr v-else-if="!accounts.length">
            <td colspan="7" class="ops-empty">暂无账号</td>
          </tr>
          <tr v-for="accountItem in accounts" v-else :key="accountItem.id">
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

    <input ref="importFileInput" class="ops-file-input" type="file" accept=".xlsx,.xls,.csv,.tsv,.json,.docx,.ods,.pdf,.txt" @change="handleImportFileChange" />

    <van-popup v-model:show="showImportDialog" teleport="body" :style="{ width: 'min(920px, 96vw)', maxHeight: '92vh', borderRadius: '8px', overflow: 'hidden' }">
      <div class="ops-dialog ops-dialog--import">
        <header>
          <h3>文件导入账号</h3>
          <van-icon name="cross" @click="closeImportDialog" />
        </header>
        <div class="ops-import-panel">
          <div class="ops-import-meta">
            <div><span>文件</span><strong>{{ importFileName || '未选择' }}</strong></div>
            <div><span>总数</span><strong>{{ importPreview?.total_count || 0 }}</strong></div>
            <div><span>可导入</span><strong>{{ importPreview?.ready_count || 0 }}</strong></div>
            <div><span>错误</span><strong>{{ importPreview?.error_count || 0 }}</strong></div>
          </div>
          <p class="ops-import-tip">支持 xlsx、csv、tsv、json、docx、ods、pdf、txt；建议优先使用 xlsx 或 csv。PDF 仅支持可复制文本的表格型文件。</p>
          <div v-if="importLoading" class="ops-import-state">正在解析文件...</div>
          <div v-else-if="importError" class="ops-import-state ops-import-state--error">{{ importError }}</div>
          <div v-else class="ops-import-table-wrap">
            <table class="ops-import-table">
              <thead>
                <tr>
                  <th>行号</th>
                  <th>账号</th>
                  <th>角色</th>
                  <th>初始密码</th>
                  <th>显示名</th>
                  <th>状态</th>
                  <th>问题</th>
                </tr>
              </thead>
              <tbody>
                <tr v-if="!importPreviewItems.length">
                  <td colspan="7" class="ops-empty">暂无导入内容</td>
                </tr>
                <tr v-for="item in importPreviewItems" :key="`${item.row_number}-${item.username}`">
                  <td>{{ item.row_number }}</td>
                  <td>{{ item.username }}</td>
                  <td><span class="ops-role" :class="`ops-role--${item.role}`">{{ roleLabel(item.role) }}</span></td>
                  <td>{{ item.password || '123456' }}</td>
                  <td>{{ item.display_name || item.real_name || '-' }}</td>
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
          <van-button type="primary" :loading="importCommitting" :disabled="!importPreview?.ready_count" @click="commitImport">确认导入</van-button>
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
  bio?: string
  status?: string
  errors?: string[]
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
const accounts = ref<Account[]>([])
const keyword = ref('')
const roleFilter = ref('')
const showAccountDialog = ref(false)
const showBatchDialog = ref(false)
const showResetDialog = ref(false)
const showImportDialog = ref(false)
const editingAccount = ref<Account | null>(null)
const resetTarget = ref<Account | null>(null)
const newPassword = ref('123456')
const importFileInput = ref<HTMLInputElement | null>(null)
const importFileName = ref('')
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
  bio: '',
})

const batchForm = reactive({
  template: '251040702xx',
  start_no: 1,
  end_no: 10,
  password: '123456',
})

const importPreviewItems = computed(() => importPreview.value?.items || [])

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
    if (keyword.value) params.keyword = keyword.value
    const res: any = await request.get('/ops/accounts', { params })
    accounts.value = Array.isArray(res) ? res : []
  } finally {
    loading.value = false
  }
}

const triggerImportFile = () => {
  importFileInput.value?.click()
}

const closeImportDialog = () => {
  showImportDialog.value = false
  importFileName.value = ''
  importPreview.value = null
  importError.value = ''
  importLoading.value = false
  importCommitting.value = false
  if (importFileInput.value) importFileInput.value.value = ''
}

const buildImportTemplate = () => {
  const csv = '账号,初始密码,角色,显示名,姓名,电话,邮箱,单位,部门,备注\nstudent001,123456,学员端账号,示例学员,张三,13800000000,zs@example.com,示例单位,示例部门,备注'
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
    const res: any = await request.post('/ops/accounts/import/preview', formData)
    importPreview.value = res
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
  await previewImportFile(file)
}

const commitImport = async () => {
  const items = importPreview.value?.items || []
  const readyItems = items.filter((item) => item.status === 'ready').map((item) => ({
    row_number: item.row_number,
    username: item.username,
    password: item.password,
    role: item.role,
    display_name: item.display_name,
    real_name: item.real_name,
    phone: item.phone,
    email: item.email,
    unit: item.unit,
    department: item.department,
    bio: item.bio,
  }))
  if (!readyItems.length) {
    showToast('没有可导入的账号')
    return
  }
  importCommitting.value = true
  try {
    const res: any = await request.post('/ops/accounts/import/commit', { accounts: readyItems })
    showToast({ type: 'success', message: `已创建 ${res.created_count || 0} 个，跳过 ${res.skipped_count || 0} 个` })
    closeImportDialog()
    await fetchAccounts()
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
  accountForm.bio = ''
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
    await fetchAccounts()
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
    })
    showToast({ type: 'success', message: `新增 ${res.created_count || 0} 个，跳过 ${res.skipped_count || 0} 个` })
    showBatchDialog.value = false
    await fetchAccounts()
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
  await fetchAccounts()
}

onMounted(fetchAccounts)
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
  min-width: 1020px;
  border-collapse: collapse;
}

.ops-table th,
.ops-table td {
  border-bottom: 1px solid #eef2f7;
  padding: 12px 14px;
  text-align: left;
  font-size: 13px;
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
  grid-template-rows: auto auto minmax(0, 1fr);
  gap: 12px;
  padding: 16px;
  overflow: hidden;
}

.ops-import-meta {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
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
  min-width: 860px;
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
}
</style>
