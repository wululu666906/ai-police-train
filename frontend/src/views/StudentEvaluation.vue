<template>
  <div class="evaluation-page">
    <div v-if="loading" class="loading-state">
      <van-loading color="#165DFF" vertical>正在生成评分报告...</van-loading>
    </div>

    <div v-else-if="report" class="report-content">
      <!-- Score Header -->
      <div class="score-header">
        <div class="score-bg-icon">
          <van-icon name="medal-o" size="120" />
        </div>
        <p class="score-label">综合评分</p>
        <div class="score-number">{{ report.total_score }}</div>
        <div class="score-level">
          <van-tag 
            :color="getLevelColor(report.total_score)" 
            size="large" 
            round
          >
            {{ getLevel(report.total_score) }}
          </van-tag>
        </div>
      </div>

      <!-- Dimension Scores -->
      <section class="section">
        <h3 class="section-title">
          <span class="title-bar"></span>
          分项评分详情
        </h3>
        <div class="score-grid">
          <div v-for="s in report.scores" :key="s.dimension" class="score-card">
            <div class="score-card-header">
              <span class="dim-name">{{ s.dimension }}</span>
              <span class="dim-score" :class="getScoreClass(s.score, s.full_score)">
                {{ s.score }}<span class="dim-full">/{{ s.full_score }}</span>
              </span>
            </div>
            <div class="dim-bar-track">
              <div 
                class="dim-bar-fill"
                :class="getBarClass(s.score, s.full_score)"
                :style="{ width: (s.score / s.full_score * 100) + '%' }"
              ></div>
            </div>
            <p class="dim-reason">{{ s.reason }}</p>
          </div>
        </div>
      </section>

      <!-- Strengths & Improvements -->
      <div class="two-col">
        <section class="feedback-card strengths-card">
          <h3 class="feedback-title">
            <van-icon name="like-o" color="#00B42A" />
            表现亮点
          </h3>
          <ul class="feedback-list">
            <li v-for="item in report.strengths" :key="item">
              <span class="dot dot-green"></span>
              {{ item }}
            </li>
          </ul>
        </section>

        <section class="feedback-card improvements-card">
          <h3 class="feedback-title">
            <van-icon name="info-o" color="#FF7D00" />
            改进建议
          </h3>
          <ul class="feedback-list">
            <li v-for="item in report.improvements" :key="item">
              <span class="dot dot-orange"></span>
              {{ item }}
            </li>
          </ul>
        </section>
      </div>

      <!-- Expert Summary -->
      <section class="section" v-if="report.suggestions">
        <div class="expert-card">
          <van-icon name="comment-o" class="expert-icon" />
          <h3 class="expert-title">专家综合点评</h3>
          <p class="expert-text">{{ report.suggestions }}</p>
        </div>
      </section>

      <!-- Actions -->
      <div class="action-bar">
        <van-button 
          size="large" 
          class="btn-secondary"
          @click="router.push('/student/hall')"
        >
          返回训练大厅
        </van-button>
        <van-button 
          type="primary" 
          size="large" 
          class="btn-primary"
          @click="router.push('/student/history')"
        >
          查看训练历史
        </van-button>
      </div>
    </div>

    <!-- No Data -->
    <div v-else class="empty-state">
      <van-icon name="info-o" size="48" color="#C9CDD4" />
      <p>暂无评分数据</p>
      <van-button type="primary" size="small" @click="router.push('/student/hall')">
        前往训练大厅
      </van-button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'

const router = useRouter()
const report = ref<any>(null)
const loading = ref(true)

onMounted(() => {
  const data = localStorage.getItem('last_evaluation')
  if (data) {
    report.value = JSON.parse(data)
  }
  loading.value = false
})

const getLevel = (score: number) => {
  if (score >= 90) return '卓越'
  if (score >= 80) return '优秀'
  if (score >= 60) return '合格'
  return '需改进'
}

const getLevelColor = (score: number) => {
  if (score >= 85) return '#00B42A'
  if (score >= 60) return '#FF7D00'
  return '#F53F3F'
}

const getScoreClass = (score: number, full: number) => {
  const ratio = score / full
  if (ratio >= 0.85) return 'score-green'
  if (ratio >= 0.6) return 'score-orange'
  return 'score-red'
}

const getBarClass = (score: number, full: number) => {
  const ratio = score / full
  if (ratio >= 0.85) return 'bar-green'
  if (ratio >= 0.6) return 'bar-orange'
  return 'bar-red'
}
</script>

<style scoped>
.evaluation-page {
  max-width: 800px;
  margin: 0 auto;
  padding: 32px;
  font-family: 'PingFang SC', 'Microsoft YaHei', 'Inter', sans-serif;
}

.loading-state,
.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 100px 0;
  gap: 16px;
  color: #86909C;
}

/* Score Header */
.score-header {
  background: #0E2F56;
  border-radius: 6px;
  padding: 40px 0;
  text-align: center;
  position: relative;
  overflow: hidden;
  margin-bottom: 24px;
}

.score-bg-icon {
  position: absolute;
  right: -20px;
  top: -20px;
  color: rgba(255, 255, 255, 0.05);
}

.score-label {
  font-size: 13px;
  color: rgba(255, 255, 255, 0.5);
  letter-spacing: 2px;
  text-transform: uppercase;
  margin: 0 0 8px;
}

.score-number {
  font-size: 64px;
  font-weight: 800;
  color: white;
  line-height: 1;
  margin-bottom: 12px;
}

.score-level {
  position: relative;
  z-index: 1;
}

/* Section */
.section {
  margin-bottom: 24px;
}

.section-title {
  font-size: 16px;
  font-weight: 600;
  color: #1D2129;
  margin: 0 0 16px;
  display: flex;
  align-items: center;
  gap: 8px;
}

.title-bar {
  width: 3px;
  height: 16px;
  background: #165DFF;
  border-radius: 2px;
}

/* Score Grid */
.score-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(340px, 1fr));
  gap: 12px;
}

.score-card {
  background: white;
  border-radius: 6px;
  padding: 16px 20px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
}

.score-card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 10px;
}

.dim-name {
  font-size: 14px;
  font-weight: 600;
  color: #1D2129;
}

.dim-score {
  font-size: 18px;
  font-weight: 700;
}

.dim-full {
  font-size: 12px;
  font-weight: 400;
  color: #86909C;
}

.score-green { color: #00B42A; }
.score-orange { color: #FF7D00; }
.score-red { color: #F53F3F; }

.dim-bar-track {
  height: 6px;
  background: #F2F3F5;
  border-radius: 3px;
  overflow: hidden;
  margin-bottom: 10px;
}

.dim-bar-fill {
  height: 100%;
  border-radius: 3px;
  transition: width 1s ease;
}

.bar-green { background: #00B42A; }
.bar-orange { background: #FF7D00; }
.bar-red { background: #F53F3F; }

.dim-reason {
  font-size: 13px;
  color: #86909C;
  line-height: 1.6;
  margin: 0;
}

/* Two Column */
.two-col {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
  margin-bottom: 24px;
}

.feedback-card {
  background: white;
  border-radius: 6px;
  padding: 20px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
}

.strengths-card { border-top: 3px solid #00B42A; }
.improvements-card { border-top: 3px solid #FF7D00; }

.feedback-title {
  font-size: 14px;
  font-weight: 600;
  color: #1D2129;
  margin: 0 0 14px;
  display: flex;
  align-items: center;
  gap: 8px;
}

.feedback-list {
  list-style: none;
  padding: 0;
  margin: 0;
}

.feedback-list li {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  padding: 6px 0;
  font-size: 13px;
  color: #4E5969;
  line-height: 1.6;
}

.dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  margin-top: 7px;
  flex-shrink: 0;
}

.dot-green { background: #00B42A; }
.dot-orange { background: #FF7D00; }

/* Expert Card */
.expert-card {
  background: white;
  border-radius: 6px;
  padding: 24px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
  position: relative;
}

.expert-icon {
  position: absolute;
  right: 24px;
  top: 24px;
  font-size: 40px;
  color: #F2F3F5;
}

.expert-title {
  font-size: 14px;
  font-weight: 600;
  color: #1D2129;
  margin: 0 0 12px;
}

.expert-text {
  font-size: 14px;
  color: #4E5969;
  line-height: 1.8;
  margin: 0;
}

/* Actions */
.action-bar {
  display: flex;
  gap: 12px;
  padding: 24px 0;
}

.btn-secondary {
  flex: 1;
  border-radius: 4px !important;
  border: 1px solid #C9CDD4 !important;
  color: #4E5969 !important;
  background: white !important;
}

.btn-primary {
  flex: 1;
  border-radius: 4px !important;
  background: #165DFF !important;
  border: none !important;
}
</style>
