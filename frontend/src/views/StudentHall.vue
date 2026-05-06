<template>
  <div class="hall-page">
    <div class="page-header">
      <div class="header-content">
        <h1 class="page-title">训练大厅</h1>
        <p class="page-desc">选择案件开始模拟训练，提升警情处置与问询能力。</p>
      </div>
      <div class="header-search">
        <van-field
          v-model="searchText"
          placeholder="搜索案件名称..."
          left-icon="search"
          clearable
          class="search-input"
          @update:model-value="filterCases"
        />
      </div>
    </div>

    <div class="filter-bar">
      <div class="filter-group">
        <span class="filter-label">案件类型</span>
        <div class="filter-tags">
          <span class="filter-tag" :class="{ active: selectedType === '' }" @click="selectedType = ''; filterCases()">全部</span>
          <span
            v-for="t in caseTypes"
            :key="t"
            class="filter-tag"
            :class="{ active: selectedType === t }"
            @click="selectedType = t; filterCases()"
          >
            {{ t }}
          </span>
        </div>
      </div>
      <div class="filter-group">
        <span class="filter-label">难度</span>
        <div class="filter-tags">
          <span class="filter-tag" :class="{ active: selectedDifficulty === '' }" @click="selectedDifficulty = ''; filterCases()">全部</span>
          <span
            v-for="d in difficulties"
            :key="d"
            class="filter-tag"
            :class="{ active: selectedDifficulty === d, ['diff-' + d]: true }"
            @click="selectedDifficulty = d; filterCases()"
          >
            {{ d }}
          </span>
        </div>
      </div>
    </div>

    <div v-if="recentActiveScenes.length > 0" class="resume-panel">
      <div class="resume-panel-header">
        <div>
          <div class="resume-panel-title">最近未完成训练</div>
          <div class="resume-panel-desc">优先回到你还没完成的场景，避免重复创建新会话。</div>
        </div>
        <van-tag type="primary" plain size="medium">共 {{ recentActiveScenes.length }} 项</van-tag>
      </div>
      <div class="resume-list">
        <div
          v-for="scene in recentActiveScenes.slice(0, 3)"
          :key="scene.active_session_id || scene.id"
          class="resume-item"
        >
          <div class="resume-item-main">
            <div class="resume-item-title">{{ scene.case_title }}</div>
            <div class="resume-item-meta">
              <span>{{ scene.name }}</span>
              <span>会话 #{{ scene.active_session_id }}</span>
            </div>
          </div>
          <van-button
            type="primary"
            size="small"
            class="resume-btn"
            :loading="loadingSceneId === scene.id"
            :disabled="loadingSceneId !== null"
            @click="startTraining(scene)"
          >
            继续训练
          </van-button>
        </div>
      </div>
    </div>

    <div v-if="filteredCases.length > 0" class="card-grid">
      <div v-for="c in filteredCases" :key="c.id" class="case-card">
        <div class="card-header">
          <van-tag :type="getTypeColor(c.case_type) as any" plain size="medium">{{ c.case_type }}</van-tag>
          <span class="train-count">
            <van-icon name="star-o" class="train-count-icon" />
            已训练 {{ c.train_count }} 次
          </span>
        </div>

        <h3 class="card-title">{{ c.title }}</h3>

        <div class="card-section background-section">
          <div class="section-label">案件背景</div>
          <p class="card-desc">
            {{ c.background ? c.background.slice(0, 75) + (c.background.length > 75 ? '...' : '') : '系统正在等待更完整的案件背景...' }}
          </p>
        </div>

        <div class="card-section scenario-section">
          <div class="section-label">训练场景</div>
          <div class="scene-list">
            <div v-for="scene in getVisibleScenes(c).slice(0, 2)" :key="scene.id" class="scene-item">
              <div class="scene-info">
                <span class="scene-name">{{ scene.name }}</span>
              </div>
              <van-button
                type="primary"
                size="small"
                class="start-btn"
                :loading="loadingSceneId === scene.id"
                :disabled="loadingSceneId !== null"
                @click="startTraining(scene)"
              >
                {{ scene.has_active_session ? '继续训练' : '开始训练' }}
              </van-button>
            </div>
          </div>

          <div v-if="getVisibleScenes(c).length > 2" class="expand-trigger" @click="openExpandedDetail(c)">
            <div class="expand-icon-circle">
              <van-icon name="arrow-down" />
            </div>
            <span class="expand-text">展开查看全部 {{ getVisibleScenes(c).length }} 个场景</span>
          </div>
        </div>
      </div>
    </div>

    <van-popup
      v-model:show="showExpanded"
      round
      class="immersive-modal"
      :overlay-style="{ backgroundColor: 'rgba(255,255,255,0.6)', backdropFilter: 'blur(12px)' }"
    >
      <div v-if="expandedCase" class="expanded-card">
        <div class="modal-close" @click="showExpanded = false">
          <van-icon name="cross" />
        </div>

        <div class="modal-header">
          <van-tag type="primary" plain size="large">{{ expandedCase.case_type }}</van-tag>
          <h2 class="modal-title">{{ expandedCase.title }}</h2>
        </div>

        <div class="modal-body">
          <div class="modal-section">
            <div class="section-label">完整案件背景</div>
            <p class="modal-desc">{{ expandedCase.background }}</p>
          </div>

          <div class="modal-section">
            <div class="section-label">全部训练场景（{{ getVisibleScenes(expandedCase).length }}）</div>
            <div class="modal-scene-list">
              <div v-for="scene in getVisibleScenes(expandedCase)" :key="scene.id" class="modal-scene-item">
                <div class="scene-left">
                  <span class="scene-name">{{ scene.name }}</span>
                  <van-tag :color="getDifficultyColor(scene.difficulty)" plain size="medium">{{ scene.difficulty }}</van-tag>
                </div>
                <van-button
                  type="primary"
                  size="small"
                  class="modal-start-btn"
                  :loading="loadingSceneId === scene.id"
                  :disabled="loadingSceneId !== null"
                  @click="startTraining(scene)"
                >
                  {{ scene.has_active_session ? '继续训练' : '开始训练' }}
                </van-button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </van-popup>

    <div v-if="filteredCases.length === 0" class="empty-state">
      <van-icon name="search" size="48" color="#C9CDD4" />
      <p>暂无符合条件的训练案件</p>
      <span>请调整筛选条件，或联系管理员补充案件。</span>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { showToast } from 'vant'
import request from '../utils/request'

const router = useRouter()

const cases = ref<any[]>([])
const filteredCases = ref<any[]>([])
const caseTypes = ref<string[]>([])
const difficulties = ['简单', '中等', '困难']
const searchText = ref('')
const selectedType = ref('')
const selectedDifficulty = ref('')
const loadingSceneId = ref<number | null>(null)

const showExpanded = ref(false)
const expandedCase = ref<any>(null)

const recentActiveScenes = computed(() =>
  cases.value
    .flatMap((caseItem: any) =>
      (caseItem.scenes || [])
        .filter((scene: any) => scene.has_active_session)
        .map((scene: any) => ({
          ...scene,
          case_id: caseItem.id,
          case_title: caseItem.title,
          case_type: caseItem.case_type
        }))
    )
    .sort((a: any, b: any) => (b.active_session_id || 0) - (a.active_session_id || 0))
)

const openExpandedDetail = (c: any) => {
  expandedCase.value = c
  showExpanded.value = true
}

const getVisibleScenes = (caseItem: any) => {
  const scenes = caseItem?.scenes || []
  if (!selectedDifficulty.value) return scenes
  return scenes.filter((scene: any) => scene.difficulty === selectedDifficulty.value)
}

const fetchCases = async () => {
  try {
    const [casesRes, typesRes]: any = await Promise.all([
      request.get('/student/cases'),
      request.get('/student/case-types')
    ])
    cases.value = casesRes || []
    caseTypes.value = typesRes || []
    filterCases()
  } catch (error) {
    showToast('获取训练案件失败')
  }
}

const filterCases = () => {
  let result = [...cases.value]

  if (searchText.value) {
    result = result.filter((c) => (c.title || '').includes(searchText.value))
  }

  if (selectedType.value) {
    result = result.filter((c) => c.case_type === selectedType.value)
  }

  if (selectedDifficulty.value) {
    result = result.filter((c) => getVisibleScenes(c).length > 0)
  }

  filteredCases.value = result
}

const startTraining = async (scene: any) => {
  const sceneId = scene?.id
  if (!sceneId) {
    showToast('无效的场景编号')
    return
  }
  if (loadingSceneId.value !== null) return

  loadingSceneId.value = sceneId
  try {
    const res: any = await request.post(`/training/start/${sceneId}`)
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

const getTypeColor = (type: string) => {
  const map: Record<string, string> = {
    邻里纠纷: 'primary',
    打架斗殴: 'danger',
    酒驾: 'warning',
    盗窃: 'success'
  }
  return map[type] || 'primary'
}

const getDifficultyColor = (diff: string) => {
  if (diff === '简单') return '#00B42A'
  if (diff === '困难') return '#F53F3F'
  return '#FF7D00'
}

onMounted(fetchCases)
</script>

<style scoped>
.hall-page {
  padding: 24px 32px;
  max-width: 1200px;
  margin: 0 auto;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-end;
  margin-bottom: 24px;
  gap: 16px;
}

.page-title {
  font-size: 24px;
  font-weight: 600;
  color: #1d2129;
  margin: 0;
}

.page-desc {
  font-size: 14px;
  color: #86909c;
  margin: 6px 0 0;
}

.search-input {
  width: 280px;
  border-radius: 8px;
  border: 1px solid #c9cdd4;
  overflow: hidden;
}

.filter-bar {
  display: flex;
  flex-wrap: wrap;
  gap: 24px;
  margin-bottom: 24px;
  padding: 16px 20px;
  background: white;
  border-radius: 12px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
}

.filter-group {
  display: flex;
  align-items: center;
  gap: 12px;
}

.filter-label {
  font-size: 13px;
  font-weight: 600;
  color: #4e5969;
}

.filter-tags {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
}

.filter-tag {
  padding: 4px 14px;
  border-radius: 999px;
  font-size: 13px;
  color: #4e5969;
  background: #f2f3f5;
  cursor: pointer;
  transition: all 0.2s;
  border: 1px solid transparent;
}

.filter-tag.active {
  color: #165dff;
  background: #e8f3ff;
  border-color: #b8d7ff;
}

.resume-panel {
  margin-bottom: 24px;
  padding: 20px;
  border-radius: 16px;
  background: linear-gradient(135deg, #f8fbff 0%, #eef5ff 100%);
  border: 1px solid #dbeafe;
}

.resume-panel-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 16px;
  margin-bottom: 16px;
}

.resume-panel-title {
  font-size: 18px;
  font-weight: 700;
  color: #1d3557;
}

.resume-panel-desc {
  margin-top: 6px;
  font-size: 13px;
  color: #5b6b7f;
}

.resume-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.resume-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 16px;
  padding: 14px 16px;
  background: rgba(255, 255, 255, 0.9);
  border-radius: 12px;
}

.resume-item-title {
  font-weight: 600;
  color: #1d2129;
}

.resume-item-meta {
  display: flex;
  gap: 12px;
  margin-top: 6px;
  font-size: 12px;
  color: #86909c;
}

.card-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
  gap: 20px;
}

.case-card {
  background: white;
  border-radius: 18px;
  padding: 20px;
  box-shadow: 0 4px 18px rgba(0, 0, 0, 0.06);
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.card-header,
.scene-item,
.modal-scene-item,
.scene-left {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
}

.train-count {
  font-size: 12px;
  color: #86909c;
  display: inline-flex;
  align-items: center;
  gap: 4px;
}

.card-title {
  margin: 0;
  font-size: 20px;
  line-height: 1.4;
  color: #1d2129;
}

.card-section {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.section-label {
  font-size: 12px;
  font-weight: 700;
  color: #86909c;
  letter-spacing: 0.08em;
}

.card-desc,
.modal-desc {
  margin: 0;
  color: #4e5969;
  line-height: 1.7;
}

.scene-list,
.modal-scene-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.scene-item,
.modal-scene-item {
  padding: 10px 12px;
  border-radius: 12px;
  background: #f7f8fa;
}

.scene-name {
  font-size: 14px;
  color: #1d2129;
  font-weight: 500;
}

.expand-trigger {
  margin-top: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  cursor: pointer;
  color: #165dff;
  font-size: 13px;
}

.expand-icon-circle {
  width: 24px;
  height: 24px;
  border-radius: 999px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #e8f3ff;
}

.immersive-modal {
  width: min(760px, calc(100vw - 32px));
  padding: 28px;
}

.expanded-card {
  position: relative;
}

.modal-close {
  position: absolute;
  top: -10px;
  right: -6px;
  cursor: pointer;
  color: #86909c;
}

.modal-header {
  margin-bottom: 20px;
}

.modal-title {
  margin: 12px 0 0;
  font-size: 28px;
  color: #1d2129;
}

.modal-body {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.modal-section {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 96px 0;
  gap: 10px;
  color: #86909c;
}

.empty-state p {
  font-size: 16px;
  color: #4e5969;
  margin: 0;
}

@media (max-width: 768px) {
  .hall-page {
    padding: 16px;
  }

  .page-header {
    flex-direction: column;
    align-items: stretch;
  }

  .search-input {
    width: 100%;
  }

  .resume-item,
  .scene-item,
  .modal-scene-item {
    flex-direction: column;
    align-items: stretch;
  }
}
</style>
