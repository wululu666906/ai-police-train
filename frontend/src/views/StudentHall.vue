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
            :type="getTypeColor(c.case_type) as any" 
            plain 
            size="medium"
          >{{ c.case_type }}</van-tag>
          <span class="train-count">
            <van-icon name="star-o" class="train-count-icon" />
            已训练 {{ c.train_count }} 次
          </span>
        </div>

        <h3 class="card-title">{{ c.title }}</h3>
        
        <!-- 案件背景区：固定高度防止跳变 -->
        <div class="card-section background-section">
          <div class="section-label">案情背景</div>
          <p class="card-desc">
            {{ c.background ? (c.background.slice(0, 75) + (c.background.length > 75 ? '...' : '')) : '系统正在等待详细剧本注入...' }}
          </p>
        </div>

        <!-- 训练科目区：模块化列表 -->
        <div class="card-section scenario-section">
          <div class="section-label">训练科目</div>
          <div class="scene-list">
            <!-- 仅在卡片内展示前3个科目，增加 null 检查防止崩溃 -->
            <div v-for="scene in (c.scenes || []).slice(0, 3)" :key="scene.id" class="scene-item">
              <div class="scene-info">
                <span class="scene-name">{{ scene.name }}</span>
              </div>
              <van-button 
                type="primary" 
                size="small" 
                class="start-btn"
                @click="startTraining(scene.id)"
              >
                开始训练
              </van-button>
            </div>
          </div>
          
          <!-- 如果科目多于3个，显示展开箭头 -->
          <div v-if="(c.scenes || []).length > 3" class="expand-trigger" @click="openExpandedDetail(c)">
             <div class="expand-icon-circle">
                <van-icon name="arrow-down" />
             </div>
             <span class="expand-text">查看全部 {{ c.scenes.length }} 个科目</span>
          </div>
        </div>
      </div>
    </div>

    <!-- 沉浸式详情弹窗 (背景模糊) -->
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
               <div class="section-label">案情完整背景</div>
               <p class="modal-desc">{{ expandedCase.background }}</p>
            </div>

            <div class="modal-section">
               <div class="section-label">全部训练科目 ({{ (expandedCase.scenes || []).length }})</div>
               <div class="modal-scene-list">
                  <div v-for="scene in (expandedCase.scenes || [])" :key="scene.id" class="modal-scene-item">
                     <div class="scene-left">
                        <span class="scene-name">{{ scene.name }}</span>
                        <van-tag :color="getDifficultyColor(scene.difficulty)" plain size="medium">{{ scene.difficulty }}</van-tag>
                     </div>
                     <van-button 
                        type="primary" 
                        size="small" 
                        class="modal-start-btn"
                        @click="startTraining(scene.id)"
                     >
                        开始训练
                     </van-button>
                  </div>
               </div>
            </div>
         </div>
      </div>
    </van-popup>

    <!-- Empty State -->
    <div v-if="filteredCases.length === 0" class="empty-state">
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
import { showToast } from 'vant'

const router = useRouter()

const cases = ref<any[]>([])
const filteredCases = ref<any[]>([])
const caseTypes = ref<string[]>([])
const searchText = ref('')
const selectedType = ref('')
const selectedDifficulty = ref('')
const loadingSceneId = ref<number | null>(null)

const showExpanded = ref(false)
const expandedCase = ref<any>(null)

const openExpandedDetail = (c: any) => {
  expandedCase.value = c
  showExpanded.value = true
}

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
  if (!sceneId) {
    showToast('无效的科目ID')
    return
  }
  loadingSceneId.value = sceneId
  console.log('正在启动训练，科目ID:', sceneId)
  
  try {
    const res: any = await request.post(`/training/start/${sceneId}`)
    console.log('训练会话创建成功:', res)
    
    if (res && res.id) {
      router.push(`/student/training/${res.id}`)
    } else {
      throw new Error('服务器未返回会话ID')
    }
  } catch (e: any) {
    console.error('启动训练失败详情:', e)
    const errorMsg = e?.response?.data?.detail || e.message || '训练环境部署失败'
    showToast(errorMsg)
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
  gap: 24px;
}

.case-card {
  background: white;
  border-radius: 12px;
  padding: 24px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.04);
  border: 1px solid #F2F3F5;
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  display: flex;
  flex-direction: column;
  height: 480px; /* 统一卡片高度 */
}

.case-card:hover {
  transform: translateY(-4px);
  border-color: #165DFF;
  box-shadow: 0 12px 24px rgba(22, 93, 255, 0.08);
}

.card-title {
  font-size: 20px;
  font-weight: 800;
  color: #1D2129;
  margin: 0 0 16px;
  line-height: 1.2;
}

.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.train-count {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 14px;
  color: #4E5969;
}

.train-count-icon {
  color: #165DFF;
  font-size: 16px;
}

.card-section {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.background-section {
  max-height: 120px;
  margin-bottom: 16px;
}

.scenario-section {
  position: relative;
  border-top: 1px dashed #F2F3F5;
  padding-top: 16px;
}

.section-label {
  font-size: 11px;
  font-weight: 900;
  color: #C9CDD4;
  text-transform: uppercase;
  letter-spacing: 0.15em;
  margin-bottom: 12px;
}

.card-desc {
  font-size: 13px;
  color: #4E5969;
  line-height: 1.7;
  margin: 0;
  display: -webkit-box;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

/* Scene List */
.scene-list {
  background: #F7F8FA;
  border-radius: 12px;
  padding: 4px 12px 40px; /* 增加底部 padding，防止按钮被完全遮挡 */
}

.scene-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 0;
}

.scene-item + .scene-item {
  border-top: 1px solid #E5E6EB;
}

.scene-name {
  font-size: 14px;
  color: #1D2129;
  font-weight: 600;
}

/* Expand Button */
.expand-trigger {
  position: absolute;
  bottom: 0;
  left: 0;
  right: 0;
  height: 80px;
  background: linear-gradient(to top, white 20%, rgba(255,255,255,0));
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: flex-end;
  padding-bottom: 8px;
  pointer-events: none; /* 穿透遮罩层，让下层按钮可点击 */
}

.expand-icon-circle {
  width: 28px;
  height: 28px;
  background: white;
  border: 1px solid #E5E6EB;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #165DFF;
  box-shadow: 0 2px 6px rgba(0,0,0,0.05);
  transition: all 0.2s;
  margin-bottom: 4px;
  pointer-events: auto; /* 恢复图标的点击能力 */
  cursor: pointer;
}

.expand-trigger:hover .expand-icon-circle {
  background: #165DFF;
  color: white;
  transform: translateY(2px);
}

.expand-text {
  font-size: 11px;
  color: #86909C;
  font-weight: bold;
  pointer-events: auto; /* 恢复文字的点击能力 */
  cursor: pointer;
}

/* Immersive Modal */
.immersive-modal {
  width: 560px;
  max-height: 85vh;
  overflow: visible !important;
  background: white;
  box-shadow: 0 24px 48px rgba(0,0,0,0.15);
}

.expanded-card {
  padding: 40px;
  position: relative;
}

.modal-close {
  position: absolute;
  top: 20px;
  right: 20px;
  width: 32px;
  height: 32px;
  background: #F2F3F5;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #4E5969;
  cursor: pointer;
  transition: all 0.2s;
}

.modal-close:hover {
  background: #E5E6EB;
  color: #1D2129;
}

.modal-header {
  margin-bottom: 32px;
}

.modal-title {
  font-size: 28px;
  font-weight: 800;
  color: #1D2129;
  margin-top: 12px;
}

.modal-section {
  margin-bottom: 32px;
}

.modal-desc {
  font-size: 15px;
  color: #4E5969;
  line-height: 1.8;
}

.modal-scene-list {
  background: #F7F8FA;
  border-radius: 16px;
  padding: 8px 20px;
}

.modal-scene-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px 0;
}

.modal-scene-item + .modal-scene-item {
  border-top: 1px solid #E5E6EB;
}

.scene-left {
  display: flex;
  align-items: center;
  gap: 12px;
}

.modal-start-btn {
  background: #165DFF !important;
  border: none !important;
  padding: 0 20px !important;
  border-radius: 8px !important;
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

