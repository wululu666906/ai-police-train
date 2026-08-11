<template>
  <div class="student-page student-page--hall hall-page">
    <div class="hall-layout hall-layout--list">
      <div class="list-toolbar">
        <span class="list-title">{{ resultSummary }}</span>
      </div>

      <section class="card card--compact filter-card">
        <SelectFilter :data="filterData" :default-values="filterValues" @change="onFilterChange" />
      </section>

      <section class="card tasks-panel tasks-panel--list">
        <div class="tasks-toolbar">
          <el-tabs v-model="activeTaskTab" class="task-tabs">
            <el-tab-pane label="全部任务" name="all" />
            <el-tab-pane label="继续训练" name="active" />
            <el-tab-pane label="未开始" name="idle" />
            <el-tab-pane label="已完成训练" name="completed" />
          </el-tabs>
          <div class="tasks-controls">
            <el-select v-model="sortBy" size="small" class="sort-select">
              <el-option label="最新创建" value="newest" />
              <el-option label="训练次数" value="train_count" />
              <el-option label="案件名称" value="title" />
            </el-select>
            <div class="view-toggle">
              <button
                type="button"
                class="view-btn"
                :class="{ 'view-btn--active': viewMode === 'grid' }"
                @click="viewMode = 'grid'"
              >
                <el-icon><Grid /></el-icon>
              </button>
              <button
                type="button"
                class="view-btn"
                :class="{ 'view-btn--active': viewMode === 'list' }"
                @click="viewMode = 'list'"
              >
                <el-icon><List /></el-icon>
              </button>
            </div>
          </div>
        </div>

        <div v-if="isLoadingCases" class="state-panel">
          <el-skeleton :rows="6" animated />
        </div>
        <div v-else-if="loadError" class="state-panel">
          <el-empty :description="loadError">
            <el-button type="primary" @click="fetchCases">重新加载</el-button>
          </el-empty>
        </div>
        <div v-else-if="displayCases.length" class="task-grid task-grid--list-view" :class="{ 'task-grid--list': viewMode === 'list' }">
          <TrainingTaskCard
            v-for="caseItem in displayCases"
            :key="caseItem.id"
            :case-item="caseItem"
            :status="getCaseStatus(caseItem)"
            :status-label="getCaseStatusLabel(caseItem)"
            :view-mode="viewMode"
            :loading-scene-id="loadingSceneId"
            :disabled="loadingSceneId !== null"
            @start-case="openTrainingBrief"
          />
        </div>
        <div v-else class="state-panel">
          <el-empty description="暂无符合条件的训练案件" />
        </div>
      </section>
    </div>

    <TrainingBriefDialog
      v-model:show="showTrainingBrief"
      :title="activeCase?.title || '未命名案件'"
      :subtitle="activeCase?.background || '请选择一个训练场景后开始训练。'"
      hero-type="案件训练"
      :tag-label="activeCase?.case_type || '未分类'"
      tag-type="warning"
      summary-title="案件背景"
      :briefing="activeCase?.background"
      :fallback-briefing="activeCase?.background || '当前案件暂无可展示背景。'"
      :cancel-text="'取消'"
      :confirm-text="dialogConfirmText"
      :allow-mode-switch="false"
      @cancel="closeTrainingBrief"
      @confirm="confirmTrainingSelection"
    >
      <section class="scene-picker">
        <div class="scene-picker__head">
          <h3>选择训练场景</h3>
          <span>{{ activeSceneList.length }} 个场景</span>
        </div>
        <div class="scene-picker__list">
          <button
            v-for="scene in activeSceneList"
            :key="scene.id"
            type="button"
            class="scene-picker__item"
            :class="{ 'scene-picker__item--active': selectedSceneId === scene.id }"
            @click="selectedSceneId = scene.id"
          >
            <div class="scene-picker__title">
              <strong>{{ scene.name }}</strong>
              <span>{{ normalizeDifficulty(scene.difficulty || '中') }}</span>
            </div>
            <div class="scene-picker__meta">
              <span>{{ scene.estimated_minutes ? `${scene.estimated_minutes} 分钟` : '时长待定' }}</span>
              <span :class="scene.training_status === 'completed' ? 'scene-picker__meta--done' : scene.has_active_session ? 'scene-picker__meta--active' : 'scene-picker__meta--idle'">
                {{ getSceneStatusLabel(scene) }}
              </span>
            </div>
            <p>{{ scene.dispatch_brief || scene.first_impression || scene.description || '暂无结构化场景说明' }}</p>
          </button>
        </div>
      </section>
    </TrainingBriefDialog>
  </div>
</template>

<script setup lang="ts">
import { computed, inject, onMounted, onUnmounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { showToast } from 'vant'
import { Grid, List } from '@element-plus/icons-vue'
import TrainingBriefDialog from '../components/TrainingBriefDialog.vue'
import SelectFilter from '../geeker-adapt/components/SelectFilter/index.vue'
import TrainingTaskCard from '../geeker-adapt/components/TrainingTaskCard.vue'
import request from '../utils/request'
import '../geeker-adapt/styles/student-hall.scss'

type SceneItem = {
  id: number
  name: string
  difficulty?: string
  estimated_minutes?: number | null
  description?: string
  dispatch_brief?: string | null
  first_impression?: string | null
  stages?: any[]
  has_active_session?: boolean
  active_session_id?: number | null
  active_session_is_empty?: boolean
  finished_session_id?: number | null
  final_score?: number | null
  training_status?: 'not_started' | 'in_progress' | 'evaluating' | 'completed'
  status_label?: string
}

type CaseItem = {
  id: number
  title: string
  case_type: string
  background: string
  created_at?: string
  train_count?: number
  scene_count?: number
  primary_difficulty?: string
  estimated_minutes_summary?: string | null
  core_items?: string[]
  scenes?: SceneItem[]
}

const router = useRouter()
const setMainScrollable = inject<(value: boolean) => void>('setMainScrollable')

const cases = ref<CaseItem[]>([])
const filteredCases = ref<CaseItem[]>([])
const caseTypes = ref<string[]>([])
const difficulties = ['低', '中', '高']
const selectedType = ref('')
const selectedDifficulty = ref('')
const selectedStatus = ref('')
const activeTaskTab = ref<'all' | 'active' | 'idle' | 'completed'>('all')
const sortBy = ref<'newest' | 'train_count' | 'title'>('newest')
const viewMode = ref<'grid' | 'list'>('grid')
const isLoadingCases = ref(false)
const loadError = ref('')
const loadingSceneId = ref<number | null>(null)
const showTrainingBrief = ref(false)
const activeCase = ref<CaseItem | null>(null)
const selectedSceneId = ref<number | null>(null)

onMounted(() => {
  setMainScrollable?.(false)
  fetchCases()
})

onUnmounted(() => {
  setMainScrollable?.(false)
})

const filterValues = computed(() => ({
  type: selectedType.value,
  status: selectedStatus.value,
  difficulty: selectedDifficulty.value,
}))

const filterData = computed(() => [
  {
    title: '案件类型',
    key: 'type',
    options: [{ label: '全部类型', value: '' }, ...caseTypes.value.map((type) => ({ label: type, value: type }))],
  },
  {
    title: '训练状态',
    key: 'status',
    options: [
      { label: '全部状态', value: '' },
      { label: '继续训练', value: 'active' },
      { label: '已完成训练', value: 'completed' },
      { label: '未开始', value: 'idle' },
    ],
  },
  {
    title: '案件难度',
    key: 'difficulty',
    options: [{ label: '全部难度', value: '' }, ...difficulties.map((item) => ({ label: item, value: item }))],
  },
])

const sceneFilterStatus = computed<'active' | 'completed' | 'idle' | ''>(() => (
  activeTaskTab.value === 'all' ? (selectedStatus.value as 'active' | 'completed' | 'idle' | '') : activeTaskTab.value
))

const resultSummary = computed(() => {
  const sceneCount = displayCases.value.reduce((total, caseItem) => total + (caseItem.scenes?.length || 0), 0)
  return `筛选结果（${sceneCount} 个场景 / ${displayCases.value.length} 个案件）`
})

const displayCases = computed(() => {
  let result = filteredCases.value
    .map((caseItem) => ({
      ...caseItem,
      scenes: getFilteredScenes(caseItem),
    }))
    .filter((caseItem) => (caseItem.scenes?.length || 0) > 0)

  if (sortBy.value === 'train_count') {
    result.sort((a, b) => Number(b.train_count || 0) - Number(a.train_count || 0))
  } else if (sortBy.value === 'title') {
    result.sort((a, b) => (a.title || '').localeCompare(b.title || '', 'zh-CN'))
  } else {
    result.sort((a, b) => {
      const ta = a.created_at ? new Date(a.created_at).getTime() : 0
      const tb = b.created_at ? new Date(b.created_at).getTime() : 0
      return tb - ta
    })
  }

  return result
})

const normalizeDifficulty = (value: string) => {
  const text = String(value || '').trim()
  if (['简单', '低'].includes(text)) return '低'
  if (['中等'].includes(text)) return '中'
  if (['困难', '高'].includes(text)) return '高'
  return text || '中'
}

const getVisibleScenes = (caseItem: CaseItem) => getFilteredScenes(caseItem)

const getFilteredScenes = (caseItem: CaseItem) => {
  const scenes = Array.isArray(caseItem?.scenes) ? caseItem.scenes : []
  return scenes.filter((scene) => {
    const difficultyMatched = !selectedDifficulty.value || normalizeDifficulty(scene.difficulty || '') === selectedDifficulty.value
    const statusMatched = !sceneFilterStatus.value || matchSceneStatus(scene, sceneFilterStatus.value)
    return difficultyMatched && statusMatched
  })
}

const getSceneTrainingStatus = (scene: SceneItem) => {
  if (scene.training_status) return scene.training_status
  if (scene.has_active_session) return 'in_progress'
  return 'not_started'
}

const matchSceneStatus = (scene: SceneItem, status: 'active' | 'completed' | 'idle') => {
  const sceneStatus = getSceneTrainingStatus(scene)
  if (status === 'active') return sceneStatus === 'in_progress' || sceneStatus === 'evaluating'
  if (status === 'completed') return sceneStatus === 'completed'
  return sceneStatus === 'not_started'
}

const getSceneStatusLabel = (scene: SceneItem) => {
  const status = getSceneTrainingStatus(scene)
  if (status === 'completed') return scene.final_score != null ? `已评分 ${scene.final_score}分` : '已完成训练'
  if (scene.status_label) return scene.status_label
  if (status === 'evaluating') return '评估中'
  if (status === 'in_progress') return '继续训练'
  return '未开始训练'
}

const getSceneActionLabel = (scene: SceneItem) => {
  const status = getSceneTrainingStatus(scene)
  if (status === 'evaluating') return '评估中'
  if (status === 'in_progress') return '继续训练'
  return '开始训练'
}

const activeSceneList = computed(() => activeCase.value ? getVisibleScenes(activeCase.value) : [])

const selectedScene = computed(() => activeSceneList.value.find((scene) => scene.id === selectedSceneId.value) || null)

const dialogConfirmText = computed(() => {
  if (!selectedScene.value) return '请选择场景'
  return getSceneActionLabel(selectedScene.value)
})

const openTrainingBrief = (caseItem: CaseItem) => {
  const scenes = getVisibleScenes(caseItem)
  if (!scenes.length) {
    showToast('该案件暂无可训练场景')
    return
  }
  activeCase.value = caseItem
  selectedSceneId.value = scenes.find((scene) => getSceneTrainingStatus(scene) !== 'evaluating')?.id || scenes[0].id
  showTrainingBrief.value = true
}

const closeTrainingBrief = () => {
  showTrainingBrief.value = false
  activeCase.value = null
  selectedSceneId.value = null
}

const confirmTrainingSelection = () => {
  const scene = selectedScene.value
  if (!scene) {
    showToast('请先选择训练场景')
    return
  }
  if (scene.training_status === 'evaluating') {
    showToast('该场景正在评估中，暂不能开始')
    return
  }
  startTraining(scene)
}

const getCaseStatus = (caseItem: CaseItem): 'active' | 'completed' | 'idle' => {
  const scenes = Array.isArray(caseItem?.scenes) ? caseItem.scenes : []
  if (!scenes.length) return 'idle'
  const statuses = scenes.map(getSceneTrainingStatus)
  if (statuses.every((status) => status === 'completed')) return 'completed'
  if (statuses.some((status) => status === 'in_progress' || status === 'evaluating' || status === 'completed')) return 'active'
  return 'idle'
}

const getCaseStatusLabel = (caseItem: CaseItem) => {
  const status = getCaseStatus(caseItem)
  if (status === 'active') return '继续训练'
  if (status === 'completed') return '已完成训练'
  return '未开始'
}

const viewSceneReview = (scene: SceneItem) => {
  const sessionId = Number(scene.finished_session_id || scene.active_session_id)
  if (!sessionId) {
    showToast('该场景暂无可查看的复盘记录')
    return
  }
  router.push(`/student/evaluation?session_id=${sessionId}`)
}

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

const onFilterChange = (values: Record<string, unknown>) => {
  selectedType.value = String(values.type ?? '')
  selectedStatus.value = String(values.status ?? '')
  selectedDifficulty.value = String(values.difficulty ?? '')
  activeTaskTab.value = selectedStatus.value ? (selectedStatus.value as 'active' | 'idle' | 'completed') : 'all'
  filterCases()
}

const filterCases = () => {
  let result = [...cases.value]

  if (selectedType.value) {
    result = result.filter((caseItem) => caseItem.case_type === selectedType.value)
  }

  filteredCases.value = result
}

watch(activeTaskTab, (value) => {
  const nextStatus = value === 'all' ? '' : value
  if (selectedStatus.value !== nextStatus) {
    selectedStatus.value = nextStatus
  }
})

const startTraining = async (scene: SceneItem) => {
  const sceneId = Number(scene?.id)
  if (!sceneId) {
    showToast('场景无效，请刷新后重试')
    return
  }
  if (loadingSceneId.value !== null) return

  loadingSceneId.value = sceneId
  try {
    const res: any = await request.post(`/training/start/${sceneId}`, null, { _skipErrorToast: true } as any)
    if (!res?.id) throw new Error('训练初始化失败，请稍后重试')

    if (scene?.has_active_session && scene?.active_session_id === res.id) {
      showToast('已恢复你上次未完成的训练')
    }
    closeTrainingBrief()
    router.push(`/student/training/${res.id}`)
  } catch (error: any) {
    showToast(error?.response?.data?.detail || error?.message || '训练环境初始化失败')
  } finally {
    loadingSceneId.value = null
  }
}
</script>

<style scoped lang="scss">
.tasks-panel {
  padding: 0;
  border: 1px solid rgb(255 255 255 / 58%);
  background:
    linear-gradient(135deg, rgb(255 255 255 / 56%), rgb(255 255 255 / 26%)),
    radial-gradient(circle at 8% 0%, rgb(59 130 246 / 10%), transparent 34%),
    radial-gradient(circle at 92% 12%, rgb(20 184 166 / 10%), transparent 30%);
  box-shadow: inset 0 1px 0 rgb(255 255 255 / 72%), 0 18px 42px rgb(15 23 42 / 8%);
  backdrop-filter: blur(18px) saturate(150%);
  -webkit-backdrop-filter: blur(18px) saturate(150%);
}

.tasks-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  padding: 8px 16px;
  border-bottom: 1px solid rgb(226 232 240 / 64%);
  flex-shrink: 0;
}

.task-tabs {
  :deep(.el-tabs__header) {
    margin-bottom: 0;
  }

  :deep(.el-tabs__nav-wrap::after) {
    display: none;
  }

  :deep(.el-tabs__item) {
    height: 40px;
    font-size: 13px;
    padding: 0 12px;
  }

  :deep(.el-tabs__item.is-active) {
    color: var(--student-accent, #0066ff);
    font-weight: 600;
  }

  :deep(.el-tabs__active-bar) {
    background: var(--student-accent, #0066ff);
  }
}

.tasks-controls {
  display: flex;
  align-items: center;
  gap: 8px;
}

.sort-select {
  width: 110px;
}

.view-toggle {
  display: flex;
  gap: 3px;
  padding: 2px;
  border-radius: 6px;
  background: #f3f4f6;
}

.view-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 26px;
  border: none;
  border-radius: 5px;
  background: transparent;
  color: #6b7280;
  cursor: pointer;

  &--active {
    background: #fff;
    color: var(--student-accent, #0066ff);
    box-shadow: 0 1px 2px rgb(0 0 0 / 8%);
  }
}

.task-grid--list-view {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 22px;
  justify-content: start;
  padding: 24px;

  &.task-grid--list {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }
}

.list-toolbar {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-shrink: 0;
}

.list-title {
  font-size: 14px;
  font-weight: 700;
  color: #111827;
}

.filter-card {
  border: 1px solid rgb(255 255 255 / 58%);
  background: rgb(255 255 255 / 54%);
  box-shadow: inset 0 1px 0 rgb(255 255 255 / 72%), 0 12px 28px rgb(15 23 42 / 6%);
  backdrop-filter: blur(16px) saturate(150%);
  -webkit-backdrop-filter: blur(16px) saturate(150%);
}

.state-panel {
  padding: 32px 16px;
  text-align: center;
}

.scene-picker {
  display: grid;
  gap: 12px;
}

.scene-picker__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;

  h3 {
    margin: 0;
    color: #111827;
    font-size: 14px;
    font-weight: 800;
  }

  span {
    color: #64748b;
    font-size: 12px;
    font-weight: 700;
  }
}

.scene-picker__list {
  display: grid;
  gap: 10px;
}

.scene-picker__item {
  display: grid;
  gap: 8px;
  width: 100%;
  padding: 13px 14px;
  border: 1px solid #e5e7eb;
  border-radius: 14px;
  background: #fff;
  color: #334155;
  cursor: pointer;
  text-align: left;
  transition: border-color 180ms ease, background 180ms ease, transform 180ms ease;

  &:hover {
    border-color: #93c5fd;
    background: #f8fafc;
  }

  &--active {
    border-color: #60a5fa;
    background: #eff6ff;
  }

  p {
    display: -webkit-box;
    margin: 0;
    overflow: hidden;
    color: #475569;
    font-size: 12px;
    line-height: 1.7;
    -webkit-box-orient: vertical;
    -webkit-line-clamp: 2;
    word-break: break-word;
  }
}

.scene-picker__title,
.scene-picker__meta {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
}

.scene-picker__title strong {
  min-width: 0;
  overflow: hidden;
  color: #111827;
  font-size: 14px;
  font-weight: 800;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.scene-picker__title span {
  flex: 0 0 auto;
  padding: 3px 8px;
  border-radius: 999px;
  background: #fef3c7;
  color: #b45309;
  font-size: 12px;
  font-weight: 800;
}

.scene-picker__meta {
  justify-content: flex-start;
  flex-wrap: wrap;
  color: #64748b;
  font-size: 12px;
  font-weight: 700;

  span {
    white-space: nowrap;
  }
}

.scene-picker__meta--active {
  color: #2563eb;
}

.scene-picker__meta--done {
  color: #059669;
}

.scene-picker__meta--idle {
  color: #64748b;
}

@media (max-width: 1400px) {
  .task-grid--list-view:not(.task-grid--list) {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }
}

@media (max-width: 960px) {
  .task-grid--list-view,
  .task-grid--list-view.task-grid--list,
  .task-grid--list-view:not(.task-grid--list) {
    grid-template-columns: 1fr;
  }
}
</style>
