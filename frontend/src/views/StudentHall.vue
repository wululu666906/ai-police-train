<template>
  <div class="hall-page">
    <section class="filter-bar">
      <label class="filter-field">
        <span>案件类型</span>
        <select v-model="selectedType" @change="filterCases">
          <option value="">全部类型</option>
          <option v-for="type in caseTypes" :key="type" :value="type">{{ type }}</option>
        </select>
      </label>
      <label class="filter-field">
        <span>训练状态</span>
        <select v-model="selectedStatus" @change="filterCases">
          <option value="">全部状态</option>
          <option value="active">进行中</option>
          <option value="completed">已完成</option>
          <option value="idle">未开始</option>
        </select>
      </label>
      <label class="filter-field">
        <span>难度</span>
        <select v-model="selectedDifficulty" @change="filterCases">
          <option value="">全部难度</option>
          <option v-for="difficulty in difficulties" :key="difficulty" :value="difficulty">{{ difficulty }}</option>
        </select>
      </label>
    </section>

    <section v-if="isLoadingCases" class="state-panel loading-state">
      <van-loading color="#165dff" vertical>正在加载训练案件...</van-loading>
    </section>

    <section v-else-if="loadError" class="state-panel empty-state">
      <van-icon name="warning-o" size="48" color="#F59E0B" />
      <p>训练案件加载失败</p>
      <span>{{ loadError }}</span>
      <van-button type="primary" size="small" class="retry-btn" @click="fetchCases">
        重新加载
      </van-button>
    </section>

    <section v-else-if="filteredCases.length" class="cases-panel">
      <div class="case-grid">
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
                    <span>{{ normalizeDifficulty(scene.difficulty || '中等') }}</span>
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
      </div>
    </section>

    <section v-else class="state-panel empty-state">
      <van-icon name="orders-o" size="48" color="#C9CDD4" />
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
                  <span>{{ normalizeDifficulty(scene.difficulty || '中等') }}</span>
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
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { showToast } from 'vant'
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
const selectedType = ref('')
const selectedDifficulty = ref('')
const selectedStatus = ref('')
const isLoadingCases = ref(false)
const loadError = ref('')
const loadingSceneId = ref<number | null>(null)
const showExpanded = ref(false)
const expandedCase = ref<CaseItem | null>(null)

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

const getVisibleScenes = (caseItem: CaseItem) => {
  const scenes = Array.isArray(caseItem?.scenes) ? caseItem.scenes : []
  if (!selectedDifficulty.value) return scenes
  return scenes.filter((scene) => normalizeDifficulty(scene.difficulty || '') === selectedDifficulty.value)
}

const getCaseStatus = (caseItem: CaseItem) => {
  const scenes = Array.isArray(caseItem?.scenes) ? caseItem.scenes : []
  if (scenes.some((scene) => scene.has_active_session)) return 'active'
  if (Number(caseItem.train_count || 0) > 0) return 'completed'
  return 'idle'
}

const getCaseStatusLabel = (caseItem: CaseItem) => {
  const status = getCaseStatus(caseItem)
  if (status === 'active') return '进行中'
  if (status === 'completed') return '已完成'
  return '未开始'
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

const filterCases = () => {
  let result = [...cases.value]

  if (selectedType.value) {
    result = result.filter((caseItem) => caseItem.case_type === selectedType.value)
  }

  if (selectedStatus.value) {
    result = result.filter((caseItem) => getCaseStatus(caseItem) === selectedStatus.value)
  }

  if (selectedDifficulty.value) {
    result = result.filter((caseItem) => getVisibleScenes(caseItem).length > 0)
  }

  filteredCases.value = result
}

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
    if (!res?.id) {
      throw new Error('训练初始化失败，请稍后重试')
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
  max-width: 1360px;
  margin: 0 auto;
  padding: 16px 28px 32px;
  background: #fff;
}

.filter-bar {
  display: flex;
  flex-wrap: wrap;
  gap: 16px 24px;
  align-items: center;
  padding: 14px 18px;
  border: 1px solid #e5e7eb;
  border-radius: 10px;
  background: #fff;
}

.filter-field {
  display: flex;
  align-items: center;
  gap: 10px;
}

.filter-field span {
  font-size: 13px;
  font-weight: 600;
  color: #475569;
  white-space: nowrap;
}

.filter-field select {
  min-width: 140px;
  height: 36px;
  border: 1px solid #d1d5db;
  border-radius: 6px;
  background: #fff;
  padding: 0 12px;
  color: #334155;
  font-size: 13px;
  outline: none;
}

.filter-field select:focus {
  border-color: #165dff;
}

.cases-panel {
  margin-top: 16px;
  padding-top: 4px;
  border-top: 1px solid #f1f5f9;
}

.case-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 16px;
}

.case-card {
  display: flex;
  flex-direction: column;
  gap: 12px;
  min-height: 292px;
  padding: 16px;
  border-radius: 10px;
  background: #fff;
  border: 1px solid #e5e7eb;
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
  color: #94a3b8;
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
  background: #eff6ff;
}

.status-completed {
  color: #047857;
  background: #ecfdf5;
}

.status-idle {
  color: #64748b;
  background: #f8fafc;
}

.case-title {
  margin: 0;
  font-size: 17px;
  font-weight: 800;
  color: #0f172a;
}

.case-background {
  margin: 0;
  color: #64748b;
  line-height: 1.65;
  min-height: 66px;
  font-size: 13px;
}

.scene-block {
  margin-top: auto;
}

.scene-block-title,
.detail-label {
  margin-bottom: 10px;
  font-size: 13px;
  font-weight: 700;
  color: #64748b;
}

.scene-list,
.detail-scene-list {
  display: grid;
  gap: 8px;
}

.scene-item,
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

.scene-main {
  min-width: 0;
  flex: 1;
}

.scene-actions {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  justify-content: flex-end;
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
  color: #94a3b8;
}

.meta-active {
  color: #165dff;
}

.meta-idle {
  color: #94a3b8;
}

.meta-empty {
  color: #c2410c;
}

.expand-trigger {
  width: 100%;
  margin-top: 10px;
  border: 1px dashed #cbd5e1;
  background: #fff;
  color: #165dff;
  border-radius: 8px;
  padding: 9px 12px;
  cursor: pointer;
  font-size: 13px;
}

.state-panel {
  margin-top: 16px;
  border-radius: 10px;
  background: #fff;
  border: 1px solid #e5e7eb;
  padding: 64px 20px;
  text-align: center;
}

.empty-state {
  color: #94a3b8;
}

.empty-state p {
  margin: 16px 0 8px;
  font-size: 16px;
  color: #475569;
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
}

.detail-header h2 {
  margin: 12px 0 0;
  color: #0f172a;
}

.detail-close {
  font-size: 22px;
  color: #94a3b8;
  cursor: pointer;
}

.detail-section + .detail-section {
  margin-top: 20px;
}

.detail-section p {
  margin: 0;
  color: #64748b;
  line-height: 1.8;
}

@media (max-width: 1100px) {
  .case-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 768px) {
  .hall-page {
    padding: 12px 14px 24px;
  }

  .filter-bar {
    flex-direction: column;
    align-items: stretch;
  }

  .filter-field {
    flex-direction: column;
    align-items: stretch;
  }

  .filter-field select {
    width: 100%;
    min-width: 0;
  }

  .case-grid {
    grid-template-columns: 1fr;
  }

  .scene-item,
  .detail-scene-item,
  .card-top {
    flex-direction: column;
    align-items: stretch;
  }
}
</style>
