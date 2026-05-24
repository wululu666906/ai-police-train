<template>
  <div class="hall-page">
    <section class="hero">
      <div class="hero-copy">
        <p class="hero-kicker">Student Training Hub</p>
        <h1 class="hero-title">训练大厅</h1>
        <p class="hero-desc">
          选择案件后即可进入模拟训练。建议优先围绕接警研判、现场问询、情绪安抚和关键风险控制开展练习。
        </p>
      </div>

      <div class="hero-search">
        <van-field
          v-model="searchText"
          placeholder="搜索案件名称、类型或背景关键词"
          left-icon="search"
          clearable
          class="search-input"
          @update:model-value="filterCases"
        />
      </div>
    </section>

    <section class="overview-grid">
      <div class="overview-card">
        <span class="overview-label">案件总数</span>
        <strong class="overview-value">{{ cases.length }}</strong>
      </div>
      <div class="overview-card">
        <span class="overview-label">可继续训练</span>
        <strong class="overview-value">{{ recentActiveScenes.length }}</strong>
      </div>
      <div class="overview-card">
        <span class="overview-label">当前筛选结果</span>
        <strong class="overview-value">{{ filteredCases.length }}</strong>
      </div>
    </section>

    <section class="filter-panel">
      <div class="filter-group">
        <span class="filter-label">案件类型</span>
        <div class="filter-tags">
          <button type="button" class="filter-tag" :class="{ active: selectedType === '' }" @click="setType('')">全部</button>
          <button
            v-for="type in caseTypes"
            :key="type"
            type="button"
            class="filter-tag"
            :class="{ active: selectedType === type }"
            @click="setType(type)"
          >
            {{ type }}
          </button>
        </div>
      </div>

      <div class="filter-group">
        <span class="filter-label">难度</span>
        <div class="filter-tags">
          <button type="button" class="filter-tag" :class="{ active: selectedDifficulty === '' }" @click="setDifficulty('')">全部</button>
          <button
            v-for="difficulty in difficulties"
            :key="difficulty"
            type="button"
            class="filter-tag"
            :class="{ active: selectedDifficulty === difficulty }"
            @click="setDifficulty(difficulty)"
          >
            {{ difficulty }}
          </button>
        </div>
      </div>
    </section>

    <section v-if="recentActiveScenes.length" class="resume-panel">
      <div class="resume-header">
        <div>
          <h2>继续未完成训练</h2>
          <p>以下场景已存在进行中的训练会话，可以直接返回现场继续。</p>
        </div>
        <div class="resume-header-actions">
          <van-tag type="primary" plain size="medium">共 {{ recentActiveScenes.length }} 项</van-tag>
          <van-button
            size="small"
            type="danger"
            plain
            :loading="deletingAllSessions"
            :disabled="deletingAllSessions || deletingSessionId !== null || loadingSceneId !== null"
            @click="deleteAllActiveSessions"
          >
            一键删除
          </van-button>
        </div>
      </div>

      <div class="resume-list">
        <div v-for="scene in visibleRecentActiveScenes" :key="scene.active_session_id || scene.id" class="resume-item">
          <div class="resume-main">
            <div class="resume-title">{{ scene.case_title }}</div>
            <div class="resume-meta">
              <span>{{ scene.name }}</span>
              <span>会话 #{{ scene.active_session_id }}</span>
              <span>{{ scene.difficulty || '中等' }}</span>
              <span :class="scene.active_session_is_empty ? 'meta-empty' : 'meta-active'">
                {{ scene.active_session_is_empty ? '仅创建未开聊' : '已有进行中对话' }}
              </span>
            </div>
          </div>
          <div class="resume-actions">
            <van-button
              type="primary"
              size="small"
              :loading="loadingSceneId === scene.id"
              :disabled="loadingSceneId !== null || deletingSessionId !== null || deletingAllSessions"
              @click="startTraining(scene)"
            >
              继续训练
            </van-button>
            <van-button
              size="small"
              type="danger"
              plain
              :loading="deletingSessionId === scene.active_session_id"
              :disabled="loadingSceneId !== null || deletingSessionId !== null || deletingAllSessions"
              @click="deleteActiveSession(scene)"
            >
              删除对话
            </van-button>
          </div>
        </div>
      </div>

      <div v-if="recentActiveScenes.length > 3" class="resume-footer">
        <button type="button" class="resume-toggle" @click="showAllResumes = !showAllResumes">
          {{ showAllResumes ? '收起额外会话' : `再展开 ${recentActiveScenes.length - 3} 条进行中会话` }}
        </button>
      </div>
    </section>

    <section v-if="isLoadingCases" class="loading-state">
      <van-loading color="#165dff" vertical>正在加载训练案件...</van-loading>
    </section>

    <section v-else-if="loadError" class="empty-state">
      <van-icon name="warning-o" size="48" color="#F59E0B" />
      <p>训练大厅加载失败</p>
      <span>{{ loadError }}</span>
      <van-button type="primary" size="small" class="retry-btn" @click="fetchCases">
        重新加载
      </van-button>
    </section>

    <section v-else-if="filteredCases.length" class="case-grid">
      <article v-for="caseItem in filteredCases" :key="caseItem.id" class="case-card">
        <div class="card-top">
          <van-tag :type="getTypeColor(caseItem.case_type) as any" plain size="medium">
            {{ caseItem.case_type || '未分类' }}
          </van-tag>
          <div class="card-top-right">
            <span class="case-train-count">已训练 {{ caseItem.train_count || 0 }} 次</span>
            <span class="case-status" :class="`status-${getCaseStatus(caseItem)}`">{{ getCaseStatusLabel(caseItem) }}</span>
          </div>
        </div>

        <h3 class="case-title">{{ caseItem.title || '未命名案件' }}</h3>
        <p class="case-background">
          {{ truncateText(caseItem.background, 88) || '当前案件暂无完整背景描述。' }}
        </p>

        <div class="scene-block">
          <div class="scene-block-title">训练场景</div>
          <div class="scene-list">
            <div v-for="scene in getVisibleScenes(caseItem).slice(0, 3)" :key="scene.id" class="scene-item">
              <div class="scene-main">
                <div class="scene-name">{{ scene.name }}</div>
                <div class="scene-meta">
                  <span>{{ scene.difficulty || '中等' }}</span>
                  <span :class="scene.has_active_session ? 'meta-active' : 'meta-idle'">
                    {{ scene.has_active_session ? '进行中' : '未开始' }}
                  </span>
                  <span v-if="scene.has_active_session" :class="scene.active_session_is_empty ? 'meta-empty' : 'meta-active'">
                    {{ scene.active_session_is_empty ? '仅创建未开聊' : '已有进行中对话' }}
                  </span>
                </div>
              </div>
              <div class="scene-actions">
                <van-button
                  type="primary"
                  size="small"
                  :loading="loadingSceneId === scene.id"
                  :disabled="loadingSceneId !== null"
                  @click="startTraining(scene)"
                >
                  {{ scene.has_active_session ? '继续训练' : '开始训练' }}
                </van-button>
              </div>
            </div>
          </div>

          <button
            v-if="getVisibleScenes(caseItem).length > 3"
            type="button"
            class="expand-trigger"
            @click="openExpandedDetail(caseItem)"
          >
            查看全部 {{ getVisibleScenes(caseItem).length }} 个场景
          </button>
        </div>
      </article>
    </section>

    <section v-else class="empty-state">
      <van-icon name="search" size="48" color="#C9CDD4" />
      <p>暂无符合条件的训练案件</p>
      <span>请调整筛选条件，或联系管理员补充案件。</span>
    </section>

    <van-popup
      v-model:show="showExpanded"
      round
      class="detail-popup"
      :overlay-style="{ backgroundColor: 'rgba(15, 23, 42, 0.24)', backdropFilter: 'blur(6px)' }"
    >
      <div v-if="expandedCase" class="detail-card">
        <div class="detail-header">
          <div>
            <van-tag type="primary" plain size="large">{{ expandedCase.case_type || '未分类' }}</van-tag>
            <h2>{{ expandedCase.title || '未命名案件' }}</h2>
          </div>
          <van-icon name="cross" class="detail-close" @click="showExpanded = false" />
        </div>

        <section class="detail-section">
          <div class="detail-label">案件背景</div>
          <p>{{ expandedCase.background || '暂无案件背景信息。' }}</p>
        </section>

        <section class="detail-section">
          <div class="detail-label">全部训练场景（{{ getVisibleScenes(expandedCase).length }}）</div>
          <div class="detail-scene-list">
            <div v-for="scene in getVisibleScenes(expandedCase)" :key="scene.id" class="detail-scene-item">
              <div>
                <div class="scene-name">{{ scene.name }}</div>
                <div class="scene-meta">
                  <span>{{ scene.difficulty || '中等' }}</span>
                  <span :class="scene.has_active_session ? 'meta-active' : 'meta-idle'">
                    {{ scene.has_active_session ? '进行中' : '未开始' }}
                  </span>
                  <span v-if="scene.has_active_session" :class="scene.active_session_is_empty ? 'meta-empty' : 'meta-active'">
                    {{ scene.active_session_is_empty ? '仅创建未开聊' : '已有进行中对话' }}
                  </span>
                </div>
              </div>
              <div class="scene-actions">
                <van-button
                  type="primary"
                  size="small"
                  :loading="loadingSceneId === scene.id"
                  :disabled="loadingSceneId !== null"
                  @click="startTraining(scene)"
                >
                  {{ scene.has_active_session ? '继续训练' : '开始训练' }}
                </van-button>
              </div>
            </div>
          </div>
        </section>
      </div>
    </van-popup>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { showConfirmDialog, showToast } from 'vant'
import request from '../utils/request'

type SceneItem = {
  id: number
  name: string
  difficulty?: string
  has_active_session?: boolean
  active_session_id?: number | null
  active_session_is_empty?: boolean
}

type CaseItem = {
  id: number
  title: string
  case_type: string
  background: string
  train_count?: number
  scenes?: SceneItem[]
}

const router = useRouter()

const cases = ref<CaseItem[]>([])
const filteredCases = ref<CaseItem[]>([])
const caseTypes = ref<string[]>([])
const difficulties = ['低', '中等', '高']
const searchText = ref('')
const selectedType = ref('')
const selectedDifficulty = ref('')
const isLoadingCases = ref(false)
const loadError = ref('')
const showAllResumes = ref(false)
const loadingSceneId = ref<number | null>(null)
const deletingSessionId = ref<number | null>(null)
const deletingAllSessions = ref(false)
const showExpanded = ref(false)
const expandedCase = ref<CaseItem | null>(null)

const recentActiveScenes = computed(() =>
  cases.value
    .flatMap((caseItem) =>
      (caseItem.scenes || [])
        .filter((scene) => scene.has_active_session)
        .map((scene) => ({
          ...scene,
          case_id: caseItem.id,
          case_title: caseItem.title,
          case_type: caseItem.case_type,
        }))
    )
    .sort((a, b) => (b.active_session_id || 0) - (a.active_session_id || 0))
)

const visibleRecentActiveScenes = computed(() =>
  showAllResumes.value ? recentActiveScenes.value : recentActiveScenes.value.slice(0, 3)
)

const truncateText = (value: string, maxLength: number) => {
  const text = String(value || '').trim()
  if (!text) return ''
  return text.length > maxLength ? `${text.slice(0, maxLength)}...` : text
}

const normalizeDifficulty = (value: string) => {
  const text = String(value || '').trim()
  if (['简单', '低'].includes(text)) return '低'
  if (['困难', '高'].includes(text)) return '高'
  return text || '中等'
}

const openExpandedDetail = (caseItem: CaseItem) => {
  expandedCase.value = caseItem
  showExpanded.value = true
}

const setType = (type: string) => {
  selectedType.value = type
  filterCases()
}

const setDifficulty = (difficulty: string) => {
  selectedDifficulty.value = difficulty
  filterCases()
}

const getVisibleScenes = (caseItem: CaseItem) => {
  const scenes = Array.isArray(caseItem?.scenes) ? caseItem.scenes : []
  if (!selectedDifficulty.value) return scenes
  return scenes.filter((scene) => normalizeDifficulty(scene.difficulty || '') === selectedDifficulty.value)
}

const getCaseStatus = (caseItem: CaseItem) => {
  const scenes = Array.isArray(caseItem?.scenes) ? caseItem.scenes : []
  if (scenes.some((scene) => scene.has_active_session)) return 'active'
  return 'idle'
}

const getCaseStatusLabel = (caseItem: CaseItem) => (getCaseStatus(caseItem) === 'active' ? '进行中' : '未开始')

const fetchCases = async () => {
  isLoadingCases.value = true
  loadError.value = ''
  try {
    const [casesRes, typesRes]: any = await Promise.all([
      request.get('/student/cases', { _skipErrorToast: true } as any),
      request.get('/student/case-types', { _skipErrorToast: true } as any),
    ])
    cases.value = Array.isArray(casesRes) ? casesRes : []
    caseTypes.value = Array.isArray(typesRes) ? typesRes : []
    if (recentActiveScenes.value.length <= 3) {
      showAllResumes.value = false
    }
    filterCases()
  } catch (error: any) {
    loadError.value = error?.response?.data?.detail || '当前无法加载训练案件，请稍后重试。'
    cases.value = []
    filteredCases.value = []
    caseTypes.value = []
  } finally {
    isLoadingCases.value = false
  }
}

const filterCases = () => {
  let result = [...cases.value]
  const keyword = searchText.value.trim()

  if (keyword) {
    result = result.filter((caseItem) => {
      const haystack = [caseItem.title, caseItem.case_type, caseItem.background].join(' ')
      return haystack.includes(keyword)
    })
  }

  if (selectedType.value) {
    result = result.filter((caseItem) => caseItem.case_type === selectedType.value)
  }

  if (selectedDifficulty.value) {
    result = result.filter((caseItem) => getVisibleScenes(caseItem).length > 0)
  }

  filteredCases.value = result
}

const startTraining = async (scene: SceneItem) => {
  const sceneId = Number(scene?.id)
  if (!sceneId) {
    showToast('无效的场景编号')
    return
  }
  if (loadingSceneId.value !== null) return

  loadingSceneId.value = sceneId
  try {
    const res: any = await request.post(`/training/start/${sceneId}`, null, { _skipErrorToast: true } as any)
    if (!res?.id) {
      throw new Error('服务端未返回训练会话编号')
    }

    if (scene?.has_active_session && scene?.active_session_id === res.id) {
      showToast('已恢复你上次未完成的训练')
    }
    router.push(`/student/training/${res.id}`)
  } catch (error: any) {
    const errorMsg = error?.response?.data?.detail || error?.message || '训练环境初始化失败'
    showToast(errorMsg)
  } finally {
    loadingSceneId.value = null
  }
}

const deleteActiveSession = async (scene: SceneItem & { case_title?: string }) => {
  const sessionId = Number(scene?.active_session_id)
  if (!sessionId || deletingSessionId.value !== null || loadingSceneId.value !== null || deletingAllSessions.value) return

  try {
    await showConfirmDialog({
      title: '删除历史对话',
      message: `删除后，会话 #${sessionId} 的历史对话将无法恢复。删除后可从“${scene.name || '当前场景'}”重新开始训练。`,
      confirmButtonColor: '#dc2626',
    })
  } catch {
    return
  }

  deletingSessionId.value = sessionId
  try {
    await request.delete(`/training/session/${sessionId}`, { _skipErrorToast: true } as any)
    showToast({ type: 'success', message: '历史对话已删除，可重新开始训练' })
    await fetchCases()
  } catch (error: any) {
    const errorMsg = error?.response?.data?.detail || '删除历史对话失败'
    showToast(errorMsg)
  } finally {
    deletingSessionId.value = null
  }
}

const deleteAllActiveSessions = async () => {
  if (!recentActiveScenes.value.length || deletingAllSessions.value || deletingSessionId.value !== null || loadingSceneId.value !== null) return

  try {
    await showConfirmDialog({
      title: '一键删除历史对话',
      message: `将删除上方 ${recentActiveScenes.value.length} 条进行中的历史对话，删除后不可恢复，但下方训练场景卡片会保留。是否继续？`,
      confirmButtonColor: '#dc2626',
    })
  } catch {
    return
  }

  deletingAllSessions.value = true
  try {
    const res: any = await request.delete('/training/sessions/active', { _skipErrorToast: true } as any)
    const deletedCount = Number(res?.deleted_count || 0)
    showToast({ type: 'success', message: deletedCount > 0 ? `已删除 ${deletedCount} 条历史对话` : '当前没有可删除的历史对话' })
    await fetchCases()
  } catch (error: any) {
    const errorMsg = error?.response?.data?.detail || '一键删除历史对话失败'
    showToast(errorMsg)
  } finally {
    deletingAllSessions.value = false
  }
}

const getTypeColor = (type: string) => {
  const map: Record<string, string> = {
    邻里纠纷: 'primary',
    打架斗殴: 'danger',
    酒驾醉驾: 'warning',
    盗窃: 'success',
    故意杀人: 'danger',
  }
  return map[type] || 'primary'
}

onMounted(fetchCases)
</script>

<style scoped>
.hall-page {
  max-width: 1240px;
  margin: 0 auto;
  padding: 28px 24px 40px;
}

.hero {
  display: flex;
  justify-content: space-between;
  gap: 20px;
  align-items: end;
  margin-bottom: 18px;
}

.hero-kicker {
  margin: 0 0 6px;
  color: #165dff;
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.12em;
  text-transform: uppercase;
}

.hero-title {
  margin: 0;
  font-size: 34px;
  font-weight: 800;
  color: #102a43;
}

.hero-desc {
  margin: 10px 0 0;
  max-width: 680px;
  color: #52606d;
  line-height: 1.75;
}

.hero-search {
  width: 360px;
  max-width: 100%;
}

.search-input {
  border-radius: 18px;
  overflow: hidden;
  border: 1px solid #d9e2ec;
  background: rgba(255, 255, 255, 0.92);
}

.overview-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 14px;
  margin-bottom: 18px;
}

.overview-card {
  padding: 18px 20px;
  border-radius: 20px;
  background: rgba(255, 255, 255, 0.92);
  border: 1px solid #e6edf5;
  box-shadow: 0 10px 30px rgba(15, 23, 42, 0.05);
}

.overview-label {
  display: block;
  color: #6b7c93;
  font-size: 13px;
}

.overview-value {
  display: block;
  margin-top: 8px;
  color: #12344d;
  font-size: 28px;
  font-weight: 800;
}

.filter-panel {
  display: grid;
  gap: 16px;
  padding: 18px 20px;
  border-radius: 20px;
  background: #fff;
  border: 1px solid #e6edf5;
  box-shadow: 0 12px 32px rgba(15, 23, 42, 0.04);
}

.filter-group {
  display: flex;
  gap: 12px;
  align-items: flex-start;
}

.filter-label {
  min-width: 72px;
  padding-top: 7px;
  font-size: 13px;
  font-weight: 700;
  color: #334e68;
}

.filter-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.filter-tag {
  border: 1px solid #d9e2ec;
  background: #f8fbff;
  color: #486581;
  border-radius: 999px;
  padding: 7px 14px;
  font-size: 13px;
  cursor: pointer;
  transition: 0.2s ease;
}

.filter-tag.active {
  background: #165dff;
  border-color: #165dff;
  color: #fff;
}

.resume-panel {
  margin-top: 20px;
  border-radius: 22px;
  padding: 20px;
  background: linear-gradient(135deg, #eff6ff 0%, #f8fbff 100%);
  border: 1px solid #dbeafe;
}

.resume-header {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  align-items: flex-start;
  margin-bottom: 16px;
}

.resume-header-actions {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
  justify-content: flex-end;
}

.resume-header h2 {
  margin: 0;
  font-size: 20px;
  color: #12344d;
}

.resume-header p {
  margin: 8px 0 0;
  color: #5b7083;
  font-size: 13px;
}

.resume-list,
.scene-list,
.detail-scene-list {
  display: grid;
  gap: 12px;
}

.resume-footer {
  margin-top: 14px;
  display: flex;
  justify-content: center;
}

.resume-toggle {
  border: none;
  background: transparent;
  color: #165dff;
  font-size: 13px;
  font-weight: 700;
  cursor: pointer;
}

.resume-item,
.scene-item,
.detail-scene-item {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  align-items: center;
  border-radius: 16px;
  background: rgba(255, 255, 255, 0.95);
  border: 1px solid #e6edf5;
  padding: 14px 16px;
}

.resume-main,
.scene-main {
  min-width: 0;
  flex: 1;
}

.resume-actions,
.scene-actions {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  justify-content: flex-end;
}

.resume-title,
.case-title,
.scene-name {
  font-weight: 700;
  color: #102a43;
}

.resume-meta,
.scene-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  margin-top: 6px;
  font-size: 12px;
  color: #7b8794;
}

.meta-active {
  color: #165dff;
}

.meta-idle {
  color: #7b8794;
}

.meta-empty {
  color: #c2410c;
}

.case-grid {
  margin-top: 20px;
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
  gap: 20px;
}

.case-card {
  display: flex;
  flex-direction: column;
  gap: 16px;
  min-height: 340px;
  padding: 20px;
  border-radius: 22px;
  background: #fff;
  border: 1px solid #e6edf5;
  box-shadow: 0 10px 30px rgba(15, 23, 42, 0.05);
}

.card-top {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  align-items: center;
}

.card-top-right {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  justify-content: flex-end;
  align-items: center;
}

.case-train-count {
  color: #7b8794;
  font-size: 12px;
}

.case-status {
  padding: 4px 10px;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 700;
}

.status-active {
  color: #165dff;
  background: #eaf2ff;
}

.status-idle {
  color: #7b8794;
  background: #f1f5f9;
}

.case-background {
  margin: 0;
  color: #52606d;
  line-height: 1.75;
  min-height: 76px;
}

.scene-block {
  margin-top: auto;
}

.scene-block-title,
.detail-label {
  margin-bottom: 12px;
  font-size: 13px;
  font-weight: 700;
  color: #486581;
}

.expand-trigger {
  width: 100%;
  margin-top: 12px;
  border: 1px dashed #bfd5ff;
  background: #f8fbff;
  color: #165dff;
  border-radius: 14px;
  padding: 10px 12px;
  cursor: pointer;
}

.empty-state {
  margin-top: 20px;
  border-radius: 22px;
  background: #fff;
  border: 1px dashed #d9e2ec;
  padding: 64px 20px;
  text-align: center;
  color: #7b8794;
}

.loading-state {
  margin-top: 20px;
  border-radius: 22px;
  background: #fff;
  border: 1px solid #e6edf5;
  padding: 64px 20px;
  text-align: center;
}

.empty-state p {
  margin: 16px 0 8px;
  font-size: 18px;
  color: #334e68;
}

.retry-btn {
  margin-top: 16px;
  background: #165dff !important;
  border: none !important;
}

.detail-popup {
  width: min(820px, calc(100vw - 24px));
  max-height: calc(100vh - 32px);
  overflow: auto;
  background: transparent;
}

.detail-card {
  border-radius: 28px;
  background: #fff;
  padding: 24px;
}

.detail-header {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  align-items: flex-start;
}

.detail-header h2 {
  margin: 12px 0 0;
  color: #102a43;
}

.detail-close {
  font-size: 22px;
  color: #7b8794;
  cursor: pointer;
}

.detail-section + .detail-section {
  margin-top: 20px;
}

.detail-section p {
  margin: 0;
  color: #52606d;
  line-height: 1.8;
}

@media (max-width: 900px) {
  .overview-grid {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 768px) {
  .hall-page {
    padding: 18px 14px 28px;
  }

  .hero,
  .resume-header,
  .filter-group,
  .resume-item,
  .scene-item,
  .detail-scene-item,
  .card-top {
    flex-direction: column;
    align-items: stretch;
  }

  .hero-search {
    width: 100%;
  }

  .filter-label {
    min-width: 0;
    padding-top: 0;
  }
}
</style>
