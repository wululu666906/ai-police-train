<template>
  <div class="student-page student-page--hall hall-page">
    <div class="hall-layout hall-layout--list">
      <section class="hall-hero">
        <div class="hall-hero__content">
          <span class="hall-hero__eyebrow">训练工作台</span>
          <h1>警情处置模拟训练</h1>
          <p>围绕案件脚本、现场角色和处置阶段开展 AI 对话训练，按场景继续、复盘或重新训练。</p>
          <div class="hall-hero__chips">
            <span>AI 对话</span>
            <span>多角色沟通</span>
            <span>处置复盘</span>
          </div>
        </div>
        <div class="hall-hero__metrics">
          <div class="hall-metric hall-metric--primary">
            <span class="hall-metric__label">可训练场景</span>
            <strong>{{ totalSceneCount }}</strong>
          </div>
          <div class="hall-metric">
            <span class="hall-metric__label">进行中</span>
            <strong>{{ activeSceneCount }}</strong>
          </div>
          <div class="hall-metric">
            <span class="hall-metric__label">已完成</span>
            <strong>{{ completedSceneCount }}</strong>
          </div>
          <div class="hall-metric">
            <span class="hall-metric__label">案件数</span>
            <strong>{{ totalCaseCount }}</strong>
          </div>
        </div>
      </section>

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
            <el-select v-model="sortBy" size="small" class="sort-select" :teleported="false">
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
        <div
          v-else-if="displayCases.length"
          class="task-grid task-grid--list-view"
          :class="{ 'task-grid--list': viewMode === 'list' }"
        >
          <TrainingTaskCard
            v-for="caseItem in displayCases"
            :key="caseItem.id"
            :case-item="caseItem"
            :status="getCaseStatus(caseItem)"
            :status-label="getCaseStatusLabel(caseItem)"
            :view-mode="viewMode"
            :loading-scene-id="loadingSceneId"
            :disabled="loadingSceneId !== null"
            @start-scene="startTraining"
            @view-review="viewSceneReview"
            @view-detail="openExpandedDetail(caseItem)"
          />
        </div>
        <div v-else class="state-panel">
          <el-empty description="暂无符合条件的训练案件" />
        </div>
      </section>
    </div>

    <van-popup
      v-model:show="showExpanded"
      round
      class="detail-popup"
      :overlay-style="{ backgroundColor: 'rgba(15, 23, 42, 0.24)', backdropFilter: 'blur(6px)' }"
    >
      <div v-if="expandedCase" class="detail-card">
        <div class="detail-header">
          <div>
            <el-tag type="primary" effect="plain">{{ expandedCase.case_type || '未分类' }}</el-tag>
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
                  <span>{{ normalizeDifficulty(scene.difficulty || '中') }}</span>
                  <span :class="scene.training_status === 'completed' ? 'meta-done' : scene.has_active_session ? 'meta-active' : 'meta-idle'">
                    {{ getSceneStatusLabel(scene) }}
                  </span>
                </div>
              </div>
              <div class="scene-actions">
                <template v-if="scene.training_status === 'completed'">
                  <el-button
                    plain
                    size="small"
                    :disabled="loadingSceneId !== null"
                    @click="viewSceneReview(scene)"
                  >
                    查看复盘
                  </el-button>
                  <el-button
                    type="primary"
                    size="small"
                    :loading="loadingSceneId === scene.id"
                    :disabled="loadingSceneId !== null"
                    @click="startTraining(scene)"
                  >
                    重新训练
                  </el-button>
                </template>
                <el-button
                  v-else
                  type="primary"
                  size="small"
                  :loading="loadingSceneId === scene.id"
                  :disabled="loadingSceneId !== null || scene.training_status === 'evaluating'"
                  @click="startTraining(scene)"
                >
                  {{ getSceneActionLabel(scene) }}
                </el-button>
              </div>
            </div>
          </div>
        </section>
      </div>
    </van-popup>
  </div>
</template>

<script setup lang="ts">
import { computed, inject, onMounted, onUnmounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { showToast } from 'vant'
import { Grid, List } from '@element-plus/icons-vue'
import SelectFilter from '../geeker-adapt/components/SelectFilter/index.vue'
import TrainingTaskCard from '../geeker-adapt/components/TrainingTaskCard.vue'
import request from '../utils/request'
import { fetchStudentCases, fetchStudentCaseTypes } from '../utils/studentCases'
import '../geeker-adapt/styles/student-hall.scss'

type SceneItem = {
  id: number
  name: string
  difficulty?: string
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
const showExpanded = ref(false)
const expandedCase = ref<CaseItem | null>(null)

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

const allScenes = computed(() => cases.value.flatMap((caseItem) => Array.isArray(caseItem.scenes) ? caseItem.scenes : []))
const totalCaseCount = computed(() => cases.value.length)
const totalSceneCount = computed(() => allScenes.value.length)
const activeSceneCount = computed(() => allScenes.value.filter((scene) => {
  const status = getSceneTrainingStatus(scene)
  return status === 'in_progress' || status === 'evaluating'
}).length)
const completedSceneCount = computed(() => allScenes.value.filter((scene) => getSceneTrainingStatus(scene) === 'completed').length)

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

const openExpandedDetail = (caseItem: CaseItem) => {
  expandedCase.value = caseItem
  showExpanded.value = true
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

function getSceneTrainingStatus(scene: SceneItem) {
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
    const casesRes = await fetchStudentCases()
    cases.value = casesRes
    caseTypes.value = await fetchStudentCaseTypes(casesRes)
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
    router.push(`/student/training/${res.id}`)
  } catch (error: any) {
    showToast(error?.response?.data?.detail || error?.message || '训练环境初始化失败')
  } finally {
    loadingSceneId.value = null
  }
}
</script>

<style scoped lang="scss">
.hall-page {
  color: #17213b;
}

.hall-hero {
  display: grid;
  grid-template-columns: minmax(0, 1.45fr) minmax(360px, 0.95fr);
  gap: 18px;
  min-height: 210px;
  overflow: hidden;
  border-radius: 8px;
  padding: 24px;
  background:
    linear-gradient(135deg, rgba(3, 28, 80, 0.96), rgba(24, 63, 168, 0.94)),
    #031c50;
  color: #fff;
  box-shadow: 0 14px 30px rgba(23, 56, 145, 0.16);
}

.hall-hero__content {
  display: flex;
  flex-direction: column;
  justify-content: center;
  min-width: 0;

  h1 {
    margin: 14px 0 10px;
    font-size: 30px;
    line-height: 1.16;
    font-weight: 800;
    letter-spacing: 0;
  }

  p {
    max-width: 640px;
    margin: 0;
    color: rgba(255, 255, 255, 0.78);
    font-size: 14px;
    line-height: 1.9;
  }
}

.hall-hero__eyebrow {
  display: inline-flex;
  align-items: center;
  width: fit-content;
  height: 28px;
  padding: 0 12px;
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.12);
  border: 1px solid rgba(255, 255, 255, 0.18);
  color: rgba(255, 255, 255, 0.86);
  font-size: 12px;
  font-weight: 700;
}

.hall-hero__chips {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 22px;

  span {
    display: inline-flex;
    align-items: center;
    height: 30px;
    padding: 0 12px;
    border-radius: 8px;
    background: rgba(255, 255, 255, 0.1);
    border: 1px solid rgba(255, 255, 255, 0.14);
    color: rgba(255, 255, 255, 0.84);
    font-size: 12px;
    font-weight: 600;
  }
}

.hall-hero__metrics {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
  align-content: center;
}

.hall-metric {
  min-height: 82px;
  border-radius: 8px;
  padding: 16px;
  background: rgba(255, 255, 255, 0.1);
  border: 1px solid rgba(255, 255, 255, 0.14);

  &--primary {
    background: rgba(255, 255, 255, 0.16);
  }
}

.hall-metric__label {
  display: block;
  color: rgba(255, 255, 255, 0.72);
  font-size: 12px;
}

.hall-metric strong {
  display: block;
  margin-top: 10px;
  font-size: 28px;
  line-height: 1;
  font-weight: 800;
}

.tasks-panel {
  padding: 0;
}

.tasks-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  padding: 4px 16px 0;
  border-bottom: 1px solid #edf0f5;
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
  gap: 14px;
  padding: 16px;

  &.task-grid--list {
    grid-template-columns: 1fr;
  }
}

.list-toolbar {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-shrink: 0;
  min-height: 24px;
}

.list-title {
  font-size: 14px;
  font-weight: 700;
  color: #253047;
}

.state-panel {
  padding: 32px 16px;
  text-align: center;
}

.detail-popup {
  width: min(820px, calc(100vw - 24px));
  max-height: calc(100vh - 32px);
  overflow: auto;
  background: transparent;
}

.detail-card {
  border-radius: 12px;
  background: #fff;
  padding: 24px;
  border: 1px solid #e5e7eb;
}

.detail-header {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  align-items: flex-start;

  h2 {
    margin: 12px 0 0;
    color: #111827;
  }
}

.detail-close {
  font-size: 22px;
  color: #9ca3af;
  cursor: pointer;
}

.detail-section + .detail-section {
  margin-top: 20px;
}

.detail-label {
  margin-bottom: 10px;
  font-size: 13px;
  font-weight: 700;
  color: #6b7280;
}

.detail-section p {
  margin: 0;
  color: #6b7280;
  line-height: 1.8;
}

.detail-scene-list {
  display: grid;
  gap: 8px;
}

.detail-scene-item {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  align-items: center;
  border-radius: 8px;
  background: #f8fafc;
  border: 1px solid #e5e7eb;
  padding: 10px 12px;
}

.scene-name {
  font-weight: 700;
  color: #1e293b;
  font-size: 14px;
}

.scene-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 4px;
  font-size: 12px;
  color: #9ca3af;
}

.meta-active {
  color: var(--student-accent, #0066ff);
}

.meta-done {
  color: #047857;
}

.meta-idle {
  color: #9ca3af;
}

@media (max-width: 1400px) {
  .task-grid--list-view:not(.task-grid--list) {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 960px) {
  .hall-hero {
    grid-template-columns: 1fr;
    padding: 20px;
  }

  .hall-hero__content h1 {
    font-size: 24px;
  }

  .hall-hero__metrics {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .task-grid--list-view:not(.task-grid--list) {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 640px) {
  .hall-hero__metrics {
    grid-template-columns: 1fr;
  }
}
</style>
