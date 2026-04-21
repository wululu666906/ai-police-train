<template>
  <div class="hall-page">
    <!-- Page Header -->
    <div class="page-header">
      <div class="header-content">
        <h1 class="page-title">训练大厅</h1>
        <p class="page-desc">选择案件开始模拟训练，提升警情处置实战能力</p>
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

    <!-- Filter Bar -->
    <div class="filter-bar">
      <div class="filter-group">
        <span class="filter-label">案件类型</span>
        <div class="filter-tags">
          <span 
            class="filter-tag" 
            :class="{ active: selectedType === '' }"
            @click="selectedType = ''; filterCases()"
          >全部</span>
          <span 
            v-for="t in caseTypes" :key="t"
            class="filter-tag"
            :class="{ active: selectedType === t }"
            @click="selectedType = t; filterCases()"
          >{{ t }}</span>
        </div>
      </div>
      <div class="filter-group">
        <span class="filter-label">难度</span>
        <div class="filter-tags">
          <span 
            class="filter-tag"
            :class="{ active: selectedDifficulty === '' }"
            @click="selectedDifficulty = ''; filterCases()"
          >全部</span>
          <span 
            v-for="d in ['简单', '中等', '困难']" :key="d"
            class="filter-tag"
            :class="{ active: selectedDifficulty === d, ['diff-' + d]: true }"
            @click="selectedDifficulty = d; filterCases()"
          >{{ d }}</span>
        </div>
      </div>
    </div>

    <!-- Case Card Grid -->
    <div class="card-grid" v-if="filteredCases.length > 0">
      <div 
        v-for="c in filteredCases" 
        :key="c.id" 
        class="case-card"
      >
        <div class="card-header">
          <van-tag 
            :type="getTypeColor(c.case_type)" 
            plain 
            size="medium"
          >{{ c.case_type }}</van-tag>
          <span class="train-count">
            <van-icon name="chart-trending-o" />
            已训练 {{ c.train_count }} 次
          </span>
        </div>

        <h3 class="card-title">{{ c.title }}</h3>
        <p class="card-desc">{{ c.background?.slice(0, 80) }}{{ c.background?.length > 80 ? '...' : '' }}</p>

        <!-- Scenes List -->
        <div class="scene-list">
          <div 
            v-for="scene in c.scenes" 
            :key="scene.id" 
            class="scene-item"
          >
            <div class="scene-info">
              <span class="scene-name">{{ scene.name }}</span>
              <van-tag 
                :color="getDifficultyColor(scene.difficulty)" 
                plain 
                size="small"
                class="diff-tag"
              >
                {{ scene.difficulty }}
              </van-tag>
            </div>
            <van-button 
              type="primary" 
              size="small" 
              class="start-btn"
              @click="startTraining(scene.id)"
              :loading="loadingSceneId === scene.id"
            >
              开始训练
            </van-button>
          </div>
        </div>
      </div>
    </div>

    <!-- Empty State -->
    <div v-else class="empty-state">
      <van-icon name="search" size="48" color="#C9CDD4" />
      <p>暂无符合条件的训练案件</p>
      <span>请联系教官创建案件剧本</span>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import request from '../utils/request'
import { showToast, showLoadingToast } from 'vant'

const router = useRouter()

const cases = ref<any[]>([])
const filteredCases = ref<any[]>([])
const caseTypes = ref<string[]>([])
const searchText = ref('')
const selectedType = ref('')
const selectedDifficulty = ref('')
const loadingSceneId = ref<number | null>(null)

const fetchCases = async () => {
  try {
    const [casesRes, typesRes]: any = await Promise.all([
      request.get('/student/cases'),
      request.get('/student/case-types')
    ])
    cases.value = casesRes
    filteredCases.value = casesRes
    caseTypes.value = typesRes
  } catch (e) {
    showToast('获取训练案件失败')
  }
}

const filterCases = () => {
  let result = [...cases.value]
  
  if (searchText.value) {
    result = result.filter(c => c.title.includes(searchText.value))
  }

  if (selectedType.value) {
    result = result.filter(c => c.case_type === selectedType.value)
  }

  if (selectedDifficulty.value) {
    result = result.filter(c => 
      c.scenes.some((s: any) => s.difficulty === selectedDifficulty.value)
    )
  }

  filteredCases.value = result
}

const startTraining = async (sceneId: number) => {
  loadingSceneId.value = sceneId
  try {
    const res: any = await request.post(`/training/start/${sceneId}`)
    router.push(`/student/training/${res.id}`)
  } catch (e: any) {
    showToast(e?.response?.data?.detail || '训练环境部署失败')
  } finally {
    loadingSceneId.value = null
  }
}

const getTypeColor = (type: string) => {
  const map: Record<string, string> = {
    '邻里纠纷': 'primary',
    '打架斗殴': 'danger', 
    '酒驾': 'warning',
    '盗窃': 'success'
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

/* Page Header */
.page-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-end;
  margin-bottom: 24px;
}

.page-title {
  font-size: 24px;
  font-weight: 600;
  color: #1D2129;
  margin: 0;
}

.page-desc {
  font-size: 14px;
  color: #86909C;
  margin: 6px 0 0;
}

.search-input {
  width: 280px;
  border-radius: 4px;
  border: 1px solid #C9CDD4;
  overflow: hidden;
}

.search-input :deep(.van-field__control) {
  font-size: 14px;
}

/* Filter Bar */
.filter-bar {
  display: flex;
  gap: 32px;
  margin-bottom: 24px;
  padding: 16px 20px;
  background: white;
  border-radius: 6px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
}

.filter-label {
  font-size: 13px;
  font-weight: 600;
  color: #4E5969;
  margin-right: 12px;
}

.filter-group {
  display: flex;
  align-items: center;
}

.filter-tags {
  display: flex;
  gap: 6px;
}

.filter-tag {
  padding: 4px 14px;
  border-radius: 4px;
  font-size: 13px;
  color: #4E5969;
  background: #F2F3F5;
  cursor: pointer;
  transition: all 0.2s;
  border: 1px solid transparent;
}

.filter-tag:hover {
  color: #165DFF;
  background: #E8F3FF;
}

.filter-tag.active {
  color: #165DFF;
  background: #E8F3FF;
  border-color: #165DFF;
}

/* Card Grid */
.card-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(360px, 1fr));
  gap: 20px;
}

.case-card {
  background: white;
  border-radius: 6px;
  padding: 20px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
  border: 1px solid transparent;
  transition: all 0.2s;
}

.case-card:hover {
  border-color: #165DFF;
  box-shadow: 0 4px 16px rgba(22, 93, 255, 0.1);
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}

.train-count {
  font-size: 12px;
  color: #86909C;
  display: flex;
  align-items: center;
  gap: 4px;
}

.card-title {
  font-size: 18px;
  font-weight: 600;
  color: #1D2129;
  margin: 0 0 8px;
}

.card-desc {
  font-size: 13px;
  color: #86909C;
  line-height: 1.6;
  margin: 0 0 16px;
}

/* Scene List */
.scene-list {
  border-top: 1px solid #F2F3F5;
  padding-top: 12px;
}

.scene-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 0;
}

.scene-item + .scene-item {
  border-top: 1px dashed #F2F3F5;
}

.scene-info {
  display: flex;
  align-items: center;
  gap: 8px;
}

.scene-name {
  font-size: 14px;
  color: #4E5969;
  font-weight: 500;
}

.start-btn {
  background: #165DFF !important;
  border: none !important;
  border-radius: 4px !important;
  font-size: 13px !important;
}

/* Empty State */
.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 80px 0;
  color: #86909C;
}

.empty-state p {
  font-size: 15px;
  font-weight: 500;
  margin: 16px 0 4px;
  color: #4E5969;
}

.empty-state span {
  font-size: 13px;
}
</style>
