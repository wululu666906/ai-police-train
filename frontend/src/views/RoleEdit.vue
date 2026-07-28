<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { showConfirmDialog, showToast } from 'vant'
import RoleCompactForm from '../components/RoleCompactForm.vue'
import { expandRoleCompactToPerson } from '../utils/roleCompact'
import request from '../utils/request'

const route  = useRoute()
const router = useRouter()

const isNew = computed(() => route.params.id === undefined || route.path.endsWith('/new'))

const loadingRole   = ref(false)
const loadError     = ref('')
const saving        = ref(false)
const deleting      = ref(false)
const roleOptions   = ref<any[]>([])
const syncingCaseSelection = ref(false)

const form = reactive({
  id: null as number | null,
  scope: 'public' as 'public' | 'case',
  case_id: null as number | null,
  scene_ids: [] as number[],
  primary_scene_id: null as number | null,
})

const roleProfile = ref<Record<string, any>>({})

// ── watchers ───────────────────────────────────────────────
watch(
  () => form.case_id,
  () => {
    if (syncingCaseSelection.value) return
    form.scene_ids = []
    form.primary_scene_id = null
  },
  { flush: 'sync' }
)

// ── computed ───────────────────────────────────────────────
const currentCaseScenes = computed(() => {
  const currentCase = roleOptions.value.find((item) => item.id === form.case_id)
  return currentCase?.scenes || []
})

const currentPrimaryScene = computed(() => {
  const preferredId = form.primary_scene_id || form.scene_ids[0]
  return currentCaseScenes.value.find((item: any) => item.id === preferredId) || null
})

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
  return {
    normalized,
    memories,
    boundaryGroups: [
      { key: 'unresolved', label: '待核实 / 无法确认', items: Array.isArray(normalized.unresolved_claims) ? normalized.unresolved_claims.slice(0, 4) : [] },
      { key: 'constraints', label: '回答边界', items: Array.isArray(normalized.response_constraints) ? normalized.response_constraints.slice(0, 4) : [] },
    ],
    summaryText: memories.length ? `已整理 ${memories.length} 条来源人物线，运行时只依据这些证言与公开信息作答。` : '当前还没有可回溯的人物线。',
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

// ── actions ────────────────────────────────────────────────
const goBack = () => router.push('/admin/roles')

const fetchRoleOptions = async () => {
  try {
    const res: any = await request.get('/cases/role-case-options', { _skipErrorToast: true } as any)
    roleOptions.value = Array.isArray(res) ? res : []
  } catch {}
}

const loadRole = async () => {
  if (isNew.value) {
    roleProfile.value = expandRoleCompactToPerson({}, '核查取证型')
    return
  }
  loadingRole.value = true
  loadError.value = ''
  try {
    const res: any = await request.get(`/cases/roles/${route.params.id}`, { _skipErrorToast: true } as any)
    if (!res) { loadError.value = '角色不存在'; return }
    syncingCaseSelection.value = true
    form.id = res.id
    form.scope = res.is_public ? 'public' : 'case'
    form.case_id = res.case_id ?? null
    form.scene_ids = Array.isArray(res.scene_ids) ? [...res.scene_ids] : []
    form.primary_scene_id = res.primary_scene_id ?? null
    roleProfile.value = { ...expandRoleCompactToPerson(res, '') }
    syncingCaseSelection.value = false
  } catch {
    loadError.value = '角色加载失败，请重试'
    showToast('加载失败')
  } finally {
    loadingRole.value = false
  }
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
    router.push('/admin/roles')
  } catch {
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
      message: form.scope === 'case'
        ? '删除案件人物后，学员端将不再在对应场景中看到该人物。确定继续吗？'
        : '删除公共角色模板后，不会影响已存在案件，但模板本身将被移除。确定继续吗？',
    })
    deleting.value = true
    await request.delete(`/cases/roles/${form.id}`, { _skipErrorToast: true } as any)
    showToast({ type: 'success', message: '角色已删除' })
    router.push('/admin/roles')
  } catch (error) {
    if (error) showToast('角色删除失败')
  } finally {
    deleting.value = false
  }
}

onMounted(async () => {
  await fetchRoleOptions()
  await loadRole()
})
</script>

<template>
  <div class="re-page">

    <!-- 顶部导航 -->
    <div class="re-topbar">
      <button class="re-back-btn" @click="goBack">
        <van-icon name="arrow-left" />
        <span>AI 角色库</span>
      </button>
      <div class="re-topbar__center">
        <span class="re-topbar__title">
          {{ isNew ? '新增角色' : (roleProfile.name || '编辑角色') }}
        </span>
      </div>
      <div class="re-topbar__actions">
        <van-button
          v-if="!isNew && form.id"
          plain
          type="danger"
          size="small"
          class="!rounded-[8px]"
          :loading="deleting"
          @click="deleteRole"
        >
          删除角色
        </van-button>
        <van-button
          type="primary"
          size="small"
          class="!bg-[#1D3557] !border-none !rounded-[8px]"
          :loading="saving"
          :disabled="loadingRole"
          @click="saveRole"
        >
          保存
        </van-button>
      </div>
    </div>

    <!-- 加载中 -->
    <div v-if="loadingRole" class="re-loading">
      <van-loading color="#1D3557" vertical>加载中...</van-loading>
    </div>
    <div v-else-if="loadError" class="re-error">
      <p>{{ loadError }}</p>
      <van-button plain @click="goBack">返回列表</van-button>
    </div>

    <!-- 主内容 -->
    <div v-else class="re-body">

      <!-- 左栏：表单 -->
      <div class="re-main">

        <!-- 角色范围 -->
        <section class="re-card">
          <div class="re-card__header">
            <span class="re-card__step">01</span>
            <div>
              <div class="re-card__title">角色范围</div>
              <div class="re-card__sub">选择公共模板或绑定到具体案件</div>
            </div>
          </div>
          <div class="re-card__body">
            <div class="re-scope-grid">
              <button
                type="button"
                class="re-scope-btn"
                :class="{ 'is-active': form.scope === 'public', 'is-disabled': Boolean(form.id) }"
                :disabled="Boolean(form.id)"
                @click="form.scope = 'public'"
              >
                <span class="re-scope-btn__icon">🌐</span>
                <span class="re-scope-btn__label">公共模板</span>
                <span class="re-scope-btn__desc">可在所有案件中复用</span>
              </button>
              <button
                type="button"
                class="re-scope-btn"
                :class="{ 'is-active': form.scope === 'case', 'is-disabled': Boolean(form.id) }"
                :disabled="Boolean(form.id)"
                @click="form.scope = 'case'"
              >
                <span class="re-scope-btn__icon">📁</span>
                <span class="re-scope-btn__label">案件人物</span>
                <span class="re-scope-btn__desc">绑定到特定案件场景</span>
              </button>
            </div>
            <p v-if="form.id" class="re-tip">编辑已有角色时，范围保持不变；如需迁移范围，建议新建后删除旧角色。</p>
          </div>
        </section>

        <!-- 案件场景绑定 -->
        <section v-if="form.scope === 'case'" class="re-card re-card--sky">
          <div class="re-card__header">
            <span class="re-card__step">02</span>
            <div>
              <div class="re-card__title">案件与场景绑定</div>
              <div class="re-card__sub">选择所属案件并分配出现场景</div>
            </div>
          </div>
          <div class="re-card__body">
            <div class="re-field">
              <label class="re-label">所属案件</label>
              <select v-model="form.case_id" class="re-input">
                <option :value="null">请选择所属案件</option>
                <option v-for="item in roleOptions" :key="item.id" :value="item.id">{{ item.title }}</option>
              </select>
            </div>
            <div v-if="currentCaseScenes.length" class="re-field re-mt">
              <label class="re-label">出现场景（可多选）</label>
              <div class="re-scene-grid">
                <label v-for="scene in currentCaseScenes" :key="scene.id" class="re-scene-opt">
                  <input v-model="form.scene_ids" type="checkbox" :value="scene.id" />
                  <span>{{ scene.name }}</span>
                </label>
              </div>
            </div>
            <div v-else-if="form.case_id" class="re-empty-note">
              该案件下还没有可分配场景，请先回案件页生成或维护场景。
            </div>
            <div v-if="form.scene_ids.length" class="re-field re-mt">
              <label class="re-label">主对话场景</label>
              <select v-model="form.primary_scene_id" class="re-input">
                <option :value="null">不指定，由系统自动决策</option>
                <option
                  v-for="scene in currentCaseScenes.filter((item: any) => form.scene_ids.includes(item.id))"
                  :key="scene.id"
                  :value="scene.id"
                >{{ scene.name }}</option>
              </select>
            </div>
          </div>
        </section>

        <!-- 角色模板 -->
        <section class="re-card">
          <div class="re-card__header">
            <span class="re-card__step">{{ form.scope === 'case' ? '03' : '02' }}</span>
            <div>
              <div class="re-card__title">轻量角色模板</div>
              <div class="re-card__sub">
                {{ form.scope === 'case' && roleSceneBehaviorMode ? `场景模式：${roleSceneBehaviorMode}` : '填写来源人物线与回答边界' }}
              </div>
            </div>
          </div>
          <div class="re-card__body re-card__body--form">
            <RoleCompactForm v-model="roleProfile" :scene-behavior-mode="roleSceneBehaviorMode" />
          </div>
        </section>

      </div>

      <!-- 右栏：实时预览 -->
      <aside class="re-aside">
        <div class="re-preview-sticky">
          <div class="re-card re-card--preview">
            <div class="re-card__header">
              <span class="re-card__step re-card__step--green">AI</span>
              <div>
                <div class="re-card__title">实时预览</div>
                <div class="re-card__sub">AI 对该角色的理解</div>
              </div>
            </div>

            <div class="re-preview-body">
              <!-- 角色摘要 -->
              <div class="re-preview-head">
                <div class="re-preview-name">{{ roleProfile.name || '未命名角色' }}</div>
                <div class="re-preview-tags">
                  <span class="re-ptag">{{ roleDraftProfile.normalized.role_type || '相关人员' }}</span>
                  <span class="re-ptag re-ptag--blue">人物线 {{ roleDraftProfile.memories.length }} 条</span>
                  <span class="re-ptag">{{ previewStateLabel }}</span>
                </div>
              </div>

              <div class="re-preview-block">
                <div class="re-preview-block__label">AI 会把这个人理解为</div>
                <p class="re-preview-block__text">{{ roleDraftProfile.summaryText }}</p>
              </div>

              <div class="re-preview-block">
                <div class="re-preview-block__label">人物线首条证言</div>
                <p class="re-preview-quote">{{ roleDraftProfile.memories[0]?.statement || '（暂无证言）' }}</p>
              </div>

              <div class="re-preview-block">
                <div class="re-preview-block__label">预计突破口</div>
                <ul class="re-preview-list">
                  <li v-for="item in previewBreakthroughs" :key="item">{{ item }}</li>
                  <li v-if="!previewBreakthroughs.length">补充角色证言后自动生成可追问线索。</li>
                </ul>
              </div>

              <div v-for="field in roleDraftProfile.boundaryGroups" :key="field.key" class="re-preview-block">
                <div class="re-preview-block__label">{{ field.label }}</div>
                <ul class="re-preview-list">
                  <li v-for="item in field.items" :key="item">{{ item }}</li>
                  <li v-if="!field.items.length">暂未补充。</li>
                </ul>
              </div>
            </div>
          </div>
        </div>
      </aside>

    </div>
  </div>
</template>

<style scoped>
/* ── 页面基础 ──────────────────────────────────────────── */
.re-page {
  height: 100vh;
  overflow: hidden;
  background: #f8fafc;
  display: flex;
  flex-direction: column;
}

/* ── 顶部导航 ──────────────────────────────────────────── */
.re-topbar {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 0 24px;
  height: 56px;
  background: #fff;
  border-bottom: 1px solid #f1f5f9;
  z-index: 20;
  flex-shrink: 0;
}

.re-back-btn {
  display: flex;
  align-items: center;
  gap: 5px;
  padding: 6px 10px;
  border-radius: 8px;
  border: none;
  background: transparent;
  color: #64748b;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.14s;
  white-space: nowrap;
}

.re-back-btn:hover { background: #f1f5f9; color: #1e293b; }

.re-topbar__center { flex: 1; text-align: center; }
.re-topbar__title  { font-size: 15px; font-weight: 700; color: #0f172a; }
.re-topbar__actions { display: flex; align-items: center; gap: 8px; }

/* ── 加载 / 错误 ───────────────────────────────────────── */
.re-loading, .re-error {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 16px;
  color: #94a3b8;
  font-size: 14px;
}

/* ── 主体两栏 ──────────────────────────────────────────── */
.re-body {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  display: grid;
  grid-template-columns: 1fr 320px;
  gap: 20px;
  padding: 20px 24px;
  align-items: start;
}

.re-main  { display: flex; flex-direction: column; gap: 16px; }
.re-aside { position: sticky; top: 0; }

/* ── 卡片 ──────────────────────────────────────────────── */
.re-card {
  border: 1px solid #e2e8f0;
  border-radius: 12px;
  background: #fff;
  overflow: hidden;
}

.re-card--sky     { border-color: #bae6fd; background: #f0f9ff; }
.re-card--preview { border-color: #e2e8f0; }

.re-card__header {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 16px;
  border-bottom: 1px solid #f1f5f9;
  background: #f8fafc;
}

.re-card--sky .re-card__header {
  background: #e0f2fe;
  border-color: #bae6fd;
}

.re-card__step {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  border-radius: 8px;
  background: #1d3557;
  color: #fff;
  font-size: 11px;
  font-weight: 800;
  flex-shrink: 0;
}

.re-card__step--green { background: #16a34a; }

.re-card__title {
  font-size: 13px;
  font-weight: 700;
  color: #1e293b;
}

.re-card__sub {
  font-size: 12px;
  color: #94a3b8;
  margin-top: 2px;
}

.re-card__body {
  padding: 14px 16px;
}

.re-card__body--form { padding: 0; }

/* ── 范围选择 ──────────────────────────────────────────── */
.re-scope-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 10px;
}

.re-scope-btn {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
  padding: 14px 12px;
  border-radius: 10px;
  border: 2px solid #e2e8f0;
  background: #fff;
  cursor: pointer;
  transition: all 0.14s;
  text-align: center;
}

.re-scope-btn:hover:not(.is-disabled) {
  border-color: #1d3557;
  background: #f8fafc;
}

.re-scope-btn.is-active {
  border-color: #1d3557;
  background: #1d3557;
}

.re-scope-btn.is-disabled { opacity: 0.5; cursor: not-allowed; }

.re-scope-btn__icon  { font-size: 20px; }
.re-scope-btn__label {
  font-size: 13px;
  font-weight: 700;
  color: #1e293b;
}
.re-scope-btn.is-active .re-scope-btn__label { color: #fff; }
.re-scope-btn.is-active .re-scope-btn__desc  { color: rgba(255,255,255,.7); }
.re-scope-btn__desc {
  font-size: 11px;
  color: #94a3b8;
  line-height: 1.4;
}

/* ── 表单控件 ──────────────────────────────────────────── */
.re-field { display: flex; flex-direction: column; gap: 5px; }
.re-mt    { margin-top: 12px; }

.re-label {
  font-size: 12px;
  font-weight: 700;
  color: #64748b;
  line-height: 1;
}

.re-input {
  width: 100%;
  box-sizing: border-box;
  padding: 7px 10px;
  border: 1.5px solid #e2e8f0;
  border-radius: 8px;
  background: #fff;
  font-size: 13px;
  color: #0f172a;
  outline: none;
  font-family: inherit;
  transition: border-color 0.15s;
}

.re-input:focus { border-color: #1d3557; }

.re-scene-grid {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 4px;
}

.re-scene-opt {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 5px 10px;
  border-radius: 8px;
  border: 1.5px solid #e2e8f0;
  background: #fff;
  font-size: 13px;
  cursor: pointer;
  transition: all 0.14s;
}

.re-scene-opt:hover { border-color: #1d3557; background: #eff6ff; }

.re-empty-note {
  padding: 12px;
  border-radius: 8px;
  background: #fef9c3;
  font-size: 13px;
  color: #a16207;
  margin-top: 8px;
}

.re-tip {
  margin-top: 10px;
  font-size: 12px;
  color: #94a3b8;
  line-height: 1.6;
}

/* ── 预览区 ────────────────────────────────────────────── */
.re-preview-sticky { position: sticky; top: 0; }

.re-preview-body {
  padding: 14px 16px;
  display: flex;
  flex-direction: column;
  gap: 12px;
  max-height: calc(100vh - 120px);
  overflow-y: auto;
}

.re-preview-head { border-bottom: 1px solid #f1f5f9; padding-bottom: 12px; }
.re-preview-name { font-size: 16px; font-weight: 800; color: #0f172a; }

.re-preview-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  margin-top: 6px;
}

.re-ptag {
  display: inline-flex;
  align-items: center;
  padding: 2px 8px;
  border-radius: 999px;
  font-size: 11px;
  font-weight: 600;
  background: #f1f5f9;
  color: #475569;
}

.re-ptag--blue { background: #eff6ff; color: #1d4ed8; border: 1px solid #bfdbfe; }

.re-preview-block__label {
  font-size: 11px;
  font-weight: 700;
  color: #94a3b8;
  letter-spacing: 0.05em;
  text-transform: uppercase;
  margin-bottom: 6px;
}

.re-preview-block__text {
  font-size: 13px;
  line-height: 1.7;
  color: #334155;
}

.re-preview-quote {
  font-size: 12px;
  line-height: 1.6;
  color: #475569;
  margin: 2px 0;
}

.re-preview-quote--muted { color: #94a3b8; }

.re-preview-list {
  padding-left: 14px;
  margin: 0;
  font-size: 12px;
  line-height: 1.8;
  color: #475569;
}

/* ── 响应式 ────────────────────────────────────────────── */
@media (max-width: 900px) {
  .re-body {
    grid-template-columns: 1fr;
  }
  .re-aside {
    position: static;
  }
}
</style>
