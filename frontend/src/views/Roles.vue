<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { showConfirmDialog, showToast } from 'vant'
import { useRouter } from 'vue-router'
import RoleCompactForm from '../components/RoleCompactForm.vue'
import {
  buildRoleCompactSummary,
  expandRoleCompactToPerson,
  personToRoleCompact,
} from '../utils/roleCompact'
import request from '../utils/request'

const router = useRouter()

const roles = ref<any[]>([])
const roleSearchText = ref('')
const roleTypeFilter = ref('')
const roleScopeFilter = ref('')
const roleCaseFilter = ref('')
const loading = ref(false)
const saving = ref(false)
const deleting = ref(false)
const showDetail = ref(false)
const roleOptions = ref<any[]>([])
const pageError = ref('')
const syncingCaseSelection = ref(false)
const form = reactive({
  id: null as number | null,
  scope: 'public' as 'public' | 'case',
  case_id: null as number | null,
  scene_ids: [] as number[],
  primary_scene_id: null as number | null,
})

const roleProfile = ref<Record<string, any>>({})

const previewList = (value: any) => (Array.isArray(value) ? value : []).slice(0, 4)

const roleTypeFilterOptions = computed(() =>
  Array.from(new Set(roles.value.map((item) => String(item?.role_type || '').trim()).filter(Boolean))).sort()
)

const roleCaseFilterOptions = computed(() =>
  Array.from(new Set(roles.value.map((item) => String(item?.case_title || '').trim()).filter(Boolean))).sort()
)

const filteredRoles = computed(() => {
  const keyword = roleSearchText.value.trim()
  return roles.value.filter((role) => {
    if (roleTypeFilter.value && role.role_type !== roleTypeFilter.value) return false
    if (roleScopeFilter.value === 'public' && !role.is_public) return false
    if (roleScopeFilter.value === 'case' && role.is_public) return false
    if (roleCaseFilter.value && String(role.case_title || '') !== roleCaseFilter.value) return false
    if (!keyword) return true
    const haystack = [
      role.name,
      role.role_type,
      role.case_title,
      role.status,
      buildRoleOverview(role),
    ].join(' ')
    return haystack.includes(keyword)
  })
})

const groupedRoles = computed(() => {
  const groups: Record<string, any[]> = {}
  filteredRoles.value.forEach((role) => {
    const title = role.case_title || '公共角色模板'
    if (!groups[title]) groups[title] = []
    groups[title].push(role)
  })
  return groups
})

const currentCaseScenes = computed(() => {
  const currentCase = roleOptions.value.find((item) => item.id === form.case_id)
  return currentCase?.scenes || []
})

const currentPrimaryScene = computed(() => {
  const preferredId = form.primary_scene_id || form.scene_ids[0]
  return currentCaseScenes.value.find((item: any) => item.id === preferredId) || null
})

const roleCountSummary = computed(() => ({
  total: roles.value.length,
  publicCount: roles.value.filter((item) => item.is_public).length,
  caseCount: roles.value.filter((item) => !item.is_public).length,
}))

watch(
  () => form.case_id,
  () => {
    if (syncingCaseSelection.value) return
    form.scene_ids = []
    form.primary_scene_id = null
  },
  { flush: 'sync' }
)

const roleSceneBehaviorMode = computed(() => {
  if (form.scope === 'case' && form.primary_scene_id) {
    const scene = currentCaseScenes.value.find((item: any) => item.id === form.primary_scene_id)
    if (scene?.behavior_mode) return scene.behavior_mode
  }
  if (form.scope === 'case' && currentPrimaryScene.value?.behavior_mode) {
    return currentPrimaryScene.value.behavior_mode
  }
  return String(roleProfile.value?.scene_behavior_mode || '核查取证型')
})

const roleDraftProfile = computed(() => {
  const normalized = expandRoleCompactToPerson(roleProfile.value, roleSceneBehaviorMode.value)
  const memories = Array.isArray(normalized.role_memories) ? normalized.role_memories : []
  const unresolvedClaims = Array.isArray(normalized.unresolved_claims) ? normalized.unresolved_claims : []
  return {
    normalized,
    memories,
    unresolvedClaims,
    summaryText: memories.length ? `已整理 ${memories.length} 条来源人物线，按时间、地点和证言边界参与运行时回答。` : '当前还没有可回溯的人物线，建议补充原文证言。',
  }
})

const previewStateLabel = computed(() => {
  const profile = roleDraftProfile.value.normalized
  if (profile.risk_level === '高') return '需要优先稳控'
  if (profile.clarity_level === '低') return '表达混乱不稳'
  if (profile.cooperation_level === '高') return '开场较易配合'
  if (profile.emotion_level === '高') return '开场情绪高压'
  return '初始谨慎试探'
})

const previewBreakthroughs = computed(() => {
  return roleDraftProfile.value.memories.slice(0, 4).map((item: any) => item.statement).filter(Boolean)
})

const buildRoleOverview = (role: any) => {
  const memories = Array.isArray(role?.role_memories) ? role.role_memories : []
  return memories.length ? `人物线 ${memories.length} 条：${memories[0]?.statement || ''}` : '还没有补充来源人物线。'
}

const getRoleSummaryChips = (role: any) => {
  const compact = personToRoleCompact(role)
  return [
    `人物线 ${compact.role_memories.length} 条`,
    compact.unresolved_claims.length ? `待核实 ${compact.unresolved_claims.length} 项` : '',
    compact.response_constraints.length ? `边界 ${compact.response_constraints.length} 条` : '',
  ].filter(Boolean).slice(0, 3)
}

const getInteractionStyleClass = (type: string) => {
  if (type === '委屈宣泄型' || type === '醉酒失控型') return 'bg-orange-100 text-orange-700'
  if (type === '强硬对抗型' || type === '围观起哄型') return 'bg-red-100 text-red-700'
  if (type === '求助配合型') return 'bg-green-100 text-green-700'
  return 'bg-blue-100 text-blue-700'
}

const fetchRoles = async () => {
  loading.value = true
  pageError.value = ''
  try {
    const res: any = await request.get('/cases/all/roles', { _skipErrorToast: true } as any)
    roles.value = Array.isArray(res) ? res : []
  } catch (error) {
    console.error('Fetch roles error:', error)
    pageError.value = '角色列表加载失败，请稍后重试。'
  } finally {
    loading.value = false
  }
}

const fetchRoleOptions = async () => {
  try {
    const res: any = await request.get('/cases/role-case-options', { _skipErrorToast: true } as any)
    roleOptions.value = Array.isArray(res) ? res : []
  } catch (error) {
    console.error('Fetch role options error:', error)
    pageError.value = pageError.value || '案件选项加载失败，请稍后重试。'
  }
}

const refreshPage = async () => {
  await Promise.all([fetchRoles(), fetchRoleOptions()])
}

const resetForm = () => {
  form.id = null
  form.scope = 'public'
  form.case_id = null
  form.scene_ids = []
  form.primary_scene_id = null
  roleProfile.value = expandRoleCompactToPerson({}, '核查取证型')
}

const closeDetail = () => {
  showDetail.value = false
}

const openCreate = () => {
  router.push('/admin/roles/new')
}

const openDetail = (role: any) => {
  router.push(`/admin/roles/${role.id}/edit`)
}

const buildPayload = () => {
  const normalized = expandRoleCompactToPerson(roleProfile.value, roleSceneBehaviorMode.value)
  return {
    ...normalized,
    name: String(normalized.name || '').trim(),
    case_id: form.scope === 'case' ? form.case_id : null,
    scene_ids: form.scope === 'case' ? form.scene_ids : [],
    primary_scene_id: form.scope === 'case' ? form.primary_scene_id : null,
  }
}

const saveRole = async () => {
  if (!String(roleProfile.value?.name || '').trim()) {
    showToast('请输入角色名称')
    return
  }
  if (form.scope === 'case' && !form.case_id) {
    showToast('案件人物必须先选择所属案件')
    return
  }
  if (form.scope === 'case' && !form.scene_ids.length) {
    showToast('案件人物至少分配一个场景')
    return
  }
  if (form.scope === 'case' && form.primary_scene_id && !form.scene_ids.includes(form.primary_scene_id)) {
    showToast('主对话场景必须包含在已分配场景中')
    return
  }

  saving.value = true
  try {
    const payload = buildPayload()
    if (form.id) {
      await request.put(`/cases/roles/${form.id}`, payload, { _skipErrorToast: true } as any)
      showToast({ type: 'success', message: '角色已更新' })
    } else {
      await request.post('/cases/roles', payload, { _skipErrorToast: true } as any)
      showToast({ type: 'success', message: '角色已创建' })
    }
    closeDetail()
    await fetchRoles()
  } catch (error) {
    console.error('Save role error:', error)
    showToast('角色保存失败')
  } finally {
    saving.value = false
  }
}

const deleteRole = async () => {
  if (!form.id || deleting.value) return
  try {
    await showConfirmDialog({
      title: '确认删除',
      message:
        form.scope === 'case'
          ? '删除案件人物后，学员端将不再在对应场景中看到该人物。确定继续吗？'
          : '删除公共角色模板后，不会影响已存在案件，但模板本身将被移除。确定继续吗？',
    })
    deleting.value = true
    await request.delete(`/cases/roles/${form.id}`, { _skipErrorToast: true } as any)
    showToast({ type: 'success', message: '角色已删除' })
    closeDetail()
    await fetchRoles()
  } catch (error) {
    if (error) {
      console.error('Delete role error:', error)
      showToast('角色删除失败')
    }
  } finally {
    deleting.value = false
  }
}

onMounted(refreshPage)
</script>

<template>
  <div class="roles-page">
    <div class="admin-list-header">
      <div>
        <h2>AI训练角色仓库</h2>
        <p>
          公共模板用于沉淀可复用人物；案件人物会同步进入案件并按你分配的场景出现在学员端。现在两类角色统一使用“行为原型 + 对警方态度 + 诉求 + 顾虑 + 触发点 + 安抚点”的轻量模板。
        </p>
      </div>
      <van-button type="primary" icon="plus" class="!bg-[#003087] !border-none !rounded-[6px] px-5" @click="openCreate">
        新增角色
      </van-button>
    </div>

    <div class="hero-note">
      <div class="hero-note__label">录入建议</div>
      <p class="hero-note__text">
        先判断“这个人一开口像哪种现场人物”，再补他眼下最怕什么、最想保住什么、什么会把他点燃、什么能把他稳住。
      </p>
    </div>

    <div class="role-stat-grid">
      <div class="stat-card">
        <div class="stat-card__label">总角色数</div>
        <div class="stat-card__value">{{ roleCountSummary.total }}</div>
      </div>
      <div class="stat-card stat-card--sky">
        <div class="stat-card__label">公共模板</div>
        <div class="stat-card__value">{{ roleCountSummary.publicCount }}</div>
      </div>
      <div class="stat-card stat-card--emerald">
        <div class="stat-card__label">案件人物</div>
        <div class="stat-card__value">{{ roleCountSummary.caseCount }}</div>
      </div>
    </div>

    <section class="admin-filter-panel">
      <div class="admin-filter-bar">
        <label class="admin-filter-item">
          <span>角色类型</span>
          <select v-model="roleTypeFilter">
            <option value="">全部</option>
            <option v-for="item in roleTypeFilterOptions" :key="item" :value="item">{{ item }}</option>
          </select>
        </label>
        <label class="admin-filter-item">
          <span>角色范围</span>
          <select v-model="roleScopeFilter">
            <option value="">全部</option>
            <option value="public">公共模板</option>
            <option value="case">案件人物</option>
          </select>
        </label>
        <label class="admin-filter-item">
          <span>所属案件</span>
          <select v-model="roleCaseFilter">
            <option value="">全部案件</option>
            <option v-for="item in roleCaseFilterOptions" :key="item" :value="item">{{ item }}</option>
          </select>
        </label>
      </div>
      <label class="admin-search-box">
        <van-icon name="search" />
        <input v-model.trim="roleSearchText" type="text" placeholder="搜索姓名、画像或案件" />
      </label>
      <div class="admin-filter-summary">当前筛选 {{ filteredRoles.length }} / {{ roles.length }} 个角色</div>
    </section>

    <div v-if="loading" class="flex justify-center py-20">
      <van-loading type="spinner" color="#1D3557" />
    </div>

    <div v-else-if="pageError" class="rounded-3xl border border-amber-200 bg-amber-50 px-6 py-12 text-center">
      <van-icon name="warning-o" size="32" class="text-amber-500" />
      <p class="mt-4 text-base font-bold text-amber-700">{{ pageError }}</p>
      <van-button plain type="primary" class="mt-5" @click="refreshPage">重新加载</van-button>
    </div>

    <div v-else-if="roles.length === 0" class="rounded-[8px] border border-dashed border-slate-200 bg-white py-20 text-center">
      <van-icon name="friends-o" size="60" class="mb-4 text-slate-200" />
      <p class="text-base font-bold text-slate-500">暂无角色数据</p>
      <van-button type="primary" round class="!bg-[#1D3557] !border-none mt-6" @click="openCreate">
        新增第一个角色
      </van-button>
    </div>

    <div v-else-if="filteredRoles.length" class="role-groups">
      <div v-for="(group, caseTitle) in groupedRoles" :key="caseTitle" class="role-group">
        <div class="role-group__head">
          <h3>{{ caseTitle }}</h3>
          <span>共 {{ group.length }} 个角色</span>
        </div>

        <div class="role-list">
          <div
            v-for="role in group"
            :key="role.id"
            class="role-card group"
            @click="openDetail(role)"
          >
            <div class="flex items-start justify-between gap-3">
              <div class="flex items-center gap-3">
                <div class="role-card__avatar">
                  <van-icon name="user-o" size="22" class="text-slate-400" />
                </div>
                <div>
                  <h3 class="text-base font-bold text-slate-900">{{ role.name }}</h3>
                  <div class="mt-2 flex flex-wrap gap-2">
                    <span class="role-pill role-pill--slate">{{ role.role_type || '相关人员' }}</span>
                    <span class="role-pill role-pill--sky">人物线 {{ Array.isArray(role.role_memories) ? role.role_memories.length : 0 }} 条</span>
                    <span class="role-pill" :class="role.is_public ? 'role-pill--sky' : 'role-pill--emerald'">
                      {{ role.is_public ? '公共模板' : '案件人物' }}
                    </span>
                  </div>
                </div>
              </div>
              <van-icon name="setting-o" class="text-slate-300 transition-colors group-hover:text-[#1D3557]" />
            </div>

            <div class="role-card__summary">
              <div class="role-card__eyebrow">来源人物线摘要</div>
              <p class="role-card__summary-text line-clamp-3">{{ buildRoleOverview(role) }}</p>
            </div>

            <div class="role-chip-list">
              <span v-for="chip in getRoleSummaryChips(role)" :key="chip" class="role-chip">{{ chip }}</span>
              <span v-if="!getRoleSummaryChips(role).length" class="role-chip role-chip--muted">待补充核心画像</span>
            </div>

            <div class="grid grid-cols-2 gap-4">
              <div class="space-y-1">
                <div class="flex items-center justify-between text-[10px] font-bold uppercase tracking-wider text-slate-400">
                  <span>情绪强度</span>
                  <span class="text-orange-500">{{ role.init_emotion }}%</span>
                </div>
                <div class="h-1 overflow-hidden rounded-full bg-slate-100">
                  <div class="h-full bg-orange-400" :style="{ width: `${role.init_emotion}%` }"></div>
                </div>
              </div>
              <div class="space-y-1">
                <div class="flex items-center justify-between text-[10px] font-bold uppercase tracking-wider text-slate-400">
                  <span>配合程度</span>
                  <span class="text-blue-500">{{ role.init_trust }}%</span>
                </div>
                <div class="h-1 overflow-hidden rounded-full bg-slate-100">
                  <div class="h-full bg-blue-500" :style="{ width: `${role.init_trust}%` }"></div>
                </div>
              </div>
            </div>

            <div class="role-card__footer">
              <span>{{ role.status || '正常' }}</span>
              <span v-if="!role.is_public">已分配 {{ role.scene_ids?.length || 0 }} 个场景</span>
              <span v-else>公共模板</span>
            </div>
          </div>
        </div>
      </div>
    </div>

    <div v-else class="rounded-[8px] border border-dashed border-slate-200 bg-white py-20 text-center text-slate-400">
      暂无符合筛选条件的角色
    </div>

  </div>
</template>

<style scoped>
.roles-page {
  display: flex;
  flex-direction: column;
  gap: 16px;
  padding-bottom: 32px;
}

.line-clamp-3 {
  display: -webkit-box;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.hero-note {
  border: 1px solid #dbeafe;
  border-radius: 8px;
  background: #f2f8ff;
  padding: 12px 14px;
}

.admin-list-header,
.admin-filter-panel {
  border: 1px solid var(--police-border);
  border-radius: 8px;
  background: #fff;
}

.admin-list-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 16px 18px;
}

.admin-list-header h2 {
  margin: 0;
  color: var(--police-text-primary);
  font-size: 20px;
  font-weight: 800;
}

.admin-list-header p {
  max-width: 960px;
  margin: 4px 0 0;
  color: var(--police-text-muted);
  font-size: 13px;
  line-height: 1.7;
}

.admin-filter-panel {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 14px;
  padding: 14px 16px;
}

.admin-filter-bar {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}

.admin-filter-item {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  color: var(--police-text-secondary);
  font-size: 13px;
}

.admin-filter-item select {
  min-width: 132px;
  height: 36px;
  border: 1px solid var(--police-border);
  border-radius: 6px;
  background: #fff;
  padding: 0 10px;
  color: var(--police-text-primary);
}

.admin-search-box {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  width: min(320px, 100%);
  height: 36px;
  border: 1px solid var(--police-border);
  border-radius: 6px;
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
}

.hero-note__label {
  font-size: 12px;
  font-weight: 900;
  letter-spacing: 0;
  text-transform: none;
  color: #2563eb;
}

.hero-note__text {
  margin-top: 8px;
  max-width: 920px;
  font-size: 13px;
  line-height: 1.7;
  color: #475569;
}

.role-stat-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 14px;
}

.stat-card {
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  background: #fff;
  padding: 18px 20px;
}

.stat-card--sky {
  background: #f8fbff;
  border-color: #dbeafe;
}

.stat-card--emerald {
  background: #f0fdf4;
  border-color: #bbf7d0;
}

.stat-card__label {
  font-size: 12px;
  font-weight: 900;
  letter-spacing: 0;
  text-transform: none;
  color: #94a3b8;
}

.stat-card__value {
  margin-top: 10px;
  font-size: 28px;
  line-height: 1;
  font-weight: 900;
  color: #0f172a;
}

.role-groups {
  display: flex;
  flex-direction: column;
  gap: 22px;
}

.role-group {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.role-group__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 0 2px;
}

.role-group__head h3 {
  margin: 0;
  color: #0f172a;
  font-size: 15px;
  font-weight: 900;
}

.role-group__head span {
  color: #475569;
  font-size: 13px;
  font-weight: 700;
}

.role-list {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 14px;
}

.role-card {
  display: flex;
  min-height: 184px;
  flex-direction: column;
  gap: 10px;
  cursor: pointer;
  border: 1px solid var(--police-border);
  border-radius: 8px;
  background: #fff;
  padding: 14px 16px;
  box-shadow: 0 6px 18px rgba(15, 23, 42, 0.04);
  transition: border-color 0.2s ease, box-shadow 0.2s ease, transform 0.2s ease;
}

.role-card:hover {
  transform: translateY(-1px);
  border-color: #bfdbfe;
  box-shadow: 0 12px 24px rgba(15, 23, 42, 0.08);
  background: #fff;
}

.role-card__avatar {
  display: flex;
  width: 42px;
  height: 42px;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  border-radius: 999px;
  border: 1px solid #e2e8f0;
  background: #f8fafc;
}

.role-pill {
  display: inline-flex;
  align-items: center;
  border-radius: 999px;
  padding: 3px 8px;
  font-size: 10px;
  font-weight: 800;
}

.role-pill--slate {
  background: #e2e8f0;
  color: #334155;
}

.role-pill--sky {
  background: #dbeafe;
  color: #1d4ed8;
}

.role-pill--emerald {
  background: #d1fae5;
  color: #047857;
}

.role-card__summary {
  min-height: 44px;
  border: none;
  border-radius: 0;
  background: transparent;
  padding: 0;
}

.role-card__eyebrow {
  font-size: 10px;
  font-weight: 900;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  color: #94a3b8;
}

.role-card__summary-text {
  margin-top: 4px;
  font-size: 12px;
  line-height: 1.55;
  color: #334155;
}

.role-chip-list {
  display: flex;
  flex-wrap: wrap;
  min-height: 28px;
  gap: 6px;
}

.role-chip {
  display: inline-flex;
  align-items: center;
  border-radius: 999px;
  background: #eff6ff;
  color: #1d4ed8;
  padding: 4px 8px;
  font-size: 10px;
  font-weight: 700;
}

.role-chip--muted {
  background: #f1f5f9;
  color: #64748b;
}

.role-card__footer {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  margin-top: auto;
  border-radius: 0;
  background: transparent;
  padding: 0;
  font-size: 12px;
  font-weight: 700;
  color: #64748b;
}

.section-card {
  border: 1px solid #e2e8f0;
  border-radius: 26px;
  background: linear-gradient(180deg, #ffffff 0%, #f8fafc 100%);
  padding: 18px;
}

.section-card--sky {
  background: linear-gradient(180deg, #f8fbff 0%, #eff6ff 100%);
  border-color: #dbeafe;
}

.section-card--indigo {
  background: linear-gradient(180deg, #eef2ff 0%, #f8fafc 100%);
  border-color: #c7d2fe;
}

.section-card--amber {
  background: linear-gradient(180deg, #fffaf0 0%, #fffbeb 100%);
  border-color: #fde68a;
}

.section-card--emerald {
  background: linear-gradient(180deg, #f0fdf4 0%, #f8fafc 100%);
  border-color: #bbf7d0;
}

.section-card__header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 16px;
}

.section-card__eyebrow {
  font-size: 11px;
  font-weight: 900;
  letter-spacing: 0.16em;
  text-transform: uppercase;
  color: #64748b;
}

.section-card__title {
  margin-top: 4px;
  font-size: 20px;
  line-height: 1.25;
  font-weight: 900;
  color: #0f172a;
}

.section-card__hint {
  max-width: 260px;
  border-radius: 18px;
  background: rgba(255, 255, 255, 0.78);
  padding: 10px 12px;
  font-size: 12px;
  line-height: 1.6;
  color: #64748b;
}

.section-card__tip {
  margin-top: 12px;
  font-size: 12px;
  line-height: 1.7;
  color: #64748b;
}

.scope-card {
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding: 16px;
  border-radius: 18px;
  border: 1px solid #e2e8f0;
  background: rgba(255, 255, 255, 0.84);
  text-align: left;
  transition: all 0.2s ease;
}

.scope-card.active {
  border-color: #1d3557;
  background: #f4f8fd;
  box-shadow: 0 12px 30px rgba(29, 53, 87, 0.08);
}

.scope-card.disabled {
  cursor: not-allowed;
  opacity: 0.7;
}

.scope-card__title {
  font-size: 14px;
  font-weight: 800;
  color: #1f2937;
}

.scope-card__desc {
  font-size: 12px;
  line-height: 1.7;
  color: #64748b;
}

.field-label {
  display: block;
  margin-bottom: 8px;
  font-size: 13px;
  font-weight: 800;
  color: #334155;
}

.form-input,
.form-textarea {
  width: 100%;
  border: 1px solid #dbe3ee;
  border-radius: 16px;
  padding: 12px 14px;
  font-size: 14px;
  color: #0f172a;
  outline: none;
  background: #fff;
  transition: border-color 0.2s ease, box-shadow 0.2s ease;
}

.form-input:focus,
.form-textarea:focus {
  border-color: #93b4d6;
  box-shadow: 0 0 0 4px rgba(69, 123, 157, 0.12);
}

.form-textarea {
  resize: vertical;
  min-height: 88px;
}

.scene-grid {
  display: grid;
  gap: 10px;
}

.scene-option {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 12px;
  border-radius: 14px;
  background: rgba(255, 255, 255, 0.86);
  border: 1px solid #dbeafe;
  font-size: 13px;
  color: #475569;
}

.empty-inline-note {
  border: 1px dashed #bfdbfe;
  border-radius: 18px;
  background: rgba(255, 255, 255, 0.74);
  padding: 14px;
  font-size: 12px;
  line-height: 1.7;
  color: #475569;
}

.slider-head {
  display: flex;
  justify-content: space-between;
  margin-bottom: 10px;
  font-size: 13px;
  font-weight: 700;
  color: #475569;
}

.preview-panel {
  display: flex;
  flex-direction: column;
  gap: 14px;
  padding: 16px;
  border-radius: 22px;
  border: 1px solid #bbf7d0;
  background:
    radial-gradient(circle at top right, rgba(34, 197, 94, 0.12), transparent 30%),
    linear-gradient(180deg, #ffffff 0%, #f6fef8 100%);
}

.preview-panel__header {
  display: flex;
  justify-content: space-between;
  gap: 12px;
}

.preview-panel__name {
  font-size: 18px;
  font-weight: 900;
  color: #0f172a;
}

.preview-panel__meta {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 8px;
  font-size: 11px;
  font-weight: 700;
  color: #365d4a;
}

.preview-panel__meta span {
  padding: 4px 8px;
  border-radius: 999px;
  background: rgba(15, 118, 110, 0.08);
}

.preview-grid {
  display: grid;
  gap: 12px;
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.preview-card,
.preview-block {
  border-radius: 18px;
  border: 1px solid #dbe5dd;
  background: rgba(255, 255, 255, 0.92);
  padding: 14px;
}

.preview-card__title,
.preview-block__label {
  margin-bottom: 10px;
  font-size: 11px;
  font-weight: 900;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: #64748b;
}

.preview-block__text {
  font-size: 14px;
  line-height: 1.8;
  color: #0f172a;
}

.preview-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.preview-tag {
  display: inline-flex;
  align-items: center;
  padding: 6px 10px;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 700;
}

.preview-tag--blue {
  background: #e0f2fe;
  color: #0369a1;
}

.preview-tag--amber {
  background: #fef3c7;
  color: #b45309;
}

.preview-tag--emerald {
  background: #dcfce7;
  color: #047857;
}

.preview-empty {
  font-size: 12px;
  color: #94a3b8;
}

.preview-quote {
  font-size: 13px;
  line-height: 1.8;
  color: #0f172a;
}

.preview-quote--muted {
  margin-top: 6px;
  color: #475569;
}

.preview-list {
  display: grid;
  gap: 8px;
  padding-left: 18px;
  font-size: 13px;
  line-height: 1.7;
  color: #334155;
}

@media (max-width: 960px) {
  .role-stat-grid,
  .role-list {
    grid-template-columns: 1fr;
  }

  .section-card__header {
    flex-direction: column;
  }

  .section-card__hint {
    max-width: none;
  }

  .preview-grid {
    grid-template-columns: 1fr;
  }
}
</style>
